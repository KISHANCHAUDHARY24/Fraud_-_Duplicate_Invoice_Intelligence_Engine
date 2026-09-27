"""Analytics endpoint and CSV/PDF report exports: permissions, scoping, figures, safety."""

import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from approvals.models import Approval
from audit.models import AuditLog
from common.test_utils import make_invoice, make_user, make_vendor
from fraud.models import FraudAlert, FraudAnalysis, FraudSignal
from invoices.models import Invoice
from vendors.services import add_bank_account

from .renderers import csv_safe

Status = Invoice.ApprovalStatus


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def read_csv(response):
    text = response.content.decode("utf-8")
    assert text.startswith("﻿"), "CSV must start with a BOM for Excel"
    return list(csv.reader(io.StringIO(text[1:])))


class ReportFixture(TestCase):
    def setUp(self):
        self.ap, self.other_ap = make_user("AP_OFFICER"), make_user("AP_OFFICER")
        self.manager, self.auditor, self.admin = make_user("MANAGER", department="IT"), make_user("AUDITOR"), make_user("ADMIN")
        self.today = timezone.localdate()
        self.vendor = make_vendor(vendor_name="ACME Corp")
        add_bank_account(self.vendor, "HDFC Bank", "111122223333")
        self.flagged = make_invoice(vendor=self.vendor, submitted_by=self.ap, amount=Decimal("9900"), invoice_date=self.today,
                                    approval_status=Status.UNDER_REVIEW, risk_score=70, risk_level="HIGH", department="IT",
                                    invoice_number="INV-1")
        self.normal = make_invoice(vendor=self.vendor, submitted_by=self.ap, amount=Decimal("100"), invoice_date=self.today,
                                   approval_status=Status.APPROVED, risk_score=0, risk_level="LOW", department="IT",
                                   invoice_number="INV-2")
        self.old = make_invoice(vendor=self.vendor, submitted_by=self.other_ap, amount=Decimal("5000"),
                                invoice_date=self.today - timedelta(days=400), approval_status=Status.APPROVED,
                                risk_score=5, risk_level="LOW", invoice_number="OLD-1")
        # A user-controlled value that a spreadsheet would run as a formula.
        self.evil = make_invoice(vendor=make_vendor(vendor_name="=HYPERLINK(\"http://x\",\"click\")"), submitted_by=self.ap,
                                 amount=Decimal("50"), invoice_date=self.today, approval_status=Status.APPROVED,
                                 invoice_number="EVIL-1", description="+SUM(A1:A9)")
        analysis = FraudAnalysis.objects.create(invoice=self.flagged, risk_score=70, risk_level="HIGH")
        FraudSignal.objects.create(analysis=analysis, invoice=self.flagged, signal_type="DUPLICATE", points=30, message="dup")
        FraudSignal.objects.create(analysis=analysis, invoice=self.flagged, signal_type="ROUND_AMOUNT", points=5, message="round")
        FraudAlert.objects.create(invoice=self.flagged, analysis=analysis, primary_type="DUPLICATE", severity="HIGH")
        FraudAlert.objects.create(invoice=self.normal, primary_type="ROUND_AMOUNT", severity="MEDIUM")
        now = timezone.now()
        Approval.objects.create(invoice=self.flagged, level="MANAGER", assigned_to=self.manager)
        human = Approval.objects.create(invoice=self.normal, level="MANAGER", assigned_to=self.manager,
                                        decision="APPROVED", decided_by=self.manager)
        Approval.objects.filter(pk=human.pk).update(created_at=now - timedelta(hours=6), decided_at=now)
        Approval.objects.create(invoice=self.evil, level="STANDARD", decision="APPROVED", decided_at=now)  # automatic


class AnalyticsTests(ReportFixture):
    def test_only_analytics_roles(self):
        self.assertEqual(client_for(self.ap).get("/api/analytics/").status_code, 403)
        self.assertEqual(client_for(self.manager).get("/api/analytics/").status_code, 200)

    def test_figures_for_the_default_last_twelve_months(self):
        body = client_for(self.admin).get("/api/analytics/").json()
        summary = body["summary"]
        self.assertEqual(summary["invoice_count"], 3)                 # OLD-1 is outside the range
        self.assertEqual(Decimal(str(summary["total_spending"])), Decimal("10050"))
        self.assertEqual(summary["alert_count"], 2)
        self.assertEqual(summary["duplicate_rate"], 50.0)             # 1 of 2 analysed invoices (EVIL-1 has no score)
        self.assertEqual(summary["auto_approval_rate"], 50.0)         # 1 automatic of 2 decisions
        self.assertEqual(summary["average_decision_hours"], 6.0)      # the human decision only
        self.assertEqual(len(body["monthly"]), 12)
        self.assertEqual(body["signal_frequency"][0]["type"], "DUPLICATE")
        self.assertEqual(body["department_spending"][0]["key"], "IT")

    def test_impossible_durations_are_ignored(self):
        broken = Approval.objects.create(invoice=self.flagged, level="AUDITOR", assigned_to=self.auditor,
                                         decision="REJECTED", decided_by=self.auditor)
        Approval.objects.filter(pk=broken.pk).update(decided_at=timezone.now() - timedelta(days=30))
        summary = client_for(self.admin).get("/api/analytics/").json()["summary"]
        self.assertEqual(summary["average_decision_hours"], 6.0)      # not pulled negative

    def test_date_filter_and_validation(self):
        client = client_for(self.admin)
        old = self.old.invoice_date.isoformat()
        body = client.get(f"/api/analytics/?date_from={old}&date_to={old}").json()
        self.assertEqual(body["summary"]["invoice_count"], 1)
        self.assertEqual(len(body["monthly"]), 1)
        bad = client.get("/api/analytics/?date_from=2026-13-01")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(bad.json()["error"]["code"], "VALIDATION_ERROR")
        reversed_range = client.get("/api/analytics/?date_from=2026-09-10&date_to=2026-09-01")
        self.assertIn("date_from", reversed_range.json()["error"]["details"])

    def test_scoped_to_visible_invoices(self):
        self.assertEqual(client_for(self.manager).get("/api/analytics/").json()["summary"]["invoice_count"], 2)  # IT, not EVIL


class ReportExportTests(ReportFixture):
    def test_report_list_per_role(self):
        types = lambda user: [row["type"] for row in client_for(user).get("/api/reports/").json()]  # noqa: E731
        self.assertEqual(types(self.manager), ["invoices", "approvals"])
        self.assertEqual(types(self.auditor), ["invoices", "fraud", "vendors", "approvals", "audit"])
        self.assertEqual(client_for(self.ap).get("/api/reports/").status_code, 403)

    def test_invoice_csv_is_scoped_safe_and_audited(self):
        response = client_for(self.admin).get("/api/reports/invoices/?format=csv")
        self.assertEqual(response.status_code, 200)
        self.assertIn('filename="expense-intelligence_invoices_', response["Content-Disposition"])
        rows = read_csv(response)
        self.assertEqual(rows[0][:4], ["Invoice", "Vendor", "Invoice date", "Amount"])
        numbers = {row[0] for row in rows[1:]}
        self.assertEqual(numbers, {"INV-1", "INV-2", "EVIL-1"})       # OLD-1 outside the default range
        evil = next(row for row in rows if row[0] == "EVIL-1")
        self.assertTrue(evil[1].startswith("'="))                    # formula neutralised
        self.assertTrue(evil[-1].startswith("'+"))
        entry = AuditLog.objects.get(action=AuditLog.Action.REPORT_EXPORTED)
        self.assertEqual((entry.entity_id, entry.new_value["rows"], entry.user_id), ("invoices", 3, self.admin.pk))

    def test_times_use_the_business_timezone(self):
        from datetime import datetime, timezone as dt_timezone

        from system_settings.models import SystemSetting
        SystemSetting.objects.update_or_create(key="timezone", defaults={"value": "Asia/Kolkata", "value_type": "STRING"})
        Invoice.objects.filter(pk=self.normal.pk).update(submission_date=datetime(2026, 9, 1, 6, 40, tzinfo=dt_timezone.utc))
        rows = read_csv(client_for(self.admin).get("/api/reports/invoices/?format=csv"))
        submitted = rows[0].index("Submitted at")
        self.assertEqual(next(row for row in rows if row[0] == "INV-2")[submitted], "2026-09-01 12:10")   # UTC+5:30

    def test_manager_export_contains_only_visible_invoices(self):
        rows = read_csv(client_for(self.manager).get("/api/reports/invoices/?format=csv"))
        self.assertEqual({row[0] for row in rows[1:]}, {"INV-1", "INV-2"})

    def test_pdf_export(self):
        response = client_for(self.auditor).get("/api/reports/fraud/?format=pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertEqual(response["X-Report-Rows"], "2")

    def test_vendor_report_is_not_inflated_by_joins(self):
        FraudAlert.objects.create(invoice=self.flagged, primary_type="DUPLICATE", severity="HIGH", status="DISMISSED")
        add_bank_account(self.vendor, "ICICI Bank", "999988887777")
        rows = read_csv(client_for(self.auditor).get("/api/reports/vendors/?format=csv"))
        acme = next(row for row in rows if row[0] == "ACME Corp")
        header = rows[0]
        self.assertEqual(acme[header.index("Invoices")], "2")
        self.assertEqual(acme[header.index("Spending")], "10000.00")   # counted once each (same rule as the dashboard)
        self.assertEqual(acme[header.index("Open alerts")], "2")
        self.assertEqual(acme[header.index("Pays to")], "ICICI Bank ****7777")   # masked

    def test_permissions_and_bad_parameters_return_json_errors(self):
        self.assertEqual(client_for(self.manager).get("/api/reports/audit/?format=csv").status_code, 403)
        self.assertEqual(client_for(self.ap).get("/api/reports/invoices/?format=csv").status_code, 403)
        unknown = client_for(self.admin).get("/api/reports/salaries/?format=csv")
        self.assertEqual(unknown.status_code, 404)
        self.assertEqual(unknown.json()["success"], False)
        bad_format = client_for(self.admin).get("/api/reports/invoices/?format=xml")
        self.assertEqual(bad_format.status_code, 400)
        self.assertIn("format", bad_format.json()["error"]["details"])


class DateRangeTests(TestCase):
    def test_default_is_twelve_whole_months(self):
        from datetime import date

        from .params import months_between, start_of_months_back
        self.assertEqual(start_of_months_back(date(2026, 9, 24), 12), date(2025, 10, 1))
        self.assertEqual(start_of_months_back(date(2026, 1, 31), 12), date(2025, 2, 1))
        self.assertEqual(len(months_between(date(2025, 10, 1), date(2026, 9, 24))), 12)


class CsvSafetyTests(TestCase):
    def test_formula_prefixes(self):
        self.assertEqual(csv_safe("=1+1"), "'=1+1")
        self.assertEqual(csv_safe("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(csv_safe("-12.50"), "-12.50")                # a negative number stays a number
        self.assertEqual(csv_safe("ACME"), "ACME")
        self.assertEqual(csv_safe({"a": 1}), '{"a": 1}')
