# Chapter 4: Literature Review

> **Guidance:** This is a structure with key sources to look up. Read each source yourself, then summarise and cite it properly (Harvard/IEEE as your university requires). Do not cite anything you have not read. Verify every reference detail below before using it.

## 4.1 Occupational and invoice fraud
- ACFE, *Occupational Fraud: A Report to the Nations* (latest edition). Prevalence of billing schemes, median losses, detection methods (tips vs. controls vs. data analytics).
- Discuss: duplicate payments, shell vendors, split purchases, business email compromise / bank-detail change fraud.
- [INSERT: 2–3 academic sources on accounts-payable fraud or continuous auditing]

## 4.2 Rule-based fraud detection and continuous auditing
- Traditional audit analytics (e.g. Benford's law, threshold tests, duplicate tests in tools like ACL/IDEA).
- Strengths: transparency and regulatory acceptance. Weaknesses: rigid, needs manual upkeep.
- [INSERT: source on continuous auditing / computer-assisted audit techniques]

## 4.3 Approximate string matching
- Levenshtein, V. I. (1966). Binary codes capable of correcting deletions, insertions, and reversals. *Soviet Physics Doklady*.
- Jaro, M. A. (1989) and Winkler, W. E. (1990). Record-linkage string comparators.
- Token-based similarity and record linkage (e.g. Christen, P., *Data Matching*, Springer, 2012).
- Relevance: invoice numbers and vendor names are short strings with typos, so edit-distance and prefix-weighted measures suit them.

## 4.4 Anomaly detection
- Chandola, V., Banerjee, A., Kumar, V. (2009). Anomaly detection: a survey. *ACM Computing Surveys*.
- Liu, F. T., Ting, K. M., Zhou, Z.-H. (2008). Isolation Forest. *IEEE ICDM*.
- Compare: statistical (z-score), distance/density (LOF: Breunig et al., 2000), One-Class SVM (Schölkopf et al., 2001), autoencoders.
- Justify Isolation Forest: linear-time, no labels, handles mixed-scale features.

## 4.5 Machine learning in financial fraud detection
- Surveys on ML for financial fraud (e.g. credit-card fraud with class imbalance). [INSERT sources]
- Key issues: label scarcity, class imbalance, concept drift, and the cost of false positives.

## 4.6 Explainable AI and human-in-the-loop decision support
- Why explanations matter in finance and audit: accountability, regulation (e.g. GDPR Art. 22 on automated decision-making).
- Approaches: inherently interpretable models and rule traces vs. post-hoc methods (SHAP: Lundberg & Lee, 2017; LIME: Ribeiro et al., 2016).
- This project uses **signal-level additive explanations**: each detector contributes visible points.

## 4.7 Summary and research gap
Existing tools either use transparent but rigid rules, or ML models that are harder to explain. Few student-scale systems combine fuzzy duplicate matching, configurable rules and unsupervised ML in one **explainable, workflow-integrated** tool. This project addresses that gap at a demonstrable scale.
