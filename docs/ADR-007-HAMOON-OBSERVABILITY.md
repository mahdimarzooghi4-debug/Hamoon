# ADR-007 — Hamoon Observability

> وضعیت: Accepted for V1  
> دامنه تصمیم: Logs, Metrics, Traces, AI Telemetry, Event/Workflow Monitoring, Alerting, Correlation  
> وابسته به:
> - `HAMOON_TECHNICAL_ARCHITECTURE_V1.md`
> - `HAMOON_EVENT_CONTRACTS_V1.md`
> - `HAMOON_SECURITY_RBAC_V1.md`
> - `ADR-001-HAMOON-CORE-STACK.md`
> - `ADR-005-HAMOON-WORKFLOW-ORCHESTRATION.md`
> - `ADR-006-HAMOON-AI-PROVIDER-STRATEGY.md`

---

# 1. Context

Hamoon یک سامانه معمولی نیست. علاوه بر سلامت API و Database، باید بتوانیم سلامت خود «ماشین تصمیم‌گیری و یادگیری» را نیز مشاهده کنیم.

بنابراین Observability باید هم‌زمان این لایه‌ها را پوشش دهد:

```text
Platform
Data
Domain
Events
Workflows
Providers
AI
Human-in-the-loop
Learning
Security
```

هدف فقط Debugging نیست؛ باید بتوانیم بفهمیم:

- آیا سامانه کار می‌کند؟
- آیا داده سالم است؟
- آیا Eventها گیر کرده‌اند؟
- آیا Workflowها متوقف شده‌اند؟
- آیا AI خروجی معتبر می‌دهد؟
- آیا Human Override زیاد شده؟
- آیا Referralها دیر پاسخ می‌گیرند؟
- آیا Outcomeها ثبت می‌شوند؟
- آیا Learning loop واقعاً بسته می‌شود؟

---

# 2. Decision Summary

برای V1 تصمیم می‌گیریم:

```text
Observability Standard:
OpenTelemetry

Telemetry Types:
Logs + Metrics + Traces

Application Instrumentation:
OpenTelemetry SDK

Trace Propagation:
W3C Trace Context

Correlation:
request_id
correlation_id
event_id
workflow_id
AI trace_id
aggregate/resource ids where safe

Metrics:
Prometheus-compatible

Dashboarding:
Grafana-compatible

Logs:
structured JSON

Log Aggregation:
Loki-compatible or equivalent backend

Tracing Backend:
Tempo-compatible or equivalent backend

Alerting:
Grafana/Prometheus-compatible alerting

Concrete deployment:
finalized in ADR-008
```

Vendor-specific tooling may change, but OpenTelemetry remains the application instrumentation contract.

---

# 3. Why OpenTelemetry

Hamoon uses multiple execution paths:

- synchronous API
- PostgreSQL
- NATS
- Temporal
- AI workers
- provider adapters
- object storage
- integration callbacks

Without a standard trace/context model، observability becomes fragmented.

OpenTelemetry provides a vendor-neutral contract for:

- traces
- metrics
- logs correlation
- context propagation
- exporter replacement

---

# 4. Observability Layers

## 4.1 Platform Observability

Tracks:

- API availability
- latency
- error rates
- worker health
- database health
- NATS health
- Temporal health
- object storage health

## 4.2 Data Observability

Tracks:

- missing required indicators
- unresolved conflicts
- stale data
- integration failures
- invalid mappings
- projection lag
- accepted-state anomalies

## 4.3 Intelligence Observability

Tracks:

- AI request volume
- provider latency
- schema failures
- fallback rate
- grounding failures
- human confirm/modify/replace rates
- model/prompt/routing versions
- evaluation drift

## 4.4 Outcome/Learning Observability

Tracks:

- provider result → reassessment completion
- outcome availability
- learning signal creation
- learning signal quality
- feedback loop closure time

---

# 5. Structured Logging

تمام application logها باید JSON structured باشند.

Minimum fields:

```text
timestamp
level
service
environment
message
request_id?
correlation_id?
trace_id?
span_id?
actor_id?
aggregate_type?
aggregate_id?
event_id?
workflow_id?
operation?
error_code?
```

---

# 6. Logging Guardrails

ممنوع در logs:

- national ID
- phone
- exact address
- passwords
- access tokens
- refresh tokens
- client secrets
- raw sensitive evidence
- raw AI prompts with PII
- raw provider payloads containing sensitive data

در صورت نیاز برای diagnostics:

```text
reference IDs + hashes + classification-safe metadata
```

ثبت می‌شوند.

---

# 7. Log Levels

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

Production default:

```text
INFO
```

DEBUG برای production فقط به‌صورت کنترل‌شده و زمان‌دار.

---

# 8. Request Correlation

هر inbound API request:

```text
X-Request-Id
X-Correlation-Id
```

را می‌پذیرد یا تولید می‌کند.

این context باید به:

- domain command
- outbox event
- NATS message
- Temporal workflow/activity
- AI call
- provider call

منتقل شود.

---

# 9. W3C Trace Context

برای distributed trace:

```text
traceparent
tracestate
```

استاندارد اصلی propagation است.

Custom correlation ID همچنان برای Business flow حفظ می‌شود.

---

# 10. API Metrics

Minimum:

```text
http_requests_total
http_request_duration
http_request_errors_total
http_active_requests
```

Dimensions:

- route template
- method
- status class
- service
- environment

نه raw URL با household ID.

---

# 11. Database Metrics

```text
db_query_duration
db_pool_active
db_pool_wait
db_connection_errors
db_transaction_failures
db_deadlocks
db_migration_status
```

Slow query logging باید controlled و PII-safe باشد.

---

# 12. Outbox Metrics

```text
outbox_pending_count
outbox_oldest_age
outbox_publish_success_total
outbox_publish_failure_total
outbox_retry_total
```

Alert مهم:

> outbox backlog growing.

---

# 13. NATS Metrics

```text
event_publish_total
event_publish_failed_total
event_consume_total
event_consume_failed_total
consumer_lag
redelivery_total
dead_letter_total
```

Dimensions:

- event_type
- event_version
- consumer
- producer

---

# 14. Temporal Metrics

```text
workflow_started_total
workflow_completed_total
workflow_failed_total
workflow_cancelled_total
workflow_running_count
activity_retry_total
activity_failed_total
workflow_timeout_total
workflow_task_queue_backlog
```

Task queues:

```text
hamoon-core
hamoon-ai
hamoon-provider
hamoon-evidence
```

---

# 15. Human Wait Metrics

چون Hamoon Human-in-the-loop است:

```text
diagnosis_review_wait_duration
prescription_review_wait_duration
provider_selection_wait_duration
outcome_review_wait_duration
reassessment_completion_wait_duration
```

هدف:

- operational bottleneck
- SLA monitoring
- workflow design improvement

نه ranking فردی مددکار.

---

# 16. PGOR Metrics

```text
pgor_calculation_total
pgor_calculation_duration
pgor_calculation_failure_total
pgor_missing_required_total
pgor_conflict_block_total
pgor_snapshot_reuse_total
pgor_reproducibility_failure_total
```

Dimensions:

- engine_version
- definition_version
- formula_version
- assessment_type

---

# 17. Data Health Metrics

```text
households_with_missing_required_data
households_with_unresolved_conflict
stale_source_fact_count
invalid_external_mapping_count
accepted_state_projection_lag
assessment_incomplete_count
```

این metrics باید aggregate باشند و PII نداشته باشند.

---

# 18. AI Metrics

```text
ai_request_total
ai_success_total
ai_failure_total
ai_latency
ai_fallback_total
ai_schema_failure_total
ai_guardrail_reject_total
ai_grounding_failure_total
ai_provider_unavailable_total
ai_cost_estimate
ai_input_units
ai_output_units
```

Dimensions:

- task_class
- provider
- model_alias
- model_version
- routing_policy_version
- prompt_policy_version
- environment

---

# 19. Human Review Metrics

برای AI quality:

```text
ai_human_confirm_total
ai_human_modify_total
ai_human_replace_total
ai_human_reject_total
ai_human_defer_total
```

By:

- task_class
- model version
- prompt version
- routing policy

نباید به شکل performance score فردی مددکار استفاده شود.

---

# 20. AI Quality Signals

Derived metrics:

```text
confirmation_rate
modification_rate
replacement_rate
schema_compliance_rate
grounding_pass_rate
fallback_rate
```

این‌ها diagnostic/evaluation signals هستند.

---

# 21. Provider Metrics

```text
provider_referral_sent_total
provider_accept_total
provider_reject_total
provider_no_response_total
provider_response_duration
provider_service_duration
provider_result_received_total
provider_callback_failure_total
provider_delivery_retry_total
```

Dimensions:

- provider_id
- service_type
- region if permitted

Provider comparison باید contextual باشد و به یک امتیاز کلی غیرشفاف تبدیل نشود.

---

# 22. Outcome Metrics

```text
reassessment_started_total
reassessment_completed_total
outcome_prepared_total
outcome_confirmed_total
outcome_needs_more_time_total
outcome_needs_more_data_total
time_provider_result_to_outcome
```

Outcome distribution می‌تواند در analytics جداگانه محاسبه شود.

---

# 23. Learning Loop Metrics

```text
learning_signal_created_total
learning_signal_quality_raw
learning_signal_quality_curated
dataset_version_created_total
evaluation_run_total
evaluation_run_failed_total
model_candidate_created_total
model_promoted_total
```

مهم‌ترین operational question:

> آیا تصمیم → نتیجه → learning signal واقعاً کامل می‌شود؟

---

# 24. Security Metrics

```text
auth_failure_total
forbidden_request_total
scope_violation_total
provider_cross_scope_denied_total
sensitive_evidence_access_total
role_change_total
export_total
webhook_auth_failure_total
audit_pipeline_failure_total
```

---

# 25. Evidence Metrics

```text
evidence_upload_started_total
evidence_upload_completed_total
evidence_upload_failed_total
evidence_scan_failed_total
evidence_quarantined_total
evidence_download_total
evidence_storage_error_total
evidence_derivative_failed_total
```

---

# 26. SLO Categories

V1 حداقل این SLOها را تعریف می‌کند:

## Availability

- API availability
- critical workflow execution availability

## Latency

- interactive API p95
- interactive AI p95
- PGOR calculation latency

## Reliability

- event delivery success
- outbox age
- workflow failure rate
- provider dispatch success

## Data Freshness

- accepted-state projection lag
- integration lag

عدد دقیق SLO در deployment/operations policy تعیین می‌شود.

---

# 27. Error Budget

پس از تعیین SLO، error budget برای:

- API
- AI provider
- workflow
- integration

قابل تعریف است.

V1 architecture باید metrics لازم را از ابتدا تولید کند.

---

# 28. Health Endpoints

```text
GET /health/live
GET /health/ready
```

## Liveness

آیا process زنده است؟

## Readiness

آیا dependencyهای ضروری برای سرویس‌دهی در وضعیت قابل قبول هستند؟

Readiness باید با احتیاط طراحی شود تا failure یک dependency غیرحیاتی کل API را از load balancer خارج نکند.

---

# 29. Dependency Health

Health status:

```text
HEALTHY
DEGRADED
UNAVAILABLE
```

برای:

- PostgreSQL
- NATS
- Temporal
- Object Storage
- Identity validation/JWKS cache
- AI provider(s)

---

# 30. AI Health

AI Provider Health به‌صورت جدا:

```text
HEALTHY
DEGRADED
UNAVAILABLE
DISABLED
```

و Routing Policy می‌تواند از آن استفاده کند.

---

# 31. Dashboards

حداقل Dashboardهای V1:

## Platform
- API
- DB
- NATS
- Temporal
- Workers

## Data Health
- missing
- conflicts
- projection lag
- integration failures

## AI Health
- latency
- failures
- schema/grounding
- fallback
- human override

## Referral Operations
- sent
- accepted
- no-response
- result lag

## Learning Loop
- outcome completion
- learning signal flow
- evaluation status

---

# 32. Admin Dashboard vs Engineering Dashboard

این دو نباید یکی باشند.

### Product/Admin Dashboard

Business-facing:

- household population
- PGOR distribution
- bottlenecks
- intervention/outcome
- operational queues

### Engineering Observability Dashboard

Technical:

- latency
- errors
- lag
- workers
- DB
- NATS
- Temporal
- AI provider health

---

# 33. Alerting Philosophy

Alert باید actionable باشد.

Alert بد:

```text
CPU > 70%
```

بدون context.

Alert بهتر:

```text
Outbox oldest event > threshold
and backlog growing
```

یا:

```text
Provider callback failures > threshold
for 10 minutes
```

---

# 34. High-Priority Alerts

V1:

- API critical error spike
- PostgreSQL unavailable
- outbox stuck
- NATS consumer lag critical
- Temporal workflow failure spike
- provider dispatch failures
- AI provider unavailable without fallback
- AI schema failure spike
- audit pipeline failure
- evidence quarantine spike
- integration mapping failure spike

---

# 35. AI Drift Monitoring

Online monitoring:

- human modification rate
- human replacement rate
- schema failure
- grounding failure
- fallback rate
- outcome-linked quality when available

Model drift conclusion نباید فقط از یک metric گرفته شود.

---

# 36. Evaluation vs Monitoring

تفکیک:

```text
Monitoring = production behavior
Evaluation = controlled dataset quality measurement
```

Production metrics جای offline evaluation را نمی‌گیرند.

---

# 37. Business Correlation Trace

برای یک Household Decision Flow باید بتوانیم ببینیم:

```text
API Request
→ Command
→ PGOR Snapshot
→ AI Request
→ AI Decision
→ Human Review
→ Event
→ Workflow
→ Referral
→ Provider Result
→ Reassessment
→ Outcome
→ Learning Signal
```

بدون نمایش PII در trace labels.

---

# 38. Trace Attributes

Safe attributes:

```text
service.name
environment
operation
task_class
aggregate_type
event_type
workflow_type
provider_id
model_alias
formula_version
```

Unsafe:

- household name
- national ID
- phone
- evidence text

Household ID نیز فقط در secure internal trace metadata و طبق policy، نه public metric dimensions.

---

# 39. Sampling

Tracing sampling باید configurable باشد.

- errors: high/always sample
- critical workflows: higher sampling
- routine successful traffic: lower sampling if scale requires

Security/Audit data به tracing sampling وابسته نیست.

---

# 40. Retention

Telemetry retention بر اساس type:

- logs
- traces
- metrics
- AI cost data

در Deployment/Operations policy تعیین می‌شود.

Telemetry نباید جای Business Audit retention را بگیرد.

---

# 41. Audit vs Observability

```text
Audit:
who did what and when

Observability:
what is happening to the system and why
```

Audit append-only business/security record است.

Logs/traces ممکن است sample/expire شوند.

---

# 42. OpenTelemetry Instrumentation

V1 باید instrumentation برای این لایه‌ها داشته باشد:

- FastAPI
- PostgreSQL/SQLAlchemy
- HTTP clients
- NATS publisher/consumer
- Temporal activities/workflows where supported
- AI Gateway
- provider adapters
- storage adapters

Custom spans برای Business-critical operations اضافه می‌شود.

---

# 43. Custom Business Spans

نمونه:

```text
hamoon.pgor.calculate
hamoon.ai.generate_diagnosis
hamoon.diagnosis.human_review
hamoon.referral.dispatch
hamoon.outcome.prepare
```

Spanها نباید sensitive payload داشته باشند.

---

# 44. Cost Observability

AI cost باید measurable باشد.

Dashboard:

- cost per task class
- cost per model alias
- cost trend
- fallback cost
- batch vs interactive

اما cost telemetry نباید household PII داشته باشد.

---

# 45. Capacity Planning

Metrics باید امکان capacity planning برای:

- API workers
- AI workers
- provider workers
- NATS consumers
- Temporal task queues
- PostgreSQL
- object storage

را بدهد.

---

# 46. Development Environment

Local stack می‌تواند:

- OTEL Collector
- Prometheus
- Grafana
- Loki
- Tempo

را به‌صورت optional container profile اجرا کند.

حداقل app instrumentation باید حتی اگر backend observability local اجرا نشود فعال/قابل export باشد.

---

# 47. Stage Environment

Stage باید observability کامل داشته باشد تا قبل از Production:

- traces
- alerts
- workflow failures
- AI failures
- provider sandbox issues

قابل مشاهده باشند.

---

# 48. Production

Production observability باید:

- access-controlled
- environment isolated
- PII-safe
- alert-integrated
- retention-governed

باشد.

Production Prometheus metrics are protected by a dedicated monitoring credential.
Unauthenticated requests to `/metrics` must return HTTP 401. The credential is
separate from end-user OIDC tokens and must not appear in logs or artifacts.

Production configuration also requires OpenTelemetry export to a non-local HTTPS
collector endpoint. A deploy that disables metrics or OTEL is configuration-invalid.

---

# 49. Observability Access

Roles:

- Engineering/Ops: technical telemetry
- Security: security telemetry
- Product/Admin: approved business analytics only

مددکار operational به raw logs/traces دسترسی ندارد.

---

# 50. Incident Correlation

Incident باید بتواند از alert به:

```text
dashboard
→ trace
→ logs
→ event/workflow IDs
→ affected aggregate IDs
```

برسد.

---

# 51. Failure Taxonomy

Errors باید stable code داشته باشند.

مثال:

```text
PGOR_*
AI_*
REFERRAL_*
PROVIDER_*
INTEGRATION_*
EVIDENCE_*
AUTH_*
WORKFLOW_*
```

این taxonomy برای dashboards و alerting استفاده می‌شود.

---

# 52. No Metric Cardinality Explosion

Metric labels نباید شامل:

- household_id
- referral_id
- user_id
- request_id
- trace_id

باشند.

این‌ها فقط در logs/traces مناسب‌اند.

---

# 53. Privacy Guardrail

قبل از ارسال telemetry به backend:

- redact sensitive fields
- normalize URLs
- strip tokens
- avoid raw request/response bodies
- avoid raw prompts/responses

AI prompt logging به‌صورت پیش‌فرض disabled.

---

# 54. Model/Prompt Traceability

Observability باید هر AI request را به:

```text
model_version
prompt_policy_version
routing_policy_version
feature_schema_version
```

وصل کند.

---

# 55. Formula Traceability

PGOR metrics/traces باید:

```text
engine_version
definition_version
scoring_version
formula_version
```

را حمل کنند.

---

# 56. Provider Traceability

Provider flow:

```text
referral_id
provider_id
provider_service_id
delivery_attempt
external_event_id
```

در secure trace/log context قابل دنبال‌کردن باشد.

---

# 57. Workflow Traceability

Temporal:

```text
workflow_id
run_id
workflow_type
activity_type
attempt
```

با correlation ID Hamoon مرتبط شود.

---

# 58. Learning Traceability

Learning Signal باید به:

- AI Decision
- Human Decision
- Intervention
- Provider Result
- Outcome

reference داشته باشد.

Observability می‌تواند orphan signal/reference را شناسایی کند.

---

# 59. Data Quality Alerts

نمونه:

- spike in missing PGOR indicators
- unresolved conflict backlog increasing
- external integration freshness below threshold
- provider result ingestion stopped
- reassessment backlog growing

---

# 60. Synthetic Checks

Production می‌تواند synthetic checks داشته باشد:

```text
health
auth validation
basic API
event publish/consume canary
AI gateway health without sensitive data
```

هیچ synthetic check نباید production household data بسازد مگر policy صریح.

---

# 61. Release Observability

هر deployment باید version metadata داشته باشد:

```text
application_version
git_commit
migration_version
deployment_id
```

Hamoon exposes this non-sensitive runtime identity through:

```text
GET /health/release
```

The endpoint reads the active Alembic version from PostgreSQL and reports the
application version, immutable Git commit baked into the OCI image, and runtime
deployment ID. Release/Stage/Production verification must compare these values with
the promoted release evidence before declaring a deployment healthy.

AI/PGOR versionها جدا هستند.

---

# 62. Deployment Markers

Dashboard/trace backend باید deployment marker داشته باشد تا error/latency change با release مقایسه شود.

---

# 63. Operational Runbooks

هر Critical Alert باید Runbook reference داشته باشد.

حداقل:

- DB unavailable
- NATS backlog
- Temporal stuck
- AI provider outage
- provider callbacks failing
- audit pipeline failure
- evidence storage unavailable

---

# 64. Consequences

## Positive

- end-to-end traceability
- vendor-neutral instrumentation
- AI quality visibility
- event/workflow diagnostics
- measurable learning loop
- production incident response
- cost visibility

## Trade-offs

- telemetry infrastructure adds operational cost
- careful PII redaction required
- metrics taxonomy needs discipline
- distributed tracing adds implementation overhead

---

# 65. Guardrails

1. OpenTelemetry is the app instrumentation contract.
2. Structured logs only.
3. No raw PII in logs/metrics.
4. No high-cardinality IDs in metric labels.
5. Audit is not replaced by logs.
6. Monitoring is not evaluation.
7. AI prompt/response logging disabled by default.
8. Correlation context must cross API/Event/Workflow/AI boundaries.
9. Alert must be actionable.
10. Every critical async subsystem needs lag/backlog metrics.

---

# 66. Acceptance Criteria

ADR-007 implemented when:

- OpenTelemetry initialized.
- request/correlation/trace context propagates.
- structured JSON logs exist.
- API metrics exist.
- PostgreSQL instrumentation exists.
- outbox/NATS metrics exist.
- Temporal metrics exist.
- AI Gateway telemetry exists.
- PGOR version metrics exist.
- provider flow metrics exist.
- security-sensitive logs are redacted.
- dashboards for Platform/Data/AI/Referral exist.
- critical alerts and runbook references exist.
- stage environment demonstrates end-to-end trace.

---

# 67. Next ADR

> **ADR-008 — Deployment Platform**

پس از آن:

```text
Product Backlog
→ Sprint 1
→ Code
```
