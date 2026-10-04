# HAMOON_POSTGRES_UNAVAILABLE

## Signal

The centralized operational scrape cannot query PostgreSQL or DB-backed metric refreshes repeatedly fail.

## Diagnosis

Check database reachability, connection saturation, TLS/network policy, migration state, and whether the runtime still reports the admitted deployment identity.

## Immediate actions

Avoid destructive failover actions. Restore connectivity or use the platform's approved database failover procedure, then confirm readiness and migration identity.

## Escalation

Escalate immediately because PostgreSQL is a critical dependency for accepted state, audit, outbox, governance, and learning data.

## Safe recovery

After database recovery, verify /health/ready, /health/release, outbox backlog age, and both worker heartbeats before reopening normal operations.
