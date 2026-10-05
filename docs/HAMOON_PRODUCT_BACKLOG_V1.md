# Hamoon — Product Backlog v1

> وضعیت: Scrum / Product Backlog Baseline v1  
> دامنه: اولین Backlog اجرایی هامون پس از تثبیت Business + Technical Architecture  
> اصل: **Backlog بر Vertical Sliceهای Business + AI ساخته می‌شود؛ نه بر اساس لایه‌های جداگانه Infrastructure.**
>
> وابسته به:
> - `HAMOON_AI_ARCHITECTURE_BASELINE.md`
> - `HAMOON_TECHNICAL_ARCHITECTURE_V1.md`
> - `HAMOON_DATA_MODEL_V1.md`
> - `HAMOON_PGOR_ENGINE_SPEC_V1.md`
> - `HAMOON_API_CONTRACTS_V1.md`
> - `HAMOON_EVENT_CONTRACTS_V1.md`
> - `HAMOON_SECURITY_RBAC_V1.md`
> - `ADR-001-HAMOON-CORE-STACK.md`
> - `ADR-002-HAMOON-REPOSITORY-ENGINEERING-STANDARDS.md`
> - `ADR-003-HAMOON-IDENTITY-AUTHENTICATION.md`
> - `ADR-004-HAMOON-EVIDENCE-OBJECT-STORAGE.md`
> - `ADR-005-HAMOON-WORKFLOW-ORCHESTRATION.md`
> - `ADR-006-HAMOON-AI-PROVIDER-STRATEGY.md`
> - `ADR-007-HAMOON-OBSERVABILITY.md`
> - `ADR-008-HAMOON-DEPLOYMENT-PLATFORM.md`

---

# 1. Product Goal v1

نسخه اول Hamoon باید بتواند یک Household را از وضعیت داده خام به یک حلقه تصمیم‌یار هوشمند قابل پیگیری برساند:

```text
Household
→ Accepted State
→ Assessment
→ PGOR
→ AI Diagnosis
→ Human Review
→ Prescription
→ Provider Match
→ Referral
→ Provider Result
→ Re-assessment
→ Outcome
→ Learning Signal
```

هدف V1 ساخت «ماشین تصمیم و یادگیری» است، نه تکمیل همه صفحات یا همه integrationها.

---

# 2. Priority Model

Priority:

```text
P0 = Core path / release blocker
P1 = Required for operational pilot
P2 = Important after core pilot
P3 = Later optimization
```

Backlog order بر اساس dependency و Vertical Slice تنظیم می‌شود.

---

# 3. Epic Map

```text
E0  Engineering Foundation
E1  Identity & Access
E2  Household & Temporal Data
E3  Assessment & PGOR
E4  AI Diagnosis + Human Review
E5  Prescription & Intervention
E6  Provider Matching & Referral
E7  Provider Result & Re-assessment
E8  Outcome & Learning
E9  Evidence
E10 Work Queue & Timeline
E11 Admin / Data / Machine Health
E12 Quality / Security / Observability
```

---

# 4. E0 — Engineering Foundation

## PB-001 — Repository Bootstrap
Priority: P0

**As engineering system**, we need an executable repository skeleton so that all later slices share the same boundaries and CI rules.

Acceptance Criteria:
- `src/hamoon` structure exists.
- FastAPI app starts.
- `/health/live` and `/health/ready` exist.
- `pyproject.toml` and dependency lock exist.
- Ruff, type checking and pytest commands exist.
- local config loader exists.
- no business logic in bootstrap.

Dependencies:
- ADR-001
- ADR-002

---

## PB-002 — Local Infrastructure Stack
Priority: P0

Acceptance Criteria:
- Docker Compose runs PostgreSQL, NATS, Temporal, Keycloak, MinIO.
- API can connect to PostgreSQL.
- NATS health check passes.
- Temporal worker can connect.
- MinIO test bucket exists.
- local FakeAIProvider is default.
- one command starts core local stack.

---

## PB-003 — CI Baseline
Priority: P0

Acceptance Criteria:
- lint
- type-check
- unit tests
- contract tests
- migration checks
- container build

run on pull requests.

---

## PB-004 — Request / Correlation Context
Priority: P0

Acceptance Criteria:
- every API request has request_id.
- correlation_id is created or propagated.
- structured logs contain request/correlation IDs.
- context can propagate into Domain Event and Temporal Activity.

---

# 5. E1 — Identity & Access

## PB-010 — OIDC Login Integration
Priority: P0

Acceptance Criteria:
- Keycloak dev realm exists.
- Authorization Code + PKCE works.
- API validates issuer/audience/signature/expiry.
- authenticated subject maps to internal Actor/UserAccount.
- Hamoon stores no password.

---

## PB-011 — Authorization Context
Priority: P0

Acceptance Criteria:
- actor_id
- actor_type
- organization_id
- unit_id
- roles
- token scopes

are available to application layer.

---

## PB-012 — Caseworker Resource Scope
Priority: P0

Acceptance Criteria:
- caseworker can read assigned household.
- caseworker cannot read unauthorized household.
- assignment is resolved server-side.
- authorization failure leaks no protected metadata.

---

## PB-013 — Service Identities
Priority: P1

Acceptance Criteria:
- worker-core identity exists.
- worker-ai identity exists.
- provider identity model exists.
- external integration identity model exists.
- credentials are environment-specific.

---

# 6. E2 — Household & Temporal Data

## PB-020 — Create Household
Priority: P0

User Story:

> As a caseworker, I can create a household case so that assessment can begin.

Acceptance Criteria:
- Household ID generated.
- case_code stored.
- lifecycle = DRAFT.
- caseworker assignment stored.
- HouseholdCreated event emitted.
- audit entry created.

---

## PB-021 — Household Workspace Read Model
Priority: P0

Acceptance Criteria:
- endpoint returns household summary.
- current PGOR slot exists even when empty.
- current diagnosis/prescription/referrals slots exist.
- no direct cross-domain writes through projection.

---

## PB-022 — Record Household Fact
Priority: P0

Acceptance Criteria:
- new fact is immutable.
- effective_at and recorded_at are separate.
- source_id required.
- actor recorded.
- HouseholdFactRecorded event emitted.
- raw data is not automatically treated as valid merely because source is authorized.

---

## PB-023 — Correct Fact
Priority: P0

Acceptance Criteria:
- old fact preserved.
- new fact version created.
- supersedes relation stored.
- correction reason required.
- audit produced.
- optimistic concurrency enforced.

---

## PB-024 — Dispute Fact
Priority: P0

Acceptance Criteria:
- disputed status/relation recorded.
- reason/evidence can be attached.
- unresolved dispute visible to assessment/PGOR readiness logic.
- no silent overwrite.

---

## PB-025 — Current Accepted State
Priority: P0

Acceptance Criteria:
- accepted-state projection exists.
- resolution command requires authorized human.
- CurrentAcceptedStateChanged event emitted.
- historical facts remain unchanged.
- AI cannot invoke resolve permission.

---

# 7. E3 — Assessment & PGOR

## PB-030 — Seed PGOR Definition v1
Priority: P0

Acceptance Criteria:
- P/G/O/R variables seeded.
- dimensions seeded.
- indicators seeded.
- definition version is explicit.
- seed data matches approved PGOR specification.

---

## PB-031 — Start Assessment
Priority: P0

Acceptance Criteria:
- BASELINE assessment can be created.
- definition version is pinned.
- assessment version exists.
- AssessmentStarted event emitted.

---

## PB-032 — Record Indicator Observation
Priority: P0

Acceptance Criteria:
- score 0..100 validated.
- source is required.
- effective_at is stored.
- observation is versioned.
- IndicatorObservationRecorded event emitted.

---

## PB-033 — Observation Correction
Priority: P0

Acceptance Criteria:
- no update-in-place.
- new observation version created.
- old version remains traceable.
- evidence links preserved.

---

## PB-034 — Assessment Readiness
Priority: P0

Acceptance Criteria:
- required indicator completeness evaluated.
- unresolved required conflicts block OFFICIAL calculation.
- missing != zero.
- PREVIEW and OFFICIAL are separate.

---

## PB-035 — Deterministic PGOR Engine
Priority: P0

Acceptance Criteria:
- normalization works.
- dimensions aggregate deterministically.
- P/G/O/R calculate deterministically.
- formula version is required.
- coefficient validation exists.
- E calculated server-side.
- bottleneck generated.
- no LLM dependency.
- reproducibility tests pass.

---

## PB-036 — Persist PGOR Snapshot
Priority: P0

Acceptance Criteria:
- snapshot immutable.
- engine/definition/scoring/formula versions stored.
- input observation references stored.
- fingerprint stored.
- PGORSnapshotCalculated event emitted.

---

## PB-037 — PGOR Trace
Priority: P1
Implementation: COMPLETE. Authorized caseworkers/managers can inspect the immutable historical
input trace of a persisted PGOR snapshot, including exact observation IDs/versions, definition
metadata, raw and normalized scores, engine/scoring versions and input fingerprint. The trace
is read-only and never recomputes PGOR; the live household workspace renders this persisted trace.

Acceptance Criteria:
- authorized user can inspect which observations and versions produced the snapshot.
- no recomputation required for historical trace.

---

# 8. E4 — AI Diagnosis + Human Review

## PB-040 — AI Gateway Interface
Priority: P0

Acceptance Criteria:
- provider-agnostic interface exists.
- FakeAIProvider exists.
- one real adapter can be plugged in.
- Domain imports no vendor SDK.

---

## PB-041 — Diagnosis Output Schema v1
Priority: P0

Acceptance Criteria:
- versioned JSON Schema exists.
- diagnosis item types defined.
- evidence refs supported.
- rationale is structured.
- invalid free-text response cannot create Diagnosis entity.

---

## PB-042 — Feature Package Builder
Priority: P0

Acceptance Criteria:
- consumes accepted state + PGOR + relevant history only.
- PII minimized.
- feature package version stored.
- evidence refs recorded.
- feature package is immutable.

---

## PB-043 — Generate Diagnosis Proposal
Priority: P0

Acceptance Criteria:
- request pins routing/model/prompt/output schema versions.
- AI output validated.
- AIDecision persisted.
- DiagnosisGenerated event emitted.
- diagnosis status = UNDER_REVIEW.
- no automatic acceptance.

---

## PB-044 — Human Confirm Diagnosis
Priority: P0

Acceptance Criteria:
- authorized caseworker can confirm.
- human decision stored separately.
- DiagnosisConfirmed event emitted.
- learning signal generated.
- AI decision remains immutable.

---

## PB-045 — Human Modify Diagnosis
Priority: P0

Acceptance Criteria:
- original AI proposal preserved.
- modified structured items stored.
- reason code/text stored.
- DiagnosisModified event emitted.
- learning signal records change.

---

## PB-046 — Human Replace Diagnosis
Priority: P1

Acceptance Criteria:
- human replacement stored as final accepted diagnosis.
- machine diagnosis remains traceable.
- reason required.
- LearningSignalCreated.

---

# 9. E5 — Prescription & Intervention

## PB-050 — Prescription Output Schema v1
Priority: P0

Acceptance Criteria:
- intervention target
- priority
- rationale
- success criteria
- review schedule
- evidence/diagnosis refs

are structured.

---

## PB-051 — Generate Prescription Proposal
Priority: P0

Acceptance Criteria:
- accepted diagnosis required.
- AI trace stored.
- structured output validated.
- PrescriptionGenerated event emitted.
- status requires human review.

---

## PB-052 — Approve / Modify Prescription
Priority: P0

Acceptance Criteria:
- human decision separate.
- accepted items explicit.
- modification reason captured.
- learning signal emitted.

---

## PB-053 — Activate Intervention
Priority: P0

Acceptance Criteria:
- only accepted prescription item can activate.
- Intervention entity created.
- target PGOR variable retained.
- InterventionActivated event emitted.

---

# 10. E6 — Provider Matching & Referral

## PB-060 — Provider Registry
Priority: P0

Acceptance Criteria:
- provider
- services
- coverage
- capacity snapshot
- active status

are queryable.

---

## PB-061 — Rule-based Provider Matching v1
Priority: P0

Matching inputs:

```text
Need
+ Eligibility
+ Service Type
+ Coverage
+ Capacity
```

Acceptance Criteria:
- candidate list returned.
- eligibility reason available.
- no hidden winner.
- ProviderMatchGenerated event emitted.

---

## PB-062 — Human Provider Selection
Priority: P0

Acceptance Criteria:
- caseworker explicitly chooses provider.
- human decision stored.
- ProviderSelectedByHuman event emitted.
- AI/runtime cannot select autonomously.

---

## PB-063 — Create Referral
Priority: P0

Acceptance Criteria:
- referral tied to intervention/provider/service.
- shared data items are explicit/minimal.
- status = READY.
- ReferralCreated event emitted.

---

## PB-064 — Send Referral
Priority: P0

Acceptance Criteria:
- human authorization required.
- data sharing audit produced.
- provider payload minimized.
- idempotency key used.
- status transition validated.
- ReferralSent event emitted.

---

## PB-065 — Referral State Machine
Priority: P0

Supported operational states:

```text
READY
SENT
ACCEPTED
WAITING_CAPACITY
NEEDS_INFORMATION
IN_PROGRESS
COMPLETED
REJECTED
NO_RESPONSE
CANCELLED
```

Acceptance Criteria:
- invalid transitions rejected.
- each transition creates event/history.
- optimistic concurrency enforced.

---

## PB-066 — ReferralWorkflow
Priority: P0
Implementation: COMPLETE in the provider-neutral runtime, including idempotent dispatch, callback/cancellation signals, timeout → NO_RESPONSE, and REFERRAL_FOLLOWUP work-queue materialization; real external Provider endpoint/credential verification remains deployment-specific.

Acceptance Criteria:
- Temporal workflow starts by referral ID.
- provider dispatch activity idempotent.
- callback can signal workflow.
- timeout creates NO_RESPONSE/follow-up behavior.
- cancellation works.
- workflow stores minimal PII.

---

# 11. E7 — Provider Result & Re-assessment

## PB-070 — Provider Callback Inbox
Priority: P0
Implementation: COMPLETE. Provider OIDC identity is scoped to the mapped Provider, `external_event_id` is idempotent per Provider, callback schema version `1` is enforced at both API and application boundaries, and the integration endpoint maps the callback into a Domain Command before persistence.

Acceptance Criteria:
- provider identity verified.
- external_event_id idempotent.
- payload schema validated.
- direct DB write impossible.
- callback maps to Domain Command.

---

## PB-071 — Provider Result
Priority: P0

Acceptance Criteria:
- result separate from Hamoon Outcome.
- provider result linked to referral.
- evidence can be attached.
- ProviderResultReceived event emitted.

---

## PB-072 — Create Re-assessment
Priority: P0

Acceptance Criteria:
- new assessment instance created.
- previous PGOR snapshot unchanged.
- reason/intervention linked.
- ReassessmentStarted event emitted.

---

## PB-073 — Reassessment Workflow
Priority: P1

Acceptance Criteria:
- review schedule policy version stored.
- Temporal timer supports future reassessment.
- work item created when due.
- completion signals workflow.
- post-intervention PGOR generated.

---

# 12. E8 — Outcome & Learning

## PB-080 — Prepare Outcome
Priority: P0

Inputs:

```text
pre PGOR snapshot
post PGOR snapshot
intervention
provider result
```

Acceptance Criteria:
- deltas calculated.
- no default causal claim.
- OutcomePrepared event emitted.
- human review required.

---

## PB-081 — Human Confirm / Modify Outcome
Priority: P0

Acceptance Criteria:
- classification explicit.
- reason captured on modification.
- OutcomeConfirmed/Modified event emitted.
- provider result remains separate.

---

## PB-082 — Learning Signal
Priority: P0

Acceptance Criteria:
- signals created from diagnosis/prescription/provider/outcome decisions.
- references AI decision + human decision where relevant.
- no automatic production retraining.
- signal quality status exists.

---

## PB-083 — Decision Trace
Priority: P0
Implementation: COMPLETE. DecisionTrace persists Accepted State context version, PGOR snapshot, feature package, AI decision, human decision, prescription/intervention/referral/provider-result/outcome links and the resulting learning signal. AI persistence rejects stale Accepted State context.

Acceptance Criteria:
- household state version
- PGOR snapshot
- feature package
- AI decision
- human decision
- intervention
- referral
- provider result
- outcome
- learning signal

are connected.

---

# 13. E9 — Evidence

## PB-090 — Evidence Upload Init
Priority: P1
Implementation: COMPLETE. Household authorization and sensitivity policy gate metadata creation; upload capability is short-lived and signed; opaque storage keys contain no user PII.

Acceptance Criteria:
- authorization checked.
- Evidence metadata created.
- signed short-lived upload target generated.
- object key contains no PII.

---

## PB-091 — Evidence Finalize / Integrity
Priority: P1
Implementation: COMPLETE at the application/runtime contract. Object existence, size and SHA-256 are verified and Production requires a remote HTTPS scanner. Real external Production scanner/storage evidence remains deployment-specific.

Acceptance Criteria:
- existence verified.
- size verified.
- SHA-256 stored.
- scan state begins.
- mismatch rejected.

---

## PB-092 — Evidence Availability / Quarantine
Priority: P1
Implementation: COMPLETE. Evidence becomes AVAILABLE only after clean validation/scan; infected evidence is quarantined and unavailable to normal download paths; lifecycle events are emitted.

Acceptance Criteria:
- AVAILABLE only after validation/scan policy.
- quarantined file cannot be downloaded.
- evidence lifecycle events emitted.

---

## PB-093 — Authorized Evidence Download
Priority: P1
Implementation: COMPLETE. Household assignment and sensitivity scope are checked server-side; access uses short-lived signed capability tokens and issuance is audited.

Acceptance Criteria:
- case scope checked.
- sensitivity policy checked.
- short-lived access.
- sensitive access audited.

---

# 14. E10 — Work Queue & Timeline

## PB-100 — Household Timeline
Priority: P1
Implementation: COMPLETE. The caseworker-scoped household read model returns a deterministic,
PII-minimal ordered timeline across facts, assessments, PGOR, diagnosis, prescription,
referral, provider result and Outcome. Provider free text is excluded from the projection,
and the live React household workspace renders the backend timeline.

Acceptance Criteria:
- facts
- assessments
- PGOR
- diagnosis
- prescription
- referral
- provider result
- outcome

appear as ordered timeline projections.

---

## PB-101 — Caseworker Work Queue
Priority: P0
Implementation: COMPLETE. Work items are source-linked and idempotent, queue visibility is constrained by active household assignment, unassigned tasks can be claimed, due/overdue is part of the API read model, and diagnosis/prescription/referral/reassessment/outcome/data-completion/conflict transitions create or complete their operational projections.

Initial task types:

```text
DIAGNOSIS_REVIEW
PRESCRIPTION_REVIEW
REFERRAL_FOLLOWUP
REASSESSMENT_DUE
OUTCOME_REVIEW
DATA_COMPLETION
CONFLICT_RESOLUTION
```

Acceptance Criteria:
- only authorized tasks visible.
- due/overdue supported.
- source entity linked.
- domain event drives task creation.

---

# 15. E11 — Admin / Data / Machine Health

## PB-110 — Data Health Projection
Priority: P1
Implementation: COMPLETE. The persisted admin projection now exposes missing-required-data work,
unresolved fact conflicts, incomplete assessments, objectively expired accepted-source facts,
and unresolved integration failures across provider inbox/dispatch and durable outbox state.
The ADMIN/SECURITY_AUDITOR workspace renders the live projection without mutating product state.

Metrics:
- missing required data
- unresolved conflicts
- incomplete assessments
- stale source data
- integration failures

---

## PB-111 — Machine Health Projection
Priority: P1
Implementation: COMPLETE. Diagnosis human-review outcomes are counted only in DIAGNOSIS context;
PII-safe durable runtime events capture AI schema, inference and routing failures; real AI fallback
incidents and open workflow-generated operational work are projected separately. The live admin
workspace is authorized for ADMIN/SECURITY_AUDITOR and remains read-only.

Metrics:
- diagnosis confirms/modifies/replaces
- schema failures
- AI fallback
- inference failures
- workflow backlog

---

## PB-112 — Empowerment Overview
Priority: P2
Implementation: COMPLETE. MANAGER/ADMIN users with an explicit OIDC unit_id receive a
de-identified unit-scoped aggregate over the latest OFFICIAL PGOR snapshot per Household.
The projection exposes numeric P/G/O/R/E distribution summaries, persisted E-band counts,
persisted bottleneck counts (including ties), and reviewed Outcome classification counts.
Missing unit scope is denied server-side and no Household drill-down is exposed.

Includes:
- PGOR distribution
- E bands
- bottlenecks
- outcome counts

Aggregated by authorized organizational scope.

---

# 16. E12 — Quality / Security / Observability

## PB-120 — Structured Logging + OpenTelemetry
Priority: P0
Implementation: COMPLETE. Request/correlation context propagates through durable events/NATS and long-running Temporal workflow inputs; AI Gateway emits a PII-safe custom span with the same business correlation. Structured logs are sanitized, OpenTelemetry instruments FastAPI/SQLAlchemy/HTTPX, and Stage Admission proves OTLP trace/log transport for the exact promoted release.

Acceptance Criteria:
- request/event/workflow/AI traces correlate.
- raw PII excluded.
- OpenTelemetry initialized.

---

## PB-121 — Core Metrics
Priority: P0
Implementation: COMPLETE. Production Monitoring requires PII-safe metric families covering API, PostgreSQL, durable outbox/NATS delivery, exact-release Temporal worker health, deterministic PGOR, structured AI gateway execution, provider dispatch and security denials.

Must include:
- API
- DB
- outbox
- NATS
- Temporal
- PGOR
- AI
- provider
- security

---

## PB-122 — Security Regression Suite
Priority: P0
Implementation: COMPLETE. CI has an explicit six-boundary acceptance contract covering unauthorized household access, Provider isolation, AI/service authority restrictions, Accepted State human authorization, sensitive Evidence scope and PII-safe structured logging, plus the broader security/provider-result suites.

Must test:
- unauthorized household
- provider isolation
- AI authority restrictions
- accepted-state authorization
- evidence scope
- no PII leakage in logs

---

## PB-123 — Core E2E Test
Priority: P0
Implementation: COMPLETE. CI executes the full application/domain golden path from real Household creation and human Accepted State resolution through deterministic pre/post PGOR, AI diagnosis + human review, prescription + intervention, rule-based Provider Match + explicit human Provider selection/referral, sent referral + Provider Result, version-pinned reassessment, Outcome review and the resulting Learning Signal. Infrastructure persistence is isolated behind in-memory repositories in this acceptance test; PostgreSQL/NATS/MinIO and exact-image runtime boundaries remain covered by their dedicated integration, release and Stage gates.

Scenario:

```text
Create Household
→ Record Facts
→ Assessment
→ PGOR
→ AI Diagnosis
→ Human Confirm/Modify
→ Prescription
→ Intervention
→ Provider Match
→ Referral
→ Provider Result
→ Reassessment
→ Outcome
→ Learning Signal
```

---

# 17. Release Slices

## Slice A — Intelligence Core

```text
Household
→ Fact
→ Accepted State
→ Assessment
→ PGOR
→ AI Diagnosis
→ Human Review
→ Learning Signal
```

Release target:
Internal Stage.

---

## Slice B — Prescription to Referral

```text
Accepted Diagnosis
→ Prescription
→ Intervention
→ Match
→ Select
→ Referral
→ ReferralWorkflow
```

Release target:
Controlled pilot.

---

## Slice C — Outcome Loop

```text
Provider Result
→ Re-assessment
→ PGOR
→ Outcome
→ Learning Signal
```

Release target:
Closed-loop pilot.

---

# 18. Recommended Sprint Order

## Sprint 1 — Executable Intelligence Core

Target:

```text
Household
→ Assessment
→ PGOR
→ AI Diagnosis Proposal
→ Human Review
→ Learning Signal
```

Candidate PBIs:

```text
PB-001 Repository Bootstrap
PB-002 Local Infrastructure Stack
PB-003 CI Baseline
PB-004 Correlation Context

PB-010 OIDC Login Integration
PB-011 Authorization Context

PB-020 Create Household
PB-022 Record Household Fact
PB-025 Current Accepted State

PB-030 Seed PGOR Definition
PB-031 Start Assessment
PB-032 Record Indicator Observation
PB-034 Assessment Readiness
PB-035 Deterministic PGOR Engine
PB-036 Persist PGOR Snapshot

PB-040 AI Gateway Interface
PB-041 Diagnosis Output Schema
PB-042 Feature Package Builder
PB-043 Generate Diagnosis Proposal
PB-044 Human Confirm Diagnosis
PB-045 Human Modify Diagnosis

PB-082 Learning Signal
PB-083 Decision Trace

PB-120 OpenTelemetry Baseline
PB-122 Security Regression Baseline
```

---

# 19. Sprint 1 Exit Criteria

Sprint 1 زمانی موفق است که یک flow واقعی end-to-end در Stage/Local قابل اجرا باشد:

```text
Caseworker logs in
→ creates household
→ records/accepts required PGOR data
→ starts assessment
→ calculates deterministic PGOR
→ system creates feature package
→ AI generates structured diagnosis
→ caseworker confirms or modifies
→ decision trace persists
→ learning signal is created
```

و این flow:

- audited
- authorized
- observable
- tested
- reproducible

باشد.

---

# 20. Not in Sprint 1

عمداً خارج:

- provider referral
- Temporal ReferralWorkflow
- evidence binary upload
- outcome loop
- admin dashboard
- full analytics
- multiple AI providers
- model calibration
- prediction/simulation
- Kubernetes

---

# 21. Definition of Ready — Backlog Item

هر PBI برای ورود به Sprint باید:

- user/business value روشن داشته باشد.
- acceptance criteria داشته باشد.
- dependencies مشخص باشد.
- security impact مشخص باشد.
- data/event/API impact مشخص باشد.
- design ambiguity blocking نداشته باشد.

برای AI Item:

- input contract
- output schema
- human review behavior
- evaluation approach

نیز لازم است.

---

# 22. Definition of Done — Backlog Item

حداقل:

```text
Code
+ Unit/Integration/Contract Tests
+ Security checks
+ API/Event contract alignment
+ Observability
+ Code Review
+ Stage verification
```

برای AI:

```text
+ structured output validation
+ model/prompt/version trace
+ evaluation
+ human review path
```

---

# 23. Product Backlog Governance

هر Backlog change مهم باید یکی از این دلایل را داشته باشد:

- validated product need
- architecture dependency
- pilot evidence
- security requirement
- operational learning
- model evaluation result

Backlog نباید به فهرست درخواست‌های پراکنده تبدیل شود.

---

# 24. Next Artifact

گام بعدی:

> **HAMOON_SPRINT_1_PLAN.md**

این سند باید:
- Sprint Goal
- selected PBIs
- task breakdown
- sequence
- dependencies
- acceptance test plan
- Definition of Done
- expected code artifacts

را مشخص کند.
