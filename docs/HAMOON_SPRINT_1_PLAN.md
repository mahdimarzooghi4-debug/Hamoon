# Hamoon — Sprint 1 Plan

> وضعیت: Approved Sprint Plan v1  
> Sprint Theme: **Executable Intelligence Core**  
> Sprint Goal: اجرای اولین Vertical Slice واقعی و end-to-end از ورود مددکار تا PGOR، تشخیص هوشمند، بازبینی انسانی و Learning Signal.
>
> مبنا:
> - `HAMOON_PRODUCT_BACKLOG_V1.md`
> - `ADR-001-HAMOON-CORE-STACK.md`
> - `ADR-002-HAMOON-REPOSITORY-ENGINEERING-STANDARDS.md`
> - `ADR-003-HAMOON-IDENTITY-AUTHENTICATION.md`
> - `ADR-006-HAMOON-AI-PROVIDER-STRATEGY.md`
> - `ADR-007-HAMOON-OBSERVABILITY.md`
> - `HAMOON_PGOR_ENGINE_SPEC_V1.md`
> - `HAMOON_SECURITY_RBAC_V1.md`

---

# 1. Sprint Goal

در پایان Sprint 1 باید این مسیر واقعی قابل اجرا باشد:

```text
Caseworker Login
→ Create Household
→ Record Household Facts
→ Resolve Current Accepted State
→ Start Assessment
→ Record PGOR Observations
→ Calculate Deterministic PGOR
→ Persist PGOR Snapshot
→ Build Feature Package
→ Generate Structured AI Diagnosis Proposal
→ Human Confirm / Modify
→ Persist Decision Trace
→ Create Learning Signal
```

این Sprint اولین اثبات عملی این اصل است:

> **Hamoon یک ماشین تصمیم و یادگیری است، نه CRUD با قابلیت AI.**

---

# 2. Sprint Duration

فرض اجرایی V1:

```text
10 working days
```

Sprint باید با Demo end-to-end بسته شود؛ نه صرفاً completion چند task فنی.

---

# 3. Sprint Scope — Must Have

Selected PBIs:

```text
PB-001 Repository Bootstrap
PB-002 Local Infrastructure Stack
PB-003 CI Baseline
PB-004 Request / Correlation Context

PB-010 OIDC Login Integration
PB-011 Authorization Context

PB-020 Create Household
PB-022 Record Household Fact
PB-025 Current Accepted State

PB-030 Seed PGOR Definition v1
PB-031 Start Assessment
PB-032 Record Indicator Observation
PB-034 Assessment Readiness
PB-035 Deterministic PGOR Engine
PB-036 Persist PGOR Snapshot

PB-040 AI Gateway Interface
PB-041 Diagnosis Output Schema v1
PB-042 Feature Package Builder
PB-043 Generate Diagnosis Proposal
PB-044 Human Confirm Diagnosis
PB-045 Human Modify Diagnosis

PB-082 Learning Signal
PB-083 Decision Trace

PB-120 Structured Logging + OpenTelemetry Baseline
PB-122 Security Regression Baseline
```

---

# 4. Stretch Scope

فقط اگر Must Have کامل و پایدار باشد:

```text
PB-012 Caseworker Resource Scope hardening
PB-021 Household Workspace Read Model
PB-037 PGOR Trace API
PB-046 Human Replace Diagnosis
PB-101 Caseworker Work Queue — diagnosis review only
```

Stretch item نباید Must Have را عقب بیندازد.

---

# 5. Explicitly Out of Sprint

این موارد عمداً وارد Sprint 1 نمی‌شوند:

- Prescription
- Intervention
- Provider Registry
- Provider Matching
- Referral
- Temporal ReferralWorkflow
- Provider Result
- Re-assessment Workflow
- Outcome
- Evidence binary upload
- Admin Dashboard
- Full Work Queue
- Prediction
- Simulation
- Calibration
- Multi-provider AI routing
- Kubernetes
- Production deployment

---

# 6. Sprint Architecture Slice

```text
Web/API
  ↓
Authentication / Authorization Context
  ↓
Household
  ↓
Facts / Accepted State
  ↓
Assessment
  ↓
PGOR Engine
  ↓
PGOR Snapshot
  ↓
Feature Package
  ↓
AI Gateway
  ↓
Diagnosis Proposal
  ↓
Human Review
  ↓
Decision Trace
  ↓
Learning Signal
```

---

# 7. Workstream A — Engineering Foundation

## S1-T001 — Repository Bootstrap

Implements:
`PB-001`

Deliverables:

```text
pyproject.toml
src/hamoon/
tests/
migrations/
contracts/
scripts/
docs/
```

Required files:

```text
src/hamoon/app/main.py
src/hamoon/app/config/settings.py
src/hamoon/app/api/router.py
src/hamoon/shared/errors/
```

Acceptance:

- application imports cleanly.
- FastAPI app starts.
- no domain implementation inside bootstrap.
- package layout follows ADR-002.

---

## S1-T002 — Health Endpoints

Deliver:

```text
GET /health/live
GET /health/ready
```

Acceptance:

- liveness does not query unnecessary dependencies.
- readiness verifies critical dependencies.
- no PII in output.

---

## S1-T003 — Dependency Management

Decision implementation:

```text
uv
```

Required development dependencies:

- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL driver
- pytest
- async test support
- Ruff
- type checker
- OpenTelemetry baseline
- NATS client

Exact pinned versions are captured in lockfile.

---

## S1-T004 — Local Docker Compose

Implements:
`PB-002`

Services:

```text
postgres
nats
keycloak
temporal
minio
```

Optional profile:

```text
otel-collector
grafana stack
```

Acceptance:

```text
one command → local dependencies running
```

---

## S1-T005 — CI Baseline

Implements:
`PB-003`

Pipeline:

```text
install
→ lint
→ type-check
→ unit tests
→ contract tests
→ migration validation
→ container build
```

CI must fail on test/lint/type failure.

---

# 8. Workstream B — Observability & Request Context

## S1-T010 — Structured Logging

Implements:
`PB-120`

Fields:

```text
timestamp
level
service
environment
request_id
correlation_id
trace_id
operation
error_code
```

No raw request body logging by default.

---

## S1-T011 — Request / Correlation Middleware

Implements:
`PB-004`

Acceptance:

- inbound request ID accepted or generated.
- correlation ID accepted or generated.
- response returns request ID.
- context available to application handlers.
- future event/AI trace can inherit it.

---

## S1-T012 — OpenTelemetry Bootstrap

Minimum instrumentation:

- FastAPI
- SQLAlchemy/PostgreSQL
- HTTP client
- custom span helper

Acceptance:

- local trace export can be enabled by configuration.
- disabled backend does not break app startup.

---

# 9. Workstream C — Identity & Authorization

## S1-T020 — Keycloak Development Realm

Implements:
`PB-010`

Create:

- local realm
- hamoon-web client
- hamoon-api audience
- caseworker test identity
- manager test identity

No production credentials.

---

## S1-T021 — JWT Validation

Acceptance:

- issuer validated.
- audience validated.
- signature validated.
- expiry validated.
- invalid token → 401.

---

## S1-T022 — Actor Mapping

Create persistence model:

```text
ACTOR
USER_ACCOUNT
```

Acceptance:

- OIDC subject maps to stable actor_id.
- Hamoon stores no password.

---

## S1-T023 — Authorization Context

Implements:
`PB-011`

Logical:

```text
actor_id
actor_type
organization_id
unit_id
roles[]
scopes[]
```

Domain receives actor context, not JWT.

---

# 10. Workstream D — Household & Accepted State

## S1-T030 — Household Aggregate

Implements:
`PB-020`

Core entity:

```text
Household
- id
- case_code
- lifecycle_status
- organizational_unit_id
- primary_caseworker_id
- version
```

Rules:

- create starts DRAFT.
- assignment recorded.
- optimistic version available.

---

## S1-T031 — Create Household API

```text
POST /api/v1/households
```

Acceptance:

- requires authorized actor.
- persists household.
- emits HouseholdCreated.
- audit entry created.
- response follows common envelope.

---

## S1-T032 — Household Fact Aggregate

Implements:
`PB-022`

Minimum fields:

```text
id
household_id
fact_type
value_type
value
source_id
effective_from
recorded_at
recorded_by
status
version
supersedes_fact_id?
```

Rule:

> Authorized Source does not imply automatically validated truth.

---

## S1-T033 — Record Fact API

```text
POST /api/v1/households/{id}/facts
```

Acceptance:

- immutable insert.
- source required.
- event emitted.
- audit emitted.

---

## S1-T034 — Current Accepted State Model

Implements:
`PB-025`

Create:

```text
CURRENT_ACCEPTED_FACT
ACCEPTED_STATE_CHANGE
```

Accepted state is projection/reference to selected fact.

---

## S1-T035 — Resolve Accepted State Command

```text
POST /api/v1/households/{id}/accepted-state/{fact_type}/resolve
```

Acceptance:

- human authorization required.
- optimistic concurrency.
- CurrentAcceptedStateChanged event.
- AI service identity denied.
- history preserved.

---

# 11. Workstream E — Assessment & PGOR

## S1-T040 — PGOR Definition Seed v1

Implements:
`PB-030`

Seed:

- Variables P/G/O/R
- Dimensions
- Indicators
- Definition version

No invented categorical numeric mapping.

---

## S1-T041 — Assessment Aggregate

Implements:
`PB-031`

Minimum:

```text
Assessment
- id
- household_id
- type
- definition_version_id
- status
- version
```

---

## S1-T042 — Start Assessment API

```text
POST /api/v1/households/{id}/assessments
```

Acceptance:

- BASELINE supported.
- definition version pinned.
- AssessmentStarted event emitted.

---

## S1-T043 — Indicator Observation

Implements:
`PB-032`

Validation:

```text
0 <= raw_score_0_100 <= 100
```

Fields include:

- indicator ID
- source
- effective_at
- recorded_by
- version

---

## S1-T044 — Record Observation API

```text
POST /api/v1/assessments/{id}/observations
```

Acceptance:

- invalid score → 422.
- observation is immutable/versioned.
- event emitted.

---

## S1-T045 — Assessment Readiness

Implements:
`PB-034`

Rules:

- Missing != Zero
- missing required → official calculation blocked
- unresolved required conflict → blocked
- preview and official status separate

---

## S1-T046 — PGOR Engine Core

Implements:
`PB-035`

Functions:

```text
normalize()
aggregate_dimension()
aggregate_variable()
calculate_pgor()
calculate_e()
determine_bottleneck()
determine_e_band()
```

No DB/network/framework dependency.

---

## S1-T047 — Formula Version Seed

Production activation requires explicit:

```text
alpha
beta
gamma
alpha + beta + gamma = 1
```

If official coefficients are not approved yet:

- Production Formula remains inactive.
- test fixture formula can be used only in test/local demonstration.
- test fixture must be clearly marked NON_PRODUCTION.

---

## S1-T048 — Calculate PGOR Application Command

```text
CalculatePGOR
```

Input:

- assessment ID
- expected version
- formula version
- mode

Output:

- deterministic result

---

## S1-T049 — Persist PGOR Snapshot

Implements:
`PB-036`

Store:

- P/G/O/R/E
- bottleneck
- bands
- engine version
- definition version
- scoring version
- formula version
- observation refs
- fingerprint

Snapshot immutable.

---

## S1-T050 — Calculate PGOR API

```text
POST /api/v1/assessments/{id}/calculate-pgor
```

Acceptance:

- client cannot submit authoritative P/G/O/R/E.
- official calculation respects readiness.
- event emitted.
- same inputs/versions reproduce same values.

---

# 12. Workstream F — AI Diagnosis

## S1-T060 — AI Gateway Interface

Implements:
`PB-040`

Interface:

```text
generate_structured(...)
```

Adapters:

- FakeAIProvider
- one provider adapter skeleton

Domain has no vendor SDK dependency.

---

## S1-T061 — Diagnosis JSON Schema

Implements:
`PB-041`

Schema supports:

```text
diagnosis items
needs
risks
capacities
constraints
bottleneck refs
evidence refs
structured rationale
```

No unrestricted arbitrary object output.

---

## S1-T062 — Feature Package

Implements:
`PB-042`

Inputs:

- Current Accepted State
- PGOR Snapshot
- relevant facts
- relevant assessment context
- data quality flags

Rules:

- versioned
- immutable
- PII minimized
- evidence refs only as needed

---

## S1-T063 — Fake Diagnosis Generation

First deterministic/local development path:

```text
Feature Package
→ FakeAIProvider
→ valid Diagnosis schema
```

This makes E2E test independent of external AI.

---

## S1-T064 — Real Provider Adapter Skeleton

Requirement:

- model alias
- routing policy
- timeout
- normalized error
- structured output parse

Real credentials not required in CI.

---

## S1-T065 — Generate Diagnosis Command

Implements:
`PB-043`

Flow:

```text
PGOR snapshot
→ feature package
→ AI Gateway
→ validate schema
→ persist AI Decision
→ create Diagnosis UNDER_REVIEW
```

---

## S1-T066 — Generate Diagnosis API

```text
POST /api/v1/households/{id}/diagnoses/generate
```

Acceptance:

- official PGOR required.
- AI Decision version trace persisted.
- no automatic final diagnosis.

---

# 13. Workstream G — Human Review

## S1-T070 — Confirm Diagnosis

Implements:
`PB-044`

```text
POST /api/v1/diagnoses/{id}/confirm
```

Acceptance:

- authorized human only.
- HumanDecision separate from AIDecision.
- DiagnosisConfirmed event.
- AI proposal immutable.

---

## S1-T071 — Modify Diagnosis

Implements:
`PB-045`

```text
POST /api/v1/diagnoses/{id}/modify
```

Acceptance:

- accepted/modified items structured.
- reason code stored.
- optional reason text.
- DiagnosisModified event.
- machine proposal preserved.

---

# 14. Workstream H — Decision Trace & Learning

## S1-T080 — Decision Trace

Implements:
`PB-083`

Sprint 1 trace:

```text
Household State Version
→ Assessment
→ PGOR Snapshot
→ Feature Package
→ AI Decision
→ Diagnosis
→ Human Decision
→ Learning Signal
```

Acceptance:

- all IDs connected.
- trace query can reconstruct flow.
- no reliance on log search to reconstruct Business trace.

---

## S1-T081 — Learning Signal

Implements:
`PB-082`

Initial types:

```text
DIAGNOSIS_CONFIRMED
DIAGNOSIS_MODIFIED
```

Fields:

- AI decision ID
- human decision ID
- household ID
- diagnosis ID
- signal type
- quality status
- created_at

No automatic training.

---

# 15. Workstream I — Events / Outbox

## S1-T090 — Outbox Table

Minimum:

```text
OUTBOX_MESSAGE
- id
- event_id
- event_type
- event_version
- aggregate_type
- aggregate_id
- aggregate_version
- correlation_id
- causation_id
- payload
- created_at
- published_at?
- attempt_count
```

---

## S1-T091 — Outbox Publisher

Flow:

```text
PostgreSQL Outbox
→ Publisher
→ NATS JetStream
```

Acceptance:

- at-least-once.
- publish retry.
- event_id preserved.
- no direct event publish before domain commit.

---

## S1-T092 — Core Event Schemas

Sprint 1 minimum:

```text
HouseholdCreated
HouseholdFactRecorded
CurrentAcceptedStateChanged
AssessmentStarted
IndicatorObservationRecorded
PGORSnapshotCalculated
AIDecisionGenerated
DiagnosisGenerated
DiagnosisConfirmed
DiagnosisModified
LearningSignalCreated
```

Contract schemas versioned.

---

# 16. Workstream J — Audit & Security

## S1-T100 — Audit Entry Foundation

Audit required for:

- household creation
- fact recording
- accepted state resolution
- PGOR official calculation
- diagnosis generation
- human confirm/modify

---

## S1-T101 — Security Regression Tests

Implements:
`PB-122`

Must pass:

- unauthenticated request denied.
- unauthorized household denied.
- AI runtime cannot resolve accepted state.
- AI runtime cannot confirm diagnosis.
- manager cannot mutate facts by default.
- no raw token/PII in logs.

---

# 17. Data Model Tables Required in Sprint 1

Minimum migration set:

```text
actor
user_account

household
case_assignment

data_source
household_fact
current_accepted_fact
accepted_state_change

pgor_definition_version
pgor_variable_definition
pgor_dimension_definition
pgor_indicator_definition

assessment
indicator_observation

pgor_formula_version
pgor_snapshot
pgor_snapshot_input

feature_package
feature_value

ai_model
ai_model_version
prompt_policy
prompt_policy_version
ai_decision

diagnosis
diagnosis_item
human_decision
decision_trace

learning_signal

domain_event
outbox_message
audit_entry
```

Tables can be implemented incrementally by migration, but Sprint exit requires the needed schema to exist.

---

# 18. API Surface Required in Sprint 1

```text
GET  /health/live
GET  /health/ready

POST /api/v1/households
GET  /api/v1/households/{id}

POST /api/v1/households/{id}/facts
GET  /api/v1/households/{id}/accepted-state
POST /api/v1/households/{id}/accepted-state/{fact_type}/resolve

POST /api/v1/households/{id}/assessments
POST /api/v1/assessments/{id}/observations
POST /api/v1/assessments/{id}/calculate-pgor
GET  /api/v1/pgor-snapshots/{id}

POST /api/v1/households/{id}/diagnoses/generate
GET  /api/v1/diagnoses/{id}
POST /api/v1/diagnoses/{id}/confirm
POST /api/v1/diagnoses/{id}/modify

GET  /api/v1/ai/decisions/{id}/trace
```

---

# 19. Sprint 1 Sequence

Recommended implementation sequence:

```text
1. Bootstrap / CI / Local Infrastructure
2. Config / DB / Migrations / Logging
3. OIDC / Actor / Authorization Context
4. Household
5. Facts / Accepted State
6. PGOR Definitions / Assessment / Observations
7. PGOR Engine
8. Snapshot / Event / Outbox
9. AI Gateway / Fake Provider
10. Feature Package
11. Diagnosis Proposal
12. Human Review
13. Decision Trace
14. Learning Signal
15. Security / Contract / E2E Tests
16. Stage-like Demo
```

---

# 20. Dependency Graph

```text
Foundation
  ↓
Identity
  ↓
Household
  ↓
Facts / Accepted State
  ↓
Assessment / Observation
  ↓
PGOR
  ↓
Feature Package
  ↓
AI Diagnosis
  ↓
Human Review
  ↓
Decision Trace
  ↓
Learning Signal
```

Outbox / Audit / Observability are cross-cutting and implemented alongside each step.

---

# 21. Acceptance Test — Golden Path

Test scenario:

## Given

- authenticated caseworker
- authorized household scope
- valid PGOR definition
- approved/test-active formula version
- complete accepted observations
- FakeAIProvider configured

## When

1. caseworker creates household
2. records required data
3. resolves accepted values
4. starts baseline assessment
5. records all required indicator observations
6. calculates PGOR
7. requests diagnosis
8. AI returns valid structured diagnosis
9. caseworker confirms or modifies

## Then

System must contain:

- immutable facts
- current accepted state
- assessment
- PGOR snapshot
- feature package
- AI decision
- diagnosis
- human decision
- decision trace
- learning signal
- domain events
- audit entries

and all references are connected.

---

# 22. Acceptance Test — Missing Data

Given:

- required indicator missing

When:

```text
OFFICIAL PGOR calculation requested
```

Then:

```text
422
MISSING_REQUIRED_INDICATOR
```

No official snapshot created.

---

# 23. Acceptance Test — Unresolved Conflict

Given:

- required indicator has unresolved conflict
- no accepted observation/value

Then:

```text
official calculation blocked
```

AI diagnosis cannot proceed.

---

# 24. Acceptance Test — PGOR Reproducibility

Given same:

- observation IDs/versions
- definition version
- formula version
- engine version

Then:

```text
P/G/O/R/E identical
fingerprint identical
```

---

# 25. Acceptance Test — AI Schema Failure

Given:

- AI provider returns invalid structure

Then:

- Diagnosis entity not finalized from invalid output.
- error normalized.
- failure trace stored.
- optional retry follows policy.
- no human-review item from invalid output.

---

# 26. Acceptance Test — Human Modification

Given:

- AI diagnosis proposal

When caseworker modifies it:

Then:

- AI proposal preserved.
- HumanDecision = MODIFY.
- final diagnosis reflects modified items.
- reason stored.
- LearningSignal = DIAGNOSIS_MODIFIED.
- trace links all entities.

---

# 27. Acceptance Test — Authorization

Caseworker A:

- can access assigned household.
- cannot access household assigned only to Caseworker B.

AI Runtime:

- can generate AI decision.
- cannot confirm diagnosis.
- cannot resolve accepted state.

Manager:

- read-only where permitted.
- cannot record/correct fact by default.

---

# 28. Test Layers Required

## Unit

- PGOR formulas
- assessment readiness
- authorization rules
- diagnosis state transitions
- learning signal mapping

## Integration

- PostgreSQL repositories
- migrations
- outbox
- NATS publish
- OIDC validation
- AI adapter contract

## Contract

- API schemas
- event schemas
- diagnosis schema

## E2E

- Golden Path

---

# 29. Sprint Quality Gates

Before Sprint closure:

```text
lint = pass
type check = pass
unit tests = pass
integration tests = pass
contract tests = pass
security regression = pass
golden path E2E = pass
migration check = pass
no critical unresolved defect
```

---

# 30. Observability Gates

Sprint exit requires:

- request ID visible
- correlation ID visible
- PGOR operation trace visible
- AI operation trace visible
- event publish metrics visible
- no raw PII in standard logs

---

# 31. Demo Script

Sprint Review demo:

```text
1. Login as Caseworker
2. Create Household
3. Enter PGOR observations
4. Resolve accepted data
5. Run PGOR
6. Show P/G/O/R/E + bottleneck
7. Generate AI diagnosis
8. Show evidence/feature trace
9. Modify one diagnosis item
10. Confirm decision
11. Show Decision Trace
12. Show Learning Signal
13. Show correlated technical trace
```

---

# 32. Definition of Done — Sprint 1

Sprint 1 Done فقط وقتی:

- Golden Path end-to-end اجرا می‌شود.
- PGOR deterministic و reproducible است.
- AI output structured و versioned است.
- Human review جدا از AI decision است.
- Accepted State با source validity اشتباه گرفته نمی‌شود.
- Domain Events از Outbox منتشر می‌شوند.
- Decision Trace کامل است.
- Learning Signal تولید می‌شود.
- Authorization enforce شده است.
- Audit وجود دارد.
- observability پایه فعال است.
- CI green است.
- Stage/local demo قابل تکرار است.

---

# 33. Expected Code Artifacts

در پایان Sprint انتظار داریم حداقل این artifactها وجود داشته باشند:

```text
pyproject.toml
uv.lock
docker-compose.yml
Dockerfile
.env.example

src/hamoon/app/
src/hamoon/domains/household/
src/hamoon/domains/family_data/
src/hamoon/domains/assessment/
src/hamoon/domains/pgor/
src/hamoon/domains/intelligence/
src/hamoon/domains/diagnosis/
src/hamoon/domains/learning/
src/hamoon/domains/audit/
src/hamoon/infrastructure/db/
src/hamoon/infrastructure/events/
src/hamoon/infrastructure/ai/

contracts/events/
contracts/ai/diagnosis/

migrations/

tests/unit/
tests/integration/
tests/contract/
tests/e2e/
```

---

# 34. Sprint Risks

## R1 — Official α/β/γ not approved

Mitigation:

- do not invent production coefficients.
- keep production formula inactive.
- use clearly labeled NON_PRODUCTION test fixture only for software validation.

## R2 — Identity setup delays feature work

Mitigation:

- FakeAuthorizationContext allowed for early unit/domain development.
- real OIDC remains Sprint exit requirement.

## R3 — External AI availability

Mitigation:

- FakeAIProvider is the E2E baseline.
- real adapter can remain non-default in local/CI.

## R4 — Scope overload

Mitigation:

- no Prescription/Referral/Outcome in Sprint 1.
- Stretch scope dropped first.
- priority is executable vertical slice.

---

# 35. Sprint Review Decision Gate

At Sprint Review answer these questions:

1. Can Hamoon calculate PGOR deterministically from accepted assessment data?
2. Can Hamoon create a structured AI diagnosis grounded in versioned household state?
3. Can a human confirm/modify without destroying AI history?
4. Can we reconstruct the full decision trace?
5. Does the system create a learning signal from human review?
6. Can unauthorized actors be prevented from performing sensitive actions?
7. Can one request be traced through API → Domain → Event → AI?
8. Is the architecture still modular and consistent with ADRs?

If any answer is "No", Sprint 1 is not considered complete.

---

# 36. Next Stage After Sprint 1

After Sprint 1:

```text
Code Review
→ Stage
→ QA / Testing
→ Sprint Review
→ Sprint 2
```

Sprint 2 target:

> **Prescription → Intervention → Provider Matching → Referral → ReferralWorkflow**
