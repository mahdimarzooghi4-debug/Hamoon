# Hamoon — External Telemetry Verification

Status: runtime trace/log export and executable verification contract implemented;
external observability infrastructure and its verification adapter are not provisioned by
this repository.

Hamoon does not treat an OTLP exporter configuration as proof that telemetry is
queryable, retained, or operationally useful. Verification is tied to a fresh,
PII-free Production probe and to the exact monitored release.

## Runtime signals

The API exports:

- distributed traces through OTLP/HTTP;
- sanitized application logs through OTLP/HTTP;
- release resource attributes:
  - service name and version;
  - environment;
  - Git commit;
  - image ID;
  - deployment ID.

The log bridge exports only the already-approved safe structured fields and sanitizes
the message before it reaches the OTLP pipeline.

## Synthetic probe

A protected endpoint exists at:

```text
POST /health/telemetry-probe
```

It requires the same dedicated monitoring credential used for protected metrics. The
endpoint creates no business data. It emits:

- span name `hamoon.observability.probe`;
- a random `hamoon-otel-...` probe ID;
- an application log `Observability verification probe emitted`;
- trace/log correlation for the same trace;
- commit and deployment identity.

## Stage proof

Stage Admission runs an ephemeral OpenTelemetry Collector and writes OTLP traces and
logs to separate capture files. Admission fails unless the same probe ID, release SHA,
deployment ID, and probe log are observed in the collector output. The Stage monitoring
credential is also checked not to appear in exported logs.

This makes Stage demonstrate actual OTLP trace/log transport rather than only successful
SDK initialization.

## External Production policy

`ops/observability/external-telemetry-policy.json` defines the V1 minimum:

- trace retention: 14 days;
- log retention: 30 days;
- required Platform dashboard;
- required Async Workers dashboard;
- required release/resource attributes;
- forbidden sensitive evidence fields.

These are operational minima, not business/audit retention requirements.

## Verification adapter

Observability products have different query APIs. Hamoon therefore uses a small
vendor-neutral verification-adapter contract instead of embedding a vendor-specific
query language in the repository.

The adapter endpoint is configured through:

```text
HAMOON_OBSERVABILITY_VERIFICATION_URL
HAMOON_OBSERVABILITY_VERIFICATION_TOKEN
```

The workflow sends the fresh probe ID, trace ID, commit SHA, and deployment ID. The
adapter must query the real external telemetry backend and return normalized evidence
covering:

- the exact probe trace;
- the correlated probe log;
- exact Production resource identity;
- configured trace/log retention;
- HTTPS evidence for retention configuration;
- availability and URLs of required dashboards.

Because every verification uses a random runtime-generated probe ID, stale static
evidence cannot satisfy the contract.

## External workflow

The manual `External Telemetry Verification` workflow requires an existing successful
`Production Monitoring Baseline` for the exact commit and:

```text
HAMOON_PRODUCTION_METRICS_TOKEN
HAMOON_OBSERVABILITY_VERIFICATION_URL
HAMOON_OBSERVABILITY_VERIFICATION_TOKEN
```

Only a successful run may emit evidence with:

```text
external_telemetry_backend_verified=true
trace_ingestion_verified=true
log_ingestion_verified=true
retention_verified=true
dashboards_verified=true
```

## Deliberate limits

This gate does not claim that all future ADR-007 dashboards already exist. V1 verifies
only dashboards supported by telemetry Hamoon currently exports centrally. Data-health,
AI, Referral, and Learning dashboards remain separate implementation work until their
required metric families are real.

Until a real external backend and adapter pass this workflow, external telemetry remains
unverified.
