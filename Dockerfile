FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md alembic.ini ./
COPY migrations ./migrations
COPY src ./src

RUN uv pip install --system .

EXPOSE 8000

CMD ["uvicorn", "hamoon.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
