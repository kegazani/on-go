# modeling-baselines

Сервисный модуль шагов `G1-G3`, `H2`, `H3` и `H5` для baseline/personalization-моделей и comparative reporting на unified dataset artifacts.

Текущий инкремент покрывает:

1. `AUDIT`: safety-аудит признаков/split перед любым modeling run;
1. `G1`: `watch-only` baseline на `WESAD`;
2. `G2`: сравнительный `fusion` baseline пакет на `WESAD` c несколькими model variants;
3. `G3`: агрегированный comparative report (`G1 + G2`) с единой таблицей claims и presentation-ready plots;
4. `G3.1-LOSO`: extended model-zoo benchmark в режиме leave-one-subject-out;
5. `G3.2-Strategy`: multi-dataset training protocol для разделения `real / protocol-mapped / proxy` arousal labels;
6. `G3.2-Protocol`: phase execution gate c readiness-checks по multi-dataset training protocol;
7. `G3.2-Self-Training-Scaffold`: исполняемый фазовый scaffold (`Phase 0-8`) с metrics contract и runbook;
8. `G3.2-Self-Training-Execution`: реальный проход `Phase 0-8` с teacher selection, pseudo-label generation и freeze decision;
4. `H2`: `light personalization` сравнение `global vs personalized` на subject-level calibration split;
5. `H3`: `full personalization` сравнение `global vs light vs full` со subject-specific refit.
6. `H5`: `weak-label vs label-free personalization` сравнение `global vs weak-label vs label-free`.
9. `M7.3`: `polar-first` ablation contract с anti-collapse gate и report-template.
10. `M7.4`: runtime candidate gate с pass/fail verdict и remediation actions.
11. `M7.4.1`: remediation loop до claim-safe runtime promotion.
12. `M7.5`: runtime bundle export с manifest/feature-names contract и bundle smoke-check.
3. classification targets:
   - `activity_label`;
   - `arousal_coarse` (`low/medium/high`);
4. ordinal `arousal` support metrics:
   - `mae`;
   - `spearman_rho`;
   - `quadratic_weighted_kappa`;
5. research-grade artifacts:
   - `evaluation-report.json`;
   - `predictions-test.csv`;
   - `per-subject-metrics.csv`;
   - `model-comparison.csv`;
   - `research-report.md`;
   - `plots/`.

## Запуск safety audit (обязательный pre-run gate)

```bash
on-go-modeling-baselines \
  --run-kind audit-wesad \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7
```

Outputs:

```text
<output-dir>/wesad/wesad-v1/safety-audit/
  evaluation-report.json
  selected-features.csv
  split-audit.json
  leakage-audit.json
```

## Установка

Из `services/modeling-baselines`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Запуск G1 baseline

```bash
on-go-modeling-baselines \
  --run-kind watch-only-wesad \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7
```

Outputs:

```text
<output-dir>/wesad/wesad-v1/watch-only-baseline/
  evaluation-report.json
  predictions-test.csv
```

## Запуск G2 fusion comparison

```bash
on-go-modeling-baselines \
  --run-kind fusion-wesad \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7
```

Outputs:

```text
<output-dir>/wesad/wesad-v1/fusion-baseline/
  evaluation-report.json
  predictions-test.csv
  per-subject-metrics.csv
  model-comparison.csv
  research-report.md
  plots/
```

## Запуск E2.3 Polar/Watch benchmark (arousal + valence)

```bash
on-go-modeling-baselines \
  --run-kind e2-3-wesad-polar-watch-benchmark \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7
```

Outputs:

```text
<output-dir>/wesad/wesad-v1/e2-3-polar-watch-benchmark/
  evaluation-report.json
  predictions-test.csv
  per-subject-metrics.csv
  model-comparison.csv
  research-report.md
  plots/
```

## Запуск G3 comparative report

```bash
on-go-modeling-baselines \
  --run-kind g3-wesad \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7
```

Outputs:

```text
<output-dir>/wesad/wesad-v1/comparison/
  evaluation-report.json
  model-comparison.csv
  per-subject-metrics.csv
  comparison-report.md
  research-report.md
  plots/
```

## Запуск G3.1 LOSO benchmark

```bash
on-go-modeling-baselines \
  --run-kind g3-1-wesad-loso \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7
```

Outputs:

```text
<output-dir>/wesad/wesad-v1/model-zoo-benchmark-loso/
  evaluation-report.json
  fold-metrics.csv
  model-comparison.csv
  failed-variants.csv
  research-report.md
  plots/
```

## Запуск G3.2 multi-dataset training strategy

```bash
on-go-modeling-baselines \
  --run-kind g3-2-multi-dataset-strategy \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external \
  --registry-path /Users/kgz/Desktop/p/on-go/services/dataset-registry/registry/datasets.jsonl \
  --min-confidence 0.7
```

Outputs:

```text
<output-dir>/multi-dataset/strategy/
  training-strategy-report.json
  dataset-strategy.csv
  training-phases.csv
  training-protocol.md
```

## Запуск G3.2 protocol execution gate

```bash
on-go-modeling-baselines \
  --run-kind g3-2-multi-dataset-protocol \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external \
  --registry-path /Users/kgz/Desktop/p/on-go/services/dataset-registry/registry/datasets.jsonl \
  --min-confidence 0.7
```

Outputs:

```text
<output-dir>/multi-dataset/protocol-execution/
  protocol-execution-report.json
  readiness-checks.csv
  phase-execution.csv
  protocol-execution.md
```

## Запуск G3.2 self-training scaffold

```bash
on-go-modeling-baselines \
  --run-kind g3-2-self-training-scaffold \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external \
  --registry-path /Users/kgz/Desktop/p/on-go/services/dataset-registry/registry/datasets.jsonl \
  --min-confidence 0.7
```

Outputs:

```text
<output-dir>/multi-dataset/self-training-scaffold/
  self-training-scaffold-report.json
  self-training-phases.csv
  metrics-contract.csv
  self-training-runbook.md
```

## Запуск G3.2 self-training execution

```bash
on-go-modeling-baselines \
  --run-kind g3-2-self-training-execution \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external \
  --registry-path /Users/kgz/Desktop/p/on-go/services/dataset-registry/registry/datasets.jsonl \
  --min-confidence 0.7
```

Outputs:

```text
<output-dir>/multi-dataset/self-training-execution/
  self-training-execution-report.json
  phase-0-freeze-gates.json
  phase-1-proxy-pretraining.json
  phase-2-real-label-finetune.json
  phase-3-protocol-transfer.json
  phase-4-teacher-selection.json
  phase-5-pseudo-label-generation.json
  phase-5-pseudo-labels.csv
  phase-6-self-training-refit.json
  phase-7-cross-dataset-evaluation.json
  phase-8-model-freeze-decision.json
  phase-execution.csv
  model-comparison.csv
  research-report.md
```

## Варианты моделей в G2

1. `watch_only_centroid`
2. `chest_only_centroid`
3. `fusion_centroid`
4. `fusion_gaussian_nb`

## Запуск H2 light personalization

```bash
on-go-modeling-baselines \
  --run-kind h2-light-personalization-wesad \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7 \
  --calibration-segments 2
```

Outputs:

```text
<output-dir>/wesad/wesad-v1/light-personalization/
  evaluation-report.json
  predictions-test.csv
  per-subject-metrics.csv
  model-comparison.csv
  failed-variants.csv
  research-report.md
  plots/
```

## Запуск H3 full personalization

```bash
on-go-modeling-baselines \
  --run-kind h3-full-personalization-wesad \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7 \
  --calibration-segments 2 \
  --adaptation-weight 5
```

Outputs:

```text
<output-dir>/wesad/wesad-v1/full-personalization/
  evaluation-report.json
  predictions-test.csv
  per-subject-metrics.csv
  model-comparison.csv
  failed-variants.csv
  research-report.md
  plots/
```

## Запуск H5 weak-label / label-free personalization

```bash
on-go-modeling-baselines \
  --run-kind h5-weak-label-label-free-wesad \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7 \
  --calibration-segments 2 \
  --adaptation-weight 5
```

Outputs:

```text
<output-dir>/wesad/wesad-v1/weak-label-label-free-personalization/
  evaluation-report.json
  predictions-test.csv
  per-subject-metrics.csv
  model-comparison.csv
  failed-variants.csv
  research-report.md
  plots/
```

## Запуск M7.3 Polar-first training dataset build

```bash
on-go-modeling-baselines \
  --run-kind m7-3-polar-first-training-dataset-build \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7
```

Expected ablation matrix variants:

1. `polar_only`
2. `watch_motion_only`
3. `polar+watch_motion`

Outputs:

```text
<output-dir>/wesad/wesad-v1/m7-3-polar-first-training-dataset-build/
  evaluation-report.json
  predictions-test.csv
  per-subject-metrics.csv
  model-comparison.csv
  research-report.md
  plots/
```

Anti-collapse interpretation for `evaluation-report.json`:

1. `anti_collapse.predicted_class_count` should be greater than `1` on the stress-set used for gate review.
2. `anti_collapse.dominant_class_share` should stay well below `1.0`; if it reaches `1.0`, the run is effectively collapsed.
3. If the predictions collapse to a single class, the candidate is not promotable even if headline metrics look acceptable.
4. The research report should call this out explicitly in the failure-analysis and interpretation-limits sections.

Minimal `research-report.md` skeleton for M7.3:

1. `Experiment summary`
2. `Data provenance`
3. `Label definition and usage`
4. `Preprocessing and features`
5. `Split and evaluation protocol`
6. `Model definition`
7. `Results`
8. `Failure analysis`
9. `Research conclusion`
10. `Interpretation limits`

## Запуск M7.4 runtime candidate gate

```bash
on-go-modeling-baselines \
  --run-kind m7-4-runtime-candidate-gate \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7 \
  --no-mlflow
```

Outputs:

```text
<output-dir>/wesad/wesad-v1/m7-4-runtime-candidate-gate/
  runtime-candidate-verdict.json
  runtime-candidate-report.md
```

Interpretation:

1. `pass` means all three track winners are present, `claim_status == supported`, `anti_collapse_status == ok`, and the run can advance to `P5 Runtime Bundle Export`.
2. `pass` also requires `anti_collapse_summary.passed == true`, `track_failures == []`, `global_issues == []`, `flagged_rows == []`, and `remediation_actions == []`.
3. `fail` means the candidate must stay in `P4 remediation loop`; do not export a runtime bundle yet.
4. Typical fail reasons are `missing_winner`, `claim_not_supported`, `anti_collapse_not_ok`, `anti_collapse_summary_failed`, and `flagged_rows_present`.

## M7.4.1 remediation loop

`M7.4.1` is the rerun loop after a failed `M7.4` verdict.

Loop:

1. fix the flagged `polar_only/activity` anti-collapse issue;
2. improve `arousal_coarse` until the winner becomes `supported`;
3. rerun `M7.3` to regenerate `evaluation-report.json`;
4. rerun `M7.4` on the fresh `M7.3` report;
5. repeat until the gate turns `pass`.

Completion criteria:

1. `gate_verdict == pass`;
2. `gate_passed == true`;
3. `track_failures == []`;
4. `global_issues == []`;
5. `anti_collapse_summary.flagged_rows == []`;
6. `remediation_actions == []`.

## Запуск M7.5 runtime bundle export

```bash
on-go-modeling-baselines \
  --run-kind m7-5-runtime-bundle-export \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7 \
  --no-mlflow
```

Expected outputs:

```text
<output-dir>/wesad/wesad-v1/m7-5-runtime-bundle-export/
  model-bundle.manifest.json
  runtime-bundle-export-report.json
  runtime-bundle-smoke-summary.json
  activity.joblib
  arousal_coarse.joblib
  valence_coarse.joblib
  activity_*.joblib
  arousal_coarse_*.joblib
  valence_coarse_*.joblib
  activity_feature_names.json
  arousal_coarse_feature_names.json
  valence_coarse_feature_names.json
```

Interpretation:

1. `gate_passed` must be `true`; otherwise export fails fast and no bundle is written.
2. `model-bundle.manifest.json` is the loader contract for the exported runtime bundle.
3. `activity`, `arousal_coarse`, and `valence_coarse` must all be present in the exported bundle.
4. `runtime-bundle-smoke-summary.json` reloads the saved models and validates the held-out test split.
5. Earlier contract drafts referred to `bundle/model-bundle.manifest.json` and `runtime-bundle-export-report.md`; the current export keeps the bundle at the run root and writes `runtime-bundle-smoke-summary.json` instead.

## Запуск M7.9 polar-expanded fusion benchmark

```bash
on-go-modeling-baselines \
  --run-kind m7-9-polar-expanded-fusion-benchmark \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7 \
  --no-mlflow
```

Outputs:

```text
<output-dir>/wesad/wesad-v1/m7-9-polar-expanded-fusion-benchmark/
  evaluation-report.json
  predictions-test.csv
  per-subject-metrics.csv
  model-comparison.csv
  research-report.md
  plots/
```

## Запуск M7.9 runtime bundle export

```bash
on-go-modeling-baselines \
  --run-kind m7-9-runtime-bundle-export \
  --segment-labels /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl \
  --split-manifest /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json \
  --wesad-raw-root /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1 \
  --min-confidence 0.7 \
  --no-mlflow
```

Outputs:

```text
<output-dir>/wesad/wesad-v1/m7-9-runtime-bundle-export/
  model-bundle.manifest.json
  runtime-bundle-export-report.json
  runtime-bundle-smoke-summary.json
  activity_*.joblib
  arousal_coarse_*.joblib
  valence_coarse_*.joblib
  activity_feature_names.json
  arousal_coarse_feature_names.json
  valence_coarse_feature_names.json
```

Manifest policy:

1. `required_live_streams` includes `watch_accelerometer`, `polar_hr`, `polar_rr`.
2. `polar_rr` is policy-required for `M7.9` runtime bundle.

## Experiment tracking и model registry (J1)

При запуске включен MLflow experiment tracking. Каждый run логирует:
- params: `run_kind`, `dataset_id`, `dataset_version`, `preprocessing_version`, `min_confidence`, paths;
- metrics: метрики из `evaluation-report.json` (tracks);
- artifacts: весь output root (reports, plots, predictions).

Флаги:
- `--no-mlflow` — отключить tracking;
- `--mlflow-tracking-uri <uri>` — задать tracking URI (иначе `MLFLOW_TRACKING_URI` или `./mlruns`);
- `--save-models` — сохранить обученные модели в `output_dir/.../models/` (watch-only run); файлы попадают в артефакты run при включенном tracking.

## Ограничения текущего инкремента

1. Внешний unified corpus пока ограничен `WESAD`.
2. Sequence-aware families в `G2` еще не добавлены; это осознанно переносится на следующий modeling-этап после baseline comparative package.
3. `feature-importance.csv` не формируется для centroid / Gaussian NB baselines.
