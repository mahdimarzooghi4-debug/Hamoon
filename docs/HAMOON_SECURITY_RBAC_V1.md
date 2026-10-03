# Hamoon — Security & RBAC Specification v1

> وضعیت: Technical Security Baseline v1
> وابسته به معماری، Data Model، API Contracts و Event Contracts هامون.
> اصل: **امنیت در Hamoon باید دسترسی به داده، تصمیم، AI، Provider و Audit را در سراسر چرخه توانمندسازی کنترل کند.**

## 1. اصول پایه

- Least Privilege
- Deny by Default
- Server-side Authorization
- Purpose-bound Access
- Organization/Case Scope
- Field-level Access
- Provider Isolation
- Data Minimization
- Full Auditability
- AI is not an authority principal

## 2. Actor Types

```text
HUMAN
SYSTEM
AI_ENGINE
PROVIDER
EXTERNAL_SYSTEM
```

## 3. Roles v1

```text
CASEWORKER
MANAGER
ADMIN
SYSTEM_INTEGRATION
PROVIDER_INTEGRATION
AI_RUNTIME
SECURITY_AUDITOR
```

### CASEWORKER
کاربر اصلی عملیاتی پرونده و تصمیم انسانی.

### MANAGER
نظارت و تحلیل مدیریتی، عمدتاً read-only.

### ADMIN
مدیریت عملیاتی و دسترسی‌های سامانه؛ Admin به معنی دسترسی نامحدود به محتوای حساس پرونده نیست.

### SYSTEM_INTEGRATION
هویت machine-to-machine برای منابع بیرونی.

### PROVIDER_INTEGRATION
هویت مستقل هر Provider، فقط برای Referralهای متعلق به خودش.

### AI_RUNTIME
هویت سرویس برای Intelligence Platform با دسترسی حداقلی و بدون اختیار نهایی انسانی.

### SECURITY_AUDITOR
دسترسی read-only به Audit/Security records تحت سیاست سازمانی.

## 4. Permission Naming

```text
<domain>.<resource>.<action>
```

نمونه:

```text
household.case.read
household.fact.create
household.fact.correct
household.accepted_state.resolve
assessment.pgor.calculate
diagnosis.review.confirm
prescription.review.approve
provider.select
referral.send
outcome.confirm
ai.decision.trace.read
audit.read
```

## 5. Caseworker Permissions

در Scope پرونده‌های مجاز:

- read household/member
- create/correct/dispute facts
- resolve accepted state
- create/read evidence
- create assessment
- create/correct indicator observation
- calculate PGOR preview/official
- read PGOR trace
- generate/review diagnosis
- generate/review prescription
- activate intervention
- request provider matching
- select provider
- create/send/transition referral
- read provider result
- create reassessment
- prepare/review outcome
- read AI decision trace

## 6. Manager Permissions

به‌صورت پیش‌فرض:

- admin/management dashboards
- PGOR distributions
- bottlenecks
- referral/outcome aggregates
- operational health
- machine health
- data health
- scoped household drill-down when explicitly permitted

Manager نباید به‌صورت پیش‌فرض Fact خانوار را اصلاح یا تصمیم مددکار را override کند.

## 7. Admin Permissions

- operational configuration
- user/role administration where authorized
- provider registry administration
- model/prompt/formula registry visibility
- audit/operational monitoring

Admin به معنی Database Superuser یا unrestricted PII access نیست.

## 8. Provider Permissions

Provider فقط:

```text
provider.referral.read_own
provider.referral.status_update
provider.result.submit
provider.evidence.submit
```

دارد.

Rule:

```text
resource.provider_id == authenticated_provider_id
```

در غیر این صورت:

```text
DENY
```

Provider هرگز `/households/{id}` یا Fact Store را مستقیم نمی‌خواند.

## 9. AI Runtime Permissions

AI_RUNTIME می‌تواند فقط داده‌های حداقلی و مجاز برای همان تصمیم را مصرف کند و خروجی پیشنهادی بسازد.

مجاز:

```text
ai.feature.read_authorized
ai.decision.write
ai.trace.write
pgor.snapshot.read
household.accepted_state.read_minimized
evidence.read_authorized
```

غیرمجاز:

```text
household.accepted_state.resolve
diagnosis.review.confirm
prescription.review.approve
provider.select
referral.send
outcome.confirm
admin.user_access.manage
```

## 10. Human Approval Gates

در V1 تصمیم انسانی برای این موارد الزامی است:

- data conflict resolution
- diagnosis confirmation/modification/replacement
- prescription confirmation/modification/replacement
- provider selection
- referral send
- outcome confirmation

AI می‌تواند پیشنهاد دهد، اما مرجع نهایی نیست.

## 11. Resource Scope

Authorization نهایی:

```text
Permission
+ Resource Scope
+ Organization Scope
+ Purpose
+ Data Classification
→ ALLOW / MASK / DENY
```

Caseworker معمولاً پرونده‌های assigned خودش یا delegation معتبر را می‌بیند.

## 12. Temporary Delegation

```text
CASE_ASSIGNMENT
- household_id
- actor_id
- assignment_type
- valid_from
- valid_to
- assigned_by
- reason
```

Delegation باید زمان پایان داشته باشد.

## 13. Field-level Access

Classification پایه:

```text
PUBLIC
INTERNAL
CONFIDENTIAL
SENSITIVE_PERSONAL
HIGHLY_SENSITIVE
```

Field policy سه خروجی دارد:

```text
ALLOW
MASK
DENY
```

Masking باید server-side باشد.

## 14. PII Boundary

معماری منطقی:

```text
Identity / Contact Data
        ↕ controlled reference
Empowerment / PGOR / Decision Data
```

AI به‌صورت پیش‌فرض نباید نام، کد ملی، تلفن یا نشانی را دریافت کند مگر برای Task مشخص واقعاً ضروری باشد.

## 15. AI Evidence Boundary

AI فقط Evidenceهایی را مصرف می‌کند که:

- به Decision Type مرتبط‌اند
- policy اجازه می‌دهد
- sensitivity class مجاز است
- در Feature Package ثبت می‌شوند

هر Evidence مصرف‌شده باید در Decision Trace قابل ردیابی باشد.

## 16. Provider Data Minimization

قبل از Referral:

```text
ReferralDataItem[]
```

به‌صورت صریح ساخته می‌شود.

هر Item باید داشته باشد:

- data reference/value snapshot
- purpose
- shared_at
- authorization basis if applicable

کل پرونده خانوار هرگز به Provider ارسال نمی‌شود.

## 17. Purpose Limitation

Purposeهای نمونه:

```text
SERVICE_ELIGIBILITY
SERVICE_DELIVERY
FOLLOW_UP
RESULT_VALIDATION
```

Purpose باید در Data Sharing Audit ثبت شود.

## 18. Authentication

معماری ترجیحی:

```text
OIDC / OAuth2 compatible organizational identity
```

Role از حساب و policy server-side تعیین می‌شود؛ Client role انتخاب نمی‌کند.

## 19. Service Identities

برای:

- Application services
- AI Runtime
- external integrations
- Providers

هویت‌های مستقل machine-to-machine استفاده می‌شود.

Human account برای integration مجاز نیست.

## 20. Session / Access Baseline

- short-lived access tokens
- session revocation
- inactivity policy
- prompt removal of disabled-user access
- MFA policy delegated to organizational identity provider where available

## 21. Data Protection

حداقل:

- encryption in transit
- encryption at rest
- protected backups
- private evidence storage
- no secret in source code, frontend bundle, logs or event payloads

Platform-specific details در ADR تعیین می‌شود.

## 22. Evidence Storage

Evidence file access باید:

- private باشد
- server authorization را عبور دهد
- short-lived access reference تولید کند
- برای موارد حساس audit شود

Database فقط metadata/reference نگه می‌دارد.

## 23. Logging

Logها می‌توانند داشته باشند:

```text
request_id
correlation_id
actor_id
route
resource_id
status
error_code
latency
```

به‌صورت پیش‌فرض نباید raw PII یا full evidence text را log کنند.

## 24. Audit Requirements

Audit اجباری برای:

- fact correction
- accepted-state resolution
- diagnosis human decision
- prescription human decision
- provider selection
- referral send/cancel
- provider data sharing
- outcome confirmation
- user/role changes
- model/prompt/formula activation
- exports
- sensitive administrative actions

Audit append-only است و normal product roles حق ویرایش آن را ندارند.

## 25. Security Scope for Events

Event consumers از Service Identity استفاده می‌کنند.

Event payload باید حداقلی باشد.

اگر Consumer به داده بیشتری نیاز داشت:

```text
event reference
→ authorized API lookup
```

ترجیح دارد.

## 26. Search Security

Search باید authorization-aware باشد.

کاربر نباید حتی از طریق Search بتواند وجود پرونده خارج از Scope خودش را به‌طور ناخواسته کشف کند.

## 27. Work Queue Security

Task فقط در Scope Actor/Team مجاز نمایش داده می‌شود.

Projection کارتابل نباید اطلاعات پرونده خارج از Scope را leak کند.

## 28. Admin Analytics

Dashboard مدیریتی ترجیحاً داده Aggregated/De-identified نمایش می‌دهد.

Drill-down به Household-level نیازمند Permission جداست.

## 29. Learning Store Security

Production caseworker دسترسی مستقیم به Training/Evaluation dataset ندارد.

Learning/Evaluation data باید:

- purpose-specific
- versioned
- access-controlled
- de-identified where possible

باشد.

## 30. Model / Prompt / Formula Governance

مجوزهای مدیریتی جدا هستند:

```text
pgor.formula.manage
pgor.definition.manage
ai.model.manage
ai.prompt_policy.manage
ai.model.promote
```

این Permissionها به Caseworker یا Manager عادی تعلق ندارند.

AI Runtime حق self-promotion مدل یا self-modification formula ندارد.

## 31. Organization Isolation

اگر Hamoon چند Organization داشته باشد:

```text
cross-organization access = DENY by default
```

تمام Core Resourceها باید organization scope قابل enforce داشته باشند.

## 32. Logical Row Scope

حتی اگر DB-level RLS بعداً انتخاب شود یا نشود، Policy منطقی باید این کلیدها را enforce کند:

```text
organization_id
household assignment
provider_id
actor scope
resource ownership
```

## 33. Exports

Bulk export Permission مستقل دارد و از read access عادی infer نمی‌شود.

```text
data.export.operational
analytics.export
audit.export
```

## 34. Break-glass Principle

دسترسی اضطراری، در صورت پیاده‌سازی، باید:

- محدود
- موقت
- reason-required
- fully audited
- reviewable

باشد.

## 35. Environment Separation

```text
DEV
STAGE
PROD
```

باید credential و integration جدا داشته باشند.

Production PII نباید به‌صورت پیش‌فرض وارد DEV/Test شود.

## 36. Security Observability

Metrics نمونه:

```text
auth_failure_count
forbidden_request_count
scope_violation_count
provider_scope_denied_count
sensitive_evidence_access_count
role_change_count
export_count
integration_auth_failure_count
audit_pipeline_failure_count
```

بدون PII در metric labels.

## 37. Mandatory Security Tests

### Caseworker
- cannot read unauthorized household
- cannot mutate outside case scope

### Manager
- cannot correct household facts by default

### Provider
- cannot call household workspace API
- cannot access another provider's referral

### AI Runtime
- cannot resolve accepted state
- cannot confirm diagnosis
- cannot approve prescription
- cannot select/send referral
- cannot confirm outcome

### Field Access
- masking enforced server-side
- sensitive evidence requires explicit authorization

### Audit
- correction/review/referral sharing/outcome/registry activation audited

### Integration
- duplicate inbound event remains idempotent
- invalid integration identity is rejected

## 38. RBAC Summary

| Capability | Caseworker | Manager | Admin | Provider | AI Runtime | Auditor |
|---|---|---|---|---|---|---|
| Assigned household read | Yes | Scoped | Restricted | No | Minimized | Masked/No |
| Fact write/correct | Yes | No | No by default | No | No | No |
| Accepted-state resolve | Yes | No | No by default | No | No | No |
| Official PGOR calculate | Yes | No | No | No | Only through authorized service workflow | No |
| Diagnosis review | Yes | No | No | No | No | No |
| Prescription review | Yes | No | No | No | No | No |
| Provider select | Yes | No | No | No | No | No |
| Referral send | Yes | No | No | No | No | No |
| Provider result submit | No | No | No | Own only | No | No |
| Outcome confirm | Yes | No | No | No | No | No |
| Management analytics | Limited | Yes | Yes | No | No | No |
| Audit read | Limited | Limited | Yes | Own integration subset | Own trace subset | Yes |
| Model/prompt/formula manage | No | No | Controlled internal | No | No | Audit only |

## 39. Open Decisions

نیازمند ADR/Policy بعدی:

1. Identity Provider
2. exact organization hierarchy
3. DB-level RLS vs application enforcement
4. field encryption strategy
5. PII physical separation
6. audit/evidence retention periods
7. break-glass implementation
8. secrets/KMS platform
9. data residency
10. model-provider data-processing restrictions
11. export governance
12. de-identification standard for Learning datasets

## 40. Definition of Done

Security/RBAC v1 آماده Implementation است وقتی:

- Role/Permission model تثبیت شده باشد.
- Caseworker Scope enforce شود.
- Provider isolation تست‌پذیر باشد.
- AI Runtime authority محدود باشد.
- Field ALLOW/MASK/DENY policy وجود داشته باشد.
- PII minimization برای AI تعریف شده باشد.
- Audit commandهای حساس مشخص باشد.
- service/provider identity جدا باشد.
- security tests قابل اجرا باشند.

## 41. مرحله بعد

```text
Stack ADRs
→ Product Backlog
→ Sprint 1
```

اولین تصمیم بعدی:

> **ADR-001 — Backend / Primary Data / Event / AI Runtime Stack**
