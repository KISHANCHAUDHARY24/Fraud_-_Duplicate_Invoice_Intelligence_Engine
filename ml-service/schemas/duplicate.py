from pydantic import BaseModel, ConfigDict, Field, model_validator

from .invoice import InvoiceSnapshot

MAX_CANDIDATES = 500


class DuplicateWeights(BaseModel):
    """Weight of each similarity component. Must add up to 1.0 (docs/duplicate-detection.md §6)."""

    model_config = ConfigDict(extra="forbid")

    invoice_number: float = Field(default=0.30, ge=0, le=1)
    vendor: float = Field(default=0.25, ge=0, le=1)
    amount: float = Field(default=0.20, ge=0, le=1)
    date: float = Field(default=0.15, ge=0, le=1)
    description: float = Field(default=0.10, ge=0, le=1)

    @model_validator(mode="after")
    def weights_sum_to_one(self):
        total = self.invoice_number + self.vendor + self.amount + self.date + self.description
        if abs(total - 1) > 0.001:
            raise ValueError(f"weights must add up to 1.0 (got {total:.3f})")
        return self


class DuplicateCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice: InvoiceSnapshot
    candidates: list[InvoiceSnapshot] = Field(default_factory=list, max_length=MAX_CANDIDATES)
    weights: DuplicateWeights = Field(default_factory=DuplicateWeights)
    threshold: int = Field(default=80, ge=1, le=100, description="Score at or above which an invoice is a possible duplicate")
    date_window_days: int = Field(default=30, ge=1, le=365, description="Invoices this many days apart score 0 on date")


class ComponentScores(BaseModel):
    invoice_number: float
    vendor: float
    amount: float
    date: float
    description: float


class CandidateMatch(BaseModel):
    invoice_id: int | None
    invoice_number: str
    vendor_name: str
    score: int = Field(description="Combined similarity 0-100")
    components: ComponentScores


class DuplicateCheckResponse(BaseModel):
    duplicate_score: int = Field(description="Best combined similarity 0-100")
    is_possible_duplicate: bool
    matched_invoice_id: int | None
    matched_invoice_number: str | None
    components: ComponentScores | None = Field(description="Component scores of the best match")
    signals: list[str] = Field(description="Human-readable reasons for the best match")
    candidates: list[CandidateMatch] = Field(description="Top matches, most similar first")
    candidates_evaluated: int
    disclaimer: str = "A possible duplicate is a risk indicator for human review, not a confirmed duplicate."

    model_config = ConfigDict(json_schema_extra={"example": {
        "duplicate_score": 96, "is_possible_duplicate": True, "matched_invoice_id": 12,
        "matched_invoice_number": "INV-1001",
        "components": {"invoice_number": 1.0, "vendor": 1.0, "amount": 1.0, "date": 0.93, "description": 0.88},
        "signals": ["Very similar invoice number (INV1001 vs INV-1001): identical apart from spaces or separators",
                    "Same vendor", "Same amount (5,000.00 USD)", "Invoice dates 2 day(s) apart"],
        "candidates": [], "candidates_evaluated": 1,
        "disclaimer": "A possible duplicate is a risk indicator for human review, not a confirmed duplicate.",
    }})
