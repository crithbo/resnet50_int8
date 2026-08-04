"""Build the minimal DeepSeek Ring4 server smoke overlay.

This diagnostic revision deliberately stops at server liveness.  It reuses the
four upstream-generated Ring4 configuration streams and the already generated
Clock/Load/Start prefix, but it does not install a completion barrier, golden
data, output sentinel, readback regions, or numeric-return analyzer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from resnet50_pipeline.hardware_simulation_frontend import load_execplan_commands


REVISION = "dg4smoke"
INSTALL_NAME = "hwop-deepseek-ring-dg4smoke"
SOURCE_CONFIG_SHA256 = "6a2ca9f2edd2e9c7b8ebbb558a84dd23c8e583781f8a8ac01c213b78c6737e91"
SOURCE_EXECPLAN_SHA256 = "c7a85234423be65b1669b7ac0995b8e75833dd29801deec0540be21bb1cd9a36"
SOURCE_BITSTREAM_SHA256 = {
    0: "03ca22f08a415b89bf934aa52f81b66a6532f060d91d965a16fd395d9111bbed",
    1: "6313115831a1c2ed1108a51c8e95a9524904cef0536c8bbdf5c5d994f7a450b9",
    2: "52734b869cec5e7f6c0f9d94435c6454a7b41133e41ea2b16f327468b99af020",
    3: "bfdd796a7b912b3d58a4b15590c1ccd9c34521ca4d6b31101f0144430ca8eec1",
}
CONFIG_BASES = (0x00010000, 0x00010400, 0x00010800, 0x00010C00)
INPUT_BASES = (0x00000000, 0x02000000, 0x04000000, 0x06000000)
EXEC_BASE = 0x00011000
ZERO_INPUT_BYTES = 0x8000


RUNNER = r'''#!/usr/bin/env bash
set -Eeuo pipefail

runner_source="${BASH_SOURCE[0]}"
runner_dir="${runner_source%/*}"
if [ "${runner_dir}" = "${runner_source}" ]; then runner_dir="."; fi
cd -- "${runner_dir}"

revision="dg4smoke"
install_root="install/cfg_pkg/hwop-deepseek-ring-dg4smoke"
sca_cfg="${install_root}/sca_cfg.json"
clock_tcl="${install_root}/dg4smoke_reserved_axi_clock.tcl"
make_override="${install_root}/dg4smoke_runtime_no_archive.mk"
smoke_timeout="${SMOKE_TIMEOUT:-6h}"
result_root="run/${revision}_result"
result_archive="run/sim_results_${revision}.zip"

for command_name in make vcs timeout tee zip mkdir mv ln dirname date tail cp rm; do
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    echo "ERROR: required command is unavailable: ${command_name}" >&2
    exit 20
  fi
done

for required_file in \
  Makefile.tb_NDP_Top_new_phy \
  tb_NDP_Top_new_phy.sv \
  rtl/filelists/NDP_Top_phy_filelist.f \
  "${sca_cfg}" \
  "${install_root}/sca_cfg_D.json" \
  "${clock_tcl}" \
  "${make_override}"; do
  if [ ! -f "${required_file}" ]; then
    echo "ERROR: required file is missing: ${required_file}" >&2
    exit 20
  fi
done

archive_epoch="$(date +%s)"
preexisting_root="run/archive/preexisting-${revision}-${archive_epoch}"
if [ -e sim_results ] || [ -e run/sim_results ] || [ -e "${result_root}" ] || [ -e "${result_archive}" ]; then
  mkdir -p "${preexisting_root}"
  if [ -e sim_results ]; then mv -- sim_results "${preexisting_root}/sim_results"; fi
  if [ -e run/sim_results ]; then mv -- run/sim_results "${preexisting_root}/run_sim_results"; fi
  if [ -e "${result_root}" ]; then mv -- "${result_root}" "${preexisting_root}/${revision}_result"; fi
  if [ -e "${result_archive}" ]; then mv -- "${result_archive}" "${preexisting_root}/sim_results_${revision}.zip"; fi
fi

# VCS uses this as a disposable compile cache.  Remove it so the diagnostic
# logging define below is guaranteed to reach the new executable.
rm -rf -- run/csrc
mkdir -p sim_results run/sim_results

sink_runtime_log() {
  local relative_path="$1"
  local sink_path="sim_results/${relative_path}"
  mkdir -p "$(dirname "${sink_path}")"
  ln -s /dev/null "${sink_path}"
}

# The active RTL opens these files directly.  Sink verbose per-slice diagnostics
# while retaining gexec2slice.log, compile.log, sim.log, and the console log.
for ((slice_id = 0; slice_id < 28; slice_id++)); do
  sink_runtime_log "gconfig2slice/slice${slice_id}/gconfig2slice.log"
  sink_runtime_log "nrm_buf_write/slice${slice_id}/nrm2buf_write.log"
  sink_runtime_log "nrm_buf_read/slice${slice_id}/nrm2buf_read.log"
  for mse_id in 0 1 2 3 4; do
    for channel in req wdata rdata; do
      sink_runtime_log "local/slice${slice_id}/local_mse${mse_id}_${channel}.log"
    done
  done
  for bank_id in 0 1 2 3; do
    sink_runtime_log "local/slice${slice_id}/hub/local_hub_req_bank${bank_id}.log"
    sink_runtime_log "bank_frame/slice${slice_id}/bank${bank_id}_frame.log"
    sink_runtime_log "bank_frame/slice${slice_id}/bank${bank_id}_mc_rdata.log"
    sink_runtime_log "bank_frame/slice${slice_id}/bank${bank_id}_full.log"
  done
  for channel in req wdata rdata; do
    sink_runtime_log "global/slice${slice_id}/global_req_${channel}.log"
  done
done
sink_runtime_log "local_summary/slice_all/local_summary.log"

console_log="run/sim_results/${revision}_console.log"
run_argv=(
  make
  -f Makefile.tb_NDP_Top_new_phy
  -f "${make_override}"
  compile dg4smoke_sim_no_archive
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0
  "VCS_EXTRA_OPTS=-debug_access+all +define+BANK_FRAME_LOG_SLICE_START_ONLY"
  "SIM_EXTRA_OPTS=-ucli -i ${clock_tcl}"
  "PLUSARGS=+SCA_CFG=${sca_cfg}"
)

echo "SMOKE_SCOPE: control/liveness only; no numeric validation"
echo "SMOKE_TIMEOUT: ${smoke_timeout}"
printf 'RUN:'
printf ' %q' "${run_argv[@]}"
printf '\n'

unset MAKEFLAGS MAKEFILES GNUMAKEFLAGS MFLAGS MAKELEVEL
set +e
timeout --signal=TERM --kill-after=5m "${smoke_timeout}" \
  "${run_argv[@]}" </dev/null 2>&1 | tee "${console_log}"
pipeline_status=("${PIPESTATUS[@]}")
run_status=${pipeline_status[0]}
tee_status=${pipeline_status[1]}
set -e
if [ "${tee_status}" -ne 0 ]; then run_status="${tee_status}"; fi

mkdir -p "${result_root}/logs" "${result_root}/config"
printf '%s\n' "${run_status}" > "${result_root}/${revision}_exit_status.txt"
printf '%s\n' "${smoke_timeout}" > "${result_root}/smoke_timeout.txt"
cp -- "${sca_cfg}" "${install_root}/sca_cfg_D.json" \
  "${install_root}/install/execplan.txt" "${result_root}/config/"

copy_log_tail() {
  local source_path="$1"
  local output_name="$2"
  if [ -f "${source_path}" ]; then
    tail -c 4194304 "${source_path}" > "${result_root}/logs/${output_name}"
  fi
}
copy_log_tail "${console_log}" "${revision}_console_tail.log"
copy_log_tail "run/sim_results/compile.log" "compile_tail.log"
copy_log_tail "run/sim_results/sim.log" "sim_tail.log"
copy_log_tail "sim_results/gexec2slice/slice_all/gexec2slice.log" "gexec2slice_tail.log"

set +e
(cd run && zip -q -r "sim_results_${revision}.zip" "${revision}_result")
zip_status=$?
set -e
if [ "${zip_status}" -ne 0 ]; then
  echo "ERROR: could not create ${result_archive}" >&2
  exit 21
fi
echo "Return archive: ${result_archive}"
exit "${run_status}"
'''


CLOCK_TCL = """set reserved_clock_path \"tb_NDP_Top_new_phy.u_NDP_Top_new.m_axi_reserved_clk\"
echo \"RESERVED_AXI_CLOCK_FORCE_BEGIN\"
if {[catch {force $reserved_clock_path 0 0ns, 1 1.25ns -repeat 2.5ns} force_error]} {
  echo \"RESERVED_AXI_CLOCK_FORCE_FAILED\"
  echo $force_error
  quit
} else {
  echo \"RESERVED_AXI_CLOCK_FORCE_APPLIED\"
  run
}
"""


MAKE_OVERRIDE = """.PHONY: dg4smoke_sim_no_archive
dg4smoke_sim_no_archive: $(SIMV)
\t@echo \"Running minimal DeepSeek Ring4 smoke simulation...\"
\t@sim_status=0; \\
\t$(SIMV) $(SIM_OPTS) $(SIM_EXTRA_OPTS) || sim_status=$$?; \\
\techo \"Simulation exit status: $$sim_status\"; \\
\texit $$sim_status
"""


README = """DeepSeek Ring4 DG4SMOKE

Purpose: verify that the server can compile, start all four Ring4 slices, pass
the former single-slice startup deadlock point, and exit naturally.

This is intentionally NOT a numeric validation package.  Inputs are zero, the
output is not read back, and no golden/sentinel/barrier/run1-run2 audit contract
is installed.

Runtime topology:
  Clock mask 0xF
  Load_Config mask 0x1, 0x2, 0x4, 0x8
  Start_Comp mask 0xF

The four configuration bitstreams are LF-normalized copies of the outputs from
the unchanged upstream ndp-sim run_all_slices.py flow.  Server-only local glue is
limited to the zero preload, SCA files, 400 MHz reserved AXI clock driver,
verbose-log sinks, no-archive make target, and runner.

Run from the NDP_copy01 server directory:
  SMOKE_TIMEOUT=6h bash RUN_SERVER_DG4SMOKE.sh

Return:
  run/sim_results_dg4smoke.zip
"""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8"))


def _copy_lf(source: Path, destination: Path) -> None:
    _write_lf(destination, source.read_text(encoding="ascii"))


def _zip_overlay(source_root: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(source_root.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file():
                continue
            relative = path.relative_to(source_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if path.name == "RUN_SERVER_DG4SMOKE.sh" else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compresslevel=9)


def build(project_root: Path, output_root: Path) -> dict[str, object]:
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    if output_root.exists():
        raise RuntimeError(f"refusing to replace existing smoke overlay: {output_root}")

    upstream_json = project_root / "upstream_recheck_20260722/ndp-sim/jsons/prefill_gemm_ring_4slice.json"
    if _sha256(upstream_json) != SOURCE_CONFIG_SHA256:
        raise RuntimeError("upstream Ring4 JSON identity differs")

    v2_root = project_root / "artifacts/w5/deepseek_ring_gemm_control/v2/hardware_execplan_package"
    source_exec = v2_root / "install/execplan.txt"
    if _sha256(source_exec) != SOURCE_EXECPLAN_SHA256:
        raise RuntimeError("source Ring4 execplan identity differs")

    ndp_root = output_root / "NDP_copy01"
    install_root = ndp_root / "install/cfg_pkg" / INSTALL_NAME
    cfg_root = install_root / "install/cfg_pkg"
    input_root = install_root / "install/control_input"
    cfg_root.mkdir(parents=True)
    input_root.mkdir(parents=True)

    source_lines = source_exec.read_text(encoding="ascii").splitlines()
    if len(source_lines) != 4:
        raise RuntimeError("source Ring4 execplan does not contain four 128-bit beats")
    smoke_exec = install_root / "install/execplan.txt"
    _write_lf(smoke_exec, "\n".join(source_lines[:3]) + "\n")
    commands = load_execplan_commands(smoke_exec, expected_beats=3)
    observed = [(command.kind, int(command.fields.get("slice_mask", 0))) for command in commands]
    expected = [
        ("clock_enable", 0xF),
        ("load_config", 0x1),
        ("load_config", 0x2),
        ("load_config", 0x4),
        ("load_config", 0x8),
        ("start_comp", 0xF),
    ]
    if observed != expected:
        raise RuntimeError(f"minimal Ring4 command sequence differs: {observed}")

    config_paths: list[Path] = []
    for slice_id in range(4):
        filename = f"prefill_gemm_ring_4slice_slice{slice_id}_bitstream_128b.bin"
        source = v2_root / "install/cfg_pkg" / filename
        if _sha256(source) != SOURCE_BITSTREAM_SHA256[slice_id]:
            raise RuntimeError(f"source slice{slice_id} bitstream identity differs")
        destination = cfg_root / filename
        _copy_lf(source, destination)
        config_paths.append(destination)

    zero_path = input_root / "ring_zero_32KiB.txt"
    zero_line = "0" * 128 + "\n"
    _write_lf(zero_path, zero_line * (ZERO_INPUT_BYTES // 16))

    sca: dict[str, object] = {
        "Exec_Base": f"0x{EXEC_BASE:08X}",
        "Exec_Length": 3,
        "ExecutionPlan": {
            "base_addr": f"0x{EXEC_BASE:08X}",
            "path": f"install/cfg_pkg/{INSTALL_NAME}/install/execplan.txt",
        },
        "Repeat_Num": 1,
    }
    for slice_id, (config_base, config_path) in enumerate(zip(CONFIG_BASES, config_paths, strict=True)):
        sca[f"ring_slice{slice_id}_config"] = {
            "base_addr": f"0x{config_base:08X}",
            "path": f"install/cfg_pkg/{INSTALL_NAME}/install/cfg_pkg/{config_path.name}",
        }
    for slice_id, input_base in enumerate(INPUT_BASES):
        sca[f"ring_slice{slice_id}_zero_input"] = {
            "base_addr": f"0x{input_base:08X}",
            "path": f"install/cfg_pkg/{INSTALL_NAME}/install/control_input/{zero_path.name}",
        }
    _write_lf(install_root / "sca_cfg.json", json.dumps(sca, indent=2) + "\n")
    _write_lf(install_root / "sca_cfg_D.json", "{}\n")
    _write_lf(install_root / "dg4smoke_reserved_axi_clock.tcl", CLOCK_TCL)
    _write_lf(install_root / "dg4smoke_runtime_no_archive.mk", MAKE_OVERRIDE)
    _write_lf(ndp_root / "RUN_SERVER_DG4SMOKE.sh", RUNNER)
    _write_lf(output_root / "README_SERVER_DG4SMOKE.txt", README)

    zip_path = output_root.with_suffix(".zip")
    sidecar = zip_path.with_suffix(zip_path.suffix + ".sha256")
    _zip_overlay(output_root, zip_path)
    zip_sha256 = _sha256(zip_path)
    _write_lf(sidecar, f"{zip_sha256}  {zip_path.name}\n")
    return {
        "status": "minimal_control_liveness_smoke_overlay_generated",
        "revision": REVISION,
        "numeric_validation": False,
        "exec_128bit_lines": 3,
        "preload_count": 9,
        "bitstream_count": 4,
        "overlay_file_count": sum(1 for path in output_root.rglob("*") if path.is_file()),
        "zip": str(zip_path),
        "zip_sha256": zip_sha256,
        "sidecar": str(sidecar),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/w5/dg/server_overlay_dg4smoke"),
    )
    args = parser.parse_args()
    result = build(args.project_root, args.output)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
