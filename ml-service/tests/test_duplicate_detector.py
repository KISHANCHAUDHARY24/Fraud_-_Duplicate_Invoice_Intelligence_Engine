from datetime import date

import pytest

from schemas.duplicate import DuplicateCheckRequest, DuplicateWeights
from schemas.invoice import InvoiceSnapshot
from services.duplicate_detector import check, compare

ORIGINAL = dict(id=12, invoice_number="INV-1001", vendor_id=4, vendor_name="ACME Corp", amount=5000,
                invoice_date=date(2026, 9, 1), description="Software License")


def invoice(**overrides):
    return InvoiceSnapshot(**{**ORIGINAL, "id": 50, **overrides})


def score_against_original(**overrides):
    return compare(invoice(**overrides), InvoiceSnapshot(**ORIGINAL), DuplicateWeights()).score


class TestScenarios:
    """The documented examples (docs/duplicate-detection.md) with the default threshold of 80."""

    def test_documented_example_scores_high(self):
        score = score_against_original(invoice_number="INV1001", vendor_id=None, vendor_name="ACME Corporation",
                                       invoice_date=date(2026, 9, 3), description="Software licence")
        assert score >= 95

    def test_lookalike_number_is_flagged(self):
        assert score_against_original(invoice_number="INV-100I") >= 95

    def test_monthly_recurring_invoice_is_not_flagged(self):
        # Same vendor, amount and description, next number, one month later: normal billing.
        assert score_against_original(invoice_number="INV-1002", invoice_date=date(2026, 10, 1)) < 80

    def test_unrelated_invoice_scores_low(self):
        assert score_against_original(invoice_number="PO-7788", vendor_id=9, vendor_name="Initech", amount=120,
                                      invoice_date=date(2026, 6, 1), description="Catering") < 20


class TestCheck:
    def request(self, candidates, **kwargs):
        return DuplicateCheckRequest(invoice=invoice(invoice_number="INV1001", invoice_date=date(2026, 9, 3)),
                                     candidates=candidates, **kwargs)

    def test_best_match_and_explanations(self):
        result = check(self.request([
            InvoiceSnapshot(**{**ORIGINAL, "id": 7, "invoice_number": "INV-0555", "amount": 80}),
            InvoiceSnapshot(**ORIGINAL),
        ]))
        assert result.is_possible_duplicate
        assert result.matched_invoice_id == 12
        assert result.matched_invoice_number == "INV-1001"
        assert [c.invoice_id for c in result.candidates] == [12, 7]  # most similar first
        assert result.signals == [
            "Very similar invoice number (INV1001 vs INV-1001): identical apart from spaces or separators",
            "Same vendor",
            "Same amount (5,000.00 USD)",
            "Invoice dates 2 day(s) apart",
            "Very similar description (100% similar)",
        ]
        assert "not a confirmed duplicate" in result.disclaimer

    def test_below_threshold_is_not_a_possible_duplicate(self):
        result = self.request([InvoiceSnapshot(**ORIGINAL)], threshold=100)
        assert check(result).is_possible_duplicate is False

    def test_no_candidates(self):
        result = check(self.request([]))
        assert (result.duplicate_score, result.is_possible_duplicate, result.candidates_evaluated) == (0, False, 0)
        assert result.signals == []

    def test_invoice_is_never_compared_with_itself(self):
        itself = InvoiceSnapshot(**{**ORIGINAL, "id": 50})
        assert check(self.request([itself])).candidates_evaluated == 0

    def test_similar_vendor_record_is_explained(self):
        result = check(self.request([InvoiceSnapshot(**{**ORIGINAL, "vendor_id": 99, "vendor_name": "ACME Corporation"})]))
        assert any("possible duplicate vendor record" in reason for reason in result.signals)

    def test_custom_weights_change_the_score(self):
        candidate = InvoiceSnapshot(**{**ORIGINAL, "invoice_number": "ZZ-9999"})
        default = check(self.request([candidate])).duplicate_score
        number_heavy = check(self.request([candidate], weights=DuplicateWeights(
            invoice_number=0.9, vendor=0.025, amount=0.025, date=0.025, description=0.025))).duplicate_score
        assert number_heavy < default

    def test_weights_must_sum_to_one(self):
        with pytest.raises(ValueError, match="add up to 1.0"):
            DuplicateWeights(invoice_number=0.5, vendor=0.5, amount=0.5, date=0, description=0)
