# HAMOON_METRICS_MISSING

## Signal

The monitoring backend no longer sees Hamoon HTTP metrics for five minutes.

## Diagnosis

Confirm the Production endpoint is reachable, check the protected /metrics scrape with the monitoring credential, then inspect collector/scraper health and recent deployment identity.

## Immediate actions

Do not disable authentication. Restore scraper credentials or routing, verify /health/release still matches the admitted deployment, and confirm metrics resume.

## Escalation

Escalate to Production Ops if the scrape path remains absent for ten minutes or if runtime identity cannot be verified.

## Safe recovery

Recover the observability path without changing business data. If a deployment caused the loss, use the approved rollback path and re-run Production Verification.
