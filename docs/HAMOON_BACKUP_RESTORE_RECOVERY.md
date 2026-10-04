# Hamoon — Backup, Restore and Recovery

Status: Stage restore rehearsal contract implemented. Managed Production backup, PITR, retention and provider recovery remain external infrastructure milestones.

ADR-008 requires backups for PostgreSQL and object storage and explicitly states that backup without restore testing is insufficient.

## Automated Stage recovery rehearsal

After a successful Stage Admission, the Recovery Rehearsal workflow restores the same release in an isolated recovery exercise. It proves PostgreSQL backup/restore, Alembic identity, a synthetic database marker, evidence object mirror/archive/restore, and immutable release integrity.

The workflow persists metadata only. Raw database dumps and evidence backup contents are never uploaded as CI artifacts.

## Deliberate claim boundary

Stage evidence always records:

```text
production_managed_backup_verified=false
production_pitr_verified=false
external_backup_retention_verified=false
```

Therefore a successful rehearsal cannot be misrepresented as proof that a managed Production provider has backups, PITR or retention configured.

## Self-hosted conditional assets

When Production uses self-hosted infrastructure, independent recovery evidence is also required for NATS JetStream, Temporal persistence, and Keycloak database/config.

## RPO/RTO

Numeric RPO and RTO are intentionally not invented by this implementation. Their status remains PENDING_OPERATIONS_POLICY until the Operations owner approves explicit targets.

## Chain

```text
Release Artifact
→ Stage Admission
→ Recovery Rehearsal
→ managed Production backup/PITR/retention verification
→ Disaster Recovery readiness
```
