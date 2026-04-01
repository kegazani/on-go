# H3 - Full personalization

## Статус

- Step ID: `H3`
- Status: `completed`
- Date: `2026-03-22`

## Запрос

Реализовать stronger personalization adaptation (`full`) и сравнить `global vs light vs full` на одном protocol, чтобы завершить personalization-фазу перед `I1`.

## Что сделано

1. В `modeling-baselines` добавлен run-kind:
   - `h3-full-personalization-wesad`.
2. Реализован `full personalization` метод:
   - subject-specific refit на `global_train + calibration`;
   - calibration samples усиливаются параметром `adaptation_weight`.
3. Реализовано тройное сравнение для каждого variant:
   - `global`;
   - `light` (из H2 protocol);
   - `full`.
4. Добавлены H3 comparative artifacts:
   - `evaluation-report.json`;
   - `predictions-test.csv`;
   - `per-subject-metrics.csv`;
   - `model-comparison.csv`;
   - `failed-variants.csv`;
   - `research-report.md`;
   - `plots/`.
5. Добавлены H3-specific plots:
   - full-vs-light gain distribution;
   - calibration budget sensitivity (`light` vs `full`);
   - worst-case degradation (`full vs global`).

## Реальный запуск

- `experiment_id`: `h3-full-personalization-wesad-20260322T194248Z`
- Parameters: `calibration_segments=2`, `adaptation_weight=5`
- `successful_variant_count=4`
- `failed_variant_count=0`
- Output root:
  - `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/full-personalization/`

## Ключевые результаты

1. `full` стабильно восстанавливает потери `light` для нескольких моделей (например `watch_only_random_forest`, `fusion_gaussian_nb`) и дает положительный `delta_vs_light`.
2. По текущему holdout full-подход чаще дает `delta_vs_global=0.0`, чем устойчивый положительный прирост — то есть убирает деградацию light-подхода, но не формирует новый headline gain против лучших global моделей.
3. Лучшие full-personalized winners:
   - `activity`: `watch_only_ada_boost` (`macro_f1=1.0`, `delta_vs_global=0.0`);
   - `arousal_coarse`: `watch_only_ada_boost` (`macro_f1=1.0`, `delta_vs_light=+0.388889`).

## Ограничения

1. Небольшой eval holdout после calibration split (`3` subjects, `9` eval segments при budget=2).
2. При отдельных budget значениях full adaptation может переобучаться (видно в sensitivity curves).

## Следующий шаг

`I1 - Research report и production scope decision`
