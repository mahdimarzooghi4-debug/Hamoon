# Hamoon — Hosted Production Verification

Status: Verification contract implemented; Hosted Production is not yet provisioned.

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

The manual `Production Verification` workflow can run only after a successful
Production Deployment Admission exists for the exact commit. It:

1. downloads the immutable Production admission;
2. follows it back through Release Approval, Stage Admission and source CI evidence;
3. re-verifies the entire governance chain;
4. probes only the admitted HTTPS Production endpoint;
5. verifies liveness and readiness;
6. verifies backend commit/image/deployment/schema identity;
7. verifies frontend commit/image/deployment identity;
8. requires frontend/backend application versions to agree;
9. emits a hashed Production verification attestation.

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
→ provider-specific deployment
→ backend /health/release
→ frontend /release.json
→ Production Verification VERIFIED
→ Monitoring
```
