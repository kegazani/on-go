# Scripts

Служебные скрипты для разработки, генерации контрактов, локального bootstrap
и автоматизации повторяющихся задач.

- `run-stack.sh` — поднимает `infra/compose/on-go-stack.yml` (+ TLS-профиль при `ON_GO_ENABLE_TLS_PROXY=1` в `.env`).
- `restart-stack.sh` — `docker compose down` **без** удаления томов (`-v` не используется), затем `up -d --build`: перезапуск бекенда с сохранением Postgres/MinIO/именованных томов; миграции БД применяет `ingest-api` при старте (`ingest-api-migrate`).
- `bootstrap-model-volume.sh` — копирует runtime bundle с хоста в том `on-go-models` (`ON_GO_MODEL_BUNDLE_SOURCE`).
- `run-signal-worker.sh` — одноразовый `signal-processing-worker` для `session_id`.
- `minio_audit_sessions.py` — обход бакета `on-go-raw`, проверка потоков и checksums (те же переменные окружения, что у ingest MinIO).
- `draft_personalization_profile_from_minio.py` — черновик тела `PUT /v1/profile` из реальных объектов `raw-sessions/<session_id>/` (manifest, `annotations/self-report.json`, опционально HR из sample-файлов в MinIO; опционально `--l2-model-predictions-json` для `l2_calibration.output_label_maps`). Переменные: `INGEST_S3_*` / `S3_*`, для `--subject-id` — `INGEST_DATABASE_DSN`.
- `push_l2_from_replay_infer.py` — batch PER-5: `POST {live}/v1/replay/infer` по `session_id`, агрегация majority по окнам (`activity` / `arousal_coarse` / `valence_coarse`), якоря из `annotations/self-report.json` в MinIO (как у draft-скрипта), затем `PATCH {personalization}/v1/profile/{subject_id}/l2-calibration`. Флаги: `--dry-run`, `--ensure-profile` (минимальный `PUT` при 404), `--write-replay-json`. Нужны `httpx`, те же `S3_*` что у ingest, поднятые `live-inference-api` и `personalization-worker`.

## ML Pipeline (J2)

`scripts/ml/` — автоматизация dataset build, training и evaluation:

- `run-dataset-build.sh` — импорт датасета (WESAD/EmoWear/G-REx/DAPPER)
- `run-training.sh` — запуск modeling-baselines с версионированием
- `run-full-pipeline.sh` — build + training

См. `scripts/ml/README.md`.
