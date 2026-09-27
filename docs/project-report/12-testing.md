# Chapter 12: Testing

> Draft material with the real results of Phase 15–16. Rewrite in your own words; keep the numbers.

## 12.1 Strategy
Tests were written together with each phase, not at the end: unit tests (similarity functions, rules, risk scorer, validators), API tests (status codes, permissions, error format), integration tests (Django → mocked ML service → routing), five live end-to-end tests against the real ML service and trained model, and frontend component and page tests. In Phase 15 coverage was measured and tests were added where a defect would matter most (settings validation, reviewer assignment, session handling, role-based page access). Details in [../testing.md](../testing.md).

## 12.2 Test environment
Windows 11, Python 3.11.9, Node.js 24, PostgreSQL 17 (the Django test runner creates and removes a temporary test database). Tools: Django test runner + `coverage.py`, pytest + `pytest-cov`, Vitest + React Testing Library + V8 coverage. `scripts\run_tests.ps1` runs every suite and prints a summary.

## 12.3 Test results
| Suite | Tests | Passed | Failed | Coverage |
|---|---|---|---|---|
| Django (incl. 5 live end-to-end tests run with `ML_LIVE_TESTS=1`) | 257 | 257 | 0 | 96% with the live tests, 95% without (statements + branches) |
| FastAPI / ML | 199 | 199 | 0 | 98% (statements + branches) |
| Frontend | 166 | 166 | 0 | 74% of lines |
| **Total** | **622** | **622** | **0** | |

In a normal run (ML service not required) the Django suite reports the 5 live tests as skipped. Frontend lint and production build are clean.

[INSERT TEST RESULTS screenshots of terminal output: scripts\run_tests.ps1 summary]

## 12.4 Sample test cases
Each case is an automated test; the “Actual” column is what the test asserts and observed.

| ID | Description | Input | Expected | Actual | Status | Automated test |
|---|---|---|---|---|---|---|
| TC-01 | Login with valid credentials | `ap_officer` / demo password | 200 + tokens | 200 with `access`, `refresh`, `user` | Pass | `common/test_report_cases.py::test_tc01…` |
| TC-02 | AP officer tries to approve | POST approve as AP (even if assigned) | 403 | 403, invoice still *Under review* | Pass | `…::test_tc02…` |
| TC-03 | Negative amount | amount = -5 | 400 | 400 `VALIDATION_ERROR` with a message for `amount` | Pass | `…::test_tc03…` |
| TC-04 | Near-duplicate | `INV1001` vs `INV-1001`, same vendor/amount | duplicate score ≥ 80 | ≥ 95 | Pass | `ml-service/tests/test_duplicate_detector.py::test_documented_example_scores_high` |
| TC-05 | Split purchase | 3 × ~9,800 within the window | SPLIT_PURCHASE signal | signal raised | Pass | `ml-service/tests/test_rules.py::test_classic_split` |
| TC-06 | Critical risk | score 85 (CRITICAL) | status BLOCKED | BLOCKED | Pass | `common/test_report_cases.py::test_tc06…` |
| TC-07 | ML service down | analysis call fails | ANALYSIS_FAILED, Manager review | ANALYSIS_FAILED, pending MANAGER approval | Pass | `…::test_tc07…` |
| TC-08 | Reject without comment | empty comment | 400 | 400, approval still PENDING | Pass | `…::test_tc08…` |

## 12.5 Demo scenario results
Observed with the real trained model (live end-to-end tests, re-run in Phase 15) and with `python manage.py seed_data` (Phase 14).

| Scenario | Expected | Observed score / level (live test) | Observed with `seed_data` | Pass |
|---|---|---|---|---|
| 1 Normal | LOW | 0 LOW, approved automatically | 0 LOW, approved and paid (simulated) | ✔ |
| 2 Duplicate | HIGH/CRITICAL | 60 HIGH, 98% similar to INV-1001 → Auditor | 60 HIGH → Auditor | ✔ |
| 3 Unusual (Sunday 02:17, ~9× average) | ≥ MEDIUM | 40 MEDIUM → Manager | 40 MEDIUM → Manager | ✔ |
| 4 Split | ≥ MEDIUM | 56 MEDIUM → Manager | 70 HIGH → Auditor (also a near-duplicate) | ✔ |
| 5 Bank change | HIGH | 60 HIGH → Auditor | 60 HIGH → Auditor | ✔ |

## 12.6 Defects found by testing (examples)
| Found by | Defect | Fix |
|---|---|---|
| Timing-dependent test failures | Records with identical timestamps sorted unpredictably | Id as tie-breaker in every ordering |
| Browser check (Phase 12) | A closed alert could be set back to “in review” | Status check (409) + tests |
| Browser check (Phase 13) | Negative “average time to decide” | Inconsistent timestamps ignored + test |
| Coverage review (Phase 15) | Settings validators and reviewer assignment partly untested | Full rejection-path tests (100%) |
| Hybrid evaluation (Phase 16) | One strong signal alone never reached review | Two escalation floors (Chapter 11.7) |
