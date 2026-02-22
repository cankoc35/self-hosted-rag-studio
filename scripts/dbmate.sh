#!/usr/bin/env bash
set -euo pipefail

# Run dbmate via Docker Compose (no local install required).
#
# Examples:
#   scripts/dbmate.sh up
#   scripts/dbmate.sh status
#   scripts/dbmate.sh new create_documents

if [[ "${1:-up}" == "up" ]]; then
  docker compose --profile tools run --rm dbmate --wait up
  exit 0
fi

docker compose --profile tools run --rm dbmate "$@"

