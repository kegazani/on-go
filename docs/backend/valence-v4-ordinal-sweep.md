# E2.5.V4: Valence Ordinal-first Model Sweep

## Статус

- Parent step: `E2.5`
- Substep: `V4`
- Status: `completed`
- Date: `2026-03-27`

## Цель

Проверить, какая model family дает лучшую устойчивость по `valence` при приоритете ordinal качества (coarse + QWK).

## Что сделано

1. Запущен model sweep на фиксированных лучших конфигурациях `V2/V3`:
   - `polar_rr_only` (`base_plus_norm`, policy from V2)
   - `polar_rr_acc` (`base`, policy from V2)
   - `watch_plus_polar_fusion` (`base`, policy from V2)
2. Сравнены classifier families:
   - `centroid`, `gaussian_nb`, `logistic_regression`, `ridge_classifier`,
   - `random_forest`, `xgboost`, `lightgbm`, `catboost`.
3. Оценка:
   - holdout
   - LOSO (`macro_f1` + `QWK`, tie-break по `QWK`).
4. Зафиксированы failed-runs (`lightgbm` на `polar_rr_only` из-за class coverage condition).

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-5-valence-v4-ordinal-sweep/`

Файлы:

1. `ordinal-sweep-holdout.csv`
2. `ordinal-sweep-loso-fold.csv`
3. `ordinal-sweep-loso-summary.csv`
4. `ordinal-sweep-best-by-variant.csv`
5. `ordinal-sweep-failed.csv`
6. `v4-report.json`
7. `v4-report.md`

## Winner-кандидаты (LOSO)

1. `polar_rr_only`:
   - winner: `centroid`
   - mean macro_f1: `0.430318`
   - mean QWK: `0.470583`
2. `polar_rr_acc`:
   - winner: `ridge_classifier`
   - mean macro_f1: `0.725450`
   - mean QWK: `0.471001`
3. `watch_plus_polar_fusion`:
   - winner: `catboost`
   - mean macro_f1: `0.786984`
   - mean QWK: `0.763680`

## Вывод

1. `V4` дал явный прирост по сравнению с ранними конфигурациями, особенно для `polar_rr_acc` и `fusion`.
2. Для `valence` наиболее сильный текущий кандидат — `watch_plus_polar_fusion + catboost`.
3. Следующий шаг — `V5`: cross-dataset transfer validation, чтобы подтвердить переносимость, а не только `WESAD`-локальный выигрыш.

## Следующий подшаг

`E2.5.V5` — Cross-dataset transfer validation (без нового собственного датасета).
