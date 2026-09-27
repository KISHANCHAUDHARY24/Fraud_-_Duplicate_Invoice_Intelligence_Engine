# Testing Strategy

> **Status:** ✅ Final results (Phase 16, 2026-09-24): **622 automated tests, all passing**, coverage 95% (Django; 96% with the live tests) · 98% (ML) · 74% (frontend lines). See §4. `scripts\run_tests.ps1` runs everything.

## 1. Levels
| Level | Tool | What |
|---|---|---|
| Unit | Django `TestCase` / pytest | services, validators, similarity functions, risk scorer |
| API | DRF `APIClient`, FastAPI `TestClient` | endpoints, status codes, permissions, error shapes |
| ML | pytest | feature engineering, model loading, prediction shape/range |
| Integration | Django tests with the ML client **mocked** + one live smoke test | submit → analyse → route |
| Frontend | Vitest + React Testing Library | components and key flows |
| Manual / demo | Checklist below | the 5 demo scenarios end-to-end |

## 2. Commands (PowerShell)
```powershell
# Django (uses a temporary PostgreSQL test DB; the DB user needs CREATEDB)
cd backend; .\venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt        # once: adds coverage
python manage.py test
python -m coverage run manage.py test; python -m coverage report     # settings in backend\.coveragerc
python -m coverage html                              # browsable report in backend\htmlcov\index.html

# FastAPI + ML (python -m pytest also works where pytest.exe is blocked)
cd ml-service; .\venv\Scripts\Activate.ps1
python -m pytest
python -m pytest --cov                               # coverage (settings in ml-service\.coveragerc)

# React
cd frontend
npm test
npm run coverage                                     # summary + frontend\coverage\index.html
```

## 3. Planned test cases

### Django
| Area | Cases |
|---|---|
| Authentication | login OK / bad password (401, generic message) / refresh / logout blacklists / inactive user cannot log in |
| Permissions | AP cannot approve (403). Manager cannot see another department's unassigned invoice (404). Auditor can read audit logs. AP cannot read audit logs (403). Only Admin changes settings |
| Invoice creation | valid → 201 DRAFT. Audit entry created |
| Invoice validation | amount ≤ 0, due < invoice date, future invoice date, inactive vendor, exact duplicate (409) |
| CSV import | missing column, bad amount on one row (partial success + row errors), unknown vendor, empty file, non-CSV file |
| Vendor | create, masked bank account in response, bank change deactivates the old account and raises an alert |
| Workflow | each routing branch (LOW auto, LOW > threshold, MEDIUM, HIGH, CRITICAL, ML down). Illegal transition 409. Self-approval blocked. Reject requires a comment |
| Audit | approve/reject/settings change each write one AuditLog with old/new values. No update/delete API |

### FastAPI / ML
| Area | Cases |
|---|---|
| Health | 200, `model_loaded` flag |
| Duplicate endpoint | INV-1001 vs INV1001 → ≥ 80. Unrelated → < 50. Empty candidates → 0 |
| Fraud endpoint | valid payload → score in 0–100 with signals. Missing field → 422 in error shape. Missing API key → 401 |
| Similarity | Levenshtein ratio, Jaro-Winkler, token similarity, OCR map, amount/date similarity edge cases |
| Rules | each rule fires / does not fire at its boundary. Split detection with 3 invoices |
| Risk scoring | 0 signals → 0 LOW. Cap at 100. Floors. Boundaries 29/30, 59/60, 79/80 |
| Feature engineering | expected columns and order. Weekend/off-hours flags. Cyclical encoding range |
| Model | loads from disk. Predicts on one row. Score in [0, 1]. Graceful fallback when the file is missing |

### Frontend
RiskBadge renders text + icon for each level · ProtectedRoute redirects unauthenticated users · Login form shows the backend error message · Invoice table renders empty state · ConfirmDialog requires a comment for reject.

## 3b. Live end-to-end test (Phase 9)
`backend/fraud/test_live_e2e.py` runs the five demo scenarios through the **real** Django API → **real** FastAPI → **real** trained model. It is skipped in the normal suite. To run it:
```powershell
# window 1
cd ml-service; .\venv\Scripts\Activate.ps1; python -m uvicorn main:app --port 8001
# window 2
cd backend; .\venv\Scripts\Activate.ps1
$env:ML_LIVE_TESTS = "1"; python manage.py test fraud.test_live_e2e -v 2
```
Result (Phase 9): **5/5 passed** (0 LOW auto-approved · 60 HIGH auditor · 40 MEDIUM manager · 56 MEDIUM manager · 60 HIGH auditor).
Re-run in Phase 15 as part of the full suite: **5/5 passed** with identical scores.

## 4. Results (Phase 15, 2026-09-24)
| Suite | Tests | Passed | Failed | Coverage |
|---|---|---|---|---|
| Django (incl. 5 live end-to-end tests, `ML_LIVE_TESTS=1`) | 257 | 257 | 0 | **96%** with the live tests, 95% without (statements + branches, `coverage.py`) |
| FastAPI / ML | 199 | 199 | 0 | **98%** statements + branches (`pytest-cov`) |
| Frontend | 166 | 166 | 0 | **74%** lines · 73% statements · 71% branches (V8) |
| **Total** | **622** | **622** | **0** | |

Phase 16 added the report's sample test cases as tests (`backend/common/test_report_cases.py`, TC-01…TC-08) and tests for the two new escalation floors.

Without `ML_LIVE_TESTS=1` the Django suite reports 257 tests with 5 skipped. Frontend lint (oxlint) and production build are clean.

[INSERT TEST RESULTS SCREENSHOT]

### 4.1 How the coverage gaps were chosen
Coverage was measured first, then tests were added where a bug would matter most, not where the percentage was cheapest:

| Area | Before | After | New tests |
|---|---|---|---|
| Settings validators (a bad value silently breaks detection) | 72% | 100% | Every rejection path for all 17 settings; every default passes its own validator (`system_settings/test_validators.py`) |
| Reviewer assignment (department → fewest pending → fallbacks, never the submitter) | 80% | 100% | `accounts/test_assignment.py` |
| ML vendor patterns and duplicate explanations | 79% / 86% | 100% / 94% | `tests/test_vendor_patterns.py` |
| Frontend overall | 44% | 74% | Route table × roles smoke test (49 cases), session restore / expiry / cross-tab sign-out, invoice page actions per role and status, CSV import incl. “submit all”, bank-account change confirmation, notification bell, formatting helpers |

**Still below 100%, by choice:** chart drawing code (Recharts renders nothing measurable in jsdom; every chart has a table view that is tested through `ChartCard`), Django admin registrations, and defensive branches that need a broken database to reach.

### 4.2 Route-table smoke test
`src/App.test.jsx` renders every page for every role (12 routes × 4 roles) and expects either the page heading or “You do not have access to this page”. The expected table is written from `backend/accounts/capabilities.py`, so a route guarded by the wrong capability fails the test.

### 4.3 Security checks (Phase 15)
| Check | Result |
|---|---|
| Secrets in the repository | All three `.env` files, virtual environments, `node_modules`, the trained model, generated data and coverage output are git-ignored. The 6 secret values in the `.env` files were searched for in all 392 committable files: **none found** |
| `python manage.py check --deploy` | With `DEBUG=False HTTPS=True`: only W005 (HSTS include subdomains) and W021 (HSTS preload) remain; both are deliberate opt-ins because they are hard to undo (see deployment.md). Without `HTTPS=True` the four HTTPS warnings are expected on local `http://` |
| `npm audit` | 0 vulnerabilities |
| Authorization | Object-level scoping (404 outside scope), capability checks per action, self-approval and self-resolution blocked: covered by the Django API tests; UI gating by the route smoke test |
| CSV injection, masked bank accounts, audit trail | Covered by `reports/test_exports.py`, `vendors/test_api.py`, `audit/test_api.py` |

## 5. Demo scenario checklist
| # | Scenario | Expected | Result |
|---|---|---|---|
| 1 | Normal invoice | LOW, auto-approved or standard approval | ✅ end-to-end: 0 LOW, auto-approved (Phase 9) |
| 2 | Duplicate invoice | Duplicate score ≥ 90, HIGH or CRITICAL, matched invoice shown | ✅ end-to-end: 98%, 60 HIGH → Auditor |
| 3 | Unusual invoice (Sunday 02:17, 9× vendor average) | TIME + AMOUNT + ML signals, MEDIUM or higher | ✅ end-to-end: 40 MEDIUM → Manager |
| 4 | Split invoice (3 × ~9,800 in 4 days) | "Potential Split Purchase", MEDIUM or higher, Manager review | ✅ end-to-end: 56 MEDIUM → Manager |
| 5 | Bank account change | BANK_ACCOUNT_CHANGE, HIGH, Auditor review | ✅ end-to-end: 60 HIGH → Auditor |

**Reproduce with demo data (Phase 14):** `python manage.py seed_data` builds all five with the live model and checks each result (`OK` / `CHECK`). Result on 2026-09-24: 5/5 OK: normal 0 LOW → approved and paid (simulated) · duplicate `INV1001` 60 HIGH → Auditor · unusual `AC-2003` (Sunday 02:17, 9× average) 40 MEDIUM → Manager · split `BP-3003` 70 HIGH → Auditor · bank change `FL-2005` 60 HIGH → Auditor. `demo/tests.py` covers the command itself with the ML service mocked (accounts, consistent history, fixed submission times, idempotency, reset scope, refusal without DEBUG).
