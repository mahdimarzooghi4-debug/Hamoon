# Hamoon — Recovery Objectives Approval

Status: governance gate implemented; Production RPO/RTO values are not yet approved.

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

## Next verification boundary

A future Production recovery verification must consume this exact approval and prove,
using real provider/runtime evidence, that:

- managed PostgreSQL backup/PITR meets the approved PostgreSQL RPO;
- a restore exercise meets the approved PostgreSQL RTO;
- evidence storage durability/backup meets the approved evidence RPO;
- evidence recovery meets the approved evidence RTO;
- retention and conditional self-hosted recovery assets are satisfied where relevant.

Until that verification succeeds, Recovery Objectives approval is policy authorization,
not Production recovery readiness.
