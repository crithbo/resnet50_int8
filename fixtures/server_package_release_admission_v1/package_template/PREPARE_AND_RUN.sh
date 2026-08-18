#!/usr/bin/env bash
set -euo pipefail
package_root="$(cd "$(dirname "$0")" && pwd)"
evidence_root="${package_root}/evidence"
mkdir -p "$evidence_root"
set +e
python3 "$package_root/package_tools/package_runtime.py" preflight --package-root "$package_root" >"$evidence_root/package_preflight.stdout.log" 2>"$evidence_root/package_preflight.stderr.log"
package_preflight_exit=$?
set -e
printf '%s\n' "$package_preflight_exit" >"$evidence_root/package_preflight.exit.txt"
if [ "$package_preflight_exit" -ne 0 ]; then
  printf '%s\n' '{"classification":"COMPILE_NOT_STARTED","preflight_evidence_retained":true}' >"$evidence_root/compile_not_started_core.json"
  exit "$package_preflight_exit"
fi
# CODEX_PRODUCTION_LAUNCH
exit 86
