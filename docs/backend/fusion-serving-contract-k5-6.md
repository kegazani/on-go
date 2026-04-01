# K5.6 - Fusion Serving Contract and Bundle Alignment

## Статус

- Step ID: `K5.6`
- Status: `completed`
- Date: `2026-03-29`

## Цель

Убрать расхождение между research/protocol evidence и текущим runtime serving path, который все еще жестко завязан на `watch_only` model bundle.

## Что зафиксировано

### 1. Канонический direct-model stack

Для runtime должны различаться три прямых track-а:

1. `activity`
   - primary candidate: strongest global production-grade winner из `G3.1/I1`.
   - текущий reference winner: `watch_only_ada_boost`.
   - rationale: `activity` лучше всего подтвержден в claim-grade evidence именно на watch-derived motion path.
2. `arousal_coarse`
   - primary candidate: `fusion-first` stack c `Polar H10` как главным cardio source и `Watch` как motion/context source.
   - research reference winner для Polar+Watch линии: `watch_plus_polar_fusion`.
   - production-grade global winner по model-zoo: `fusion_catboost`.
3. `valence_coarse`
   - только optional/scoped output.
   - strongest research candidate: `watch_plus_polar_fusion + catboost`.
   - runtime policy boundary: `internal_scoped`, `ridge_classifier`, confidence gate `0.7`, без user-facing claims.

### 2. Канонический sensor contract

Для fusion runtime bundle обязательным считается split по ролям источников:

1. `Polar H10`:
   - primary cardio source;
   - baseline streams: `polar_rr`, `polar_hr`;
   - extended streams: `polar_ecg`, `polar_acc`.
2. `Apple Watch`:
   - primary motion/context source;
   - baseline stream: `watch_accelerometer`;
   - optional context streams: `watch_activity_context`, `watch_hrv`.

### 3. Runtime policy

1. `activity` и `arousal_coarse` считаются primary runtime outputs.
2. `valence_coarse` остается scoped path:
   - `internal_dashboard`
   - `research_only`
   - `shadow_mode`
3. `public_app` не должен зависеть от `valence` как от обязательного или user-facing claim track.

## Почему текущий runtime не соответствует контракту

1. `inference-api` и `live-inference-api` грузят только `watch_only_centroid_*` bundle.
2. `live-inference-api` принимает только `watch_heart_rate` и `watch_accelerometer`.
3. current live feature extractor строит только watch-style features и не использует `Polar` как primary cardio source.
4. В репозитории есть research evidence за `fusion` stack, но нет manifest-driven serving path и нет экспортированного runtime bundle под этот контракт.

## Нормализация решения

Для production/runtime больше нельзя считать bundle именованием вида `watch_only_centroid_*` каноническим контрактом. Каноническим должен быть bundle manifest, который явно задает:

1. какой файл отвечает за `activity`;
2. какой файл отвечает за `arousal_coarse`;
3. есть ли `valence_coarse`;
4. какой `feature_profile` ожидается;
5. какие raw/live streams обязательны и какие optional;
6. какой policy scope действует для `valence`.

## Минимальный инкремент после этого шага

1. Перевести loaders на manifest-driven bundle loading.
2. Добавить export path для `fusion` bundles в `modeling-baselines`.
3. Подготовить runtime bundle, в котором:
   - `activity` привязан к approved activity candidate;
   - `arousal` привязан к fusion candidate;
   - `valence` подключается только при scoped policy.

## Следующий рекомендуемый шаг

`K5.7` - Manifest-driven fusion bundle export and runtime loading.
