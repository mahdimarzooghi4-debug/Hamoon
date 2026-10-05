# Hamoon — Hosted Production Verification

Status: Verification contract implemented and now bound to immutable hosted deployment execution evidence. A concrete hosted Production runtime is still an external environment dependency.

A provider reporting that a deployment completed is not sufficient evidence that the
correct Hamoon release is serving traffic.

## Runtime identity contract

The backend exposes:

```text
GET /health/release
```

with:

- application version;
- Git commit;
- exact runtime backend image ID supplied by the deployment;
- deployment ID;
- active Alembic migration versions from PostgreSQL.

The frontend exposes:

```text
GET /release.json
```

with:

- application version;
- Git commit;
- exact runtime frontend image ID supplied by the deployment;
- deployment ID.

Both endpoints are non-sensitive and must be served with no-store caching semantics.

## Production Verification workflow

The manual `Production Verification` workflow can run only after both a successful
Production Deployment Admission and a successful immutable Production Deploy artifact
exist for the exact commit. It:

1. downloads the immutable Production admission;
2. downloads the immutable hosted deployment request/receipt/attestation;
3. follows the chain back through Release Approval, Stage Admission and source CI evidence;
4. re-verifies both release governance and hosted deployment evidence, including the
   versioned runtime preflight contract, READY receipt, preflight ID and the deploy
   request/receipt binding to that preflight;
5. probes only the deployed HTTPS Production endpoint;
6. verifies liveness and readiness;
7. verifies backend commit/image/deployment/schema identity;
8. verifies frontend commit/image/deployment identity;
9. requires frontend/backend application versions to agree;
10. emits a hashed Production verification attestation bound to the Production Deploy artifact.

Only this verified artifact may state:

```text
production_deployed=true
status=VERIFIED
runtime_identity_verified=true
```

## Failure semantics

A stale frontend, stale backend, wrong image ID, wrong deployment ID, missing migration
identity, non-Production backend environment, or tampered observation prevents
Production verification.

## Chain

```text
Release Artifact
→ Stage Admission
→ Human Release Approval
→ Production Deployment Admission
→ Production Deploy / DEPLOYED receipt
→ backend /health/release
→ frontend /release.json
→ Production Verification VERIFIED
→ Monitoring
```
