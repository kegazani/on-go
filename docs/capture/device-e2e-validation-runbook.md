# Device E2E Validation Runbook

Руководство для сквозной ручной проверки цепочки `phone + watch + polar -> ingest`.

## Цель

Убедиться, что:

1. iPhone приложение запускает сессию с реальными устройствами.
2. Polar H10 и Apple Watch поставляют данные в raw package.
3. Raw package корректно загружается в ingest-api и финализируется как `ingested`.

## Prerequisites

### Оборудование

| Компонент | Требование |
|-----------|------------|
| iPhone | iOS 18+, с Bluetooth |
| Apple Watch | watchOS 11+, с парой к iPhone |
| Polar H10 | Заряжен, надет по протоколу |

### Backend

Ingest stack должен быть запущен:

```bash
cd <on-go>
docker compose -f infra/compose/raw-ingest-stack.yml up --build
```

Сервисы:

- Postgres на `localhost:5432`
- MinIO на `localhost:9000` (console: `localhost:9001`)
- ingest-api на `localhost:8080`

Проверка:

```bash
curl -s http://localhost:8080/health
```

Ожидается `{"status":"ok"}` или аналог.

### on-go-ios

1. Сгенерирован проект: `./scripts/generate-project.sh`
2. Собран и установлен на устройства (Xcode: iPhone + Watch scheme).
3. HealthKit: для watch-приложения включены capabilities `HealthKit` (heart rate, HRV).
4. Bluetooth: в Info.plist описано использование для Polar (при необходимости).

## Конфигурация iPhone-приложения

### ON_GO_INGEST_BASE_URL

- **Симулятор:** `http://localhost:8080` (или `http://127.0.0.1:8080`)
- **Физическое устройство:** `http://<host-ip>:8080`, где `<host-ip>` — IP Mac в той же сети (например, `192.168.1.10`)

Настройка через Xcode: Edit Scheme → Run → Arguments → Environment Variables.

### ON_GO_INGEST_AUTH_TOKEN (опционально)

Bearer token, если ingest-api требует авторизацию.

### Polar H10 (опционально)

- `ON_GO_POLAR_DEVICE_ID` — явный device id для подключения.
- `ON_GO_POLAR_AUTOCONNECT_RSSI` — порог авто-поиска (по умолчанию `-65`).
- `ON_GO_POLAR_AUTOCONNECT_DEVICE_TYPE` — тип устройства (по умолчанию `H10`).

## Pre-flight Checklist

Перед запуском сессии:

| # | Проверка | ✓ |
|---|----------|---|
| 1 | ingest-api отвечает на `/health` |
| 2 | iPhone и Watch в одной паре, Watch не в режиме полёта |
| 3 | Polar H10 надет, включен, индикатор активен |
| 4 | `ON_GO_INGEST_BASE_URL` настроен в схеме приложения |
| 5 | HealthKit разрешения для watch-приложения выданы (heart rate, HRV) |

## Capture Flow

### 1. Prepare

1. Запустить OnGoCapture на iPhone.
2. Нажать **Prepare**.
3. Ожидать: `Session prepared`, `session_id` отображается.

| Критерий | ✓ |
|----------|---|
| session_id не пустой |
| Статус: prepared |

### 2. Start

1. Нажать **Start**.
2. Polar H10 должен подключиться (индикатор, статус в UI).
3. Watch должен начать mirroring (если используется).

| Критерий | ✓ |
|----------|---|
| Polar state: connected / streaming |
| Watch (если есть): mirroring started |
| В логах: batch counts для polar_* и watch_* |

### 3. Record (опционально)

1. Подождать 30–60 секунд.
2. По желанию: вызвать Begin Segment (если доступно в UI).
3. Убедиться, что данные продолжают поступать (логи).

| Критерий | ✓ |
|----------|---|
| Потоки polar_hr, polar_rr (и при наличии polar_ecg) активны |
| Потоки watch_* активны при наличии watch |

### 4. Stop

1. Заполнить self-report (arousal, valence, activity, notes).
2. Нажать **Stop**.
3. Дождаться финализации.

| Критерий | ✓ |
|----------|---|
| Статус: export_ready или exported |
| Сообщение: "Session exported and uploaded to backend" при успешной загрузке |

### 5. Verify Local Package

На Mac (если есть доступ к симулятору или к экспорту):

```bash
# Симулятор
ls ~/Library/Developer/CoreSimulator/Devices/*/data/Containers/Data/Application/*/Documents/on-go-sessions/
```

Ожидается каталог `session_<session_id>/` с:

| Файл/каталог | ✓ |
|--------------|---|
| manifest/session.json |
| manifest/subject.json |
| manifest/devices.json |
| manifest/segments.json |
| manifest/streams.json |
| streams/*/metadata.json |
| streams/*/samples.csv |
| annotations/session-events.jsonl |
| reports/quality-report.json |
| checksums/SHA256SUMS |

### 6. Verify Backend Ingest

```bash
curl -s http://localhost:8080/v1/raw-sessions/<session_id>
```

Ожидается:

- `ingest_status`: `ingested`
- `uploaded_artifact_count` = expected
- `validation_summary.required_artifacts_ok`: true
- `validation_summary.checksum_ok`: true

| Критерий | ✓ |
|----------|---|
| ingest_status == ingested |
| Нет missing_required_artifacts |
| checksum_ok == true |

### 7. Verify Storage (опционально)

MinIO console: `http://localhost:9001` → bucket `on-go-raw` → префикс `raw-sessions/<session_id>/`.

Postgres:

```sql
SELECT session_id, ingest_status, uploaded_artifact_count, expected_artifact_count
FROM ingest.raw_sessions
WHERE session_id = '<session_id>';
```

## Acceptance Checklist

| # | Критерий приемки | ✓ |
|---|------------------|---|
| 1 | Polar H10 подключается и передаёт HR/RR (и ECG при наличии) |
| 2 | Apple Watch передаёт данные на iPhone через WatchConnectivity |
| 3 | Raw package создаётся локально по схеме A1 |
| 4 | Upload в ingest-api завершается без ошибок |
| 5 | Backend показывает ingest_status = ingested |
| 6 | Все ожидаемые artifacts загружены и verified |
| 7 | checksum-валидация проходит |

## Troubleshooting

### Polar H10 не подключается

- Проверить заряд и индикатор.
- Убедиться, что Polar не сопряжён с другим приложением.
- Перезапустить Bluetooth на iPhone.
- При необходимости задать `ON_GO_POLAR_DEVICE_ID` вручную.

### Watch не получает handoff

- Проверить, что Watch и iPhone в одной паре.
- Проверить, что WatchConnectivity активирован (Watch app видна на iPhone).
- Перезапустить оба приложения.

### Upload failed

- Проверить `ON_GO_INGEST_BASE_URL`: для физического устройства должен быть IP хоста, не localhost.
- Убедиться, что ingest-api запущен и доступен с iPhone (проверить с браузера/curl с телефона при возможности).
- Проверить логи приложения: точный текст ошибки (create/upload/complete/finalize).

### Ingest status = failed

- Запросить `GET /v1/raw-sessions/<session_id>` и смотреть `last_error`, `missing_required_artifacts`.
- Возможные причины: несовпадение checksums, отсутствующий artifact, неверный manifest.

### Симулятор без устройств

- Polar и Watch требуют реальное оборудование.
- В симуляторе можно проверить только: prepare, start (simulated), stop, локальный package.
- Upload при `ON_GO_INGEST_BASE_URL=http://localhost:8080` в симуляторе работает.

## Связанные документы

1. `docs/research/research-protocol.md`
2. `docs/research/session-data-schema.md`
3. `on-go-ios/docs/setup/local-development.md` (sibling repo)
4. `services/ingest-api/README.md`
5. `contracts/http/raw-session-ingest.openapi.yaml`
