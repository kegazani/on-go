# M7.9 - Polar-Expanded Fusion: Implementation and Factual Run

## Scope

1. Add a dedicated `M7.9` modeling run-kind for expanded Polar-first fusion benchmarking.
2. Add `M7.9` runtime bundle export with `polar_rr` as a required live stream.
3. Keep train/serve parity signals by extending runtime online features with RR proxy and cardio-motion coupling features.

## Implementation

1. `modeling-baselines`:
   - new run-kinds:
     - `m7-9-polar-expanded-fusion-benchmark`;
     - `m7-9-runtime-bundle-export`;
   - new ablation matrix:
     - `polar_cardio_only`;
     - `watch_motion_only`;
     - `polar_expanded_fusion`;
   - new research artifacts generation (`evaluation-report`, `predictions`, `per-subject`, `model-comparison`, `plots`, `research-report`).
2. Offline feature extraction:
   - added RR/HRV proxy features from chest ECG window (`chest_rr_*`);
   - added RR quality proxy features (`polar_quality_*`);
   - added cardio-motion coupling features (`fusion_hr_motion_*`).
3. `live-inference-api`:
   - stream buffer now forwards RR window samples;
   - required primary streams now follow runtime bundle manifest (`required_live_streams`);
   - online feature extractor now supports RR proxy and coupling features in manifest mode.

## Factual Run (2026-03-30)

1. Benchmark run:
   - `experiment_id`: `m7-9-polar-expanded-fusion-benchmark-20260330T160125Z`
   - output:
     - `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-9-polar-expanded-fusion-benchmark/`
2. Runtime export run:
   - `experiment_id`: `m7-9-runtime-bundle-export-20260330T160150Z`
   - output:
     - `/Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts/wesad/wesad-v1/m7-9-runtime-bundle-export/`
   - bundle:
     - `bundle_id`: `on-go-m7-9-polar-expanded-runtime-bundle`
     - `bundle_version`: `v2`
     - `required_live_streams`: `watch_accelerometer`, `polar_hr`, `polar_rr`

## Validation

1. `services/modeling-baselines`:
   - `python3 -m pytest -q tests/test_pipeline.py tests/test_m7_5_runtime_bundle_export_contract.py`
   - result: `24 passed`
2. `services/live-inference-api`:
   - `python3 -m pytest -q tests/test_features.py tests/test_buffer.py tests/test_api.py tests/test_loader.py`
   - result: `15 passed`
3. Runtime loader smoke:
   - `inference-api` and `live-inference-api` loaders both read `M7.9` bundle and expose required streams including `polar_rr`.
