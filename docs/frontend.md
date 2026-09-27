# Frontend (React + Vite)

> **Status:** ✅ Foundation implemented in Phase 10 (setup, API client, authentication, layout, profile), see §8. ✅ Dashboard and invoice screens implemented in Phase 11, see §9. ✅ Vendors, fraud investigation and approvals implemented in Phase 12, see §10. ✅ Analytics, audit logs, reports and settings implemented in Phase 13, see §11. Every page in §3 now exists.

## 1. Stack
React 19 · Vite 8 · JavaScript · React Router 7 · Axios · Recharts 3 · Tailwind CSS 4 · lucide-react (icons) · Vitest 5 + React Testing Library · oxlint.

## 2. Folder structure
```text
frontend/
├── index.html
├── package.json
├── vite.config.js
├── .env.example                 # VITE_API_BASE_URL=http://127.0.0.1:8000/api
└── src/
    ├── main.jsx                 # entry: Router + AuthProvider
    ├── App.jsx                  # route table
    ├── index.css                # Tailwind + design tokens
    ├── api/
    │   ├── client.js            # Axios instance, JWT + refresh interceptors, error normaliser
    │   ├── auth.js  invoices.js  vendors.js  fraud.js  approvals.js
    │   └── reports.js  audit.js  notifications.js  settings.js  dashboard.js
    ├── context/AuthContext.jsx  # user, role, login(), logout()
    ├── hooks/                   # useFetch, useDebounce, usePagination, useAuth
    ├── layouts/AppLayout.jsx    # Sidebar + Topbar + <Outlet/>
    ├── components/
    │   ├── common/              # Button, Card, Modal, ConfirmDialog, DataTable, Pagination,
    │   │                        # Spinner, EmptyState, ErrorState, Toast, FilterBar
    │   ├── badges/              # RiskBadge, StatusBadge, SeverityBadge
    │   ├── charts/              # SpendingChart, RiskDistributionChart, AlertsTrendChart…
    │   ├── fraud/               # RiskScoreGauge, SignalList, DuplicateComparison
    │   └── routing/ProtectedRoute.jsx
    ├── pages/                   # one folder per page (see below)
    └── utils/                   # formatCurrency, formatDate, roles.js, constants.js
```

## 3. Routes
| Path | Page | Roles |
|---|---|---|
| `/login` | LoginPage | public |
| `/dashboard` | DashboardPage | all |
| `/invoices` | InvoiceListPage | all |
| `/invoices/upload` | InvoiceUploadPage (form + CSV/JSON) | ADMIN, AP_OFFICER |
| `/invoices/:id` | InvoiceDetailPage | all (backend-scoped) |
| `/vendors` | VendorListPage | all |
| `/vendors/:id` | VendorDashboardPage | all |
| `/fraud-alerts` | FraudAlertListPage | ADMIN, AUDITOR, MANAGER, AP_OFFICER |
| `/fraud-alerts/:id` | FraudInvestigationPage | ADMIN, AUDITOR, MANAGER(assigned) |
| `/approvals` | ApprovalQueuePage | MANAGER, AUDITOR, ADMIN |
| `/analytics` | AnalyticsPage | ADMIN, MANAGER, AUDITOR |
| `/audit-logs` | AuditLogPage | ADMIN, AUDITOR |
| `/reports` | ReportsPage | ADMIN, AUDITOR, MANAGER |
| `/settings` | SettingsPage | ADMIN |
| `/profile` | ProfilePage | all |

## 4. API client behaviour (`api/client.js`)
1. The request interceptor adds `Authorization: Bearer <access>`.
2. On a response `401`: call `/auth/refresh/` **once**, queue concurrent requests, then retry. If the refresh fails → logout → `/login`.
3. It normalises errors to `{ code, message, details }` from the backend's error shape. Network errors become `"Cannot reach server"`.
4. Pages show `error.message` in `<ErrorState>` or a toast. Raw server output is never shown.

## 5. UI design principles
- **Enterprise look:** fixed left sidebar (grouped nav), top bar (search, notifications bell with unread count, user menu), neutral background, white cards, dense but readable tables.
- **Risk is never shown by colour alone:**
  | Level | Badge |
  |---|---|
  | LOW | green ✓ `Low` |
  | MEDIUM | amber ⚠ `Medium` |
  | HIGH | orange ▲ `High` |
  | CRITICAL | red ⛔ `Critical` |
- Every data view has **loading**, **empty** and **error** states.
- Destructive or decision actions (reject, delete, block) open a **ConfirmDialog**, with a comment field where required.
- Responsive: the sidebar collapses to a drawer below 1024 px, and tables scroll horizontally inside their card.
- Accessibility: labelled form fields, focus rings, `aria-label` on icon buttons, sufficient contrast.

## 6. Key pages
- **Dashboard:** 6 KPI cards (Total Invoices, Total Spending, Suspicious, Possible Duplicates, Pending Approvals, Blocked). Charts: Monthly Spending (area), Fraud Alerts Over Time (line), Risk Distribution (donut), Invoice Status (bar), Vendor Risk (horizontal bar, top 10), Approval Trends (stacked bar). A high-risk invoice table.
- **Invoice list:** search, filters (status, risk, vendor, date range, amount range), sortable columns, server-side pagination, risk and status badges.
- **Invoice detail / Fraud investigation:** a risk gauge, the ordered **signal list with points**, a side-by-side duplicate comparison (matching fields highlighted), vendor history, approval timeline, audit history, and action buttons (Approve, Reject, Escalate, Mark as Reviewed) shown according to role and state.
- **Upload:** a manual form with inline validation, plus CSV/JSON drag-and-drop with a downloadable template, per-row error table and "Submit all for analysis".

## 7. State management
React Context holds auth only. Page data is fetched per page through small hooks (`useFetch`). No Redux, which is unnecessary at this scale.

## 8. Implementation (Phase 10)

### 8.1 Structure as built
```text
frontend/
├── .env / .env.example        VITE_API_BASE_URL=http://127.0.0.1:8000/api  (public: never secrets)
├── vite.config.js             React + Tailwind plugins; dev server fixed to http://localhost:5173 (CORS);
│                              Vitest config (jsdom)
├── package.json               scripts call node directly (see §8.5)
└── src/
    ├── main.jsx               BrowserRouter → AuthProvider → App
    ├── App.jsx                route table; later-phase pages used ComingSoonPage (removed in Phase 13)
    ├── index.css              Tailwind + design tokens (brand palette, 4 risk colours)
    ├── api/                   client.js (Axios + JWT + refresh + errors), auth.js, notifications.js, system.js
    ├── context/               authContext.js (the context object), AuthProvider.jsx (state + login/logout)
    ├── hooks/                 useAuth, useAsync (loading/error/data), useDismiss (close dropdowns)
    ├── layouts/               AppLayout, Sidebar (desktop + mobile drawer), NotificationBell, UserMenu
    ├── components/
    │   ├── common/            Button, Card, Alert, FormField, PageHeader, StateViews (Loading/Empty/Error)
    │   ├── badges/            RiskBadge, StatusBadge
    │   └── routing/           ProtectedRoute
    ├── pages/                 LoginPage, DashboardPage (starter), ProfilePage, ComingSoonPage (removed in Phase 13),
    │                          ForbiddenPage, NotFoundPage
    ├── utils/                 permissions.js (capability names), navigation.js (sidebar as data), format.js
    └── test/                  setup.js, renderWithAuth.jsx (fake auth context for tests)
```

### 8.2 API client (`src/api/client.js`), viva points
| Behaviour | How |
|---|---|
| Adds the token | Request interceptor sets `Authorization: Bearer <access>` (unless `skipAuth`, e.g. login) |
| Silent refresh | On 401 it calls `/auth/refresh/` **once**. Concurrent failing requests share the same refresh promise, then all retry with the new token. The new *rotated* refresh token is stored |
| Session end | If refreshing fails, tokens are cleared and AuthProvider shows "Your session has expired" on the login page |
| Errors | Everything becomes `ApiError {status, code, message, details}` from the backend's error JSON. A network failure says "Cannot reach the server… Is the Django backend running?". Pages only show `error.message`, never raw responses |
| Storage | Tokens in `localStorage` (keys `ei.access`, `ei.refresh`), wrapped in try/catch; signing out in one tab signs out the others (`storage` event) |

### 8.3 Permissions in the UI
`GET /api/auth/me/` returns the user's capability list. `useAuth().can('audit.view')` checks it. The sidebar (`utils/navigation.js`) and the routes (`App.jsx` + `ProtectedRoute`) use **the same capability names as the backend**, so a Manager never even sees "Upload invoice" or "Audit logs". Typing the URL shows "You do not have access to this page". The API would answer 403 anyway.

### 8.4 Verified in the browser (Phase 10)
With Django + FastAPI + Vite running, as a temporary Manager account (since deactivated):
- The session was restored from stored tokens on page load. The dashboard showed the Manager's shortcuts and live system status (Django, PostgreSQL, ML service online).
- The sidebar had no Upload / Audit logs entries. `/audit-logs` showed the "no access" page.
- The profile listed the 10 Manager capabilities. The notification dropdown worked ("You are all caught up.").
- Sign out → back to `/login`, tokens removed, and **the server rejected the old refresh token ("Token is blacklisted")**.
- No console errors. `npm run build` and `npm run lint` are clean.

### 8.5 Why `package.json` scripts call `node …` directly
The project folder name contains `&` (`Fraud_&_Duplicate_…`). npm runs scripts through `cmd.exe` via small `.cmd` launchers, and in `cmd.exe` `&` means "start another command", so `vite` could not start. The scripts therefore run each tool with Node directly, e.g. `node node_modules/vite/bin/vite.js`. You still type `npm run dev` / `npm test` as usual. See troubleshooting.md.

### 8.6 Tests (`npm test`, 33 passing)
| File | What it proves |
|---|---|
| `components/badges/RiskBadge.test.jsx` | Every level shows text + icon (+ screen-reader text). "Not analysed" state. The tooltip says "not a finding of fraud". Status labels incl. "Paid (simulated)" |
| `components/routing/ProtectedRoute.test.jsx` | Signed-out → /login. Missing capability → "no access". Allowed → page. Waits while the session is checked |
| `pages/LoginPage.test.jsx` | Shows the backend's message. Empty-field validation without a server call. Redirect after sign-in. Show/hide password. Expired-session message |
| `api/client.test.js` | Error normalisation. **Two concurrent 401s → exactly one refresh → both retried**. Rejected refresh ends the session. A failed login never triggers a refresh |
| `utils/navigation.test.js` | Sidebar per role. Empty groups removed. Page titles |

## 9. Implementation (Phase 11): dashboard and invoice screens

### 9.1 New files
```text
src/
├── api/                  invoices.js (list/get/create/update/submit/analyse/import/similar), vendors.js, dashboard.js
├── hooks/                useDebouncedValue.js (search waits until typing stops)
├── utils/                invoiceOptions.js (statuses, categories, risk levels), invoiceValidation.js (same rules as the backend)
├── components/
│   ├── charts/           chartTheme.js (colours), ChartCard.jsx (chart ⇄ table toggle), ChartTooltip.jsx, DashboardCharts.jsx
│   ├── common/           ConfirmDialog, Pagination, Fields (SelectField, TextAreaField), KpiCard
│   ├── fraud/            RiskScoreGauge, RiskExplanation, SignalList, DuplicateComparison
│   └── invoices/         InvoiceTable, InvoiceFilters, InvoiceForm, ImportPanel, HistoryTimeline
└── pages/                DashboardPage, InvoiceListPage, InvoiceUploadPage, InvoiceEditPage, InvoiceDetailPage
```
Routes: `/invoices`, `/invoices/upload`, `/invoices/:id`, `/invoices/:id/edit` (drafts only).

### 9.2 Viva points
| Question | Answer |
|---|---|
| Where are the list filters kept? | In the **URL** (`?risk_level=HIGH,CRITICAL&ordering=-risk_score&page=2`). A filtered list can be bookmarked or shared, and the Back button works. Changing a filter returns to page 1 |
| Why is validation done twice? | The form checks the same rules as the backend (amount > 0, no future date, due date ≥ invoice date…) for instant feedback. The **backend is still the authority**: its field errors appear under the matching field, and a duplicate invoice number links to the existing invoice |
| How does the detail page explain a score? | Gauge + level, the summary sentence, every reason with the points it added, the signal list with severities, and a field-by-field comparison with each possible duplicate. The disclaimer "not a determination of fraud" is always visible |
| Why one dashboard request? | `/dashboard/summary/` returns KPIs, six chart series and the high-risk table together: one loading state, one role-scoped query set on the server |

### 9.3 Chart colours (checked, not guessed)
Colours were run through a colour-blindness validator:
- **Categories** (approval trends: approved / rejected / clarification / escalated) use a fixed four-colour order that passed the checks.
- **Risk-level charts** do *not* reuse the badge colours (green/amber/orange/red): those failed the colour-blindness check as chart fills. Risk is an ordered scale, so the charts use one blue hue from light (Low) to dark (Critical). Grey means "not analysed".
- Some colours have low contrast against white, so **every chart has a "Show as table" button** with the same numbers. Badges still use icon + word, never colour alone.

### 9.4 Verified in the browser (Phase 11)
Checked against a **separate preview database** (`expense_intelligence_preview`), never the real one. It was filled with a year of history plus the demo scenarios, all analysed by the real FastAPI service and model:
- Dashboard: 6 KPI cards, monthly spending, alerts over time, risk and status distribution, vendor risk, approval trends, high-risk table.
- List: URL filters, column sorting, debounced search ("hooli" → 2 rows), pagination.
- Detail of the disguised duplicate `INV1001`: 64 HIGH, "98% similarity with invoice INV-1001 (+29)", field comparison (number 100%, date 93%).
- Manual upload → *Save and submit* → analysed (0 LOW) → auto-approved → detail page.
- CSV import: a wrong column name gives a clear error; a mixed file gives "1 of 3 invoices imported" plus a row / field / problem table.
- Draft edit page loads pre-filled.
- The same `/dashboard/summary/` gave 206 invoices for the AP officer (own only), 204 for the Manager (no drafts), 208 for the Auditor (all).
- Fixed during the check: the reasons column was squeezed next to the gauge on medium screens (it now stacks until extra-wide screens); the "missing column" message was repeated.

### 9.5 Tests (`npm test`, 54 passing)
| File | What it proves |
|---|---|
| `components/invoices/InvoiceForm.test.jsx` | Client validation rules. Blocked vendors hidden. No server call while invalid. Server field errors shown, with a link to the existing duplicate |
| `components/fraud/fraudComponents.test.jsx` | Reasons with points, warnings and the disclaimer. Gauge announced to screen readers. Duplicate comparison per field |
| `components/charts/ChartCard.test.jsx` | Chart ⇄ accessible table toggle. Empty state instead of a blank chart |
| `pages/InvoiceListPage.test.jsx` | Filters read from and written to the URL. Sort by column. Empty state. "Upload invoice" only for roles that can create invoices |

## 10. Implementation (Phase 12): vendors, fraud investigation, approvals

### 10.1 New pages and routes
| Route | Page | Who | What it does |
|---|---|---|---|
| `/vendors` | VendorListPage | all | Search, status filter, sort by name / invoices / spending. Masked active account per vendor |
| `/vendors/new`, `/vendors/:id/edit` | VendorFormPage | ADM, AP (new) · ADM (edit, status) | Vendor form; an equivalent name links to the existing vendor |
| `/vendors/:id` | VendorDashboardPage | all | Risk indicators, 4 KPIs, monthly spending and risk charts, recent invoices, bank-account history + change (Admin) |
| `/fraud-alerts` | FraudAlertListPage | all (scoped) | Opens on *open or in review*; filters: status, severity, indicator (any signal), vendor, “assigned to me” (Auditors) |
| `/fraud-alerts/:id` | FraudInvestigationPage | all (scoped) | Explained score, signals, duplicates, vendor profile, vendor history, approval steps, audit trail + Assign / Start review / Resolve |
| `/approvals` | ApprovalQueuePage | MGR, AUD, ADM | My pending steps, riskiest first; decided steps with comments; Admins see every step (read-only) |

The invoice page also gained: **“Your decision is needed”** for the assigned reviewer, a link to the invoice's **investigation**, and **Simulate payment** (Admin, approved invoices).

### 10.2 New building blocks
```text
src/api/            fraud.js, approvals.js; vendors.js extended
src/hooks/          useUrlFilters.js: filters / ordering / page in the URL, with defaults (used by all four list pages)
src/components/
  common/           Filters (SearchInput, FilterSelect, ClearFilters), SortHeader; Button size "icon"; ConfirmDialog
                    now takes extra fields (children, confirmDisabled) and renders in a portal
  badges/           StateBadge: vendor / alert / decision status with icon + word
  vendors/          VendorForm, BankAccountPanel
  fraud/            AlertActions (assign / start review / resolve dialogs), RiskAnalysisCard (shared with the invoice page)
  approvals/        ApprovalActions (approve / reject / clarify / escalate; compact icon version for tables), ApprovalTimeline
src/utils/          reviewOptions.js (choice lists), approvals.js (canDecide), vendorValidation.js, formErrors.js
```

### 10.3 Viva points
| Question | Answer |
|---|---|
| How does the UI decide which buttons to show? | Capability **and** state: e.g. *Resolve* needs `alerts.resolve`, an open alert, and an invoice the auditor did not submit; decision buttons need `approvals.decide`, a PENDING step and being its assignee. The backend checks the same rules again, so hiding a button is convenience, not security |
| Why is a bank-account change confirmed? | It is a classic fraud technique (the “vendor” asks to be paid to a new account). The dialog explains that Admins and Auditors are notified and the vendor's next invoices get a *Bank account change* signal, and asks to confirm with the vendor by phone |
| Why must resolving need an outcome and a note? | The note is the evidence of the human decision; it is stored with the alert and in the audit log. Only a human sets an outcome. The model never “convicts” |
| Why do list filters live in the URL? | A reviewer can bookmark “my open critical alerts”, and Back returns to the same view. Defaults (e.g. *open alerts*) apply only when the key is missing; choosing “All” stores `?status=` so it is not replaced by the default |

### 10.4 Problems found in the browser check (and fixed)
| Symptom | Cause | Fix |
|---|---|---|
| A resolved alert could be set back to “In review” | `mark_reviewed` did not check the status | Backend: only OPEN → IN_REVIEW; `assign` only while open; both return 409 otherwise (tests added) |
| Blank screen after scrolling a long page | Screen-reader-only text (`position:absolute`) had no positioned ancestor, so it extended the *document*; the window scrolled instead of `<main>` | `<main>` is `relative`, so it contains them |
| Pages wider than a phone screen | Grid items default to `min-width:auto`, so a wide table stretched its column despite its own scroll box | `min-w-0` on page-grid children; tables scroll inside their card |
| Comment box beside its label in the queue's dialog | The dialog was rendered inside a `white-space:nowrap` table cell and inherited it | ConfirmDialog renders in a portal (`document.body`) |
| Icons squeezed to 8px in table buttons | `px-0` lost to the size class's `px-3` | A real `icon` button size |
| “Bank account changed 0 day(s) ago” | Plain `day(s)` template | “today”, “1 day ago”, “5 days ago” (backend + ML service) |

### 10.5 Tests (`npm test`, 72 passing; 18 new)
| File | What it proves |
|---|---|
| `components/fraud/AlertActions.test.jsx` | Buttons per role and alert state; no *Resolve* on your own invoice; resolving needs outcome **and** note; assigning sends the chosen auditor |
| `components/approvals/ApprovalActions.test.jsx` | Only the assignee of a PENDING step sees decisions (not Admins); no *Escalate* at auditor level; reject needs a reason; approve works without |
| `components/vendors/VendorForm.test.jsx` | Same account-number rule as the backend (IBANs allowed); both bank fields or neither; link to the existing vendor on a name clash; no bank fields when editing |
| `pages/FraudAlertListPage.test.jsx` | Default *open* filter sent to the API; “All statuses” kept in the URL; “Assigned to” only for investigators |

## 11. Implementation (Phase 13): analytics, audit logs, reports, settings

### 11.1 Pages
| Route | Page | Who | What it does |
|---|---|---|---|
| `/analytics` | AnalyticsPage | ADM, MGR, AUD | Period picker (URL-kept) → 8 headline figures and 8 charts: spending per month, risk over time (high/critical invoices + alerts), risk mix, indicators that fire most, vendor risk, spending by department and category, time to decide per level |
| `/audit-logs` | AuditLogPage | ADM, AUD | Search, action / record-type / period filters, sortable; each row expands to a before → after table; records link to the invoice, vendor or alert |
| `/reports` | ReportsPage | ADM, MGR, AUD | One period for all reports; a card per report the role may export, with CSV and PDF buttons and the row count of the last download |
| `/settings` | SettingsPage | ADM edit · MGR, AUD view | The 17 business rules in 5 groups, each with an editor that fits the value (number + unit, switch, time range, weekday picker, weight grid with running total, per-signal floors) |

The Phase 10 “coming soon” placeholder page was removed: every route now has its real page.

### 11.2 New building blocks
```text
src/api/            analytics.js, reports.js (blob download, filename + row count from headers), audit.js, settings.js;
                    client.js reads JSON error bodies of failed blob downloads
src/components/
  common/           DateRangeFilter (presets + From/To, shared by Analytics, Reports and Audit logs)
  charts/           AnalyticsCharts (RiskTrendChart, RankedBarChart), ChartLegend; ChartCard gained `height`
  audit/            ValueChanges (old → new values)
  settings/         SettingEditor
src/utils/          dateRanges.js (presets), settingsMeta.js (labels, groups, units, draft conversion, checks)
```

### 11.3 Viva points
| Question | Answer |
|---|---|
| How is a file downloaded when the API needs a token? | A plain link cannot send the `Authorization` header. The page requests the file as a **blob** with axios, reads the filename from `Content-Disposition`, and saves it through a temporary object URL. The backend exposes that header (and the row-count headers) through CORS |
| Why is a CSV cell like `=HYPERLINK(...)` prefixed with `'`? | **CSV injection**: vendor names and descriptions come from users and imported files. Excel would run a cell that starts with `=`, `+`, `-` or `@` as a formula; the quote makes it plain text |
| Why does the settings screen compare values “ignoring key order”? | PostgreSQL **JSONB** stores object keys in its own order. `{"invoice_number": 0.3, …}` comes back as `{"date": 0.15, …}`; a plain string comparison would call an unchanged value “changed” |
| Why can Managers see settings but not change them? | Transparency: a reviewer should know the thresholds behind a score. Changing them is an Admin decision, validated per key and audited with old and new value |
| Why only one y-axis in “Risk over time”? | Both series are counts per month, so they share one scale. Two different measures would get two charts, never a dual axis |

### 11.4 Problems found in the browser check (and fixed)
| Symptom | Cause | Fix |
|---|---|---|
| “Average time to decide: -4460 h” | Preview seed data had decisions stamped before their step was opened | Analytics ignores such rows (`decided_at >= created_at`, test added); the preview seed was corrected |
| Report times 5½ hours behind the app | Server timezone is UTC | Exports render in the business timezone setting; the PDF names it (test added) |
| “Reset to default” on untouched weights, fields in odd order | JSONB key order | Order-independent comparison; fields shown in a fixed order |
| Default analytics period had 13 months | “Last 365 days” touches 13 calendar months | Default = 12 whole months starting on the 1st (backend and presets agree) |
| Record-type filter listed “invoice” dozens of times | `distinct()` on a model with a default ordering adds the ordering column | `order_by().distinct()` in the new endpoint |
| A refused export said only “Request failed” | The error body of a blob request is a Blob | The API client parses JSON error blobs (test added) |

### 11.5 Tests (`npm test`, 90 passing; 18 new)
| File | What it proves |
|---|---|
| `utils/dateRangesAndSettings.test.js` | Whole-month presets, preset detection, “custom” keeps the dates, reversed range; draft → number conversion; weights must total 1, increasing thresholds, working hours/days; key-order-independent comparison |
| `components/settings/SettingEditor.test.jsx` | Read-only without `settings.manage`; weights blocked until they add up to 1, then saved as numbers; backend message shown; reset after confirmation |
| `pages/ReportsPage.test.jsx` | Download with the chosen period and row count; refusal reason shown; buttons disabled for an impossible period; audit before/after table |
| `api/client.test.js` (+1) | The error message of a failed blob download is read |

### 11.6 Phase 14 follow-up
Checking the seeded demo at phone width showed a few pixels of sideways scrolling. Cause: the screen-reader text inside **risk badges** in wide tables was positioned against `<main>` (made `relative` in Phase 12), not against the table's scroll box, so it stuck out past the page edge. `RiskBadge` is now `relative` itself, which keeps that text inside the badge.

## 12. Phase 16: pages loaded on demand
Every page behind the login is a `React.lazy` import in `App.jsx`; `AppLayout` wraps the page area in `<Suspense>` so the sidebar and top bar stay visible while a page's code arrives. The login page stays in the main bundle so the first screen is instant.

| | Before | After |
|---|---|---|
| Main JavaScript file | 881 kB (262 kB gzip), one file | 354 kB (115 kB gzip) |
| Chart library (Recharts) | always downloaded | only with Dashboard, Analytics and the vendor page |
| Build warning “chunks larger than 500 kB” | yes | no |

Checked in the browser: opening the invoice list downloads only `InvoiceListPage`. The route-table test waits a little longer for the first lazily loaded page.
