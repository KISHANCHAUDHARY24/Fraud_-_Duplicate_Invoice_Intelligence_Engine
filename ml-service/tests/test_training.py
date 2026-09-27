"""Feature pipeline, model training, saving, loading and prediction."""

import json

import pandas as pd
import pytest

from services.anomaly_detector import AnomalyDetector, ModelNotLoaded, describe, to_signal
from services.feature_engineering import FEATURE_NAMES
from training import train
from training.context import build_feature_frame
from utils.preprocessing import clean_invoices


@pytest.fixture(scope="module")
def feature_frame(small_tables):
    invoices, _ = clean_invoices(small_tables["invoices"])
    return build_feature_frame(invoices, small_tables["vendors"], small_tables["bank_accounts"])


class TestFeaturePipeline:
    def test_every_feature_present_for_every_invoice(self, feature_frame):
        assert set(FEATURE_NAMES) <= set(feature_frame.columns)
        assert not feature_frame[FEATURE_NAMES].isna().any().any()

    def test_no_look_ahead(self, feature_frame):
        """A vendor's first invoice has no history: statistics must come only from earlier invoices."""
        first = feature_frame.groupby("vendor_id").head(1)
        assert (first["amount_dev_vendor"] == 0).all()
        assert (first["duplicate_similarity"] == 0).all()
        assert (first["days_since_previous_invoice"] == 365).all()

    def test_features_reflect_the_injected_patterns(self, feature_frame):
        by_type = feature_frame.groupby("anomaly_type")
        assert by_type["duplicate_similarity"].mean()["duplicate"] > 0.8
        assert (feature_frame.query("anomaly_type == 'bank_change'")["bank_account_changed"] == 1).all()
        assert by_type["is_outside_hours"].mean()["off_hours"] > by_type["is_outside_hours"].mean()[""]
        assert by_type["amount_dev_vendor"].median()["amount_spike"] > 3


class TestTrainingRun:
    def test_files_and_metadata(self, trained_model_dir):
        models = trained_model_dir / "models"
        assert {p.name for p in models.iterdir()} == {train.MODEL_FILE, train.SCALER_FILE, train.METADATA_FILE}
        metadata = json.loads((models / train.METADATA_FILE).read_text(encoding="utf-8"))
        assert metadata["feature_names"] == train.MODEL_FEATURES
        assert metadata["hyperparameters"]["random_state"] == 42
        assert metadata["calibration"]["raw_p50"] < metadata["calibration"]["raw_boundary"] <= metadata["calibration"]["raw_max"]
        assert "synthetic" in metadata["dataset"]["source"]

    def test_evaluation_report(self, trained_model_dir):
        report = json.loads((trained_model_dir / "reports" / "evaluation_report.json").read_text(encoding="utf-8"))
        holdout = report["holdout"]
        for key in ("precision", "recall", "f1", "roc_auc", "average_precision"):
            assert 0 <= holdout[key] <= 1
        matrix = holdout["confusion_matrix"]
        assert sum(matrix.values()) == holdout["rows"] == report["split"]["test_rows"]
        # Better than random ranking, even on this small dataset.
        assert holdout["roc_auc"] > 0.6

    def test_normalise_scale(self):
        calibration = {"raw_p50": 0.4, "raw_boundary": 0.5, "raw_max": 0.7}
        assert list(train.normalise([0.3, 0.4, 0.5, 0.6, 0.7, 0.9], calibration)) == pytest.approx([0, 0, 0.6, 0.8, 1, 1])


class TestServing:
    def test_missing_files_leave_detector_unloaded(self, tmp_path):
        detector = AnomalyDetector()
        assert detector.load(tmp_path) is False and not detector.loaded
        with pytest.raises(ModelNotLoaded):
            detector.score({name: 0.0 for name in FEATURE_NAMES})

    def test_incompatible_model_is_refused(self, trained_model_dir, tmp_path):
        for name in (train.MODEL_FILE, train.SCALER_FILE):
            (tmp_path / name).write_bytes((trained_model_dir / "models" / name).read_bytes())
        metadata = json.loads((trained_model_dir / "models" / train.METADATA_FILE).read_text(encoding="utf-8"))
        metadata["feature_names"] = metadata["feature_names"] + ["feature_that_no_longer_exists"]
        (tmp_path / train.METADATA_FILE).write_text(json.dumps(metadata), encoding="utf-8")
        assert AnomalyDetector().load(tmp_path) is False

    def test_scores_rank_anomalies_above_normal_invoices(self, trained_model_dir, feature_frame):
        detector = AnomalyDetector()
        assert detector.load(trained_model_dir / "models")
        scores = [detector.score(row[FEATURE_NAMES].to_dict()).anomaly_score for _, row in feature_frame.iterrows()]
        frame = feature_frame.assign(score=scores)
        assert frame["score"].between(0, 1).all()
        means = frame.groupby("anomaly_type")["score"].mean()
        assert means["off_hours"] > means[""] and means["amount_spike"] > means[""]

    def test_signal_and_explanations(self, trained_model_dir, feature_frame):
        detector = AnomalyDetector()
        detector.load(trained_model_dir / "models")
        off_hours = feature_frame.query("anomaly_type == 'off_hours'").iloc[0][FEATURE_NAMES].to_dict()
        result = detector.score(off_hours, threshold=0.0)          # force the signal to fire
        signal = to_signal(result)
        assert signal.type == "ML_ANOMALY" and signal.message.startswith("Unusual combination of features")
        assert signal.details["model_version"] == detector.version
        assert to_signal(detector.score(off_hours, threshold=1.01)) is None

    @pytest.mark.parametrize("name, value, z, expected", [
        ("amount_dev_vendor", 4.2, 3.0, "amount is 4.2σ above the vendor average"),
        ("amount_dev_vendor", 10.0, 9.0, "amount is more than 10σ above the vendor average"),
        ("is_weekend", 1.0, 3.0, "submitted on a non-working day"),
        ("bank_account_changed", 1.0, 5.0, "vendor bank account recently changed"),
        ("duplicate_similarity", 0.96, 4.0, "96% similar to an earlier invoice"),
        ("amount_dev_vendor", -3.0, -3.0, None),      # unusually LOW amounts are not explained as risk
    ])
    def test_describe(self, name, value, z, expected):
        assert describe(name, {name: value, "submission_hour": 2.3}, z) == expected
