# Server deployment (Docker Compose)

## Model bundle

- Default: named Docker volume `on-go-models` mounted at `/models` in `inference-api` and `live-inference-api`.
- Set `ON_GO_MODEL_BUNDLE_SOURCE` to a host directory containing the runtime bundle, then from repo root:

```bash
./scripts/bootstrap-model-volume.sh
```

- Alternatively set `ON_GO_MODEL_VOLUME` in `.env` to an absolute host path to the bundle directory (bind mount instead of the named volume).

- Bundle identity: [infra/model-bundle.version](../../infra/model-bundle.version).

## Stack

```bash
cp .env.example .env
./scripts/run-stack.sh
```

Optional TLS reverse proxy (Caddy) on the same machine:

```bash
export ON_GO_ENABLE_TLS_PROXY=1
```

Set `SITE_ADDRESS` (e.g. `api.example.com:443`) and `SITE_DOMAIN` for the MinIO public host (second site block `s3.${SITE_DOMAIN}` in [infra/compose/Caddyfile](../../infra/compose/Caddyfile)). For local HTTPS with self-signed certs, defaults use `tls internal`.

With Caddy in front, point the iPhone at the HTTPS URL that maps to `ingest-api` paths (`/v1/raw-sessions`, `/health`, etc.).

## Presigned uploads (iPhone)

`ingest-api` must sign URLs with a host the phone can reach. Set:

```bash
INGEST_S3_PRESIGN_ENDPOINT_URL=https://s3.example.com
```

Use the same host you expose for MinIO (direct port `9000` or the `s3.*` site in Caddy).

## Batch preprocessing

After a session is ingested:

```bash
./scripts/run-signal-worker.sh <session_id>
```

Requires stack up with batch profile idle container:

```bash
docker compose -f infra/compose/on-go-stack.yml --profile batch up -d
```

Or rely on `docker compose run` pulling dependencies without keeping `sleep infinity` running.

## Capacity

Up to roughly five simultaneous capture clients: see plan section on single VM sizing (about 4 vCPU / 8 GiB RAM, ample disk for MinIO).
