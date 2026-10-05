# Hamoon — Core Metrics Contract

Status: PB-121 is implemented as a low-cardinality, PII-safe Prometheus contract.

## Required coverage

Hamoon exposes core metrics for:

- API: request totals, 5xx totals, duration and active requests.
- Database: PostgreSQL dependency health and operational metric refresh failures.
- Outbox / NATS: durable outbox backlog plus publish success/failure counters.
- Temporal: exact-release worker heartbeat/health for the Temporal worker.
- PGOR: deterministic calculation attempts by mode and terminal status.
- AI: structured gateway executions by task class, configured provider code and terminal status.
- Provider integration: referral dispatch success/failure.
- Security: authentication/authorization denials by fixed boundary/reason labels.

## Privacy boundary

Metrics must never use household, referral, actor/user, request, trace, national ID or phone values as labels.

The Production Monitoring verifier rejects forbidden labels and requires the core metric families in both the baseline and post-probe snapshots.

## PGOR metric

`hamoon_pgor_calculations_total{mode,status}`

Current mode is `official`. Status values are bounded operational states such as `success`, `blocked` and `formula_missing`.

No PGOR score, household identifier or assessment identifier is a metric label.

## AI metric

`hamoon_ai_executions_total{task_class,provider,status}`

`task_class` comes from the versioned finite `AITaskClass` enum. Provider is the configured adapter code, not a model prompt, user or household value. Terminal status is one of the bounded gateway outcomes such as `success`, `routing_error`, `provider_error` or `schema_error`.

## Security metric

`hamoon_security_denials_total{boundary,reason}`

Only fixed security boundaries and reason codes are exposed. Tokens, subjects, actor IDs and protected resource IDs are never metric labels.

## Production gate

`scripts/verify_production_monitoring.py` requires all core metric families and continues to enforce exact-release worker health and forbidden-label checks.

This contract proves the built-in Prometheus surface. It does not claim that an external metrics backend, alert delivery channel or long-term retention service is configured unless separate Production evidence verifies it.
