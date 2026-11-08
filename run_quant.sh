#!/usr/bin/env bash
set -euo pipefail

app_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$app_dir"
export PYTHONHASHSEED=0
exec micromamba run -n quant python GUIkhQuant.py "$@"
