# ML Pipeline Automation (J2)

Скрипты для автоматизации dataset build, training и evaluation без ручной сборки аргументов.

## Переменные окружения

| Переменная | По умолчанию | Описание |
| --- | --- | --- |
| `ON_GO_ROOT` | `$(git rev-parse --show-toplevel)` | Корень репозитория |
| `DATA_EXTERNAL` | `$ROOT/data/external` | Корень внешних датасетов |
| `REGISTRY_PATH` | `$ROOT/data/external/registry/datasets.jsonl` | Путь к registry |
| `DATASET_ID` | `wesad` | Идентификатор датасета |
| `DATASET_VERSION` | `wesad-v1` | Версия датасета |
| `PREPROCESSING_VERSION` | `e2-v1` | Версия preprocessing |
| `RUN_KIND` | `watch-only-wesad` | Тип run modeling-baselines |
| `MIN_CONFIDENCE` | `0.7` | Минимальная confidence для сегментов |
| `BUILD_DATASET` | `1` | Собирать датасет перед training (для run-full-pipeline) |
| `NO_MLFLOW` | — | Любое значение отключает MLflow tracking |
| `SAVE_MODELS` | — | Сохранять модели (watch-only) |

## Команды

### 1. Сборка датасета

```bash
./scripts/ml/run-dataset-build.sh
```

Или с параметрами:

```bash
DATASET_ID=wesad DATASET_VERSION=wesad-v1 ./scripts/ml/run-dataset-build.sh
```

Поддерживаемые `DATASET_ID`: `wesad`, `emowear`, `grex`, `dapper`.

### 2. Training (и evaluation)

```bash
./scripts/ml/run-training.sh
```

Варианты:

```bash
RUN_KIND=watch-only-wesad ./scripts/ml/run-training.sh
RUN_KIND=fusion-wesad ./scripts/ml/run-training.sh
RUN_KIND=g3-1-wesad ./scripts/ml/run-training.sh
RUN_KIND=g3-2-multi-dataset ./scripts/ml/run-training.sh
RUN_KIND=h2-light-personalization-wesad CALIBRATION_SEGMENTS=2 ./scripts/ml/run-training.sh
SAVE_MODELS=1 RUN_KIND=watch-only-wesad ./scripts/ml/run-training.sh
```

### 3. Полный pipeline (build + train)

```bash
./scripts/ml/run-full-pipeline.sh
```

Отключить сборку датасета (только training):

```bash
BUILD_DATASET=0 ./scripts/ml/run-full-pipeline.sh
```

### 4. K5.4 Derived-State offline/replay evaluation

```bash
python3 scripts/ml/state_k5_4_derived_state_evaluation.py
```

Скрипт строит `K5.4` bundle в:

`data/external/wesad/artifacts/wesad/wesad-v1/k5-4-derived-state-evaluation/`

### 5. E2.20 Weekly canary monitoring dry-run

```bash
python3 scripts/ml/valence_e2_20_weekly_monitoring_dry_run.py
```

Скрипт строит `E2.20` bundle в:

`data/external/wesad/artifacts/wesad/wesad-v1/e2-20-weekly-monitoring-dry-run/`

### 6. E2.22 Weekly operations readiness review

```bash
python3 scripts/ml/valence_e2_22_weekly_readiness_review.py
```

Скрипт строит `E2.22` bundle в:

`data/external/wesad/artifacts/wesad/wesad-v1/e2-22-weekly-operations-readiness-review/`

### 7. E2.24 First steady-state weekly cycle audit

```bash
python3 scripts/ml/valence_e2_24_first_weekly_cycle_audit.py
```

Скрипт строит `E2.24` bundle в:

`data/external/wesad/artifacts/wesad/wesad-v1/e2-24-first-weekly-cycle-audit/`

### 8. E2.25 Execute factual first weekly cycle audit

```bash
python3 scripts/ml/valence_e2_25_execute_factual_weekly_cycle_audit.py
```

Скрипт строит `E2.25` bundle в:

`data/external/wesad/artifacts/wesad/wesad-v1/e2-25-factual-first-weekly-cycle-audit/`

### 9. K5.8 Build runtime bundle manifest

```bash
python3 scripts/ml/build_runtime_bundle_manifest.py \
  --output-dir /tmp/runtime-bundle \
  --bundle-id on-go-fusion-runtime-v1 \
  --activity-model /path/to/activity.joblib \
  --activity-features /path/to/activity_feature_names.json \
  --activity-classifier-kind ada_boost \
  --activity-feature-profile watch_motion_v1 \
  --arousal-model /path/to/arousal.joblib \
  --arousal-features /path/to/arousal_feature_names.json \
  --arousal-classifier-kind catboost \
  --arousal-feature-profile polar_watch_fusion_v1 \
  --valence-model /path/to/valence.joblib \
  --valence-features /path/to/valence_feature_names.json
```

Скрипт генерирует `model-bundle.manifest.json` в `--output-dir`.

### 10. Export live-aligned valence track into runtime bundle

```bash
python3 scripts/ml/export_live_valence_track.py
```

По умолчанию скрипт:

- берет `WESAD` unified labels + split manifest;
- использует текущий live-aligned feature space из `k5-9-fusion-runtime-v4-live-feature-aligned/arousal_feature_names.json`;
- обучает `ridge_classifier` для `valence_coarse`;
- сохраняет в активный runtime bundle:
  - `valence_watch_acc_bvp_ridge_classifier.joblib`,
  - `valence_feature_names.json`,
  - `valence_watch_acc_bvp_ridge_classifier.report.json`.

## Версионирование

- `dataset_version`: версия датасета (напр. `wesad-v1`); фиксируется в registry и artifact paths
- `preprocessing_version`: версия preprocessing pipeline (напр. `e2-v1`); логируется в params/modeling runs

Артефакты сохраняются в:

```
$DATA_EXTERNAL/$DATASET_ID/artifacts/$DATASET_ID/$DATASET_VERSION/
  unified/segment-labels.jsonl
  manifest/split-manifest.json
  watch-only-baseline/...
  fusion-baseline/...
  ...
```
