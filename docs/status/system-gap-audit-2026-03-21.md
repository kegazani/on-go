# System Gap Audit (2026-03-21)

## Цель

Зафиксировать нереализованные аспекты по `on-go` и `on-go-ios`, чтобы они не потерялись между фазами и были превращены в явные шаги execution backlog.

## Область сканирования

1. `on-go/services`, `on-go/infra`, `on-go/docs/backend`
2. `on-go-ios/packages/CaptureKit`, `on-go-ios/apps/OnGoCapture`, `on-go-ios/docs`
3. Маркеры: `TODO`, `simulated`, `in-memory`, `stubbed`, а также "что остается" в backend-документах.

## Найденные нереализованные аспекты

### 1) Реальные датчики (Capture runtime)

1. `LivePolarH10SDKAdapter` содержит TODO по discovery/connection/callbacks:
   - `on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PolarH10Adapter.swift`
2. `LiveWatchSensorAdapter` содержит TODO по HealthKit/CoreMotion collectors и mapping samples:
   - `on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchSensorAdapter.swift`

### 2) Phone-Watch transport и session handoff

1. Используется `InMemorySessionTransport`:
   - `on-go-ios/packages/CaptureKit/Sources/WatchConnectivityBridge/SessionTransport.swift`
2. Watch UI использует `scaffoldSessionID`, а не phone-owned session handoff:
   - `on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionViewModel.swift`

### 3) Локальное хранение raw package и upload

1. `SessionArchiveStore` остается in-memory:
   - `on-go-ios/packages/CaptureKit/Sources/CaptureStorage/SessionArchiveStore.swift`
2. `SessionUploadClient` остается in-memory queue:
   - `on-go-ios/packages/CaptureKit/Sources/BackendClient/SessionUploadClient.swift`

### 4) Backend hardening и e2e coverage

1. В `raw-ingest-c2` явно отложены:
   - расширенная full-package checksum policy;
   - интеграционные/контрактные тесты ingest.
2. В `replay-d1` явно отложены:
   - streaming transport (`SSE/WebSocket`);
   - orchestration modes и replay run registry;
   - full-stack replay integration tests.
3. Локальный compose-стек покрывает только ingest-контур (`raw-ingest-stack.yml`), без replay/processing сервисов.

## Backlog-синхронизация

По результатам аудита добавлены шаги в `docs/status/execution-status.md`:

1. `B4` - Live Polar H10 SDK integration
2. `B5` - Live Watch HealthKit/CoreMotion integration
3. `B6` - WatchConnectivity transport и session handoff
4. `B7` - Raw package assembly в локальном storage iPhone
5. `B8` - Backend upload handoff в ingest-api
6. `B9` - Device E2E validation runbook
7. `C3` - Full package checksum policy hardening
8. `C4` - Ingest integration/contract tests with fixtures
9. `D2` - Replay integration tests на полном локальном стеке
10. `D3` - Streaming replay transport и orchestration modes

## Итог

Критические пробелы переведены в явный backlog. Следующий приоритетный шаг выставлен как `B4`.
