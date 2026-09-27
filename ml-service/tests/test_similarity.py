from datetime import date

import pytest

from utils import similarity as s


@pytest.mark.parametrize("raw, expected", [
    ("INV-1001", "INV1001"), ("inv 1001", "INV1001"), ("INV_1001", "INV1001"),
    ("INV/10.01#", "INV1001"), ("", ""),
])
def test_normalize_invoice_number(raw, expected):
    assert s.normalize_invoice_number(raw) == expected


@pytest.mark.parametrize("raw", ["ACME Corp", "ACME Corp.", "ACME Corporation", "ACME CORP", "acme, inc."])
def test_vendor_name_variants_normalise_to_same_value(raw):
    assert s.normalize_vendor_name(raw) == "acme"


def test_levenshtein_and_jaro_winkler_basics():
    assert s.levenshtein_similarity("INV1001", "INV1001") == 1.0
    assert s.levenshtein_similarity("INV1001", "INV1002") == pytest.approx(1 - 1 / 7)
    assert s.jaro_winkler_similarity("MARTHA", "MARHTA") == pytest.approx(0.961, abs=0.001)
    assert s.levenshtein_similarity("", "") == 1.0


def test_token_similarity_ignores_word_order():
    assert s.token_similarity("computer equipment office", "office computer equipment") == 1.0


class TestInvoiceNumberSimilarity:
    def test_formatting_differences_are_identical(self):
        assert s.invoice_number_similarity("INV-1001", "INV1001") == (1.0, "identical apart from spaces or separators")

    def test_lookalike_characters(self):
        score, reason = s.invoice_number_similarity("INV-1001", "INV-100I")
        assert score == 0.95 and "look-alike" in reason
        assert s.invoice_number_similarity("INV-10O1", "INV-1001")[0] == 0.95  # letter O vs zero

    def test_sequential_numbers_are_penalised(self):
        # Consecutive numbers are usually different invoices (e.g. monthly billing).
        assert s.invoice_number_similarity("INV-1001", "INV-1002")[0] < 0.5

    def test_same_digits_with_different_prefix(self):
        assert s.invoice_number_similarity("INV-1001", "ACME-1001") == (0.9, "same number with a different prefix")
        assert s.invoice_number_similarity("INV-1001", "1001")[0] == 0.9

    def test_unrelated_and_missing(self):
        assert s.invoice_number_similarity("INV-1001", "PO-7788")[0] < 0.2
        assert s.invoice_number_similarity("", "INV-1")[0] == 0.0


class TestVendorSimilarity:
    @pytest.mark.parametrize("other", ["ACME Corporation", "ACME CORP.", "acme inc"])
    def test_legal_suffix_variants_match(self, other):
        assert s.vendor_name_similarity("ACME Corp", other) == 1.0

    def test_typo_in_vendor_name_is_close(self):
        assert s.vendor_name_similarity("Microsoft", "Micros0ft") > 0.9

    def test_short_name_is_not_similar_to_longer_name_starting_with_it(self):
        assert s.vendor_name_similarity("ACME Corp", "ACME Global Solutions") < 0.5

    def test_different_vendors(self):
        assert s.vendor_name_similarity("ACME Corp", "Globex Ltd") < 0.5


def test_description_similarity():
    assert s.description_similarity("Office computer equipment", "Office computer equipments") > 0.95
    assert s.description_similarity("Software licence", "Catering services") < 0.5
    assert s.description_similarity("", "anything") == 0.0


@pytest.mark.parametrize("a, b, expected", [
    (5000, 5000, 1.0), (5000, 5000.004, 1.0), (5000, 4750, 0.5), (5000, 4500, 0.0), (5000, 100, 0.0),
])
def test_amount_similarity(a, b, expected):
    assert s.amount_similarity(a, b) == pytest.approx(expected)


def test_amounts_in_different_currencies_are_not_compared():
    assert s.amount_similarity(5000, 5000, "USD", "INR") == 0.0


@pytest.mark.parametrize("days_apart, expected", [(0, 1.0), (15, 0.5), (30, 0.0), (90, 0.0)])
def test_date_similarity(days_apart, expected):
    first = date(2026, 1, 1)
    second = date.fromordinal(first.toordinal() + days_apart)
    assert s.date_similarity(first, second) == pytest.approx(expected)
    assert s.date_similarity(second, first) == pytest.approx(expected)  # symmetric
