# E2.5.V1: Valence Error Anatomy

## Статус

- Parent step: `E2.5`
- Substep: `V1`
- Status: `completed`
- Date: `2026-03-27`

## Цель

Зафиксировать, где именно `valence` нестабилен до начала улучшений (`V2+`), без нового датасета.

## Что сделано

1. Построен segment-level error breakdown по `E2.3` predictions.
2. Построена subject-level таблица стабильности `valence` для каждого варианта.
3. Построены class-level precision/recall (`negative/neutral/positive`).
4. Добавлен LOSO summary (`E2.4`) в единый V1 пакет.
5. Подготовлен V1 summary report с failure modes и следующим действием.

## Артефакты V1

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-5-valence-v1-error-anatomy/`

Файлы:

1. `valence-error-analysis.csv`
2. `valence-subject-stability.csv`
3. `valence-confusion-by-variant.csv`
4. `valence-class-performance.csv`
5. `valence-loso-summary.csv`
6. `valence-v1-report.md`

## Ключевые наблюдения

1. На одном test split:
   - `watch_plus_polar_fusion` дает `valence_macro_f1=1.0`.
2. Но LOSO показывает более реалистичную картину:
   - `watch_plus_polar_fusion` mean `valence_macro_f1=0.742540`, `std=0.187386`.
3. Для `polar_rr_only` и `polar_rr_acc` основные ошибки приходятся на смешение `neutral` и `positive`.
4. Следовательно, одиночный holdout-результат недостаточен для claim-safe решения по `valence`.

## Следующий подшаг

`E2.5.V2` — Label Quality Hardening (`tiered weights + confidence policy`).
