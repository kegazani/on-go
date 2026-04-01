# inference-api

Online inference API для предсказаний direct outputs по feature vector (K2).
Включает runtime guardrails для scoped `valence` policy (E2.11).
Поддерживает canary auto-disable state для scoped режима (E2.13).
Поддерживает runtime dashboard snapshot endpoint и freshness-check (E2.16).
На шаге K5.2 контракт расширен canonical semantic fields (`derived_state`, `confidence`, `fallback_reason`, `claim_level`).

## Контракт

- `contracts/http/inference-api.openapi.yaml`

## Endpoints

- `GET /health` — status, model_loaded
- `POST /v1/predict` — `{"feature_vector": {"feat1": 0.1, ...}}` → direct outputs + semantic layer:
  - `activity` (legacy), `activity_class`, `arousal_coarse`, `valence_coarse`
  - `derived_state`, `confidence`, `fallback_reason`, `claim_level`
  - `valence_scoped_status`
- `GET /v1/policy/valence-scoped` — активная policy-конфигурация scoped режима
- `GET /v1/monitoring/valence-canary` — dashboard snapshot + freshness-флаг

## Конфигурация

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `INFERENCE_APP_HOST` | 0.0.0.0 | Host |
| `INFERENCE_APP_PORT` | 8100 | Port |
| `INFERENCE_APP_LOG_LEVEL` | info | Log level |
| `INFERENCE_MODEL_DIR` | /models | Путь к директории с model bundle |
| `INFERENCE_VALENCE_SCOPED_POLICY_PATH` | unset | Путь к `scoped-policy.json` для valence guardrails |
| `INFERENCE_VALENCE_CANARY_STATE_PATH` | unset | Путь к `canary-state.json` для auto-disable/effective-mode override |
| `INFERENCE_VALENCE_DASHBOARD_SNAPSHOT_PATH` | unset | Путь к `dashboard-snapshot.json` для runtime monitoring endpoint |
| `INFERENCE_VALENCE_DASHBOARD_FRESHNESS_SLO_MINUTES` | 120 | SLO-окно свежести dashboard snapshot |

## Model bundle

Канонический runtime-format теперь manifest-driven:

- `model-bundle.manifest.json` — per-track manifest
- `*.joblib` — classifier per direct output
- `*_feature_names.json` — feature space per track

Manifest позволяет разводить разные feature profiles по track-ам:

- `activity` может жить на `watch-only` motion feature space
- `arousal_coarse` может жить на `fusion` feature space
- `valence_coarse` может быть optional/scoped track с отдельным model path

Схема manifest:

- `contracts/operations/inference-bundle-manifest.schema.json`

Legacy fallback пока сохранен для старого watch-only bundle:

- `watch_only_centroid_activity.joblib`
- `watch_only_centroid_arousal.joblib`
- `watch_only_centroid_valence.joblib` (optional)
- `feature_names.json`

Legacy bundle нужен только для обратной совместимости и не считается каноническим fusion runtime contract.

## Запуск локально

```bash
cd services/inference-api
pip install -e .
INFERENCE_MODEL_DIR=/path/to/models inference-api
```

С policy:

```bash
INFERENCE_MODEL_DIR=/path/to/models \
INFERENCE_VALENCE_SCOPED_POLICY_PATH=/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/scoped-policy.json \
INFERENCE_VALENCE_CANARY_STATE_PATH=/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/canary-state.json \
INFERENCE_VALENCE_DASHBOARD_SNAPSHOT_PATH=/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/e2-15-valence-scheduler-dashboard/dashboard-snapshot.json \
inference-api
```

Или с docker compose (модель в volume `inference-models` — пустой по умолчанию; для dev используйте override с bind mount):

```bash
INFERENCE_MODEL_DIR=$PWD/data/external/wesad/artifacts/wesad/wesad-v1/watch-only-baseline/models docker compose -f infra/compose/on-go-stack.yml up
```

Для bind mount создайте `infra/compose/docker-compose.override.yml`:

```yaml
services:
  inference-api:
    volumes:
      - ./data/external/wesad/artifacts/wesad/wesad-v1/watch-only-baseline/models:/models:ro
```
