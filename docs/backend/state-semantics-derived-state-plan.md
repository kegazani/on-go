# K5.0: State Semantics and Derived-State Rollout Plan

## Цель

Зафиксировать, как backend должен интерпретировать текущее состояние пользователя без ложного обещания "точного распознавания эмоций".

План нужен, чтобы:

1. разделить прямые model outputs и product-facing interpretation;
2. опереться на уже подтвержденные tracks `activity` и `arousal`;
3. оставить `valence` в scoped/internal режиме до более сильного evidence;
4. ввести единый `derived_state` слой для `inference-api` и `live-inference-api`.

## Текущее состояние

На момент `2026-03-28` в проекте уже есть:

1. `activity` и `arousal_coarse` в `inference-api`;
2. scoped policy для `valence` с canary/rollback guardrails;
3. live streaming path;
4. replay/runtime gates и fallback policy для exploratory `valence`.

При этом пока не зафиксированы:

1. единая taxonomy итоговых product-facing состояний;
2. канонический контракт полей `derived_state`, `confidence`, `fallback_reason`;
3. правила, когда система обязана вернуть `unknown`, а не "эмоцию".

## Базовое решение

Слой inference должен быть разделен на две части.

### 1. Direct outputs

Это то, что модель или policy определяет напрямую:

1. `activity`
2. `arousal_coarse`
3. `valence_coarse`

Правило:

1. `activity` и `arousal_coarse` считаются primary runtime outputs.
2. `valence_coarse` разрешен только при прохождении scoped policy и confidence gates.
3. Если `valence` не проходит gate, runtime должен возвращать `unknown`, а не слабое эмоциональное утверждение.

### 2. Derived outputs

Это интерпретационный слой поверх direct outputs:

1. `derived_state`
2. `confidence`
3. `fallback_reason`
4. `claim_level`

Предварительная canonical taxonomy для `derived_state`:

1. `calm_rest`
2. `active_movement`
3. `physical_load`
4. `possible_stress`
5. `positive_activation`
6. `negative_activation`
7. `uncertain_state`

## Claim boundaries

Что можно считать claim-safe на текущем evidence:

1. `rest / movement / activity-context`
2. `low / medium / high arousal`
3. `possible_stress` как guarded interpretation при `rest/stationary + high arousal`

Что нельзя делать default product claim:

1. дискретные эмоции вроде `joy`, `anger`, `fear`, `sadness`;
2. user-facing `valence` без scoped/internal режима;
3. эмоциональные утверждения, если runtime ушел в `unknown` или `uncertain_state`.

## План задач

### K5.1 - State semantics and derived-state contract

Что сделать:

1. Зафиксировать canonical direct outputs и derived outputs.
2. Описать mapping-правила `activity/arousal/valence -> derived_state`.
3. Явно определить `unknown` и `uncertain_state`.
4. Зафиксировать claim boundaries и non-claim language.

Артефакты:

1. backend design note;
2. contract draft для response semantics;
3. decision table для state mapping.

Критерий завершения:

1. можно однозначно ответить, что считается "покой", "движение", "возможное напряжение" и когда возвращается `unknown`.

### K5.2 - Inference and live API response contract update

Что сделать:

1. Обновить `inference-api` и `live-inference-api` contracts.
2. Добавить поля `derived_state`, `confidence`, `fallback_reason`, `claim_level`.
3. Согласовать online и live response shape.

Артефакты:

1. OpenAPI/WebSocket contract update;
2. schema examples;
3. API README updates.

Критерий завершения:

1. у обоих runtime paths один и тот же канонический ответ про состояние пользователя.

### K5.3 - Runtime derived-state layer implementation

Что сделать:

1. Реализовать mapping layer поверх direct predictions.
2. Подключить confidence/fallback rules.
3. Заблокировать user-facing emotional claims вне разрешенных policy contexts.

Артефакты:

1. runtime code в `inference-api` и `live-inference-api`;
2. unit tests на mapping and fallback behavior;
3. example responses для allowed/blocked contexts.

Критерий завершения:

1. runtime отдает стабильный `derived_state` и корректно уходит в `unknown` при слабом сигнале.

### K5.4 - Offline and replay evaluation for derived states

Что сделать:

1. Прогнать replay/offline evaluation для derived-state layer.
2. Измерить coverage, unknown-rate и false-claim risk.
3. Проверить, не маскирует ли derived layer ошибки direct outputs.

Артефакты:

1. evaluation-report;
2. confusion tables;
3. risk summary и recommendation.

Критерий завершения:

1. понятно, какие derived states достаточно стабильны для runtime use, а какие должны оставаться guarded.

### K5.5 - Product wording and exposure policy

Что сделать:

1. Зафиксировать user-facing wording.
2. Разделить internal labels и product copy.
3. Подготовить policy, что можно показывать в app/dashboard/API clients.

Артефакты:

1. wording guide;
2. exposure matrix;
3. examples "safe phrasing" vs "forbidden phrasing".

Критерий завершения:

1. продуктовый слой не обещает больше, чем реально подтверждено evidence.

## Порядок выполнения

Рекомендуемый порядок:

1. `K5.1`
2. `K5.2`
3. `K5.3`
4. `K5.4`
5. `K5.5`

`E2.19` остается отдельным operational monitoring track и не конфликтует с K5, но K5 нужен раньше любого расширения user-facing semantics.

## Статус выполнения K5.1-K5.4

`K5.1` завершен `2026-03-28`.

Артефакты:

1. `docs/backend/state-semantics-derived-state-contract.md`
2. `contracts/operations/derived-state-semantics.schema.json`

`K5.2` завершен `2026-03-28`.

Артефакты:

1. `contracts/http/inference-api.openapi.yaml`
2. `contracts/http/live-inference-api.openapi.yaml`
3. `contracts/operations/examples/inference-semantic-response.example.json`
4. `contracts/operations/examples/live-inference-semantic-message.example.json`

`K5.3` завершен `2026-03-28`.

Артефакты:

1. `services/inference-api/src/inference_api/semantics.py`
2. `services/live-inference-api/src/live_inference_api/semantics.py`
3. `services/inference-api/tests/test_semantics.py`
4. `services/live-inference-api/tests/test_semantics.py`

`K5.4` завершен `2026-03-28`.

Артефакты:

1. `scripts/ml/state_k5_4_derived_state_evaluation.py`
2. `docs/backend/state-semantics-k5-4-derived-evaluation.md`
3. `data/external/wesad/artifacts/wesad/wesad-v1/k5-4-derived-state-evaluation/`

`K5.5` завершен `2026-03-28`.

Артефакты:

1. `docs/backend/state-semantics-k5-5-wording-exposure-policy.md`

## Рекомендуемый следующий шаг

`E2.19 - Long-horizon canary monitoring pack`

В этом шаге нужно:

1. подготовить weekly summary aggregation для canary-контура;
2. зафиксировать incident template и escalation path;
3. собрать handoff-пакет для длительной эксплуатации monitoring цикла.
