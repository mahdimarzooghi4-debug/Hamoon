# ADR-002 — Hamoon Repository Structure & Engineering Standards

> وضعیت: Accepted for V1  
> دامنه تصمیم: Repository Layout, Module Boundaries, Coding Standards, Testing, Review, CI/CD Readiness  
> وابسته به:
> - `ADR-001-HAMOON-CORE-STACK.md`
> - `HAMOON_TECHNICAL_ARCHITECTURE_V1.md`
> - `HAMOON_DATA_MODEL_V1.md`
> - `HAMOON_API_CONTRACTS_V1.md`
> - `HAMOON_EVENT_CONTRACTS_V1.md`
> - `HAMOON_SECURITY_RBAC_V1.md`

---

# 1. Context

Hamoon باید بتواند هم‌زمان:

- Domain Logic پیچیده
- Temporal Data
- PGOR deterministic engine
- AI decision flows
- Human-in-the-loop
- Events
- Provider integrations
- Security/Audit
- Learning/Evaluation

را در یک codebase قابل توسعه و قابل نگهداری پیاده‌سازی کند.

هدف این ADR جلوگیری از دو خطاست:

1. تبدیل Modular Monolith به یک monolith درهم‌تنیده.
2. ایجاد abstraction و infrastructure بیش‌ازحد قبل از نیاز واقعی.

---

# 2. Decision Summary

V1 از یک **single repository** با ساختار Modular Monolith استفاده می‌کند.

ساختار اصلی:

```text
src/
  hamoon/
    app/
    domains/
    infrastructure/
    shared/

tests/
  unit/
  integration/
  contract/
  e2e/

migrations/
contracts/
scripts/
docs/
```

اصل dependency:

```text
API / Interface
→ Application
→ Domain
← Infrastructure via Ports
```

Domain layer نباید به FastAPI، SQLAlchemy، NATS یا Model Provider خاص وابسته باشد.

---

# 3. Repository Layout

```text
.
├── src/
│   └── hamoon/
│       ├── app/
│       │   ├── api/
│       │   ├── config/
│       │   ├── security/
│       │   ├── startup/
│       │   └── observability/
│       │
│       ├── domains/
│       │   ├── household/
│       │   ├── family_data/
│       │   ├── assessment/
│       │   ├── pgor/
│       │   ├── diagnosis/
│       │   ├── prescription/
│       │   ├── intervention/
│       │   ├── provider/
│       │   ├── referral/
│       │   ├── outcome/
│       │   ├── intelligence/
│       │   ├── learning/
│       │   ├── audit/
│       │   └── integration/
│       │
│       ├── infrastructure/
│       │   ├── db/
│       │   ├── events/
│       │   ├── ai/
│       │   ├── storage/
│       │   ├── identity/
│       │   └── observability/
│       │
│       └── shared/
│           ├── errors/
│           ├── ids/
│           ├── time/
│           ├── contracts/
│           ├── pagination/
│           └── typing/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── e2e/
│
├── migrations/
├── contracts/
│   ├── api/
│   ├── events/
│   ├── provider/
│   └── ai/
│
├── scripts/
├── docs/
├── pyproject.toml
├── README.md
└── .env.example
```

---

# 4. Domain Module Standard

هر Domain Module باید در صورت نیاز این ساختار را داشته باشد:

```text
domains/<module>/
  domain/
    entities.py
    value_objects.py
    services.py
    rules.py
    events.py
    errors.py

  application/
    commands.py
    queries.py
    handlers.py
    dto.py

  ports/
    repositories.py
    services.py

  infrastructure/
    repositories.py
    adapters.py

  api/
    routes.py
    schemas.py
```

این ساختار Template است، نه الزام برای ایجاد فایل‌های خالی.

قاعده:

> فقط فایل و abstractionی ساخته شود که نیاز واقعی دارد.

---

# 5. Dependency Rules

مجاز:

```text
api → application
application → domain
infrastructure → domain/application ports
app → composition root
```

غیرمجاز:

```text
domain → FastAPI
domain → SQLAlchemy
domain → NATS
domain → vendor AI SDK
domain A → infrastructure of domain B
frontend → database
provider → database
```

---

# 6. Cross-Module Communication

ترتیب ترجیح:

1. Application Service / Port مشخص
2. Domain Event
3. Read Projection
4. Shared Kernel فقط برای primitives واقعاً مشترک

ممنوع:

- import مستقیم repository داخلی module دیگر
- mutation مستقیم tableهای module دیگر
- circular dependency بین domainها

---

# 7. Shared Kernel

`shared/` فقط برای مفاهیم عمومی و پایدار:

- ID types
- time utilities
- common error envelope
- pagination primitives
- correlation/request context
- generic result types

نباید به محل ریختن business logic مشترک تبدیل شود.

قانون:

> اگر مفهوم Business دارد، احتمالاً متعلق به یک Domain است نه Shared.

---

# 8. Naming

## Python

- modules/files: `snake_case`
- classes: `PascalCase`
- functions/variables: `snake_case`
- constants: `UPPER_SNAKE_CASE`

## Domain Commands

Imperative:

```text
CreateHousehold
RecordHouseholdFact
CalculatePGOR
GenerateDiagnosis
ConfirmDiagnosis
SendReferral
```

## Domain Events

Past tense:

```text
HouseholdCreated
PGORSnapshotCalculated
DiagnosisConfirmed
ReferralSent
```

---

# 9. IDs

Business entities باید typed IDs داشته باشند.

مثال:

```text
HouseholdId
AssessmentId
PGORSnapshotId
DiagnosisId
ReferralId
OutcomeId
AIDecisionId
```

استفاده از raw string در سراسر Domain باید محدود شود.

ID generation strategy دقیق در ADR مستقل قابل تغییر است.

---

# 10. Time Handling

در Domain:

- timezone-aware datetime
- UTC internally
- no naive datetime
- effective_at و recorded_at جدا

UI مسئول نمایش شمسی/محلی است.

---

# 11. Money / Numeric Precision

برای score و formula:

- float binary برای محاسبات authoritative ترجیح داده نمی‌شود.
- Decimal یا precision کنترل‌شده استفاده شود.
- rounding فقط در boundary نمایشی.

PGOR tests باید exact/controlled tolerance داشته باشند.

---

# 12. Configuration

Configuration typed و environment-driven باشد.

نمونه categories:

```text
APP_ENV
DATABASE_*
NATS_*
OIDC_*
AI_*
OBJECT_STORAGE_*
OBSERVABILITY_*
```

قوانین:

- secret در repo ممنوع
- config import-time side effect ممنوع
- production defaults خطرناک ممنوع

---

# 13. Error Model

سه سطح:

## Domain Error
مثال:

```text
InvalidReferralTransition
MissingRequiredIndicator
UnauthorizedStateChange
```

## Application Error
مثال:

```text
VersionConflict
ResourceNotFound
DependencyUnavailable
```

## Transport Error Mapping
مثال:

```text
Domain/Application Error
→ HTTP code + stable error code
```

Free-text error نباید contract اصلی باشد.

---

# 14. Command / Query Separation

در Application Layer:

```text
Command = state change
Query   = read
```

Command handler نباید hidden query API برای UI شود.

Query handler نباید side effect Business ایجاد کند.

CQRS کامل infrastructure-level در V1 لازم نیست؛ تفکیک مفهومی کافی است.

---

# 15. Transaction Boundary

هر Command باید transaction boundary مشخص داشته باشد.

نمونه:

```text
CorrectHouseholdFact
→ new fact
→ supersede relation
→ accepted-state projection
→ domain event
→ audit
→ outbox
COMMIT
```

Transaction نباید از remote model/provider call عبور کند.

---

# 16. External Calls

قاعده:

```text
Database transaction
≠
remote network transaction
```

برای Provider/AI:

- persist intent/state
- commit
- dispatch async or controlled call
- persist result separately

از long DB transaction حول network call اجتناب شود.

---

# 17. AI Code Boundary

تمام vendor SDKها در:

```text
infrastructure/ai/
```

قرار می‌گیرند.

Domain/Application فقط Interfaceهای Hamoon را می‌شناسند:

```text
GenerateStructuredDecision
BuildFeaturePackage
EvaluateDecision
```

Prompt متن خام نباید داخل route/handler پراکنده شود.

---

# 18. Prompt & Policy Assets

پیشنهاد repository:

```text
contracts/ai/
  diagnosis/
    output.schema.json
  prescription/
    output.schema.json

src/hamoon/infrastructure/ai/policies/
  ...
```

Prompt/Policy version باید traceable باشد.

در صورت انتقال promptها به registry خارجی، repo همچنان contract/version references را نگه می‌دارد.

---

# 19. PGOR Code Boundary

```text
domains/pgor/
```

باید pure و deterministic بماند.

ساختار پیشنهادی:

```text
pgor/
  domain/
    definitions.py
    scoring.py
    formula.py
    snapshot.py
    errors.py

  application/
    calculate.py

  tests/
```

Forbidden:

- HTTP
- LLM
- NATS
- provider SDK
- database-specific calculation logic

---

# 20. Database Models

SQLAlchemy models در infrastructure/db یا module infrastructure قرار می‌گیرند.

قاعده:

> ORM model = persistence representation، نه Domain Entity.

Mapping واضح لازم است.

برای بخش‌های ساده می‌توان mapping را pragmatic نگه داشت، اما Domain invariants نباید فقط در DB model بمانند.

---

# 21. Migration Standards

هر migration:

- نام توصیفی
- forward path روشن
- destructive change review
- reference data impact مشخص
- compatible rollout plan برای production

ممنوع:

- auto-create schema on application boot در production
- migration بدون review
- تغییر مستقیم production DB خارج از migration process

---

# 22. API Schema Standards

Pydantic schemaها:

- transport-specific هستند
- Domain Entity نیستند
- validation transport را انجام می‌دهند
- stable field naming دارند

API date/time:

- ISO-8601
- UTC

Enumها باید canonical code داشته باشند.

---

# 23. Event Schema Standards

هر Event contract باید:

- event_type
- version
- schema
- producer
- consumers
- sensitivity class

داشته باشد.

JSON Schemaها در:

```text
contracts/events/
```

قرار می‌گیرند.

---

# 24. Provider Contract Standards

Provider-specific تفاوت‌ها باید پشت Adapter بمانند.

Canonical Hamoon model:

```text
Referral
ProviderStatus
ProviderResult
```

Provider adapter:

```text
Canonical
↔
Provider-specific payload
```

Domain نباید payload اختصاصی Provider را بشناسد.

---

# 25. Testing Pyramid

## Unit — بیشترین تعداد

هدف:

- Domain rules
- PGOR
- state machines
- authorization
- mapping logic
- deterministic transformations

## Integration

هدف:

- PostgreSQL
- repositories
- migrations
- outbox
- NATS
- storage adapter
- AI adapter with controlled test double

## Contract

هدف:

- REST schemas
- Event JSON schemas
- Provider payloads
- AI structured outputs

## E2E — محدود ولی حیاتی

مسیرهای اصلی Business.

---

# 26. Mandatory Test Rules

هر Bug مهم باید regression test داشته باشد.

هر Domain Rule مهم بدون test پذیرفته نیست.

موارد حیاتی:

- fact history
- accepted state
- PGOR reproducibility
- diagnosis human override
- referral state machine
- provider isolation
- outcome separation
- learning trace

---

# 27. AI Tests

AI integration test دو نوع دارد:

## Deterministic Contract Tests

با fake/stub:

- schema validation
- routing
- timeout handling
- trace capture

## Evaluation Tests

با dataset نسخه‌بندی‌شده:

- quality metrics
- groundedness
- human acceptance/modification patterns
- safety

Unit test جای Evaluation را نمی‌گیرد.

---

# 28. Test Data

Production PII در test ممنوع مگر فرآیند رسمی و de-identified.

ترجیح:

- synthetic fixtures
- anonymized datasets
- versioned evaluation sets

---

# 29. Formatting / Linting

V1 standard:

```text
Ruff
```

برای:

- lint
- import sorting
- formatting policy

در صورت نیاز formatter جدا می‌تواند بعداً اضافه شود، اما ابزارهای هم‌پوشان متعدد ترجیح داده نمی‌شوند.

---

# 30. Type Checking

V1 باید static typing جدی داشته باشد.

پیشنهاد:

```text
Pyright
```

یا معادل مورد تأیید پروژه.

حداقل moduleهای زیر باید typed باشند:

- domain
- application
- contracts
- PGOR
- AI interfaces

---

# 31. Test Framework

```text
pytest
```

با:

- async support where needed
- fixtures محدود و واضح
- no giant global fixture graph

Test name باید behavior را توصیف کند.

---

# 32. Coverage

Coverage عدد خام هدف اصلی نیست.

اما Core Domainها باید coverage بالا داشته باشند.

گیت اصلی:

> Business invariant بدون test نباید merge شود.

PGOR، authorization، referral state machine و data correction باید پوشش بسیار بالا داشته باشند.

---

# 33. Code Review Standard

هر تغییر production-bound باید review شود.

Review checklist:

- domain correctness
- source/contract alignment
- security
- data migration impact
- event compatibility
- AI traceability
- tests
- observability
- backward compatibility

---

# 34. Pull Request Size

ترجیح:

- کوچک
- یک هدف اصلی
- قابل review
- قابل rollback

PR عظیم چندموضوعی فقط در bootstrap اولیه با justification.

---

# 35. Commit Standard

Commitها باید معنی‌دار و atomic باشند.

پیشنهاد سبک:

```text
feat:
fix:
refactor:
docs:
test:
chore:
```

مثال:

```text
feat(pgor): add deterministic snapshot calculation
```

---

# 36. Branching

V1:

- `main` همیشه قابل release
- short-lived feature branches
- no long-lived develop branch مگر نیاز واقعی

ترجیح:

```text
feature/*
fix/*
chore/*
```

---

# 37. CI Minimum Gates

هر PR:

1. install/lock verification
2. lint
3. type check
4. unit tests
5. contract tests
6. migration consistency checks
7. security/static checks where configured

Integration/E2E بر اساس زمان اجرا می‌تواند tiered باشد ولی قبل از release باید پاس شود.

---

# 38. Dependency Management

Python dependencyها باید lock شوند.

پیشنهاد:

```text
uv
```

برای environment/dependency workflow.

قاعده:

- dependency جدید باید دلیل داشته باشد
- library duplicate ممنوع
- security-sensitive dependency review شود

---

# 39. Python Version

نسخه Python باید در repo pin شود.

V1 باید روی یک نسخه مدرن و پشتیبانی‌شده Python تثبیت شود.

عدد دقیق runtime در bootstrap implementation بر اساس compatibility dependencies ثبت می‌شود و بدون ADR کوچک تغییر عمده نمی‌کند.

---

# 40. Security in Engineering Workflow

ممنوع:

- secret در commit
- production token در test
- raw PII در fixture
- sensitive payload در log
- bypass authorization برای convenience

Security test بخشی از CI است.

---

# 41. Observability in Code

هر request/command/event باید correlation context را حفظ کند.

حداقل:

```text
request_id
correlation_id
actor_id where applicable
aggregate_id
event_id
trace_id for AI
```

Logging structured باشد.

---

# 42. Feature Flags

Feature flag فقط برای rollout/control.

نباید جای versioning مدل/فرمول/schema را بگیرد.

مثال مناسب:

```text
enable_async_diagnosis_v2
```

مثال نامناسب:

```text
use_formula_without_versioning
```

---

# 43. Backward Compatibility

Contractهای زیر باید compatibility strategy داشته باشند:

- API
- Event
- Provider Integration
- AI structured output
- DB migrations

Breaking change بدون version bump یا migration plan مجاز نیست.

---

# 44. Deprecation

API/Event deprecation باید:

- marked
- documented
- monitored
- removal date/process داشته باشد

Silent removal ممنوع.

---

# 45. Documentation as Code

اسناد معماری در `docs/` بخشی از محصول فنی هستند.

هر تغییر معماری مهم باید یکی از این‌ها را update کند:

- ADR
- API Contract
- Event Contract
- Data Model
- Security Spec
- Engine Spec

Code نباید quietly از architecture docs منحرف شود.

---

# 46. Definition of Done — Feature

یک Feature فقط با Code تمام نیست.

حداقل:

```text
Requirement
+ Domain behavior
+ Code
+ Tests
+ Security checks
+ Events/API contract
+ Observability
+ Review
+ Stage verification
```

برای AI Feature:

```text
+ output schema
+ evaluation
+ traceability
+ human review behavior
```

---

# 47. Definition of Done — Bug Fix

- root cause مشخص
- regression test
- fix minimal
- audit/data impact بررسی
- no hidden contract break

---

# 48. Release Readiness

قبل از Production:

- CI green
- migration tested
- config validated
- rollback strategy
- monitoring in place
- critical alerts defined
- security checks complete
- model/prompt/formula versions pinned
- seed/reference data verified

---

# 49. Engineering Decision Rule

هنگام انتخاب abstraction یا infrastructure:

```text
Is there a current requirement?
Is it measurable?
Does it reduce current risk?
Does it preserve future extraction?
```

اگر نه:

> defer.

Hamoon نباید با architecture astronautics کند.

---

# 50. Vertical Slice Rule

Backlog و Sprint باید تا حد امکان بر Vertical Slice بنا شوند.

مثال خوب:

```text
Household
→ Observation
→ PGOR
→ AI Diagnosis
→ Human Review
→ Learning Signal
```

مثال ضعیف:

```text
Sprint 1: only repositories
Sprint 2: only DTOs
Sprint 3: only events
```

Infrastructure در خدمت یک جریان Business واقعی ساخته می‌شود.

---

# 51. First Implementation Slice — Required Modules

برای Slice اول:

```text
household
assessment
pgor
intelligence
diagnosis
learning
audit
events
security
```

حداقل infrastructure:

```text
postgres
migrations
outbox
nats
ai gateway interface
```

---

# 52. Bootstrap Deliverables

قبل از Feature Code:

- `pyproject.toml`
- dependency lock
- package structure
- config loader
- FastAPI app bootstrap
- DB session/transaction foundation
- Alembic
- lint/type/test config
- base error envelope
- request/correlation middleware
- health endpoint
- CI workflow

Bootstrap باید کوچک و قابل اجرا باشد.

---

# 53. Health Endpoints

حداقل:

```text
GET /health/live
GET /health/ready
```

Readiness می‌تواند dependency state را بررسی کند.

هیچ PII در health response.

---

# 54. Local Development

هدف:

```text
one command
→ API + Postgres + NATS
```

مثلاً از container-based local stack.

AI provider می‌تواند در local با fake adapter اجرا شود.

---

# 55. Fake Adapters

برای توسعه/test:

- FakeAIProvider
- FakeProviderIntegration
- InMemoryEventPublisher where appropriate
- StubObjectStorage

اما integration tests باید adapter واقعی infrastructure را نیز پوشش دهند.

---

# 56. No Hidden Business Logic

Business rule نباید در:

- route
- ORM callback
- migration
- UI
- event consumer glue
- prompt text

پنهان شود.

Rule باید در Domain/Application قابل test باشد.

---

# 57. No Silent AI Logic

Prompt نباید تنها محل تعریف decision semantics باشد.

Prompt باید بر:

- domain inputs
- output schema
- policy
- evidence rules

تکیه کند.

Critical policy خارج از prompt enforce می‌شود.

---

# 58. Repository Ownership Boundaries

هر Domain در code owner/review ownership قابل تعریف است، حتی اگر تیم در V1 کوچک باشد.

هدف:

- review context
- future team scaling
- جلوگیری از cross-domain edits بدون توجه

---

# 59. Consequences

## Positive

- codebase ساده ولی ساختاریافته
- AI و backend در یک language ecosystem
- domain boundaries روشن
- testing strategy واضح
- امکان extraction آینده
- architecture drift کمتر

## Trade-offs

- discipline برای boundaryها لازم است
- modular monolith tooling باید enforce شود
- بعضی boilerplateها بیشتر از CRUD ساده است
- contract/version discipline هزینه اولیه دارد

---

# 60. Guardrails

1. فایل خالی فقط برای رعایت template ایجاد نشود.
2. Domain به framework وابسته نشود.
3. Cross-domain table mutation ممنوع.
4. Vendor AI SDK خارج از infrastructure/ai ممنوع.
5. Business Rule در route ممنوع.
6. Event بدون schema/version ممنوع.
7. Migration خارج از repo ممنوع.
8. Secret در code/config commit ممنوع.
9. AI feature بدون evaluation/trace ناقص است.
10. PR بزرگ چندهدفه باید exceptional باشد.

---

# 61. Acceptance Criteria

ADR-002 زمانی پیاده شده محسوب می‌شود که:

- repository structure ایجاد شده باشد.
- module boundaryها در code enforce شوند.
- FastAPI app bootstrap اجرا شود.
- PostgreSQL + Alembic راه‌اندازی شده باشد.
- lint/type/test commands تعریف شده باشند.
- CI اولیه فعال باشد.
- request/correlation context وجود داشته باشد.
- PGOR module بدون framework dependency باشد.
- AI Gateway interface در infrastructure boundary باشد.
- tests directory چهار سطح اصلی را داشته باشد.
- first vertical slice بدون نقض dependency rules قابل ساخت باشد.

---

# 62. Next Step

بعد از ADR-002:

```text
ADR-003 — Identity Provider & Authentication
ADR-004 — Evidence/Object Storage
ADR-005 — Workflow Orchestration
ADR-006 — AI Provider Strategy
ADR-007 — Observability
ADR-008 — Deployment

→ Product Backlog
→ Sprint 1
```

گام بعدی فوری:

> **ADR-003 — Identity Provider & Authentication**
