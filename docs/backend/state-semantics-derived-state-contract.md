# K5.1: State Semantics and Derived-State Contract

## Цель

Зафиксировать канонический semantic contract для runtime-интерпретации состояния пользователя:

1. какие direct outputs считаются входом semantic layer;
2. как `activity/arousal/valence` маппятся в `derived_state`;
3. когда система обязана вернуть `uncertain_state` и `no_claim`;
4. какие `fallback_reason` и `claim_level` разрешены.

Дата фиксации: `2026-03-28`.

## Canonical direct outputs

Semantic layer использует нормализованные direct outputs.

### 1. `activity_class`

Разрешенные значения:

1. `rest`
2. `recovery`
3. `movement`
4. `physical_load`
5. `cognitive`
6. `mixed`
7. `unknown`

Нормализация делается из runtime activity labels (watch/fusion) по mapping-таблице K5.3.

### 2. `arousal_coarse`

Разрешенные значения:

1. `low`
2. `medium`
3. `high`
4. `unknown`

### 3. `valence_coarse`

Разрешенные значения:

1. `negative`
2. `neutral`
3. `positive`
4. `unknown`

`valence_coarse` учитывается только если:

1. scoped policy effective mode не `disabled`;
2. контекст входит в `allowed_contexts`;
3. отсутствует `auto_disable`;
4. пройден confidence gate valence policy.

Иначе valence считается `unknown` с соответствующим `fallback_reason`.

## Canonical derived outputs

### 1. `derived_state`

Разрешенные значения:

1. `calm_rest`
2. `active_movement`
3. `physical_load`
4. `possible_stress`
5. `positive_activation`
6. `negative_activation`
7. `uncertain_state`

### 2. `claim_level`

Разрешенные значения:

1. `safe` — допустим user-facing claim без эмоциональной категоризации;
2. `guarded` — допустим только осторожный wording (например "возможное напряжение");
3. `internal_only` — только internal/research/dashboard contexts;
4. `no_claim` — user-facing claim запрещен.

### 3. `fallback_reason`

Разрешенные значения:

1. `none`
2. `insufficient_signal`
3. `low_confidence`
4. `unknown_activity`
5. `unknown_arousal`
6. `contradictory_signals`
7. `valence_policy_disabled`
8. `valence_context_blocked`
9. `valence_auto_disabled`
10. `valence_low_confidence`

### 4. `confidence`

Канонический shape для K5.2:

1. `score` (`0..1` или `null`, если confidence не вычислен);
2. `band` (`high` / `medium` / `low` / `insufficient`).

## Правила `unknown` и `uncertain_state`

1. `unknown` используется только на уровне direct outputs (`activity_class`, `arousal_coarse`, `valence_coarse`).
2. `uncertain_state` используется только как derived output.
3. Если `activity_class=unknown` или `arousal_coarse=unknown`, runtime обязан вернуть:
   - `derived_state=uncertain_state`
   - `claim_level=no_claim`
   - `fallback_reason=unknown_activity` или `unknown_arousal`.
4. Если direct outputs противоречат друг другу и не попадают ни в одно каноническое правило, runtime обязан вернуть:
   - `derived_state=uncertain_state`
   - `claim_level=no_claim`
   - `fallback_reason=contradictory_signals`.

## Decision table (`activity/arousal/valence -> derived_state`)

Правила применяются в порядке приоритета сверху вниз.

| Rule | Условия | derived_state | claim_level | fallback_reason |
| --- | --- | --- | --- | --- |
| R1 | `activity_class=unknown` | `uncertain_state` | `no_claim` | `unknown_activity` |
| R2 | `arousal_coarse=unknown` | `uncertain_state` | `no_claim` | `unknown_arousal` |
| R3 | `activity_class in {mixed}` | `uncertain_state` | `no_claim` | `insufficient_signal` |
| R4 | `activity_class in {rest,recovery}` and `arousal_coarse=low` | `calm_rest` | `safe` | `none` |
| R5 | `activity_class=movement` and `arousal_coarse in {low,medium}` | `active_movement` | `safe` | `none` |
| R6 | `activity_class=physical_load` and `arousal_coarse in {medium,high}` | `physical_load` | `safe` | `none` |
| R7 | `activity_class in {rest,recovery,cognitive}` and `arousal_coarse=high` and `valence_coarse in {unknown,neutral}` | `possible_stress` | `guarded` | `none` |
| R8 | `arousal_coarse=high` and `valence_coarse=positive` and valence policy passed | `positive_activation` | `internal_only` | `none` |
| R9 | `arousal_coarse=high` and `valence_coarse=negative` and valence policy passed | `negative_activation` | `internal_only` | `none` |
| R10 | default | `uncertain_state` | `no_claim` | `contradictory_signals` |

### Уточнение по valence fallback в R4-R7

Если valence недоступен из-за policy, в ответе остается rule-based derived state, но `fallback_reason` выставляется приоритетно:

1. `valence_policy_disabled`
2. `valence_context_blocked`
3. `valence_auto_disabled`
4. `valence_low_confidence`

Это не повышает `claim_level` и не переводит valence-зависимые states в user-facing claims.

## Claim boundaries (K5.1 freeze)

### Разрешено как claim-safe

1. `calm_rest`, `active_movement`, `physical_load` (`claim_level=safe`);
2. `possible_stress` только с guarded wording (`claim_level=guarded`).

### Только internal/research

1. `positive_activation`, `negative_activation` (`claim_level=internal_only`);
2. любые valence-driven интерпретации в `public_app` контексте.

### Запрещено

1. дискретные эмоции (`joy`, `anger`, `fear`, `sadness`) как runtime default;
2. user-facing claims при `claim_level=no_claim`;
3. эмоциональные утверждения, если `derived_state=uncertain_state`.

## Non-claim language baseline

Для `claim_level=guarded` и `no_claim`:

1. использовать формулировки вида `possible`, `may indicate`, `insufficient confidence`;
2. не использовать категоричные утверждения `you are ...` или диагнозоподобные формулировки.

## Артефакты K5.1

1. Этот документ: `docs/backend/state-semantics-derived-state-contract.md`.
2. Contract draft schema: `contracts/operations/derived-state-semantics.schema.json`.

## Следующий шаг

`K5.2` — обновить HTTP/WS контракты (`inference-api`, `live-inference-api`) под canonical поля:

1. `derived_state`
2. `confidence`
3. `fallback_reason`
4. `claim_level`
