"""
Contract for the full analysis (POST /api/v1/fraud/analyze): the single call Django makes
per invoice. `config` carries ALL of Django's SystemSettings; unknown keys are ignored.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .duplicate import CandidateMatch, ComponentScores, DuplicateWeights
from .fraud import AnalysedInvoice, BankContext, HistoryInvoice, RuleConfig, Signal, VendorContext
from .invoice import InvoiceSnapshot
from .risk import RiskResult, ScoringConfig


class AnalysisConfig(RuleConfig, ScoringConfig):
    """Rule settings + scoring settings + duplicate settings in one object."""

    model_config = ConfigDict(extra="ignore")

    duplicate_weights: DuplicateWeights = Field(default_factory=DuplicateWeights)
    duplicate_date_window_days: int = Field(default=30, ge=1, le=365)


class FraudAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice: AnalysedInvoice
    vendor_context: VendorContext = Field(default_factory=VendorContext)
    bank: BankContext = Field(default_factory=BankContext)
    recent_vendor_invoices: list[HistoryInvoice] = Field(default_factory=list, max_length=500,
                                                         description="Same vendor, recent weeks (split / same-day checks)")
    duplicate_candidates: list[InvoiceSnapshot] = Field(default_factory=list, max_length=500,
                                                        description="Earlier invoices to compare for duplicates")
    config: AnalysisConfig = Field(default_factory=AnalysisConfig)


class DuplicateSummary(BaseModel):
    duplicate_score: int
    is_possible_duplicate: bool
    matched_invoice_id: int | None
    matched_invoice_number: str | None
    components: ComponentScores | None
    reasons: list[str]
    candidates: list[CandidateMatch]


class AnomalySummary(BaseModel):
    model_loaded: bool
    model_version: str | None = None
    anomaly_score: float | None = None
    is_anomaly: bool = False
    threshold: float | None = None
    reasons: list[str] = Field(default_factory=list)


class FraudAnalysisResponse(BaseModel):
    invoice_id: int | None
    risk_score: int
    risk_level: str
    summary: str
    explanation: list[str] = Field(description="Ready-to-display reasons, most important first")
    signals: list[Signal] = Field(description="Every signal with its full details, most important first")
    scoring: RiskResult
    duplicate: DuplicateSummary
    anomaly: AnomalySummary
    features: dict[str, float]
    routing_hints: dict[str, bool]
    warnings: list[str]
    analyzed_at: datetime
    disclaimer: str = "Risk indicators for human review. This analysis does not determine that an invoice is fraudulent."

