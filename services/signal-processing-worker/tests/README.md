# Tests

Базовые unit-тесты шагов `E1/E2`:

1. проверка синхронизации и вычисления `alignment_delta_ms`;
2. проверка очистки и `motion_artifact`/`noisy` флагов;
3. проверка `gap` и `packet_loss` расчетов;
4. проверка window-based feature extraction (numeric и activity-context streams);
5. проверка моделей feature-layer (`FeatureWindow`, `StreamFeatureSummary`, dump-behavior `ProcessedStream`).
6. P2: проверка selectors по семействам (`polar_cardio_*`, `watch_motion_core`) через inclusion/exclusion фич.
7. P2: проверка quality-gated export (исключение noisy RR и no-window сценарий при полном отбраковывании).
