"""
Contract for rule-based analysis. Django builds these objects from its database;
this service only computes. All business thresholds arrive in `config`
(the Admin-editable SystemSettings), so nothing is hard-coded here.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .invoice import InvoiceSnapshot


class SignalType(str, Enum):
    DUPLICATE = "DUPLICATE"
    AMOUNT_ANOMALY = "AMOUNT_ANOMALY"
    TIME_ANOMALY = "TIME_ANOMALY"
    THRESHOLD_PROXIMITY = "THRESHOLD_PROXIMITY"
    SPLIT_PURCHASE = "SPLIT_PURCHASE"
    BANK_ACCOUNT_CHANGE = "BANK_ACCOUNT_CHANGE"
    ROUND_AMOUNT = "ROUND_AMOUNT"
    VENDOR_ANOMALY = "VENDOR_ANOMALY"
    ML_ANOMALY = "ML_ANOMALY"


class RiskLevel(str, Enum):
    """Same values as Django's common.choices.RiskLevel."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Severity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Signal(BaseModel):
    """One explainable risk indicator. Points are assigned by the risk scorer (Phase 8)."""

    type: SignalType
    strength: float = Field(ge=0, le=1, description="How strongly the indicator applies, 0-1")
    severity: Severity
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    related_invoice_id: int | None = None


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
class WorkingHours(BaseModel):
    start: str = Field(default="08:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(default="19:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")

    @model_validator(mode="after")
    def start_before_end(self):
        if self.start >= self.end:
            raise ValueError("working_hours.start must be before working_hours.end")
        return self


class RuleConfig(BaseModel):
    """Business settings (same keys and defaults as Django's SystemSetting table)."""

    model_config = ConfigDict(extra="ignore")

    approval_threshold: float = Field(default=10000, gt=0)
    near_threshold_percent: float = Field(default=10, gt=0, le=50)
    working_hours: WorkingHours = Field(default_factory=WorkingHours)
    working_days: list[int] = Field(default=[0, 1, 2, 3, 4], min_length=1)
    timezone: str = "Asia/Kolkata"
    split_window_days: int = Field(default=7, ge=1, le=90)
    split_min_invoices: int = Field(default=2, ge=1, le=20)
    round_amount_base: int = Field(default=1000, ge=1)
    bank_change_window_days: int = Field(default=30, ge=1, le=365)
    duplicate_threshold: int = Field(default=80, ge=1, le=100)
    ml_anomaly_threshold: float = Field(default=0.6, ge=0, le=1)

    @field_validator("working_days")
    @classmethod
    def valid_days(cls, days):
        if any(day < 0 or day > 6 for day in days):
            raise ValueError("working_days must contain numbers 0 (Monday) to 6 (Sunday)")
        return sorted(set(days))

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, name):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError(f"unknown timezone '{name}'")
        return name


class AnalysedInvoice(InvoiceSnapshot):
    submission_datetime: datetime = Field(description="When the invoice was entered; must include a timezone offset",
                                          examples=["2026-09-20T20:47:00Z"])
    department: str = Field(default="", max_length=100)

    @field_validator("submission_datetime")
    @classmethod
    def must_be_timezone_aware(cls, value: datetime):
        if value.tzinfo is None:
            raise ValueError("submission_datetime must include a timezone, e.g. 2026-09-20T20:47:00Z")
        return value


class VendorContext(BaseModel):
    """Vendor statistics computed by Django from invoices BEFORE this one."""

    model_config = ConfigDict(extra="ignore")

    vendor_invoice_count: int = Field(default=0, ge=0)
    vendor_avg_amount: float | None = Field(default=None, ge=0)
    vendor_std_amount: float | None = Field(default=None, ge=0)
    company_avg_amount: float | None = Field(default=None, ge=0)
    company_std_amount: float | None = Field(default=None, ge=0)
    invoices_last_30_days: int = Field(default=0, ge=0)
    avg_monthly_invoices: float = Field(default=0, ge=0, description="Normal monthly invoice count for this vendor")
    days_since_previous_invoice: int | None = Field(default=None, ge=0)
    vendor_age_days: int | None = Field(default=None, ge=0)
    vendor_status: str = "ACTIVE"
    open_alert_count: int = Field(default=0, ge=0)
    confirmed_issue_count: int = Field(default=0, ge=0)


class BankContext(BaseModel):
    """Bank-account facts, prepared by Django from masked accounts (no full numbers ever sent)."""

    model_config = ConfigDict(extra="ignore")

    current_account_masked: str | None = Field(default=None, examples=["****4821"])
    current_account_age_days: int | None = Field(default=None, ge=0)
    previous_account_masked: str | None = Field(default=None, examples=["****1111"])
    differs_from_last_paid: bool = Field(default=False, description="Payment account differs from the one on the vendor's last paid invoice")
    last_paid_account_masked: str | None = None


class HistoryInvoice(InvoiceSnapshot):
    department: str = ""


class RuleCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice: AnalysedInvoice
    vendor_context: VendorContext = Field(default_factory=VendorContext)
    bank: BankContext = Field(default_factory=BankContext)
    recent_vendor_invoices: list[HistoryInvoice] = Field(default_factory=list, max_length=500,
                                                         description="Same vendor, recent weeks (for split / same-day checks)")
    config: RuleConfig = Field(default_factory=RuleConfig)
    duplicate_score: float = Field(default=0, ge=0, le=100, description="From /duplicate/check, if already run")
    duplicate_match_id: int | None = None
    duplicate_match_number: str | None = None


class RuleCheckResponse(BaseModel):
    signals: list[Signal]
    features: dict[str, float]
    routing_hints: dict[str, bool]
    rules_evaluated: list[str]
    disclaimer: str = "Signals are risk indicators for human review, not a determination of fraud."


class TopFeature(BaseModel):
    feature: str
    value: float
    z: float = Field(description="Standard deviations from normal training data")


class AnomalyResponse(BaseModel):
    model_version: str
    anomaly_score: float = Field(ge=0, le=1, description="0 = typical; 0.6 = among the most unusual 5% of history")
    is_anomaly: bool
    threshold: float
    reasons: list[str]
    top_features: list[TopFeature]
    signal: Signal | None
    disclaimer: str = "An anomaly is an unusual invoice, not proof of fraud. Many unusual invoices are legitimate."


class VendorAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_id: int | None = None
    vendor_name: str = Field(min_length=1, max_length=200)
    vendor_context: VendorContext = Field(default_factory=VendorContext)
    bank: BankContext = Field(default_factory=BankContext)
    recent_invoices: list[HistoryInvoice] = Field(default_factory=list, max_length=1000)
    config: RuleConfig = Field(default_factory=RuleConfig)


class VendorAnalysisResponse(BaseModel):
    vendor_id: int | None
    vendor_name: str
    indicators: list[Signal]
    indicator_count: int
    disclaimer: str = "Vendor indicators are prompts for review, not findings of wrongdoing."
