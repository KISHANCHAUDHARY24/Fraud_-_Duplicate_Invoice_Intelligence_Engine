"""Risk-scoring contract (docs/risk-scoring.md). Defaults equal Django's SystemSetting defaults."""

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .fraud import RiskLevel, Severity, SignalType


class SignalWeights(BaseModel):
    """Maximum points each signal type can add (points = weight x strength)."""

    model_config = ConfigDict(extra="forbid")

    DUPLICATE: int = Field(default=30, ge=0, le=100)
    BANK_ACCOUNT_CHANGE: int = Field(default=20, ge=0, le=100)
    SPLIT_PURCHASE: int = Field(default=20, ge=0, le=100)
    AMOUNT_ANOMALY: int = Field(default=15, ge=0, le=100)
    THRESHOLD_PROXIMITY: int = Field(default=15, ge=0, le=100)
    ML_ANOMALY: int = Field(default=15, ge=0, le=100)
    TIME_ANOMALY: int = Field(default=10, ge=0, le=100)
    VENDOR_ANOMALY: int = Field(default=10, ge=0, le=100)
    ROUND_AMOUNT: int = Field(default=5, ge=0, le=100)

    def weight(self, signal_type: SignalType) -> int:
        return getattr(self, signal_type.value)


class ScoreFloor(BaseModel):
    """If this signal is present with at least `min_strength`, the score is at least `min_score`."""

    model_config = ConfigDict(extra="forbid")

    min_strength: float = Field(ge=0, le=1)
    min_score: int = Field(ge=0, le=100)


def _default_floors():
    return {
        SignalType.DUPLICATE: ScoreFloor(min_strength=0.9, min_score=60),
        SignalType.BANK_ACCOUNT_CHANGE: ScoreFloor(min_strength=0.0, min_score=60),
        SignalType.SPLIT_PURCHASE: ScoreFloor(min_strength=0.0, min_score=30),
        # Added in Phase 16 (scripts/evaluate_hybrid.py): one strong signal alone must reach review.
        SignalType.ML_ANOMALY: ScoreFloor(min_strength=0.8, min_score=30),
        SignalType.AMOUNT_ANOMALY: ScoreFloor(min_strength=1.0, min_score=30),
    }


class RiskLevelThresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")

    medium: int = Field(default=30, ge=1, le=100)
    high: int = Field(default=60, ge=1, le=100)
    critical: int = Field(default=80, ge=1, le=100)

    @model_validator(mode="after")
    def increasing(self):
        if not self.medium < self.high < self.critical:
            raise ValueError("risk level thresholds must increase: medium < high < critical")
        return self

    def level_for(self, score: int) -> RiskLevel:
        if score >= self.critical:
            return RiskLevel.CRITICAL
        if score >= self.high:
            return RiskLevel.HIGH
        if score >= self.medium:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW


class ScoringConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    signal_weights: SignalWeights = Field(default_factory=SignalWeights)
    signal_floors: dict[SignalType, ScoreFloor] = Field(default_factory=_default_floors)
    risk_level_thresholds: RiskLevelThresholds = Field(default_factory=RiskLevelThresholds)


class SignalInput(BaseModel):
    """A signal for /risk/score: only type and strength are needed."""

    type: SignalType
    strength: float = Field(ge=0, le=1)
    message: str = ""
    severity: Severity = Severity.INFO


class ScoredSignal(BaseModel):
    type: SignalType
    strength: float
    weight: int
    points: int = Field(description="Rounded contribution; the points of all signals add up to the score (before a floor)")
    message: str


class AppliedFloor(BaseModel):
    signal_type: SignalType
    min_score: int
    reason: str


class RiskResult(BaseModel):
    risk_score: int = Field(ge=0, le=100)
    risk_level: RiskLevel
    points_total: int = Field(description="Sum of signal points before the cap of 100 and any floor")
    capped: bool
    floor_applied: AppliedFloor | None
    breakdown: list[ScoredSignal] = Field(description="Most important first")
    explanation: list[str]
    summary: str
    disclaimer: str = "The risk score is a risk indicator for human review. It is not a probability or a determination of fraud."


class RiskScoreRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signals: list[SignalInput] = Field(default_factory=list, max_length=50)
    config: ScoringConfig = Field(default_factory=ScoringConfig)
