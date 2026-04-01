FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/personalization-worker/pyproject.toml /app/pyproject.toml
COPY services/personalization-worker/src /app/src

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

EXPOSE 8110

CMD ["personalization-worker"]
