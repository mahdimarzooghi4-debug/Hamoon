# Hamoon — External Alert Delivery Verification

Status: executable verification gate implemented; external Alertmanager infrastructure
and credentials are not provisioned by this repository.

Hamoon does not treat a checked-in alert expression as proof that Production paging
works. External alert delivery becomes VERIFIED only after a real Alertmanager instance
accepts a synthetic alert, routes it to the expected receiver, and exposes notification
metrics showing a notification attempt without a corresponding failure.

## Materialized production rules

The governed alert policy remains:

```text
ops/observability/alert-policy.json
```

and the deployable Prometheus-compatible rule document is:

```text
ops/observability/prometheus/hamoon-alerts.yml
```

The rule file is JSON-encoded YAML. CI verifies exact one-to-one agreement for alert
name, PromQL expression, duration, severity, category, summary and runbook.

## External gate prerequisites

The manual `External Alert Delivery Verification` workflow requires a successful
`Production Monitoring Baseline` for the exact commit plus these GitHub secrets:

```text
HAMOON_ALERTMANAGER_URL
HAMOON_ALERTMANAGER_METRICS_URL
HAMOON_ALERTMANAGER_BEARER_TOKEN
```

Both URLs must be remote HTTPS endpoints. The Alertmanager API must expose API v2 and
the metrics endpoint must include the `receiver` label on notification metrics for the
configured receiver. This is intentionally strict because aggregate integration-only
metrics cannot prove which Production receiver was exercised.

The operator supplies the exact receiver and integration labels when dispatching the
workflow.

## What the verification proves

The workflow:

1. resolves the successful Production Monitoring artifact for the exact commit;
2. re-validates alert policy and materialized rules;
3. validates Alertmanager API status and receiver existence;
4. snapshots receiver-labelled notification/failure counters;
5. posts a PII-free synthetic critical alert through Alertmanager API v2;
6. proves the alert is active and routed to the expected receiver;
7. waits for that receiver/integration notification counter to advance;
8. rejects any increase in notification failures;
9. hashes all external observations into an immutable attestation;
10. resolves the synthetic alert.

Only the resulting artifact may state:

```text
external_observability_backend_verified=true
alertmanager_routing_verified=true
alert_delivery_verified=true
```

## Deliberate limits

This gate verifies the Alertmanager routing/delivery boundary. It does not by itself
prove dashboard quality, long-term retention, every OTEL signal, or every future alert
family. Those remain separate operational requirements.

Until the workflow runs successfully against real infrastructure, Hamoon must continue
to report the external alerting backend as unverified.
