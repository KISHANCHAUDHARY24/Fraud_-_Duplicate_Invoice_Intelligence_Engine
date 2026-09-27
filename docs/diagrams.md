# Software Engineering Diagrams

> **Status:** ✅ Matches the finished system (Phase 16). All diagrams are Mermaid. They render on GitHub and in VS Code (with the "Markdown Preview Mermaid Support" extension). To export PNGs for your report, paste each diagram into https://mermaid.live and download.

## 1. Use case diagram
Mermaid has no native use-case notation, so actors and use cases are drawn as a flowchart.

```mermaid
flowchart LR
    ADM([👤 Admin])
    AP([👤 AP Officer])
    MGR([👤 Manager])
    AUD([👤 Auditor])
    ML([⚙ ML Service])

    subgraph SYS[Expense Intelligence Engine]
      UC1((Log in / out))
      UC2((Manage users & roles))
      UC3((Manage vendors))
      UC4((Configure settings))
      UC5((Create / upload invoice))
      UC6((Submit invoice))
      UC7((Analyse invoice))
      UC8((View risk analysis))
      UC9((Approve / reject / clarify))
      UC10((Escalate))
      UC11((Investigate alert))
      UC12((Compare invoices))
      UC13((View audit logs))
      UC14((View analytics))
      UC15((Export reports))
    end

    ADM --- UC1 & UC2 & UC3 & UC4 & UC13 & UC14 & UC15
    AP --- UC1 & UC3 & UC5 & UC6 & UC8
    MGR --- UC1 & UC8 & UC9 & UC10 & UC14
    AUD --- UC1 & UC8 & UC9 & UC11 & UC12 & UC13 & UC15
    UC6 -. includes .-> UC7
    UC7 --- ML
```

## 2. Activity diagram: invoice lifecycle
```mermaid
flowchart TD
    A([Start]) --> B[AP enters / uploads invoice]
    B --> C{Valid?}
    C -- No --> B1[Show validation errors] --> B
    C -- Yes --> D[Save as DRAFT]
    D --> E[Submit]
    E --> F[Status = PROCESSING]
    F --> G[Django builds context and calls FastAPI]
    G --> H{ML service OK?}
    H -- No --> H1[fraud_status = ANALYSIS_FAILED] --> M
    H -- Yes --> I[Duplicate check + rules + Isolation Forest]
    I --> J[Risk score + reasons]
    J --> K{Risk level}
    K -- LOW ≤ threshold --> L[Auto-approve]
    K -- LOW > threshold / MEDIUM --> M[Manager review]
    K -- HIGH --> N[Auditor review]
    K -- CRITICAL --> O[Block payment + investigation]
    M --> P{Decision}
    N --> P
    O --> Q{Auditor outcome}
    Q -- Cleared --> N
    Q -- Confirmed issue --> R[REJECTED]
    P -- Approve --> S[APPROVED]
    P -- Reject --> R
    P -- Clarify --> D
    P -- Escalate --> N
    L --> S
    S --> T[Simulated payment → PAID]
    R --> U[Audit log + notify]
    T --> U
    U --> V([End])
```

## 3. Sequence diagram: fraud analysis
```mermaid
sequenceDiagram
    actor AP as AP Officer
    participant FE as React
    participant API as Django View
    participant SVC as Invoice/Fraud Service
    participant DB as PostgreSQL
    participant ML as FastAPI
    participant RT as Routing Engine
    AP->>FE: Click "Submit"
    FE->>API: POST /api/invoices/42/submit/
    API->>API: Check JWT + role + ownership
    API->>SVC: submit_invoice(42, user)
    SVC->>DB: status → PROCESSING
    SVC->>DB: fetch candidates, vendor stats, settings
    SVC->>ML: POST /api/v1/fraud/analyze
    ML-->>SVC: score, level, signals
    SVC->>DB: FraudAnalysis, FraudSignals, FraudAlert
    SVC->>RT: route(invoice, result)
    RT->>DB: Approval / status update
    SVC->>DB: AuditLog, Notifications
    SVC-->>API: invoice
    API-->>FE: 200 + risk details
    FE-->>AP: Show score and reasons
```

## 4. Sequence diagram: manager decision
```mermaid
sequenceDiagram
    actor M as Manager
    participant FE as React
    participant API as Django
    participant DB as PostgreSQL
    M->>FE: Reject (comment)
    FE->>API: POST /api/approvals/7/reject/ {comment}
    API->>API: assigned_to == user? comment present? state allowed?
    API->>DB: BEGIN
    API->>DB: Approval=REJECTED, Invoice=REJECTED
    API->>DB: AuditLog(INVOICE_REJECTED, old, new)
    API->>DB: Notification(submitter)
    API->>DB: COMMIT
    API-->>FE: 200
```

## 5. Class diagram (main domain classes)
```mermaid
classDiagram
    class Role { +code +name }
    class User { +username +email +department +role +has_role(codes) }
    class Vendor { +vendor_name +normalized_name +registration_number +status +active_bank_account() }
    class VendorBankAccount { +bank_name +account_last4 +account_hash +is_active +masked() }
    class Invoice { +invoice_number +amount +invoice_date +submission_date +approval_status +fraud_status +risk_score +risk_level +can_transition(to) }
    class InvoiceItem { +description +quantity +unit_price +line_total }
    class FraudAnalysis { +risk_score +risk_level +duplicate_score +anomaly_score +model_version }
    class FraudSignal { +signal_type +severity +points +message +details }
    class FraudAlert { +primary_type +severity +status +outcome +resolve() }
    class Approval { +level +decision +comment +approve() +reject() +escalate() }
    class Payment { +amount +status +reference }
    class AuditLog { +action +entity_type +entity_id +old_value +new_value }
    class Notification { +type +title +is_read }
    class SystemSetting { +key +value }

    Role "1" --> "*" User
    Vendor "1" *-- "*" VendorBankAccount
    Vendor "1" --> "*" Invoice
    User "1" --> "*" Invoice : submits
    Invoice "1" *-- "*" InvoiceItem
    Invoice "1" --> "*" FraudAnalysis
    FraudAnalysis "1" *-- "*" FraudSignal
    Invoice "1" --> "0..1" FraudAlert
    Invoice "1" --> "*" Approval
    Invoice "1" --> "0..1" Payment
    User "1" --> "*" Notification

    class DuplicateDetector { +check(invoice, candidates, weights) DuplicateResult }
    class RuleEngine { +evaluate(features, config) List~Signal~ }
    class FeatureEngineer { +build(invoice, context) DataFrame }
    class ModelRegistry { +load() +predict(features) float }
    class RiskScorer { +score(signals, config) RiskResult }
    class FraudDetector { +analyze(request) AnalysisResult }
    FraudDetector --> DuplicateDetector
    FraudDetector --> RuleEngine
    FraudDetector --> FeatureEngineer
    FraudDetector --> ModelRegistry
    FraudDetector --> RiskScorer
```

## 6. ER diagram
See [database.md §1](database.md#1-er-diagram).

## 7. System architecture diagram
See [architecture.md §1](architecture.md#1-overview).

## 8. Data flow diagram

### Level 0 (context)
```mermaid
flowchart LR
    AP[AP Officer] -- invoices, CSV --> S((Expense Intelligence Engine))
    S -- validation results, risk --> AP
    MGR[Manager] -- decisions --> S
    S -- approval requests --> MGR
    AUD[Auditor] -- investigation outcomes --> S
    S -- alerts, reports, audit logs --> AUD
    ADM[Admin] -- users, vendors, settings --> S
    S -- analytics --> ADM
```

### Level 1
```mermaid
flowchart LR
    AP[AP Officer] --> P1((1. Validate & store invoice))
    P1 --> D1[(D1 Invoices)]
    P1 --> P2((2. Analyse risk))
    D1 --> P2
    D2[(D2 Vendors & bank history)] --> P2
    D5[(D5 Settings)] --> P2
    P2 --> D3[(D3 Analyses, signals, alerts)]
    P2 --> P3((3. Route & decide))
    P3 --> D4[(D4 Approvals & payments)]
    MGR[Manager / Auditor] --> P3
    P1 & P2 & P3 --> P4((4. Audit & notify))
    P4 --> D6[(D6 Audit log & notifications)]
    D1 & D3 & D4 & D6 --> P5((5. Analytics & reports))
    P5 --> AUD[Auditor / Admin]
```

## 9. Deployment diagram
See [deployment.md §1](deployment.md#1-deployment-diagram): one Windows computer running the React dev server, Django, FastAPI and PostgreSQL. No Docker.
