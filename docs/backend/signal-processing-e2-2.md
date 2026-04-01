# E2.2: Extended Polar H10 RR/ECG/ACC feature extraction

## Статус

- Step ID: `E2.2`
- Status: `completed`
- Date: `2026-03-27`

## Запрос

Реализовать расширенный `Polar H10` feature stack после спецификации `E2.1`:

1. live `polar_acc` capture;
2. сохранение `contact/contactSupported`;
3. расширенные `RR/HRV` и `ECG quality` признаки;
4. подготовка fusion-ready основы под `arousal + valence`.

## Что реализовано

### Capture (`on-go-ios`)

1. В `LivePolarH10SDKAdapter` добавлен запуск и сбор `polar_acc` online streaming.
2. Добавлен батч `polar_acc` в drain-flow и cleanup/dispose логика для ACC stream.
3. В HR callback сохранены `contact` и `contact_supported` в `polar_hr` samples.
4. Simulated adapter расширен `polar_acc` потоками для локального тестового capture-flow.
5. CSV schema в `FileBasedSessionArchiveStore` обновлена:
   - `polar_hr` теперь пишет `hr_bpm`, `contact`, `contact_supported`.

### Processing (`signal-processing-worker`)

1. Расширены допустимые поля `polar_hr` в value limits:
   - `contact` (`0..1`)
   - `contact_supported` (`0..1`).
2. Для RR-like рядов добавлен расширенный `HRV` набор:
   - `sdnn`, `rmssd`, `sdsd`;
   - `nn20/pnn20`, `nn50/pnn50`;
   - `cvnn/cvsd`;
   - `mean/median/range/iqr/mad`;
   - `min/max`, `p10/p90`, `mean_abs_diff`, `median_abs_diff`;
   - `mean_hr/hr_min/hr_max/hr_range`;
   - `sd1/sd2/sd1_sd2_ratio`;
   - `triangular_index`, `shannon_entropy`, `sample_entropy_m2_r02`;
   - frequency-domain: `vlf_power`, `lf_power`, `hf_power`, `lf_hf_ratio`, `lf_nu`, `hf_nu`;
   - `outlier_ratio`, `valid_count`, `window_duration_ms`.
3. Для `polar_ecg` добавлен quality-блок:
   - `ecg_sample_count`;
   - `ecg_coverage_ratio`;
   - `ecg_peak_count`;
   - `ecg_peak_success_ratio`;
   - `ecg_noise_ratio`;
   - `ecg_baseline_wander_score`.
4. Для `polar_acc` добавлены motion-признаки:
   - `polar_acc__energy`;
   - `polar_acc__jerk_mean`;
   - `polar_acc__jerk_std`;
   - `polar_acc__stationary_ratio`;
   - `polar_acc__motion_burst_count`.

## Тесты

`signal-processing-worker`:

1. Добавлены unit tests на:
   - extended RR/HRV features;
   - ECG quality features;
   - Polar ACC motion features.
2. Выполнен прогон:
   - `python3 -m pytest -q`
   - результат: `12 passed`.

## Измененные файлы

1. `on-go-ios/packages/CaptureKit/Sources/PhoneCapture/PolarH10Adapter.swift`
2. `on-go-ios/packages/CaptureKit/Sources/CaptureStorage/FileBasedSessionArchiveStore.swift`
3. `services/signal-processing-worker/src/signal_processing_worker/service.py`
4. `services/signal-processing-worker/tests/test_service.py`
5. `docs/research/session-data-schema.md`
6. `docs/backend/signal-processing-e2-2.md`

## Ограничения текущего инкремента

1. Валидация по Swift runtime не выполнялась в этой shell-среде (нет live iOS/Polar SDK runtime).
2. Моделирование `arousal + valence` пока не прогонялось на новом feature stack; это следующий шаг.

## Следующий рекомендуемый шаг

`E2.3` — fusion-ready benchmark на расширенном feature stack:

1. `polar_rr_only`;
2. `polar_rr_acc`;
3. `watch_plus_polar_fusion`;
4. отчёт по `arousal + valence` с subject-wise protocol.
