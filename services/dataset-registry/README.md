# dataset-registry

Сервисный модуль фазы `F2/F2.1/F2.2` для следующих задач:

1. вести `dataset registry` (версия датасета, provenance, split strategy, labels/modalities);
2. выполнять первый внешний импорт (`WESAD`) в unified internal schema.
3. выполнять расширенный импорт `G-REx`, `EmoWear`, `DAPPER` в unified schema для multi-dataset harmonization.
3. валидировать локальную раскладку source-датасетов перед импортом.
4. выполнять глубокую инспекцию реальных source-датасетов: headers, label schema и parseability.

## Команды CLI

Из `services/dataset-registry`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 1) Регистрация dataset metadata

```bash
dataset-registry register \
  --registry-path registry/datasets.jsonl \
  --dataset-id wesad \
  --dataset-version wesad-v1 \
  --source WESAD \
  --ingestion-script-version wesad-import-v1 \
  --preprocessing-version e2-v1 \
  --metadata-object datasets/wesad/wesad-v1/manifest/dataset-metadata.json \
  --target-track activity/context \
  --target-track arousal \
  --label activity_label \
  --label arousal_score
```

### 2) Импорт WESAD

```bash
dataset-registry import-wesad \
  --registry-path registry/datasets.jsonl \
  --source-dir /path/to/WESAD \
  --output-dir /path/to/on-go-artifacts \
  --dataset-version wesad-v1 \
  --preprocessing-version e2-v1
```

### 2.1) Импорт EmoWear / G-REx / DAPPER

```bash
dataset-registry import-emowear \
  --registry-path registry/datasets.jsonl \
  --source-dir /path/to/EmoWear \
  --output-dir /path/to/on-go-artifacts \
  --dataset-version emowear-v1 \
  --preprocessing-version e2-v1

dataset-registry import-grex \
  --registry-path registry/datasets.jsonl \
  --source-dir /path/to/G-REx \
  --output-dir /path/to/on-go-artifacts \
  --dataset-version grex-v1 \
  --preprocessing-version e2-v1

dataset-registry import-dapper \
  --registry-path registry/datasets.jsonl \
  --source-dir /path/to/DAPPER \
  --output-dir /path/to/on-go-artifacts \
  --dataset-version dapper-v1 \
  --preprocessing-version e2-v1
```

### 3) Просмотр registry

```bash
dataset-registry list --registry-path registry/datasets.jsonl
```

### 4) Каталог датасетов и ссылки на скачивание

```bash
dataset-registry dataset-catalog
```

### 5) Валидация source-папки датасета

```bash
dataset-registry validate-source --dataset-id wesad --source-dir /path/to/WESAD
dataset-registry validate-source --dataset-id emowear --source-dir /path/to/EmoWear
dataset-registry validate-source --dataset-id grex --source-dir /path/to/G-REx
dataset-registry validate-source --dataset-id dapper --source-dir /path/to/DAPPER
```

### 6) Глубокая инспекция source-датасета

```bash
dataset-registry inspect-source --dataset-id wesad --source-dir /path/to/WESAD
dataset-registry inspect-source --dataset-id emowear --source-dir /path/to/EmoWear
dataset-registry inspect-source --dataset-id grex --source-dir /path/to/G-REx
dataset-registry inspect-source --dataset-id dapper --source-dir /path/to/DAPPER
```

## Формат артефактов импорта

`import-wesad` создает:

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

Mapping `WESAD` в canonical labels (`A2/A3`):

1. `1 baseline -> seated_rest/rest, arousal=2, valence=5`
2. `2 stress -> focused_cognitive_task/cognitive, arousal=8, valence=3`
3. `3 amusement -> focused_cognitive_task/cognitive, arousal=6, valence=8`
4. `4 meditation -> recovery_rest/recovery, arousal=2, valence=7`

`import-wesad` сохраняет contiguous non-zero `wesad_state` segments.
Если во входных label-sequences встречаются source values вне базового mapping (`5/6/7`),
они сохраняются как `unknown` segments с provenance-полями:

1. `source_segment_start_index`
2. `source_segment_end_index`
3. `source_sample_count`

## Ограничения текущего инкремента F2

1. Импорт строит unified metadata и segment-level mapping, но не копирует полные raw streams WESAD в ingest storage.
2. Для label extraction поддержаны простой CSV (`label(s).csv`) и python2-compatible pickle (`S*.pkl`) варианты структуры subject-папки.
3. Для production ingestion потребуется расширить adapter на полный per-sample pipeline и quality checks.
4. Для `EmoWear` и `DAPPER` текущий импорт использует proxy-mapping в `activity/arousal` и помечает provenance `source=proxy_mapping`; эти labels нельзя трактовать как claim-grade ground truth.
