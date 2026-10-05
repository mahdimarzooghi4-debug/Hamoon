# Hamoon — External Provider Integration Verification

Status: executable verification gate implemented. Real Provider verification endpoints
and credentials remain environment-owned external dependencies.

## Purpose

Hamoon already has a provider-neutral outbound referral dispatcher and Temporal
orchestration. Repository tests prove the application contract, but they cannot prove
that a concrete external Provider endpoint accepts Hamoon credentials and supports the
required delivery semantics.

The `External Provider Integration Verification` workflow closes that evidence gap
without sending a real referral.

## Safe verification endpoint

Each configured Provider may add a verification endpoint to
`HAMOON_PROVIDER_DISPATCH_CONFIG`:

```json
{
  "<provider-uuid>": {
    "endpoint": "https://provider.example/referrals",
    "verification_endpoint": "https://provider.example/integration/verify",
    "bearer_token": "<secret>"
  }
}
```

Rules:

- both endpoints must use remote HTTPS;
- the verification endpoint must use the exact same HTTPS origin as the referral
  endpoint, including effective port;
- the existing bearer credential is reused only on that same origin;
- redirects are not followed;
- the credential never enters request/receipt artifacts.

## Synthetic probe

The workflow sends a PII-free request:

```text
operation = VERIFY_HAMOON_PROVIDER_INTEGRATION
synthetic = true
contains_pii = false
```

The request contains only:

- exact Hamoon commit SHA;
- Provider UUID;
- a random verification ID;
- requested capability checks.

It contains no Household ID, Referral ID, Dispatch ID, identity data, contact data,
evidence or business payload.

## Required Provider receipt

The verification endpoint must return:

```text
schema_version = 1
status = READY
provider_id = exact requested provider
commit_sha = exact Hamoon commit
verification_id = exact probe ID
checked_at = timezone-aware timestamp
```

with all required checks equal to `true`:

```text
credential_accepted
dispatch_contract_supported
idempotency_supported
```

A missing, extra or false check fails verification.

## Governance binding

The manual workflow requires:

- exact 40-character commit SHA;
- Provider UUID;
- explicit `VERIFY_PROVIDER` confirmation;
- successful Stage Admission for the same commit;
- protected GitHub `production` environment;
- `HAMOON_PROVIDER_DISPATCH_CONFIG` secret.

The final evidence is uploaded as:

```text
hamoon-provider-integration-<provider-id>-<commit-sha>
```

and contains:

- synthetic request;
- normalized Provider receipt;
- immutable verification attestation.

The attestation hashes the exact Stage attestation, request and receipt and records the
human verifier and workflow run ID.

## Evidence safety

The verifier rejects evidence containing forbidden fields including:

```text
authorization
bearer_token
token
household_id
referral_id
dispatch_id
national_id
phone
```

This gate proves only external integration readiness. It does not create a Referral,
change Provider selection, mark any Referral as SENT, or bypass human authorization.

## Relationship to Production preflight

Production runtime preflight already requires:

```text
provider_dispatch_configured = true
```

That check proves configuration exists. This external gate is stronger: it proves the
specific configured Provider credential/origin can complete a live synthetic contract
handshake.

Because Hamoon may have multiple Providers and deployment-specific launch scope, the
repository does not automatically require every Provider UUID to pass this gate before
Release Approval. Operations must verify the Providers that are in the approved
Production rollout scope.
