# Chapter 13: Results

> Every number below was produced by the project's own scripts and tests (Phases 7–16). Screenshots and user feedback must be added by you. **Do not fabricate results.** Rewrite the text in your own words.

## 13.1 Functional results
| Objective | Achieved? | Evidence |
|---|---|---|
| O4 Duplicate detection | Yes | Five weighted attributes incl. OCR look-alikes; `INV1001` vs `INV-1001` scores 98% (demo scenario 2); field-by-field comparison in the UI. [INSERT screenshot of duplicate comparison] |
| O5 Rules (split, bank change, time…) | Yes | Nine configurable rules with unit tests; demo scenarios 3–5 raise the expected signals. [INSERT screenshot of signal list] |
| O6 Isolation Forest | Yes | Trained on 13 engineered features; hold-out ROC-AUC 0.887 (Chapter 11) |
| O7 Explainable score | Yes | Every analysis lists each signal with its points and any escalation floor, plus “not a determination of fraud”. [INSERT screenshot of reasons list] |
| O8 Workflow + audit | Yes | Risk-based routing with fail-safes, approve/reject/clarify/escalate, alert investigation, simulated payment; every action in an append-only audit log with old/new values. [INSERT screenshot of audit log] |
| O9 Dashboard + reports | Yes | Dashboard (6 KPIs, 6 charts), analytics for any period (8 figures, 8 charts), 5 reports as CSV and PDF. [INSERT screenshots, sample PDF] |

## 13.2 Detection results on synthetic data
Hold-out: the last 6 months of the synthetic dataset (1,772 invoices, 88 injected anomalies). The Isolation Forest was trained on the earlier months only. “Flagged” means the invoice is sent to a person (risk MEDIUM or higher). Produced by `scripts/evaluate_hybrid.py` (`data/processed/hybrid_evaluation.json`).

| Detector | Precision | Recall | F1 | Invoices sent to review |
|---|---|---|---|---|
| Isolation Forest only | 0.417 | 0.284 | 0.338 | 3.4% |
| Rules + duplicate detector only | 0.380 | 0.614 | 0.470 | 8.0% |
| **Hybrid system (final)** | **0.400** | **0.682** | **0.504** | 8.5% |
| Hybrid with the earlier default floors (before Phase 16) | 0.307 | 0.443 | 0.363 | 7.2% |

Recall by injected anomaly type:

| Type (count) | ML only | Rules only | Hybrid |
|---|---|---|---|
| Bank-account change (7) | 0.14 | 1.00 | 1.00 |
| Duplicate (22) | 0.18 | 0.82 | 0.82 |
| Amount spike (14) | 0.57 | 0.79 | 0.79 |
| Off-hours submission (10) | 0.90 | 0.10 | 0.60 |
| Split purchase (24) | 0.08 | 0.58 | 0.58 |
| Threshold hugging (11) | 0.09 | 0.27 | 0.36 |

## 13.3 Performance
Measured on the development laptop (Intel, 12 logical CPUs, Windows 11), Django development server and ML service on the same machine, database with 303 invoices. Median of repeated calls unless stated.

| Measurement | Value |
|---|---|
| Single-invoice analysis, end to end (Django → ML service → routing, submit request) | 80 ms median, 130 ms 95th percentile |
| CSV import of 100 rows (validation + save) | 0.8 s |
| Submitting those 100 invoices for analysis one after another | 8.7 s |
| Invoice list API (20 per page) | 9 ms |
| Dashboard summary | 20 ms |
| Analytics (12 months) | 33 ms |
| Fraud investigation payload | 72 ms |
| Invoice report as PDF | 0.43 s |
| Frontend first download (JavaScript, gzip) | 115 kB (262 kB before on-demand page loading) |

## 13.4 Screenshots
Suggested set (sign in with the demo accounts after `seed_data`):
[INSERT SCREENSHOT: Dashboard (manager or auditor)]
[INSERT SCREENSHOT: Invoice list with filters]
[INSERT SCREENSHOT: Invoice INV1001: risk gauge, reasons, duplicate comparison]
[INSERT SCREENSHOT: Fraud investigation for the bank-change invoice FL-2005]
[INSERT SCREENSHOT: Approval queue (auditor)]
[INSERT SCREENSHOT: Analytics]
[INSERT SCREENSHOT: A page of the fraud report PDF]

## 13.5 User feedback (optional)
[INSERT: feedback from classmates/supervisor who tried the system]
