# HAMOON_RECOVERY_REHEARSAL

## Purpose

Prove that Hamoon backup artifacts can actually be restored. A configured backup job without a successful restore rehearsal is not sufficient recovery evidence.

## Stage rehearsal

The automated rehearsal uses synthetic/non-Production data only. It must:

1. verify the immutable release and Stage admission evidence;
2. apply the exact release migrations to an isolated PostgreSQL source database;
3. create a synthetic operational recovery marker;
4. create a synthetic object in the evidence bucket;
5. create a PostgreSQL custom-format backup;
6. mirror and archive the evidence bucket;
7. restore PostgreSQL into a separate database;
8. restore evidence into a separate bucket;
9. verify Alembic versions, the PostgreSQL marker, and the evidence object hash;
10. emit only hashes/metadata as the persistent recovery attestation.

## Production boundary

A Stage rehearsal does not prove managed PostgreSQL backups, point-in-time recovery, provider-side retention, cross-region durability, or recovery of self-hosted NATS, Temporal, or Keycloak.

## Failure response

If any restore differs from the source, block release readiness for the affected recovery path. Do not waive restore failure based on the existence of a backup file.

## Data handling

Never upload raw database dumps or evidence objects as CI artifacts. Persist only non-sensitive hashes, sizes, version identifiers, and pass/fail attestation metadata.

## Recovery objectives approval

Production RPO/RTO values are an Operations governance decision and must not be inferred from the Stage rehearsal. After a successful rehearsal, a human operator may run `Recovery Objectives Approval` for the exact commit and explicitly approve positive RPO/RTO targets for PostgreSQL and evidence object storage.

The approval is authorization-only. It does not prove managed Production backups, PITR, provider retention, or that the approved objectives are currently achieved.

## Production recovery verification

Run `Production Recovery Verification` only for the exact commit that has both a successful Recovery Objectives Approval and a successful Production Monitoring baseline. The workflow requires `VERIFY_PRODUCTION_RECOVERY` confirmation plus a remote HTTPS verification adapter configured through `HAMOON_RECOVERY_VERIFICATION_URL` and `HAMOON_RECOVERY_VERIFICATION_TOKEN`.

The provider observation must prove PostgreSQL backup/PITR/retention/encryption and an isolated restore with schema and critical-data sanity. Evidence object storage must prove backup or versioning, retention, encryption, isolated restore, integrity, and critical-evidence sanity. The verifier computes RPO/RTO from timestamps and compares them to the exact approved objectives; provider Booleans cannot override a missed objective.

For self-hosted Production, the same evidence must also prove backup restore and integrity for NATS JetStream, Temporal persistence, and Keycloak database/config. Managed Production must not claim those self-hosted assets.

The raw provider observation is ephemeral and is not uploaded. Secret-like evidence fields are rejected. Only the sanitized immutable Production recovery attestation may persist.
