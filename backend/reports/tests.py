from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from approvals.models import Approval
from common.test_utils import make_invoice, make_user, make_vendor
from fraud.models import FraudAlert, FraudAnalysis, FraudSignal
from invoices.models import Invoice

from .dashboard import month_keys

Status = Invoice.ApprovalStatus


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


class MonthKeysTests(TestCase):
    def test_last_twelve_months_across_a_year_boundary(self):
        keys = month_keys(date(2026, 2, 15))
        self.assertEqual(len(keys), 12)
        self.assertEqual((keys[0], keys[-1]), ("2025-03", "2026-02"))


class DashboardSummaryTests(TestCase):
    def setUp(self):
        self.ap, self.other_ap = make_user("AP_OFFICER"), make_user("AP_OFFICER")
        self.manager = make_user("MANAGER", department="IT")
        self.admin = make_user("ADMIN")
        vendor = make_vendor(vendor_name="ACME Corp")
        today = timezone.localdate()
        self.approved = make_invoice(vendor=vendor, submitted_by=self.ap, amount=Decimal("1000"), invoice_date=today,
                                     approval_status=Status.APPROVED, risk_score=5, risk_level="LOW")
        self.blocked = make_invoice(vendor=vendor, submitted_by=self.ap, amount=Decimal("9900"), invoice_date=today,
                                    approval_status=Status.BLOCKED, risk_score=85, risk_level="CRITICAL")
        make_invoice(vendor=vendor, submitted_by=self.ap, amount=Decimal("500"))   # draft: not spending
        make_invoice(submitted_by=self.other_ap, amount=Decimal("7777"), approval_status=Status.APPROVED,
                     invoice_date=today - timedelta(days=40))
        analysis = FraudAnalysis.objects.create(invoice=self.blocked, risk_score=85, risk_level="CRITICAL")
        FraudSignal.objects.create(analysis=analysis, invoice=self.blocked, signal_type="DUPLICATE", points=30,
                                   message="98% similarity")
        FraudAlert.objects.create(invoice=self.blocked, analysis=analysis, primary_type="DUPLICATE", severity="CRITICAL")
        # invoice_date pinned to today: the monthly chart must not depend on the day of the month.
        pending = make_invoice(submitted_by=self.ap, department="IT", approval_status=Status.UNDER_REVIEW,
                               amount=Decimal("1250"), invoice_date=today, risk_score=40, risk_level="MEDIUM")
        Approval.objects.create(invoice=pending, level="MANAGER", assigned_to=self.manager)
        Approval.objects.create(invoice=self.approved, level="STANDARD", decision="APPROVED", decided_at=timezone.now())

    def summary(self, user):
        response = client_for(user).get("/api/dashboard/summary/")
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_ap_officer_sees_only_own_invoices(self):
        body = self.summary(self.ap)
        kpis = body["kpis"]
        self.assertEqual(kpis["total_invoices"], 4)
        # 1,000 approved + 9,900 blocked + 1,250 under review; the draft and the other officer's invoice excluded
        self.assertEqual(Decimal(str(kpis["total_spending"])), Decimal("12150"))
        self.assertEqual((kpis["suspicious_invoices"], kpis["possible_duplicates"], kpis["blocked_invoices"]), (2, 1, 1))
        self.assertEqual((kpis["pending_approvals"], kpis["pending_approvals_scope"]), (1, "my_invoices"))
        self.assertEqual([row["invoice_number"] for row in body["high_risk_invoices"]], [self.blocked.invoice_number])

    def test_admin_sees_everything(self):
        kpis = self.summary(self.admin)["kpis"]
        self.assertEqual(kpis["total_invoices"], 5)
        self.assertEqual((kpis["pending_approvals"], kpis["pending_approvals_scope"]), (1, "all"))

    def test_manager_pending_count_is_their_queue(self):
        kpis = self.summary(self.manager)["kpis"]
        self.assertEqual((kpis["pending_approvals"], kpis["pending_approvals_scope"]), (1, "mine"))

    def test_chart_series_have_fixed_shapes(self):
        body = self.summary(self.admin)
        self.assertEqual(len(body["monthly_spending"]), 12)
        self.assertEqual(len(body["alerts_over_time"]), 12)
        self.assertEqual(body["alerts_over_time"][-1]["count"], 1)
        self.assertEqual([r["level"] for r in body["risk_distribution"]], ["LOW", "MEDIUM", "HIGH", "CRITICAL", "NOT_ANALYZED"])
        self.assertEqual(len(body["status_distribution"]), 8)
        self.assertEqual(body["approval_trends"][-1]["APPROVED"], 1)
        self.assertEqual(body["vendor_risk"][0]["vendor_name"], "ACME Corp")
        current = body["monthly_spending"][-1]
        self.assertEqual(Decimal(str(current["total"])), Decimal("12150"))   # the 7,777 invoice is 40 days old

    def test_requires_login(self):
        self.assertEqual(APIClient().get("/api/dashboard/summary/").status_code, 401)
