# Hamoon — Technical Architecture v1

> وضعیت: Technical Architecture Baseline v1  
> مبنا: `HAMOON_AI_ARCHITECTURE_BASELINE.md`  
> اصل راهنما: **Hamoon یک ماشین تصمیم‌گیری و یادگیری توانمندسازی است، نه CRUD + AI.**

---

## 1. هدف این سند

این سند Baseline محصولی و AI هامون را به یک معماری فنی قابل پیاده‌سازی تبدیل می‌کند.

هدف این نسخه انتخاب نهایی تکنولوژی نیست؛ هدف تثبیت موارد زیر است:

- مرزهای سیستم
- Domain Model
- Temporal Data Model
- Current Accepted State
- PGOR Data Model
- Intelligence Architecture
- Human-in-the-loop
- Learning Architecture
- API / Event boundaries
- Audit / Traceability
- Security boundaries
- الزامات Observability و Evaluation

تصمیم‌های Stack، Cloud، Database Engine، Message Broker، Model Provider و Deployment Topology در ADRهای جداگانه ثبت خواهند شد.

---

# 2. اصول غیرقابل نقض معماری

## 2.1 AI-First

Hamoon از ابتدا یک سیستم هوشمند تصمیم‌یار است.

```text
Data
→ State
→ Evidence
→ PGOR
→ Intelligence
→ Human Decision
→ Action
→ Result
→ Outcome
→ Learning Signal
↺
```

UI و Workflow برای تغذیه و کنترل همین حلقه ساخته می‌شوند.

---

## 2.2 PGOR قطعی است، AI مولد نیست

محاسبه:

- P
- G
- O
- R
- E

باید:

- deterministic
- versioned
- reproducible
- auditable

باشد.

LLM مجاز نیست این مقادیر را حدس بزند.

---

## 2.3 Current Accepted State منبع تصمیم است

Hamoon همه نسخه‌های داده را حفظ می‌کند، اما موتورهای تصمیم از:

> **Current Accepted Value**

استفاده می‌کنند.

Current Accepted State یک Projection است، نه overwrite رکورد قبلی.

---

## 2.4 تاریخچه حذف نمی‌شود

هر اصلاح داده باید قابل بازسازی باشد.

```text
Old Value
+ New Value
+ Source
+ Effective At
+ Recorded At
+ Changed By
+ Reason
+ Evidence
+ Status
+ Version
```

---

## 2.5 Provider Result با Hamoon Outcome یکی نیست

```text
Provider Result ≠ Hamoon Outcome
```

Provider نتیجه اجرای خدمت را گزارش می‌کند.

Hamoon Outcome فقط بعد از سنجش مستقل و Re-assessment ثبت می‌شود.

---

## 2.6 Human-in-the-loop

خروجی AI در نقاط حساس باید قابل:

- Confirm
- Modify
- Replace
- Reject
- Explain
- Audit

باشد.

Human Decision خودش بخشی از Learning Signal است.

---

## 2.7 Learning به معنی Retrain فوری نیست

```text
Production Signal
→ Learning Store
→ Curated Dataset
→ Offline Evaluation
→ Candidate
→ Validation
→ Approval
→ Versioned Deployment
→ Monitoring
```

هیچ تغییر مستقیم و خودکار Production Model بر اساس یک Feedback منفرد مجاز نیست.

---

# 3. System Context

## 3.1 بازیگران

### Caseworker
کاربر اصلی عملیاتی Hamoon.

مسئول:

- مشاهده پرونده
- تکمیل داده
- اصلاح داده
- ارزیابی
- بررسی تشخیص
- بررسی نسخه
- انتخاب / تأیید Provider
- Referral
- پیگیری
- Re-assessment

### Admin / Management

مسئول مشاهده:

- وضعیت جمعیت
- PGOR distribution
- bottlenecks
- intervention outcomes
- operational health
- model health
- diagnosis disagreement
- learning signals

### Household

موضوع مسیر توانمندسازی است، نه کاربر اصلی عملیاتی سیستم.

### External Systems

منابع داده بیرونی مجاز.

### Specialized Providers

ارائه‌دهندگان مستقل خدمت.

---

# 4. High-Level Architecture

```text
                    ┌──────────────────────┐
                    │      Hamoon UI       │
                    │ Caseworker / Admin   │
                    └──────────┬───────────┘
                               │
                         Application API
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
        ▼                      ▼                      ▼
 Household Domain       Empowerment Domain      Referral Domain
        │                      │                      │
        ▼                      ▼                      ▼
 Temporal Facts          PGOR / Assessment       Provider / Result
        │                      │                      │
        └─────────────┬────────┴───────────┬─────────┘
                      │                    │
                      ▼                    ▼
             Current State Layer    Event / Audit Layer
                      │
                      ▼
               Feature / Evidence Layer
                      │
                      ▼
                 PGOR Engine
                      │
                      ▼
             Intelligence Platform
        ┌─────────────┼─────────────────────────────┐
        │             │              │              │
        ▼             ▼              ▼              ▼
   Diagnosis      Prediction    Prescription      Matching
        │             │              │              │
        └─────────────┴──────┬───────┴──────────────┘
                             ▼
                      Decision Package
                             │
                             ▼
                       Human Review
                             │
                             ▼
                         Action
                             │
                             ▼
                   Result / Re-assessment
                             │
                             ▼
                         Outcome
                             │
                             ▼
                      Learning Store
```

---

# 5. Bounded Contexts

## 5.1 Identity & Access

مسئول:

- authentication
- organizational identity
- roles
- permissions
- sessions
- access policy

نقش‌های اولیه:

```text
CASEWORKER
ADMIN
MANAGER
SYSTEM_INTEGRATION
PROVIDER_INTEGRATION
```

---

## 5.2 Household

مالک:

- Household
- Member
- Case Metadata
- Household lifecycle
- source linkage

این Context مالک PGOR نیست.

---

## 5.3 Family Data / Temporal Facts

مالک تمام Factهای زمان‌مند خانوار.

وظایف:

- provenance
- versioning
- correction
- dispute
- evidence
- current accepted projection
- historical reconstruction

---

## 5.4 Assessment & PGOR

مالک:

- PGOR Indicator Definition
- Indicator Observation
- Assessment
- PGOR Snapshot
- E calculation
- formula version

---

## 5.5 Diagnosis

مالک:

- machine diagnosis
- evidence
- confidence
- human decision
- accepted diagnosis
- diagnosis history

---

## 5.6 Prescription

مالک:

- machine proposal
- intervention candidates
- human modifications
- accepted prescription
- priorities
- targets
- success criteria

---

## 5.7 Provider & Referral

مالک:

- Provider registry
- service catalog
- coverage
- capacity
- eligibility
- referral
- referral status
- minimal data package
- provider result

---

## 5.8 Outcome

مالک:

- provider result interpretation
- re-assessment link
- observed change
- outcome classification
- non-causal reporting
- intervention effect record

---

## 5.9 Intelligence

مالک:

- AI inference orchestration
- feature/evidence packaging
- decision trace
- model version
- prompt/policy version
- evaluation metadata

---

## 5.10 Learning

مالک:

- learning signals
- human override signals
- curated training/evaluation datasets
- experiment records
- model evaluation
- promotion history

---

# 6. Core Domain Model

```text
Household
├── Members
├── CaseMetadata
├── Facts
│   ├── FactVersion
│   ├── Source
│   ├── Evidence
│   └── Status
├── CurrentAcceptedState
├── Assessments
│   ├── IndicatorObservations
│   ├── PGORSnapshot
│   └── FormulaVersion
├── Diagnoses
│   ├── MachineDiagnosis
│   ├── HumanDecision
│   └── AcceptedDiagnosis
├── Prescriptions
│   ├── MachineProposal
│   ├── HumanChanges
│   └── AcceptedPrescription
├── Interventions
├── Referrals
├── ProviderResults
├── ReAssessments
├── Outcomes
├── DecisionTraces
├── LearningSignals
└── TimelineEvents
```

---

# 7. Temporal Family Data Model

## 7.1 Fact

هر داده عملیاتی مهم باید به صورت Fact ثبت شود.

نمونه:

```text
HouseholdFact
- id
- household_id
- member_id? 
- fact_type
- value
- unit?
- source_id
- source_type
- evidence_id?
- effective_from
- effective_to?
- recorded_at
- recorded_by
- status
- supersedes_fact_id?
- correction_reason?
- schema_version
```

---

## 7.2 وضعیت Fact

```text
ACCEPTED
CORRECTED
DISPUTED
SUPERSEDED
```

قاعده:

- داده منبع مجاز به صورت پیش‌فرض ACCEPTED است.
- اصلاح مقدار قبلی را حذف نمی‌کند.
- SUPERSEDED فقط تاریخچه را نشان می‌دهد.
- DISPUTED باید در تصمیم حساس قابل مشاهده باشد.

---

## 7.3 Source Type

در سطح مفهومی:

```text
HOUSEHOLD_DECLARATION
EXPERT_ASSESSMENT
EXTERNAL_DATA
```

جزئیاتی مثل:

- مددکار
- سامانه بیمه
- Provider Result
- گزارش بازدید
- فایل
- مدرک

به عنوان Source Detail / Evidence ثبت می‌شوند.

---

## 7.4 Current Accepted State

Projection:

```text
CurrentAcceptedState
- household_id
- fact_type
- accepted_fact_id
- accepted_value
- effective_at
- source
- status
- computed_at
```

این Projection قابل بازسازی از Fact history است.

---

## 7.5 Historical State Reconstruction

Hamoon باید بتواند پاسخ دهد:

> وضعیت پذیرفته‌شده خانوار در زمان T چه بوده است؟

برای بازسازی:

```text
Household
+ Facts effective at T
+ acceptance history
+ formula/model versions valid at T
→ State(T)
```

این قابلیت برای Audit و AI Evaluation حیاتی است.

---

# 8. PGOR Indicator Model

تعریف Indicator باید Configuration/Version باشد، نه Hard-coded پراکنده در UI.

## 8.1 Structure

```text
PGORVariable
→ Dimension
→ Indicator
```

---

## 8.2 P — Participation

### انگیزه
- تمایل به تغییر
- امید به آینده

### مسئولیت‌پذیری
- پیگیری امور
- انجام تعهدات

### تعامل
- ارتباط با نهادها
- مشارکت اجتماعی

### حضور در برنامه‌ها
- آموزش
- جلسات
- فعالیت‌های توسعه‌ای

---

## 8.3 G — Growth Capacity

### سرمایه انسانی
- تحصیلات
- مهارت

### تجربه
- سابقه کاری
- تجربه تولید

### قابلیت یادگیری
- آموزش‌پذیری
- انعطاف

### سلامت عملکردی
- توان جسمی
- توان شناختی

---

## 8.4 O — Opportunity

### بازار
- تقاضا
- اشتغال

### زیرساخت
- حمل‌ونقل
- اینترنت

### دسترسی
- خدمات
- سرمایه

### شبکه اقتصادی
- ارتباطات
- زنجیره ارزش

---

## 8.5 R — Resilience

- ثبات درآمد
- حمایت اجتماعی
- سلامت خانوادگی
- توان مقابله با بحران
- تنوع منابع درآمدی

---

# 9. Indicator Observation

هر Indicator Observation باید قابلیت نگهداری مقدار خام را داشته باشد.

```text
IndicatorObservation
- id
- assessment_id
- indicator_definition_id
- raw_value
- raw_score_0_100
- normalized_score_0_1
- source_type
- source_detail
- evidence
- effective_at
- observed_at
- observer
- status
```

UI می‌تواند از scale انسانی استفاده کند:

```text
خیلی کم
کم
متوسط
بالا
خیلی بالا
```

اما mapping به score باید versioned و قابل Audit باشد.

---

# 10. PGOR Engine

## 10.1 Input

فقط:

- accepted indicator observations
- active scoring version
- formula version

---

## 10.2 Output

```text
PGORSnapshot
- assessment_id
- p
- g
- o
- r
- e
- bottleneck
- formula_version
- scoring_version
- calculated_at
- input_fingerprint
```

---

## 10.3 Empowerment Function

نسخه فعلی Baseline:

```text
E = (α P^3 + β G^2 + γ O)(0.5 + 0.5 R)
```

با:

```text
P,G,O,R ∈ [0,1]
```

ضرایب:

```text
α
β
γ
```

نباید در Code پراکنده باشند؛ باید در Formula Version مدیریت شوند.

---

## 10.4 Reproducibility

برای هر Snapshot باید امکان محاسبه مجدد دقیق وجود داشته باشد.

ذخیره حداقل:

- input fact/observation ids
- scoring version
- formula version
- coefficient version
- code/engine version

---

# 11. Temporal Feature / Evidence Layer

AI نباید مستقیماً و آزادانه از جداول عملیاتی Query بزند.

بین Data Domain و AI یک لایه کنترل‌شده لازم است:

```text
Operational Data
→ Accepted State
→ Feature Builder
→ Evidence Package
→ AI Engine
```

نمونه Featureها:

- current PGOR
- PGOR trend
- bottleneck
- recent events
- intervention history
- referral history
- provider results
- prior outcomes
- unresolved disputes
- current constraints
- relevant evidence

---

# 12. Intelligence Architecture

```text
                AI Gateway
                    │
          Intelligence Orchestrator
                    │
 ┌──────────────────┼──────────────────┐
 │                  │                  │
 ▼                  ▼                  ▼
Diagnosis       Prescription       Matching
 │                  │                  │
 ├──── Prediction   ├── Simulation     │
 │                  │                  │
 └──────────────────┴──────┬───────────┘
                           ▼
                    Decision Package
```

---

# 13. AI Gateway

مسئول:

- provider abstraction
- model routing
- timeout
- retry policy
- safety policy
- structured output enforcement
- token/cost accounting
- tracing
- version capture

هیچ Domain Service نباید مستقیماً به یک Model Provider خاص وابسته شود.

---

# 14. Decision Package

هر خروجی هوشمند مهم باید به شکل Structured Decision Package ذخیره شود.

```text
AIDecision
- id
- household_id
- decision_type
- state_version
- pgor_snapshot_id?
- model_id
- model_version
- prompt_policy_version?
- feature_version
- evidence_refs[]
- output
- confidence?
- uncertainty?
- generated_at
- trace_id
```

---

# 15. Human Decision

```text
HumanDecision
- id
- ai_decision_id
- actor_id
- action
- accepted_output?
- modified_output?
- reason?
- evidence_refs?
- decided_at
```

Action:

```text
CONFIRM
MODIFY
REPLACE
REJECT
DEFER
```

---

# 16. Decision Trace

برای هر تصمیم حساس باید بتوانیم زنجیره زیر را بازسازی کنیم:

```text
State Version
→ PGOR Snapshot
→ Feature Package
→ AI Model/Rule
→ AI Output
→ Human Decision
→ Action
→ Result
→ Outcome
```

Decision Trace یک الزام معماری است، نه صرفاً Log Debug.

---

# 17. Diagnosis Engine

ورودی:

- accepted state
- PGOR snapshot
- trajectory
- evidence
- current disputes
- history

خروجی:

- diagnosis candidates
- bottleneck explanation
- supporting evidence
- confidence/uncertainty where applicable
- suggested review priority

Final Accepted Diagnosis فقط بعد از policy مربوط به Human Review معتبر می‌شود.

---

# 18. Prescription Engine

ورودی:

- accepted diagnosis
- current state
- PGOR
- intervention catalog
- constraints
- history

خروجی:

- prioritized intervention options
- target PGOR dimension
- current → target
- success criteria
- review timing
- rationale
- evidence

AI proposal و Human Accepted Prescription باید جدا ذخیره شوند.

---

# 19. Matching Engine

V1:

Rule-based eligibility and matching.

```text
Service Type
+ Eligibility
+ Coverage
+ Capacity
+ Availability
→ Candidate Providers
```

بعداً می‌تواند evidence-informed شود.

Matching نباید خروجی «بهترین Provider» تولید کند.

خروجی مطلوب:

> Candidate providers + reason for suitability under current conditions

---

# 20. Referral State Machine

```text
READY
→ SENT
→ ACCEPTED
→ IN_PROGRESS
→ COMPLETED
```

Variant states:

```text
WAITING_CAPACITY
NEEDS_INFORMATION
REJECTED
NO_RESPONSE
CANCELLED
```

هر transition باید Event و Audit تولید کند.

---

# 21. Provider Result

```text
ProviderResult
- referral_id
- provider_id
- status
- result_type
- result_payload
- evidence
- completed_at
- submitted_at
- provider_reference
```

این Entity Outcome نیست.

---

# 22. Outcome Model

Outcome فقط بعد از Re-assessment یا سنجش معتبر ثبت می‌شود.

```text
HamoonOutcome
- intervention_id
- referral_id?
- pre_assessment_id
- post_assessment_id
- observed_change
- pgor_delta
- e_delta
- classification
- evidence
- assessed_by
- assessed_at
```

Classification اولیه:

```text
GOAL_ACHIEVED
PROGRESS
NO_SIGNIFICANT_CHANGE
REGRESSION
NEEDS_MORE_TIME
NEEDS_MORE_DATA
```

از ادعای causal بدون روش علمی مناسب اجتناب می‌شود.

---

# 23. Learning Signal

```text
LearningSignal
- signal_type
- household_state_version
- ai_decision_id?
- human_decision_id?
- intervention_id?
- provider_id?
- provider_result_id?
- outcome_id?
- label/value
- quality
- created_at
```

نمونه:

```text
DIAGNOSIS_CONFIRMED
DIAGNOSIS_MODIFIED
DIAGNOSIS_REPLACED
PRESCRIPTION_MODIFIED
PROVIDER_CHANGED
MATCHING_REJECTED
OUTCOME_OBSERVED
DATA_CONFLICT_RESOLVED
```

---

# 24. Learning Store

Learning Store نباید مستقیماً Production DB را به Training Pipeline تبدیل کند.

```text
Operational Events
→ Learning Signals
→ Curated Learning Store
→ Dataset Version
→ Evaluation
→ Candidate Model
```

---

# 25. Model Registry

هر مدل Production باید حداقل:

- model_id
- version
- purpose
- owner
- training/evaluation dataset version
- metrics
- limitations
- status
- approval
- deployed_at
- retired_at

داشته باشد.

Status:

```text
EXPERIMENT
CANDIDATE
APPROVED
PRODUCTION
RETIRED
```

---

# 26. Prompt / Policy Registry

برای اجزای LLM-based:

```text
PromptPolicy
- id
- purpose
- version
- template
- output_schema_version
- guardrail_version
- model_constraints
- approved_at
- retired_at
```

Prompt change یک تغییر Production قابل Audit است.

---

# 27. Evaluation Framework

قبل از Production هر Intelligence Engine باید Evaluation مخصوص خودش داشته باشد.

نمونه:

### Diagnosis
- agreement with expert review
- modification rate
- replacement rate
- evidence coverage
- calibration

### Prescription
- expert acceptance
- modification patterns
- safety violations
- target alignment

### Matching
- eligibility correctness
- provider acceptance
- no-response rate
- outcome evidence

### LLM
- schema compliance
- groundedness
- hallucination checks
- safety
- consistency

---

# 28. Event Architecture

Eventها باید Domain Event باشند، نه صرفاً Technical Log.

نمونه:

```text
HouseholdFactRecorded
HouseholdFactCorrected
HouseholdFactDisputed
CurrentAcceptedStateChanged

AssessmentStarted
IndicatorObserved
AssessmentCompleted
PGORSnapshotCalculated

DiagnosisGenerated
DiagnosisConfirmed
DiagnosisModified
DiagnosisReplaced

PrescriptionGenerated
PrescriptionApproved
PrescriptionModified

ReferralCreated
ReferralSent
ReferralAccepted
ReferralRejected
ReferralNoResponse
ReferralCompleted

ProviderResultSubmitted

ReassessmentCompleted
OutcomeRecorded

LearningSignalCreated
```

---

# 29. API Boundary

APIها در V1 باید Domain-oriented باشند.

نمونه سطح بالا:

```text
/households
/households/{id}/facts
/households/{id}/accepted-state

/assessments
/assessments/{id}/indicators
/assessments/{id}/pgor

/diagnoses
/prescriptions

/providers
/referrals
/provider-results

/reassessments
/outcomes

/ai/decisions
/ai/evaluations
```

جزئیات Endpoint Contract در سند API جداگانه تعریف می‌شود.

---

# 30. Integration Architecture

```text
External System
   ↓
Integration Adapter
   ↓
Canonical Data Contract
   ↓
Validation
   ↓
Provenance
   ↓
Household Fact
```

هیچ Integration خارجی نباید مستقیم Domain Tables را بنویسد.

---

# 31. Idempotency

تمام Integrationهای بیرونی باید Idempotent باشند.

هر پیام/درخواست خارجی باید:

```text
source_system
external_event_id
external_record_id
received_at
payload_hash
```

داشته باشد.

---

# 32. Security Architecture

حداقل:

- SSO / Organizational Identity
- RBAC
- provider isolation
- purpose-bound access
- referral-specific sharing
- field-level filtering where needed
- audit log
- encryption in transit
- encryption at rest
- secret management
- session control
- access logging

---

# 33. Provider Data Isolation

Provider هرگز دسترسی مستقیم به Household Workspace ندارد.

فقط:

```text
Referral Data Package
→ Provider
```

با حداقل داده لازم.

Provider Result نیز از قرارداد مشخص وارد می‌شود.

---

# 34. Audit

Audit باید برای این موارد اجباری باشد:

- fact changes
- accepted state changes
- diagnosis decisions
- prescription decisions
- provider selection
- referral status
- data sharing
- admin actions
- model/prompt version changes
- human override
- outcome classification

---

# 35. Observability

سه دسته Monitoring جدا:

## Platform
- latency
- errors
- throughput
- availability

## Data
- freshness
- integration failures
- disputed data
- missing critical indicators
- source anomalies

## AI
- inference failures
- schema failures
- confidence drift
- human modification rate
- human replacement rate
- model/version distribution
- evaluation drift
- safety violations

---

# 36. Current Accepted State و AI

AI حق تغییر مستقیم Current Accepted State را ندارد.

AI می‌تواند:

- anomaly flag کند
- conflict flag کند
- correction suggestion بدهد
- evidence request کند

اما تغییر رسمی نیازمند Rule/Authority/Human Action مشخص است.

---

# 37. Deployment Principle

Application Runtime و Intelligence Runtime باید از نظر منطقی قابل جداسازی باشند، حتی اگر در V1 روی زیرساخت مشترک Deploy شوند.

```text
Application Plane
Data Plane
Intelligence Plane
Integration Plane
Observability Plane
```

این جداسازی امکان Scaling، امنیت و Model Evolution مستقل را فراهم می‌کند.

---

# 38. تصمیم‌هایی که در این نسخه تثبیت شدند

- Hamoon AI-first است.
- PGOR deterministic است.
- Facts append/version based هستند.
- Current Accepted State projection است.
- Historical state باید reconstructable باشد.
- AI decisions structured و traceable هستند.
- Human decisions learning signals هستند.
- Provider Result با Outcome جداست.
- Retraining مستقیم از Production feedback ممنوع است.
- Model / Prompt / Formula / Feature versions باید قابل Audit باشند.
- Integrationها فقط از Canonical Contract وارد Domain می‌شوند.

---

# 39. تصمیم‌های باز

این موارد هنوز باید در ADR تصمیم‌گیری شوند:

- backend stack
- relational database engine
- temporal storage strategy
- event broker
- object/evidence storage
- search/index
- cache
- identity provider
- AI model providers
- embedding/vector strategy
- workflow engine
- cloud/deployment platform
- observability stack
- secrets/KMS
- data warehouse/lake strategy

---

# 40. مرحله بعد

مرحله بعد از این سند:

```text
1. ERD / Database Schema v1
2. PGOR Indicator & Formula Schema
3. API Contracts v1
4. Event Contracts v1
5. AI Decision Schema
6. Referral State Machine
7. Security / RBAC Matrix
8. ADRهای Stack
9. Product Backlog
10. Sprint 1
```

اولین خروجی بعدی:

> **HAMOON_DATA_MODEL_V1.md + ERD**

چون Data Model پایه تمام PGOR، AI، Audit، Outcome و Learning است.
