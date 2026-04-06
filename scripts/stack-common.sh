ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
if [[ -z "${ON_GO_MODEL_VOLUME:-}" ]]; then
  _b="$ROOT/data/external/wesad/artifacts/wesad/wesad-v1/m7-9-runtime-bundle-export"
  if [[ -f "$_b/model-bundle.manifest.json" ]]; then
    export ON_GO_MODEL_VOLUME="$_b"
  fi
fi
STACK_PROFILES=()
if [[ "${ON_GO_ENABLE_TLS_PROXY:-}" == "1" ]]; then
  STACK_PROFILES+=(--profile tls)
fi
