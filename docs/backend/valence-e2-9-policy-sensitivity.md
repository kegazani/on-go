# E2.9: Direction-specific Transfer Policy + Gate Sensitivity

## Статус

- Parent track: `E2` (`valence transfer governance`)
- Step: `E2.9`
- Status: `completed`
- Date: `2026-03-28`

## Цель

Провести sensitivity-анализ trusted-floor и формализовать direction-specific policy-матрицу для `valence`.

## Что сделано

1. Добавлен скрипт анализа:
   - `scripts/ml/valence_e2_9_policy_sensitivity.py`.
2. На базе `E2.8 model-comparison` рассчитаны gate-состояния для floors:
   - `0.35`
   - `0.38`
   - `0.40`
3. Сформированы:
   - двунаправленная sensitivity-сводка;
   - direction-specific policy matrix (`WESAD->G-REx`, `G-REx->WESAD`).
4. Зафиксировано формальное решение:
   - глобально: `keep_exploratory`;
   - scoped-кандидат: `ridge` при floor `0.35` только для internal/research режима.

## Артефакты

Папка:

- `data/external/wesad/artifacts/wesad/wesad-v1/e2-9-valence-policy-sensitivity/`

Файлы:

1. `evaluation-report.json`
2. `sensitivity-summary.csv`
3. `direction-policy-matrix.csv`
4. `research-report.md`

## Ключевые выводы

1. При default floor `0.40` нет bidirectional trusted-модели.
2. При floor `0.35` только `ridge_classifier` проходит bidirectional gate:
   - `WESAD->G-REx = 0.354316`
   - `G-REx->WESAD = 0.507519`
3. `catboost` и `xgboost` показывают directional pass только в отдельных направлениях и не подходят как bidirectional trusted candidates.

## Policy-решение

1. Глобальная production-policy не меняется: `valence = exploratory_only`.
2. Допускается опциональный узкий scoped режим:
   - `ridge_classifier`,
   - floor `0.35`,
   - только internal/research,
   - без user-facing claims и без автоматических risk-trigger сценариев.

## Следующий шаг

`E2.10` — Operational policy hardening:

1. зафиксировать contract-level флаги scoped режима;
2. добавить runtime guardrails/monitoring для direction-specific маршрутов;
3. подготовить decision gate на включение/отключение scoped режима.
