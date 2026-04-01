# Scripts

Служебные скрипты для разработки, генерации контрактов, локального bootstrap
и автоматизации повторяющихся задач.

- `run-stack.sh` — поднимает `infra/compose/on-go-stack.yml` (+ TLS-профиль при `ON_GO_ENABLE_TLS_PROXY=1` в `.env`).
- `bootstrap-model-volume.sh` — копирует runtime bundle с хоста в том `on-go-models` (`ON_GO_MODEL_BUNDLE_SOURCE`).
- `run-signal-worker.sh` — одноразовый `signal-processing-worker` для `session_id`.

## ML Pipeline (J2)

`scripts/ml/` — автоматизация dataset build, training и evaluation:

- `run-dataset-build.sh` — импорт датасета (WESAD/EmoWear/G-REx/DAPPER)
- `run-training.sh` — запуск modeling-baselines с версионированием
- `run-full-pipeline.sh` — build + training

См. `scripts/ml/README.md`.
