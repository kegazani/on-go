# E2.16: Runtime Dashboard Endpoint Integration

## Статус

- Parent track: `E2`
- Step: `E2.16`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Интегрировать dashboard snapshot в runtime API, добавить CI schema-check и формализовать SLO freshness для canary monitoring.

## Что сделано

1. В `inference-api` добавлен monitoring endpoint:
   - `GET /v1/monitoring/valence-canary`
2. Добавлена загрузка dashboard snapshot через env:
   - `INFERENCE_VALENCE_DASHBOARD_SNAPSHOT_PATH`
   - `INFERENCE_VALENCE_DASHBOARD_FRESHNESS_SLO_MINUTES`
3. В `/health` добавлены поля:
   - `valence_dashboard_snapshot_loaded`
   - `valence_dashboard_fresh`
4. Обновлены OpenAPI и service README.
5. Добавлен CI schema-check:
   - `scripts/contracts/validate_valence_canary_snapshot.py`
   - job `contract-checks` в `.github/workflows/ci.yml`
6. Выполнен dry-run runtime dashboard behavior:
   - `scripts/ml/valence_e2_16_runtime_dashboard_dryrun.py`
   - `e2-16-runtime-dashboard-endpoint/*`

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-16-runtime-dashboard-endpoint/`

Файлы:

1. `evaluation-report.json`
2. `runtime-dashboard-response.json`
3. `research-report.md`

## Ключевой результат

Dashboard monitoring теперь доступен из runtime API с явным freshness-флагом по SLO; schema валидируется в CI через контракт `valence-canary-dashboard`.

## Следующий шаг

`E2.17` — End-to-end canary observability drill:

1. выполнить e2e проверку scheduler -> canary-state -> dashboard endpoint;
2. проверить CI contract-check + artifact publication в одном цикле;
3. зафиксировать operational sign-off checklist перед длительным continuous-run.
