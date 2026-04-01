# Tests

Базовые тесты `modeling-baselines`:

1. `test_metrics.py` - корректность базовых classification и ordinal метрик.
2. `test_pipeline.py` - feature-selection helper, `GaussianNB` baseline classifier и M7.4 runtime-candidate guardrails.
3. `test_m7_3_polar_first_contract.py` - Polar-first ablation matrix, anti-collapse signal и `research-report` template contract.
4. `test_m7_5_runtime_bundle_export_contract.py` - M7.5 fail-fast export gate, bundle manifest и export report contract.

Запуск:

```bash
cd /Users/kgz/Desktop/p/on-go/services/modeling-baselines
python3 -m pytest -q
```
