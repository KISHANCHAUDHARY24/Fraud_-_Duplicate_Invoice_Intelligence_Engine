# Documentation Index

> **Status legend:** 📐 *Design* = written in Phase 0 as the specification · ✅ *Implemented* = updated after the feature was built and tested.

| Document | Purpose | Status |
|---|---|---|
| [development-plan.md](development-plan.md) | Phase-by-phase build plan and progress tracker | 📐 |
| [architecture.md](architecture.md) | System components, communication, request flows | 📐 |
| [installation.md](installation.md) | Windows setup: Python, Node, PostgreSQL, env vars | 📐 |
| [database.md](database.md) | Models, ER diagram, constraints, indexes | 📐 |
| [api.md](api.md) | All Django REST and FastAPI endpoints | 📐 |
| [authentication.md](authentication.md) | JWT flow, roles, permission matrix | 📐 |
| [fraud-detection.md](fraud-detection.md) | Hybrid rule + ML + NLP detection design | 📐 |
| [duplicate-detection.md](duplicate-detection.md) | Fuzzy matching algorithms and combined score | 📐 |
| [machine-learning.md](machine-learning.md) | Dataset, features, Isolation Forest pipeline | 📐 |
| [risk-scoring.md](risk-scoring.md) | Signal weights, score calculation, risk levels | 📐 |
| [approval-workflow.md](approval-workflow.md) | Statuses, routing, decisions, payments (simulated) | 📐 |
| [frontend.md](frontend.md) | React structure, pages, components, state | 📐 |
| [testing.md](testing.md) | Test strategy and commands | 📐 |
| [deployment.md](deployment.md) | Windows local deployment (no Docker) | 📐 |
| [troubleshooting.md](troubleshooting.md) | Common Windows problems and fixes | 📐 |
| [user-guide.md](user-guide.md) | End-user manual | 📐 |
| [diagrams.md](diagrams.md) | UML / SE diagrams (use case, sequence, class, DFD…) | 📐 |
| [requirements.md](requirements.md) | Functional and non-functional requirements | 📐 |
| [project-report/](project-report/) | University report chapters (drafts + placeholders) | 📐 |

## Terminology used throughout

| Term | Meaning |
|---|---|
| **Signal** | One observed risk indicator, e.g. "amount is 1% below approval threshold" |
| **Risk score** | 0–100 weighted combination of signals. **Not** a probability of fraud |
| **Risk level** | LOW / MEDIUM / HIGH / CRITICAL band derived from the score |
| **Alert** | A record created when an invoice reaches MEDIUM risk or higher, for a human to review |
| **Possible duplicate** | An invoice whose combined similarity to an earlier one exceeds the threshold |
| **Potential split purchase** | Several invoices from one vendor, close in time, each just below the approval threshold |
| **Confirmed issue** | Only a **human reviewer** can set this outcome. The system never does |
