#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

BUILD_DATASET="${BUILD_DATASET:-1}"

if [ "$BUILD_DATASET" = "1" ]; then
  "$SCRIPT_DIR/run-dataset-build.sh"
fi

"$SCRIPT_DIR/run-training.sh"
