"""Vendor-level patterns (services/vendor_analyzer.py) and the remaining duplicate explanations."""

from datetime import date, timedelta

from schemas.duplicate import DuplicateWeights
from schemas.fraud import RuleConfig
from schemas.invoice import InvoiceSnapshot
from services.duplicate_detector import compare, explain
from services.vendor_analyzer import near_threshold_pattern, round_amount_pattern, split_clusters

from .factories import history

CONFIG = RuleConfig()
START = date(2026, 6, 1)


def invoices(amounts, spacing_days=20):
    return [history(i + 1, amount, START + timedelta(days=spacing_days * i)) for i, amount in enumerate(amounts)]


class TestNearThresholdPattern:
    def test_needs_enough_invoices(self):
        assert near_threshold_pattern(invoices([9500, 9600]), CONFIG) is None

    def test_below_the_share_is_quiet(self):
        # 1 of 4 (25%) just under 10,000: under the 30% share
        assert near_threshold_pattern(invoices([9500, 1200, 1300, 1100]), CONFIG) is None

    def test_many_near_threshold_invoices_are_flagged(self):
        signal = near_threshold_pattern(invoices([9500, 9700, 1200, 9900]), CONFIG)
        assert signal.type == "THRESHOLD_PROXIMITY"
        assert signal.severity == "MEDIUM"                       # 75% >= 50%
        assert signal.details["near_threshold_count"] == 3
        assert "3 of 4 recent invoices (75%)" in signal.message

    def test_exactly_at_the_threshold_counts_above_it_does_not(self):
        assert near_threshold_pattern(invoices([10000, 10000, 10001]), CONFIG).details["near_threshold_count"] == 2


class TestRoundAmountPattern:
    def test_needs_five_invoices(self):
        assert round_amount_pattern(invoices([1000, 2000, 3000, 4000]), CONFIG) is None

    def test_mostly_round_amounts_is_a_weak_indicator(self):
        signal = round_amount_pattern(invoices([1000, 2000, 3000, 1234.5, 4000]), CONFIG)
        assert (signal.type, signal.severity, signal.details["round_count"]) == ("ROUND_AMOUNT", "INFO", 4)

    def test_mostly_ordinary_amounts_is_quiet(self):
        assert round_amount_pattern(invoices([1000, 1234.5, 987.1, 1500.3, 2210.9]), CONFIG) is None


class TestSplitClusters:
    def test_groups_under_the_threshold_within_the_window(self):
        signal = split_clusters(invoices([9900, 9700, 9800], spacing_days=2), CONFIG)
        assert signal.type == "SPLIT_PURCHASE"
        assert signal.details["invoice_ids"] == [1, 2, 3]

    def test_same_amounts_spread_over_months_are_not_a_split(self):
        assert split_clusters(invoices([9900, 9700, 9800], spacing_days=30), CONFIG) is None


ORIGINAL = InvoiceSnapshot(id=12, invoice_number="INV-1001", vendor_id=4, vendor_name="ACME Corp", amount=5000,
                           invoice_date=date(2026, 9, 1), description="Software License")


def reasons(**overrides):
    candidate = InvoiceSnapshot(**{**ORIGINAL.model_dump(), "id": 50, **overrides})
    return explain(candidate, compare(candidate, ORIGINAL, DuplicateWeights()))


class TestDuplicateExplanations:
    def test_identical_number_and_date(self):
        found = reasons()
        assert "Same invoice number (INV-1001)" in found
        assert "Same invoice date" in found

    def test_almost_the_same_amount(self):
        assert any(r.startswith("Almost the same amount (4,990.00 vs 5,000.00") for r in reasons(amount=4990))

    def test_similar_vendor_name_without_a_shared_vendor_id(self):
        found = reasons(vendor_id=None, vendor_name="ACME Corporation")
        assert any("possible duplicate vendor record" in r for r in found)
        assert "Same vendor" not in found
