# personalization-worker

Profile store, calibration and adaptation for personalized inference.

## Endpoints

- `GET /health` — health check
- `GET /v1/profile/{subject_id}` — get user profile (404 if not found)
- `PUT /v1/profile` — create/update profile

## Config (env)

- `PERSONALIZATION_APP_HOST` (default: 0.0.0.0)
- `PERSONALIZATION_APP_PORT` (default: 8110)
- `PERSONALIZATION_APP_LOG_LEVEL` (default: info)

## Local run

```
cd services/personalization-worker
uv run personalization-worker
```

## Docker

Included in `infra/compose/on-go-stack.yml`. Port 8110.
