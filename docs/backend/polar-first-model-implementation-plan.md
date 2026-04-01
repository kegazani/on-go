# Polar-first Model Implementation Plan (Activity / Arousal / Valence)

## 1) Scope and Design Constraints

1. Cardio and autonomic features must come from `Polar H10` only (`polar_rr`, `polar_hr`, optional `polar_ecg`, `polar_acc` as auxiliary motion quality).
2. Watch features must be motion/context only (`watch_accelerometer`, optional `watch_gyroscope`, `watch_activity_context`).
3. No watch heart-rate or watch HRV in final production feature set; keep only temporary fallback path for transport resilience.
4. Targets to support: `activity`, `arousal_coarse`, `valence_coarse`.

## 2) Current Baseline (Repo Audit)

### Already implemented

1. `signal-processing-worker` already computes advanced RR/HRV from `polar_rr`:
   - time-domain: `sdnn`, `rmssd`, `sdsd`, `nn20/50`, `pnn20/50`, `cvnn/cvsd`, percentile and dispersion stats;
   - nonlinear: `sd1/sd2`, `sd1_sd2_ratio`, `triangular_index`, `shannon_entropy`, `sample_entropy`;
   - frequency-domain: `vlf/lf/hf`, `lf_hf_ratio`, `lf_nu/hf_nu`.
2. `signal-processing-worker` already computes ECG-quality proxies from `polar_ecg`.
3. Live path now forwards `polar_hr` + watch motion and receives inference in iPhone runtime.

### Critical bottlenecks

1. Current runtime bundles produce near-constant predictions (`recovery_rest`, `low`, `neutral`) under varied inputs.
2. `live-inference-api` online feature extractor is still watch-centric and does not use the full Polar RR/HRV family.
3. Online/offline feature parity is incomplete: training uses richer features than live inference.

## 3) WESAD-aligned Polar Feature Set (Prioritized)

## Must-have (MVP claim-grade)

1. RR/HRV time-domain: `mean_rr`, `sdnn`, `rmssd`, `sdsd`, `pnn20`, `pnn50`, `mean_hr`, `hr_range`.
2. RR/HRV frequency-domain: `lf_power`, `hf_power`, `lf_hf_ratio`, `lf_nu`, `hf_nu`.
3. RR/HRV nonlinear: `sd1`, `sd2`, `sd1_sd2_ratio`, `sample_entropy`, `triangular_index`.
4. ECG quality gates: `ecg_coverage_ratio`, `ecg_noise_ratio`, `ecg_baseline_wander_score`.
5. Watch motion-only: `watch_acc_*`, `watch_acc_mag_*`, activity-context mode.

## Should-have

1. Baseline-normalized HRV deltas (per-subject/session baseline windows).
2. Window-quality flags as model features and as training filters.
3. Polar ACC motion-quality companion features to deconfound movement artifacts.

## Could-have

1. Arrhythmia-robust RR outlier handling and uncertainty features.
2. Adaptive windowing for sparse RR segments.
3. Temporal smoothing and hysteresis in online semantic state layer.

## 4) Incremental Delivery Plan (Small Verifiable Steps)

## P1 - Feature Contract Freeze (Polar-first)

1. Define canonical feature contract for `activity/arousal/valence` with source tags: `polar_only`, `watch_motion_only`.
2. Remove watch cardio fields from selected training feature lists.
3. Artifact: `contracts/personalization/polar-first-feature-contract.schema.json` + markdown note.
4. Dependency: none.
5. Ready when: contract validated by schema and referenced by training/runtime loaders.

## P2 - Offline Feature Pipeline Alignment

1. Add explicit feature family selectors in `signal-processing-worker` outputs: `polar_cardio_core`, `polar_cardio_extended`, `watch_motion_core`.
2. Add quality-gated feature export (drop or mark windows with poor ECG/RR quality).
3. Artifact: updated feature summary, unit tests for inclusion/exclusion rules.
4. Dependency: P1.
5. Ready when: worker tests pass and feature manifest includes source-family tags.

## P3 - Training Dataset Build (Polar-first)

1. Update `modeling-baselines` run-kind for Polar-first tracks:
   - `activity`: watch motion + optional polar cardio support;
   - `arousal`: polar cardio primary;
   - `valence`: polar cardio primary + motion context.
2. Add ablation matrix: `polar_only`, `watch_motion_only`, `polar+watch_motion`.
3. Artifact: claim-grade run bundle (`evaluation-report`, `model-comparison`, `per-subject`, `plots`, `research-report`).
4. Dependency: P2.
5. Ready when: non-trivial class distribution and non-constant predictions across ablations.

## P4 - Model Selection and Runtime-Candidate Gate

1. Select per-track winners by stability criteria (subject-wise variance + worst-case degradation).
2. Add anti-collapse gate: reject candidate if predictions collapse to single class on validation stress-set.
3. Artifact: `runtime-candidate-report.md` + machine-readable gate verdict JSON.
4. Dependency: P3.
5. Ready when: gate status `pass` for all 3 tracks.

## P5 - Runtime Bundle Export

1. Export per-track bundle via manifest path:
   - `activity` model + feature names;
   - `arousal_coarse` model + feature names;
   - `valence_coarse` model + feature names.
2. Artifact: new runtime bundle directory + `model-bundle.manifest.json`.
3. Dependency: P4.
4. Ready when: offline smoke predicts non-constant outputs on synthetic motion/cardio scenarios.

## P6 - Live Inference API Polar-first Online Features

1. Replace watch-centric online feature extraction with parity profile matching offline selected feature families.
2. Ensure input stream policy:
   - required: `polar_hr` + `watch_accelerometer`;
   - optional/aux: `polar_rr`, `polar_ecg`, `watch_activity_context`.
3. Add telemetry logs for feature coverage and per-track feature_count.
4. Artifact: API tests + parity test (offline vs online feature vector consistency).
5. Dependency: P5.
6. Ready when: websocket inference varies with controlled movement/HR scenarios.

## P7 - on-go-ios Integration

1. Keep transport real-only; forward streams required by Polar-first runtime profile.
2. Surface state quality in UI (e.g., cardio quality degraded).
3. Preserve reconnect control on watch.
4. Artifact: iOS integration checklist + e2e logs.
5. Dependency: P6.
6. Ready when: stable 10+ minute session with changing states under protocol actions.

## P8 - Acceptance and Claim Gate

1. Device protocol test: `rest -> movement -> cognitive load -> recovery` with label anchors.
2. Validate `activity/arousal/valence` responsiveness and guardrails.
3. Freeze release candidate bundle and rollout notes.
4. Artifact: acceptance report + rollback criteria.
5. Dependency: P7.
6. Ready when: acceptance checklist pass and no-collapse gate pass.

## 5) Dependency Graph

1. P1 -> P2 -> P3 -> P4 -> P5 -> P6 -> P7 -> P8.
2. P6 depends on exact feature names selected in P4/P5.
3. P7 cannot be finalized before P6 websocket contract is frozen.

## 6) Risks and Mitigations

1. Risk: label scarcity for valence causes unstable model.
   - Mitigation: stricter uncertainty policy + fallback semantics + no-claim thresholding.
2. Risk: online/offline feature drift.
   - Mitigation: parity tests and manifest-locked feature lists.
3. Risk: model collapse into one class.
   - Mitigation: anti-collapse gate in P4 and mandatory stress-set before export.
4. Risk: sensor quality degradation during movement.
   - Mitigation: ECG/RR quality features + gated inference confidence.

## 7) Subagent Delegation Plan

1. Subagent A (`Feature Architect`): execute P1-P2.
   - Deliverables: contract schema, worker feature-family selectors, tests.
2. Subagent B (`Modeling Lead`): execute P3-P5.
   - Deliverables: ablation runs, selection report, runtime bundle.
3. Subagent C (`Runtime Integrator`): execute P6-P7.
   - Deliverables: live-inference feature parity, websocket telemetry, iOS integration updates.
4. Subagent D (`Validation QA`): execute P8.
   - Deliverables: device acceptance report, release/rollback recommendation.

## 8) First Execution Slice (Recommended Immediately)

1. Start with P1 (contract freeze) + anti-collapse check script on current bundles.
2. Run one short P3 pilot (`polar_only` vs `polar+watch_motion`) to verify non-constant behavior before full sweep.
3. Block further runtime rollout until P4 gate is green.
