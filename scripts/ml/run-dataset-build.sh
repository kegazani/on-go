#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [ -n "$ON_GO_ROOT" ]; then ROOT="$ON_GO_ROOT"; fi

DATA_EXTERNAL="${DATA_EXTERNAL:-$ROOT/data/external}"
REGISTRY_PATH="${REGISTRY_PATH:-$ROOT/data/external/registry/datasets.jsonl}"
DATASET_ID="${DATASET_ID:-wesad}"
DATASET_VERSION="${DATASET_VERSION:-wesad-v1}"
PREPROCESSING_VERSION="${PREPROCESSING_VERSION:-e2-v1}"

mkdir -p "$(dirname "$REGISTRY_PATH")"

cd "$ROOT/services/dataset-registry"

OUTPUT_BASE="$DATA_EXTERNAL/$DATASET_ID/artifacts"

case "$DATASET_ID" in
  wesad)
    PYTHONPATH=src python3 -m dataset_registry.main import-wesad \
      --registry-path "$REGISTRY_PATH" \
      --source-dir "$DATA_EXTERNAL/wesad/raw" \
      --output-dir "$OUTPUT_BASE" \
      --dataset-version "$DATASET_VERSION" \
      --preprocessing-version "$PREPROCESSING_VERSION"
    ;;
  emowear)
    PYTHONPATH=src python3 -m dataset_registry.main import-emowear \
      --registry-path "$REGISTRY_PATH" \
      --source-dir "$DATA_EXTERNAL/emowear/raw" \
      --output-dir "$OUTPUT_BASE" \
      --dataset-version "$DATASET_VERSION" \
      --preprocessing-version "$PREPROCESSING_VERSION"
    ;;
  grex)
    PYTHONPATH=src python3 -m dataset_registry.main import-grex \
      --registry-path "$REGISTRY_PATH" \
      --source-dir "$DATA_EXTERNAL/grex/raw" \
      --output-dir "$OUTPUT_BASE" \
      --dataset-version "$DATASET_VERSION" \
      --preprocessing-version "$PREPROCESSING_VERSION"
    ;;
  dapper)
    PYTHONPATH=src python3 -m dataset_registry.main import-dapper \
      --registry-path "$REGISTRY_PATH" \
      --source-dir "$DATA_EXTERNAL/dapper/raw" \
      --output-dir "$OUTPUT_BASE" \
      --dataset-version "$DATASET_VERSION" \
      --preprocessing-version "$PREPROCESSING_VERSION"
    ;;
  *)
    echo "Unknown DATASET_ID=$DATASET_ID" >&2
    exit 1
    ;;
esac

echo "Dataset build complete: $DATASET_ID:$DATASET_VERSION"
