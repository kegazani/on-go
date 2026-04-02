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
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl enable --now nginx
```

Use a real address for `-m` (or add `--register-unsafely-without-email`). Non-interactive example:

```bash
sudo certbot certonly --webroot -w /var/www/certbot \
  --agree-tos --no-eff-email -m you@example.com \
  -d api.kegazani.ru -d s3.kegazani.ru
```

If validation fails with `Fetching https://...` and `tls: internal error`, the validator got an **HTTP→HTTPS redirect** and then TLS on **443** failed. HTTP-01 must succeed on **plain port 80** with **no** redirect for `/.well-known/acme-challenge/`.

Checklist:

- **Who owns port 80?** `sudo ss -tlnp | grep ':80 '` — if you see `docker-proxy`, a container is bound to `:80` and **host nginx is not** what the internet hits. Stop that container or change it to `127.0.0.1:8080:80` (or similar). Only one listener can bind `0.0.0.0:80` on the VM.
- **No second nginx vhost** redirecting first: `sudo nginx -T 2>/dev/null | grep -E 'listen 80|server_name|return 301|acme-challenge'`. Keep only [bootstrap-http.conf](../../infra/nginx-host/bootstrap-http.conf) enabled until the cert exists; remove `default` and any other `sites-enabled` entries that use `return 301 https`.
- **From your laptop** (not only localhost): `curl -4sI http://api.kegazani.ru/.well-known/acme-challenge/x` — must **not** show `Location: https://...`. A `404` from nginx is fine (no file yet); a `301`/`302` to `https` is not.

If **80** is owned by Docker and you cannot free it quickly, use **standalone** (stop everything on 80, including Docker publish) or **DNS-01** (no HTTP):

```bash
sudo certbot certonly --manual --preferred-challenges dns \
  --agree-tos --no-eff-email -m you@example.com \
  -d api.kegazani.ru -d s3.kegazani.ru
```

Follow the prompts to create the TXT records at your DNS provider, then continue.

If port **80** is free of redirects but webroot is awkward, stop nginx and use standalone once:

```bash
sudo systemctl stop nginx
sudo certbot certonly --standalone --agree-tos --no-eff-email -m you@example.com \
  -d api.kegazani.ru -d s3.kegazani.ru
sudo systemctl start nginx
```

Then install [infra/nginx-host/on-go.conf](../../infra/nginx-host/on-go.conf) as below (HTTPS will work after certs exist).

4. Replace the site config with TLS + reverse proxy (edit `server_name` and `ssl_certificate` paths if you use different hostnames; certificate directory name must match the first `-d` you used with certbot):

```bash
sudo cp infra/nginx-host/on-go.conf /etc/nginx/sites-available/on-go
sudo nginx -t && sudo systemctl reload nginx
```

Configs live in [infra/nginx-host/bootstrap-http.conf](../../infra/nginx-host/bootstrap-http.conf) and [infra/nginx-host/on-go.conf](../../infra/nginx-host/on-go.conf). Certbot’s timer renews certificates; after renewal, run `sudo systemctl reload nginx` (hook or cron).

5. In `.env` for `ingest-api`, set presigned URLs to the public S3 host (same origin the phone uses for `PUT`; must match TLS hostname and signing):

```bash
INGEST_S3_PRESIGN_ENDPOINT_URL=https://s3.kegazani.ru
INGEST_S3_PRESIGN_REQUIRE_HTTPS=true
```

`INGEST_S3_PRESIGN_REQUIRE_HTTPS` makes the API refuse to start unless the presign base URL is set and uses `https://`, so clients never receive `http://` upload targets.

6. Mobile app: `ON_GO_INGEST_BASE_URL=https://api.kegazani.ru`.

## Presigned uploads (iPhone)

`ingest-api` must sign URLs with a host the phone can reach. Set:

```bash
INGEST_S3_PRESIGN_ENDPOINT_URL=https://s3.example.com
INGEST_S3_PRESIGN_REQUIRE_HTTPS=true
```

Use the same host you expose for MinIO (reverse proxy TLS on `s3.*`, not an internal Docker hostname or raw `:9000` URL unless that endpoint is HTTPS and reachable from the device).

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
