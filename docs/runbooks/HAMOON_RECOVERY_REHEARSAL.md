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
