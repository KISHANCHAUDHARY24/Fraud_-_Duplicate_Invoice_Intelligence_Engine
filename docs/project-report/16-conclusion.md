# Chapter 16: Conclusion

> Write this last. Base every claim on your Results chapter.

## 16.1 Summary
This project designed and implemented a web-based decision-support system that screens invoices for potential duplicates and anomalies. It combines fuzzy string matching, configurable business rules and an Isolation Forest model, and presents an explainable 0–100 risk score. The score drives a risk-based approval workflow with a complete audit trail.

## 16.2 Achievement of objectives
Draft, one sentence per objective (check each against your final chapters):
- **O1** Existing approaches to duplicate detection, anomaly detection and explainability were reviewed (Chapter 4). [complete after writing Chapter 4]
- **O2** Functional and non-functional requirements for four roles were specified (Chapter 5).
- **O3** A modular architecture separates the Django business system from a stateless FastAPI intelligence service (Chapters 7–8).
- **O4** Fuzzy duplicate detection over five weighted attributes identifies `INV1001` as a 98% match of `INV-1001` and detects 82% of injected duplicates (Chapters 12–13).
- **O5** Nine configurable rules detect every injected bank-account change and 58% of split purchases (Chapter 13).
- **O6** An Isolation Forest on 13 engineered features reaches a hold-out ROC-AUC of 0.887 (Chapter 11).
- **O7** Every analysis gives a 0–100 score with each contributing signal, its points and any escalation floor.
- **O8** A risk-based workflow with fail-safes and an append-only audit trail is implemented and covered by automated tests (Chapter 12).
- **O9** Dashboard, analytics and CSV/PDF reports are implemented (Chapter 13).
- **O10** 622 automated tests pass; the hybrid system reaches recall 0.682 at precision 0.400 on the synthetic hold-out (Chapters 12–13).

## 16.3 Key contributions
- A hybrid detection design in which each detector contributes visible, additive points.
- Near-duplicate detection across five weighted invoice attributes.
- Split-purchase and bank-change detection integrated with routing.
- A clean separation between the business system and a stateless ML service.

## 16.4 Personal reflection
[INSERT: what you learned about full-stack development, ML, and working incrementally]

## 16.5 Closing statement
The system shows that practical, explainable invoice screening can be built with open-source tools. It also shows that such systems must remain **decision support**: they highlight risk, and people decide.
