# Chapter 1: Introduction

> Draft material. Rewrite in your own words before submission. Items in `[BRACKETS]` must be filled in.

## 1.1 Background
Accounts payable (AP) is the business function that receives, checks and pays supplier invoices. Medium and large organisations handle thousands of invoices each month from hundreds of vendors. Most are legitimate, but a small share are erroneous or improper: invoices submitted twice, invoices with slightly altered numbers, purchases split to avoid approval limits, and payments redirected to fraudulent bank accounts. Industry surveys of occupational fraud consistently identify billing schemes as one of the most frequent forms of asset misappropriation [CITE: e.g. ACFE Report to the Nations, latest edition].

Traditional controls rely on exact-match duplicate checks and manual review. Exact matching misses near-duplicates (`INV-1001` vs `INV1001`). Manual review does not scale and depends on reviewer attention.

## 1.2 Motivation
Recent progress in approximate string matching and unsupervised anomaly detection makes it practical to screen every invoice automatically and send only the suspicious ones to people. The key design challenge is **trust**. Finance staff will only act on a system's output if they understand *why* an invoice was flagged. This project therefore puts **explainability** at the centre.

## 1.3 Project overview
The *Corporate Expense Fraud & Duplicate Invoice Intelligence Engine* is a web-based decision-support system built with React, Django, FastAPI, PostgreSQL and scikit-learn. It:
- stores vendors and invoices with role-based access control,
- detects near-duplicate invoices with fuzzy matching,
- applies configurable business rules and an Isolation Forest anomaly model,
- combines the resulting signals into an explainable 0–100 risk score, and
- routes each invoice to the appropriate human reviewer, recording every action in an audit log.

## 1.4 Scope
**In scope:** invoice and vendor management, CSV/JSON import, duplicate and anomaly detection, risk scoring, approval workflow, simulated payment, audit logging, notifications, analytics and reports, running locally on Windows.
**Out of scope:** OCR of scanned invoices, real payment integration, ERP integration, production cloud deployment, and training on real corporate fraud data.

## 1.5 Report structure
Chapter 2 defines the problem. Chapter 3 states the aim and objectives. Chapter 4 reviews related literature. Chapters 5–9 cover requirements, analysis, design, architecture and database. Chapter 10 describes the implementation, Chapter 11 the machine-learning component, and Chapter 12 testing. Chapters 13–16 present results, limitations, future work and conclusions.
