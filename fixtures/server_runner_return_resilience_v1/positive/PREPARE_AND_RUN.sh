#!/usr/bin/env bash
set -Eeuo pipefail
server_root="${1:?server root required}"
package_id="synthetic_positive"
bootstrap_root="$server_root/install/codex_runs/$package_id/bootstrap-001"
compile_argv_json="$bootstrap_root/compile_argv.json"
compile_source_identity_json="$bootstrap_root/compile_source_identity.json"
compile_exit_txt="$bootstrap_root/compile_exit.txt"
compile_driver_log="$bootstrap_root/compile_driver.log"
compile_first_error_txt="$bootstrap_root/compile_first_error.txt"
compile_log_head_txt="$bootstrap_root/compile_log_head.txt"
compile_log_tail_txt="$bootstrap_root/compile_log_tail.txt"
return_allowlist="compile_argv.json compile_source_identity.json compile_exit.txt compile_driver.log compile_first_error.txt compile_log_head.txt compile_log_tail.txt"
finalize() { printf '%s\n' "$return_allowlist" >/dev/null; }
trap finalize EXIT HUP INT TERM
mkdir -p "$bootstrap_root"
run_root="$server_root/install/codex_runs/$package_id/attempt-001"
printf '%s\n' '["make","compile"]' >"$compile_argv_json"
printf '%s\n' '{"filelist":"rtl.f"}' >"$compile_source_identity_json"
: >"$compile_driver_log"
make compile >"$compile_driver_log" 2>&1
compile_rc=$?
printf '%s\n' "$compile_rc" >"$compile_exit_txt"
head -n 80 "$compile_driver_log" >"$compile_log_head_txt"
tail -n 80 "$compile_driver_log" >"$compile_log_tail_txt"
grep -m1 -E 'error:|Error-|fatal:' "$compile_driver_log" >"$compile_first_error_txt" || true
printf '%s\n' "$run_root" >/dev/null

