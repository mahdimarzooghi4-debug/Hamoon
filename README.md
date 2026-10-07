# Hamoon

Hamoon is an AI-first household empowerment decision-and-learning system.

## Local bootstrap

Requirements:

- Python 3.12
- uv
- Docker / Docker Compose

The repository commits `uv.lock`; dependency resolution is therefore reproducible.

Install the locked Python environment:

```bash
uv sync --frozen --all-extras
```

Start the complete local platform:

```bash
docker compose up --build
```

This starts the local PostgreSQL, NATS JetStream, Keycloak, MinIO, Temporal,
database migration service, FastAPI application, outbox worker and Temporal worker.

Local endpoints:

```text
API:             http://localhost:8000
API liveness:    http://localhost:8000/health/live
API readiness:   http://localhost:8000/health/ready
Metrics:         http://localhost:8000/metrics
Keycloak:        http://localhost:8081
MinIO console:   http://localhost:9001
NATS monitoring: http://localhost:8222
Temporal:        localhost:7233
```

For API-only development outside Docker:

```bash
cp .env.example .env
uv run alembic upgrade head
uv run uvicorn hamoon.app.main:app --reload
```

## Verification

```bash
uv lock --check
uv run ruff check .
uv run pyright src
uv run pytest tests/unit
uv run pytest tests/contract
docker compose config --quiet
uv run alembic heads
docker build -t hamoon-local-release .
```

The authoritative release gate is GitHub Actions CI, which additionally runs:

- security regression tests;
- closed-loop Reassessment → Outcome → Learning Golden Path;
- Diagnosis and Outcome offline evaluation replay gates;
- fresh PostgreSQL migration from zero;
- PostgreSQL evidence persistence;
- Data/Machine Health queries against PostgreSQL;
- PostgreSQL Outbox → NATS JetStream publish/consume integration;
- complete local-stack boot smoke.

Production hosting, real service-provider integrations, private storage, and internal
model checkpoint/artifact provisioning are intentionally outside the local release boundary.
Production AI itself remains internal to Hamoon and has no external model endpoint/token.

See `docs/HAMOON_LOCAL_RELEASE_READINESS.md` for the exact Go/No-Go contract.


## Frontend

The canonical Persian/RTL product UI lives in `frontend/` and is implemented against the
existing internal Hamoon API contracts. The first vertical slice contains the application shell,
Figma-derived design tokens, the real work queue, and work-item claiming with optimistic
version handling.

```bash
cd frontend
npm install
npm run dev
```

Frontend verification:

```bash
npm run typecheck
npm run build
```

Browser authentication uses OIDC Authorization Code + PKCE against the configured Keycloak
issuer. The local `hamoon-web` client accepts the Vite development origin
`http://localhost:5173`. Access and refresh tokens are session-scoped in the browser and
authenticated API calls never fall back to fake product data.
