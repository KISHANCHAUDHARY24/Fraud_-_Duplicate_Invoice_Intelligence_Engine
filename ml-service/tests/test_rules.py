"""Each rule: fires when it should, stays silent at its boundaries, explains itself."""

from datetime import date, datetime

import pytest

from schemas.fraud import BankContext, RuleCheckRequest, RuleConfig, SignalType, VendorContext
from services import rule_engine as rules

from .factories import IST, SUNDAY_0217_IST, history, invoice

CONFIG = RuleConfig()


class TestApprovalThresholdRouting:
    def test_above_threshold(self):
        assert rules.above_approval_threshold(invoice(amount=10000.01), CONFIG)
        assert not rules.above_approval_threshold(invoice(amount=10000), CONFIG)


class TestDuplicateRule:
    def test_fires_at_threshold_with_match(self):
        signal = rules.duplicate_rule(80, CONFIG, match_id=12, match_number="INV-1001")
        assert signal.type == SignalType.DUPLICATE and signal.strength == 0.8
        assert signal.message == "80% similarity with invoice INV-1001" and signal.related_invoice_id == 12

    def test_silent_below_threshold(self):
        assert rules.duplicate_rule(79.9, CONFIG) is None


class TestBankChangeRule:
    def test_recent_change(self):
        signal = rules.bank_change_rule(BankContext(current_account_masked="****4821", current_account_age_days=30,
                                                    previous_account_masked="****1111"), CONFIG)
        assert signal.strength == 1.0 and signal.severity == "HIGH"
        assert "****1111 → ****4821" in signal.message

    def test_change_outside_window_is_silent(self):
        assert rules.bank_change_rule(BankContext(current_account_masked="****4821", current_account_age_days=31,
                                                  previous_account_masked="****1111"), CONFIG) is None

    def test_first_account_is_not_a_change(self):
        assert rules.bank_change_rule(BankContext(current_account_masked="****4821", current_account_age_days=2), CONFIG) is None

    def test_differs_from_last_paid_invoice(self):
        signal = rules.bank_change_rule(BankContext(current_account_masked="****4821", differs_from_last_paid=True,
                                                    last_paid_account_masked="****1111"), CONFIG)
        assert "differs from the account used" in signal.message


class TestTimeRule:
    def test_normal_working_time_is_silent(self):
        assert rules.time_rule(invoice(), CONFIG) is None

    def test_night_on_a_sunday_is_strong(self):
        signal = rules.time_rule(invoice(submission_datetime=SUNDAY_0217_IST), CONFIG)
        assert signal.strength == 1.0
        assert signal.message.startswith("Submitted Sunday 02:17 (Asia/Kolkata)")

    @pytest.mark.parametrize("moment, expected", [
        (datetime(2026, 9, 15, 7, 59, tzinfo=IST), 0.6),    # weekday, before hours
        (datetime(2026, 9, 15, 8, 0, tzinfo=IST), None),    # start is inside
        (datetime(2026, 9, 15, 18, 59, tzinfo=IST), None),
        (datetime(2026, 9, 15, 19, 0, tzinfo=IST), 0.6),    # end is outside
        (datetime(2026, 9, 19, 12, 0, tzinfo=IST), 0.6),    # Saturday noon
    ])
    def test_boundaries(self, moment, expected):
        signal = rules.time_rule(invoice(submission_datetime=moment), CONFIG)
        assert (signal.strength if signal else None) == expected

    def test_uses_configured_hours(self):
        late_shift = RuleConfig(working_hours={"start": "06:00", "end": "23:00"})
        assert rules.time_rule(invoice(submission_datetime=datetime(2026, 9, 15, 22, 0, tzinfo=IST)), late_shift) is None


class TestThresholdProximityRule:
    @pytest.mark.parametrize("amount, fires", [(8999.99, False), (9000, True), (9900, True), (10000, True), (10000.01, False)])
    def test_band(self, amount, fires):
        assert (rules.threshold_proximity_rule(invoice(amount=amount), CONFIG) is not None) is fires

    def test_closer_is_stronger_and_explained(self):
        near = rules.threshold_proximity_rule(invoice(amount=9900), CONFIG)
        far = rules.threshold_proximity_rule(invoice(amount=9200), CONFIG)
        assert near.strength > far.strength
        assert near.message == "Amount 9,900.00 is 1.0% below the approval threshold (10,000.00)"

    def test_band_is_configurable(self):
        assert rules.threshold_proximity_rule(invoice(amount=9200), RuleConfig(near_threshold_percent=5)) is None


class TestSplitPurchaseRule:
    SPLIT = dict(amount=9800, invoice_date=date(2026, 9, 4), description="Office computer equipment")

    def parts(self):
        return [history(1, 9900, date(2026, 9, 1)), history(2, 9700, date(2026, 9, 3))]

    def test_classic_split(self):
        signal = rules.split_purchase_rule(invoice(**self.SPLIT), self.parts(), CONFIG)
        assert signal.type == SignalType.SPLIT_PURCHASE
        assert signal.message.startswith("Potential Split Purchase: 3 invoices from ACME Corp")
        assert "29,400.00" in signal.message
        assert signal.details["related_invoice_ids"] == [1, 2]
        assert signal.strength == 1.0  # same department + similar description + total above threshold

    def test_needs_enough_other_invoices(self):
        assert rules.split_purchase_rule(invoice(**self.SPLIT), self.parts()[:1], CONFIG) is None
        assert rules.split_purchase_rule(invoice(**self.SPLIT), self.parts()[:1], RuleConfig(split_min_invoices=1)) is not None

    def test_invoices_outside_window_are_ignored(self):
        old = [history(1, 9900, date(2026, 8, 1)), history(2, 9700, date(2026, 8, 2))]
        assert rules.split_purchase_rule(invoice(**self.SPLIT), old, CONFIG) is None

    def test_small_or_above_threshold_amounts_do_not_count(self):
        small = [history(1, 900, date(2026, 9, 1)), history(2, 12000, date(2026, 9, 3))]
        assert rules.split_purchase_rule(invoice(**self.SPLIT), small, CONFIG) is None
        assert rules.split_purchase_rule(invoice(amount=12000, invoice_date=date(2026, 9, 4)), self.parts(), CONFIG) is None

    def test_weaker_when_departments_and_descriptions_differ(self):
        mixed = [history(1, 9900, date(2026, 9, 1), "Catering", "HR"), history(2, 9700, date(2026, 9, 3), "Travel", "Sales")]
        signal = rules.split_purchase_rule(invoice(**self.SPLIT), mixed, CONFIG)
        assert signal.strength == pytest.approx(0.7)  # base 0.6 + total above threshold
        assert signal.severity == "MEDIUM"

    def test_invoice_itself_in_history_is_ignored(self):
        itself = history(100, 9800, date(2026, 9, 4))
        assert rules.split_purchase_rule(invoice(**self.SPLIT), [itself, self.parts()[0]], CONFIG) is None


class TestRoundAmountRule:
    def test_round_and_not_round(self):
        signal = rules.round_amount_rule(invoice(amount=5000), CONFIG)
        assert signal.severity == "INFO" and "weak indicator" in signal.message
        assert rules.round_amount_rule(invoice(amount=5001), CONFIG) is None


class TestAmountAnomalyRule:
    VENDOR = VendorContext(vendor_invoice_count=20, vendor_avg_amount=1000, vendor_std_amount=200)

    def test_three_sigma_is_the_boundary(self):
        assert rules.amount_anomaly_rule(invoice(amount=1600), self.VENDOR) is None           # exactly 3σ
        assert rules.amount_anomaly_rule(invoice(amount=1601), self.VENDOR).strength == pytest.approx(0.5, abs=0.01)

    def test_extreme_amount_reports_true_sigma(self):
        signal = rules.amount_anomaly_rule(invoice(amount=6000), self.VENDOR)
        assert signal.strength == 1.0
        assert signal.message == "Amount 6,000.00 is 25.0σ above this vendor's average (1,000.00)"

    def test_low_amounts_are_not_flagged(self):
        assert rules.amount_anomaly_rule(invoice(amount=10), self.VENDOR) is None

    def test_falls_back_to_company_statistics_for_new_vendors(self):
        new_vendor = VendorContext(vendor_invoice_count=2, vendor_avg_amount=50, vendor_std_amount=5,
                                   company_avg_amount=2000, company_std_amount=500)
        signal = rules.amount_anomaly_rule(invoice(amount=9000), new_vendor)
        assert "the company average" in signal.message and signal.details["compared_with"] == "company"

    def test_constant_amounts_use_ratio(self):
        constant = VendorContext(vendor_invoice_count=12, vendor_avg_amount=1200, vendor_std_amount=0)
        assert "3.0x this vendor's usual amount" in rules.amount_anomaly_rule(invoice(amount=3600), constant).message
        assert rules.amount_anomaly_rule(invoice(amount=2000), constant) is None

    def test_no_statistics_no_signal(self):
        assert rules.amount_anomaly_rule(invoice(amount=99999), VendorContext()) is None


class TestVendorAnomalyRule:
    def test_clean_vendor(self):
        assert rules.vendor_anomaly_rule(VendorContext(vendor_age_days=400, invoices_last_30_days=2, avg_monthly_invoices=2)) is None

    def test_reasons_are_combined_strongest_first(self):
        signal = rules.vendor_anomaly_rule(VendorContext(confirmed_issue_count=1, vendor_age_days=10,
                                                         invoices_last_30_days=9, avg_monthly_invoices=2))
        assert signal.strength == 1.0 and signal.severity == "HIGH"
        assert signal.details["reasons"][0].startswith("vendor has 1 previously confirmed issue")
        assert len(signal.details["reasons"]) == 3

    @pytest.mark.parametrize("context, strength", [
        (VendorContext(open_alert_count=2), 0.6),
        (VendorContext(vendor_status="UNDER_REVIEW"), 0.6),
        (VendorContext(vendor_age_days=5), 0.5),
        (VendorContext(invoices_last_30_days=6, avg_monthly_invoices=2), 0.7),
    ])
    def test_individual_reasons(self, context, strength):
        assert rules.vendor_anomaly_rule(context).strength == strength

    def test_small_counts_are_not_a_spike(self):
        assert rules.vendor_anomaly_rule(VendorContext(invoices_last_30_days=2, avg_monthly_invoices=0.5)) is None


def test_evaluate_runs_every_rule():
    request = RuleCheckRequest(
        invoice=invoice(amount=9800, invoice_date=date(2026, 9, 4), submission_datetime=SUNDAY_0217_IST,
                        description="Office computer equipment"),
        bank=BankContext(current_account_masked="****4821", current_account_age_days=3, previous_account_masked="****1111"),
        recent_vendor_invoices=[history(1, 9900, date(2026, 9, 1)), history(2, 9700, date(2026, 9, 3))],
        duplicate_score=91, duplicate_match_id=1, duplicate_match_number="INV-1",
    )
    types = {signal.type for signal in rules.evaluate(request)}
    assert types == {SignalType.DUPLICATE, SignalType.BANK_ACCOUNT_CHANGE, SignalType.TIME_ANOMALY,
                     SignalType.THRESHOLD_PROXIMITY, SignalType.SPLIT_PURCHASE}
