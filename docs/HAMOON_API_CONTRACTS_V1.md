# Hamoon — API Contracts v1

> وضعیت: Technical API Contract Baseline v1  
> وابسته به:
> - `HAMOON_AI_ARCHITECTURE_BASELINE.md`
> - `HAMOON_TECHNICAL_ARCHITECTURE_V1.md`
> - `HAMOON_DATA_MODEL_V1.md`
> - `HAMOON_PGOR_ENGINE_SPEC_V1.md`
>
> اصل: **API هامون باید حلقه تصمیم و یادگیری را پشتیبانی کند؛ نه صرفاً CRUD روی جدول‌ها.**

---

# 1. هدف

این سند قرارداد API منطقی V1 را برای کل مسیر عملیاتی Hamoon تعریف می‌کند:

```text
Household
→ Data / Accepted State
→ Assessment
→ PGOR
→ Diagnosis
→ Prescription
→ Intervention
→ Provider Matching
→ Referral
→ Provider Result
→ Re-assessment
→ Outcome
→ Learning Signal
```

این سند هنوز OpenAPI نهایی نیست؛ مبنای تولید OpenAPI/JSON Schema و Implementation است.

---

# 2. API Principles

## 2.1 Domain-oriented

Endpointها حول Aggregate و Commandهای واقعی محصول طراحی می‌شوند.

مثال خوب:

```text
POST /diagnoses/{id}/confirm
POST /referrals/{id}/transition
POST /assessments/{id}/calculate-pgor
```

نه:

```text
PATCH /tables/diagnosis_rows/...
```

---

## 2.2 AI Output و Human Decision جدا هستند

```text
AI Proposal
≠
Human Accepted Decision
```

API باید هر دو را مستقل ثبت کند.

---

## 2.3 Immutable history

API نباید برای Factهای تاریخی update-in-place ارائه دهد.

اصلاح داده:

```text
POST correction
→ new version
→ accepted-state transition
```

---

## 2.4 Optimistic Concurrency

Commandهای حساس باید:

```text
expected_version
```

یا معادل ETag/If-Match داشته باشند.

موارد اجباری:

- correction
- accepted-state resolution
- diagnosis review
- prescription review
- referral transition
- outcome confirmation

---

## 2.5 Idempotency

برای Commandهای خارجی/حساس:

Header:

```text
Idempotency-Key: <uuid/string>
```

همراه با:

```text
request_hash
actor
resource
result_reference
```

Retry نباید عملیات تکراری تولید کند.

---

# 3. Base Path

```text
/api/v1
```

مثال:

```text
GET /api/v1/households/{household_id}
```

---

# 4. Authentication

V1 فرض می‌کند Authentication توسط Organizational Identity/SSO انجام می‌شود.

Header:

```text
Authorization: Bearer <access_token>
```

Context استخراج‌شده:

```text
actor_id
organization_id
roles[]
permissions[]
```

Role از Client ارسال نمی‌شود.

---

# 5. Common Request Headers

```text
Authorization
X-Request-Id
X-Correlation-Id
Idempotency-Key        // for commands where required
If-Match / expected_version
```

Provider Integration علاوه بر Authentication باید Integration Identity مستقل داشته باشد.

---

# 6. Common Response Envelope

Success:

```json
{
  "data": {},
  "meta": {
    "request_id": "req_...",
    "version": 3
  }
}
```

Collection:

```json
{
  "data": [],
  "meta": {
    "request_id": "req_...",
    "next_cursor": null
  }
}
```

---

# 7. Error Envelope

```json
{
  "error": {
    "code": "UNRESOLVED_REQUIRED_CONFLICT",
    "message": "Official PGOR calculation is blocked.",
    "details": {},
    "request_id": "req_..."
  }
}
```

Error code باید stable و machine-readable باشد.

---

# 8. HTTP Semantics

```text
200 OK
201 Created
202 Accepted
204 No Content

400 Validation Error
401 Unauthenticated
403 Forbidden
404 Not Found
409 Conflict / Version Conflict
422 Domain Rule Violation
429 Rate Limited

500 Internal Error
503 Dependency Unavailable
```

---

# 9. Pagination

Cursor-based:

```text
?limit=50&cursor=...
```

برای Timeline، Cases، Referrals و Events.

Offset pagination برای داده operational اصلی ترجیح داده نمی‌شود.

---

# 10. Date / Time

همه timestampها:

```text
ISO-8601
timezone-aware
UTC in API payload
```

نمایش تاریخ شمسی فقط concern UI است.

---

# 11. Household APIs

## 11.1 Create Household

```text
POST /households
```

Request:

```json
{
  "case_code": "H-1405-21842",
  "organizational_unit_id": "unit_12",
  "primary_caseworker_id": "actor_123"
}
```

Response:

```json
{
  "data": {
    "id": "hh_...",
    "case_code": "H-1405-21842",
    "lifecycle_status": "DRAFT",
    "version": 1
  }
}
```

---

## 11.2 Get Household Workspace Summary

```text
GET /households/{household_id}
```

Response شامل summary عملیاتی:

```json
{
  "data": {
    "household": {},
    "current_pgor": {},
    "accepted_diagnosis": {},
    "active_prescription": {},
    "active_interventions": [],
    "active_referrals": [],
    "next_actions": [],
    "latest_insight": {}
  }
}
```

این Endpoint Projection است، Source of Truth جداگانه باقی می‌ماند.

---

## 11.3 My Cases

```text
GET /households
```

Filters:

```text
caseworker_id=me
status=ACTIVE
bottleneck=O
needs_attention=true
search=...
cursor=...
```

---

# 12. Household Member APIs

```text
GET  /households/{id}/members
POST /households/{id}/members
POST /households/{id}/members/{member_id}/close
```

Member facts همچنان از Fact API عبور می‌کنند.

---

# 13. Fact APIs

## 13.1 List Facts

```text
GET /households/{id}/facts
```

Filters:

```text
fact_type
member_id
status
effective_at
source_type
```

---

## 13.2 Record New Fact

```text
POST /households/{id}/facts
```

Request:

```json
{
  "member_id": null,
  "fact_type": "EMPLOYMENT_STATUS",
  "value": "UNEMPLOYED",
  "value_type": "CODE",
  "source_id": "source_household",
  "source_detail": "مصاحبه خانوار",
  "effective_from": "2026-10-03T00:00:00Z",
  "evidence_ids": []
}
```

---

## 13.3 Correct Fact

```text
POST /households/{id}/facts/{fact_id}/corrections
```

Request:

```json
{
  "expected_version": 2,
  "new_value": "UNEMPLOYED",
  "effective_from": "2026-09-25T00:00:00Z",
  "source_id": "source_external_insurance",
  "correction_reason_code": "CONFLICT_WITH_OFFICIAL_SOURCE",
  "reason_text": "..."
}
```

Result:

- old fact preserved
- new fact created
- accepted-state projection updated if approved by policy
- Audit/Event produced

---

## 13.4 Dispute Fact

```text
POST /households/{id}/facts/{fact_id}/dispute
```

Request:

```json
{
  "expected_version": 2,
  "reason_code": "SOURCE_CONFLICT",
  "reason_text": "...",
  "evidence_ids": []
}
```

---

# 14. Current Accepted State APIs

## 14.1 Get State

```text
GET /households/{id}/accepted-state
```

---

## 14.2 Resolve Accepted Value

```text
POST /households/{id}/accepted-state/{fact_type}/resolve
```

Request:

```json
{
  "accepted_fact_id": "fact_...",
  "expected_projection_version": 4,
  "reason_code": "HUMAN_RESOLUTION",
  "reason_text": "..."
}
```

AI حق فراخوانی خودکار این Command بدون Actor مجاز را ندارد.

---

# 15. Data Source / Evidence APIs

```text
GET  /data-sources
POST /households/{id}/evidence
GET  /households/{id}/evidence
GET  /evidence/{evidence_id}
```

Upload Binary در Object Storage contract جدا خواهد داشت؛ API اصلی metadata/reference را ثبت می‌کند.

---

# 16. PGOR Definition APIs

برای UI و Engine Configuration:

```text
GET /pgor/definitions/active
GET /pgor/definitions/{version_id}
GET /pgor/scoring-scales/{version_id}
GET /pgor/formulas/{version_id}
```

Frontend نباید Indicator list یا score mapping را مستقل hard-code کند.

---

# 17. Assessment APIs

## 17.1 Start Assessment

```text
POST /households/{id}/assessments
```

Request:

```json
{
  "assessment_type": "BASELINE",
  "definition_version_id": "pgor_def_v1",
  "reason": "INITIAL_ASSESSMENT"
}
```

---

## 17.2 Get Assessment

```text
GET /assessments/{assessment_id}
```

---

## 17.3 Record Indicator Observation

```text
POST /assessments/{assessment_id}/observations
```

Request:

```json
{
  "indicator_definition_id": "p_motivation_willingness",
  "raw_score_0_100": 60,
  "source_id": "source_household",
  "source_detail": "مصاحبه خانوار",
  "effective_at": "2026-10-03T00:00:00Z",
  "evidence_ids": []
}
```

---

## 17.4 Replace / Correct Observation

```text
POST /assessments/{assessment_id}/observations/{id}/corrections
```

همان اصل immutable/versioned.

---

# 18. Calculate PGOR

```text
POST /assessments/{assessment_id}/calculate-pgor
```

Request:

```json
{
  "expected_assessment_version": 8,
  "formula_version_id": "formula_v1",
  "mode": "OFFICIAL"
}
```

Mode:

```text
PREVIEW
OFFICIAL
```

Response:

```json
{
  "data": {
    "snapshot_id": "pgor_...",
    "status": "OFFICIAL",
    "p": 0.68,
    "g": 0.61,
    "o": 0.34,
    "r": 0.53,
    "e": 0.54,
    "bottleneck_variables": ["O"],
    "e_band": "SUPPORTED_EMPOWERMENT",
    "completeness_ratio": 1.0,
    "data_quality_flags": [],
    "formula_version": "formula_v1",
    "definition_version": "pgor_def_v1",
    "engine_version": "1.0.0"
  }
}
```

Client هیچ‌وقت P/G/O/R/E را به‌عنوان authoritative input ارسال نمی‌کند.

---

# 19. PGOR Snapshot APIs

```text
GET /households/{id}/pgor-snapshots
GET /pgor-snapshots/{snapshot_id}
GET /pgor-snapshots/{snapshot_id}/trace
```

Trace شامل Input Observationها و Versionهاست.

---

# 20. Diagnosis APIs

## 20.1 Generate Diagnosis

```text
POST /households/{id}/diagnoses/generate
```

Request:

```json
{
  "pgor_snapshot_id": "pgor_...",
  "expected_household_state_version": 24
}
```

Response:

```json
{
  "data": {
    "diagnosis_id": "diag_...",
    "ai_decision_id": "aid_...",
    "status": "UNDER_REVIEW"
  }
}
```

---

## 20.2 Get Diagnosis

```text
GET /diagnoses/{id}
```

Response باید Machine Proposal و Human Accepted State را جدا نشان دهد.

---

## 20.3 Confirm Diagnosis

```text
POST /diagnoses/{id}/confirm
```

Request:

```json
{
  "expected_version": 2,
  "reason_text": null
}
```

---

## 20.4 Modify Diagnosis

```text
POST /diagnoses/{id}/modify
```

Request:

```json
{
  "expected_version": 2,
  "accepted_items": [],
  "modified_items": [],
  "reason_code": "CASEWORKER_JUDGMENT",
  "reason_text": "..."
}
```

---

## 20.5 Replace Diagnosis

```text
POST /diagnoses/{id}/replace
```

Machine diagnosis preserved.

---

# 21. Prescription APIs

## 21.1 Generate Prescription

```text
POST /households/{id}/prescriptions/generate
```

Request:

```json
{
  "diagnosis_id": "diag_...",
  "pgor_snapshot_id": "pgor_..."
}
```

---

## 21.2 Review Commands

```text
POST /prescriptions/{id}/approve
POST /prescriptions/{id}/modify
POST /prescriptions/{id}/replace
POST /prescriptions/{id}/defer
```

Human modifications باید Structured باشند.

---

# 22. Intervention APIs

```text
GET  /households/{id}/interventions
POST /prescriptions/{id}/items/{item_id}/activate
GET  /interventions/{id}
POST /interventions/{id}/cancel
```

Activation فقط از Prescription Item پذیرفته‌شده مجاز است.

---

# 23. Provider Registry APIs

Internal/Admin:

```text
GET /providers
GET /providers/{id}
GET /providers/{id}/services
GET /provider-services/{id}
```

Filter:

```text
service_type
coverage
capacity
active
```

---

# 24. Provider Matching API

```text
POST /interventions/{id}/match-providers
```

Request:

```json
{
  "service_type": "EMPLOYMENT_MARKET",
  "household_context_version": 24
}
```

Response:

```json
{
  "data": {
    "ai_decision_id": "aid_match_...",
    "candidates": [
      {
        "provider_id": "provider_1",
        "service_id": "service_1",
        "eligibility": "ELIGIBLE",
        "capacity_status": "AVAILABLE",
        "reasons": []
      }
    ]
  }
}
```

API نباید یک Provider را به‌عنوان «winner» قطعی برگرداند.

---

# 25. Referral APIs

## 25.1 Create Referral

```text
POST /interventions/{id}/referrals
```

Request:

```json
{
  "provider_id": "provider_1",
  "provider_service_id": "service_1",
  "priority": "NORMAL",
  "response_due_at": "2026-10-06T12:00:00Z",
  "shared_data_items": [
    {
      "source_fact_id": "fact_...",
      "purpose": "SERVICE_ELIGIBILITY"
    }
  ]
}
```

Response status اولیه:

```text
READY
```

---

## 25.2 Send Referral

```text
POST /referrals/{id}/send
```

---

## 25.3 Transition Referral

```text
POST /referrals/{id}/transition
```

Request:

```json
{
  "expected_version": 4,
  "to_status": "IN_PROGRESS",
  "reason_code": null,
  "occurred_at": "2026-10-03T10:00:00Z"
}
```

State Machine validation الزامی است.

---

## 25.4 Get Referral

```text
GET /referrals/{id}
```

---

## 25.5 Referral Timeline

```text
GET /referrals/{id}/events
```

---

# 26. Provider Integration API

Provider تنها به Scope خودش دسترسی دارد.

## 26.1 Receive Referral Package

Outbound Hamoon contract:

```text
POST {provider_endpoint}/referrals
```

Canonical payload شامل حداقل:

```json
{
  "hamoon_referral_id": "ref_...",
  "service_code": "EMPLOYMENT_MARKET",
  "priority": "NORMAL",
  "response_due_at": "...",
  "subject_reference": "opaque_ref",
  "authorized_data": {}
}
```

کل Household record ارسال نمی‌شود.

---

## 26.2 Provider Status Callback

Inbound:

```text
POST /provider-integrations/referrals/{external_referral_id}/status
```

Request:

```json
{
  "external_event_id": "evt_provider_123",
  "status": "ACCEPTED",
  "occurred_at": "...",
  "reason_code": null
}
```

Idempotency:

```text
(provider, external_event_id) unique
```

---

# 27. Provider Result APIs

## 27.1 Submit Result — Provider

```text
POST /provider-integrations/referrals/{external_referral_id}/results
```

Request:

```json
{
  "external_result_id": "result_123",
  "result_status": "COMPLETED",
  "result_type": "SERVICE_COMPLETION",
  "result_summary": "...",
  "service_started_at": "...",
  "service_completed_at": "...",
  "evidence": []
}
```

Provider Result به‌تنهایی Hamoon Outcome ایجاد نمی‌کند.

---

## 27.2 Caseworker View

```text
GET /referrals/{id}/provider-results
GET /provider-results/{id}
```

---

# 28. Re-assessment APIs

```text
POST /households/{id}/reassessments
GET  /reassessments/{id}
```

Internally همان Assessment Aggregate با type:

```text
REASSESSMENT
OUTCOME_REASSESSMENT
```

است.

---

# 29. Outcome APIs

## 29.1 Calculate / Prepare Outcome

```text
POST /interventions/{id}/outcomes/prepare
```

Request:

```json
{
  "pre_assessment_id": "a1",
  "post_assessment_id": "a2",
  "provider_result_id": "pr_..."
}
```

---

## 29.2 Review Outcome

```text
POST /outcomes/{id}/confirm
POST /outcomes/{id}/modify
POST /outcomes/{id}/needs-more-time
POST /outcomes/{id}/needs-more-data
```

Outcome language نباید بدون method معتبر causal claim تولید کند.

---

## 29.3 Get Outcome

```text
GET /outcomes/{id}
```

Response:

```json
{
  "data": {
    "classification": "PROGRESS",
    "pre": {
      "e": 0.54,
      "o": 0.34
    },
    "post": {
      "e": 0.59,
      "o": 0.46
    },
    "delta": {
      "e": 0.05,
      "o": 0.12
    },
    "provider_result": {},
    "observed_change_summary": "..."
  }
}
```

---

# 30. AI Decision APIs

## 30.1 Get Decision Trace

```text
GET /ai/decisions/{id}
GET /ai/decisions/{id}/trace
```

Trace باید شامل:

- feature package
- state version
- PGOR snapshot
- model version
- prompt/policy version
- evidence refs
- structured output
- human decision
- downstream action/outcome when available

باشد.

---

# 31. Human Decision API

Generic endpoint فقط برای Engineهایی که Domain-specific command ندارند:

```text
POST /ai/decisions/{id}/human-review
```

Request:

```json
{
  "action": "MODIFY",
  "reason_code": "CASEWORKER_JUDGMENT",
  "reason_text": "...",
  "modified_payload": {}
}
```

برای Diagnosis/Prescription ترجیح با Endpointهای Domain-specific است.

---

# 32. Learning Signal APIs

Learning Signal معمولاً server-generated است.

Internal/Admin:

```text
GET /learning/signals
GET /learning/signals/{id}
```

Client عملیاتی نباید Arbitrary Learning Signal بسازد مگر API داخلی کنترل‌شده.

---

# 33. Model / Prompt Registry APIs

Admin/Internal:

```text
GET /ai/models
GET /ai/models/{id}/versions
GET /ai/prompt-policies
GET /ai/prompt-policies/{id}/versions
```

Mutation این Registryها در V1 بهتر است از Internal Admin/Deployment process انجام شود، نه Caseworker API.

---

# 34. Evaluation APIs

Internal:

```text
POST /ai/evaluations
GET  /ai/evaluations/{id}
GET  /ai/evaluations/{id}/metrics
```

Production Model promotion API جداگانه و نیازمند approval خواهد بود.

---

# 35. Timeline API

```text
GET /households/{id}/timeline
```

Filters:

```text
event_type
from
to
cursor
```

Timeline Projection است و نباید Source Entity را جایگزین کند.

---

# 36. Cartable / Work Queue API

UI کارتابل نیازمند Projection اختصاصی است:

```text
GET /work-queue
```

Filters:

```text
owner=me
due=today
overdue=true
type=REFERRAL_FOLLOWUP
cursor=...
```

Response item:

```json
{
  "id": "task_...",
  "household_id": "hh_...",
  "action_type": "REFERRAL_FOLLOWUP",
  "due_at": "...",
  "priority": "HIGH",
  "reason": "...",
  "source_entity_type": "REFERRAL",
  "source_entity_id": "ref_..."
}
```

---

# 37. Admin Command Center APIs

Admin UI نباید مستقیماً raw OLTP aggregateها را query کند.

Projection APIs:

```text
GET /admin/empowerment-overview
GET /admin/pgor-distribution
GET /admin/bottlenecks
GET /admin/intervention-outcomes
GET /admin/operational-health
GET /admin/machine-health
GET /admin/data-health
```

Filters:

```text
organization_level
province
region
unit
caseworker
from
to
```

---

# 38. Machine Health API

```text
GET /admin/machine-health
```

Metrics نمونه:

```text
diagnosis_confirmed_count
diagnosis_modified_count
diagnosis_replaced_count
prescription_modified_count
model_review_required_count
schema_failure_count
inference_failure_count
```

این Metrics برای Monitoring/Learning هستند، نه leaderboard مددکار.

---

# 39. Search

Household search:

```text
GET /households/search?q=...
```

Search authorization-aware است.

PII matching باید طبق Security Policy محدود باشد.

---

# 40. Bulk / Batch

برای Data Integration، Bulk endpoint مجاز است؛ برای UI عملیاتی نه.

```text
POST /integrations/{source}/facts:batch
```

هر item:

- external_event_id
- external_record_id
- canonical fact
- effective_at
- source provenance

را حمل می‌کند.

Partial success باید per-item result داشته باشد.

---

# 41. Integration Inbox Contract

Inbound message ابتدا:

```text
Integration Inbox
→ Validate
→ Map
→ Domain Command
```

External integration مستقیم table write ندارد.

---

# 42. External Schema Versioning

هر Provider/System payload باید:

```text
schema_version
```

داشته باشد یا از endpoint version infer شود.

Breaking contract بدون Version جدید مجاز نیست.

---

# 43. Request Correlation

تمام flowهای چندمرحله‌ای:

```text
correlation_id
```

دارند.

مثال:

```text
Prescription
→ Referral
→ Provider Event
→ Provider Result
→ Outcome
```

برای Trace باید قابل اتصال باشند.

---

# 44. Command Result

Commandهایی که downstream async work دارند:

```text
202 Accepted
```

Response:

```json
{
  "data": {
    "operation_id": "op_...",
    "status": "PENDING"
  }
}
```

مانند بعضی AI inferenceها یا Integrationها.

---

# 45. AI Inference Semantics

Domain API باید client را به Model Provider وابسته نکند.

Client می‌گوید:

```text
Generate Diagnosis
```

نه:

```text
Call model X with prompt Y
```

Model routing concern Intelligence Platform است.

---

# 46. Structured AI Output

هر AI endpoint باید JSON Schema معتبر داشته باشد.

اگر output schema validation fail شود:

```text
AI_OUTPUT_SCHEMA_INVALID
```

Domain object نباید از unvalidated free text ساخته شود.

---

# 47. AI Grounding Requirement

برای تصمیم‌های حساس:

```text
AI Decision
→ Evidence Refs / Feature Refs
```

بدون Trace کافی، Decision status می‌تواند:

```text
REVIEW_REQUIRED
```

شود.

---

# 48. Data Minimization

API Responseها role/purpose-aware هستند.

Provider API هرگز response کامل:

```text
GET /households/{id}
```

دریافت نمی‌کند.

Provider فقط Referral-specific contract دارد.

---

# 49. Sensitive Field Filtering

Field-level authorization باید server-side باشد.

Frontend نباید مسئول Hide کردن داده حساس به‌عنوان کنترل امنیتی اصلی باشد.

---

# 50. Audit Requirement per Command

Commandهای حساس باید Audit تولید کنند:

```text
actor
action
resource
before ref
after ref
purpose
timestamp
request_id
correlation_id
```

---

# 51. Version Conflict Example

Request:

```json
{
  "expected_version": 4
}
```

ولی current version = 5.

Response:

```text
409 VERSION_CONFLICT
```

Client باید state جدید را fetch و تصمیم را دوباره اعمال کند.

---

# 52. Idempotency Conflict

اگر یک Idempotency-Key با payload متفاوت دوباره استفاده شود:

```text
409 IDEMPOTENCY_KEY_REUSED_WITH_DIFFERENT_REQUEST
```

---

# 53. Validation Error Example

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Request validation failed.",
    "details": {
      "fields": [
        {
          "path": "raw_score_0_100",
          "code": "OUT_OF_RANGE"
        }
      ]
    }
  }
}
```

---

# 54. PGOR Error Mapping

نمونه:

```text
MISSING_REQUIRED_INDICATOR
→ 422

UNRESOLVED_REQUIRED_CONFLICT
→ 422

INVALID_FORMULA_VERSION
→ 422

VERSION_CONFLICT
→ 409
```

---

# 55. Referral State Error Mapping

Invalid transition:

```text
422 INVALID_REFERRAL_TRANSITION
```

Response details:

```json
{
  "from": "COMPLETED",
  "requested_to": "IN_PROGRESS"
}
```

---

# 56. API Observability

برای هر request:

- request_id
- correlation_id
- actor_id
- route
- status
- latency
- domain command type
- error code

ثبت می‌شود.

PII و sensitive payload نباید به‌صورت خام در logs نوشته شوند.

---

# 57. Rate Limiting

Scopeهای جدا:

- Caseworker UI
- Admin aggregation
- Provider callback
- External data integration
- AI generation

Provider callback rate limit نباید باعث از دست رفتن Event شود؛ retry/idempotency لازم است.

---

# 58. API Security

حداقل:

- OAuth2/OIDC compatible auth
- short-lived access token
- server-side authorization
- RBAC + resource scope
- organization scope
- provider isolation
- purpose-bound access
- request audit
- rate limiting
- schema validation
- output filtering

---

# 59. No Direct Database Contract

هیچ Consumer خارجی نباید به Schema Database به‌عنوان Integration Contract وابسته شود.

Contract رسمی:

```text
API
or
Event
```

است.

---

# 60. OpenAPI Generation Rule

پس از تثبیت این سند:

```text
HAMOON_API_CONTRACTS_V1.md
→ OpenAPI 3.1
→ JSON Schemas
→ Client Types
→ Server Validation
```

JSON Schema باید Source مشترک Validation باشد تا Frontend/Backend drift کاهش پیدا کند.

---

# 61. Minimum V1 API Surface

برای Sprintهای اول حداقل:

```text
Household
Facts
Accepted State
Evidence

PGOR Definitions
Assessments
Observations
PGOR Calculation

Diagnosis Review
Prescription Review

Providers
Provider Matching
Referrals
Provider Result

Reassessment
Outcome

AI Decision Trace
Timeline
Work Queue
```

Admin projection API می‌تواند بعد از Core Operational flow اضافه شود.

---

# 62. End-to-End Contract — Baseline Assessment

```text
POST /households
→ POST /households/{id}/facts
→ POST /households/{id}/assessments
→ POST /assessments/{id}/observations
→ POST /assessments/{id}/calculate-pgor
→ POST /households/{id}/diagnoses/generate
→ POST /diagnoses/{id}/confirm|modify|replace
→ POST /households/{id}/prescriptions/generate
→ POST /prescriptions/{id}/approve|modify
```

---

# 63. End-to-End Contract — Referral to Outcome

```text
POST /prescriptions/{id}/items/{item}/activate
→ POST /interventions/{id}/match-providers
→ POST /interventions/{id}/referrals
→ POST /referrals/{id}/send
→ provider callbacks
→ provider result
→ reassessment
→ calculate PGOR
→ outcome prepare
→ outcome confirm
→ learning signal
```

---

# 64. Definition of Done — API v1

API Contract v1 آماده Implementation است وقتی:

- endpointها با Domain Model هم‌راستا باشند
- هیچ direct overwrite برای Fact history وجود نداشته باشد
- optimistic concurrency روی commandهای حساس تعریف شده باشد
- idempotency برای Integration/Commandهای لازم تعریف شده باشد
- PGOR authoritative calculation فقط server-side باشد
- AI Decision و Human Decision جدا باشند
- Provider Result و Outcome جدا باشند
- Provider isolation رعایت شود
- Error codes machine-readable باشند
- API Trace/Audit contract مشخص باشد
- OpenAPI بتواند بدون تغییر مفهومی از این سند استخراج شود

---

# 65. مرحله بعد

پس از API Contracts:

```text
Event Contracts v1
→ Security / RBAC Matrix
→ Stack ADRs
→ Product Backlog
→ Sprint 1
```

اولین سند بعدی:

> **HAMOON_EVENT_CONTRACTS_V1.md**
