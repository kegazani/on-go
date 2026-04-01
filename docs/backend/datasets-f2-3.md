# F2.3: Реальная валидация скачанного `G-REx`

## Цель шага

После `F2.2` закрыть последний gap по приоритетным external datasets и подтвердить на реальных локальных данных, что `G-REx`:

1. скачан в ожидаемом release layout;
2. содержит согласованные `raw`/`transformed` artifacts;
3. проходит реальную локальную инспекцию без `blocked`-статуса.

## Что реализовано

1. Для `G-REx` добавлена реальная `inspect-source` логика вместо placeholder `blocked`.
2. Уточнены `validate-source` rules под фактический layout release:
   - `1_Stimuli`;
   - `2_Questionnaire`;
   - `3_Physio`;
   - `4_Annotation`;
   - `5_Scripts`;
   - `6_Results`.
3. В deep inspection добавлены проверки:
   - `video_info.csv/json`;
   - `quest_raw_data.csv/json`;
   - transformed pickles для `stimuli/questionnaire/physio/annotation`;
   - raw physio filenames `S*_physio_raw_data_M*.hdf5`;
   - HDF5 magic bytes;
   - embedded tokens (`data`, `Arousal EDA`, `Valence EDA`, `sampling rate`, `movie`) в sample raw files;
   - наличие `6_Results/EDA`, `6_Results/PPG`, `6_Results/Analysis`.
4. Добавлен unit-test на минимальный валидный `G-REx` fixture.

## Реальный прогон

Команды:

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
python3 -m compileall -q src tests

PYTHONPATH=src python3 -m dataset_registry.main validate-source \
  --dataset-id grex \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/grex/raw

PYTHONPATH=src python3 -m dataset_registry.main inspect-source \
  --dataset-id grex \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/grex/raw
```

## Результат

### `validate-source`

Статус: `passed`

Подтверждено наличие:

1. top-level structure `1_Stimuli..6_Results`;
2. ключевых metadata/transformed files;
3. raw physio `*.hdf5`.

### `inspect-source`

Статус: `passed`

Подтвержденные counts:

1. `movie_count = 31`
2. `questionnaire_row_count = 254`
3. `physio_raw_hdf5_count = 31`
4. `session_count = 241`
5. `segment_count = 1481`

Подтверждено:

1. `video_info.csv` и `quest_raw_data.csv` соответствуют observed release headers;
2. `CSV` и `JSON` counts совпадают для stimuli/questionnaire metadata;
3. transformed pickles согласованы между собой на уровнях `session` и `segments`;
4. raw physio files соответствуют naming scheme и имеют корректную `HDF5` сигнатуру;
5. sampled raw files содержат embedded tokens, которые ожидают bundled scripts;
6. directories `6_Results/Analysis`, `6_Results/EDA`, `6_Results/PPG` присутствуют.

### Supplemental raw `HDF5` inspection via temporary `h5py`

После первичной проверки дополнительно был выполнен read-only обход реальной `HDF5` hierarchy через временное окружение с `h5py`.

Подтверждено:

1. все `31` raw physio files открываются как `HDF5`;
2. в каждом файле от `5` до `11` device-groups;
3. `data` datasets имеют shape `N x 4`;
4. attrs `movie` и `sampling rate` присутствуют во всех inspected device-groups.

Найдено реальное предупреждение:

1. в `10` raw files некоторые device-groups не содержат `Arousal EDA` и/или `Valence EDA`;
2. это не ломает transformed artifacts, но означает, что не каждый raw device-group полностью размечен на уровне аннотаций.

Файлы с partial missing annotation datasets:

1. `S10_physio_raw_data_M12.hdf5`
2. `S12_physio_raw_data_M14.hdf5`
3. `S14_physio_raw_data_M16.hdf5`
4. `S18_physio_raw_data_M20.hdf5`
5. `S24_physio_raw_data_M26.hdf5`
6. `S25_physio_raw_data_M27.hdf5`
7. `S4_physio_raw_data_M6.hdf5`
8. `S5_physio_raw_data_M7.hdf5`
9. `S6_physio_raw_data_M8.hdf5`
10. `S9_physio_raw_data_M11.hdf5`

## Ограничения

1. Основной `inspect-source` в текущем runtime подтверждает layout/metadata/transformed artifacts; полный raw `HDF5` hierarchy check пока выполнялся отдельно через временное окружение с `h5py`.
2. Raw `G-REx` physio layer usable, но не every device-group fully annotated (`Arousal EDA`/`Valence EDA` partial gaps в `10` files).
3. Полноценный `G-REx` import-adapter в unified internal schema пока не реализован.
