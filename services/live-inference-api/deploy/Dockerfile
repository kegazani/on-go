FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/modeling-baselines/pyproject.toml /deps/modeling-baselines/pyproject.toml
COPY services/modeling-baselines/src /deps/modeling-baselines/src
COPY services/live-inference-api/pyproject.toml /app/pyproject.toml
COPY services/live-inference-api/src /app/src

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /deps/modeling-baselines && \
    pip install --no-cache-dir .

EXPOSE 8120

CMD ["live-inference-api"]
