# Hamoon — Recovery Objectives Approval

Status: governance gate implemented; Production RPO/RTO values exist only when a human
runs the approval workflow for an exact successful recovery rehearsal.

RPO and RTO are business/operations commitments. Hamoon must not invent them from
technical benchmarks or infer them from a Stage restore rehearsal.

## Approval workflow

The manual `Recovery Objectives Approval` workflow requires:

- an exact commit SHA on `main`;
- a successful `Recovery Rehearsal` for that same commit;
- explicit `APPROVE_RECOVERY_OBJECTIVES` confirmation;
- positive RPO and RTO values for PostgreSQL;
- positive RPO and RTO values for evidence object storage;
- a change/governance reference;
- a human rationale;
- a non-bot GitHub approver.

The immutable artifact is named:

```text
hamoon-recovery-objectives-<commit-sha>
```

## Evidence boundary

The approval records:

```text
authorization_only=true
production_recovery_verified=false
production_managed_backup_verified=false
production_pitr_verified=false
external_backup_retention_verified=false
```

This is deliberate. Human approval defines the targets; it does not prove that the
Production platform currently meets them.

## Production verification boundary

The `Production Recovery Verification` gate consumes this exact approval and real
provider/runtime evidence. It independently computes whether PostgreSQL and evidence
storage satisfy the approved RPO/RTO, requires restore/PITR/retention/encryption and
sanity evidence, and requires conditional NATS/Temporal/Keycloak recovery when
Production is self-hosted.

Until that workflow succeeds for the exact deployed commit, Recovery Objectives
approval is policy authorization, not Production recovery readiness.
