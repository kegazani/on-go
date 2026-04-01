# G1: Baseline watch-only model

## Цель шага

Собрать первый воспроизводимый `watch-only baseline` pipeline на unified dataset artifacts,
чтобы закрыть минимальный modeling loop после `E2/F2`.

## Что реализовано

1. Добавлен новый модуль `services/modeling-baselines`.
2. Реализован CLI `on-go-modeling-baselines` для запуска baseline на `WESAD`.
3. Реализована загрузка segment-level unified labels и subject-wise split manifest.
4. Реализовано построение `watch-only` признаков из `WESAD` wrist streams (`ACC/BVP/EDA/TEMP`) по source boundaries сегмента.
5. Реализована baseline-модель `nearest centroid`:
   - `activity_label` classification;
   - `arousal_coarse` classification (`low/medium/high`).
6. Добавлены ordinal-метрики для `arousal_score`:
   - `mae`;
   - `spearman_rho`;
   - `quadratic_weighted_kappa`.
7. Добавлены trivial baselines:
   - `majority_class` для classification tracks;
   - `global_median_predictor` для ordinal arousal.
8. Добавлен bootstrap `95% CI` по субъектам для primary metric (`macro_f1`) и дельты против majority baseline.
9. Формируются артефакты запуска:
   - `evaluation-report.json`;
   - `predictions-test.csv`.

## Пример запуска

```bash
cd /Users/kgz/Desktop/p/on-go/services/modeling-baselines
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

on-go-modeling-baselines \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7
```

## Формат output

```text
data/external/wesad/artifacts/wesad/wesad-v1/watch-only-baseline/
  evaluation-report.json
  predictions-test.csv
```

## Ограничения текущего инкремента

1. `G1` реализован на external `WESAD`, так как internal unified modeling dataset еще не зарегистрирован в dataset-registry.
2. `fusion` baseline и cross-modality comparison не входят в этот шаг и выполняются в `G2/G3`.
3. Используется минимальная classical ML family для reproducible baseline; расширение до sequence models отложено.
