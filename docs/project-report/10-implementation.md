# Chapter 10: Implementation

> Draft material based on the finished system (Phase 16). Rewrite in your own words before submission, and choose 3–5 short code excerpts from the files named below (a few lines each, with an explanation), not whole files.

## 10.1 Development environment
| Item | Version |
|---|---|
| OS | Windows 11 Home (no Docker, WSL or Linux) |
| Python | 3.11.9 |
| Node.js | 24.13 |
| PostgreSQL | 17.10 |
| IDE | [INSERT the editor you used] |
| Backend libraries | Django 5.2.17, Django REST Framework 3.18.1, SimpleJWT 5.5.1, django-filter 26.1, django-cors-headers 4.9.0, psycopg 3.3.6, reportlab 4.5.1 |
| ML service libraries | FastAPI 0.141.1, Uvicorn 0.53.0, Pydantic 2, RapidFuzz 3.14.6, scikit-learn 1.9.1, pandas 3.0.6, NumPy 2.4.6, joblib 1.6.0 |
| Frontend libraries | React 19.2, React Router 7.18, Axios 1.20, Recharts 3.10, Tailwind CSS 4.3, lucide-react, Vite 8, Vitest 5 |

## 10.2 Backend (Django)
- **Project structure.** One Django project (`config`) and one app per responsibility: `accounts` (users, roles, capabilities), `vendors`, `invoices`, `fraud` (analyses, signals, alerts, ML client), `approvals` (workflow, routing, simulated payments), `audit`, `notifications`, `system_settings`, `reports` (dashboard, analytics, exports) and `demo` (the `seed_data` command).
- **Custom user model and roles.** `accounts/models.py` defines `User` with a `Role` (Admin, AP Officer, Manager, Auditor). Permissions are *capabilities* (e.g. `approvals.decide`) mapped to roles in `accounts/capabilities.py`; the same names are used by the React UI. Suggested excerpt: `ROLE_CAPABILITIES` and `ActionCapabilityMixin` (`accounts/permissions.py`), which refuses any view action without a declared capability ("fail closed").
- **Object-level scoping.** `invoices/selectors.py` `visible_invoices(user)`: AP officers see their own invoices, managers their department's and those assigned to them, auditors and admins all. Invoices outside the scope return 404, so their existence is not revealed.
- **Invoice validation and CSV import.** Serializer validation (amount > 0, no future dates, due date ≥ invoice date, known active vendor) plus database constraints. `invoices/importers.py` validates each CSV row separately, saves valid rows and reports the rest with row, field and reason (partial success).
- **Service layer and audit logging.** Business rules live in `services.py` modules, not in views; every important action calls `audit.services.log_action()` with old and new values. The audit table is append-only (no update or delete API).
- **Routing engine.** `approvals/routing.py` `decide()` turns the risk level into the next step (auto-approve, Manager, Auditor, blocked) with fail-safes: if the analysis failed or the ML model was not loaded, the invoice always goes to a Manager and is never auto-approved. Suggested excerpt: `decide()`.

## 10.3 ML service (FastAPI)
- **Pydantic schemas.** Every request and response is a Pydantic model (`schemas/`), so invalid input is rejected with a readable 422 before any logic runs.
- **Similarity functions.** `utils/similarity.py`: normalised invoice numbers with OCR look-alike handling (`INV-100I` vs `INV-1001`), vendor-name similarity (token sort and Jaro-Winkler), amount, date and description similarity; `services/duplicate_detector.py` weights them 0.30/0.25/0.20/0.15/0.10.
- **Rule engine.** `services/rule_engine.py`: nine rules (duplicate, bank-account change, unusual time, near approval threshold, split purchase, round amount, amount anomaly, vendor anomaly and the ML signal). Suggested excerpt: `split_purchase_rule()`.
- **Risk scorer.** `services/risk_scorer.py`: points = weight × strength per signal, capped at 100, then *escalation floors* (e.g. a strong duplicate is at least 60 = HIGH). Every point and floor appears in the explanation.
- **Model loading at startup.** `services/anomaly_detector.py` loads the Isolation Forest, scaler and metadata once (FastAPI lifespan); if the files are missing the service still runs and says so in every response.

## 10.4 Integration
`fraud/context.py` builds the analysis payload from the database (vendor statistics, bank-account history, recent invoices, duplicate candidates, current settings); `fraud/ml_client.py` sends it with an API key and a timeout. The HTTP call happens **outside** any database transaction, and a failure is caught and recorded (`ANALYSIS_FAILED`) so an invoice is never lost. Suggested excerpt: `analyze_invoice()` in `fraud/services.py`.

## 10.5 Frontend (React)
- **Routing and protected routes.** `App.jsx` names the capability each route needs; `ProtectedRoute` shows “no access” otherwise. Pages are loaded on demand (`React.lazy`), which halved the first download (Chapter 13).
- **Axios interceptor with token refresh.** `api/client.js`: adds the JWT, refreshes it **once** when several requests fail with 401 at the same time, retries them, and turns every error into one readable message.
- **Explainable analysis.** `components/fraud/`: risk gauge, reasons with points, signal list and a field-by-field duplicate comparison.
- **Dashboard charts.** Recharts with a colour palette checked for colour-blind readers and a table view for every chart. [INSERT screenshot]
- **Fraud investigation page.** Everything about one alert on one screen, with assign / start review / resolve actions. [INSERT screenshot]

## 10.6 Challenges and solutions
Real problems met during development (details in `docs/troubleshooting.md` and `docs/frontend.md`):

| Challenge | Solution |
|---|---|
| `pip.exe` blocked by Windows Application Control | Always run `python -m pip` |
| `npm run …` failed: the `&` in the folder name breaks npm's `.cmd` launchers | npm scripts call `node …/vite.js` directly |
| First import of pandas/scikit-learn took over two minutes | Windows Defender scanning new files once; documented, no code change |
| Windows had no timezone database (`Asia/Kolkata` not found) | Added the `tzdata` package |
| Tests failing randomly: two records with the same timestamp | Every ordering uses the id as a tie-breaker |
| A resolved fraud alert could be reopened | State check added (409), with tests |
| Report times 5½ hours off | Exports use the business timezone setting |
| PostgreSQL JSONB re-orders object keys, so settings looked “changed” | Key-order-independent comparison in the settings screen |
| A strong ML or amount signal alone never reached review | Measured with `scripts/evaluate_hybrid.py`, then two escalation floors added (Chapter 11.7) |
