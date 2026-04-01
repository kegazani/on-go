# signal-processing-worker

Worker строит preprocessing и feature-layer (`E1 + E2`):

1. синхронизация `Polar` и `Watch` по единой временной шкале;
2. базовая очистка кардио- и motion-сигналов;
3. расчет quality flags (`gaps`, `packet_loss`, `motion_artifacts`, `noisy_intervals`);
4. сохранение clean-артефактов и quality-summary в object storage.
5. windowing clean-сэмплов и извлечение feature-наборов для downstream baseline-моделей.

## P2 (кратко): selectors + quality-gated export

Текущий P2-контур в `signal-processing-worker`:

1. Семейства признаков разделяются по stream-origin и префиксам фич:
   - `polar_cardio_core`/`polar_cardio_extended`: `polar_rr` (`rr_like__*`) и `polar_ecg` (`ecg_*`);
   - `watch_motion_core`: `watch_accelerometer` (`acc_mag__*`) и motion-агрегаты.
2. Quality gate применяется до feature export: шумные/out-of-range сэмплы исключаются на этапе cleaning.
3. Если после cleaning поток пустой, feature windows не экспортируются, а в summary добавляются предупреждения качества.
4. Unit-тесты проверяют inclusion/exclusion для семейств и деградационные quality-gated сценарии.

## Реализация E1/E2

Что делает воркер на запуске по `session_id`:

1. читает session metadata и stream mapping из `Postgres` (`ingest` schema);
2. загружает raw stream samples (`samples.csv(.gz)`) из `MinIO/S3`;
3. оценивает `alignment_delta_ms` по паре `offset_ms`/`timestamp_utc`;
4. строит `aligned_offset_ms`, чистит шумные значения и помечает quality-флаги;
5. сохраняет clean stream artifacts и session preprocessing-summary в `clean`-слое;
6. строит feature windows и агрегированные признаки (cardio/motion/context);
7. сохраняет feature artifacts в `features`-слое;
8. обновляет `ingest.session_quality_reports` записью `preprocessing_<version>`.

## Локальный запуск

Из `services/signal-processing-worker`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
set -a && source .env && set +a
signal-processing-worker --session-id sess_20260321_001
```

Запуск без записи артефактов (только расчет и вывод summary):

```bash
signal-processing-worker --session-id sess_20260321_001 --dry-run
```

## Структура

```text
services/signal-processing-worker/
  pyproject.toml
  .env.example
  README.md
  src/
    signal_processing_worker/
      config.py
      db.py
      errors.py
      models.py
      repository.py
      service.py
      storage.py
      main.py
  tests/
  deploy/
```

Связанные документы шагов `E1/E2`:

1. `docs/backend/signal-processing-e1.md`
2. `docs/backend/signal-processing-e2.md`
3. `docs/research/session-data-schema.md`
4. `docs/research/evaluation-plan.md`
