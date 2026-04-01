# M7.3 Polar-first Ablation Contract

## Status

- Step ID: `M7.3`
- Status: `spec`
- Date: `2026-03-29`
- Scope: Polar-first run-kind, ablation matrix, anti-collapse gate, and reporting template.

## Goal

Lock the expected behavior for the Polar-first modeling slice:

1. compare `polar_only`, `watch_motion_only`, and `polar+watch_motion`;
2. keep `polar_only` as the baseline reference for the ablation matrix;
3. expose an anti-collapse signal in evaluation artifacts;
4. keep the research report compatible with `docs/research/model-reporting-standard.md`.

## Current execution alias

The repository already has an executable path that matches the current artifact shape:

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

This doc treats that run as the current executable alias for the Polar-first contract. If a dedicated M7.3 alias lands later, it should preserve the same output shape.

## Expected artifacts

```text
<output-dir>/wesad/wesad-v1/e2-3-polar-watch-benchmark/
  evaluation-report.json
  predictions-test.csv
  per-subject-metrics.csv
  model-comparison.csv
  research-report.md
  plots/
```

`feature-importance.csv` is optional and may be absent for baselines that do not expose stable feature importance.

## Ablation matrix

The report should make the three variants explicit:

1. `polar_only`
2. `watch_motion_only`
3. `polar+watch_motion`

Recommended comparison layout:

| Variant | Baseline | Track | Metric | Delta | Claim |
| --- | --- | --- | --- | --- | --- |
| `polar_only` | `polar_only` | `activity` / `arousal_coarse` / `valence_coarse` | `macro_f1` | `0` | `baseline` |
| `watch_motion_only` | `polar_only` | same | `macro_f1` | `delta_vs_polar_only` | `supported` / `inconclusive` / `regression` |
| `polar+watch_motion` | `polar_only` | same | `macro_f1` | `delta_vs_polar_only` | `supported` / `inconclusive` / `regression` |

## Anti-collapse signal

`evaluation-report.json` should include an explicit anti-collapse block, for example:

```json
{
  "anti_collapse": {
    "stress_set_name": "validation_stress",
    "predicted_class_count": 3,
    "dominant_class": "neutral",
    "dominant_class_share": 0.52,
    "is_collapsed": false
  }
}
```

Interpretation:

1. `predicted_class_count > 1` means the model is not degenerate on the stress-set.
2. `dominant_class_share == 1.0` means the model has collapsed to a single class.
3. A collapsed model is not promotable, even if headline metrics look acceptable.
4. The report should call out collapse risk explicitly in `Failure analysis` and `Interpretation limits`.

## Minimal `research-report.md` skeleton

The report should keep the standard research sections and add an explicit limits block when needed:

```text
# Polar-first Research Report

## Experiment summary
## Data provenance
## Label definition and usage
## Preprocessing and features
## Split and evaluation protocol
## Model definition
## Results
## Failure analysis
## Research conclusion
## Interpretation limits
```

Section content should stay compact:

1. `Experiment summary`: goal, hypothesis, status, run id.
2. `Data provenance`: dataset, version, subjects/sessions/segments, exclusions.
3. `Label definition and usage`: canonical labels, filters, coarse/ordinal mapping.
4. `Preprocessing and features`: stream sources, feature families, quality gates.
5. `Split and evaluation protocol`: split policy, leakage guards, evaluation tracks.
6. `Model definition`: model family, inputs, hyperparameters, comparison variants.
7. `Results`: headline metrics, per-subject spread, delta vs baseline, uncertainty.
8. `Failure analysis`: where the model collapses or underperforms.
9. `Research conclusion`: whether the result is claim-safe.
10. `Interpretation limits`: anything that makes the run exploratory rather than claim-grade.

## Notes

1. The standard `docs/research/model-reporting-standard.md` still applies.
2. If the artifact shape changes, update this contract and the README together.
3. Anti-collapse belongs in the report, not only in the model-selection code path.
