"""
Serving the Isolation Forest (docs/machine-learning.md §4.9 and §5).

The model is loaded ONCE when the service starts (never retrained per request).
If the files are missing the service still runs: rules and duplicate detection
keep working, and /health reports model_loaded = false.
"""

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np

from schemas.fraud import Severity, Signal, SignalType

from .feature_engineering import FEATURE_NAMES, MAX_Z

logger = logging.getLogger("ml_service.anomaly")

MODEL_FILE, SCALER_FILE, METADATA_FILE = "isolation_forest.pkl", "scaler.pkl", "model_metadata.json"
NOTABLE_Z = 2.0          # a feature is "notable" if it is >= 2 standard deviations from normal
MAX_REASONS = 3


@dataclass
class AnomalyResult:
    anomaly_score: float
    is_anomaly: bool
    threshold: float
    model_version: str
    reasons: list[str] = field(default_factory=list)
    top_features: list[dict] = field(default_factory=list)


class ModelNotLoaded(RuntimeError):
    pass


class AnomalyDetector:
    def __init__(self):
        self.model = self.scaler = self.metadata = None

    @property
    def loaded(self) -> bool:
        return self.model is not None

    @property
    def version(self) -> str | None:
        return self.metadata["model_version"] if self.metadata else None

    def load(self, model_dir: Path) -> bool:
        paths = [model_dir / MODEL_FILE, model_dir / SCALER_FILE, model_dir / METADATA_FILE]
        if not all(path.exists() for path in paths):
            logger.warning("Model files not found in %s: ML anomaly signal disabled. "
                           "Run scripts/train_model.py and restart the service.", model_dir)
            self.model = self.scaler = self.metadata = None
            return False
        metadata = json.loads(paths[2].read_text(encoding="utf-8"))
        unknown = set(metadata["feature_names"]) - set(FEATURE_NAMES)
        if unknown:
            # The model expects features this code no longer produces: refuse rather than mis-score.
            logger.error("Model %s expects unknown features %s: not loaded", metadata.get("model_version"), unknown)
            return False
        self.model, self.scaler, self.metadata = joblib.load(paths[0]), joblib.load(paths[1]), metadata
        logger.info("Loaded anomaly model %s (%d features)", self.version, len(metadata["feature_names"]))
        return True

    # ------------------------------------------------------------------ scoring
    def score(self, features: dict[str, float], threshold: float | None = None) -> AnomalyResult:
        if not self.loaded:
            raise ModelNotLoaded("The anomaly model is not loaded. Run scripts/train_model.py and restart the service.")
        names = self.metadata["feature_names"]          # the exact column order used in training
        row = np.array([[features[name] for name in names]], dtype=float)
        scaled = self.scaler.transform(row)
        raw = float(-self.model.score_samples(scaled)[0])
        calibration = self.metadata["calibration"]
        default_threshold = self.metadata["anomaly_threshold"]
        # Same piecewise scale as training/train.py normalise(): median 0, boundary 0.6, max 1.0.
        score = float(np.clip(np.interp(raw, [calibration["raw_p50"], calibration["raw_boundary"], calibration["raw_max"]],
                                        [0.0, default_threshold, 1.0]), 0.0, 1.0))
        threshold = default_threshold if threshold is None else threshold

        z_by_feature = dict(zip(names, scaled[0]))
        ranked = sorted(z_by_feature.items(), key=lambda item: abs(item[1]), reverse=True)
        top = [{"feature": name, "value": round(features[name], 4), "z": round(float(z), 2)} for name, z in ranked[:5]]
        reasons = [text for name, z in ranked if abs(z) >= NOTABLE_Z
                   for text in [describe(name, features, z)] if text][:MAX_REASONS]
        return AnomalyResult(anomaly_score=round(score, 4), is_anomaly=score >= threshold, threshold=threshold,
                             model_version=self.version, reasons=reasons, top_features=top)


def describe(name: str, features: dict[str, float], z: float) -> str | None:
    """Plain-English description of one unusual feature (None when it would not help a reviewer)."""
    value = features[name]
    if name in ("amount_dev_vendor", "amount_dev_company") and z > 0:
        # The feature is capped at MAX_Z; say so instead of showing the cap as the real value.
        size = f"more than {MAX_Z:.0f}σ" if value >= MAX_Z else f"{value:.1f}σ"
        return f"amount is {size} above the {'vendor' if name == 'amount_dev_vendor' else 'company'} average"
    if name == "log_amount":
        return f"{'unusually large' if z > 0 else 'unusually small'} amount ({math.expm1(value):,.2f})"
    if name == "is_weekend" and value == 1:
        return "submitted on a non-working day"
    if name == "is_outside_hours" and value == 1:
        hour = features.get("submission_hour")
        return f"submitted outside working hours ({int(hour):02d}:{int(round(hour % 1 * 60)):02d})" if hour is not None \
            else "submitted outside working hours"
    if name in ("hour_sin", "hour_cos") and features.get("is_outside_hours") == 1:
        return None  # already covered by is_outside_hours
    if name == "vendor_invoice_frequency" and z > 0:
        return f"{int(value)} invoices from this vendor in the last 30 days"
    if name == "duplicate_similarity" and z > 0:
        return f"{value * 100:.0f}% similar to an earlier invoice"
    if name == "threshold_distance":
        return "amount is above the approval threshold" if value < 0 else "amount is just below the approval threshold"
    if name == "same_day_invoice_count" and value >= 1:
        return f"{int(value)} other invoice(s) from this vendor on the same day"
    if name == "round_amount_flag" and value == 1:
        return "round amount"
    if name == "bank_account_changed" and value == 1:
        return "vendor bank account recently changed"
    return None


def to_signal(result: AnomalyResult) -> Signal | None:
    if not result.is_anomaly:
        return None
    because = "; ".join(result.reasons) if result.reasons else "several moderately unusual values together"
    return Signal(
        type=SignalType.ML_ANOMALY, strength=result.anomaly_score,
        severity=Severity.HIGH if result.anomaly_score >= 0.85 else Severity.MEDIUM,
        message=f"Unusual combination of features (anomaly score {result.anomaly_score:.2f}): {because}",
        details={"anomaly_score": result.anomaly_score, "threshold": result.threshold,
                 "model_version": result.model_version, "top_features": result.top_features},
    )


detector = AnomalyDetector()   # one shared instance, loaded at startup (main.py lifespan)
