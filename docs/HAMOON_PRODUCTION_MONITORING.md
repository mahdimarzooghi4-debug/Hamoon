# Hamoon — Production Monitoring Baseline

Status: Built-in monitoring baseline implemented; external observability backend
verification remains an infrastructure milestone.

A Production deployment is not considered operationally observable merely because its
health checks pass. Hamoon requires proof that runtime telemetry is protected, present,
PII-safe at the metric-label level, and actually changes when safe synthetic traffic is
generated.

## Production requirements

Production configuration is invalid unless:

- Prometheus metrics are enabled;
- a dedicated metrics access token of at least 32 characters is configured;
- OpenTelemetry is enabled;
- the OTLP exporter points to a non-local HTTPS endpoint.

The public application path may proxy `/metrics`, but unauthenticated access must
return HTTP 401. Monitoring systems use `X-Hamoon-Metrics-Token`.

## Automatic baseline

After a successful `Production Verification`, the
`Production Monitoring Baseline` workflow automatically:

1. resolves the exact Production verification artifact;
2. checks that unauthenticated metrics access is rejected;
3. reads the protected Prometheus endpoint using the GitHub secret
   `HAMOON_PRODUCTION_METRICS_TOKEN`;
4. captures a baseline metric snapshot;
5. performs five non-mutating readiness/release probes;
6. captures a second metric snapshot;
7. re-checks backend and frontend runtime identity;
8. verifies required Hamoon metric families exist;
9. rejects forbidden high-cardinality/sensitive labels such as household, user,
   request, trace, referral, national-ID, or phone identifiers;
10. requires the centralized PostgreSQL/outbox/worker metric families used by the
    enforced alert policy;
11. proves the readiness request counter advanced by at least the number of synthetic
    probes;
12. emits a hashed monitoring-baseline attestation.

## Deliberate boundary

The baseline records:

```text
external_observability_backend_verified=false
```

until an actual managed Prometheus/OTel/logging/alerting backend and alert routes are
provisioned and independently verified. The baseline must never be interpreted as proof
that dashboards, retention, paging, or external alert delivery exist.

## Chain

```text
Production Verification VERIFIED
→ protected metrics boundary
→ synthetic telemetry movement
→ runtime identity re-check
→ Production Monitoring Baseline PASSED
→ materialized Prometheus alert rules
→ external Alertmanager routing/delivery verification
→ external OTLP trace/log query + retention/dashboard verification
→ ongoing monitoring
→ improvement
```


## External trace/log verification

A separate `External Telemetry Verification` gate emits a fresh protected
Production telemetry probe and requires a remote verification adapter to prove that the
same trace and correlated sanitized log are queryable in the real external backend.
The adapter also supplies retention and dashboard evidence governed by
`ops/observability/external-telemetry-policy.json`. Until that gate succeeds,
Production Monitoring does not imply that external trace/log storage is verified.
