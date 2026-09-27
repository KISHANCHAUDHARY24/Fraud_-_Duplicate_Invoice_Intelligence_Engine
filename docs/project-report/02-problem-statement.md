# Chapter 2: Problem Statement

> Draft material. Rewrite in your own words.

## 2.1 The problem
Organisations lose money through duplicate, split and redirected invoice payments. Existing basic controls have three weaknesses:

1. **Exact matching is brittle.** A duplicate invoice with a reformatted number (`INV-1001` → `INV1001`), a typo, or a slightly different vendor name (`ACME Corp` → `ACME Corporation`) passes an equality check.
2. **Rules are fixed.** Static rules catch known patterns but not unusual *combinations* of features (e.g. a normal amount, from a normal vendor, submitted at 2 a.m. on a Sunday, after an unusually short gap).
3. **Opaque alerts are ignored.** A system that says only "suspicious" without reasons creates alert fatigue and cannot be defended in an audit.

## 2.2 Specific issues addressed
| Issue | Example |
|---|---|
| Near-duplicate invoices | Same vendor, same amount, invoice number differs by one character |
| Split purchases | Three invoices of 9,900 / 9,700 / 9,800 within four days, each below a 10,000 approval limit |
| Threshold hugging | Amounts consistently 1–5% below the approval limit |
| Bank-account redirection | A vendor's bank details change shortly before a large invoice |
| Off-hours submission | Invoices entered at night or at weekends |
| Amount anomalies | An invoice five times larger than the vendor's usual amount |

## 2.3 Research / design question
*How can an invoice-processing system automatically identify and explain potential duplicate and anomalous invoices, combining fuzzy matching, rule-based detection and unsupervised machine learning, and route them to human reviewers without claiming to determine fraud?*

## 2.4 Constraints
- Real labelled fraud data is not available, so synthetic data is used.
- The system must run locally on Windows without containerisation.
- Decisions remain with humans. The system provides decision support only.
