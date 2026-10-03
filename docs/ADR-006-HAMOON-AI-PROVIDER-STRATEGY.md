# ADR-006 — Hamoon AI Provider Strategy & Model Routing

> وضعیت: Accepted for V1  
> دامنه تصمیم: AI Provider Abstraction, Model Routing, Structured Output, Fallback, Cost/Latency Control, Evaluation, Safety  
> وابسته به:
> - `HAMOON_AI_ARCHITECTURE_BASELINE.md`
> - `HAMOON_TECHNICAL_ARCHITECTURE_V1.md`
> - `HAMOON_PGOR_ENGINE_SPEC_V1.md`
> - `HAMOON_API_CONTRACTS_V1.md`
> - `HAMOON_SECURITY_RBAC_V1.md`
> - `ADR-001-HAMOON-CORE-STACK.md`
> - `ADR-005-HAMOON-WORKFLOW-ORCHESTRATION.md`

---

# 1. Context

Hamoon از ابتدا AI-first طراحی شده است، اما نباید Domain Logic یا تصمیم‌های حیاتی به یک Vendor یا Model خاص قفل شوند.

AI در Hamoon برای این حوزه‌ها استفاده می‌شود:

- Diagnosis
- Prescription
- Provider Matching support
- Prediction
- Simulation
- Outcome interpretation
- anomaly/conflict explanation
- summarization
- evidence synthesis
- caseworker copilot

در عین حال:

- PGOR deterministic است
- Human-in-the-loop اجباری است
- AI output باید structured و traceable باشد
- هر تصمیم AI باید model/prompt/policy version داشته باشد
- provider/model تغییرپذیر است
- داده حساس باید minimized شود

---

# 2. Decision Summary

برای V1:

```text
AI Access Layer:
Internal AI Gateway

Provider Strategy:
Provider-agnostic adapters

Production Strategy:
One primary provider per task class
+ optional configured fallback

Routing:
Policy-based, not random

Model Selection:
Task alias → model policy → concrete provider/model

Structured Output:
Mandatory for decision-producing tasks

Prompt/Policy Versioning:
Mandatory

Provider SDK Boundary:
infrastructure/ai only

Domain Dependency:
none on provider/model names

PGOR:
never routed through LLM

Human Decision:
always separate from AI Decision

Evaluation:
required before model/prompt promotion

Automatic provider switching:
allowed only for technical failure policy,
not for changing business semantics silently
```

---

# 3. AI Gateway

تمام AI callها از یک Gateway عبور می‌کنند.

Logical interface:

```text
AIGateway
- generate_structured(task, feature_package, policy_version)
- generate_text(task, context, policy_version)
- embed(content, embedding_policy)
- classify(task, input, policy_version)
```

Domain نباید بداند:

- provider name
- endpoint
- API key
- SDK
- concrete model ID

---

# 4. Provider Adapter Contract

هر Provider Adapter:

```text
AIProviderAdapter
- generate_structured(...)
- generate_text(...)
- supports(capability)
- health()
- normalize_error(...)
```

در:

```text
src/hamoon/infrastructure/ai/providers/
```

قرار می‌گیرد.

---

# 5. Task Classes

Model routing بر اساس Task Class انجام می‌شود، نه صرفاً user prompt.

V1 task classes:

```text
DIAGNOSIS
PRESCRIPTION
PROVIDER_MATCH_EXPLANATION
CASE_SUMMARY
EVIDENCE_SYNTHESIS
DATA_ANOMALY_EXPLANATION
OUTCOME_INTERPRETATION
PREDICTION_EXPLANATION
SIMULATION_EXPLANATION
COPILOT_ASSIST
```

Prediction/Simulation numerical models ممکن است غیر-LLM باشند؛ LLM فقط explanation/interface layer است مگر در Spec جدا خلاف آن تصویب شود.

---

# 6. Model Alias

Domain از concrete model ID استفاده نمی‌کند.

مثال:

```text
hamoon.diagnosis.v1
hamoon.prescription.v1
hamoon.summary.v1
hamoon.match-explanation.v1
```

هر Alias به Model Routing Policy وصل می‌شود.

---

# 7. Model Routing Policy

Logical record:

```text
MODEL_ROUTING_POLICY
- id
- task_class
- version
- primary_provider
- primary_model
- fallback_provider?
- fallback_model?
- max_latency_ms?
- max_cost_class?
- required_capabilities[]
- structured_output_required
- region/data_policy
- status
- approved_at
```

Routing Policy یک artifact versioned و auditable است.

---

# 8. Routing Order

برای هر request:

```text
1. Resolve Task Class
2. Resolve Routing Policy Version
3. Validate Data Policy
4. Select Primary Provider/Model
5. Execute
6. Validate Structured Output
7. Apply safety/grounding checks
8. Persist AI Decision Trace
9. Return proposal
```

Fallback فقط در شرایط policy-approved انجام می‌شود.

---

# 9. Fallback Semantics

Fallback برای failure فنی مجاز است:

```text
timeout
provider unavailable
rate limit
temporary network failure
```

Fallback برای موارد زیر به‌صورت silent مجاز نیست:

```text
low confidence
bad business answer
different diagnosis
policy disagreement
```

این موارد باید evaluation/review شوند.

---

# 10. No Silent Semantic Drift

اگر fallback provider/model semantics متفاوت دارد، Routing Policy باید آن را explicitly approve کرده باشد.

هر fallback execution باید در trace ثبت کند:

```text
primary attempted
failure reason
fallback selected
fallback model version
```

---

# 11. Structured Output

برای taskهای تصمیم‌ساز:

```text
DIAGNOSIS
PRESCRIPTION
PROVIDER_MATCH_EXPLANATION
OUTCOME_INTERPRETATION
```

Structured output اجباری است.

Output باید JSON Schema version داشته باشد.

مثال:

```text
contracts/ai/diagnosis/v1.schema.json
```

Free-text پاسخ نمی‌تواند مستقیماً Domain Entity نهایی بسازد.

---

# 12. Schema Validation

Flow:

```text
Provider Response
→ Parse
→ JSON Schema Validate
→ Business Guardrail Validate
→ Persist AI Decision
```

Failure:

```text
AI_OUTPUT_SCHEMA_INVALID
```

ممکن است یک retry محدود با repair policy انجام شود، ولی raw invalid output وارد Domain نمی‌شود.

---

# 13. Prompt / Policy Registry

هر AI task دارای:

```text
prompt_policy_id
prompt_policy_version
output_schema_version
routing_policy_version
```

است.

Prompt change بدون version bump/approval ممنوع است.

---

# 14. System Prompt vs Business Policy

Business Ruleهای حیاتی فقط در Prompt تعریف نمی‌شوند.

مثال:

اینکه AI حق تغییر Accepted State ندارد باید در Authorization/Domain enforce شود، نه فقط prompt instruction.

Prompt فقط behavior guidance است، نه security boundary.

---

# 15. Input Contract

AI ورودی آزاد از Database نمی‌گیرد.

Flow:

```text
Current Accepted State
+ PGOR Snapshot
+ Relevant Timeline
+ Evidence References
+ Constraints
→ Feature Package
→ AI Gateway
```

Feature Package versioned است.

---

# 16. Data Minimization

هر Task فقط داده لازم را می‌گیرد.

مثال Diagnosis:

مجاز:

- PGOR
- accepted facts relevant to need
- recent interventions
- relevant evidence summary
- unresolved disputes
- trajectory

غیرضروری:

- full identity profile
- national ID
- unrelated household details
- arbitrary notes

---

# 17. Provider Data Policy

هر Routing Policy باید Data Policy داشته باشد.

مثال:

```text
PII_ALLOWED = false
SENSITIVE_EVIDENCE_ALLOWED = false
REGION = approved-region
RETENTION_MODE = provider-policy-reference
```

اگر داده Task با Provider policy سازگار نباشد:

```text
ROUTING_BLOCKED_BY_DATA_POLICY
```

---

# 18. Model Registry

هر concrete model version در:

```text
AI_MODEL
AI_MODEL_VERSION
```

ثبت می‌شود.

حداقل metadata:

```text
provider
model_id
purpose
capabilities
status
evaluation_version
limitations
approved_at
deployed_at
retired_at
```

---

# 19. Provider Registry

Logical provider record:

```text
AI_PROVIDER
- id
- code
- status
- adapter_type
- region?
- data_processing_policy_ref
- supports_structured_output
- supports_tool_calling
- supports_vision
- supports_embeddings
```

Secretها در این Registry ذخیره نمی‌شوند.

---

# 20. Capability-based Routing

Routing می‌تواند requirement داشته باشد:

```text
STRUCTURED_OUTPUT
TOOL_CALLING
LONG_CONTEXT
VISION
EMBEDDING
LOW_LATENCY
HIGH_REASONING
```

Provider/model باید capability مورد نیاز را declare کند.

---

# 21. Task-Specific Model Strategy

V1 یک model واحد برای همه taskها فرض نمی‌کند.

ممکن است:

```text
Diagnosis → reasoning-capable model
Summary → lower-cost fast model
Evidence synthesis → long-context model
Embedding → embedding model
```

باشد.

اما هر mapping باید versioned/evaluated باشد.

---

# 22. Cost Classes

Routing Policy می‌تواند Cost Class داشته باشد:

```text
LOW
STANDARD
HIGH
```

Business criticality تعیین می‌کند کدام task اجازه استفاده از مدل گران‌تر دارد.

Caseworker UI نباید model انتخاب کند.

---

# 23. Latency Classes

```text
INTERACTIVE
BACKGROUND
BATCH
```

مثال:

- case summary → INTERACTIVE
- diagnosis generation → BACKGROUND/INTERACTIVE depending UX
- evaluation batch → BATCH

Routing می‌تواند بر اساس latency class model متفاوت انتخاب کند.

---

# 24. Synchronous vs Async

Interactive tasks:

```text
API → AI Gateway → response
```

Longer tasks:

```text
API → 202
→ Temporal Activity / AI Worker
→ AI Gateway
→ AIDecisionGenerated
```

---

# 25. Timeout

هر Routing Policy timeout دارد.

No infinite model call.

Timeout result:

```text
AI_PROVIDER_TIMEOUT
```

و workflow retry policy تصمیم بعدی را می‌گیرد.

---

# 26. Retry

Retry فقط برای failureهای transient.

مثال:

```text
rate limit
timeout
temporary unavailable
network error
```

Retry برای invalid business output بی‌نهایت ممنوع است.

---

# 27. Tool Calling

LLM ممکن است Tool Calling داشته باشد، اما Toolها توسط Hamoon allow-list می‌شوند.

Model نمی‌تواند arbitrary API call انجام دهد.

Tool policy:

```text
task
→ allowed tools
→ actor/system permission
→ request validation
→ audit
```

---

# 28. Read Tools vs Write Tools

V1 preference:

AI tools primarily read/analysis-oriented.

Write commandها:

- accepted-state mutation
- diagnosis confirmation
- prescription approval
- referral send
- outcome confirmation

در اختیار AI مستقیم نیستند.

---

# 29. Grounding

برای decision-support output:

AI باید evidence refs / feature refs داشته باشد.

```text
AI Decision
→ supporting evidence refs
→ source feature refs
```

اگر grounding کافی نباشد:

```text
status = REVIEW_REQUIRED
```

---

# 30. Confidence

Confidence فقط وقتی ذخیره می‌شود که method آن برای task تعریف شده باشد.

LLM self-reported confidence به‌تنهایی معیار علمی قابل اعتماد محسوب نمی‌شود.

بنابراین:

- confidence field optional
- calibration/evaluation policy required
- UI نباید عدد ساختگی نمایش دهد

---

# 31. Uncertainty

Uncertainty می‌تواند از:

- missing data
- conflicting sources
- model calibration
- ensemble/model output variance
- insufficient evidence

بیاید.

Type آن باید مشخص باشد.

---

# 32. Explainability

AI output باید بتواند ارائه دهد:

- what was observed
- which evidence/features mattered
- what is proposed
- why
- what is uncertain
- what needs human review

Explainability نباید chain-of-thought داخلی مدل را ذخیره یا نمایش دهد.

Hamoon reasoning trace باید مبتنی بر structured rationale/evidence refs باشد.

---

# 33. Decision Trace

برای هر AI Decision:

```text
task_class
feature_package_id
state_version
pgor_snapshot_id
provider
model_version
routing_policy_version
prompt_policy_version
output_schema_version
evidence_refs
structured_output
latency
cost metadata
fallback metadata
generated_at
trace_id
```

ثبت می‌شود.

---

# 34. Cost Telemetry

حداقل:

```text
input_units/tokens
output_units/tokens
estimated_cost
provider
model
task_class
```

در observability ثبت می‌شود.

Household PII در labels ممنوع است.

---

# 35. Rate Limits

Gateway باید per-provider limits را مدیریت کند.

همچنین per-task concurrency:

```text
diagnosis_concurrency
summary_concurrency
batch_evaluation_concurrency
```

تا کارهای Batch interactive traffic را مختل نکنند.

---

# 36. Circuit Breaker

اگر Provider failure rate بالا رفت:

```text
open circuit
→ route according to fallback policy
or
→ fail controlled
```

نه اینکه retry storm ایجاد شود.

---

# 37. Provider Health

Gateway health model:

```text
HEALTHY
DEGRADED
UNAVAILABLE
DISABLED
```

Health routing factor است، ولی Domain semantics را تغییر نمی‌دهد.

---

# 38. Development Adapter

برای local/test:

```text
FakeAIProvider
```

الزامی است.

هدف:

- deterministic tests
- zero external cost
- no internet dependency
- contract testing

---

# 39. Recording / Replay in Tests

برای integration tests می‌توان sanitized fixtures از provider responses نگه داشت.

Raw production prompts/responses containing PII نباید fixture شوند.

---

# 40. Evaluation Gate

هر model/prompt/routing change قبل از Production:

```text
Candidate
→ Evaluation Dataset
→ Metrics
→ Safety/Schema Tests
→ Review
→ Approval
→ Versioned Activation
```

---

# 41. Diagnosis Evaluation

حداقل metrics:

```text
expert confirmation rate
modification rate
replacement rate
evidence coverage
unsupported claim rate
schema compliance
safety violation rate
```

این metrics به معنی score سیاسی/ارزشی نیستند؛ فقط کیفیت سیستم را می‌سنجند.

---

# 42. Prescription Evaluation

حداقل:

```text
human acceptance
modification patterns
contraindicated suggestion rate
target PGOR alignment
evidence grounding
schema compliance
```

---

# 43. Matching Evaluation

حداقل:

```text
eligibility correctness
provider acceptance
human change rate
no-response rate
outcome-linked evidence
```

AI نباید provider winner غیرقابل توضیح تولید کند.

---

# 44. Summary / Copilot Evaluation

حداقل:

```text
factuality
source coverage
omission rate
hallucination rate
actionability
latency
```

---

# 45. Promotion

Promotion به Production فقط از Registry/Governance process.

AI Runtime حق self-promote ندارد.

---

# 46. Rollback

هر active model/prompt/routing policy باید previous approved version داشته باشد.

Rollback باید بدون code rewrite ممکن باشد.

---

# 47. Shadow Evaluation

برای مدل جدید می‌توان:

```text
same feature package
→ production model
→ candidate model in shadow
```

اجرا کرد.

Candidate output به کاربر نمایش داده نمی‌شود مگر در controlled experiment.

---

# 48. A/B Testing

برای تصمیم‌های حساس V1 به‌صورت پیش‌فرض A/B آزاد روی کاربران نداریم.

هر controlled experiment باید:

- governance approval
- evaluation plan
- safety constraints
- traceability

داشته باشد.

---

# 49. Learning Boundary

Learning Signal مستقیم مدل Production را تغییر نمی‌دهد.

```text
Learning Signals
→ Curated Dataset
→ Offline Evaluation
→ Candidate
→ Approval
→ Deploy
```

---

# 50. Embeddings

Embeddings فقط برای use case مشخص فعال می‌شوند.

مثال:

- semantic evidence retrieval
- knowledge retrieval

Embedding model نیز:

- Registry
- Version
- Data Policy
- Evaluation

دارد.

---

# 51. RAG Boundary

اگر RAG اضافه شود:

```text
Authorized Retrieval
→ Evidence/Knowledge Refs
→ Context Package
→ AI Gateway
```

Model حق search آزاد روی کل data corpus را ندارد.

---

# 52. Knowledge Sources

منابع Knowledge باید:

- approved
- versioned where possible
- permission-aware
- traceable

باشند.

AI response باید source refs را نگه دارد.

---

# 53. Vision / Document AI

Vision فقط برای Taskهای مشخص و با Data Policy مجاز.

Binary evidence به‌صورت پیش‌فرض به provider ارسال نمی‌شود.

اگر task نیاز داشت:

- authorization
- provider capability
- data policy
- evidence trace

الزامی است.

---

# 54. Safety / Guardrail Layer

Gateway باید امکان اجرای guardrail قبل و بعد از model call داشته باشد.

Pre-call:

- data minimization
- forbidden field check
- policy validation

Post-call:

- schema validation
- unsupported action detection
- sensitive output checks
- grounding validation
- domain rule validation

---

# 55. Domain Guardrails

نمونه:

اگر model output پیشنهاد دهد:

```text
change accepted employment status
```

Domain/API آن را به accepted-state mutation تبدیل نمی‌کند.

AI فقط می‌تواند:

```text
flag conflict
suggest review
```

---

# 56. Provider Selection for Production

ADR-006 عمداً یک Vendor خاص را به‌عنوان دائمی تثبیت نمی‌کند.

Production provider باید بر اساس deployment-specific factors انتخاب شود:

- data residency
- security/compliance
- structured-output capability
- latency
- availability
- cost
- model quality
- contractual data handling

انتخاب concrete provider در environment/deployment record ثبت می‌شود.

---

# 57. Initial Implementation Rule

اولین implementation باید حداقل داشته باشد:

- FakeAIProvider
- one real provider adapter
- task aliases
- routing policy registry
- structured output validation
- trace persistence
- evaluation harness

اما Domain tests نباید به real provider وابسته باشند.

---

# 58. Secrets

Provider credentials:

- secret manager
- per environment
- rotated
- never in repo
- never in prompt
- never in logs

---

# 59. Error Model

Stable errors:

```text
AI_PROVIDER_UNAVAILABLE
AI_PROVIDER_TIMEOUT
AI_RATE_LIMITED
AI_OUTPUT_SCHEMA_INVALID
AI_OUTPUT_GROUNDING_FAILED
AI_ROUTING_POLICY_NOT_FOUND
AI_MODEL_VERSION_DISABLED
AI_DATA_POLICY_BLOCKED
AI_TOOL_NOT_ALLOWED
AI_GUARDRAIL_REJECTED
```

---

# 60. Observability

Metrics:

```text
ai_request_total
ai_success_total
ai_failure_total
ai_latency
ai_fallback_total
ai_schema_failure_total
ai_guardrail_reject_total
ai_grounding_failure_total
ai_cost_estimate
ai_input_units
ai_output_units
ai_provider_health
```

Dimensions:

- task_class
- provider
- model_alias
- routing_policy_version
- environment

No household PII.

---

# 61. Security

- AI Gateway service identity separate
- Provider credential scoped
- Feature Package access authorized
- evidence minimized
- prompt injection treated as untrusted content
- model output treated as untrusted until validated
- tool calls allow-listed
- no direct DB access for external model provider

---

# 62. Prompt Injection Boundary

Evidence/document text is untrusted input.

Rules:

- retrieved content cannot override system/policy instructions
- tools are not granted based on evidence text
- external content cannot change authorization
- suspicious instruction-like evidence remains data, not policy

---

# 63. Model Output Trust

Model output is untrusted proposal.

Before use:

```text
schema validate
→ guardrail validate
→ domain validate
→ human review where required
```

---

# 64. Consequences

## Positive

- no vendor lock in Domain
- task-specific model optimization
- controlled fallback
- auditable model changes
- cost/latency control
- safe AI boundaries
- easier future multi-provider strategy

## Trade-offs

- Gateway/Registry complexity
- evaluation infrastructure required early
- provider capability differences need adapters
- fallback semantics require discipline

---

# 65. Guardrails

1. No direct model SDK in Domain/Application modules.
2. No LLM in PGOR path.
3. No AI decision without versioned trace.
4. No free-text decision → final Domain Entity directly.
5. No provider/model choice from UI.
6. No silent semantic fallback.
7. No self-reported confidence treated as calibrated probability by default.
8. No production model/prompt change without evaluation.
9. No unrestricted AI tool calling.
10. No Learning Signal → automatic production retrain.

---

# 66. Acceptance Criteria

ADR-006 implemented when:

- AI Gateway interface exists.
- provider adapter interface exists.
- FakeAIProvider exists.
- at least one real provider adapter exists.
- task aliases exist.
- routing policy is versioned.
- structured output schema validation works.
- provider/model/prompt/routing versions persist in trace.
- fallback behavior is tested.
- data policy can block routing.
- model evaluation harness exists.
- domain layer contains no provider-specific dependency.
- AI output cannot bypass human approval gates.

---

# 67. Next ADR

> **ADR-007 — Observability**

بعد از آن:

```text
ADR-008 — Deployment

→ Product Backlog
→ Sprint 1
```
