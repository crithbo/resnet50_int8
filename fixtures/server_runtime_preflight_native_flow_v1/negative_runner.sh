#!/usr/bin/env bash
set -euo pipefail
server_root="$1"
test -d "$server_root/install"
stat "$server_root/rtl"
find "$server_root" -name '*.sv'
sha256sum "$server_root/Makefile.tb_NDP_Top_new_phy"
git -C "$server_root" rev-parse HEAD
command -v vcs
make -n -f "$server_root/Makefile.tb_NDP_Top_new_phy" compile
python3 tools/server_compile_environment_gate.py probe
python3 tools/runtime_helper.py preflight
# CODEX_PRODUCTION_LAUNCH
make -f Makefile.tb_NDP_Top_new_phy compile sim
