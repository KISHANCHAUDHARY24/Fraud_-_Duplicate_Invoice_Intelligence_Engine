"""Data cleaning before feature engineering (docs/machine-learning.md §4.1)."""

from dataclasses import dataclass

import pandas as pd

REQUIRED_COLUMNS = ["invoice_id", "vendor_id", "vendor_name", "invoice_number", "invoice_date",
                    "submission_datetime", "amount"]


@dataclass
class CleaningReport:
    rows_in: int
    missing_values: int
    invalid_amount: int  # missing, non-numeric or <= 0
    unparseable_dates: int
    exact_duplicates: int
    rows_out: int

    def as_dict(self):
        return self.__dict__.copy()


def clean_invoices(frame: pd.DataFrame) -> tuple[pd.DataFrame, CleaningReport]:
    """
    Removes rows that cannot be used and reports how many of each problem were found.
    'Exact duplicates' here are identical export rows (a data error), NOT the
    business duplicates that the duplicate detector is designed to find.
    """
    rows_in = len(frame)
    data = frame.copy()

    missing = data[REQUIRED_COLUMNS].isna().any(axis=1) | (data["invoice_number"].astype(str).str.strip() == "")
    data = data[~missing]

    data["amount"] = pd.to_numeric(data["amount"], errors="coerce")
    invalid_amount = ~(data["amount"] > 0)  # NaN (missing / not a number) also fails this test
    data = data[~invalid_amount]

    data["invoice_date"] = pd.to_datetime(data["invoice_date"], errors="coerce").dt.date
    data["submission_datetime"] = pd.to_datetime(data["submission_datetime"], errors="coerce", utc=True)
    bad_dates = data["invoice_date"].isna() | data["submission_datetime"].isna()
    data = data[~bad_dates]

    content_columns = [c for c in data.columns if c != "invoice_id"]
    exact_copy = data.duplicated(subset=content_columns, keep="first")
    data = data[~exact_copy]

    data = data.sort_values(["submission_datetime", "invoice_id"], kind="stable").reset_index(drop=True)
    report = CleaningReport(rows_in=rows_in, missing_values=int(missing.sum()), invalid_amount=int(invalid_amount.sum()),
                            unparseable_dates=int(bad_dates.sum()), exact_duplicates=int(exact_copy.sum()),
                            rows_out=len(data))
    return data, report
