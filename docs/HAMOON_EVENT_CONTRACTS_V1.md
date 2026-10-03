# Hamoon — Event Contracts v1

> وضعیت: Technical Event Contract Baseline v1  
> وابسته به:
> - `HAMOON_AI_ARCHITECTURE_BASELINE.md`
> - `HAMOON_TECHNICAL_ARCHITECTURE_V1.md`
> - `HAMOON_DATA_MODEL_V1.md`
> - `HAMOON_PGOR_ENGINE_SPEC_V1.md`
> - `HAMOON_API_CONTRACTS_V1.md`
>
> اصل: **Eventها ستون فقرات حلقه تصمیم، اقدام، پیامد و یادگیری Hamoon هستند؛ Event Log صرفاً لاگ فنی نیست.**

---

# 1. هدف

این سند قرارداد Eventهای Domain و Integration را برای Hamoon تعریف می‌کند تا اجزای زیر بدون coupling مستقیم بتوانند با هم کار کنند:

- Household Data
- Accepted State
- Assessment / PGOR
- Diagnosis
- Prescription
- Intervention
- Provider / Referral
- Provider Result
- Outcome
- Work Queue
- Audit
- AI Decision Trace
- Learning Store
- Monitoring / Evaluation

Eventها باید امکان بازسازی این زنجیره را فراهم کنند:

```text
State Change
→ Assessment
→ PGOR
→ AI Decision
→ Human Decision
→ Action
→ Provider Result
→ Re-assessment
→ Outcome
→ Learning Signal
```

---

# 2. Event Types

Hamoon سه دسته Event دارد:

## 2.1 Domain Event

بیانگر یک واقعیت Business که رخ داده است.

مثال:

```text
HouseholdFactRecorded
PGORSnapshotCalculated
DiagnosisConfirmed
ReferralCompleted
OutcomeRecorded
```

## 2.2 Integration Event

برای خروج Event به یک System دیگر یا دریافت Event از Provider/System خارجی.

مثال:

```text
ReferralSentToProvider
ProviderReferralAccepted
ProviderResultReceived
```

## 2.3 Internal Technical Event

برای زیرساخت داخلی؛ نباید با Domain Event مخلوط شود.

مثال:

```text
OutboxPublished
ProjectionRebuilt
DeadLetterCreated
```

این Eventها معمولاً برای Product/AI Meaning استفاده نمی‌شوند.

---

# 3. Event Envelope

تمام Domain/Integration Eventها باید Envelope مشترک داشته باشند:

```json
{
  "event_id": "evt_01...",
  "event_type": "PGORSnapshotCalculated",
  "event_version": 1,
  "occurred_at": "2026-10-03T10:00:00Z",
  "recorded_at": "2026-10-03T10:00:01Z",

  "aggregate_type": "ASSESSMENT",
  "aggregate_id": "assessment_...",
  "aggregate_version": 8,

  "household_id": "hh_...",
  "actor": {
    "actor_id": "actor_...",
    "actor_type": "HUMAN"
  },

  "correlation_id": "corr_...",
  "causation_id": "evt_previous_...",
  "request_id": "req_...",

  "schema_version": "1",
  "payload": {}
}
```

---

# 4. Event Identity

## event_id

- globally unique
- immutable
- generated once
- same event retry must preserve same event_id when republished from Outbox

---

# 5. occurred_at vs recorded_at

```text
occurred_at = business occurrence time
recorded_at = time Hamoon persisted the event
```

برای Provider callback ممکن است occurred_at متعلق به Provider باشد و recorded_at دیرتر باشد.

---

# 6. Aggregate Version

تمام Eventهای Aggregate باید:

```text
aggregate_version
```

داشته باشند.

هدف:

- ordering
- optimistic concurrency
- projection consistency
- replay diagnostics

---

# 7. Correlation & Causation

## correlation_id

یک Flow کامل را به هم متصل می‌کند.

مثال:

```text
Prescription
→ Referral
→ Provider Result
→ Outcome
```

## causation_id

Event مستقیم قبلی که Event جدید را ایجاد کرده است.

مثال:

```text
ReferralSent
causes
ProviderReferralAccepted
```

---

# 8. PII Rule

Event payload نباید داده حساس غیرضروری حمل کند.

ترجیح:

```text
IDs + canonical codes + minimal values
```

نه:

```text
نام کامل
کد ملی
آدرس
متن آزاد حساس
```

در صورت نیاز به داده حساس، Event باید sensitivity classification و access policy مشخص داشته باشد.

---

# 9. Event Versioning

```text
event_type + event_version
```

Contract identity را می‌سازد.

Backward-compatible field addition:

- version ثابت می‌تواند بماند اگر consumerها tolerate کنند.

Breaking change:

- event_version جدید.

Event قبلی هرگز rewrite نمی‌شود.

---

# 10. Delivery Semantics

V1 فرض:

```text
at-least-once delivery
```

بنابراین Consumerها باید Idempotent باشند.

هر Consumer باید processed_event registry یا equivalent mechanism داشته باشد.

---

# 11. Ordering

Ordering فقط در Scope Aggregate تضمین می‌شود.

مثال:

```text
referral_id
aggregate_version 4
→ version 5
→ version 6
```

Global ordering تضمین نمی‌شود.

---

# 12. Outbox Pattern

تمام Eventهای ناشی از Domain Transaction:

```text
Domain Change
+ Outbox Record
COMMIT
↓
Publisher
↓
Event Bus
```

هدف: جلوگیری از Dual Write Failure.

---

# 13. Inbox Pattern

برای Integrationهای ورودی:

```text
External Message
→ Integration Inbox
→ Idempotency Check
→ Schema Validation
→ Domain Command
→ Domain Event
```

Provider payload مستقیم Domain Table را تغییر نمی‌دهد.

---

# 14. Dead Letter

Event/Message غیرقابل پردازش باید:

```text
DLQ / Dead Letter
```

داشته باشد.

Metadata حداقل:

- event_id
- consumer
- failure_code
- failure_reason
- retry_count
- first_failed_at
- last_failed_at

---

# 15. Retry Policy

Retry فقط برای failureهای transient.

نمونه:

```text
NETWORK_ERROR
DEPENDENCY_TIMEOUT
BROKER_UNAVAILABLE
```

برای Domain validation error retry خودکار بی‌نهایت ممنوع است.

---

# 16. Household Events

## 16.1 HouseholdCreated

```text
event_type: HouseholdCreated
aggregate_type: HOUSEHOLD
```

Payload:

```json
{
  "household_id": "hh_...",
  "case_code": "H-1405-21842",
  "organizational_unit_id": "unit_12",
  "primary_caseworker_id": "actor_..."
}
```

---

## 16.2 HouseholdActivated

```json
{
  "household_id": "hh_...",
  "previous_status": "DRAFT",
  "new_status": "ACTIVE"
}
```

---

## 16.3 HouseholdClosed

Payload:

```json
{
  "household_id": "hh_...",
  "reason_code": "..."
}
```

---

# 17. Member Events

```text
HouseholdMemberAdded
HouseholdMemberUpdatedByFact
HouseholdMemberClosed
```

Identity changes ideally via Fact model, نه update destructive.

---

# 18. Fact Events

## 18.1 HouseholdFactRecorded

```json
{
  "fact_id": "fact_...",
  "household_id": "hh_...",
  "member_id": null,
  "fact_type": "EMPLOYMENT_STATUS",
  "value_type": "CODE",
  "value": "UNEMPLOYED",
  "source_id": "source_...",
  "effective_from": "...",
  "status": "ACCEPTED",
  "version": 1
}
```

---

## 18.2 HouseholdFactCorrected

```json
{
  "previous_fact_id": "fact_old",
  "new_fact_id": "fact_new",
  "fact_type": "EMPLOYMENT_STATUS",
  "reason_code": "SOURCE_CONFLICT",
  "effective_from": "..."
}
```

---

## 18.3 HouseholdFactDisputed

```json
{
  "fact_id": "fact_...",
  "fact_type": "EMPLOYMENT_STATUS",
  "reason_code": "SOURCE_CONFLICT"
}
```

---

## 18.4 HouseholdFactSuperseded

```json
{
  "old_fact_id": "fact_old",
  "new_fact_id": "fact_new",
  "fact_type": "EMPLOYMENT_STATUS"
}
```

---

# 19. Accepted State Events

## 19.1 CurrentAcceptedStateChanged

```json
{
  "household_id": "hh_...",
  "member_id": null,
  "fact_type": "EMPLOYMENT_STATUS",
  "previous_fact_id": "fact_old",
  "new_fact_id": "fact_new",
  "projection_version": 5,
  "reason_code": "HUMAN_RESOLUTION"
}
```

این Event برای:

- projections
- AI feature invalidation
- reassessment prompts
- audit

مهم است.

---

# 20. Evidence Events

```text
EvidenceRecorded
EvidenceLinkedToFact
EvidenceLinkedToObservation
EvidenceLinkedToDecision
```

Event payload باید reference بدهد، نه binary content.

---

# 21. Assessment Events

## 21.1 AssessmentStarted

```json
{
  "assessment_id": "assessment_...",
  "household_id": "hh_...",
  "assessment_type": "BASELINE",
  "definition_version_id": "pgor_def_v1"
}
```

---

## 21.2 IndicatorObservationRecorded

```json
{
  "assessment_id": "assessment_...",
  "observation_id": "obs_...",
  "indicator_definition_id": "p_motivation_willingness",
  "raw_score_0_100": 60,
  "source_id": "source_..."
}
```

---

## 21.3 IndicatorObservationCorrected

```json
{
  "assessment_id": "assessment_...",
  "previous_observation_id": "obs_old",
  "new_observation_id": "obs_new"
}
```

---

## 21.4 AssessmentReadyForCalculation

وقتی required data و conflict policy اجازه می‌دهد.

---

## 21.5 AssessmentCompleted

```json
{
  "assessment_id": "assessment_...",
  "completed_at": "...",
  "pgor_snapshot_id": "pgor_..."
}
```

---

# 22. PGOR Events

## 22.1 PGORCalculationBlocked

```json
{
  "assessment_id": "assessment_...",
  "reason_code": "MISSING_REQUIRED_INDICATOR",
  "blocking_indicator_ids": []
}
```

یا:

```text
UNRESOLVED_REQUIRED_CONFLICT
INVALID_FORMULA_VERSION
```

---

## 22.2 PGORSnapshotCalculated

```json
{
  "snapshot_id": "pgor_...",
  "assessment_id": "assessment_...",
  "household_id": "hh_...",

  "p": 0.68,
  "g": 0.61,
  "o": 0.34,
  "r": 0.53,
  "e": 0.54,

  "bottleneck_variables": ["O"],
  "e_band": "SUPPORTED_EMPOWERMENT",

  "definition_version": "pgor_def_v1",
  "scoring_version": "score_v1",
  "formula_version": "formula_v1",
  "engine_version": "1.0.0",

  "input_fingerprint": "sha256:..."
}
```

---

## 22.3 PGORSnapshotSuperseded

```json
{
  "old_snapshot_id": "pgor_old",
  "new_snapshot_id": "pgor_new",
  "reason_code": "INPUT_CORRECTED"
}
```

---

# 23. Intelligence Events

## 23.1 AIDecisionRequested

```json
{
  "decision_type": "DIAGNOSIS",
  "household_id": "hh_...",
  "feature_package_id": "fp_...",
  "pgor_snapshot_id": "pgor_..."
}
```

این Event internal orchestration است و ممکن است synchronous path هم داشته باشد.

---

## 23.2 AIDecisionGenerated

```json
{
  "ai_decision_id": "aid_...",
  "decision_type": "DIAGNOSIS",
  "household_id": "hh_...",
  "feature_package_id": "fp_...",
  "model_version_id": "modelv_...",
  "prompt_policy_version_id": "promptv_...",
  "output_schema_version": "1",
  "status": "REVIEW_REQUIRED",
  "trace_id": "trace_..."
}
```

---

## 23.3 AIDecisionFailed

```json
{
  "decision_type": "DIAGNOSIS",
  "failure_code": "MODEL_TIMEOUT",
  "retryable": true
}
```

---

# 24. Human Decision Events

## 24.1 HumanDecisionConfirmed

```json
{
  "human_decision_id": "hd_...",
  "ai_decision_id": "aid_...",
  "decision_context": "DIAGNOSIS",
  "action": "CONFIRM",
  "actor_id": "actor_..."
}
```

## 24.2 HumanDecisionModified

```json
{
  "action": "MODIFY",
  "reason_code": "CASEWORKER_JUDGMENT"
}
```

## 24.3 HumanDecisionReplaced

## 24.4 HumanDecisionRejected

## 24.5 HumanDecisionDeferred

این Eventها به Learning Signal تبدیل می‌شوند، نه اینکه AI output حذف شود.

---

# 25. Diagnosis Events

```text
DiagnosisGenerated
DiagnosisConfirmed
DiagnosisModified
DiagnosisReplaced
DiagnosisSuperseded
```

## DiagnosisGenerated

```json
{
  "diagnosis_id": "diag_...",
  "household_id": "hh_...",
  "pgor_snapshot_id": "pgor_...",
  "ai_decision_id": "aid_...",
  "status": "UNDER_REVIEW"
}
```

## DiagnosisConfirmed

```json
{
  "diagnosis_id": "diag_...",
  "accepted_by": "actor_...",
  "accepted_at": "..."
}
```

---

# 26. Prescription Events

```text
PrescriptionGenerated
PrescriptionApproved
PrescriptionModified
PrescriptionReplaced
PrescriptionDeferred
PrescriptionSuperseded
```

## PrescriptionApproved

Payload حداقل:

```json
{
  "prescription_id": "rx_...",
  "diagnosis_id": "diag_...",
  "accepted_item_ids": [],
  "accepted_by": "actor_..."
}
```

---

# 27. Intervention Events

```text
InterventionPlanned
InterventionActivated
InterventionReadyForReferral
InterventionCompleted
InterventionCancelled
```

---

# 28. Provider Registry Events

```text
ProviderRegistered
ProviderServiceActivated
ProviderServiceDeactivated
ProviderCapacityUpdated
```

Capacity Event:

```json
{
  "provider_service_id": "svc_...",
  "capacity_status": "AVAILABLE",
  "available_slots": 12,
  "valid_at": "..."
}
```

---

# 29. Matching Events

## 29.1 ProviderMatchGenerated

```json
{
  "ai_decision_id": "aid_match_...",
  "intervention_id": "int_...",
  "candidate_count": 3,
  "candidate_provider_ids": ["p1", "p2", "p3"]
}
```

Event نباید concept «winner» داشته باشد.

---

## 29.2 ProviderSelectedByHuman

```json
{
  "intervention_id": "int_...",
  "provider_id": "p2",
  "provider_service_id": "svc_2",
  "human_decision_id": "hd_..."
}
```

---

# 30. Referral Events

## 30.1 ReferralCreated

```json
{
  "referral_id": "ref_...",
  "intervention_id": "int_...",
  "provider_id": "p2",
  "provider_service_id": "svc_2",
  "status": "READY"
}
```

---

## 30.2 ReferralSent

```json
{
  "referral_id": "ref_...",
  "provider_id": "p2",
  "sent_at": "...",
  "shared_data_item_ids": []
}
```

---

## 30.3 ReferralAccepted

## 30.4 ReferralWaitingCapacity

## 30.5 ReferralNeedsInformation

## 30.6 ReferralInProgress

## 30.7 ReferralRejected

## 30.8 ReferralNoResponse

## 30.9 ReferralCompleted

## 30.10 ReferralCancelled

هر Event باید:

```text
from_status
to_status
occurred_at
actor/provider
reason_code?
```

داشته باشد.

---

# 31. Provider Integration Events

## 31.1 ReferralDispatchedToProvider

Integration Event:

```json
{
  "referral_id": "ref_...",
  "provider_id": "p2",
  "provider_endpoint_key": "default",
  "contract_version": "1"
}
```

## 31.2 ProviderCallbackReceived

فقط Processing/Audit Event؛ Domain status change بعداً Event مربوط خودش را تولید می‌کند.

---

# 32. Provider Result Events

## 32.1 ProviderResultReceived

```json
{
  "provider_result_id": "pr_...",
  "referral_id": "ref_...",
  "provider_id": "p2",
  "result_type": "SERVICE_COMPLETION",
  "result_status": "COMPLETED",
  "submitted_at": "..."
}
```

## 32.2 ProviderResultEvidenceAdded

---

# 33. Re-assessment Events

```text
ReassessmentStarted
ReassessmentCompleted
```

ReassessmentCompleted باید Snapshot جدید را reference دهد.

---

# 34. Outcome Events

## 34.1 OutcomePrepared

```json
{
  "outcome_id": "out_...",
  "intervention_id": "int_...",
  "pre_pgor_snapshot_id": "pgor_before",
  "post_pgor_snapshot_id": "pgor_after",
  "provider_result_id": "pr_..."
}
```

## 34.2 OutcomeConfirmed

```json
{
  "outcome_id": "out_...",
  "classification": "PROGRESS",
  "p_delta": 0.02,
  "g_delta": 0.01,
  "o_delta": 0.12,
  "r_delta": 0.00,
  "e_delta": 0.05,
  "confirmed_by": "actor_..."
}
```

## 34.3 OutcomeModified

## 34.4 OutcomeNeedsMoreTime

## 34.5 OutcomeNeedsMoreData

---

# 35. Learning Events

## 35.1 LearningSignalCreated

```json
{
  "learning_signal_id": "ls_...",
  "household_id": "hh_...",
  "signal_type": "DIAGNOSIS_MODIFIED",
  "ai_decision_id": "aid_...",
  "human_decision_id": "hd_...",
  "outcome_id": null,
  "quality_status": "RAW"
}
```

LearningSignalCreated نباید Production Model را مستقیماً تغییر دهد.

---

# 36. Dataset / Evaluation Events

```text
DatasetVersionCreated
DatasetVersionApproved

EvaluationRunStarted
EvaluationRunCompleted
EvaluationRunFailed

ModelCandidateCreated
ModelVersionApproved
ModelVersionDeployed
ModelVersionRetired
```

---

# 37. Prompt / Policy Events

```text
PromptPolicyVersionCreated
PromptPolicyVersionApproved
PromptPolicyVersionActivated
PromptPolicyVersionRetired
```

Prompt change باید event/audit trace داشته باشد.

---

# 38. Formula / PGOR Definition Events

```text
PGORDefinitionVersionCreated
PGORDefinitionVersionApproved
PGORDefinitionVersionActivated
PGORDefinitionVersionRetired

PGORFormulaVersionCreated
PGORFormulaVersionApproved
PGORFormulaVersionActivated
PGORFormulaVersionRetired

ScoringScaleVersionCreated
ScoringScaleVersionActivated
```

---

# 39. Formula Calibration Events

Calibration جدا از PGOR Calculation است.

```text
CalibrationRunStarted
CalibrationRunCompleted
CalibrationCandidateProduced
CalibrationCandidateApproved
```

فقط Approval می‌تواند به Formula Version جدید منتهی شود.

---

# 40. Work Queue Events

Work Queue بهتر است Projection از Domain Eventها باشد.

نمونه Trigger:

```text
ReferralNoResponse
→ create follow-up work item

PGORCalculationBlocked
→ create data completion task

ProviderResultReceived
→ create outcome review task

DiagnosisGenerated
→ create diagnosis review task
```

Domain Event Source باقی می‌ماند.

---

# 41. Notification Events

Notification concern جدا:

```text
NotificationRequested
NotificationSent
NotificationFailed
```

Domain Service مستقیماً SMS/Email/UI Push نمی‌فرستد.

---

# 42. Projection Events

برای rebuild/maintenance:

```text
ProjectionRebuildRequested
ProjectionRebuilt
ProjectionRebuildFailed
```

این Technical Eventها Learning Signal نیستند.

---

# 43. Audit Relationship

هر Domain Command حساس:

```text
Command
→ Domain Change
→ Domain Event
→ Audit Entry
```

Audit و Event دو مفهوم متفاوت‌اند.

Event:
- چه اتفاق Business افتاد؟

Audit:
- چه کسی، از کجا، با چه دسترسی و درخواست این کار را انجام داد؟

---

# 44. Event Consumers

## Household Projection Consumer
مصرف:
- Fact
- Accepted State
- Assessment
- Referral
- Outcome

تولید:
- household workspace projections
- timeline

## Work Queue Consumer
مصرف:
- review-needed events
- due/timeout events

## AI Feature Consumer
مصرف:
- CurrentAcceptedStateChanged
- PGORSnapshotCalculated
- OutcomeRecorded

تولید:
- feature invalidation/rebuild

## Learning Consumer
مصرف:
- HumanDecision*
- Outcome*
- DataConflictResolved
- Provider*
- AIDecision*

تولید:
- LearningSignalCreated

## Admin Analytics Consumer
مصرف:
- PGOR
- Referral
- Outcome
- AI/Human review

---

# 45. Consumer Idempotency

هر Consumer:

```text
consumer_name + event_id
```

را unique پردازش می‌کند.

Duplicate Event نباید duplicate projection/task/learning signal ایجاد کند.

---

# 46. Event Replay

Replay فقط برای:

- rebuild projection
- recover consumer state
- offline analytics
- test

است.

Replay نباید External Side Effect تکراری ایجاد کند.

مثلاً:

```text
ReferralSent replay
```

نباید دوباره Provider را call کند مگر workflow مخصوص replay-safe dispatch داشته باشیم.

---

# 47. Side-effect Boundary

Event Consumerها به دو نوع تقسیم شوند:

## Pure Projection Consumer
Replay-safe.

## External Side-effect Consumer
نیازمند delivery ledger/idempotency.

مثال:

```text
Provider Dispatch
Notification
External Webhook
```

---

# 48. Provider Webhook Delivery Ledger

برای outbound Provider events:

```text
WEBHOOK_DELIVERY
- id
- provider_id
- event_id
- endpoint_key
- attempt
- status
- response_code
- requested_at
- completed_at
- next_retry_at
```

---

# 49. Event Schema Registry

Event schemas باید version-controlled باشند.

ساختار پیشنهادی repo:

```text
contracts/events/
  household/
  facts/
  assessment/
  pgor/
  diagnosis/
  prescription/
  referral/
  outcome/
  ai/
  learning/
```

در مرحله Implementation، هر Event JSON Schema رسمی خواهد داشت.

---

# 50. Naming Convention

Past tense.

درست:

```text
DiagnosisGenerated
ReferralAccepted
OutcomeRecorded
```

نادرست:

```text
GenerateDiagnosis
AcceptReferral
```

Command و Event نباید نام یکسان داشته باشند.

---

# 51. Event Granularity

Event باید یک Business Fact معنی‌دار باشد.

خیلی ریز:

```text
ButtonClicked
FieldChanged
ModalOpened
```

Domain Event نیستند.

خیلی درشت:

```text
HouseholdUpdated
```

معنای کافی ندارد.

ترجیح:

```text
HouseholdFactCorrected
DiagnosisModified
ReferralRejected
```

---

# 52. Free Text Policy

Event payload باید تا حد ممکن code/ID محور باشد.

Free text فقط در صورت نیاز:

```text
reason_text
summary
```

و باید sensitivity handling داشته باشد.

---

# 53. Event Security Classification

هر Event Type باید classification داشته باشد:

```text
INTERNAL
CONFIDENTIAL
SENSITIVE_PERSONAL
HIGHLY_SENSITIVE
```

Provider-facing Eventها contract جدا و minimized دارند.

---

# 54. Provider-facing Events

Provider هیچ Event داخلی Hamoon را مستقیم subscribe نمی‌کند.

Hamoon Domain Event:

```text
ReferralSent
```

به Integration Contract تبدیل می‌شود:

```text
ReferralDispatchedToProvider v1
```

Internal schema و external schema جدا می‌مانند.

---

# 55. Event Retention

Retention باید بر اساس Event class تعریف شود.

حداقل:

- Domain decision history: long-term/audit aligned
- AI decision trace: long-term per governance
- Integration delivery logs: operational retention
- technical logs: shorter retention

مدت دقیق در Security/Data Governance ADR تعیین می‌شود.

---

# 56. Clock / Time Safety

برای external events:

```text
occurred_at_source
received_at_hamoon
```

هر دو قابل نگهداری باشند تا clock skew قابل تشخیص باشد.

---

# 57. Event Validation

قبل از publish:

- schema valid
- required IDs valid
- aggregate version present
- event type/version supported
- payload classification known

Invalid event نباید منتشر شود.

---

# 58. Event Observability

Metrics:

```text
events_published_total
events_publish_failed_total
events_consumed_total
events_consume_failed_total
event_retry_total
dead_letter_total
consumer_lag
outbox_pending_count
inbox_duplicate_count
```

Dimensions:

- event_type
- event_version
- consumer
- producer

بدون PII.

---

# 59. Traceability Query

سیستم باید بتواند برای یک Decision Trace پاسخ دهد:

```text
چه Stateای مبنا بود؟
کدام PGOR Snapshot؟
کدام AI Model/Prompt؟
AI چه گفت؟
مددکار چه تصمیمی گرفت؟
چه Referral/Intervention انجام شد؟
Provider چه نتیجه‌ای داد؟
Outcome چه شد؟
چه Learning Signal ایجاد شد؟
```

Event Contracts باید این Query را ممکن کنند.

---

# 60. Core End-to-End Event Chain

```text
HouseholdFactRecorded
↓
CurrentAcceptedStateChanged
↓
AssessmentStarted
↓
IndicatorObservationRecorded
↓
PGORSnapshotCalculated
↓
AIDecisionGenerated
↓
DiagnosisGenerated
↓
DiagnosisConfirmed / Modified / Replaced
↓
PrescriptionGenerated
↓
PrescriptionApproved / Modified
↓
InterventionActivated
↓
ProviderMatchGenerated
↓
ProviderSelectedByHuman
↓
ReferralCreated
↓
ReferralSent
↓
ReferralAccepted
↓
ReferralInProgress
↓
ReferralCompleted
↓
ProviderResultReceived
↓
ReassessmentStarted
↓
PGORSnapshotCalculated
↓
OutcomePrepared
↓
OutcomeConfirmed
↓
LearningSignalCreated
```

این زنجیره هسته «ماشین توانمندسازی هوشمند» است.

---

# 61. Minimum V1 Event Set

برای اولین Implementation، حداقل:

```text
HouseholdCreated

HouseholdFactRecorded
HouseholdFactCorrected
HouseholdFactDisputed
CurrentAcceptedStateChanged

AssessmentStarted
IndicatorObservationRecorded
AssessmentReadyForCalculation
PGORCalculationBlocked
PGORSnapshotCalculated

AIDecisionGenerated

DiagnosisGenerated
DiagnosisConfirmed
DiagnosisModified
DiagnosisReplaced

PrescriptionGenerated
PrescriptionApproved
PrescriptionModified

InterventionActivated

ProviderMatchGenerated
ProviderSelectedByHuman

ReferralCreated
ReferralSent
ReferralAccepted
ReferralRejected
ReferralInProgress
ReferralCompleted
ReferralNoResponse

ProviderResultReceived

ReassessmentStarted
ReassessmentCompleted

OutcomePrepared
OutcomeConfirmed
OutcomeModified

LearningSignalCreated
```

---

# 62. Definition of Done — Event Contracts v1

Event layer آماده Implementation است وقتی:

- Envelope واحد تعریف شده باشد.
- event_id/correlation_id/causation_id استاندارد باشند.
- Aggregate Version در Eventهای لازم باشد.
- Event naming past-tense باشد.
- At-least-once semantics پذیرفته شده باشد.
- Consumer idempotency تعریف شده باشد.
- Outbox/Inbox در معماری باشد.
- Domain Event و Audit تفکیک شده باشند.
- Provider-facing contract از internal events جدا باشد.
- AI Decision/Human Decision/Outcome/Learning chain قابل trace باشد.
- Replay برای projectionها safe باشد.
- External side effectها delivery ledger داشته باشند.
- Core V1 event schemas قابل تبدیل به JSON Schema باشند.

---

# 63. مرحله بعد

پس از Event Contracts:

```text
Security / RBAC Matrix
→ Stack ADRs
→ Product Backlog
→ Sprint 1
```

اولین سند بعدی:

> **HAMOON_SECURITY_RBAC_V1.md**
