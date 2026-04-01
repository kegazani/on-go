# E2.7: Transfer-robust Valence Stabilization + Re-gate

## Статус

- Parent track: `E2` (`valence transfer stabilization`)
- Step: `E2.7`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Проверить, даст ли `domain-invariant feature strategy` стабильный cross-dataset прирост и позволит ли выделить trusted model subset для `valence`.

## Что сделано

1. Добавлен скрипт:
   - `scripts/ml/valence_e2_7_transfer_robust_gate.py`.
2. Реализован pairwise feature filtering:
   - отбор признаков по междоменному shift-score;
   - отдельный feature subset для каждого направления `source -> target`.
3. Проведен re-gate на направлениях:
   - `WESAD -> {WESAD, G-REx, EmoWear}`,
   - `G-REx -> {WESAD, G-REx, EmoWear}`.
4. Добавлен trusted-model gate:
   - модель считается trusted только если `min(WESAD->G-REx, G-REx->WESAD) >= 0.40`.

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-7-valence-transfer-robust-regate/`

Файлы:

1. `evaluation-report.json`
2. `model-comparison.csv`
3. `feature-shift-selection.csv`
4. `trusted-models.csv`
5. `research-report.md`

## Ключевые результаты

1. Trusted-model subset не сформирован (`trusted_models=[]`).
2. Для ключевого направления `WESAD -> G-REx` метрики низкие:
   - `ridge=0.177901`
   - `catboost=0.184517`
   - `xgboost=0.184517`
3. Итоговый gate decision: `keep_exploratory`.

## Вывод

1. Агрессивный transfer-robust feature filtering в текущем виде слишком сильно режет информативность и приводит к деградации cross-dataset качества.
2. `valence` остается в `exploratory` policy.
3. Нужен следующий шаг с гибридной стратегией (не чистый фильтр), чтобы сохранить приросты `E2.6` и одновременно контролировать domain shift.

## Следующий шаг

`E2.8` — Hybrid transfer adaptation:

1. комбинировать `CORAL`-адаптацию (`E2.6`) с мягким feature reweighting вместо жесткого отсечения;
2. ввести directional guardrails для `WESAD->G-REx` как primary transfer gate;
3. повторить re-gate и оценить readiness для limited-production.
