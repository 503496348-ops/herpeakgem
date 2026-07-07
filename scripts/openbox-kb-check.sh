#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

printf '[openbox] Python compile check\n'
python -m py_compile herpeakgem_cli/kb.py

printf '[openbox] CLI KB unit tests\n'
python -m pytest tests/cli/test_kb.py -q

printf '[openbox] PASS\n'
