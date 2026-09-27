# Chapter 9: Database Design

## 9.1 DBMS choice
PostgreSQL was chosen for ACID transactions (needed for atomic approval decisions), strong constraint support (foreign keys, unique, check, partial unique indexes), JSONB for storing raw analysis results and flexible settings, and first-class Django support.

## 9.2 Entity-relationship model
[INSERT Figure 9.1: ER diagram from ../database.md]

Entities: Role, User, Vendor, VendorBankAccount, Invoice, InvoiceItem, FraudAnalysis, FraudSignal, FraudAlert, Approval, Payment, AuditLog, Notification, SystemSetting.

## 9.3 Normalisation
The schema is in **third normal form** for the transactional entities:
- Vendor details are stored once and referenced by invoices (no repeated vendor names).
- Bank accounts are a separate entity with history (1:N from Vendor).
- Signals are a child table of analyses rather than repeated columns.

**Deliberate denormalisation:** `Invoice.risk_score` and `Invoice.risk_level` copy the latest analysis, so list pages can filter and sort quickly without joins. They are updated in the same transaction as the analysis.

## 9.4 Integrity constraints
| Constraint | Purpose |
|---|---|
| UNIQUE (vendor_id, invoice_number) | Blocks exact duplicates |
| CHECK amount > 0, tax ≥ 0 | Valid money values |
| Partial UNIQUE (vendor_id) WHERE is_active | One active bank account per vendor |
| FK ON DELETE PROTECT (invoice → vendor/user) | Preserves history |
| Enforced status transitions (application layer) | Valid workflow |

## 9.5 Indexing
Indexes on (vendor_id, invoice_date), approval_status, risk_level, submission_date, audit timestamp, and (recipient, is_read). Justification: these support duplicate-candidate lookup, dashboard filters and notification counts.

## 9.6 Sensitive data handling
Bank account numbers are never stored in full: only the last 4 digits and an HMAC-SHA256 hash. Passwords are stored as salted PBKDF2 hashes.

## 9.7 Data dictionary
See [../database.md §2](../database.md#2-tables). [Copy the final tables after Phase 2]
