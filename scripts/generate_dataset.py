"""
Generate the SYNTHETIC invoice dataset (academic demonstration only; not real fraud data).

Run from the project root with the ML service's virtual environment:
    ml-service\\venv\\Scripts\\python.exe scripts\\generate_dataset.py
Options:
    --vendors 60 --months 18 --seed 42 --out data\\raw
"""

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml-service"))

from training import dataset  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--vendors", type=int, default=60)
    parser.add_argument("--months", type=int, default=18)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2025, 3, 1))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "raw")
    args = parser.parse_args()

    tables = dataset.generate(n_vendors=args.vendors, start=args.start, months=args.months, seed=args.seed)
    dataset.save(tables, args.out)
    invoices = tables["invoices"]
    print(f"Wrote {len(tables['vendors'])} vendors, {len(tables['bank_accounts'])} bank accounts and "
          f"{len(invoices)} invoices to {args.out}")
    print(f"Injected anomalies: {int(invoices['is_injected_anomaly'].sum())} "
          f"({invoices['is_injected_anomaly'].mean():.1%})")
    print(invoices.loc[invoices['anomaly_type'] != '', 'anomaly_type'].value_counts().to_string())
    print("NOTE: synthetic data for academic demonstration; it does not represent real corporate fraud data.")


if __name__ == "__main__":
    main()
