# Polar-First Feature Contract

## Purpose

This contract freezes source-of-truth rules for model features across `activity`, `arousal_coarse`, and `valence_coarse`:

1. `Polar H10` is the only cardio/autonomic source.
2. Apple Watch is motion/context only.
3. Watch cardio streams/features are forbidden in production model contracts.

Canonical schema:
`/Users/kgz/Desktop/p/on-go/contracts/personalization/polar-first-feature-contract.schema.json`

## Policy Rules

1. `source_policies.polar_cardio_only = true`
2. `source_policies.watch_motion_only = true`
3. Allowed streams per track are declared via `required_streams` and `optional_streams`.
4. Feature families are split into `must/should/could`.
5. Forbidden watch-cardio streams and feature prefixes are declared in `forbidden_watch_cardio`.

## Example Payload

```json
{
  "contract_version": "polar-first-feature-contract-v1",
  "source_policies": {
    "polar_cardio_only": true,
    "watch_motion_only": true
  },
  "tracks": {
    "activity": {
      "required_streams": ["watch_accelerometer", "polar_hr"],
      "optional_streams": ["watch_activity_context", "watch_gyroscope", "polar_rr"],
      "feature_families": {
        "must": ["watch_acc_kinematics", "polar_hr_level_variability"],
        "should": ["watch_activity_context_categorical", "polar_rr_time_domain_hrv"],
        "could": ["subject_baseline_normalized_deltas"]
      }
    },
    "arousal_coarse": {
      "required_streams": ["polar_hr", "polar_rr", "watch_accelerometer"],
      "optional_streams": ["polar_ecg", "polar_acc", "watch_activity_context"],
      "feature_families": {
        "must": [
          "polar_rr_time_domain_hrv",
          "polar_rr_frequency_domain_hrv",
          "polar_rr_nonlinear_hrv",
          "polar_ecg_quality",
          "watch_acc_kinematics"
        ],
        "should": ["polar_acc_motion_quality", "quality_gate_flags"],
        "could": ["respiration_proxy_from_rr"]
      }
    },
    "valence_coarse": {
      "required_streams": ["polar_hr", "polar_rr", "watch_accelerometer"],
      "optional_streams": ["polar_ecg", "watch_activity_context"],
      "feature_families": {
        "must": [
          "polar_rr_time_domain_hrv",
          "polar_rr_nonlinear_hrv",
          "polar_ecg_quality",
          "watch_acc_kinematics"
        ],
        "should": ["watch_activity_context_categorical", "quality_gate_flags"],
        "could": ["subject_baseline_normalized_deltas", "respiration_proxy_from_rr"]
      }
    }
  },
  "forbidden_watch_cardio": {
    "forbidden_streams": ["watch_heart_rate", "watch_hrv"],
    "forbidden_feature_prefixes": ["watch_hr_", "watch_hrv_", "watch_bvp_", "watch_eda_", "watch_temp_"]
  }
}
```

## Notes

1. Runtime transport fallback may still carry `watch_heart_rate` for resilience; this does not make watch cardio valid for training or primary claim-grade inference.
2. Any model bundle violating this contract should be rejected by training/runtime validation gates.
