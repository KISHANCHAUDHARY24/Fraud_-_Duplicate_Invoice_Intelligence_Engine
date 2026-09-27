# API Documentation

> **Status:** Django §2.1–2.8 ✅ implemented (Phases 1–4 and 9). Dashboard, analytics and reports (§2.9) ✅ implemented (Phases 11 and 13). FastAPI (§3) ✅ implemented (Phases 5–8).

- **Django base URL:** `http://127.0.0.1:8000/api`
- **FastAPI base URL:** `http://127.0.0.1:8001` (interactive docs: `/docs`)

## 1. Conventions

### Authentication
All Django endpoints except `/auth/login/`, `/auth/refresh/` and `/health/` require:
```
Authorization: Bearer <access_token>
```
FastAPI endpoints (except `/health`) require the internal header `X-Internal-API-Key`. Only Django calls them, never the browser.

### Success response
List endpoints are paginated:
```json
{ "count": 125, "next": "…?page=2", "previous": null, "results": [ … ] }
```
Single objects are returned directly.

### Error response (all services) ✅ Django: implemented in Phase 1 (`common/exceptions.py`)
```json
{
  "success": false,
  "error": {
    "code": "INVALID_INVOICE",
    "message": "Invoice amount must be greater than zero.",
    "details": { "amount": ["Ensure this value is greater than 0."] }
  }
}
```

| HTTP | Code examples | When |
|---|---|---|
| 400 | `VALIDATION_ERROR`, `INVALID_IMPORT_FILE` | Bad input or unusable upload file |
| 401 | `NOT_AUTHENTICATED`, `TOKEN_INVALID`, `INVALID_CREDENTIALS`, `AUTHENTICATION_FAILED` | Missing/expired/blacklisted token, wrong login, inactive user |
| 403 | `PERMISSION_DENIED` | Role not allowed |
| 404 | `NOT_FOUND` | Object missing or not visible to you |
| 403 | `NOT_ASSIGNED`, `SELF_APPROVAL` | Only the assigned reviewer may decide. Nobody reviews their own invoice |
| 409 | `DUPLICATE_INVOICE_NUMBER`, `INVOICE_NOT_EDITABLE`, `INVOICE_NOT_DELETABLE`, `VENDOR_ALREADY_EXISTS`, `VENDOR_HAS_INVOICES`, `CANNOT_DEACTIVATE_SELF`, `INVALID_STATE_TRANSITION`, `PAYMENT_BLOCKED` | Conflict with current data or state |
| 400 | `COMMENT_REQUIRED` | Reject / clarify / escalate / resolve need a comment |
| 502/503 | `ML_SERVICE_UNAVAILABLE` | FastAPI unreachable (invoice is still saved) |
| 429 | `TOO_MANY_REQUESTS` | Login rate limit exceeded |
| 500 | `SERVER_ERROR` | Unexpected; details only in server logs |

### Query parameters (list endpoints)
`?page=2&page_size=20&search=acme&ordering=-risk_score` plus the endpoint-specific filters listed below. Default page size 20, maximum 100. Sorting always puts empty values last (e.g. un-analysed invoices come after scored ones when sorting by `-risk_score`), and ties are broken by id, so pagination is stable.

---

## 2. Django REST API

Role abbreviations: **ADM** Admin · **AP** Accounts Payable Officer · **MGR** Manager · **AUD** Auditor

### 2.1 Health ✅ Implemented (Phase 1)
| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/health/` | none | `{"status":"ok","database":"ok","ml_service":{"status":"ok","model_loaded":true,"model_version":"…"}}`. ML service down → still **200** with `"status":"degraded"` (Django keeps working and routes invoices to manual review). Database down → **503** |

### 2.2 Authentication (`accounts`) ✅ Implemented (Phase 3)
| Method | Endpoint | Roles | Description |
|---|---|---|---|
| POST | `/auth/login/` | public | Body `{username, password}` → `{access, refresh, user}` |
| POST | `/auth/refresh/` | public | Body `{refresh}` → `{access, refresh}` |
| POST | `/auth/logout/` | any | Body `{refresh}`. Blacklists the refresh token |
| GET | `/auth/me/` | any | Current user + role + permissions list |
| POST | `/auth/change-password/` | any | `{old_password, new_password}` |

**Example: login**
```http
POST /api/auth/login/
Content-Type: application/json

{ "username": "ap_officer", "password": "Demo@12345" }
```
```json
{
  "access": "eyJhbGciOi…",
  "refresh": "eyJhbGciOi…",
  "user": { "id": 2, "username": "ap_officer", "role": "AP_OFFICER", "full_name": "Asha Patel" }
}
```
Errors: `401 INVALID_CREDENTIALS` (same message whether the username or the password is wrong), `429 TOO_MANY_REQUESTS` after 10 attempts per minute, `400 VALIDATION_ERROR` if a field is missing.

### 2.3 Users & roles (`accounts`) ✅ Implemented (Phase 3)
| Method | Endpoint | Roles |
|---|---|---|
| GET/POST | `/users/` | ADM. Filters `?role=MANAGER&is_active=true&search=…&ordering=-last_login`. POST body: `username, email, first_name, last_name, role (code), department, password` |
| GET/PATCH | `/users/{id}/` | ADM |
| POST | `/users/{id}/deactivate/` | ADM. Cannot deactivate yourself (409 `CANNOT_DEACTIVATE_SELF`). Revokes the user's tokens |
| POST | `/users/{id}/activate/` | ADM |
| GET | `/roles/` | ADM |

### 2.4 Vendors (`vendors`) ✅ Implemented (Phase 4)
| Method | Endpoint | Roles | Notes |
|---|---|---|---|
| GET | `/vendors/` | all | Filters: `status`, `search` (name, registration no., email, phone). Ordering: `vendor_name`, `created_at`, `invoice_count`, `total_spending`. Each row includes `invoice_count`, `total_spending` and the masked `active_bank_account` |
| POST | `/vendors/` | ADM, AP | Optional `bank_name` + `account_number` for the first account. A name equivalent to an existing vendor ("ACME Corp" vs "ACME Corporation") → `409 VENDOR_ALREADY_EXISTS` |
| GET | `/vendors/{id}/` | all | bank accounts masked |
| PATCH | `/vendors/{id}/` | ADM | Audited with old/new values. Bank details cannot be changed here (use bank-accounts) |
| DELETE | `/vendors/{id}/` | ADM | Only if the vendor has no invoices, otherwise `409 VENDOR_HAS_INVOICES` (set status INACTIVE instead) |
| GET | `/vendors/{id}/dashboard/` | all | totals, averages, alerts, recent invoices, bank history. `bank_accounts` is `[]` without `bank_accounts.view` (same rule as `/bank-accounts/`); the current masked account is always in `vendor` |
| GET | `/vendors/{id}/bank-accounts/` | ADM, AUD, AP | masked history |
| POST | `/vendors/{id}/bank-accounts/` | ADM | `{bank_name, account_number}`. Stored as last 4 digits + keyed hash. Closes the previous account. On a *change*, notifies all Admins and Auditors (`VENDOR_RISK_ALERT`) and writes a masked audit entry |

**Example vendor dashboard response.** Totals cover *all* the vendor's invoices (spending excludes drafts and rejected invoices). `recent_invoices` respects the viewer's invoice scope.
```json
{
  "vendor": { "id": 4, "vendor_name": "ACME Corp", "status": "ACTIVE" },
  "total_invoices": 23, "total_spending": "184250.00", "average_invoice": "8010.87",
  "submitted_invoices": 21, "alert_count": 3, "open_alert_count": 1,
  "risk_distribution": {"LOW": 15, "MEDIUM": 4, "HIGH": 2}, "status_counts": {"APPROVED": 14, "DRAFT": 2},
  "risk_indicators": ["Bank account changed 12 day(s) ago (****1111 → ****4821)", "2 possible duplicate invoice(s)"],
  "monthly_spending": [ {"month": "2026-08", "total": "24100.00", "count": 3} ],
  "recent_invoices": [ … ],
  "bank_accounts": [ { "bank_name": "HDFC", "masked": "****4821", "is_active": true, "valid_from": "2026-09-12" } ]
}
```

### 2.5 Invoices (`invoices`) ✅ Implemented (Phases 4 and 9)
| Method | Endpoint | Roles | Notes |
|---|---|---|---|
| GET | `/invoices/` | all* | Filters: `approval_status`, `fraud_status`, `risk_level`, `purchase_category` (comma lists allowed, e.g. `risk_level=HIGH,CRITICAL`), `vendor`, `submitted_by`, `department`, `date_from`/`date_to` (invoice date), `submitted_from`/`submitted_to`, `amount_min`/`amount_max`, `risk_score_min`, `search` (number, vendor, description, PO, department), `ordering` (`invoice_date`, `submission_date`, `due_date`, `amount`, `risk_score`, `invoice_number`, `vendor__vendor_name`, `approval_status`, `created_at`) |
| POST | `/invoices/` | ADM, AP | Creates a DRAFT. Optional `items: [{description, quantity, unit_price}]`. `department` defaults to the submitter's. `payment_bank_account` defaults to the vendor's active account |
| GET | `/invoices/{id}/` | all* | includes latest analysis + signals |
| PATCH | `/invoices/{id}/` | ADM, AP | only when DRAFT |
| DELETE | `/invoices/{id}/` | ADM, AP | only when DRAFT |
| POST | `/invoices/{id}/submit/` | ADM, AP | DRAFT → SUBMITTED → PROCESSING → ML analysis → routed (APPROVED / UNDER_REVIEW / BLOCKED). Returns the invoice with `latest_analysis` (score, level, `summary`, `explanation[]`, `signals[]`, `warnings[]`). If the ML service is down the invoice is still saved and sent to Manager review (`fraud_status = ANALYSIS_FAILED`) |
| POST | `/invoices/{id}/analyze/` | ADM, AP, AUD | Run the analysis again and store a new FraudAnalysis. The workflow status is **not** changed, except for an invoice stuck in PROCESSING. ML still down → `503 ML_SERVICE_UNAVAILABLE`. Drafts → 409 |
| GET | `/invoices/{id}/history/` | all* | audit entries for this invoice |
| GET | `/invoices/{id}/similar/` | all* | Duplicate candidates from the latest analysis: `[{score, components, invoice, description}]`. Reviewers (MGR/AUD/ADM) see every candidate. AP officers only see candidates within their own scope |
| POST | `/invoices/upload-csv/` | ADM, AP | multipart field `file` (.csv, ≤ 2 MB, ≤ 1000 rows) |
| POST | `/invoices/upload-json/` | ADM, AP | JSON list of invoices, or `{"invoices": [...]}`. `vendor` may be an id or a name |
| GET | `/invoices/csv-template/` | ADM, AP | Downloads an example CSV with every supported column |

\* **Object-level visibility:** Managers see invoices assigned to them for approval, plus non-draft invoices of their department. **Auditors see all invoices (read-only)**, which they need to compare a flagged invoice with normal ones and read a vendor's history (changed in Phase 9). AP officers see what they submitted. Admin sees everything. Invoices outside your scope return **404**, not 403, so their existence is not revealed.

**Example: create invoice**
```json
POST /api/invoices/
{
  "invoice_number": "INV-1001",
  "vendor": 4,
  "invoice_date": "2026-09-01",
  "due_date": "2026-10-01",
  "amount": "9900.00",
  "currency": "USD",
  "tax": "0.00",
  "description": "Office computer equipment",
  "purchase_category": "HARDWARE",
  "purchase_order_number": "PO-7788",
  "department": "IT"
}
```
Validation (`400 VALIDATION_ERROR`, messages per field in `details`): amount must be > 0, tax ≥ 0, invoice date not in the future, due date ≥ invoice date, currency a 3-letter code, invoice number made of letters/digits/`- _ / . #`, description ≥ 3 characters, vendor must exist and not be INACTIVE/BLOCKED, payment bank account must belong to the vendor, ≤ 100 items.

Conflicts: the same (vendor, invoice_number) → `409 DUPLICATE_INVOICE_NUMBER` with `details.existing_invoice_id`. Editing or deleting a non-DRAFT invoice → `409 INVOICE_NOT_EDITABLE` / `INVOICE_NOT_DELETABLE`. A *near*-duplicate (e.g. `INV1001` vs `INV-1001`) is accepted, and flagged later by the duplicate detector.

**CSV upload response**
```json
{
  "total_rows": 5, "created": 4, "failed": 1,
  "errors": [ { "row": 3, "field": "amount", "message": "Must be a positive number." } ],
  "invoice_ids": [31, 32, 33, 34]
}
```
Required CSV columns: `invoice_number, vendor, amount, invoice_date, description`. Optional: `due_date, currency, tax, purchase_category, purchase_order_number, department`. Unknown columns are ignored.

- **Vendor matching:** exact name (case-insensitive), then registration number, then equivalent name ("ACME Corporation" → "ACME Corp") if exactly one vendor matches. Unknown vendors are reported as row errors, never auto-created.
- **Formats:** dates `YYYY-MM-DD`. Amounts may contain `,` and `$ € £ ₹` (`"$5,000.50"`). Categories are case-insensitive (`office supplies` → `OFFICE_SUPPLIES`). Empty optional cells use defaults. Blank lines are skipped. UTF-8 and Excel's Windows encoding (cp1252) are both accepted.
- **Row numbers** match the spreadsheet (header = row 1). Duplicates within the same file are reported against the earlier row.
- **Partial success:** each row is saved in its own savepoint, so valid rows are kept and only the listed rows need fixing. File-level problems (not .csv, too big, empty, missing columns, too many rows) → `400 INVALID_IMPORT_FILE` and nothing is imported.
- Response status is `201` if at least one invoice was created, otherwise `200`.

### 2.6 Fraud (`fraud`) ✅ Implemented (Phase 9)
| Method | Endpoint | Roles | Notes |
|---|---|---|---|
| GET | `/fraud/alerts/` | all (alert visible when its invoice is visible) | Filters: `severity`, `type` (matches **any** signal of the analysis, e.g. `type=SPLIT_PURCHASE`), `primary_type`, `status`, `assigned_to`, `vendor`, `invoice`, `date_from`, `date_to`, `search`. Each row: invoice, vendor, amount, risk score, primary type, all `signal_types`, severity, status, assigned auditor |
| GET | `/fraud/alerts/{id}/` | same | full investigation payload |
| GET | `/fraud/alerts/auditors/` | ADM, AUD | ✅ Phase 12. Active auditors for the “Assign to” drop-down: `[{id, name}]` only (user management stays Admin-only) |
| POST | `/fraud/alerts/{id}/assign/` | ADM, AUD | `{auditor}` (id of an active auditor). Audited, auditor notified. Only while OPEN / IN_REVIEW, otherwise `409 INVALID_STATE_TRANSITION` |
| POST | `/fraud/alerts/{id}/resolve/` | AUD | `{outcome: CLEARED \| CONFIRMED_ISSUE, note}` (note required). **CLEARED** on a BLOCKED invoice → UNDER_REVIEW with an AUDITOR approval and the payment block lifted. **CONFIRMED_ISSUE** → invoice REJECTED, `fraud_status = REVIEWED_CONFIRMED_ISSUE`, payment held |
| POST | `/fraud/alerts/{id}/mark-reviewed/` | AUD | OPEN → IN_REVIEW (assigns the alert to the caller if unassigned). Any other status → `409 INVALID_STATE_TRANSITION`, so a closed alert can never be reopened |
| GET | `/fraud/analyses/?invoice={id}` | all* | analysis history |

**Investigation payload** (`GET /fraud/alerts/{id}/`): `alert`, `invoice` (full detail incl. `latest_analysis` with score, explanation and signals), `vendor` (details, totals, `risk_indicators`), `similar_invoices[]`, `vendor_history[]` (10 most recent), `approval_history[]`, `audit_history[]`.

### 2.7 Approvals & payments (`approvals`) ✅ Implemented (Phase 9)
| Method | Endpoint | Roles | Notes |
|---|---|---|---|
| GET | `/approvals/` | MGR, AUD, ADM | MGR/AUD: approvals assigned to me. ADM: all. Filters `decision`, `level`, `invoice`, `search`. Each row includes the invoice number, vendor, amount, risk score/level and status |
| GET | `/approvals/{id}/` | assignee, ADM | |
| POST | `/approvals/{id}/approve/` | assignee (MGR/AUD) | `{comment?}` → invoice APPROVED, payment SCHEDULED, open alert dismissed, a flagged invoice becomes REVIEWED_CLEARED |
| POST | `/approvals/{id}/reject/` | assignee | `{comment}` required |
| POST | `/approvals/{id}/request-clarification/` | assignee | `{comment}` required → invoice back to DRAFT |
| POST | `/approvals/{id}/escalate/` | MGR | `{comment}` → new AUDITOR approval |
| GET | `/payments/` | ADM, AUD | simulated payments |
| POST | `/payments/{invoice_id}/simulate/` | ADM | APPROVED → PAID. `Payment.status = PAID_SIMULATED`, reference `SIM-PAY-…`. Blocked → `409 PAYMENT_BLOCKED`. Not approved → `409 INVALID_STATE_TRANSITION`. **No money is moved** |

Illegal transitions (e.g. approving an already rejected invoice) → `409 INVALID_STATE_TRANSITION`.

### 2.8 Audit, notifications, settings ✅ Implemented (Phase 4)
| Method | Endpoint | Roles |
|---|---|---|
| GET | `/audit-logs/` | ADM, AUD. Filters: `user`, `action` (comma list), `entity_type`, `entity_id`, `date_from`, `date_to`, `search`. Read-only: POST/PATCH/DELETE → 405 |
| GET | `/audit-logs/actions/` | ADM, AUD. All action codes + labels (for filter drop-downs) |
| GET | `/audit-logs/entity-types/` | ADM, AUD. ✅ Phase 13. Record types present in the log: `[{value, label}]` (e.g. `invoice` → “Invoice”) |
| GET | `/notifications/` | any (own only). Filters `is_read`, `type` |
| POST | `/notifications/{id}/read/` | owner (someone else's id → 404) |
| POST | `/notifications/read-all/` | any |
| GET | `/notifications/unread-count/` | any |
| GET | `/settings/` | ADM, MGR, AUD. Each row: `key, value, value_type, description, default, updated_by_name, updated_at` |
| GET | `/settings/{key}/` | ADM, MGR, AUD |
| PATCH | `/settings/{key}/` | ADM. Body `{"value": …}`. Validated per key (e.g. weights must sum to 1.0, thresholds must increase, valid timezone), then audited with old/new value. Invalid → `400` with the reason in `details.value` |
| POST | `/settings/{key}/reset/` | ADM. Restore the default value (audited) |

### 2.9 Dashboard, analytics, reports (`reports`)
| Method | Endpoint | Roles | Notes |
|---|---|---|---|
| GET | `/dashboard/summary/` | all | ✅ Phase 11. KPI cards + chart datasets + high-risk table (scoped by role, see below) |
| GET | `/analytics/?date_from=&date_to=` | ADM, AUD, MGR | ✅ Phase 13. See below |
| GET | `/reports/` | ADM, AUD, MGR | ✅ Phase 13. The report types this user may export: `[{type, title, description, date_basis, formats}]` |
| GET | `/reports/{type}/?format=csv\|pdf&date_from=&date_to=` | ADM, AUD (MGR: invoices, approvals) | ✅ Phase 13. `type` ∈ `invoices, fraud, vendors, approvals, audit`. Returns a file download |

**`GET /dashboard/summary/` ✅ Implemented (Phase 11).** One request fills the whole dashboard. Every number is computed from `visible_invoices(user)`, so an AP officer's dashboard counts only their own invoices and a Manager's does not include drafts. Response keys:

| Key | Content |
|---|---|
| `kpis` | `total_invoices`, `total_spending` (drafts and rejected excluded), `suspicious_invoices` (MEDIUM or higher), `possible_duplicates`, `pending_approvals` + `pending_approvals_scope` (`all` / `mine` / `my_invoices`), `blocked_invoices` |
| `monthly_spending` | last 12 months, oldest first, empty months included as 0 |
| `alerts_over_time` | fraud alerts opened per month (same 12 months) |
| `risk_distribution`, `status_distribution` | counts per level / status (`NOT_ANALYZED` for invoices without a score) |
| `vendor_risk` | top 8 vendors by average risk score of analysed invoices |
| `approval_trends` | decisions per month: approved, rejected, clarification, escalated |
| `high_risk_invoices` | HIGH/CRITICAL invoices not yet rejected or paid, highest score first |
| `generated_at` | server timestamp |

**Dates (analytics and reports).** `date_from` / `date_to` are `YYYY-MM-DD`, both inclusive. Missing → the last **12 whole calendar months** up to today (e.g. 2025-10-01 → 2026-09-24). A bad date, a reversed range or more than 5 years → `400 VALIDATION_ERROR` with the field in `details`.

**`GET /analytics/` ✅ Implemented (Phase 13).** Invoice figures use the invoice date, alert figures the date the alert was raised, approval figures the decision date; everything is limited to `visible_invoices(user)`.

| Key | Content |
|---|---|
| `range` | the dates actually used |
| `summary` | `invoice_count`, `analysed_count`, `total_spending`, `average_invoice`, `alert_count`, `open_alert_count`, `duplicate_rate` and `high_risk_rate` (% of analysed invoices), `average_risk_score`, `decisions`, `auto_approval_rate`, `average_decision_hours` (reviewer decisions only; a decision stamped before its step was opened is ignored) |
| `monthly` | per month: `total`, `count`, `high_risk`, `alerts` |
| `risk_distribution` | as the dashboard |
| `signal_frequency` | per signal type: `invoices` with it and `average_points` |
| `vendor_risk` | top 10 by average risk score |
| `approval_times` | per review level: `average_hours`, `decisions` |
| `department_spending`, `category_spending` | top 10: `label`, `total`, `count` |

**Report exports ✅ Implemented (Phase 13).**

| Report | Rows | Period filters on | Who |
|---|---|---|---|
| `invoices` | invoices you may see | invoice date | ADM, AUD, MGR |
| `fraud` | alerts with all indicators and the investigation outcome | date the alert was raised | ADM, AUD |
| `vendors` | every vendor: invoices, spending, average risk, high/critical count in the period; open alerts; masked account | invoice date | ADM, AUD |
| `approvals` | approval steps with reviewer, decision, hours to decide, comment | date the step was opened | ADM, AUD, MGR |
| `audit` | audit entries incl. old/new values (CSV) | action date | ADM, AUD |

- **CSV:** UTF-8 with BOM (Excel shows ₹ / € correctly), up to 10,000 rows. Cells beginning with `= + - @` are prefixed with `'`, so a spreadsheet never runs a vendor name or description as a formula (**CSV injection**). Plain negative numbers are left alone.
- **PDF:** landscape A4 (reportlab), header with period, author and row count, table header repeated on each page, page numbers, the “not a determination of fraud” note. Up to 2,000 rows; long free-text columns are CSV-only.
- **Times** are shown in the business timezone setting (`timezone`, default Asia/Kolkata), the same one the working-hours rule uses; the PDF says which.
- **Response headers:** `Content-Disposition: attachment; filename="expense-intelligence_{type}_{from}_{to}.{csv|pdf}"`, `X-Report-Rows`, `X-Report-Truncated` (exposed to the browser through CORS).
- Every export is written to the audit log (`REPORT_EXPORTED`, with format, period and row count).
- `?format=` normally selects a DRF renderer; the export view uses its own content negotiation, so `format=csv|pdf` picks the file type while errors are still JSON (`404` unknown report, `403` role, `400` bad format or dates).

---

## 3. FastAPI ML service

All requests and responses are validated with Pydantic. Errors use the same error shape (`422 VALIDATION_ERROR` for invalid input).

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | ✅ `{"status":"ok","service":"expense-intelligence-ml-service","version":"0.1.0","model_loaded":true,"model_version":"iforest-20260924-025523"}` |
| POST | `/api/v1/duplicate/check` | Compare one invoice to candidate invoices |
| POST | `/api/v1/fraud/analyze` | Full analysis: duplicates + rules + ML + risk score |
| POST | `/api/v1/vendor/analyze` | Vendor-level indicators (bank change, frequency spikes, alert history) |
| POST | `/api/v1/risk/score` | Score a supplied list of signals (useful for testing/what-if) |

### 3.1 `POST /api/v1/duplicate/check` ✅ Implemented (Phase 5)
Optional request fields: `weights` (default 0.30/0.25/0.20/0.15/0.10, must sum to 1.0), `threshold` (default 80), `date_window_days` (default 30). Each invoice may carry `id`, `vendor_id` and `currency` (default `USD`); unknown extra fields are ignored. The response also has `candidates` (top 5 with component scores), `candidates_evaluated` and `disclaimer`. Invalid input → `422 VALIDATION_ERROR` with `details: [{field: "invoice.amount", message: …}]`. Missing or wrong key → `401 NOT_AUTHENTICATED`.

```json
{
  "invoice": { "id": 50, "invoice_number": "INV1001", "vendor_name": "ACME Corporation",
               "amount": 5000.0, "invoice_date": "2026-09-03", "description": "Software licence" },
  "candidates": [
    { "id": 12, "invoice_number": "INV-1001", "vendor_name": "ACME Corp",
      "amount": 5000.0, "invoice_date": "2026-09-01", "description": "Software License" }
  ],
  "weights": { "invoice_number": 0.30, "vendor": 0.25, "amount": 0.20, "date": 0.15, "description": 0.10 },
  "threshold": 80
}
```
```json
{
  "duplicate_score": 96,
  "is_possible_duplicate": true,
  "matched_invoice_id": 12,
  "matched_invoice_number": "INV-1001",
  "components": { "invoice_number": 0.97, "vendor": 1.0, "amount": 1.0, "date": 0.93, "description": 0.9 },
  "signals": ["Very similar invoice number (INV1001 vs INV-1001)", "Same vendor", "Same amount", "Invoice dates 2 days apart"],
  "candidates": [ { "id": 12, "score": 96 } ]
}
```

### 3.1b `POST /api/v1/fraud/rules` ✅ Implemented (Phase 6)
Rules only (no ML, no points). Request: `invoice` (with `submission_datetime` incl. timezone and `department`), optional `vendor_context`, `bank`, `recent_vendor_invoices`, `config`, `duplicate_score`, `duplicate_match_id`, `duplicate_match_number`. Response: `signals[]` (`type`, `strength` 0–1, `severity`, `message`, `details`, `related_invoice_id`), `features{}` (18 values), `routing_hints{above_approval_threshold}`, `rules_evaluated[]`, `disclaimer`. See fraud-detection.md §10.

### 3.1c `POST /api/v1/vendor/analyze` ✅ Implemented (Phase 6)
Request: `vendor_id`, `vendor_name`, optional `vendor_context`, `bank`, `recent_invoices`, `config`. Response: `indicators[]` (Signal objects, strongest first), `indicator_count`, `disclaimer`.

### 3.1d `POST /api/v1/fraud/anomaly` ✅ Implemented (Phase 7)
Same request as `/fraud/rules`. Response: `model_version`, `anomaly_score` (0–1), `is_anomaly`, `threshold` (from `config.ml_anomaly_threshold`, default 0.6), `reasons[]`, `top_features[]` (`feature`, `value`, `z`), `signal` (an `ML_ANOMALY` Signal or `null`), `disclaimer`. If no model is loaded → `503 SERVICE_UNAVAILABLE` ("Run scripts/train_model.py and restart the service"). See machine-learning.md.

### 3.2 `POST /api/v1/fraud/analyze` ✅ Implemented (Phase 8)
**Actual request:** `invoice` (AnalysedInvoice: invoice fields + `submission_datetime` with timezone + `department`), `vendor_context`, `bank`, `recent_vendor_invoices[]`, `duplicate_candidates[]`, `config` (Django's full settings dict; unknown keys ignored).
**Actual response:** `invoice_id`, `risk_score`, `risk_level`, `summary`, `explanation[]`, `signals[]` (with `details`, e.g. the duplicate reasons and components), `scoring` (`breakdown[]` with weight/strength/points, `points_total`, `capped`, `floor_applied`), `duplicate` (score, match, reasons, top 5 `candidates`), `anomaly` (`model_loaded`, `model_version`, `anomaly_score`, `is_anomaly`, `threshold`, `reasons`), `features`, `routing_hints.above_approval_threshold`, `warnings[]`, `analyzed_at`, `disclaimer`. The example below shows the general idea; see risk-scoring.md §9.

Request = invoice + `vendor_context` (average amount, invoice count, days since previous invoice, bank-change info, prior alerts) + `candidates` (for duplicates and split detection) + `config` (all `SystemSetting` values).

Response:
```json
{
  "risk_score": 87,
  "risk_level": "CRITICAL",
  "duplicate": { "duplicate_score": 94, "is_possible_duplicate": true, "matched_invoice_id": 12 },
  "anomaly": { "anomaly_score": 0.71, "is_anomaly": true, "model_version": "iforest-2026-09-24" },
  "signals": [
    { "type": "DUPLICATE", "severity": "HIGH", "points": 30, "message": "94% similarity with invoice INV-1001", "related_invoice_id": 12 },
    { "type": "THRESHOLD_PROXIMITY", "severity": "MEDIUM", "points": 15, "message": "Amount is 1.0% below the approval threshold (10,000)" },
    { "type": "TIME_ANOMALY", "severity": "LOW", "points": 10, "message": "Submitted Sunday 02:17, outside configured working hours" }
  ],
  "explanation": "Risk score 87/100 (CRITICAL). This is a risk indicator, not a determination of fraud.",
  "disclaimer": "Risk indicators require human review."
}
```

### 3.3 `POST /api/v1/risk/score` ✅ Implemented (Phase 8)
```json
{ "signals": [ { "type": "DUPLICATE", "strength": 0.94 }, { "type": "BANK_ACCOUNT_CHANGE", "strength": 1.0 } ],
  "config": { "signal_weights": { … }, "risk_level_thresholds": { "medium": 30, "high": 60, "critical": 80 } } }
```
→ `{ "risk_score": 48, "risk_level": "MEDIUM", "breakdown": [ … ] }`
