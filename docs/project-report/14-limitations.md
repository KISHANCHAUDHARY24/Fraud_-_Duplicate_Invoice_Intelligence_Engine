# Chapter 14: Limitations

1. **Synthetic data.** The model was trained and evaluated on generated data, whose patterns reflect the generator's assumptions. Real-world performance is unknown.
2. **Risk scores are not probabilities.** Weights were set by design judgement, not calibrated against real outcomes.
3. **Unsupervised model limits.** Isolation Forest flags unusual invoices, many of which are legitimate. The `contamination` parameter is an assumption.
4. **No OCR.** Invoices must be entered manually or via CSV/JSON. Scanned PDFs are not read.
5. **Synchronous analysis.** Analysis runs within the request. Very large CSV uploads will be slow without a task queue.
6. **Token storage.** JWTs in `localStorage` are exposed to XSS if a vulnerability existed. HttpOnly cookies would be stronger.
7. **Simulated payments only.** No integration with banking or ERP systems.
8. **Single-machine deployment.** Not tested under concurrent multi-user load or in a hardened production environment.
9. **Language and currency.** Text similarity is tuned for English descriptions. Amounts are compared without currency conversion.
10. **Candidate window.** Duplicates older than the look-back window (default 180 days) are not compared.
11. **Floor calibration on the evaluation data.** The two escalation floors added in Phase 16 were selected among four candidates on the same synthetic hold-out used to report the result, which can overstate the gain.
12. **The shipped model saw all synthetic data.** Reported ML metrics use a separate model trained on the earlier months only; the model delivered with the system was retrained on everything.
13. **Sequential bulk analysis.** “Submit all” after a CSV import analyses invoices one by one (about 9 s per 100 invoices on the development laptop).
14. **PDF character set.** PDF reports use the standard Helvetica font, which cannot show characters such as ₹ or non-Latin vendor names (CSV exports are UTF-8).
15. **Business timezone.** Working-hours checks and report times use one configured timezone for the whole company.
