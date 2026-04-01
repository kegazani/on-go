# Operations Runbook (K3)

## Локальный запуск

### Полный стек (Postgres, MinIO, ingest-api, replay-service, inference-api, Redis)

```bash
docker compose -f infra/compose/on-go-stack.yml up --build
```

Или через скрипт:

```bash
./scripts/run-stack.sh
```

Порты:

| Сервис | Порт |
| --- | --- |
| ingest-api | 8080 |
| replay-service | 8090 |
| inference-api | 8100 |
| Postgres | 5432 |
| MinIO API | 9000 |
| MinIO Console | 9001 |
| Redis | 6379 |

### Health checks

```bash
curl -s http://localhost:8080/health
curl -s http://localhost:8090/health
curl -s http://localhost:8100/health
```

### Inference-api с моделью

Модель должна быть в volume `inference-models` или примонтирована. Для bind mount создайте `infra/compose/docker-compose.override.yml`:

```yaml
services:
  inference-api:
    volumes:
      - ./data/external/wesad/artifacts/wesad/wesad-v1/watch-only-baseline/models:/models:ro
```

## CI/CD

GitHub Actions (`.github/workflows/ci.yml`):

1. **unit-tests** — pytest для ingest-api, replay-service, signal-processing-worker, dataset-registry, modeling-baselines
2. **stack-e2e** — поднимает стек, запускает replay integration tests

## Observability

- `/health` — во всех HTTP-сервисах
- Логи — stdout/stderr, docker compose собирает
- Метрики (Prometheus) — планируется расширение

## Troubleshooting

### Порты заняты

```bash
lsof -i :8080
```

Остановить стек: `docker compose -f infra/compose/on-go-stack.yml down`

### База не инициализирована

```bash
docker compose -f infra/compose/on-go-stack.yml down -v
docker compose -f infra/compose/on-go-stack.yml up --build
```

### Inference-api: model_loaded=false

Проверить `INFERENCE_MODEL_DIR` и наличие файлов: `watch_only_centroid_activity.joblib`, `watch_only_centroid_arousal.joblib`, `feature_names.json`. См. `services/inference-api/README.md`.

## См. также

- `docs/setup/local-docker-setup.md`
- `docs/architecture/production-backend.md`
- `docs/operations/valence-canary-scheduler.md`
- `docs/operations/valence-canary-operational-signoff.md`
- `docs/operations/valence-canary-weekly-summary.md`
- `docs/operations/valence-canary-incident-template.md`
- `docs/operations/valence-canary-handoff-pack.md`
- `docs/operations/valence-canary-operations-hardening.md`
- `docs/operations/valence-canary-steady-state-kickoff.md`
