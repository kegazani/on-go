# Статус выполнения

## Текущее состояние

- Последнее обновление: `2026-03-22`
- Текущая фаза: `C - Backend hardening (post-capture integrity)`
- Следующий рекомендуемый шаг: `C3 - Full package checksum policy hardening`
- Режим работы: `сначала сверка статуса -> предложение следующего шага -> подтверждение -> выполнение -> запись результата`

## Уже сделано

1. Создан базовый backend monorepo.
2. Описана верхнеуровневая архитектура.
3. Подготовлен подробный roadmap по фазам `Research -> Pipeline -> Backend`.
4. Добавлен протокол совместной работы и журналирование шагов.
5. Подготовлены `research protocol` и `session data schema` для paired-сессий `Polar H10 + Apple Watch`.
6. Подготовлена спецификация labels: `activity`, `arousal`, `valence`, включая storage format и правила валидации.
7. Подготовлен `evaluation plan`: headline metrics, split rules, baselines и правила сравнения `watch-only`, `fusion` и personalization.
8. Зафиксирована структура отдельного Swift-репозитория `on-go-ios`: app targets, shared package и границы capture-модулей.
9. Создан базовый каркас отдельного репозитория `on-go-ios`: `project.yml`, app entrypoints для `iPhone/watchOS`, локальный пакет `CaptureKit`, shared-модули capture/storage/transport и базовая документация по запуску.
10. В `on-go-ios` интегрированы adapter-границы `Polar H10` и watch sensors, встроенные в session lifecycle с первыми stream-batches и обновленной локальной документацией.
11. Для backend ingest подготовлены контракт `OpenAPI`, базовая SQL-схема `Postgres` и сервисный каркас `ingest-api` для raw sessions.
12. Для backend ingest реализован runtime `ingest-api` (`FastAPI`) с `Postgres + MinIO/S3`: endpoint-ы lifecycle, idempotency, finalize/checksum flow и локальный `docker compose`-стек.
13. Для replay-контура реализован `replay-service`: `replay_manifest`, replay windows (`realtime/accelerated`), `OpenAPI`-контракт и базовые unit-тесты.
14. Для preprocessing-контура реализован `signal-processing-worker`: sync по `aligned_offset_ms`, базовая очистка stream-данных, quality flags (`gaps`, `packet_loss`, `motion_artifact`, `noisy_intervals`) и запись clean-артефактов.
15. Проведен аудит нереализованных аспектов по `on-go` и `on-go-ios`; backlog расширен дополнительными шагами `B4-B9`, `C3-C4`, `D2-D3`.
16. В `on-go-ios` завершена live-интеграция `Polar H10` через `PolarBleSdk`: реальный callback lifecycle (`observer/power/features`), `HR/ECG` streaming, disconnect/cleanup flow и runtime-конфиг подключения.
17. В `on-go-ios` завершена live-интеграция watch sensors через `HealthKit/CoreMotion`: live collectors для `heart_rate/hrv/accelerometer/gyroscope`, activity-context derivation и преобразование в stream batches.
18. В `on-go-ios` реализован `WatchConnectivity` transport с двусторонним envelope-каналом и session handoff: watch получает реальный `start(session_id)` от iPhone без `scaffoldSessionID`.
19. В `on-go-ios` реализован `FileBasedSessionArchiveStore`: raw package assembly в `Documents/on-go-sessions/session_<id>/` по схеме A1 (manifest, streams, annotations, reports, checksums, SHA256SUMS).
20. В `on-go-ios` реализован `HTTPIngestClient`: HTTP lifecycle к ingest-api (create/presign/complete/finalize), замена in-memory `SessionUploadClient`; конфиг через `ON_GO_INGEST_BASE_URL` и `ON_GO_INGEST_AUTH_TOKEN`.
21. Подготовлен Device E2E validation runbook: prerequisites, pre-flight checklist, capture flow, verification checklist, troubleshooting.
22. В `on-go-ios` устранена потеря данных в capture package: `Polar` и `Watch` stream batches теперь несут реальные sample payloads вместо `sampleCount-only`/нулевых placeholder-строк; watch screen автоматически входит в режим ожидания handoff от iPhone.
23. Подготовлен подробный design note по миграции watch capture на `HKWorkoutSession`: platform rationale, target architecture `watch primary -> phone mirrored`, риски, control/data plane и поэтапный migration plan.
24. В `on-go-ios` реализована миграция capture transport на `HKWorkoutSession`: iPhone запускает watch app через HealthKit и ждет mirrored workout session; watch поднимает primary session и передает envelopes через workout data plane с fallback на `WatchConnectivity`.

## Реестр шагов

| ID | Фаза | Шаг | Статус | Обновлено | Результат |
| --- | --- | --- | --- | --- | --- |
| A0 | Foundation | Каркас репозитория и общий roadmap | completed | 2026-03-21 | Созданы структура monorepo и roadmap |
| A1 | Research | Research protocol и схема данных сессии | completed | 2026-03-21 | Подготовлены протокол записи и каноническая схема raw session package |
| A2 | Research | Спецификация labels: activity, arousal, valence | completed | 2026-03-21 | Зафиксированы ontology labels, шкалы self-report и правила валидации |
| A3 | Research | Evaluation plan и метрики | completed | 2026-03-21 | Зафиксированы metrics, split rules, baselines и claim rules для `watch-only`, `fusion` и personalization |
| A4 | Foundation | Full-scan нереализованных аспектов и синхронизация backlog | completed | 2026-03-21 | Проведен аудит `on-go/on-go-ios`; добавлены недостающие шаги выполнения, чтобы исключить потерю scope |
| B1 | Capture | Структура отдельного Swift-репозитория | completed | 2026-03-21 | Зафиксирована структура `on-go-ios`: app targets, `CaptureKit`, зоны ответственности iPhone/watchOS и связь с raw session schema |
| B2 | Capture | Каркас iPhone/watchOS app для записи сессий | completed | 2026-03-21 | Создан репозиторий `on-go-ios` с app skeleton, `project.yml`, локальным `CaptureKit` и базовым wiring capture lifecycle |
| B3 | Capture | Интеграция Polar H10 и сбор данных часов | completed | 2026-03-21 | Добавлены `PolarH10Adapter` и `WatchSensorAdapter` с live-integration points и симуляционным fallback; lifecycle обновлен для получения первых stream-batches |
| B4 | Capture | Live Polar H10 SDK integration | completed | 2026-03-21 | `LivePolarH10SDKAdapter` переведен на реальный `PolarBleSdk` lifecycle: connect/auto-connect, callbacks readiness, `HR/ECG` streams и stop/disconnect cleanup |
| B5 | Capture | Live Watch HealthKit/CoreMotion integration | completed | 2026-03-21 | `LiveWatchSensorAdapter` переведен на `HealthKit/CoreMotion`: authorization, anchored queries, motion updates, activity-context derivation и live stream-batch counters |
| B6 | Capture | WatchConnectivity transport и session handoff | completed | 2026-03-21 | Реализован `WatchConnectivitySessionTransport` + `receive()` канал, добавлен phone-side прием watch envelopes и watch-side ожидание `start(sessionID)` |
| B7 | Capture | Raw package assembly в локальном storage iPhone | completed | 2026-03-21 | Реализован `FileBasedSessionArchiveStore`, raw package в `Documents/on-go-sessions/` по схеме A1 |
| B8 | Capture | Backend upload handoff в ingest-api | completed | 2026-03-21 | Реализован `HTTPIngestClient` с HTTP lifecycle (create/upload/complete/finalize), конфиг `ON_GO_INGEST_BASE_URL` |
| B9 | Capture | Device E2E validation runbook | completed | 2026-03-21 | Создан runbook в docs/capture/device-e2e-validation-runbook.md |
| B10 | Capture | Device capture debugging: real sample payloads и watch auto-handoff | completed | 2026-03-22 | `rr/hr/ecg` и watch streams больше не сериализуются нулевыми placeholder-значениями; watch view автоматически слушает `start(sessionID)` |
| B11 | Capture | HKWorkoutSession migration design note | completed | 2026-03-22 | Подготовлен детальный документ по переходу с `WatchConnectivity`-only handoff на `HKWorkoutSession`/mirrored session flow |
| B12 | Capture | HKWorkoutSession-based capture migration implementation | completed | 2026-03-22 | Реализованы `activate/startRemoteCapture`, `WorkoutSessionTransport` (iOS/watchOS), phone-initiated `startWatchApp` + mirrored session ожидание, workout data plane для envelopes и fallback через `WatchConnectivity` |
| C1 | Backend | Ingest API и схема БД raw sessions | completed | 2026-03-21 | Зафиксированы `raw-session-ingest.openapi.yaml`, `0001_raw_ingest_metadata.sql` и документация C1 с ingest lifecycle |
| C2 | Backend | Raw storage в Postgres + MinIO/S3 | completed | 2026-03-21 | Реализованы runtime endpoint-ы `ingest-api`, интеграция с `Postgres + MinIO/S3`, idempotency и finalize/upload verification lifecycle |
| C3 | Backend | Full package checksum policy hardening | next | 2026-03-22 | Полная проверка package checksum policy и согласованность checksums artifacts |
| C4 | Backend | Ingest integration/contract tests with fixtures | pending | 2026-03-21 | Интеграционные и контрактные тесты ingest lifecycle с тестовыми raw packages |
| D1 | Replay | Replay service и replay manifest | completed | 2026-03-21 | Реализованы `replay-service`, `raw-session-replay.openapi.yaml`, manifest/window replay API и базовые unit-тесты |
| D2 | Replay | Replay integration tests на полном локальном стеке | pending | 2026-03-21 | Проверка replay на `Postgres + MinIO + ingest + replay` end-to-end |
| D3 | Replay | Streaming replay transport и orchestration modes | pending | 2026-03-21 | `SSE/WebSocket`, replay scenarios и run registry |
| E1 | Processing | Preprocessing: sync, clean, quality flags | completed | 2026-03-21 | Реализован `signal-processing-worker`: чтение raw streams, sync/clean/quality flags, запись clean summary и upsert quality report |
| E2 | Processing | Feature extraction и clean/features layers | pending | 2026-03-21 | После E1 и стабилизации capture ingest-контура (`B4-B9`) |
| F1 | Datasets | Обзор и приоритет внешних датасетов | pending | 2026-03-21 | После A3, можно частично параллелить |
| F2 | Datasets | Dataset registry и импорт первого датасета | pending | 2026-03-21 | После F1 |
| G1 | Modeling | Baseline watch-only model | pending | 2026-03-21 | После E2 и F2 |
| G2 | Modeling | Baseline fusion model | pending | 2026-03-21 | После G1 |
| G3 | Modeling | Сравнительный evaluation report | pending | 2026-03-21 | После G1-G2 |
| H1 | Personalization | Схема профиля пользователя | pending | 2026-03-21 | После G3 |
| H2 | Personalization | Light personalization | pending | 2026-03-21 | После H1 |
| H3 | Personalization | Full personalization | pending | 2026-03-21 | После H2 |
| I1 | Research Gate | Research report и production scope decision | pending | 2026-03-21 | После H3 |
| J1 | ML Platform | Experiment tracking и model registry | pending | 2026-03-21 | После I1 |
| J2 | ML Platform | Автоматизация training/evaluation jobs | pending | 2026-03-21 | После J1 |
| K1 | Production | Production backend architecture | pending | 2026-03-21 | После J2 |
| K2 | Production | Inference API и async processing | pending | 2026-03-21 | После K1 |
| K3 | Production | Deployment, observability, operations | pending | 2026-03-21 | После K2 |

## Правило перехода

Если пользователь пишет `перейдем к следующему шагу`, агент должен:

1. посмотреть этот файл;
2. найти шаг со статусом `next`;
3. назвать его пользователю;
4. кратко описать, что будет сделано;
5. дождаться подтверждения или корректировки.

## Как обновлять этот файл

После завершения шага:

1. текущий шаг переводится в `completed`;
2. следующий логический шаг переводится в `next`;
3. обновляется дата;
4. в `Результат` кратко фиксируется выход шага.
