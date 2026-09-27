# Risk Scoring Engine

> **Status:** ✅ Implemented in Phase 8 (`ml-service/services/risk_scorer.py`, `services/fraud_detector.py`). §3 and §7 reflect the final rounding rule; §9 has measured results.

## 1. Risk indicator ≠ confirmed fraud
| | Risk indicator (what the system produces) | Confirmed issue (what only a human decides) |
|---|---|---|
| Who | Software | Auditor after investigation |
| Meaning | "This invoice has characteristics worth checking" | "We verified this invoice was improper" |
| Stored as | `risk_score`, `risk_level`, `FraudSignal` rows | `FraudAlert.outcome = CONFIRMED_ISSUE` |
| Is it a probability? | **No.** A score of 80 does not mean an 80% chance of fraud | — |

## 2. Signals and weights
Each detector returns a **strength** between 0 and 1. Points = `weight × strength`. Default weights (Admin can change them in Settings → `signal_weights`):

| Signal | Max points (weight) | Strength comes from |
|---|---|---|
| `DUPLICATE` | 30 | duplicate_score / 100 |
| `BANK_ACCOUNT_CHANGE` | 20 | 1.0 if changed within window |
| `SPLIT_PURCHASE` | 20 | pattern strength (see fraud-detection.md §3) |
| `AMOUNT_ANOMALY` | 15 | z-score mapped to 0–1 (z=3 → 0.5, z≥6 → 1) |
| `THRESHOLD_PROXIMITY` | 15 | 1 − gap%/near_threshold_percent |
| `ML_ANOMALY` | 15 | Isolation Forest anomaly score |
| `TIME_ANOMALY` | 10 | 0.6 (off-hours or weekend) / 1.0 (both) |
| `VENDOR_ANOMALY` | 10 | prior alerts / new vendor / frequency spike |
| `ROUND_AMOUNT` | 5 | 1.0 if round |

## 3. Calculation
```text
points_i    = round(weight_i × strength_i)          # rounded PER SIGNAL
score       = min(100, Σ points_i)
score       = max(score, strongest applicable floor) # see §4
```
**Why round per signal (refined in Phase 8):** the reviewer sees "+28, +20, +14 …" next to each reason, and those numbers must add up exactly to the score shown. Rounding only the total would make them differ by ±1, which undermines trust in the explanation.
The weights add up to 140, so no single signal can reach 100, but several strong signals together can. The score is **capped** (not divided by 140), so a single strong duplicate is not diluted by all the signals that did not fire.

## 4. Escalation floors (configurable `signal_floors`)
Some signals are serious enough on their own that they must reach a specific reviewer whatever else fires:

Setting format (`signal_floors`): `{"DUPLICATE": {"min_strength": 0.9, "min_score": 60}, …}`. A floor applies when that signal is present with at least `min_strength`. Only the strongest applicable floor is used.

| Condition | Minimum score | Resulting minimum level |
|---|---|---|
| DUPLICATE with duplicate_score ≥ 90 | 60 | HIGH → Auditor |
| BANK_ACCOUNT_CHANGE present | 60 | HIGH → Auditor (high-priority review) |
| SPLIT_PURCHASE present | 30 | MEDIUM → Manager |

Floors are shown in the explanation, e.g. *"Minimum score 60 (HIGH) because a very strong duplicate match must always be reviewed"*.

## 5. Risk levels (configurable `risk_level_thresholds`)
| Score | Level | Icon + label (UI never uses colour alone) |
|---|---|---|
| 0–29 | LOW | ✓ "Low risk" (green) |
| 30–59 | MEDIUM | ⚠ "Medium risk" (amber) |
| 60–79 | HIGH | ▲ "High risk" (orange) |
| 80–100 | CRITICAL | ⛔ "Critical" (red) |

## 6. Routing
| Level | Route | Invoice status |
|---|---|---|
| LOW and amount ≤ threshold | Normal approval (auto-approve if `auto_approve_low_risk`, otherwise standard approver) | APPROVED / UNDER_REVIEW |
| LOW and amount > threshold | Manager approval (Rule R1) | UNDER_REVIEW |
| MEDIUM | Manager review | UNDER_REVIEW |
| HIGH | Auditor review | UNDER_REVIEW |
| CRITICAL | Payment blocked + auditor investigation | BLOCKED |
| Analysis failed, or ML part skipped (model not loaded) | Manager review (fail safe, never auto-approved) | UNDER_REVIEW |

Details: [approval-workflow.md](approval-workflow.md).

## 7. Worked example
Invoice: 9,900 to ACME Corp, submitted Sunday 02:17, 94% similar to INV-1001, vendor bank account changed 12 days ago.

| Signal | Weight | Strength | Exact | Points |
|---|---|---|---|---|
| DUPLICATE | 30 | 0.94 | 28.2 | 28 |
| BANK_ACCOUNT_CHANGE | 20 | 1.00 | 20.0 | 20 |
| THRESHOLD_PROXIMITY | 15 | 0.90 | 13.5 | 14 |
| ML_ANOMALY | 15 | 0.71 | 10.65 | 11 |
| TIME_ANOMALY | 10 | 1.00 | 10.0 | 10 |
| **Total** | | | 82.35 | **83 (CRITICAL)** |

(This exact case is a unit test: `tests/test_risk_scorer.py::test_documented_worked_example`.)

Explanation shown to the user:
```text
Risk Score: 83/100 (CRITICAL). This is a risk indicator, not a finding of fraud.
Reasons:
✓ 94% similarity with previous invoice INV-1001            (+28)
✓ Vendor bank account differs from historical record       (+20)
✓ Amount is 1.0% below the approval threshold              (+14)
✓ Unusual combination of features (ML anomaly score 0.71)  (+11)
✓ Submitted Sunday 02:17, outside working hours            (+10)
```
Reasons are sorted by points, and each shows its contribution.

## 8. Implementation location
- `ml-service/services/risk_scorer.py`: `score(signals, config) -> RiskResult` (a pure function, easy to test).
- `ml-service/routers/risk.py`: `POST /api/v1/risk/score`.
- Tests cover: no signals → 0/LOW, cap at 100, floors, level boundaries (29/30, 59/60, 79/80), custom weights.

## 9. Implementation and measured results (Phase 8)

### 9.1 Endpoints
| Endpoint | Purpose |
|---|---|
| `POST /api/v1/fraud/analyze` | **The call Django makes per invoice.** Duplicate detection + rules + ML → score, level, `explanation[]` (ready to display), `signals[]` (full details, same order), `scoring` (breakdown, cap, floor), `duplicate` (match + reasons + top 5 candidates), `anomaly` (model, score, reasons), `features`, `routing_hints`, `warnings` |
| `POST /api/v1/risk/score` | The scorer alone: `{signals: [{type, strength, message?}], config?}` → score, level, breakdown, explanation. Useful for "what if" checks of new settings |

The `config` object accepts **Django's complete settings dictionary as-is** (unknown keys are ignored). This is tested by loading `backend/system_settings/defaults.py` inside the ML-service tests, so the two services cannot drift apart.

### 9.2 The five demo scenarios (real model `iforest-20260924-025523`, Django default settings)
| # | Scenario | Explanation (points) | Score | Level |
|---|---|---|---|---|
| 1 | Normal invoice, Tuesday 11:20 | none | 0 | LOW |
| 2 | `INV1001` vs existing `INV-1001`, same vendor, 5,000 | duplicate 98% (+29), amount 11.7σ (+15), ML 0.69 (+10), round (+5) → 59, **floor 60** | 60 | HIGH |
| 3 | Sunday 02:17, 13,500 (vendor avg 1,500) | amount 40σ (+15), ML 1.00 (+15), time (+10) | 40 | MEDIUM |
| 4 | 9,800 after 9,900 and 9,700 in 3 days | split (+20), amount (+15), threshold 2% (+12), ML 0.73 (+11) | 58 | MEDIUM |
| 5 | Vendor bank account changed 12 days ago | bank change (+20), ML 0.62 (+9) → 29, **floor 60** | 60 | HIGH |

### 9.3 Finding: what happens without the ML model
If the model files are missing, `/fraud/analyze` still works: `anomaly.model_loaded = false`, and `warnings` explains that the ML signal was skipped. The score can then be **lower**. Scenario 3 got only 15 + 10 = **25 (LOW)** without the ML signal (Phase 8; since Phase 16 the extreme-amount floor lifts it to 30 MEDIUM, see §10).
**Consequence for the workflow (implemented in Phase 9):** Django must treat "ML part skipped" like "analysis failed", i.e. **never auto-approve** such an invoice and route it to Manager review. See [approval-workflow.md](approval-workflow.md) §3.

### 9.4 Tests
`tests/test_risk_scorer.py` (points, rounding, cap at 100, each floor and its min-strength boundary, every level boundary 29/30 · 59/60 · 79/80, custom weights, invalid settings) and `tests/test_analysis_api.py` (the five scenarios with and without a model, reasons add up to the score, duplicate details attached, settings change the outcome, validation, `/risk/score`).

## 10. Calibration change in Phase 16: single-signal floors
**Problem found by measurement.** `scripts/evaluate_hybrid.py` replays the synthetic hold-out (1,772 invoices, 88 injected anomalies) through the full pipeline with a model trained only on earlier months. With the Phase 8 defaults, one strong signal on its own could never reach the review threshold (30): the ML signal gives at most 15 points and the amount rule 15. The combined system therefore caught only 10% of off-hours anomalies (the model alone: 90%) and 7% of amount spikes (model alone: 57%).

**Change.** Two more escalation floors in the default `signal_floors` setting (both services):

| Signal | From strength | Minimum score | Meaning |
|---|---|---|---|
| `ML_ANOMALY` | 0.8 | 30 (MEDIUM) | the anomaly model rates the invoice as very unusual |
| `AMOUNT_ANOMALY` | 1.0 | 30 (MEDIUM) | the amount is at least 6σ above this vendor's average |

**Effect on the hold-out** (flagged = MEDIUM or higher):

| Floors | Precision | Recall | F1 | Sent to review |
|---|---|---|---|---|
| Phase 8 defaults | 0.307 | 0.443 | 0.363 | 7.2% |
| + ML floor only | 0.343 | 0.534 | 0.418 | 7.7% |
| + amount floor only | 0.385 | 0.625 | 0.476 | 8.1% |
| **+ both (new default)** | **0.400** | **0.682** | **0.504** | 8.5% |
| + both + a time floor | 0.400 | 0.682 | 0.504 | 8.5% (no gain, not adopted) |

Both precision and recall improve, for 1.3% more invoices sent to review. **Caveat:** the variant was chosen on the same hold-out, so the gain should be confirmed on independent data.

**Upgrading existing databases.** Migration `system_settings/0003` adds the floors only if `signal_floors` still has the old built-in value; a value an Admin changed is left alone (checked both ways, including rollback). The explanation names the floor, e.g. *“Minimum score 30 (MEDIUM) because the amount is extremely far above this vendor's usual amounts (6σ or more)”*.
