# Chapter 5: Requirements

## 5.1 Requirements gathering
Requirements were derived from: (a) the project brief, (b) typical accounts-payable controls (approval limits, segregation of duties, vendor master-data controls), and (c) known invoice-fraud patterns from the literature (Chapter 4). [INSERT: any interviews, questionnaires or supervisor meetings you conducted]

## 5.2 Stakeholders and actors
| Actor | Goal |
|---|---|
| AP Officer | Enter invoices quickly and learn early about problems |
| Manager | Approve legitimate spending and see risks before approving |
| Auditor | Investigate suspicious activity with full evidence |
| Administrator | Maintain users, vendors and rule configuration |
| ML Service (system actor) | Analyse invoices and return explainable results |

## 5.3 Functional requirements
The full table (FR-01 to FR-18) is in [../requirements.md](../requirements.md#1-functional-requirements). Copy it here for the report.

## 5.4 Non-functional requirements
The full table (NFR-01 to NFR-12) is in [../requirements.md](../requirements.md#2-non-functional-requirements).

## 5.5 Prioritisation (MoSCoW)
| Must | Should | Could | Won't (this version) |
|---|---|---|---|
| Auth, RBAC, vendors, invoices, CSV import, duplicate detection, rules, Isolation Forest, risk score, explanations, workflow, audit | Notifications, simulated payment, PDF export | Email notifications, Celery async processing, dark mode | OCR, real payments, ERP integration, cloud deployment |

## 5.6 Use cases
See the use case diagram in [../diagrams.md](../diagrams.md#1-use-case-diagram).

### Example use-case description: UC6 Submit Invoice
| Field | Description |
|---|---|
| Actor | AP Officer |
| Precondition | Logged in. Invoice exists in DRAFT |
| Main flow | 1. Officer opens the invoice. 2. Clicks Submit. 3. System analyses it. 4. System shows the risk score and reasons. 5. System routes the invoice |
| Alternative flow | 3a. ML service unavailable → invoice routed to Manager review with "analysis failed" |
| Postcondition | Invoice is APPROVED, UNDER_REVIEW or BLOCKED. Audit log entry exists |
