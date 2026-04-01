# K5.7 - Manifest-driven Runtime Bundle Loading

## Статус

- Step ID: `K5.7`
- Status: `completed`
- Date: `2026-03-29`

## Цель

Перевести runtime loading с жестко зашитого `watch_only_centroid_*` именования на manifest-driven bundle, который умеет различать per-track model/feature spaces для `activity`, `arousal_coarse` и optional `valence_coarse`.

## Что сделано

1. Добавлен канонический JSON Schema контракт:
   - `contracts/operations/inference-bundle-manifest.schema.json`.
2. `inference-api` переведен на новый loader:
   - сначала ищется `model-bundle.manifest.json`,
   - затем, если manifest отсутствует, включается legacy fallback на старый watch-only bundle.
3. `live-inference-api` переведен на тот же loader pattern:
   - manifest-driven `LoadedBundle`,
   - optional `valence_coarse`,
   - сохранен legacy fallback для обратной совместимости.
4. В bundle loading добавлена поддержка разных feature spaces по track-ам:
   - `activity` может использовать `watch-only` feature profile;
   - `arousal_coarse` может использовать `fusion` feature profile;
   - `valence_coarse` может использовать свой feature profile и включаться только как scoped path.
5. `inference-api` теперь корректно различает:
   - `valence_enabled`,
   - `valence_model_not_available`.
6. Добавлены unit-тесты на manifest loading и per-track feature usage.

## Что это решает

1. Runtime больше не зависит от названий вида `watch_only_centroid_activity.joblib` как от канонического production contract.
2. Появилась техническая основа для mixed stack, который был зафиксирован в `K5.6`:
   - `activity` на watch-driven candidate;
   - `arousal_coarse` на Polar+Watch fusion candidate;
   - `valence_coarse` как optional scoped candidate.

## Что это еще не решает

1. В репозитории все еще нет экспортированного fusion runtime bundle с реальными artifact-файлами.
2. `live-inference-api` raw stream contract все еще watch-centric и пока не доведен до полного `Polar + Watch` live feature path.

## Следующий рекомендуемый шаг

`K5.8` - Export selected runtime bundle and align live raw-stream contract:

1. экспортировать approved per-track artifacts в manifest-driven bundle;
2. согласовать live raw streams с `Polar cardio + Watch accel/context`;
3. подключить этот bundle в `inference-api/live-inference-api` как основной runtime path.
