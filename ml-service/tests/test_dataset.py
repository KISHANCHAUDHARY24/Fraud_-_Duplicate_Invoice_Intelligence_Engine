"""Synthetic dataset generator and data cleaning."""

import pandas as pd

from training import dataset
from utils.preprocessing import clean_invoices
from utils.similarity import apply_lookalikes, normalize_invoice_number

ANOMALY_TYPES = {"duplicate", "split_purchase", "off_hours", "amount_spike", "bank_change", "threshold_hugging"}


def test_generation_is_reproducible():
    first = dataset.generate(n_vendors=8, months=4, seed=3)["invoices"]
    second = dataset.generate(n_vendors=8, months=4, seed=3)["invoices"]
    pd.testing.assert_frame_equal(first, second)
    assert not first.equals(dataset.generate(n_vendors=8, months=4, seed=4)["invoices"])


def test_shape_and_labels(small_tables):
    invoices = small_tables["invoices"]
    assert set(invoices["anomaly_type"]) - {""} == ANOMALY_TYPES
    assert 0.02 <= invoices["is_injected_anomaly"].mean() <= 0.10
    assert (invoices["is_injected_anomaly"] == (invoices["anomaly_type"] != "").astype(int)).all()
    assert len(small_tables["vendors"]) == 15
    assert set(small_tables["bank_accounts"]["vendor_id"]) == set(small_tables["vendors"]["vendor_id"])


def test_split_purchases_are_groups_of_three_under_the_threshold(small_tables):
    splits = small_tables["invoices"].query("anomaly_type == 'split_purchase'")
    for _, group in splits.groupby("anomaly_group"):
        assert len(group) == 3 and group["vendor_id"].nunique() == 1
        assert group["amount"].between(9000, dataset.APPROVAL_THRESHOLD).all()
        dates = pd.to_datetime(group["invoice_date"])
        assert (dates.max() - dates.min()).days <= 5


def test_duplicates_disguise_an_existing_invoice_number(small_tables):
    invoices = small_tables["invoices"]
    normal_numbers = {apply_lookalikes(normalize_invoice_number(n)) for n in invoices.query("anomaly_type == ''")["invoice_number"]}
    for number in invoices.query("anomaly_type == 'duplicate'")["invoice_number"]:
        key = apply_lookalikes(normalize_invoice_number(number))
        assert key in normal_numbers or key.removesuffix("A") in normal_numbers, number


def test_off_hours_rows_are_outside_office_time(small_tables):
    moments = pd.to_datetime(small_tables["invoices"].query("anomaly_type == 'off_hours'")["submission_datetime"])
    assert ((moments.dt.weekday >= 5) | (moments.dt.hour < 6)).all()


def test_save_and_load_round_trip(small_tables, tmp_path):
    dataset.save(small_tables, tmp_path)
    loaded = dataset.load(tmp_path)
    assert len(loaded["invoices"]) == len(small_tables["invoices"])
    assert loaded["invoices"]["anomaly_type"].eq("").sum() == small_tables["invoices"]["anomaly_type"].eq("").sum()


def test_cleaning_removes_the_injected_data_problems(small_tables, tmp_path):
    dataset.save(small_tables, tmp_path)
    cleaned, report = clean_invoices(dataset.load(tmp_path)["invoices"])
    assert (report.invalid_amount, report.unparseable_dates, report.exact_duplicates) == (2, 1, 5)
    assert report.rows_out == report.rows_in - 8 == len(cleaned)
    assert (cleaned["amount"] > 0).all()
    assert cleaned["submission_datetime"].is_monotonic_increasing
    # Cleaning never removes labelled anomalies.
    assert cleaned["is_injected_anomaly"].sum() == small_tables["invoices"]["is_injected_anomaly"].sum()


def test_cleaning_handles_missing_required_values():
    frame = pd.DataFrame([
        {"invoice_id": 1, "vendor_id": 1, "vendor_name": "A", "invoice_number": "N-1", "invoice_date": "2026-01-02",
         "submission_datetime": "2026-01-02T10:00:00+05:30", "amount": 10},
        {"invoice_id": 2, "vendor_id": 1, "vendor_name": "A", "invoice_number": " ", "invoice_date": "2026-01-02",
         "submission_datetime": "2026-01-02T10:00:00+05:30", "amount": 10},
        {"invoice_id": 3, "vendor_id": None, "vendor_name": "A", "invoice_number": "N-3", "invoice_date": "2026-01-02",
         "submission_datetime": "2026-01-02T10:00:00+05:30", "amount": 10},
    ])
    cleaned, report = clean_invoices(frame)
    assert report.missing_values == 2 and list(cleaned["invoice_id"]) == [1]
