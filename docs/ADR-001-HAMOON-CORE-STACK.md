# ADR-001 — Hamoon Core Technical Stack

> وضعیت: Accepted for V1  
> دامنه تصمیم: Application Backend, Primary Database, Event Backbone, AI Runtime  
> وابسته به:
> - `HAMOON_TECHNICAL_ARCHITECTURE_V1.md`
> - `HAMOON_DATA_MODEL_V1.md`
> - `HAMOON_PGOR_ENGINE_SPEC_V1.md`
> - `HAMOON_API_CONTRACTS_V1.md`
> - `HAMOON_EVENT_CONTRACTS_V1.md`
> - `HAMOON_SECURITY_RBAC_V1.md`

---

# 1. Context

Hamoon یک سامانه CRUD معمولی نیست. هسته محصول باید هم‌زمان این نیازها را پشتیبانی کند:

- Temporal household data
- deterministic PGOR calculation
- human-in-the-loop decisions
- AI diagnosis / prescription / matching
- immutable decision trace
- provider integrations
- event-driven workflow
- auditability
- reproducibility
- future model calibration and learning
- operational simplicity for V1

معماری باید AI-first باشد، اما نباید از روز اول با Microserviceهای متعدد پیچیدگی عملیاتی غیرضروری ایجاد کند.

---

# 2. Decision Summary

برای V1 تصمیم می‌گیریم:

```text
Application Runtime:
Python + FastAPI

Architecture Style:
Modular Monolith
with explicit bounded contexts

Primary Database:
PostgreSQL

Persistence:
SQLAlchemy
+ Alembic migrations

Validation / Contracts:
Pydantic models
+ OpenAPI / JSON Schema

Event Reliability:
Transactional Outbox in PostgreSQL

Event Backbone:
NATS JetStream

AI Runtime:
Python Intelligence Runtime
behind an internal AI Gateway

AI Provider Integration:
Provider Adapter abstraction
(no domain dependency on a specific model vendor)

PGOR Engine:
Pure deterministic Python module/library
(no LLM dependency)

Async / Long-running Work:
Event-driven workers initially;
durable workflow engine evaluated separately in a later ADR

Evidence Files:
Object Storage through abstract storage interface

Cache:
Not a source of truth;
introduced only for measured performance needs
```

---

# 3. Application Backend — Python + FastAPI

## Decision

Hamoon V1 backend will use:

```text
Python
FastAPI
Pydantic
SQLAlchemy
Alembic
```

## Why

Hamoon's technical core contains both:

1. classical application/domain logic
2. AI/ML/intelligence workloads

Using Python for both minimizes language boundaries between:

- API layer
- PGOR engine
- feature building
- AI orchestration
- evaluation
- calibration tooling
- offline analysis

FastAPI fits the API contracts already defined:

- typed request/response models
- OpenAPI generation
- async support
- dependency-based authorization
- structured validation
- clean separation between transport and domain layers

---

# 4. Architecture Style — Modular Monolith First

## Decision

V1 is a:

> **Modular Monolith with strict bounded-context boundaries**

Not a distributed microservice system.

Logical modules:

```text
identity
household
family_data
assessment
pgor
diagnosis
prescription
intervention
provider
referral
outcome
intelligence
learning
audit
integration
```

Each module owns:

- domain rules
- application commands/queries
- repository interfaces
- event contracts
- authorization rules

Modules must not directly mutate another module's internal tables.

---

# 5. Why Not Microservices in V1

Hamoon already has substantial inherent complexity:

- temporal state
- event history
- AI traces
- provider contracts
- human review
- outcome measurement
- model versioning

Adding distributed transactions, service discovery and network failure modes before they are needed would reduce development speed without improving product intelligence.

Therefore:

```text
Logical separation now
Physical separation later when justified
```

A bounded context can later be extracted into a service without changing its public domain contract.

---

# 6. Primary Database — PostgreSQL

## Decision

PostgreSQL is the primary operational database.

## Why

Hamoon requires:

- strong transactions
- relational integrity
- versioned relationships
- temporal queries
- JSON where selectively useful
- indexing
- audit/query flexibility
- analytical compatibility
- mature operational tooling

Core domain entities remain relational.

JSON storage is permitted for:

- structured AI output snapshots
- external payload snapshots
- versioned metadata
- flexible evidence metadata

but core business relationships must not be hidden in generic JSON blobs.

---

# 7. Temporal Data Strategy

V1 uses explicit application-level temporal/version tables.

Example:

```text
household_facts
current_accepted_facts
accepted_state_changes
pgor_snapshots
human_decisions
referral_events
```

We do not depend on database-specific temporal-table magic as the sole historical model.

Reason:

- domain semantics remain explicit
- easier audit
- easier replay
- easier migration
- less vendor lock-in

---

# 8. Persistence Layer

## Decision

Use:

```text
SQLAlchemy
Alembic
```

Rules:

- ORM entities are not domain objects by definition.
- Domain layer must not depend on FastAPI.
- Database transaction boundaries live in application/infrastructure layer.
- migrations are version-controlled.
- reference data such as PGOR definitions/formula versions are seeded/versioned.

---

# 9. API Contracts

FastAPI/Pydantic schemas will implement the contracts from:

```text
HAMOON_API_CONTRACTS_V1.md
```

Authoritative public interfaces:

```text
REST API
Domain Events
Integration Contracts
```

Database schema is not an integration contract.

---

# 10. Event Reliability — Transactional Outbox

Every important domain transaction writes:

```text
Domain State
+
Outbox Event
```

in the same database transaction.

Then:

```text
Outbox Publisher
→ NATS JetStream
```

This avoids:

```text
DB committed
but event publish failed
```

dual-write inconsistency.

---

# 11. Event Backbone — NATS JetStream

## Decision

Use NATS JetStream as the V1 event backbone.

## Why

Hamoon needs:

- durable event delivery
- consumer groups
- replay
- lightweight operations
- low latency
- at-least-once semantics
- scalable event consumers

It is sufficient for:

- projections
- work queue triggers
- AI feature invalidation
- learning signal generation
- provider integration workflows
- admin analytics feeds

The system still treats PostgreSQL domain state as operational source of truth.

---

# 12. Event Semantics

Baseline:

```text
delivery = at least once
consumer = idempotent
ordering = per aggregate where needed
```

Consumers persist processed event IDs or equivalent deduplication state.

---

# 13. AI Runtime

## Decision

AI runs in a dedicated logical module/runtime:

```text
Intelligence Runtime
```

built in Python.

It is accessed through an internal:

```text
AI Gateway
```

Domain modules do not call external model providers directly.

---

# 14. AI Gateway Responsibilities

```text
model routing
provider adapters
structured output enforcement
timeouts
retries
trace IDs
model version capture
prompt/policy version capture
token/cost telemetry
safety/guardrail hooks
failure normalization
```

The gateway hides vendor-specific APIs from domain logic.

---

# 15. Model Provider Abstraction

Interface concept:

```text
AIProvider
  generate_structured(...)
  generate_text(...)
  embed(...)          // if later required
```

Domain use case:

```text
GenerateDiagnosis
```

must not become:

```text
CallVendorSpecificModel(...)
```

Provider replacement should not change Diagnosis domain logic.

---

# 16. PGOR Engine Boundary

PGOR is implemented as a deterministic Python package/module.

Allowed dependencies:

- numeric/decimal standard libraries
- versioned PGOR definitions
- accepted observations

Forbidden dependencies in calculation path:

- LLM
- remote model call
- vector database
- web search
- generative inference

Contract:

```text
Inputs + Version
→ deterministic PGOR Snapshot
```

---

# 17. Intelligence Flow

```text
Operational DB
    ↓
Current Accepted State
    ↓
Feature Builder
    ↓
Feature Package
    ↓
AI Gateway
    ↓
Model Provider Adapter
    ↓
Structured AI Decision
    ↓
Human Review
    ↓
Domain Decision
    ↓
Outcome
    ↓
Learning Signal
```

---

# 18. AI Output Storage

AI outputs are stored as structured, versioned decision records.

Required trace:

```text
state version
feature package
PGOR snapshot
model version
prompt/policy version
evidence refs
structured output
human decision
downstream result/outcome
```

Raw provider response may be retained only under governed diagnostic/audit policy.

---

# 19. Embeddings / Vector Database

## Decision

No dedicated Vector DB is required for V1 core.

Reason:

Hamoon's core intelligence is primarily:

- structured household state
- PGOR
- temporal history
- evidence
- decisions
- outcomes

If semantic retrieval becomes necessary, first evaluate:

```text
PostgreSQL + vector extension
```

before introducing a separate vector platform.

This decision will be documented in a dedicated ADR if needed.

---

# 20. Cache

No mandatory distributed cache in the first implementation.

Introduce Redis or equivalent only after a measured need such as:

- hot projection reads
- short-lived distributed coordination
- rate limiting
- ephemeral job state

Cache never becomes source of truth.

---

# 21. Object Storage

Evidence binaries are stored outside PostgreSQL.

Interface:

```text
EvidenceStorage
  put()
  get_authorized_reference()
  delete_by_policy()
```

The concrete cloud/storage vendor remains an ADR decision.

Database stores:

- metadata
- storage reference
- integrity hash
- classification
- audit references

---

# 22. Search

V1 starts with PostgreSQL-supported operational search.

A separate search engine is introduced only if measured requirements justify:

- large-scale full-text search
- complex faceting
- cross-domain indexing

Authorization must remain server-enforced regardless of search technology.

---

# 23. Async Processing

V1 workers consume NATS events for:

- projections
- notifications
- provider dispatch
- feature refresh
- learning signal creation
- background AI tasks
- integration processing

Long-running durable orchestration may later use a workflow engine.

---

# 24. Workflow Engine Decision Deferred

Referral and human-review flows can become long-running.

However, workflow engine selection is not part of ADR-001.

A later ADR will compare:

```text
Temporal
vs
event/state-machine orchestration
```

after the first workflow backlog is finalized.

---

# 25. Repository Structure

Proposed:

```text
src/
  hamoon/
    app/
      api/
      config/
      security/

    domains/
      household/
      family_data/
      assessment/
      pgor/
      diagnosis/
      prescription/
      intervention/
      provider/
      referral/
      outcome/
      intelligence/
      learning/
      audit/
      integration/

    infrastructure/
      db/
      events/
      ai/
      storage/
      observability/

    shared/
      ids/
      time/
      errors/
      contracts/

tests/
  unit/
  integration/
  contract/
  e2e/

migrations/
docs/
```

---

# 26. Domain Module Structure

Example:

```text
domains/referral/
  domain/
    entities.py
    value_objects.py
    rules.py
    events.py

  application/
    commands.py
    queries.py
    handlers.py

  ports/
    repositories.py
    providers.py

  infrastructure/
    repositories.py

  api/
    schemas.py
    routes.py
```

Dependency direction:

```text
API
→ Application
→ Domain
← Infrastructure through ports
```

---

# 27. Testing Strategy

## Unit

- PGOR calculation
- state transitions
- authorization policies
- domain rules
- AI output validation

## Integration

- PostgreSQL repositories
- outbox
- NATS consumers
- provider adapters
- object storage adapters

## Contract

- API schemas
- event schemas
- provider contracts
- AI structured outputs

## E2E

```text
Household
→ PGOR
→ Diagnosis
→ Prescription
→ Referral
→ Result
→ Outcome
```

---

# 28. AI Evaluation Is Part of Delivery

AI feature completion requires:

```text
implementation
+ structured output schema
+ evaluation dataset
+ evaluation metrics
+ human review behavior
+ traceability
```

A prompt/model integration without Evaluation is not considered done.

---

# 29. Observability Stack Contract

Concrete vendor deferred.

Required interfaces:

- structured logs
- metrics
- distributed traces
- correlation IDs
- AI inference telemetry
- event consumer lag
- database health
- outbox backlog
- provider delivery health

OpenTelemetry-compatible instrumentation is preferred.

---

# 30. Configuration

Environment-driven typed configuration.

Categories:

```text
database
event bus
identity
AI provider adapters
object storage
observability
feature flags
integration endpoints
```

Secrets must come from a secret-management mechanism, not committed configuration.

---

# 31. Deployment Units V1

Initial physical deployment may be:

```text
hamoon-api
hamoon-worker
hamoon-ai-worker
postgres
nats
```

Logical domain boundaries remain inside application code.

The AI worker can scale separately from API workers.

---

# 32. Why Separate AI Worker

AI inference differs from request/response API workloads:

- variable latency
- external provider dependency
- potentially longer jobs
- independent concurrency limits
- independent cost controls
- separate retry policy

Therefore background intelligence work can use a distinct worker process even within a modular-monolith codebase.

---

# 33. Synchronous vs Async AI

Use synchronous AI only where user experience requires immediate response and latency is acceptable.

Use asynchronous operation for:

- heavier diagnosis generation
- batch evaluation
- provider analysis
- learning/evaluation pipelines

API can return:

```text
202 Accepted
operation_id
```

when asynchronous.

---

# 34. Security Boundary

Application runtime and AI runtime use separate service identities.

AI Runtime receives only authorized feature/evidence packages.

No unrestricted database credentials for AI worker.

Preferred flow:

```text
AI Worker
→ approved repository/service interface
→ minimized data
```

---

# 35. Database Access Policy

Only backend services access PostgreSQL directly.

Forbidden:

- frontend direct DB access
- provider direct DB access
- external system direct DB write
- model vendor direct DB access

---

# 36. Development Environments

```text
local
test
stage
production
```

must support equivalent contracts.

Local development may run PostgreSQL and NATS through containers.

---

# 37. Schema Migration Policy

- Alembic migrations committed to repo
- forward migration tested
- destructive migration reviewed
- reference seed versioning explicit
- production migration separated from app startup if risk warrants
- no auto schema mutation by ORM

---

# 38. Reference Data

Versioned reference/config data:

- PGOR definitions
- scoring scales
- formula versions
- event schema versions
- outcome codes
- referral states
- learning signal types

must be managed as code/data migration artifacts.

---

# 39. Technology We Intentionally Do Not Adopt Yet

Not mandatory for V1:

- Kubernetes
- Kafka
- separate vector database
- Elasticsearch/OpenSearch
- separate graph database
- multiple microservices
- data lake
- online feature store
- real-time model retraining

These may be introduced only through later ADRs when a concrete requirement justifies them.

---

# 40. Consequences

## Positive

- one primary language for product + AI
- strong relational consistency
- lower operational complexity
- explicit event architecture
- scalable AI workers
- future service extraction possible
- traceability preserved
- no premature infrastructure sprawl

## Trade-offs

- modular boundaries require discipline inside one codebase
- NATS introduces an additional operational component
- PostgreSQL carries several responsibilities in V1
- future high-scale analytics may require separate data infrastructure
- durable workflow requirements may require another platform later

---

# 41. Guardrails

1. No direct model calls from domain modules.
2. No LLM in PGOR calculation path.
3. No direct provider DB access.
4. No cross-module table mutation.
5. No event publish outside Outbox for domain transactions.
6. No AI decision without model/version trace.
7. No production prompt/formula/model change without versioning.
8. No microservice extraction without an ADR and measurable reason.
9. No new database technology without a concrete query/scale requirement.
10. No training pipeline directly against uncontrolled production tables.

---

# 42. Acceptance Criteria

ADR-001 is implemented when:

- FastAPI application skeleton exists.
- bounded-context package structure exists.
- PostgreSQL connection/migration setup exists.
- SQLAlchemy repositories follow module boundaries.
- outbox table and publisher exist.
- NATS JetStream development setup exists.
- PGOR engine exists as deterministic module.
- AI Gateway interface exists.
- one model-provider adapter can be plugged in without domain dependency.
- API/worker/AI-worker can run as separate processes.
- tracing/correlation IDs flow across API and events.
- tests cover one end-to-end vertical slice.

---

# 43. First Vertical Slice

Recommended first implemented slice:

```text
Create Household
→ Record PGOR Observation
→ Calculate PGOR
→ Persist Snapshot
→ Emit PGORSnapshotCalculated
→ Build Feature Package
→ Generate Structured Diagnosis Proposal
→ Human Confirm/Modify
→ Persist Decision Trace
→ Emit Learning Signal
```

This slice validates both classical backend and AI-first architecture before referral integrations are built.

---

# 44. Next ADRs

```text
ADR-002 — Repository / Project Structure & Engineering Standards
ADR-003 — Identity Provider & Authentication
ADR-004 — Evidence/Object Storage
ADR-005 — Durable Workflow Orchestration
ADR-006 — AI Provider Strategy & Model Routing
ADR-007 — Observability Stack
ADR-008 — Deployment Platform
```

---

# 45. Next Product Engineering Stage

After the minimum ADR set is accepted:

```text
Technical
→ Product Backlog
→ Sprint 1
→ Code
```

The first backlog should be organized around vertical business/AI slices, not infrastructure-only epics.
