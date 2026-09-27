from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from audit.models import AuditLog
from common.test_utils import make_invoice, make_user, make_vendor

from .models import Invoice

YESTERDAY = str(date.today() - timedelta(days=1))
HEADER = "invoice_number,vendor,amount,invoice_date,description\n"


def csv_file(text, name="invoices.csv", encoding="utf-8"):
    return SimpleUploadedFile(name, text.encode(encoding), content_type="text/csv")


class CsvImportTests(TestCase):
    def setUp(self):
        self.ap = make_user("AP_OFFICER")
        self.client = APIClient()
        self.client.force_authenticate(self.ap)
        self.acme = make_vendor(vendor_name="ACME Corp", registration_number="REG-ACME")
        self.globex = make_vendor(vendor_name="Global Ltd")

    def upload(self, text, **kwargs):
        return self.client.post("/api/invoices/upload-csv/", {"file": csv_file(text, **kwargs)}, format="multipart")

    def test_valid_file_creates_all_invoices(self):
        response = self.upload(HEADER
                               + f"INV-1001,ACME Corp,5000,{YESTERDAY},Software License\n"
                               + f"INV-1002,Global Ltd,9900,{YESTERDAY},Hardware Purchase\n")
        body = response.json()
        self.assertEqual(response.status_code, 201, body)
        self.assertEqual((body["total_rows"], body["created"], body["failed"]), (2, 2, 0))
        self.assertEqual(Invoice.objects.filter(submitted_by=self.ap, approval_status="DRAFT").count(), 2)
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.INVOICE_UPLOADED).exists())

    def test_partial_success_reports_row_numbers(self):
        response = self.upload(HEADER
                               + f"INV-1,ACME Corp,5000,{YESTERDAY},Good row\n"
                               + f"INV-2,ACME Corp,abc,{YESTERDAY},Bad amount\n"
                               + f"INV-3,Nobody Inc,100,{YESTERDAY},Unknown vendor\n"
                               + "INV-4,ACME Corp,100,31/12/2025,Wrong date format\n")
        body = response.json()
        self.assertEqual((body["created"], body["failed"]), (1, 3))
        errors = {(e["row"], e["field"]) for e in body["errors"]}
        self.assertEqual(errors, {(3, "amount"), (4, "vendor"), (5, "invoice_date")})

    def test_vendor_matching_by_registration_number_and_equivalent_name(self):
        body = self.upload(HEADER
                           + f"R-1,REG-ACME,100,{YESTERDAY},By registration\n"
                           + f"R-2,ACME Corporation,100,{YESTERDAY},By equivalent name\n").json()
        self.assertEqual(body["created"], 2, body)
        self.assertEqual(Invoice.objects.filter(vendor=self.acme).count(), 2)

    def test_duplicates_inside_file_and_against_database(self):
        make_invoice(vendor=self.acme, invoice_number="EXISTING-1")
        body = self.upload(HEADER
                           + f"D-1,ACME Corp,100,{YESTERDAY},First\n"
                           + f"D-1,ACME Corp,100,{YESTERDAY},Same number again\n"
                           + f"EXISTING-1,ACME Corp,100,{YESTERDAY},Already in DB\n").json()
        self.assertEqual((body["created"], body["failed"]), (1, 2))
        self.assertIn("Duplicate of row 2", body["errors"][0]["message"])
        self.assertIn("already exists", body["errors"][1]["message"])

    def test_amount_formatting_and_optional_columns(self):
        body = self.upload("invoice_number,vendor,amount,invoice_date,description,currency,purchase_category,due_date\n"
                           f'X-1,ACME Corp,"$5,000.50",{YESTERDAY},Formatted amount,inr,office supplies,\n').json()
        self.assertEqual(body["created"], 1, body)
        invoice = Invoice.objects.get(invoice_number="X-1")
        self.assertEqual(str(invoice.amount), "5000.50")
        self.assertEqual((invoice.currency, invoice.purchase_category), ("INR", "OFFICE_SUPPLIES"))
        self.assertIsNone(invoice.due_date)

    def test_windows_excel_encoding_and_blank_lines(self):
        body = self.upload(HEADER + f"W-1,ACME Corp,100,{YESTERDAY},Café supplies\n\n,,,,\n", encoding="cp1252").json()
        self.assertEqual((body["total_rows"], body["created"]), (1, 1), body)

    def test_file_level_errors(self):
        cases = [
            (HEADER.replace(",description", ""), "INVALID_IMPORT_FILE", "description"),
            ("", "INVALID_IMPORT_FILE", "empty"),
            (HEADER, "INVALID_IMPORT_FILE", "no invoice rows"),
        ]
        for text, code, fragment in cases:
            with self.subTest(fragment=fragment):
                response = self.upload(text)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["error"]["code"], code)
                self.assertIn(fragment, response.json()["error"]["message"])

    def test_non_csv_file_and_missing_file(self):
        self.assertEqual(self.upload(HEADER, name="invoices.xlsx").status_code, 400)
        self.assertEqual(self.client.post("/api/invoices/upload-csv/", {}, format="multipart").status_code, 400)

    @override_settings(IMPORT_MAX_ROWS=2)
    def test_row_limit(self):
        rows = "".join(f"L-{i},ACME Corp,100,{YESTERDAY},Row {i}\n" for i in range(3))
        response = self.upload(HEADER + rows)
        self.assertEqual(response.status_code, 400)
        self.assertIn("Too many rows", response.json()["error"]["message"])

    def test_manager_cannot_import(self):
        client = APIClient()
        client.force_authenticate(make_user("MANAGER"))
        response = client.post("/api/invoices/upload-csv/", {"file": csv_file(HEADER)}, format="multipart")
        self.assertEqual(response.status_code, 403)

    def test_template_download(self):
        response = self.client.get("/api/invoices/csv-template/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(response.content.decode().startswith("invoice_number,vendor,amount,invoice_date,description"))


class JsonImportTests(TestCase):
    def setUp(self):
        self.ap = make_user("AP_OFFICER")
        self.client = APIClient()
        self.client.force_authenticate(self.ap)
        self.vendor = make_vendor(vendor_name="ACME Corp")

    def test_json_list_with_vendor_id_or_name(self):
        response = self.client.post("/api/invoices/upload-json/", [
            {"invoice_number": "J-1", "vendor": self.vendor.pk, "amount": 100, "invoice_date": YESTERDAY, "description": "By id"},
            {"invoice_number": "J-2", "vendor": "ACME Corp", "amount": "200.50", "invoice_date": YESTERDAY, "description": "By name"},
            {"invoice_number": "J-3", "vendor": "ACME Corp", "amount": 0, "invoice_date": YESTERDAY, "description": "Zero"},
            "not an object",
        ], format="json")
        body = response.json()
        self.assertEqual((body["total_rows"], body["created"], body["failed"]), (4, 2, 2), body)
        self.assertEqual({e["row"] for e in body["errors"]}, {3, 4})

    def test_wrapped_payload_and_invalid_payload(self):
        ok = self.client.post("/api/invoices/upload-json/", {"invoices": [
            {"invoice_number": "J-9", "vendor": "ACME Corp", "amount": 1, "invoice_date": YESTERDAY, "description": "Wrapped"}]},
            format="json")
        self.assertEqual(ok.json()["created"], 1)
        bad = self.client.post("/api/invoices/upload-json/", {"something": "else"}, format="json")
        self.assertEqual(bad.status_code, 400)
