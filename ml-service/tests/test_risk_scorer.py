"""Risk scorer: points, cap, floors, levels, custom settings, explanations."""

import pytest
from pydantic import ValidationError

from schemas.fraud import SignalType as T
from schemas.risk import RiskLevelThresholds, ScoringConfig, SignalInput, SignalWeights
from services.risk_scorer import score


def s(signal_type, strength=1.0, message=""):
    return SignalInput(type=signal_type, strength=strength, message=message)


def test_no_signals_is_zero_and_low():
    result = score([])
    assert (result.risk_score, result.risk_level, result.explanation) == (0, "LOW", [])
    assert "not a determination of fraud" in result.summary


def test_points_are_weight_times_strength_and_add_up():
    result = score([s(T.DUPLICATE, 0.5), s(T.TIME_ANOMALY, 0.6), s(T.ROUND_AMOUNT)])
    assert [(b.type, b.points) for b in result.breakdown] == [(T.DUPLICATE, 15), (T.TIME_ANOMALY, 6), (T.ROUND_AMOUNT, 5)]
    assert result.risk_score == result.points_total == 26


def test_documented_worked_example():
    """docs/risk-scoring.md §7: rounded per signal, so the reasons add up exactly to the score."""
    result = score([s(T.DUPLICATE, 0.94), s(T.THRESHOLD_PROXIMITY, 0.90), s(T.TIME_ANOMALY, 1.0),
                    s(T.BANK_ACCOUNT_CHANGE, 1.0), s(T.ML_ANOMALY, 0.71)])
    assert [b.points for b in result.breakdown] == [28, 20, 14, 11, 10]
    assert (result.risk_score, result.risk_level) == (83, "CRITICAL")
    assert result.floor_applied is None   # 83 is already above every floor


def test_score_is_capped_at_100():
    everything = [s(t) for t in T]
    result = score(everything)
    assert result.points_total == 140 and result.risk_score == 100 and result.capped
    assert result.explanation[-1] == "Points total 140, capped at 100"


@pytest.mark.parametrize("signals, expected_score, floor_type", [
    ([s(T.DUPLICATE, 0.90)], 60, T.DUPLICATE),            # strong duplicate: at least HIGH
    ([s(T.DUPLICATE, 0.89)], 27, None),                   # just below the floor's min strength
    ([s(T.BANK_ACCOUNT_CHANGE)], 60, T.BANK_ACCOUNT_CHANGE),
    ([s(T.SPLIT_PURCHASE, 0.7)], 30, T.SPLIT_PURCHASE),   # 14 points, raised to 30
    ([s(T.SPLIT_PURCHASE), s(T.BANK_ACCOUNT_CHANGE)], 60, T.BANK_ACCOUNT_CHANGE),  # strongest floor wins
    # Phase 16: one strong ML or amount signal alone must reach review (MEDIUM).
    ([s(T.ML_ANOMALY, 0.80)], 30, T.ML_ANOMALY),          # 12 points, raised to 30
    ([s(T.ML_ANOMALY, 0.79)], 12, None),                  # just below: stays LOW
    ([s(T.AMOUNT_ANOMALY, 1.0)], 30, T.AMOUNT_ANOMALY),   # amount >= 6 sigma above the vendor average
    ([s(T.AMOUNT_ANOMALY, 0.9)], 14, None),
])
def test_escalation_floors(signals, expected_score, floor_type):
    result = score(signals)
    assert result.risk_score == expected_score
    assert (result.floor_applied.signal_type if result.floor_applied else None) == floor_type
    if floor_type:
        assert result.explanation[-1].startswith(f"Minimum score {expected_score}")


def test_floor_not_reported_when_points_already_higher():
    result = score([s(T.BANK_ACCOUNT_CHANGE), s(T.DUPLICATE), s(T.SPLIT_PURCHASE)])   # 20 + 30 + 20 = 70
    assert result.risk_score == 70 and result.floor_applied is None


@pytest.mark.parametrize("points, level", [(29, "LOW"), (30, "MEDIUM"), (59, "MEDIUM"), (60, "HIGH"),
                                           (79, "HIGH"), (80, "CRITICAL"), (100, "CRITICAL")])
def test_level_boundaries(points, level):
    config = ScoringConfig(signal_weights=SignalWeights(AMOUNT_ANOMALY=points), signal_floors={})
    assert score([s(T.AMOUNT_ANOMALY)], config).risk_level == level


def test_custom_weights_thresholds_and_floors():
    config = ScoringConfig(
        signal_weights=SignalWeights(ROUND_AMOUNT=0, TIME_ANOMALY=40),
        risk_level_thresholds=RiskLevelThresholds(medium=20, high=35, critical=90),
        signal_floors={},
    )
    result = score([s(T.ROUND_AMOUNT), s(T.TIME_ANOMALY), s(T.BANK_ACCOUNT_CHANGE)], config)
    assert result.risk_score == 60 and result.risk_level == "HIGH"
    assert result.breakdown[-1].points == 0          # disabled signal still listed, with 0 points


def test_explanation_uses_messages_or_labels_sorted_by_points():
    result = score([s(T.ROUND_AMOUNT), s(T.DUPLICATE, 0.94, "94% similarity with invoice INV-1001")])
    assert result.explanation[:2] == ["94% similarity with invoice INV-1001 (+28)", "Round amount (+5)"]


def test_invalid_configuration_is_rejected():
    with pytest.raises(ValidationError):
        RiskLevelThresholds(medium=60, high=30, critical=80)
    with pytest.raises(ValidationError):
        SignalWeights(DUPLICATE=150)
    with pytest.raises(ValidationError):
        SignalWeights(NOT_A_SIGNAL=5)
