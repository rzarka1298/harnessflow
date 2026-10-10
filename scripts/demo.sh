#!/usr/bin/env bash
# Backwards-compatible entrypoint with bounded startup and owned process cleanup.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$REPO_ROOT/scripts/local-dev.py" --demo "$@"
