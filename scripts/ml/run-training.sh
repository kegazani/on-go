#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [ -n "$ON_GO_ROOT" ]; then ROOT="$ON_GO_ROOT"; fi

DATA_EXTERNAL="${DATA_EXTERNAL:-$ROOT/data/external}"
DATASET_ID="${DATASET_ID:-wesad}"
DATASET_VERSION="${DATASET_VERSION:-wesad-v1}"
PREPROCESSING_VERSION="${PREPROCESSING_VERSION:-e2-v1}"
RUN_KIND="${RUN_KIND:-watch-only-wesad}"
MIN_CONFIDENCE="${MIN_CONFIDENCE:-0.7}"
CALIBRATION_SEGMENTS="${CALIBRATION_SEGMENTS:-2}"
ADAPTATION_WEIGHT="${ADAPTATION_WEIGHT:-5}"
NO_MLFLOW="${NO_MLFLOW:-}"
SAVE_MODELS="${SAVE_MODELS:-}"

if [ "$RUN_KIND" = "g3-2-multi-dataset" ]; then
  OUTPUT_DIR="$DATA_EXTERNAL"
  SEGMENT_LABELS="$DATA_EXTERNAL/wesad/artifacts/wesad/wesad-v1/unified/segment-labels.jsonl"
  SPLIT_MANIFEST="$DATA_EXTERNAL/wesad/artifacts/wesad/wesad-v1/manifest/split-manifest.json"
  WESAD_RAW="$DATA_EXTERNAL/wesad/raw"
else
  ARTIFACTS_ROOT="$DATA_EXTERNAL/$DATASET_ID/artifacts"
  SEGMENT_LABELS="$ARTIFACTS_ROOT/$DATASET_ID/$DATASET_VERSION/unified/segment-labels.jsonl"
  SPLIT_MANIFEST="$ARTIFACTS_ROOT/$DATASET_ID/$DATASET_VERSION/manifest/split-manifest.json"
  WESAD_RAW="$DATA_EXTERNAL/wesad/raw"
  OUTPUT_DIR="$ARTIFACTS_ROOT"
  if [ ! -f "$SEGMENT_LABELS" ]; then
    echo "Missing segment-labels: $SEGMENT_LABELS" >&2
    echo "Run scripts/ml/run-dataset-build.sh first" >&2
    exit 1
  fi
  if [ ! -f "$SPLIT_MANIFEST" ]; then
    echo "Missing split-manifest: $SPLIT_MANIFEST" >&2
    exit 1
  fi
fi

EXTRA=()
[ -n "$NO_MLFLOW" ] && EXTRA+=(--no-mlflow)
[ -n "$SAVE_MODELS" ] && [ "$RUN_KIND" = "watch-only-wesad" ] && EXTRA+=(--save-models)

cd "$ROOT/services/modeling-baselines"
PYTHONPATH=src python3 -m modeling_baselines.main \
  --run-kind "$RUN_KIND" \
  --segment-labels "$SEGMENT_LABELS" \
  --split-manifest "$SPLIT_MANIFEST" \
  --wesad-raw-root "$WESAD_RAW" \
  --output-dir "$OUTPUT_DIR" \
  --dataset-id "$DATASET_ID" \
  --dataset-version "$DATASET_VERSION" \
  --preprocessing-version "$PREPROCESSING_VERSION" \
  --min-confidence "$MIN_CONFIDENCE" \
  --calibration-segments "$CALIBRATION_SEGMENTS" \
  --adaptation-weight "$ADAPTATION_WEIGHT" \
  "${EXTRA[@]}"

echo "Training complete: $RUN_KIND on $DATASET_ID:$DATASET_VERSION"
