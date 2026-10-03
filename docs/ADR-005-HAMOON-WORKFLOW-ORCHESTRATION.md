# ADR-005 — Hamoon Workflow Orchestration

> وضعیت: Accepted for V1  
> دامنه تصمیم: Long-running Workflows, Human Tasks, Timeouts, Retries, Referral Orchestration, Re-assessment Scheduling  
> وابسته به:
> - `HAMOON_TECHNICAL_ARCHITECTURE_V1.md`
> - `HAMOON_EVENT_CONTRACTS_V1.md`
> - `HAMOON_API_CONTRACTS_V1.md`
> - `HAMOON_SECURITY_RBAC_V1.md`
> - `ADR-001-HAMOON-CORE-STACK.md`
> - `ADR-002-HAMOON-REPOSITORY-ENGINEERING-STANDARDS.md`

---

# 1. Context

Hamoon چندین فرآیند کوتاه و بلندمدت دارد که ممکن است از چند دقیقه تا چند ماه ادامه پیدا کنند.

نمونه‌ها:

- AI diagnosis generation
- human review
- prescription approval
- provider matching
- referral dispatch
- waiting for provider acceptance
- provider no-response timeout
- service delivery
- provider result
- scheduled re-assessment
- outcome review
- learning signal creation

این فرآیندها باید:

- durable باشند
- restart-safe باشند
- retry داشته باشند
- timeout داشته باشند
- human-in-the-loop را پشتیبانی کنند
- callback خارجی را تحمل کنند
- state قابل audit داشته باشند
- با Domain State یکی نشوند
- replay-safe باشند

---

# 2. Decision Summary

برای V1 تصمیم می‌گیریم:

```text
Durable Workflow Engine:
Temporal

Domain State:
PostgreSQL

Domain Event Backbone:
NATS JetStream

Workflow Role:
Orchestration only

Source of Truth:
Domain aggregates in PostgreSQL

Human Tasks:
Domain Work Queue + Temporal wait/signal

External Call Retries:
Temporal Activities

Business Events:
Outbox → NATS

Workflow Commands:
Application Services / Domain Commands

Long Delays:
Temporal Timers

Provider Callbacks:
API/Inbox → Domain Command → Event/Signal

Re-assessment Scheduling:
Temporal Timer / durable workflow

Workflow Data:
IDs + minimal orchestration state
not full household payload
```

---

# 3. Why Temporal

Hamoon has workflows that are:

- long-running
- callback-driven
- time-dependent
- human-dependent
- integration-heavy
- retry-sensitive

Examples:

```text
Referral Sent
→ wait 72 hours
→ Provider Accepted?
   Yes → continue
   No  → create follow-up / no-response state
```

یا:

```text
Outcome Review
→ wait until reassessment date
→ create reassessment work item
→ wait for completion
→ calculate outcome
```

پیاده‌سازی این رفتار فقط با cron + queue + status columns باعث پراکندگی orchestration logic می‌شود.

Temporal برای durable execution انتخاب می‌شود تا orchestration قابل تعریف، تست و بازیابی باشد.

---

# 4. Temporal Is Not the Domain Database

قانون اصلی:

> Temporal workflow history منبع حقیقت Business نیست.

Source of Truth:

```text
PostgreSQL Domain State
```

Temporal نگه می‌دارد:

- orchestration progress
- timer state
- retry state
- activity execution history
- workflow signals

اما وضعیت نهایی Referral، Diagnosis، Outcome و غیره داخل Domain Aggregate ذخیره می‌شود.

---

# 5. NATS vs Temporal

این دو جای یکدیگر را نمی‌گیرند.

## NATS JetStream

برای:

- domain events
- projections
- learning signals
- analytics feeds
- event consumers
- decoupled reactions

## Temporal

برای:

- multi-step orchestration
- durable waiting
- timeout
- retry
- human approval wait
- external callback coordination
- scheduled future continuation

قاعده:

```text
Event-driven reaction → NATS
Long-running coordinated process → Temporal
```

---

# 6. Workflow Boundaries

V1 workflowهای اصلی:

```text
DiagnosisReviewWorkflow
PrescriptionReviewWorkflow
ReferralWorkflow
ReassessmentWorkflow
OutcomeWorkflow
```

ممکن است بعداً:

```text
EvidenceProcessingWorkflow
ModelEvaluationWorkflow
ProviderOnboardingWorkflow
```

اضافه شوند.

---

# 7. Workflow → Domain Interaction

Workflow مستقیماً table update نمی‌کند.

درست:

```text
Workflow
→ Activity
→ Application Command
→ Domain Aggregate
→ Repository
→ Outbox Event
```

غلط:

```text
Workflow
→ UPDATE referrals SET status = ...
```

---

# 8. Activity Rule

تمام side effectها باید داخل Activity باشند.

Workflow code نباید مستقیم:

- database call
- HTTP call
- provider SDK call
- AI provider call
- object storage call

انجام دهد.

Workflow فقط orchestration logic است.

---

# 9. Deterministic Workflow Rule

Temporal workflow code باید deterministic بماند.

ممنوع در Workflow:

- random بدون deterministic API
- wall-clock مستقیم
- network call
- DB query مستقیم
- mutable global state
- arbitrary non-deterministic library behavior

تمام این‌ها داخل Activity می‌روند.

---

# 10. Referral Workflow

Reference flow:

```text
ReferralCreated
↓
SendReferral Activity
↓
ReferralSent
↓
wait for Provider response
├─ Accepted
│   ↓
│   mark accepted
│   ↓
│   wait for service progression
│
├─ Rejected
│   ↓
│   mark rejected
│   ↓
│   create work item
│
└─ Timeout
    ↓
    ReferralNoResponse
    ↓
    create follow-up work item
```

بعد:

```text
Provider In Progress
↓
Provider Completed
↓
Provider Result
↓
start Reassessment Workflow
```

---

# 11. Provider Callback Path

Provider callback:

```text
Provider
→ Integration API
→ Inbox / Idempotency
→ Domain Command
→ Domain Event
→ Temporal Signal
```

Workflow به callback خام Provider اعتماد نمی‌کند.

ابتدا Domain validation انجام می‌شود.

---

# 12. Temporal Signals

نمونه Signalها:

```text
ProviderAccepted
ProviderRejected
ProviderStatusChanged
ProviderResultReceived
HumanDiagnosisReviewed
HumanPrescriptionReviewed
ReassessmentCompleted
OutcomeReviewed
```

Signal payload ترجیحاً فقط IDs و status codes دارد.

---

# 13. Human Review Workflow

مثال Diagnosis:

```text
GenerateDiagnosis Activity
↓
DiagnosisGenerated
↓
CreateWorkItem Activity
↓
wait for HumanReview signal
↓
Confirm / Modify / Replace / Reject
↓
ApplyDomainDecision Activity
↓
LearningSignal
```

Human تصمیم را از API ثبت می‌کند، نه مستقیم داخل Temporal UI.

---

# 14. Work Queue Is a Domain Projection

Temporal task queue با Hamoon Work Queue یکی نیست.

Hamoon Work Queue:

- محصولی
- متعلق به مددکار
- در PostgreSQL/projection
- قابل فیلتر و گزارش

Temporal Task Queue:

- زیرساخت اجرای Worker
- برای کاربر نهایی نمایش داده نمی‌شود

---

# 15. Long Timers

Temporal برای delayهای بلندمدت استفاده می‌شود.

مثال:

```text
wait 6 months
→ create reassessment task
```

یا:

```text
wait until provider response_due_at
→ no response?
→ follow-up
```

Cron polling گسترده برای این use caseها ترجیح داده نمی‌شود.

---

# 16. Reassessment Workflow

```text
InterventionCompleted
↓
Determine Review Schedule
↓
Temporal Timer
↓
Create Reassessment Work Item
↓
wait Human Completion
↓
Calculate PGOR
↓
Prepare Outcome
↓
wait Outcome Review
↓
Learning Signal
```

Schedule source باید versioned/policy-driven باشد.

---

# 17. Outcome Workflow

```text
Pre Snapshot
+ Provider Result
+ Post Snapshot
↓
Prepare Outcome Activity
↓
OutcomePrepared
↓
Human Review
↓
OutcomeConfirmed / Modified / More Time / More Data
↓
Learning Signal
```

اگر:

```text
NEEDS_MORE_TIME
```

باشد، Workflow می‌تواند timer جدید ایجاد کند.

---

# 18. AI Workflow Boundary

AI call یک Activity است.

```text
Workflow
→ GenerateDiagnosisActivity
→ AI Gateway
→ structured AI Decision
```

Workflow نباید مدل یا prompt را بشناسد.

---

# 19. AI Retry Policy

AI retries باید محدود و failure-aware باشند.

Retryable:

```text
timeout
temporary provider unavailable
rate limit
transient network failure
```

Non-retryable:

```text
invalid structured output after policy threshold
authorization failure
invalid feature package
unsupported model version
```

در failure نهایی:

```text
AI Decision Failed
→ Human fallback / retry work item
```

---

# 20. Provider Retry Policy

Provider dispatch:

```text
retry transient delivery failures
```

اما duplicate referral creation نباید رخ دهد.

نیازمند:

- idempotency key
- external delivery ledger
- provider contract version
- stable referral ID

---

# 21. Workflow IDs

Workflow ID باید stable و business-linked باشد.

مثال:

```text
referral:<referral_id>
diagnosis-review:<diagnosis_id>
prescription-review:<prescription_id>
reassessment:<assessment_id>
outcome:<outcome_id>
```

این کار از duplicate workflow start جلوگیری می‌کند.

---

# 22. Idempotency

هر Activity side effect باید idempotent باشد.

نمونه:

```text
SendReferral(referral_id)
```

اگر دوباره اجرا شد، نباید referral دوم بسازد.

Domain/Application نیز باید idempotency را enforce کند.

---

# 23. Retry vs Business Retry

تفکیک:

## Technical Retry

برای failure موقت:

```text
HTTP timeout
DB transient failure
provider gateway unavailable
```

## Business Retry / Follow-up

مثلاً Provider پاسخ نداده:

```text
ReferralNoResponse
→ business event
→ human follow-up
```

این را نباید با retry فنی مخلوط کرد.

---

# 24. Timeouts

هر External Activity باید timeout صریح داشته باشد.

انواع:

- start-to-close
- schedule-to-close
- heartbeat where needed

No infinite remote call.

---

# 25. Cancellation

Workflowها باید cancellation semantics داشته باشند.

مثال:

```text
household closed
intervention cancelled
referral cancelled
```

Cancellation باید:

- Domain state را validate کند
- pending timers را stop کند
- external side effects لازم را اجرا کند
- audit/event ایجاد کند

---

# 26. Compensation

Distributed transaction نداریم.

در صورت failure بعد از side effect:

```text
explicit compensating action
```

مثال:

Referral به Provider ارسال شده ولی local follow-up setup fail شده:

- referral ارسال‌شده باقی می‌ماند
- workflow recovery ادامه orchestration را rebuild می‌کند
- referral را silently rollback نمی‌کنیم

---

# 27. Workflow Versioning

Workflow code در طول زمان تغییر می‌کند.

Rule:

- running workflows must remain replay-compatible
- incompatible behavior needs version gate / new workflow version
- production deployment must test replay compatibility

Workflow version بخشی از operational observability است.

---

# 28. Domain Policy Versioning

Workflow نباید policyهای حساس را hard-code کند.

مثال:

```text
provider response timeout
reassessment interval
human review SLA
```

باید از versioned policy/config استفاده کند.

Workflow execution باید policy version مورد استفاده را ثبت کند.

---

# 29. Data Minimization in Workflow History

Temporal history ممکن است long-lived باشد.

پس Workflow Input/Signal باید حداقلی باشد.

Prefer:

```text
household_id
referral_id
assessment_id
policy_version
status_code
```

Avoid:

- national ID
- full household profile
- full evidence text
- raw AI prompt
- sensitive provider payload

---

# 30. Sensitive Data Rule

اگر Activity به sensitive data نیاز دارد:

```text
Activity
→ authorized application service
→ fetch current minimal data
```

نه اینکه data از ابتدا داخل workflow history embed شود.

---

# 31. Temporal Search Attributes

برای operational lookup می‌توان metadata غیرحساس را index کرد:

```text
WorkflowType
OrganizationId
ProviderId
StatusCode
```

PII در Search Attribute ممنوع است.

---

# 32. Workflow State vs Domain State

در اختلاف بین Workflow State و Domain State:

> Domain State مرجع Business است.

Workflow باید reconciliation/recovery logic داشته باشد.

مثال:

اگر workflow فکر کند Referral pending است ولی Domain = COMPLETED:

```text
workflow continues from authoritative domain state
```

---

# 33. Reconciliation

Periodic operational check می‌تواند موارد زیر را شناسایی کند:

- open domain process without workflow
- running workflow for closed aggregate
- stuck activity
- missing work item
- delayed provider result processing

هدف repair است، نه business decision.

---

# 34. Temporal Namespace Strategy

Reference:

```text
hamoon-dev
hamoon-stage
hamoon-prod
```

Environment isolation الزامی است.

Organization per namespace در V1 لازم نیست.

---

# 35. Task Queues

Logical queues:

```text
hamoon-core
hamoon-ai
hamoon-provider
hamoon-evidence
```

هدف:

- independent concurrency
- independent scaling
- isolation of slow external work

---

# 36. Worker Deployment

Workers می‌توانند process/container جدا باشند:

```text
hamoon-worker-core
hamoon-worker-ai
hamoon-worker-provider
```

همه می‌توانند از همان repository/codebase استفاده کنند.

---

# 37. Temporal Storage

Temporal server persistence، در صورت self-hosting، infrastructure concern است و نباید با Hamoon Primary PostgreSQL schema مخلوط شود.

Domain DB و Temporal internal persistence logical/physical separation دارند.

---

# 38. Self-hosted vs Managed

این ADR Temporal را انتخاب می‌کند، اما Deployment Mode را نهایی نمی‌کند.

گزینه:

```text
Temporal Cloud
or
self-hosted Temporal
```

در ADR-008 Deployment تعیین می‌شود.

---

# 39. Error Model

Activity errors باید typed شوند.

نمونه:

```text
RetryableProviderError
NonRetryableProviderError
VersionConflict
AuthorizationDenied
InvalidDomainTransition
AIOutputInvalid
```

Workflow بر اساس type تصمیم retry/fallback می‌گیرد.

---

# 40. Observability

حداقل metrics:

```text
workflow_started_total
workflow_completed_total
workflow_failed_total
workflow_cancelled_total
workflow_running_count
activity_retry_total
activity_failure_total
workflow_timeout_total
human_wait_duration
provider_wait_duration
reassessment_wait_duration
```

بدون PII.

---

# 41. Tracing

Correlation:

```text
request_id
correlation_id
workflow_id
run_id
activity_id
domain aggregate id
AI trace_id
```

باید تا حد امکان در trace/log context حفظ شود.

---

# 42. Audit

Temporal history جای Audit Business نیست.

Audit همچنان در Hamoon Audit subsystem ثبت می‌شود.

Temporal برای:

- orchestration diagnostics
- execution history

است.

---

# 43. Testing

## Workflow Unit Tests

با time-skipping:

- timeout
- long timer
- signal
- cancellation
- retry
- branching

## Activity Tests

- application command invocation
- idempotency
- provider failure behavior
- AI failure behavior

## Integration

- Temporal worker + PostgreSQL
- callback → signal
- domain event → workflow start

## E2E

```text
Referral
→ provider callback
→ result
→ reassessment timer
→ outcome
```

---

# 44. First Workflow to Implement

اولین Workflow:

> **ReferralWorkflow**

چون هم‌زمان این قابلیت‌ها را validate می‌کند:

- domain state machine
- external provider call
- callback
- timeout
- retry
- human follow-up
- event integration
- idempotency

بعد از آن:

```text
DiagnosisReviewWorkflow
ReassessmentWorkflow
OutcomeWorkflow
```

---

# 45. Minimal Referral Workflow v1

```text
Start(referral_id)
↓
Load authoritative referral
↓
Send provider activity
↓
Mark SENT
↓
Wait:
  ProviderAccepted
  ProviderRejected
  Timeout
↓
If Accepted:
  wait InProgress / Completed / Result
↓
On Result:
  trigger reassessment workflow
↓
Complete
```

---

# 46. Human Task Pattern

Temporal workflow نباید خودش user-facing task table باشد.

Pattern:

```text
Workflow
→ CreateWorkItem Activity
→ Work Queue projection
→ User acts via API
→ Domain Command
→ Domain Event
→ Temporal Signal
→ Workflow continues
```

---

# 47. No Hidden Business Logic

Business state rules مثل valid referral transitions داخل Domain باقی می‌مانند.

Workflow فقط ترتیب و زمان‌بندی را کنترل می‌کند.

اگر Workflow بگوید transition انجام شود ولی Domain rule آن را رد کند:

```text
Domain wins
```

---

# 48. Security

Temporal Workerها Service Identity مستقل دارند.

Workerها فقط Activityهای مجاز خودشان را اجرا می‌کنند.

AI Worker مجوز Provider mutation ندارد.

Provider Worker مجوز Accepted State resolution ندارد.

---

# 49. Guardrails

1. Temporal is orchestration, not source of truth.
2. No direct DB write from Workflow code.
3. No network call inside Workflow code.
4. All side effects in Activities.
5. Activities must be idempotent.
6. Sensitive household data should not be stored in Workflow History.
7. NATS remains domain-event backbone.
8. Human Work Queue is not Temporal Task Queue.
9. Business validation remains in Domain.
10. Workflow versioning/replay compatibility is mandatory.

---

# 50. Consequences

## Positive

- durable long-running workflows
- reliable timers
- simpler timeout/retry logic
- natural callback/human wait model
- workflow recovery after restart
- reduced custom scheduling infrastructure
- explicit orchestration

## Trade-offs

- adds Temporal infrastructure
- developers must understand deterministic workflow constraints
- replay/versioning discipline required
- two async mechanisms exist: NATS + Temporal, with clear boundaries required

---

# 51. Acceptance Criteria

ADR-005 implemented when:

- Temporal development environment exists.
- Python worker connects successfully.
- ReferralWorkflow exists.
- workflow ID is business-stable.
- activities use application commands, not direct table writes.
- provider callback can signal workflow.
- timeout creates correct domain follow-up behavior.
- retry policy differentiates technical vs business failure.
- human task pattern works.
- workflow payload contains no unnecessary PII.
- workflow tests cover timer/signal/retry/cancel.
- trace context connects Workflow ↔ Domain Event ↔ API.

---

# 52. Next ADR

> **ADR-006 — AI Provider Strategy & Model Routing**

بعد از آن:

```text
ADR-007 — Observability
ADR-008 — Deployment

→ Product Backlog
→ Sprint 1
```
