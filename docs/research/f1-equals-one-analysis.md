# Анализ: macro_f1 = 1.0 — реальные причины и исправление

## Контекст

Пользователь указал, что часть запусков показывает `macro_f1 = 1.0`, что выглядит неправдоподобно. Повторная проверка кода и артефактов подтвердила, что проблема не сводится к "удачному split" или обычному переобучению.

## Где фиксируется F1 = 1.0

Основные артефакты:

- `data/external/wesad/artifacts/wesad/wesad-v1/model-zoo-benchmark/` (`G3.1`)
- `data/external/multi-dataset/comparison/` (`G3.2`)
- downstream-артефакты `H1/H2/H3/H5/I1`, которые опираются на эти запуски

## Факты из кодовой базы

### 1. `G3.2`: явная утечка label-данных в признаки

В `services/modeling-baselines/src/modeling_baselines/multi_dataset.py` использовались признаки:

- `label_source_value_numeric`
- `label_source_label_hash`
- `label_dataset_hash`
- `meta_segment_duration_sec`
- `meta_source_sample_count`

Это означает, что benchmark учился на производных от label/protocol metadata, а не на переносимых signal-признаках. Для `WESAD` этого достаточно, чтобы почти напрямую восстановить target.

Вывод: старые результаты `G3.2` являются невалидными как модельное сравнение.

### 2. `G3.1/H2/H3/H5`: protocol shortcut через `meta_*`

- Split: subject-wise (train 10, val 2, test 3 субъекта).
- Test: `wesad:S10`, `wesad:S14`, `wesad:S16`.
- С учётом `min_confidence = 0.7` test содержит `15` сегментов.
- В feature set входили `meta_segment_duration_sec` и `meta_source_sample_count`.
- Повторная sanity-проверка показала: если оставить только эти два признака, tree-based модели (`random_forest`, `ada_boost`, `gradient_boosting`, `xgboost`, `catboost`) снова дают `macro_f1 = 1.0` на `activity` и `arousal_coarse`.

Причина: сегментные границы в `WESAD` задаются протоколом, а длительность сегмента фактически кодирует состояние сценария (`rest`, `stress`, `amusement`, `recovery`).

### 3. Размер и структура WESAD усиливают проблему

- WESAD: 15 субъектов, ~119 сегментов, 3 условия: baseline, stress (TSST), amusement.
- Holdout очень маленький: всего 3 test-субъекта.
- Даже без явной leakage маленький fixed holdout делает метрику дисперсной.
- На этом фоне shortcut-признаки особенно опасны: модель может выглядеть "идеальной" на одном split.

## Возможные причины F1 = 1.0

### 1. Shortcut features в `WESAD`

- `meta_segment_duration_sec`
- `meta_source_sample_count`

Эти признаки нужно считать небезопасными для headline evaluation, потому что они кодируют протокол, а не физиологию.

### 2. Label leakage в `G3.2`

- `label_source_value_numeric`
- `label_source_label_hash`

Эти признаки прямо используют структуру labels и invalidируют benchmark.

### 3. Недостаточно строгий режим оценки для малого корпуса

- Для малого числа субъектов `evaluation-plan` уже требует `LOSO` или `GroupKFold`.
- Текущие `G3.1/H2/H3/H5` использовали фиксированный holdout на 3 субъектах, что оставляет слишком большую дисперсию.

## Рекомендации

### Исправления в коде

1. Из `modeling-baselines/pipeline.py` убраны `meta_*` из model inputs по умолчанию.
2. В `multi_dataset.py` запрещены `label_*` и `meta_*` shortcut-features.
3. `G3.2` теперь должен пропускать датасет, если для него нет harmonized non-label signal features.

### Следующие шаги для корректной переоценки

1. Пересчитать `G3.1/H2/H3/H5` без `meta_*`.
2. Для `WESAD` перейти на `LOSO` или `GroupKFold`, как уже требует `docs/research/evaluation-plan.md`.
3. Не использовать старые `G3.2/H1/I1` артефакты как evidence до появления harmonized signal features.
4. После нового запуска зафиксировать mean/std/CI, а не единичный "красивый" holdout.

---

*Создано: 2026-03-22. Контекст: docs/process/collaboration-protocol.md.*
