"""
Duplicate invoice detection (docs/duplicate-detection.md).

For each candidate invoice:
    5 component similarities (0-1)  x  configurable weights  ->  combined score 0-100
The best-scoring candidate is the match. If its score >= threshold the invoice is a
*possible* duplicate, and every strong component becomes a human-readable reason.
Nothing here decides that an invoice IS a duplicate. A person reviews it.
"""

from dataclasses import dataclass

from schemas.duplicate import (
    CandidateMatch, ComponentScores, DuplicateCheckRequest, DuplicateCheckResponse, DuplicateWeights,
)
from schemas.invoice import InvoiceSnapshot
from utils import similarity

TOP_CANDIDATES_RETURNED = 5

# A component at or above these values becomes an explanation.
EXPLAIN_NUMBER = 0.9
EXPLAIN_VENDOR = 0.85
EXPLAIN_DATE = 0.8
EXPLAIN_DESCRIPTION = 0.85
EXPLAIN_AMOUNT_CLOSE = 0.8


@dataclass
class Comparison:
    candidate: InvoiceSnapshot
    components: ComponentScores
    number_reason: str
    score: int


def compare(invoice: InvoiceSnapshot, candidate: InvoiceSnapshot, weights: DuplicateWeights,
            date_window_days: int = 30) -> Comparison:
    number_score, number_reason = similarity.invoice_number_similarity(invoice.invoice_number, candidate.invoice_number)
    same_vendor_record = invoice.vendor_id is not None and invoice.vendor_id == candidate.vendor_id
    components = ComponentScores(
        invoice_number=number_score,
        vendor=1.0 if same_vendor_record else similarity.vendor_name_similarity(invoice.vendor_name, candidate.vendor_name),
        amount=similarity.amount_similarity(invoice.amount, candidate.amount, invoice.currency, candidate.currency),
        date=similarity.date_similarity(invoice.invoice_date, candidate.invoice_date, date_window_days),
        description=similarity.description_similarity(invoice.description, candidate.description),
    )
    weighted = (
        weights.invoice_number * components.invoice_number
        + weights.vendor * components.vendor
        + weights.amount * components.amount
        + weights.date * components.date
        + weights.description * components.description
    )
    rounded = ComponentScores(**{name: round(value, 3) for name, value in components.model_dump().items()})
    return Comparison(candidate=candidate, components=rounded, number_reason=number_reason, score=round(weighted * 100))


def explain(invoice: InvoiceSnapshot, match: Comparison) -> list[str]:
    """Turn the strong components of the best match into plain-English reasons."""
    c, other = match.components, match.candidate
    reasons = []

    if c.invoice_number >= EXPLAIN_NUMBER:
        if invoice.invoice_number == other.invoice_number:
            reasons.append(f"Same invoice number ({other.invoice_number})")
        else:
            reasons.append(f"Very similar invoice number ({invoice.invoice_number} vs {other.invoice_number}): {match.number_reason}")

    if invoice.vendor_id is not None and invoice.vendor_id == other.vendor_id:
        reasons.append("Same vendor")
    elif c.vendor >= EXPLAIN_VENDOR:
        reasons.append(
            f"Vendor '{invoice.vendor_name}' is very similar to '{other.vendor_name}' "
            f"({round(c.vendor * 100)}% similar; possible duplicate vendor record)"
        )

    if c.amount == 1.0:
        reasons.append(f"Same amount ({other.amount:,.2f} {other.currency})")
    elif c.amount >= EXPLAIN_AMOUNT_CLOSE:
        reasons.append(f"Almost the same amount ({invoice.amount:,.2f} vs {other.amount:,.2f} {other.currency})")

    if c.date >= EXPLAIN_DATE:
        days = abs((invoice.invoice_date - other.invoice_date).days)
        reasons.append("Same invoice date" if days == 0 else f"Invoice dates {days} day(s) apart")

    if c.description >= EXPLAIN_DESCRIPTION:
        reasons.append(f"Very similar description ({round(c.description * 100)}% similar)")
    return reasons


def check(request: DuplicateCheckRequest) -> DuplicateCheckResponse:
    invoice = request.invoice
    comparisons = [
        compare(invoice, candidate, request.weights, request.date_window_days)
        for candidate in request.candidates
        # Never compare an invoice with itself.
        if not (invoice.id is not None and candidate.id == invoice.id)
    ]
    comparisons.sort(key=lambda comp: comp.score, reverse=True)
    top = [
        CandidateMatch(invoice_id=comp.candidate.id, invoice_number=comp.candidate.invoice_number,
                       vendor_name=comp.candidate.vendor_name, score=comp.score, components=comp.components)
        for comp in comparisons[:TOP_CANDIDATES_RETURNED]
    ]

    if not comparisons:
        return DuplicateCheckResponse(
            duplicate_score=0, is_possible_duplicate=False, matched_invoice_id=None, matched_invoice_number=None,
            components=None, signals=[], candidates=[], candidates_evaluated=0,
        )

    best = comparisons[0]
    return DuplicateCheckResponse(
        duplicate_score=best.score,
        is_possible_duplicate=best.score >= request.threshold,
        matched_invoice_id=best.candidate.id,
        matched_invoice_number=best.candidate.invoice_number,
        components=best.components,
        signals=explain(invoice, best),
        candidates=top,
        candidates_evaluated=len(comparisons),
    )
