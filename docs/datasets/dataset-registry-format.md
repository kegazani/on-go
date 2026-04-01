# Dataset Registry Format (F2)

## Назначение

`dataset registry` фиксирует версионированные записи о внешних и внутренних training datasets,
чтобы `G/H/J` шаги могли ссылаться на стабильные dataset identifiers вместо ad-hoc путей.

В `F2` registry хранится как JSONL-файл:

- `services/dataset-registry/registry/datasets.jsonl`

## Формат записи

Каждая строка JSONL — это `DatasetRecord`.

Обязательные поля:

1. `dataset_id`
2. `dataset_version`
3. `source`
4. `ingestion_script_version`
5. `preprocessing_version`
6. `split_strategy`
7. `target_tracks`
8. `labels_available`
9. `modalities_available`
10. `row_count`
11. `subject_count`
12. `session_count`
13. `created_at_utc`
14. `metadata_object`

Опциональные поля:

1. `source_uri`
2. `source_license`

## Семантика ключевых полей

1. `dataset_id`
   Стабильный logical id датасета (`wesad`, `emowear`, ...).
2. `dataset_version`
   Версия собранного датасет-артефакта (`wesad-v1`, `wesad-v2`).
3. `ingestion_script_version`
   Версия ingestion adapter/скрипта, создавшего запись.
4. `preprocessing_version`
   Версия preprocessing pipeline, примененная к данным.
5. `metadata_object`
   Путь к `dataset-metadata.json` относительно dataset artifact root.

## Правила обновления

1. Upsert-ключ: `(dataset_id, dataset_version)`.
2. Повторная регистрация той же пары заменяет прошлую запись.
3. Новая версия того же `dataset_id` добавляется отдельной строкой.

## Связь с unified artifacts

Каждая запись должна ссылаться на artifact tree вида:

```text
<output-dir>/<dataset_id>/<dataset_version>/
  manifest/
    dataset-metadata.json
    split-manifest.json
  unified/
    subjects.jsonl
    sessions.jsonl
    segment-labels.jsonl
```

`segment-labels.jsonl` может дополнительно содержать provenance-поля внешнего датасета,
если importer умеет сохранить границы исходной segment sequence:

1. `source_segment_start_index`
2. `source_segment_end_index`
3. `source_sample_count`

## Ограничения F2

1. Registry в `F2` файловый (JSONL), не DB-backed.
2. Полный governance (approval/licensing workflow) будет расширяться в последующих шагах.
