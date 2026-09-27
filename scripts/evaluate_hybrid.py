"""
Rules only vs ML only vs the full hybrid pipeline, on the same hold-out invoices (docs/machine-learning.md §8).

Honest set-up, mirroring training/train.py:
  * the synthetic invoices are replayed in submission order; every invoice only "sees" earlier invoices,
  * the Isolation Forest is fitted on the earlier months only (the shipped model saw all data, so it is NOT used),
  * the last TEST_MONTHS months are the hold-out; each hold-out invoice goes through the real
    services/fraud_detector.analyze() pipeline (duplicate detector + rules + ML + risk scorer).

"Flagged" = risk level MEDIUM or higher, i.e. the invoice is sent to a person for review.

Run from the project root with the ML service's virtual environment:
    ml-service\\venv\\Scripts\\python.exe scripts\\evaluate_hybrid.py
Writes data/processed/hybrid_evaluation.json (synthetic data: academic demonstration only).
"""

import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml-service"))

from schemas.analysis import AnalysisConfig, FraudAnalysisRequest  # noqa: E402
from schemas.fraud import SignalType  # noqa: E402
from schemas.invoice import InvoiceSnapshot  # noqa: E402
from services import risk_scorer  # noqa: E402
from services.anomaly_detector import detector  # noqa: E402
from services.fraud_detector import analyze  # noqa: E402
from training import dataset  # noqa: E402
from training.context import DUPLICATE_LOOKBACK_DAYS, ContextBuilder, build_feature_frame  # noqa: E402
from training.train import ANOMALY_THRESHOLD, MODEL_FEATURES, TEST_MONTHS, fit  # noqa: E402
from utils.preprocessing import clean_invoices  # noqa: E402

FLAGGED = {"MEDIUM", "HIGH", "CRITICAL"}
# Alternative signal_floors settings, scored on the same analyses (the "hybrid" row uses the current defaults).
PREVIOUS_DEFAULT_FLOORS = {   # before Phase 16: only duplicate, bank change and split purchase escalate
    "DUPLICATE": {"min_strength": 0.9, "min_score": 60},
    "BANK_ACCOUNT_CHANGE": {"min_strength": 0.0, "min_score": 60},
    "SPLIT_PURCHASE": {"min_strength": 0.0, "min_score": 30},
}
FLOOR_VARIANTS = {
    "previous_default_floors": lambda current: PREVIOUS_DEFAULT_FLOORS,
    "previous_plus_ml_floor": lambda current: {**PREVIOUS_DEFAULT_FLOORS, "ML_ANOMALY": current["ML_ANOMALY"]},
    "previous_plus_amount_floor": lambda current: {**PREVIOUS_DEFAULT_FLOORS, "AMOUNT_ANOMALY": current["AMOUNT_ANOMALY"]},
    "current_plus_time_floor": lambda current: {**current, "TIME_ANOMALY": {"min_strength": 1.0, "min_score": 30}},
}
MAX_CANDIDATES = 500
SNAPSHOT_FIELDS = set(InvoiceSnapshot.model_fields)


def metrics(labels: pd.Series, flagged: pd.Series, types: pd.Series) -> dict:
    tp = int((flagged & labels).sum())
    fp = int((flagged & ~labels).sum())
    fn = int((~flagged & labels).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    by_type = {kind: {"count": int((types == kind).sum()), "recall": round(float(flagged[types == kind].mean()), 4)}
               for kind in sorted(types[labels].dropna().unique())}
    return {"precision": round(precision, 4), "recall": round(recall, 4),
            "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
            "flagged_share": round(float(flagged.mean()), 4), "true_positive": tp, "false_positive": fp,
            "false_negative": fn, "recall_by_type": by_type}


def main():
    tables = dataset.load(ROOT / "data" / "raw")
    invoices, _ = clean_invoices(tables["invoices"])
    cut = invoices["submission_datetime"].max() - pd.DateOffset(months=TEST_MONTHS)

    # 1. Isolation Forest fitted on the earlier months only.
    features = build_feature_frame(invoices, tables["vendors"], tables["bank_accounts"])
    scaler, model, calibration = fit(features[features["submission_datetime"] < cut])
    detector.model, detector.scaler = model, scaler
    detector.metadata = {"model_version": "holdout-evaluation", "feature_names": MODEL_FEATURES,
                         "calibration": calibration, "anomaly_threshold": ANOMALY_THRESHOLD}

    # 2. Replay every invoice; analyse the hold-out ones with the full pipeline.
    config = AnalysisConfig()
    builder = ContextBuilder(tables["vendors"], tables["bank_accounts"])
    rows, all_signals = [], []
    for row in invoices.itertuples(index=False):
        context = builder.context_for(row)
        invoice = context["invoice"]
        if row.submission_datetime >= cut:
            window = [h for h in context["past"]
                      if abs((invoice.invoice_date - h.invoice_date).days) <= DUPLICATE_LOOKBACK_DAYS][-MAX_CANDIDATES:]
            response = analyze(FraudAnalysisRequest(
                invoice=invoice, vendor_context=context["vendor_context"], bank=context["bank"],
                recent_vendor_invoices=context["recent"][-500:],
                duplicate_candidates=[InvoiceSnapshot(**h.model_dump(include=SNAPSHOT_FIELDS)) for h in window],
                config=config))
            rule_signals = [s for s in response.signals if s.type != SignalType.ML_ANOMALY]
            all_signals.append(response.signals)
            rows.append({
                "label": bool(row.is_injected_anomaly), "type": row.anomaly_type if row.is_injected_anomaly else None,
                "hybrid": response.risk_level in FLAGGED,
                "rules": risk_scorer.score(rule_signals, config).risk_level.value in FLAGGED,
                "ml": bool(response.anomaly.is_anomaly),
                "score": response.risk_score, "signals": [s.type.value for s in response.signals],
            })
        builder.record(invoice)

    frame = pd.DataFrame(rows)
    labels, types = frame["label"], frame["type"]
    report = {
        "dataset": "synthetic (training/dataset.py, seed 42): academic demonstration only",
        "holdout": {"from": cut.isoformat(), "invoices": len(frame), "anomalies": int(labels.sum())},
        "flag_rule": "risk level MEDIUM or higher (sent to human review)",
        "ml_only": metrics(labels, frame["ml"], types),
        "rules_only": metrics(labels, frame["rules"], types),
        "hybrid": metrics(labels, frame["hybrid"], types),
        "current_default_floors": config.model_dump(mode="json")["signal_floors"],
        "floor_variants": {
            name: {"signal_floors": floors, **metrics(labels, pd.Series(
                [risk_scorer.score(signals, variant).risk_level.value in FLAGGED for signals in all_signals]), types)}
            for name, make in FLOOR_VARIANTS.items()
            for floors in [make(config.model_dump(mode="json")["signal_floors"])]
            # validated like a real settings change
            for variant in [AnalysisConfig(**{**config.model_dump(), "signal_floors": floors})]},
        "signals_on_normal_invoices": dict(Counter(s for signals, label in zip(frame["signals"], labels)
                                                   if not label for s in signals).most_common()),
    }
    out = ROOT / "data" / "processed" / "hybrid_evaluation.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Hold-out: {len(frame)} invoices ({int(labels.sum())} injected anomalies) from {cut:%Y-%m-%d}")
    print(f"{'':24}{'precision':>10}{'recall':>8}{'F1':>7}{'flagged':>9}")
    for name, m in [(n, report[n]) for n in ("ml_only", "rules_only", "hybrid")] + list(report["floor_variants"].items()):
        print(f"{name:24}{m['precision']:>10.3f}{m['recall']:>8.3f}{m['f1']:>7.3f}{m['flagged_share']:>9.1%}")
    print("Recall by anomaly type (ml / rules / hybrid):")
    for kind in report["hybrid"]["recall_by_type"]:
        values = [report[name]["recall_by_type"][kind]["recall"] for name in ("ml_only", "rules_only", "hybrid")]
        count = report["hybrid"]["recall_by_type"][kind]["count"]
        print(f"  {kind:18} n={count:<3} " + " / ".join(f"{v:.2f}" for v in values))
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
