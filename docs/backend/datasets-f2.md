# F2: Dataset registry и импорт первого датасета (WESAD)

## Цель шага

Сделать минимально воспроизводимый `external dataset` контур:

1. зафиксировать формат `dataset registry`;
2. реализовать первый ingestion adapter (`WESAD`);
3. сохранить unified artifacts, пригодные для следующих шагов `G1/G2`.

## Что реализовано

1. Добавлен новый сервисный модуль `services/dataset-registry`.
2. Реализован JSONL-backed registry (`DatasetRegistry`) с upsert/list поведением.
3. Зафиксированы модели:
   - `DatasetRecord`;
   - `UnifiedSubject`;
   - `UnifiedSession`;
   - `UnifiedSegmentLabel`;
   - `SplitManifest`.
4. Добавлен CLI:
   - `dataset-registry register`;
   - `dataset-registry list`;
   - `dataset-registry import-wesad`.
5. Реализован `WESAD` importer:
   - discovery subject-папок `S*`;
   - label extraction из `labels.csv`/`label.csv`/python2-compatible `S*.pkl`;
   - mapping contiguous non-zero `wesad_state` segments в canonical `activity/arousal/valence` labels;
   - subject-wise split manifest;
   - запись unified artifacts и dataset metadata;
   - сохранение source boundaries (`source_segment_start_index`, `source_segment_end_index`, `source_sample_count`) для segment labels.

## Формат outputs

`import-wesad` формирует tree:

```text
<output-dir>/wesad/<dataset-version>/
  manifest/
    dataset-metadata.json
    split-manifest.json
  unified/
    subjects.jsonl
    sessions.jsonl
    segment-labels.jsonl
```

Registry-запись обновляется в:

- `services/dataset-registry/registry/datasets.jsonl`

## Тесты

Добавлены unit-тесты:

1. `tests/test_registry.py` — upsert/list semantics registry;
2. `tests/test_wesad.py` — генерация unified artifacts и негативный сценарий пустого source.

## Ограничения текущего инкремента

1. `F2` покрывает metadata/unified labels слой; полный per-sample ingest внешнего датасета в raw storage не включен.
2. WESAD mapping реализован как базовый canonical bridge для запуска baseline pipeline.
3. Для production-grade cross-dataset pipeline потребуется расширение quality checks и richer label alignment.
