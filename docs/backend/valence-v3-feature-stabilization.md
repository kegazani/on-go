# E2.5.V3: Valence Feature Stabilization + Ablation

## Статус

- Parent step: `E2.5`
- Substep: `V3`
- Status: `completed`
- Date: `2026-03-27`

## Цель

Проверить, улучшает ли `valence` устойчивость feature-side стабилизация (normalization + interactions) на лучших V2 policy.

## Что проверено

Transforms:

1. `base`
2. `base_plus_norm`
3. `base_plus_norm_interact`

Оценка:

1. holdout (`valence_macro_f1`, `valence_qwk`)
2. LOSO (`mean/std/CI`, `mean_qwk`)

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-5-valence-v3-feature-stabilization/`

Файлы:

1. `transform-comparison-holdout.csv`
2. `transform-comparison-loso-fold.csv`
3. `transform-comparison-loso-summary.csv`
4. `transform-best-by-variant.csv`
5. `v3-report.json`
6. `v3-report.md`

## Результаты (LOSO best by variant)

1. `polar_rr_only`:
   - best transform: `base_plus_norm`
   - LOSO mean macro_f1: `0.414974` (выше V2 best `0.391852`)
2. `polar_rr_acc`:
   - best transform: `base`
   - LOSO mean macro_f1: `0.468307` (без улучшения от normalization/interactions)
3. `watch_plus_polar_fusion`:
   - best transform: `base`
   - LOSO mean macro_f1: `0.742540` (без улучшения от normalization/interactions)

## Вывод

1. Простая normalization-ветка полезна для `polar_rr_only`.
2. Для `polar_rr_acc` и `fusion` текущий bottleneck не решается этим классом feature engineering.
3. Следующий приоритет — `V4`: ordinal-first model sweep (модельный слой), а не дальнейшее усложнение этих же transforms.

## Следующий подшаг

`E2.5.V4` — Ordinal-first model sweep:

1. сравнить model families на валидных V2/V3 конфигурациях;
2. выбрать winner по комбинированному критерию coarse + ordinal stability.
