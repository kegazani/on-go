# Personalization User Profile Schema (H1)

## Цель

Зафиксировать канонический профиль пользователя и контракт входов personalization pipeline для шагов `H2` и `H3`.

## Версии

1. `user profile schema`: `h1-v1`
2. `feature contract schema`: `h1-feature-contract-v1`
3. Effective date: `2026-03-22`

## Источники для выбора baseline-кандидатов

1. `G3.1` (`g3-1-model-zoo-wesad-20260322T190114Z`):
   - winner `activity`: `watch_only_ada_boost`, `macro_f1=1.0`
   - winner `arousal_coarse`: `fusion_catboost`, `macro_f1=1.0`
2. `G3.2` (`g3-2-multi-dataset-20260322T191834Z`):
   - `wesad`: winner `activity=label_centroid`, `arousal=label_gaussian_nb`
   - `grex`: winner `activity=label_random_forest`, `arousal=label_gaussian_nb`
   - `emowear`: proxy-label dataset, scores не считаются claim-grade.

## Что входит в профиль пользователя

Профиль делится на блоки:

1. `data_provenance`
   - dataset/split/preprocessing/evaluation версии;
   - traceability к источнику и правилам отбора.
2. `calibration_budget`
   - лимиты на сессии/сегменты/минуты;
   - порог confidence;
   - допустимые label sources.
3. `physiology_baseline`
   - `resting_hr_bpm`, `hrv_rmssd_ms`, `hrv_sdnn_ms`, `resp_rate_bpm`, `eda_scl_uS`.
4. `behavioral_baseline`
   - activity mix;
   - motion intensity range;
   - типичное sleep-window.
5. `quality_summary`
   - usable/excluded coverage и причины исключений.
6. `adaptation_state`
   - ссылка на global модель;
   - активный уровень personalization (`none/light/full`);
   - время последней калибровки.

## Leakage guards

В personalization feature contract запрещено использовать как predictive inputs:

1. `subject_id`
2. `session_id`
3. target labels и их прямые производные
4. post-session annotations вне разрешенного calibration budget

Разрешено использовать subject-specific statistics только если сегмент помечен как `allowed_for_calibration`.

## Кандидаты на старт personalization

### Track: `activity`

1. Global watch-only reference: `watch_only_ada_boost` (`G3.1`)
2. Multi-dataset safety fallback: `label_random_forest` на `G-REx` (`G3.2`)

### Track: `arousal_coarse`

1. Global fusion reference: `fusion_catboost` (`G3.1`)
2. Cross-dataset fallback family: `gaussian_nb` (`G3.2`, стабильный winner на нескольких datasets)

## Правила для H2/H3

1. `H2` (light personalization):
   - без fine-tune всей модели;
   - только normalization/threshold/calibration поверх global кандидатов.
2. `H3` (full personalization):
   - допускается subject-specific head или частичный fine-tune;
   - обязателен отдельный budget-control и worst-case degradation контроль.

## Артефакты

1. Contracts:
   - `contracts/personalization/user-profile.schema.json`
   - `contracts/personalization/personalization-feature-contract.schema.json`
2. H1 research package:
   - `data/artifacts/personalization/h1-profile-schema/evaluation-report.json`
   - `data/artifacts/personalization/h1-profile-schema/model-comparison.csv`
   - `data/artifacts/personalization/h1-profile-schema/per-subject-metrics.csv`
   - `data/artifacts/personalization/h1-profile-schema/research-report.md`
   - `data/artifacts/personalization/h1-profile-schema/plots/*`
