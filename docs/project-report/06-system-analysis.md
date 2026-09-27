# Chapter 6: System Analysis

## 6.1 Existing system (manual / basic ERP)
| Aspect | Current practice | Weakness |
|---|---|---|
| Duplicate check | Exact invoice-number match | Misses reformatted/typo duplicates |
| Approval | Fixed amount limit | Invites split purchases just below the limit |
| Vendor bank changes | Email request, manual update | Common vector for payment-redirection fraud |
| Review | Random sampling / all invoices by hand | Slow. Inconsistent. Does not scale |
| Evidence | Scattered emails and spreadsheets | Weak audit trail |

## 6.2 Proposed system
Automated screening of every invoice, explainable risk scoring, risk-based routing and a complete audit trail. Humans still make every final decision.

## 6.3 Feasibility
| Type | Assessment |
|---|---|
| Technical | All components are mature open-source tools (Django, FastAPI, scikit-learn, RapidFuzz, PostgreSQL, React) that run on Windows |
| Economic | Zero licence cost. Runs on a standard laptop |
| Operational | Familiar web UI. Explanations in plain language. Configurable rules without code changes |
| Schedule | Phased plan of 17 phases (see development-plan.md). [INSERT your timeline / Gantt chart] |
| Legal/ethical | Synthetic data only. No real personal financial data. Presented as decision support |

## 6.4 Development methodology
An **incremental / iterative** approach: each phase delivers a working, tested slice (foundation → models → auth → APIs → ML → integration → UI → testing). This lowers risk, because the core workflow works early and advanced features are added on a stable base. [Optionally relate to Agile sprints if you used them]

## 6.5 Risk analysis (project risks)
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| No real fraud data | High | Medium | Synthetic generator with documented assumptions |
| Integration issues between services | Medium | High | Clear JSON contracts. Early integration (Phase 9). Fallback when ML is down |
| Scope creep | High | High | MoSCoW prioritisation. Core first |
| Windows environment issues | Medium | Medium | Troubleshooting guide. No Docker dependency |
