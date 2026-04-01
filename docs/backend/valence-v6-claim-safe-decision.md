# E2.5.V6: Valence Claim-safe Decision

## Статус

- Parent step: `E2.5`
- Substep: `V6`
- Status: `completed`
- Date: `2026-03-27`

## Цель

Сформировать финальное решение по `valence` после фаз `V1-V5`: можно ли переводить модель в ограниченный production-scope или нужно оставить `exploratory` политику.

## Основание решения

1. `V4` (in-domain LOSO, `WESAD`) показал сильный результат:
   - `watch_plus_polar_fusion + catboost`:
     - `macro_f1=0.786984`
     - `qwk=0.763680`
2. `V5` зафиксировал слабый cross-dataset перенос:
   - `WESAD -> G-REx`: `macro_f1=0.289200`, `qwk=-0.040829`
   - `G-REx -> WESAD`: `macro_f1=0.365079`, `qwk=0.166667`
3. Safety-gates пройдены:
   - `single_feature_probe top_macro_f1=0.885714 < 0.95`
   - permutation sanity: `empirical_p_value=0.0 < 0.05`

## Финальное решение (V6)

1. `valence` не продвигается в `limited-production`.
2. Фиксируется политика: `exploratory_only`.
3. Главный blocker: `domain shift` и недостаточная междатасетная стабильность.

## Deployment boundaries

1. `valence` остается optional-выходом.
2. Включается confidence gate:
   - если `p_max < 0.7` -> вернуть `unknown` и подавить prediction.
3. Запрещены user-facing claim/алерты только на основе `valence`.
4. `valence` не используется как единственный триггер personalization update.

## Monitoring KPI

1. `valence_macro_f1_replay_wesad_like`:
   - target: `>=0.72`
   - alert: `<0.65`
2. `valence_qwk_replay_wesad_like`:
   - target: `>=0.55`
   - alert: `<0.40`
3. `cross_dataset_macro_f1_floor`:
   - target: `>=0.45`
   - alert: `<0.35`
4. `unknown_rate_after_confidence_gate`:
   - target: `<=0.35`
   - alert: `>0.50`

## Артефакты V6

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-5-valence-v6-claim-safe-decision/`

Файлы:

1. `decision-report.json`
2. `model-comparison.csv`
3. `monitoring-kpis.csv`
4. `research-report.md`
5. `plots/v5-transfer-macro_f1.png`
6. `plots/v5-transfer-qwk.png`

## Следующий шаг

`E2.6` — Domain adaptation + calibration для `valence` (без нового датасета), затем повторный cross-dataset gate.
