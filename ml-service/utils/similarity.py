"""
String and value similarity functions (docs/duplicate-detection.md §3-4).

Every function returns a float between 0.0 (nothing alike) and 1.0 (identical).
They are pure functions, with no framework code, so each one is easy to test and explain.
"""

import re
from datetime import date

from rapidfuzz import fuzz
from rapidfuzz.distance import JaroWinkler, Levenshtein

# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------
_INVOICE_SEPARATORS = re.compile(r"[\s\-_./#]")
_NON_ALNUM = re.compile(r"[^a-z0-9\s]")
_SPACES = re.compile(r"\s+")
_DIGITS = re.compile(r"\d+")

# Characters that are easily confused when typed or scanned: I/1, O/0, S/5 ...
OCR_LOOKALIKES = str.maketrans({"O": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2"})

# Same list as backend/common/text.py (kept in sync on purpose: the services share no code).
LEGAL_SUFFIXES = {
    "co", "company", "corp", "corporation", "inc", "incorporated",
    "llc", "llp", "ltd", "limited", "plc", "pvt", "private", "gmbh",
}


def normalize_invoice_number(value: str) -> str:
    """'inv-1001' / 'INV 1001' / 'INV_1001' -> 'INV1001'"""
    return _INVOICE_SEPARATORS.sub("", (value or "").upper())


def apply_lookalikes(value: str) -> str:
    """'INV100I' -> '1NV1001' (applied to BOTH numbers, so only confusable characters differ)."""
    return value.translate(OCR_LOOKALIKES)


def normalize_vendor_name(name: str) -> str:
    """'ACME Corp.' / 'ACME Corporation' / 'acme, inc.' -> 'acme'"""
    text = _NON_ALNUM.sub(" ", (name or "").lower())
    tokens = [token for token in _SPACES.split(text) if token]
    meaningful = [token for token in tokens if token not in LEGAL_SUFFIXES]
    return " ".join(meaningful or tokens)


def normalize_text(text: str) -> str:
    """Lower-case, punctuation removed, single spaces."""
    return _SPACES.sub(" ", _NON_ALNUM.sub(" ", (text or "").lower())).strip()


# ---------------------------------------------------------------------------
# Generic string measures
# ---------------------------------------------------------------------------
def levenshtein_similarity(a: str, b: str) -> float:
    """
    1 - (edits needed / length of the longer string).
    'INV1001' vs 'INV1002' -> 1 edit / 7 chars -> 0.857
    """
    if not a and not b:
        return 1.0
    return Levenshtein.normalized_similarity(a, b)


def jaro_winkler_similarity(a: str, b: str) -> float:
    """Counts matching characters and transpositions, with a bonus for a shared prefix."""
    if not a and not b:
        return 1.0
    return JaroWinkler.normalized_similarity(a, b)


def token_similarity(a: str, b: str) -> float:
    """Word-order-independent similarity: 'computer office equipment' ~ 'office computer equipment'."""
    if not a and not b:
        return 1.0
    return fuzz.token_sort_ratio(a, b) / 100


# ---------------------------------------------------------------------------
# Invoice-specific components
# ---------------------------------------------------------------------------
DIGIT_MISMATCH_PENALTY = 0.5  # sequential numbers (INV-1001 / INV-1002) are usually different invoices
SAME_DIGITS_FLOOR = 0.9       # 'INV-1001' vs 'ACME-1001': same number core with a different prefix


def invoice_number_similarity(a: str, b: str) -> tuple[float, str]:
    """
    Returns (score, reason).
      'INV-1001' vs 'INV1001'  -> 1.00  same after removing separators
      'INV-1001' vs 'INV-100I' -> 0.95  differ only by look-alike characters
      'INV-1001' vs 'INV-1002' -> 0.43  digits differ (sequential invoices are normally distinct)
    """
    na, nb = normalize_invoice_number(a), normalize_invoice_number(b)
    if not na or not nb:
        return 0.0, "missing invoice number"
    if na == nb:
        return 1.0, "identical apart from spaces or separators"
    la, lb = apply_lookalikes(na), apply_lookalikes(nb)
    if la == lb:
        return 0.95, "differ only by look-alike characters (e.g. I/1, O/0)"

    score = levenshtein_similarity(la, lb)
    # Digits come from the numbers BEFORE the look-alike mapping; otherwise the "I" in the
    # prefix "INV" would turn into a digit and 'INV1001' would not match 'ACME-1001'.
    digits_a, digits_b = "".join(_DIGITS.findall(na)), "".join(_DIGITS.findall(nb))
    if digits_a and digits_a == digits_b and len(digits_a) >= 3:
        return max(score, SAME_DIGITS_FLOOR), "same number with a different prefix"
    if digits_a != digits_b:
        score *= DIGIT_MISMATCH_PENALTY
    return score, "different invoice numbers"


def vendor_name_similarity(a: str, b: str) -> float:
    """
    Max of token similarity and Jaro-Winkler on normalised names. Jaro-Winkler is scaled by
    the length ratio so a short name ('acme') is not judged similar to a longer name that
    merely starts with it ('acme global solutions').
    """
    na, nb = normalize_vendor_name(a), normalize_vendor_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    length_ratio = min(len(na), len(nb)) / max(len(na), len(nb))
    return max(token_similarity(na, nb), jaro_winkler_similarity(na, nb) * length_ratio)


def description_similarity(a: str, b: str) -> float:
    """'Office computer equipment' vs 'Office computer equipments' -> ~0.98"""
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    return token_similarity(na, nb)


AMOUNT_TOLERANCE = 0.01
AMOUNT_STRICTNESS = 10  # 5% apart -> 0.5, 10% or more apart -> 0


def amount_similarity(a: float, b: float, currency_a: str = "USD", currency_b: str = "USD") -> float:
    """1.0 for the same amount; falls quickly as amounts diverge. Different currencies -> 0."""
    if currency_a != currency_b:
        return 0.0
    a, b = float(a), float(b)
    if abs(a - b) < AMOUNT_TOLERANCE:
        return 1.0
    largest = max(abs(a), abs(b))
    if largest == 0:
        return 1.0
    return max(0.0, 1 - (abs(a - b) / largest) * AMOUNT_STRICTNESS)


def date_similarity(a: date, b: date, window_days: int = 30) -> float:
    """Same day -> 1.0, half the window apart -> 0.5, window or more apart -> 0."""
    return max(0.0, 1 - abs((a - b).days) / window_days)
