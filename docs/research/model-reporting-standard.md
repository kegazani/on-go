# Standard Research Reporting and Model Comparison Policy

## Цель

Этот документ фиксирует обязательный стандарт для всех шагов, где строятся, сравниваются или анализируются модели.

Его задача:

1. не допускать "быстрых" экспериментов без полноценной traceability;
2. заставлять каждый modeling-шаг оставлять после себя материал, пригодный для research review и презентации;
3. фиксировать, что сравниваются не одна-две случайные модели, а набор разумных candidate approaches;
4. делать сравнение моделей воспроизводимым, визуально понятным и пригодным для последующего decision gate.

## Область действия

Этот стандарт обязателен для шагов:

1. `G1-G3`
2. `H1-H3`
3. `I1`
4. любых дополнительных research-экспериментов, ablations и model sweeps

## Базовое правило

Любой modeling- или personalization-шаг считается незавершенным, если после него нет:

1. подробного текстового отчета;
2. machine-readable evaluation artifacts;
3. визуальных сравнений;
4. явного описания labels, preprocessing, split rules и данных;
5. сравнения нескольких моделей или нескольких экспериментальных подходов, если шаг не ограничен одним очень узким техническим подэтапом.

## Что обязательно фиксировать в каждом experiment report

Каждый отчет обязан содержать следующие разделы.

### 1. Experiment summary

1. `experiment_id`
2. дата запуска
3. цель эксперимента
4. исследовательская гипотеза
5. статус результата:
   - `baseline`
   - `improved`
   - `inconclusive`
   - `regression`

### 2. Data provenance

1. какие датасеты использовались;
2. версии датасетов;
3. какие subsets использовались;
4. число `subjects`, `sessions`, `segments`, `windows`;
5. что было исключено и почему.

### 3. Label definition and usage

1. какие target labels использовались;
2. canonical label version;
3. mapping source labels -> canonical labels;
4. какие labels были missing;
5. какие labels были отброшены из-за confidence/quality rules;
6. какие coarse/ordinal представления использовались.

### 4. Preprocessing and features

1. preprocessing version;
2. какие stream-источники вошли в experiment;
3. как была сделана синхронизация;
4. какие quality filters применялись;
5. какое окно использовалось;
6. какие feature families использовались;
7. какие derived features были исключены или добавлены относительно предыдущих запусков.

### 5. Split and evaluation protocol

1. split policy;
2. split manifest version;
3. train/validation/test composition;
4. headline tracks и secondary tracks;
5. aggregation rule `window -> segment`, если он есть;
6. leakage guards.

### 6. Model definition

1. model family;
2. входные модальности;
3. target definition;
4. hyperparameters;
5. training procedure;
6. decision rule / threshold / aggregation rule;
7. чем эта модель отличается от остальных кандидатов.

### 7. Results

1. headline metrics;
2. secondary metrics;
3. uncertainty estimates;
4. per-class support;
5. subject-level breakdown;
6. delta vs baselines;
7. delta vs previous best run.

### 8. Failure analysis

1. на каких классах модель ошибается;
2. на каких subject-группах или сессиях ухудшается результат;
3. какие ограничения данных или labels могли повлиять на результат;
4. какие артефакты качества могли исказить вывод.

### 9. Research conclusion

1. что эксперимент показал;
2. можно ли использовать результат в claim;
3. что рекомендовано делать следующим шагом.

## Обязательные визуальные артефакты

Для каждого сравнительного modeling-шага нужно сохранять графики, пригодные для research review и презентации.

Минимально обязательный набор:

1. bar chart сравнения headline metrics по всем сравниваемым моделям;
2. bar chart или point plot для delta vs baseline;
3. confusion matrix для каждого classification target;
4. per-subject metric distribution:
   - boxplot, violin plot или strip plot;
5. calibration/ordinal scatter plot, если track ordinal;
6. таблица или heatmap feature/modality ablation, если делались ablations;
7. learning curve или data-scaling curve, если менялся объем данных;
8. comparison table с train/validation/test metrics и CI.

Если шаг включает personalization, дополнительно обязательны:

1. график gain distribution по субъектам;
2. график зависимости качества от размера calibration budget;
3. график worst-case degradation.

## Политика сравнения большого числа моделей

Исследовательская программа не должна ограничиваться одной моделью на шаг.

Для каждого major modeling step нужно, где это практически возможно, сравнивать несколько candidate approaches:

1. trivial baselines;
2. simplest feature-based classical ML baseline;
3. как минимум еще одну альтернативную classical ML family;
4. как минимум одну sequence-aware или более expressive family, когда данных уже достаточно;
5. modality ablations;
6. feature ablations;
7. при необходимости calibration/personalization variants.

Минимальное ожидание по количеству сравниваемых постановок:

1. на раннем baseline-этапе: не меньше `3` осмысленных model variants плюс trivial baseline;
2. на сравнительном этапе `G3`: не меньше `5` runs в общей сравнительной таблице;
3. на personalization-этапе: global, light personalization и stronger personalization variants.

Если какой-то класс моделей не был протестирован, в отчете это должно быть явно объяснено:

1. недостаточно данных;
2. неподходящая модальность;
3. техническое ограничение текущего шага;
4. перенос на следующий шаг.

## Обязательные machine-readable артефакты

Каждый completed modeling step должен по возможности оставлять:

1. `evaluation-report.json`
2. `predictions-test.csv`
3. `per-subject-metrics.csv`
4. `model-comparison.csv`
5. `feature-importance.csv` или аналогичный artifact, если применимо;
6. каталог `plots/` с экспортированными графиками;
7. markdown- или md-like `research-report.md`

Если какой-то artifact неприменим, это должно быть явно отмечено в `research-report.md`.

## Каноническая структура research report

Рекомендуемая структура файла:

```text
artifacts/<dataset>/<dataset-version>/<experiment-family>/<run-id>/
  evaluation-report.json
  predictions-test.csv
  per-subject-metrics.csv
  model-comparison.csv
  plots/
  research-report.md
```

Если шаг агрегирует несколько run-ов, рядом должен существовать сводный каталог:

```text
artifacts/<dataset>/<dataset-version>/comparison/
  comparison-report.md
  model-comparison.csv
  plots/
```

## Обязательные вопросы, на которые должен отвечать отчет

1. Какие именно labels использовались?
2. Как labels были получены и отфильтрованы?
3. Какие данные вошли в train/validation/test?
4. Какие preprocessing- и feature-шаги использовались?
5. Какие модели были сравнены?
6. Какая модель лучшая по headline metric?
7. Насколько она стабильна по субъектам?
8. Есть ли прирост по сравнению с более простыми подходами?
9. Есть ли деградация на отдельных subject-ах или label-классах?
10. Достаточно ли результата для презентации и research claim?

## Правило пригодности для презентации

Материал считается пригодным для презентации только если:

1. есть минимум один текстовый summary для человека;
2. есть таблица сравнения нескольких моделей;
3. есть минимум три графика сравнения;
4. явно показаны labels, данные, preprocessing и метрики;
5. вывод отделен от raw numbers и сформулирован как decision-oriented summary.

## Правило исполнения

Все будущие modeling, personalization и research-report шаги должны исполняться с учетом этого стандарта по умолчанию, без отдельного напоминания пользователя.
