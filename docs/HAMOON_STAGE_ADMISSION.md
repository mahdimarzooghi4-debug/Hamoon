# Hamoon — Stage Admission Gate

Status: Implemented CI promotion boundary.

This gate is deliberately separate from the source CI workflow. Its purpose is to
prove that the immutable release bundle produced by CI can cross a workflow boundary
and be admitted without rebuilding application code.

## What the gate proves

For each successful CI run on `main`:

1. the Stage Admission workflow checks out the exact promoted commit only for
   deployment manifests and verification scripts;
2. it downloads `hamoon-release-<commit>` from the completed source CI run;
3. the release bundle, SBOM digests and provenance are verified before execution;
4. backend and frontend OCI archives are loaded directly from the bundle;
5. loaded image IDs must equal the IDs recorded by the source release manifest;
6. the clean admission stack starts with `docker compose ... up --no-build`;
7. API readiness, OIDC discovery, NATS, MinIO and web/deep-link/API-proxy smoke checks run;
8. API, migration and worker containers must use the exact promoted backend image ID;
9. web must use the exact promoted frontend image ID;
10. a separate Stage admission attestation is generated, verified, and uploaded.

## Important boundary

This is a **Stage Admission** environment, not the externally hosted STAGE environment.
It intentionally uses disposable CI infrastructure and synthetic/local dependencies.
It proves artifact promotion and release identity. It does not claim that production
networking, DNS/TLS, managed PostgreSQL, external OIDC, Temporal Cloud, managed NATS,
or managed S3 have been deployed.

The hosted STAGE environment remains a separate infrastructure milestone and must
consume only a release bundle that already has a PASSED Stage Admission attestation.

## Promotion chain

```text
Commit
→ CI quality/integration
→ Build application images once
→ Vulnerability scan
→ Exact-image local release smoke
→ SBOM + provenance + verified release bundle
→ separate Stage Admission workflow
→ download same bundle
→ verify
→ load without rebuild
→ Stage-admission smoke
→ verified Stage attestation
→ hosted STAGE (future infrastructure milestone)
→ Release Approval
→ PROD
```
