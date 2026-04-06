# personalization-worker

Profile store, calibration and adaptation for personalized inference.

## Endpoints

- `GET /health` — health check
- `GET /v1/profile/{subject_id}` — get user profile (404 if not found)
- `PUT /v1/profile` — create/update profile
- `PATCH /v1/profile/{subject_id}/l2-calibration` — merge `output_label_maps` and optional `adaptation_state` fields without replacing the whole profile (client path after calibration)

## Config (env)

- `PERSONALIZATION_APP_HOST` (default: 0.0.0.0)
- `PERSONALIZATION_APP_PORT` (default: 8110)
- `PERSONALIZATION_APP_LOG_LEVEL` (default: info)
- `PERSONALIZATION_DATABASE_DSN` (optional): when set, profiles persist in Postgres (`personalization.user_profiles`). Apply ingest-api migrations through `0003_personalization_profiles.sql` (container `ingest-api` runs `ingest-api-migrate` before start).

## Live inference (PER-1)

`live-inference-api` may set `LIVE_INFERENCE_PERSONALIZATION_BASE_URL` to this service (for example `http://personalization-worker:8110`). Clients send optional `subject_id` on `stream_batch` messages; each `inference` payload may then include `personalization` with `subject_id`, `profile` (JSON from GET `/v1/profile/{id}` or null if missing), and optional `error` on fetch failure.

Profile JSON aligns with L1–L3 in `docs/process/collaboration-protocol.md`: `physiology_baseline` for baseline normalization (L1); `adaptation_state.active_personalization_level` (`none`/`light`/`full`), `global_model_reference`, and optional `l2_calibration` (`output_label_maps` per model head, optional `global_model_reference_match`) for live L2 post-hoc routing in `live-inference-api`. Online adaptation and label ingestion remain follow-up steps.

## Профиль из MinIO (ingested raw session)

Чтобы не задавать baseline вручную, можно собрать черновик из объектов в бакете ingest (реальные загрузки, не фикстуры тестов):

```bash
export INGEST_S3_ENDPOINT_URL=http://127.0.0.1:9000
export INGEST_S3_BUCKET=on-go-raw
export INGEST_S3_ACCESS_KEY_ID=minioadmin
export INGEST_S3_SECRET_ACCESS_KEY=minioadmin
export INGEST_DATABASE_DSN=postgresql://on_go:on_go@127.0.0.1:5432/on_go

python3 scripts/draft_personalization_profile_from_minio.py --subject-id YOUR_SUBJECT --include-hr-baseline \
  --global-model-reference m7-9-runtime-bundle > /tmp/profile.json

curl -sS -X PUT http://127.0.0.1:8110/v1/profile -H "Content-Type: application/json" -d @/tmp/profile.json
```

```bash
curl -sS -X PATCH http://127.0.0.1:8110/v1/profile/YOUR_SUBJECT/l2-calibration \
  -H "Content-Type: application/json" \
  -d '{"output_label_maps":{"arousal_coarse":{"low":"medium"}},"active_personalization_level":"light","global_model_reference":"m7-9-runtime-bundle"}'
```

Скрипт читает `manifest/session.json`, при необходимости `annotations/self-report.json` и складывает сводку self-report в `notes`. Для L2 укажи `--l2-model-predictions-json` с объектом `activity` / `arousal_coarse` / `valence_coarse` (выход глобальной модели на этой сессии): скрипт построит `output_label_maps` как «модель → self-report» по session-level меткам и выставит `active_personalization_level` (по умолчанию `light`). Затем `PUT /v1/profile` или точечный `PATCH /v1/profile/{id}/l2-calibration`.

Автоматический batch (replay → majority по окнам → тот же якорь self-report → `PATCH`): `scripts/push_l2_from_replay_infer.py` (см. `scripts/README.md`).

## Local run

```
cd services/personalization-worker
uv run personalization-worker
```

## Docker

Included in `infra/compose/on-go-stack.yml`. Port 8110.
