#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -x "$ROOT_DIR/ADC-Debugger" ]]; then
    export LD_LIBRARY_PATH="$ROOT_DIR/_internal${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
    exec "$ROOT_DIR/ADC-Debugger" "$@"
fi

export LD_LIBRARY_PATH="$ROOT_DIR/runtime/linux/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec python3 "$ROOT_DIR/main.py" "$@"
