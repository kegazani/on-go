# M7.5 Runtime Bundle Export

## Status

- Step ID: `M7.5`
- Status: `spec`
- Date: `2026-03-29`
- Scope: P5 runtime bundle export after a passing `M7.4` verdict.

## Goal

Export the approved Polar-first runtime bundle as a manifest-driven package, then verify that the bundle is structurally loadable before advancing to `P6`.

## Inputs

1. `M7.4` `runtime-candidate-verdict.json`
2. `M7.4` `runtime-candidate-report.md`
3. Selected per-track artifacts for:
   - `activity`
   - `arousal_coarse`
   - `valence_coarse`
4. Per-track feature name payloads for the same three tracks.

## Expected Outputs

The export should produce a run root like:

```text
<output-dir>/wesad/wesad-v1/m7-5-runtime-bundle-export/
  model-bundle.manifest.json
  runtime-bundle-export-report.json
  runtime-bundle-smoke-summary.json
  activity.joblib
  activity_feature_names.json
  arousal_coarse.joblib
  arousal_coarse_feature_names.json
  valence_coarse.joblib
  valence_coarse_feature_names.json
```

## Bundle Contract

1. `model-bundle.manifest.json` is the canonical loader contract.
2. The manifest must declare explicit per-track entries for:
   - `activity`
   - `arousal_coarse`
   - `valence_coarse`
3. Every track entry must include:
   - `variant_name`
   - `claim_status`
   - `anti_collapse_status`
   - `policy_scope`
   - `model_path`
   - `feature_names_path`
   - `feature_names`
4. The export report must summarize the bundle root, manifest path, and a machine-readable artifact index.
5. Earlier contract drafts used `bundle/model-bundle.manifest.json` and `runtime-bundle-export-report.md`; the current export keeps the bundle at the run root and writes `runtime-bundle-smoke-summary.json` instead.

## Acceptance Smoke

The export is only acceptable when all of the following are true:

1. `gate_passed == true` in the source `M7.4` verdict.
2. The manifest can be loaded and resolves every exported artifact path.
3. All three track artifacts exist in the bundle directory.
4. The report records `manifest_loadable == true`.
5. The report records `required_track_files_present == true`.
6. The report records a green smoke check before the run is considered ready for `P6`.

## Failure Modes

1. If `gate_passed == false`, the export must fail fast and write no bundle.
2. If any required track artifact is missing, the export is not claim-safe.
3. If the manifest and artifact index disagree, the bundle should be treated as invalid.

## Notes

1. This step is the runtime-promotion bridge between `M7.4` and `P6`.
2. The contract should stay manifest-driven so the loader can resolve track-specific model and feature-name paths without hard-coded bundle names.
3. If the bundle shape changes, update this doc and the service README together.
