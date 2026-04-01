# Local Docker Setup

Запуск всей backend-системы в Docker и подключение мобильного приложения.

## Стек

| Сервис        | Порт | Назначение                          |
|---------------|------|-------------------------------------|
| ingest-api    | 8080 | Приём raw sessions от iPhone       |
| replay-service| 8090 | Replay ingested sessions           |
| inference-api | 8100 | Online inference activity/arousal   |
| personalization-worker | 8110 | Profile store, calibration           |
| live-inference-api | 8120 | Live streaming inference (WebSocket)  |
| MinIO         | 9000, 9001 | S3-совместимое хранилище     |
| Postgres      | 5432 | Metadata, ingest state             |
| Redis         | 6379 | Queue для offline workers          |

## Модель (inference / live-inference)

По умолчанию используется Docker-том `on-go-models`. Перед первым запуском либо задайте `ON_GO_MODEL_VOLUME` в `.env` на абсолютный путь к каталогу runtime bundle на хосте, либо заполните том:

```bash
export ON_GO_MODEL_BUNDLE_SOURCE=/path/to/m7-9-runtime-bundle-export
./scripts/bootstrap-model-volume.sh
```

Идентификатор bundle: `infra/model-bundle.version`. Рекомендуется `COMPOSE_PROJECT_NAME=on-go` в `.env` (см. `.env.example`).

## Запуск

Из корня репозитория:

```bash
./scripts/run-stack.sh
```

Или напрямую:

```bash
docker compose -f infra/compose/on-go-stack.yml up --build
```

Прокси TLS (Caddy): `ON_GO_ENABLE_TLS_PROXY=1` и оба файла compose, см. [Server deploy](../deployment/server-deploy.md).

Фоновый режим:

```bash
./scripts/run-stack.sh -d
```

Проверка:

```bash
curl -s http://localhost:8080/health
curl -s http://localhost:8090/health
curl -s http://localhost:8100/health
curl -s http://localhost:8110/health
curl -s http://localhost:8120/health
```

## Подключение мобильного приложения

### iPhone capture

Capture проверяется только на физическом iPhone + Apple Watch + Polar H10. Симулятор не является поддерживаемым capture-путем.

Для backend-only smoke checks можно использовать `localhost`:

| Переменная             | Значение                |
|------------------------|-------------------------|
| ON_GO_INGEST_BASE_URL  | `http://localhost:8080` |

**Xcode:** Edit Scheme → Run → Arguments → Environment Variables.

### Физическое устройство (iPhone)

Физический iPhone и Mac должны быть в одной Wi‑Fi сети. Backend доступен по IP Mac:

1. Узнать IP Mac:
   ```bash
   ipconfig getifaddr en0
   ```
   Или: System Settings → Network → Wi‑Fi → Details → IP Address.

2. Установить в схеме приложения:
   | Переменная             | Значение                    |
   |------------------------|-----------------------------|
   | ON_GO_INGEST_BASE_URL  | `http://<MAC_IP>:8080`      |

   Пример: `http://192.168.1.10:8080`

3. Для загрузки артефактов в MinIO — presigned URLs должны быть доступны с iPhone. Создать `.env` в корне репозитория (рядом с `docker compose`) или экспортировать переменную перед запуском:
   ```
   INGEST_S3_PRESIGN_ENDPOINT_URL=http://<MAC_IP>:9000
   ```
   Пример: `http://192.168.1.109:9000` — iPhone будет загружать файлы напрямую в MinIO на этом адресе.

4. Убедиться, что порты 8080 и 9000 открыты на Mac (firewall).

**Xcode:** Edit Scheme → Run → Arguments → Environment Variables → добавить `ON_GO_INGEST_BASE_URL` = `http://192.168.1.x:8080`.

### Пример схемы (Environment Variables)

```
ON_GO_INGEST_BASE_URL = http://localhost:8080
```

Для устройства заменить на IP Mac.

Non-live validation в этой системе выполняется через replay-service и записанные sessions, а не через simulated capture.

## Быстрый тест с curl

После запуска стека:

```bash
curl -s http://localhost:8080/health
```

Ожидается ответ с `status` (например `{"status":"ok"}`).

## Остановка

```bash
docker compose -f infra/compose/on-go-stack.yml down
```

С удалением volumes:

```bash
docker compose -f infra/compose/on-go-stack.yml down -v
```

## Live streaming

Для real-time inference: `live-inference-api` на порту 8120, WebSocket `/ws/live`. См. `docs/setup/live-streaming-integration.md`.

## Связанные документы

- [Server deploy](../deployment/server-deploy.md)
- [Device E2E Validation Runbook](../capture/device-e2e-validation-runbook.md)
- [Watch ↔ phone checklist](../capture/watch-phone-connectivity-checklist.md)
- [Ingest API README](../../services/ingest-api/README.md)
