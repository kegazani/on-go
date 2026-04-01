# Подробный roadmap: research -> ML pipeline -> backend

## 1. Цель проекта

Нужно построить систему, которая:

1. Собирает совместные данные с `Polar H10` и `Apple Watch`.
2. Хранит сырые записи так, чтобы их можно было воспроизводить для симуляции.
3. Обрабатывает, синхронизирует и очищает сигналы.
4. Обучает две модели:
   - `fusion model`: `Polar H10 + Apple Watch`;
   - `watch-only model`: только `Apple Watch`.
5. Показывает, как персонализация влияет на качество обеих моделей.
6. Постепенно эволюционирует из исследовательского прототипа в полноценную backend-систему.

## 2. Базовые допущения

1. `Polar H10` используется как более качественный источник кардиоданных.
2. `Apple Watch` используется как массовое носимое устройство с ограниченным доступом к сердечным данным, но полезным motion/context сигналом.
3. Во время исследовательских сессий пользователь носит оба устройства одновременно.
4. Основная научная гипотеза: модель на `Polar H10 + Apple Watch` должна быть лучше, чем модель на одних часах.
5. Дополнительная гипотеза: персонализация улучшает обе модели.

## 3. Репозитории и зоны ответственности

### 3.1 Backend monorepo

Текущий репозиторий:

- `on-go/`

Отвечает за:

- ingest API;
- хранение raw/clean/features;
- replay;
- preprocessing;
- dataset registry;
- training pipeline;
- model registry;
- personalization;
- inference API.

### 3.2 Отдельный Swift-репозиторий

Отдельный репозиторий, который нужно будет создать позже:

- `on-go-ios/`

Отвечает за:

- `watchOS app`;
- `iPhone companion app`;
- запись сессий;
- подключение к `Polar H10`;
- сбор данных `Apple Watch`;
- отправку сессий в backend;
- ручную разметку состояния пользователя.

## 4. Общая стратегия реализации

Проект делится на три крупные фазы:

1. `Research`
   Сначала доказываем, что гипотеза вообще подтверждается.
2. `Reproducible ML Pipeline`
   Затем делаем воспроизводимый путь от сырых данных до обученной модели.
3. `Production Backend`
   Только потом превращаем исследовательские наработки в полноценно обслуживаемую backend-систему.

Переход к следующей фазе делается только после достижения критериев завершения предыдущей.

## 5. Фаза A: Research Foundation

### Цель

Подготовить исследовательский каркас и зафиксировать правила, по которым дальше будет вестись сбор и оценка данных.

### Задачи

1. Зафиксировать исследовательские гипотезы.
2. Выбрать целевые состояния для моделирования:
   - `activity/context`;
   - `arousal/stress`;
   - позже `valence`.
3. Определить метрики качества:
   - classification metrics;
   - regression metrics, если цель будет непрерывной;
   - subject-wise evaluation;
   - прирост от персонализации.
4. Описать структуру сессии записи.
5. Описать сущности данных:
   - `subject`;
   - `session`;
   - `device_stream`;
   - `label`;
   - `quality_report`;
   - `replay_manifest`;
   - `model_run`.
6. Зафиксировать протокол разметки:
   - когда пользователь заполняет self-report;
   - какие вопросы задаются;
   - как задаются `valence` и `arousal`.

### Артефакты

1. Документ `research protocol`.
2. Схема данных сессии.
3. Спецификация лейблов.
4. Таблица метрик и правил валидации.

### Критерий завершения

Можно однозначно ответить:

1. Что именно считается целевой переменной.
2. Какие данные должны быть записаны в каждой сессии.
3. Как будет измеряться успех модели.

### Что просить у меня на этом этапе

1. "Сделай research protocol и схему данных сессии."
2. "Опиши формат разметки valence/arousal и activity labels."
3. "Подготовь спецификацию метрик и evaluation plan."

## 6. Фаза B: Capture Prototype

### Цель

Создать минимальную систему записи paired-сессий с `Polar H10` и `Apple Watch`.

### Задачи

1. Спроектировать структуру Swift-репозитория.
2. Подключить `Polar H10` на iPhone через SDK.
3. Реализовать начало и завершение сессии записи.
4. Получать и сохранять потоки:
   - `Polar ECG`;
   - `Polar RR`;
   - `Polar HR`;
   - `Polar ACC`, если нужен и доступен для записи;
   - `Apple Watch heart-related metrics`;
   - `Apple Watch accelerometer/gyroscope/context`.
5. Добавить локальное временное хранение на телефоне на случай обрыва сети.
6. Добавить статус соединения устройств и состояние сессии.
7. Добавить ручную разметку после сессии.

### Артефакты

1. Swift-приложение с рабочей записью paired sessions.
2. Локальный экспорт тестовой сессии.
3. Минимальная документация по запуску.

### Критерий завершения

Есть хотя бы несколько воспроизводимых тестовых сессий, где:

1. оба устройства синхронно записаны;
2. у каждого потока есть timestamps и metadata;
3. запись не теряется при кратковременных сбоях.

### Что просить у меня на этом этапе

1. "Спроектируй структуру отдельного Swift-репозитория."
2. "Сделай каркас iPhone/watchOS приложения для записи сессий."
3. "Добавь интеграцию с Polar H10 SDK."
4. "Добавь экран начала/завершения записи и сохранение сырых сессий."

## 7. Фаза C: Raw Data Ingestion and Storage

### Цель

Построить backend-контур, который принимает и хранит сырые записи без потерь.

### Задачи

1. Спроектировать контракты ingest API.
2. Реализовать загрузку сессии и связанных stream-файлов.
3. Ввести разделение на уровни хранения:
   - `raw`;
   - `clean`;
   - `features`.
4. Выбрать способ хранения:
   - metadata в `Postgres`;
   - time series и артефакты в `MinIO/S3`;
   - при необходимости колоночное представление для датасетов.
5. Добавить версионирование записей и audit trail.
6. Ввести checksums и контроль целостности.

### Артефакты

1. `ingest-api`.
2. Схема БД.
3. Объектное хранилище raw sessions.
4. Документация по загрузке и форматам файлов.

### Критерий завершения

Можно загрузить сырую сессию и потом полностью восстановить ее из backend.

### Что просить у меня на этом этапе

1. "Сделай ingest API и схему БД для raw sessions."
2. "Добавь хранение raw streams в S3/MinIO."
3. "Опиши data contracts для загрузки сессий."

## 8. Фаза D: Replay and Simulation

### Цель

Сделать воспроизведение записанных сессий как live stream для отладки и демонстрации моделей.

### Задачи

1. Определить формат `replay_manifest`.
2. Реализовать чтение raw session из хранилища.
3. Реализовать режимы воспроизведения:
   - realtime;
   - accelerated;
   - window-by-window.
4. Добавить синхронное воспроизведение нескольких потоков:
   - Polar;
   - Watch;
   - labels/events.
5. Подготовить API или worker для подачи replay-потока в inference pipeline.

### Артефакты

1. `replay-service`.
2. Набор тестовых replay sessions.
3. Интерфейс запуска replay для моделирования.

### Критерий завершения

Модель можно прогонять на исторической сессии так, будто она идет в live-режиме.

### Что просить у меня на этом этапе

1. "Сделай replay service для воспроизведения raw sessions."
2. "Добавь replay manifest и API запуска симуляции."

## 9. Фаза E: Signal Processing Research Pipeline

### Цель

Сделать первую полноценную цепочку обработки сигналов.

### Задачи

1. Синхронизировать потоки `Polar` и `Watch`.
2. Привести временные метки к единой шкале.
3. Реализовать базовую очистку кардиосигналов.
4. Реализовать обработку motion-данных.
5. Добавить quality flags:
   - gaps;
   - packet loss;
   - motion artifacts;
   - noisy intervals.
6. Сделать windowing.
7. Вычислять derived features:
   - HRV features;
   - time-domain features;
   - frequency-domain features;
   - activity features;
   - context features.
8. Сохранять результат в `clean` и `features`.

### Артефакты

1. `signal-processing-worker`.
2. Версия preprocessing pipeline.
3. Документ по признакам и правилам очистки.

### Критерий завершения

Из любой raw-сессии можно получить стандартизованный clean/features набор.

### Что просить у меня на этом этапе

1. "Сделай preprocessing pipeline для синхронизации Polar и Watch."
2. "Добавь quality flags и feature extraction."
3. "Опиши, какие признаки мы извлекаем и зачем."

## 10. Фаза F: Public Datasets and Dataset Registry

### Цель

Подключить внешние датасеты и навести порядок в версиях тренировочных наборов.

### Задачи

1. Выбрать стартовые внешние датасеты.
2. Написать ingestion scripts для каждого датасета.
3. Привести внешние данные к общей внутренней схеме.
4. Отдельно пометить:
   - собственные paired data;
   - внешние датасеты;
   - synthesized/replay datasets.
5. Ввести dataset registry:
   - источник;
   - версия;
   - preprocessing version;
   - split strategy;
   - target labels.

### Приоритетные датасеты

1. `WESAD`
2. `EmoWear`
3. `G-REx`
4. `DAPPER`

### Артефакты

1. `dataset-registry`.
2. Скрипты импорта датасетов.
3. Единая схема train/validation/test datasets.

### Критерий завершения

Можно воспроизводимо собрать тренировочный датасет из внешних и собственных данных.

### Что просить у меня на этом этапе

1. "Подготовь обзор и приоритет внешних датасетов."
2. "Сделай dataset registry и формат dataset metadata."
3. "Добавь импорт WESAD в нашу внутреннюю схему."

## 11. Фаза G: Baseline Modeling

### Цель

Обучить первые сравнимые модели.

### Задачи

1. Подготовить baseline-постановки:
   - `activity/context classification`;
   - `arousal/stress prediction`;
   - позже `valence`.
2. Сформировать две группы входов:
   - `fusion inputs`;
   - `watch-only inputs`.
3. Построить первые baseline модели:
   - feature-based classical ML;
   - затем sequence model.
4. Реализовать единую evaluation pipeline.
5. Сделать честные split rules:
   - subject-wise;
   - session-wise;
   - cross-dataset, где применимо.
6. Подготовить сравнительный отчет.
7. Для каждого major run сохранять подробный research report:
   - labels;
   - preprocessing;
   - features;
   - data inclusion/exclusion;
   - model config;
   - результаты;
   - failure analysis;
   - выводы для decision making.
8. Для baseline и comparison шагов строить подробные графики и таблицы, пригодные для презентации.
9. Сравнивать не одну модель, а несколько candidate approaches:
   - trivial baselines;
   - classical ML baselines;
   - modality ablations;
   - feature ablations;
   - при достаточных данных sequence-aware families.
10. Перед переходом к personalization выполнять multi-dataset harmonization и benchmarking:
   - довести минимум `3` внешних datasets до modeling-ready состояния;
   - прогнать per-dataset и cross-dataset сравнение;
   - зафиксировать переносимость лучших `watch-only/fusion` подходов.

### Артефакты

1. `training-pipeline`.
2. Baseline experiment configs.
3. Evaluation report.
4. Detailed `research report` по каждому основному experiment family.
5. Пакет графиков и сравнительных таблиц для презентации.
6. Сводная таблица сравнения model families, modalities и ablations.

### Критерий завершения

Есть сравнимые цифры по `fusion` и `watch-only` на одинаковом evaluation protocol, плюс подробные отчеты и визуальные comparison artifacts, достаточные для research review и презентации.

### Что просить у меня на этом этапе

1. "Сделай baseline training pipeline для fusion и watch-only моделей."
2. "Добавь evaluation scripts и отчеты по метрикам."
3. "Сделай первое сравнение моделей на наших данных."
4. "Сделай подробный research report с графиками, label/data/preprocessing traceability и сравнением нескольких моделей."
5. "Сделай multi-dataset harmonization и comparative benchmark по WESAD/EmoWear/DAPPER/G-REx."

## 12. Фаза H: Personalization Research

### Цель

Проверить, насколько персонализация улучшает качество, и сформировать воспроизводимую методику персонализации как основной научный вклад работы.

### Задачи

1. Спроектировать профиль пользователя:
   - resting HR;
   - baseline HRV;
   - поведенческие паттерны;
   - индивидуальные диапазоны.
2. Реализовать `light personalization`:
   - baseline normalization;
   - calibration;
   - subject-specific thresholds.
3. Реализовать `full personalization`:
   - fine-tuning части модели;
   - отдельная subject-specific head;
   - few-shot adaptation.
4. Сравнить:
   - `global fusion` vs `personalized fusion`;
   - `global watch-only` vs `personalized watch-only`.
5. Для каждого personalization run публиковать подробный research report с budget, subject-level gains, деградациями и графиками.
6. После базовых `light/full` вариантов выделить отдельный methodological track:
   - персонализация поверх уже обученного `WESAD` baseline;
   - `watch-only` и `fusion` как две обязательные линии;
   - `arousal` и `valence` как основные целевые personalization outputs;
   - label-efficient и label-free варианты адаптации как основной предмет исследования.
7. Перед переходом в ML Platform зафиксировать:
   - research objective;
   - сравниваемые personalization strategies;
   - границы claim-grade интерпретации для `valence` и внешних datasets.

### Артефакты

1. `personalization-worker`.
2. Персональный профиль субъекта.
3. Отчет по приросту качества после персонализации.
4. Графики subject-level personalization gain и sensitivity к calibration budget.
5. Документ с методикой персонализации и научными гипотезами по adaptation strategies.

### Критерий завершения

Есть измеримый и воспроизводимый результат влияния персонализации на обе модели, документированный подробным сравнительным отчетом и визуальными артефактами.

### Что просить у меня на этом этапе

1. "Сделай схему профиля пользователя для персонализации."
2. "Добавь light personalization в pipeline."
3. "Реализуй персонализированное дообучение модели."
4. "Переформулируй roadmap так, чтобы основной научный вклад был в методике персонализации поверх WESAD baseline."
5. "Добавь сравнение label-efficient и label-free personalization strategies."

## 13. Фаза I: Research Report and Decision Gate

### Цель

Подвести итог исследования и решить, что именно переносить в production.

### Задачи

1. Подготовить исследовательский отчет:
   - гипотезы;
   - данные;
   - preprocessing;
   - модели;
   - метрики;
   - ограничения.
2. Зафиксировать итог сравнения:
   - `fusion`;
   - `watch-only`;
   - personalized variants.
3. Свести в единый presentation-ready пакет:
   - comparison tables;
   - графики;
   - narrative summary;
   - ограничения и decision points.
4. Определить production scope:
   - какие модели идут дальше;
   - какие сигналы обязательны;
   - какие функции остаются исследовательскими.

### Артефакты

1. Research report.
2. Production scope decision.
3. Список зафиксированных допущений и ограничений.
4. Presentation-ready comparison package.

### Критерий завершения

Понятно, какие части модели и пайплайна уже достаточно зрелые для продуктового backend.

### Что просить у меня на этом этапе

1. "Собери research report по текущим экспериментам."
2. "Сформулируй production scope на основе результатов исследования."

### Уточнение после первого decision gate

Если после `I1` принято решение, что основной научный вклад работы должен быть не в расширении global modeling, а в personalization methodology, допускается возврат в `H` для отдельного methodological sub-track перед `J`.

В этом режиме:

1. `WESAD`-trained baseline считается достаточной стартовой глобальной моделью.
2. Основной акцент переносится на personalization strategies для:
   - `watch-only`;
   - `fusion`.
3. Следующие research steps должны отвечать на вопросы:
   - какие personalization variants реально улучшают `arousal/valence`;
   - сколько calibration budget нужно;
   - можно ли персонализировать модель без новых ручных labels;
   - как это затем проверять в realtime/replay-контуре.
4. Возврат к расширению global modeling фиксируется как отдельный future track, а не как ближайший приоритет.
5. Обучение более крупной pooled multi-dataset модели имеет смысл только после выполнения обоих условий:
   - появились безопасные harmonized non-label signal features, общие для внешних datasets;
   - для внешних datasets появились нормальные claim-grade labels вместо proxy-mapping как основного источника supervision.
6. До выполнения этих условий внешние datasets используются прежде всего для harmonization, validation, transfer-checks и подготовки будущего pooled training контура.

## 14. Фаза J: Reproducible ML Platform

### Цель

Перевести исследовательскую работу из ad-hoc режима в воспроизводимый ML pipeline.

### Задачи

1. Ввести experiment tracking.
2. Ввести model registry.
3. Версионировать datasets и preprocessing.
4. Автоматизировать:
   - dataset build;
   - training;
   - evaluation;
   - report generation.
5. Настроить хранение артефактов обучения.
6. Настроить повторяемые job-ы.

### Артефакты

1. `model-registry`.
2. Experiment tracker.
3. Автоматизированные training/evaluation jobs.

### Критерий завершения

Любую модель можно обучить заново по версии датасета, конфигу и preprocessing pipeline без ручной магии.

### Что просить у меня на этом этапе

1. "Добавь MLflow или аналог для tracking и model registry."
2. "Автоматизируй training job и evaluation job."
3. "Сделай версионирование datasets и preprocessing."

## 15. Фаза K: Production Backend

### Цель

Построить стабильную backend-систему вокруг уже подтвержденной модели.

### Сервисы

1. `ingest-api`
2. `raw-session-store`
3. `sync-processing-worker`
4. `replay-service`
5. `dataset-registry`
6. `training-orchestrator`
7. `model-registry`
8. `inference-api`
9. `personalization-worker`

### Задачи

1. Формализовать сервисные контракты.
2. Разделить online и offline контуры.
3. Настроить очереди и асинхронную обработку.
4. Ввести auth, audit, observability.
5. Ввести деплой в окружения.
6. Настроить мониторинг качества моделей после выкладки.
7. Зафиксировать semantic output layer для inference:
   - прямые сигналы `activity/context`;
   - прямые сигналы `arousal`;
   - scoped `valence` с `unknown` fallback;
   - производный `derived_state` для продуктовой интерпретации.
8. Явно разделить:
   - что можно показывать пользователю;
   - что остается internal/research-only;
   - где обязательны confidence gates и fallback rules.

### Артефакты

1. Рабочая backend-архитектура.
2. CI/CD.
3. Production-grade observability.
4. Документы по эксплуатации.
5. Контракт semantic outputs и derived-state policy.

### Критерий завершения

Система стабильно принимает записи, обрабатывает их, выдает инференс и поддерживает персонализацию без ручного вмешательства исследовательской команды.

### Что просить у меня на этом этапе

1. "Сделай сервисную архитектуру production backend."
2. "Реализуй inference API и очередь асинхронной обработки."
3. "Добавь model registry и механизм выкладки новой модели."
4. "Зафиксируй contract для activity/arousal/valence/derived_state и правила unknown/fallback."
5. "Опиши, как из activity/arousal/valence собирать product-facing состояние пользователя."

## 16. Рекомендуемый технический стек

Для research и backend я рекомендую начинать так:

1. `Python`
2. `FastAPI`
3. `Postgres`
4. `MinIO` или `S3`
5. `Redis` или брокер очередей
6. `Polars/Pandas`
7. `SciPy`
8. `PyTorch`
9. `MLflow`
10. `Docker Compose` для локальной среды

Причина: это дает быстрый старт в исследовании и не мешает потом разложить систему на сервисы.

## 17. Порядок реализации, который я рекомендую

Вот порядок, в котором лучше просить меня делать работу:

1. Подготовить `research protocol`.
2. Подготовить схему данных сессий и labels.
3. Спроектировать отдельный Swift-репозиторий и capture app.
4. Сделать backend ingest и raw storage.
5. Сделать replay.
6. Сделать preprocessing pipeline.
7. Подключить внешние датасеты.
8. Сделать baseline модели.
9. Сделать персонализацию.
10. Автоматизировать ML pipeline.
11. Перевести систему в production backend.

## 18. Как дробить работу на маленькие инкременты

Чтобы двигаться безопасно и предсказуемо, каждая новая задача должна быть маленькой и проверяемой.

Хорошие примеры запросов:

1. "Сделай документ research protocol."
2. "Добавь schema для session и device streams."
3. "Сделай FastAPI сервис ingest-api."
4. "Подними локально Postgres и MinIO через docker compose."
5. "Сделай worker для синхронизации Polar и Watch."
6. "Добавь импорт датасета WESAD."
7. "Сделай baseline watch-only модель."
8. "Сделай baseline fusion модель."
9. "Добавь light personalization."
10. "Сделай replay service."

## 19. Стоп-критерии

Нельзя переходить дальше, если:

1. нет стабильной схемы данных;
2. raw data не сохраняются без потерь;
3. preprocessing нельзя воспроизвести;
4. evaluation protocol меняется от эксперимента к эксперименту;
5. персонализация сравнивается нечестно;
6. production backend строится до подтверждения исследовательской гипотезы.

## 20. Минимальный реалистичный MVP

Если нужно сузить проект до первого осязаемого результата, то MVP такой:

1. Capture paired sessions с `Polar H10 + Apple Watch`.
2. Raw storage.
3. Replay.
4. Preprocessing.
5. Baseline `fusion` и `watch-only` модели.
6. Предсказание `activity/context` и `arousal/stress`.
7. Базовая персонализация.

`Valence` лучше оставить на следующий шаг после того, как базовый контур покажет стабильный результат.
