# Hamoon — Security Regression Contract

Status: PB-122 is enforced in CI.

The regression contract is intentionally organized around product authority boundaries rather than framework implementation details.

## Required checks

Every release must prove:

1. **Unauthorized household** — a caseworker without an active assignment receives a not-found boundary and protected household metadata is not disclosed.
2. **Provider isolation** — a Provider result cannot be submitted against another Provider's referral.
3. **AI authority restriction** — an AI/service identity cannot enter the human authorization context.
4. **Accepted State authorization** — the Accepted State resolution route requires CASEWORKER authority; AI runtime authority is rejected.
5. **Evidence scope** — HIGHLY_SENSITIVE evidence requires the explicit `evidence.highly_sensitive` scope.
6. **No PII leakage in logs** — structured logging removes bearer credentials, passwords, national IDs, email addresses and phone-like values from log messages, while the structured-extra allowlist prevents arbitrary sensitive fields from being exported.

## CI enforcement

`.github/workflows/ci.yml` runs:

```text
tests/unit/security/test_security_regression_contract.py
tests/unit/security
tests/unit/provider_result/test_provider_result.py
```

The first test module is the acceptance contract for PB-122. The broader security and provider-result suites provide defense in depth around OIDC, service identities, evidence access and provider scoping.

## Authority boundary

This suite does not grant authority to AI. It proves the opposite: service/AI roles cannot traverse the human context used by CASEWORKER-only commands, including Accepted State resolution.

Provider selection remains human-only and Provider callbacks/results remain scoped to the authenticated Provider identity.

## Logging boundary

Logging sanitization is a defense-in-depth layer, not permission to log raw sensitive payloads. Application code must continue to avoid request bodies, evidence text, raw prompts/responses and provider free text in logs.

The sanitizer additionally redacts common keyed secrets/PII and standalone email/phone-like values so accidental message formatting is less likely to leak them.
