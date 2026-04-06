# Журнал работ

Этот журнал ведется в хронологическом порядке и нужен для ответа на вопросы:

1. что уже сделано;
2. когда это было сделано;
3. какие файлы были изменены;
4. какой шаг следующий.

---

## 2026-04-05 - PER-6-20260405 - PER-6: on-go-ios PATCH L2 после self-report

### Запрос

Подтверждение шага `PER-6` («да»): в репозитории `on-go-ios` после калибровочной сессии вызывать `PATCH /v1/profile/{subject_id}/l2-calibration`.

### Что сделано

1. **CaptureDomain**: `L2CalibrationMaps` — якоря из `SelfReportDraft` (как coarse-маппинг в `draft_personalization_profile_from_minio.py`) и сборка `output_label_maps` при расхождении majority-модели и якоря по дорожкам `activity` / `arousal_coarse` / `valence_coarse`.
2. **BackendClient**: голосование по окнам инференса в `LiveInferenceConnection` (`snapshotMajorityPredictions`), `PersonalizationHTTPClient` (`PATCH` L2, `PUT` ensure-profile при 404), `BackendEnv.personalizationBaseURLString()` (`ON_GO_PERSONALIZATION_BASE_URL` или производный `http(s)://host:8110` без Caddy-edge).
3. **SessionViewModel**: перед отключением live WebSocket снимается majority snapshot; после `stopRecording` и upload выполняется push L2 при настроенном URL; `subject_id` берётся из подготовленной сессии (`activeSubjectID`).
4. **Конфиг iOS**: `Info.plist` + `ON_GO_IOS_PERSONALIZATION_BASE_URL` в `Base.xcconfig` и `Secrets.local.xcconfig.example`.

### Измененные файлы (репозиторий `on-go-ios`)

1. `packages/CaptureKit/Sources/CaptureDomain/L2CalibrationMaps.swift`
2. `packages/CaptureKit/Sources/BackendClient/LiveInferenceClient.swift`
3. `packages/CaptureKit/Sources/BackendClient/PersonalizationHTTPClient.swift`
4. `packages/CaptureKit/Sources/BackendClient/BackendEnv+ResolvedURLs.swift`
5. `apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
6. `apps/OnGoCapture/iPhoneApp/Info.plist`
7. `config/xcconfig/Base.xcconfig`
8. `config/Secrets.local.xcconfig.example`

### Результат

Продуктовый путь **PER-6** закрыт: при заданном `ON_GO_PERSONALIZATION_BASE_URL` (или производном URL для локального хоста) приложение после остановки сессии с self-report отправляет L2 PATCH, при отсутствии профиля — ensure-profile и повтор PATCH.

### Следующий рекомендуемый шаг

Проверка на устройстве со стеком `live-inference-api` + `personalization-worker` и явным `ON_GO_IOS_PERSONALIZATION_BASE_URL` за Caddy; затем по плану ops — **`E2.24`** (weekly cycle audit) или доработка UX self-report под реальную калибровку.

---

## 2026-04-05 - PER-5-20260405 - PER-5: batch replay infer → L2 PATCH

### Запрос

Подтверждение шага `PER-5` («да»): доставка L2 после калибровки — batch `replay/predict → worker` и/или клиент iOS.

### Что сделано

1. Скрипт **`scripts/push_l2_from_replay_infer.py`**: HTTP `POST {live}/v1/replay/infer` по `--session-id`, majority-агрегация по непропущенным окнам для `activity`, `arousal_coarse`, `valence_coarse`; чтение якорей из MinIO через логику `draft_personalization_profile_from_minio.py` (`annotations/self-report.json`); сборка `output_label_maps` и `PATCH {personalization}/v1/profile/{subject_id}/l2-calibration` с `active_personalization_level`, `last_calibrated_at_utc`, опционально `global_model_reference` / `global_model_reference_match`.
2. Флаги **`--dry-run`**, **`--ensure-profile`** (минимальный `PUT` при 404), **`--write-replay-json`**, опциональные `--window-ms`, `--step-ms`, `--replay-base-url`, `--stream-names`.
3. Документация: `scripts/README.md`, `services/personalization-worker/README.md`, `services/live-inference-api/README.md`.
4. Реестр: **`PER-5`** → `completed`; следующий шаг **`PER-6`** (on-go-ios, вне monorepo).

### Измененные файлы

1. `scripts/push_l2_from_replay_infer.py`
2. `scripts/README.md`
3. `services/personalization-worker/README.md`
4. `services/live-inference-api/README.md`
5. `docs/status/execution-status.md`
6. `docs/status/work-log.md`

### Результат

Закрыт продуктовый batch-путь PER-5 без ручного JSON предсказаний: одна команда от ingested `session_id` и `subject_id` до обновлённого L2 в worker при наличии self-report якорей и расхождении с majority-моделью по окнам.

### Следующий рекомендуемый шаг

`PER-6 - on-go-ios: PATCH L2 после калибровочной сессии`

---

## 2026-04-05 - PER-4-20260405 - PER-4: источник данных для l2_calibration (PATCH + draft script)

### Запрос

Подтверждение шага `PER-4` («да»): запись `l2_calibration` из калибровочных сессий или фонового сценария; клиентский путь без полного PUT.

### Что сделано

1. **personalization-worker**: модель `L2CalibrationPatchBody`, функция `merge_l2_calibration_patch`, маршрут **`PATCH /v1/profile/{subject_id}/l2-calibration`** (слияние карт по дорожкам, опционально `active_personalization_level` / `global_model_reference` / `last_calibrated_at_utc`).
2. **contracts/http/personalization-worker.openapi.yaml**: операция `patch_profile_l2_calibration`, схема `L2CalibrationPatchBody`.
3. **scripts/draft_personalization_profile_from_minio.py**: флаги `--l2-model-predictions-json`, `--l2-personalization-level`; якоря из session-level self-report (`arousal_score`/`valence_score`/`activity_*`); построение `output_label_maps` как «выход модели → якорь» при расхождении.
4. Документация: `services/personalization-worker/README.md`, `scripts/README.md`; тесты `services/personalization-worker/tests/test_api.py` (`9 passed`).

### Измененные файлы

1. `services/personalization-worker/src/personalization_worker/models.py`
2. `services/personalization-worker/src/personalization_worker/api.py`
3. `services/personalization-worker/tests/test_api.py`
4. `contracts/http/personalization-worker.openapi.yaml`
5. `scripts/draft_personalization_profile_from_minio.py`
6. `services/personalization-worker/README.md`
7. `scripts/README.md`
8. `docs/status/execution-status.md`
9. `docs/status/work-log.md`

### Результат

Шаг **`PER-4`** закрыт: клиент может обновлять L2 точечным PATCH; оператор или job может собрать черновик профиля с L2 из MinIO при наличии JSON предсказаний глобальной модели на ту же сессию, что и self-report.

### Следующий рекомендуемый шаг

`PER-5 - клиентская доставка L2 после калибровки (on-go-ios) и/или batch: replay/predict → JSON → worker`

---

## 2026-04-05 - PER-3-20260405 - PER-3: L2 post-hoc routing в live по adaptation_state

### Запрос

Подтверждение шага `PER-3` («погнали»): L2 hook — калибровка / маршрутизация по `adaptation_state` для live-предсказаний.

### Что сделано

1. **personalization-worker**: модели `L2CalibrationState` и поле `adaptation_state.l2_calibration`; схема `L2CalibrationState` и расширение `AdaptationState` в OpenAPI.
2. **live-inference-api**: `calibration_l2.apply_adaptation_l2` — при `light`/`full` маппинг меток после глобального `predict`, guard `global_model_reference_match`, блок `personalization.l2` в WS при изменении меток; интеграция в `api.py` после L1 и до семантики.
3. Тесты: `tests/test_calibration_l2.py`, `tests/test_api.py` (`test_live_inference_l2_remaps_after_predict`), `personalization-worker/tests/test_api.py` (`test_profile_put_accepts_l2_calibration`).
4. README **live-inference-api** и **personalization-worker**; обновлены `execution-status.md` и журнал.

### Измененные файлы

1. `services/personalization-worker/src/personalization_worker/models.py`
2. `contracts/http/personalization-worker.openapi.yaml`
3. `services/live-inference-api/src/live_inference_api/calibration_l2.py`
4. `services/live-inference-api/src/live_inference_api/api.py`
5. `services/live-inference-api/tests/test_calibration_l2.py`
6. `services/live-inference-api/tests/test_api.py`
7. `services/personalization-worker/tests/test_api.py`
8. `services/live-inference-api/README.md`
9. `services/personalization-worker/README.md`
10. `docs/status/execution-status.md`
11. `docs/status/work-log.md`

### Результат

Шаг **`PER-3`** закрыт: профиль может нести `l2_calibration.output_label_maps`; при уровне персонализации `light` или `full` live-инференс применяет post-hoc маппинг согласованно с опциональной привязкой к `global_model_reference`.

### Следующий рекомендуемый шаг

`PER-4 - запись l2_calibration из калибровочных сессий или фонового job (клиент PUT / worker)`

---

## 2026-04-05 - PER-2-20260405 - PER-2: L1 нормализация признаков в live по профилю

### Запрос

Подтверждение шага `PER-2` («погнали»): применить сохранённый `physiology_baseline` в live-извлечении признаков.

### Что сделано

1. Модуль `services/live-inference-api/src/live_inference_api/baseline_l1.py`: L1 z-score по `l1_feature_mu`/`l1_feature_sigma` или по `resting_hr_bpm` (median, p10/p90 → sigma), опционально `hrv_rmssd_ms`/`hrv_sdnn_ms` для `chest_rr_rmssd`/`chest_rr_sdnn`.
2. `features.py`: публичная `refresh_fusion_proxy_stats` для пересчёта fusion-proxy после нормализации HR.
3. `api.py`: `GET` профиля до извлечения признаков; после `extract_watch_features` и L1 — `refresh_fusion_proxy_stats` при manifest-layout; затем `predict`; в `personalization` добавлен объект `l1` при `applied`.
4. Тесты: `tests/test_baseline_l1.py`, дополнены `tests/test_api.py` (L1 до predict, отсутствие `l1` при пустом baseline).

### Измененные файлы

1. `services/live-inference-api/src/live_inference_api/baseline_l1.py`
2. `services/live-inference-api/src/live_inference_api/features.py`
3. `services/live-inference-api/src/live_inference_api/api.py`
4. `services/live-inference-api/tests/test_baseline_l1.py`
5. `services/live-inference-api/tests/test_api.py`
6. `docs/status/execution-status.md`
7. `docs/status/work-log.md`

### Результат

Шаг **`PER-2`** закрыт: при непустом `physiology_baseline` в профиле и переданном `subject_id` вектор для модели нормализуется до инференса; клиент видит метаданные L1 в ответе.

### Следующий рекомендуемый шаг

`PER-3 - L2 hook: calibration / adaptation_state routing for live predictions (when contract is fixed)`

---

## 2026-04-05 - PER-1-20260405 - PER-1: Postgres-профиль и live snapshot

### Запрос

Подтверждение шага `PER-1` (погнали): персистентность профиля и связка с live-inference.

### Что сделано

1. Миграция `services/ingest-api/migrations/0003_personalization_profiles.sql`: схема `personalization`, таблица `user_profiles` (JSONB baseline/adaptation, timestamps).
2. `personalization-worker`: `PostgresProfileStore` при `PERSONALIZATION_DATABASE_DSN`, иначе in-memory; `/health` отдаёт `store` и `db`; `create_app(..., store=)` для тестов; зависимость `psycopg`.
3. `live-inference-api`: lifespan + `httpx.AsyncClient`, env `LIVE_INFERENCE_PERSONALIZATION_BASE_URL` / `LIVE_INFERENCE_PERSONALIZATION_TIMEOUT_S`; на `stream_batch` опциональный `subject_id`; в `inference` опциональный блок `personalization`; сброс `subject_id` на `session_reset`.
4. `infra/compose/on-go-stack.yml`: DSN у worker, `depends_on` postgres + ingest-api (миграции); у live — URL на worker и `depends_on` personalization-worker.
5. Документация: README сервисов, `ingest-api` список миграций, OpenAPI personalization-worker; тесты (`personalization-worker` 4 passed, `live-inference-api` 47 passed).

### Измененные файлы

1. `services/ingest-api/migrations/0003_personalization_profiles.sql`
2. `services/ingest-api/README.md`
3. `services/personalization-worker/pyproject.toml`
4. `services/personalization-worker/src/personalization_worker/store.py`
5. `services/personalization-worker/src/personalization_worker/config.py`
6. `services/personalization-worker/src/personalization_worker/api.py`
7. `services/personalization-worker/tests/test_api.py`
8. `services/personalization-worker/README.md`
9. `services/live-inference-api/src/live_inference_api/config.py`
10. `services/live-inference-api/src/live_inference_api/api.py`
11. `services/live-inference-api/tests/test_api.py`
12. `services/live-inference-api/README.md`
13. `infra/compose/on-go-stack.yml`
14. `contracts/http/personalization-worker.openapi.yaml`
15. `docs/status/execution-status.md`
16. `docs/status/work-log.md`

### Результат

Шаг **`PER-1`** закрыт: профиль переживает рестарт сервиса; live-пайплайн может подмешивать снимок профиля в каждый inference при переданном `subject_id`.

### Следующий рекомендуемый шаг

`PER-2 - L1 hook: apply persisted physiology_baseline in live feature extraction`

---

## 2026-04-05 - PER-PRIORITY-20260405 - Приоритет: персонализация в продукте

### Запрос

Приступить к персонализации сразу (возможно ли и что делать дальше).

### Что сделано

1. Подтверждено: отложенная приёмка M7 не мешает персонализации; **H1–H6** в реестре уже `completed`, **K4** даёт API профиля, но **live-inference-api** с worker не связан.
2. В `docs/status/execution-status.md`: фаза **Personalization — product path**, шаг **`PER-1`** в статусе `next`, **E2.24** снова `pending`, пункт **140** в списке «Уже сделано».

### Измененные файлы

1. `docs/status/execution-status.md`
2. `docs/status/work-log.md`

### Результат

Следующий формальный шаг реестра: **`PER-1`** — контракт профиля, персистентность, план интеграции с live.

### Следующий рекомендуемый шаг

`PER-1 - Production personalization kickoff: profile persistence + live integration plan`

---

## 2026-04-05 - DEFER-M7-20260405 - Временный пропуск линии приёмки M7.8 / M7.10

### Запрос

Отметить M7.9 / M7.10 как временно пропущенные и вернуться к ним позже.

### Что сделано

1. В `docs/status/execution-status.md` добавлена секция **«Временно пропущенные шаги»** с перечислением `M7.8`, `M7.10`, `M7.10.1`, `M7.10.2`, `M7.10.4` в статусе `pending`.
2. Уточнено, что **`M7.9`**, **`M7.9.1`**, **`M7.10.3`** остаются `completed` (bundle и compose).
3. Статус **`next`** перенесён на **`E2.24`** (first steady-state weekly cycle audit).
4. Обновлены «Текущее состояние», фаза и список «Уже сделано» (п. `139`).

### Измененные файлы

1. `docs/status/execution-status.md`
2. `docs/status/work-log.md`

### Результат

Линия device acceptance для M7.9 runtime зафиксирована как отложенная; реестр имеет один актуальный шаг `next` = `E2.24`.

### Следующий рекомендуемый шаг

`E2.24 - First steady-state weekly cycle audit`

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

---

## 2026-03-22 - C3 - Full package checksum policy hardening

### Запрос

После подтверждения пользователя выполнить шаг `C3`: ужесточить checksum policy для полного raw package на стороне backend ingest.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. В `FinalizeRawSessionRequest` добавлено ограничение `checksum_file_path` на канонический путь `checksums/SHA256SUMS`.
3. В `ingest-api` добавлен strict parsing `SHA256SUMS`:
   - UTF-8 проверка;
   - формат строки `<sha256> <relative_path>`;
   - запрет дубликатов path;
   - запрет невалидных hash/path и `..` сегментов.
4. В `finalize` добавлена full-package checksum policy проверка:
   - `package_checksum_sha256` сверяется с checksum артефактом;
   - `SHA256SUMS` должен покрывать все non-checksum artifacts;
   - `SHA256SUMS` не должен содержать лишние пути;
   - hash в `SHA256SUMS` сверяется с checksum артефакта из ingest manifest.
5. В `finalize` добавлена проверка, что весь пакет artifacts находится в `uploaded/verified` перед переводом в `ingested`.
6. Расширен audit payload (`checksum_policy_errors`) для явной диагностики policy-нарушений.
7. Добавлены unit-тесты на checksum policy в `services/ingest-api/tests/test_checksum_policy.py`.
8. Добавлен backend-документ шага `docs/backend/raw-ingest-c3.md` и обновлены ссылки в `README`.
9. Локальная верификация:
   - `python3 -m compileall -q src tests` — успешно;
   - `python3 -m pytest -q` не выполнен: `No module named pytest` в текущем окружении.

### Измененные файлы

1. `services/ingest-api/src/ingest_api/models.py`
2. `services/ingest-api/src/ingest_api/repository.py`
3. `services/ingest-api/src/ingest_api/service.py`
4. `services/ingest-api/tests/test_checksum_policy.py`
5. `services/ingest-api/README.md`
6. `docs/backend/raw-ingest-c3.md`
7. `README.md`
8. `docs/status/execution-status.md`
9. `docs/status/work-log.md`

### Результат

`C3` завершен: finalize-процесс в `ingest-api` теперь валидирует не только checksum-файл как объект, но и согласованность checksum-манифеста со всем raw package.

### Следующий рекомендуемый шаг

`C4 - Ingest integration/contract tests with fixtures`

---

## 2026-03-22 - C4 - Ingest integration/contract tests with fixtures

### Запрос

После подтверждения пользователя выполнить шаг `C4`: добавить интеграционные и контрактные тесты ingest lifecycle с тестовыми raw package fixtures.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. Добавлен новый набор тестов `services/ingest-api/tests/test_ingest_lifecycle_fixtures.py`.
3. Реализованы in-memory test doubles для `Database`, `IngestRepository` и `S3Storage` с monkeypatch на уровень `FastAPI create_app`.
4. Добавлен fixture generator raw package (`manifest/*`, `streams/*`, `checksums/SHA256SUMS`) с валидными SHA256.
5. Добавлен API-level lifecycle тест с фикстурой: `create -> presign -> complete -> finalize -> get state`.
6. Добавлены контрактные проверки against `contracts/http/raw-session-ingest.openapi.yaml`:
   - сверка `operationId`;
   - фиксация обязательных ingest lifecycle routes.
7. Добавлены негативные сценарии:
   - idempotency conflict при `complete` с одинаковым `Idempotency-Key` и другим payload;
   - failed finalize при `package_checksum_sha256` mismatch.
8. Обновлены docs для C4 (`docs/backend/raw-ingest-c4.md`, README ссылки, tests README).
9. Выполнена локальная проверка:
   - `python3 -m compileall -q src tests` — успешно;
   - `python3 -m pytest -q tests/test_ingest_lifecycle_fixtures.py` — не выполнен из-за отсутствия `pytest` в текущем окружении (`No module named pytest`).

### Измененные файлы

1. `services/ingest-api/tests/test_ingest_lifecycle_fixtures.py`
2. `services/ingest-api/tests/README.md`
3. `services/ingest-api/README.md`
4. `docs/backend/raw-ingest-c4.md`
5. `README.md`
6. `docs/status/execution-status.md`
7. `docs/status/work-log.md`

### Результат

`C4` завершен: ingest lifecycle теперь покрыт API-level integration/contract тестами на fixture-пакетах, включая проверки устойчивости idempotency и checksum policy.

### Следующий рекомендуемый шаг

`D2 - Replay integration tests на полном локальном стеке`

---

## 2026-03-22 - D2 - Replay integration tests на полном локальном стеке

### Запрос

После подтверждения пользователя выполнить шаг `D2`: добавить интеграционные replay-тесты на полном локальном стеке `Postgres + MinIO + ingest-api + replay-service`.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. Добавлен full-stack e2e runner `services/replay-service/tests/stack_e2e.py`.
3. В e2e сценарий включены этапы:
   - health-check `ingest-api` и `replay-service`;
   - ingest lifecycle (`create -> presign upload -> complete -> finalize`) на fixture raw session;
   - replay проверки (`manifest` и `windows`) для уже ingested session.
4. Добавлена pytest-обертка интеграционного сценария `services/replay-service/tests/test_integration_stack.py`.
5. Обновлены replay test docs и service README (`services/replay-service/tests/README.md`, `services/replay-service/README.md`).
6. Добавлен backend-документ шага `docs/backend/replay-d2.md` и обновлены ссылки в корневом `README.md`.
7. Выполнена верификация в текущем окружении:
   - `python3 -m compileall -q services/replay-service/tests/stack_e2e.py services/replay-service/tests/test_integration_stack.py` — успешно;
   - `docker compose -f infra/compose/on-go-stack.yml up -d --build` — стек поднят;
   - `python3 services/replay-service/tests/stack_e2e.py` — успешно (`[stack-e2e] OK`).

### Измененные файлы

1. `services/replay-service/tests/stack_e2e.py`
2. `services/replay-service/tests/test_integration_stack.py`
3. `services/replay-service/tests/README.md`
4. `services/replay-service/README.md`
5. `docs/backend/replay-d2.md`
6. `README.md`
7. `docs/status/execution-status.md`
8. `docs/status/work-log.md`

### Результат

`D2` завершен: replay-контур подтвержден интеграционным end-to-end сценарием на полном docker-стеке, включая сквозной путь ingest fixture package -> replay manifest/windows.

### Следующий рекомендуемый шаг

`D3 - Streaming replay transport и orchestration modes`

---

## 2026-03-22 - D3 - Streaming replay transport и orchestration modes

### Запрос

После подтверждения пользователя выполнить шаг `D3`: добавить потоковый replay transport, orchestration modes и run registry.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. Добавлен `ReplayRunRegistry` (`services/replay-service/src/replay_service/run_registry.py`) для управления replay run-состояниями.
3. Добавлены новые модели replay run в `models.py`:
   - `ReplayRunRequest`, `ReplayRunState`, `ReplayRunListResponse`;
   - типы `ReplayRunOrchestrationMode` и `ReplayRunStatus`.
4. В `ReplayService` добавлен orchestration helper `iterate_windows(...)` с режимами:
   - `single_window`;
   - `full_session`.
5. В `api.py` добавлены новые endpoint-ы:
   - `POST /v1/replay/sessions/{session_id}/runs`;
   - `GET /v1/replay/runs`;
   - `GET /v1/replay/runs/{run_id}`;
   - `GET /v1/replay/runs/{run_id}/events` (`text/event-stream`).
6. Реализован SSE transport: события `replay_window`, `run_completed`, `run_failed`.
7. Обновлен контракт `contracts/http/raw-session-replay.openapi.yaml` под run/streaming API.
8. Добавлены тесты и e2e-проверки D3:
   - `test_run_registry.py`;
   - `test_orchestration.py`;
   - `stack_stream_e2e.py`;
   - `test_streaming_stack.py`.
9. Обновлены docs/reports для D3 (`services/replay-service/README.md`, `services/replay-service/tests/README.md`, `docs/backend/replay-d3.md`, корневой `README.md`).
10. Выполнена верификация:
   - `python3 -m compileall -q services/replay-service/src services/replay-service/tests` — успешно;
   - `docker compose -f infra/compose/on-go-stack.yml up -d --build` — успешно;
   - `python3 services/replay-service/tests/stack_stream_e2e.py` — успешно (`[stack-stream-e2e] OK`).

### Измененные файлы

1. `services/replay-service/src/replay_service/api.py`
2. `services/replay-service/src/replay_service/service.py`
3. `services/replay-service/src/replay_service/models.py`
4. `services/replay-service/src/replay_service/run_registry.py`
5. `contracts/http/raw-session-replay.openapi.yaml`
6. `services/replay-service/tests/test_run_registry.py`
7. `services/replay-service/tests/test_orchestration.py`
8. `services/replay-service/tests/stack_stream_e2e.py`
9. `services/replay-service/tests/test_streaming_stack.py`
10. `services/replay-service/README.md`
11. `services/replay-service/tests/README.md`
12. `docs/backend/replay-d3.md`
13. `README.md`
14. `docs/status/execution-status.md`
15. `docs/status/work-log.md`

### Результат

`D3` завершен: replay-контур получил run registry и потоковый SSE transport для orchestrated replay run-сценариев (`single_window/full_session`).

### Следующий рекомендуемый шаг

`E2 - Feature extraction и clean/features layers`

---

## 2026-03-22 - E2 - Feature extraction и clean/features layers

### Запрос

После сверки статуса и подтверждения пользователя выполнить шаг `E2`: добавить extraction признаков поверх clean-слоя и сохранить features-layer артефакты для downstream modeling.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. В `signal-processing-worker` расширены модели processing-результата:
   - добавлены `FeatureWindow` и `StreamFeatureSummary`;
   - `ProcessedStream` дополнен `feature_windows`, `feature_summary`, `features_object_key`.
3. В preprocessing-flow добавлен этап window-based feature extraction поверх `clean_samples` для каждого stream.
4. Реализованы baseline-признаки по окнам:
   - общие: `sample_count`, `window_duration_ms`, `motion_artifact_ratio`;
   - numeric-агрегации: `mean/std/min/max/last`;
   - motion-вектора: magnitude statistics для `accelerometer/gyroscope`;
   - cardio: `rr_like__rmssd` для `rr/hrv`-подобных рядов;
   - context: категориальный `mode` для non-numeric ключей (например, `activity_label__mode`).
5. Добавлено сохранение feature artifacts в object storage:
   - `clean-sessions/<session_id>/<version>/features/<stream_name>/windows.features.csv.gz`.
6. Обновлена документация `signal-processing-worker` и добавлен backend-документ шага `E2`.
7. Добавлены/расширены unit-тесты для feature-layer и моделей `E2`.
8. Выполнена локальная верификация:
   - `python3 -m compileall -q src tests` — успешно;
   - `python3 -m pytest -q` — не выполнен из-за отсутствия `pytest` в текущем окружении (`No module named pytest`).

### Измененные файлы

1. `services/signal-processing-worker/src/signal_processing_worker/models.py`
2. `services/signal-processing-worker/src/signal_processing_worker/service.py`
3. `services/signal-processing-worker/src/signal_processing_worker/main.py`
4. `services/signal-processing-worker/tests/test_models.py`
5. `services/signal-processing-worker/tests/test_service.py`
6. `services/signal-processing-worker/tests/README.md`
7. `services/signal-processing-worker/README.md`
8. `docs/backend/signal-processing-e2.md`
9. `README.md`
10. `docs/status/execution-status.md`
11. `docs/status/work-log.md`

### Результат

`E2` завершен: preprocessing-контур теперь формирует и сохраняет feature-layer поверх clean-сигналов в стандартизованном оконном формате, пригодном для следующих шагов modeling (`G1/G2`).

### Следующий рекомендуемый шаг

`F1 - Обзор и приоритет внешних датасетов`

---

## 2026-03-22 - F1 - Обзор и приоритет внешних датасетов

### Запрос

После сверки статуса и подтверждения пользователя выполнить шаг `F1`: подготовить обзор и приоритизацию внешних датасетов для следующего шага `F2`.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. Сверены текущие `research`-артефакты (`evaluation-plan`, `label-specification`, `session-data-schema`) для привязки приоритизации к обязательным target tracks (`activity/context`, `arousal`).
3. Добавлен отдельный документ шага `F1`:
   - `docs/datasets/external-datasets-f1-prioritization.md`.
4. В документе зафиксированы:
   - shortlist кандидатов (`WESAD`, `EmoWear`, `DAPPER`, `G-REx`);
   - критерии ranking (`target_fit`, `sensor_fit`, `label_quality`, `ingestion_effort`, `license_risk`);
   - приоритизационная матрица и порядок импорта для `F2`.
5. Зафиксирован рекомендуемый execution order:
   - `P1: WESAD`;
   - `P2: EmoWear`;
   - `P3: DAPPER`;
   - `P4: G-REx`.
6. Добавлены правила нормализации внешних датасетов в unified internal schema и зафиксированы ограничения/допущения шага `F1`.
7. Обновлены индексные ссылки в `README.md`.
8. Обновлен `execution-status`: `F1 -> completed`, `F2 -> next`.

### Измененные файлы

1. `docs/datasets/external-datasets-f1-prioritization.md`
2. `README.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`

### Результат

`F1` завершен: зафиксирован приоритет и порядок подключения внешних датасетов, достаточный для начала шага `F2` (dataset registry + первый импорт `WESAD`).

### Следующий рекомендуемый шаг

`F2 - Dataset registry и импорт первого датасета`

---

## 2026-03-22 - F2 - Dataset registry и импорт первого датасета

### Запрос

После сверки статуса и подтверждения пользователя выполнить шаг `F2`: реализовать `dataset registry` и сделать первый импорт внешнего датасета (`WESAD`) в unified internal schema.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. Добавлен новый сервис `services/dataset-registry` с минимальным production-подобным каркасом (`src/tests/deploy/migrations`).
3. Реализованы pydantic-модели registry и unified artifacts:
   - `DatasetRecord`;
   - `UnifiedSubject`;
   - `UnifiedSession`;
   - `UnifiedSegmentLabel`;
   - `SplitManifest`.
4. Реализован JSONL-backed `DatasetRegistry` (`upsert/list`) с ключом версии `(dataset_id, dataset_version)`.
5. Реализован CLI `dataset-registry`:
   - `register`;
   - `list`;
   - `import-wesad`.
6. Реализован `WESAD` ingestion adapter:
   - discovery subject-папок `S*`;
   - чтение labels из CSV (`label.csv/labels.csv/S*_labels.csv`) или pickle (`S*.pkl/data.pkl`);
   - mapping dominant `wesad_state` в canonical `activity/arousal/valence` labels;
   - генерация subject-wise split manifest;
   - запись unified artifacts (`subjects/sessions/segment-labels`) и `dataset-metadata.json`.
7. Добавлена документация шага `F2`:
   - backend note `docs/backend/datasets-f2.md`;
   - формат registry `docs/datasets/dataset-registry-format.md`;
   - обновлены root/service индексы документации.
8. Добавлены unit-тесты `dataset-registry`:
   - `test_registry.py`;
   - `test_wesad.py`.
9. Выполнена локальная верификация:
   - `cd services/dataset-registry && python3 -m compileall -q src tests` — успешно;
   - smoke-run `PYTHONPATH=src python3 -m dataset_registry.main import-wesad ...` на синтетическом mini-WESAD наборе — успешно (созданы unified artifacts и registry entry).
   - `pytest` не запускался в этой среде, так как глобально отсутствует модуль `pytest`.

### Измененные файлы

1. `services/dataset-registry/pyproject.toml`
2. `services/dataset-registry/README.md`
3. `services/dataset-registry/src/README.md`
4. `services/dataset-registry/src/dataset_registry/__init__.py`
5. `services/dataset-registry/src/dataset_registry/main.py`
6. `services/dataset-registry/src/dataset_registry/models.py`
7. `services/dataset-registry/src/dataset_registry/registry.py`
8. `services/dataset-registry/src/dataset_registry/wesad.py`
9. `services/dataset-registry/tests/README.md`
10. `services/dataset-registry/tests/test_registry.py`
11. `services/dataset-registry/tests/test_wesad.py`
12. `services/dataset-registry/migrations/README.md`
13. `services/dataset-registry/deploy/README.md`
14. `services/dataset-registry/registry/.gitkeep`
15. `services/README.md`
16. `docs/datasets/dataset-registry-format.md`
17. `docs/backend/datasets-f2.md`
18. `README.md`
19. `docs/status/execution-status.md`
20. `docs/status/work-log.md`

### Результат

`F2` завершен: в репозитории появился рабочий `dataset-registry` контур с первым импортом `WESAD` в unified internal schema и версионируемым registry metadata format.

### Следующий рекомендуемый шаг

`G1 - Baseline watch-only model`

---

## 2026-03-22 - G3 - Сравнительный evaluation report

### Запрос

После подтверждения пользователя выполнить следующий шаг `G3`: собрать единый comparative report по результатам `G1+G2`, зафиксировать claims и подготовить presentation-ready пакет.

### Что сделано

1. Повторно сверены roadmap, execution status, work log и `model-reporting-standard` перед стартом.
2. В `services/modeling-baselines` добавлен новый CLI-режим `--run-kind g3-wesad`.
3. Реализован G3 runner, который агрегирует готовые artifacts:
   - `G1`: `watch-only-baseline/evaluation-report.json`;
   - `G2`: `fusion-baseline/evaluation-report.json` и `fusion-baseline/per-subject-metrics.csv`.
4. Собран единый comparison bundle:
   - `comparison/evaluation-report.json`;
   - `comparison/model-comparison.csv`;
   - `comparison/per-subject-metrics.csv`;
   - `comparison/comparison-report.md`;
   - `comparison/research-report.md`;
   - `comparison/plots/*`.
5. В comparison таблицу сведены минимум `5` runs:
   - `g1_watch_only_centroid`;
   - `watch_only_centroid`;
   - `chest_only_centroid`;
   - `fusion_centroid`;
   - `fusion_gaussian_nb`.
6. Для каждого track сохранены:
   - `delta_vs_watch_only`;
   - `delta_vs_watch_only_ci95`;
   - `claim_status`.
7. Добавлены G3-графики:
   - macro F1 bars по track;
   - delta-vs-watch bars;
   - per-subject boxplots.
8. Выполнена локальная верификация:
   - `cd services/modeling-baselines && python3 -m compileall -q src tests` — успешно;
   - `cd services/modeling-baselines && source .venv/bin/activate && pytest -q` — `5 passed`.
9. Выполнен реальный G3 run:
   - `experiment_id = g3-comparison-wesad-20260322T183444Z`;
   - source runs: `g1-watch-only-wesad-20260322T180954Z`, `g2-fusion-wesad-20260322T182732Z`;
   - `run_count = 5`.
10. Зафиксированы consolidated результаты:
    - `activity`: лучший вариант `fusion_gaussian_nb`, `macro_f1 = 0.885714`, статус `inconclusive_positive`;
    - `arousal_coarse`: лучший вариант `fusion_gaussian_nb`, `macro_f1 = 0.932773`, статус `supported`.
11. Добавлен backend-документ `docs/backend/modeling-g3.md` и обновлены индексные `README`.
12. Обновлен `execution-status`: `G3 -> completed`, `H1 -> next`.

### Измененные файлы

1. `services/modeling-baselines/src/modeling_baselines/main.py`
2. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
3. `services/modeling-baselines/README.md`
4. `docs/backend/modeling-g3.md`
5. `README.md`
6. `services/README.md`
7. `docs/status/execution-status.md`
8. `docs/status/work-log.md`
9. `data/external/wesad/artifacts/wesad/wesad-v1/comparison/evaluation-report.json`
10. `data/external/wesad/artifacts/wesad/wesad-v1/comparison/model-comparison.csv`
11. `data/external/wesad/artifacts/wesad/wesad-v1/comparison/per-subject-metrics.csv`
12. `data/external/wesad/artifacts/wesad/wesad-v1/comparison/comparison-report.md`
13. `data/external/wesad/artifacts/wesad/wesad-v1/comparison/research-report.md`
14. `data/external/wesad/artifacts/wesad/wesad-v1/comparison/plots/g3-activity-macro-f1.png`
15. `data/external/wesad/artifacts/wesad/wesad-v1/comparison/plots/g3-arousal-macro-f1.png`
16. `data/external/wesad/artifacts/wesad/wesad-v1/comparison/plots/g3-activity-delta-vs-watch.png`
17. `data/external/wesad/artifacts/wesad/wesad-v1/comparison/plots/g3-arousal-delta-vs-watch.png`
18. `data/external/wesad/artifacts/wesad/wesad-v1/comparison/plots/g3-subject-activity-macro-f1.png`
19. `data/external/wesad/artifacts/wesad/wesad-v1/comparison/plots/g3-subject-arousal-macro-f1.png`

### Результат

`G3` завершен: есть единый comparative пакет по `G1+G2` с consolidated claims, machine-readable артефактами и графиками, пригодными для исследования и презентации.

### Следующий рекомендуемый шаг

`H1 - Схема профиля пользователя`

---

## 2026-03-22 - A3.1 - Standard research reporting and model comparison policy

### Запрос

Добавить в план и зафиксировать как обязательное правило, что все шаги по разработке и сравнению ИИ-моделей должны сопровождаться подробными отчетами, описанием labels/данных/preprocessing, большим числом сравнений моделей, метрик и подробными графиками, пригодными для последующей презентации.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. В протокол совместной работы добавлено обязательное правило:
   - для шагов `modeling`, `personalization`, `evaluation`, `research report` и сравнения моделей агент обязан читать `docs/research/model-reporting-standard.md`;
   - такие шаги не считаются завершенными без обязательных отчетных артефактов.
3. Создан отдельный документ `docs/research/model-reporting-standard.md`.
4. В новом стандарте зафиксированы обязательные требования:
   - detailed experiment report;
   - явное описание labels, datasets, preprocessing, features, splits и leakage guards;
   - machine-readable artifacts;
   - presentation-ready plots;
   - multi-model comparison policy;
   - minimum expected number of candidate model variants;
   - обязательный failure analysis и decision-oriented summary.
5. Обновлен `docs/research/evaluation-plan.md`, чтобы он прямо ссылался на новый обязательный стандарт для всех modeling/personalization шагов.
6. Обновлен roadmap:
   - в фазе `G` зафиксированы подробные research reports, графики, multi-model comparisons и presentation-ready comparison artifacts;
   - в фазах `H` и `I` добавлены обязательные subject-level personalization reports и единый presentation-ready research package.
7. Обновлен `README.md` ссылкой на новый research standard.
8. Обновлен `execution-status`: шаг `A3.1` зарегистрирован как `completed`, а следующим шагом сохранен `G2`.

### Измененные файлы

1. `docs/process/collaboration-protocol.md`
2. `docs/research/model-reporting-standard.md`
3. `docs/research/evaluation-plan.md`
4. `docs/roadmap/research-pipeline-backend-plan.md`
5. `README.md`
6. `docs/status/execution-status.md`
7. `docs/status/work-log.md`

### Результат

Требование пользователя зафиксировано как обязательная часть процесса: все будущие modeling-, personalization- и research-report шаги теперь по умолчанию должны оставлять подробные отчеты, сравнение нескольких моделей, machine-readable артефакты и графики, пригодные для презентации.

### Следующий рекомендуемый шаг

`G2 - Baseline fusion model`

---

## 2026-03-22 - G2 - Baseline fusion model

### Запрос

После сверки статуса и подтверждения пользователя выполнить следующий шаг `G2`: собрать `fusion` baseline pipeline на том же split/eval protocol и с обязательным research-grade reporting standard.

### Что сделано

1. Повторно сверены roadmap, execution status, work log и `docs/research/model-reporting-standard.md` перед началом шага.
2. `services/modeling-baselines` расширен от `G1` к общему multimodal baseline pipeline для `WESAD`.
3. Добавлен multimodal feature extraction по unified segment boundaries:
   - wrist: `ACC/BVP/EDA/TEMP`;
   - chest: `ACC/ECG/EDA/EMG/Resp/Temp`;
   - summary stats per channel: `mean/std/min/max/last`;
   - accelerometer magnitude для wrist/chest.
4. Добавлены четыре осмысленных variants для сравнения:
   - `watch_only_centroid`;
   - `chest_only_centroid`;
   - `fusion_centroid`;
   - `fusion_gaussian_nb`.
5. Добавлен альтернативный model family `GaussianNB`, чтобы `G2` не ограничивался одним centroid-style baseline.
6. Реализованы новые research-grade artifacts:
   - `evaluation-report.json`;
   - `predictions-test.csv`;
   - `per-subject-metrics.csv`;
   - `model-comparison.csv`;
   - `research-report.md`;
   - `plots/`.
7. В comparison layer добавлены:
   - pairwise `delta_vs_watch_only`;
   - bootstrap `95% CI` для дельты;
   - `claim_status` для track-level интерпретации.
8. Добавлены unit-тесты для нового pipeline helper и `GaussianNB` classifier.
9. Выполнена локальная верификация:
   - `cd services/modeling-baselines && python3 -m compileall -q src tests` — успешно;
   - `cd services/modeling-baselines && source .venv/bin/activate && pip install -e .` — успешно;
   - `cd services/modeling-baselines && source .venv/bin/activate && pytest -q` — `5 passed`.
10. Выполнен реальный `G2` run на полном `WESAD`:
    - `experiment_id = g2-fusion-wesad-20260322T182732Z`;
    - usable segments (`confidence >= 0.7`) = `75`;
    - сформированы все обязательные artifacts и графики.
11. Зафиксированы реальные результаты:
    - `activity macro_f1`:
      - `watch_only_centroid = 0.719048`
      - `chest_only_centroid = 0.722222`
      - `fusion_centroid = 0.637037`
      - `fusion_gaussian_nb = 0.885714`
    - `arousal_coarse macro_f1`:
      - `watch_only_centroid = 0.655556`
      - `chest_only_centroid = 0.497280`
      - `fusion_centroid = 0.587179`
      - `fusion_gaussian_nb = 0.932773`
    - `fusion_gaussian_nb` дал лучший результат на обоих mandatory tracks;
    - для `activity` его pairwise delta CI против `watch_only` = `[0.0, 0.511111]`, поэтому статус `inconclusive_positive`;
    - для `arousal_coarse` pairwise delta CI = `[0.177778, 0.572222]`, поэтому статус `supported`.
12. Добавлена документация шага `docs/backend/modeling-g2.md` и обновлены индексные `README`.
13. Обновлен статус выполнения: `G2` закрыт, следующим шагом выставлен `G3`.

### Измененные файлы

1. `services/modeling-baselines/pyproject.toml`
2. `services/modeling-baselines/README.md`
3. `services/modeling-baselines/src/README.md`
4. `services/modeling-baselines/src/modeling_baselines/main.py`
5. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
6. `services/modeling-baselines/tests/README.md`
7. `services/modeling-baselines/tests/test_pipeline.py`
8. `docs/backend/modeling-g2.md`
9. `services/README.md`
10. `README.md`
11. `docs/status/execution-status.md`
12. `docs/status/work-log.md`
13. `data/external/wesad/artifacts/wesad/wesad-v1/fusion-baseline/evaluation-report.json`
14. `data/external/wesad/artifacts/wesad/wesad-v1/fusion-baseline/predictions-test.csv`
15. `data/external/wesad/artifacts/wesad/wesad-v1/fusion-baseline/per-subject-metrics.csv`
16. `data/external/wesad/artifacts/wesad/wesad-v1/fusion-baseline/model-comparison.csv`
17. `data/external/wesad/artifacts/wesad/wesad-v1/fusion-baseline/research-report.md`
18. `data/external/wesad/artifacts/wesad/wesad-v1/fusion-baseline/plots/activity-macro-f1.png`
19. `data/external/wesad/artifacts/wesad/wesad-v1/fusion-baseline/plots/arousal-macro-f1.png`
20. `data/external/wesad/artifacts/wesad/wesad-v1/fusion-baseline/plots/activity-confusion-matrix.png`
21. `data/external/wesad/artifacts/wesad/wesad-v1/fusion-baseline/plots/arousal-confusion-matrix.png`
22. `data/external/wesad/artifacts/wesad/wesad-v1/fusion-baseline/plots/subject-activity-macro-f1.png`
23. `data/external/wesad/artifacts/wesad/wesad-v1/fusion-baseline/plots/subject-arousal-macro-f1.png`

### Результат

`G2` завершен: в репозитории появился воспроизводимый multimodal baseline comparison package на `WESAD`, который уже содержит несколько model families/ablations, pairwise delta CI, подробный textual report и presentation-ready графики.

### Следующий рекомендуемый шаг

`G3 - Сравнительный evaluation report`

---

## 2026-03-22 - G1 - Baseline watch-only model

### Запрос

После сверки статуса и подтверждения пользователя выполнить следующий шаг `G1`: собрать первый воспроизводимый `watch-only baseline` pipeline и зафиксировать артефакты обучения/оценки.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. Добавлен новый сервисный модуль `services/modeling-baselines` с CLI `on-go-modeling-baselines`.
3. Реализован baseline pipeline для `WESAD`:
   - чтение `unified/segment-labels.jsonl` и `split-manifest.json`;
   - фильтрация по `confidence >= 0.7` (headline-gate из evaluation plan);
   - построение watch-only признаков из wrist streams (`ACC/BVP/EDA/TEMP`) по `source_segment_start_index/end_index`;
   - subject-wise обучение `nearest centroid` модели.
4. Добавлены evaluation-блоки:
   - `activity_label` classification;
   - `arousal_coarse` classification (`low/medium/high`);
   - `arousal` ordinal metrics (`mae`, `spearman_rho`, `quadratic_weighted_kappa`);
   - trivial baselines (`majority_class`, `global_median_predictor`);
   - bootstrap `95% CI` по субъектам для primary metric и дельты против baseline.
5. Добавлен backend-документ шага `G1` и ссылки в индексные `README`.
6. Выполнена локальная верификация:
   - `cd services/modeling-baselines && python3 -m compileall -q src tests` — успешно;
   - `cd services/modeling-baselines && source .venv/bin/activate && pytest -q` — `2 passed`;
   - реальный run CLI на полном `WESAD` — успешно.
7. Получены реальные артефакты и метрики:
   - `evaluation-report.json` и `predictions-test.csv`;
   - test `macro_f1`:
     - `activity = 0.719048` (vs majority `0.190476`);
     - `arousal_coarse = 0.655556` (vs majority `0.25`);
   - test ordinal arousal: `mae = 1.333333`, `spearman_rho = 0.393713`, `quadratic_weighted_kappa = 0.380952`.
8. Обновлен статус выполнения: `G1` закрыт, `G2` выставлен следующим шагом.

### Измененные файлы

1. `services/modeling-baselines/pyproject.toml`
2. `services/modeling-baselines/README.md`
3. `services/modeling-baselines/src/README.md`
4. `services/modeling-baselines/src/modeling_baselines/__init__.py`
5. `services/modeling-baselines/src/modeling_baselines/main.py`
6. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
7. `services/modeling-baselines/src/modeling_baselines/metrics.py`
8. `services/modeling-baselines/tests/README.md`
9. `services/modeling-baselines/tests/test_metrics.py`
10. `docs/backend/modeling-g1.md`
11. `services/README.md`
12. `README.md`
13. `docs/status/execution-status.md`
14. `docs/status/work-log.md`
15. `data/external/wesad/artifacts/wesad/wesad-v1/watch-only-baseline/evaluation-report.json`
16. `data/external/wesad/artifacts/wesad/wesad-v1/watch-only-baseline/predictions-test.csv`

### Результат

`G1` завершен: в репозитории появился рабочий `watch-only baseline` training/evaluation pipeline с реальным прогоном на `WESAD`, зафиксированными метриками, uncertainty-оценкой и артефактами отчета/предсказаний.

### Следующий рекомендуемый шаг

`G2 - Baseline fusion model`

---

## 2026-03-22 - F2.1 - Onboarding runbook и source validation для внешних датасетов

### Запрос

После подтверждения пользователя подготовить для каждого приоритетного датасета (`WESAD`, `EmoWear`, `G-REx`, `DAPPER`) практическую инструкцию: где скачать, куда положить локально, и обязательно прогнать/протестировать проверку.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. Через внешние источники уточнены reference links для скачивания/доступа:
   - `WESAD`: official page + direct sciebo link;
   - `EmoWear`: Zenodo DOI + descriptor paper + related GitLab repo;
   - `G-REx`: Zenodo record + EULA form + descriptor paper;
   - `DAPPER`: Synapse DOI + descriptor paper + supplementary DOI из paper metadata.
3. Добавлен единый onboarding runbook:
   - `docs/datasets/external-datasets-onboarding-runbook.md`.
4. Зафиксирована единая локальная раскладка внешних датасетов:
   - `data/external/<dataset>/raw`;
   - `data/external/<dataset>/artifacts`.
5. Добавлен `data/external/README.md` с правилами размещения external data.
6. В `dataset-registry` добавлен `dataset catalog` и `source validation`:
   - новый модуль `catalog.py`;
   - новая CLI-команда `dataset-catalog`;
   - новая CLI-команда `validate-source --dataset-id {wesad,emowear,grex,dapper}`.
7. Добавлены source-validation rules для всех 4 датасетов и unit-тесты каталога/валидации.
8. Выполнен обязательный прогон проверки:
   - `python3 -m compileall -q src tests` — успешно;
   - smoke-run `dataset-catalog` — успешно;
   - smoke-run `validate-source` выполнен по всем 4 dataset-id на синтетических layout — успешно (статус `passed` для каждого).
9. Обновлены индексные документы (`README`, backend dataset docs).

### Измененные файлы

1. `docs/datasets/external-datasets-onboarding-runbook.md`
2. `docs/datasets/dataset-registry-format.md`
3. `docs/backend/datasets-f2-1.md`
4. `data/external/README.md`
5. `services/dataset-registry/src/dataset_registry/catalog.py`
6. `services/dataset-registry/src/dataset_registry/main.py`
7. `services/dataset-registry/src/dataset_registry/__init__.py`
8. `services/dataset-registry/src/README.md`
9. `services/dataset-registry/README.md`
10. `services/dataset-registry/tests/test_catalog.py`
11. `services/dataset-registry/tests/README.md`
12. `README.md`
13. `docs/status/execution-status.md`
14. `docs/status/work-log.md`

### Результат

`F2.1` завершен: для всех приоритетных внешних датасетов зафиксированы источники скачивания, локальная раскладка и обязательная команда валидации структуры; проверочный smoke-run выполнен для каждого dataset-id.

### Следующий рекомендуемый шаг

`G1 - Baseline watch-only model`

---

## 2026-03-22 - F2.2 - Реальная валидация скачанных external datasets (`WESAD`, `EmoWear`, `DAPPER`)

### Запрос

Проверить на реально скачанных датасетах без `G-REx`, что данные подготовлены корректно: структура соответствует ожиданию, файлы парсятся, headers/labels совпадают с ожидаемой схемой, а импорт `WESAD` реально проходит на полном наборе.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. Проверены локально скачанные source-папки:
   - `data/external/wesad/raw`;
   - `data/external/emowear/raw`;
   - `data/external/dapper/raw`.
3. В `dataset-registry` добавлена команда `inspect-source` для deep inspection реальных датасетов:
   - `WESAD`: subject layout, `quest.csv`, `E4` directories, `S*.pkl`, label values и shape checks;
   - `EmoWear`: `meta.csv`, `questionnaire.csv`, `mqtt.db`, parseability `e4.zip/bh3.zip`;
   - `DAPPER`: session groups, observed CSV headers, first-row parseability, zero-byte files.
4. Уточнены inspection/validation rules под реальные release layouts:
   - `WESAD` принимает `# Subj;...` и `# Subj:;...` в `quest.csv`;
   - `EmoWear` валидируется по `questionnaire.csv` и participant dirs `<code>-<id>`;
   - `DAPPER` проверяется по реальным `*.csv`, `*_ACC.csv`, `*_GSR.csv`, `*_PPG.csv`.
5. Во время реального прогона найден и исправлен дефект `WESAD` importer:
   - добавлена загрузка python2-compatible pickle через `encoding=\"latin1\"`;
   - importer перестал схлопывать весь subject до одного dominant label;
   - теперь сохраняются contiguous non-zero segments с provenance-полями `source_segment_start_index/source_segment_end_index/source_sample_count`.
6. Для `DAPPER` zero-byte sensor files вынесены в отдельный warning, чтобы не маскироваться под `header_mismatch`.
7. Добавлены/расширены unit-тесты на:
   - colon-вариант `WESAD` quest header;
   - zero-byte `DAPPER` sensor file;
   - `WESAD` pickle import с сохранением contiguous segments.
8. Выполнена локальная верификация:
   - `cd services/dataset-registry && python3 -m compileall -q src tests` — успешно;
   - `inspect-source` на полном `WESAD` — `passed`;
   - `inspect-source` на полном `EmoWear` — `passed`;
   - `inspect-source` на полном `DAPPER` — `warning`;
   - реальный `import-wesad` на полном `WESAD` — `completed`, `subject_count=15`, `session_count=15`, `segment_label_count=119`.

### Измененные файлы

1. `services/dataset-registry/src/dataset_registry/models.py`
2. `services/dataset-registry/src/dataset_registry/wesad.py`
3. `services/dataset-registry/src/dataset_registry/catalog.py`
4. `services/dataset-registry/src/dataset_registry/main.py`
5. `services/dataset-registry/src/dataset_registry/__init__.py`
6. `services/dataset-registry/tests/test_wesad.py`
7. `services/dataset-registry/tests/test_inspect_source.py`
8. `services/dataset-registry/tests/README.md`
9. `services/dataset-registry/src/README.md`
10. `services/dataset-registry/README.md`
11. `docs/datasets/dataset-registry-format.md`
12. `docs/datasets/external-datasets-onboarding-runbook.md`
13. `docs/backend/datasets-f2.md`
14. `docs/backend/datasets-f2-2.md`
15. `README.md`
16. `docs/status/execution-status.md`
17. `docs/status/work-log.md`

### Результат

`F2.2` завершен: `WESAD` и `EmoWear` подтверждены на реальных данных без blocking schema issues; `WESAD` importer исправлен и теперь строит `119` реальных segment labels на полном наборе; `DAPPER` признан пригодным с warning-статусом из-за неполных session groups и двух zero-byte sensor files в source release.

### Следующий рекомендуемый шаг

`G1 - Baseline watch-only model`

---

## 2026-03-22 - F2.3 - Реальная валидация скачанного `G-REx`

### Запрос

После скачивания `G-REx` проверить и его тоже на реальных локальных данных: структура release, headers, transformed artifacts и пригодность raw physio data для последующего import-шага.

### Что сделано

1. Повторно сверены roadmap, execution status и work log перед началом шага.
2. Осмотрена реальная локальная раскладка `data/external/grex/raw`:
   - `1_Stimuli`;
   - `2_Questionnaire`;
   - `3_Physio`;
   - `4_Annotation`;
   - `5_Scripts`;
   - `6_Results`.
3. Из bundled `G-REx` scripts и реальных файлов извлечена observed release schema:
   - `video_info.csv/json`;
   - `quest_raw_data.csv/json`;
   - transformed pickles для `stimuli/questionnaire/physio/annotation`;
   - raw physio files `S*_physio_raw_data_M*.hdf5`.
4. В `dataset-registry` реализована реальная `inspect-source` логика для `grex` вместо placeholder `blocked`.
5. Для `grex` усилены `validate-source` rules:
   - обязательные top-level directories;
   - обязательные raw/transformed metadata files;
   - обязательное наличие raw physio `*.hdf5`.
6. В `inspect-source` для `grex` добавлены проверки:
   - headers `video_info.csv` и `quest_raw_data.csv`;
   - совпадение counts между `CSV` и `JSON`;
   - согласованность transformed artifacts на уровнях `session` и `segments`;
   - naming scheme и `HDF5` magic bytes raw physio files;
   - expected embedded tokens (`data`, `Arousal EDA`, `Valence EDA`, `sampling rate`, `movie`) в sampled raw files;
   - наличие `6_Results/EDA`, `6_Results/PPG`, `6_Results/Analysis`.
7. Добавлен unit-test для минимального валидного `G-REx` fixture.
8. Выполнена локальная верификация:
   - `cd services/dataset-registry && python3 -m compileall -q src tests` — успешно;
   - `validate-source` на полном `G-REx` — `passed`;
   - `inspect-source` на полном `G-REx` — `passed`.
9. После уточняющего вопроса пользователя выполнен дополнительный read-only `HDF5` обход через временное окружение с `h5py`:
   - все `31` raw physio files открываются корректно;
   - `data` datasets имеют shape `N x 4`;
   - attrs `movie` и `sampling rate` присутствуют;
   - в `10` raw files некоторые device-groups не содержат `Arousal EDA` и/или `Valence EDA`.

### Измененные файлы

1. `services/dataset-registry/src/dataset_registry/catalog.py`
2. `services/dataset-registry/tests/test_inspect_source.py`
3. `services/dataset-registry/tests/README.md`
4. `docs/backend/datasets-f2-3.md`
5. `README.md`
6. `docs/status/execution-status.md`
7. `docs/status/work-log.md`

### Результат

`F2.3` завершен: `G-REx` подтвержден на реальном локальном release. Проверка подтвердила `31` movie metadata records, `254` questionnaire rows, `31` raw physio HDF5 files, `241` session artifacts и `1481` segment artifacts; дополнительный `h5py`-обход показал, что в `10` raw files часть device-groups не имеет `Arousal/Valence` annotation datasets, поэтому raw HDF5 layer следует считать usable с warning, а не полностью безоговорочно чистым.

### Следующий рекомендуемый шаг

`G1 - Baseline watch-only model`

---

## 2026-03-22 - G3.1 - Extended model zoo benchmarking

### Запрос

Расширить modeling-step до большого набора моделей (включая `RandomForest`, `XGBoost`, `LightGBM`, `CatBoost`) и получить подробный comparative пакет для research/presentation.

### Что сделано

1. В `services/modeling-baselines` добавлен отдельный estimator layer с поддержкой широкого `model zoo`.
2. Реализован новый run-kind `g3-1-wesad` с benchmark pipeline по `watch_only/chest_only/fusion` вариантам.
3. Добавлены классические и бустинговые семейства: `logistic/ridge/lda/qda/svm/knn/tree/random_forest/extra_trees/bagging/adaboost/gradient_boosting/hist_gb/mlp/sgd/xgboost/lightgbm/catboost`.
4. Собран обязательный research-grade пакет артефактов: `evaluation-report.json`, `predictions-test.csv`, `per-subject-metrics.csv`, `model-comparison.csv`, `feature-importance.csv`, `failed-variants.csv`, `research-report.md`, `plots/`.
5. Реальный запуск `WESAD` выполнен (`experiment_id = g3-1-model-zoo-wesad-20260322T190114Z`): `41` successful variants, `0` failed.
6. Победители треков: `activity -> watch_only_ada_boost`, `arousal_coarse -> fusion_catboost`; оба со статусом claim `supported`.
7. По сравнению с предыдущим `G3` best-run получен прирост: `activity +0.114286`, `arousal_coarse +0.067227`.
8. Добавлены/обновлены тесты estimator/pipeline слоя; `pytest` проходит.

### Измененные файлы

1. `services/modeling-baselines/src/modeling_baselines/estimators.py`
2. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
3. `services/modeling-baselines/src/modeling_baselines/main.py`
4. `services/modeling-baselines/pyproject.toml`
5. `services/modeling-baselines/tests/test_estimators.py`
6. `services/modeling-baselines/tests/test_pipeline.py`
7. `data/external/wesad/artifacts/wesad/wesad-v1/model-zoo-benchmark/*`

### Результат

Baseline modeling переведен из узкого sanity-check в широкий comparative benchmark, пригодный для выбора кандидатов перед personalization.

### Следующий рекомендуемый шаг

`G3.2 - Multi-dataset harmonization and benchmarking`

---

## 2026-03-22 - G3.2 - Multi-dataset harmonization and benchmarking

### Запрос

Расширить сравнение моделей за пределы одного `WESAD`, добавить больше datasets и зафиксировать подробный multi-model comparative пакет для research/presentation.

### Что сделано

1. В `dataset-registry` реализованы импортёры внешних datasets:
   - `import-grex`;
   - `import-emowear`;
   - `import-dapper`.
2. Выполнены реальные импорты в unified artifacts:
   - `grex-v1`: `subject_count=191`, `session_count=232`, `segment_label_count=1481`;
   - `emowear-v1`: `subject_count=49`, `session_count=49`, `segment_label_count=114`;
   - `dapper-v1`: `subject_count=88`, `session_count=411`, `segment_label_count=411`.
3. В `modeling-baselines` добавлен шаг `g3-2-multi-dataset` с единым comparative pipeline по datasets (`wesad/grex/emowear/dapper`) и моделям:
   - `centroid`, `gaussian_nb`, `logistic_regression`, `random_forest`, `xgboost`, `lightgbm`, `catboost`.
4. Обновлен `research-report.md` генератор: добавлен обязательный раздел `Interpretation Limits` для явной фиксации ограничений proxy labels.
5. Выполнен реальный multi-dataset прогон:
   - `experiment_id = g3-2-multi-dataset-20260322T191834Z`;
   - `dataset_count=3`, `skipped_dataset_count=1`;
   - `DAPPER` пропущен с причиной `insufficient train/test examples after filtering`.
6. Зафиксированы edge-cases запуска:
   - предупреждения `sklearn` по матричным операциям;
   - один ожидаемый `LightGBMError` на `EmoWear/arousal_coarse` при вырожденном числе классов.

### Измененные файлы

1. `services/dataset-registry/src/dataset_registry/external_imports.py`
2. `services/dataset-registry/src/dataset_registry/main.py`
3. `services/dataset-registry/README.md`
4. `services/modeling-baselines/src/modeling_baselines/multi_dataset.py`
5. `services/modeling-baselines/src/modeling_baselines/main.py`
6. `data/external/multi-dataset/comparison/evaluation-report.json`
7. `data/external/multi-dataset/comparison/model-comparison.csv`
8. `data/external/multi-dataset/comparison/predictions-test.csv`
9. `data/external/multi-dataset/comparison/per-subject-metrics.csv`
10. `data/external/multi-dataset/comparison/failed-variants.csv`
11. `data/external/multi-dataset/comparison/research-report.md`
12. `data/external/multi-dataset/comparison/plots/*`
13. `docs/backend/modeling-g3-2.md`
14. `docs/status/execution-status.md`
15. `docs/status/work-log.md`

### Результат

`G3.2` завершен: multi-dataset harmonization и benchmarking выполнены на реальных данных (`WESAD/G-REx/EmoWear`) с расширенным model set и полным comparative research bundle. Для `EmoWear/DAPPER` ограничения proxy labels явно зафиксированы в отчете; `DAPPER` корректно отмечен как `skipped` по условию достаточности split.

### Следующий рекомендуемый шаг

`H1 - Схема профиля пользователя`

---

## 2026-03-22 - H1 - Схема профиля пользователя

### Запрос

После завершения `G3.2` зафиксировать каноническую схему профиля пользователя для personalization и добавить подробные артефакты (контракты, отчет, сравнение кандидатов, графики), чтобы можно было переходить к `H2`.

### Что сделано

1. Повторно сверены обязательные документы перед шагом:
   - `docs/roadmap/research-pipeline-backend-plan.md`
   - `docs/status/execution-status.md`
   - `docs/status/work-log.md`
   - `docs/research/model-reporting-standard.md`
2. Добавлены contracts personalization-контура:
   - `contracts/personalization/user-profile.schema.json` (`h1-v1`);
   - `contracts/personalization/personalization-feature-contract.schema.json` (`h1-feature-contract-v1`);
   - `contracts/personalization/README.md`.
3. Создан исследовательский документ `H1` со структурой профиля, leakage guards, calibration budget rules и candidate mapping из `G3.1/G3.2`:
   - `docs/research/personalization-user-profile-schema.md`.
4. Собран machine-readable/presentation-ready H1 пакет:
   - `data/artifacts/personalization/h1-profile-schema/evaluation-report.json`;
   - `model-comparison.csv`;
   - `per-subject-metrics.csv`;
   - `research-report.md`;
   - `plots/model-family-candidates.svg`;
   - `plots/calibration-budget-sensitivity.svg`;
   - `plots/worst-case-degradation-guard.svg`.
5. Создан backend step-doc:
   - `docs/backend/personalization-h1.md`.
6. Обновлены индексные ссылки в `README.md`.
7. Обновлен `execution-status`:
   - `H1 -> completed`;
   - `H2 -> next`;
   - текущая фаза переведена в `H - Personalization`.

### Измененные файлы

1. `contracts/personalization/README.md`
2. `contracts/personalization/user-profile.schema.json`
3. `contracts/personalization/personalization-feature-contract.schema.json`
4. `docs/research/personalization-user-profile-schema.md`
5. `data/artifacts/personalization/h1-profile-schema/evaluation-report.json`
6. `data/artifacts/personalization/h1-profile-schema/model-comparison.csv`
7. `data/artifacts/personalization/h1-profile-schema/per-subject-metrics.csv`
8. `data/artifacts/personalization/h1-profile-schema/research-report.md`
9. `data/artifacts/personalization/h1-profile-schema/plots/model-family-candidates.svg`
10. `data/artifacts/personalization/h1-profile-schema/plots/calibration-budget-sensitivity.svg`
11. `data/artifacts/personalization/h1-profile-schema/plots/worst-case-degradation-guard.svg`
12. `docs/backend/personalization-h1.md`
13. `README.md`
14. `docs/status/execution-status.md`
15. `docs/status/work-log.md`

### Результат

`H1` завершен: определен канонический профиль пользователя и входной personalization contract, зафиксированы ограничения качества/утечки, а также выбран набор primary/fallback global кандидатов для `H2` на базе результатов `G3.1/G3.2`.

### Следующий рекомендуемый шаг

`H2 - Light personalization`

---

## 2026-03-22 - H2 - Light personalization

### Запрос

После `H1` реализовать `light personalization` без fine-tune, сравнить `global vs personalized` на одном protocol и выпустить подробный comparative пакет с графиками для презентации.

### Что сделано

1. Повторно сверены обязательные документы перед шагом:
   - `docs/roadmap/research-pipeline-backend-plan.md`
   - `docs/status/execution-status.md`
   - `docs/status/work-log.md`
   - `docs/research/model-reporting-standard.md`
2. В `services/modeling-baselines` реализован новый run-kind:
   - `h2-light-personalization-wesad`.
3. Реализован `light personalization` метод:
   - subject-level post-hoc predicted->true mapping на calibration subset;
   - disjoint split между calibration и evaluation subset внутри test subjects.
4. Добавлено multi-model сравнение для personalization:
   - `watch_only_ada_boost`;
   - `watch_only_random_forest`;
   - `fusion_catboost`;
   - `fusion_gaussian_nb`.
5. Добавлены H2-specific artifacts и генерация отчетности:
   - `evaluation-report.json`;
   - `predictions-test.csv`;
   - `per-subject-metrics.csv`;
   - `model-comparison.csv`;
   - `failed-variants.csv`;
   - `research-report.md`;
   - `plots/`.
6. Добавлены personalization-specific plots:
   - gain distribution по субъектам;
   - calibration budget sensitivity;
   - worst-case degradation.
7. Обновлены CLI/README `modeling-baselines` и добавлены unit tests для H2 helper-логики.
8. Выполнена локальная проверка:
   - `pytest` -> `12 passed`;
   - `compileall` -> `COMPILE_OK`.
9. Выполнен реальный H2 запуск:
   - `experiment_id = h2-light-personalization-wesad-20260322T193412Z`;
   - `successful_variant_count=4`, `failed_variant_count=0`;
   - outputs: `data/external/wesad/artifacts/wesad/wesad-v1/light-personalization/*`.

### Измененные файлы

1. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
2. `services/modeling-baselines/src/modeling_baselines/main.py`
3. `services/modeling-baselines/README.md`
4. `services/modeling-baselines/tests/test_pipeline.py`
5. `data/external/wesad/artifacts/wesad/wesad-v1/light-personalization/evaluation-report.json`
6. `data/external/wesad/artifacts/wesad/wesad-v1/light-personalization/model-comparison.csv`
7. `data/external/wesad/artifacts/wesad/wesad-v1/light-personalization/per-subject-metrics.csv`
8. `data/external/wesad/artifacts/wesad/wesad-v1/light-personalization/predictions-test.csv`
9. `data/external/wesad/artifacts/wesad/wesad-v1/light-personalization/failed-variants.csv`
10. `data/external/wesad/artifacts/wesad/wesad-v1/light-personalization/research-report.md`
11. `data/external/wesad/artifacts/wesad/wesad-v1/light-personalization/plots/*`
12. `docs/backend/personalization-h2.md`
13. `README.md`
14. `docs/status/execution-status.md`
15. `docs/status/work-log.md`

### Результат

`H2` завершен: реализован и верифицирован воспроизводимый `light personalization` benchmark с честным `global vs personalized` сравнением. На текущем `WESAD` holdout (`3` test subjects, `budget=2`) устойчивого headline improvement относительно лучших global-моделей не получено; для ряда baseline families зафиксированы regressions, что формирует обоснование для перехода к stronger adaptation в `H3`.

### Следующий рекомендуемый шаг

`H3 - Full personalization`

---

## 2026-03-22 - H3 - Full personalization

### Запрос

После `H2` реализовать stronger adaptation (`full personalization`) и выпустить подробный сравнительный пакет `global vs light vs full` на одинаковом personalization protocol.

### Что сделано

1. Повторно сверены обязательные документы перед шагом:
   - `docs/roadmap/research-pipeline-backend-plan.md`
   - `docs/status/execution-status.md`
   - `docs/status/work-log.md`
   - `docs/research/model-reporting-standard.md`
2. В `services/modeling-baselines` добавлен новый run-kind:
   - `h3-full-personalization-wesad`.
3. Реализован `full personalization` метод:
   - subject-specific refit на `global_train + calibration`;
   - параметр `adaptation_weight` для усиления влияния calibration examples.
4. Реализовано тройное сравнение по каждому варианту:
   - `global`;
   - `light`;
   - `full`.
5. Добавлены H3-specific artifacts и отчетность:
   - `evaluation-report.json`;
   - `predictions-test.csv`;
   - `per-subject-metrics.csv`;
   - `model-comparison.csv`;
   - `failed-variants.csv`;
   - `research-report.md`;
   - `plots/`.
6. Добавлены H3-specific plots:
   - full-vs-light gain distribution;
   - calibration budget sensitivity (`light` vs `full`);
   - worst-case degradation (`full vs global`).
7. Обновлены CLI/README `modeling-baselines` и расширены unit tests.
8. Выполнена локальная верификация:
   - `compileall` -> `COMPILE_OK`;
   - `pytest` -> `13 passed`.
9. Выполнен реальный H3 запуск:
   - `experiment_id = h3-full-personalization-wesad-20260322T194248Z`;
   - `successful_variant_count=4`, `failed_variant_count=0`;
   - outputs: `data/external/wesad/artifacts/wesad/wesad-v1/full-personalization/*`.

### Измененные файлы

1. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
2. `services/modeling-baselines/src/modeling_baselines/main.py`
3. `services/modeling-baselines/README.md`
4. `services/modeling-baselines/tests/test_pipeline.py`
5. `data/external/wesad/artifacts/wesad/wesad-v1/full-personalization/evaluation-report.json`
6. `data/external/wesad/artifacts/wesad/wesad-v1/full-personalization/model-comparison.csv`
7. `data/external/wesad/artifacts/wesad/wesad-v1/full-personalization/per-subject-metrics.csv`
8. `data/external/wesad/artifacts/wesad/wesad-v1/full-personalization/predictions-test.csv`
9. `data/external/wesad/artifacts/wesad/wesad-v1/full-personalization/failed-variants.csv`
10. `data/external/wesad/artifacts/wesad/wesad-v1/full-personalization/research-report.md`
11. `data/external/wesad/artifacts/wesad/wesad-v1/full-personalization/plots/*`
12. `docs/backend/personalization-h3.md`
13. `README.md`
14. `docs/status/execution-status.md`
15. `docs/status/work-log.md`

### Результат

`H3` завершен: реализован и верифицирован `full personalization` benchmark с тройным сравнением (`global/light/full`) и полным research-grade пакетом. На текущем holdout full-подход в основном восстанавливает деградации `light` (положительный `delta_vs_light` для ряда вариантов), но не формирует устойчивый headline прирост относительно лучших global моделей.

### Следующий рекомендуемый шаг

`I1 - Research report и production scope decision`

---

## 2026-03-22 - I1 - Research report и production scope decision

### Запрос

После `H3` выполнить `I1`: свести результаты `G1-G3` и `H1-H3` в единый decision-oriented research пакет, пригодный для presentation и решения по production scope.

### Что сделано

1. Повторно сверены обязательные документы перед шагом:
   - `docs/roadmap/research-pipeline-backend-plan.md`
   - `docs/status/execution-status.md`
   - `docs/status/work-log.md`
   - `docs/research/model-reporting-standard.md`
2. Сформирован единый `I1` artifact bundle в каталоге:
   - `data/artifacts/research-gate/i1-production-scope-decision/`
3. Подготовлены machine-readable артефакты:
   - `evaluation-report.json` (decision summary, source runs, risks, in-scope/out-of-scope);
   - `model-comparison.csv` (top `G3.1`, winners `G3.2`, `H3 global/light/full`);
   - `per-subject-metrics.csv` (subject-level personalization evidence).
4. Подготовлен подробный текстовый отчет:
   - `research-report.md` с decision-oriented выводами и production scope.
5. Подготовлены presentation-ready графики:
   - агрегированные top-by-step charts (`activity`, `arousal_coarse`);
   - subject-level `full vs light` gain distribution;
   - reference plots: feature importance, multi-dataset winner view, worst-case degradation.
6. Добавлена backend-документация шага:
   - `docs/backend/research-gate-i1.md`.
7. Обновлены индексные ссылки и статус:
   - `README.md`;
   - `docs/status/execution-status.md` (`I1 -> completed`, `J1 -> next`, фаза `J`).

### Измененные файлы

1. `data/artifacts/research-gate/i1-production-scope-decision/evaluation-report.json`
2. `data/artifacts/research-gate/i1-production-scope-decision/model-comparison.csv`
3. `data/artifacts/research-gate/i1-production-scope-decision/per-subject-metrics.csv`
4. `data/artifacts/research-gate/i1-production-scope-decision/research-report.md`
5. `data/artifacts/research-gate/i1-production-scope-decision/plots/*`
6. `docs/backend/research-gate-i1.md`
7. `README.md`
8. `docs/status/execution-status.md`
9. `docs/status/work-log.md`

### Результат

`I1` завершен: собран единый decision gate пакет по результатам modeling/personalization, зафиксирован production scope и ограничения claim-grade интерпретации (proxy labels, небольшой holdout). Переход к `J1` обоснован и зафиксирован в статусе.

### Следующий рекомендуемый шаг

`J1 - Experiment tracking и model registry`

---

## 2026-03-22 - I1.1 - Корректировка roadmap под методику персонализации

### Запрос

После `I1` скорректировать задачи и roadmap так, чтобы проект не уходил сразу в `J1`, а продолжил personalization research с фокусом на методику персонализации как основной научный вклад работы.

### Что сделано

1. Повторно сверены обязательные документы перед шагом:
   - `docs/roadmap/research-pipeline-backend-plan.md`
   - `docs/status/execution-status.md`
   - `docs/status/work-log.md`
   - `docs/research/model-reporting-standard.md`
2. Обновлен roadmap:
   - в фазу `H` добавлен methodological emphasis для personalization;
   - зафиксирован `WESAD` как достаточный baseline anchor;
   - добавлено уточнение, что после `I1` можно вернуться в дополнительный personalization sub-track перед `J`.
3. Добавлены новые шаги выполнения:
   - `H4 - Personalization methodology redesign`;
   - `H5 - Weak-label / label-free personalization benchmark`;
   - `H6 - Realtime personalization evaluation plan`.
4. Создан отдельный step-doc:
   - `docs/backend/personalization-i1-1.md`.
5. Обновлен `execution-status`:
   - текущая фаза возвращена в `H - Personalization Research`;
   - `H4 -> next`;
   - `J1 -> pending`.
6. Обновлен `README.md` ссылкой на новый документ.

### Измененные файлы

1. `docs/roadmap/research-pipeline-backend-plan.md`
2. `docs/backend/personalization-i1-1.md`
3. `README.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`

### Результат

План проекта официально скорректирован: дальнейшая исследовательская работа концентрируется на методике персонализации поверх уже обученного `WESAD` baseline для двух линий (`watch-only`, `fusion`), а не на немедленном переходе в ML Platform.

### Следующий рекомендуемый шаг

`H4 - Personalization methodology redesign`

---

## 2026-03-22 - H4 - Personalization methodology redesign

### Запрос

После сверки статуса и подтверждения пользователя выполнить шаг `H4`: зафиксировать методику персонализации как основной научный вклад (objective, hypotheses, strategy matrix для `watch-only/fusion` и `arousal/valence`) и подготовить артефакты перехода к `H5`.

### Что сделано

1. Повторно сверены обязательные документы перед шагом:
   - `docs/roadmap/research-pipeline-backend-plan.md`
   - `docs/status/execution-status.md`
   - `docs/status/work-log.md`
   - `docs/research/model-reporting-standard.md`
2. Подготовлен методологический документ:
   - `docs/research/personalization-methodology-redesign.md`.
3. Зафиксированы:
   - формальный `research objective`;
   - гипотезы `H4-HYP-1..H4-HYP-4`;
   - strategy matrix (`watch-only/fusion` x `arousal_coarse/valence`, с label-efficient и label-free линиями);
   - claim boundaries и readiness criteria для запуска `H5`.
4. Собран research-grade H4 bundle:
   - `data/artifacts/personalization/h4-methodology-redesign/evaluation-report.json`
   - `data/artifacts/personalization/h4-methodology-redesign/model-comparison.csv`
   - `data/artifacts/personalization/h4-methodology-redesign/per-subject-metrics.csv`
   - `data/artifacts/personalization/h4-methodology-redesign/research-report.md`
   - `data/artifacts/personalization/h4-methodology-redesign/plots/*`
5. Добавлен backend step-doc:
   - `docs/backend/personalization-h4.md`.
6. Обновлены индексы и статус:
   - `README.md`;
   - `docs/status/execution-status.md` (`H4 -> completed`, `H5 -> next`).

### Измененные файлы

1. `docs/research/personalization-methodology-redesign.md`
2. `docs/backend/personalization-h4.md`
3. `data/artifacts/personalization/h4-methodology-redesign/evaluation-report.json`
4. `data/artifacts/personalization/h4-methodology-redesign/model-comparison.csv`
5. `data/artifacts/personalization/h4-methodology-redesign/per-subject-metrics.csv`
6. `data/artifacts/personalization/h4-methodology-redesign/research-report.md`
7. `data/artifacts/personalization/h4-methodology-redesign/plots/strategy-matrix-overview.svg`
8. `data/artifacts/personalization/h4-methodology-redesign/plots/claim-boundary-map.svg`
9. `data/artifacts/personalization/h4-methodology-redesign/plots/h5-readiness-gates.svg`
10. `docs/status/execution-status.md`
11. `docs/status/work-log.md`
12. `README.md`

### Результат

`H4` завершен: personalization track переведен в явный hypothesis-driven методологический режим с фиксированной strategy matrix, границами claim-grade интерпретации и критериями готовности к benchmark шагу `H5`.

### Следующий рекомендуемый шаг

`H5 - Weak-label / label-free personalization benchmark`

---

## 2026-03-22 - H5 - Weak-label / label-free personalization benchmark

### Запрос

После `H4` и подтверждения пользователя выполнить шаг `H5`: сравнить `weak-label` и `label-free` personalization variants поверх `WESAD` baseline с полным research-grade отчетом и артефактами.

### Что сделано

1. Повторно сверены обязательные документы перед шагом:
   - `docs/roadmap/research-pipeline-backend-plan.md`
   - `docs/status/execution-status.md`
   - `docs/status/work-log.md`
   - `docs/research/model-reporting-standard.md`
2. В `services/modeling-baselines` реализован новый run-kind:
   - `h5-weak-label-label-free-wesad`.
3. Добавлен H5 pipeline:
   - `global vs weak_label vs label_free` на одном subject-wise protocol;
   - weak-label adaptation через смешанные calibration labels;
   - label-free adaptation на pseudo-labels без ручной разметки.
4. Добавлены H5 artifacts/writers/report/plots и обновлен CLI:
   - `evaluation-report.json`;
   - `predictions-test.csv`;
   - `per-subject-metrics.csv`;
   - `model-comparison.csv`;
   - `failed-variants.csv`;
   - `research-report.md`;
   - `plots/h5-*`.
5. Выполнен реальный H5 запуск:
   - `experiment_id = h5-weak-label-label-free-wesad-20260322T202905Z`;
   - `successful_variant_count=4`, `failed_variant_count=0`;
   - outputs: `data/external/wesad/artifacts/wesad/wesad-v1/weak-label-label-free-personalization/*`.
6. Добавлена backend документация шага:
   - `docs/backend/personalization-h5.md`.
7. Обновлены индексные ссылки и статус:
   - `README.md`;
   - `docs/status/execution-status.md` (`H5 -> completed`, `H6 -> next`).

### Измененные файлы

1. `services/modeling-baselines/src/modeling_baselines/main.py`
2. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
3. `services/modeling-baselines/tests/test_pipeline.py`
4. `services/modeling-baselines/README.md`
5. `data/external/wesad/artifacts/wesad/wesad-v1/weak-label-label-free-personalization/evaluation-report.json`
6. `data/external/wesad/artifacts/wesad/wesad-v1/weak-label-label-free-personalization/predictions-test.csv`
7. `data/external/wesad/artifacts/wesad/wesad-v1/weak-label-label-free-personalization/per-subject-metrics.csv`
8. `data/external/wesad/artifacts/wesad/wesad-v1/weak-label-label-free-personalization/model-comparison.csv`
9. `data/external/wesad/artifacts/wesad/wesad-v1/weak-label-label-free-personalization/failed-variants.csv`
10. `data/external/wesad/artifacts/wesad/wesad-v1/weak-label-label-free-personalization/research-report.md`
11. `data/external/wesad/artifacts/wesad/wesad-v1/weak-label-label-free-personalization/plots/*`
12. `docs/backend/personalization-h5.md`
13. `README.md`
14. `docs/status/execution-status.md`
15. `docs/status/work-log.md`

### Результат

`H5` завершен: реализован и выполнен reproducible benchmark для `weak-label` и `label-free` personalization. На текущем `WESAD` holdout устойчивого прироста `label-free` относительно `global`/`weak-label` не зафиксировано; часть baseline variants показывает регрессии при noisy/pseudo adaptation.

### Следующий рекомендуемый шаг

`H6 - Realtime personalization evaluation plan`

---

## 2026-03-22 - H6 - Realtime personalization evaluation plan

### Запрос

После `H5` и подтверждения пользователя выполнить шаг `H6`: зафиксировать, как проверять personalized `activity/arousal/valence` в `replay/live` контуре и какие ограничения должны быть закрыты до перехода в `J1`.

### Что сделано

1. Повторно сверены обязательные документы перед шагом:
   - `docs/roadmap/research-pipeline-backend-plan.md`
   - `docs/status/execution-status.md`
   - `docs/status/work-log.md`
   - `docs/research/model-reporting-standard.md`
2. Подготовлен research документ шага:
   - `docs/research/personalization-realtime-evaluation-plan.md`.
3. Зафиксированы:
   - runtime modes (`offline/replay/live_shadow`);
   - scenario matrix `H6-S1..H6-S8`;
   - KPI thresholds (latency/drop/sync/worst-subject-delta);
   - fallback policy и claim boundaries для `valence`.
4. Собран H6 artifact bundle:
   - `data/artifacts/personalization/h6-realtime-evaluation-plan/evaluation-report.json`
   - `data/artifacts/personalization/h6-realtime-evaluation-plan/model-comparison.csv`
   - `data/artifacts/personalization/h6-realtime-evaluation-plan/per-subject-metrics.csv`
   - `data/artifacts/personalization/h6-realtime-evaluation-plan/research-report.md`
   - `data/artifacts/personalization/h6-realtime-evaluation-plan/plots/*`
5. Добавлен backend step-doc:
   - `docs/backend/personalization-h6.md`.
6. Обновлены индексы и статус:
   - `README.md`;
   - `docs/status/execution-status.md` (`H6 -> completed`, `J1 -> next`).

### Измененные файлы

1. `docs/research/personalization-realtime-evaluation-plan.md`
2. `docs/backend/personalization-h6.md`
3. `data/artifacts/personalization/h6-realtime-evaluation-plan/evaluation-report.json`
4. `data/artifacts/personalization/h6-realtime-evaluation-plan/model-comparison.csv`
5. `data/artifacts/personalization/h6-realtime-evaluation-plan/per-subject-metrics.csv`
6. `data/artifacts/personalization/h6-realtime-evaluation-plan/research-report.md`
7. `data/artifacts/personalization/h6-realtime-evaluation-plan/plots/replay-live-gates.svg`
8. `data/artifacts/personalization/h6-realtime-evaluation-plan/plots/runtime-kpi-thresholds.svg`
9. `data/artifacts/personalization/h6-realtime-evaluation-plan/plots/fallback-policy-flow.svg`
10. `README.md`
11. `docs/status/execution-status.md`
12. `docs/status/work-log.md`

### Результат

`H6` завершен: определен формальный replay/live evaluation gate для personalized inference с KPI-порогами, fallback-правилами и критериями готовности к переходу в `J1`.

### Следующий рекомендуемый шаг

`J1 - Experiment tracking и model registry`

---

## 2026-03-22 - Анализ macro_f1 = 1.0 (диагностика)

### Запрос

По результатам работы обещанные модели показывают F1 = 1.0; возможно переобучение или иной артефакт. Требуется анализ проекта.

### Что сделано

1. Проверены roadmap, execution-status и work-log по протоколу collaboration.
2. Проанализирован pipeline моделирования: split logic, feature construction, evaluation flow.
3. Проверено отсутствие явной утечки (subject_id/session_id не в признаках; calibration/eval disjoint).
4. Оценены объём eval subset (~9 сегментов, 3 test subjects) и структура WESAD.
5. Создан документ анализа: `docs/research/f1-equals-one-analysis.md` с гипотезами и рекомендациями.

### Измененные файлы

1. `docs/research/f1-equals-one-analysis.md`
2. `docs/status/work-log.md`

### Результат

Выявлено: F1 = 1.0 скорее всего объясняется (1) простотой задачи WESAD (stress vs rest), (2) малой eval выборкой (~9 сегментов) с высокой дисперсией, (3) возможным косвенным протокольным сигналом через meta-признаки. Явной утечки данных не обнаружено. `fusion_gaussian_nb` не достигает 1.0, что подтверждает разделение по качеству моделей.

Рекомендации: LOSO evaluation, расширение eval subset, ablation meta-признаков, multi-dataset валидация.

### Следующий рекомендуемый шаг

Ввести диагностический шаг `G3.3` или `H5.1`: LOSO evaluation по WESAD и проверка влияния meta-признаков. После подтверждения пользователя реализовать и зафиксировать обновлённые claim-правила для подозрительно высоких метрик.

---

## 2026-03-22 - J1 - Experiment tracking и model registry

### Запрос

Выполнить шаг J1: добавить experiment tracking и model registry в modeling-baselines с привязкой к H6 evaluation gate.

### Что сделано

1. Добавлены зависимости `mlflow` и `joblib` в `pyproject.toml`.
2. Создан модуль `modeling_baselines/tracking.py`: `TrackingContext`, `NoOpTracking`, `create_tracking_context`, `_flatten_metrics`.
3. Интегрирован MLflow в `main.py`: логирование params (run_kind, dataset_id, preprocessing_version и др.), metrics из evaluation-report, artifacts (output root).
4. Добавлены аргументы CLI: `--no-mlflow`, `--mlflow-tracking-uri`, `--save-models`.
5. Расширен pipeline: `_evaluate_variant` принимает `model_save_dir`; при наличии сохраняет activity/arousal модели через `joblib.dump`; `run_watch_only_wesad_baseline` передаёт `model_save_dir` при `--save-models`.
6. Обновлён README modeling-baselines: описание J1 tracking и флагов.

### Измененные файлы

1. `services/modeling-baselines/pyproject.toml`
2. `services/modeling-baselines/src/modeling_baselines/tracking.py` (новый)
3. `services/modeling-baselines/src/modeling_baselines/main.py`
4. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
5. `services/modeling-baselines/README.md`
6. `docs/status/execution-status.md`
7. `docs/status/work-log.md`

### Результат

J1 завершён: MLflow experiment tracking подключён ко всем run-kind, логируются params/metrics/artifacts; опциональное сохранение моделей watch-only в `output_dir/.../models/`; при включённом tracking артефакты включают reports, plots и модели для воспроизводимости.

### Следующий рекомендуемый шаг

`J2 - Автоматизация training/evaluation jobs`

---

## 2026-03-22 - J2 - Автоматизация training/evaluation jobs

### Запрос

Выполнить шаг J2: автоматизировать training и evaluation jobs, версионировать datasets и preprocessing.

### Что сделано

1. Создан каталог `scripts/ml/` с automated jobs.
2. `run-dataset-build.sh`: импорт датасета (wesad/emowear/grex/dapper) через dataset-registry с версионированием.
3. `run-training.sh`: запуск modeling-baselines с конфигурацией через env (`DATASET_ID`, `DATASET_VERSION`, `PREPROCESSING_VERSION`, `RUN_KIND` и др.); поддержка всех run-kind включая `g3-2-multi-dataset`.
4. `run-full-pipeline.sh`: цепочка dataset build (опционально) + training.
5. Добавлены `config.env.example` и `scripts/ml/README.md` с документацией переменных и команд.

### Измененные файлы

1. `scripts/ml/run-dataset-build.sh` (новый)
2. `scripts/ml/run-training.sh` (новый)
3. `scripts/ml/run-full-pipeline.sh` (новый)
4. `scripts/ml/config.env.example` (новый)
5. `scripts/ml/README.md` (новый)
6. `scripts/README.md`
7. `docs/status/execution-status.md`
8. `docs/status/work-log.md`

### Результат

J2 завершён: любой run modeling-baselines можно запустить одной командой по версии датасета и preprocessing без ручного указания путей; dataset build и training объединены в повторяемый pipeline.

### Следующий рекомендуемый шаг

`K1 - Production backend architecture`

---

## 2026-03-22 - K1 - Production backend architecture

### Запрос

Выполнить шаг K1: зафиксировать production backend architecture.

### Что сделано

1. Создан документ `docs/architecture/production-backend.md`: инвентарь сервисов (ingest-api, replay-service, signal-processing-worker, dataset-registry, modeling-baselines; планируемые inference-api, personalization-worker), разделение online/offline контуров, потоки данных, контракты, инфраструктура, auth/audit, план миграции.
2. Формализован индекс контрактов в `contracts/README.md`: HTTP-контракты, schema, events (planned).
3. Добавлена ссылка на production architecture в `README.md`.

### Измененные файлы

1. `docs/architecture/production-backend.md` (новый)
2. `contracts/README.md`
3. `README.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`

### Результат

K1 завершён: production backend architecture зафиксирована; сервисы, контракты и контуры определены; документ служит основой для K2 (inference-api, async processing).

### Следующий рекомендуемый шаг

`K2 - Inference API и async processing`

---

## 2026-03-22 - K2 - Inference API и async processing

### Запрос

Выполнить шаг K2: реализовать inference API и асинхронную обработку.

### Что сделано

1. Создан сервис `inference-api`: FastAPI, `GET /health`, `POST /v1/predict`; загрузка model bundle (activity/arousal joblib + feature_names.json) из `INFERENCE_MODEL_DIR`.
2. Добавлен OpenAPI контракт `contracts/http/inference-api.openapi.yaml`.
3. В modeling-baselines при `--save-models` добавлено сохранение `feature_names.json` рядом с joblib-моделями.
4. Добавлен inference-api в `infra/compose/on-go-stack.yml`; Redis добавлен в стек для будущей async очереди.
5. Обновлены contracts/README, production-backend.md, README.md.

### Измененные файлы

1. `services/inference-api/` (новый сервис)
2. `contracts/http/inference-api.openapi.yaml` (новый)
3. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
4. `infra/compose/on-go-stack.yml`
5. `contracts/README.md`
6. `docs/architecture/production-backend.md`
7. `README.md`
8. `docs/status/execution-status.md`
9. `docs/status/work-log.md`

### Результат

K2 завершён: inference-api принимает feature_vector и возвращает activity/arousal; model bundle совместим с modeling-baselines --save-models; Redis в стеке для async processing.

### Следующий рекомендуемый шаг

`K3 - Deployment, observability, operations`

---

## 2026-03-22 - K3 - Deployment, observability, operations

### Запрос

Выполнить шаг K3: deployment, observability, operations.

### Что сделано

1. Создан CI workflow `.github/workflows/ci.yml`: job unit-tests (pytest для ingest-api, replay-service, signal-processing-worker, dataset-registry, modeling-baselines), job stack-e2e (docker compose up + replay integration tests).
2. Добавлен operations runbook `docs/operations/runbook.md`: локальный запуск, health checks, CI/CD, observability, troubleshooting.
3. Обновлены `docs/setup/local-docker-setup.md` (inference-api, Redis, порты), `.github/workflows/README.md`.
4. В replay-service pyproject добавлен `tests` в pytest pythonpath для stack_e2e imports.

### Измененные файлы

1. `.github/workflows/ci.yml` (новый)
2. `docs/operations/runbook.md` (новый)
3. `docs/setup/local-docker-setup.md`
4. `.github/workflows/README.md`
5. `services/replay-service/pyproject.toml`
6. `README.md`
7. `docs/status/execution-status.md`
8. `docs/status/work-log.md`

### Результат

K3 завершён: CI запускает unit-тесты и stack-e2e; operations runbook фиксирует процедуры запуска и troubleshooting.

### Следующий рекомендуемый шаг

Следующий инкремент по roadmap: personalization-worker, training-orchestrator, расширение observability или auth (K3).

---

## 2026-03-22 - K4 - Personalization worker

### Запрос

Реализовать следующий шаг по roadmap — personalization-worker.

### Что сделано

1. Создан сервис `personalization-worker`: FastAPI с `GET /health`, `GET /v1/profile/{subject_id}`, `PUT /v1/profile`; in-memory profile store; Pydantic модели для ProfileCreate/ProfileResponse.
2. Добавлен OpenAPI контракт `contracts/http/personalization-worker.openapi.yaml`.
3. Сервис добавлен в `infra/compose/on-go-stack.yml`, порт 8110.
4. Обновлены contracts/README, production-backend.md, local-docker-setup.md, README.md.
5. Добавлены unit-тесты и сервис в CI matrix.

### Измененные файлы

1. `services/personalization-worker/` (новый сервис)
2. `contracts/http/personalization-worker.openapi.yaml` (новый)
3. `infra/compose/on-go-stack.yml`
4. `contracts/README.md`
5. `docs/architecture/production-backend.md`
6. `docs/setup/local-docker-setup.md`
7. `.github/workflows/ci.yml`
8. `README.md`
9. `docs/status/execution-status.md`
10. `docs/status/work-log.md`

### Результат

K4 завершён: personalization-worker принимает и хранит профили; inference-api может в будущем запрашивать профиль для персонализированного inference.

### Следующий рекомендуемый шаг

Следующий инкремент: training-orchestrator, интеграция inference-api с personalization-worker (персонализированный inference path) или расширение Phase K.

---

## 2026-03-22 - Live streaming (вариант A)

### Запрос

Реализовать вариант A: live streaming с устройства в backend, feature extraction на backend, inference, push обратно клиенту.

### Что сделано

1. Создан сервис `live-inference-api`: WebSocket `/ws/live`, приём `stream_batch` (watch_heart_rate, watch_accelerometer); буферизация; window-based feature extraction; inference через ту же model bundle что inference-api; push результата (activity, arousal_coarse) клиенту.
2. Feature adapter: watch_accelerometer → watch_acc_*, watch_heart_rate → watch_bvp_*; watch_eda_*, watch_temp_* заполняются нулями (модель WESAD).
3. Добавлен в compose (порт 8120), contracts, production-backend, local-docker-setup, CI.
4. Документ `docs/setup/live-streaming-integration.md` — инструкция для интеграции on-go-ios.

### Измененные файлы

1. `services/live-inference-api/` (новый сервис)
2. `contracts/http/live-inference-api.openapi.yaml` (новый)
3. `infra/compose/on-go-stack.yml`
4. `docs/setup/live-streaming-integration.md` (новый)
5. `docs/setup/local-docker-setup.md`
6. `docs/architecture/production-backend.md`
7. `contracts/README.md`
8. `.github/workflows/ci.yml`
9. `README.md`
10. `docs/status/execution-status.md`
11. `docs/status/work-log.md`

### Результат

Backend для live streaming готов. Фронт (on-go-ios) должен: открыть WebSocket к `ws://host:8120/ws/live`, отправлять stream_batch при получении сэмплов от Polar/Watch, обрабатывать incoming inference и обновлять UI.

### Следующий рекомендуемый шаг

Интеграция WebSocket-клиента в on-go-ios и UI для отображения activity/arousal в реальном времени.

---

## 2026-03-25 - Зафиксирован future track для крупной multi-dataset модели

### Запрос

Зафиксировать в плане, что возврат к обучению более крупной общей модели на нескольких внешних датасетах допускается позже, но только после выполнения явных условий по feature safety и quality labels.

### Что сделано

1. В roadmap добавлено явное правило: текущий `WESAD` baseline остается достаточной стартовой глобальной моделью, а pooled multi-dataset global modeling считается отдельным future track, а не ближайшим приоритетом.
2. Зафиксированы два обязательных предусловия для возврата к этой линии:
   - безопасные harmonized non-label signal features, общие для внешних datasets;
   - нормальные claim-grade labels для внешних datasets вместо proxy-mapping как основного supervision source.
3. В `execution-status` добавлен отдельный блок с отложенным решением, чтобы эта договоренность не потерялась при переходе к следующим backend/platform шагам.
4. Явно зафиксировано промежуточное правило: до выполнения этих условий внешние datasets используются для harmonization, validation и transfer/cross-dataset проверок, а не для обучения большой общей модели.

### Измененные файлы

1. `docs/roadmap/research-pipeline-backend-plan.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`

### Результат

Решение сохранено в плане и статусных документах: future pooled multi-dataset model не забывается, но и не смешивается с текущим приоритетом на personalization и production backend.

---

## 2026-03-25 - G3.1r - Safety audit, LOSO rerun and numeric stability hardening

### Запрос

Разобраться, почему результаты обучения выглядят нереалистично, устранить источник ошибки и перевести baseline selection на строгий fold-based protocol.

### Что сделано

1. В `modeling-baselines` добавлен обязательный pre-run safety gate `audit-wesad`.
2. Зафиксирован repair plan в `docs/research/model-validation-repair-plan.md`:
   - feature safety;
   - split integrity;
   - numeric stability;
   - обязательный `LOSO/GroupKFold` для малого числа субъектов.
3. Выполнен реальный safety audit на `WESAD`; подтверждено:
   - forbidden shortcut features = `0`;
   - duplicate segments = `0`;
   - subject overlap across splits = `0`.
4. Выполнен реальный `G3.1` rerun в режиме `LOSO`.
5. Во время прогона выявлен и исправлен numeric-stability дефект:
   - на части моделей при `predict` возникали `RuntimeWarning` (`overflow`, `divide by zero`);
   - в `estimators.py` добавлена санация признаков (`nan/inf -> finite`, clipping);
   - runtime warnings на инференсе приведены к воспроизводимому контролируемому состоянию.
6. Добавлен regression test на нечисловые/бесконечные входы.

### Измененные файлы

1. `services/modeling-baselines/src/modeling_baselines/estimators.py`
2. `services/modeling-baselines/tests/test_estimators.py`
3. `docs/research/model-validation-repair-plan.md`
4. `services/modeling-baselines/README.md`

### Результат

Безопасный `LOSO` baseline зафиксирован как новый claim-grade reference для `WESAD`. Логи benchmark больше не искажаются численной нестабильностью.

### Следующий рекомендуемый шаг

Разделить multi-dataset линию по качеству supervision, а не смешивать `real`, `protocol-mapped` и `proxy` labels в один training/evaluation контур.

---

## 2026-03-25 - G3.2s - Multi-dataset strategy и supervision tiers

### Запрос

Использовать оставшиеся датасеты корректно и определить, какие из них можно применять для обучения `arousal`, а какие только для вспомогательных целей.

### Что сделано

1. Проанализирован registry внешних datasets и реальное качество labels:
   - `G-REx` -> `real` arousal supervision;
   - `WESAD` -> `protocol-mapped` arousal;
   - `EmoWear`/`DAPPER` -> `proxy` labels.
2. В `modeling-baselines` добавлен run-kind `g3-2-multi-dataset-strategy`.
3. Реализована логика:
   - классификации datasets по quality tier;
   - назначения ролей dataset-а в обучении;
   - построения training phases;
   - фиксации synthetic-data policy.
4. Сформированы strategy artifacts:
   - `training-strategy-report.json`;
   - `dataset-strategy.csv`;
   - `training-phases.csv`;
   - `training-protocol.md`.
5. Зафиксировано правило:
   - `G-REx` -> `primary_supervision`;
   - `EmoWear` -> `auxiliary_pretraining`;
   - `WESAD` -> `protocol_transfer_or_eval`;
   - `DAPPER` -> `skip`.
6. Synthetic/AI-generated data ограничены режимом `augmentation_only`; они не допускаются как основной supervised source и как основание для финального model selection.

### Измененные файлы

1. `services/modeling-baselines/src/modeling_baselines/multi_dataset.py`
2. `services/modeling-baselines/src/modeling_baselines/main.py`
3. `services/modeling-baselines/tests/test_multi_dataset.py`
4. `services/modeling-baselines/README.md`

### Результат

Multi-dataset линия переведена из режима "смешать все подряд" в режим явной стратегии обучения с разделением datasets по качеству supervision.

### Следующий рекомендуемый шаг

Добавить protocol gate, который проверит readiness фаз перед реальным multi-dataset training loop.

---

## 2026-03-27 - G3.2p - Protocol execution gate и harmonized signal features

### Запрос

Сначала исправить все блокеры multi-dataset линии, а уже потом переходить к обучению.

### Что сделано

1. В `modeling-baselines` добавлен run-kind `g3-2-multi-dataset-protocol`.
2. Реализованы readiness-checks и phase execution status для фаз:
   - `proxy_pretraining`;
   - `real_label_finetune`;
   - `protocol_transfer`;
   - `cross_dataset_evaluation`.
3. Выявлен фактический блокер: отсутствие harmonized non-label signal features в multi-dataset пайплайне.
4. Добавлен harmonized signal feature extraction из raw data для:
   - `WESAD`;
   - `G-REx`;
   - `EmoWear`.
5. Реализованы dataset-specific loaders/adapters внутри `multi_dataset.py`, чтобы readiness считался по реальным signal features, а не по placeholder metadata.
6. Логика protocol gate скорректирована так, чтобы datasets со статусом `skip` не блокировали весь training protocol.
7. После исправлений выполнен реальный protocol execution run; подтверждено:
   - `overall_status = ready`;
   - `blocking_check_count = 0`;
   - `blocking_phase_count = 0`.
8. Подтверждено покрытие harmonized features:
   - `wesad = 80`;
   - `grex = 16`;
   - `emowear = 28`.

### Измененные файлы

1. `services/modeling-baselines/src/modeling_baselines/multi_dataset.py`
2. `services/modeling-baselines/src/modeling_baselines/main.py`
3. `services/modeling-baselines/tests/test_multi_dataset.py`
4. `services/modeling-baselines/README.md`
5. `docs/backend/modeling-g3-2.md`
6. `docs/research/model-validation-repair-plan.md`

### Результат

Multi-dataset training protocol больше не заблокирован инфраструктурно: данные, роли datasets и harmonized signal features готовы к фазовому обучению.

### Следующий рекомендуемый шаг

Запустить контролируемое фазовое обучение: `EmoWear proxy pretraining -> G-REx real-label finetune -> WESAD protocol transfer -> controlled self-training -> cross-dataset evaluation`.

---

## 2026-03-27 - E2.1 - Спецификация Polar H10 feature stack для arousal/valence fusion

### Запрос

Работать по протоколу, изучить реальные возможности `Polar H10`, понять что именно мы можем из него достать и зафиксировать, какие метрики/признаки нужно вычислять для модели `arousal + valence` с ориентиром на связку `Apple Watch + Polar H10`.

### Что сделано

1. Сверены обязательные документы по протоколу:
   - `docs/roadmap/research-pipeline-backend-plan.md`
   - `docs/status/execution-status.md`
   - `docs/status/work-log.md`
   - `docs/research/model-reporting-standard.md`
2. Проверены официальные возможности `Polar H10` по документации Polar:
   - `HR` и `RR` через стандартный поток;
   - `ECG` `130 Hz`;
   - `accelerometer` `25/50/100/200 Hz` с диапазонами `2G/4G/8G`;
   - ограничение internal recording: для `H10` это не замена live `ECG/RR/ACC` потоку и в первую очередь относится к `HR`.
3. Сверена текущая реализация в `on-go/on-go-ios`:
   - raw schema уже предусматривает `polar_ecg`, `polar_rr`, `polar_hr`, `polar_acc`;
   - live adapter сейчас реально пишет `polar_ecg`, `polar_rr`, `polar_hr`, но не `polar_acc`;
   - callback получает `contact/contactSupported`, но они не сохраняются;
   - `signal-processing-worker` считает только baseline-агрегации и один `RR`-derived признак `rr_like__rmssd`.
4. Подготовлен отдельный design-doc по следующему исследовательскому инкременту:
   - какие feature families нужны из `RR/HRV`, `ECG`, `Polar ACC`;
   - какие quality-gates обязательны;
   - какие окна рекомендованы;
   - как разводить вклад `Polar H10` в `arousal` и `valence`.
5. Зафиксирован практический вывод:
   - для `arousal` основной ожидаемый прирост должен идти от полноценного `RR/HRV` стека;
   - для `valence` `Polar H10` полезен, но track должен быть `fusion-first`, с сильной ролью watch-context и baseline-normalized признаков.

### Измененные файлы

1. `docs/backend/signal-processing-e2-1.md`
2. `docs/backend/signal-processing-e2.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`

### Результат

Появилась зафиксированная спецификация для следующего processing/modeling инкремента: теперь ясно, что `Polar H10` реально дает достаточную базу для сильного `arousal` трека и полезного fusion-вклада в `valence`, а главный bottleneck находится в нашем feature extraction, а не в самом датчике.

### Следующий рекомендуемый шаг

`E2.2` — реализовать расширенный `Polar H10` feature stack:

1. live `polar_acc` capture;
2. сохранение `contact/contactSupported`;
3. полноценные `RR/HRV` и `ECG quality` признаки в `signal-processing-worker`;
4. fusion-ready benchmark для `arousal + valence`.

---

## 2026-03-27 - E2.2 - Реализация расширенного Polar H10 RR/ECG/ACC feature extraction

### Запрос

После подтверждения шага `E2.2` реализовать кодом расширенный feature stack для связки `Polar H10 + Apple Watch` под `arousal + valence`.

### Что сделано

1. В `on-go-ios` расширен `LivePolarH10SDKAdapter`:
   - добавлен live `polar_acc` online streaming;
   - добавлен `polar_acc` batch в `drainAccumulatedBatches`;
   - добавлен cleanup/dispose для ACC stream;
   - в HR callback добавлены `contact` и `contact_supported` поля в `polar_hr` samples.
2. В simulated Polar adapter добавлены `polar_acc` samples для start/drain циклов, чтобы тестовый capture-flow не оставался `HR/RR/ECG`-only.
3. В `FileBasedSessionArchiveStore` обновлена схема CSV колонок для `polar_hr`:
   - `hr_bpm`, `contact`, `contact_supported`.
4. В `signal-processing-worker` расширен processing/feature layer:
   - `STREAM_VALUE_LIMITS` для `polar_hr` дополнен `contact/contact_supported`;
   - для RR-like рядов добавлены расширенные признаки `RR/HRV` (`sdnn`, `rmssd`, `sdsd`, `nn20/pnn20`, `nn50/pnn50`, `cvnn/cvsd`, `sd1/sd2`, `mean_hr/hr_min/hr_max`, `iqr/mad`, quality ratios и др.);
   - для `polar_ecg` добавлены quality-признаки (`ecg_coverage_ratio`, `ecg_peak_count`, `ecg_peak_success_ratio`, `ecg_noise_ratio`, `ecg_baseline_wander_score`);
   - для `polar_acc` добавлены motion-признаки (`energy`, `jerk_mean/std`, `stationary_ratio`, `motion_burst_count`).
5. Добавлены unit tests в `signal-processing-worker` на новые feature families:
   - extended RR/HRV;
   - ECG quality;
   - Polar ACC motion features.
6. Обновлена raw schema документация:
   - `polar_hr` теперь описан как `hr_bpm` + optional `contact/contact_supported`.

### Измененные файлы

1. `on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PolarH10Adapter.swift`
2. `on-go-ios/packages/CaptureKit/Sources/CaptureStorage/FileBasedSessionArchiveStore.swift`
3. `services/signal-processing-worker/src/signal_processing_worker/service.py`
4. `services/signal-processing-worker/tests/test_service.py`
5. `docs/research/session-data-schema.md`
6. `docs/backend/signal-processing-e2.md`
7. `docs/backend/signal-processing-e2-2.md`
8. `docs/status/execution-status.md`
9. `docs/status/work-log.md`

### Результат

`E2.2` завершен: code path от capture до feature extraction теперь реально использует более полный сигнал `Polar H10` (ACC + HR contact + расширенный RR/ECG feature layer), что закрывает основной технический bottleneck перед честным fusion benchmark для `arousal + valence`.

### Проверка

1. `cd services/signal-processing-worker && python3 -m pip install -e '.[dev]'`
2. `cd services/signal-processing-worker && python3 -m pytest -q`
3. Результат: `12 passed`

### Следующий рекомендуемый шаг

`E2.3` — запустить fusion-ready benchmark на новом feature stack:

1. `polar_rr_only`;
2. `polar_rr_acc`;
3. `watch_plus_polar_fusion`;
4. comparative report по `arousal + valence` с subject-wise protocol.

---

## 2026-03-27 - E2.2 (addendum) - Расширение HRV-признаков из raw RR

### Запрос

Уточнить и расширить набор вычисляемых метрик из сырых `RR` данных (включая `SDNN` и другие HRV-показатели), чтобы повысить точность модели.

### Что сделано

1. Проверена текущая реализация `signal-processing-worker`: подтверждено, что часть базовых RR/HRV метрик уже была, но отсутствовал расширенный nonlinear/frequency-domain блок.
2. В `service.py` расширен RR feature extraction:
   - добавлены `min/max`, `p10/p90`, `mean_abs_diff`, `median_abs_diff`;
   - добавлены nonlinear-метрики: `triangular_index`, `shannon_entropy`, `sample_entropy_m2_r02`;
   - добавлены frequency-domain метрики: `vlf_power`, `lf_power`, `hf_power`, `lf_hf_ratio`, `lf_nu`, `hf_nu`.
3. Обновлены unit tests для RR-window с проверкой новых ключей признаков.
4. Обновлена документация `E2.2` и статус-файл, чтобы явно зафиксировать расширенный HRV-стек как выполненный.

### Измененные файлы

1. `services/signal-processing-worker/src/signal_processing_worker/service.py`
2. `services/signal-processing-worker/tests/test_service.py`
3. `docs/backend/signal-processing-e2-2.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`

### Результат

RR/HRV ветка стала существенно полнее: теперь помимо базовых time-domain признаков считаются nonlinear и frequency-domain показатели, что убирает предыдущий feature-gap перед `E2.3` benchmark.

### Проверка

1. `cd services/signal-processing-worker && python3 -m pytest -q`
2. Результат: `12 passed`

### Следующий рекомендуемый шаг

`E2.3` — запустить fusion-ready benchmark на обновленном stack (`polar_rr_only`, `polar_rr_acc`, `watch_plus_polar_fusion`) и собрать comparative report для `arousal + valence`.

---

## 2026-03-27 - E2.3 - Fusion-ready benchmark для arousal + valence на расширенном feature stack

### Запрос

После подтверждения запустить следующий шаг `E2.3`: проверить `polar_rr_only`, `polar_rr_acc`, `watch_plus_polar_fusion` и собрать проверяемый comparative report по `arousal + valence`.

### Что сделано

1. В `modeling-baselines` реализован новый run-kind:
   - `e2-3-wesad-polar-watch-benchmark`.
2. Добавлены три постановки benchmark:
   - `polar_rr_only` (ECG proxy features);
   - `polar_rr_acc` (ECG + ACC proxy features);
   - `watch_plus_polar_fusion` (watch + ECG/ACC proxy features).
3. В pipeline добавлен valence-track:
   - `valence_coarse` classification;
   - `valence_ordinal` (exploratory, `mae/spearman_rho/qwk`).
4. Обновлены `SegmentExample` и parsing unified labels:
   - добавлены `valence_score`, `valence_coarse`.
5. Добавлены E2.3-specific артефакты:
   - `evaluation-report.json`
   - `predictions-test.csv`
   - `per-subject-metrics.csv`
   - `model-comparison.csv`
   - `research-report.md`
   - `plots/*`
6. Обновлены тесты `modeling-baselines`; прогон успешен.
7. Выполнен реальный benchmark run на `WESAD`:
   - `experiment_id`: `e2-3-polar-watch-benchmark-20260327T195906Z`.

### Измененные файлы

1. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
2. `services/modeling-baselines/src/modeling_baselines/main.py`
3. `services/modeling-baselines/README.md`
4. `services/modeling-baselines/tests/test_pipeline.py`
5. `services/modeling-baselines/tests/test_audit.py`
6. `docs/status/execution-status.md`
7. `docs/status/work-log.md`

### Результат

`E2.3` завершен: собран первый fusion-ready benchmark для `arousal + valence` с требуемыми вариантами и полной отчетностью. На текущем `WESAD`-прогоне лучшим оказался `watch_plus_polar_fusion` по обоим coarse tracks (`arousal=0.798319`, `valence=1.000000`), при этом valence результат помечается как повышенно рискованный и требует отдельного stress/leakage этапа перед любым сильным claim.

### Проверка

1. `cd services/modeling-baselines && python3 -m pytest -q`
2. Результат: `35 passed`
3. `python3 -m modeling_baselines.main --run-kind e2-3-wesad-polar-watch-benchmark ... --no-mlflow`
4. Артефакты сохранены в:
   - `data/external/wesad/artifacts/wesad/wesad-v1/e2-3-polar-watch-benchmark/`

### Следующий рекомендуемый шаг

`E2.4` — провести stress-test и anti-leakage валидацию E2.3:

1. LOSO/holdout sanity-check для `arousal` и особенно `valence`;
2. проверить устойчивость пер-субъектно и CI;
3. зафиксировать claim-safe решение по winner model.

---

## 2026-03-27 - E2.4 - Stress-test и anti-leakage validation для E2.3

### Запрос

После подтверждения выполнить следующий шаг `E2.4`: проверить устойчивость результатов `E2.3`, особенно по `valence`, и исключить shortcut/leakage эффекты перед выбором финальной модели.

### Что сделано

1. Расширен safety-аудит `modeling-baselines`:
   - `audit.py` дополнен `valence_coarse` coverage и single-feature leakage probe;
   - добавлен `valence_single_feature_shortcut` alert в gate logic.
2. Прогнан реальный `audit-wesad`:
   - `experiment_id`: `audit-wesad-20260327T202858Z`
   - статус: `passed`.
3. Выполнен E2.4 stress-run для E2.3 вариантов:
   - LOSO по субъектам для `polar_rr_only`, `polar_rr_acc`, `watch_plus_polar_fusion`;
   - собраны `loso-fold-metrics.csv` и `loso-summary.csv`.
4. Выполнен permutation sanity-check для `watch_plus_polar_fusion` по `valence`:
   - `40` перестановок train-labels;
   - baseline `valence_macro_f1=1.0` vs permutation mean `0.291319`, max `0.75`, `p_value=0.0`.
5. Подготовлен отдельный backend-док `E2.4` с выводами и ограничениями.

### Измененные файлы

1. `services/modeling-baselines/src/modeling_baselines/audit.py`
2. `services/modeling-baselines/tests/test_audit.py`
3. `docs/backend/signal-processing-e2.md`
4. `docs/backend/signal-processing-e2-4.md`
5. `docs/status/execution-status.md`
6. `docs/status/work-log.md`

### Результат

`E2.4` завершен: blocking leakage-findings не обнаружены, но устойчивость `valence` заметно ниже при строгой LOSO проверке (`mean_macro_f1=0.74254` для fusion вместо `1.0` на одном split), поэтому `valence` остается exploratory и не должен использоваться как production claim-gate.

### Проверка

1. `cd services/modeling-baselines && python3 -m pytest -q`
2. Результат: `35 passed`
3. `python3 -m modeling_baselines.main --run-kind audit-wesad ... --no-mlflow`
4. Дополнительно выполнен E2.4 stress-script с сохранением артефактов в:
   - `data/external/wesad/artifacts/wesad/wesad-v1/e2-4-safety-gate/`

### Следующий рекомендуемый шаг

`E2.5` — claim-safe model selection:

1. зафиксировать production-safe winner по `arousal`;
2. оставить `valence` в exploratory policy;
3. подготовить freeze/deployment кандидаты и границы использования.

---

## 2026-03-27 - E2.5 (planning) - План улучшения valence без собственного датасета

### Запрос

Составить практический план, как улучшить `valence` без создания своего нового датасета.

### Что сделано

1. Подготовлен отдельный execution-plan документ для `valence`:
   - фазовый план `V1..V6`;
   - конкретные gates и минимальные метрики;
   - порядок запуска;
   - обязательный artifact-пакет.
2. План фиксирует ограничения:
   - без нового собственного датасета;
   - external datasets используются контролируемо (`real/proxy` роли);
   - synthetic не используется как primary supervision.
3. В план добавлены критерии claim-safe перехода:
   - LOSO stability;
   - worst-subject guardrail;
   - leakage/permutation sanity.

### Измененные файлы

1. `docs/backend/valence-improvement-plan-no-new-dataset.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`

### Результат

Появился пошаговый и проверяемый план улучшения `valence` без сбора нового датасета, который можно исполнять инкрементами и привязывать к decision gates.

### Следующий рекомендуемый шаг

`E2.5` (execution) — начать с `V1`:

1. детализировать error anatomy по `valence` (subject/class/fold);
2. собрать baseline stability-артефакты для сравнения с последующими фазами.

---

## 2026-03-27 - E2.5.V1 - Valence error anatomy

### Запрос

После подтверждения начать исполнение `E2.5` с подшага `V1`: сделать детальный разбор ошибок `valence` без нового датасета.

### Что сделано

1. Собран V1 artifact-пакет в:
   - `data/external/wesad/artifacts/wesad/wesad-v1/e2-5-valence-v1-error-anatomy/`
2. Подготовлены таблицы:
   - segment-level errors (`valence-error-analysis.csv`);
   - per-subject stability (`valence-subject-stability.csv`);
   - confusion by variant (`valence-confusion-by-variant.csv`);
   - per-class precision/recall (`valence-class-performance.csv`);
   - LOSO summary copy (`valence-loso-summary.csv`).
3. Подготовлен краткий текстовый отчет:
   - `valence-v1-report.md`.
4. Зафиксирован backend-doc подшага:
   - `docs/backend/valence-v1-error-anatomy.md`.

### Измененные файлы

1. `docs/backend/valence-v1-error-anatomy.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`

### Результат

`V1` завершен: подтвержден разрыв между single-split и LOSO устойчивостью для `valence`; определены ключевые зоны ошибок (особенно `neutral/positive` для non-fusion), подготовлена база для `V2` (label quality hardening).

### Следующий рекомендуемый шаг

`E2.5.V2` — Label Quality Hardening:

1. ввести quality tiers для valence labels;
2. добавить weighted policy в обучение;
3. сравнить устойчивость `V2` против `V1` на тех же gate-метриках.

---

## 2026-03-27 - E2.5.V2 - Valence label quality hardening

### Запрос

После подтверждения перейти к `V2`: проверить tiered label policy для улучшения `valence` без новых данных.

### Что сделано

1. Протестированы policy-варианты:
   - `baseline_all_equal`
   - `tiered_extreme_upweight`
   - `tiered_extreme_focus_drop_neutral`
   - `tiered_soft_neutral_downweight`
2. Для каждого E2.3 варианта рассчитаны:
   - holdout `valence_macro_f1` и `valence_qwk`;
   - LOSO fold-метрики и агрегированная сводка.
3. Собран V2 artifact пакет:
   - `policy-comparison-holdout.csv`
   - `policy-comparison-loso-fold.csv`
   - `policy-comparison-loso-summary.csv`
   - `policy-best-by-variant.csv`
   - `v2-report.json`, `v2-report.md`
4. Подготовлен backend-док подшага:
   - `docs/backend/valence-v2-label-hardening.md`.

### Измененные файлы

1. `docs/backend/valence-v2-label-hardening.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`

### Результат

`V2` завершен: label hardening улучшил LOSO `valence` для non-fusion веток (`polar_rr_only`, `polar_rr_acc`), но не улучшил fusion (`watch_plus_polar_fusion`), что указывает на необходимость перехода к feature-level стабилизации (`V3`).

### Следующий рекомендуемый шаг

`E2.5.V3` — Feature stabilization + ablation:

1. baseline-normalized признаки;
2. interaction features (`watch x polar`);
3. LOSO-gated comparison на лучших V2 policy.

---

## 2026-03-27 - E2.5.V3 - Valence feature stabilization + ablation

### Запрос

После подтверждения перейти к `V3`: проверить feature-side стабилизацию `valence` (normalization + interaction features) на лучших policy из `V2`.

### Что сделано

1. Протестированы transform-варианты:
   - `base`
   - `base_plus_norm`
   - `base_plus_norm_interact`
2. Для каждого E2.3 варианта и transform посчитаны:
   - holdout `valence_macro_f1`, `valence_qwk`;
   - LOSO fold-метрики и агрегированная сводка.
3. Собран V3 artifact пакет:
   - `transform-comparison-holdout.csv`
   - `transform-comparison-loso-fold.csv`
   - `transform-comparison-loso-summary.csv`
   - `transform-best-by-variant.csv`
   - `v3-report.json`, `v3-report.md`
4. Подготовлен backend-док подшага:
   - `docs/backend/valence-v3-feature-stabilization.md`.

### Измененные файлы

1. `docs/backend/valence-v3-feature-stabilization.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`

### Результат

`V3` завершен: feature stabilization дал локальное улучшение для `polar_rr_only` (`base_plus_norm`), но для `polar_rr_acc` и `watch_plus_polar_fusion` лучшим остался `base`, поэтому следующий прирост нужно искать в model-layer (`V4` ordinal-first sweep).

### Следующий рекомендуемый шаг

`E2.5.V4` — Ordinal-first model sweep:

1. сравнить model families на лучших `V2/V3` конфигурациях;
2. выбрать winner по комбинированному критерию coarse + ordinal stability;
3. подготовить claim-safe recommendation для `valence`.

---

## 2026-03-27 - E2.5.V4 - Valence ordinal-first model sweep

### Запрос

После подтверждения запустить `V4`: сравнить model families для `valence` на лучших конфигурациях `V2/V3` и выбрать winner-кандидатов по LOSO.

### Что сделано

1. Запущен sweep classifiers:
   - `centroid`, `gaussian_nb`, `logistic_regression`, `ridge_classifier`,
   - `random_forest`, `xgboost`, `lightgbm`, `catboost`.
2. Оценка выполнена на:
   - holdout;
   - LOSO folds.
3. Собраны артефакты:
   - `ordinal-sweep-holdout.csv`
   - `ordinal-sweep-loso-fold.csv`
   - `ordinal-sweep-loso-summary.csv`
   - `ordinal-sweep-best-by-variant.csv`
   - `ordinal-sweep-failed.csv`
   - `v4-report.json`, `v4-report.md`
4. Подготовлен backend-doc подшага:
   - `docs/backend/valence-v4-ordinal-sweep.md`.

### Измененные файлы

1. `docs/backend/valence-v4-ordinal-sweep.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`

### Результат

`V4` завершен: определены winner-кандидаты по LOSO (`polar_rr_only=centroid`, `polar_rr_acc=ridge_classifier`, `watch_plus_polar_fusion=catboost`). Для `lightgbm` в ветке `polar_rr_only` зафиксированы `class coverage` ошибки на части прогонов (отражено в `ordinal-sweep-failed.csv`).

### Следующий рекомендуемый шаг

`E2.5.V5` — Cross-dataset transfer validation:

1. проверить перенос winner-кандидатов за пределами текущего `WESAD`-контекста;
2. подтвердить, что gain по `valence` не локальный split artifact;
3. подготовить финальную claim-safe рекомендацию (`V6`).

---

## 2026-03-27 - E2.5.V5 - Valence cross-dataset transfer validation

### Запрос

После подтверждения выполнить `V5`: проверить переносимость результатов `valence` за пределами `WESAD` и зафиксировать, не является ли прирост локальным split artifact.

### Что сделано

1. Добавлен воспроизводимый скрипт:
   - `scripts/ml/valence_v5_cross_dataset_transfer.py`.
2. Выполнен cross-dataset run:
   - source datasets: `WESAD`, `G-REx`;
   - target datasets: `WESAD`, `G-REx`, `EmoWear`;
   - classifiers: `centroid`, `ridge_classifier`, `catboost`, `xgboost`.
3. Собран V5 artifact пакет:
   - `transfer-matrix.csv`
   - `transfer-summary.csv`
   - `transfer-subject-metrics.csv`
   - `transfer-data-coverage.csv`
   - `transfer-failed.csv`
   - `v5-report.json`, `v5-report.md`
   - `plots/v5-transfer-macro_f1.png`, `plots/v5-transfer-qwk.png`
4. Подготовлен backend-doc подшага:
   - `docs/backend/valence-v5-cross-dataset-transfer.md`.

### Измененные файлы

1. `scripts/ml/valence_v5_cross_dataset_transfer.py`
2. `docs/backend/valence-v5-cross-dataset-transfer.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`

### Результат

`V5` завершен: in-domain `WESAD` качество для `valence` остается высоким, но cross-dataset перенос на `G-REx/EmoWear` заметно слабее, что подтверждает `domain shift` как текущий blocker для claim-grade обобщения. Полных runtime-failures в V5 не зафиксировано.

### Следующий рекомендуемый шаг

`E2.5.V6` — финальная claim-safe рекомендация:

1. зафиксировать production/exploratory границы для `valence`;
2. определить freeze policy и разрешенные claim формулировки;
3. утвердить, какая модель допускается как текущий рабочий кандидат и при каких ограничениях.

---

## 2026-03-27 - E2.5.V6 - Valence claim-safe decision

### Запрос

После подтверждения выполнить `V6`: принять финальное claim-safe решение по `valence` и зафиксировать deployment boundaries.

### Что сделано

1. Сведены результаты `V1-V5` и safety-gates в единое решение:
   - сильный in-domain LOSO на `WESAD` после `V4`;
   - слабый cross-dataset перенос по `V5` как основной blocker.
2. Зафиксировано финальное решение:
   - `valence = exploratory_only` (без продвижения в limited-production).
3. Определены deployment boundaries:
   - confidence gate (`p_max < 0.7` -> `unknown`);
   - запрет user-facing claims только на `valence`;
   - запрет использования `valence` как единственного personalization trigger.
4. Сформирован V6 artifact пакет:
   - `decision-report.json`
   - `model-comparison.csv`
   - `monitoring-kpis.csv`
   - `research-report.md`
   - transfer plots для decision review.
5. Подготовлен backend-doc подшага:
   - `docs/backend/valence-v6-claim-safe-decision.md`.

### Измененные файлы

1. `docs/backend/valence-v6-claim-safe-decision.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-5-valence-v6-claim-safe-decision/decision-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-5-valence-v6-claim-safe-decision/model-comparison.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-5-valence-v6-claim-safe-decision/monitoring-kpis.csv`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-5-valence-v6-claim-safe-decision/research-report.md`

### Результат

`E2.5` завершен: формально принято claim-safe решение оставить `valence` в exploratory policy до прохождения cross-dataset stability gate; зафиксированы границы деплоя, fallback-поведение и KPI-мониторинг.

### Следующий рекомендуемый шаг

`E2.6` — Domain adaptation + calibration для `valence` (без нового датасета):

1. внедрить адаптацию к междатасетному сдвигу;
2. повторить cross-dataset evaluation gate;
3. проверить условия для возможного limited-production promotion.

---

## 2026-03-28 - E2.6 - Valence domain adaptation + calibration

### Запрос

После подтверждения запустить `E2.6`: выполнить инкремент стабилизации переноса `valence` без нового датасета и повторить cross-dataset gate.

### Что сделано

1. Добавлен скрипт:
   - `scripts/ml/valence_e2_6_domain_adaptation.py`.
2. Реализованы режимы:
   - `baseline`,
   - `coral`,
   - `coral_temp`,
   - `coral_temp_gate`.
3. Выполнен cross-dataset rerun (`WESAD/G-REx -> WESAD/G-REx/EmoWear`) и собраны артефакты:
   - `adaptation-matrix.csv`
   - `adaptation-summary.csv`
   - `adaptation-subject-metrics.csv`
   - `calibration-summary.csv`
   - `e2-6-report.json`
   - `research-report.md`
   - `plots/e2-6-transfer-baseline-vs-coral-temp.png`
4. Подготовлен backend-doc шага:
   - `docs/backend/valence-e2-6-domain-adaptation.md`.

### Измененные файлы

1. `scripts/ml/valence_e2_6_domain_adaptation.py`
2. `docs/backend/valence-e2-6-domain-adaptation.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-6-valence-domain-adaptation/adaptation-matrix.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-6-valence-domain-adaptation/adaptation-summary.csv`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-6-valence-domain-adaptation/adaptation-subject-metrics.csv`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-6-valence-domain-adaptation/calibration-summary.csv`
9. `data/external/wesad/artifacts/wesad/wesad-v1/e2-6-valence-domain-adaptation/e2-6-report.json`
10. `data/external/wesad/artifacts/wesad/wesad-v1/e2-6-valence-domain-adaptation/research-report.md`

### Результат

`E2.6` завершен: domain adaptation улучшил cross-dataset перенос для ключевых направлений (`WESAD->G-REx`, `G-REx->WESAD`), но устойчивый promotion floor для всех transfer-направлений еще не достигнут; `valence` остается в exploratory policy.

### Следующий рекомендуемый шаг

`E2.7` — Transfer-robust valence stabilization + re-gate:

1. усилить domain-invariant feature strategy;
2. зафиксировать trusted model subset для transfer-сценариев;
3. повторить cross-dataset gate и пересмотреть promotion boundaries.

---

## 2026-03-28 - E2.7 - Transfer-robust valence stabilization + re-gate

### Запрос

После подтверждения выполнить `E2.7`: усилить transfer-robust стратегию для `valence` и повторно проверить cross-dataset gate.

### Что сделано

1. Добавлен скрипт:
   - `scripts/ml/valence_e2_7_transfer_robust_gate.py`.
2. Реализован pairwise feature filtering по междоменному shift-score.
3. Выполнен re-gate по направлениям `WESAD/G-REx -> WESAD/G-REx/EmoWear`.
4. Добавлен trusted-model критерий:
   - trusted только если `min(WESAD->G-REx, G-REx->WESAD) >= 0.40`.
5. Собран E2.7 artifact пакет:
   - `evaluation-report.json`
   - `model-comparison.csv`
   - `feature-shift-selection.csv`
   - `trusted-models.csv`
   - `research-report.md`
6. Подготовлен backend-doc шага:
   - `docs/backend/valence-e2-7-transfer-robust-regate.md`.

### Измененные файлы

1. `scripts/ml/valence_e2_7_transfer_robust_gate.py`
2. `docs/backend/valence-e2-7-transfer-robust-regate.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-7-valence-transfer-robust-regate/evaluation-report.json`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-7-valence-transfer-robust-regate/model-comparison.csv`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-7-valence-transfer-robust-regate/feature-shift-selection.csv`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-7-valence-transfer-robust-regate/trusted-models.csv`
9. `data/external/wesad/artifacts/wesad/wesad-v1/e2-7-valence-transfer-robust-regate/research-report.md`

### Результат

`E2.7` завершен: trusted-model subset не сформирован (все кандидаты ниже trusted-floor на `WESAD->G-REx`), поэтому итоговый decision сохранен как `keep_exploratory`.

### Следующий рекомендуемый шаг

`E2.8` — Hybrid transfer adaptation (`CORAL + soft reweighting`) + re-gate:

1. заменить жесткое отсечение признаков на мягкое reweighting;
2. удержать приросты `E2.6` и уменьшить деградацию transfer-направлений;
3. повторить primary transfer gate для возможного пересмотра promotion policy.

---

## 2026-03-28 - E2.8 - Hybrid transfer adaptation + re-gate

### Запрос

После подтверждения выполнить `E2.8`: запустить гибридную стратегию (`CORAL + soft reweighting`) и повторно проверить trusted-model gate.

### Что сделано

1. Добавлен скрипт:
   - `scripts/ml/valence_e2_8_hybrid_transfer.py`.
2. Реализован гибридный режим:
   - soft reweighting признаков по междоменному shift;
   - `CORAL` в reweighted пространстве.
3. Выполнен re-gate на направлениях `WESAD/G-REx -> WESAD/G-REx/EmoWear`.
4. Собран E2.8 artifact пакет:
   - `evaluation-report.json`
   - `model-comparison.csv`
   - `soft-weights-summary.csv`
   - `trusted-models.csv`
   - `research-report.md`
5. Подготовлен backend-doc шага:
   - `docs/backend/valence-e2-8-hybrid-transfer-regate.md`.

### Измененные файлы

1. `scripts/ml/valence_e2_8_hybrid_transfer.py`
2. `docs/backend/valence-e2-8-hybrid-transfer-regate.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-8-valence-hybrid-transfer-regate/evaluation-report.json`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-8-valence-hybrid-transfer-regate/model-comparison.csv`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-8-valence-hybrid-transfer-regate/soft-weights-summary.csv`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-8-valence-hybrid-transfer-regate/trusted-models.csv`
9. `data/external/wesad/artifacts/wesad/wesad-v1/e2-8-valence-hybrid-transfer-regate/research-report.md`

### Результат

`E2.8` завершен: гибридный подход улучшил часть directional-переходов относительно `E2.7`, но trusted subset по двунаправленному критерию (`min_cross >= 0.40`) не сформирован; итоговый decision остается `keep_exploratory`.

### Следующий рекомендуемый шаг

`E2.9` — Direction-specific transfer policy + gate sensitivity:

1. выполнить sensitivity-анализ trusted-floor (`0.35/0.38/0.40`);
2. определить допустимый scoped режим для direction-specific promotion без user-facing claims;
3. зафиксировать итоговую policy-матрицу для `valence`.

---

## 2026-03-28 - E2.9 - Direction-specific transfer policy + gate sensitivity

### Запрос

После подтверждения выполнить `E2.9`: посчитать sensitivity trusted-floor и зафиксировать direction-specific policy-матрицу для `valence`.

### Что сделано

1. Добавлен скрипт:
   - `scripts/ml/valence_e2_9_policy_sensitivity.py`.
2. Проведен анализ по floors:
   - `0.35`, `0.38`, `0.40`.
3. Сформированы артефакты:
   - `sensitivity-summary.csv`
   - `direction-policy-matrix.csv`
   - `evaluation-report.json`
   - `research-report.md`
4. Подготовлен backend-doc шага:
   - `docs/backend/valence-e2-9-policy-sensitivity.md`.

### Измененные файлы

1. `scripts/ml/valence_e2_9_policy_sensitivity.py`
2. `docs/backend/valence-e2-9-policy-sensitivity.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-9-valence-policy-sensitivity/evaluation-report.json`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-9-valence-policy-sensitivity/sensitivity-summary.csv`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-9-valence-policy-sensitivity/direction-policy-matrix.csv`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-9-valence-policy-sensitivity/research-report.md`

### Результат

`E2.9` завершен: глобальный decision сохраняется `keep_exploratory`; sensitivity показал, что bidirectional scoped internal-кандидат возможен только для `ridge` при floor `0.35`, без user-facing claims.

### Следующий рекомендуемый шаг

`E2.10` — Scoped valence policy operational hardening:

1. добавить contract/runtime guardrails для scoped режима;
2. зафиксировать monitoring + rollback триггеры;
3. подготовить операционный decision gate на включение scoped режима.

---

## 2026-03-28 - E2.10 - Scoped valence policy operational hardening

### Запрос

После подтверждения выполнить `E2.10`: зафиксировать operational policy для scoped режима `valence`, включая guardrails, monitoring и rollback.

### Что сделано

1. Добавлен новый контракт:
   - `contracts/personalization/valence-scoped-policy.schema.json`.
2. Добавлен gate-скрипт:
   - `scripts/ml/valence_e2_10_operational_gate.py`.
3. Сформирован E2.10 operational пакет:
   - `scoped-policy.json`
   - `evaluation-report.json`
   - `monitoring-kpis.csv`
   - `rollback-triggers.csv`
   - `research-report.md`
4. Добавлен runbook:
   - `docs/operations/valence-scoped-policy-runbook.md`.
5. Подготовлен backend-doc шага:
   - `docs/backend/valence-e2-10-operational-hardening.md`.

### Измененные файлы

1. `contracts/personalization/valence-scoped-policy.schema.json`
2. `contracts/personalization/README.md`
3. `scripts/ml/valence_e2_10_operational_gate.py`
4. `docs/operations/valence-scoped-policy-runbook.md`
5. `docs/backend/valence-e2-10-operational-hardening.md`
6. `docs/status/execution-status.md`
7. `docs/status/work-log.md`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/scoped-policy.json`
9. `data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/evaluation-report.json`
10. `data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/monitoring-kpis.csv`
11. `data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/rollback-triggers.csv`
12. `data/external/wesad/artifacts/wesad/wesad-v1/e2-10-valence-operational-gate/research-report.md`

### Результат

`E2.10` завершен: policy переведена в управляемый operational режим (`internal_scoped`), с явными non-user-facing ограничениями, KPI мониторингом и rollback-триггерами.

### Следующий рекомендуемый шаг

`E2.11` — Scoped mode runtime integration:

1. внедрить policy loader и флаги режима в runtime/inference контур;
2. добавить hard guardrails в API слой;
3. выполнить dry-run переключения `disabled <-> internal_scoped`.

---

## 2026-03-28 - E2.11 - Scoped mode runtime integration

### Запрос

После подтверждения выполнить `E2.11`: интегрировать scoped `valence` policy в runtime/inference контур и проверить режимы `disabled <-> internal_scoped` в dry-run.

### Что сделано

1. В `inference-api` добавлена загрузка policy из `INFERENCE_VALENCE_SCOPED_POLICY_PATH`.
2. Расширен runtime API:
   - `GET /health` возвращает `valence_policy_loaded` и `valence_mode`;
   - добавлен `GET /v1/policy/valence-scoped`;
   - `POST /v1/predict` принимает `X-On-Go-Context` и возвращает `valence_scoped_status`.
3. Добавлены hard guardrails для `valence` scoped режима:
   - allowlist контекстов,
   - non-user-facing ограничения,
   - reason-code для block/degrade состояний.
4. Обновлены API contracts и docs:
   - `contracts/http/inference-api.openapi.yaml`;
   - `services/inference-api/README.md`.
5. Добавлен dry-run скрипт и получены артефакты:
   - `scripts/ml/valence_e2_11_runtime_dryrun.py`;
   - `e2-11-runtime-dryrun/dryrun-mode-matrix.csv`, `dryrun-report.json`, `dryrun-report.md`.
6. Подготовлен backend-doc шага:
   - `docs/backend/valence-e2-11-runtime-integration.md`.

### Измененные файлы

1. `services/inference-api/src/inference_api/models.py`
2. `services/inference-api/src/inference_api/config.py`
3. `services/inference-api/src/inference_api/api.py`
4. `contracts/http/inference-api.openapi.yaml`
5. `services/inference-api/README.md`
6. `scripts/ml/valence_e2_11_runtime_dryrun.py`
7. `docs/backend/valence-e2-11-runtime-integration.md`
8. `docs/status/execution-status.md`
9. `docs/status/work-log.md`
10. `data/external/wesad/artifacts/wesad/wesad-v1/e2-11-runtime-dryrun/dryrun-mode-matrix.csv`
11. `data/external/wesad/artifacts/wesad/wesad-v1/e2-11-runtime-dryrun/dryrun-report.json`
12. `data/external/wesad/artifacts/wesad/wesad-v1/e2-11-runtime-dryrun/dryrun-report.md`

### Результат

`E2.11` завершен: runtime scoped policy интегрирована, в `internal_scoped` разрешены только `research_only/internal_dashboard/shadow_mode`, `public_app` блокируется; user-facing claims по `valence` остаются запрещены.

### Следующий рекомендуемый шаг

`E2.12` — Scoped mode shadow-cycle evaluation:

1. прогнать серию shadow/replay циклов с runtime policy;
2. проверить monitoring KPI и rollback-триггеры на реальных метриках;
3. принять операционное решение: оставить scoped режим или откатить.

---

## 2026-03-28 - E2.12 - Scoped mode shadow-cycle evaluation

### Запрос

После подтверждения выполнить `E2.12`: прогнать shadow-cycle оценку scoped `valence` режима, проверить rollback-триггеры и принять операционное решение.

### Что сделано

1. Добавлен скрипт:
   - `scripts/ml/valence_e2_12_shadow_cycle_evaluation.py`.
2. Выполнена оценка `5` shadow-циклов на основе артефактов `E2.9/E2.10/E2.11`:
   - `wesad_to_grex_macro_f1`
   - `grex_to_wesad_macro_f1`
   - `unknown_rate_after_gate`
   - `prediction_volume_daily`
3. Выполнена rollback-проверка по всем условиям из `rollback-triggers.csv` для каждого цикла.
4. Подтвержден context gate:
   - allowed: `research_only/internal_dashboard/shadow_mode`;
   - blocked: `public_app`.
5. Сформирован E2.12 artifact пакет и backend-doc шага:
   - `docs/backend/valence-e2-12-shadow-cycle-evaluation.md`.

### Измененные файлы

1. `scripts/ml/valence_e2_12_shadow_cycle_evaluation.py`
2. `docs/backend/valence-e2-12-shadow-cycle-evaluation.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-12-valence-shadow-cycle-evaluation/evaluation-report.json`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-12-valence-shadow-cycle-evaluation/shadow-cycle-metrics.csv`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-12-valence-shadow-cycle-evaluation/rollback-check-results.csv`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-12-valence-shadow-cycle-evaluation/research-report.md`

### Результат

`E2.12` завершен: rollback triggers не сработали ни в одном цикле; scoped `valence` режим сохраняется как `internal_scoped` с блокировкой `public_app`.

### Следующий рекомендуемый шаг

`E2.13` — Scoped mode canary hardening:

1. автоматизировать периодический пересчет rollback KPI;
2. подключить alerting и auto-disable флаг при trigger-событиях;
3. сформировать canary readiness checklist для controlled internal rollout.

---

## 2026-03-28 - E2.13 - Scoped mode canary hardening

### Запрос

После подтверждения выполнить `E2.13`: автоматизировать периодические runtime-checks, alerting и auto-disable по rollback-условиям.

### Что сделано

1. Добавлен canary скрипт:
   - `scripts/ml/valence_e2_13_canary_hardening.py`.
2. Сформирован artifact bundle `E2.13`:
   - `canary-state.json` (auto-disable/effective-mode state),
   - `alerts.json`,
   - `canary-trigger-results.csv`,
   - `canary-readiness-checklist.csv`,
   - `evaluation-report.json`,
   - `research-report.md`.
3. Выполнена runtime интеграция в `inference-api`:
   - новый env: `INFERENCE_VALENCE_CANARY_STATE_PATH`,
   - `auto_disable/effective_mode_override` влияют на effective `valence` mode,
   - расширены `GET /health` и `GET /v1/policy/valence-scoped`.
4. Обновлены контракт и документация:
   - `contracts/http/inference-api.openapi.yaml`,
   - `services/inference-api/README.md`,
   - `docs/operations/valence-scoped-policy-runbook.md`,
   - `docs/backend/valence-e2-13-canary-hardening.md`.
5. Проверки:
   - `python3 -m py_compile` для `inference-api` и `E2.13` скрипта;
   - smoke check загрузки canary-state и расчета effective-mode (`internal_scoped` при `auto_disable=false`).

### Измененные файлы

1. `scripts/ml/valence_e2_13_canary_hardening.py`
2. `services/inference-api/src/inference_api/config.py`
3. `services/inference-api/src/inference_api/models.py`
4. `services/inference-api/src/inference_api/api.py`
5. `contracts/http/inference-api.openapi.yaml`
6. `services/inference-api/README.md`
7. `docs/operations/valence-scoped-policy-runbook.md`
8. `docs/backend/valence-e2-13-canary-hardening.md`
9. `docs/status/execution-status.md`
10. `docs/status/work-log.md`
11. `data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/evaluation-report.json`
12. `data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/canary-state.json`
13. `data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/alerts.json`
14. `data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/canary-trigger-results.csv`
15. `data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/canary-readiness-checklist.csv`
16. `data/external/wesad/artifacts/wesad/wesad-v1/e2-13-valence-canary-hardening/research-report.md`

### Результат

`E2.13` завершен: canary-loop автоматизирован, alerting подключен, а runtime теперь поддерживает принудительный `auto-disable` scoped режима через отдельный state-файл без изменения основной policy.

### Следующий рекомендуемый шаг

`E2.14` — Canary drill and rollback simulation:

1. провести forced rollback drill с искусственным trigger-событием;
2. подтвердить переход runtime в `disabled` через canary-state;
3. зафиксировать recovery-процедуру и SLA на возврат в `internal_scoped`.

---

## 2026-03-28 - E2.14 - Canary drill and rollback simulation

### Запрос

После подтверждения выполнить `E2.14`: провести forced rollback drill, подтвердить runtime auto-disable и зафиксировать recovery/SLA.

### Что сделано

1. Добавлен drill-скрипт:
   - `scripts/ml/valence_e2_14_canary_drill.py`.
2. Выполнен controlled forced-trigger сценарий:
   - на последнем цикле искусственно нарушены rollback-пороги,
   - сформированы `drill-shadow-cycle-metrics.csv` и `drill-trigger-results.csv`.
3. Сформирован drill canary-state:
   - `drill-canary-state.json` с `auto_disable=true` и `effective_mode_override=disabled`,
   - `drill-alerts.json` с trigger-событиями.
4. Подтвержден runtime rollback-path через `inference-api` helpers:
   - baseline effective mode: `internal_scoped`,
   - drill effective mode: `disabled`.
5. Зафиксированы recovery procedure и SLA:
   - `recovery-sla.json`, `target_rto_minutes=80`.
6. Добавлены backend-док и обновление operations runbook:
   - `docs/backend/valence-e2-14-canary-drill.md`,
   - `docs/operations/valence-scoped-policy-runbook.md`.

### Измененные файлы

1. `scripts/ml/valence_e2_14_canary_drill.py`
2. `docs/backend/valence-e2-14-canary-drill.md`
3. `docs/operations/valence-scoped-policy-runbook.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-14-valence-canary-drill/evaluation-report.json`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-14-valence-canary-drill/runtime-drill-confirmation.json`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-14-valence-canary-drill/drill-canary-state.json`
9. `data/external/wesad/artifacts/wesad/wesad-v1/e2-14-valence-canary-drill/drill-alerts.json`
10. `data/external/wesad/artifacts/wesad/wesad-v1/e2-14-valence-canary-drill/drill-shadow-cycle-metrics.csv`
11. `data/external/wesad/artifacts/wesad/wesad-v1/e2-14-valence-canary-drill/drill-trigger-results.csv`
12. `data/external/wesad/artifacts/wesad/wesad-v1/e2-14-valence-canary-drill/recovery-sla.json`
13. `data/external/wesad/artifacts/wesad/wesad-v1/e2-14-valence-canary-drill/research-report.md`

### Результат

`E2.14` завершен: rollback-path подтвержден (`rollback_path_confirmed`) и runtime корректно уходит в `disabled` при trigger-событиях; recovery/SLA зафиксированы в операционных артефактах.

### Следующий рекомендуемый шаг

`E2.15` — Canary scheduler and dashboard contract:

1. добавить scheduler wiring для регулярного запуска canary-check job;
2. зафиксировать dashboard-friendly snapshot contract (`state + alerts + rollup`);
3. подготовить acceptance checklist для continuous internal rollout.

---

## 2026-03-28 - E2.15 - Canary scheduler and dashboard contract

### Запрос

После подтверждения выполнить `E2.15`: добавить scheduler wiring, dashboard snapshot contract и acceptance checklist.

### Что сделано

1. Добавлен dashboard schema contract:
   - `contracts/operations/valence-canary-dashboard.schema.json`.
2. Добавлен скрипт сборки scheduler/dashboard артефактов:
   - `scripts/ml/valence_e2_15_scheduler_dashboard.py`.
3. Реализован scheduler wiring в трех вариантах:
   - GitHub Actions: `.github/workflows/valence-canary-check.yml` (hourly + manual),
   - cron: `infra/ops/valence-canary/cron/valence-canary-check.cron`,
   - systemd: `infra/ops/valence-canary/systemd/valence-canary-check.service` + `.timer`.
4. Сформирован artifact bundle `E2.15`:
   - `dashboard-snapshot.json`,
   - `scheduler-spec.json`,
   - `acceptance-checklist.csv`,
   - `evaluation-report.json`,
   - `research-report.md`.
5. Добавлены документы:
   - `docs/backend/valence-e2-15-scheduler-dashboard.md`,
   - `docs/operations/valence-canary-scheduler.md`.
6. Обновлены индексы документации:
   - `contracts/README.md`,
   - `.github/workflows/README.md`.

### Измененные файлы

1. `contracts/operations/valence-canary-dashboard.schema.json`
2. `contracts/README.md`
3. `scripts/ml/valence_e2_15_scheduler_dashboard.py`
4. `.github/workflows/valence-canary-check.yml`
5. `.github/workflows/README.md`
6. `infra/ops/valence-canary/cron/valence-canary-check.cron`
7. `infra/ops/valence-canary/systemd/valence-canary-check.service`
8. `infra/ops/valence-canary/systemd/valence-canary-check.timer`
9. `docs/backend/valence-e2-15-scheduler-dashboard.md`
10. `docs/operations/valence-canary-scheduler.md`
11. `docs/status/execution-status.md`
12. `docs/status/work-log.md`
13. `data/external/wesad/artifacts/wesad/wesad-v1/e2-15-valence-scheduler-dashboard/evaluation-report.json`
14. `data/external/wesad/artifacts/wesad/wesad-v1/e2-15-valence-scheduler-dashboard/dashboard-snapshot.json`
15. `data/external/wesad/artifacts/wesad/wesad-v1/e2-15-valence-scheduler-dashboard/scheduler-spec.json`
16. `data/external/wesad/artifacts/wesad/wesad-v1/e2-15-valence-scheduler-dashboard/acceptance-checklist.csv`
17. `data/external/wesad/artifacts/wesad/wesad-v1/e2-15-valence-scheduler-dashboard/research-report.md`

### Результат

`E2.15` завершен: scheduler wiring и dashboard contract формализованы; acceptance checklist пройден полностью (`6/6`), статус readiness — `ready`.

### Следующий рекомендуемый шаг

`E2.16` — Runtime dashboard endpoint integration:

1. добавить runtime endpoint для отдачи dashboard snapshot;
2. подключить schema-check для snapshot в CI;
3. зафиксировать SLO по freshness dashboard данных.

---

## 2026-03-28 - E2.16 - Runtime dashboard endpoint integration

### Запрос

После подтверждения выполнить `E2.16`: добавить runtime dashboard endpoint, schema-check в CI и зафиксировать freshness SLO.

### Что сделано

1. В `inference-api` добавлен новый monitoring endpoint:
   - `GET /v1/monitoring/valence-canary`.
2. Расширена конфигурация runtime:
   - `INFERENCE_VALENCE_DASHBOARD_SNAPSHOT_PATH`,
   - `INFERENCE_VALENCE_DASHBOARD_FRESHNESS_SLO_MINUTES`.
3. В `GET /health` добавлены индикаторы dashboard-состояния:
   - `valence_dashboard_snapshot_loaded`,
   - `valence_dashboard_fresh`.
4. Обновлены контракт и docs inference-api:
   - `contracts/http/inference-api.openapi.yaml`,
   - `services/inference-api/README.md`.
5. Добавлен CI schema-check:
   - `scripts/contracts/validate_valence_canary_snapshot.py`,
   - новый job `contract-checks` в `.github/workflows/ci.yml`.
6. Добавлен пример snapshot для schema validation:
   - `contracts/operations/examples/valence-canary-dashboard.example.json`.
7. Выполнен dry-run runtime endpoint behavior:
   - `scripts/ml/valence_e2_16_runtime_dashboard_dryrun.py`,
   - сформирован `e2-16-runtime-dashboard-endpoint` artifact bundle.
8. Добавлены backend/operations docs:
   - `docs/backend/valence-e2-16-runtime-dashboard-endpoint.md`,
   - обновлен `docs/operations/valence-scoped-policy-runbook.md`.

### Измененные файлы

1. `services/inference-api/src/inference_api/config.py`
2. `services/inference-api/src/inference_api/models.py`
3. `services/inference-api/src/inference_api/api.py`
4. `contracts/http/inference-api.openapi.yaml`
5. `services/inference-api/README.md`
6. `contracts/operations/examples/valence-canary-dashboard.example.json`
7. `scripts/contracts/validate_valence_canary_snapshot.py`
8. `.github/workflows/ci.yml`
9. `.github/workflows/README.md`
10. `scripts/ml/valence_e2_16_runtime_dashboard_dryrun.py`
11. `docs/backend/valence-e2-16-runtime-dashboard-endpoint.md`
12. `docs/operations/valence-scoped-policy-runbook.md`
13. `docs/status/execution-status.md`
14. `docs/status/work-log.md`
15. `data/external/wesad/artifacts/wesad/wesad-v1/e2-16-runtime-dashboard-endpoint/evaluation-report.json`
16. `data/external/wesad/artifacts/wesad/wesad-v1/e2-16-runtime-dashboard-endpoint/runtime-dashboard-response.json`
17. `data/external/wesad/artifacts/wesad/wesad-v1/e2-16-runtime-dashboard-endpoint/research-report.md`

### Результат

`E2.16` завершен: runtime endpoint для canary dashboard интегрирован, freshness SLO учитывается в health, а snapshot contract валидируется в CI.

### Следующий рекомендуемый шаг

`E2.17` — End-to-end canary observability drill:

1. прогнать полный e2e цикл scheduler -> canary-state -> runtime endpoint;
2. проверить совместно runtime freshness + CI contract-check + artifacts;
3. зафиксировать operational sign-off checklist для continuous режима.

---

## 2026-03-28 - E2.17 - End-to-end canary observability drill

### Запрос

После подтверждения выполнить `E2.17`: провести e2e observability drill и оформить operational sign-off.

### Что сделано

1. Добавлен e2e orchestration-скрипт:
   - `scripts/ml/valence_e2_17_observability_drill.py`.
2. В одном цикле выполнены:
   - `scripts/ml/valence_e2_13_canary_hardening.py`,
   - `scripts/ml/valence_e2_15_scheduler_dashboard.py`,
   - `scripts/contracts/validate_valence_canary_snapshot.py`.
3. Подтверждена runtime-consistency:
   - `effective_mode` в runtime и snapshot совпадают (`internal_scoped`),
   - freshness проходит по SLO (`120` минут).
4. Сформирован sign-off bundle:
   - `evaluation-report.json`,
   - `signoff-checklist.csv`,
   - `scheduler-run-log.json`,
   - `runtime-endpoint-response.json`,
   - `research-report.md`.
5. Добавлены docs:
   - `docs/backend/valence-e2-17-observability-drill.md`,
   - `docs/operations/valence-canary-operational-signoff.md`.

### Измененные файлы

1. `scripts/ml/valence_e2_17_observability_drill.py`
2. `docs/backend/valence-e2-17-observability-drill.md`
3. `docs/operations/valence-canary-operational-signoff.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-17-end-to-end-canary-observability/evaluation-report.json`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-17-end-to-end-canary-observability/signoff-checklist.csv`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-17-end-to-end-canary-observability/scheduler-run-log.json`
9. `data/external/wesad/artifacts/wesad/wesad-v1/e2-17-end-to-end-canary-observability/runtime-endpoint-response.json`
10. `data/external/wesad/artifacts/wesad/wesad-v1/e2-17-end-to-end-canary-observability/research-report.md`

### Результат

`E2.17` завершен: полный e2e observability-контур подтвержден, operational sign-off получен (`7/7`, `operational_signoff_ready`).

### Следующий рекомендуемый шаг

`E2.18` — Continuous-run burn-in:

1. выполнить серию последовательных scheduler-циклов (`>=3`) без ручных правок;
2. проверить стабильность freshness/alerts/effective-mode по каждому циклу;
3. оформить итоговый burn-in decision gate.

---

## 2026-03-28 - E2.18 - Continuous-run burn-in

### Запрос

После подтверждения выполнить `E2.18`: прогнать continuous-run burn-in и зафиксировать итоговый decision gate.

### Что сделано

1. Добавлен burn-in скрипт:
   - `scripts/ml/valence_e2_18_continuous_burnin.py`.
2. Выполнены `3` последовательных цикла без ручных правок:
   - `E2.13` canary check,
   - `E2.15` dashboard refresh,
   - contract check (`validate_valence_canary_snapshot.py`).
3. Для каждого цикла проверены:
   - `effective_mode`,
   - `auto_disable`,
   - `alerts_count`,
   - `dashboard_fresh`,
   - успешность шагов pipeline.
4. Сформирован decision gate:
   - `burnin-decision-gate.json`.
5. Добавлены backend/operations обновления:
   - `docs/backend/valence-e2-18-continuous-burnin.md`,
   - обновление `docs/operations/valence-canary-operational-signoff.md`.

### Измененные файлы

1. `scripts/ml/valence_e2_18_continuous_burnin.py`
2. `docs/backend/valence-e2-18-continuous-burnin.md`
3. `docs/operations/valence-canary-operational-signoff.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-18-continuous-run-burnin/evaluation-report.json`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-18-continuous-run-burnin/burnin-decision-gate.json`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-18-continuous-run-burnin/burnin-cycle-summary.csv`
9. `data/external/wesad/artifacts/wesad/wesad-v1/e2-18-continuous-run-burnin/burnin-step-log.csv`
10. `data/external/wesad/artifacts/wesad/wesad-v1/e2-18-continuous-run-burnin/research-report.md`

### Результат

`E2.18` завершен: burn-in выполнен успешно (`3/3` pass), итоговый decision gate — `burnin_passed`.

### Следующий рекомендуемый шаг

`E2.19` — Long-horizon canary monitoring pack:

1. добавить weekly summary aggregation по canary истории;
2. подготовить incident template для rollback/auto-disable сценариев;
3. сформировать эксплуатационный handoff пакет для длительного monitoring-режима.

---

## 2026-03-28 - K5.0 - State semantics and derived-state rollout planning

### Запрос

После сверки статуса разложить в задачи, как система должна определять состояние пользователя: `покой/движение`, `arousal`, guarded `valence` и итоговый product-facing state без ложных emotional claims.

### Что сделано

1. Сверены текущие roadmap/status/runtime артефакты:
   - `inference-api`,
   - `live-inference-api`,
   - scoped `valence` policy,
   - production architecture.
2. Зафиксирован отдельный planning document:
   - `docs/backend/state-semantics-derived-state-plan.md`.
3. Определено разделение на:
   - direct outputs: `activity`, `arousal_coarse`, scoped `valence_coarse`;
   - derived outputs: `derived_state`, `confidence`, `fallback_reason`, `claim_level`.
4. Зафиксирована предварительная canonical taxonomy для product-facing state:
   - `calm_rest`,
   - `active_movement`,
   - `physical_load`,
   - `possible_stress`,
   - `positive_activation`,
   - `negative_activation`,
   - `uncertain_state`.
5. Разложен новый production track `K5.1-K5.5`:
   - contract,
   - API semantics,
   - runtime implementation,
   - evaluation,
   - wording/exposure policy.
6. Обновлены roadmap и production architecture, чтобы semantic layer был зафиксирован как отдельная часть фазы `K`.
7. Обновлен execution status:
   - `E2.19` переведен в `pending`;
   - следующим шагом выставлен `K5.1`.

### Измененные файлы

1. `docs/roadmap/research-pipeline-backend-plan.md`
2. `docs/architecture/production-backend.md`
3. `docs/backend/state-semantics-derived-state-plan.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`

### Результат

Появился отдельный зафиксированный трек, который переводит вопрос "как определять эмоции и состояние человека" в управляемую реализацию через `activity/arousal/scoped valence -> derived_state`, с явными `unknown/fallback` правилами и без необоснованных product claims.

### Следующий рекомендуемый шаг

`K5.1 - State semantics and derived-state contract`

1. зафиксировать каноническую taxonomy direct и derived outputs;
2. подготовить decision table `activity/arousal/valence -> derived_state`;
3. определить `unknown`, `uncertain_state`, `fallback_reason` и claim boundaries.

---

## 2026-03-28 - K5.1 - State semantics and derived-state contract

### Запрос

После подтверждения выполнить `K5.1`: зафиксировать canonical direct/derived taxonomy, decision table `activity/arousal/valence -> derived_state`, правила `unknown/fallback` и claim boundaries.

### Что сделано

1. Подготовлен отдельный contract-документ semantic layer:
   - `docs/backend/state-semantics-derived-state-contract.md`.
2. Зафиксированы canonical direct outputs:
   - `activity_class`,
   - `arousal_coarse`,
   - `valence_coarse` (только при passed scoped policy).
3. Зафиксированы canonical derived outputs:
   - `derived_state`,
   - `claim_level`,
   - `fallback_reason`,
   - `confidence`.
4. Добавлена decision table с приоритетными правилами `R1-R10`:
   - explicit mapping в `calm_rest/active_movement/physical_load/possible_stress/positive_activation/negative_activation/uncertain_state`.
5. Зафиксированы правила разделения `unknown` (direct outputs) и `uncertain_state` (derived output), а также claim boundaries (`safe/guarded/internal_only/no_claim`) и non-claim language baseline.
6. Добавлен machine-readable schema draft:
   - `contracts/operations/derived-state-semantics.schema.json`.
7. Обновлены индекс контрактов и production architecture, чтобы K5.1 artifacts были частью canonical references.
8. Обновлен execution status:
   - `K5.1` -> `completed`,
   - `K5.2` -> `next`.

### Измененные файлы

1. `docs/backend/state-semantics-derived-state-contract.md`
2. `contracts/operations/derived-state-semantics.schema.json`
3. `contracts/README.md`
4. `docs/architecture/production-backend.md`
5. `docs/status/execution-status.md`
6. `docs/status/work-log.md`

### Результат

`K5.1` завершен: semantic contract для derived-state formalized, decision table и fallback/claim policy зафиксированы, подготовлен schema baseline для перехода к API/WS контрактам шага `K5.2`.

### Следующий рекомендуемый шаг

`K5.2 - Inference and live API semantic response contract`:

1. обновить `inference-api` OpenAPI (`/v1/predict`) под canonical semantic поля;
2. обновить `live-inference-api` WS response shape теми же полями;
3. добавить contract examples и синхронизировать README сервисов.

---

## 2026-03-28 - K5.2 - Inference and live API semantic response contract

### Запрос

После подтверждения выполнить `K5.2`: обновить HTTP/WS контракты под canonical semantic response (`derived_state`, `confidence`, `fallback_reason`, `claim_level`) и синхронизировать сервисную документацию.

### Что сделано

1. Обновлен `inference-api` OpenAPI-контракт:
   - `PredictResponse` расширен canonical semantic полями:
     - `activity_class`,
     - `valence_coarse`,
     - `derived_state`,
     - `confidence`,
     - `fallback_reason`,
     - `claim_level`;
   - legacy `activity` сохранен как `deprecated`.
2. Обновлен `live-inference-api` OpenAPI-контракт:
   - формализован WS message contract через `x-websocket-messages`;
   - добавлен `LiveInferenceMessage` с тем же canonical semantic shape, что и в `inference-api`.
3. Синхронизированы README сервисов:
   - `services/inference-api/README.md`,
   - `services/live-inference-api/README.md`;
   - добавлены обновленные response/message примеры с semantic fields.
4. Добавлены machine-readable examples для интеграций:
   - `contracts/operations/examples/inference-semantic-response.example.json`,
   - `contracts/operations/examples/live-inference-semantic-message.example.json`.
5. Обновлен индекс контрактов `contracts/README.md` с ссылками на новые examples.
6. Обновлен execution status:
   - `K5.2` -> `completed`,
   - `K5.3` -> `next`.

### Измененные файлы

1. `contracts/http/inference-api.openapi.yaml`
2. `contracts/http/live-inference-api.openapi.yaml`
3. `services/inference-api/README.md`
4. `services/live-inference-api/README.md`
5. `contracts/operations/examples/inference-semantic-response.example.json`
6. `contracts/operations/examples/live-inference-semantic-message.example.json`
7. `contracts/README.md`
8. `docs/status/execution-status.md`
9. `docs/status/work-log.md`

### Результат

`K5.2` завершен: контракты `inference-api` и `live-inference-api` синхронизированы с canonical semantic response из `K5.1`; интеграционный слой получил единый schema-first baseline для runtime-реализации шага `K5.3`.

### Следующий рекомендуемый шаг

`K5.3 - Runtime derived-state layer implementation`:

1. реализовать mapping layer в runtime (`activity/arousal/valence -> derived_state`);
2. добавить вычисление `confidence`, `fallback_reason`, `claim_level` в API/WS ответах;
3. добавить unit-тесты на mapping/fallback behavior и блокировку недопустимых claim contexts.

---

## 2026-03-28 - K5.3 - Runtime derived-state layer implementation

### Запрос

После подтверждения выполнить `K5.3`: реализовать runtime mapping layer для semantic output (`activity/arousal/valence -> derived_state`), добавить `confidence/fallback_reason/claim_level` в ответы API/WS и покрыть поведение unit-тестами.

### Что сделано

1. В `inference-api` добавлен runtime semantic mapper:
   - `services/inference-api/src/inference_api/semantics.py`.
2. Обновлена runtime выдача `POST /v1/predict`:
   - добавлены поля `activity_class`, `valence_coarse`, `derived_state`, `confidence`, `fallback_reason`, `claim_level`;
   - `valence_scoped_status` интегрирован в fallback-логику.
3. В `live-inference-api` добавлен runtime semantic mapper:
   - `services/live-inference-api/src/live_inference_api/semantics.py`.
4. Обновлен WebSocket runtime `/ws/live`:
   - inference-сообщения теперь выдают canonical semantic fields;
   - добавана поддержка optional `context` в `stream_batch` для context-aware valence gating.
5. Обновлены runtime модели `inference-api` под semantic response shape:
   - `services/inference-api/src/inference_api/models.py`.
6. Добавлены unit-тесты:
   - `services/inference-api/tests/test_semantics.py`,
   - `services/live-inference-api/tests/test_semantics.py`.
7. Обновлены связанные контракты/доки для фактической runtime формы:
   - `contracts/http/live-inference-api.openapi.yaml` (optional `context` в `LiveStreamBatchMessage`),
   - `services/live-inference-api/README.md`.
8. Локальные проверки:
   - `services/inference-api`: `python3 -m pytest tests -q` -> `3 passed`;
   - `services/live-inference-api`: `python3 -m pytest tests -q` -> `5 passed`.
9. Обновлен execution status:
   - `K5.3` -> `completed`,
   - `K5.4` -> `next`.

### Измененные файлы

1. `services/inference-api/src/inference_api/models.py`
2. `services/inference-api/src/inference_api/api.py`
3. `services/inference-api/src/inference_api/semantics.py`
4. `services/inference-api/tests/test_semantics.py`
5. `services/live-inference-api/src/live_inference_api/api.py`
6. `services/live-inference-api/src/live_inference_api/semantics.py`
7. `services/live-inference-api/tests/test_semantics.py`
8. `contracts/http/live-inference-api.openapi.yaml`
9. `services/live-inference-api/README.md`
10. `.github/workflows/ci.yml`
11. `docs/status/execution-status.md`
12. `docs/status/work-log.md`

### Результат

`K5.3` завершен: semantic derived-state слой реально работает в runtime (`inference-api` и `live-inference-api`), canonical response fields выдаются в API/WS, а mapping/fallback/context-blocking поведение покрыто unit-тестами.

### Следующий рекомендуемый шаг

`K5.4 - Offline and replay evaluation for derived states`:

1. прогнать offline/replay оценку покрытия derived states;
2. измерить `unknown-rate` и false-claim risk для semantic layer;
3. зафиксировать risk summary и рекомендации по runtime exposure.

---

## 2026-03-28 - K5.4 - Offline and replay evaluation for derived states

### Запрос

После подтверждения выполнить `K5.4`: провести offline/replay оценку derived-state слоя, измерить coverage, `unknown-rate`, false-claim risk и оформить research-grade артефакты.

### Что сделано

1. Добавлен evaluation script:
   - `scripts/ml/state_k5_4_derived_state_evaluation.py`.
2. Выполнен реальный прогон `K5.4` на `WESAD` baseline prediction artifacts:
   - `watch-only-baseline/predictions-test.csv`,
   - `fusion-baseline/predictions-test.csv`.
3. Сформирован полный K5.4 bundle:
   - `evaluation-report.json`,
   - `predictions-test.csv`,
   - `per-subject-metrics.csv`,
   - `model-comparison.csv`,
   - `replay-session-metrics.csv`,
   - `plots/derived-state-coverage.png`,
   - `plots/risk-rates.png`,
   - `plots/per-subject-false-claim.png`,
   - `research-report.md`.
4. Зафиксированы headline метрики:
   - `samples_total=75`,
   - `unknown_rate=0.4133`,
   - `false_claim_rate=0.0667`,
   - `claimable_rate=0.5867`.
5. Добавлен backend summary документ:
   - `docs/backend/state-semantics-k5-4-derived-evaluation.md`.
6. Обновлен `scripts/ml/README.md` с командой запуска `K5.4`.
7. Обновлен execution status:
   - `K5.4` -> `completed`,
   - `K5.5` -> `next`.

### Измененные файлы

1. `scripts/ml/state_k5_4_derived_state_evaluation.py`
2. `scripts/ml/README.md`
3. `docs/backend/state-semantics-k5-4-derived-evaluation.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`
6. `data/external/wesad/artifacts/wesad/wesad-v1/k5-4-derived-state-evaluation/evaluation-report.json`
7. `data/external/wesad/artifacts/wesad/wesad-v1/k5-4-derived-state-evaluation/predictions-test.csv`
8. `data/external/wesad/artifacts/wesad/wesad-v1/k5-4-derived-state-evaluation/per-subject-metrics.csv`
9. `data/external/wesad/artifacts/wesad/wesad-v1/k5-4-derived-state-evaluation/model-comparison.csv`
10. `data/external/wesad/artifacts/wesad/wesad-v1/k5-4-derived-state-evaluation/replay-session-metrics.csv`
11. `data/external/wesad/artifacts/wesad/wesad-v1/k5-4-derived-state-evaluation/research-report.md`
12. `data/external/wesad/artifacts/wesad/wesad-v1/k5-4-derived-state-evaluation/plots/derived-state-coverage.png`
13. `data/external/wesad/artifacts/wesad/wesad-v1/k5-4-derived-state-evaluation/plots/risk-rates.png`
14. `data/external/wesad/artifacts/wesad/wesad-v1/k5-4-derived-state-evaluation/plots/per-subject-false-claim.png`

### Результат

`K5.4` завершен: offline/replay derived-state оценка проведена, риски квантитативно измерены и оформлены в reproducible research bundle для decision-перехода к `K5.5`.

### Следующий рекомендуемый шаг

`K5.5 - Product wording and exposure policy`:

1. зафиксировать user-facing wording для `safe/guarded/no_claim` состояний;
2. закрепить exposure matrix по каналам (`public_app/internal_dashboard/research`);
3. формализовать forbidden phrasing и fallback copy для `uncertain_state`.

---

## 2026-03-28 - K5.5 - Product wording and exposure policy

### Запрос

После подтверждения выполнить `K5.5`: зафиксировать user-facing wording по `claim_level`, разделить internal labels и product copy, подготовить exposure matrix и forbidden/fallback phrasing policy.

### Что сделано

1. Добавлен policy-документ:
   - `docs/backend/state-semantics-k5-5-wording-exposure-policy.md`.
2. Зафиксированы шаблоны wording по `claim_level`:
   - `safe`,
   - `guarded`,
   - `internal_only`,
   - `no_claim`.
3. Зафиксирована матрица экспонирования по каналам:
   - `public_app`,
   - `partner_api_public`,
   - `internal_dashboard`,
   - `research_report`,
   - `replay_debug`.
4. Зафиксированы правила fallback для `uncertain_state` и запрет прямого рендера technical-codes в публичном UX.
5. Формализован список forbidden phrasing (эмоциональные категоричные/диагностические утверждения и любые claims при `no_claim`).
6. Обновлен execution status:
   - `K5.5` -> `completed`,
   - `E2.19` -> `next`.
7. Обновлен K5 plan с фиксацией завершения `K5.5` и переводом рекомендаций на `E2.19`.

### Измененные файлы

1. `docs/backend/state-semantics-k5-5-wording-exposure-policy.md`
2. `docs/backend/state-semantics-derived-state-plan.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`

### Результат

`K5.5` завершен: продуктовый слой получил формальные правила wording/exposure, которые ограничивают публичные claims фактическими evidence boundaries и задают безопасный fallback для `uncertain_state`.

### Следующий рекомендуемый шаг

`E2.19 - Long-horizon canary monitoring pack`:

1. подготовить weekly canary summary aggregation;
2. оформить incident template с escalation path;
3. сформировать handoff-пакет для длительной эксплуатации.

---

## 2026-03-28 - E2.19 - Long-horizon canary monitoring pack

### Запрос

После подтверждения выполнить `E2.19`: подготовить долгосрочный monitoring pack для canary-контура (`weekly summary`, `incident template`, `handoff`).

### Что сделано

1. Добавлен backend summary-документ шага:
   - `docs/backend/valence-e2-19-long-horizon-monitoring-pack.md`.
2. Подготовлен weekly summary template:
   - `docs/operations/valence-canary-weekly-summary.md`.
3. Подготовлен incident template:
   - `docs/operations/valence-canary-incident-template.md`.
4. Подготовлен handoff pack:
   - `docs/operations/valence-canary-handoff-pack.md`.
5. В operations runbook добавлены ссылки на canary monitoring документы.
6. Обновлен execution status:
   - `E2.19` -> `completed`,
   - `E2.20` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-19-long-horizon-monitoring-pack.md`
2. `docs/operations/valence-canary-weekly-summary.md`
3. `docs/operations/valence-canary-incident-template.md`
4. `docs/operations/valence-canary-handoff-pack.md`
5. `docs/operations/runbook.md`
6. `docs/status/execution-status.md`
7. `docs/status/work-log.md`

### Результат

`E2.19` завершен: для canary-контура зафиксирован полный long-horizon операционный пакет с единым weekly форматом, стандартным incident-шаблоном и handoff/checklist процессом.

### Следующий рекомендуемый шаг

`E2.20 - Weekly canary monitoring dry-run`:

1. выполнить один полный weekly monitoring цикл по новым шаблонам;
2. смоделировать `warn/critical` triage по incident template;
3. зафиксировать readiness decision для регулярного weekly handoff.

---

## 2026-03-28 - E2.20 - Weekly canary monitoring dry-run

### Запрос

После подтверждения выполнить `E2.20`: провести один полный weekly monitoring dry-run по `E2.19` шаблонам и зафиксировать readiness decision.

### Что сделано

1. Добавлен reproducible dry-run script:
   - `scripts/ml/valence_e2_20_weekly_monitoring_dry_run.py`.
2. Выполнен dry-run pipeline:
   - `E2.13` canary check,
   - `E2.15` dashboard refresh,
   - contract-check.
3. Сформирован `E2.20` artifact bundle:
   - `evaluation-report.json`,
   - `weekly-summary-dry-run.md`,
   - `incident-warn-dry-run.md`,
   - `incident-critical-dry-run.md`,
   - `handoff-dry-run-checklist.csv`,
   - `scheduler-step-log.csv`,
   - `research-report.md`.
4. Зафиксирован итог dry-run:
   - `decision=weekly_handoff_ready`,
   - `weekly_decision=investigate`,
   - `warn_triggered=true` (ожидаемо, неполное weekly окно),
   - `critical_triggered=false`.
5. Обновлены docs для операционного sign-off и запуска скрипта.
6. Обновлен execution status:
   - `E2.20` -> `completed`,
   - `E2.21` -> `next`.

### Измененные файлы

1. `scripts/ml/valence_e2_20_weekly_monitoring_dry_run.py`
2. `scripts/ml/README.md`
3. `docs/backend/valence-e2-20-weekly-monitoring-dry-run.md`
4. `docs/operations/valence-canary-operational-signoff.md`
5. `docs/status/execution-status.md`
6. `docs/status/work-log.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-20-weekly-monitoring-dry-run/evaluation-report.json`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-20-weekly-monitoring-dry-run/weekly-summary-dry-run.md`
9. `data/external/wesad/artifacts/wesad/wesad-v1/e2-20-weekly-monitoring-dry-run/incident-warn-dry-run.md`
10. `data/external/wesad/artifacts/wesad/wesad-v1/e2-20-weekly-monitoring-dry-run/incident-critical-dry-run.md`
11. `data/external/wesad/artifacts/wesad/wesad-v1/e2-20-weekly-monitoring-dry-run/handoff-dry-run-checklist.csv`
12. `data/external/wesad/artifacts/wesad/wesad-v1/e2-20-weekly-monitoring-dry-run/scheduler-step-log.csv`
13. `data/external/wesad/artifacts/wesad/wesad-v1/e2-20-weekly-monitoring-dry-run/research-report.md`

### Результат

`E2.20` завершен: weekly monitoring flow подтвержден на реальном dry-run, handoff readiness достигнут (`weekly_handoff_ready`), triage-шаблоны проверены.

### Следующий рекомендуемый шаг

`E2.21 - Weekly canary operations hardening`:

1. зафиксировать retention policy для weekly artifacts/incidents;
2. формализовать ownership rotation;
3. закрепить SLA/OLA по weekly triage и handoff completion.

---

## 2026-03-28 - E2.21 - Weekly canary operations hardening

### Запрос

После подтверждения выполнить `E2.21`: закрепить operations hardening weekly canary-процесса (retention, ownership rotation, SLA/OLA).

### Что сделано

1. Добавлен отдельный operations hardening policy:
   - `docs/operations/valence-canary-operations-hardening.md`.
2. Обновлен weekly summary template:
   - добавлены обязательные поля `triage_started_at_utc`, `triage_completed_at_utc`, `handoff_completed_at_utc`, compliance status.
3. Обновлен handoff pack:
   - добавлены weekly ownership rotation и completion-требования.
4. Обновлен operations runbook ссылкой на hardening policy.
5. Добавлен backend summary-документ шага:
   - `docs/backend/valence-e2-21-weekly-operations-hardening.md`.
6. Обновлен execution status:
   - `E2.21` -> `completed`,
   - `E2.22` -> `next`.

### Измененные файлы

1. `docs/operations/valence-canary-operations-hardening.md`
2. `docs/operations/valence-canary-weekly-summary.md`
3. `docs/operations/valence-canary-handoff-pack.md`
4. `docs/operations/runbook.md`
5. `docs/backend/valence-e2-21-weekly-operations-hardening.md`
6. `docs/status/execution-status.md`
7. `docs/status/work-log.md`

### Результат

`E2.21` завершен: weekly canary operations переведены в формализованный режим с retention policy, ownership rotation и SLA/OLA-правилами для triage/handoff.

### Следующий рекомендуемый шаг

`E2.22 - Weekly operations readiness review`:

1. пройти readiness checklist по новой policy;
2. проверить заполнение SLA/OLA полей на одном simulated weekly cycle;
3. зафиксировать final operational readiness decision.

---

## 2026-03-28 - E2.22 - Weekly operations readiness review

### Запрос

После подтверждения выполнить `E2.22`: провести readiness review weekly operations по новой policy и зафиксировать final decision.

### Что сделано

1. Добавлен reproducible review script:
   - `scripts/ml/valence_e2_22_weekly_readiness_review.py`.
2. Выполнен `E2.22` review run на входах из `E2.20`:
   - `e2-20.../evaluation-report.json`,
   - `e2-20.../handoff-dry-run-checklist.csv`.
3. Сформирован `E2.22` bundle:
   - `evaluation-report.json`,
   - `readiness-checklist.csv`,
   - `weekly-summary-simulated.md`,
   - `research-report.md`.
4. Обновлен operations sign-off:
   - добавлен `Weekly Readiness Gate (E2.22)`.
5. Обновлен `scripts/ml/README.md` командой запуска `E2.22`.
6. Обновлен execution status:
   - `E2.22` -> `completed`,
   - `E2.23` -> `next`.

### Измененные файлы

1. `scripts/ml/valence_e2_22_weekly_readiness_review.py`
2. `scripts/ml/README.md`
3. `docs/operations/valence-canary-operational-signoff.md`
4. `docs/backend/valence-e2-22-weekly-readiness-review.md`
5. `docs/status/execution-status.md`
6. `docs/status/work-log.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-22-weekly-operations-readiness-review/evaluation-report.json`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-22-weekly-operations-readiness-review/readiness-checklist.csv`
9. `data/external/wesad/artifacts/wesad/wesad-v1/e2-22-weekly-operations-readiness-review/weekly-summary-simulated.md`
10. `data/external/wesad/artifacts/wesad/wesad-v1/e2-22-weekly-operations-readiness-review/research-report.md`

### Результат

`E2.22` завершен: readiness review подтверждает `steady_state_ready` (`4/4` checks pass), weekly operations policy готова к steady-state kickoff.

### Следующий рекомендуемый шаг

`E2.23 - Weekly operations steady-state kickoff`:

1. зафиксировать календарный weekly cadence window;
2. сформировать ownership roster на ближайшие недели;
3. оформить контрольные точки weekly handoff.

---

## 2026-03-28 - E2.23 - Weekly operations steady-state kickoff

### Запрос

После подтверждения выполнить `E2.23`: запустить steady-state weekly operations режим с календарным cadence, ownership roster и handoff checkpoints.

### Что сделано

1. Добавлен operations kickoff-документ:
   - `docs/operations/valence-canary-steady-state-kickoff.md`.
2. Зафиксирован weekly cadence window:
   - `Monday 00:00 -> Sunday 23:59` (UTC),
   - summary/handoff deadlines (`Sunday 18:00/20:00`),
   - rotation confirmation (`Monday <=12:00`).
3. Зафиксирован стартовый ownership roster на `3` недели (`2026-W14..W16`).
4. Зафиксированы weekly handoff checkpoints `T0..T4` и обязательные weekly artifacts.
5. Добавлен backend summary-документ шага:
   - `docs/backend/valence-e2-23-steady-state-kickoff.md`.
6. Обновлен operations runbook ссылкой на kickoff policy.
7. Обновлен execution status:
   - `E2.23` -> `completed`,
   - `E2.24` -> `next`.

### Измененные файлы

1. `docs/operations/valence-canary-steady-state-kickoff.md`
2. `docs/backend/valence-e2-23-steady-state-kickoff.md`
3. `docs/operations/runbook.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`

### Результат

`E2.23` завершен: steady-state weekly operations режим формально запущен с явным cadence, ownership roster и контрольными точками handoff.

### Следующий рекомендуемый шаг

`E2.24 - First steady-state weekly cycle audit`:

1. проверить соблюдение deadlines и checkpoints на первом weekly окне;
2. провести SLA/OLA compliance audit по фактической неделе;
3. зафиксировать post-kickoff adjustments (если нужны).

---

## 2026-03-28 - E2.24 - First steady-state weekly cycle audit

### Запрос

После подтверждения выполнить `E2.24`: провести аудит первого weekly окна steady-state режима.

### Что сделано

1. Добавлен temporal-gated audit script:
   - `scripts/ml/valence_e2_24_first_weekly_cycle_audit.py`.
2. Выполнен audit precheck для окна `2026-W14`:
   - window: `2026-03-30 .. 2026-04-05` (UTC),
   - audit due date: `2026-04-06`.
3. Сформирован `E2.24` bundle:
   - `evaluation-report.json`,
   - `audit-checklist-template.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
4. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-24-first-weekly-cycle-audit.md`.
5. Обновлен `scripts/ml/README.md` командой запуска `E2.24`.
6. Обновлен execution status:
   - `E2.24` -> `blocked`,
   - `E2.25` -> `next`.

### Измененные файлы

1. `scripts/ml/valence_e2_24_first_weekly_cycle_audit.py`
2. `scripts/ml/README.md`
3. `docs/backend/valence-e2-24-first-weekly-cycle-audit.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-24-first-weekly-cycle-audit/evaluation-report.json`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-24-first-weekly-cycle-audit/audit-checklist-template.csv`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-24-first-weekly-cycle-audit/post-kickoff-adjustments.md`
9. `data/external/wesad/artifacts/wesad/wesad-v1/e2-24-first-weekly-cycle-audit/research-report.md`

### Результат

`E2.24` временно блокирован по календарю: на дату выполнения (`2026-03-28`) первое weekly окно еще не закрыто. Фактический аудит возможен начиная с `2026-04-06` (UTC).

### Следующий рекомендуемый шаг

`E2.25 - Execute factual first weekly cycle audit`:

1. после `2026-04-06` выполнить фактический аудит `2026-W14`;
2. заполнить реальные SLA/OLA compliance поля;
3. зафиксировать post-kickoff adjustments по фактическим данным недели.

---

## 2026-03-28 - E2.25 - Execute factual first weekly cycle audit

### Запрос

После подтверждения выполнить `E2.25`: провести фактический аудит первого steady-state weekly окна и закрыть compliance по реальным данным.

### Что сделано

1. Добавлен factual-audit script:
   - `scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py`.
2. В скрипт добавлены:
   - temporal gate (`audit_due_date=2026-04-06`, UTC),
   - проверка входов `weekly-summary.md` и `handoff-checklist.csv`,
   - SLA/OLA/compliance checklist (timestamps completeness, chronology, OLA deadlines, checklist pass).
3. Выполнены проверки:
   - `python3 -m py_compile scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py`,
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py`.
4. Сформирован `E2.25` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
5. Добавлен backend summary-документ шага:
   - `docs/backend/valence-e2-25-execute-factual-weekly-cycle-audit.md`.
6. Обновлен `scripts/ml/README.md` командой запуска `E2.25`.
7. Обновлен execution status:
   - `E2.25` -> `blocked`,
   - `E2.26` -> `next`.

### Измененные файлы

1. `scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py`
2. `scripts/ml/README.md`
3. `docs/backend/valence-e2-25-execute-factual-weekly-cycle-audit.md`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-25-factual-first-weekly-cycle-audit/evaluation-report.json`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-25-factual-first-weekly-cycle-audit/audit-checklist.csv`
8. `data/external/wesad/artifacts/wesad/wesad-v1/e2-25-factual-first-weekly-cycle-audit/post-kickoff-adjustments.md`
9. `data/external/wesad/artifacts/wesad/wesad-v1/e2-25-factual-first-weekly-cycle-audit/research-report.md`

### Результат

`E2.25` временно блокирован по календарю: на дату выполнения (`2026-03-28`) factual-аудит окна `2026-03-30..2026-04-05` (UTC) еще недоступен, запуск разрешен начиная с `2026-04-06`.

### Следующий рекомендуемый шаг

`E2.26 - Re-run factual first weekly cycle audit after window close`:

1. после `2026-04-06` заполнить фактические `weekly-summary.md` и `handoff-checklist.csv`;
2. повторно запустить `E2.25` script;
3. зафиксировать финальный compliance decision (`pass/warn/fail`) по фактическим данным недели.

---

## 2026-03-28 - E2.26 - Re-run factual first weekly cycle audit after window close

### Запрос

После подтверждения выполнить `E2.26`: повторно запустить factual weekly-cycle audit после `E2.25` и зафиксировать финальный compliance status.

### Что сделано

1. Выполнен rerun factual audit script с отдельным output path:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-26-factual-first-weekly-cycle-audit-rerun ...`.
2. Сформирован `E2.26` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-26-factual-weekly-cycle-audit-rerun.md`.
4. Обновлен execution status:
   - `E2.26` -> `blocked`,
   - `E2.27` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-26-factual-weekly-cycle-audit-rerun.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-26-factual-first-weekly-cycle-audit-rerun/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-26-factual-first-weekly-cycle-audit-rerun/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-26-factual-first-weekly-cycle-audit-rerun/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-26-factual-first-weekly-cycle-audit-rerun/research-report.md`

### Результат

`E2.26` остается временно блокированным: на дату выполнения (`2026-03-28`) audit due date (`2026-04-06`, UTC) еще не достигнута, поэтому completion-аудит фактически не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.27 - Factual weekly-cycle audit completion run`:

1. на/после `2026-04-06` заполнить фактические `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить completion run;
3. зафиксировать финальный compliance decision (`pass/warn/fail`).

---

## 2026-03-28 - E2.27 - Factual weekly-cycle audit completion run

### Запрос

После подтверждения выполнить `E2.27`: сделать completion-run фактического weekly-cycle аудита.

### Что сделано

1. Выполнен completion-run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-27-factual-weekly-cycle-audit-completion-run ...`.
2. Сформирован `E2.27` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-27-factual-weekly-cycle-audit-completion-run.md`.
4. Обновлен execution status:
   - `E2.27` -> `blocked`,
   - `E2.28` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-27-factual-weekly-cycle-audit-completion-run.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-27-factual-weekly-cycle-audit-completion-run/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-27-factual-weekly-cycle-audit-completion-run/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-27-factual-weekly-cycle-audit-completion-run/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-27-factual-weekly-cycle-audit-completion-run/research-report.md`

### Результат

`E2.27` остается временно блокированным: на `2026-03-28` окно `2026-03-30..2026-04-05` еще не закрыто, factual-аудит возможен только с `2026-04-06` (UTC).

### Следующий рекомендуемый шаг

`E2.28 - Post-window factual weekly-cycle audit run`:

1. на/после `2026-04-06` заполнить фактические `weekly-summary.md` и `handoff-checklist.csv`;
2. запустить factual-аудит;
3. зафиксировать финальный `pass/warn/fail`.

---

## 2026-03-28 - E2.28 - Post-window factual weekly-cycle audit run

### Запрос

После подтверждения выполнить `E2.28`: сделать post-window factual run weekly-cycle аудита.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-28-post-window-factual-weekly-cycle-audit-run ...`.
2. Сформирован `E2.28` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-28-post-window-factual-weekly-cycle-audit-run.md`.
4. Обновлен execution status:
   - `E2.28` -> `blocked`,
   - `E2.29` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-28-post-window-factual-weekly-cycle-audit-run.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-28-post-window-factual-weekly-cycle-audit-run/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-28-post-window-factual-weekly-cycle-audit-run/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-28-post-window-factual-weekly-cycle-audit-run/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-28-post-window-factual-weekly-cycle-audit-run/research-report.md`

### Результат

`E2.28` временно блокирован: на `2026-03-28` factual-аудит остается недоступен до `2026-04-06` (UTC), поэтому финальный compliance-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.29 - Dated factual completion run`:

1. на/после `2026-04-06` заполнить фактические `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-28 - E2.29 - Dated factual completion run

### Запрос

После подтверждения выполнить `E2.29`: провести dated factual completion-run weekly-cycle аудита.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-29-dated-factual-completion-run ...`.
2. Сформирован `E2.29` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-29-dated-factual-completion-run.md`.
4. Обновлен execution status:
   - `E2.29` -> `blocked`,
   - `E2.30` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-29-dated-factual-completion-run.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-29-dated-factual-completion-run/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-29-dated-factual-completion-run/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-29-dated-factual-completion-run/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-29-dated-factual-completion-run/research-report.md`

### Результат

`E2.29` временно блокирован: на дату выполнения (`2026-03-28`) temporal gate закрыт до `2026-04-06` (UTC), поэтому фактическое закрытие compliance-run пока невозможно.

### Следующий рекомендуемый шаг

`E2.30 - Factual completion run on/after gate date`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать финальный `pass/warn/fail`.

---

## 2026-03-28 - E2.30 - Factual completion run on/after gate date

### Запрос

После подтверждения выполнить `E2.30`: провести factual completion run on/after gate date.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-30-factual-completion-run-on-after-gate-date ...`.
2. Сформирован `E2.30` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-30-factual-completion-run-on-after-gate-date.md`.
4. Обновлен execution status:
   - `E2.30` -> `blocked`,
   - `E2.31` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-30-factual-completion-run-on-after-gate-date.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-30-factual-completion-run-on-after-gate-date/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-30-factual-completion-run-on-after-gate-date/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-30-factual-completion-run-on-after-gate-date/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-30-factual-completion-run-on-after-gate-date/research-report.md`

### Результат

`E2.30` остается временно блокированным: на `2026-03-28` temporal gate закрыт до `2026-04-06` (UTC), поэтому фактическое закрытие compliance-run пока недоступно.

### Следующий рекомендуемый шаг

`E2.31 - First post-gate factual completion attempt`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итог `pass/warn/fail`.

---

## 2026-03-28 - E2.31 - First post-gate factual completion attempt

### Запрос

После подтверждения выполнить `E2.31`: провести первую post-gate попытку factual completion-run.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-31-first-post-gate-factual-completion-attempt ...`.
2. Сформирован `E2.31` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-31-first-post-gate-factual-completion-attempt.md`.
4. Обновлен execution status:
   - `E2.31` -> `blocked`,
   - `E2.32` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-31-first-post-gate-factual-completion-attempt.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-31-first-post-gate-factual-completion-attempt/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-31-first-post-gate-factual-completion-attempt/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-31-first-post-gate-factual-completion-attempt/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-31-first-post-gate-factual-completion-attempt/research-report.md`

### Результат

`E2.31` временно блокирован: на `2026-03-28` temporal gate все еще закрыт до `2026-04-06` (UTC), поэтому фактический completion-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.32 - Gate-date factual completion rerun`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-28 - E2.32 - Gate-date factual completion rerun

### Запрос

После подтверждения выполнить `E2.32`: провести gate-date factual completion rerun.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-32-gate-date-factual-completion-rerun`.
2. Сформирован `E2.32` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-32-gate-date-factual-completion-rerun.md`.
4. Обновлен execution status:
   - `E2.32` -> `blocked`,
   - `E2.33` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-32-gate-date-factual-completion-rerun.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-32-gate-date-factual-completion-rerun/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-32-gate-date-factual-completion-rerun/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-32-gate-date-factual-completion-rerun/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-32-gate-date-factual-completion-rerun/research-report.md`

### Результат

`E2.32` временно блокирован: на `2026-03-28` temporal gate все еще закрыт до `2026-04-06` (UTC), поэтому фактический completion-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.33 - Post-gate factual completion rerun follow-up`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-28 - E2.33 - Post-gate factual completion rerun follow-up

### Запрос

После подтверждения выполнить `E2.33`: провести post-gate factual completion rerun follow-up.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-33-post-gate-factual-completion-rerun-follow-up`.
2. Сформирован `E2.33` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-33-post-gate-factual-completion-rerun-follow-up.md`.
4. Обновлен execution status:
   - `E2.33` -> `blocked`,
   - `E2.34` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-33-post-gate-factual-completion-rerun-follow-up.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-33-post-gate-factual-completion-rerun-follow-up/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-33-post-gate-factual-completion-rerun-follow-up/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-33-post-gate-factual-completion-rerun-follow-up/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-33-post-gate-factual-completion-rerun-follow-up/research-report.md`

### Результат

`E2.33` временно блокирован: на `2026-03-28` temporal gate все еще закрыт до `2026-04-06` (UTC), поэтому фактический completion-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.34 - Post-gate factual completion rerun continuation`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-28 - E2.34 - Post-gate factual completion rerun continuation

### Запрос

После подтверждения выполнить `E2.34`: провести post-gate factual completion rerun continuation.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-34-post-gate-factual-completion-rerun-continuation`.
2. Сформирован `E2.34` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-34-post-gate-factual-completion-rerun-continuation.md`.
4. Обновлен execution status:
   - `E2.34` -> `blocked`,
   - `E2.35` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-34-post-gate-factual-completion-rerun-continuation.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-34-post-gate-factual-completion-rerun-continuation/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-34-post-gate-factual-completion-rerun-continuation/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-34-post-gate-factual-completion-rerun-continuation/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-34-post-gate-factual-completion-rerun-continuation/research-report.md`

### Результат

`E2.34` временно блокирован: на `2026-03-28` temporal gate все еще закрыт до `2026-04-06` (UTC), поэтому фактический completion-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.35 - Post-gate factual completion rerun extension`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-28 - E2.35 - Post-gate factual completion rerun extension

### Запрос

После подтверждения выполнить `E2.35`: провести post-gate factual completion rerun extension.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-35-post-gate-factual-completion-rerun-extension`.
2. Сформирован `E2.35` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-35-post-gate-factual-completion-rerun-extension.md`.
4. Обновлен execution status:
   - `E2.35` -> `blocked`,
   - `E2.36` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-35-post-gate-factual-completion-rerun-extension.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-35-post-gate-factual-completion-rerun-extension/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-35-post-gate-factual-completion-rerun-extension/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-35-post-gate-factual-completion-rerun-extension/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-35-post-gate-factual-completion-rerun-extension/research-report.md`

### Результат

`E2.35` временно блокирован: на `2026-03-28` temporal gate все еще закрыт до `2026-04-06` (UTC), поэтому фактический completion-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.36 - Post-gate factual completion rerun progression`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-28 - E2.36 - Post-gate factual completion rerun progression

### Запрос

После подтверждения выполнить `E2.36`: провести post-gate factual completion rerun progression.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-36-post-gate-factual-completion-rerun-progression`.
2. Сформирован `E2.36` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-36-post-gate-factual-completion-rerun-progression.md`.
4. Обновлен execution status:
   - `E2.36` -> `blocked`,
   - `E2.37` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-36-post-gate-factual-completion-rerun-progression.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-36-post-gate-factual-completion-rerun-progression/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-36-post-gate-factual-completion-rerun-progression/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-36-post-gate-factual-completion-rerun-progression/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-36-post-gate-factual-completion-rerun-progression/research-report.md`

### Результат

`E2.36` временно блокирован: на `2026-03-28` temporal gate все еще закрыт до `2026-04-06` (UTC), поэтому фактический completion-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.37 - Post-gate factual completion rerun sequence`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-28 - E2.37 - Post-gate factual completion rerun sequence

### Запрос

После подтверждения выполнить `E2.37`: провести post-gate factual completion rerun sequence.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-37-post-gate-factual-completion-rerun-sequence`.
2. Сформирован `E2.37` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-37-post-gate-factual-completion-rerun-sequence.md`.
4. Обновлен execution status:
   - `E2.37` -> `blocked`,
   - `E2.38` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-37-post-gate-factual-completion-rerun-sequence.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-37-post-gate-factual-completion-rerun-sequence/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-37-post-gate-factual-completion-rerun-sequence/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-37-post-gate-factual-completion-rerun-sequence/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-37-post-gate-factual-completion-rerun-sequence/research-report.md`

### Результат

`E2.37` временно блокирован: на `2026-03-28` temporal gate все еще закрыт до `2026-04-06` (UTC), поэтому фактический completion-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.38 - Post-gate factual completion rerun iteration`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-28 - E2.38 - Post-gate factual completion rerun iteration

### Запрос

После подтверждения выполнить `E2.38`: провести post-gate factual completion rerun iteration.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-38-post-gate-factual-completion-rerun-iteration`.
2. Сформирован `E2.38` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-38-post-gate-factual-completion-rerun-iteration.md`.
4. Обновлен execution status:
   - `E2.38` -> `blocked`,
   - `E2.39` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-38-post-gate-factual-completion-rerun-iteration.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-38-post-gate-factual-completion-rerun-iteration/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-38-post-gate-factual-completion-rerun-iteration/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-38-post-gate-factual-completion-rerun-iteration/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-38-post-gate-factual-completion-rerun-iteration/research-report.md`

### Результат

`E2.38` временно блокирован: на `2026-03-28` temporal gate все еще закрыт до `2026-04-06` (UTC), поэтому фактический completion-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.39 - Post-gate factual completion rerun chain`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-28 - E2.39 - Post-gate factual completion rerun chain

### Запрос

После подтверждения выполнить `E2.39`: провести post-gate factual completion rerun chain.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-39-post-gate-factual-completion-rerun-chain`.
2. Сформирован `E2.39` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-39-post-gate-factual-completion-rerun-chain.md`.
4. Обновлен execution status:
   - `E2.39` -> `blocked`,
   - `E2.40` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-39-post-gate-factual-completion-rerun-chain.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-39-post-gate-factual-completion-rerun-chain/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-39-post-gate-factual-completion-rerun-chain/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-39-post-gate-factual-completion-rerun-chain/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-39-post-gate-factual-completion-rerun-chain/research-report.md`

### Результат

`E2.39` временно блокирован: на `2026-03-28` temporal gate все еще закрыт до `2026-04-06` (UTC), поэтому фактический completion-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.40 - Post-gate factual completion rerun continuation-2`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-28 - E2.40 - Post-gate factual completion rerun continuation-2

### Запрос

После подтверждения выполнить `E2.40`: провести post-gate factual completion rerun continuation-2.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-40-post-gate-factual-completion-rerun-continuation-2`.
2. Сформирован `E2.40` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-40-post-gate-factual-completion-rerun-continuation-2.md`.
4. Обновлен execution status:
   - `E2.40` -> `blocked`,
   - `E2.41` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-40-post-gate-factual-completion-rerun-continuation-2.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-40-post-gate-factual-completion-rerun-continuation-2/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-40-post-gate-factual-completion-rerun-continuation-2/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-40-post-gate-factual-completion-rerun-continuation-2/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-40-post-gate-factual-completion-rerun-continuation-2/research-report.md`

### Результат

`E2.40` временно блокирован: на `2026-03-28` temporal gate все еще закрыт до `2026-04-06` (UTC), поэтому фактический completion-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.41 - Post-gate factual completion rerun continuation-3`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-28 - E2.41 - Post-gate factual completion rerun continuation-3

### Запрос

После подтверждения выполнить `E2.41`: провести post-gate factual completion rerun continuation-3.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-41-post-gate-factual-completion-rerun-continuation-3`.
2. Сформирован `E2.41` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-41-post-gate-factual-completion-rerun-continuation-3.md`.
4. Обновлен execution status:
   - `E2.41` -> `blocked`,
   - `E2.42` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-41-post-gate-factual-completion-rerun-continuation-3.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-41-post-gate-factual-completion-rerun-continuation-3/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-41-post-gate-factual-completion-rerun-continuation-3/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-41-post-gate-factual-completion-rerun-continuation-3/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-41-post-gate-factual-completion-rerun-continuation-3/research-report.md`

### Результат

`E2.41` временно блокирован: на `2026-03-28` temporal gate все еще закрыт до `2026-04-06` (UTC), поэтому фактический completion-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.42 - Post-gate factual completion rerun continuation-4`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-28 - E2.42 - Post-gate factual completion rerun continuation-4

### Запрос

После подтверждения выполнить `E2.42`: провести post-gate factual completion rerun continuation-4.

### Что сделано

1. Выполнен run:
   - `python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py --output-dir .../e2-42-post-gate-factual-completion-rerun-continuation-4`.
2. Сформирован `E2.42` bundle:
   - `evaluation-report.json`,
   - `audit-checklist.csv`,
   - `post-kickoff-adjustments.md`,
   - `research-report.md`.
3. Добавлен backend summary-документ:
   - `docs/backend/valence-e2-42-post-gate-factual-completion-rerun-continuation-4.md`.
4. Обновлен execution status:
   - `E2.42` -> `blocked`,
   - `E2.43` -> `next`.

### Измененные файлы

1. `docs/backend/valence-e2-42-post-gate-factual-completion-rerun-continuation-4.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`
4. `data/external/wesad/artifacts/wesad/wesad-v1/e2-42-post-gate-factual-completion-rerun-continuation-4/evaluation-report.json`
5. `data/external/wesad/artifacts/wesad/wesad-v1/e2-42-post-gate-factual-completion-rerun-continuation-4/audit-checklist.csv`
6. `data/external/wesad/artifacts/wesad/wesad-v1/e2-42-post-gate-factual-completion-rerun-continuation-4/post-kickoff-adjustments.md`
7. `data/external/wesad/artifacts/wesad/wesad-v1/e2-42-post-gate-factual-completion-rerun-continuation-4/research-report.md`

### Результат

`E2.42` временно блокирован: на `2026-03-28` temporal gate все еще закрыт до `2026-04-06` (UTC), поэтому фактический completion-run пока не может быть закрыт.

### Следующий рекомендуемый шаг

`E2.43 - Post-gate factual completion rerun continuation-5`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-29 - R6.13 - Live state refresh + watch reconnect control

### Запрос

Исправить проблему, где в live UI состояния `activity/arousal` не меняются, `valence` постоянно `unknown`, а также добавить на watch кнопку для ручного перезапуска подключения к iPhone при потере mirroring.

### Что сделано

1. Исправлен live inference UI-binding на iPhone:
   - `LiveInferenceSection` переведен на прямое наблюдение `LiveInferenceClient` через `@ObservedObject`;
   - вынесен отдельный fallback-блок `LiveInferenceUnavailableSection`, если WS-конфиг не задан.
2. Обновлен payload в `LiveInferenceClient`:
   - `context` теперь берется из `ON_GO_LIVE_INFERENCE_CONTEXT` (default: `research_only` вместо hardcoded `public_app`);
   - добавлена расшифровка valence-статусов при `unknown`: `blocked_by_context` и `model_not_loaded`.
3. Добавлен ручной reconnect на watch:
   - в `WatchSessionViewModel` добавлен `reconnectMirroring()` с форс-остановкой локального capture и повторным запуском mirrored runtime;
   - в `WatchSessionView` добавлена кнопка `Reconnect`.
4. Прогнана проверка сборки:
   - `swift build --package-path /Users/kgz/Desktop/p/on-go-ios/packages/CaptureKit` проходит успешно.

### Измененные файлы

1. `on-go-ios/packages/CaptureKit/Sources/BackendClient/LiveInferenceClient.swift`
2. `on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionDashboardView.swift`
3. `on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionViewModel.swift`
4. `on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionView.swift`
5. `on-go/docs/status/execution-status.md`
6. `on-go/docs/status/work-log.md`

### Результат

Live-секция на iPhone должна обновляться по каждому новому inference-сообщению; valence теперь получает более точный runtime-статус вместо «немого» `unknown` и может перейти в предсказания при разрешенном контексте и наличии valence-модели; на watch появился ручной путь восстановления mirroring без перезапуска приложения.

### Следующий рекомендуемый шаг

`E2.43 - Post-gate factual completion rerun continuation-5` (по roadmap), либо прикладной device-step:

1. проверить на реальной паре iPhone+Watch сценарий «долгая сессия -> mirroring lost -> Reconnect»;
2. сверить, что `activity/arousal` реально меняются при изменении нагрузки, а valence показывает `negative/neutral/positive` при валидном valence runtime bundle;
3. если valence остается `model_not_loaded`, подключить runtime bundle с valence-track в `live-inference-api`.

---

## 2026-03-29 - R6.14 - Live inference unfreeze for sparse heart-rate updates

### Запрос

После внедрения `R6.13` пользователь подтвердил, что `valence` появился, но `activity/arousal` все равно не меняются после первого показа.

### Что сделано

1. Исправлен server-side windowing в `live-inference-api`:
   - `StreamBuffer` теперь использует `watch_accelerometer` как ведущий таймлайн для продвижения окон;
   - если в окне нет новых HR sample, буфер использует последний доступный HR sample при условии, что он не старее `max_heart_staleness_ms` (по умолчанию `30000ms`).
2. Добавлены unit-тесты для нового поведения буфера:
   - продолжение эмиссии окон при sparse HR;
   - блокировка эмиссии при слишком старом HR sample.
3. Исправлена пересылка live cardio source на iPhone:
   - `PhoneCaptureCoordinator` теперь форвардит `polar_hr` в live inference pipeline;
   - `LiveInferenceClient` отправляет `polar_hr` в websocket наряду с `watch_heart_rate/watch_accelerometer`.
4. Выполнены проверки:
   - `python3 -m pytest -q` в `services/live-inference-api` (`15 passed`);
   - `swift build --package-path /Users/kgz/Desktop/p/on-go-ios/packages/CaptureKit` проходит.

### Измененные файлы

1. `on-go/services/live-inference-api/src/live_inference_api/buffer.py`
2. `on-go/services/live-inference-api/tests/test_buffer.py`
3. `on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PhoneCaptureCoordinator.swift`
4. `on-go-ios/packages/CaptureKit/Sources/BackendClient/LiveInferenceClient.swift`
5. `on-go/docs/status/execution-status.md`
6. `on-go/docs/status/work-log.md`

### Результат

Live inference больше не должен “залипать” после первого предикта в сценариях с редкими обновлениями heart-rate: окна продолжают двигаться по motion потоку, а cardio сигнал берется из последнего свежего sample; при наличии `polar_hr` он теперь корректно доходит до live backend.

### Следующий рекомендуемый шаг

`E2.43 - Post-gate factual completion rerun continuation-5` (по roadmap), либо прикладной device-step:

1. на реальном iPhone+Watch+Polar проверить последовательность infer-обновлений в течение 2-3 минут с чередованием `rest -> movement -> rest`;
2. убедиться по логам, что в live backend приходит `polar_hr` и `watch_accelerometer`;
3. если состояние все еще выглядит статичным, сохранить кусок runtime-лога (`LiveForward`/`LiveInference`) и сделать отдельный calibration-инкремент thresholds/model bundle.

---

## 2026-03-29 - R6.12 - Runtime bundle wiring + live Polar cardio path verification

### Запрос

Собрать реальный runtime bundle (`activity/arousal/optional valence`) через новый manifest script, подключить bundle в окружение `inference-api/live-inference-api` и проверить live inference на Polar cardio path.

### Что сделано

1. Подготовлен runtime bundle в `data/runtime-bundles/k5-9-fusion-runtime-v1`:
   - добавлены `activity/arousal` модели и соответствующие `feature_names`;
   - сгенерирован `model-bundle.manifest.json` через `scripts/ml/build_runtime_bundle_manifest.py`;
   - `valence` оставлен optional (track отсутствует в текущем bundle).
2. Подключен runtime bundle в docker-compose через override:
   - `inference-api` и `live-inference-api` монтируют bundle в `/models`.
3. Пересобраны образы `inference-api/live-inference-api` и перезапущены сервисы.
4. Проверена готовность runtime:
   - `GET /health` на `8100` и `8120` возвращает `model_loaded=true`.
5. Выполнен live WS smoke (`/ws/live`) с `source_mode=live`, `watch_accelerometer + polar_hr`:
   - inference приходит;
   - `heart_source=polar_hr`;
   - `heart_source_fallback_active=false`.

### Измененные файлы

1. `on-go/infra/compose/docker-compose.override.yml`
2. `on-go/data/runtime-bundles/k5-9-fusion-runtime-v1/model-bundle.manifest.json`
3. `on-go/data/runtime-bundles/k5-9-fusion-runtime-v1/activity_watch_only_centroid.joblib`
4. `on-go/data/runtime-bundles/k5-9-fusion-runtime-v1/arousal_watch_only_centroid.joblib`
5. `on-go/data/runtime-bundles/k5-9-fusion-runtime-v1/activity_feature_names.json`
6. `on-go/data/runtime-bundles/k5-9-fusion-runtime-v1/arousal_feature_names.json`
7. `on-go/docs/status/execution-status.md`
8. `on-go/docs/status/work-log.md`

### Результат

Backend runtime работает с manifest-driven bundle и выдает live inference по Polar primary cardio path. Ошибка прежней несовместимости старого docker image устранена пересборкой сервисов.

### Следующий рекомендуемый шаг

Короткий device E2E на физическом iPhone+Watch:

1. запустить live-capture с реальным Polar H10;
2. подтвердить в логах `LiveForward`/`LiveInference`, что идут `watch_accelerometer` и `polar_hr` батчи;
3. убедиться, что нет `heart_source_fallback_active`, а при искусственной потере Polar появляется fallback-событие и затем `heart_source_recovered`.

---

## 2026-03-29 - K5.6/K5.7 - Fusion serving contract и manifest-driven runtime bundle loading

### Запрос

Разобрать по протоколам, какая модель должна использоваться в runtime для `activity/arousal/valence`, где `Polar H10` и `Apple Watch` работают одновременно, а затем убрать жесткую привязку backend runtime к старому `watch_only_centroid_*` bundle.

### Что сделано

1. Сверены research/protocol документы и зафиксирован канонический serving contract:
   - `activity` может жить на watch-driven motion candidate;
   - `arousal_coarse` должен быть `fusion-first` с `Polar` как primary cardio source и `Watch` как motion/context source;
   - `valence_coarse` остается optional/scoped track без user-facing claims.
2. Добавлен новый contract artifact:
   - `contracts/operations/inference-bundle-manifest.schema.json`.
3. `inference-api` переведен на manifest-driven bundle loading:
   - сначала ищется `model-bundle.manifest.json`,
   - затем, если manifest отсутствует, включается legacy fallback на `watch_only_centroid_*`.
4. В `inference-api` введен per-track loading:
   - у `activity`, `arousal_coarse`, `valence_coarse` теперь могут быть разные `model_path` и `feature_names_path`;
   - статус `valence` различает `valence_enabled` и `valence_model_not_available`.
5. `live-inference-api` переведен на тот же bundle-loader pattern:
   - runtime держит единый `LoadedBundle`,
   - поддерживается optional `valence_coarse`,
   - legacy watch-only fallback сохранен.
6. Обновлены service docs и contracts index под новый bundle contract.
7. Добавлены unit-тесты на manifest loading и per-track feature usage.

### Измененные файлы

1. `contracts/operations/inference-bundle-manifest.schema.json`
2. `contracts/README.md`
3. `services/inference-api/src/inference_api/loader.py`
4. `services/inference-api/src/inference_api/api.py`
5. `services/inference-api/tests/test_loader.py`
6. `services/inference-api/README.md`
7. `services/live-inference-api/src/live_inference_api/loader.py`
8. `services/live-inference-api/src/live_inference_api/api.py`
9. `services/live-inference-api/tests/test_api.py`
10. `services/live-inference-api/tests/test_loader.py`
11. `services/live-inference-api/README.md`
12. `docs/backend/fusion-serving-bundle-loading-k5-7.md`
13. `docs/status/execution-status.md`
14. `docs/status/work-log.md`

### Результат

Backend runtime больше не считает `watch_only_centroid_*` каноническим production contract. Зафиксирован правильный target stack для вашей линии (`Polar + Watch`) и добавлена техническая основа для mixed per-track bundle, где `activity`, `arousal` и optional `valence` могут загружаться из разных model/feature profiles.

### Следующий рекомендуемый шаг

`K5.8 - Export selected runtime bundle and align live raw-stream contract`:

1. экспортировать реальные per-track artifacts в manifest-driven bundle;
2. согласовать live raw streams с `Polar cardio + Watch accel/context`;
3. подключить этот bundle как основной runtime path в `inference-api/live-inference-api`.

---

## 2026-03-29 - K5.8 - Runtime bundle export path и live stream contract alignment

### Запрос

Продолжить по протоколу: перейти от `K5.7` к практической интеграции `Polar + Watch` runtime path, чтобы backend принимал правильную sensor shape и появился рабочий способ собирать manifest-driven bundle.

### Что сделано

1. Добавлен script-level export path для runtime manifest:
   - `scripts/ml/build_runtime_bundle_manifest.py`.
2. Скрипт формирует `model-bundle.manifest.json` с per-track блоками:
   - `activity`,
   - `arousal_coarse`,
   - optional `valence_coarse` (scoped).
3. В `live-inference-api` расширен live raw-stream contract:
   - добавлены stream names `polar_hr`, `polar_rr`, `watch_activity_context`, `watch_hrv`;
   - сохранены `watch_accelerometer`, `watch_heart_rate`.
4. В `StreamBuffer` добавлен приоритет heart-source:
   - при наличии `polar_hr` для окна используется он;
   - если `polar_hr` нет, используется `watch_heart_rate`.
5. Обновлены контракты и docs:
   - `contracts/http/live-inference-api.openapi.yaml`,
   - `services/live-inference-api/README.md`,
   - `scripts/ml/README.md`.
6. Добавлены тесты для нового path:
   - WebSocket acceptance test на `polar_hr`,
   - buffer test на приоритет `polar_hr`.

### Измененные файлы

1. `scripts/ml/build_runtime_bundle_manifest.py`
2. `scripts/ml/README.md`
3. `services/live-inference-api/src/live_inference_api/buffer.py`
4. `services/live-inference-api/src/live_inference_api/api.py`
5. `services/live-inference-api/tests/test_api.py`
6. `services/live-inference-api/tests/test_buffer.py`
7. `contracts/http/live-inference-api.openapi.yaml`
8. `services/live-inference-api/README.md`
9. `docs/backend/fusion-serving-k5-8-runtime-bundle-export-and-live-contract.md`
10. `docs/status/execution-status.md`
11. `docs/status/work-log.md`

### Результат

Backend live contract теперь принимает `Polar` cardio stream в каноничном виде (`polar_hr` как preferred source) с backward-compatible fallback на `watch_heart_rate`. Появился воспроизводимый инструмент для сборки `model-bundle.manifest.json`, чтобы подключать per-track runtime bundle без ручного редактирования.

### Проверка

1. `python3 -m pytest -q` (`services/live-inference-api`) -> `13 passed`.
2. `python3 -m pytest -q` (`services/inference-api`) -> `5 passed`.
3. `python3 scripts/ml/build_runtime_bundle_manifest.py --help` -> успешно.

### Следующий рекомендуемый шаг

`K5.9 - Bundle selection and activation`:

1. выбрать и собрать реальный runtime bundle из approved artifact-кандидатов (`activity`, `arousal`, optional `valence`);
2. подключить bundle в `inference-api/live-inference-api` окружение;
3. выполнить end-to-end device/backend валидацию на live capture.

---

## 2026-03-29 - K5.8 (follow-up) - Явная сигнализация fallback heart-source

### Запрос

Сделать явный runtime-сигнал, когда `polar_hr` недоступен и сервер переходит на `watch_heart_rate`.

### Что сделано

1. В `live-inference-api` websocket runtime добавлены явные error-события:
   - `heart_source_fallback_active` при переходе на `watch_heart_rate`,
   - `heart_source_recovered` при возврате на `polar_hr`.
2. В `inference` payload добавлены поля:
   - `heart_source` (`polar_hr` или `watch_heart_rate`),
   - `heart_source_fallback_active` (`true/false`).
3. Обновлен `StreamBuffer` contract:
   - `try_emit_window()` теперь возвращает выбранный heart source вместе с окном.
4. Обновлены OpenAPI и README `live-inference-api`.
5. Добавлены/обновлены тесты на fallback-сигнализацию и приоритет `polar_hr`.

### Измененные файлы

1. `services/live-inference-api/src/live_inference_api/buffer.py`
2. `services/live-inference-api/src/live_inference_api/api.py`
3. `services/live-inference-api/tests/test_api.py`
4. `services/live-inference-api/tests/test_buffer.py`
5. `contracts/http/live-inference-api.openapi.yaml`
6. `services/live-inference-api/README.md`
7. `docs/backend/fusion-serving-k5-8-runtime-bundle-export-and-live-contract.md`
8. `docs/status/execution-status.md`
9. `docs/status/work-log.md`

### Результат

Fallback на `watch_heart_rate` больше не "тихий": клиент получает явное websocket error-событие и видит текущий источник heart-data в каждом inference сообщении.

### Проверка

1. `python3 -m pytest -q` (`services/live-inference-api`) -> `13 passed`.

### Следующий рекомендуемый шаг

`K5.9 - Bundle selection and activation`:

1. подключить реальный production runtime bundle;
2. выполнить device E2E и проверить, что fallback-события появляются только при фактической потере `polar_hr`.

---

## 2026-03-29 - R6.10 - iPhone off-main start-flow и диагностика mirrored transport

### Запрос

Исправить ситуацию, когда iPhone-приложение визуально зависает на `Starting session...`: экран перестает нормально скроллиться и не дает понять, на каком этапе застрял startup.

### Что сделано

1. В `SessionViewModel` запуск длительных операций вынесен с `MainActor`:
   - `prepare/start/stop` теперь выполняются в `Task.detached(priority: .userInitiated)`;
   - UI-состояние (`status`, `detailText`, `runtime gate`, `polar state`) обновляется только через `MainActor`.
2. Для управления жизненным циклом фоновых операций добавлены отдельные task-handles:
   - `prepareTask`;
   - `startTask`;
   - `stopTask`.
3. В `WorkoutSessionTransportIOS` добавлены явные диагностические логи старта mirrored capture:
   - запрос workout authorization;
   - `startWatchApp`;
   - ожидание mirrored session;
   - приход mirrored session handler;
   - отправка `start` envelope.
4. Тем самым следующий device-run теперь должен либо оставлять экран отзывчивым во время старта, либо явно показывать последнюю достигнутую фазу transport startup в логе.
5. Проверена доступная сборка пакета `CaptureKit`: `swift build` проходит.

### Измененные файлы

1. `on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
2. `on-go-ios/packages/CaptureKit/Sources/WatchConnectivityBridge/SessionTransport.swift`
3. `on-go/docs/status/execution-status.md`
4. `on-go/docs/status/work-log.md`

### Результат

Start-flow на iPhone больше не должен удерживать экран на `MainActor`, а лог теперь дает конкретную фазу mirrored transport startup вместо неопределенного `Starting session...`.

### Следующий рекомендуемый шаг

Короткая device-проверка этого инкремента:

1. полностью пересобрать и переустановить `OnGoCapture` на физический iPhone;
2. нажать `Prepare -> Start`;
3. проверить, остается ли экран скроллируемым;
4. если startup все еще не завершается, снять последние строки лога с префиксами `Start step:` и `[WorkoutTransportIOS]`.

---

## 2026-03-29 - R6.11 - iPhone log rendering backpressure for startup stability

### Запрос

После выноса start-flow с `MainActor` iPhone экран перестал зависать сразу, но через несколько секунд снова становился неотзывчивым: не нажимались кнопки и переставал работать скролл.

### Что сделано

1. В `SessionViewModel` логовый поток переведен с немедленного append на batched flush:
   - новые сообщения сначала складываются в `pendingLogEntries`;
   - UI обновляется не чаще одного раза в `250ms`;
   - общий буфер ограничен `120` строками.
2. Добавлено отдельное `renderedLogText`:
   - в UI теперь рендерятся только последние `40` строк;
   - логовое окно получает уже готовый компактный текст вместо сотен отдельных SwiftUI-строк.
3. В `SessionDashboardView` логовый блок упрощен:
   - вместо `LazyVStack` с множеством `Text` используется один `Text(verbatim:)`;
   - это уменьшает стоимость каждого входящего log-update для SwiftUI layout/scroll.
4. Доступная сборка `CaptureKit` повторно проверена через `swift build`.

### Измененные файлы

1. `on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
2. `on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionDashboardView.swift`
3. `on-go/docs/status/execution-status.md`
4. `on-go/docs/status/work-log.md`

### Результат

Если freeze был вызван накоплением и отрисовкой частых логов во время startup, экран теперь должен оставаться заметно более отзывчивым и не деградировать через несколько секунд после `Start`.

### Следующий рекомендуемый шаг

Проверка на устройстве после полной переустановки app:

1. `Prepare -> Start`;
2. убедиться, что экран все еще реагирует через `5-10` секунд после старта;
3. если зависание повторится, снять последние видимые строки лога с префиксами `Start step:` и `[WorkoutTransportIOS]` — тогда следующим шагом уже будет точечный разбор конкретной transport-фазы, а не UI-слоя.

---

## 2026-03-28 - R6.2 - Polar H10 runtime enablement in iPhone build

### Запрос

Исправить ошибку `polar runtime unavailable: PolarBleSdk/RxSwift not linked...`, потому что данные от `Polar H10` не приходят в iPhone runtime и, соответственно, не попадают в дальнейшую обработку.

### Что сделано

1. Найден корневой дефект в `on-go-ios`:
   - `CaptureKit` не объявлял зависимости на `PolarBleSdk` и `RxSwift`,
   - из-за этого `PolarH10AdapterFactory` всегда собирался в ветку `UnsupportedPolarH10Adapter`.
2. В `packages/CaptureKit/Package.swift` добавлены реальные SwiftPM-зависимости:
   - официальный `PolarBleSdk` (`https://github.com/polarofficial/polar-ble-sdk.git`),
   - `RxSwift` (`https://github.com/ReactiveX/RxSwift.git`),
   - `PhoneCapture` теперь зависит от этих продуктов условно для `iOS`.
3. Для iPhone target добавлены обязательные BLE-runtime настройки:
   - `NSBluetoothAlwaysUsageDescription`,
   - `UIBackgroundModes = bluetooth-central`.
4. В `project.yml` зафиксированы `CODE_SIGN_ENTITLEMENTS` для `OnGoCapture` и `OnGoWatchExtension`, чтобы генерация `xcodeproj` оставалась воспроизводимой.
5. Перегенерирован `apps/OnGoCapture/OnGoCapture.xcodeproj`.
6. Проведена проверка:
   - `cd packages/CaptureKit && swift build` проходит после резолва зависимостей,
   - SwiftPM фактически подтянул `PolarBleSdk 6.16.1` и `RxSwift 6.5.0`.

### Измененные файлы

1. `on-go-ios/packages/CaptureKit/Package.swift`
2. `on-go-ios/apps/OnGoCapture/project.yml`
3. `on-go-ios/apps/OnGoCapture/iPhoneApp/Info.plist`
4. `on-go-ios/docs/setup/local-development.md`
5. `on-go-ios/apps/OnGoCapture/OnGoCapture.xcodeproj/project.pbxproj`
6. `on-go/docs/status/execution-status.md`
7. `on-go/docs/status/work-log.md`

### Результат

Главный blocker снят: iPhone build больше не должен всегда падать в `unsupported_runtime` из-за отсутствующего `PolarBleSdk`. После открытия проекта в Xcode и запуска на физическом iPhone приложение должно собираться с живым `LivePolarH10SDKAdapter` и запрашивать Bluetooth permission корректно.

### Следующий рекомендуемый шаг

`R6.3 - Device validation of Polar live path`:

1. открыть `OnGoCapture.xcodeproj` в Xcode;
2. дождаться `Resolve Package Dependencies`;
3. запустить `OnGoCapture` на физическом iPhone;
4. подтвердить, что `Polar source` меняется с `unsupported_runtime` на `live_polar_sdk`, а `Polar` state переходит в `connecting/connected/streaming`.

---

## 2026-03-29 - R6.3 - Polar H10 adapter compile fix for actor isolation

### Запрос

Исправить compile errors в `PolarH10Adapter.swift` после включения официального `PolarBleSdk`: ошибки actor-isolation в `init`, пропущенный `await` и отсутствующие helper-функции для `polar_rr`.

### Что сделано

1. В `LivePolarH10SDKAdapter` убрана настройка SDK observers из `actor init`:
   - wiring `observer/powerStateObserver/deviceFeaturesObserver/deviceHrObserver` перенесен в отдельный actor-isolated метод `configureSDKBindingsIfNeeded()`,
   - метод вызывается из `connect()`.
2. Исправлен async-вызов:
   - в `startCapture()` добавлен `await` для `drainAccumulatedBatches(...)`.
3. Возвращены локальные helper-функции, которые требовались для сборки и генерации `polar_rr`:
   - `makeBackfilledDates(...)`,
   - `makePolarRRSamples(...)`.
4. Проведена проверка:
   - `cd /Users/kgz/Desktop/p/on-go-ios/packages/CaptureKit && swift build` проходит успешно.

### Измененные файлы

1. `on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PolarH10Adapter.swift`
2. `on-go/docs/status/execution-status.md`
3. `on-go/docs/status/work-log.md`

### Результат

`PolarH10Adapter.swift` снова собирается с реальным `PolarBleSdk`, а compile-blockers по actor isolation и отсутствующим helper-функциям сняты.

### Следующий рекомендуемый шаг

`R6.4 - Device validation of Polar live path`:

1. открыть проект в Xcode;
2. запустить на физическом iPhone;
3. подтвердить переход `Polar source -> live_polar_sdk`;
4. проверить, что в логах появляются реальные `polar_hr/polar_rr/polar_ecg/polar_acc` batches.

---

## 2026-03-29 - R6.4 - Polar H10 adapter protocol mutability fix

### Запрос

Исправить новый compile blocker в `PolarH10Adapter.swift`: `Cannot assign to property: 'api' is a 'let' constant` при назначении `observer` и других SDK callbacks.

### Что сделано

1. Найдена причина:
   - `api` был объявлен как `let api: PolarBleApi`,
   - для protocol existential `PolarBleApi` Swift не разрешает присваивать mutable properties (`observer`, `powerStateObserver`, `deviceFeaturesObserver`, `deviceHrObserver`, `automaticReconnection`) через `let`.
2. В `PolarH10Adapter.swift` `api` переведен в `var api: PolarBleApi`.
3. Проведена проверка:
   - `cd /Users/kgz/Desktop/p/on-go-ios/packages/CaptureKit && swift build` проходит успешно.

### Измененные файлы

1. `on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PolarH10Adapter.swift`
2. `on-go/docs/status/execution-status.md`
3. `on-go/docs/status/work-log.md`

### Результат

SDK observer wiring для `PolarBleApi` теперь компилируется корректно, и `CaptureKit` снова собирается без ошибок по `PolarH10Adapter`.

### Следующий рекомендуемый шаг

`R6.5 - Device validation of Polar live path`:

1. открыть проект в Xcode;
2. собрать и запустить на физическом iPhone;
3. подтвердить, что `Polar source = live_polar_sdk`;
4. проверить реальные `polar_*` batches в логах приложения.

---

## 2026-03-29 - R6.5 - Polar H10 Swift 6 sendability bridge fix

### Запрос

Исправить новые Swift 6 concurrency ошибки в `PolarH10Adapter.swift`:
`Passing closure as a 'sending' parameter risks causing data races`
и `Sending 'feature'/'ready'/'unavailable' risks causing data races`.

### Что сделано

1. В `nonisolated` delegate callbacks убрана передача `PolarBleSdkFeature` напрямую в `Task`.
2. Добавлен bridge-слой:
   - `PolarBleSdkFeature` конвертируется в строковый ключ (`feature_hr`, `feature_polar_online_streaming`),
   - в actor передаются только `String` и `[String]` (`Sendable`).
3. Actor-side обработчики обновлены:
   - `handleFeatureReady(..., featureName: String)`,
   - `handleFeaturesReadiness(..., readyFeatureNames: [String], ...)`.
4. Проверка:
   - `cd /Users/kgz/Desktop/p/on-go-ios/packages/CaptureKit && swift build` проходит.

### Измененные файлы

1. `on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PolarH10Adapter.swift`
2. `on-go/docs/status/execution-status.md`
3. `on-go/docs/status/work-log.md`

### Результат

Ошибки sendability/data-race для `PolarH10Adapter` сняты, и `CaptureKit` снова собирается под текущие Swift 6 concurrency checks.

### Следующий рекомендуемый шаг

`R6.6 - Device validation of Polar live path`:

1. запустить app на физическом iPhone;
2. подтвердить `Polar source = live_polar_sdk`;
3. проверить поток `polar_hr/polar_rr/polar_ecg/polar_acc` в runtime логах.

---

## 2026-03-29 - R6.6 - Polar SDK preconcurrency import fix

### Запрос

Исправить Swift 6 ошибку в `PolarH10Adapter.swift`:
`Sending 'settings' risks causing data races` в `requestStreamSettings(...)-> continuation.resume(returning: settings)`.

### Что сделано

1. Источник проблемы: `PolarSensorSetting` приходит из внешнего SDK (`PolarBleSdk`) и не размечен как `Sendable`, что в Swift 6 триггерит strict-concurrency ошибку при передаче через continuation boundary.
2. В `PolarH10Adapter.swift` изменен импорт SDK:
   - `import PolarBleSdk` -> `@preconcurrency import PolarBleSdk`.
3. Проверка:
   - `cd /Users/kgz/Desktop/p/on-go-ios/packages/CaptureKit && swift build` проходит.

### Измененные файлы

1. `on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PolarH10Adapter.swift`
2. `on-go/docs/status/execution-status.md`
3. `on-go/docs/status/work-log.md`

### Результат

Ошибки `Sending 'settings' risks causing data races` для `PolarH10Adapter` сняты, сборка `CaptureKit` снова чисто проходит.

### Следующий рекомендуемый шаг

`R6.7 - Device validation`:

1. запуск на физическом iPhone;
2. проверка `Polar source = live_polar_sdk`;
3. подтверждение поступления `polar_*` батчей в логах.

---

## 2026-03-29 - R6.7 - iPhone log-driven UI update loop mitigation

### Запрос

По runtime-логам зафиксирован warning:
`onChange(of: Int) action tried to update multiple times per frame.`

### Что сделано

1. В `SessionDashboardView` убран лишний `Task { await viewModel.refreshRuntimeGateState() }` из `.onReceive(.onGoCaptureLog)`.
2. Это снижает частые state-update циклы при потоке логов и убирает лишние UI перерисовки в одном кадре.
3. Проверка:
   - `cd /Users/kgz/Desktop/p/on-go-ios/packages/CaptureKit && swift build` проходит.

### Измененные файлы

1. `on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionDashboardView.swift`
2. `on-go/docs/status/execution-status.md`
3. `on-go/docs/status/work-log.md`

### Результат

Снижен риск повторных UI-update циклов при интенсивном логе; warning `onChange(... multiple times per frame)` не должен срабатывать из-за runtime-gate refresh на каждую лог-строку.

### Следующий рекомендуемый шаг

`R6.8 - Device network + live stream validation`:

1. убедиться, что `live-inference-api` реально поднят на `192.168.1.109:8120`;
2. проверить `ON_GO_LIVE_INFERENCE_WS_URL=ws://192.168.1.109:8120/ws/live` (не `http://`);
3. повторить run на iPhone и сверить новые логи.

---

## 2026-03-29 - R6.8 - iPhone start-flow responsiveness hardening

### Запрос

При нажатии `Start` мобильное приложение визуально “виснет”, экран перестает нормально скроллиться.

### Что сделано

1. В `SessionDashboardView` убран принудительный auto-scroll лога на каждое изменение `logEntries.count`.
2. В `SessionViewModel` добавлен флаг `isStartingSession`:
   - повторный `Start` во время старта блокируется,
   - `Prepare` тоже временно отключается на время старта,
   - пользователь получает явный текст `Starting session...`.
3. Live inference connect отвязан от critical path старта:
   - раньше `startSession()` сначала ждал `liveClient.connect()`,
   - теперь capture start выполняется первым, а websocket connect только планируется после успешного старта.
4. Проверка:
   - `cd /Users/kgz/Desktop/p/on-go-ios/packages/CaptureKit && swift build` проходит.

### Измененные файлы

1. `on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
2. `on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionDashboardView.swift`
3. `on-go/docs/status/execution-status.md`
4. `on-go/docs/status/work-log.md`

### Результат

Старт capture больше не должен визуально стопорить экран из-за логового auto-scroll и необязательного websocket-connect на критическом пути. Пользователь должен видеть responsive UI и иметь возможность скроллить лог вручную.

### Следующий рекомендуемый шаг

`R6.9 - Device rerun with fresh logs`:

1. снова нажать `Start` на физическом iPhone;
2. проверить, что экран продолжает скроллиться;
3. прислать новые логи, если останется зависание или таймаут на watch mirroring.

---

## 2026-03-29 - R6.9 - Local backend/live-inference availability verification

### Запрос

Проверить гипотезу, что backend не поднят в Docker, и что из-за этого старт сессии/подключение live-inference ведет себя некорректно.

### Что сделано

1. Проверен локальный Docker stack:
   - `docker compose -f infra/compose/on-go-stack.yml ps` показал, что сервисы были остановлены.
2. Найден локальный model bundle:
   - `data/external/wesad/artifacts/wesad/wesad-v1/watch-only-baseline/models`.
3. Поднят локальный backend для inference/live-inference с bind mount модели на `/models`:
   - `inference-api`,
   - `live-inference-api`.
4. Проверен health:
   - `http://localhost:8100/health` -> `status=ok`, `model_loaded=true`,
   - `http://localhost:8120/health` -> `status=ok`, `model_loaded=true`.
5. Проверен текущий Wi-Fi IP хоста:
   - `ipconfig getifaddr en0` -> `192.168.1.109`,
   - он совпадает с адресом в iPhone scheme для `ON_GO_LIVE_INFERENCE_WS_URL`.

### Измененные файлы

1. `on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
2. `on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PhoneCaptureCoordinator.swift`
3. `on-go/docs/status/execution-status.md`
4. `on-go/docs/status/work-log.md`

### Результат

Backend действительно был не поднят. Сейчас `live-inference-api` и `inference-api` доступны локально на `192.168.1.109:8120` и `192.168.1.109:8100`, поэтому websocket/connect ошибки из-за отсутствующего сервера больше не должны воспроизводиться.

### Следующий рекомендуемый шаг

`R6.10 - Device rerun after backend + start-flow fixes`:

1. повторить `Prepare` -> `Start` на физическом iPhone;
2. проверить, что экран не “замирает” и остается скроллимым;
3. если старт все еще зависает, прислать новый лог с последней строкой `Start step: ...`, чтобы локализовать точный этап (`watch transport`, `Polar connect`, `Polar capture`, `watch mirrored session`).

---

## 2026-03-28 - R6.1 - iPhone Runtime Gate layout hardening

### Запрос

После правок для часов осталась та же проблема на iPhone-экране `Runtime Gate`: длинные значения и причина блокировки визуально не помещаются и выглядят сжатыми/обрезанными.

### Что сделано

1. Экран `SessionDashboardView` переведен на общий `ScrollView`, чтобы блок `Runtime Gate` и лог не упирались в высоту экрана.
2. Заголовок режима переработан:
   - `mode` показывается отдельным крупным блоком;
   - состояние `ready/blocked` вынесено в badge.
3. Поля `Blocked component`, `Polar source`, `Watch transport`, `Watch sensor source` переведены из горизонтального `label/value` в вертикальные строки без принудительного сжатия по ширине.
4. Текст причины блокировки оформлен как отдельный многострочный блок с фоном, чтобы длинные runtime-сообщения читались полностью.

### Измененные файлы

1. `on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionDashboardView.swift`
2. `on-go/docs/status/execution-status.md`
3. `on-go/docs/status/work-log.md`

### Результат

`Runtime Gate` на iPhone теперь должен корректно показывать длинные runtime-статусы и причины блокировки без обрезания значения `watch transport`, `unsupported_runtime` и других длинных строк.

### Следующий рекомендуемый шаг

`E2.43 - Post-gate factual completion rerun continuation-5` (по roadmap), либо прикладной UI-инкремент:

1. прогнать экран на реальном iPhone;
2. проверить длинные строки `unsupported_runtime` / `hkworkout_mirrored_ios` / `live_healthkit_coremotion`;
3. при необходимости отдельно ужать typography под smallest-width device.

---

## 2026-03-28 - R6 - Watch UX hardening и лог отправки батчей

### Запрос

По изображению и реальному использованию переработать экран на часах: кнопки не помещаются, нет нормального скролла, нужен явный просмотр того, что происходит и что отправляется с часов.

### Что сделано

1. Через агентов выполнена переработка watch UI:
   - экран переведен на `ScrollView`,
   - кнопки `Start/Batch/Stop` сделаны круговыми и компактными,
   - сохранена автозагрузка mirror-режима.
2. Добавлен watch-side лог операций:
   - `WatchSessionViewModel` публикует `logEntries` с timestamp,
   - логируются start/stop, ошибки и отправка батчей (`stream + sampleCount`),
   - включен лимит буфера (`180` строк).
3. На watch-экране добавлен блок `Watch Log` с прокручиваемым списком последних событий (показываются последние строки лога).
4. Дополнительно улучшено чтение runtime-gate на iPhone по скриншоту:
   - вместо `LabeledContent` для gate-полей добавлены многострочные строки без обрезания длинных значений (`watch transport` и т.д.).
5. Улучшен текст причины для `unsupported_runtime` в runtime gate:
   - теперь причина явно указывает на отсутствие SDK/неподдерживаемый runtime и нужное действие (физический девайс).

### Измененные файлы

1. `on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionView.swift`
2. `on-go-ios/apps/OnGoCapture/WatchExtension/WatchSessionViewModel.swift`
3. `on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionDashboardView.swift`
4. `on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PhoneCaptureCoordinator.swift`
5. `on-go/docs/status/execution-status.md`
6. `on-go/docs/status/work-log.md`

### Результат

Watch-интерфейс стал пригоден для реального экрана часов: управление не клиппится, действия доступны, а поток отправляемых событий/батчей виден прямо на устройстве.

### Следующий рекомендуемый шаг

`E2.43 - Post-gate factual completion rerun continuation-5` (по roadmap), либо отдельный короткий инкремент `R6.1`:

1. проверить watch UI на реальных размерах (`41/45/49mm`);
2. зафиксировать скриншоты и UX-checklist в runbook;
3. при необходимости поджать типографику/отступы под smallest device.

---

## 2026-03-28 - R1-R5 - Strict real-only capture + replay-only non-live

### Запрос

Вырезать симуляцию из проекта, оставить только реальные device-потоки и replay по уже записанным сессиям; выполнить полный план `R1..R5` с проверкой работоспособности и фиксацией статуса.

### Что сделано

1. Выполнен `R1` в `on-go-ios`:
   - удалены симуляционные runtime-пути (`SimulatedPolarH10Adapter`, `SimulatedWatchSensorAdapter`, `InMemorySessionTransport`, `NoOpUploadClient`);
   - вместо fallback включены fail-fast реализации с явными runtime-ошибками.
2. Выполнен `R2` в `on-go-ios`:
   - добавлен strict `real_only_mode` gate в `PhoneCaptureCoordinator`;
   - старт сессии блокируется, если не выполнены условия: `polar=live_polar_sdk`, `watch transport=hkworkout_mirrored_ios`, `watch sensor=live_healthkit_coremotion`;
   - в iPhone UI добавлен явный блок `Runtime Gate` (режим, состояние, блокирующий компонент, причина), кнопка `Start` отключается при `blocked`.
3. Выполнен `R3` в backend:
   - в `live-inference-api` добавлен gate `source_mode=live` для `stream_batch`;
   - для missing/non-live источников возвращается структурированная ошибка `live_source_required`;
   - replay-сервис оставлен без функциональных изменений.
4. Выполнен `R4` (docs cleanup):
   - в `on-go` и `on-go-ios` удалены упоминания simulation/fallback capture как поддерживаемого режима;
   - non-live путь зафиксирован как replay-only по ранее записанным raw sessions.
5. Выполнен `R5` (verification):
   - `swift build` для `CaptureKit` проходит;
   - `live-inference-api` tests: `10 passed`;
   - `inference-api` tests: `3 passed`;
   - docker-stack (`ingest/replay/inference/personalization/live-inference`) поднимается;
   - `POST /v1/predict` отвечает;
   - WS проверка подтверждает gate:
     - без `source_mode` -> `{"code":"live_source_required",...}`;
     - с `source_mode=live` -> корректный `inference` ответ.

### Измененные файлы

1. `on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PolarH10Adapter.swift`
2. `on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchSensorAdapter.swift`
3. `on-go-ios/packages/CaptureKit/Sources/WatchConnectivityBridge/SessionTransport.swift`
4. `on-go-ios/packages/CaptureKit/Sources/WatchCapture/WatchCaptureController.swift`
5. `on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PhoneCaptureCoordinator.swift`
6. `on-go-ios/packages/CaptureKit/Sources/BackendClient/SessionUploadClient.swift`
7. `on-go-ios/packages/CaptureKit/Sources/BackendClient/NoOpUploadClient.swift` (удален)
8. `on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
9. `on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionDashboardView.swift`
10. `on-go-ios/README.md`
11. `on-go-ios/docs/setup/local-development.md`
12. `on-go-ios/docs/architecture/capture-runtime.md`
13. `on-go-ios/docs/live-streaming-changes.md`
14. `on-go/services/live-inference-api/src/live_inference_api/api.py`
15. `on-go/services/live-inference-api/tests/test_api.py`
16. `on-go/contracts/http/live-inference-api.openapi.yaml`
17. `on-go/services/live-inference-api/README.md`
18. `on-go/contracts/http/README.md`
19. `on-go/services/README.md`
20. `on-go/services/replay-service/README.md`
21. `on-go/docs/setup/live-streaming-integration.md`
22. `on-go/docs/architecture/production-backend.md`
23. `on-go/docs/capture/device-e2e-validation-runbook.md`
24. `on-go/docs/setup/local-docker-setup.md`
25. `on-go/docs/status/execution-status.md`
26. `on-go/docs/status/work-log.md`

### Результат

Симуляционный capture-runtime отключен: система работает в strict real-only режиме для live-capture и live-inference, а non-live проверки формально ограничены replay-контуром по уже записанным сессиям.

### Следующий рекомендуемый шаг

`E2.43 - Post-gate factual completion rerun continuation-5`:

1. на/после `2026-04-06` заполнить реальные `weekly-summary.md` и `handoff-checklist.csv`;
2. выполнить factual completion run;
3. зафиксировать итоговый `pass/warn/fail`.

---

## 2026-03-29 - M7.0 - Polar-first architecture research and implementation plan

### Запрос

Провести исследование и подготовить технический план перехода на Polar-first модель: использовать `Polar H10` для сердечных метрик (включая WESAD-подобные HRV/derived features), использовать часы только для движения, покрыть `activity/arousal/valence`, а также включить план внедрения и делегирования этапов.

### Что сделано

1. Выполнен аудит текущего контура `on-go/on-go-ios`:
   - подтверждено наличие расширенного RR/HRV/ECG feature extraction в `signal-processing-worker`;
   - подтверждено, что live pipeline доставляет `polar_hr` и motion streams;
   - зафиксирован bottleneck: текущие runtime bundles дают фактически константные предикты.
2. Сформирован целевой Polar-first policy:
   - cardio/autonomic признаки — только из `Polar H10`;
   - watch — только motion/context;
   - запрет watch HR/HRV в финальном feature contract (кроме временного runtime fallback).
3. Составлен WESAD-aligned prioritized feature list (`must/should/could`) для `activity/arousal/valence`.
4. Подготовлен детальный внедренческий план по инкрементам `P1..P8`:
   - `preprocessing -> training -> runtime bundle export -> live-inference-api -> on-go-ios -> acceptance`;
   - для каждого шага добавлены зависимости, артефакты, риски и критерии готовности.
5. Добавлена матрица делегирования по субагентам (`Feature Architect`, `Modeling Lead`, `Runtime Integrator`, `Validation QA`).

### Измененные файлы

1. `on-go/docs/backend/polar-first-model-implementation-plan.md`
2. `on-go/docs/status/execution-status.md`
3. `on-go/docs/status/work-log.md`

### Результат

Готов исполнимый technical roadmap для перехода на Polar-first модельный стек с явным фокусом на HRV/ECG-derived признаки из `Polar H10`, motion-only ролью watch и поэтапным внедрением в training/runtime/mobile контуры.

### Следующий рекомендуемый шаг

`M7.1 - P1 Feature Contract Freeze`:

1. формализовать канонический Polar-first feature contract (schema + docs);
2. зафиксировать source-policy (`polar_only_cardio`, `watch_motion_only`) в training/runtime;
3. добавить anti-collapse precheck для runtime-candidate models до следующего bundle export.

---

## 2026-03-29 - M7.1 - P1 Feature Contract Freeze + runtime policy guardrails

### Запрос

Запустить делегирование следующего инкремента после `M7.0`: формализовать `Polar-first` feature contract и добавить минимальную runtime policy-валидацию в `live-inference-api`, не ломая существующий `source_mode=live` gate.

### Что сделано

1. Зафиксирован канонический контракт признаков:
   - добавлена JSON schema `polar-first-feature-contract-v1` с source-политиками (`polar_cardio_only=true`, `watch_motion_only=true`);
   - описаны required/optional streams по трекам `activity/arousal_coarse/valence_coarse`;
   - зафиксированы запрещенные watch-cardio streams/feature prefixes.
2. Добавлен companion doc к контракту с policy-правилами и примерами.
3. В `live-inference-api` добавлен policy guardrail:
   - при inference без полного primary набора (`polar_hr`, `watch_accelerometer`) сервер отправляет структурированный policy-signal `polar_primary_policy_fallback`;
   - `watch_heart_rate` остается допустимым только как fallback path (существующий `heart_source_fallback_active` сохранен).
4. Обновлены unit/integration tests `live-inference-api` под новый policy flow:
   - happy-path с primary streams;
   - fallback path с policy warning + fallback warning;
   - existing real-source gate остается валидным.
5. Проверка выполнена:
   - `python3 -m pytest -q` в `services/live-inference-api`: `15 passed`.

### Измененные файлы

1. `on-go/contracts/personalization/polar-first-feature-contract.schema.json`
2. `on-go/docs/backend/polar-first-feature-contract.md`
3. `on-go/services/live-inference-api/src/live_inference_api/api.py`
4. `on-go/services/live-inference-api/tests/test_api.py`
5. `on-go/docs/status/execution-status.md`
6. `on-go/docs/status/work-log.md`

### Результат

`Polar-first` policy формально закреплен контрактом, а live runtime теперь явно сигнализирует, когда primary cardio policy не выполнена и включен fallback; тестовый контур `live-inference-api` остается зеленым.

### Следующий рекомендуемый шаг

`M7.2 - P2 Offline Feature Pipeline Alignment`:

1. добавить в `signal-processing-worker` явные feature-family selectors (`polar_cardio_core`, `polar_cardio_extended`, `watch_motion_core`);
2. ввести quality-gated export для RR/ECG family перед training;
3. подготовить machine-readable feature manifest для последующего `P3` training runs.

---

## 2026-03-29 - M7.2 - P2 Offline Feature Pipeline Alignment

### Запрос

Выполнить `M7.2` через делегирование в сабагенты: выровнять offline feature pipeline под `Polar-first` policy, добавить selectors по семействам признаков и quality-gated export для RR/ECG перед этапом обучения.

### Что сделано

1. В `signal-processing-worker` добавлены явные family selectors и source-tags:
   - `polar_cardio_core`;
   - `polar_cardio_extended`;
   - `watch_motion_core`.
2. Расширены модели preprocessing-результатов:
   - `FeatureWindow` теперь содержит `feature_family_tags` и поля quality-gate (`status/action/flags`);
   - `StreamFeatureSummary` включает selectors/tags и агрегаты quality-gate;
   - `StreamQualitySummary` дополнен gate-статусами и счетчиками marked/dropped окон.
3. Реализован quality-gated export feature windows:
   - для RR/ECG окон вводится mark/drop логика;
   - severe-окна не попадают в экспорт `feature_windows`;
   - агрегированная статистика quality-gate пишется в `quality` и `feature_summary`.
4. Обновлен CSV export `windows.features` новыми колонками:
   - `feature_family_tags`;
   - `quality_gate_status`;
   - `quality_gate_action`;
   - `quality_gate_flags`.
5. Добавлены/обновлены unit-тесты и документация для P2:
   - inclusion/exclusion по семействам;
   - quality-gated сценарии RR/ECG;
   - README-описание P2-контуров в worker и tests.
6. Проверка выполнена локально:
   - `cd services/signal-processing-worker && python3 -m pytest -q` -> `16 passed`.

### Измененные файлы

1. `on-go/services/signal-processing-worker/src/signal_processing_worker/models.py`
2. `on-go/services/signal-processing-worker/src/signal_processing_worker/service.py`
3. `on-go/services/signal-processing-worker/tests/test_service.py`
4. `on-go/services/signal-processing-worker/README.md`
5. `on-go/services/signal-processing-worker/tests/README.md`
6. `on-go/docs/status/execution-status.md`
7. `on-go/docs/status/work-log.md`

### Результат

Offline feature pipeline приведен к `Polar-first` политике на уровне сигнал-процессинга: family selectors и quality-gated export уже формируют устойчивый вход для следующего шага обучения (`P3`) без смешивания watch-cardio признаков в целевом production-наборе.

### Следующий рекомендуемый шаг

`M7.3 - P3 Training Dataset Build (Polar-first)`:

1. обновить `modeling-baselines` run-kind под `activity/arousal/valence` c `Polar-first` источниками;
2. запустить ablation matrix (`polar_only`, `watch_motion_only`, `polar+watch_motion`);
3. собрать claim-grade artifacts и проверить anti-collapse поведение предиктов.

---

## 2026-03-29 - M7.3 - P3 Training Dataset Build (Polar-first)

### Запрос

Выполнить `M7.3`: внедрить в `modeling-baselines` Polar-first training run с явной ablation matrix (`polar_only`, `watch_motion_only`, `polar+watch_motion`), добавить anti-collapse проверку и подготовить claim-grade артефакты по стандарту отчетности.

### Что сделано

1. В `modeling-baselines` добавлен новый run-kind:
   - `m7-3-polar-first-training-dataset-build`;
   - alias: `polar-first-training-dataset-build`.
2. Реализован отдельный pipeline `M7.3` с 3 вариантами ablation:
   - `polar_only`;
   - `watch_motion_only`;
   - `polar+watch_motion`.
3. Добавлена anti-collapse диагностика в classification tracks:
   - статус (`ok/near_constant/collapsed/...`);
   - dominant share;
   - число уникальных предсказанных классов;
   - summary-блок `anti_collapse_summary` в `evaluation-report`.
4. Расширены writers/отчеты под `M7.3`:
   - `evaluation-report.json`;
   - `predictions-test.csv`;
   - `per-subject-metrics.csv`;
   - `model-comparison.csv`;
   - `research-report.md`;
   - `plots/`.
5. Обновлены tests/docs:
   - unit/contract coverage на run-kind, ablation matrix и anti-collapse;
   - README runbook для `M7.3`;
   - backend note с контрактом `M7.3` и report template.
6. Выявлены и исправлены runtime-дефекты по итогам реального запуска:
   - `KeyError: model_family` в report-summary;
   - рассинхрон полей в `model-comparison.csv` writer;
   - несовместимость plotting helper (`delta_vs_watch_only` vs `delta_vs_polar_only`) через backward-compatible alias.
7. Выполнен реальный запуск `M7.3` на локальном `WESAD`:
   - `experiment_id`: `m7-3-polar-first-training-dataset-build-20260329T122224Z`;
   - артефакты сохранены в `data/external/wesad/artifacts/wesad/wesad-v1/m7-3-polar-first-training-dataset-build/`.
8. Зафиксирован результат anti-collapse gate:
   - `passed=false`;
   - flagged row: `polar_only/activity` (`near_constant`, dominant share `0.933333`).

### Измененные файлы

1. `on-go/services/modeling-baselines/src/modeling_baselines/main.py`
2. `on-go/services/modeling-baselines/src/modeling_baselines/pipeline.py`
3. `on-go/services/modeling-baselines/tests/test_pipeline.py`
4. `on-go/services/modeling-baselines/tests/test_m7_3_polar_first_contract.py`
5. `on-go/services/modeling-baselines/README.md`
6. `on-go/services/modeling-baselines/tests/README.md`
7. `on-go/docs/backend/m7-3-polar-first-ablation-contract.md`
8. `on-go/docs/status/execution-status.md`
9. `on-go/docs/status/work-log.md`

### Результат

`M7.3` закрыт: Polar-first training run внедрен и реально выполнен, claim-grade артефакты сформированы; anti-collapse проверка встроена и выявила деградацию в `polar_only/activity`, что формирует вход для следующего decision-step `M7.4`.

### Следующий рекомендуемый шаг

`M7.4 - P4 Model Selection and Runtime-Candidate Gate`:

1. выбрать runtime-кандидатов по трекам `activity/arousal/valence` из `M7.3` артефактов;
2. формализовать machine-readable verdict (`pass/fail`) с учетом anti-collapse;
3. подготовить remediation-plan для flagged варианта(ов) до перехода к `P5` runtime bundle export.

---

## 2026-03-29 - M7.4 - P4 Model Selection and Runtime-Candidate Gate

### Запрос

Довести предыдущую ветку до конца: выполнить `M7.4` после `M7.3`, получить machine-readable gate verdict и явно зафиксировать, можно ли переходить к `P5`.

### Что сделано

1. В `modeling-baselines` добавлен новый run-kind:
   - `m7-4-runtime-candidate-gate`.
2. Реализован gate-runner, который:
   - читает `M7.3` `evaluation-report.json`;
   - проверяет winner по трекам (`activity`, `arousal_coarse`, `valence_coarse`);
   - проверяет anti-collapse summary и flagged rows;
   - формирует verdict `pass/fail` + remediation actions.
3. Добавлены артефакты `M7.4`:
   - `runtime-candidate-verdict.json`;
   - `runtime-candidate-report.md`.
4. Добавлены unit-тесты для `M7.4` gate логики (pass/fail сценарии).
5. Выполнен реальный `M7.4` запуск поверх реального `M7.3` отчета:
   - `experiment_id`: `m7-4-runtime-candidate-gate-20260329T165340Z`;
   - `gate_verdict = fail`;
   - `gate_passed = false`.
6. Зафиксированы причины fail:
   - `global_issues`: `anti_collapse_summary_failed`, `flagged_rows_present`;
   - track failure: `arousal_coarse` -> `claim_not_supported`.

### Измененные файлы

1. `on-go/services/modeling-baselines/src/modeling_baselines/main.py`
2. `on-go/services/modeling-baselines/src/modeling_baselines/pipeline.py`
3. `on-go/services/modeling-baselines/tests/test_pipeline.py`
4. `on-go/services/modeling-baselines/README.md`
5. `on-go/docs/backend/m7-4-runtime-candidate-gate.md`
6. `on-go/docs/status/execution-status.md`
7. `on-go/docs/status/work-log.md`

### Результат

`M7.4` завершен как gate-step: runtime promotion в `P5` заблокирован по объективным критериям (`fail` verdict). Формально подтверждена необходимость remediation-loop перед экспортом runtime bundle.

### Следующий рекомендуемый шаг

`M7.4.1 - P4 Remediation Loop (anti-collapse + arousal claim support)`:

1. устранить `polar_only/activity` near-constant collapse;
2. поднять `arousal_coarse` winner до `claim_status=supported`;
3. повторить `M7.3` и затем `M7.4` до получения `gate_verdict=pass`.

---

## 2026-03-29 - M7.4.1 - P4 Remediation Loop (anti-collapse + arousal claim support)

### Запрос

Продолжить после `M7.4 fail`: выполнить remediation через сабагентов, повторить `M7.3 -> M7.4` и довести runtime-candidate gate до `pass`.

### Что сделано

1. Через сабагенты выполнена remediation-итерация в `modeling-baselines`:
   - в `M7.3` для Polar-first абляций переключены классификаторы на `sgd_linear`;
   - добавлен более строгий winner-selection приоритет (`supported + anti_collapse_ok` перед fallback);
   - в `M7.4` добавлен guardrail-пересчет runtime кандидатов из `model_comparison` (не только из precomputed summary).
2. Расширены tests/docs:
   - усилены guardrail-тесты `M7.4` (track_failures/global_issues/remediation_actions/next-step поля);
   - добавлен remediation-loop doc `M7.4.1` и обновлены runbook sections.
3. Локальная верификация:
   - `python3 -m pytest -q services/modeling-baselines/tests` -> `46 passed`.
4. Выполнен реальный rerun `M7.3`:
   - `experiment_id`: `m7-3-polar-first-training-dataset-build-20260329T171302Z`;
   - `anti_collapse_passed=true`;
   - winners:
     - `activity` -> `watch_motion_only`, `supported`, `ok`;
     - `arousal_coarse` -> `polar+watch_motion`, `supported`, `ok`;
     - `valence_coarse` -> `watch_motion_only`, `supported`, `ok`.
5. Выполнен реальный rerun `M7.4`:
   - `experiment_id`: `m7-4-runtime-candidate-gate-20260329T171309Z`;
   - `gate_verdict=pass`, `gate_passed=true`.

### Измененные файлы

1. `on-go/services/modeling-baselines/src/modeling_baselines/pipeline.py`
2. `on-go/services/modeling-baselines/src/modeling_baselines/main.py`
3. `on-go/services/modeling-baselines/tests/test_pipeline.py`
4. `on-go/services/modeling-baselines/tests/test_m7_3_polar_first_contract.py`
5. `on-go/services/modeling-baselines/README.md`
6. `on-go/services/modeling-baselines/tests/README.md`
7. `on-go/docs/backend/m7-4-runtime-candidate-gate.md`
8. `on-go/docs/backend/m7-4-1-remediation-loop.md`
9. `on-go/docs/status/execution-status.md`
10. `on-go/docs/status/work-log.md`

### Результат

`M7.4.1` завершен успешно: remediation сняла блокеры `M7.4`, runtime-candidate gate стал `pass`, переход к `P5` разблокирован.

### Следующий рекомендуемый шаг

`M7.5 - P5 Runtime Bundle Export`:

1. экспортировать runtime bundle из одобренных кандидатов `activity/arousal/valence`;
2. закрепить manifest + feature-names contracts;
3. выполнить bundle smoke-check перед `P6`.

---

## 2026-03-29 - M7.5 - P5 Runtime Bundle Export

### Запрос

Выполнить `M7.5` с делегированием: экспортировать runtime bundle из одобренных `M7.4` кандидатов, зафиксировать manifest/feature names и подтвердить загрузку bundle runtime loader-ом.

### Что сделано

1. Через сабагенты реализован новый run-kind:
   - `m7-5-runtime-bundle-export` в `modeling-baselines`.
2. Логика `M7.5`:
   - читает `m7-4-runtime-candidate-gate/runtime-candidate-verdict.json`;
   - fail-fast при `gate_passed=false`;
   - экспортирует per-track artifacts для `activity`, `arousal_coarse`, `valence_coarse`:
     - `*.joblib`;
     - `*_feature_names.json`;
   - собирает `model-bundle.manifest.json`;
   - пишет `runtime-bundle-export-report.json` и `runtime-bundle-smoke-summary.json`.
3. Добавлены/обновлены tests/docs/contract:
   - unit/contract tests для fail-fast и successful export;
   - runbook `M7.5` в README;
   - backend doc `M7.5 runtime bundle export`.
4. Локальная верификация:
   - `python3 -m pytest -q services/modeling-baselines/tests` -> `51 passed`.
5. Реальный запуск `M7.5`:
   - `experiment_id`: `m7-5-runtime-bundle-export-20260329T172500Z`;
   - output root: `data/external/wesad/artifacts/wesad/wesad-v1/m7-5-runtime-bundle-export/`.
6. Runtime smoke-check загрузки:
   - `PYTHONPATH=src python3 ... from inference_api.loader import load_model_bundle`;
   - `uses_manifest=true`;
   - tracks: `activity`, `arousal_coarse`, `valence_coarse`;
   - feature counts: `20/25/20`.

### Измененные файлы

1. `on-go/services/modeling-baselines/src/modeling_baselines/main.py`
2. `on-go/services/modeling-baselines/src/modeling_baselines/pipeline.py`
3. `on-go/services/modeling-baselines/tests/test_pipeline.py`
4. `on-go/services/modeling-baselines/tests/test_m7_5_runtime_bundle_export_contract.py`
5. `on-go/services/modeling-baselines/README.md`
6. `on-go/services/modeling-baselines/tests/README.md`
7. `on-go/docs/backend/m7-5-runtime-bundle-export.md`
8. `on-go/docs/status/execution-status.md`
9. `on-go/docs/status/work-log.md`

### Результат

`M7.5` завершен: runtime bundle экспортируется из `M7.4 pass` кандидатов в manifest-driven формате и успешно загружается runtime loader-ом.

### Следующий рекомендуемый шаг

`M7.6 - P6 Live Inference API Polar-first Online Feature Parity`:

1. выровнять online feature extraction в `live-inference-api` с профилями `M7.5` bundle;
2. добавить coverage/feature-count telemetry по трекам;
3. подтвердить websocket parity-smoke на контролируемых сценариях.

---

## 2026-03-29 - M7.6 - P6 Live Inference API Polar-first Online Feature Parity

### Запрос

Подготовить tests + docs/status updates для live-inference-api parity и telemetry шага `M7.6`.

### Что сделано

1. Добавлен backend step doc `M7.6` с websocket telemetry contract, acceptance-smoke и Polar-first arousal chest-prefix rule.
2. Расширен `services/live-inference-api/README.md` секцией про telemetry parity и примером нового websocket payload.
3. Добавлены тесты:
   - bundle-backed parity check для `M7.5` arousal track chest-prefixed feature names;
   - websocket telemetry contract test for `feature_count_total` / `feature_count_nonzero` / `feature_coverage_by_track`.
4. Обновлены status docs:
   - `M7.6` помечен `completed`;
   - next logical step advanced to `M7.7`.
5. Локальная верификация:
   - `python3 -m pytest -q tests` в `services/live-inference-api` -> `17 passed`.

### Измененные файлы

1. `services/live-inference-api/tests/test_loader.py`
2. `services/live-inference-api/tests/test_api.py`
3. `services/live-inference-api/README.md`
4. `docs/backend/m7-6-live-inference-polar-first-parity.md`
5. `docs/status/execution-status.md`
6. `docs/status/work-log.md`

### Результат

`M7.6` завершен: live-inference-api websocket contract now exposes the Polar-first telemetry block, including track-level coverage and arousal chest-prefixed parity when `polar_hr` is streamed.

### Следующий шаг

`M7.7 - P7 on-go-ios Integration for Polar-first Runtime`.

---

## 2026-03-29 - M7.7 - P7 on-go-ios Integration for Polar-first Runtime

### Запрос

Выполнить `M7.7` для `on-go-ios`: подключить новый websocket telemetry contract (`M7.6`) в live клиент/UI, сохранить real-only forwarding policy и зафиксировать integration checklist + переход к `M7.8`.

### Что сделано

1. В `on-go-ios` реализовано потребление telemetry полей в live клиенте:
   - добавлен typed parser `LiveInferenceTelemetry` для полей `heart_source`, `heart_source_fallback_active`, `feature_count_total`, `feature_count_nonzero`, `feature_coverage_by_track`;
   - в `LiveInferenceClient` добавлен `@Published telemetry`, логирование parity summary при изменениях и проксирование telemetry в UI слой;
   - в `SessionDashboardView` добавлены UI quality сигналы: `Cardio fallback` badge, heart source, aggregate feature counts, per-track coverage (`activity/arousal_coarse/valence_coarse`) с акцентом на `arousal_coarse`.
2. Исправлен контрактный mapping coverage ключей в iOS parser:
   - backend отправляет `expected_feature_count/present_feature_count/nonzero_feature_count`;
   - parser теперь читает эти ключи (с backward-compatible fallback на короткие имена).
3. Добавлен backend integration doc `docs/backend/m7-7-on-go-ios-polar-first-runtime-integration.md`:
   - websocket fields consumed by iOS;
   - UI quality signals for heart-source fallback and coverage counters;
   - integration checklist;
   - acceptance criteria for a 10+ minute real-device session.
4. Обновлен `on-go-ios/docs/live-streaming-changes.md`:
   - добавлены новые telemetry fields из `M7.6`;
   - описаны UI quality signals;
   - добавлены troubleshooting steps для websocket, fallback и coverage mismatch.
5. Обновлены status docs:
   - `M7.7` помечен `completed`;
   - next step advanced to `M7.8 - P8 Acceptance and Claim Gate`.
6. Локальная верификация:
   - `swift build` в `/Users/kgz/Desktop/p/on-go-ios/packages/CaptureKit` проходит;
   - parser coverage-mapping синхронизирован с контрактом `M7.6`.

### Измененные файлы

1. `docs/backend/m7-7-on-go-ios-polar-first-runtime-integration.md`
2. `/Users/kgz/Desktop/p/on-go-ios/docs/live-streaming-changes.md`
3. `/Users/kgz/Desktop/p/on-go-ios/packages/CaptureKit/Sources/BackendClient/LiveInferenceTelemetry.swift`
4. `/Users/kgz/Desktop/p/on-go-ios/packages/CaptureKit/Sources/BackendClient/LiveInferenceClient.swift`
5. `/Users/kgz/Desktop/p/on-go-ios/apps/OnGoCapture/iPhoneApp/Features/SessionDashboardView.swift`
6. `docs/status/execution-status.md`
7. `docs/status/work-log.md`

### Результат

`M7.7` закрыт как runtime integration шаг: iOS live-клиент и dashboard теперь потребляют telemetry контракт `M7.6`, показывают heart-source fallback/coverage quality signals и сохраняют real-only forwarding policy; roadmap переведен на `M7.8`.

### Следующий шаг

`M7.8 - P8 Acceptance and Claim Gate`.

## 2026-03-29 - M7.8 - P8 Acceptance and Claim Gate

### Запрос

Inspect produced M7.8 artifacts, write the backend gate doc, and update execution status conservatively based on factual acceptance evidence.

### Что сделано

1. Проверен acceptance bundle по пути `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-8-acceptance-claim-gate/`.
2. Считаны фактические артефакты:
   - `acceptance-gate-report.json`
   - `acceptance-gate-report.md`
   - `protocol-phase-trace.csv`
   - `websocket-inference-log.jsonl`
3. Подтверждено из отчета:
   - `gate_decision=blocked`;
   - `device_protocol_validated=false`;
   - `real_device_evidence_present=false`.
4. Создан/обновлен backend-doc [m7-8-acceptance-claim-gate.md](/Users/kgz/Desktop/p/on-go/docs/backend/m7-8-acceptance-claim-gate.md) с factual run summary, trace summary и blocked decision.
5. Обновлен [execution-status.md](/Users/kgz/Desktop/p/on-go/docs/status/execution-status.md):
   - `M7.8` зафиксирован как `blocked`;
   - next recommended step set to `M7.8.1 - factual physical-device acceptance run`.
6. Runtime source code не изменялся.

### Changed files

1. `docs/backend/m7-8-acceptance-claim-gate.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`

### Command output summary

1. `acceptance-gate-report.json` contains `experiment_id=m7-8-acceptance-claim-gate-20260329T175533Z`, `gate_decision=blocked`, `device_protocol_validated=false`, `real_device_evidence_present=false`.
2. `protocol-phase-trace.csv` shows the three phases `rest -> movement -> recovery`, `12` sent batches, `5` inference messages, and `0` errors.
3. `websocket-inference-log.jsonl` shows repeated inference payloads with `heart_source=polar_hr`, `feature_count_total=25`, `feature_count_nonzero=20`, and the same missing `watch_bvp_c0` feature set.

### Result

`M7.8` blocked because the factual report does not validate the device protocol and does not contain real-device evidence.

### Next recommended step

`M7.8.1 - factual physical-device acceptance run`

---

## 2026-03-29 - M7.9 (planning) - Polar-expanded fusion implementation plan freeze

### Запрос

Пользователь попросил зафиксировать детальный план: расширить модель до полного набора метрик из `Polar H10` (включая вычисляемые из raw RR/HR признаки), оставить часы источником движения, и подготовить реализацию на следующий день.

### Что сделано

1. Подготовлен отдельный подробный план реализации `M7.9`:
   - target runtime policy (`Polar` как primary cardio, watch как motion-only);
   - расширенный feature contract (`RR/HRV/frequency/nonlinear/quality/cross-modal`);
   - train/serve parity требования;
   - retraining/evaluation/reporting/rollout/canary план.
2. В `execution-status` обновлен `Следующий рекомендуемый шаг` на пользовательский приоритет `M7.9`.
3. В таблицу шагов добавлен `M7.9` со статусом `next` и ссылкой на план-артефакт.
4. Реализация кода/моделей не запускалась в этом шаге; зафиксирована только planning-база для старта работ завтра.

### Измененные файлы

1. `docs/backend/m7-9-polar-expanded-fusion-implementation-plan.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`

### Результат

Подробный план `M7.9` сохранен в репозитории и готов как стартовая спецификация для завтрашней реализации.

### Следующий шаг

`M7.9 - Polar-expanded fusion implementation kickoff (user-priority)`

---

## 2026-03-30 - M7.9 - Polar-expanded fusion implementation kickoff

### Запрос

Пользователь подтвердил запуск `M7.9`: реализовать расширенный Polar-first fusion инкремент с RR/HRV/quality/cross-modal feature-space, retraining и runtime bundle export.

### Что сделано

1. В `modeling-baselines` добавлены новые run-kind:
   - `m7-9-polar-expanded-fusion-benchmark`;
   - `m7-9-runtime-bundle-export`.
2. В offline feature extraction добавлены `M7.9` proxy-фичи:
   - `chest_rr_*` (RR/HRV proxy из chest ECG окна),
   - `polar_quality_*`,
   - `fusion_hr_motion_*`.
3. В `live-inference-api` добавлен RR path в runtime окно:
   - `StreamBuffer` возвращает RR samples для окна;
   - required primary streams теперь берутся из manifest (`required_live_streams`) с fallback на дефолт;
   - online extractor поддерживает RR/quality/cross-modal proxy фичи в manifest-layout режиме.
4. Выполнены factual `M7.9` прогоны:
   - `m7-9-polar-expanded-fusion-benchmark-20260330T160125Z`;
   - `m7-9-runtime-bundle-export-20260330T160150Z`.
5. Экспортирован новый runtime bundle:
   - `bundle_id=on-go-m7-9-polar-expanded-runtime-bundle`,
   - `bundle_version=v2`,
   - `required_live_streams=[watch_accelerometer, polar_hr, polar_rr]`.
6. Добавлен backend-отчет шага: `docs/backend/m7-9-polar-expanded-fusion.md`.
7. Пройдены локальные тесты:
   - `services/modeling-baselines`: `24 passed`;
   - `services/live-inference-api`: `15 passed`.

### Измененные файлы

1. `services/modeling-baselines/src/modeling_baselines/main.py`
2. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
3. `services/modeling-baselines/tests/test_pipeline.py`
4. `services/modeling-baselines/README.md`
5. `services/live-inference-api/src/live_inference_api/features.py`
6. `services/live-inference-api/src/live_inference_api/buffer.py`
7. `services/live-inference-api/src/live_inference_api/api.py`
8. `services/live-inference-api/tests/test_features.py`
9. `services/live-inference-api/tests/test_buffer.py`
10. `services/live-inference-api/tests/test_api.py`
11. `docs/backend/m7-9-polar-expanded-fusion.md`
12. `docs/status/execution-status.md`
13. `docs/status/work-log.md`

### Результат

`M7.9` выполнен: внедрен расширенный modeling+runtime контур, выполнены factual training/export runs и выпущен `v2` manifest-driven runtime bundle с обязательным `polar_rr`.

### Следующий шаг

`M7.10 - Polar-expanded factual device acceptance and canary gate`


---

## 2026-03-30 - M7.10 - Polar-expanded factual device acceptance and canary gate

### Запрос

Пользователь подтвердил `M7.10`: выполнить factual device acceptance/canary gate для runtime bundle `M7.9` и зафиксировать claim-gate решение.

### Что сделано

1. Расширен acceptance runner `scripts/ml/m7_8_acceptance_claim_gate.py` для `M7.10`-режима:
   - добавлена отправка `polar_rr` (`--include-polar-rr`);
   - добавлен параметр `--experiment-prefix`;
   - добавлен canary summary по `activity/arousal` в JSON/MD отчеты.
2. Выполнен factual rerun `M7.10`:
   - команда: `python3 scripts/ml/m7_8_acceptance_claim_gate.py --include-polar-rr --experiment-prefix m7-10-polar-expanded-acceptance-canary-gate --output-dir data/external/wesad/artifacts/wesad/wesad-v1/m7-10-polar-expanded-acceptance-canary-gate --context internal_dashboard`;
   - `experiment_id`: `m7-10-polar-expanded-acceptance-canary-gate-20260330T160939Z`.
3. Подтверждены фактические результаты по артефактам:
   - `streams_sent=[watch_accelerometer, polar_hr, polar_rr]`;
   - `inference_count=5`, `error_count=0`, `heart_source=polar_hr` во всех ответах;
   - canary evidence присутствует: `activity_canary_present=true`, `arousal_canary_present=true`.
4. Gate-решение зафиксировано как `blocked`, так как `real_device_evidence_present=false` и `device_protocol_validated=false`.
5. Добавлен backend-отчет шага `M7.10` и обновлены status docs (`execution-status`, `work-log`) с переводом следующего шага на `M7.10.1`.

### Измененные файлы

1. `scripts/ml/m7_8_acceptance_claim_gate.py`
2. `docs/backend/m7-10-polar-expanded-factual-device-acceptance-canary-gate.md`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`

### Результат

`M7.10` выполнен как factual rerun и оформлен в артефактах; canary telemetry подтверждена на `M7.9` bundle с `polar_rr`, но claim-gate остается `blocked` до предъявления physical-device evidence.

### Следующий шаг

`M7.10.1 - Physical-device evidence capture and factual rerun for M7.10 gate`

---

## 2026-03-30 - M7.10.1 - Physical-device evidence capture and factual rerun for M7.10 gate

### Запрос

Пользователь подтвердил `M7.10.1`: выполнить rerun для `M7.10` с physical-device evidence и зафиксировать результат gate.

### Что сделано

1. Проверен workspace на наличие готового physical-device evidence артефакта (`on-go`, `on-go-ios`, `data/*`) — подходящий файл не найден.
2. Выполнен factual rerun `M7.10.1`:
   - команда: `python3 scripts/ml/m7_8_acceptance_claim_gate.py --include-polar-rr --experiment-prefix m7-10-1-physical-device-evidence-rerun --output-dir data/external/wesad/artifacts/wesad/wesad-v1/m7-10-1-physical-device-evidence-rerun --context internal_dashboard`;
   - `experiment_id`: `m7-10-1-physical-device-evidence-rerun-20260330T161622Z`.
3. Подтверждены фактические результаты по артефактам:
   - `streams_sent=[watch_accelerometer, polar_hr, polar_rr]`;
   - `inference_count=5`, `error_count=0`, `heart_source=polar_hr`;
   - canary evidence присутствует: `activity_canary_present=true`, `arousal_canary_present=true`.
4. Gate-решение зафиксировано как `blocked`, так как `--real-device-evidence` не был передан и отчет содержит `real_device_evidence_present=false`, `device_protocol_validated=false`.
5. Добавлен backend-отчет шага `M7.10.1` и обновлены status docs (`execution-status`, `work-log`) с переводом следующего шага на `M7.10.2`.

### Измененные файлы

1. `docs/backend/m7-10-1-physical-device-evidence-rerun.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`

### Результат

`M7.10.1` выполнен как factual rerun, но остается `blocked`: до предоставления конкретного физического evidence-файла gate не может перейти в `pass`.

### Следующий рекомендуемый шаг

`M7.10.2 - Provide concrete physical-device evidence path and rerun gate with --real-device-evidence`

---

## 2026-03-30 - M7.10.2 - Provide concrete physical-device evidence path and rerun gate with --real-device-evidence

### Запрос

Пользователь подтвердил `M7.10.2`: предоставить конкретный physical-device evidence path и выполнить rerun gate с `--real-device-evidence`.

### Что сделано

1. Выполнена обязательная сверка `roadmap/status/work-log` и `model-reporting-standard` перед стартом шага.
2. Проверен acceptance runner `scripts/ml/m7_8_acceptance_claim_gate.py`:
   - подтверждено, что флаг `--real-device-evidence` проверяет существование файла (`Path.exists()`), а не его содержимое.
3. Выполнен фактический поиск physical-device evidence артефактов:
   - в `on-go`, `on-go-ios`, `Desktop`, `Downloads`;
   - дополнительно по типовым путям экспорта `on-go-sessions/session_*`.
4. Найдены только simulator-артефакты:
   - `/Users/kgz/Library/Developer/CoreSimulator/.../Documents/on-go-sessions/session_*`.
5. Проверяемый артефакт реальной paired-сессии (`iPhone + Apple Watch + Polar H10`) не найден.
6. Rerun с `--real-device-evidence` не запускался намеренно, чтобы избежать нефактического `pass` из-за передачи нерелевантного файла.
7. Обновлен статус выполнения:
   - `M7.10.2` переведен в `blocked`;
   - следующий шаг выставлен как `M7.10.3`.

### Измененные файлы

1. `docs/status/execution-status.md`
2. `docs/status/work-log.md`

### Результат

`M7.10.2` заблокирован: в текущей файловой системе не найден проверяемый physical-device evidence path для фактического rerun с `--real-device-evidence`.

### Следующий рекомендуемый шаг

`M7.10.3 - Rerun gate after user-provided physical-device evidence path`

---

## 2026-03-30 - M7.10.3 - Switch runtime services to M7.9 bundle for real-data check

### Запрос

Пользователь попросил переключить текущий runtime на `M7.9` bundle, чтобы проверить работу на реальных данных (`rest -> movement -> recovery`).

### Что сделано

1. Выполнена обязательная сверка `roadmap/status/work-log` и `model-reporting-standard`.
2. Обновлен compose override:
   - `inference-api` и `live-inference-api` volume-пути переключены на `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-9-runtime-bundle-export:/models:ro`.
3. Выполнен перезапуск сервисов с пересборкой:
   - `docker compose -f infra/compose/on-go-stack.yml -f infra/compose/docker-compose.override.yml up -d --build inference-api live-inference-api`.
4. Проверена фактическая готовность сервисов:
   - `GET http://localhost:8100/health` -> `model_loaded=true`;
   - `GET http://localhost:8120/health` -> `model_loaded=true`.
5. Проверено содержимое `/models` внутри контейнера `inference-api`:
   - присутствуют `model-bundle.manifest.json`, `activity_*`, `arousal_coarse_*`, `valence_coarse_*` файлы из `m7-9-runtime-bundle-export`.
6. Обновлены статус и следующий шаг в соответствии с фактическим результатом.

### Измененные файлы

1. `infra/compose/docker-compose.override.yml`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`

### Результат

Runtime успешно переключен на `M7.9` bundle; `inference-api` и `live-inference-api` подняты и загружают модельный bundle (`model_loaded=true` на `8100/8120`).

### Следующий рекомендуемый шаг

`M7.10.4 - Real-device acceptance rerun on M7.9 runtime bundle with evidence path`

---

## 2026-03-31 - OPS-20260331-B - Логи исходящих предсказаний и журнал по протоколу

### Запрос

1. Добавить в логи видимость данных предсказания, которые сервер отправляет клиенту (что приходит «с бекенда» в смысле исходящего ответа).
2. Работать по `docs/process/collaboration-protocol.md` и зафиксировать в журнале всё сделанное в этой сессии.

### Что сделано

1. Прочитаны обязательные для режима документы: `docs/process/collaboration-protocol.md`, `docs/status/execution-status.md`, `docs/status/work-log.md` (сверка статуса перед записью).
2. В `live-inference-api` для каждого отправляемого сообщения `type: inference` добавлено логирование:
   - `prediction` — JSON со срезом семантических полей и счётчиков фич;
   - `prediction_new_or_changed` — только поля, отличающиеся от предыдущего окна (на первом окне — полный срез как «новый»).
3. В `inference-api` после формирования `PredictResponse` добавлена строка лога `predict outbound` с `model_dump(mode="json")`.
4. Запущены unit-тесты: `live-inference-api` — `20 passed`, `inference-api` — `6 passed`.
5. Обновлены `docs/status/execution-status.md` (пункт в списке «Уже сделано») и данная запись в `docs/status/work-log.md`.

### Измененные файлы

1. `services/live-inference-api/src/live_inference_api/api.py`
2. `services/inference-api/src/inference_api/api.py`
3. `docs/status/execution-status.md`
4. `docs/status/work-log.md`

### Результат

В логах сервисов видно полный срез исходящего предсказания и дельту по окнам для WebSocket; для REST — полный JSON ответа predict. Сессия задокументирована в статусе и журнале по протоколу.

### Следующий рекомендуемый шаг

`M7.10.4 - Real-device acceptance rerun on M7.9 runtime bundle with evidence path` (без изменения приоритета roadmap; шаг `OPS-20260331-B` — вспомогательный инкремент наблюдаемости).

---

## 2026-03-31 - OPS-20260331 - Replay infer: MinIO vs Postgres, маршрут `/api`, rebuild

### Запрос

1. Разобраться, почему страница воспроизведения/инференса по `session_id` `93728209-0e9f-41df-845a-2cabfe410719` сообщает «не найдено», хотя данные в MinIO есть.
2. Разобрать `HTTP 404` на `POST http://localhost:8121/api/v1/replay/infer`.
3. Пересобрать образ `live-inference-api` самостоятельно.
4. Работать по `docs/process/collaboration-protocol.md` и зафиксировать итог в журнале и статусе.

### Что сделано

1. Сверка с кодом: `replay-service` и `POST /v1/replay/infer` (через `live-inference-api`) читают метаданные сессии из PostgreSQL (`ingest.raw_sessions`); MinIO используется для объектов по ключам из метаданных, но не как источник «существования» сессии без строки в БД.
2. Обновлена текстовая подсказка в UI `replay-infer-ui`: явно указано, что нужна запись в ingest catalog (Postgres), а не только префикс в object storage.
3. В `live-inference-api` вынесен общий обработчик и добавлен маршрут `POST /api/v1/replay/infer` (дубль `POST /v1/replay/infer`) для прямых вызовов с префиксом `/api` и согласованности с `replay-infer-ui` (nginx на `8121` проксирует `/api/` на `live-inference-api`).
4. В `tests/test_replay_infer.py` добавлены проверки, что оба пути дают одинаковые ответы (`503` без bundle, `200` при моке).
5. Выполнена пересборка Docker из каталога `infra/compose`: `docker compose -f on-go-stack.yml build live-inference-api --no-cache` и `docker compose -f on-go-stack.yml up -d live-inference-api` (контейнер `on-go-live-inference-api` пересоздан).
6. Обновлены `docs/status/execution-status.md` и добавлена эта запись в `docs/status/work-log.md` по формату протокола.

### Измененные файлы

1. `services/replay-infer-ui/public/index.html`
2. `services/live-inference-api/src/live_inference_api/api.py`
3. `services/live-inference-api/tests/test_replay_infer.py`
4. `docs/status/execution-status.md`
5. `docs/status/work-log.md`

### Результат

Поведение replay/infer задокументировано в коде и UI; маршрутизация `POST /api/v1/replay/infer` поддерживается на уровне приложения; образ `live-inference-api` пересобран и контейнер перезапущен; шаг `OPS-20260331` отмечен как `completed` в реестре и в списке «Уже сделано».

### Следующий рекомендуемый шаг

`M7.10.4 - Real-device acceptance rerun on M7.9 runtime bundle with evidence path` (без изменения по roadmap; при необходимости подтвердить или скорректировать по `docs/process/collaboration-protocol.md`).

---

## 2026-03-31 - OPS-CONSOLIDATED-20260331 - Сводка: live-inference, replay batch, UI, MinIO audit (сессия с агентом)

### Запрос

Работать по `docs/process/collaboration-protocol.md` и записать в журнал всё, что было сделано в совместной сессии (исправления live inference, replay→inference, compose, UI на 8121, аудит MinIO, разъяснения по MinIO Console и Postgres vs object storage).

### Что сделано

1. **Manifest / признаки (live-inference-api):** для `manifest_layout=True` в `extract_watch_features` признаки пульса дублируются в `watch_bvp_c0__*`, чтобы вектор совпадал с `feature_names.json` бандла (раньше в manifest-ветке заполнялся только `chest_ecg_c0`, из‑за чего HR-часть для модели могла быть нулевой).
2. **RR и контекст часов:** при одном RR-интервале в окне заполняется полный блок `chest_rr_*` + quality; из `watch_activity_context` в окне считаются числовые агрегаты `watch_activity_context_<поле>__*`.
3. **StreamBuffer:** `try_emit_window` возвращает сэмплы `watch_activity_context` за окно; WebSocket передаёт их в `extract_watch_features`.
4. **Batch replay→inference:** модуль `replay_infer.py`, `POST /v1/replay/infer` и дубль `POST /api/v1/replay/infer` (общий handler), вызов `replay-service` (manifest + окна со скользящим шагом), маппинг окон в те же фичи и семантику, что и `/ws/live`; `httpx` в зависимостях; `REPLAY_SERVICE_BASE_URL` в `Settings` и в compose для `live-inference-api`.
5. **Compose:** `inference-api` и `live-inference-api` монтируют `m7-9-runtime-bundle-export` bind-mount из репозитория; удалён пустой named volume `inference-models`; удалён дублирующий `infra/compose/docker-compose.override.yml` с абсолютным путём; добавлен сервис `replay-infer-ui` (nginx, порт 8121) с прокси `/api/` → `live-inference-api`.
6. **Контракт:** в `contracts/http/live-inference-api.openapi.yaml` добавлены `POST /v1/replay/infer` и server `http://localhost:8120`.
7. **Скрипт аудита MinIO:** `scripts/minio_audit_sessions.py` — список сессий под `raw-sessions/`, проверка обязательных стримов (по умолчанию `watch_accelerometer,polar_hr,polar_rr`), опции `--complete-only`, `--require-checksums`, `--delete-incomplete --i-am-sure`.
8. **Пояснения пользователю:** объекты в MinIO появляются только после успешной загрузки; консоль MinIO: избегать `%2F` в URL, заходить кликами по `bucket → raw-sessions → <uuid>`; replay/infer требует строку в **Postgres** (`ingest.raw_sessions`), а не только префикс в бакете.

### Измененные или созданные файлы

1. `services/live-inference-api/src/live_inference_api/features.py`
2. `services/live-inference-api/src/live_inference_api/buffer.py`
3. `services/live-inference-api/src/live_inference_api/api.py`
4. `services/live-inference-api/src/live_inference_api/config.py`
5. `services/live-inference-api/src/live_inference_api/replay_infer.py`
6. `services/live-inference-api/pyproject.toml`
7. `services/live-inference-api/tests/test_buffer.py`
8. `services/live-inference-api/tests/test_features.py`
9. `services/live-inference-api/tests/test_api.py`
10. `services/live-inference-api/tests/test_replay_infer.py`
11. `infra/compose/on-go-stack.yml`
12. `contracts/http/live-inference-api.openapi.yaml`
13. `scripts/minio_audit_sessions.py`
14. `services/replay-infer-ui/nginx.conf`
15. `services/replay-infer-ui/public/index.html`
16. Удалён: `infra/compose/docker-compose.override.yml` (актуально на момент записи; при необходимости восстановить из git)

### Результат

Зафиксирована полная цепочка: корректные признаки для manifest-бандла, офлайн-окна из replay, HTTP API и UI для прогона без устройства, инструмент проверки полноты сессий в MinIO, инфраструктура compose без абсолютных путей в override. Поведение «not found» в UI replay разделено на: (а) отсутствие сессии в Postgres, (б) особенности URL MinIO Console.

### Следующий рекомендуемый шаг

По `docs/status/execution-status.md`: **`M7.10.4 - Real-device acceptance rerun on M7.9 runtime bundle with evidence path`**. Перед выполнением — сверка статуса и подтверждение шага по `docs/process/collaboration-protocol.md`.

---

## 2026-03-31 - K5.9 - Live inference: watch_activity_context, valence public_app, журнал сессии

### Запрос

1. Разобрать неверное состояние (`seated_rest`, `low`, `calm_rest`) при росте HR и активности по акселерометру на примерах CSV (`samples-4.csv`, `samples-5.csv`).
2. Спланировать и реализовать учёт `watch_activity_context.activity_type` в live inference (пост-модельная коррекция без обязательного переобучения; опционально признаки для следующего бандла).
3. Уточнить про Docker-сборку после изменений.
4. Объяснить низкий arousal, отсутствие valence и ограничения различения когнитивной нагрузки и тревоги по одним часам.
5. Включить valence для публичного приложения.
6. Объяснить, как в проекте корректно определять эмоции (ground truth vs модель).
7. Работать по `docs/process/collaboration-protocol.md` и записать в журнал всё сделанное в этой сессии.

### Что сделано

1. Сверены `docs/status/execution-status.md`, `docs/status/work-log.md` и релевантные части roadmap; шаг оформлен как инкремент `K5.9` (Production / live inference), без смены следующего roadmap-шага `M7.10.4`.
2. Диагностика: строковый `activity_type` из `watch_activity_context` не попадал в числовые признаки; бандл activity использует ACC+BVP без контекста часов; семантика `calm_rest` следует из пары rest-класс + low arousal.
3. Реализован модуль `activity_context_adjust`: разбор `activity_type` / `activityType`, агрегация по окну, замена rest-меток модели на `walking` или `light_exercise` при устойчивом motion-сигнале; пороги `MIN_LABELED_SAMPLES`, `MOTION_FRACTION_THRESHOLD`.
4. Подключено после `predict`, до `derive_semantic_state`, в WebSocket (`api.py`) и `replay_infer.py`; в ответе клиенту отдаётся скорректированная `activity`.
5. В `extract_watch_features` добавлены статистики `watch_activity_context_motion_level__*` по уровням 0/1/2 для будущего включения в `feature_names.json` при переобучении.
6. Тесты: `services/live-inference-api/tests/test_activity_context_adjust.py`, обновлены `test_semantics.py`; прогон `python3 -m pytest tests/` в `live-inference-api`: `38 passed`.
7. Valence: в `live_inference_api/semantics.py` в `_ALLOWED_CONTEXTS` добавлен `public_app`, для него при загруженной модели valence выставляется `user_facing_claims=true`; `inference-api` и политика canary для batch `POST /v1/predict` не менялись.
8. Пользователю выполнена пересборка Docker: `docker compose -f infra/compose/on-go-stack.yml build live-inference-api --no-cache` и `up -d live-inference-api` (образ без изменений Dockerfile — копируется `src`).
9. Зафиксировано в ответах: эталон аффекта в исследованиях — `participant_self_report` по `docs/research/label-specification.md`; модель даёт прокси по сенсорам; «базовые эмоции» в продукте — отдельный UX-слой поверх coarse arousal × valence.
10. Обновлены `docs/status/execution-status.md` (п. 129 «Уже сделано», строка реестра `K5.9`) и эта запись в `docs/status/work-log.md`.

### Измененные или созданные файлы

1. `services/live-inference-api/src/live_inference_api/activity_context_adjust.py` (новый)
2. `services/live-inference-api/src/live_inference_api/api.py`
3. `services/live-inference-api/src/live_inference_api/replay_infer.py`
4. `services/live-inference-api/src/live_inference_api/features.py`
5. `services/live-inference-api/src/live_inference_api/semantics.py`
6. `services/live-inference-api/tests/test_activity_context_adjust.py` (новый)
7. `services/live-inference-api/tests/test_semantics.py`
8. `docs/status/execution-status.md`
9. `docs/status/work-log.md`

### Результат

Live inference учитывает категориальный контекст часов при конфликте с rest-предсказанием ML; valence в WebSocket доступен для `public_app` при наличии valence-трека в бандле; ограничения и роль self-report задокументированы в журнале; тесты зелёные.

### Следующий рекомендуемый шаг

`M7.10.4 - Real-device acceptance rerun on M7.9 runtime bundle with evidence path` (подтвердить по протоколу). Опционально: согласовать с продуктом обновление `K5.5` exposure policy, если user-facing valence в `public_app` требует пересмотра формулировок относительно истории `E2.x` exploratory-only.

---

## 2026-03-31 - M7.9.1 - Live inference hardening, fusion arousal export, WESAD retrain, журнал совместной сессии

### Запрос

1. Разобрать проблемы live inference: предсказания `activity` / `valence` / `arousal` один раз определились и не менялись; при спокойном сидении — неверная пара (`arousal` high, `activity` rest).
2. Уточнить, одна ли модель на три выхода и как устроены входы (часы — акселерометр, Polar — кардио).
3. Цель: единый fusion и для `arousal` (Polar + watch motion).
4. Переобучить модели и подготовить bundle для backend.
5. Возможность гонять обучение без человека с данными из MinIO.
6. Работать по `docs/process/collaboration-protocol.md` и записать в статус и журнал всё сделанное в этой совместной сессии.

### Что сделано

1. Сверка с протоколом: прочитаны `docs/status/execution-status.md`, `docs/status/work-log.md`; roadmap по modeling для контекста не менялся, следующий рекомендуемый шаг остаётся `M7.10.4`.
2. Диагностика залипания: окна выдаются только при «свежем» HR относительно конца окна; слишком короткий `max_heart_staleness_ms` (30 с) при плотном акселерометре и редком Polar HR приводил к отсутствию новых `inference` после первого окна.
3. Диагностика неверных классов: при `manifest_layout` и fallback `watch_heart_rate` HR не попадал в `chest_ecg_c0__*`, fusion-треки получали нули по кардио; для `M7.9` до переопределения экспорта `arousal` мог быть отдельной моделью `watch_motion_only` (только ACC), в отличие от `activity`/`valence` (`polar_expanded_fusion`).
4. Код `live-inference-api`: в `Settings` добавлен `heart_staleness_ms` и env `LIVE_INFERENCE_HEART_STALENESS_MS`, default `max(120000, window_ms*6)`; `StreamBuffer` получает значение из конфига; в `extract_watch_features` для manifest + `watch_heart_rate` добавлено заполнение `chest_ecg_c0__*`; тесты `test_buffer.py`, `test_features.py`.
5. Код `modeling-baselines`: в `run_m7_9_runtime_bundle_export` добавлен `track_variant_overrides`, CLI `--m79-override-activity-variant`, `--m79-override-arousal-variant`, `--m79-override-valence-variant`; при overrides `bundle_version` v3, поля в отчёте; тесты `test_pipeline.py`.
6. Выполнен полный пересчёт на локальных WESAD артефактах: `m7-9-polar-expanded-fusion-benchmark-20260331T185127Z`, затем `m7-9-runtime-bundle-export-20260331T185147Z` с `--m79-override-arousal-variant polar_expanded_fusion`; итоговый каталог `data/external/wesad/artifacts/wesad/wesad-v1/m7-9-runtime-bundle-export`, manifest `bundle_version` v3, все три дорожки `polar_expanded_fusion`, по 53 признака; smoke `passed`; проверка `load_model_bundle` для `arousal_coarse` = `polar_expanded_fusion`.
7. MinIO: зафиксировано, что `modeling-baselines` читает только локальные пути; MinIO в стеке используется ingest/replay/processing, не обучение; для безлюдного прогона нужен sync из бакета в рабочий каталог или отдельная доработка пайплайна.
8. Обновлены `docs/status/execution-status.md` (п. 130 «Уже сделано», строка реестра `M7.9.1`) и данная запись в `docs/status/work-log.md`.

### Измененные или созданные файлы (код)

1. `services/live-inference-api/src/live_inference_api/config.py`
2. `services/live-inference-api/src/live_inference_api/api.py`
3. `services/live-inference-api/src/live_inference_api/features.py`
4. `services/live-inference-api/tests/test_buffer.py`
5. `services/live-inference-api/tests/test_features.py`
6. `services/modeling-baselines/src/modeling_baselines/pipeline.py`
7. `services/modeling-baselines/src/modeling_baselines/main.py`
8. `services/modeling-baselines/tests/test_pipeline.py`
9. `docs/status/execution-status.md`
10. `docs/status/work-log.md`

### Артефакты данных (не в git, путь на машине разработки)

1. `data/external/wesad/artifacts/wesad/wesad-v1/m7-9-polar-expanded-fusion-benchmark/` (отчёт бенчмарка от `20260331T185127Z`).
2. `data/external/wesad/artifacts/wesad/wesad-v1/m7-9-runtime-bundle-export/` (runtime bundle v3, fusion arousal).

### Результат

Live inference устойчивее к редкому HR; fusion-признаки не обнуляются при watch HR fallback; `arousal` в runtime bundle согласован с fusion-стеком activity/valence; WESAD переобучен и экспортирован; ограничения MinIO для ML задокументированы; сессия отражена в статусе и журнале по протоколу.

### Следующий рекомендуемый шаг

`M7.10.4 - Real-device acceptance rerun on M7.9 runtime bundle with evidence path` (подтвердить по протоколу: paired-прогон на устройстве, затем `m7_8_acceptance_claim_gate.py` с `--include-polar-rr` и фактическим `--real-device-evidence <path>`). После смены bundle перезапустить `inference-api` / `live-inference-api` с volume на `m7-9-runtime-bundle-export` v3 при необходимости.

---

## 2026-04-01 - UI-LIVE-1 / UI-LIVE-2 - Тёмный live-дашборд on-go-ios (ЭКГ, пульс, inference)

### Запрос

Выполнить план: тёмный современный UI на iPhone с реалтайм ЭКГ (пики/волна), пульсом/BPM, activity/arousal/valence и производными полями inference, кнопками Prepare/Start/Stop и явным статусом успех/ошибка; без изменений backend live-inference-api; работа по протоколу совместной работы.

### Что сделано

1. `CaptureKit` / `PhoneCapture`: уведомления `Notification.Name.onGoCaptureECGSampleChunk` и `onGoCaptureHRBpm` при потоковой выдаче Polar SDK (микровольты ЭКГ и BPM) для мгновенной отрисовки на телефоне.
2. `BackendClient` / `LiveInferenceClient`: структура `LiveInferenceLabels`, колбэк `onLabels`, поля `derivedState` и `userDisplayLabel` из JSON inference.
3. `SessionViewModel`: кольцевой буфер `ecgMicrovoltSamples`, `heartRateBpm`, `SessionResultBanner` (успех/неуспех после stop/upload и при ошибках start/stop/watchdog), методы `appendECGMicrovolts` / `updateHeartRateBpm`, сброс виталов при prepare/stop.
4. `LivePhysioStripViews.swift`: `ECGMicrovoltStripView` (Canvas), `PulseOrbView` (TimelineView + анимация удара).
5. `SessionDashboardView.swift`: тёмная тема, градиентный фон, блоки виталов и inference, collapsible runtime gate, обновлённая панель управления сессией.
6. Сборка `swift build` в пакете `CaptureKit` прошла успешно.

### Измененные или созданные файлы

Репозиторий `on-go-ios`:

1. `packages/CaptureKit/Sources/PhoneCapture/PhoneCaptureCoordinator.swift`
2. `packages/CaptureKit/Sources/PhoneCapture/PolarH10Adapter.swift`
3. `packages/CaptureKit/Sources/BackendClient/LiveInferenceClient.swift`
4. `apps/OnGoCapture/iPhoneApp/Features/SessionViewModel.swift`
5. `apps/OnGoCapture/iPhoneApp/Features/LivePhysioStripViews.swift` (новый)
6. `apps/OnGoCapture/iPhoneApp/Features/SessionDashboardView.swift`

### Результат

Оператор видит на iPhone тёмный дашборд с живой полосой ЭКГ из Polar, пульсом по BPM, семантикой live inference и баннерами результата сессии; данные ЭКГ не отправляются на сервер по WebSocket (как в согласованном плане).

### Следующий рекомендуемый шаг

Физическая проверка на iPhone + Watch + Polar: `M7.10.4` или отдельный smoke UI-LIVE на устройстве; при необходимости `xcodegen` и сборка таргета `OnGoCapture`.

---

## 2026-04-02 - OPS-DIAG-20260402 - Диагностика логов production: ingest vs inference vs live

### Запрос

1. Сообщение о симптоме: «backend похоже не делает предсказания», «к нему не приходят запросы»; приложены фрагменты `docker logs` для `on-go-live-inference-api`, `on-go-inference-api`, `on-go-ingest-api` с VM `msk-1-vm-ek8b`.
2. Отдельный запрос: работать по `docs/process/collaboration-protocol.md` и записать в журнал всё сделанное в этой переписке.

### Что сделано

1. Прочитаны `docs/process/collaboration-protocol.md`, `docs/status/execution-status.md`, `docs/status/work-log.md` перед фиксацией записи по протоколу.
2. По коду репозитория восстановлена цепочка сервисов: `ingest-api` обслуживает lifecycle raw session и не обращается к `inference-api` / `live-inference-api`; `inference-api` (порт `8100`) — HTTP `POST /v1/predict`; `live-inference-api` (порт `8120`) — WebSocket `/ws/live`, сообщения `stream_batch`, условие `source_mode=live`, инференс после `StreamBuffer.try_emit_window` при загруженном `model_bundle`.
3. Сопоставление с логами: `POST /v1/raw-sessions` `201` на ingest подтверждает только приём пакета, не ML; отсутствие строк после старта у `inference-api` согласуется с отсутствием вызовов predict; у `live-inference-api` видны только accept/open/close WebSocket без ожидаемых при валидных батчах строк `stream_batch received` / `inference outbound` — вывод: либо нет полезной нагрузки по WS, либо нужно проверить `GET /health` (`model_loaded`), URL клиента (`wss://…/ws/live` через Caddy, см. протокол), либо сессия обрывается до батчей.
4. Зафиксирован альтернативный контур проверки ML по сохранённым сессиям: `replay-infer-ui` → `POST /api/v1/replay/infer` (прокси на `live-inference-api`).
5. Обновлены `docs/status/work-log.md` (данная запись) и `docs/status/execution-status.md` (п. `133` в «Уже сделано», строка «Параллельно зафиксировано»).

### Измененные или созданные файлы

1. `docs/status/work-log.md`
2. `docs/status/execution-status.md`

Код приложений в `on-go` в рамках диагностического обсуждения не менялся.

### Результат

Пользователю дано структурированное объяснение, почему логи выглядят «без предсказаний», и чеклист проверок на сервере и клиенте; состояние проекта отражено в статусе и журнале по протоколу совместной работы.

### Следующий рекомендуемый шаг

Подтвердить по протоколу и выполнить `M7.10.4` (real-device acceptance с evidence path) либо точечный smoke: `curl`/браузер `GET https://<хост>/health` на контур live (через прокси) и `8100` при необходимости, убедиться что iOS шлёт `stream_batch` после открытия WebSocket; при сохранении симптома — прислать свежие логи `live-inference-api` с момента старта сессии на устройстве.

---

## 2026-04-02 - OPS-MOBILE-ENV-20260402 - Прод `.env` сервера и переменные мобильного клиента

### Запрос

1. По приведённому фрагменту серверного `.env` (`ON_GO_MODEL_BUNDLE_SOURCE`, `COMPOSE_PROJECT_NAME`, `ON_GO_MODEL_VOLUME`, TLS/Caddy, `INGEST_S3_PRESIGN_ENDPOINT_URL=https://s3.kegazani.ru`, `SITE_ADDRESS=api.kegazani.ru`, `SITE_DOMAIN=kegazani.ru`, `CADDY_ACME_EMAIL`, порты Caddy) уточнить, какие настройки должны быть у мобильного приложения.
2. Работать по `docs/process/collaboration-protocol.md` и зафиксировать в журнале всё сделанное в этой переписке.

### Что сделано

1. Сверка с `docs/deployment/server-deploy.md`, `docs/process/collaboration-protocol.md`, `docs/setup/local-docker-setup.md`, `services/ingest-api/src/ingest_api/config.py` и связанными runbook-записями.
2. Зафиксировано для продакшена с TLS и `SITE_ADDRESS=api.kegazani.ru`: в Xcode (Environment Variables) **`ON_GO_INGEST_BASE_URL`** = `https://api.kegazani.ru` (без path); **`ON_GO_LIVE_INFERENCE_WS_URL`** = `wss://api.kegazani.ru/ws/live`; опционально **`ON_GO_INGEST_AUTH_TOKEN`**, **`ON_GO_LIVE_INFERENCE_CONTEXT`**, **`ON_GO_POLAR_*`** по необходимости.
3. Разграничены серверные переменные (compose, модель, Caddy, ACME) и клиент: **`INGEST_S3_PRESIGN_ENDPOINT_URL`** задаётся только на **ingest-api**, чтобы presigned URL указывали на **`https://s3.kegazani.ru`**; iPhone не получает эту переменную отдельно, а следует URL из ответа presign.
4. Обновлены `docs/status/work-log.md` (данная запись) и `docs/status/execution-status.md` (строка «Параллельно зафиксировано в журнале»).

### Измененные или созданные файлы

1. `docs/status/work-log.md`
2. `docs/status/execution-status.md`

### Результат

Единое явное соответствие между прод-конфигом `kegazani.ru` и ожидаемыми URL в `on-go-ios`; сессия отражена в статусе и журнале согласно протоколу совместной работы.

### Следующий рекомендуемый шаг

`M7.10.4 - Real-device acceptance rerun on M7.9 runtime bundle with evidence path` (подтвердить по протоколу) либо smoke с реальным устройством против `https://api.kegazani.ru` и проверкой загрузки по presigned URL на `https://s3.kegazani.ru`.

---

## 2026-04-02 - DEBUG-INGEST-ATS-20260402 - Диагностика загрузки сессии (ATS, presign MinIO, откат правок)

### Запрос

1. Сообщение об ошибке при экспорте/загрузке сессии: App Transport Security / требование secure connection.
2. Уточнение, что клиентское приложение лежит в `/Users/kgz/Desktop/p/on-go-ios`, а не только в monorepo `on-go`.
3. Логи с реального устройства: успешный `POST https://api.kegazani.ru/v1/raw-sessions` (201), затем падение на PUT по presigned URL вида `http://api.kegazani.ru:9000/...` с `NSURLErrorDomain -1022` (ATS).
4. Повторный лог с той же ошибкой после ожидания правок на сервере.
5. Команда «отмени все изменения» — вернуть репозитории к состоянию без внесённых правок.
6. Команда работать по `docs/process/collaboration-protocol.md` и записать в журнал всё сделанное в переписке.

### Что сделано

1. Разобрана цепочка: локальный пакет собирается на iPhone; `HTTPIngestClient` делает create → PUT по `upload_url` из ответа → complete/finalize; ATS блокирует **cleartext HTTP** к публичному хосту, если URL не подпадает под исключения Info.plist.
2. В `on-go-ios` просмотрены `BackendEnv`, схема Xcode в `project.yml` (дефолт `ON_GO_INGEST_BASE_URL=http://127.0.0.1:8080` — на физическом устройстве это loopback телефона), `HTTPIngestClient`, `Info.plist` (исключение ATS только для `localhost`, не для `127.0.0.1`).
3. По логам зафиксирована корневая причина на проде: **ingest-api** формировал presigned URL с хостом из `Host` и схемой **`http://…:9000`**, тогда как клиент ходит на API по **HTTPS**, а публичный MinIO по проекту должен быть за Caddy как **`https://s3.<SITE_DOMAIN>`** (`infra/compose/Caddyfile.acme`), а не `http://api…:9000`.
4. Предлагались и частично внедрялись правки в `on-go`: приоритет **`INGEST_S3_PRESIGN_ENDPOINT_URL`** над выводом из `Host`; разбор `Host` через `urlsplit`; параметр `presign_endpoint` в `create_raw_session`; fallback **`https://s3.<SITE_DOMAIN>`** при заданном `SITE_DOMAIN` в `Settings`; проброс **`SITE_DOMAIN`** в сервис `ingest-api` в compose; строка **`SITE_DOMAIN`** в `services/ingest-api/.env.example`.
5. В `on-go-ios` временно добавлялись: исключение ATS для **`127.0.0.1`**, ключ **`NSLocalNetworkUsageDescription`** (для LAN и iOS 14+), синхронно в `Info.plist` и `project.yml`.
6. По запросу пользователя выполнен **откат**: в `on-go` — `git restore` к отслеживаемому состоянию (`origin/main`); в `on-go-ios` — ручной откат правок ATS / Local Network в `Info.plist` и `project.yml`.

### Измененные или затронутые файлы (в ходе сессии; итоговое состояние после отката)

**Репозиторий `on-go`:** перечисленные ниже файлы менялись в сессии, затем откатаны к состоянию git; в текущем дереве правок сессии **нет**.

1. `services/ingest-api/src/ingest_api/api.py`
2. `services/ingest-api/src/ingest_api/config.py`
3. `services/ingest-api/src/ingest_api/service.py`
4. `infra/compose/on-go-stack.yml`
5. `infra/compose/raw-ingest-stack.yml`
6. `services/ingest-api/.env.example`

**Репозиторий `on-go-ios` (вне monorepo):**

7. `apps/OnGoCapture/iPhoneApp/Info.plist` — правки откатаны.
8. `apps/OnGoCapture/project.yml` — правки откатаны.

**Документация monorepo (эта запись):**

9. `docs/status/work-log.md`
10. `docs/status/execution-status.md`

### Результат

1. Причина ошибки на устройстве с `https://api.kegazani.ru` и логами **подтверждена**: presigned PUT указывал на **`http://api.kegazani.ru:9000`**, что iOS ATS отклоняет для публичного имени.
2. Операционный вывод для продакшена (без обязательного merge откатанного кода): на сервере нужно, чтобы presign совпадал с публичным HTTPS S3-фронтом — **`INGEST_S3_PRESIGN_ENDPOINT_URL=https://s3.kegazani.ru`** (или эквивалент) и согласованный с Caddy DNS/TLS; либо правка логики ingest (как в п.4 выше), чтобы не подставлять `http://<Host>:9000` поверх явного presign-URL.
3. Для локальной отладки с iPhone по Wi‑Fi: в схеме Xcode задавать **`http://<IP_Mac>:8080`**, на хосте — **`INGEST_S3_PRESIGN_ENDPOINT_URL=http://<IP_Mac>:9000`**; учитывать ATS и при необходимости локальную сеть (разрешения iOS).
4. Кодовая база `on-go` после отката соответствует последнему закоммиченному состоянию; описанные исправления остаются как **рекомендуемый патч** при повторном внедрении.

### Следующий рекомендуемый шаг

Подтвердить по протоколу: либо **повторно внедрить** патч presign + `SITE_DOMAIN` в `ingest-api`/compose и задеплоить с заполненным **`INGEST_S3_PRESIGN_ENDPOINT_URL`**, либо ограничиться **только** настройкой `.env` на сервере, если текущий код на сервере уже отдаёт `https://s3.…` при корректной переменной; затем smoke: загрузка сессии с iPhone и проверка ingest/MinIO. Параллельно при необходимости вернуть точечные правки `on-go-ios` (127.0.0.1 / Local Network) отдельным подтверждённым шагом.

---

## 2026-04-02 - OPS-LIVE-OBS-DOC-20260402 - Наблюдаемость live-inference при сбоях записи/доставки + журнал по протоколу

### Запрос

1. Сделать так, чтобы при неудачной записи или доставке данных были ошибка в логах и понятный сигнал пользователю (клиенту WebSocket).
2. Работать по `docs/process/collaboration-protocol.md` и зафиксировать в журнале всё сделанное в этой переписке.

### Что сделано

1. Сверка со статусом: прочитаны `docs/status/execution-status.md`, `docs/status/work-log.md`, начало `docs/roadmap/research-pipeline-backend-plan.md`, полностью `docs/process/collaboration-protocol.md`.
2. Разбор `services/live-inference-api`: обработчик `WS /ws/live` в `api.py` уже шлёт структурированные `type=error` для невалидного JSON, неизвестного стрима, `source_mode!=live`, политики Polar primary и переключения heart source; исходящий inference логируется (`logger.info` с `prediction` и дельтой); глобальные исключения логируются через `logger.exception` и по возможности уходят клиенту как `internal_error`.
3. Зафиксированы пробелы для следующего инкремента кода (в этой переписке **не реализованы**): невалидные элементы `samples` в `stream_batch` сейчас тихо пропускаются в цикле без счётчика и без `error`-сообщения; сбой `websocket.send_json` для `inference` не обёрнут отдельно (при обрыве соединения клиент может не получить явный код, хотя сервер залогирует только при падении всего цикла).
4. Добавлена эта запись в `docs/status/work-log.md` и обновлён `docs/status/execution-status.md` (п. `136` в «Уже сделано» и строка «Параллельно зафиксировано в журнале»).

### Измененные или созданные файлы

1. `docs/status/work-log.md`
2. `docs/status/execution-status.md`

### Результат

Сессия задокументирована по протоколу; граница между уже существующим поведением live WebSocket и желаемым усилением наблюдаемости для «молчаливых» потерь сэмплов / сбоя доставки inference явно зафиксирована для следующего подтверждённого шага.

### Следующий рекомендуемый шаг

Подтвердить по протоколу небольшой шаг **`OPS-LIVE-OBS-20260402-impl`** (или включить в ближайший ops-инкремент): в `live-inference-api` при частично невалидном `samples` — `logger.warning`/`error` с `stream_name` и счётчиком отброшенных строк + опционально одно `type=error` с кодом вроде `invalid_samples_skipped`; обернуть `send_json(inference)` с логированием и при живом сокете — `type=error` с кодом `inference_delivery_failed`. Альтернатива по roadmap: **`M7.10.4`** (device acceptance), если приоритет — железо, а не серверный UX.

---

## 2026-04-02 - PROTOCOL-PRODUCT-202604 - Симуляция состояний, эмоции (arousal/valence/activity), фиксация в протоколе

### Запрос

1. Можно ли симулировать стресс, счёт и другие состояния, чтобы посмотреть, как система ведёт себя в этих режимах.
2. Можно ли сделать так, чтобы модель показывала не только активность, но и эмоции (arousal + valence), и нужна ли при этом activity.
3. Записать выводы в `docs/process/collaboration-protocol.md`.
4. Повторный запрос: работать по протоколу совместной работы и записать в журнал всё сделанное в этой переписке.

### Что сделано

1. **Симуляция и состояния:** согласовано, что основной путь проверки без «живого» человека в моменте — **replay** ingested raw-сессий через `replay-service` (`manifest`, окна, `realtime` / `accelerated`); семантика стресса/счёта/когнитивки в данных — через **протокол записи и лейблы** (`docs/research/research-protocol.md`, `docs/research/label-specification.md`); **live-inference** не принимает `simulated`, для сохранённых сессий — **replay**, не подмена live-потоком; универсального генератора синтетического «стресса» в репозитории нет (отдельная задача: датасеты, `dataset-registry` и т.д.).
2. **Эмоции и activity:** зафиксировано, что контракт `inference-api` уже включает `activity`, `activity_class`, `arousal_coarse`, `valence_coarse`, `derived_state`, `claim_level` и политику valence (`services/inference-api/src/inference_api/models.py`); UX может опираться на arousal/valence и `derived_state`, но **activity остаётся в модели/семантике** для различения нагрузки и аффекта (`services/inference-api/src/inference_api/semantics.py`, `derive_semantic_state`); в ответах агенту не утверждать, что activity можно убрать из логики — максимум упростить показ в UI.
3. В `docs/process/collaboration-protocol.md` добавлен раздел **`## Продукт и исследования: зафиксировано`** с подразделами «Симуляция состояний и replay» и «Activity, arousal, valence и эмоции в моменте» (размещён перед `## Рабочий цикл`).
4. Обновлены `docs/status/execution-status.md`: пункт **136** в списке «Уже сделано» (`PROTOCOL-PRODUCT-202604`); в блоке «Параллельно зафиксировано в журнале» отражена сессия `PROTOCOL-PRODUCT-202604`.
5. Добавлена данная запись в `docs/status/work-log.md` по формату протокола (дата, идентификатор, запрос, работа, файлы, результат, следующий шаг).

### Измененные или созданные файлы

1. `docs/process/collaboration-protocol.md`
2. `docs/status/execution-status.md`
3. `docs/status/work-log.md`

### Результат

Договорённости по replay/simulated/live, по отсутствию встроенной синтетической физиологии и по связке activity + arousal + valence закреплены в протоколе совместной работы; полная хронология сессии доступна в журнале; статус проекта отражает шаг **136** (`PROTOCOL-PRODUCT-202604`).

### Следующий рекомендуемый шаг

Подтвердить по протоколу **`M7.10.4`** (real-device acceptance с evidence path) или точечный smoke replay (`stack_e2e` / replay infer UI) для проверки сценариев с размеченными сегментами; при изменении продуктовых правил — править тот же раздел протокола и кратко дублировать в `work-log`.

---

## 2026-04-02 - OPS-BACKEND-HARDENING-20260402 - Live WS lifecycle, ingest finalize guards, журнал по протоколу

### Запрос

1. Улучшить корректное завершение live-сессии на WebSocket: при сбоях и «залипании» часов/inference — предсказуемое поведение, явные сигналы клиенту, финальный flush окна.
2. Разобрать баги ingest: данные вроде идут, но в БД/хранилище не сходится, finalize даёт неверные статусы, ручные правки в Postgres.
3. Работать по `docs/process/collaboration-protocol.md` и записать в журнал всё сделанное в этих переписках (live + ingest + эта фиксация).

### Что сделано

**live-inference-api**

1. `StreamBuffer`: `try_emit_final_window()` (финальное окно без step-gate, расширенный staleness для HR/RR/activity), `reset()`, `peek_emit_block_reason()`, параметр `final_heart_staleness_ms` и env `LIVE_INFERENCE_FINAL_HEART_STALENESS_MS` в `Settings`.
2. WebSocket `/ws/live`: `end_session` / `session_end` → при необходимости финальный inference с `session_final`, ответ `session_ended` (`had_final_inference`, `model_loaded`); `session_reset` → сброс буфера и состояния, `session_reset_ack`.
3. Диагностика: throttled `stream_health` (`inference_blocked` + `reason` для `step_backoff`, `heart_stale_or_missing`, `no_accelerometer_in_window`); ошибки inference → `inference_failed` без обрыва цикла; логи disconnect/`finally`.
4. Тесты `live-inference-api`: расширены `tests/test_buffer.py`, `tests/test_api.py`; прогон `46 passed`.

**ingest-api**

1. `finalize_session`: до `validating` — **422** `artifacts_not_ready_for_finalize` при `pending`/`failed` артефактах (в `details` счётчики и `ingest_status`); повтор finalize при `ingested` с новым `Idempotency-Key` — **409** `session_already_finalized`.
2. Фейковый `IngestRepository` в тестах выровнен с Postgres: `get_artifact_counts`, `get_missing_required_artifacts`, `assert_session_can_accept_uploads`.
3. Тесты: `test_finalize_rejects_when_artifacts_still_pending`, `test_finalize_rejects_second_call_after_ingested_new_idempotency_key`.

**Протокол**

1. Обновлены `docs/status/work-log.md` (данная запись) и `docs/status/execution-status.md` (п. `135` «Уже сделано» для `OPS-BACKEND-HARDENING-20260402`, строка «Параллельно зафиксировано», п. `137` для `OPS-LIVE-OBS-DOC-20260402`).

### Измененные или созданные файлы

1. `services/live-inference-api/src/live_inference_api/buffer.py`
2. `services/live-inference-api/src/live_inference_api/api.py`
3. `services/live-inference-api/src/live_inference_api/config.py`
4. `services/live-inference-api/tests/test_buffer.py`
5. `services/live-inference-api/tests/test_api.py`
6. `services/ingest-api/src/ingest_api/service.py`
7. `services/ingest-api/tests/test_ingest_lifecycle_fixtures.py`
8. `docs/status/work-log.md`
9. `docs/status/execution-status.md`

### Результат

Live-путь даёт явное завершение сессии и причины блокировки окон; ingest не уходит в `validating` при неготовых артефактах и блокирует повторный finalize после `ingested` без согласованного idempotency; фейк тестов ближе к БД. Для `on-go-ios`: перед закрытием WS — `end_session`, новая запись на том же сокете — `session_reset`; сырой пакет — цепочка create → PUT → complete → finalize.

### Следующий рекомендуемый шаг

Подтвердить по протоколу **`M7.10.4`** (real-device acceptance с evidence path) либо точечно: внедрить в `LiveInferenceClient` вызовы `end_session` / `session_reset`; smoke ingest со сверкой ответов **422**/**409** при досрочном finalize. Опционально подтвердить шаг **`OPS-LIVE-OBS-20260402-impl`** из записи `OPS-LIVE-OBS-DOC-20260402` (молчаливые невалидные `samples`).

---

## 2026-04-02 - OPS-SESSION-20260402 - Сводка сессии: presign iOS, Docker, live window 1s

### Запрос

Работать по `docs/process/collaboration-protocol.md` и зафиксировать в журнале всё, что выполнялось в совместной сессии с агентом: ТЗ presigned upload для iOS, перезапуски compose, диагностика ATS `-1022`, окно live-inference 1000 ms, команды пересборки одного сервиса.

### Что сделано

1. **ingest-api — presigned PUT под iOS (ATS):** убрана подстановка `http://{Host}:9000` из заголовка `Host` при `POST /v1/raw-sessions`; `upload_targets` и `/artifacts/presign` используют один источник — `INGEST_S3_PRESIGN_ENDPOINT_URL`, иначе тот же endpoint, что `INGEST_S3_ENDPOINT_URL`. Добавлены `INGEST_S3_PRESIGN_REQUIRE_HTTPS` и проверка при старте: при включении флага требуется `https://` в presign base URL. Удалён `presign_endpoint_override` из `S3Storage.create_put_target`. В тестах фейковое хранилище отдаёт `https://fake-s3.local/...`.
2. **Документация и compose:** обновлены `docs/deployment/server-deploy.md` (prod: `https://s3...`, `INGEST_S3_PRESIGN_REQUIRE_HTTPS`), `docs/setup/local-docker-setup.md` (ATS, единый presign URL); в `.env.example`, `services/ingest-api/.env.example`, `infra/compose/on-go-stack.yml`, `infra/compose/raw-ingest-stack.yml` добавлены переменные presign/HTTPS.
3. **Операции (ответы в чате, без изменения репо):** команды перезапуска `ingest-api` и полного стека с Caddy (`--profile tls`, два compose-файла); пояснение, что `docker compose down` без `-v` не удаляет тома Postgres/MinIO; команда пересборки одного сервиса (`up -d --build <service>`).
4. **Диагностика прод-ошибки:** URL вида `http://api.kegazani.ru:9000/...` соответствует старому коду или конфигурации, где публичный HTTP endpoint ошибочно задан как `INGEST_S3_ENDPOINT_URL`; для телефона нужны деплой нового образа, `INGEST_S3_PRESIGN_ENDPOINT_URL=https://s3.<домен>` и внутренний `INGEST_S3_ENDPOINT_URL=http://minio:9000` в Docker.
5. **live-inference-api:** дефолт `LIVE_INFERENCE_WINDOW_MS` изменён с 15000 на 1000; в `infra/compose/on-go-stack.yml` для `live-inference-api` задано `LIVE_INFERENCE_WINDOW_MS: "1000"`; обновлён `services/live-inference-api/README.md`. Прогоны: `python3 -m pytest tests/` в `live-inference-api` — 42 passed.

### Измененные или созданные файлы

1. `services/ingest-api/src/ingest_api/service.py`
2. `services/ingest-api/src/ingest_api/api.py`
3. `services/ingest-api/src/ingest_api/storage.py`
4. `services/ingest-api/src/ingest_api/config.py`
5. `services/ingest-api/tests/test_ingest_lifecycle_fixtures.py`
6. `services/ingest-api/.env.example`
7. `.env.example`
8. `infra/compose/on-go-stack.yml`
9. `infra/compose/raw-ingest-stack.yml`
10. `docs/deployment/server-deploy.md`
11. `docs/setup/local-docker-setup.md`
12. `services/live-inference-api/src/live_inference_api/config.py`
13. `services/live-inference-api/README.md`
14. `docs/status/work-log.md` (данная запись)
15. `docs/status/execution-status.md` (п. `134` «Уже сделано», строка «Параллельно зафиксировано», реестр `OPS-SESSION-20260402`)

### Результат

Критерии ТЗ по presign (HTTPS, публичный хост, согласованность подписи) закреплены в коде и документации; оператору даны безопасные команды перезапуска compose; зафиксирована проверка конфигурации для устранения ATS `-1022`; скользящее окно live-inference по умолчанию 1 s для мобильного отображения; сессия отражена в статусе и журнале по протоколу.

### Следующий рекомендуемый шаг

`M7.10.4` — повторный real-device прогон после деплоя исправленного `ingest-api` и настройки `INGEST_S3_PRESIGN_ENDPOINT_URL` на публичный HTTPS MinIO; проверка `POST /v1/raw-sessions`, что все `upload_url` начинаются с `https://`. Подтвердить шаг по протоколу перед выполнением.

---

## 2026-04-03 - PROTOCOL-SESSION-INDEX-20260403 - Оглавление совместных сессий (март–апрель 2026)

### Запрос

1. Работать по `docs/process/collaboration-protocol.md`.
2. Записать в журнал всё, что было сделано в совместных сессиях с агентом (сквозной обзор).

### Что сделано

1. Прочитаны обязательные для режима документы: `docs/process/collaboration-protocol.md`, `docs/roadmap/research-pipeline-backend-plan.md`, `docs/status/execution-status.md`, `docs/status/work-log.md`.
2. Сопоставлены темы переписки с уже существующими секциями журнала (детали — в перечисленных заголовках, здесь только указатели):
   - **Acceptance / bundle / evidence:** `M7.10`, `M7.10.1`, `M7.10.2`, `M7.10.3` (`2026-03-30`); следующий roadmap-шаг остаётся **`M7.10.4`**.
   - **Live inference и fusion:** `M7.9.1`, **`K5.9`** (`activity_type` / `watch_activity_context`, valence для `public_app`), **`K5.10`** — короткая русскоязычная подпись **`user_display_label`** (см. перечень файлов ниже); объяснения по лёгкой/тяжёлой нагрузке, `physical_load` vs `active_movement`, пост-тренировочному `walking` (практика — сужение окна; черновик ACC-gating не коммитился).
   - **Replay / ingest / UI:** `OPS-20260331`, `OPS-20260331-B`, `OPS-CONSOLIDATED-20260331` (`2026-03-31`).
   - **iOS и прод:** `UI-LIVE-1/2` (`2026-04-01`, репозиторий `on-go-ios`); в статусе также **`OPS-IOS-20260402`** (URL, Caddy, тёмный дашборд, `user_display_label` в клиенте).
   - **Presign / ATS / окно 1 s:** `OPS-SESSION-20260402` (`2026-04-02`).
   - **Диагностика VM и клиента:** `OPS-DIAG-20260402`, `OPS-MOBILE-ENV-20260402`, `DEBUG-INGEST-ATS-20260402` (`2026-04-02`).
   - **Усиление backend:** `OPS-BACKEND-HARDENING-20260402` — секция в этом файле **`2026-04-02 - OPS-BACKEND-HARDENING-20260402`**; кратко также п. **`135`** в `docs/status/execution-status.md`.
   - **Продукт и исследования в протоколе:** `PROTOCOL-PRODUCT-202604` + раздел **`## Продукт и исследования: зафиксировано`** в `docs/process/collaboration-protocol.md` (п. **`136`** в «Уже сделано»).
   - **Наблюдаемость live (пробелы):** `OPS-LIVE-OBS-DOC-20260402` (`2026-04-02`, п. **`137`** в «Уже сделано»).
3. В записи **`OPS-LIVE-OBS-DOC-20260402`** уточнена отсылка к пункту статуса: актуальный номер **`137`**.
4. В **`docs/status/execution-status.md`** добавлен п. **`138`** и уточнена строка «Параллельно зафиксировано в журнале».

### Измененные или созданные файлы

1. `docs/status/work-log.md` (данная секция)
2. `docs/status/execution-status.md` (п. `138`, блок «Параллельно зафиксировано»)

Артефакты **`K5.10`** (уже в репозитории, перечень для трассировки):

1. `services/live-inference-api/src/live_inference_api/user_display_label.py`
2. `services/live-inference-api/src/live_inference_api/api.py`
3. `services/live-inference-api/src/live_inference_api/replay_infer.py`
4. `services/live-inference-api/tests/test_user_display_label.py`
5. `contracts/http/live-inference-api.openapi.yaml`
6. `docs/product/user-display-label-policy.md`
7. `services/replay-infer-ui/public/index.html`

### Результат

Единая точка входа в журнале для навигации по совместной работе; дублирование снято за счёт ссылок на датированные секции; границы между кодом, статусом и протоколом явно разделены.

### Следующий рекомендуемый шаг

По `docs/status/execution-status.md`: подтвердить по протоколу **`M7.10.4`** (real-device acceptance с `--real-device-evidence`) либо выбрать ops-инкремент из **`OPS-LIVE-OBS-DOC-20260402`** / **`OPS-LIVE-OBS-20260402-impl`**.

