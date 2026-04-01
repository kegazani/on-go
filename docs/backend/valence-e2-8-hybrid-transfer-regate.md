# E2.8: Hybrid Transfer Adaptation + Re-gate

## Статус

- Parent track: `E2` (`valence transfer stabilization`)
- Step: `E2.8`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Проверить, может ли гибридный подход (`CORAL + soft feature reweighting`) снять деградацию `E2.7` и сформировать trusted model subset.

## Что сделано

1. Добавлен скрипт:
   - `scripts/ml/valence_e2_8_hybrid_transfer.py`.
2. Реализован гибрид:
   - `soft` понижение веса high-shift признаков (без полного отсечения);
   - `CORAL`-адаптация на reweighted пространстве.
3. Выполнен cross-dataset re-gate на:
   - `WESAD/G-REx -> WESAD/G-REx/EmoWear`.
4. Проверен trusted criterion:
   - `min(WESAD->G-REx, G-REx->WESAD) >= 0.40`.

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-8-valence-hybrid-transfer-regate/`

Файлы:

1. `evaluation-report.json`
2. `model-comparison.csv`
3. `soft-weights-summary.csv`
4. `trusted-models.csv`
5. `research-report.md`

## Ключевые результаты

1. Trusted-model subset снова не сформирован (`trusted_models=[]`).
2. Лучший компромисс показал `ridge_classifier`:
   - `WESAD->G-REx = 0.354316`
   - `G-REx->WESAD = 0.507519`
   - но `min_cross = 0.354316 < 0.40`.
3. У `catboost` и `xgboost` наблюдается асимметрия переноса:
   - одна сторона близко/выше порога, другая резко ниже.

## Вывод

1. `E2.8` лучше `E2.7` по части направлений, но не закрывает trusted-floor в двунаправленном gate.
2. Основной блокер теперь не общий провал, а directional asymmetry transfer.
3. Решение сохраняется: `keep_exploratory`.

## Следующий шаг

`E2.9` — Direction-specific policy + gate sensitivity:

1. разделить policy для направлений (`WESAD->G-REx` и `G-REx->WESAD`);
2. провести sensitivity-анализ trusted-floor (`0.35/0.38/0.40`);
3. определить, можно ли формально открыть `limited-production` только для узкого scoped режима без user-facing claims.
