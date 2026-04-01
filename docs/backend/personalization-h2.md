# H2 - Light personalization

## Статус

- Step ID: `H2`
- Status: `completed`
- Date: `2026-03-22`

## Запрос

Реализовать `light personalization` pipeline (без fine-tune), сделать сравнение `global vs personalized` на одинаковом evaluation subset и выпустить research-grade comparative package.

## Что сделано

1. В `modeling-baselines` добавлен новый run-kind:
   - `h2-light-personalization-wesad`.
2. Реализован `light personalization` метод:
   - subject-level post-hoc predicted->true mapping на calibration subset;
   - disjoint split: calibration segments не пересекаются с evaluation segments.
3. Сравнены несколько candidate families из `H1`:
   - `watch_only_ada_boost`;
   - `watch_only_random_forest`;
   - `fusion_catboost`;
   - `fusion_gaussian_nb`.
4. Собран обязательный research bundle:
   - `evaluation-report.json`;
   - `predictions-test.csv`;
   - `per-subject-metrics.csv`;
   - `model-comparison.csv`;
   - `failed-variants.csv`;
   - `research-report.md`;
   - `plots/`.
5. Добавлены personalization-specific plots:
   - gain distribution по субъектам;
   - sensitivity к calibration budget;
   - worst-case degradation.

## Реальный запуск

- `experiment_id`: `h2-light-personalization-wesad-20260322T193412Z`
- `successful_variant_count=4`
- `failed_variant_count=0`
- Output root:
  - `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/light-personalization/`

## Ключевые результаты

1. Лучшие personalized результаты без деградации:
   - `activity`: `watch_only_ada_boost` (`macro_f1=1.0`, `delta_vs_global=0.0`)
   - `arousal_coarse`: `fusion_catboost` (`macro_f1=1.0`, `delta_vs_global=0.0`)
2. Для части вариантов light calibration показал регресс (`delta_vs_global < 0`), особенно на `arousal_coarse` для watch-only baseline families.
3. На текущем `WESAD` holdout (`3` subjects, `9` eval segments после budget=2) light personalization не дал устойчивого headline gain по сравнению с лучшими global моделями.

## Ограничения

1. Малый holdout (после calibration budget) делает gain-оценки нестабильными.
2. Light personalization в этом шаге ограничен post-hoc mapping (без fine-tune), поэтому ceiling improvement ограничен.

## Следующий шаг

`H3 - Full personalization`
