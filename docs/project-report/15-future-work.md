# Chapter 15: Future Work

| Area | Improvement |
|---|---|
| Data | Validate on real, anonymised AP data with auditor-labelled outcomes |
| ML | Use reviewer outcomes (cleared / confirmed) to train a supervised or semi-supervised model. Calibrate scores. Detect drift and retrain automatically |
| Explainability | SHAP values for the ML component |
| Input | OCR/Document AI extraction from PDF and image invoices |
| Scalability | Celery + Redis for asynchronous analysis and bulk imports |
| Vendor intelligence | Detect duplicate vendor records, and vendor–employee address/bank overlaps |
| Security | HttpOnly refresh cookies, MFA, SSO (OAuth2/SAML), field-level encryption |
| Integration | ERP connectors (e.g. SAP, Oracle, Tally), real payment-file generation |
| Notifications | Email and Teams/Slack notifications |
| Multi-currency | Currency conversion before amount comparison |
