"""
Risk scoring (docs/risk-scoring.md).

    points(signal) = round(weight[type] x strength)
    score          = min(100, sum of points)
    score          = max(score, escalation floors that apply)
    level          = LOW / MEDIUM / HIGH / CRITICAL from the configured thresholds

Points are rounded per signal first, so the "+28, +20, +14 ..." a reviewer sees on
screen add up exactly to the score (unless the cap or a floor applies, which is stated).
A risk score is an indicator for human review, NOT a probability of fraud.
"""

from schemas.fraud import Signal, SignalType
from schemas.risk import AppliedFloor, RiskResult, ScoredSignal, ScoringConfig, SignalInput

MAX_SCORE = 100

SIGNAL_LABELS = {
    SignalType.DUPLICATE: "Possible duplicate invoice",
    SignalType.BANK_ACCOUNT_CHANGE: "Vendor bank account change",
    SignalType.SPLIT_PURCHASE: "Potential split purchase",
    SignalType.AMOUNT_ANOMALY: "Unusual amount",
    SignalType.THRESHOLD_PROXIMITY: "Amount close to approval threshold",
    SignalType.ML_ANOMALY: "Unusual combination of features (ML)",
    SignalType.TIME_ANOMALY: "Unusual submission time",
    SignalType.VENDOR_ANOMALY: "Vendor risk",
    SignalType.ROUND_AMOUNT: "Round amount",
}

FLOOR_REASONS = {
    SignalType.DUPLICATE: "a very strong duplicate match must always be reviewed",
    SignalType.BANK_ACCOUNT_CHANGE: "bank account changes are high-priority for review",
    SignalType.SPLIT_PURCHASE: "a potential split purchase must be reviewed by a manager",
    SignalType.ML_ANOMALY: "the anomaly model rates this invoice as very unusual (score 0.8 or more)",
    SignalType.AMOUNT_ANOMALY: "the amount is extremely far above this vendor's usual amounts (6σ or more)",
}


def score(signals: list[Signal | SignalInput], config: ScoringConfig | None = None) -> RiskResult:
    config = config or ScoringConfig()
    thresholds = config.risk_level_thresholds

    scored = [
        ScoredSignal(
            type=signal.type, strength=round(signal.strength, 3),
            weight=config.signal_weights.weight(signal.type),
            points=round(config.signal_weights.weight(signal.type) * signal.strength),
            message=signal.message or SIGNAL_LABELS[signal.type],
        )
        for signal in signals
    ]
    scored.sort(key=lambda s: (s.points, s.weight), reverse=True)

    points_total = sum(s.points for s in scored)
    risk_score = min(MAX_SCORE, points_total)

    floor = _strongest_floor(scored, config)
    if floor and floor.min_score > risk_score:
        risk_score = floor.min_score
    else:
        floor = None

    level = thresholds.level_for(risk_score)
    return RiskResult(
        risk_score=risk_score, risk_level=level, points_total=points_total,
        capped=points_total > MAX_SCORE, floor_applied=floor, breakdown=scored,
        explanation=_explanation(scored, floor, points_total),
        summary=f"Risk score {risk_score}/100 ({level.value}). "
                f"This is a risk indicator for human review, not a determination of fraud.",
    )


def _strongest_floor(scored: list[ScoredSignal], config: ScoringConfig) -> AppliedFloor | None:
    best = None
    for signal in scored:
        rule = config.signal_floors.get(signal.type)
        if rule is None or signal.strength < rule.min_strength:
            continue
        if best is None or rule.min_score > best.min_score:
            level = config.risk_level_thresholds.level_for(rule.min_score).value
            reason = FLOOR_REASONS.get(signal.type, f"{SIGNAL_LABELS[signal.type].lower()} requires review")
            best = AppliedFloor(signal_type=signal.type, min_score=rule.min_score,
                                reason=f"Minimum score {rule.min_score} ({level}) because {reason}")
    return best


def _explanation(scored: list[ScoredSignal], floor: AppliedFloor | None, points_total: int) -> list[str]:
    lines = [f"{s.message} (+{s.points})" for s in scored]
    if points_total > MAX_SCORE:
        lines.append(f"Points total {points_total}, capped at {MAX_SCORE}")
    if floor:
        lines.append(floor.reason)
    return lines
