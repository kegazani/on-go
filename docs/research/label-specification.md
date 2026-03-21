# Спецификация labels: activity, arousal, valence

## Цель

Этот документ фиксирует первую каноническую спецификацию labels для исследовательских paired-сессий `Polar H10 + Apple Watch`.

На этом шаге нужно однозначно определить:

1. какие labels считаются основными для первых исследовательских сессий;
2. в каком масштабе они собираются: `session`, `segment` или `interval`;
3. какие значения допустимы;
4. как labels хранятся и версионируются;
5. какие проверки должна проходить разметка перед использованием в dataset и evaluation.

## Роль labels в исследовательской фазе

Для начальной фазы `Research Foundation` labels делятся на две группы:

1. `activity/context`
   Нужны для классификации наблюдаемого состояния и для интерпретации физиологических сигналов.
2. `arousal` и `valence`
   Нужны как affective self-report targets для последующего моделирования состояния.

Правило первого исследовательского цикла:

1. `activity/context` и `arousal` считаются первичными targets;
2. `valence` собирается с первого дня, но рассматривается как вторичный исследовательский target до накопления достаточного числа сессий.

## Общие принципы

1. Raw session package остается неизменяемым.
2. Labels хранятся как отдельный versioned artifact, связанный с `session_id`.
3. Нужно различать `planned protocol label` и `observed label`.
4. Первичная единица разметки для контролируемых сессий: `protocol_segment`.
5. `interval` и `window` labels могут быть получены позднее автоматически из segment-level labels и границ сегментов.
6. Любой пропуск или неопределенность должны быть выражены явно через `missing_reason`, `unknown` или `confidence`, а не молчаливым отсутствием.

## Единицы разметки

На шаге `A2` фиксируются три уровня:

1. `session-level`
   Итоговая summary-разметка по всей сессии.
2. `segment-level`
   Основной уровень разметки для первых paired-сессий.
3. `interval-level`
   Дополнительный уровень для будущих refinement-задач и free-living data.

Правило для первой версии протокола:

1. каждый выполненный `protocol_segment` должен иметь segment-level `activity label`;
2. каждый выполненный `protocol_segment` должен иметь segment-level `arousal score`;
3. `valence score` собирается минимум на уровне `session`, а на уровне `segment` является настоятельно рекомендованным.

## Label Families

### 1. `protocol_segment_label`

Это не целевая переменная модели, а фиксированная разметка исследовательского сценария.

Разрешенные значения:

1. `baseline_rest`
2. `controlled_block`
3. `movement_block`
4. `recovery`
5. `ad_hoc_segment`

`protocol_segment_label` отражает, что было запланировано по сценарию. Он не заменяет `activity/context` и не должен использоваться как единственный ground truth, если фактическое поведение отличалось от плана.

### 2. `activity_label`

`activity_label` описывает доминирующее фактическое состояние участника в пределах `segment` или `interval`.

Для первой версии фиксируется двухуровневая taxonomy:

#### `activity_group`

Разрешенные значения:

1. `rest`
2. `cognitive`
3. `movement`
4. `recovery`
5. `mixed`
6. `unknown`

#### `activity_label`

Разрешенные значения:

1. `seated_rest`
2. `standing_rest`
3. `focused_cognitive_task`
4. `walking`
5. `stairs`
6. `light_exercise`
7. `vigorous_exercise`
8. `recovery_rest`
9. `mixed_transition`
10. `unknown`

Обязательное соответствие `activity_label -> activity_group`:

1. `seated_rest` -> `rest`
2. `standing_rest` -> `rest`
3. `focused_cognitive_task` -> `cognitive`
4. `walking` -> `movement`
5. `stairs` -> `movement`
6. `light_exercise` -> `movement`
7. `vigorous_exercise` -> `movement`
8. `recovery_rest` -> `recovery`
9. `mixed_transition` -> `mixed`
10. `unknown` -> `unknown`

Интерпретация:

1. `seated_rest`
   Спокойное сидячее состояние без заметной нагрузки.
2. `standing_rest`
   Спокойное стояние без существенного движения.
3. `focused_cognitive_task`
   Ментальная или стрессовая задача при относительно ограниченном движении.
4. `walking`
   Ровная ходьба без выраженной дополнительной нагрузки.
5. `stairs`
   Подъем или спуск по лестнице либо близкая по паттерну нагрузка.
6. `light_exercise`
   Контролируемая физическая активность выше уровня ходьбы, но без высокой интенсивности.
7. `vigorous_exercise`
   Явно интенсивная физическая нагрузка.
8. `recovery_rest`
   Спокойный интервал после нагрузки, используемый для восстановления.
9. `mixed_transition`
   Короткий неоднородный интервал, где нельзя честно выделить один доминирующий activity state.
10. `unknown`
   Фактическая activity недоступна или не может быть восстановлена надежно.

Рекомендуемое соответствие между protocol segments и activity labels:

1. `baseline_rest` -> обычно `seated_rest` или `standing_rest`
2. `controlled_block` -> обычно `focused_cognitive_task`
3. `movement_block` -> обычно `walking`, `stairs`, `light_exercise` или `vigorous_exercise`
4. `recovery` -> обычно `recovery_rest`

### 3. `arousal_score`

`arousal_score` описывает уровень внутренней активации участника независимо от знака эмоции.

Формат:

1. тип значения: `ordinal_int`
2. диапазон: `1..9`
3. источник для первичного label: `participant_self_report`

Якоря шкалы:

1. `1`
   Очень низкая активация, сонливость или почти полное спокойствие.
2. `3`
   Низкая активация, расслабленное состояние.
3. `5`
   Нейтральный или умеренный уровень активации.
4. `7`
   Заметно повышенная активация, напряжение или возбуждение.
5. `9`
   Максимально высокая активация в рамках сессии.

Для первых baseline-задач разрешаются два представления одного и того же label:

1. `ordinal target`
   Исходное значение `1..9`
2. `coarse class`
   `low = 1..3`, `medium = 4..6`, `high = 7..9`

### 4. `valence_score`

`valence_score` описывает субъективную приятность или неприятность состояния.

Формат:

1. тип значения: `ordinal_int`
2. диапазон: `1..9`
3. источник для первичного label: `participant_self_report`

Якоря шкалы:

1. `1`
   Очень неприятное состояние.
2. `3`
   Скорее неприятное состояние.
3. `5`
   Нейтральное состояние.
4. `7`
   Скорее приятное состояние.
5. `9`
   Очень приятное состояние.

Для исследовательной простоты допускаются два производных представления:

1. `ordinal target`
   Исходное значение `1..9`
2. `coarse class`
   `negative = 1..3`, `neutral = 4..6`, `positive = 7..9`

## Правила сбора labels

### Во время сессии

Во время записи capture app или оператор должны:

1. фиксировать границы всех `protocol_segment`;
2. записывать operator notes при отклонении от сценария;
3. не прерывать движение или стрессовый блок ради частого self-report, если это вредит fidelity сессии.

### Сразу после сессии

После завершения сессии участник заполняет короткий post-session report.

Минимальный required набор:

1. `session-level arousal_score`
2. `session-level valence_score`
3. `segment-level arousal_score` для каждого фактически выполненного segment
4. `segment-level dominant activity_label`

Рекомендуемый набор:

1. `segment-level valence_score`
2. `self_report_confidence`
3. короткий free-text комментарий по каждому аномальному segment

### Роль оператора

Оператор может:

1. подтверждать или корректировать `activity_label`;
2. помечать `mixed_transition` или `unknown`, если фактическая активность не соответствует протоколу;
3. добавлять `notes` и `quality flags`.

Оператор не должен подменять собой `arousal_score` и `valence_score`, кроме случая полного отсутствия ответа пользователя. В таком случае affective labels считаются отсутствующими, а не операторскими оценками.

## Канонический storage format

Поскольку raw package должен оставаться immutable, labels хранятся как отдельный artifact.

Рекомендуемая структура:

```text
labels/
  <session_id>/
    <label_set_version>/
      manifest.json
      segment-labels.jsonl
      session-labels.json
```

Где:

1. `manifest.json`
   Описывает версию label set, время публикации, автора и примененные правила.
2. `segment-labels.jsonl`
   Содержит segment-level labels.
3. `session-labels.json`
   Содержит session summary и агрегированные значения.

## Каноническая запись label

Каждая label-record должна содержать:

1. `label_id`
2. `label_set_version`
3. `session_id`
4. `segment_id`, если label относится к segment
5. `scope`
6. `target_name`
7. `value`
8. `value_type`
9. `source`
10. `annotator_type`
11. `annotated_at_utc`
12. `confidence`
13. `notes`

Рекомендуемые значения:

1. `scope`
   `session`, `segment`, `interval`
2. `target_name`
   `protocol_segment_label`, `activity_group`, `activity_label`, `arousal_score`, `valence_score`
3. `value_type`
   `category`, `ordinal_int`
4. `source`
   `protocol`, `participant_self_report`, `operator_review`, `derived_from_segment`
5. `annotator_type`
   `participant`, `operator`, `system`

Минимальный пример segment-level label:

```json
{
  "label_id": "lbl_seg_0001",
  "label_set_version": "A2-v1",
  "session_id": "sess_20260321_001",
  "segment_id": "seg_02",
  "scope": "segment",
  "target_name": "activity_label",
  "value": "focused_cognitive_task",
  "value_type": "category",
  "source": "operator_review",
  "annotator_type": "operator",
  "annotated_at_utc": "2026-03-21T09:19:20Z",
  "confidence": 0.92,
  "notes": "Соответствует фактически выполненной ментальной задаче"
}
```

Минимальный пример affective self-report:

```json
{
  "label_id": "lbl_seg_0002",
  "label_set_version": "A2-v1",
  "session_id": "sess_20260321_001",
  "segment_id": "seg_02",
  "scope": "segment",
  "target_name": "arousal_score",
  "value": 7,
  "value_type": "ordinal_int",
  "source": "participant_self_report",
  "annotator_type": "participant",
  "annotated_at_utc": "2026-03-21T09:19:45Z",
  "confidence": 0.88,
  "notes": "Ментальная задача ощущалась напряженной"
}
```

## Правила валидации

Разметка считается корректной только если выполняются все правила ниже.

### Структурные правила

1. Каждый label обязан ссылаться на существующий `session_id`.
2. `segment-level` label обязан ссылаться на существующий `segment_id`.
3. `target_name` должен принадлежать разрешенному списку.
4. `value` должен соответствовать типу и диапазону `target_name`.
5. `label_set_version` обязателен и immutable после публикации.

### Правила по activity/context

1. Для каждого выполненного `protocol_segment` должен существовать ровно один primary `activity_label`.
2. `activity_group` должен быть согласован с `activity_label`.
3. `mixed_transition` допустим только для реально неоднородных коротких интервалов.
4. `unknown` допустим только с заполненным `notes` или `missing_reason`.
5. Если фактическая активность не совпадает с планом, `protocol_segment_label` сохраняется, а `activity_label` отражает фактическое состояние.

### Правила по arousal/valence

1. `arousal_score` обязан быть целым числом от `1` до `9`.
2. `valence_score` обязан быть целым числом от `1` до `9`.
3. Для первой версии протокола `arousal_score` обязателен на уровне `session` и `segment`.
4. `valence_score` обязателен на уровне `session`; на уровне `segment` он рекомендован, но может отсутствовать.
5. Если segment-level `valence_score` отсутствует, это должно быть явно отражено в session summary.
6. Affective labels с источником, отличным от `participant_self_report`, не считаются ground truth.

### Правила качества

1. `confidence` должна быть числом `0..1`.
2. Если `confidence < 0.5`, label не должен использоваться как primary training target или headline evaluation sample. Подробные правила использования confidence зафиксированы в `docs/research/evaluation-plan.md`.
3. Если у одной и той же сущности есть несколько версий одного label, только одна запись может быть помечена как primary при сборке dataset.
4. Любое ручное исправление должно сохранять traceability через новый label record, а не перезаписывать старый без следа.

## Как использовать labels в следующих шагах

Документ `docs/research/evaluation-plan.md` опирается на эту спецификацию и определяет:

1. какие metrics считать для `activity_label`;
2. считать ли `arousal_score` как ordinal regression, 3-class classification или в обоих режимах;
3. включать ли `valence_score` в обязательный evaluation gate или оставить exploratory track;
4. как учитывать missing labels и low-confidence labels.

## Результат шага A2

После этой спецификации для исследовательской фазы уже зафиксировано:

1. что именно собирается как `activity/context` label;
2. как задаются `arousal` и `valence`;
3. какие значения считаются допустимыми;
4. как labels хранятся и валидируются;
5. на какие target definitions опирается evaluation protocol для следующих modeling-шагов.
