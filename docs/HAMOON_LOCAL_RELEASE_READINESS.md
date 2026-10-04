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
- Private local evidence upload, integrity verification, quarantine and download.
- Structured PII-safe logs, Prometheus-compatible metrics and OpenTelemetry hooks.
- Data Health and Machine Health aggregate read models.
- Unit, contract, security, closed-loop Golden Path and infrastructure integration gates.
- One-command local Docker Compose stack, including the real web frontend runtime.

## Intentionally deferred integrations

These items require environment credentials, a selected deployment platform or an
external system and are not blockers for UI/Figma work:

- Production/stage server deployment and DNS/TLS.
- Real OpenAI candidate execution or any other external AI provider call.
- Real provider dispatch endpoints and provider sandboxes.
- Production S3-compatible evidence adapter/credentials.
- External OpenTelemetry backend, dashboards and alert delivery.
- Production secrets/KMS, backup and retention infrastructure.

The application contracts for these integrations must remain provider-agnostic.

## Local startup

Start the complete local stack:

```bash
docker compose up --build
```

The stack includes PostgreSQL, NATS JetStream, Keycloak, MinIO, Temporal, database
migration, API, the Nginx-served React frontend, outbox worker and Temporal worker.

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
docker compose config --quiet
uv run alembic heads
docker build -t hamoon-local-release .
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
10. container build green;
11. PostgreSQL-to-JetStream integration gate green;
12. complete local Docker Compose stack smoke green, including frontend SPA/deep-link/runtime-config/API-proxy checks.

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
