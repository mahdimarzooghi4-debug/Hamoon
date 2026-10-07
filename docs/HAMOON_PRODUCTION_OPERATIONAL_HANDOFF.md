# Hamoon — Production Operational Handoff

Status: repository-side product implementation complete; external infrastructure inputs pending.

This document is the single handoff checklist for taking the current Hamoon release from
green CI/Stage/Recovery into a real hosted Production environment. It does not authorize
Production deployment by itself.

## 1. Product boundary

The product UI, backend, governed learning loop, Gemma 4 training/execution core, Evaluation,
human promotion, release evidence, rollback, monitoring, and recovery contracts are implemented.

Production AI is internal to Hamoon:

- execution mode is `IN_PROCESS`;
- there is no AI endpoint/token;
- there is no standalone inference service;
- base checkpoint loading is local/private and network model download is disabled;
- trained adapters are stored in the private immutable internal-model artifact store.

## 2. Environment-owned infrastructure inputs

The Production environment must supply real, non-placeholder values for:

- container/runtime target and public HTTPS Hamoon endpoint;
- PostgreSQL;
- NATS JetStream;
- Temporal;
- OIDC/Keycloak or approved enterprise OIDC;
- private S3-compatible evidence storage;
- external evidence scanner;
- private S3-compatible internal-model artifact store;
- read-only mounted Gemma 4 base checkpoint matching the pinned revision/digests;
- explicit Gemma training and generation configuration;
- provider-dispatch integration configuration;
- OTLP traces/logs backend;
- protected metrics access;
- Alertmanager delivery path;
- backup/restore provider and recovery verification adapter;
- DNS/TLS and secret management.

No repository workflow or application code may fabricate any of these external values.

## 3. Production runtime configuration

The runtime uses the `HAMOON_` environment prefix. At minimum the external platform must
provide Production-safe values for the configuration enforced by
`src/hamoon/app/config/settings.py`, including:

`HAMOON_ENVIRONMENT=production`

`HAMOON_APPLICATION_VERSION`
`HAMOON_GIT_COMMIT`
`HAMOON_IMAGE_ID`
`HAMOON_DEPLOYMENT_ID`

`HAMOON_DATABASE_URL`
`HAMOON_NATS_URL`
`HAMOON_TEMPORAL_ADDRESS`
`HAMOON_TEMPORAL_NAMESPACE`

`HAMOON_OIDC_ISSUER_URL`
`HAMOON_OIDC_AUDIENCE`
`HAMOON_OIDC_JWKS_URL`

`HAMOON_EVIDENCE_STORAGE_BACKEND=s3`
`HAMOON_EVIDENCE_S3_ENDPOINT`
`HAMOON_EVIDENCE_S3_ACCESS_KEY`
`HAMOON_EVIDENCE_S3_SECRET_KEY`
`HAMOON_EVIDENCE_S3_BUCKET`
`HAMOON_EVIDENCE_S3_REGION`
`HAMOON_EVIDENCE_SCANNER_BACKEND`
`HAMOON_EVIDENCE_SCANNER_ENDPOINT`
`HAMOON_EVIDENCE_SCANNER_TOKEN`
`HAMOON_EVIDENCE_SIGNING_SECRET`

`HAMOON_INTERNAL_MODEL_ARTIFACT_STORAGE_BACKEND=s3`
`HAMOON_INTERNAL_MODEL_ARTIFACT_S3_ENDPOINT`
`HAMOON_INTERNAL_MODEL_ARTIFACT_S3_ACCESS_KEY`
`HAMOON_INTERNAL_MODEL_ARTIFACT_S3_SECRET_KEY`
`HAMOON_INTERNAL_MODEL_ARTIFACT_S3_BUCKET`
`HAMOON_INTERNAL_MODEL_ARTIFACT_S3_REGION`

`HAMOON_GEMMA4_BASE_CHECKPOINT_ROOT`
`HAMOON_GEMMA4_TRAINING_CONFIG_JSON`
`HAMOON_GEMMA4_GENERATION_CONFIG_JSON`

`HAMOON_PROVIDER_DISPATCH_CONFIG`

`HAMOON_OTEL_ENABLED=true`
`HAMOON_OTEL_EXPORTER_OTLP_ENDPOINT`
`HAMOON_OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`
`HAMOON_OTEL_EXPORTER_OTLP_HEADERS`
`HAMOON_METRICS_ENABLED=true`
`HAMOON_METRICS_ACCESS_TOKEN`
`HAMOON_STRUCTURED_LOGGING=true`

`HAMOON_OPENAI_API_KEY` must not be configured. Production startup rejects external AI
credentials.

## 4. GitHub Production environment secrets

The existing workflows consume these environment-owned secrets:

Deployment:
- `HAMOON_DEPLOY_ORCHESTRATOR_ENDPOINT`
- `HAMOON_DEPLOY_ORCHESTRATOR_TOKEN`

Production metrics / telemetry:
- `HAMOON_PRODUCTION_METRICS_TOKEN`
- `HAMOON_OBSERVABILITY_VERIFICATION_URL`
- `HAMOON_OBSERVABILITY_VERIFICATION_TOKEN`

Alert delivery:
- `HAMOON_ALERTMANAGER_URL`
- `HAMOON_ALERTMANAGER_METRICS_URL`
- `HAMOON_ALERTMANAGER_BEARER_TOKEN`

Evidence integration:
- `HAMOON_EVIDENCE_S3_ENDPOINT`
- `HAMOON_EVIDENCE_S3_ACCESS_KEY`
- `HAMOON_EVIDENCE_S3_SECRET_KEY`
- `HAMOON_EVIDENCE_S3_BUCKET`
- `HAMOON_EVIDENCE_S3_REGION`
- `HAMOON_EVIDENCE_SCANNER_ENDPOINT`
- `HAMOON_EVIDENCE_SCANNER_TOKEN`

Provider integration:
- `HAMOON_PROVIDER_DISPATCH_CONFIG`

Recovery verification:
- `HAMOON_RECOVERY_VERIFICATION_URL`
- `HAMOON_RECOVERY_VERIFICATION_TOKEN`

Secrets belong in the GitHub `production` Environment or the external platform secret
manager as appropriate. They must not be committed to the repository or image.

## 5. Go-live execution order

The repository-side release chain is:

```text
CI
→ Stage Admission
→ Recovery Rehearsal
→ explicit Human Release Approval
→ Production Deployment Admission
→ Production Deploy
→ Production Verification
→ Production Monitoring Baseline
→ External Evidence Integration Verification
→ External Provider Integration Verification
→ External Telemetry Verification
→ External Alert Delivery Verification
→ Recovery Objectives Approval
→ Production Recovery Verification
→ Monitoring / Improvement
```

External integration verification may be performed before the final go-live window when the
target infrastructure already exists, but Production verification/monitoring steps must remain
bound to the exact deployed release evidence.

## 6. Final external blockers

The repository cannot complete the following without real environment ownership:

- choose/provision the hosting target;
- assign DNS and issue TLS certificates;
- create Production databases, streams/namespaces, buckets and OIDC clients;
- provide real secrets/credentials;
- mount the approved Gemma checkpoint;
- select actual hardware sizing from benchmark evidence;
- supply explicit Gemma training/generation values from benchmark evidence;
- connect the real provider-dispatch integration;
- configure the real observability/alerting backend;
- enable real backup/PITR/retention and recovery verification.

Until those inputs exist, Hamoon remains intentionally fail-closed rather than substituting
local defaults or invented Production values.

## 7. Production authorization

Passing every automated check is necessary but never sufficient for model or application
Production activation. Model Production promotion remains an explicit ADMIN action, and hosted
Production deployment remains a separate explicitly authorized release operation.
