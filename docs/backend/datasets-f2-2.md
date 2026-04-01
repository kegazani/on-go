# F2.2: Реальная валидация скачанных external datasets (`WESAD`, `EmoWear`, `DAPPER`)

## Цель шага

Подтвердить на реальных локально скачанных данных, что `external dataset` слой после `F2/F2.1` не только знает ожидаемый layout, но и действительно:

1. читает реальные файлы;
2. проверяет headers и label sources;
3. корректно парсит payloads;
4. выявляет реальные dataset-specific проблемы отдельно от багов ingestion tooling.

## Что реализовано

1. В `dataset-registry` добавлена команда `inspect-source` для глубокого анализа source-папок:
   - `WESAD`: subject structure, `S*.pkl`, label values, `quest.csv`, `E4` directories;
   - `EmoWear`: `meta.csv`, `questionnaire.csv`, `mqtt.db`, parseability `e4.zip/bh3.zip`;
   - `DAPPER`: session groups, CSV headers, first-row parseability, zero-byte files.
2. Уточнены validation/inspection rules под реальные release layouts:
   - `EmoWear` использует `questionnaire.csv` и participant dirs `<code>-<id>`;
   - `DAPPER` проверяется по реальным `*.csv`, `*_ACC.csv`, `*_GSR.csv`, `*_PPG.csv`;
   - `WESAD` принимает оба реальных варианта заголовка `quest.csv`: `# Subj;...` и `# Subj:;...`.
3. Во время реального прогона найден и исправлен дефект `WESAD` importer:
   - pickle loader переведен на `encoding="latin1"` для python2-compatible `S*.pkl`;
   - importer перестал схлопывать subject до одного dominant label;
   - теперь сохраняются contiguous non-zero `wesad_state` segments с provenance-полями `source_segment_start_index/source_segment_end_index/source_sample_count`.
4. Классификация `DAPPER` zero-byte CSV вынесена в отдельный warning вместо ложного `header_mismatch/fail`.
5. Добавлены unit-тесты для:
   - colon-варианта `WESAD` quest header;
   - zero-byte `DAPPER` sensor files;
   - `WESAD` pickle import с сохранением contiguous segments.

## Реальные прогоны

Команды:

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
python3 -m compileall -q src tests

PYTHONPATH=src python3 -m dataset_registry.main inspect-source \
  --dataset-id wesad \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/raw

PYTHONPATH=src python3 -m dataset_registry.main inspect-source \
  --dataset-id emowear \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/emowear/raw

PYTHONPATH=src python3 -m dataset_registry.main inspect-source \
  --dataset-id dapper \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/dapper/raw

PYTHONPATH=src python3 -m dataset_registry.main import-wesad \
  --registry-path /Users/kgz/Desktop/p/on-go/services/dataset-registry/registry/datasets.jsonl \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1
```

## Результат по датасетам

### `WESAD`

1. `inspect-source` -> `passed`.
2. Подтвержден full public layout:
   - `15` subject directories;
   - label values `0..7`;
   - chest stream lengths согласованы с `label`;
   - `quest.csv` и `E4` directories присутствуют.
3. Реальный `import-wesad` -> `completed`:
   - `subject_count = 15`;
   - `session_count = 15`;
   - `segment_label_count = 119`.
4. В `segment-labels.jsonl` сохранены source boundaries по contiguous segments.
5. Source labels `5/6/7` не потеряны: они сохранены как `unknown` segments и явно помечены warning’ами per subject.

### `EmoWear`

1. `inspect-source` -> `passed`.
2. Подтверждены реальные release-artifacts:
   - `49` participant directories;
   - `meta.csv` header соответствует ожидаемой схеме;
   - `questionnaire.csv` header соответствует ожидаемой схеме;
   - `e4.zip` и `bh3.zip` parseable для всех inspected participants;
   - `mqtt.db` открывается как SQLite.
3. Итог: данные готовы для следующего шага с отдельным import-adapter без выявленных schema/blocking issues.

### `DAPPER`

1. `inspect-source` -> `warning`.
2. Подтверждено, что основная схема release корректна:
   - `88` participant directories;
   - `419` session groups;
   - CSV headers соответствуют observed schema;
   - first-row parseability проходит.
3. Выявлены реальные проблемы в source data:
   - `8` incomplete session groups без полного `base/ACC/GSR/PPG` набора (`3018`, `3029`);
   - `2` zero-byte sensor files у `3024`.
4. Итог: датасет не заблокирован, но потребует tolerant importer и явных policy-правил пропуска/маркировки неполных session groups.

### `G-REx`

1. Не проверялся в `F2.2`, потому что dataset еще не скачан локально.
2. Статус: `blocked` до отдельного inspect-run.

## Ограничения

1. `inspect-source` подтверждает structure/headers/parseability, но пока не заменяет полноценные import-adapters для `EmoWear` и `DAPPER`.
2. `WESAD` importer по-прежнему работает на unified metadata/labels layer и не переносит полный per-sample raw ingest в backend storage.
3. Семантика source labels `5/6/7` в `WESAD` пока не нормализована в отдельные canonical activity classes; они осознанно сохранены как `unknown` segments.
