# HAMOON_API_CRITICAL_ERROR_SPIKE

## Signal

The five-minute API 5xx ratio remains above five percent for ten minutes.

## Diagnosis

Break down errors by normalized route and correlate with deployment markers, PostgreSQL health, worker health, and structured error codes. Never inspect raw PII payloads.

## Immediate actions

Protect critical flows, stop risky rollout activity, and identify whether the spike is dependency-specific or release-specific.

## Escalation

Escalate immediately when household decision, referral, outcome, or learning-loop operations are materially impaired.

## Safe recovery

Prefer the previously verified release if rollback is safer than forward-fixing. After recovery, re-run Production Verification and monitoring baseline.
