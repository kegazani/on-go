# Evaluation Plan и метрики

## Цель

Этот документ фиксирует, как в исследовательской фазе оценивать модели и делать сравнения между:

1. `watch-only` и `fusion` моделями;
2. `global` и `personalized` вариантами;
3. обязательными и exploratory target tracks.

Главная задача шага `A3`: задать единый и воспроизводимый evaluation protocol, чтобы дальнейшие шаги `G1-G3` и `H1-H3` сравнивались по одним и тем же правилам.

## Какие исследовательские вопросы закрывает A3

После этого документа проект должен однозначно отвечать на вопросы:

1. Какой target является основным для первой волны экспериментов.
2. Какие метрики считаются headline-метриками, а какие идут как вспомогательные.
3. Как именно делаются честные split rules без утечки по `subject`.
4. Как сравниваются `watch-only`, `fusion` и personalized-варианты.
5. Когда результат можно называть подтверждением гипотезы, а когда только предварительным сигналом.

## Evaluation Tracks

В первой исследовательской фазе вводятся три tracks.

### 1. `activity/context` track

Это обязательный track для первых baseline-моделей.

Основной target:

1. `activity_label` на уровне `segment`

Дополнительный derived target:

1. `activity_group`, получаемый из `activity_label` по правилам из `docs/research/label-specification.md`

Правило:

1. headline-метрика считается по `activity_label`;
2. `activity_group` всегда репортится рядом как более грубый sanity-check.

### 2. `arousal` track

Это обязательный affective track для первой волны исследований.

Основной target:

1. `arousal_score` на уровне `segment`

Для него обязательно считать два представления одного и того же target:

1. `coarse class`
   `low = 1..3`, `medium = 4..6`, `high = 7..9`
2. `ordinal`
   исходное значение `1..9`

Правило:

1. headline-сравнение делается по coarse-class представлению;
2. ordinal-метрики обязательно добавляются, чтобы не потерять порядок шкалы.

### 3. `valence` track

Это exploratory track до накопления более устойчивого корпуса данных.

Основные правила:

1. `session-level valence_score` собирается и хранится с первого дня;
2. `segment-level valence_score` оценивается только когда он реально присутствует;
3. результаты по `valence` не используются как обязательный research gate для перехода к фазе `B`.

## Что считается честным сравнением моделей

Любой headline-сравнительный результат обязан соблюдать все правила ниже.

### Сравнение `watch-only` vs `fusion`

1. Используется один и тот же split manifest.
2. Используется один и тот же evaluation subset.
3. Разрешается менять только входные модальности, а не саму постановку задачи.
4. Если архитектуры отличаются, это должно быть явно обозначено как отдельный experiment family, а не как чистое сравнение модальностей.

### Сравнение `global` vs `personalized`

1. Personalized-вариант должен стартовать из той же глобальной постановки или той же baseline-family.
2. Должен быть явно указан calibration/adaptation budget:
   - сколько сессий субъекта разрешено использовать;
   - какие именно сегменты доступны адаптации;
   - в какой момент времени они становятся доступны.
3. Evaluation subset для personalized и global-варианта должен совпадать.

## Запрещенные источники утечки

Следующие поля не должны использоваться как predictive inputs в headline-экспериментах:

1. `subject_id`
2. `session_id`
3. `protocol_segment_label`
4. post-session self-report
5. operator notes
6. `activity_label`, `arousal_score`, `valence_score` или любые derived labels

Разрешение на использование subject-specific statistics появляется только в personalization track и только если они построены из допустимого calibration subset.

## Единица evaluation

Headline-evaluation для первой исследовательской волны задается как `segment-centric`.

Это означает:

1. один `protocol_segment` считается одной evaluation-единицей;
2. длинные сегменты не должны автоматически иметь больший вес только потому, что в них больше окон;
3. если модель работает по окнам, headline-метрики все равно считаются после агрегации к `segment`.

Требование к агрегации:

1. rule агрегации должен быть фиксирован и описан в отчете;
2. window-level метрики можно показывать дополнительно, но не как headline.

## Evaluation Subsets

### `paired_eval_subset`

Используется для честного сравнения `watch-only` и `fusion`.

Сегмент попадает в этот subset только если:

1. сессия имеет статус `research_usable`;
2. сессия удовлетворяет `paired_complete`;
3. для сегмента есть требуемый ground truth label;
4. есть пересекающееся временное покрытие между `Polar H10` и `Apple Watch` не менее `80%` длительности сегмента;
5. все required streams для конкретной постановки признаны пригодными по quality flags.

### `watch_only_extended_subset`

Может использоваться для отдельных watch-only экспериментов, если есть дополнительные watch-only записи или неполные paired-сессии.

Правило:

1. этот subset можно использовать для ablations и data-scaling исследований;
2. его нельзя использовать для headline-заявления о превосходстве `fusion` над `watch-only`.

### `valence_exploratory_subset`

Содержит только те сессии или сегменты, где `valence_score` реально размечен и проходит quality rules.

## Правила включения и исключения данных

### Сессии

Сессия допускается в primary evaluation только если:

1. она помечена как `research_usable`;
2. все аномалии и gaps явно задокументированы;
3. version identifiers для raw package, labels и preprocessing известны.

### Сегменты

Сегмент допускается в headline evaluation только если:

1. сегмент не является только запланированным placeholder без фактического выполнения;
2. сегмент фактически выполнен и имеет наблюдаемые границы;
3. target label соответствует допустимому диапазону и типу;
4. для label известен `source`.

### Confidence rules

1. `confidence < 0.5`
   Сэмпл исключается и из primary training, и из headline evaluation.
2. `0.5 <= confidence < 0.7`
   Сэмпл может попадать только в вспомогательный sensitivity analysis и должен быть явно отмечен.
3. `confidence >= 0.7`
   Сэмпл допустим для headline evaluation.

### Source rules

1. `activity_label`
   Допускается, если источник согласуется с `protocol` или `operator_review`.
2. `arousal_score`
   Допускается как ground truth только при `source = participant_self_report`.
3. `valence_score`
   Допускается как ground truth только при `source = participant_self_report`.

### Missing-label rules

1. Отсутствующий `segment-level valence_score` не делает сессию невалидной для `activity` и `arousal`.
2. Отсутствующий `segment-level arousal_score` исключает сегмент из arousal-track, но не из activity-track.
3. Отсутствующий primary `activity_label` исключает сегмент из activity-track.

## Split Strategy

### Primary split policy

Основной режим для внутренних paired-данных: `subject-wise`.

Обязательные правила:

1. один `subject` не должен одновременно присутствовать в train, validation и test;
2. все сессии одного субъекта попадают только в один split;
3. split manifest должен быть сохранен как версионируемый артефакт.

### Режим для малого числа субъектов

Если исследовательский корпус еще мал и фиксированный test set приведет к нестабильным цифрам, используется:

1. `leave-one-subject-out`, или
2. `GroupKFold` по `subject_id`

В этом режиме нужно репортить:

1. mean по фолдам;
2. std по фолдам;
3. subject-level distribution primary metric.

### Режим после роста корпуса

Когда субъектов становится достаточно для выделенного holdout-набора, используется:

1. фиксированный `test` по субъектам;
2. `train/validation` тоже делятся по субъектам;
3. test split после публикации первого стабильного manifest не меняется без новой версии evaluation protocol.

### Session-wise split

`session-wise` split можно считать только как вспомогательный debugging view.

Он не должен использоваться как headline-результат для research claims.

### Cross-dataset evaluation

Если позже добавляются внешние датасеты, нужно отдельно репортить:

1. `in-domain internal`
2. `cross-dataset transfer`
3. `pooled training`

Нельзя смешивать эти режимы в одну headline-таблицу без явного разделения.

## Таблица метрик

| Track | Target | Scope | Headline metric | Secondary metrics | Обязательность |
| --- | --- | --- | --- | --- | --- |
| Activity fine | `activity_label` | `segment` | `macro_f1` | `balanced_accuracy`, `weighted_f1`, `macro_recall`, confusion matrix, per-class support | mandatory |
| Activity coarse | `activity_group` | `segment` | none, derived sanity-check | `macro_f1`, `balanced_accuracy`, confusion matrix | mandatory alongside fine track |
| Arousal coarse | `arousal_score` -> `low/medium/high` | `segment` | `macro_f1` | `balanced_accuracy`, `macro_recall`, confusion matrix, per-class support | mandatory |
| Arousal ordinal | `arousal_score` in `1..9` | `segment` | none, ordered support track | `mae`, `spearman_rho`, `quadratic_weighted_kappa` | mandatory alongside coarse track |
| Valence coarse | `valence_score` -> `negative/neutral/positive` | `session` or `segment` | exploratory only | `macro_f1`, `balanced_accuracy` | exploratory |
| Valence ordinal | `valence_score` in `1..9` | `session` or `segment` | exploratory only | `mae`, `spearman_rho`, `quadratic_weighted_kappa` | exploratory |

Правило интерпретации таблицы:

1. macro-метрики считаются по классам с ненулевым support в test split;
2. support table обязана явно показывать отсутствующие классы, чтобы не скрывать loss of coverage.

## Baselines

Каждый headline-отчет обязан содержать минимум три baseline-level сравнения.

### 1. Trivial baseline

Для classification:

1. `majority_class`

Для ordinal track:

1. `global_median_predictor`

### 2. Protocol prior baseline

Только для controlled research-сессий разрешается добавить baseline:

1. `protocol_segment_label -> most_frequent activity_label`

Он нужен как нижняя граница полезности сенсорной модели на контролируемом протоколе.

### 3. Symmetric modality baselines

Для claim уровня `watch-only vs fusion` нужно сравнивать:

1. `watch-only baseline model`
2. `fusion baseline model`

По возможности они должны принадлежать к одной и той же model family и отличаться только составом входов.

## Как считать uncertainty

Для всех headline-метрик нужно репортить неопределенность.

Минимальный required набор:

1. mean и std по subject-wise folds, если используется cross-validation;
2. `95% confidence interval` для primary metric;
3. `95% confidence interval` для дельты:
   - `fusion - watch-only`
   - `personalized - global`

Предпочтительный способ:

1. paired bootstrap по субъектам, если это возможно;
2. иначе fold-wise paired deltas с явным указанием ограничения.

## Правила сравнения modality gain

Утверждение `fusion better than watch-only` допустимо только если выполняются все условия:

1. обе модели обучены и оценены на одном и том же `paired_eval_subset`;
2. split manifest идентичен;
3. pipeline preprocessing идентичен по всем шагам, кроме наличия `Polar`-признаков;
4. reported delta положительна по headline metric соответствующего track;
5. `95% confidence interval` для этой дельты не пересекает `0`.

Если CI пересекает `0`, результат должен быть обозначен как `inconclusive`, а не как отсутствие эффекта.

## Правила сравнения personalization gain

Утверждение `personalized better than global` допустимо только если:

1. target subject отсутствовал в global-train split;
2. calibration subset и evaluation subset этого subject не пересекаются;
3. personalization budget зафиксирован и одинаков для сравниваемых запусков;
4. reported delta положительна по headline metric или отрицательна по error metric;
5. `95% confidence interval` для дельты не пересекает `0`.

Дополнительно в personalization-отчете всегда нужно показывать:

1. долю субъектов, у которых метрика улучшилась;
2. worst-case degradation по субъектам;
3. чувствительность к размеру calibration budget.

## Когда valence переходит из exploratory в mandatory

`valence` остается exploratory, пока одновременно не выполнены все условия:

1. есть минимум `10` субъектов с пригодной `valence`-разметкой;
2. в evaluation corpus представлены все три coarse-класса;
3. у каждого coarse-класса есть минимум `10` session-level observations или минимум `20` segment-level observations;
4. split-ы не теряют class coverage в большинстве test folds.

До выполнения этих условий `valence` можно репортить, но нельзя использовать как обязательный research gate.

## Формат обязательного evaluation report

Каждый отчет по эксперименту должен содержать:

1. `experiment_id`
2. `dataset_version`
3. `label_set_version`
4. `preprocessing_version`
5. `split_manifest_version`
6. `model_family`
7. `input_modalities`
8. число `subjects`, `sessions`, `segments` по каждому split
9. список исключений:
   - missing labels;
   - low-confidence labels;
   - poor-quality streams;
   - incomplete overlap для fusion
10. таблицу headline и secondary metrics
11. confusion matrix для classification tracks
12. subject-level breakdown для primary metric
13. pairwise delta tables:
   - `fusion vs watch-only`
   - `personalized vs global`, если применимо
14. краткий failure analysis

## Минимальные research claims

После `A3` вводятся следующие правила интерпретации результата.

### `baseline_pass`

Можно заявлять, только если модель:

1. превосходит trivial baseline по headline metric;
2. оценена subject-wise;
3. имеет зафиксированный split manifest и report metadata.

### `fusion_gain_supported`

Можно заявлять, только если:

1. есть `baseline_pass` хотя бы для одной modality family;
2. `fusion` показывает положительную дельту относительно `watch-only`;
3. CI для дельты не пересекает `0`.

### `personalization_gain_supported`

Можно заявлять, только если:

1. global baseline уже определен;
2. personalization evaluated on held-out subjects;
3. mean delta благоприятна;
4. CI для дельты не пересекает `0`.

Если один из этих пунктов не выполнен, результат нужно обозначать как:

1. `preliminary`
2. `inconclusive`
3. `not comparable`

а не как подтвержденную гипотезу.

## Результат шага A3

После этого документа исследовательская фаза имеет:

1. зафиксированные headline и secondary metrics;
2. единые split rules без leakage по `subject`;
3. правила честного сравнения `watch-only`, `fusion` и personalized-вариантов;
4. порог перевода `valence` из exploratory в mandatory track;
5. обязательный формат evaluation report для следующих modeling-шагов.
