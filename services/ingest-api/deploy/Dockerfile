FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/ingest-api/pyproject.toml /app/pyproject.toml
COPY services/ingest-api/src /app/src
COPY services/ingest-api/migrations /app/migrations

ENV INGEST_MIGRATIONS_DIR=/app/migrations

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

EXPOSE 8080

CMD ["sh", "-c", "ingest-api-migrate && ingest-api"]
