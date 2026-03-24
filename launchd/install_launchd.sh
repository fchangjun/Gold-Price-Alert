#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"
TEMPLATE_PATH="${SCRIPT_DIR}/com.fchangjun.gold-price-alert.plist.template"
TARGET_DIR="${HOME}/Library/LaunchAgents"
TARGET_PATH="${TARGET_DIR}/com.fchangjun.gold-price-alert.plist"

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3 not found in PATH. Set PYTHON_BIN=/absolute/path/to/python3 and retry." >&2
  exit 1
fi

mkdir -p "${PROJECT_DIR}/logs"
mkdir -p "${TARGET_DIR}"

python3 - <<'PY' "${TEMPLATE_PATH}" "${TARGET_PATH}" "${PROJECT_DIR}" "${PYTHON_BIN}"
from pathlib import Path
import sys

template_path = Path(sys.argv[1])
target_path = Path(sys.argv[2])
project_dir = sys.argv[3]
python_bin = sys.argv[4]

content = template_path.read_text(encoding="utf-8")
content = content.replace("__PROJECT_DIR__", project_dir)
content = content.replace("__PYTHON_PATH__", python_bin)
target_path.write_text(content, encoding="utf-8")
PY

launchctl unload "${TARGET_PATH}" 2>/dev/null || true
launchctl load "${TARGET_PATH}"

echo "Installed launch agent:"
echo "  ${TARGET_PATH}"
echo "Python:"
echo "  ${PYTHON_BIN}"
echo "Project:"
echo "  ${PROJECT_DIR}"
