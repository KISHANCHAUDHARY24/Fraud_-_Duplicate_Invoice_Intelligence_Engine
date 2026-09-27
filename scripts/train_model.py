"""
Train the Isolation Forest on the synthetic dataset and save it for the ML service.

Run from the project root with the ML service's virtual environment:
    ml-service\\venv\\Scripts\\python.exe scripts\\generate_dataset.py     (once)
    ml-service\\venv\\Scripts\\python.exe scripts\\train_model.py
Then restart the ML service so it loads the new model.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml-service"))

from training import train  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=ROOT / "data" / "raw")
    parser.add_argument("--models", type=Path, default=ROOT / "ml-service" / "models")
    parser.add_argument("--reports", type=Path, default=ROOT / "data" / "processed")
    args = parser.parse_args()

    if not (args.data / "synthetic_invoices.csv").exists():
        sys.exit(f"No dataset in {args.data}. Run scripts\\generate_dataset.py first.")
    metadata = train.run(args.data, args.models, args.reports)
    holdout = metadata["metrics"]["holdout"]
    print(f"\nModel {metadata['model_version']} trained on {metadata['training_rows']} invoices.")
    print(f"Hold-out: precision {holdout['precision']:.3f} | recall {holdout['recall']:.3f} | "
          f"F1 {holdout['f1']:.3f} | ROC-AUC {holdout['roc_auc']:.3f}")
    print("Recall by anomaly type:")
    for kind, row in holdout["recall_by_type"].items():
        print(f"  {kind:18} {row['recall']:.2f}  ({row['count']} in hold-out)")
    print(f"Full report: {args.reports / 'evaluation_report.json'}")


if __name__ == "__main__":
    main()
