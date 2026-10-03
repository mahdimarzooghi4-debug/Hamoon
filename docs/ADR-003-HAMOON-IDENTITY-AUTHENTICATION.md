# ADR-003 — Hamoon Identity Provider & Authentication

> وضعیت: Accepted for V1  
> دامنه تصمیم: Identity Provider, Authentication, Token Model, Service Identities, SSO, Session Security  
> وابسته به:
> - `HAMOON_SECURITY_RBAC_V1.md`
> - `ADR-001-HAMOON-CORE-STACK.md`
> - `ADR-002-HAMOON-REPOSITORY-ENGINEERING-STANDARDS.md`
> - `HAMOON_API_CONTRACTS_V1.md`

---

# 1. Context

Hamoon یک سامانه سازمانی و حساس است. کاربران انسانی، Providerها، سامانه‌های بیرونی و AI Runtime هرکدام باید هویت و Scope مستقل داشته باشند.

نیازهای اصلی:

- Organizational SSO
- OIDC/OAuth2 compatibility
- MFA capability
- short-lived access token
- role/organization claims
- service identities
- provider identities
- revocation
- auditability
- future federation with enterprise IdP
- zero authentication logic inside Domain

---

# 2. Decision Summary

برای V1:

```text
Authentication Standard:
OpenID Connect (OIDC) + OAuth 2.0

Reference Identity Provider:
Keycloak

Human Login:
Authorization Code Flow + PKCE

Service-to-Service:
OAuth2 Client Credentials

Access Token:
Short-lived JWT

Authorization:
Server-side in Hamoon
RBAC + Resource Scope + Organization Scope + Field Policy

MFA:
IdP policy

Provider Identity:
Dedicated confidential client per Provider

External Integration:
Dedicated client per system

AI Runtime:
Dedicated service identity with minimized permissions
```

---

# 3. Reference IdP — Keycloak

Keycloak به‌عنوان Reference IdP V1 انتخاب می‌شود چون نیازهای پایه Hamoon را پوشش می‌دهد:

- OIDC
- OAuth2
- SSO
- MFA
- service accounts
- roles/claims
- federation
- external identity providers
- self-hosted organizational control

اما Core Hamoon به Keycloak API وابسته نمی‌شود.

وابستگی رسمی Hamoon:

```text
OIDC claims
OAuth2 semantics
Hamoon AuthorizationContext
```

است.

---

# 4. Existing Enterprise Identity

اگر سازمان مقصد IdP معتبر خودش را داشته باشد:

```text
Enterprise IdP
→ federate with Keycloak
OR
→ replace Keycloak at deployment boundary
```

به شرط حفظ OIDC contract.

پس Keycloak انتخاب Reference است، نه vendor lock دائمی.

---

# 5. Human Authentication Flow

```text
User
→ Hamoon
→ IdP
→ Authorization Code
→ PKCE verification
→ Access Token
→ Hamoon API
```

Hamoon Password کاربر را دریافت یا ذخیره نمی‌کند.

---

# 6. Login UX

صفحه ورود فقط:

```text
ورود با حساب سازمانی
```

را ارائه می‌کند.

Role Picker وجود ندارد.

Role از Identity + Hamoon Policy استخراج می‌شود.

---

# 7. Token Claims

Logical example:

```json
{
  "sub": "user-123",
  "iss": "https://idp.example",
  "aud": "hamoon-api",
  "exp": 1760000000,
  "organization_id": "org_1",
  "unit_id": "unit_12",
  "roles": ["CASEWORKER"]
}
```

Household IDs و داده حساس پرونده داخل JWT قرار نمی‌گیرند.

---

# 8. Token Validation

Hamoon API باید validate کند:

- signature
- issuer
- audience
- expiration
- not-before if present
- token type
- required subject claims

Frontend هیچ‌گاه مرجع Authentication/Authorization نیست.

---

# 9. Internal Account Mapping

```text
USER_ACCOUNT
- id
- actor_id
- external_identity_subject
- issuer
- status
- last_login_at
```

Actor ID داخلی Hamoon پایدار می‌ماند.

---

# 10. Role Mapping

نقش‌های انسانی اولیه:

```text
CASEWORKER
MANAGER
ADMIN
SECURITY_AUDITOR
```

اما Authorization نهایی:

```text
Role
+ Resource Scope
+ Organization Scope
+ Purpose
+ Field Policy
→ ALLOW / MASK / DENY
```

است.

---

# 11. Household Assignment

Household assignment داخل JWT ذخیره نمی‌شود.

درست:

```text
JWT → actor/org/unit
Hamoon DB → current case assignments
```

این کار از tokenهای بزرگ و stale جلوگیری می‌کند.

---

# 12. Service-to-Service

برای machine identities:

```text
OAuth2 Client Credentials
```

نمونه Identityها:

```text
hamoon-api
hamoon-worker
hamoon-ai-worker
provider-<provider_id>
integration-<system_id>
```

Credential مشترک بین سیستم‌ها ممنوع است.

---

# 13. AI Runtime Identity

AI Runtime فقط مجوزهای حداقلی دارد:

```text
ai.feature.read_authorized
ai.decision.write
ai.trace.write
pgor.snapshot.read
household.accepted_state.read_minimized
evidence.read_authorized
```

و حق این موارد را ندارد:

```text
household.accepted_state.resolve
diagnosis.review.confirm
prescription.review.approve
provider.select
referral.send
outcome.confirm
admin.user_access.manage
```

---

# 14. Provider Identity

هر Provider Client مستقل دارد.

Rule:

```text
resource.provider_id == authenticated_provider_id
```

Cross-provider access:

```text
DENY
```

---

# 15. External System Identity

هر Source System:

- client مستقل
- scope مستقل
- قابلیت revoke
- audit
- environment-specific secret

دارد.

Human credential برای integration ممنوع است.

---

# 16. OAuth Scopes

Transport-level scopes:

```text
hamoon.read
hamoon.write
hamoon.provider
hamoon.integration
hamoon.ai
hamoon.admin
hamoon.audit
```

این Scopeها coarse هستند؛ Fine-grained authorization داخل Hamoon انجام می‌شود.

---

# 17. Authorization Context

پس از validate token:

```text
AuthorizationContext
- actor_id
- actor_type
- organization_id
- unit_id
- roles[]
- token_scopes[]
- session_id?
- authentication_strength?
```

ساخته می‌شود.

Domain هیچ JWT library یا Keycloak dependency ندارد.

---

# 18. Session Policy

- access token short-lived
- refresh policy تحت کنترل IdP/client pattern
- session revocation
- inactivity timeout
- logout support
- no insecure browser token storage

Client web می‌تواند از BFF/session pattern استفاده کند؛ انتخاب دقیق frontend session implementation در implementation design انجام می‌شود.

---

# 19. MFA

MFA توسط IdP enforce می‌شود.

برای نقش‌های حساس مثل Admin/Security Auditor می‌تواند اجباری باشد.

معماری باید future step-up authentication را نیز پشتیبانی کند.

---

# 20. Local Password Policy

Hamoon V1 credential store ندارد.

اگر سازمان IdP مستقل ندارد، Keycloak credential handling را انجام می‌دهد.

Hamoon DB هیچ password hash کاربر ذخیره نمی‌کند.

Password reset نیز IdP concern است.

---

# 21. Logout / Revocation

Logout باید session material را invalidate کند.

برای disable/revocation حساس:

- access جدید فوری deny
- session/token revocation where supported
- short token lifetime برای کاهش exposure

---

# 22. Provider Callback Security

ترجیح:

- OAuth2 identity

برای webhook-based integration:

- signature
- timestamp
- event_id
- replay protection
- provider binding

الگوریتم signature در Provider Integration ADR قابل تثبیت است.

---

# 23. Secret Management

Secretها نباید در:

- source code
- Git history
- frontend bundle
- logs
- event payload
- prompt

باشند.

Secret/KMS platform در Deployment ADR نهایی می‌شود.

---

# 24. Identity Audit

رویدادهای امنیتی قابل Audit:

```text
LoginSucceeded
LoginFailed
SessionRevoked
UserAccessDisabled
RoleMappingChanged
ServiceCredentialRotated
ProviderCredentialRevoked
PrivilegedAccessGranted
```

تا جایی که IdP integration فراهم کند.

---

# 25. Logging Rules

مجاز:

```text
actor_id
client_id
request_id
auth_result
timestamp
```

ممنوع:

```text
access_token
refresh_token
authorization_code
password
client_secret
```

---

# 26. Environment Separation

```text
DEV
STAGE
PROD
```

هرکدام باید realm/tenant، client IDs، credentials و redirect URIs مستقل داشته باشند.

Production credentials در Stage/Dev ممنوع.

---

# 27. Realm Strategy

Reference V1:

```text
one Hamoon realm per environment
```

Organization isolation داخل Hamoon policy انجام می‌شود، نه با realm جدا برای هر organization مگر نیاز آینده.

---

# 28. Client Strategy

نمونه:

```text
hamoon-web
hamoon-api
hamoon-worker
hamoon-ai-worker
hamoon-admin
provider-<id>
integration-<id>
```

---

# 29. Configuration as Code

IdP configuration باید reproducible باشد.

Repository location پیشنهادی:

```text
infra/identity/
```

Manual production configuration باید حداقلی و reviewable باشد.

---

# 30. Availability

Hamoon باید OIDC discovery/JWKS را به‌شکل امن cache کند تا validate کردن tokenهای صادرشده به lookup دائمی IdP وابسته نباشد.

قاعده:

```text
cannot trust token → fail closed
```

---

# 31. HTTP Failure Semantics

Authentication failure:

```text
401 UNAUTHENTICATED
```

Authorization failure:

```text
403 FORBIDDEN
```

Response نباید ownership یا metadata حساس resource را leak کند.

---

# 32. Local Development

Local development می‌تواند realm توسعه داشته باشد.

Test identities نمونه:

```text
caseworker_test
manager_test
admin_test
provider_test
ai_runtime_test
```

هیچ production identity data به local کپی نمی‌شود.

---

# 33. Testing

## Authentication

- invalid signature rejected
- expired token rejected
- wrong issuer rejected
- wrong audience rejected
- missing required subject rejected
- disabled account denied

## Authorization Context

- role mapping correct
- organization/unit mapping correct
- household assignment server-side
- AI/service identities resolved correctly

## Provider

- provider A cannot access provider B
- revoked credential rejected
- insufficient scope rejected

---

# 34. Unit Test Doubles

Domain/Application tests می‌توانند از:

```text
FakeAuthorizationContext
FakeIdentityResolver
```

استفاده کنند.

Keycloak فقط برای Integration/Auth tests لازم است.

---

# 35. Consequences

## Positive

- standards-based SSO
- no password store in Hamoon
- MFA/service accounts آماده
- provider identities مستقل
- AI identity محدود
- enterprise federation possible
- domain independent from IdP vendor

## Trade-offs

- Keycloak یک component عملیاتی اضافه می‌کند
- realm/client config نیازمند discipline است
- claim mapping باید با Hamoon access model هماهنگ بماند

---

# 36. Guardrails

1. No password storage in Hamoon DB.
2. No role picker in login UI.
3. No household IDs in JWT.
4. No shared provider credential.
5. No shared service credential.
6. No Keycloak dependency inside domain.
7. No long-lived access token as default.
8. No token/secret logging.
9. No frontend-only authorization.
10. No machine integration using a human account.

---

# 37. Acceptance Criteria

ADR-003 پیاده شده است وقتی:

- Keycloak development configuration exists
- OIDC login works
- Authorization Code + PKCE works
- FastAPI validates JWT
- Actor mapping persists
- role/org/unit mapping works
- client-credentials service auth works
- provider isolation works
- AI runtime identity is restricted
- auth audit events are captured
- unit/integration authentication tests pass

---

# 38. Next ADR

> **ADR-004 — Evidence / Object Storage**

سپس:

```text
ADR-005 — Workflow Orchestration
ADR-006 — AI Provider Strategy
ADR-007 — Observability
ADR-008 — Deployment

→ Product Backlog
→ Sprint 1
```
