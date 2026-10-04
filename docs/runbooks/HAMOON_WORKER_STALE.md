# HAMOON_WORKER_STALE

## Signal

An Outbox or Temporal worker heartbeat for the exact deployed release is missing, stale, degraded, or belongs to another deployment.

## Diagnosis

Compare worker heartbeat deployment_id, git_commit, and image_id with /health/release and the Production Verification artifact. Inspect container/process state and dependency connectivity.

## Immediate actions

Restart only the affected worker through the approved platform operation. Do not bypass exact-release identity checks or run a mismatched image.

## Escalation

Escalate if restart does not restore a fresh exact-release heartbeat or if workflow/event processing correctness is uncertain.

## Safe recovery

After recovery, confirm worker_healthy equals 1, heartbeat age is fresh, backlog is not growing, and the runtime identity still matches the verified release.
