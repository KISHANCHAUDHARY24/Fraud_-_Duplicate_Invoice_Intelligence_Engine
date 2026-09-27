# User Guide

> **Status:** ✅ Matches the application (Phases 10–14). Screenshots: [INSERT SCREENSHOTS] (added in Phase 16).

This guide is for someone who has never used the application.

## What does this system do?
It checks every invoice your company receives for warning signs: possible duplicates, amounts just under approval limits, invoices submitted at odd hours, recently changed vendor bank accounts, and unusual patterns found by a machine-learning model. Each invoice gets a **risk score from 0 to 100** with plain-English **reasons**. Then it goes to the right person to check it.

> The system **never says an invoice is fraud.** It says *"this is worth a look, and here's why."* People make the decisions.

## Demo accounts (after running `seed_data`, see installation.md §8)
| Username | Password | Role |
|---|---|---|
| `admin` | `Demo@12345` | Administrator |
| `ap_officer` | `Demo@12345` | Accounts Payable Officer |
| `manager` | `Demo@12345` | Manager |
| `auditor` | `Demo@12345` | Auditor |

These are **demo** accounts with a published password: use them only on your own development machine.
The demo company has 8 fictional vendors (ACME Corp, Bluepeak Consulting, Cobalt Software Ltd, …) and a year of invoice history.

## 1. How to log in
1. Open http://localhost:5173.
2. Enter your username and password and click **Sign in**.
3. You arrive at the **Dashboard**. The left menu only shows the pages your role can use.
4. To log out: click your name (top right) → **Log out**.

[INSERT SCREENSHOT: login page]

## 2. Reading the Dashboard
- **Cards at the top:** total invoices, total spending, suspicious invoices, possible duplicates, pending approvals, blocked invoices.
- **Charts:** monthly spending, alerts over time, risk distribution, and more.
- **High-risk invoices table:** click an invoice number to open it, or **View all** for the full filtered list.
- Every chart has a small **table** button that shows the same numbers as a table.
- You only see what your role allows: an AP Officer's dashboard counts only their own invoices.

Risk badges always show an icon and a word, not just a colour: ✓ Low · ⚠ Medium · ▲ High · ⛔ Critical.

## 3. How to create a vendor (Admin / AP Officer)
1. **Vendors** → **+ New vendor**.
2. Fill in name, registration number, address, email and phone.
3. Optionally add the first bank account: bank name + account number. After saving, only the last 4 digits are shown (e.g. `****4821`).
4. Click **Create vendor**. If a vendor with an equivalent name exists (“ACME Corp” vs “ACME Corporation”), you get a link to it instead.

**The vendor page** shows its risk indicators, totals, monthly spending, the risk of its invoices, recent invoices and the bank-account history.

**Changing a bank account (Admin):** on the vendor page → **Change bank account** → enter the new details → **Continue** → read the warning → **Change account**. Admins and Auditors are notified and the vendor's next invoices get a “Bank account change” signal. This is intentional: bank-detail changes are a common fraud technique, so confirm the change with the vendor by phone first.

## 4. How to upload an invoice (AP Officer)
**Single invoice:**
1. **Invoices** → **Upload invoice** → **Enter one invoice** tab.
2. Choose the vendor and fill in invoice number, dates, amount, description, category, department.
3. Click **Save as draft** (drafts can be edited later), or **Save and submit for analysis** to analyse it straight away.

**Many invoices (CSV):**
1. **Upload invoice** → **Import CSV / JSON** tab → **Download CSV template**.
2. Fill the template in Excel and save as CSV. Required columns: `invoice_number, vendor, amount, invoice_date, description`.
3. Drag the file onto the upload box.
4. Review the results: rows that failed are listed with the row number and the reason (e.g. *"Row 3, amount: must be a positive number"*). Fix them and upload those rows again.

## 5. How to view fraud analysis
Open any invoice. The **Risk analysis** panel shows:
- the **score** (gauge) and **level**
- the **reasons**, each with the points it added, e.g. *"94% similarity with invoice INV-1001 (+28)"*
- the **signals**, each with its severity
- **Possible duplicates**: each similar invoice side by side with this one, field by field, with a similarity bar per field
- the **history** of the invoice from the audit log

**Finding invoices:** the **Invoices** page has search and filters (status, risk, vendor, dates, amount). Click a column header to sort. Filters are kept in the address bar, so a filtered list can be bookmarked.

## 6. How to investigate an alert (Auditor)
1. **Fraud alerts** shows open alerts first. Filter by severity, indicator (e.g. *Possible duplicate*, *Potential split purchase*), vendor, or **Assigned to: Me**.
2. Open an alert. The investigation page shows the risk score and its reasons, the signals, possible duplicates side by side, the vendor's profile and recent invoices, the approval steps and the audit history.
3. Click **Start review** to show you are working on it (the alert is assigned to you if nobody has it). **Assign / Reassign** hands it to another auditor.
4. When finished: **Resolve** → choose **Cleared** (legitimate) or **Issue confirmed**, and write a note explaining what you checked.
   - *Cleared* on a blocked invoice lifts the payment block and sends it to an auditor for a normal approval.
   - *Issue confirmed* rejects the invoice and holds its payment.

You cannot resolve an alert on an invoice you submitted yourself.

## 7. How to approve an invoice (Manager / Auditor)
1. **Approvals** shows invoices waiting for *you*, riskiest first. Use the *Decision* filter to see what you decided earlier.
2. Click **Open** and read the risk reasons first. The invoice page shows **“Your decision is needed”** with the decision buttons.
3. Click **Approve** (optional comment) → confirm. The payment is scheduled.

In the queue, the small buttons next to **Open** do the same (hover to see their names).

**Simulated payment (Admin):** on an approved invoice, **Simulate payment** marks it *Paid (simulated)* with a `SIM-PAY-…` reference. No money is moved.

## 8. How to reject, ask for clarification or escalate
- **Reject:** click **Reject**, type a reason (required), confirm. The submitter is notified.
- **Request clarification:** type your question. The invoice goes back to the submitter as a draft.
- **Escalate** (Manager): sends the invoice to an Auditor with your comment.

You cannot approve an invoice you submitted yourself.

## 9. How to view analytics and reports
**Analytics** (Admin, Manager, Auditor): choose a **Period** (last 12 months, last 3 months, this month, this year, last year, or your own dates). You see headline figures (spending, alerts, duplicate rate, share approved automatically, average time to decide) and charts. Every chart has a **table** button with the exact numbers.

**Reports:**
1. **Reports** → choose the **Period** at the top.
2. On the report you need (Invoice, Fraud alert, Vendor risk, Approval or Audit log), click **CSV** (opens in Excel) or **PDF** (for printing).
3. The card confirms the file name and how many rows it contains.

You only see the reports your role may export (Managers: invoices and approvals). Reports contain only data you are allowed to see, bank accounts are always masked, and every download is recorded in the audit log.

## 10. How to view audit logs (Admin / Auditor)
**Audit logs** lists every important action: who did it, what, to which record, and when. Search, or filter by action, record type (invoice, vendor, alert, setting, report…) and period. Click **›** on a row to see exactly what changed (before → after). Click a record (e.g. `invoice #204`) to open it. Audit entries cannot be edited or deleted.

## 11. How to configure settings (Admin)
**Settings** has five groups: approval rules, duplicate detection, working time, pattern rules and risk scoring. To change a value:
1. Edit it (numbers, the on/off switch, the working-day buttons, the weights…). A **Save** button appears.
2. Mistakes are shown straight away, e.g. *“The weights must add up to 1 (currently 1.05)”*.
3. Click **Save**. A changed setting shows who changed it and when, and offers **Reset to default**.

Every change is recorded in the audit log with the old and new value. New values apply to invoices analysed **after** the change. Managers and Auditors can view the settings but not change them.

## 12. Notifications
The 🔔 bell in the top bar shows unread notifications (approval requests, high-risk invoices, decisions on your invoices). Click one to open the invoice. Click **Mark all read** to clear them.

## Demo walkthrough (5 scenarios)
After `seed_data`, the five scenarios are already analysed and waiting for review. Suggested order:

| # | Scenario | Invoice (vendor) | Sign in as | What you should see |
|---|---|---|---|---|
| 1 | Normal invoice | `EV-2001` (Evergreen Stationers) | `ap_officer` | ✓ Low · 0, approved automatically; `admin` simulated the payment → *Paid (simulated)* |
| 2 | Duplicate | `INV1001` (Cobalt Software Ltd) | `auditor` | High · 60. “Possible duplicate” of `INV-1001` (same amount, number without the dash); field-by-field comparison; in the auditor's approvals |
| 3 | Unusual | `AC-2003` (ACME Corp) | `manager` | Medium · 40. Submitted Sunday 02:17, about 9× the vendor's usual amount: time, amount and ML signals; in the manager's approvals |
| 4 | Split purchase | `BP-3001`–`BP-3003` (Bluepeak Consulting) | `auditor` | Three invoices just under 10,000 within a few working days; `BP-3003` High · 70 with “Potential split purchase” |
| 5 | Bank change | `FL-2005` (Falcon Logistics) | `auditor` | The vendor's bank account changed the day before; High · 60 with “Bank account change”; vendor page shows the indicator |

Things to try: approve or reject as the reviewer, resolve an alert as the auditor, export the fraud report as PDF, and compare the Analytics page before and after. Two drafts (`DF-2101`, `GM-2101`) are ready for the AP officer to submit.
