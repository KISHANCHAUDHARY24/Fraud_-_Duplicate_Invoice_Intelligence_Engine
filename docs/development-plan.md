# Development Plan (Phase-wise)

> **Status:** ✅ All 17 phases (0–16) complete and verified (2026-09-24). This file is the master tracker. Tick the checkboxes as phases finish.

The project is built **incrementally**. Each phase ends with something you can run and test, and with its documentation updated. Do not start a phase until the previous one is working.

## Phase overview

| Phase | Name | Maps to original steps | Deliverable you can demo | Docs updated |
|---|---|---|---|---|
| 0 | Planning & documentation | 1 | Complete design docs (this folder) | all (design version) |
| 1 | Foundation | 2, 3, 4 | Folder structure, Git repo, PostgreSQL DB, Django boots and connects | installation.md |
| 2 | Database models | 5 | All models migrated, visible in Django admin | database.md |
| 3 | Authentication & RBAC | 6 | JWT login/refresh, 4 roles, permission classes | authentication.md |
| 4 | Core Django APIs | 7 | Vendors, invoices, CSV/JSON import, audit logs, notifications, settings APIs | api.md |
| 5 | FastAPI service + duplicate detection | 8, 9 | `/health`, `/api/v1/duplicate/check`, Swagger at `/docs` | duplicate-detection.md |
| 6 | Fraud rules + feature engineering | 10 | Rule-based signals (threshold, time, round amount, split, bank change) | fraud-detection.md |
| 7 | Synthetic dataset + Isolation Forest | 11 | `scripts/generate_dataset.py`, `scripts/train_model.py`, saved model | machine-learning.md |
| 8 | Risk scoring + explainability | 12 | `/api/v1/fraud/analyze`, `/api/v1/risk/score` with reasons | risk-scoring.md |
| 9 | Django ↔ FastAPI integration + routing | 13, 19 (backend) | Submitting an invoice triggers analysis, stores results, routes to approver | approval-workflow.md |
| 10 | React setup + auth + layout | 14, 15 | Login page, protected routes, sidebar/topbar shell | frontend.md |
| 11 | Dashboard + invoice management | 16, 17 | KPI cards, charts, invoice table, upload page, invoice detail | frontend.md, user-guide.md |
| 12 | Vendors, fraud investigation, approvals UI | 18, 19 (UI) | Vendor dashboard, investigation page, approval queue | user-guide.md |
| 13 | Analytics, audit logs, reports, settings | 20, 21, 22 | Analytics page, audit log viewer, CSV/PDF export, settings page | user-guide.md, api.md |
| 14 | Seed data + demo scenarios | — | `python manage.py seed_data` with the 5 demo scenarios | user-guide.md |
| 15 | Testing | 23 | Django, FastAPI, ML and frontend test suites passing | testing.md |
| 16 | Final integration & report material | 24, 25 | Full end-to-end run, final docs, report chapters filled with real results | everything |

## Phase checklist

- [x] **Phase 0** — Planning & documentation
- [x] **Phase 1** — Foundation
- [x] **Phase 2** — Database models
- [x] **Phase 3** — Authentication & RBAC
- [x] **Phase 4** — Core Django APIs
- [x] **Phase 5** — FastAPI + duplicate detection
- [x] **Phase 6** — Fraud rules + feature engineering
- [x] **Phase 7** — Dataset + Isolation Forest
- [x] **Phase 8** — Risk scoring + explainability
- [x] **Phase 9** — Django ↔ FastAPI integration + routing
- [x] **Phase 10** — React setup + auth
- [x] **Phase 11** — Dashboard + invoices UI
- [x] **Phase 12** — Vendors, investigation, approvals UI
- [x] **Phase 13** — Analytics, audit, reports, settings UI
- [x] **Phase 14** — Seed data + demo scenarios
- [x] **Phase 15** — Testing
- [x] **Phase 16** — Final integration & report

## Verification log
| Phase | Verified | Evidence |
|---|---|---|
| 1 | 2026-09-24 | `GET /api/health/` → `{"status":"ok","database":"ok"}`. DB `expense_intelligence` (UTF8, owner `expense_app`). CORS allows only `http://localhost:5173` |
| 2 | 2026-09-24 | All migrations applied. 4 roles and 17 default settings seeded. Superuser created |
| 3 | 2026-09-24 | 401 `NOT_AUTHENTICATED` / `TOKEN_INVALID` on the live server |
| 1–3 | 2026-09-24 | `python manage.py test` → **91 tests, OK** (≈40 s, PostgreSQL test DB) |
| 4 | 2026-09-24 | `python manage.py test` → **155 tests, OK** on two consecutive runs (≈100 s). Timestamp-tie ordering bug found and fixed (database.md §4.5) |
| 16 | 2026-09-24 | **622 tests, all passing**: Django 257, ML 199, frontend 166. Hybrid evaluation (`scripts/evaluate_hybrid.py`): the combined system reaches recall 0.682 at precision 0.400 on the synthetic hold-out (ML alone 0.284 / 0.417); the first run exposed that one strong signal never reached review, fixed with two escalation floors (+ migration that respects Admin changes). Frontend first download 262 → 115 kB (pages loaded on demand). `start_all.ps1` and `run_tests.ps1` added; full chain re-run through the start script. Performance measured (analysis 80 ms median). Project report chapters 10–14 and 16 filled with real results |
| 15 | 2026-09-24 | **612 tests, all passing**: Django 251 (incl. the 5 live end-to-end tests, identical scores to Phase 9), ML 195, frontend 166. Coverage: Django 96%, ML 98%, frontend 74% (was 44%). New: settings validators and reviewer assignment at 100%, route table × roles smoke test, session handling, invoice page actions, import, bank change, notifications. Security: no secret in any committable file, `check --deploy` clean apart from two deliberate HSTS opt-ins (new `HTTPS` switch), `npm audit` 0 vulnerabilities |
| 14 | 2026-09-24 | Django **239 tests OK** (5 live skipped; 10 new), ML **183 passed**, frontend **90 passed**, build + lint clean. `python manage.py seed_data` on a fresh database with the live model: **5/5 scenarios OK** in ~3 s (normal 0 LOW → approved + paid · duplicate 60 HIGH → Auditor · unusual 40 MEDIUM → Manager · split 70 HIGH → Auditor · bank change 60 HIGH → Auditor); a second run added nothing. Seeded data checked in the browser as the demo auditor. Fixed: screen-reader text in risk badges widened narrow pages; two broken `Activate.ps1` lines in the docs |
| 13 | 2026-09-24 | Django **229 tests OK** (5 live skipped; 21 new), ML **183 passed**, frontend **90 passed**, build + lint clean. Browser check on the preview database: analytics for the default 12 months and “Last 3 months” (URL-kept), audit log with filters and before/after details, CSV + PDF exports (PDFs rendered and inspected: repeated header, page numbers, masked accounts, disclaimer), settings edit → save → reset as Admin, read-only settings and 2 reports for a Manager, audit log blocked for a Manager. Fixed: negative “time to decide” from inconsistent timestamps, report times in UTC instead of the business timezone, “Reset to default” shown for unchanged JSON settings (JSONB key order), a 13-month default range, duplicate entity types (`distinct()` with default ordering), unreadable errors on failed downloads (blob) |
| 12 | 2026-09-24 | Django **214 tests OK** (5 live skipped), ML **183 passed**, frontend **72 passed**, build + lint clean. Browser check on the preview database, full chain as three roles: auditor starts review → resolves the critical alert as *Cleared* (invoice BLOCKED → UNDER_REVIEW) → approves it from the queue; admin simulates the payment (PAID, `SIM-PAY-…`). Manager escalates from the invoice page. Admin changes a bank account (validation, confirmation, “Bank account changed today” indicator), creates a vendor and is stopped on an equivalent name. Fixed: a closed alert could be reopened by mark-reviewed (now 409), blank screen when the window scrolled (absolute `sr-only` text escaping `<main>`), pages wider than a phone screen (grid `min-width`), dialogs inheriting table-cell styles (now a portal), squeezed icon buttons, “0 day(s) ago” wording |
| 11 | 2026-09-24 | Django **211 tests OK** (5 live tests skipped; 6 new dashboard tests). Frontend `npm test` **54 passed**, build + lint clean. Browser check on a separate preview database (real Django → FastAPI → model): dashboard KPIs + 6 charts, list filters in the URL, search, detail page (gauge, reasons, signals, duplicate comparison, history), manual submit → auto-approved, CSV import with per-row errors, draft edit. Role scoping of `/dashboard/summary/` checked for AP officer / Manager / Auditor. Fixed: squeezed risk explanation on medium screens, duplicated "missing column" text |
| 10 | 2026-09-24 | Frontend: `npm test` **33 passed**, build + lint clean. Browser check: session restore, role-based sidebar, 403 page, profile, notifications, sign-out with server-side blacklist. Fixed: npm scripts broken by `&` in the folder path |
| 9 | 2026-09-24 | Django **205 tests OK** (5 live tests skipped by default) on repeated runs. Live end-to-end over real HTTP: **5/5 demo scenarios** routed correctly. Fixed: false "new vendor" signal, timestamp tie in bank-account lookup. Auditors given read access to all invoices |
| 8 | 2026-09-24 | `ml-service`: **183 passed**. `/fraud/analyze` + `/risk/score` live. 5 demo scenarios: LOW 0 · HIGH 60 · MEDIUM 40 · MEDIUM 58 · HIGH 60. Finding: without the ML model scenario 3 drops to LOW, so Phase 9 must not auto-approve when ML is skipped |
| 7 | 2026-09-24 | `ml-service`: **146 passed**. Dataset 5,420 invoices (4.8% anomalies). Hold-out ROC-AUC 0.887, precision 0.417, recall 0.284, F1 0.338. Model loads at startup; `/health` model_loaded true |
| 6 | 2026-09-24 | `ml-service`: `python -m pytest` → **118 passed**. Live `/api/v1/fraud/rules`: bank change + Sunday 02:17 + near threshold + split purchase all detected. Windows `tzdata` issue found and fixed |
| 5 | 2026-09-24 | `ml-service`: `python -m pytest` → **54 passed**. Live: `/health` 200, `/docs` 200, no key → 401, `INV-100I` vs `INV-1001` → score 97 with 5 reasons |

## Working rules for every phase

1. Explain the purpose and architecture of the phase.
2. List the files involved and where they belong.
3. Implement with complete file contents.
4. Explain the important code.
5. Give Windows PowerShell commands to run/test it and the expected output.
6. Update the relevant doc(s) and tick the checklist above.
7. State the next step.

## Key design decisions (locked in Phase 0)

| Decision | Choice | Why |
|---|---|---|
| Source of truth | Django + PostgreSQL | One place owns data; FastAPI stays stateless |
| ML service data access | FastAPI **never** touches the DB; Django sends the invoice + context (history, candidates, settings) | Simpler, testable, no duplicated DB config |
| Django → FastAPI call | Synchronous HTTP (`requests`, 10 s timeout) | No Redis/Celery needed for v1 |
| Service-to-service auth | Shared secret header `X-Internal-API-Key` | Simple and adequate for localhost |
| JWT library | `djangorestframework-simplejwt` | Standard, well documented |
| Settings app name | `system_settings` (not `settings`) | Avoids confusion with `config/settings.py` and `django.conf.settings` |
| Bank account storage | Store only bank name, last 4 digits and a keyed hash (HMAC-SHA256) | Enables change detection without storing full account numbers |
| Exact duplicates | DB unique constraint on (vendor, invoice_number) rejects them; *near*-duplicates are saved and flagged | Hard rule vs. intelligent detection |
| Model files (`*.pkl`) | Not committed; regenerated by `scripts/train_model.py` | Reproducible, avoids binary blobs in Git |
| PDF export | `reportlab` (pure Python) | Works on Windows without system libraries |
| Frontend tests | Vitest + React Testing Library | Native to Vite |
| Async processing | Optional Celery/Redis only after Phase 16 | Keeps dev setup simple |
