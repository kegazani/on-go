# E1: Preprocessing - sync, clean, quality flags

## Что реализовано

Шаг `E1` закрывает первый рабочий инкремент preprocessing-контура:

1. Добавлен отдельный runtime worker `signal-processing-worker`.
2. Реализовано чтение raw-session metadata из `Postgres` (`ingest.raw_sessions`, `ingest.session_streams`, `ingest.ingest_artifacts`).
3. Реализовано чтение raw sample artifacts (`samples.csv(.gz)`) из `MinIO/S3`.
4. Реализована синхронизация по единой временной шкале:
   - расчет `alignment_delta_ms` по паре `offset_ms`/`timestamp_utc`;
   - расчет `aligned_offset_ms` для downstream clean-слоя.
5. Реализована базовая очистка сигналов по stream-specific диапазонам (`hr`, `rr`, `ecg`, `acc`, `gyro`, `confidence`, `hrv`).
6. Добавлен расчет quality flags:
   - `gaps`;
   - `packet_loss_estimated_samples`;
   - `motion_artifact`;
   - `noisy_intervals`.
7. Реализована запись clean artifacts и summary в object storage (`clean-sessions/...`).
8. Реализован upsert quality report в `ingest.session_quality_reports` c id `preprocessing_<version>`.
9. Добавлены unit-тесты preprocessing-логики (`5 passed`).

## Формат выходных артефактов

Для `session_id` и `preprocessing_version` воркер формирует ключи:

1. `clean-sessions/<session_id>/<version>/streams/<stream_name>/samples.clean.csv.gz`
2. `clean-sessions/<session_id>/<version>/streams/<stream_name>/quality-flags.json`
3. `clean-sessions/<session_id>/<version>/reports/preprocessing-summary.json`

`preprocessing-summary` содержит:

1. `preprocessing_version`;
2. `session_id`;
3. `overall_quality_status`;
4. per-stream метрики clean/quality;
5. список предупреждений и количество пропущенных потоков.

## Локальный запуск

Из `services/signal-processing-worker`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install '.[dev]'
cp .env.example .env
set -a && source .env && set +a
signal-processing-worker --session-id sess_20260321_001
```

Dry-run режим (без записи artifacts и DB update):

```bash
signal-processing-worker --session-id sess_20260321_001 --dry-run
```

## Границы шага E1

Что покрыто:

1. Базовая синхронизация и очистка raw stream данных.
2. Базовый набор quality flags для gating downstream evaluation.
3. Версионированный clean-layer output и quality report update.

Что остается для `E2`:

1. windowing и построение feature layers;
2. вычисление HRV/time-domain/frequency/activity/context features;
3. стандартизованный feature artifact format для `G1/G2`.
