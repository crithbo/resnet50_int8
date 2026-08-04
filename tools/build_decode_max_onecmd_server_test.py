#!/usr/bin/env python3
"""Build a one-command stock-RTL Decode FP32 max server test package."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_probe_test_package import (  # noqa: E402
    MANIFEST_NAME,
    GapProbePackageError,
    _audit_zip,
    _github_reference_identity,
    _records,
    _reference_server_identity,
    _sha256,
    _tree_sha256,
    _write_deterministic_zip,
    _write_lf,
)
from tools.decode_max_server_runtime import preflight_package  # noqa: E402


SCHEMA = "deepseek-decode-max-fp32-stock-rtl-onecmd-package-v2"
INSTALL_NAME = "decode_max_fp32_stockrtl_onecmd_v2"
SOURCE_GRAPH = Path(
    "ndp-sim/model_execplan/output/native_deepseek_fp32_max_control_r1_graph"
)
DEFAULT_OUTPUT_REL = (
    Path("artifacts/operator_config_validation/r5-server-test-packages")
    / INSTALL_NAME
)
INSTALL_PREFIX = f"install/cfg_pkg/{INSTALL_NAME}"
MANDATORY_FILES = [
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
    "ndp-sim/generate_python_golden/README.md",
    "ndp-sim/generate_python_golden/README_gen_data.md",
    "ndp-sim/model_execplan/README.md",
    "ndp-sim/model_execplan/README_op_json.md",
    "ndp-sim/README_SERVER_PACKAGE_LOCAL.md",
    ".agents/plan.md#decode_max_fp32N_fp32N",
]


def _copy_lf(source: Path, destination: Path) -> None:
    _write_lf(
        destination,
        source.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n"),
    )


def _run_script(install_name: str) -> str:
    return f"""#!/usr/bin/env bash
set -u

if [ "$#" -ne 1 ]; then
  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX" >&2
  exit 2
fi
case "$1" in
  /*) ;;
  *)
    echo "NDP_copy path must be absolute: $1" >&2
    exit 2
    ;;
esac

package_root="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
workload_root="${{package_root}}/workload"
runtime_tool="${{package_root}}/package_tools/decode_max_server_runtime.py"
identity_tool="${{package_root}}/package_tools/capture_gap_probe_server_identity.py"
identity_verify_tool="${{package_root}}/package_tools/verify_gap_stock_rtl_identity.py"
package_manifest="${{package_root}}/{MANIFEST_NAME}"
ndp_root="$(cd "$1" && pwd)"
cfg_root="${{ndp_root}}/install/cfg_pkg/{install_name}"
run_dir="${{ndp_root}}/run_{install_name}"
evidence_root="${{ndp_root}}/evidence_{install_name}"
return_dir="${{ndp_root}}/{install_name}_return"
return_zip="${{ndp_root}}/{install_name}_return.zip"
return_sha="${{return_zip}}.sha256"

for required in \
  "${{ndp_root}}/tb_NDP_Top_new_phy.sv" \
  "${{ndp_root}}/native_return_observer.svh" \
  "${{ndp_root}}/Makefile.tb_NDP_Top_new_phy" \
  "${{ndp_root}}/rtl/filelists/NDP_Top_phy_filelist.f"; do
  if [ ! -f "${{required}}" ]; then
    echo "Missing required stock-RTL server input: ${{required}}" >&2
    exit 3
  fi
done
if ! command -v timeout >/dev/null 2>&1; then
  echo "Missing required GNU timeout command" >&2
  exit 3
fi
for fresh_target in \
  "${{cfg_root}}" \
  "${{run_dir}}" \
  "${{evidence_root}}" \
  "${{return_dir}}" \
  "${{return_zip}}" \
  "${{return_sha}}"; do
  if [ -e "${{fresh_target}}" ]; then
    echo "Fresh target already exists; refusing reuse: ${{fresh_target}}" >&2
    exit 4
  fi
done

python3 "${{runtime_tool}}" preflight-package \
  --package-root "${{package_root}}" \
  --install-name "{install_name}" >/dev/null || exit 5
mkdir "${{evidence_root}}"
python3 "${{runtime_tool}}" preflight-package \
  --package-root "${{package_root}}" \
  --install-name "{install_name}" \
  --output "${{evidence_root}}/package_preflight.json" >/dev/null || exit 5

vcs_extra_opts="+incdir+${{ndp_root}}"
server_command="timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=${{run_dir}} VCS_EXTRA_OPTS=${{vcs_extra_opts}} && timeout --foreground --signal=TERM --kill-after=30s 4h ${{run_dir}}/sim_results/simv -l ${{run_dir}}/sim_results/sim.log +vcs+lic+wait +BITSTREAM=install/bitstream.txt +SCA_CFG={INSTALL_PREFIX}/sca_cfg.json +SCA_CFG_D={INSTALL_PREFIX}/sca_cfg_D.json"
printf '%s\\n' "${{server_command}}" > "${{evidence_root}}/server_command.txt"

python3 "${{identity_tool}}" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase pre_install \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_pre_install.json" >/dev/null || exit 5

mkdir -p "${{ndp_root}}/install/cfg_pkg"
mkdir "${{cfg_root}}"
cp -a "${{workload_root}}/." "${{cfg_root}}/"
for slice_id in $(seq -w 0 27); do
  mkdir -p "${{cfg_root}}/readback/slice${{slice_id}}"
done
python3 "${{runtime_tool}}" preflight-installed \
  --package-root "${{package_root}}" \
  --ndp-root "${{ndp_root}}" \
  --install-name "{install_name}" \
  --output "${{evidence_root}}/installed_preflight.json" >/dev/null || exit 5

python3 "${{identity_tool}}" \
  --ndp-root "${{ndp_root}}" \
  --package-manifest "${{package_manifest}}" \
  --install-name "{install_name}" \
  --phase post_install \
  --server-command "${{server_command}}" \
  --output "${{evidence_root}}/server_identity_post_install.json" >/dev/null || exit 5

finalization_complete=0
run_status=125
finalize_partial_return() {{
  shell_status="$1"
  if [ "${{finalization_complete}}" -eq 1 ]; then return; fi
  finalization_complete=1
  set +e
  if [ ! -f "${{evidence_root}}/run_exit_status.txt" ]; then
    if [ "${{run_status}}" -eq 125 ] && [ "${{shell_status}}" -ne 0 ]; then
      run_status="${{shell_status}}"
    fi
    printf '%s\\n' "${{run_status}}" > "${{evidence_root}}/run_exit_status.txt"
  fi
  [ -f "${{evidence_root}}/compile_exit_status.txt" ] || printf '%s\\n' 125 > "${{evidence_root}}/compile_exit_status.txt"
  [ -f "${{evidence_root}}/sim_exit_status.txt" ] || printf '%s\\n' 125 > "${{evidence_root}}/sim_exit_status.txt"
  python3 "${{identity_tool}}" --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" --install-name "{install_name}" --phase post_run --server-command "${{server_command}}" --exit-status "${{run_status}}" --output "${{evidence_root}}/server_identity_post_run.json" >/dev/null
  python3 "${{identity_tool}}" --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" --install-name "{install_name}" --phase post_restore --server-command "${{server_command}}" --exit-status "${{run_status}}" --output "${{evidence_root}}/server_identity_post_restore.json" >/dev/null
  python3 "${{identity_verify_tool}}" --pre-install "${{evidence_root}}/server_identity_pre_install.json" --post-install "${{evidence_root}}/server_identity_post_install.json" --post-run "${{evidence_root}}/server_identity_post_run.json" --post-restore "${{evidence_root}}/server_identity_post_restore.json" --output "${{evidence_root}}/stock_rtl_identity_receipt.json" >/dev/null
  python3 "${{runtime_tool}}" analyze --ndp-root "${{ndp_root}}" --package-root "${{package_root}}" --install-name "{install_name}" --evidence-root "${{evidence_root}}" --run-status "${{run_status}}" --output "${{evidence_root}}/SERVER_RESULT_GATE.json" >/dev/null
  python3 "${{runtime_tool}}" collect --ndp-root "${{ndp_root}}" --package-root "${{package_root}}" --install-name "{install_name}" --evidence-root "${{evidence_root}}" --run-dir "${{run_dir}}" --output-dir "${{ndp_root}}" --run-status "${{run_status}}" --server-command "${{server_command}}" >/dev/null
}}
trap 'finalize_partial_return $?' EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM

cd "${{ndp_root}}"
date +%s > "${{evidence_root}}/run_started_epoch.txt"
set +e
timeout --foreground --signal=TERM --kill-after=30s 2h \
  make -f Makefile.tb_NDP_Top_new_phy compile \
  DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 \
  RUN_DIR="${{run_dir}}" VCS_EXTRA_OPTS="${{vcs_extra_opts}}"
compile_status=$?
printf '%s\\n' "${{compile_status}}" > "${{evidence_root}}/compile_exit_status.txt"
if [ "${{compile_status}}" -eq 0 ]; then
  timeout --foreground --signal=TERM --kill-after=30s 4h \
    "${{run_dir}}/sim_results/simv" \
    -l "${{run_dir}}/sim_results/sim.log" \
    +vcs+lic+wait \
    +BITSTREAM=install/bitstream.txt \
    "+SCA_CFG={INSTALL_PREFIX}/sca_cfg.json" \
    "+SCA_CFG_D={INSTALL_PREFIX}/sca_cfg_D.json"
  sim_status=$?
else
  sim_status=125
fi
printf '%s\\n' "${{sim_status}}" > "${{evidence_root}}/sim_exit_status.txt"
if [ "${{compile_status}}" -ne 0 ]; then run_status="${{compile_status}}"; else run_status="${{sim_status}}"; fi
printf '%s\\n' "${{run_status}}" > "${{evidence_root}}/run_exit_status.txt"

python3 "${{identity_tool}}" --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" --install-name "{install_name}" --phase post_run --server-command "${{server_command}}" --exit-status "${{run_status}}" --output "${{evidence_root}}/server_identity_post_run.json" >/dev/null
post_run_identity_status=$?
python3 "${{identity_tool}}" --ndp-root "${{ndp_root}}" --package-manifest "${{package_manifest}}" --install-name "{install_name}" --phase post_restore --server-command "${{server_command}}" --exit-status "${{run_status}}" --output "${{evidence_root}}/server_identity_post_restore.json" >/dev/null
post_restore_identity_status=$?
python3 "${{identity_verify_tool}}" --pre-install "${{evidence_root}}/server_identity_pre_install.json" --post-install "${{evidence_root}}/server_identity_post_install.json" --post-run "${{evidence_root}}/server_identity_post_run.json" --post-restore "${{evidence_root}}/server_identity_post_restore.json" --output "${{evidence_root}}/stock_rtl_identity_receipt.json" >/dev/null
identity_status=$?
python3 "${{runtime_tool}}" analyze --ndp-root "${{ndp_root}}" --package-root "${{package_root}}" --install-name "{install_name}" --evidence-root "${{evidence_root}}" --run-status "${{run_status}}" --output "${{evidence_root}}/SERVER_RESULT_GATE.json" >/dev/null
analysis_status=$?
python3 "${{runtime_tool}}" collect --ndp-root "${{ndp_root}}" --package-root "${{package_root}}" --install-name "{install_name}" --evidence-root "${{evidence_root}}" --run-dir "${{run_dir}}" --output-dir "${{ndp_root}}" --run-status "${{run_status}}" --server-command "${{server_command}}" >/dev/null
collection_status=$?
finalization_complete=1
trap - EXIT HUP INT TERM
set -e

if [ -f "${{return_zip}}" ] && [ -f "${{return_sha}}" ]; then
  echo "Return ZIP: ${{return_zip}}"
  echo "Return SHA256: ${{return_sha}}"
else
  echo "Return collection did not produce both expected files." >&2
fi
if [ "${{run_status}}" -ne 0 ]; then exit "${{run_status}}"; fi
if [ "${{post_run_identity_status}}" -ne 0 ]; then exit "${{post_run_identity_status}}"; fi
if [ "${{post_restore_identity_status}}" -ne 0 ]; then exit "${{post_restore_identity_status}}"; fi
if [ "${{identity_status}}" -ne 0 ]; then exit "${{identity_status}}"; fi
if [ "${{analysis_status}}" -ne 0 ]; then exit "${{analysis_status}}"; fi
exit "${{collection_status}}"
"""


def _readme() -> str:
    return f"""# Decode FP32 max stock-RTL one-command v2

This is the second, independent server job. It tests the existing DeepSeek
Decode FP32 reduction-max primitive on stock functional RTL. It does not test
or clear the ResNet INT8 MaxPool blocker.

The exact candidate is locally validated only (`candidate_release=false`).
Prior same-operator server evidence is E3; this fresh package has a different
zero-violation placement and must be tested under its own identity.

Run only:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

The script installs a unique namespace, explicitly binds both SCA files,
disables VCD/FSDB, runs in an isolated directory, compares 28 formal one-line
DDR readbacks with independent FP32 golden data, captures stock-RTL identity,
and directly creates:

```text
{INSTALL_NAME}_return.zip
{INSTALL_NAME}_return.zip.sha256
```
"""


def _build_workload(root: Path, package: Path) -> dict[str, Any]:
    source = root / SOURCE_GRAPH
    workload = package / "workload"
    (workload / "install/cfg_pkg").mkdir(parents=True, exist_ok=True)
    _copy_lf(source / "install/execplan.txt", workload / "install/execplan.txt")
    bitstream_name = "op10_decode_max_fp32N_fp32N_bitstream_128b.bin"
    _copy_lf(
        source / "install/cfg_pkg" / bitstream_name,
        workload / "install/cfg_pkg" / bitstream_name,
    )
    sca: dict[str, Any] = {
        "Exec_Base": "0x0000_0800",
        "Exec_Length": 29,
        "Repeat_Num": 1,
        "ExecutionPlan": {
            "base_addr": "0x00000800",
            "path": f"{INSTALL_PREFIX}/install/execplan.txt",
        },
    }
    sca_d: dict[str, Any] = {}
    for slice_id in range(28):
        source_slice = source / f"install/op10/slice{slice_id:02d}"
        target_input = workload / f"install/op10/slice{slice_id:02d}/matrix_A_128bit.txt"
        _copy_lf(source_slice / "matrix_A_linearized_128bit.txt", target_input)
        golden = workload / f"golden/slice{slice_id:02d}/matrix_D_128bit.txt"
        _copy_lf(source_slice / "matrix_D_linearized_128bit.txt", golden)
        slice_base = slice_id << 25
        sca[f"op10_matrixA_slice{slice_id}"] = {
            "base_addr": f"0x{slice_base:08X}",
            "path": (
                f"{INSTALL_PREFIX}/install/op10/slice{slice_id:02d}/"
                "matrix_A_128bit.txt"
            ),
        }
        sca_d[f"op10_matrixD_slice{slice_id}"] = {
            "base_addr": f"0x{slice_base + 0x20:08X}",
            "path": (
                f"{INSTALL_PREFIX}/readback/slice{slice_id:02d}/"
                "matrix_D_128bit.txt"
            ),
            "length": 1,
        }
    sca["op10_config"] = {
        "base_addr": "0x00000400",
        "path": f"{INSTALL_PREFIX}/install/cfg_pkg/{bitstream_name}",
    }
    _write_lf(
        workload / "sca_cfg.json",
        json.dumps(sca, ensure_ascii=False, indent=2) + "\n",
    )
    _write_lf(
        workload / "sca_cfg_D.json",
        json.dumps(sca_d, ensure_ascii=False, indent=2) + "\n",
    )
    for source_relative, target_relative in (
        (
            "jsons/op10_decode_max_fp32N_fp32N.json",
            "validation/source_config.json",
        ),
        (
            "config/op10/mapping_review.json",
            "validation/mapping_review.json",
        ),
        (
            "native_deepseek_fp32_max_control_r1_graph_validation.json",
            "validation/SOURCE_LOCAL_VALIDATION.json",
        ),
        (
            "native_deepseek_fp32_max_control_r1_graph_files_sha256.json",
            "validation/SOURCE_FILE_IDENTITY.json",
        ),
    ):
        _copy_lf(source / source_relative, package / target_relative)
    return {
        "source_graph": SOURCE_GRAPH.as_posix(),
        "source_validation_sha256": _sha256(
            source / "native_deepseek_fp32_max_control_r1_graph_validation.json"
        ),
        "source_config_sha256": _sha256(
            source / "jsons/op10_decode_max_fp32N_fp32N.json"
        ),
        "execplan_sha256": _sha256(workload / "install/execplan.txt"),
        "bitstream_sha256": _sha256(
            workload / "install/cfg_pkg" / bitstream_name
        ),
        "slice_count": 28,
        "sca_payload_count": 30,
        "sca_d_readback_count": 28,
        "readback_length_128bit_words": 1,
    }


def build_package(project_root: Path, output: Path) -> dict[str, Any]:
    root = project_root.resolve()
    package = output.resolve()
    zip_path = package.with_suffix(".zip")
    sha_path = Path(f"{zip_path}.sha256")
    for target in (package, zip_path, sha_path):
        if target.exists():
            raise GapProbePackageError(f"output must be fresh: {target}")
    package.parent.mkdir(parents=True, exist_ok=True)
    source_report = _build_workload(root, package)
    for relative in (
        Path("tools/decode_max_server_runtime.py"),
        Path("tools/capture_gap_probe_server_identity.py"),
        Path("tools/verify_gap_stock_rtl_identity.py"),
    ):
        _copy_lf(root / relative, package / "package_tools" / relative.name)
    _write_lf(package / "PREPARE_AND_RUN.sh", _run_script(INSTALL_NAME))
    _write_lf(package / "README.md", _readme())
    records = _records(package, exclude_manifest=True)
    manifest = {
        "schema": SCHEMA,
        "status": "one_command_server_test_package_ready",
        "install_name": INSTALL_NAME,
        "candidate_release": False,
        "release_gate_passed": False,
        "evidence_level": "E2_LOCAL_ONLY_PRIOR_SAME_OPERATOR_E3",
        "single_hypothesis": (
            "stock-RTL DeepSeek Decode FP32 reduction max completes and its "
            "28 formal DDR readbacks equal independent golden data"
        ),
        "claim_boundary": (
            "does not exercise ResNet INT8 MaxPool/int8_max and cannot clear "
            "that orthogonal RTL blocker"
        ),
        "superseded_local_drafts": [
            {
                "name": "decode_max_fp32_stockrtl_onecmd_v1",
                "released": False,
                "status": "local_preflight_incomplete",
                "reason": (
                    "did not fail fast when the TB-required "
                    "native_return_observer.svh include was absent"
                ),
            }
        ],
        "server_operation": {
            "only_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
            "manual_parameters_beyond_ndp_root": 0,
            "automatic_install_validate_run_analyze_collect": True,
        },
        "source_workload": source_report,
        "rtl_policy": {
            "mode": "server_original_unmodified",
            "functional_rtl_file_count": 0,
            "rtl_or_tb_source_file_included": False,
            "functional_rtl_write_requested": False,
            "waveforms_explicitly_disabled": {
                "DUMP_VCD": 0,
                "DUMP_FSDB": 0,
                "TB_DUMP_FSDB": 0,
            },
            "stock_rtl_identity_receipt_required": True,
        },
        "runtime_policy": {
            "unique_config_namespace": INSTALL_PREFIX,
            "unique_run_dir": f"run_{INSTALL_NAME}",
            "unique_evidence_dir": f"evidence_{INSTALL_NAME}",
            "fresh_targets_required": True,
            "sca_and_sca_d_explicit": True,
            "repeat_num": 1,
            "start_comp_count": 1,
            "compile_timeout": "2h",
            "simulation_timeout": "4h",
            "partial_return_on_timeout_or_signal": True,
        },
        "dynamic_gate_policy": {
            "formal_d": "28 slices x one full 128-bit row exact golden",
            "loader": "30 matrices loaded and 28 matrices dumped",
            "lifecycle": "one start, one completion, natural finish",
            "stock_rtl_identity": "pre/post/post-run/noop-final byte stability",
        },
        "return_policy": {
            "allowlist_only": True,
            "direct_zip_and_sidecar": True,
            "waveforms_forbidden": True,
            "build_trees_forbidden": True,
            "nested_archives_forbidden": True,
            "zip_limit_bytes": 8 * 1024 * 1024,
        },
        "rules": {
            "mandatory_files_read": MANDATORY_FILES,
            "formal_readback_not_internal_monitor_only": True,
            "generic_structure_is_not_semantic_release": True,
        },
        "reference_server_identity": _reference_server_identity(root),
        "github_reference_identity": _github_reference_identity(root),
        "run_entry": "PREPARE_AND_RUN.sh",
        "payload_file_count": len(records),
        "payload_tree_sha256": _tree_sha256(records),
        "files": records,
    }
    _write_lf(
        package / MANIFEST_NAME,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )
    preflight_package(package, INSTALL_NAME)
    _write_deterministic_zip(package, zip_path)
    digest = _sha256(zip_path)
    _write_lf(sha_path, f"{digest}  {zip_path.name}\n")
    return {
        **manifest,
        "directory": package.as_posix(),
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sha256_file": sha_path.as_posix(),
    }


def validate_package(project_root: Path, output: Path) -> dict[str, Any]:
    root = project_root.resolve()
    package = output.resolve()
    zip_path = package.with_suffix(".zip")
    sha_path = Path(f"{zip_path}.sha256")
    for required in (package, zip_path, sha_path, package / MANIFEST_NAME):
        if not required.exists():
            raise GapProbePackageError(f"package input missing: {required}")
    manifest = json.loads((package / MANIFEST_NAME).read_text(encoding="utf-8"))
    actual = _records(package, exclude_manifest=True)
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("install_name") != INSTALL_NAME
        or manifest.get("files") != actual
        or manifest.get("payload_tree_sha256") != _tree_sha256(actual)
    ):
        raise GapProbePackageError("manifest exact-set identity differs")
    forbidden = [
        relative
        for relative in actual
        if Path(relative).suffix.lower()
        in {
            ".v",
            ".sv",
            ".vh",
            ".svh",
            ".zip",
            ".tar",
            ".tgz",
            ".gz",
            ".7z",
            ".vcd",
            ".fsdb",
        }
    ]
    if forbidden:
        raise GapProbePackageError(f"forbidden package payload: {forbidden[0]}")
    script = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    for token in (
        f"+SCA_CFG={INSTALL_PREFIX}/sca_cfg.json",
        f"+SCA_CFG_D={INSTALL_PREFIX}/sca_cfg_D.json",
        "DUMP_VCD=0",
        "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0",
        "trap 'finalize_partial_return $?' EXIT",
        "timeout --foreground --signal=TERM --kill-after=30s 4h",
    ):
        if token not in script:
            raise GapProbePackageError(f"run script token missing: {token}")
    preflight = preflight_package(package, INSTALL_NAME)
    zip_audit = _audit_zip(package, zip_path)
    digest = _sha256(zip_path)
    if sha_path.read_text(encoding="ascii") != f"{digest}  {zip_path.name}\n":
        raise GapProbePackageError("SHA256 sidecar differs")
    if manifest.get("reference_server_identity") != _reference_server_identity(root):
        raise GapProbePackageError("local RTL reference identity differs")
    if manifest.get("github_reference_identity") != _github_reference_identity(root):
        raise GapProbePackageError("GitHub reference identity differs")
    return {
        "schema": SCHEMA,
        "status": "one_command_server_test_package_validated",
        "directory": package.as_posix(),
        "manifest_sha256": _sha256(package / MANIFEST_NAME),
        "payload_file_count": len(actual),
        "payload_tree_sha256": _tree_sha256(actual),
        "functional_rtl_file_count": 0,
        "preflight": preflight,
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "zip_audit": zip_audit,
        "sidecar": sha_path.as_posix(),
        "server_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "expected_return": [
            f"{INSTALL_NAME}_return.zip",
            f"{INSTALL_NAME}_return.zip.sha256",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / DEFAULT_OUTPUT_REL)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        report = (
            validate_package(ROOT, output)
            if args.validate_only
            else build_package(ROOT, output)
        )
    except Exception as exc:
        print(f"decode-max one-command package failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
