# G2 - Baseline fusion model

Шаг `G2` расширяет baseline-моделирование до comparative `fusion` пакета на `WESAD`.

## Что реализовано

1. `services/modeling-baselines` расширен с `G1` до `G2`.
2. Добавлен multimodal feature extraction по segment boundaries:
   - wrist: `ACC/BVP/EDA/TEMP`;
   - chest: `ACC/ECG/EDA/EMG/Resp/Temp`.
3. Добавлены четыре сравниваемых variants:
   - `watch_only_centroid`;
   - `chest_only_centroid`;
   - `fusion_centroid`;
   - `fusion_gaussian_nb`.
4. Для `G2` формируются research-grade artifacts:
   - `evaluation-report.json`;
   - `predictions-test.csv`;
   - `per-subject-metrics.csv`;
   - `model-comparison.csv`;
   - `research-report.md`;
   - `plots/`.
5. В comparison layer добавлены:
   - `delta_vs_watch_only`;
   - bootstrap `95% CI` для парной дельты;
   - `claim_status` (`supported/inconclusive_* / regression`).

## Реальный run на `WESAD`

Реальный эксперимент:

1. `experiment_id = g2-fusion-wesad-20260322T182732Z`
2. dataset: `wesad:wesad-v1`
3. split: `subject-wise`
4. usable segments (`confidence >= 0.7`): `75`

## Главные результаты

### Activity `macro_f1`

1. `watch_only_centroid = 0.719048`
2. `chest_only_centroid = 0.722222`
3. `fusion_centroid = 0.637037`
4. `fusion_gaussian_nb = 0.885714`

`fusion_gaussian_nb` дал лучшую `activity`-метрику, но pairwise delta CI против `watch_only` = `[0.0, 0.511111]`, поэтому claim status пока `inconclusive_positive`.

### Arousal coarse `macro_f1`

1. `watch_only_centroid = 0.655556`
2. `chest_only_centroid = 0.497280`
3. `fusion_centroid = 0.587179`
4. `fusion_gaussian_nb = 0.932773`

Для `arousal_coarse` variant `fusion_gaussian_nb` дал `delta_vs_watch_only = 0.277217` c pairwise CI `[0.177778, 0.572222]`, поэтому claim status `supported`.

### Arousal ordinal

Лучший ordinal-result также у `fusion_gaussian_nb`:

1. `mae = 0.266667`
2. `spearman_rho = 0.926696`
3. `quadratic_weighted_kappa = 0.916667`

## Артефакты

Результаты шага сохранены в:

`data/external/wesad/artifacts/wesad/wesad-v1/fusion-baseline/`

Ключевые файлы:

1. `evaluation-report.json`
2. `model-comparison.csv`
3. `research-report.md`
4. `plots/activity-macro-f1.png`
5. `plots/arousal-macro-f1.png`
6. `plots/activity-confusion-matrix.png`
7. `plots/arousal-confusion-matrix.png`
8. `plots/subject-activity-macro-f1.png`
9. `plots/subject-arousal-macro-f1.png`

## Ограничения

1. Holdout test состоит только из `3` subjects, поэтому CI остаются широкими.
2. `sequence-aware` families еще не добавлены.
3. `feature-importance.csv` не формируется для текущих baseline families.

## Вывод

`G2` дал первый воспроизводимый `fusion` comparison package и показал, что на `WESAD` простой `fusion_centroid` не превосходит `watch-only`, но `fusion_gaussian_nb` уже дает сильный прирост, особенно на `arousal` track.
