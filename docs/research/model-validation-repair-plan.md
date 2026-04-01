# Model Validation Repair Plan

## Goal

Establish a strict and repeatable validation workflow that prevents:

1. target leakage via label/protocol-derived features;
2. protocol shortcuts (`meta_*`) being used as predictive features;
3. unstable model selection from small fixed holdouts.

The plan applies to reruns of `G3.1`, `H2`, `H3`, `H5`, `G3.2`, and downstream decision package `I1`.

## Evidence Status

Before any rerun, freeze prior artifacts as historical only:

1. `G3.2` evidence from label/protocol features -> `INVALID`.
2. `G3.1/H2/H3/H5` evidence with `meta_*` shortcuts -> `STALE_UNTIL_RERUN`.
3. `H1/I1` conclusions depending on invalid/stale evidence -> `REVIEW_REQUIRED`.

No old run should be overwritten.

## Mandatory Pre-Run Gates

Each experiment must execute safety audit first (`run-kind: audit-wesad`) and fail fast on blockers.

### Gate A: Feature Safety

Artifacts:

1. `selected-features.csv`
2. `leakage-audit.json`

Blocking checks:

1. no feature with `label_` prefix;
2. no protocol shortcuts (`meta_segment_duration_sec`, `meta_source_sample_count`);
3. no target-derived helper columns;
4. single-feature probe macro F1 below shortcut threshold on both tracks.

### Gate B: Split Integrity

Artifacts:

1. `split-audit.json`

Blocking checks:

1. zero subject overlap between train/validation/test;
2. zero duplicate `segment_id` rows;
3. non-empty train and test coverage;
4. class coverage reported for each split.

### Gate C: Numeric Stability

Artifacts:

1. `failed-variants.csv`
2. run log snapshot (stderr summary)

Blocking checks:

1. no `nan/inf` values in training/evaluation matrices;
2. no catastrophic numeric overflows propagating into failed variant runs;
3. warnings are captured/suppressed in benchmark output so comparisons are reproducible and reviewable.

## Evaluation Protocol

For small-subject settings, only fold-based subject evaluation is claim-grade.

1. `LOSO` or `GroupKFold` is required for model selection.
2. Fixed holdout can exist only as debugging view.
3. Every comparison must use identical split policy and label filtering.

Required statistics:

1. fold mean;
2. fold std;
3. 95% CI;
4. per-subject distribution.

## Rerun Sequence

Execute in this exact order:

1. `audit-wesad` (safety baseline);
2. `G3.1r` (safe features + fold protocol);
3. `H2r` on selected global candidates;
4. `H3r` with same folds and calibration policy;
5. `H5r` with same folds and weak-label/label-free modes;
6. `G3.2r` only after harmonized non-label signal features exist;
7. `I1r` only after all upstream reruns pass.

## Required Artifacts Per Rerun

Every rerun package must include:

1. `evaluation-report.json`
2. `model-comparison.csv`
3. `predictions-test.csv`
4. `per-subject-metrics.csv`
5. `selected-features.csv`
6. `split-audit.json`
7. `leakage-audit.json`
8. `failed-variants.csv`
9. `research-report.md`
10. `plots/`

## Plots Checklist

At minimum:

1. leaderboard with CI;
2. fold distribution per candidate;
3. confusion matrix for winners;
4. per-subject metric distribution;
5. per-subject gain/degradation for personalization;
6. ablation comparison (`signal-only`, `meta-only`, `signal+meta`);
7. winner stability across folds/seeds;
8. split coverage chart.

## Model Selection Rules

A candidate can be selected only if:

1. all safety gates pass;
2. mean headline metric is top on fold protocol;
3. CI delta against baseline does not cross zero for claim-grade promotion;
4. worst-subject degradation is within guardrail;
5. no evidence of feature shortcut reliance.

Tie-breaker policy:

1. prefer lower variance;
2. prefer simpler model family;
3. prefer stronger per-subject robustness.

## Verification Checklist For Review

Use this order in every review:

1. inspect `selected-features.csv`;
2. inspect `split-audit.json`;
3. inspect `leakage-audit.json`;
4. inspect fold-level metrics and CI;
5. inspect `model-comparison.csv`;
6. inspect per-subject rows;
7. inspect confusion matrices and class support;
8. inspect ablation and stability plots;
9. approve or reject candidate decision.

## Exit Criteria

The repair plan is complete when:

1. all reruns above are executed with safety gates passing;
2. old invalid/stale evidence is no longer used as decision input;
3. `I1r` recommendation references only safe rerun artifacts.

## Current Status As Of 2026-03-27

The repair plan is partially executed and now has a concrete multi-dataset handoff path.

Completed:

1. `Gate C` hardening implemented: numeric sanitization and reproducible suppression of inference-time runtime warnings.
2. `audit-wesad` executed with passing safety checks on leakage/split integrity.
3. `G3.1 LOSO` rerun executed as the current claim-grade baseline for `WESAD`.
4. `G3.2` no longer relies on pooled mixed-quality comparison as a training decision input.
5. Multi-dataset strategy layer added:
   - separates `real / protocol-mapped / proxy` supervision;
   - fixes the allowed role of each dataset in training.
6. Multi-dataset protocol gate added and executed.
7. Harmonized non-label signal features now exist for `WESAD`, `G-REx`, and `EmoWear`, so `G3.2r` prerequisites are no longer blocked by missing shared features.

Still required:

1. phase-based multi-dataset training run with fixed supervision order;
2. claim-grade cross-dataset evaluation package after training;
3. rerun of downstream decision package using only repaired evidence.

## Multi-Dataset Repair Rule

For `arousal`, the following hierarchy is mandatory:

1. `real` labels can drive headline supervision and model selection;
2. `protocol-mapped` labels can be used for transfer/evaluation and limited auxiliary objectives only;
3. `proxy` labels can be used for pretraining or robustness experiments, but not as final claim evidence;
4. AI-generated or synthetic samples can be used only as bounded augmentation and never as the primary supervised corpus.

This rule supersedes any older interpretation of `G3.2` comparison runs with near-perfect scores.
