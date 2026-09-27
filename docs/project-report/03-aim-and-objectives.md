# Chapter 3: Aim and Objectives

## 3.1 Aim
To design, implement and evaluate a web-based invoice intelligence system that detects potential duplicate and anomalous invoices using hybrid rule-based, fuzzy-matching and machine-learning techniques, and presents explainable risk scores to support human review.

## 3.2 Objectives
| # | Objective | Measured by |
|---|---|---|
| O1 | Review existing approaches to duplicate detection, anomaly detection and explainable decision support | Literature review (Ch. 4) |
| O2 | Specify functional and non-functional requirements for a role-based AP system | Requirements (Ch. 5) |
| O3 | Design a modular architecture separating business logic (Django) from intelligence (FastAPI) | Design and architecture (Ch. 7–8) |
| O4 | Implement fuzzy duplicate detection over invoice number, vendor, amount, date and description | Duplicate test cases pass. Demo scenario 2 |
| O5 | Implement configurable fraud rules including split-purchase and bank-change detection | Rule unit tests. Demo scenarios 4–5 |
| O6 | Train and integrate an Isolation Forest model on engineered features | Evaluation metrics on synthetic data (Ch. 11) |
| O7 | Produce an explainable 0–100 risk score with per-signal reasons | Every analysis lists contributing signals |
| O8 | Implement a risk-based approval workflow with audit logging | Workflow tests. Audit entries for all actions |
| O9 | Build a professional dashboard with analytics and reporting | Working UI. CSV/PDF export |
| O10 | Test and evaluate the system | Test results (Ch. 12–13) |
