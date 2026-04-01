# G3 - Comparative evaluation report

Шаг `G3` агрегирует результаты `G1` и `G2` в единый comparative package для research review и презентации.

## Что реализовано

1. В `services/modeling-baselines` добавлен `run-kind = g3-wesad`.
2. Новый runner читает готовые artifacts:
   - `watch-only-baseline/evaluation-report.json` (`G1`);
   - `fusion-baseline/evaluation-report.json` и `per-subject-metrics.csv` (`G2`).
3. Формируется единый comparison bundle:
   - `comparison/evaluation-report.json`;
   - `comparison/model-comparison.csv`;
   - `comparison/per-subject-metrics.csv`;
   - `comparison/comparison-report.md`;
   - `comparison/research-report.md`;
   - `comparison/plots/*`.
4. В `model-comparison.csv` агрегируются минимум `5` runs:
   - `g1_watch_only_centroid`;
   - `watch_only_centroid`;
   - `chest_only_centroid`;
   - `fusion_centroid`;
   - `fusion_gaussian_nb`.
5. Для каждого track сохраняются:
   - `delta_vs_watch_only`;
   - `delta_vs_watch_only_ci95`;
   - `claim_status`.

## Реальный run

Реальный прогон:

1. `experiment_id = g3-comparison-wesad-20260322T183444Z`
2. source runs:
   - `G1`: `g1-watch-only-wesad-20260322T180954Z`
   - `G2`: `g2-fusion-wesad-20260322T182732Z`

## Итоговые результаты

### Activity (macro_f1)

Лидер:

1. `fusion_gaussian_nb = 0.885714`
2. `delta_vs_watch_only = +0.166666`
3. `delta_ci95 = [0.0, 0.511111]`
4. `claim_status = inconclusive_positive`

### Arousal coarse (macro_f1)

Лидер:

1. `fusion_gaussian_nb = 0.932773`
2. `delta_vs_watch_only = +0.277217`
3. `delta_ci95 = [0.177778, 0.572222]`
4. `claim_status = supported`

### Интерпретация

1. На текущем корпусе есть поддержанный claim по `arousal_coarse` в пользу fusion.
2. По `activity` эффект positive, но CI касается `0`, поэтому claim пока не окончательный.

## Графики

Сохранены:

1. `g3-activity-macro-f1.png`
2. `g3-arousal-macro-f1.png`
3. `g3-activity-delta-vs-watch.png`
4. `g3-arousal-delta-vs-watch.png`
5. `g3-subject-activity-macro-f1.png`
6. `g3-subject-arousal-macro-f1.png`

## Вывод шага

`G3` завершает baseline comparative контур: теперь есть единый machine-readable и presentation-ready пакет по `G1+G2` с зафиксированными claims и ограничениями.
