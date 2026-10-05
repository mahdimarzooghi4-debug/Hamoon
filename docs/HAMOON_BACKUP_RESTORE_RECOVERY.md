# Hamoon — Backup, Restore and Recovery

Status: Stage restore rehearsal, explicit recovery-objectives approval, and the
Production recovery verification gate are implemented. Managed Production backup,
PITR, retention, and recovery are not claimed as verified until the external Production
verification workflow succeeds with real provider/runtime evidence.

ADR-008 requires backups for PostgreSQL and object storage and explicitly states that
backup without restore testing is insufficient recovery evidence.

## Automated Stage recovery rehearsal

After a successful Stage Admission, the Recovery Rehearsal workflow restores the same
release in an isolated recovery exercise. It proves PostgreSQL backup/restore, Alembic
identity, a synthetic database marker, evidence object mirror/archive/restore, and
immutable release integrity.

The workflow persists metadata only. Raw database dumps and evidence backup contents
are never uploaded as CI artifacts.

## Deliberate Stage claim boundary

Stage evidence always records:

```text
production_managed_backup_verified=false
production_pitr_verified=false
external_backup_retention_verified=false
```

Therefore a successful rehearsal cannot be misrepresented as proof that a managed
Production provider has backups, PITR or retention configured.

## Recovery objectives

RPO and RTO are business/operations commitments and are never inferred from a Stage
benchmark. The manual `Recovery Objectives Approval` workflow requires a human to
approve positive targets for PostgreSQL and evidence object storage against the exact
successful recovery rehearsal.

That approval remains authorization-only. It cannot claim Production recovery readiness.

## Production recovery verification

The manual `Production Recovery Verification` workflow consumes the exact recovery
approval, the referenced Stage rehearsal, a successful Production monitoring baseline,
and real evidence from a remote HTTPS recovery verification adapter.

The verifier independently computes RPO/RTO from provider timestamps, requires real
restore/PITR/retention/encryption/sanity evidence, and binds everything to the exact
Production commit and deployment ID. Only this gate can emit an immutable attestation
with `production_recovery_verified=true`.

Raw provider observations are not uploaded. Secret-like fields are rejected and only a
sanitized attestation plus cryptographic hashes persist.

## Self-hosted conditional assets

When Production uses self-hosted infrastructure, independent recovery evidence is also
required for NATS JetStream, Temporal persistence, and Keycloak database/config. A
managed-provider observation must not claim those self-hosted assets.

## Chain

```text
Release Artifact
→ Stage Admission
→ Recovery Rehearsal
→ Recovery Objectives Approval
→ Production Verification / Monitoring
→ Production Recovery Verification
→ Disaster Recovery readiness evidence
```

External infrastructure is never assumed. Without a successful Production recovery
verification artifact backed by real provider/runtime evidence, managed backup, PITR,
retention, and Production restore readiness remain unverified.
