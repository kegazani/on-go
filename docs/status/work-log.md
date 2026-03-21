# Журнал работ

Этот журнал ведется в хронологическом порядке и нужен для ответа на вопросы:

1. что уже сделано;
2. когда это было сделано;
3. какие файлы были изменены;
4. какой шаг следующий.

---

## 2026-03-21 - A0 - Инициализация backend monorepo

### Запрос

Построить общую структуру многомодульной системы с backend monorepo и отдельным Swift-фронтендом.

### Что сделано

1. Создан базовый каркас backend monorepo.
2. Инициализирован git-репозиторий.
3. Добавлены каталоги `services`, `contracts`, `platform`, `infra`, `docs`, `scripts`.
4. Зафиксировано, что Swift-фронтенд должен жить в отдельном репозитории.

### Измененные файлы

1. `README.md`
2. `.gitignore`
3. `.editorconfig`
4. `services/README.md`
5. `services/_template/README.md`
6. `platform/shared/README.md`
7. `platform/testing/README.md`
8. `platform/observability/README.md`
9. `contracts/http/README.md`
10. `contracts/events/README.md`
11. `infra/compose/README.md`
12. `infra/kubernetes/README.md`
13. `infra/terraform/README.md`
14. `docs/architecture/monorepo.md`
15. `docs/decisions/README.md`
16. `scripts/README.md`
17. `.github/workflows/README.md`

### Результат

Получен стартовый backend monorepo с архитектурным каркасом.

### Следующий рекомендуемый шаг

`A1 - Research protocol и схема данных сессии`

---

## 2026-03-21 - A0 - Подробный roadmap проекта

### Запрос

Подготовить подробный план этапов, чтобы потом можно было реализовывать проект по частям.

### Что сделано

1. Добавлен подробный roadmap по фазам `Research -> ML Pipeline -> Backend`.
2. Для каждой фазы описаны:
   - цель;
   - задачи;
   - артефакты;
   - критерии завершения;
   - примеры следующих запросов.

### Измененные файлы

1. `README.md`
2. `docs/roadmap/research-pipeline-backend-plan.md`

### Результат

Появился единый план, на который можно опираться при пошаговой реализации.

### Следующий рекомендуемый шаг

`A1 - Research protocol и схема данных сессии`

---

## 2026-03-21 - A0 - Протокол работы и журналирование

### Запрос

Настроить режим, в котором агент документирует сделанное, отслеживает текущий шаг и перед следующим шагом сверяется со статусом.

### Что сделано

1. Добавлен формальный протокол совместной работы.
2. Создан файл со статусом шагов.
3. Создан журнал работ.
4. Зафиксировано правило: перед переходом к следующему шагу агент сначала сверяет статус, затем предлагает следующий шаг на подтверждение.

### Измененные файлы

1. `README.md`
2. `docs/process/collaboration-protocol.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`

### Результат

Проект переведен в управляемый пошаговый режим.

### Следующий рекомендуемый шаг

`A1 - Research protocol и схема данных сессии`

---

## 2026-03-21 - A1 - Research protocol и схема данных сессии

### Запрос

После сверки статуса выполнить следующий шаг `A1`: подготовить research protocol и схему данных сессии.

### Что сделано

1. Подготовлен `research protocol` для paired-сессий `Polar H10 + Apple Watch`.
2. Зафиксированы цели шага, исследовательские гипотезы, структура сессии и обязательные pre/post-session требования.
3. Описана каноническая `session data schema`: сущности, metadata, stream types, sample-файлы, правила времени и синхронизации.
4. Зафиксирована структура raw session package, пригодная для будущих шагов ingest, replay и preprocessing.
5. Добавлены ссылки на исследовательские документы в `README.md`.
6. Обновлен статус выполнения: `A1` закрыт, следующим шагом выставлен `A2`.

### Измененные файлы

1. `README.md`
2. `docs/research/research-protocol.md`
3. `docs/research/session-data-schema.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`

### Результат

Появилась базовая исследовательская спецификация capture-сессии и каноническая схема raw package для дальнейшей реализации capture, ingest и replay.

### Следующий рекомендуемый шаг

`A2 - Спецификация labels: activity, arousal, valence`

---

## 2026-03-21 - A2 - Спецификация labels: activity, arousal, valence

### Запрос

После сверки статуса выполнить следующий шаг `A2`: подготовить спецификацию `activity/context labels`, шкалы `arousal` и `valence`, а также правила хранения и валидации labels.

### Что сделано

1. Создан отдельный документ `label specification` для исследовательской фазы.
2. Зафиксированы label families: `protocol_segment_label`, `activity_label`, `arousal_score`, `valence_score`.
3. Определена первая каноническая taxonomy для `activity/context`, включая `activity_group`, допустимые `activity_label` и соответствия между ними.
4. Зафиксированы шкалы `arousal` и `valence` в формате `1..9`, а также их coarse-представления для будущих baseline-задач.
5. Описаны правила post-session self-report, роль оператора, versioned storage format для labels и каноническая запись label artifact.
6. Добавлены правила валидации, чтобы следующий шаг `A3` мог опираться на уже стабилизированные target definitions.
7. Обновлены связанные research-документы и `README.md` ссылками на новую спецификацию.
8. Обновлен статус выполнения: `A2` закрыт, следующим шагом выставлен `A3`.

### Измененные файлы

1. `README.md`
2. `docs/research/label-specification.md`
3. `docs/research/research-protocol.md`
4. `docs/research/session-data-schema.md`
5. `docs/status/execution-status.md`
6. `docs/status/work-log.md`

### Результат

Появилась каноническая исследовательская спецификация labels для первых paired-сессий: зафиксированы target definitions, формат хранения и базовые правила проверки качества разметки.

### Следующий рекомендуемый шаг

`A3 - Evaluation plan и метрики`

---

## 2026-03-21 - A3 - Evaluation plan и метрики

### Запрос

После сверки статуса выполнить следующий шаг `A3`: подготовить evaluation plan, headline-метрики, split rules и правила сравнения `watch-only`, `fusion` и personalized-вариантов.

### Что сделано

1. Создан отдельный документ `evaluation plan` для исследовательской фазы.
2. Зафиксированы обязательные evaluation tracks: `activity/context` и `arousal`, а также exploratory track для `valence`.
3. Определены headline и secondary metrics, включая `macro_f1`, `balanced_accuracy`, `mae`, `spearman_rho` и `quadratic_weighted_kappa`.
4. Зафиксированы правила `subject-wise` валидации, режимы `LOSO/GroupKFold` для малого корпуса и требования к split manifest.
5. Добавлены правила dataset inclusion, confidence thresholds, paired evaluation subset и ограничения против feature leakage.
6. Зафиксированы baselines, правила расчета confidence intervals и критерии для claims уровня `baseline_pass`, `fusion_gain_supported` и `personalization_gain_supported`.
7. Обновлены связанные research-документы и `README.md` ссылками на новый evaluation artifact.
8. Обновлен статус выполнения: `A3` закрыт, следующим шагом выставлен `B1`.

### Измененные файлы

1. `README.md`
2. `docs/research/evaluation-plan.md`
3. `docs/research/label-specification.md`
4. `docs/research/research-protocol.md`
5. `docs/status/execution-status.md`
6. `docs/status/work-log.md`

### Результат

Исследовательская фаза теперь полностью фиксирует не только capture protocol и labels, но и единый evaluation protocol для будущих baseline и personalization experiments.

### Следующий рекомендуемый шаг

`B1 - Структура отдельного Swift-репозитория`

---

## 2026-03-21 - B1 - Структура отдельного Swift-репозитория

### Запрос

После сверки статуса выполнить следующий шаг `B1`: спроектировать структуру отдельного Swift-репозитория для capture-прототипа.

### Что сделано

1. Создан отдельный документ со структурой будущего репозитория `on-go-ios`.
2. Зафиксирована рекомендуемая верхнеуровневая структура каталогов: `apps`, `packages`, `config`, `docs`, `scripts`, `.github`.
3. Определен минимальный shared Swift package `CaptureKit` и его target-модули: `CaptureDomain`, `CaptureStorage`, `WatchConnectivityBridge`, `PhoneCapture`, `WatchCapture`, `BackendClient`, `TestSupport`.
4. Зафиксированы границы ответственности между `iPhone` и `Apple Watch`, включая правило, что `iPhone` является владельцем `session_id`, lifecycle и финального export package.
5. Зафиксирована связь capture-структуры с уже подготовленными research-артефактами, включая `research protocol`, `session data schema`, `label specification` и `evaluation plan`.
6. Обновлен `README.md` ссылкой на новый capture-документ.
7. Обновлен статус выполнения: `B1` закрыт, следующим шагом выставлен `B2`.

### Измененные файлы

1. `README.md`
2. `docs/capture/swift-repository-structure.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`

### Результат

Появилась зафиксированная структура отдельного репозитория `on-go-ios`, на которую можно опирать следующий шаг с созданием каркаса `iPhone/watchOS` приложений и shared-модулей.

### Следующий рекомендуемый шаг

`B2 - Каркас iPhone/watchOS app для записи сессий`

---

## 2026-03-21 - B2 - Каркас iPhone/watchOS app для записи сессий

### Запрос

После сверки статуса выполнить следующий шаг `B2`: создать каркас `iPhone/watchOS` приложений для записи сессий и базовый shared-layer для capture-прототипа.

### Что сделано

1. Создан отдельный репозиторий `/Users/kgz/Desktop/p/on-go-ios` и инициализирован как новый git-репозиторий.
2. Добавлен source-of-truth проектный файл `apps/OnGoCapture/project.yml` для генерации `OnGoCapture.xcodeproj` через `xcodegen`.
3. Создан минимальный app skeleton:
   - `iPhone` entrypoint и placeholder-экран управления lifecycle сессии;
   - `watchOS` entrypoint и placeholder-экран mirror-state.
4. Создан локальный Swift package `CaptureKit` с модулями `CaptureDomain`, `CaptureStorage`, `WatchConnectivityBridge`, `PhoneCapture`, `WatchCapture`, `BackendClient`, `TestSupport`.
5. В shared-модулях зафиксирован минимальный session lifecycle skeleton: подготовка сессии, старт/стоп записи, прием stream batches, сбор archive descriptor и очередь upload jobs.
6. Добавлены `xcconfig`, базовая локальная документация и helper-script для генерации Xcode-проекта.
7. Проведена локальная проверка доступным в этой среде способом: `swift build` в `packages/CaptureKit` проходит успешно.
8. Зафиксировано ограничение среды: полный `xcodebuild` и генерация проекта не проверялись, потому что в активной developer directory нет полноценного Xcode, а `xcodegen` не установлен.
9. Обновлен статус выполнения: `B2` закрыт, следующим шагом выставлен `B3`.

### Измененные файлы

1. `../on-go-ios/README.md`
2. `../on-go-ios/.gitignore`
3. `../on-go-ios/apps/OnGoCapture/project.yml`
4. `../on-go-ios/apps/OnGoCapture/iPhoneApp/OnGoCaptureApp.swift`
5. `../on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
6. `../on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionDashboardView.swift`
7. `../on-go-ios/apps/OnGoCapture/WatchApp/OnGoWatchApp.swift`
8. `../on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionView.swift`
9. `../on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionViewModel.swift`
10. `../on-go-ios/packages/CaptureKit/Package.swift`
11. `../on-go-ios/packages/CaptureKit/Sources/CaptureDomain/CaptureDomainModels.swift`
12. `../on-go-ios/packages/CaptureKit/Sources/CaptureStorage/SessionArchiveStore.swift`
13. `../on-go-ios/packages/CaptureKit/Sources/WatchConnectivityBridge/SessionTransport.swift`
14. `../on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PhoneCaptureCoordinator.swift`
15. `../on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchCaptureController.swift`
16. `../on-go-ios/packages/CaptureKit/Sources/BackendClient/SessionUploadClient.swift`
17. `../on-go-ios/packages/CaptureKit/Sources/TestSupport/SessionFixtures.swift`
18. `../on-go-ios/config/xcconfig/Base.xcconfig`
19. `../on-go-ios/config/xcconfig/Debug.xcconfig`
20. `../on-go-ios/config/xcconfig/Release.xcconfig`
21. `../on-go-ios/docs/architecture/capture-runtime.md`
22. `../on-go-ios/docs/setup/local-development.md`
23. `../on-go-ios/scripts/generate-project.sh`
24. `docs/status/execution-status.md`
25. `docs/status/work-log.md`

### Результат

Появился реальный каркас отдельного Swift-репозитория `on-go-ios`, на который можно опирать следующий шаг с подключением `Polar H10`, реального watch-side sensor capture и transport/integration adapters.

### Следующий рекомендуемый шаг

`B3 - Интеграция Polar H10 и сбор данных часов`

---

## 2026-03-21 - B3 - Интеграция Polar H10 и сбор данных часов

### Запрос

После сверки статуса и подтверждения пользователя выполнить шаг `B3`: подключить adapter-слои `Polar H10` и `Apple Watch`, встроить их в capture lifecycle и зафиксировать результат.

### Что сделано

1. Добавлен `PolarH10Adapter` в `CaptureKit/PhoneCapture` с двумя реализациями:
   - `SimulatedPolarH10Adapter` для локальной проверки без SDK;
   - `LivePolarH10SDKAdapter` за compile-time guard `canImport(PolarBleSdk)` с integration points для реальных callback-потоков.
2. Обновлен `PhoneCaptureCoordinator`:
   - подключение `Polar` при `startRecording`;
   - запись `device_connected/device_disconnected` событий;
   - прием первых `polar_ecg/polar_rr/polar_hr` stream batches в archive store;
   - экспорт `polarConnectionState` для UI.
3. Добавлен `WatchSensorAdapter` в `CaptureKit/WatchCapture` с двумя реализациями:
   - `SimulatedWatchSensorAdapter` для stream batches `watch_heart_rate/watch_accelerometer/watch_gyroscope/watch_activity_context/watch_hrv`;
   - `LiveWatchSensorAdapter` за `os(watchOS) && canImport(HealthKit) && canImport(CoreMotion)` с точками встраивания реальных collectors.
4. Обновлен `WatchCaptureController`:
   - запуск sensor capture при `startMirroring`;
   - автоматическая отправка первых watch batches в transport;
   - добавлен `recordNextSensorBatch` и экспорт текущего sensor state.
5. Обновлены `iPhone/watchOS` view models и экраны для отображения состояния адаптеров и подтверждения приема первых batches.
6. Обновлена локальная документация `on-go-ios` под шаг `B3`: runtime-path, требования окружения и ограничения симуляционного fallback.
7. Выполнена локальная проверка: `swift build` в `../on-go-ios/packages/CaptureKit` проходит успешно.
8. Зафиксировано ограничение среды: интеграция с реальными `PolarBleSdk`, `HealthKit`, `CoreMotion` и `WatchConnectivity` в этой shell-среде не проверялась рантаймно.
9. Обновлен статус выполнения: `B3` закрыт, следующим шагом выставлен `C1`.

### Измененные файлы

1. `../on-go-ios/README.md`
2. `../on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionDashboardView.swift`
3. `../on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
4. `../on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionView.swift`
5. `../on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionViewModel.swift`
6. `../on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PhoneCaptureCoordinator.swift`
7. `../on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PolarH10Adapter.swift`
8. `../on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchCaptureController.swift`
9. `../on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchSensorAdapter.swift`
10. `../on-go-ios/docs/architecture/capture-runtime.md`
11. `../on-go-ios/docs/setup/local-development.md`
12. `docs/status/execution-status.md`
13. `docs/status/work-log.md`

### Результат

Capture runtime в `on-go-ios` теперь имеет рабочие adapter boundaries для `Polar H10` и `Apple Watch`, встроенные в lifecycle с получением первых stream batches и готовыми точками для последующего подключения реальных SDK-потоков.

### Следующий рекомендуемый шаг

`C1 - Ingest API и схема БД raw sessions`

---

## 2026-03-21 - C1 - Ingest API и схема БД raw sessions

### Запрос

После сверки статуса и подтверждения пользователя выполнить шаг `C1`: спроектировать ingest API и базовую схему БД для raw sessions.

### Что сделано

1. Подготовлен HTTP-контракт `OpenAPI` для backend ingest lifecycle:
   - регистрация ingest-сессии;
   - перевыпуск upload targets;
   - подтверждение загруженных artifacts;
   - finalize и получение состояния ingest.
2. Зафиксированы схемы запросов/ответов для `session/subject/devices/segments/streams/artifacts`, статусы ingest и правила идемпотентности через `Idempotency-Key`.
3. Добавлен SQL DDL `0001_raw_ingest_metadata.sql` для схемы `ingest` в `Postgres`:
   - таблицы metadata (`subjects`, `raw_sessions`, `session_devices`, `session_segments`, `session_streams`);
   - таблицы annotations/reports (`session_events`, `session_self_reports`, `session_quality_reports`);
   - таблицы upload lifecycle и аудита (`ingest_artifacts`, `ingest_audit_log`);
   - enum-типы статусов, индексы и `updated_at` triggers.
4. Добавлен сервисный каркас `services/ingest-api` и документ шага `docs/backend/raw-ingest-c1.md` с зафиксированными границами `C1/C2`.
5. Обновлены корневой `README.md` и `README`-файлы в `contracts/http` и `services` с ссылками на новые артефакты.
6. Выполнена базовая проверка: `raw-session-ingest.openapi.yaml` успешно парсится через `ruby`/`YAML.load_file`.
7. Зафиксировано ограничение среды: SQL-миграция не прогонялась на реальном экземпляре `Postgres` в рамках этого шага.
8. Обновлен статус выполнения: `C1` закрыт, следующим шагом выставлен `C2`.

### Измененные файлы

1. `README.md`
2. `contracts/http/README.md`
3. `contracts/http/raw-session-ingest.openapi.yaml`
4. `docs/backend/raw-ingest-c1.md`
5. `services/README.md`
6. `services/ingest-api/README.md`
7. `services/ingest-api/src/README.md`
8. `services/ingest-api/tests/README.md`
9. `services/ingest-api/deploy/README.md`
10. `services/ingest-api/migrations/0001_raw_ingest_metadata.sql`
11. `docs/status/execution-status.md`
12. `docs/status/work-log.md`

### Результат

Для backend raw ingestion теперь зафиксированы согласованные артефакты контракта и хранения: `OpenAPI` lifecycle и базовая `Postgres`-схема метаданных с upload-state, checksum-полями и audit trail, что позволяет перейти к runtime-реализации в `C2`.

### Следующий рекомендуемый шаг

`C2 - Raw storage в Postgres + MinIO/S3`

---

## 2026-03-21 - C2 - Raw storage в Postgres + MinIO/S3

### Запрос

После сверки статуса и подтверждения пользователя выполнить шаг `C2`: реализовать runtime ingest endpoint-ы, интеграцию с `Postgres + MinIO/S3` и фактический upload/verification lifecycle.

### Что сделано

1. Реализован runtime сервис `ingest-api` на `FastAPI` в `services/ingest-api/src/ingest_api`.
2. Реализованы endpoint-ы lifecycle по контракту:
   - `POST /v1/raw-sessions`;
   - `GET /v1/raw-sessions/{session_id}`;
   - `POST /v1/raw-sessions/{session_id}/artifacts/presign`;
   - `POST /v1/raw-sessions/{session_id}/artifacts/complete`;
   - `POST /v1/raw-sessions/{session_id}/finalize`.
3. Добавлен SQL-слой для записи metadata в `Postgres`: `subjects`, `raw_sessions`, `session_devices`, `session_segments`, `session_streams`, `ingest_artifacts`, audit и ingest state.
4. Добавлена интеграция с `MinIO/S3`:
   - выпуск presigned `PUT` URL;
   - `HEAD`/`GET` проверки объектов;
   - проверка checksum checksum-artifact на `finalize`.
5. Добавлена idempotency-механика для create/complete/finalize и миграция `0002_ingest_runtime_support.sql`.
6. Добавлен migration runner `ingest-api-migrate` и entrypoint `ingest-api`.
7. Добавлен локальный инфраструктурный стек `infra/compose/raw-ingest-stack.yml` + `Dockerfile` сервиса.
8. Добавлены базовые model-тесты (`pytest`) для валидации ingest request.
9. Выполнены локальные проверки:
   - `python3 -m compileall src tests` проходит;
   - `pytest -q tests/test_models.py` проходит (`2 passed` в локальном venv);
   - `docker compose ... config` проходит.
10. Зафиксировано ограничение среды: полноценный `docker compose up` не был выполнен из-за недоступного Docker daemon (`Cannot connect to the Docker daemon`).
11. Обновлены проектные документы `README` и backend-документация шага `C2`.

### Измененные файлы

1. `.gitignore`
2. `README.md`
3. `services/README.md`
4. `docs/backend/raw-ingest-c2.md`
5. `infra/compose/README.md`
6. `infra/compose/raw-ingest-stack.yml`
7. `services/ingest-api/.env.example`
8. `services/ingest-api/pyproject.toml`
9. `services/ingest-api/README.md`
10. `services/ingest-api/src/README.md`
11. `services/ingest-api/src/ingest_api/__init__.py`
12. `services/ingest-api/src/ingest_api/api.py`
13. `services/ingest-api/src/ingest_api/config.py`
14. `services/ingest-api/src/ingest_api/db.py`
15. `services/ingest-api/src/ingest_api/errors.py`
16. `services/ingest-api/src/ingest_api/main.py`
17. `services/ingest-api/src/ingest_api/migrate.py`
18. `services/ingest-api/src/ingest_api/models.py`
19. `services/ingest-api/src/ingest_api/repository.py`
20. `services/ingest-api/src/ingest_api/service.py`
21. `services/ingest-api/src/ingest_api/storage.py`
22. `services/ingest-api/migrations/0002_ingest_runtime_support.sql`
23. `services/ingest-api/deploy/Dockerfile`
24. `services/ingest-api/deploy/README.md`
25. `services/ingest-api/tests/README.md`
26. `services/ingest-api/tests/test_models.py`
27. `docs/status/execution-status.md`
28. `docs/status/work-log.md`

### Результат

`C2` завершен: backend raw ingestion теперь работает как runtime-контур с persisted metadata в `Postgres`, artifact lifecycle в `MinIO/S3`, idempotency, finalize validation и локальным compose-описанием для запуска стека.

### Следующий рекомендуемый шаг

`D1 - Replay service и replay manifest`

---

## 2026-03-21 - D1 - Replay service и replay manifest

### Запрос

После сверки статуса и подтверждения пользователя выполнить шаг `D1`: реализовать `replay-service` и формализовать `replay_manifest` для воспроизведения raw sessions.

### Что сделано

1. Создан отдельный runtime-сервис `services/replay-service` на `FastAPI`.
2. Реализованы endpoint-ы:
   - `GET /v1/replay/sessions/{session_id}/manifest`;
   - `POST /v1/replay/sessions/{session_id}/windows`;
   - `GET /health`.
3. Реализована сборка `replay_manifest` на основе `ingest.raw_sessions`, `session_segments`, `session_streams` и `ingest_artifacts`.
4. Реализовано чтение stream samples из `MinIO/S3` и формирование синхронизированного replay-окна по `offset_ms`.
5. Поддержаны replay-режимы `realtime` и `accelerated` (через расчет `replay_at_offset_ms`).
6. Добавлен контракт `contracts/http/raw-session-replay.openapi.yaml`.
7. Добавлен backend-документ `docs/backend/replay-d1.md` с форматом `replay_manifest`, границами шага и инструкцией запуска.
8. Обновлены root-документы со ссылками на новые D1-артефакты.
9. Добавлены базовые unit-тесты replay-логики.
10. Выполнены локальные проверки:
   - `python3 -m compileall src tests` проходит;
   - `pytest -q` проходит (`4 passed`);
   - `raw-session-replay.openapi.yaml` успешно парсится через `ruby`/`YAML.load_file`.
11. Зафиксировано ограничение среды: интеграция на полном docker-compose стеке (`Postgres + MinIO + ingest-api + replay-service`) в этом шаге не выполнялась.
12. Обновлен статус выполнения: `D1` закрыт, следующим шагом выставлен `E1`.

### Измененные файлы

1. `README.md`
2. `contracts/http/README.md`
3. `contracts/http/raw-session-replay.openapi.yaml`
4. `docs/backend/replay-d1.md`
5. `services/README.md`
6. `services/replay-service/.env.example`
7. `services/replay-service/pyproject.toml`
8. `services/replay-service/README.md`
9. `services/replay-service/src/README.md`
10. `services/replay-service/src/replay_service/__init__.py`
11. `services/replay-service/src/replay_service/api.py`
12. `services/replay-service/src/replay_service/config.py`
13. `services/replay-service/src/replay_service/db.py`
14. `services/replay-service/src/replay_service/errors.py`
15. `services/replay-service/src/replay_service/main.py`
16. `services/replay-service/src/replay_service/models.py`
17. `services/replay-service/src/replay_service/repository.py`
18. `services/replay-service/src/replay_service/service.py`
19. `services/replay-service/src/replay_service/storage.py`
20. `services/replay-service/tests/README.md`
21. `services/replay-service/tests/test_models.py`
22. `services/replay-service/tests/test_service.py`
23. `services/replay-service/deploy/README.md`
24. `services/replay-service/deploy/Dockerfile`
25. `services/replay-service/migrations/README.md`
26. `docs/status/execution-status.md`
27. `docs/status/work-log.md`

### Результат

`D1` завершен: backend теперь имеет отдельный `replay-service` с формальным `replay_manifest`, API для replay-окон (`realtime/accelerated`), контрактом `OpenAPI` и базовыми unit-тестами для replay-логики.

### Следующий рекомендуемый шаг

`E1 - Preprocessing: sync, clean, quality flags`

---

## 2026-03-21 - E1 - Preprocessing: sync, clean, quality flags

### Запрос

После сверки статуса и подтверждения пользователя выполнить шаг `E1`: реализовать первый preprocessing-контур с синхронизацией потоков, базовой очисткой и quality flags.

### Что сделано

1. Создан отдельный runtime-воркер `services/signal-processing-worker`.
2. Реализован CLI entrypoint `signal-processing-worker` с запуском по `session_id` и режимом `--dry-run`.
3. Реализовано чтение session/stream metadata из `Postgres` (`ingest.raw_sessions`, `ingest.session_streams`, `ingest.ingest_artifacts`).
4. Реализовано чтение raw stream artifacts (`samples.csv(.gz)`) из `MinIO/S3`.
5. Реализован preprocessing pipeline `E1`:
   - sync по единой timeline через `alignment_delta_ms` и `aligned_offset_ms`;
   - базовая очистка stream-specific значений (`hr`, `rr`, `ecg`, `acc`, `gyro`, `confidence`, `hrv`);
   - расчет quality flags: `gaps`, `packet_loss_estimated_samples`, `motion_artifact`, `noisy_intervals`.
6. Реализована запись clean-артефактов и summary в `clean-sessions/<session_id>/<version>/...`.
7. Реализован upsert quality report в `ingest.session_quality_reports` (`quality_report_id = preprocessing_<version>`).
8. Добавлен backend-документ шага `E1` и обновлены корневые `README`/service index.
9. Добавлены unit-тесты preprocessing-логики (`tests/test_models.py`, `tests/test_service.py`).
10. Выполнены локальные проверки:
    - `python -m compileall src tests` проходит;
    - `python -m pytest -q` проходит (`5 passed`).
11. Обновлен статус выполнения: `E1` закрыт, следующим шагом выставлен `E2`.

### Измененные файлы

1. `README.md`
2. `docs/backend/signal-processing-e1.md`
3. `services/README.md`
4. `services/signal-processing-worker/pyproject.toml`
5. `services/signal-processing-worker/.env.example`
6. `services/signal-processing-worker/README.md`
7. `services/signal-processing-worker/src/README.md`
8. `services/signal-processing-worker/src/signal_processing_worker/__init__.py`
9. `services/signal-processing-worker/src/signal_processing_worker/config.py`
10. `services/signal-processing-worker/src/signal_processing_worker/db.py`
11. `services/signal-processing-worker/src/signal_processing_worker/errors.py`
12. `services/signal-processing-worker/src/signal_processing_worker/main.py`
13. `services/signal-processing-worker/src/signal_processing_worker/models.py`
14. `services/signal-processing-worker/src/signal_processing_worker/repository.py`
15. `services/signal-processing-worker/src/signal_processing_worker/service.py`
16. `services/signal-processing-worker/src/signal_processing_worker/storage.py`
17. `services/signal-processing-worker/tests/README.md`
18. `services/signal-processing-worker/tests/test_models.py`
19. `services/signal-processing-worker/tests/test_service.py`
20. `services/signal-processing-worker/deploy/README.md`
21. `services/signal-processing-worker/deploy/Dockerfile`
22. `services/signal-processing-worker/migrations/README.md`
23. `docs/status/execution-status.md`
24. `docs/status/work-log.md`

### Результат

`E1` завершен: backend теперь имеет отдельный `signal-processing-worker`, который из raw-сессии строит стандартизованный clean-layer (`aligned + cleaned samples`) и quality-summary с ключевыми флагами качества.

### Следующий рекомендуемый шаг

`E2 - Feature extraction и clean/features layers`

---

## 2026-03-21 - A4 - Full-scan нереализованных аспектов и синхронизация backlog

### Запрос

Провести полное сканирование системы, убедиться, что незавершенные аспекты не теряются, и добавить недостающие шаги в план для последовательной работы.

### Что сделано

1. Выполнен аудит `on-go` и `on-go-ios` по коду и документации на предмет незавершенных аспектов (`TODO`, `simulated`, `in-memory`, отложенные backend-задачи).
2. Зафиксированы незакрытые блоки capture-контура:
   - live `Polar H10` integration callbacks;
   - live `Watch` collectors (`HealthKit/CoreMotion`);
   - `WatchConnectivity` transport вместо in-memory;
   - файловая сборка raw package вместо in-memory archive;
   - реальный backend upload lifecycle вместо in-memory queue.
3. Зафиксированы backend-блоки hardening:
   - full package checksum policy для ingest;
   - ingest integration/contract tests with fixtures;
   - replay full-stack integration tests;
   - streaming replay transport и orchestration modes.
4. Создан отдельный артефакт аудита `docs/status/system-gap-audit-2026-03-21.md`.
5. Обновлен `execution-status`: добавлены шаги `B4-B9`, `C3-C4`, `D2-D3`; `next` переведен на `B4`.

### Измененные файлы

1. `docs/status/system-gap-audit-2026-03-21.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`

### Результат

Критические незавершенные аспекты формально внесены в backlog как явные шаги с порядком выполнения, поэтому scope не теряется и можно двигаться последовательно.

### Следующий рекомендуемый шаг

`B4 - Live Polar H10 SDK integration`

---

## 2026-03-21 - B4 - Live Polar H10 SDK integration

### Запрос

После сверки статуса и подтверждения пользователя выполнить шаг `B4`: заменить TODO-реализацию `LivePolarH10SDKAdapter` на реальный `PolarBleSdk` callbacks/device lifecycle flow.

### Что сделано

1. Переработан `LivePolarH10SDKAdapter` в `CaptureKit/PhoneCapture`:
   - реальный `PolarBleSdk` API runtime (`PolarBleApiDefaultImpl`) вместо placeholder-логики;
   - подключены observer-каналы (`observer`, `powerStateObserver`, `deviceFeaturesObserver`, `deviceHrObserver`);
   - реализован connect lifecycle для explicit `device_id` и auto-connect;
   - добавлен контроль `HR` feature readiness до старта захвата.
2. Реализован реальный streaming flow:
   - `startHrStreaming` для `polar_hr` и `polar_rr` sample counters;
   - `requestStreamSettings + startEcgStreaming` для `polar_ecg` при доступной online-streaming feature;
   - stop/disconnect cleanup (`dispose`, `disconnectFromDevice`, `cleanup`).
3. Добавлен runtime-конфиг live-адаптера через environment variables (`ON_GO_POLAR_*`) и документация по ним.
4. Обновлена документация `on-go-ios` для шага `B4` (`README`, runtime/setup notes).
5. Синхронизированы текстовые хвосты по шагам:
   - `SessionViewModel` note обновлен под `B4`;
   - TODO-маркеры watch live-сенсоров переведены на `B5`.
6. Выполнена локальная проверка: `swift build` в `../on-go-ios/packages/CaptureKit` проходит успешно.
7. Зафиксировано ограничение среды: фактический runtime-прогон с реальным `Polar H10` и `PolarBleSdk` в текущей shell-среде не выполнялся.
8. Обновлен статус выполнения: `B4` закрыт, следующим шагом выставлен `B5`.

### Измененные файлы

1. `../on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PolarH10Adapter.swift`
2. `../on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchSensorAdapter.swift`
3. `../on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
4. `../on-go-ios/README.md`
5. `../on-go-ios/docs/architecture/capture-runtime.md`
6. `../on-go-ios/docs/setup/local-development.md`
7. `docs/status/execution-status.md`
8. `docs/status/work-log.md`

### Результат

`B4` завершен: `LivePolarH10SDKAdapter` теперь реализует реальный `PolarBleSdk` connection/feature/stream lifecycle для `Polar H10` вместо TODO-заглушки, сохраняя simulated fallback в средах без SDK.

### Следующий рекомендуемый шаг

`B5 - Live Watch HealthKit/CoreMotion integration`

---

## 2026-03-21 - B5 - Live Watch HealthKit/CoreMotion integration

### Запрос

После сверки статуса и подтверждения пользователя выполнить шаг `B5`: заменить TODO-реализацию `LiveWatchSensorAdapter` на реальный `HealthKit/CoreMotion` collectors flow и конвертацию live samples в stream batches.

### Что сделано

1. Переработан `LiveWatchSensorAdapter` в `CaptureKit/WatchCapture`:
   - добавлены реальные `HealthKit` authorization checks и anchored queries для `heartRate` и `heartRateVariabilitySDNN`;
   - добавлены live `CoreMotion` collectors для `accelerometer` и `gyroscope`;
   - реализован runtime state/failure flow (`authorizing/streaming/failed`) с остановкой collectors при ошибках.
2. Реализована конвертация live данных в stream-batches:
   - счетчики sample-count для `watch_heart_rate`, `watch_hrv`, `watch_accelerometer`, `watch_gyroscope`;
   - производный `watch_activity_context` через motion-intensity классификацию и периодический emit;
   - `startCapture` теперь возвращает инициализационные batches по всем watch stream-типам, `nextBatch` отдает очередной live batch с drain-счетчиком.
3. Обновлены локальные документы `on-go-ios` под завершенный шаг `B5` (`README`, runtime architecture, local setup notes).
4. Выполнена локальная проверка: `swift build` в `../on-go-ios/packages/CaptureKit` проходит успешно.
5. Зафиксировано ограничение среды: фактический runtime-прогон watch collectors (`HealthKit/CoreMotion`) в текущей shell-среде не выполнялся.
6. Обновлен статус выполнения: `B5` закрыт, следующим шагом выставлен `B6`.

### Измененные файлы

1. `../on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchSensorAdapter.swift`
2. `../on-go-ios/README.md`
3. `../on-go-ios/docs/architecture/capture-runtime.md`
4. `../on-go-ios/docs/setup/local-development.md`
5. `docs/status/execution-status.md`
6. `docs/status/work-log.md`

### Результат

`B5` завершен: `LiveWatchSensorAdapter` теперь реализует реальный watch-side capture lifecycle на базе `HealthKit/CoreMotion` с live batch-метаданными вместо TODO-заглушек.

### Следующий рекомендуемый шаг

`B6 - WatchConnectivity transport и session handoff`

---

## 2026-03-21 - B6 - WatchConnectivity transport и session handoff

### Запрос

После сверки статуса и подтверждения пользователя выполнить шаг `B6`: заменить in-memory transport на реальный phone-watch канал, убрать `scaffoldSessionID`, и довести сборку `CaptureKit` до чистого состояния по замечаниям компилятора.

### Что сделано

1. Расширен транспортный контракт `SessionTransport`:
   - добавлен двусторонний API `send/receive`;
   - `ConnectivityEnvelope` сделан `Codable` для сериализации.
2. Реализован `WatchConnectivitySessionTransport`:
   - активация `WCSession` и отправка envelope payload;
   - прием `didReceiveMessageData` и `didReceiveUserInfo`;
   - fallback через `SessionTransportFactory` на `InMemorySessionTransport`, когда `WatchConnectivity` недоступен.
3. Обновлен `InMemorySessionTransport` под новый двусторонний поток (`receiveQueue + waiters`) для локальной совместимости без watch framework.
4. Обновлен `PhoneCaptureCoordinator`:
   - default transport через `SessionTransportFactory.makeDefault()`;
   - добавлен фоновой receive-loop для обработки watch envelopes (`event`, `streamBatch`) и записи их в `SessionArchiveStore`.
5. Обновлен `WatchCaptureController`:
   - default transport через `SessionTransportFactory.makeDefault()`;
   - убран API запуска с внешним `sessionID`;
   - добавлено ожидание реального handoff (`.start(sessionID)`) от iPhone перед стартом mirroring.
6. Обновлен watch UI-layer:
   - удален `scaffoldSessionID` из `WatchSessionViewModel`;
   - текст состояния переведен на ожидание handoff от iPhone.
7. Исправлены замечания компилятора Swift 6:
   - устранены concurrency warnings в motion callbacks через передачу value-copies (`x/y/z/timestamp`) в actor methods;
   - стабилизирован continuation-код в `WatchSensorAdapter` для совместимости toolchain.
8. Обновлена локальная документация `on-go-ios` под шаг `B6`.
9. Перегенерирован проект `OnGoCapture.xcodeproj` через `xcodegen`.
10. Выполнена локальная проверка: `swift build` в `../on-go-ios/packages/CaptureKit` проходит успешно.
11. Зафиксировано ограничение среды: `xcodebuild` и автоматическое принятие Xcode "recommended settings" недоступны в текущей CLI-среде без полного Xcode developer directory.

### Измененные файлы

1. `../on-go-ios/packages/CaptureKit/Sources/WatchConnectivityBridge/SessionTransport.swift`
2. `../on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PhoneCaptureCoordinator.swift`
3. `../on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchCaptureController.swift`
4. `../on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchSensorAdapter.swift`
5. `../on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionViewModel.swift`
6. `../on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
7. `../on-go-ios/README.md`
8. `../on-go-ios/docs/architecture/capture-runtime.md`
9. `../on-go-ios/docs/setup/local-development.md`
10. `../on-go-ios/apps/OnGoCapture/OnGoCapture.xcodeproj`
11. `docs/status/execution-status.md`
12. `docs/status/work-log.md`

### Результат

`B6` завершен: transport между `iPhone` и `watchOS` переведен на `WatchConnectivity` с реальным session handoff и двусторонним envelope flow; `CaptureKit` собирается локально без reported compile ошибок.

### Следующий рекомендуемый шаг

`B7 - Raw package assembly в локальном storage iPhone`

---

## 2026-03-21 - B7 - Raw package assembly в локальном storage iPhone

### Запрос

После подтверждения пользователя выполнить шаг `B7`: заменить in-memory `SessionArchiveStore` на файловый raw package assembly по схеме A1.

### Что сделано

1. Добавлен `SessionArchiveDescriptor.packageDirectoryURL` для указания пути к готовому пакету.
2. Реализован `FileBasedSessionArchiveStore` в `CaptureKit/CaptureStorage`:
   - создание структуры `session_<id>/manifest|streams|annotations|reports|checksums` под `Documents/on-go-sessions/`;
   - запись `session-events.jsonl` при `append(event)`;
   - запись `samples.csv` по stream с placeholder-строками при `append(streamBatch)` (metadata-only batches);
   - генерация manifest (`session.json`, `subject.json`, `devices.json`, `segments.json`, `streams.json`), `metadata.json` по каждому stream, `quality-report.json`, `SHA256SUMS`.
3. Введен протокол `SessionArchiveStoring` и фабрика `SessionArchiveStoreFactory.makeDefault()` с fallback на in-memory при недоступности documents.
4. `PhoneCaptureCoordinator` переведен на `any SessionArchiveStoring` с дефолтом `FileBasedSessionArchiveStore`.
5. Обновлена документация `on-go-ios` (`README`, `capture-runtime.md`).

### Измененные файлы

1. `../on-go-ios/packages/CaptureKit/Sources/CaptureStorage/SessionArchiveStore.swift`
2. `../on-go-ios/packages/CaptureKit/Sources/CaptureStorage/FileBasedSessionArchiveStore.swift`
3. `../on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PhoneCaptureCoordinator.swift`
4. `../on-go-ios/README.md`
5. `../on-go-ios/docs/architecture/capture-runtime.md`
6. `docs/status/execution-status.md`
7. `docs/status/work-log.md`

### Результат

`B7` завершен: in-memory store заменен на файловую сборку raw package по канонической схеме A1; package сохраняется при разрыве сети и готов к upload в B8.

### Следующий рекомендуемый шаг

`B8 - Backend upload handoff в ingest-api`

---

## 2026-03-21 - B8 - Backend upload handoff в ingest-api

### Запрос

После подтверждения пользователя выполнить шаг `B8`: заменить in-memory `SessionUploadClient` на HTTP lifecycle (`create/presign/complete/finalize`).

### Что сделано

1. Обновлен `FileBasedSessionArchiveStore`: добавлены поля manifest для ingest-api (`capture_app_version`, `coordinator_device_id`, `consent_version`, `manufacturer`, `started_at_utc`/`ended_at_utc`/`planned` в segments).
2. Реализован `HTTPIngestClient` в `CaptureKit/BackendClient`: чтение raw package, парсинг SHA256SUMS, сборка CreateRawSessionIngestRequest, последовательный вызов `POST /v1/raw-sessions`, `PUT` upload targets, `POST .../artifacts/complete`, `POST .../finalize`.
3. Добавлены `SessionUploadClientProtocol`, `NoOpUploadClient`, `IngestClientConfig`, `IngestClientError`.
4. Фабрика `SessionUploadClientFactory.makeDefault()`: при `ON_GO_INGEST_BASE_URL` возвращает `HTTPIngestClient`, иначе `NoOpUploadClient`.
5. `SessionViewModel` вызывает `uploadClient.upload(descriptor)` после `stopRecording` при наличии `packageDirectoryURL`.
6. Обновлена документация `on-go-ios` (README, capture-runtime.md, local-development.md).

### Измененные файлы

1. `../on-go-ios/packages/CaptureKit/Sources/CaptureStorage/FileBasedSessionArchiveStore.swift`
2. `../on-go-ios/packages/CaptureKit/Sources/BackendClient/SessionUploadClient.swift`
3. `../on-go-ios/packages/CaptureKit/Sources/BackendClient/IngestClientConfig.swift`
4. `../on-go-ios/packages/CaptureKit/Sources/BackendClient/IngestClientError.swift`
5. `../on-go-ios/packages/CaptureKit/Sources/BackendClient/SessionUploadClientProtocol.swift`
6. `../on-go-ios/packages/CaptureKit/Sources/BackendClient/NoOpUploadClient.swift`
7. `../on-go-ios/packages/CaptureKit/Sources/BackendClient/HTTPIngestClient.swift`
8. `../on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
9. `../on-go-ios/README.md`
10. `../on-go-ios/docs/architecture/capture-runtime.md`
11. `../on-go-ios/docs/setup/local-development.md`
12. `docs/status/execution-status.md`
13. `docs/status/work-log.md`

### Результат

`B8` завершен: in-memory upload заменен на HTTP lifecycle к ingest-api; при настройке `ON_GO_INGEST_BASE_URL` iPhone загружает raw package в backend после остановки сессии.

### Следующий рекомендуемый шаг

`B9 - Device E2E validation runbook`

---

## 2026-03-21 - B9 - Device E2E validation runbook

### Запрос

После подтверждения пользователя выполнить шаг `B9`: создать сквозной ручной runbook и checklist приемки для цепочки `phone+watch+polar -> ingest`.

### Что сделано

1. Создан документ `docs/capture/device-e2e-validation-runbook.md`.
2. Описаны prerequisites: оборудование (iPhone, Apple Watch, Polar H10), backend stack, on-go-ios.
3. Добавлена конфигурация: `ON_GO_INGEST_BASE_URL` (simulator vs device), `ON_GO_INGEST_AUTH_TOKEN`, Polar env vars.
4. Pre-flight checklist: health ingest-api, пара устройств, Polar готов, HealthKit разрешения.
5. Capture flow: Prepare → Start → Record (опционально) → Stop с чеклистами на каждом шаге.
6. Verification: локальный package (структура A1), backend ingest state (`GET /v1/raw-sessions`), storage (MinIO/Postgres).
7. Acceptance checklist: 7 критериев приемки.
8. Troubleshooting: Polar, Watch handoff, upload failed, ingest failed.
9. Добавлены ссылки в README (on-go, on-go-ios).

### Измененные файлы

1. `docs/capture/device-e2e-validation-runbook.md`
2. `README.md`
3. `../on-go-ios/README.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`

### Результат

`B9` завершен: Device E2E validation runbook готов для ручного сквозного прогона capture → ingest.

### Следующий рекомендуемый шаг

`C3 - Full package checksum policy hardening`

---

## 2026-03-22 - B10 - Device capture debugging: real sample payloads и watch auto-handoff

### Запрос

После подтверждения пользователя выполнить отдельный debugging-шаг: выяснить, почему в backend записываются нули по `rr/hr/ecg`, и проверить, почему `Apple Watch` фактически не участвует в записи.

### Что сделано

1. Проверен путь данных `watch/polar -> on-go-ios CaptureKit -> raw package -> ingest-api`.
2. Локализована основная причина нулей: `StreamBatchMetadata` в `on-go-ios` переносил только `sampleCount`, а `FileBasedSessionArchiveStore` при записи `samples.csv` подставлял placeholder-значения `0`.
3. Доменные модели `CaptureKit` переведены на реальные sample payloads:
   - добавлен `StreamSample` c `timestamp` и словарем `values`;
   - `StreamBatchMetadata.sampleCount` стал вычисляться из массива samples.
4. Обновлены `PolarH10Adapter` и `WatchSensorAdapter`:
   - simulated adapters теперь генерируют реалистичные sample values вместо metadata-only batches;
   - live `Polar` path сериализует реальные `ECG voltage`, `HR`, `RR` на основе callback-данных;
   - live `Watch` path сериализует `heart_rate`, `HRV SDNN`, `accelerometer`, `gyroscope`, `activity_context`.
5. Обновлен `FileBasedSessionArchiveStore`:
   - `samples.csv` теперь пишется из реальных sample payloads с per-sample `timestamp_utc`, `offset_ms`, `source_timestamp`;
   - добавлено CSV-экранирование строковых полей;
   - для `watch_hrv` колонка выровнена на `sdnn_ms`, чтобы соответствовать preprocessing-воркеру.
6. Координаторы capture (`PhoneCaptureCoordinator`, `WatchCaptureController`) обновлены так, чтобы пустые batches не попадали в package и transport.
7. Watch UI переведен в auto-listening режим: при открытии watch-экрана `startMirror()` запускается автоматически, поэтому часы сразу ждут `start(sessionID)` от iPhone без обязательного ручного нажатия `Start`.
8. Локальная верификация:
   - `cd ../on-go-ios/packages/CaptureKit && swift build` проходит успешно;
   - `xcodebuild` недоступен в текущей shell-среде, потому что активен только `CommandLineTools`, а не полный Xcode.

### Измененные файлы

1. `../on-go-ios/packages/CaptureKit/Sources/CaptureDomain/CaptureDomainModels.swift`
2. `../on-go-ios/packages/CaptureKit/Sources/CaptureStorage/FileBasedSessionArchiveStore.swift`
3. `../on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PolarH10Adapter.swift`
4. `../on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PhoneCaptureCoordinator.swift`
5. `../on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchSensorAdapter.swift`
6. `../on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchCaptureController.swift`
7. `../on-go-ios/packages/CaptureKit/Sources/TestSupport/SessionFixtures.swift`
8. `../on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionViewModel.swift`
9. `../on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionView.swift`
10. `docs/status/execution-status.md`
11. `docs/status/work-log.md`

### Результат

`B10` завершен: capture package больше не записывает нулевые placeholder-значения для `rr/hr/ecg` и watch streams; при открытии watch app часы автоматически входят в режим ожидания handoff от iPhone и начинают участвовать в capture без дополнительного ручного шага.

### Следующий рекомендуемый шаг

`C3 - Full package checksum policy hardening`

---

## 2026-03-22 - B11 - HKWorkoutSession migration design note

### Запрос

После подтверждения пользователя подготовить очень подробную документальную фиксацию перехода от текущего `WatchConnectivity`-based watch capture к `HKWorkoutSession`/mirrored session flow, а к реализации приступить следующим шагом.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. Собран текущий локальный контекст по `on-go-ios`:
   - текущая архитектура `capture-runtime`;
   - ограничения локальной разработки;
   - действующий device E2E runbook.
3. Дополнительно проверены официальные материалы Apple по `HealthKit` и multi-device workout flow, чтобы design note опирался на platform-recommended path, а не на предположения.
4. Создан новый подробный документ `docs/capture/hkworkoutsession-migration-design.md`, в котором зафиксированы:
   - почему текущий `WatchConnectivity`-flow недостаточен;
   - platform rationale для `HKWorkoutSession`;
   - целевая архитектура `watch primary session -> iphone mirrored session`;
   - разделение ownership между `workout session` и research `session_id`;
   - target lifecycle `prepare/start/attach/record/pause/stop`;
   - recommended data plane для watch sample batches;
   - изменения по модулям `on-go-ios`;
   - acceptance criteria, риски и phased migration plan.
5. Документ добавлен в навигацию `README.md`.
6. Статус выполнения обновлен:
   - `B11` добавлен как `completed`;
   - новый implementation-шаг `B12` добавлен как `next`;
   - backend-шаг `C3` переведен из `next` в `pending`, чтобы зафиксировать согласованный приоритет на workout-session migration.

### Измененные файлы

1. `README.md`
2. `docs/capture/hkworkoutsession-migration-design.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`

### Результат

`B11` завершен: подготовлен детальный design note по migration на `HKWorkoutSession`, достаточный для начала реализации без архитектурной неоднозначности; следующим шагом зафиксирован `B12 - HKWorkoutSession-based capture migration implementation`.

### Следующий рекомендуемый шаг

`B12 - HKWorkoutSession-based capture migration implementation`

---

## 2026-03-22 - B12 - HKWorkoutSession-based capture migration implementation

### Запрос

После подтверждения пользователя выполнить шаг `B12`: реализовать migration от `WatchConnectivity`-only capture-start к `HKWorkoutSession` (`watch primary -> iPhone mirrored`), убрать зависимость старта от ручного запуска на часах и сохранить текущий research/session package flow.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. В `CaptureKit` расширен транспортный контракт:
   - добавлены lifecycle-методы `activate()` и `startRemoteCapture(sessionID:at:)`;
   - `PhoneCaptureCoordinator` переведен на `watchTransport.activate()` и `watchTransport.startRemoteCapture(...)` вместо прямой отправки `.start`.
3. Реализован `WorkoutSessionTransport` в `WatchConnectivityBridge/SessionTransport.swift`:
   - iPhone-side (`WorkoutSessionTransportIOS`): `HealthKit startWatchApp`, ожидание `mirrored workout session` c timeout, передача envelope payloads через workout remote data API;
   - watch-side (`WorkoutSessionTransportWatchOS`): подъем primary `HKWorkoutSession`, `startMirroringToCompanionDevice`, отправка/прием envelope payloads через workout data plane;
   - добавлены transport-level ошибки для failed/timed-out startup и workout send/runtime ситуаций.
4. Сохранен fallback path:
   - factory выбирает `WorkoutSessionTransport` на реальном iOS/watchOS device;
   - при недоступности workout runtime используется `WatchConnectivitySessionTransport`, а в ограниченной среде остается `InMemorySessionTransport`.
5. `WatchCaptureController` обновлен: перед ожиданием `start(sessionID)` теперь вызывает `transport.activate()`, чтобы watch-side platform session запускалась автоматически.
6. Обновлены тексты app/UI и документация `on-go-ios` под новый flow (`README`, `capture-runtime`, `local-development`).
7. Выполнена локальная верификация: `cd ../on-go-ios/packages/CaptureKit && swift build` проходит успешно.

### Измененные файлы

1. `../on-go-ios/packages/CaptureKit/Sources/WatchConnectivityBridge/SessionTransport.swift`
2. `../on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PhoneCaptureCoordinator.swift`
3. `../on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchCaptureController.swift`
4. `../on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionViewModel.swift`
5. `../on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
6. `../on-go-ios/README.md`
7. `../on-go-ios/docs/architecture/capture-runtime.md`
8. `../on-go-ios/docs/setup/local-development.md`
9. `docs/status/execution-status.md`
10. `docs/status/work-log.md`

### Результат

`B12` завершен: capture migration на `HKWorkoutSession` реализована на уровне transport/orchestration, iPhone теперь стартует watch runtime платформенно через HealthKit и работает с mirrored session/data plane; зависимость от ручного старта capture на watch устранена.

### Следующий рекомендуемый шаг

`C3 - Full package checksum policy hardening`
