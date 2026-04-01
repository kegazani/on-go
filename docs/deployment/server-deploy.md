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

Optional TLS reverse proxy (Caddy) in Docker on the same machine:

```bash
export ON_GO_ENABLE_TLS_PROXY=1
```

Set `SITE_ADDRESS` (e.g. `api.example.com:443`) and `SITE_DOMAIN` for the MinIO public host (second site block `s3.${SITE_DOMAIN}` in [infra/compose/Caddyfile](../../infra/compose/Caddyfile)). For local HTTPS with self-signed certs, defaults use `tls internal`.

With Caddy in front, point the iPhone at the HTTPS URL that maps to `ingest-api` paths (`/v1/raw-sessions`, `/health`, etc.).

### Nginx on the host (no Docker for TLS)

Use system nginx + Let’s Encrypt while the stack stays on `127.0.0.1` (Docker or native). Example hostnames: `api.kegazani.ru` (API) and `s3.kegazani.ru` (MinIO S3). Point both DNS `A` records at the server.

1. Publish backend ports only on loopback so they are not reachable from the internet. Either edit `ports` in [infra/compose/on-go-stack.yml](../../infra/compose/on-go-stack.yml) to the form `127.0.0.1:8080:8080` (and the same idea for `8090`, `8100`, `8110`, `8120`, `8121`, `9000`, `9001`, `5432`, `6379`), or add a third compose file: `-f infra/compose/on-go-stack.localhost-bind.override.yml` (requires a Compose version that supports `!override` for list replacement).

2. Install packages (Debian/Ubuntu):

```bash
sudo apt update
sudo apt install -y nginx certbot
sudo mkdir -p /var/www/certbot
```

3. First-time certificate (HTTP-01): enable a minimal site that only serves the ACME webroot, then request a **single** certificate that covers both names (the files on disk live under the **first** `-d` name, here `api.kegazani.ru`):

```bash
sudo cp infra/nginx-host/bootstrap-http.conf /etc/nginx/sites-available/on-go
sudo ln -sf /etc/nginx/sites-available/on-go /etc/nginx/sites-enabled/on-go
sudo nginx -t && sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/certbot \
  --agree-tos --no-eff-email -m YOUR_EMAIL \
  -d api.kegazani.ru -d s3.kegazani.ru
```

4. Replace the site config with TLS + reverse proxy (edit `server_name` and `ssl_certificate` paths if you use different hostnames; certificate directory name must match the first `-d` you used with certbot):

```bash
sudo cp infra/nginx-host/on-go.conf /etc/nginx/sites-available/on-go
sudo nginx -t && sudo systemctl reload nginx
```

Configs live in [infra/nginx-host/bootstrap-http.conf](../../infra/nginx-host/bootstrap-http.conf) and [infra/nginx-host/on-go.conf](../../infra/nginx-host/on-go.conf). Certbot’s timer renews certificates; after renewal, run `sudo systemctl reload nginx` (hook or cron).

5. In `.env` for `ingest-api`, set presigned URLs to the public S3 host:

```bash
INGEST_S3_PRESIGN_ENDPOINT_URL=https://s3.kegazani.ru
```

6. Mobile app: `ON_GO_INGEST_BASE_URL=https://api.kegazani.ru`.

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
