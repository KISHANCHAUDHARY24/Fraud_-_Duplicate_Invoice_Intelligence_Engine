# Chapter 7: System Design

## 7.1 Design principles
- **Separation of concerns:** UI (React), business logic and data (Django), intelligence (FastAPI).
- **Single source of truth:** only Django writes to the database.
- **Explainability by construction:** every detector emits human-readable signals with points.
- **Configurability:** business thresholds live in a settings table, not in code.
- **Fail safe:** if analysis fails, the invoice goes to manual review, never auto-approval.
- **Least privilege:** role checks on every endpoint and object-level scoping.

## 7.2 Diagrams
Include these (source in [../diagrams.md](../diagrams.md)):
- Figure 7.1 Use case diagram
- Figure 7.2 Activity diagram: invoice lifecycle
- Figure 7.3 Sequence diagram: fraud analysis
- Figure 7.4 Sequence diagram: manager decision
- Figure 7.5 Class diagram
- Figure 7.6 Data flow diagrams (Level 0 and 1)
- Figure 7.7 Invoice state diagram ([../approval-workflow.md](../approval-workflow.md#2-state-diagram))

[INSERT exported diagram images]

## 7.3 Detection design
- Duplicate detection: see [../duplicate-detection.md](../duplicate-detection.md)
- Rules: see [../fraud-detection.md](../fraud-detection.md)
- Risk scoring: see [../risk-scoring.md](../risk-scoring.md)

## 7.4 User interface design
Enterprise dashboard layout with a sidebar, top bar, KPI cards, charts and data tables. Risk is shown with text + icon + colour for accessibility. [INSERT wireframes or final screenshots]

## 7.5 Security design
JWT authentication, PBKDF2 password hashing, RBAC, masked and hashed bank data, environment-based secrets, CORS restriction, consistent error responses without internal details, append-only audit log. See [../authentication.md](../authentication.md).
