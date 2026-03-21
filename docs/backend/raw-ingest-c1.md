# C1: Ingest API и схема БД raw sessions

## Контекст шага

Этот документ фиксирует результат шага `C1` из roadmap:

1. спроектирован HTTP-контракт ingest для raw session package;
2. зафиксирована базовая схема метаданных в `Postgres`;
3. определены статусы ingest и правила переходов для дальнейшей реализации в `C2`.

Артефакты шага:

1. `contracts/http/raw-session-ingest.openapi.yaml`
2. `services/ingest-api/migrations/0001_raw_ingest_metadata.sql`

## API lifecycle

Базовый lifecycle загрузки raw package:

1. `POST /v1/raw-sessions`
   Клиент регистрирует пакет и передает metadata: `subject`, `session`, `devices`, `segments`, `streams`, список `artifacts`.
2. `POST /v1/raw-sessions/{session_id}/artifacts/presign`
   Клиент запрашивает новые upload targets для retry по `pending/failed` артефактам.
3. `POST /v1/raw-sessions/{session_id}/artifacts/complete`
   Клиент подтверждает, что часть файлов успешно загружена.
4. `POST /v1/raw-sessions/{session_id}/finalize`
   Клиент завершает upload phase и передает package checksum.
5. `GET /v1/raw-sessions/{session_id}`
   Клиент или оператор получает текущее состояние ingest.

## Статусы ingest

Используются статусы:

1. `accepted`
2. `uploading`
3. `uploaded`
4. `validating`
5. `ingested`
6. `failed`
7. `cancelled`

Ожидаемый переход:

1. `accepted -> uploading`
2. `uploading -> uploaded` (когда обязательные artifacts подтверждены)
3. `uploaded -> validating` (после `finalize`)
4. `validating -> ingested` или `validating -> failed`

## Правила идемпотентности

Для операций с ретраями используется `Idempotency-Key`:

1. `POST /v1/raw-sessions`
2. `POST /v1/raw-sessions/{session_id}/artifacts/complete`
3. `POST /v1/raw-sessions/{session_id}/finalize`

Если ключ повторяется с тем же payload, сервис должен вернуть уже созданный результат без дублирования строк и без создания новых object keys.

## Модель данных Postgres

Схема `ingest` разделена на группы:

1. `subjects`, `raw_sessions`
   Корневые сущности и ingest status.
2. `session_devices`, `session_segments`, `session_streams`
   Нормализованный состав session manifest.
3. `session_events`, `session_self_reports`, `session_quality_reports`
   Annotation/quality metadata из raw package.
4. `ingest_artifacts`
   Файлы пакета, object keys, upload/verification status.
5. `ingest_audit_log`
   Аудит переходов и действий клиента/сервиса.

## Что проверяется на finalize

При `finalize` сервер должен выполнить минимум:

1. все required artifacts зарегистрированы и переведены в `uploaded`;
2. `checksums/SHA256SUMS` присутствует;
3. `package_checksum_sha256` валиден по формату и совпадает с ожидаемым checksum policy;
4. `session_id` консистентен между `session`, `streams`, `events` и artifacts;
5. обязательные поля `session/subject/devices/streams` присутствуют.

## Границы C1 и C2

Что закрыто в `C1`:

1. стабильный API-контракт;
2. базовый SQL DDL для metadata и статусов;
3. основа для audit/idempotency.

Что остается на `C2`:

1. runtime-реализация endpoint-ов;
2. интеграция с `MinIO/S3` и выпуск presigned upload URLs;
3. фактическая проверка checksum и запись upload transitions в БД;
4. compose-инфраструктура для локального запуска ingest-api + Postgres + MinIO.
