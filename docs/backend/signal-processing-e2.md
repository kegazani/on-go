# E2: Feature extraction и clean/features layers

Шаг `E2` расширяет `signal-processing-worker` после `E1` и добавляет feature-layer,
который нужен для baseline-моделей `G1/G2`.

## Что реализовано

1. Для каждого processable stream после очистки (`clean_samples`) запускается window-based feature extraction.
2. Добавлен stream-specific window config (`window_size_ms`, `step_size_ms`) для `polar_*` и `watch_*` потоков.
3. Для каждого окна вычисляются базовые признаки:
   - `sample_count`, `window_duration_ms`, `motion_artifact_ratio`;
   - numeric-агрегации по ключам (`mean/std/min/max/last`);
   - для acceleration/gyro: magnitude features (`*_mag__mean/std/max/last`);
   - для `rr/hrv`-подобных рядов: `rr_like__rmssd`;
   - для context-ключей: категориальный `mode`.
4. В модели `ProcessedStream` добавлены:
   - runtime `feature_windows`;
   - `feature_summary` (`window_count`, `feature_names`, `covered_duration_ms`);
   - `features_object_key`.
5. При `persist_outputs=true` worker сохраняет feature artifacts в object storage.

## Формат outputs

Для каждого stream:

1. `clean-sessions/<session_id>/<version>/streams/<stream_name>/samples.clean.csv.gz`
2. `clean-sessions/<session_id>/<version>/streams/<stream_name>/quality-flags.json`
3. `clean-sessions/<session_id>/<version>/features/<stream_name>/windows.features.csv.gz`

Session summary остается в:

1. `clean-sessions/<session_id>/<version>/reports/preprocessing-summary.json`

## Что покрыто тестами

1. Feature windows создаются для numeric streams (`polar_hr`) и содержат статистики.
2. Activity-context окна получают категориальный `mode` (`activity_label__mode`).
3. `FeatureWindow` валидирует порядок offsets.
4. Runtime `feature_windows` не утекaют в сериализованный summary (`ProcessedStream.model_dump`).

## Ограничения текущего инкремента

1. Реализованы baseline-подобные признаки; расширенный research-набор HRV/frequency features пока не добавлен.
2. Features сохраняются в CSV-слое для прозрачности и простого дебага; columnar format будет отдельным шагом при масштабировании.
3. Follow-up линия `Polar H10 -> arousal/valence fusion` вынесена в отдельные инкременты:
   - спецификация: `docs/backend/signal-processing-e2-1.md`;
   - реализация feature stack: `docs/backend/signal-processing-e2-2.md`;
   - benchmark и comparative artifacts: `docs/backend/signal-processing-e2-3.md`;
   - safety/stress validation: `docs/backend/signal-processing-e2-4.md`.
