# Hamoon

Hamoon is an AI-first household empowerment decision and learning system.

## Local bootstrap

Requirements:

- Python 3.12
- uv
- Docker / Docker Compose

Start infrastructure:

```bash
docker compose up -d
```

Create local environment:

```bash
cp .env.example .env
uv sync --all-extras
```

Run API:

```bash
uv run uvicorn hamoon.app.main:app --reload
```

Checks:

```bash
uv run ruff check .
uv run pyright src tests
uv run pytest
```

Health:

```text
GET /health/live
GET /health/ready
```

Architecture decisions and Sprint plans live under `docs/`.
