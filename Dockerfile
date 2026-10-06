FROM python:3.12-slim

ARG HAMOON_APPLICATION_VERSION=0.1.0
ARG HAMOON_GIT_COMMIT=development

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    HAMOON_APPLICATION_VERSION="${HAMOON_APPLICATION_VERSION}" \
    HAMOON_GIT_COMMIT="${HAMOON_GIT_COMMIT}"

LABEL org.opencontainers.image.version="${HAMOON_APPLICATION_VERSION}" \
      org.opencontainers.image.revision="${HAMOON_GIT_COMMIT}"

WORKDIR /app

RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md alembic.ini ./
COPY requirements ./requirements
COPY migrations ./migrations
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable \
    && uv pip install \
      --python /app/.venv/bin/python \
      --requirement requirements/internal-ai-gemma4.txt

EXPOSE 8000

CMD ["uvicorn", "hamoon.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
