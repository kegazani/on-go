# M7.9 - Polar-Expanded Fusion Model: Detailed Implementation Plan

## Step Context

- Date: `2026-03-29`
- Priority source: explicit user request
- Goal: move from narrow live features (`acc + hr stats`) to expanded Polar-first feature space and deploy updated backend model for `activity`, `arousal`, `valence`.

## Target Runtime Policy

1. Cardio primary source: `Polar H10` (`polar_hr`, `polar_rr`).
2. Watch role: motion/context only (`watch_accelerometer` as mandatory motion stream).
3. Watch heart-rate remains emergency fallback only (non-primary policy).
4. Train/serve parity is mandatory: identical feature contract for offline training and live inference.

## Scope

### In

1. Expanded RR/HRV/quality feature engineering.
2. Watch motion-only feature family refresh.
3. Cross-modal feature set (cardio-motion coupling).
4. Retraining and model comparison for:
   - `activity`
   - `arousal_coarse`
   - `valence_coarse` (scoped/internal mode).
5. New runtime bundle + manifest + rollout/canary.

### Out

1. New mobile UX redesign (except critical reconnect controls if needed).
2. New external dataset ingestion track.
3. Claims beyond scoped valence policy.

## Feature Contract v2 (`polar_expanded_v2`)

### Required live streams

1. `watch_accelerometer`
2. `polar_hr`
3. `polar_rr`

### Optional live streams

1. `watch_activity_context`
2. `watch_heart_rate` (fallback only)
3. `watch_hrv` (diagnostic only)

### Polar cardio features (from RR/HR)

1. Time-domain:
   - `mean_nn`, `median_nn`, `min_nn`, `max_nn`
   - `sdnn`, `rmssd`, `sdsd`
   - `nn50`, `pnn50`
   - `iqr_nn`, `mad_nn`, `cvnn`, `cvsd`
2. Nonlinear:
   - `sd1`, `sd2`, `sd1_sd2_ratio`
   - `sample_entropy`, `shannon_entropy`
   - `triangular_index`
3. Frequency-domain:
   - `vlf_power`, `lf_power`, `hf_power`
   - `lf_hf_ratio`, `lf_nu`, `hf_nu`
   - log-scaled powers (`log_vlf`, `log_lf`, `log_hf`)
4. HR dynamics:
   - `hr_mean`, `hr_std`, `hr_min`, `hr_max`
   - `hr_slope`, `hr_delta`, recovery-style trend features

### Motion features (watch only)

1. Axis and magnitude stats:
   - `acc_x/y/z` and `acc_mag`: `mean/std/min/max/last`
2. Dynamics:
   - jerk/energy/SMA/variance features
3. Short-long window deltas for movement transitions

### Quality and reliability features

1. RR coverage ratio per window.
2. RR staleness and gap indicators.
3. Ectopic/outlier ratio.
4. Contact flags/ratio when available.
5. Window quality gate status for downstream confidence.

### Cross-modal coupling

1. Motion-normalized HR and HRV features.
2. Correlation and lag features (`hr` vs `acc_mag`).
3. Coupling stability indicators for `active movement` vs `stress-like high arousal`.

## Windowing and Parity

1. Primary window: `30s` with `10s` step for stability.
2. Secondary responsive window: `15s` with `5s` step (if needed by latency constraints).
3. One canonical extractor path for:
   - signal-processing artifacts
   - live-inference online extraction.

## Model Training Plan

1. Build `M7.9` training dataset variant with new v2 feature contract.
2. Run ablations:
   - `polar_cardio_only`
   - `watch_motion_only`
   - `polar_cardio + watch_motion` (target production candidate)
3. Train track-specific models:
   - `activity`: motion+cardio
   - `arousal_coarse`: cardio-heavy fusion
   - `valence_coarse`: scoped fusion
4. Evaluate with LOSO / subject-wise protocol.
5. Enforce anti-collapse and claim-support gates before export.

## Reporting Artifacts (Mandatory)

1. `evaluation-report.json`
2. `predictions-test.csv`
3. `per-subject-metrics.csv`
4. `model-comparison.csv`
5. `plots/` (confusion, per-subject spread, delta vs baseline)
6. `research-report.md`
7. dedicated error analysis for false `recovery_rest` under real movement.

## Runtime Bundle and Backend Rollout

1. Export new manifest-driven bundle with v2 feature names per track.
2. Manifest policy:
   - required streams include `polar_rr`
   - explicit fallback signals when policy degrades.
3. Deploy to:
   - `inference-api`
   - `live-inference-api`
4. Keep old bundle as rollback candidate.

## Canary / Acceptance Gate

1. Shadow/canary on factual device sessions.
2. Acceptance KPIs:
   - reduced false `recovery_rest` during movement protocol
   - improved `activity` and `arousal` headline metrics vs current v4
   - stable valence scoped outputs (no silent `unknown` collapse under valid context)
3. Pass criteria required before full cutover.

## Implementation Decomposition (Subagent-first)

1. Subagent A: feature contract + extractor implementation (`signal-processing-worker`, `live-inference-api`).
2. Subagent B: modeling pipeline updates + training runs + research artifacts.
3. Subagent C: runtime bundle export + manifest policy + rollout/canary scripts.
4. Main agent: orchestration, integration, gate checks, status/log updates.

## Risks and Mitigations

1. Risk: train/serve skew.
   - Mitigation: one shared feature contract and parity tests.
2. Risk: unstable RR quality in live windows.
   - Mitigation: quality gates + fallback signaling + confidence downgrade.
3. Risk: valence instability.
   - Mitigation: scoped policy preserved; no user-facing strong claims until canary pass.
4. Risk: latency increase from richer feature extraction.
   - Mitigation: profile extraction path, optimize hot loops, keep 5-10s emission cadence.

## Planned Execution Order (Next Working Day)

1. Freeze `polar_expanded_v2` feature contract.
2. Implement extractor/runtime parity.
3. Launch retraining and full model comparison.
4. Export and wire new runtime bundle.
5. Run factual canary acceptance and decide cutover.
