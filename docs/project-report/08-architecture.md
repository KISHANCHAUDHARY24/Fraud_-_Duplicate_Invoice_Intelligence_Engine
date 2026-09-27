# Chapter 8: Architecture

## 8.1 Architectural style
A **service-oriented, three-tier architecture** with a separate stateless intelligence service:
1. **Presentation tier:** React SPA.
2. **Application tier:** Django REST API (business logic, workflow, security) + FastAPI ML service (analysis).
3. **Data tier:** PostgreSQL.

[INSERT Figure 8.1: architecture diagram from ../architecture.md]

## 8.2 Component responsibilities
| Component | Responsibility | Key technologies |
|---|---|---|
| React | UI, routing, charts, form validation | Vite, React Router, Axios, Recharts, Tailwind |
| Django | Auth, RBAC, CRUD, validation, workflow, audit, reports | DRF, SimpleJWT, ORM |
| FastAPI | Duplicate detection, rules, anomaly model, scoring | Pydantic, RapidFuzz, scikit-learn |
| PostgreSQL | Persistent relational storage | Constraints, indexes, JSONB |

## 8.3 Why a separate ML service? (justify in viva)
- The model is loaded once. Heavy ML dependencies are isolated from the web app.
- The ML service can be tested independently with simple JSON in and JSON out.
- It is replaceable and scalable without changing business logic.
- Trade-off: an extra network hop and one more process to run. This is mitigated by timeouts and the fail-safe fallback.

## 8.4 Communication
REST/JSON over HTTP on localhost. React→Django uses a JWT bearer token. Django→FastAPI uses a shared internal API key. See [../architecture.md §5](../architecture.md#5-communication).

## 8.5 Deployment
Four native Windows processes on one machine (no containers). [INSERT deployment diagram from ../deployment.md]
