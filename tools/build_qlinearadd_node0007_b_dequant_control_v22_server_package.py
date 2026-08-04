from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records, write_json
from tools import build_qlinearadd_node0007_b_dequant_isolated_v21_server_package as v21


INSTALL_NAME = "r5_qadd_n7_b_dequant_control_v22"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
PARSER = ROOT / "tools/qlinearadd_node0007_b_dequant_control_canonical_v22.py"
VALIDATION = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
SOURCE_SHA = v21.SOURCE_SHA


class BuildError(ValueError):
    pass


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise BuildError(f"preimage count differs for {path}: {text.count(old)}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def build_directory(destination: Path) -> Path:
    v21.INSTALL_NAME = INSTALL_NAME
    v21.PARSER = PARSER
    package = v21.build_directory(destination)

    native = package / "tb_probe/native_return_observer.svh"
    replace_once(
        native,
        '\n`include "qlinearadd_node0007_fp32_ingress_compilefix_v20.svh"\n',
        "\n",
    )
    for relative in (
        "tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh",
        "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh",
    ):
        package.joinpath(relative).unlink()

    runner = package / "PREPARE_AND_RUN.sh"
    replace_once(
        runner,
        "  grep -q '+QADD_FP32_INGRESS_OBSERVER' "
        '"$evidence_root/actual_simulator_argv.txt" && feature_argv=true',
        "  grep -q '+RETURN_OBS_DEEP' "
        '"$evidence_root/actual_simulator_argv.txt" && feature_argv=true',
    )
    replace_once(
        runner,
        "  grep -q 'QADD_FP32_INGRESS_OBSERVER_V19_TIME0' "
        '"$run_root/sim_results/sim.log" && feature_time0=true',
        "  grep -q '\\[RETURN_OBSERVER\\] enabled for slice' "
        '"$run_root/sim_results/sim.log" && feature_time0=true',
    )
    replace_once(
        runner,
        "  grep -q '# QADD_FP32_INGRESS_OBSERVER_V19 ' "
        '"$observer_log" && feature_snapshot=true',
        "  grep -q '# Native NDP return observer v4' "
        '"$observer_log" && feature_snapshot=true',
    )
    replace_once(
        runner,
        "  printf 'feature=QADD_FP32_INGRESS_OBSERVER\\nargv_enabled=%s\\n"
        "time0_marker=%s\\nreturned_snapshot_marker=%s\\n'",
        "  printf 'feature=B_DEQUANT_BASE_OBSERVER_CONTROL\\nargv_enabled=%s\\n"
        "time0_marker=%s\\nreturned_snapshot_marker=%s\\n'",
    )
    replace_once(runner, "  +QADD_FP32_INGRESS_OBSERVER\n", "")

    parser_target = package / "package_tools/qlinearadd_progress_canonical_decision.py"
    shutil.copy2(PARSER, parser_target)
    contract_path = package / "diagnostics/progress_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract.update(
        {
            "schema": "qlinearadd-node0007-b-dequant-control-v22",
            "feature_plusarg": "+RETURN_OBSERVER +RETURN_OBS_DEEP",
            "feature_return_marker": "# Native NDP return observer v4",
            "feature_time0_marker": "[RETURN_OBSERVER] enabled for slice",
            "target_stage": "op_b_dequant",
            "stage_count": 1,
            "qualified_internal_counters": [
                "base_req_accept",
                "base_rdata_accept",
                "base_wdata_accept",
                "base_buffer_write_read",
                "base_gexec_gconfig",
            ],
            "unique_error_interval": (
                "control experiment for v20 observer-induced event storm: "
                "isolated op_b_dequant with the previously passing v18 base observer"
            ),
            "observer_regression_control": {
                "removed_fp32_ingress_tail": True,
                "removed_ga_capture_shim": True,
                "functional_rtl_modified": False,
                "config_bitstream_modified": False,
            },
        }
    )
    write_json(contract_path, contract)

    package.joinpath("README.md").write_text(
        "# QLinearAdd node0007 B-dequant observer-regression control v22\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX. This executes only the frozen "
        "op_b_dequant stage with its original B input and hardware-produced "
        "B scratch. The v20 FP32-ingress tail and GA-capture shim are absent; "
        "the previously passing v18 base observer remains. This A/B control "
        "tests whether the v20 instrumentation caused the VCS INFL_DELTA event "
        "storm. Full-chain QLinearAdd validation is still required.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("observer_compilefix_v20", None)
    manifest.update(
        {
            "schema": "qlinearadd-node0007-b-dequant-control-server-package-v22",
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_READY_NOT_RUN",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "functional_fix": False,
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "observer-regression A/B control for isolated B-dequant only; "
                "no full QAdd, numeric, production, performance or RTL claim"
            ),
            "successor_reason": {
                "last_proven_good": (
                    "V18_OP_B_DEQUANT_COMP_FINISH_AND_RELOCATION_COMP_FINISH"
                ),
                "first_divergence": (
                    "V20_OP_B_DEQUANT_VCS_INFL_DELTA_AFTER_NEW_FP32_OBSERVER"
                ),
                "unique_root_cause_proven": False,
                "root_cause_scope": "V20_PACKAGE_LOCAL_OBSERVER_REGRESSION_CONTROL",
            },
            "split_execution_v22": {
                "stage": "op_b_dequant",
                "repeat_num": 1,
                "exec_length": 29,
                "original_input_only": True,
                "host_precomputed_internal_tensor": False,
                "hardware_output": "B_SCALED scratch",
                "heartbeat_cycles": 16384,
                "simulation_timeout_hours": 2,
                "fp32_ingress_tail_present": False,
                "ga_capture_shim_present": False,
                "full_chain_required_after_diagnosis": True,
            },
            "configuration_modified": False,
            "execution_scope_modified": True,
            "timeout_modified": True,
            "server_tb_or_observer_entries": 2,
        }
    )
    manifest.pop("split_execution_v21", None)
    manifest["canonical_decision_contract"].update(
        {
            "schema": "qlinearadd-node0007-b-dequant-control-canonical-v22",
            "parser_sha256": sha(parser_target),
            "target_stage": "op_b_dequant",
            "expected_stage_count": 1,
            "base_qualified_progress_only": True,
            "fp32_ingress_tail_required": False,
        }
    )
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_"
        "b_dequant_control_v22_server_package.py"
    )
    manifest["final_zip_rule_self_audit"]["validator"] = (
        "tools/validate_qlinearadd_node0007_"
        "b_dequant_control_v22_server_package.py"
    )
    manifest["final_zip_rule_self_audit"]["report"] = (
        "artifacts/operator_config_validation/"
        "r5-qlinearadd-node0007-b-dequant-control-v22/"
        "final_zip_self_audit.json"
    )
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)

    runtime = package / "package_tools/qlinearadd_node0007_server_runtime.py"
    check = subprocess.run(
        [
            sys.executable,
            str(runtime),
            "preflight",
            "--package-root",
            str(package),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode:
        raise BuildError(f"package-local preflight failed: {check.stderr}")
    return package


def build_once(destination: Path) -> tuple[Path, Path, dict[str, Any]]:
    package = build_directory(destination)
    output = destination / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, output)
    return package, output, file_records(package, exclude_manifest=False)


def main() -> int:
    package = PACKAGE_ROOT / INSTALL_NAME
    output = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(output) + ".sha256")
    for path in (package, output, sidecar, VALIDATION):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, output, records = build_once(PACKAGE_ROOT)
        with tempfile.TemporaryDirectory(prefix="qadd-v22-repeat-") as raw:
            _, repeat_zip, repeat_records = build_once(Path(raw))
            repeat_sha = sha(repeat_zip)
        digest = sha(output)
        if records != repeat_records or digest != repeat_sha:
            raise BuildError("deterministic rebuild differs")
        sidecar.write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
        receipt = {
            "schema": "qlinearadd-node0007-b-dequant-control-build-v22",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "package": package.relative_to(ROOT).as_posix(),
            "zip": output.relative_to(ROOT).as_posix(),
            "zip_sha256": digest,
            "zip_bytes": output.stat().st_size,
            "sidecar": sidecar.relative_to(ROOT).as_posix(),
            "sidecar_sha256": sha(sidecar),
            "source_zip_sha256": SOURCE_SHA,
            "file_count": len(records),
            "repeated_build": {
                "package_tree_equal": records == repeat_records,
                "zip_equal": digest == repeat_sha,
                "repeat_zip_sha256": repeat_sha,
            },
        }
        write_json(VALIDATION, receipt)
    except Exception as exc:
        print(f"build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
