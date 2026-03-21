FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/signal-processing-worker/pyproject.toml /app/pyproject.toml
COPY services/signal-processing-worker/src /app/src

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

CMD ["signal-processing-worker", "--help"]
