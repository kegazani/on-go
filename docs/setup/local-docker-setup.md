# Local Docker Setup

Запуск всей backend-системы в Docker и подключение мобильного приложения.

## Стек

| Сервис        | Порт | Назначение                          |
|---------------|------|-------------------------------------|
| ingest-api    | 8080 | Приём raw sessions от iPhone       |
| replay-service| 8090 | Replay ingested sessions           |
| MinIO         | 9000, 9001 | S3-совместимое хранилище     |
| Postgres      | 5432 | Metadata, ingest state             |

## Запуск

Из корня репозитория:

```bash
./scripts/run-stack.sh
```

Или напрямую:

```bash
docker compose -f infra/compose/on-go-stack.yml up --build
```

Фоновый режим:

```bash
./scripts/run-stack.sh -d
```

Проверка:

```bash
curl -s http://localhost:8080/health
curl -s http://localhost:8090/health
```

## Подключение мобильного приложения

### Симулятор iPhone

Симулятор использует сеть хоста. Backend доступен по `localhost`:

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

## Связанные документы

- [Device E2E Validation Runbook](../capture/device-e2e-validation-runbook.md)
- [Ingest API README](../../services/ingest-api/README.md)
