#!/usr/bin/env bash
set -euo pipefail
server_root="$1"
package_id="demo"
trap 'printf "%s\n" "partial return" >&2' EXIT HUP INT TERM
cd "$server_root"
mkdir -p "install/cfg_pkg/$package_id" "install/codex_runs/$package_id/attempt"
# CODEX_PRODUCTION_LAUNCH
make -f Makefile.tb_NDP_Top_new_phy compile sim SCA_CFG="install/cfg_pkg/$package_id/sca_cfg.json"
if test -f "install/codex_runs/$package_id/attempt/sim.log"; then
  printf "%s\n" "collect post-launch log"
fi
