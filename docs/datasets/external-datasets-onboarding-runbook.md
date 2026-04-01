# External Datasets Onboarding Runbook (F2.1)

## Цель

Единая инструкция для каждого приоритетного датасета:

1. где скачать;
2. куда положить локально;
3. как обязательно прогнать проверку (`validate-source`);
4. как прогнать глубокую инспекцию (`inspect-source`);
5. как выполнить импорт (когда поддерживается) и что проверить на выходе.

## Единая локальная структура

Базовый путь в репозитории:

- `/Users/kgz/Desktop/p/on-go/data/external`

Структура:

```text
data/external/<dataset_id>/
  raw/
  artifacts/
```

Где `<dataset_id>`: `wesad`, `emowear`, `grex`, `dapper`.

## Общая последовательность для каждого датасета

1. Скачать dataset из официального источника.
2. Распаковать/положить файлы в `data/external/<dataset_id>/raw`.
3. Запустить проверку структуры:

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
PYTHONPATH=src python3 -m dataset_registry.main validate-source \
  --dataset-id <dataset_id> \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/<dataset_id>/raw
```

4. Если статус `failed` — исправить раскладку файлов и повторить.
5. Запустить глубокую инспекцию содержимого:

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
PYTHONPATH=src python3 -m dataset_registry.main inspect-source \
  --dataset-id <dataset_id> \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/<dataset_id>/raw
```

6. Если `inspect-source` вернул `failed` — исправить данные/layout или адаптер перед импортом.
7. Если статус `passed` или `warning` — перейти к импорту/следующему шагу.

## WESAD

### Где скачать

1. Official page: <https://ubi29.informatik.uni-siegen.de/usi/data_wesad.html>
2. Direct dataset link (from official page): <https://uni-siegen.sciebo.de/s/HGdUkoNlW1Ub0Gx>

### Куда положить

- `/Users/kgz/Desktop/p/on-go/data/external/wesad/raw`

Ожидается наличие `S*` папок (например, `S2`, `S3`, ...).

### Обязательная проверка

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
PYTHONPATH=src python3 -m dataset_registry.main validate-source \
  --dataset-id wesad \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/raw
```

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
PYTHONPATH=src python3 -m dataset_registry.main inspect-source \
  --dataset-id wesad \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/raw
```

### Импорт (реализован в F2)

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
PYTHONPATH=src python3 -m dataset_registry.main import-wesad \
  --registry-path /Users/kgz/Desktop/p/on-go/services/dataset-registry/registry/datasets.jsonl \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/raw \
  --output-dir /Users/kgz/Desktop/p/on-go/data/external/wesad/artifacts \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1
```

Проверить, что появились файлы:

1. `.../artifacts/wesad/wesad-v1/manifest/dataset-metadata.json`
2. `.../artifacts/wesad/wesad-v1/manifest/split-manifest.json`
3. `.../artifacts/wesad/wesad-v1/unified/subjects.jsonl`
4. `.../artifacts/wesad/wesad-v1/unified/sessions.jsonl`
5. `.../artifacts/wesad/wesad-v1/unified/segment-labels.jsonl`

## EmoWear

### Где скачать

1. Dataset DOI: <https://doi.org/10.5281/zenodo.10407278>
2. Descriptor paper: <https://www.nature.com/articles/s41597-024-03429-3>
3. Related repo (code): <https://gitlab.ilabt.imec.be/emowear/colemo>

### Куда положить

- `/Users/kgz/Desktop/p/on-go/data/external/emowear/raw`

### Обязательная проверка

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
PYTHONPATH=src python3 -m dataset_registry.main validate-source \
  --dataset-id emowear \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/emowear/raw
```

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
PYTHONPATH=src python3 -m dataset_registry.main inspect-source \
  --dataset-id emowear \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/emowear/raw
```

## G-REx

### Где скачать

1. Dataset record: <https://zenodo.org/record/8136135>
2. EULA/access form: <https://forms.gle/RmMosk31zvvQRaUH7>
3. Descriptor paper: <https://www.nature.com/articles/s41597-023-02905-6>

### Куда положить

- `/Users/kgz/Desktop/p/on-go/data/external/grex/raw`

### Обязательная проверка

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
PYTHONPATH=src python3 -m dataset_registry.main validate-source \
  --dataset-id grex \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/grex/raw
```

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
PYTHONPATH=src python3 -m dataset_registry.main inspect-source \
  --dataset-id grex \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/grex/raw
```

## DAPPER

### Где скачать

1. Primary Synapse DOI: <https://doi.org/10.7303/syn22418021>
2. Descriptor paper: <https://www.nature.com/articles/s41597-021-00945-4>
3. Additional record DOI (paper metadata): <https://doi.org/10.6084/m9.figshare.13803185>

### Куда положить

- `/Users/kgz/Desktop/p/on-go/data/external/dapper/raw`

### Обязательная проверка

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
PYTHONPATH=src python3 -m dataset_registry.main validate-source \
  --dataset-id dapper \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/dapper/raw
```

```bash
cd /Users/kgz/Desktop/p/on-go/services/dataset-registry
PYTHONPATH=src python3 -m dataset_registry.main inspect-source \
  --dataset-id dapper \
  --source-dir /Users/kgz/Desktop/p/on-go/data/external/dapper/raw
```

## Обязательный тест-прогон после скачивания

Для каждого датасета считаем onboarding завершенным только если:

1. `validate-source` завершился со статусом `passed` или `warning`.
2. `inspect-source` завершился со статусом `passed` или `warning`.
3. Для `wesad` дополнительно успешно выполнен `import-wesad`.
4. В `work-log` добавлена запись о фактическом запуске и результате команды.

## Примечание про статусы `validate-source`

1. `passed` — найден ожидаемый набор маркеров структуры.
2. `warning` — найдена только часть маркеров (допускается, но лучше проверить раскладку вручную).
3. `failed` — структура не соответствует ожидаемой и требует исправления перед импортом.

## Примечание про статусы `inspect-source`

1. `passed` — структура, headers, labels и parseability подтверждены на реальных файлах.
2. `warning` — структура/парсинг в целом пригодны, но обнаружены реальные dataset-specific проблемы или gaps.
3. `failed` — найдено критическое расхождение схемы/headers/parseability; импорт в текущем виде недостоверен.
4. `blocked` — датасет еще не скачан локально, либо для него пока нет реального inspect-run.
