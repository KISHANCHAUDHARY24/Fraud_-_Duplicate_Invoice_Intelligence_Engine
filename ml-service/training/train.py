"""
Train, evaluate and save the Isolation Forest (docs/machine-learning.md §4).

    raw CSVs -> clean -> rebuild context + build_features() -> scale -> Isolation Forest
             -> evaluate on a time-based hold-out (last 6 months, labels used ONLY here)
             -> retrain on all data -> save model, scaler, metadata, evaluation report
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import (average_precision_score, confusion_matrix, precision_recall_fscore_support,
                             roc_auc_score)
from sklearn.preprocessing import StandardScaler

from utils.preprocessing import clean_invoices

from . import dataset
from .context import build_feature_frame

# Chosen from the Phase 7 experiment (docs/machine-learning.md §4.7): the raw hour/weekday
# duplicate the cyclical encoding, and the gap feature added noise, so they are left out.
MODEL_FEATURES = [
    "log_amount", "amount_dev_vendor", "amount_dev_company",
    "is_weekend", "is_outside_hours", "hour_sin", "hour_cos",
    "vendor_invoice_frequency", "duplicate_similarity", "threshold_distance",
    "same_day_invoice_count", "round_amount_flag", "bank_account_changed",
]
HYPERPARAMETERS = {"n_estimators": 200, "max_samples": "auto", "contamination": 0.05, "random_state": 42}
TEST_MONTHS = 6
# Score scale (see normalise): the model's own contamination boundary maps to ANOMALY_THRESHOLD,
# so "0.6" means "among the most unusual 5% of the invoices it learned from".
ANOMALY_THRESHOLD = 0.6
MODEL_FILE, SCALER_FILE, METADATA_FILE = "isolation_forest.pkl", "scaler.pkl", "model_metadata.json"


def matrix(features: pd.DataFrame) -> np.ndarray:
    """Plain array in MODEL_FEATURES order (the order is saved in the metadata for serving)."""
    return features[MODEL_FEATURES].to_numpy(dtype=float)


def fit(features: pd.DataFrame):
    scaler = StandardScaler().fit(matrix(features))
    model = IsolationForest(**HYPERPARAMETERS).fit(scaler.transform(matrix(features)))
    raw = -model.score_samples(scaler.transform(matrix(features)))   # higher = more unusual
    calibration = {"raw_p50": float(np.percentile(raw, 50)),
                   "raw_boundary": float(np.percentile(raw, 100 * (1 - HYPERPARAMETERS["contamination"]))),
                   "raw_max": float(raw.max())}
    return scaler, model, calibration


def normalise(raw, calibration: dict):
    """
    Piecewise-linear 0-1 scale:  training median -> 0.0,  contamination boundary (95th pct) -> 0.6,
    most unusual training invoice -> 1.0. Beyond that the score stays at 1.0.
    """
    return np.clip(np.interp(raw, [calibration["raw_p50"], calibration["raw_boundary"], calibration["raw_max"]],
                             [0.0, ANOMALY_THRESHOLD, 1.0]), 0.0, 1.0)


def anomaly_scores(scaler, model, calibration, features: pd.DataFrame) -> np.ndarray:
    return normalise(-model.score_samples(scaler.transform(matrix(features))), calibration)


def evaluate(labels: pd.Series, types: pd.Series, scores: np.ndarray, threshold: float = ANOMALY_THRESHOLD) -> dict:
    predicted = scores >= threshold
    precision, recall, f1, _ = precision_recall_fscore_support(labels, predicted, average="binary", zero_division=0)
    tn, fp, fn, tp = confusion_matrix(labels, predicted, labels=[0, 1]).ravel()
    per_type = (pd.DataFrame({"type": types, "hit": predicted})[labels.values == 1]
                .groupby("type")["hit"].agg(["count", "mean"]))
    return {
        "rows": int(len(labels)), "anomalies": int(labels.sum()), "threshold": threshold,
        "precision": round(float(precision), 4), "recall": round(float(recall), 4), "f1": round(float(f1), 4),
        "roc_auc": round(float(roc_auc_score(labels, scores)), 4),
        "average_precision": round(float(average_precision_score(labels, scores)), 4),
        "flagged_share": round(float(predicted.mean()), 4),
        "confusion_matrix": {"true_negative": int(tn), "false_positive": int(fp),
                             "false_negative": int(fn), "true_positive": int(tp)},
        "recall_by_type": {t: {"count": int(r["count"]), "recall": round(float(r["mean"]), 4)}
                           for t, r in per_type.iterrows()},
    }


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def run(raw_dir: Path, model_dir: Path, report_dir: Path, log=print) -> dict:
    tables = dataset.load(raw_dir)
    invoices, cleaning = clean_invoices(tables["invoices"])
    log(f"Cleaning: {cleaning.as_dict()}")

    frame = build_feature_frame(invoices, tables["vendors"], tables["bank_accounts"])
    log(f"Features built for {len(frame)} invoices")

    # ---- honest evaluation: fit on the past, test on the most recent months --------------
    cut = frame["submission_datetime"].max() - pd.DateOffset(months=TEST_MONTHS)
    train, test = frame[frame["submission_datetime"] < cut], frame[frame["submission_datetime"] >= cut]
    scaler, model, calibration = fit(train)
    test_metrics = evaluate(test["is_injected_anomaly"], test["anomaly_type"],
                            anomaly_scores(scaler, model, calibration, test))
    log(f"Hold-out ({len(test)} invoices, last {TEST_MONTHS} months): "
        f"precision={test_metrics['precision']} recall={test_metrics['recall']} f1={test_metrics['f1']} "
        f"roc_auc={test_metrics['roc_auc']}")

    # ---- final model: all data ----------------------------------------------------------
    scaler, model, calibration = fit(frame)
    train_metrics = evaluate(frame["is_injected_anomaly"], frame["anomaly_type"],
                             anomaly_scores(scaler, model, calibration, frame))

    trained_at = datetime.now(timezone.utc)
    metadata = {
        "model_version": f"iforest-{trained_at:%Y%m%d-%H%M%S}",
        "trained_at": trained_at.isoformat(),
        "algorithm": "sklearn.ensemble.IsolationForest",
        "hyperparameters": HYPERPARAMETERS,
        "feature_names": MODEL_FEATURES,
        "calibration": calibration,
        "anomaly_threshold": ANOMALY_THRESHOLD,
        "training_rows": len(frame),
        "dataset": {"source": "synthetic (training/dataset.py) - academic demonstration only",
                    "invoices_sha256_16": _file_hash(raw_dir / "synthetic_invoices.csv")},
        "metrics": {"holdout": test_metrics, "all_data_in_sample": train_metrics},
    }

    model_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_dir / MODEL_FILE)
    joblib.dump(scaler, model_dir / SCALER_FILE)
    (model_dir / METADATA_FILE).write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    report_dir.mkdir(parents=True, exist_ok=True)
    report = {"model_version": metadata["model_version"], "cleaning": cleaning.as_dict(),
              "split": {"train_rows": len(train), "test_rows": len(test), "cut": cut.isoformat()},
              "holdout": test_metrics, "all_data_in_sample": train_metrics}
    (report_dir / "evaluation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    frame.to_csv(report_dir / "features.csv", index=False)
    log(f"Saved {MODEL_FILE}, {SCALER_FILE}, {METADATA_FILE} to {model_dir}")
    return metadata
