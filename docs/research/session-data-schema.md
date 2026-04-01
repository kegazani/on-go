# Схема данных сессии

## Цель

Этот документ задает канонический raw session package, который должен формироваться capture-прототипом и затем приниматься backend ingest-процессом.

Схема строится вокруг четырех принципов:

1. `raw-first` хранение;
2. воспроизводимый replay;
3. `append-only` downstream processing;
4. явная трассировка пропусков и проблем качества.

## Базовые сущности

### `subject`

Представляет человека, который сгенерировал запись.

Обязательные поля:

1. `subject_id`
2. `cohort` или `study_group`
3. `sex`, если поле собирается
4. `age_range`, если поле собирается
5. `consent_version`
6. `baseline_notes`

Исследовательское правило: персонально идентифицирующая информация по возможности не попадает в raw research package. Внутри пакета должен использоваться псевдонимизированный `subject_id`.

### `session`

Представляет одну непрерывную попытку записи.

Обязательные поля:

1. `session_id`
2. `subject_id`
3. `protocol_version`
4. `session_type`
5. `started_at_utc`
6. `ended_at_utc`
7. `timezone`
8. `coordinator_device`
9. `capture_app_version`
10. `status`

Рекомендуемые значения `status`:

1. `completed`
2. `partial`
3. `failed`
4. `exported`

### `protocol_segment`

Представляет упорядоченный блок внутри сессии.

Обязательные поля:

1. `segment_id`
2. `session_id`
3. `name`
4. `order_index`
5. `started_at_utc`
6. `ended_at_utc`
7. `planned`
8. `notes`

Примеры `name` на шаге `A1`:

1. `baseline_rest`
2. `controlled_block`
3. `movement_block`
4. `recovery`

### `device`

Представляет физическое устройство, использованное в сессии.

Обязательные поля:

1. `device_id`
2. `session_id`
3. `device_role`
4. `manufacturer`
5. `model`
6. `firmware_version`, если доступна
7. `source_name`
8. `connection_started_at_utc`
9. `connection_ended_at_utc`

Разрешенные значения `device_role` для начального протокола:

1. `coordinator_phone`
2. `polar_h10`
3. `apple_watch`

### `device_stream`

Представляет логический time series, испускаемый устройством.

Обязательные поля:

1. `stream_id`
2. `session_id`
3. `device_id`
4. `stream_name`
5. `stream_kind`
6. `unit_schema`
7. `sample_count`
8. `started_at_utc`
9. `ended_at_utc`
10. `file_ref`
11. `checksum`

Рекомендуемые значения `stream_name`:

1. `polar_ecg`
2. `polar_rr`
3. `polar_hr`
4. `polar_acc`
5. `watch_heart_rate`
6. `watch_accelerometer`
7. `watch_gyroscope`
8. `watch_activity_context`
9. `watch_hrv`

### `session_event`

Представляет важные несэмпловые события, влияющие на интерпретацию.

Обязательные поля:

1. `event_id`
2. `session_id`
3. `event_type`
4. `occurred_at_utc`
5. `source`
6. `payload`

Рекомендуемые значения `event_type`:

1. `session_started`
2. `session_stopped`
3. `segment_started`
4. `segment_finished`
5. `device_connected`
6. `device_disconnected`
7. `stream_gap_detected`
8. `operator_note`

### `self_report`

Представляет ручной отчет участника после сессии или внутри нее.

Обязательные поля:

1. `report_id`
2. `session_id`
3. `reported_at_utc`
4. `report_version`
5. `answers`
6. `free_text`

Точный questionnaire зафиксирован в `docs/research/label-specification.md`, но схема уже сейчас должна позволять структурированные ответы для:

1. оценки arousal или stress;
2. оценки valence;
3. воспринимаемой dominant activity или context;
4. субъективных аномалий.

### `quality_report`

Представляет структурированную оценку полноты записи.

Обязательные поля:

1. `quality_report_id`
2. `session_id`
3. `generated_at_utc`
4. `overall_status`
5. `checks`
6. `notes`

Рекомендуемые значения `overall_status`:

1. `pass`
2. `warning`
3. `fail`

## Каноническая структура экспорта

Raw session package должен использовать следующую структуру каталогов:

```text
session_<session_id>/
  manifest/
    session.json
    subject.json
    devices.json
    streams.json
    segments.json
  streams/
    polar_ecg/
      metadata.json
      samples.csv.gz
    polar_rr/
      metadata.json
      samples.csv.gz
    polar_hr/
      metadata.json
      samples.csv.gz
    polar_acc/
      metadata.json
      samples.csv.gz
    watch_heart_rate/
      metadata.json
      samples.csv.gz
    watch_accelerometer/
      metadata.json
      samples.csv.gz
    watch_gyroscope/
      metadata.json
      samples.csv.gz
    watch_activity_context/
      metadata.json
      samples.csv.gz
    watch_hrv/
      metadata.json
      samples.csv.gz
  annotations/
    session-events.jsonl
    self-report.json
  reports/
    quality-report.json
  checksums/
    SHA256SUMS
```

Если stream отсутствует, его каталог можно не создавать, но факт отсутствия должен быть отражен в `streams.json` и в отчете качества.

Этот raw package не должен включать versioned label artifacts. Labels хранятся отдельно от raw exports и специфицируются в `docs/research/label-specification.md`.

## Требования к manifest

`manifest/session.json` является корневой записью пакета и должен содержать:

1. версию схемы;
2. идентификаторы сессии;
3. ссылку на subject;
4. версию протокола;
5. время начала и завершения;
6. timezone;
7. статус сессии;
8. число запланированных и фактически наблюдаемых сегментов;
9. сводку по устройствам;
10. сводку по потокам;
11. timestamp экспорта.

Минимальный пример:

```json
{
  "schema_version": "1.0.0",
  "session_id": "sess_20260321_001",
  "subject_id": "subj_001",
  "protocol_version": "A1-v1",
  "session_type": "paired_research",
  "started_at_utc": "2026-03-21T09:00:00Z",
  "ended_at_utc": "2026-03-21T09:18:30Z",
  "timezone": "Europe/Moscow",
  "status": "exported",
  "device_count": 3,
  "stream_count": 6,
  "exported_at_utc": "2026-03-21T09:19:02Z"
}
```

## Требования к stream metadata

Каждый файл `streams/<stream_name>/metadata.json` должен содержать:

1. `stream_id`
2. `stream_name`
3. `device_id`
4. `sampling_character`
5. `expected_unit_schema`
6. `time_reference`
7. `columns`
8. `sample_count`
9. `started_at_utc`
10. `ended_at_utc`
11. `missing_intervals`
12. `checksum`

Рекомендуемые значения `sampling_character`:

1. `regular_high_frequency`
2. `regular_low_frequency`
3. `irregular_event_like`
4. `sparse_summary`

## Правила sample-файлов

Raw samples должны храниться как `samples.csv.gz` в исходном наблюдаемом порядке.

Каждый sample-файл должен содержать следующие общие колонки, когда они применимы:

1. `sample_index`
2. `timestamp_utc`
3. `offset_ms`
4. `source_timestamp`
5. `ingested_at_utc`

Определения:

1. `timestamp_utc`
   Лучшая нормализованная отметка времени для downstream alignment.
2. `offset_ms`
   Миллисекунды с начала сессии на coordinator timeline.
3. `source_timestamp`
   Сырая отметка времени, пришедшая от устройства, или device tick value.
4. `ingested_at_utc`
   Время, когда координатор получил или записал sample.

Специфичные для сигнала колонки добавляются после общих полей.

Примеры:

1. `polar_ecg`
   `voltage_uv`
2. `polar_rr`
   `rr_ms`
3. `polar_hr`
   `hr_bpm`, `contact` (optional), `contact_supported` (optional)
4. `polar_acc`
   `acc_x_mg`, `acc_y_mg`, `acc_z_mg`
5. `watch_heart_rate`
   `hr_bpm`, `confidence`, если поле доступно
6. `watch_accelerometer`
   `acc_x_g`, `acc_y_g`, `acc_z_g`
7. `watch_gyroscope`
   `gyro_x_rad_s`, `gyro_y_rad_s`, `gyro_z_rad_s`
8. `watch_activity_context`
   `activity_type`, `confidence`, `source_event_id`

## Правила времени и синхронизации

Схема использует `coordinator-centric timeline`.

Правила:

1. `iPhone`-координатор определяет границы начала и конца сессии.
2. Каждый stream сохраняет оригинальный device timestamp, если он доступен.
3. Каждый сохраненный sample также получает нормализованный timestamp, выровненный по координатору.
4. Sync corrections не должны перезаписывать исходные raw timing fields.
5. Любая последующая коррекция clock drift относится к `clean`-слою, а не к raw package.

Это разделение необходимо, потому что replay и последующий preprocessing требуют одновременно:

1. raw observed timing;
2. best-effort aligned timing для cross-device анализа.

## Представление пропусков и сбоев

Схема никогда не должна представлять gaps только через молчаливое отсутствие записей.

Если данные отсутствуют, пакет должен зафиксировать это одним или несколькими способами:

1. записями в `session-events.jsonl`, например `stream_gap_detected` или `device_disconnected`;
2. полем `missing_intervals` в stream metadata;
3. предупреждениями или ошибками в `quality-report.json`.

## Совместимость с downstream-этапами

Эта raw-схема специально спроектирована так, чтобы на нее без переделки опирались следующие фазы:

1. `C1/C2`
   ingest и raw storage могут отобразить файлы пакета в backend-сущности;
2. `D1`
   replay может читать coordinator timeline и упорядоченные sample-файлы;
3. `E1/E2`
   clean- и feature-слои можно версионировать без изменения raw exports;
4. `A2/A3`
   labels и evaluation metadata можно добавлять без переопределения базовой session record.
