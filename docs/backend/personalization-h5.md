# H5 - Weak-label / label-free personalization benchmark

## Статус

- Step ID: `H5`
- Status: `completed`
- Date: `2026-03-22`

## Запрос

Сравнить `weak-label` и `label-free` personalization variants поверх `WESAD` baseline с полным research-grade пакетом и явным сравнением против `global` reference.

## Что сделано

1. В `modeling-baselines` добавлен новый run-kind:
   - `h5-weak-label-label-free-wesad`.
2. Добавлен новый benchmark pipeline:
   - сравнение `global vs weak_label vs label_free` на одном subject-wise протоколе;
   - weak-label адаптация (частичная подмена calibration labels pseudo-labels);
   - label-free адаптация (pseudo-label adaptation без ручных labels).
3. Добавлены H5 artifacts/writers/report/plots:
   - `evaluation-report.json`;
   - `predictions-test.csv`;
   - `per-subject-metrics.csv`;
   - `model-comparison.csv`;
   - `failed-variants.csv`;
   - `research-report.md`;
   - `plots/h5-*`.
4. Обновлены CLI и документация сервиса:
   - `services/modeling-baselines/src/modeling_baselines/main.py`;
   - `services/modeling-baselines/README.md`.
5. Добавлены unit tests для H5 helper/comparison логики в `tests/test_pipeline.py`.

## Реальный запуск

- `experiment_id`: `h5-weak-label-label-free-wesad-20260322T202905Z`
- Parameters: `calibration_segments=2`, `adaptation_weight=5`
- `successful_variant_count=4`
- `failed_variant_count=0`
- Output root:
  - `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/weak-label-label-free-personalization/`

## Ключевые результаты

1. Для сильных кандидатов (`fusion_catboost`, `watch_only_random_forest`) `label_free` в основном повторяет `global` без устойчивого gain.
2. Для более слабых/нестабильных baseline (`fusion_gaussian_nb`, `watch_only_ada_boost` на activity) `weak-label` и `label-free` дают заметные regressions относительно `global`.
3. В текущем run `label_free` не показал устойчивого прироста относительно `weak-label` (`delta_vs_weak_label` близок к `0` для большинства вариантов).

## Ограничения

1. Небольшой eval holdout после calibration split (`3` test subjects, `9` eval segments при budget=2).
2. Текущий H5 benchmark покрывает `activity` и `arousal_coarse`; `valence` остается отдельным ограниченным track до дополнительной стабилизации evidence.

## Следующий шаг

`H6 - Realtime personalization evaluation plan`
