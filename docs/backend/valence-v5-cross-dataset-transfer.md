# E2.5.V5: Valence Cross-dataset Transfer Validation

## Статус

- Parent step: `E2.5`
- Substep: `V5`
- Status: `completed`
- Date: `2026-03-27`

## Цель

Проверить, что улучшения `valence` из `V1-V4` не являются только локальным `WESAD` split-эффектом, а проходят базовую проверку переносимости на внешние датасеты.

## Что сделано

1. Добавлен воспроизводимый V5 скрипт:
   - `scripts/ml/valence_v5_cross_dataset_transfer.py`.
2. Собран cross-dataset evaluation пакет на:
   - sources: `WESAD`, `G-REx`;
   - targets: `WESAD`, `G-REx`, `EmoWear`;
   - classifiers: `centroid`, `ridge_classifier`, `catboost`, `xgboost`.
3. Для каждого `source -> target` рассчитаны:
   - `macro_f1`,
   - `balanced_accuracy`,
   - `QWK`,
   - subject-level метрики.
4. Добавлены data-coverage и failure registry + heatmap plots.

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-5-valence-v5-cross-dataset-transfer/`

Файлы:

1. `transfer-matrix.csv`
2. `transfer-summary.csv`
3. `transfer-subject-metrics.csv`
4. `transfer-data-coverage.csv`
5. `transfer-failed.csv`
6. `v5-report.json`
7. `v5-report.md`
8. `plots/v5-transfer-macro_f1.png`
9. `plots/v5-transfer-qwk.png`

## Ключевые результаты

1. In-domain (`WESAD -> WESAD`) лучший: `ridge_classifier` (`macro_f1=0.833333`, `qwk=0.719101`).
2. Cross-dataset перенос существенно ниже:
   - `WESAD -> G-REx`: best `xgboost` (`macro_f1=0.289200`, `qwk=-0.040829`);
   - `G-REx -> WESAD`: best `catboost` (`macro_f1=0.365079`, `qwk=0.166667`).
3. `EmoWear` имеет `proxy`-лейблы и не содержит `high` класса в test (`transfer-data-coverage.csv`), поэтому интерпретация переносимости ограничена.

## Вывод

1. `V5` подтвердил, что основной риск `valence` сейчас связан с `domain shift`, а не только с локальным split artifacts.
2. Победа `catboost` в `V4` для fusion-линии не автоматически переносится в cross-dataset контур.
3. Для claim-safe решения нужен финальный `V6`:
   - зафиксировать production-границы использования `valence`,
   - определить promotion policy (что допускается как claim-grade, а что остается exploratory).

## Следующий подшаг

`E2.5.V6` — финальная claim-safe рекомендация по `valence` и freeze policy.
