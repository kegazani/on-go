# G3.1 - Extended model zoo benchmarking (`WESAD`)

## Статус

- Step ID: `G3.1`
- Status: `completed`
- Date: `2026-03-22`
- Run ID: `g3-1-model-zoo-wesad-20260322T190114Z`

## Цель

Расширить baseline modeling до широкого `model zoo` и получить presentation-ready comparative пакет перед personalization-фазой.

## Что реализовано

1. Добавлен новый run-kind в `modeling-baselines`: `g3-1-wesad`.
2. Добавлена широкая линейка классификаторов:
   - `centroid`, `gaussian_nb`;
   - `logistic_regression`, `ridge_classifier`, `lda`, `qda`;
   - `linear_svm`, `rbf_svm`, `knn`;
   - `decision_tree`, `random_forest`, `extra_trees`, `bagging_tree`;
   - `ada_boost`, `gradient_boosting`, `hist_gradient_boosting`;
   - `mlp`, `sgd_linear`;
   - `xgboost`, `lightgbm`, `catboost`.
3. Запущены modality variants:
   - `watch_only`;
   - `chest_only` (reference);
   - `fusion`.
4. Добавлены full artifacts и plotting для research review.

## Итоги запуска

- Всего примеров: `75`
- Успешных model variants: `41`
- Failed variants: `0`

Победители:

1. `activity`: `watch_only_ada_boost`, `macro_f1=1.0`, claim=`supported`.
2. `arousal_coarse`: `fusion_catboost`, `macro_f1=1.0`, claim=`supported`.

Изменение относительно `G3` best:

1. `activity`: `+0.114286`.
2. `arousal_coarse`: `+0.067227`.

## Артефакты

Root:

`/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/model-zoo-benchmark/`

Содержимое:

1. `evaluation-report.json`
2. `predictions-test.csv`
3. `per-subject-metrics.csv`
4. `model-comparison.csv`
5. `feature-importance.csv`
6. `failed-variants.csv`
7. `research-report.md`
8. `plots/`

## Проверки

1. `python3 -m compileall -q src tests`
2. `pytest -q` (`9 passed`)
3. Реальный run `on-go-modeling-baselines --run-kind g3-1-wesad`

## Ограничения

1. Данные все еще ограничены `WESAD` holdout (малый `test` по субъектам), поэтому CI на части сравнений остается широким.
2. До `G3.2` выводы остаются в рамках single-dataset evidence.

## Следующий шаг

`G3.2 - Multi-dataset harmonization and benchmarking`
