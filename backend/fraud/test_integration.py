"""Payload building (fraud/context.py) and the HTTP client (fraud/ml_client.py)."""

import json
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

import requests
from django.test import TestCase, override_settings
from django.utils import timezone

from common.test_utils import fake_analysis, make_invoice, make_user, make_vendor
from invoices.models import Invoice
from system_settings.defaults import DEFAULT_SETTINGS
from vendors.services import add_bank_account

from . import ml_client
from .context import build_analysis_payload

Status = Invoice.ApprovalStatus


class PayloadTests(TestCase):
    def setUp(self):
        self.vendor = make_vendor(vendor_name="ACME Corp")
        self.ap = make_user(department="IT")
        base = timezone.now() - timedelta(days=60)
        # Three earlier, submitted invoices, one draft and one rejected invoice.
        for n, amount in enumerate([1000, 1200, 1400]):
            make_invoice(vendor=self.vendor, submitted_by=self.ap, amount=Decimal(amount),
                         invoice_date=date.today() - timedelta(days=40 - n), approval_status=Status.APPROVED,
                         submission_date=base + timedelta(days=n))
        make_invoice(vendor=self.vendor, submitted_by=self.ap, amount=Decimal("99999"), invoice_number="DRAFT-1",
                     submission_date=base)
        make_invoice(vendor=self.vendor, submitted_by=self.ap, amount=Decimal("5000"), invoice_number="REJ-1",
                     approval_status=Status.REJECTED, invoice_date=date.today() - timedelta(days=3),
                     submission_date=base)
        self.invoice = make_invoice(vendor=self.vendor, submitted_by=self.ap, amount=Decimal("5000"),
                                    invoice_number="NEW-1", department="IT", approval_status=Status.PROCESSING)

    def payload(self):
        return build_analysis_payload(self.invoice)

    def test_payload_is_json_and_has_every_section(self):
        payload = json.loads(json.dumps(self.payload()))   # must be plain JSON
        self.assertEqual(set(payload), {"invoice", "vendor_context", "bank", "recent_vendor_invoices",
                                        "duplicate_candidates", "config"})
        self.assertEqual(payload["invoice"]["invoice_number"], "NEW-1")
        self.assertIn("+00:00", payload["invoice"]["submission_datetime"])     # timezone-aware
        self.assertEqual(set(payload["config"]), set(DEFAULT_SETTINGS))

    def test_vendor_statistics_use_only_earlier_submitted_non_rejected_invoices(self):
        context = self.payload()["vendor_context"]
        self.assertEqual(context["vendor_invoice_count"], 3)                   # draft + rejected excluded
        self.assertAlmostEqual(context["vendor_avg_amount"], 1200)
        self.assertAlmostEqual(context["vendor_std_amount"], 163.299, places=2)  # population std, as in training

    def test_vendor_age_counts_from_first_invoice_when_older_than_the_record(self):
        # The vendor record was created today, but it has invoices from 40 days ago: not a "new vendor".
        self.assertGreaterEqual(self.payload()["vendor_context"]["vendor_age_days"], 38)

    def test_duplicate_candidates_include_rejected_but_not_drafts_or_self(self):
        numbers = {c["invoice_number"] for c in self.payload()["duplicate_candidates"]}
        self.assertIn("REJ-1", numbers)
        self.assertNotIn("DRAFT-1", numbers)
        self.assertNotIn("NEW-1", numbers)

    def test_similar_amount_from_other_vendor_is_a_candidate(self):
        other = make_vendor(vendor_name="Globex Ltd")
        make_invoice(vendor=other, submitted_by=self.ap, amount=Decimal("5100"), invoice_number="GX-9",
                     approval_status=Status.APPROVED)
        make_invoice(vendor=other, submitted_by=self.ap, amount=Decimal("50"), invoice_number="GX-10",
                     approval_status=Status.APPROVED)
        numbers = {c["invoice_number"] for c in self.payload()["duplicate_candidates"]}
        self.assertIn("GX-9", numbers)
        self.assertNotIn("GX-10", numbers)

    def test_bank_context_is_masked_and_detects_change(self):
        add_bank_account(self.vendor, "HDFC", "111122223333")
        new = add_bank_account(self.vendor, "ICICI", "444455556666")
        self.invoice.payment_bank_account = new
        self.invoice.save()
        bank = self.payload()["bank"]
        self.assertEqual((bank["current_account_masked"], bank["previous_account_masked"]), ("****6666", "****3333"))
        self.assertEqual(bank["current_account_age_days"], 0)
        self.assertNotIn("444455556666", json.dumps(self.payload()))

    def test_settings_changes_are_sent(self):
        from system_settings.models import SystemSetting
        SystemSetting.objects.filter(key="approval_threshold").update(value=25000)
        self.assertEqual(self.payload()["config"]["approval_threshold"], 25000)


@override_settings(FASTAPI_URL="http://ml.test", ML_SERVICE_API_KEY="k", ML_SERVICE_TIMEOUT=3)
class MLClientTests(TestCase):
    def response(self, status=200, body=None):
        fake = mock.Mock(status_code=status, text=json.dumps(body))
        fake.json.return_value = body
        return fake

    def test_success_sends_key_and_timeout(self):
        with mock.patch("fraud.ml_client.requests.post", return_value=self.response(body=fake_analysis())) as post:
            result = ml_client.analyze({"x": 1})
        self.assertEqual(result["risk_level"], "LOW")
        _, kwargs = post.call_args
        self.assertEqual(post.call_args[0][0], "http://ml.test/api/v1/fraud/analyze")
        self.assertEqual(kwargs["headers"], {"X-Internal-API-Key": "k"})
        self.assertEqual(kwargs["timeout"], 3)

    def test_failures_become_ml_service_error(self):
        cases = [
            (requests.ConnectionError(), "Cannot reach"),
            (requests.Timeout(), "did not answer within 3 seconds"),
            (self.response(401, {"success": False, "error": {"message": "Missing or invalid internal API key."}}), "(401)"),
            (self.response(200, {"unexpected": True}), "unexpected response"),
        ]
        for effect, fragment in cases:
            with self.subTest(fragment=fragment):
                patch = ({"side_effect": effect} if isinstance(effect, Exception) else {"return_value": effect})
                with mock.patch("fraud.ml_client.requests.post", **patch):
                    with self.assertRaises(ml_client.MLServiceError) as ctx:
                        ml_client.analyze({})
                self.assertIn(fragment, str(ctx.exception))

    @override_settings(ML_SERVICE_API_KEY="")
    def test_missing_key_is_reported(self):
        with self.assertRaises(ml_client.MLServiceError):
            ml_client.analyze({})

    def test_health_never_raises(self):
        with mock.patch("fraud.ml_client.requests.get", side_effect=requests.ConnectionError()):
            self.assertIsNone(ml_client.health())

