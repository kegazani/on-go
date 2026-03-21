# Структура Swift-репозитория `on-go-ios`

## Цель

Этот документ фиксирует минимальную, но устойчивую структуру отдельного репозитория `on-go-ios`, который будет отвечать за capture-прототип paired-сессий с `Polar H10` и `Apple Watch`.

Задача шага `B1`: не реализовать приложение целиком, а заранее зафиксировать такие границы репозитория и модулей, чтобы шаг `B2` можно было выполнять без пересборки архитектуры с нуля.

## Роль репозитория

`on-go-ios` отвечает только за клиентскую capture-часть:

1. `iPhone companion app`;
2. `watchOS app`;
3. lifecycle записи сессии;
4. интеграцию с `Polar H10`;
5. сбор сигналов `Apple Watch`;
6. локальный буфер и экспорт raw session package;
7. отправку экспорта в backend по опубликованным контрактам;
8. ручной `post-session self-report`.

Репозиторий не должен включать backend ingest-логику, replay, preprocessing или training pipeline. Эти зоны остаются в `on-go`.

## Базовые принципы

1. `iPhone` является координатором и владельцем `session_id`, lifecycle и финального export package.
2. `Apple Watch` отвечает за локальный сбор watch-сигналов и передачу данных на телефон.
3. Все raw samples сохраняются по принципу `raw-first`, без ранней lossy-агрегации.
4. Сбор данных и экспорт должны выдерживать временные разрывы связи между часами и телефоном.
5. Интеграция с backend идет только через versioned contracts из backend-репозитория.
6. Внутренние shared-модули должны быть достаточно малыми, чтобы не тормозить шаг `B2`, но достаточно явными, чтобы не смешивать UI, capture-логику и transport code.

## Рекомендуемая структура репозитория

```text
on-go-ios/
  README.md
  apps/
    OnGoCapture/
      OnGoCapture.xcodeproj
      iPhoneApp/
      WatchApp/
      WatchExtension/
      OnGoCaptureTests/
      OnGoCaptureUITests/
  packages/
    CaptureKit/
      Package.swift
      Sources/
        CaptureDomain/
        CaptureStorage/
        WatchConnectivityBridge/
        PhoneCapture/
        WatchCapture/
        BackendClient/
        TestSupport/
      Tests/
        CaptureDomainTests/
        CaptureStorageTests/
        WatchConnectivityBridgeTests/
        PhoneCaptureTests/
        WatchCaptureTests/
        BackendClientTests/
  config/
    xcconfig/
      Base.xcconfig
      Debug.xcconfig
      Release.xcconfig
  docs/
    architecture/
      capture-runtime.md
    setup/
      local-development.md
  scripts/
  .github/
    workflows/
```

## Почему именно так

### `apps/`

В `apps/` живут только конечные application targets и их минимальный bootstrap-код:

1. `OnGoCapture` для `iPhone`;
2. `OnGoWatchApp` и `OnGoWatchExtension` для `watchOS`.

На старте рекомендуется один `xcodeproj` с обоими приложениями и общими схемами сборки. Для пары `iPhone + watchOS companion app` это проще, чем сразу заводить отдельные проекты. UI, permissions entrypoints, app lifecycle и wiring зависимостей остаются рядом с таргетами. Это позволяет на шаге `B2` быстро собрать рабочий skeleton без раннего усложнения.

### `packages/CaptureKit`

Вместо нескольких независимых пакетов на старте рекомендуется один локальный Swift package `CaptureKit` с несколькими targets. Для прототипа это проще, чем разносить код по нескольким пакетам и синхронизировать их версии.

Такой пакет дает:

1. явные границы между доменной логикой и платформенными интеграциями;
2. повторное использование кода между `iPhone` и `watchOS`;
3. изолируемые unit-tests;
4. простой переход от шага `B1` к `B2`.

## Модули `CaptureKit`

### `CaptureDomain`

Shared-модуль для доменной модели capture-сессии.

Должен содержать:

1. идентификаторы `session_id`, `stream_id`, `segment_id`, `device_id`;
2. enums для `stream_name`, `device_role`, `event_type`, `session_status`;
3. структуры для `session`, `protocol_segment`, `device`, `device_stream`, `session_event`, `self_report`, `quality_report`;
4. DTO и value objects, соответствующие канонической схеме из `docs/research/session-data-schema.md`.

Этот модуль не должен знать про `SwiftUI`, `Polar SDK`, `HealthKit`, `CoreMotion` или сеть.

### `CaptureStorage`

Модуль локального append-only хранения.

Должен отвечать за:

1. временные файлы и chunk-based буферизацию raw streams;
2. сборку `raw session package`;
3. запись manifest-файлов;
4. checksums;
5. экспорт immutable-пакета для дальнейшей отправки.

Формат экспорта обязан следовать `docs/research/session-data-schema.md`.

### `WatchConnectivityBridge`

Модуль транспорта между часами и телефоном.

Должен содержать:

1. message contracts между `watchOS` и `iPhone`;
2. адаптеры над `WatchConnectivity`;
3. подтверждения доставки и диагностику разрывов связи;
4. перевод transport-событий в доменные `session_event`.

Этот слой не должен принимать решения о UX или управлять жизненным циклом сессии.

### `PhoneCapture`

`iPhone`-специфичный orchestration-модуль.

Должен отвечать за:

1. старт и остановку сессии;
2. создание `session_id`;
3. управление protocol segments;
4. интеграцию с `Polar H10` через отдельный adapter layer;
5. прием данных от часов;
6. агрегацию raw streams;
7. подготовку self-report и экспортного статуса;
8. запуск upload flow после завершения сессии.

Именно этот модуль является владельцем финальной сборки raw package.

### `WatchCapture`

`watchOS`-специфичный модуль для сбора watch-сигналов.

Должен отвечать за:

1. доступ к watch sensors и platform APIs;
2. локальный буфер на часах при временной недоступности телефона;
3. отправку данных и session events на `iPhone`;
4. локальное отражение статуса capture и соединения.

Watch не должен собирать финальный export package и не должен знать про backend ingest.

### `BackendClient`

Тонкий клиент загрузки данных в backend.

Правила:

1. зависит от versioned контрактов backend;
2. не содержит бизнес-логики capture;
3. используется только `iPhone`-стороной;
4. должен позволять отложенную отправку уже собранного export package.

### `TestSupport`

Тестовые фикстуры и builders для manifest, streams, session events и sample exports.

Этот модуль нужен, чтобы на шагах `B2` и `B3` можно было писать тесты без копирования больших JSON- и CSV-заготовок между таргетами.

## Разделение ответственности между устройствами

### `iPhone`

На стороне телефона должны жить:

1. `Polar SDK`;
2. canonical session lifecycle;
3. статус paired-session;
4. финальная сборка raw session package;
5. локальная очередь upload-задач;
6. операторский UI и post-session form.

### `Apple Watch`

На стороне часов должны жить:

1. сбор watch sensors;
2. локальная индикация состояния записи;
3. временное хранение до доставки на телефон;
4. transport к телефону через `WatchConnectivity`.

### Shared layer

В shared-коде должны жить только:

1. доменные типы;
2. transport contracts;
3. storage contracts;
4. use case interfaces, которые не привязаны к конкретному UI target.

## Поток данных в capture-сессии

Рекомендуемый рабочий контур:

1. `iPhone` инициирует сессию и создает `session_id`.
2. `watchOS app` получает команду старта и начинает локальный сбор.
3. `PhoneCapture` запускает `Polar H10` capture и пишет coordinator-side events.
4. `WatchCapture` пересылает данные и события на телефон батчами или по окнам.
5. `CaptureStorage` на `iPhone` собирает raw streams и manifest-файлы.
6. После `stop` телефон закрывает пакет, пишет checksums и переводит сессию в export-ready состояние.
7. `BackendClient` отправляет готовый пакет в backend отдельно от самой capture-логики.

## Связь с уже зафиксированными research-артефактами

Структура `on-go-ios` должна прямо поддерживать уже подготовленные документы:

1. `docs/research/research-protocol.md` задает lifecycle paired-сессии и обязательные protocol segments.
2. `docs/research/session-data-schema.md` задает canonical raw package, который обязан формировать `CaptureStorage`.
3. `docs/research/label-specification.md` задает структуру `self-report` и label-related данных.
4. `docs/research/evaluation-plan.md` влияет на то, какие metadata и quality flags нельзя терять на этапе capture.

## Что должно быть готово на шаге `B2`

Следующий шаг должен опираться на эту структуру и создать:

1. Xcode-каркас `iPhone`- и `watchOS`-таргетов;
2. локальный пакет `CaptureKit` с пустыми или минимальными target-модулями;
3. базовый dependency wiring между app targets и shared-модулями;
4. placeholder-экраны и session lifecycle skeleton;
5. smoke-tests на сборку базовых модулей.

## Что намеренно не делается на шаге `B1`

Этот шаг намеренно не включает:

1. реальную интеграцию `Polar H10`;
2. реальный сбор `HealthKit` или motion streams;
3. backend ingest implementation;
4. полную схему локальной БД;
5. production-grade CI.

Это относится к следующим шагам `B2` и `B3`.
