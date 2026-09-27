# Requirements Specification

> **Status:** ✅ All Must requirements implemented and tested (see testing.md and project-report/12–13).

## 1. Functional requirements
| ID | Requirement | Priority | Phase |
|---|---|---|---|
| FR-01 | Users authenticate with username/password and receive JWT tokens. They can log out and change their password | Must | 3 |
| FR-02 | The system supports roles ADMIN, AP_OFFICER, MANAGER, AUDITOR. Admin manages users and roles | Must | 3 |
| FR-03 | Users can create, view, update and deactivate vendors. Bank account history is kept and displayed masked | Must | 4 |
| FR-04 | AP officers can create invoices manually and upload them in bulk via CSV and JSON | Must | 4 |
| FR-05 | The system validates invoices (required fields, types, positive amounts, date logic, active vendor, exact-duplicate constraint) and returns meaningful errors | Must | 4 |
| FR-06 | The system detects possible duplicate invoices using fuzzy matching on number, vendor, amount, date and description | Must | 5 |
| FR-07 | The system analyses invoices with rules (threshold, split purchase, unusual time, round amount, bank change, amount deviation) and an Isolation Forest model | Must | 6–7 |
| FR-08 | The system computes a 0–100 risk score and a risk level, with an explanation for every contributing signal | Must | 8 |
| FR-09 | Invoices are routed by risk level (auto / manager / auditor / blocked). Reviewers can approve, reject, request clarification and escalate | Must | 9 |
| FR-10 | Every important action is recorded in an append-only audit log | Must | 4 |
| FR-11 | Dashboard and analytics show KPIs and charts with date filters | Must | 11, 13 |
| FR-12 | Users can export invoice, fraud, vendor, approval and audit reports as CSV and PDF | Must | 13 |
| FR-13 | Users receive in-app notifications for relevant events | Should | 9 |
| FR-14 | Auditors can investigate alerts and record the outcome (cleared / confirmed issue) | Must | 12 |
| FR-15 | Admin can configure thresholds, weights and working hours without code changes | Must | 4, 13 |
| FR-16 | Invoices can be searched, filtered, sorted and paginated | Must | 4, 11 |
| FR-17 | Payment is simulated for approved invoices, and blocked for critical ones | Should | 9 |
| FR-18 | A seed command creates realistic demo data covering 5 demo scenarios | Must | 14 |

## 2. Non-functional requirements
| ID | Category | Requirement |
|---|---|---|
| NFR-01 | Security | Passwords hashed (PBKDF2). JWT with expiry and refresh rotation. Backend role checks on every endpoint. Secrets only in `.env`. Bank numbers stored as last-4 + keyed hash. CORS restricted. No tracebacks exposed |
| NFR-02 | Performance | Single-invoice analysis completes in < 2 s locally. List endpoints return in < 500 ms for 10k invoices (indexed queries, pagination) |
| NFR-03 | Scalability | ML service is stateless and separately deployable. Analysis can later be moved to a Celery queue without API changes |
| NFR-04 | Maintainability | Layered code (models / serializers / services / views). Configurable business rules. Documented APIs. Consistent naming |
| NFR-05 | Usability | Consistent enterprise UI. Loading/empty/error states. Risk shown with text and icons, not only colour. Plain-language explanations |
| NFR-06 | Reliability | If the ML service fails, the invoice is still saved and routed to manual review (fail safe). Workflow actions are atomic transactions |
| NFR-07 | Availability | Each service can be restarted independently. A health endpoint exists on each service |
| NFR-08 | Data integrity | FK constraints, unique (vendor, invoice_number), check constraints on amounts, enforced state transitions, append-only audit log |
| NFR-09 | Explainability | Every score is traceable to individual signals with points. The raw ML response is stored |
| NFR-10 | Portability | Runs natively on Windows 10/11 without Docker/WSL |
| NFR-11 | Testability | Automated tests for backend, ML service and key frontend components |
| NFR-12 | Ethics | The system is described and presented as decision support, never as an automated fraud verdict |
