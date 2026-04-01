# E2.5.V2: Valence Label Quality Hardening

## Статус

- Parent step: `E2.5`
- Substep: `V2`
- Status: `completed`
- Date: `2026-03-27`

## Цель

Проверить, можно ли улучшить устойчивость `valence` без новых данных за счет quality-tier policy на train labels.

## Что проверено

Политики:

1. `baseline_all_equal`
2. `tiered_extreme_upweight`
3. `tiered_extreme_focus_drop_neutral`
4. `tiered_soft_neutral_downweight`

Оценка:

1. holdout (`valence_macro_f1`, `valence_qwk`)
2. LOSO (`mean/std/CI` по `valence_macro_f1`, `mean_qwk`)

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-5-valence-v2-label-hardening/`

Файлы:

1. `policy-comparison-holdout.csv`
2. `policy-comparison-loso-fold.csv`
3. `policy-comparison-loso-summary.csv`
4. `policy-best-by-variant.csv`
5. `v2-report.json`
6. `v2-report.md`

## Результаты (best policy by variant)

1. `polar_rr_only`:
   - best: `tiered_extreme_focus_drop_neutral`
   - LOSO mean macro_f1: `0.391852` (улучшение vs V1 baseline `0.321058`)
2. `polar_rr_acc`:
   - best: `tiered_extreme_upweight`
   - LOSO mean macro_f1: `0.468307` (улучшение vs V1 baseline `0.416085`)
3. `watch_plus_polar_fusion`:
   - best: `baseline_all_equal`
   - LOSO mean macro_f1: `0.742540` (policy change не улучшил fusion)

## Вывод

1. Label hardening помогает non-fusion веткам.
2. Для fusion ограничение скорее в feature-side и межсубъектной вариативности, а не в простом reweight policy.
3. Следующий приоритет: `V3` (feature stabilization + ablation на лучших V2 policy).

## Следующий подшаг

`E2.5.V3` — feature stabilization:

1. baseline-normalized признаки;
2. interaction features (`watch context x polar cardio/motion`);
3. controlled ablation с LOSO gate.
