# K5.8 - Runtime Bundle Export Path and Live Stream Contract Alignment

## Статус

- Step ID: `K5.8`
- Status: `completed`
- Date: `2026-03-29`

## Цель

Сделать практический runtime-инкремент после `K5.7`: добавить рабочий export path для `model-bundle.manifest.json` и привести live WebSocket contract к `Polar + Watch` sensor shape без ломки обратной совместимости.

## Что сделано

1. Добавлен script-level export path для runtime bundle manifest:
   - `scripts/ml/build_runtime_bundle_manifest.py`.
2. Скрипт умеет формировать `model-bundle.manifest.json` с per-track блоками:
   - `activity`,
   - `arousal_coarse`,
   - optional `valence_coarse` (scoped).
3. В live raw-stream runtime расширен допустимый набор stream names:
   - `watch_accelerometer`,
   - `polar_hr`,
   - `watch_heart_rate` (fallback),
   - `polar_rr`,
   - `watch_activity_context`,
   - `watch_hrv`.
4. В `StreamBuffer` добавлен приоритет heart-source:
   - если есть `polar_hr`, используется он;
   - иначе используется `watch_heart_rate`.
5. Добавлена явная fallback-сигнализация в websocket runtime:
   - при переходе на `watch_heart_rate` отправляется `error` с кодом `heart_source_fallback_active`;
   - при восстановлении `polar_hr` отправляется `error` с кодом `heart_source_recovered`;
   - в каждом `inference` добавлены поля `heart_source` и `heart_source_fallback_active`.
6. Обновлены контракты и docs:
   - `contracts/http/live-inference-api.openapi.yaml`,
   - `services/live-inference-api/README.md`,
   - `scripts/ml/README.md`.
7. Добавлены/обновлены тесты:
   - `test_live_stream_batch_emits_fallback_error_when_using_watch_hr`,
   - `test_try_emit_window_prefers_polar_hr_when_available`.

## Результат

Runtime contract теперь совместим с fusion-сенсорной ролью (`Polar` как preferred heart source), при этом старый `watch_heart_rate` path не сломан. Появился воспроизводимый способ собирать manifest-driven bundle без ручного редактирования JSON.

## Проверка

1. `python3 -m pytest -q` в `services/live-inference-api` -> `13 passed`.
2. `python3 -m pytest -q` в `services/inference-api` -> `5 passed`.
3. `python3 scripts/ml/build_runtime_bundle_manifest.py --help` выполняется успешно.

## Следующий рекомендуемый шаг

`K5.9` - Bundle selection and activation:

1. собрать реальный production runtime bundle из выбранных artifact-кандидатов (`activity`, `arousal`, optional `valence`);
2. подключить его в окружение `inference-api/live-inference-api`;
3. выполнить end-to-end device + backend валидацию на реальном live capture потоке.
