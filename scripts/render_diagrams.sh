#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v dot >/dev/null 2>&1; then
  echo "error: 'dot' not found. Install Graphviz and re-run." >&2
  exit 1
fi

dot -Tpng "${ROOT_DIR}/docs/diagrams/pipeline.dot" -o "${ROOT_DIR}/docs/diagrams/pipeline.png" -Gdpi=144
echo "Rendered: docs/diagrams/pipeline.png"

