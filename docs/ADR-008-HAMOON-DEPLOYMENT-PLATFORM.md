# ADR-008 — Hamoon Deployment Platform

> وضعیت: Accepted for V1  
> دامنه تصمیم: Runtime Topology, Environments, Containers, Managed Services, Network Boundaries, Release Strategy  
> وابسته به:
> - `ADR-001-HAMOON-CORE-STACK.md`
> - `ADR-003-HAMOON-IDENTITY-AUTHENTICATION.md`
> - `ADR-004-HAMOON-EVIDENCE-OBJECT-STORAGE.md`
> - `ADR-005-HAMOON-WORKFLOW-ORCHESTRATION.md`
> - `ADR-006-HAMOON-AI-PROVIDER-STRATEGY.md`
> - `ADR-007-HAMOON-OBSERVABILITY.md`
> - `HAMOON_SECURITY_RBAC_V1.md`

---

# 1. Context

Hamoon V1 باید بدون پیچیدگی عملیاتی زودهنگام، این اجزا را قابل استقرار کند:

- FastAPI API
- background workers
- AI workers
- PostgreSQL
- NATS JetStream
- Temporal
- Keycloak / OIDC
- S3-compatible evidence storage
- OpenTelemetry collector / observability exporters

هم‌زمان باید:

- DEV / STAGE / PROD جدا باشند
- PII از محیط‌های غیرProduction جدا بماند
- deployment قابل تکرار باشد
- release/rollback روشن باشد
- AI و Provider integration جدا scale شوند
- هیچ component حیاتی فقط به local disk وابسته نباشد
- Kubernetes از روز اول الزام نباشد

---

# 2. Decision Summary

برای V1:

```text
Application Packaging:
Docker / OCI containers

Production Platform Style:
Managed container platform / PaaS
not Kubernetes-first

Runtime Units:
hamoon-api
hamoon-worker-core
hamoon-worker-ai
hamoon-worker-provider

Primary Database:
Managed PostgreSQL

Event Backbone:
NATS JetStream
managed where available,
otherwise dedicated persistent service

Workflow:
Temporal Cloud preferred for Production
or isolated self-hosted Temporal where policy requires

Identity:
Managed/external enterprise IdP when available
otherwise dedicated Keycloak deployment

Evidence:
Managed S3-compatible object storage

Observability:
OpenTelemetry instrumentation
→ managed or self-hosted compatible backend

Local Development:
Docker Compose

CI/CD:
build once
promote immutable image
dev → stage → prod

Kubernetes:
deferred until scale/operational requirements justify it
```

---

# 3. Why Managed Containers Instead of Kubernetes First

Hamoon V1 already contains substantial application complexity:

- temporal household state
- PGOR
- events
- workflows
- AI
- provider integrations
- outcome/learning

Kubernetes would introduce additional operational domains:

- cluster lifecycle
- ingress
- service mesh choices
- autoscaler behavior
- persistent volume operations
- RBAC duplication
- cluster upgrades

without a demonstrated V1 requirement.

قاعده:

```text
Managed containers now
Kubernetes only when measurable need appears
```

---

# 4. Deployment Units

V1 physical processes:

## hamoon-api

مسئول:

- REST API
- authentication/authorization boundary
- commands/queries
- synchronous PGOR
- user-facing request handling

## hamoon-worker-core

مسئول:

- outbox publishing
- NATS consumers
- projections
- work queue projection
- integration processing
- learning signal generation

## hamoon-worker-ai

مسئول:

- AI Gateway execution
- long-running AI activities
- structured output validation
- model routing
- AI telemetry

## hamoon-worker-provider

مسئول:

- provider dispatch
- provider delivery retries
- provider integration activities
- provider callback-related async work

Logical codebase مشترک است، processها جدا scale می‌شوند.

---

# 5. Process Separation

Rule:

```text
same repository
same application version
different runtime role
```

مثال:

```text
HAMOON_PROCESS_ROLE=api
HAMOON_PROCESS_ROLE=worker-core
HAMOON_PROCESS_ROLE=worker-ai
HAMOON_PROCESS_ROLE=worker-provider
```

این روش از ساخت چهار codebase مستقل جلوگیری می‌کند.

---

# 6. Stateless Application Runtime

API و Workerها باید تا حد امکان stateless باشند.

Durable state در:

- PostgreSQL
- NATS JetStream
- Temporal
- object storage

قرار می‌گیرد.

Local container filesystem source of truth نیست.

---

# 7. PostgreSQL

Production:

> Managed PostgreSQL preferred.

Requirements:

- automated backups
- point-in-time recovery where available
- encryption at rest
- TLS
- monitoring
- maintenance/upgrade support
- isolated credentials
- restore testing

Hamoon database و Temporal internal database، در self-hosted mode، باید logical separation داشته باشند.

---

# 8. NATS JetStream Deployment

دو حالت قابل قبول:

## Preferred

Managed NATS/compatible service with JetStream semantics.

## Alternative

Dedicated persistent NATS deployment with:

- durable storage
- backup/restore plan
- health monitoring
- environment isolation

NATS نباید به ephemeral filesystem متکی باشد.

---

# 9. Temporal Deployment

Production preference:

```text
Temporal Cloud
```

اگر policy/data residency اجازه ندهد:

```text
self-hosted Temporal
```

با persistence مستقل و operational monitoring.

دلیل preference:

- کاهش burden عملیاتی workflow cluster
- upgrade/reliability پیچیده
- long-running workflow criticality

Domain data همچنان در PostgreSQL Hamoon است؛ Temporal source of truth Business نیست.

---

# 10. Identity Deployment

ترتیب ترجیح:

```text
Existing Enterprise OIDC IdP
→ use/federate

otherwise
→ dedicated Keycloak deployment
```

Keycloak production باید:

- database persistent
- backup
- TLS
- admin access restricted
- secrets managed
- stage/prod separated

باشد.

---

# 11. Evidence Storage

Production از managed S3-compatible/private object storage استفاده می‌کند.

Local:

```text
MinIO
```

Production rule:

- private buckets
- encrypted at rest
- signed short-lived access
- lifecycle policy
- backup/durability
- environment separation

---

# 12. Network Boundaries

Logical zones:

```text
Public Edge
  ↓
Hamoon API

Private/Internal
  ├─ PostgreSQL
  ├─ NATS
  ├─ Temporal connectivity
  ├─ workers
  ├─ Keycloak/admin endpoints
  └─ observability collectors
```

Database, NATS and internal worker ports نباید public باشند.

---

# 13. Public Endpoints

Publicly reachable only when required:

- Hamoon web/API edge
- OIDC login endpoints
- provider callback endpoint
- externally authorized integration endpoint

همه با:

- TLS
- authentication/signature
- rate limiting
- audit

---

# 14. Provider Connectivity

Provider integration ترجیحاً outbound-first باشد:

```text
Hamoon → Provider API
```

Inbound callbackها فقط endpoint محدود و authenticated دارند.

Provider هیچ network access مستقیم به internal services ندارد.

---

# 15. AI Provider Connectivity

فقط AI worker/Gateway اجازه outbound به configured AI provider endpoints دارد.

Domain API/serviceها مستقیماً provider SDK call نمی‌کنند.

Network egress policy در صورت پشتیبانی platform محدود می‌شود.

---

# 16. Environments

حداقل:

```text
LOCAL
DEV
STAGE
PROD
```

## LOCAL
Developer machine + Docker Compose.

## DEV
Shared integration environment.

## STAGE
Production-like release validation.

## PROD
Real operational workloads.

---

# 17. Environment Isolation

هر environment باید جدا داشته باشد:

- database
- NATS streams
- Temporal namespace
- identity realm/client config
- object storage bucket/prefix isolation
- secrets
- AI provider credentials
- provider sandbox/production endpoints
- observability labels/backends

---

# 18. Production Data Rule

Production PII به‌صورت پیش‌فرض به:

```text
LOCAL
DEV
STAGE
```

کپی نمی‌شود.

برای test:

- synthetic
- masked
- approved de-identified datasets

استفاده می‌شود.

---

# 19. Docker Image Strategy

هر release یک immutable image دارد.

Image tagهای mutable مثل:

```text
latest
```

برای Production source of deployment truth نیستند.

Preferred identifiers:

```text
git commit SHA
semantic application version
deployment release ID
```

---

# 20. Build Once, Promote

```text
Commit
→ CI
→ Build image once
→ Test
→ Deploy DEV
→ Promote same artifact to STAGE
→ Approve
→ Promote same artifact to PROD
```

نباید برای هر environment code متفاوت rebuild شود.

Config از environment می‌آید.

---

# 21. CI Pipeline

Minimum:

```text
lint
type-check
unit tests
contract tests
integration tests
migration checks
security/static checks
container build
image scan
```

E2E stage tests قبل از Production.

---

# 22. CD Pipeline

Deployment phases:

```text
Deploy application
→ health/readiness
→ migration compatibility check
→ smoke test
→ traffic enable
→ monitor
```

برای releaseهای حساس manual approval قبل از PROD.

---

# 23. Database Migration Strategy

Rule:

> Deployments must support safe schema transition.

Preferred sequence:

```text
expand schema
→ deploy compatible code
→ migrate data if needed
→ switch behavior
→ contract old schema later
```

Destructive migration همراه همان release اولیه ممنوع مگر کاملاً safe/approved.

---

# 24. Migration Execution

Production migration:

- explicit job/step
- visible logs
- failure stops release
- not silently run by every API replica at startup

---

# 25. Rollback

Application rollback باید به previous immutable image ممکن باشد.

Database rollback همیشه automatic فرض نمی‌شود.

به همین دلیل backward-compatible migration discipline لازم است.

---

# 26. Feature Rollout

Feature flags برای rollout کنترل‌شده مجازند.

اما versioned assets جای خود را دارند:

- formula version
- prompt version
- model version
- schema version

Feature flag نباید این versioning را دور بزند.

---

# 27. Secrets

Production secrets از secret-management facility platform یا external secret manager می‌آیند.

Examples:

- DB credentials
- NATS credentials
- OIDC client secret
- AI provider key
- provider integration secret
- object storage credentials

No secret in repository or container image.

---

# 28. Configuration

Runtime config:

```text
environment variables
+ secret references
+ versioned non-secret config
```

Startup باید required config را validate کند.

Fail fast on invalid critical config.

---

# 29. Autoscaling

API و workerها مستقل scale می‌شوند.

Signals:

## API
- request concurrency
- latency
- CPU/memory

## AI worker
- task queue backlog
- provider concurrency limits

## Provider worker
- task queue backlog
- delivery latency

Autoscaling نباید از rate limits upstream عبور کند.

---

# 30. Minimum Replicas

Production policy دقیق بعداً تعیین می‌شود، اما critical stateless services باید امکان multiple replicas داشته باشند.

Singleton application process نباید architectural requirement باشد.

---

# 31. Background Worker Safety

Multiple worker replicas باید safe باشند چون:

- NATS consumer semantics
- Temporal task queues
- idempotent activities
- DB optimistic concurrency

از duplicate side effect جلوگیری می‌کنند.

---

# 32. Health Checks

هر process:

```text
/health/live
/health/ready
```

یا equivalent worker health signal دارد.

Readiness dependency-aware است.

---

# 33. Graceful Shutdown

API/worker باید:

- stop accepting new work
- finish/hand off in-flight work
- close DB/event connections
- release resources

را پشتیبانی کند.

برای Temporal/NATS workerها shutdown graceful حیاتی است.

---

# 34. Observability Export

تمام services:

```text
OpenTelemetry
→ Collector
→ metrics/logs/traces backend
```

ارسال می‌کنند.

Concrete backend می‌تواند managed یا self-hosted باشد.

---

# 35. Reference Observability Stack

برای self-hosted/reference:

```text
Prometheus
Grafana
Loki
Tempo
OpenTelemetry Collector
```

اما application به این vendor stack قفل نیست.

---

# 36. Backup Strategy

حداقل assets:

- PostgreSQL backups
- object storage durability/backup
- Keycloak DB/config backup if self-hosted
- NATS JetStream recovery plan
- Temporal persistence recovery if self-hosted
- deployment/config manifests

---

# 37. Restore Tests

Backup بدون restore test کافی نیست.

Periodic test:

```text
restore database
restore evidence metadata/object access
rebuild projections
reconnect event/workflow services
```

---

# 38. Disaster Recovery

RPO/RTO عددی در Operations policy تعیین می‌شود.

معماری باید امکان:

- DB restore
- stateless app redeploy
- event consumer restart
- workflow continuation
- evidence recovery

را داشته باشد.

---

# 39. Region / Data Residency

Deployment environment باید region/data residency policy را enforce کند.

AI provider و object storage باید با همان policy سازگار باشند.

عدد/کشور خاص در این ADR hard-code نمی‌شود.

---

# 40. Infrastructure as Code

Production infrastructure باید reproducible باشد.

Preferred:

```text
infra/
  environments/
    dev/
    stage/
    prod/
  identity/
  observability/
```

Concrete IaC tool در bootstrap می‌تواند Terraform/OpenTofu یا platform-native config باشد.

اصل مهم:

> production infrastructure should not exist only as manual clicks.

---

# 41. Local Docker Compose

Local development profile:

```text
hamoon-api
hamoon-worker-core
hamoon-worker-ai
postgres
nats
temporal
keycloak
minio
otel-collector
```

بعضی serviceها می‌توانند optional profile باشند.

Fake AI adapter default local path است.

---

# 42. Stage Fidelity

Stage باید حداقل این‌ها را با production pattern مشترک داشته باشد:

- container images
- DB migrations
- OIDC flow
- NATS
- Temporal
- object storage contract
- observability
- AI adapter contract
- provider sandbox contract

---

# 43. Production Release Gate

قبل از PROD:

- CI green
- stage smoke/E2E green
- migration tested
- security checks passed
- configuration validated
- observability dashboards healthy
- rollback plan ready
- model/prompt/formula versions pinned

---

# 44. AI Release Independence

Application release و AI model/prompt release ممکن است جدا باشند.

اما هر AI deployment/config change باید:

- versioned
- evaluated
- approved
- auditable

باشد.

Application deployment نباید silently مدل را عوض کند مگر همان release صریحاً routing policy را تغییر دهد.

---

# 45. Formula Release Independence

PGOR formula version نیز مستقل از app binary است.

Formula activation:

```text
candidate
→ approval
→ effective_from
→ activation
```

با audit.

---

# 46. Event Contract Compatibility

Producer/consumer deployment باید backward compatibility event version را رعایت کند.

Rolling deployment نباید باعث شود consumer جدید Event قدیمی را نتواند بخواند یا برعکس.

---

# 47. Temporal Workflow Compatibility

قبل از deploy:

- replay tests
- workflow version compatibility
- running workflow migration strategy

باید بررسی شود.

---

# 48. Security

Production platform باید حداقل:

- private networking
- TLS
- environment isolation
- secret management
- restricted admin access
- audit logs
- image scanning
- dependency update process

را پشتیبانی کند.

---

# 49. Administrative Access

DB/NATS/Temporal/Object Storage admin access:

- limited
- named identities
- MFA where supported
- audited
- no shared credentials

---

# 50. No Direct Production DB Editing

Business correction باید از Hamoon Domain/API انجام شود.

Direct DB mutation فقط emergency operational procedure تحت audit و review.

---

# 51. Cost Control

V1 cost drivers:

- PostgreSQL
- Temporal
- AI inference
- object storage
- observability retention
- container runtime

AI cost telemetry باید per task class موجود باشد.

Managed service انتخاب باید هزینه را با operational risk متعادل کند.

---

# 52. Capacity Growth Path

اگر scale افزایش یابد:

```text
Vertical scale managed services
→ horizontal stateless workers/API
→ split high-load bounded context
→ dedicated analytics/search
→ Kubernetes if operational need justified
```

نه برعکس.

---

# 53. Kubernetes Trigger Conditions

Kubernetes فقط با یک یا چند نیاز واقعی:

- large number of independently deployed services
- advanced scheduling
- complex autoscaling
- strict network policies at scale
- multi-region orchestration
- platform team maturity
- PaaS limitations

در ADR جدید بررسی می‌شود.

---

# 54. Vendor Neutrality

این ADR Vendor خاص را اجبار نمی‌کند.

Deployment provider باید بتواند این contract را پوشش دهد:

- container runtime
- private networking
- managed PostgreSQL or equivalent
- secrets
- TLS/custom domain
- horizontal scaling
- observability export
- environment isolation

---

# 55. Consequences

## Positive

- lower V1 operational complexity
- reproducible containers
- managed persistence
- independent worker scaling
- no premature Kubernetes
- portability preserved
- clear release/rollback path

## Trade-offs

- some infrastructure remains multi-component
- Temporal/NATS/Keycloak require operational integration
- managed-service availability differs by region/provider
- eventual Kubernetes migration may require deployment work later

---

# 56. Guardrails

1. Production app runs from immutable container image.
2. No production business state on local disk.
3. No database/event bus public exposure.
4. No production secret in repo/image.
5. No automatic destructive migration.
6. No production PII copied to non-prod by default.
7. No AI provider call directly from arbitrary service.
8. No Kubernetes until justified by measurable need.
9. No manual-only production infrastructure.
10. No release without stage verification and observability.

---

# 57. Acceptance Criteria

ADR-008 implemented when:

- Docker image builds reproducibly.
- local Docker Compose runs core dependencies.
- DEV/STAGE/PROD configuration model exists.
- managed PostgreSQL deployment path exists.
- NATS persistent deployment exists.
- Temporal production mode selected/configured.
- OIDC/Keycloak deployment path exists.
- private object storage exists.
- secrets are externalized.
- CI builds/scans image.
- CD promotes immutable artifact.
- migrations run as explicit release step.
- stage E2E path works.
- observability receives telemetry.
- rollback procedure is documented.

---

# 58. Architecture Baseline Completion

با ADR-008، مجموعه تصمیم‌های فنی V1 شامل:

```text
ADR-001 Core Stack
ADR-002 Repository & Engineering Standards
ADR-003 Identity & Authentication
ADR-004 Evidence/Object Storage
ADR-005 Workflow Orchestration
ADR-006 AI Provider Strategy
ADR-007 Observability
ADR-008 Deployment Platform
```

تکمیل می‌شود.

مرحله بعد دیگر ADR نیست.

---

# 59. Next Stage

مطابق فرآیند توسعه Hamoon:

```text
Business
→ Technical
→ Scrum / Product Backlog
→ Sprint
→ Code
→ Code Review
→ Stage
→ QA / Testing
→ Release Approval
→ Production
→ Monitoring
→ Improvement
```

گام بعدی:

> **HAMOON_PRODUCT_BACKLOG_V1.md**

Backlog باید بر اساس Vertical Sliceهای Business + AI ساخته شود، نه بر اساس لایه‌های Infrastructure.
