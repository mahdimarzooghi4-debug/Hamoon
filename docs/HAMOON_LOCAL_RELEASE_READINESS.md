# Hamoon — Local Release Readiness

Status: Internal backend/local platform completion gate.

This document defines the release boundary that must be green before Hamoon UI work
starts. It intentionally excludes production hosting and external provider APIs.

## Completed local boundary

The local product boundary includes:

- PostgreSQL migrations and versioned domain persistence.
- OIDC/RBAC contracts and security regression tests.
- Household, accepted state, assessment and deterministic PGOR.
- AI gateway boundaries with FakeAIProvider for local execution.
- Human-reviewed diagnosis, prescription, provider selection and outcome.
- Referral lifecycle and provider callback/result contracts.
- Temporal reassessment orchestration and reconciliation.
- Learning signals, curated datasets and evaluation/promotion governance.
- Durable PostgreSQL outbox with NATS JetStream delivery and retry.
- Private S3-compatible evidence storage through the real MinIO adapter, with integrity verification, quarantine and download; Production additionally requires a remote HTTPS evidence scanner and secret token.
- Structured PII-safe logs, Prometheus-compatible metrics and OpenTelemetry hooks.
- Authorization-scoped Caseworker Work Queue with source-linked review, follow-up, reassessment, data-completion and conflict tasks.
- Data Health and Machine Health aggregate read models.
- Unit, contract, security, closed-loop Golden Path and infrastructure integration gates.
- One-command local Docker Compose stack, including the real web frontend runtime.
- Build-once release artifact chain: backend/frontend images are built once, scanned, smoke-tested by exact image ID, then packaged with a digest manifest.
- Supply-chain metadata for the tested artifacts: CycloneDX SBOMs, SLSA-style in-toto provenance, SHA-256 checksums, and an offline bundle verifier.

## Intentionally deferred integrations

These items require environment credentials, a selected deployment platform or an
external system and are not blockers for UI/Figma work:

- Production/stage server deployment and DNS/TLS.
- Real OpenAI candidate execution or any other external AI provider call.
- Real provider dispatch endpoints, provider sandboxes and runtime credentials. The provider-neutral dispatch adapter and Temporal ReferralWorkflow are implemented in-repo.
- Production S3-compatible evidence adapter/credentials.
- External OpenTelemetry backend, dashboards and alert delivery.
- Production secrets/KMS, backup and retention infrastructure.

Production startup itself is no longer permissive: setting `HAMOON_ENVIRONMENT=production`
activates fail-fast validation that rejects local endpoints, local Evidence storage,
non-HTTPS OIDC/S3 endpoints, MinIO bootstrap credentials, and the local Evidence
capability-signing secret. The same `Settings` boundary is shared by API, workers,
and migrations.

The application contracts for these integrations must remain provider-agnostic.

## Local startup

Start the complete local stack:

```bash
docker compose up --build
```

The stack includes PostgreSQL, NATS JetStream, Keycloak, MinIO, Temporal, database
migration, API, the Nginx-served React frontend, outbox worker, Temporal worker and provider worker. Evidence bytes are stored in the private MinIO bucket rather than the API container filesystem.

Web product:

```text
http://localhost:3000
```

API:

```text
http://localhost:8000
```

Key operational endpoints:

```text
GET /health/live
GET /health/ready
GET /metrics
GET /api/v1/admin/health/data
GET /api/v1/admin/health/machine
```

## Release verification

The authoritative gate is GitHub Actions CI. Locally the equivalent checks are:

```bash
uv sync --all-extras
uv run ruff check .
uv run pyright src
uv run pytest tests/unit
uv run pytest tests/contract
uv run pytest tests/unit/config/test_settings.py
docker compose config --quiet
uv run alembic heads
docker build -t hamoon-local-release .
# CI builds each application OCI image exactly once after integration,
# scans those exact images, runs the complete stack from those exact image IDs,
# and packages them with a SHA-256 manifest for later promotion.
```

Infrastructure integration verification additionally requires local PostgreSQL and NATS:

```bash
docker compose up -d postgres nats
uv run alembic upgrade head
uv run pytest tests/integration
docker compose down -v
```

## Go criteria for UI/Figma

UI/Figma work may start only when the current main commit has:

1. committed dependency lock is current and frozen install succeeds;
2. lint green;
3. strict type-check green;
4. unit tests green;
5. contract tests green;
6. security regression gate green;
7. closed-loop Golden Path green;
8. diagnosis and outcome evaluation replay gates green;
9. Alembic topology and fresh-database migration green;
10. PostgreSQL/JetStream integration gate green, including real S3-compatible Evidence round-trip against MinIO;
11. backend and frontend OCI images are each built exactly once for the release gate;
12. those exact images pass the pinned Trivy HIGH/CRITICAL vulnerability gate;
13. the complete local stack smoke uses those exact scanned image IDs, including frontend SPA/deep-link/runtime-config/API-proxy checks;
14. successful main runs package both tested images plus commit/image/archive SHA-256 identity into an immutable GitHub Actions release artifact;
15. that artifact includes CycloneDX SBOMs and SLSA-style provenance, and the offline release verifier passes before upload.

A red gate means the backend contract is not considered frozen for UI work.

## Product invariants that UI must preserve

- PGOR is deterministic and authoritative; AI never edits it.
- Accepted State is a human/policy-controlled state, never an AI decision.
- AI outputs are proposals and require the defined human review boundary.
- Provider Result is not Hamoon Outcome.
- Outcome interpretation cannot claim causality by default.
- Learning signals never retrain or promote production automatically.
- Production routing requires curated data, offline evaluation, attestation and explicit promotion.
- Evidence is private, scoped, integrity-verified and quarantined until accepted.
- Sensitive data must not appear in logs, metrics or object keys.
