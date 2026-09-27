# Duplicate Invoice Detection

> **Status:** ✅ Implemented in Phase 5 (`ml-service`). §5 and §7 describe the final algorithm; §10 lists measured scores. Candidate selection (§2) is implemented by Django in Phase 9.

## 1. The problem
Exact matching (`invoice_number == invoice_number`) is easy and is already enforced by a database constraint. Real duplicates are often **near** duplicates, caused by typing mistakes, reformatting or deliberate alteration:

| Original | Variant | Why exact match fails |
|---|---|---|
| `INV-1001` | `INV1001` | hyphen removed |
| `INV-1001` | `INV-100I` | digit `1` replaced by letter `I` |
| `ACME Corp` | `ACME Corporation`, `ACME CORP.` | suffix / case / punctuation |
| `Office computer equipment` | `Office computer equipments` | small spelling change |

So we compare an incoming invoice with **candidate** invoices and compute a **combined similarity score (0–100)**.

## 2. Candidate selection (done by Django)
Comparing against every invoice ever made is slow and noisy. Django sends only candidates that:
- were created in the last `duplicate_lookback_days` (default 180), **and**
- either have a vendor whose normalised name shares its first token, **or** have an amount within ±10%, **or** have an invoice number with the same digits.

It sends at most 200 candidates, most recent first.

## 3. Normalisation (before comparing)
```text
invoice number : upper-case, remove spaces/-/_/./#,  "INV-100I" → "INV100I"
vendor name    : lower-case, remove punctuation, remove legal suffixes
                 (corp, corporation, inc, ltd, limited, llc, plc, co, pvt)
                 "ACME Corp."  → "acme"
description    : lower-case, remove punctuation, collapse spaces
```
A **look-alike map** (`O→0`, `I→1`, `L→1`, `S→5`, `B→8`, `Z→2`) is applied to *both* invoice numbers before comparing, so `INV-100I` ≈ `INV-1001`. These characters are easily confused when typed or scanned.

## 4. Algorithms

### 4.1 Levenshtein distance
The minimum number of single-character **insertions, deletions or substitutions** needed to turn one string into another.

```text
"INV1001" → "INV100I"   : 1 substitution          → distance 1
normalised similarity = 1 − distance / max(len(a), len(b)) = 1 − 1/7 = 0.857
```
Good for: invoice numbers (typos, altered characters).

### 4.2 Jaro-Winkler similarity
Measures matching characters and transpositions, and gives a **bonus for a shared prefix** (up to 4 characters). Invoice numbers and vendor names usually share a prefix, so this suits them.
```text
JW("INV1001", "INV1010") ≈ 0.94   (transposition near the end, same prefix)
```

### 4.3 Token similarity (RapidFuzz `token_sort_ratio` / `token_set_ratio`)
Splits text into words, sorts them and compares. Word order does not matter:
```text
"computer equipment office" vs "office computer equipment" → 100
"Office computer equipment" vs "Office computer equipments" → ~98
```
Good for: vendor names and descriptions.

### 4.4 Amount similarity
```text
amount_sim = 1                                   if |a − b| < 0.01
           = max(0, 1 − |a − b| / max(a, b) × 10) otherwise
```
The `× 10` makes it strict: amounts 5% apart score 0.5, and amounts 10% or more apart score 0.

### 4.5 Date similarity
```text
date_sim = max(0, 1 − |days between invoice dates| / 30)
```
Same day = 1.0, 15 days apart = 0.5, 30 or more days apart = 0.

## 5. Component scores
| Component | Method | Example |
|---|---|---|
| Invoice number | Rules + Levenshtein, see §5.1 | `INV-1001` vs `INV1001` → 1.00 |
| Vendor | 1.0 if same vendor ID. Otherwise max(token similarity, Jaro-Winkler × length ratio) on normalised names, see §5.2 | `ACME Corp` vs `ACME Corporation` → 1.00 |
| Amount | §4.4 | 5000 vs 5000 → 1.00 |
| Date | §4.5 | 2 days apart → 0.93 |
| Description | token_sort_ratio on normalised text | → 0.98 |

### 5.1 Invoice-number similarity (refined in Phase 5)
Plain Levenshtein or Jaro-Winkler rates `INV-1001` vs `INV-1002` at 0.86–0.94. But **consecutive numbers are normally different invoices** (e.g. monthly billing). If those scores were used directly, every recurring invoice would be flagged. The rules, in order:

| Step | Rule | Score | Example |
|---|---|---|---|
| 1 | Equal after removing spaces and `- _ / . #` | 1.00 | `INV-1001` / `inv 1001` |
| 2 | Equal after the look-alike map | 0.95 | `INV-1001` / `INV-100I` |
| 3 | Same digits (≥ 3), different letters | ≥ 0.90 | `INV-1001` / `ACME-1001` / `1001` |
| 4 | Otherwise Levenshtein similarity, **halved if the digits differ** | e.g. 0.43 | `INV-1001` / `INV-1002` |

Digits are taken from the numbers *before* the look-alike map. Otherwise the letter I in the prefix `INV` would become a digit and step 3 would never match.

### 5.2 Vendor similarity (refined in Phase 5)
Jaro-Winkler gives a bonus for a shared prefix, so on its own it rates `acme` vs `acme global solutions` at about 0.87. Multiplying it by the length ratio (shorter ÷ longer name) removes that bias: 0.87 × 0.36 ≈ 0.32. Genuine typos keep a high score (`Microsoft` vs `Micros0ft` → 0.96).

## 6. Combined score
```text
duplicate_score = 100 × Σ (weight_i × component_i)
```
Default weights (configurable in Settings → `duplicate_weights`, must sum to 1.0):

| Component | Weight |
|---|---|
| Invoice number | 0.30 |
| Vendor | 0.25 |
| Amount | 0.20 |
| Date | 0.15 |
| Description | 0.10 |

If `duplicate_score ≥ duplicate_threshold` (default **80**), the invoice is a **possible duplicate**.

### Worked example
| Component | New invoice | Earlier invoice | Similarity | × Weight |
|---|---|---|---|---|
| Invoice no. | INV1001 | INV-1001 | 1.00 | 0.300 |
| Vendor | ACME Corporation | ACME Corp | 1.00 | 0.250 |
| Amount | 5000 | 5000 | 1.00 | 0.200 |
| Date | 2026-09-03 | 2026-09-01 | 0.93 | 0.140 |
| Description | Software licence | Software License | 0.88 | 0.088 |
| **Total** | | | | **0.978 → 98** |

## 7. Explainable output
Each component above its explanation threshold becomes a human-readable reason:

| Component value | Message |
|---|---|
| number ≥ 0.9 | "Very similar invoice number (INV1001 vs INV-1001)" |
| vendor = same ID | "Same vendor" |
| vendor ≥ 0.85 (different ID) | "Vendor name very similar to 'ACME Corp' (possible duplicate vendor record)" |
| amount = 1.0 | "Same amount" |
| date ≥ 0.8 | "Invoice dates N days apart" |
| description ≥ 0.85 | "Very similar description" |

The result is **never** `DUPLICATE = TRUE`. It is always a score + signals + matched invoice, as specified in [api.md §3.1](api.md).

## 8. Guarding against false positives
- A recurring monthly invoice (same vendor, same amount, same description) has **different dates** (30 days apart → date 0) and a **different number** (digit penalty → 0.43), so it scores **68**, below the threshold. A weekly one scores 79 (see §10).
- The reviewer sees each component value, so they can dismiss an obvious false positive quickly.
- Weights and threshold can be tuned by the Admin.

## 9. Implementation location
- `ml-service/utils/similarity.py`: pure functions (`levenshtein_similarity`, `jaro_winkler_similarity`, `token_similarity`, `invoice_number_similarity`, `vendor_name_similarity`, `description_similarity`, `amount_similarity`, `date_similarity`, normalisers).
- `ml-service/services/duplicate_detector.py`: `compare()` one pair, `explain()` reasons, `check()` loops over candidates (skipping the invoice itself), sorts, and returns the top 5.
- `ml-service/schemas/duplicate.py`: request/response validation (weights must sum to 1.0, threshold 1–100, ≤ 500 candidates).
- Endpoint: `POST /api/v1/duplicate/check` (needs `X-Internal-API-Key`).
- Tests: `ml-service/tests/test_similarity.py`, `test_duplicate_detector.py`, `test_api.py`.

## 10. Measured results (Phase 5, default weights, threshold 80)
Compared against `INV-1001 · ACME Corp · 5,000 · 2026-09-01 · "Software License"`:

| New invoice | Score | Result |
|---|---|---|
| `INV1001` · ACME Corporation · same amount · +2 days · "Software licence" | 98 | possible duplicate |
| `INV-100I` · everything else identical | 98 | possible duplicate |
| `INV-1010` (typo) · same day · same amount | 81 | possible duplicate |
| `INV-1002` · +7 days (weekly billing) | 79 | not flagged (borderline) |
| `INV-1002` · +30 days (monthly billing) | 68 | not flagged |
| `INV-1001` · different vendor (Globex) · same amount · same day | 76 | not flagged |
| unrelated invoice | 9 | not flagged |

**Limitation:** weekly recurring invoices sit just under the threshold. A company with a lot of weekly billing may want `duplicate_threshold` = 85.
