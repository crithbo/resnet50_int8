#!/usr/bin/env bash
set -Eeuo pipefail
server_root="${1:?server root required}"
package_id="synthetic_missing_evidence"
bootstrap_root="$server_root/install/codex_runs/$package_id/bootstrap-001"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
return_allowlist="compile_exit.txt compile_driver.log"
finalize() { printf '%s\n' "$return_allowlist" >/dev/null; }
trap finalize EXIT HUP INT TERM
mkdir -p "$bootstrap_root"
run_root="$server_root/install/codex_runs/$package_id/attempt-001"
make compile >"$compile_driver_log" 2>&1
compile_rc=$?
printf '%s\n' "$compile_rc" >"$compile_exit_txt"
printf '%s\n' "$run_root" >/dev/null

