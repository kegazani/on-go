FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/replay-service/pyproject.toml /app/pyproject.toml
COPY services/replay-service/src /app/src

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

EXPOSE 8090

CMD ["replay-service"]
