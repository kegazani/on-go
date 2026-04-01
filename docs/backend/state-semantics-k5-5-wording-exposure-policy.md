# K5.5: Product Wording and Exposure Policy

## Цель

Зафиксировать product-safe правила показа semantic runtime output (`derived_state`, `claim_level`, `fallback_reason`) в user-facing и internal каналах.

Дата фиксации: `2026-03-28`.

## Принцип разделения labels и product copy

1. `derived_state` и `fallback_reason` считаются internal runtime labels и не обязаны показываться пользователю как есть.
2. Пользовательский текст формируется только через policy-шаблоны по `claim_level`.
3. Если `claim_level=no_claim`, используется fallback copy, а не утверждение о состоянии.

## Wording by claim level

### `safe`

Разрешено:

1. Нейтральные описания контекста состояния (`покой`, `движение`, `физическая нагрузка`).
2. Фразы с ограничением на текущий момент времени (`сейчас`, `в текущем окне`).

Шаблоны:

1. `Сейчас наблюдается спокойное состояние.`
2. `Сейчас наблюдается активное движение.`
3. `Сейчас наблюдается физическая нагрузка.`

### `guarded`

Разрешено:

1. Только осторожные формулировки (`возможное`, `может указывать`).
2. Явная некатегоричность интерпретации.

Шаблоны:

1. `Возможны признаки напряжения.`
2. `Текущие сигналы могут указывать на повышенное напряжение.`

### `internal_only`

Правило:

1. В `public_app` и внешних user-facing клиентах не показывается.
2. Разрешено только в `internal_dashboard/research`.

Internal copy:

1. `High arousal with positive valence signal (internal use only).`
2. `High arousal with negative valence signal (internal use only).`

### `no_claim`

Правило:

1. Любые state-claims запрещены.
2. Используется fallback copy для `uncertain_state` и неизвестных direct outputs.

Fallback copy:

1. `Недостаточно уверенности для оценки текущего состояния.`
2. `Сигнал недостаточен для надежной интерпретации состояния.`

## Exposure matrix

| Канал | `safe` | `guarded` | `internal_only` | `no_claim` |
| --- | --- | --- | --- | --- |
| `public_app` | Показывать neutral safe copy | Показывать только guarded copy | Не показывать; заменять на no-claim fallback | Показывать fallback copy |
| `partner_api_public` | Возвращать semantic fields + `display_text` safe | Возвращать semantic fields + guarded `display_text` | Возвращать `derived_state=uncertain_state`, `claim_level=no_claim` для внешнего payload | Возвращать no-claim fallback |
| `internal_dashboard` | Показывать | Показывать | Показывать с бейджем `internal_only` | Показывать + fallback explanation |
| `research_report` | Показывать | Показывать | Показывать | Показывать |
| `replay_debug` | Показывать | Показывать | Показывать | Показывать |

## State-to-copy mapping (public scope)

| derived_state | claim_level | Public copy |
| --- | --- | --- |
| `calm_rest` | `safe` | `Сейчас наблюдается спокойное состояние.` |
| `active_movement` | `safe` | `Сейчас наблюдается активное движение.` |
| `physical_load` | `safe` | `Сейчас наблюдается физическая нагрузка.` |
| `possible_stress` | `guarded` | `Возможны признаки напряжения.` |
| `positive_activation` | `internal_only` | `Недостаточно уверенности для оценки текущего состояния.` |
| `negative_activation` | `internal_only` | `Недостаточно уверенности для оценки текущего состояния.` |
| `uncertain_state` | `no_claim` | `Недостаточно уверенности для оценки текущего состояния.` |

## Forbidden phrasing

Запрещено в user-facing каналах (`public_app`, `partner_api_public`):

1. Категоричные эмоциональные утверждения: `Вы злитесь`, `Вы в депрессии`, `Вы испытываете страх`.
2. Диагностические/медицинские утверждения: `У вас тревожное расстройство`, `У вас паническая атака`.
3. Утверждения про намерения/личность: `Вы агрессивны`, `Вы эмоционально нестабильны`.
4. Любые утверждения о valence при `claim_level` не равном `internal_only` и без internal-контекста.
5. Любые claims при `claim_level=no_claim` или `derived_state=uncertain_state`.

## Fallback policy for `uncertain_state`

1. Основной текст: `Недостаточно уверенности для оценки текущего состояния.`
2. Дополнительный текст (опционально): `Попробуйте продолжить ношение устройства и повторить оценку позже.`
3. В `public_app` не показывать `fallback_reason` как технический код; допускается только human-readable reason.
4. В `internal_dashboard/research` показывать и текст, и технический `fallback_reason`.

## API client integration notes

1. Клиенты должны обрабатывать `claim_level` как приоритетный флаг показа текста.
2. Клиенты не должны напрямую рендерить `derived_state` без policy mapping.
3. Для внешних клиентов рекомендуется отдельное поле `display_text`, вычисленное policy-слоем.

## Артефакты K5.5

1. Этот документ: `docs/backend/state-semantics-k5-5-wording-exposure-policy.md`.
