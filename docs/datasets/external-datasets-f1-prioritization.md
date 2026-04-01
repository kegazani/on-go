# F1: Обзор и приоритет внешних датасетов

## Цель шага

Зафиксировать shortlist внешних датасетов и порядок их подключения в `F2`,
чтобы импорт в `dataset registry` шел маленькими проверяемыми инкрементами.

Фокус шага: `activity/context` и `arousal` как mandatory tracks (`A3`), `valence` как exploratory.

## Кандидаты из roadmap

1. `WESAD`
2. `EmoWear`
3. `G-REx`
4. `DAPPER`

## Критерии приоритизации

Используется шкала `1..5` (`5 = лучше`):

1. `target_fit`
   Насколько dataset закрывает наши target tracks (`activity`, `arousal`, `valence`).
2. `sensor_fit`
   Насколько модальности близки к нашему `watch-only/fusion` контексту.
3. `label_quality`
   Насколько четко определены labels и как легко их привести к нашим canonical labels.
4. `ingestion_effort`
   Насколько просто реализовать первый import pipeline.
5. `license_risk`
   Насколько предсказуемы условия использования для research/internal R&D.

## Приоритизационная матрица (F1)

| Dataset | target_fit | sensor_fit | label_quality | ingestion_effort | license_risk | Приоритет |
| --- | --- | --- | --- | --- | --- | --- |
| WESAD | 5 | 4 | 4 | 4 | 4 | P1 |
| EmoWear | 4 | 4 | 3 | 3 | 3 | P2 |
| DAPPER | 3 | 3 | 3 | 2 | 3 | P3 |
| G-REx | 3 | 2 | 2 | 2 | 2 | P4 |

## Рекомендованный порядок подключения

1. `P1: WESAD` (стартовый import в `F2`)
   - лучший баланс по `arousal/stress` track и скорости запуска;
   - подходит как первый reference dataset для проверки end-to-end `dataset registry`.
2. `P2: EmoWear`
   - полезен как следующий шаг после стабилизации маппинга labels и split strategy.
3. `P3: DAPPER`
   - подключать после двух первых импортов, когда зафиксирован шаблон адаптеров.
4. `P4: G-REx`
   - отложенный импорт из-за более высокой неопределенности по label-mapping и effort.

## Правила нормализации во внутреннюю схему

Для каждого датасета в `F2` обязателен mapping в canonical artifacts:

1. `subject/session/stream/label` совместимый формат (`docs/research/session-data-schema.md`).
2. Label mapping в `activity_label/activity_group`, `arousal_score`, `valence_score`.
3. `dataset provenance`:
   - `source_dataset`;
   - `source_version`;
   - `ingestion_script_version`;
   - `preprocessing_version`.
4. Явная фиксация ограничений:
   - missing modalities;
   - missing labels;
   - confidence/quality caveats.

## Ограничения и допущения

1. Этот документ фиксирует инженерный приоритет импорта, а не финальное научное сравнение датасетов.
2. Финальная юридическая верификация лицензий выполняется при реализации `F2`.
3. Если фактические форматы/лицензии датасетов отличаются от допущений `F1`, приоритет может быть пересмотрен отдельным update в статусе.

## Выход шага F1

1. Зафиксирован shortlist и order-of-implementation для внешних датасетов.
2. Следующий шаг `F2`: сделать `dataset registry` и выполнить первый импорт (`WESAD`) в unified схему.
