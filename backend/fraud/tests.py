from django.db import IntegrityError, transaction
from django.test import TestCase

from common.test_utils import make_invoice

from .models import FraudAlert, FraudAnalysis, FraudSignal, SignalType


class FraudModelTests(TestCase):
    def setUp(self):
        self.invoice = make_invoice()
        self.analysis = FraudAnalysis.objects.create(
            invoice=self.invoice, risk_score=82, risk_level="CRITICAL", duplicate_score=94,
        )

    def test_signals_are_ordered_by_contribution(self):
        FraudSignal.objects.create(analysis=self.analysis, invoice=self.invoice,
                                   signal_type=SignalType.TIME_ANOMALY, points=10, message="Sunday 02:17")
        FraudSignal.objects.create(analysis=self.analysis, invoice=self.invoice,
                                   signal_type=SignalType.DUPLICATE, points=28, message="94% similar")
        self.assertEqual([s.points for s in self.analysis.signals.all()], [28, 10])

    def test_only_one_open_alert_per_invoice(self):
        FraudAlert.objects.create(invoice=self.invoice, primary_type=SignalType.DUPLICATE, severity="HIGH")
        with self.assertRaises(IntegrityError), transaction.atomic():
            FraudAlert.objects.create(invoice=self.invoice, primary_type=SignalType.DUPLICATE, severity="HIGH")

    def test_new_alert_allowed_after_previous_is_resolved(self):
        FraudAlert.objects.create(invoice=self.invoice, primary_type=SignalType.DUPLICATE, severity="HIGH",
                                  status=FraudAlert.Status.RESOLVED, outcome=FraudAlert.Outcome.CLEARED)
        FraudAlert.objects.create(invoice=self.invoice, primary_type=SignalType.SPLIT_PURCHASE, severity="MEDIUM")

    def test_resolved_alert_requires_a_human_outcome(self):
        with self.assertRaises(IntegrityError):
            FraudAlert.objects.create(invoice=self.invoice, primary_type=SignalType.DUPLICATE,
                                      severity="HIGH", status=FraudAlert.Status.RESOLVED)
