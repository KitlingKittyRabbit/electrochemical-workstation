#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt -r build-requirements.txt
python3 -m PyInstaller --clean --noconfirm ADC-Debugger.spec
cp run_linux.sh dist/ADC-Debugger/run_linux.sh
chmod +x dist/ADC-Debugger/run_linux.sh
printf 'Built: %s\n' "$(pwd)/dist/ADC-Debugger/ADC-Debugger"
