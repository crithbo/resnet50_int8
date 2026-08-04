from __future__ import annotations

import hashlib
import json
import re
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


INSTALL_NAME = "r5_qadd_n7_b_dequant_isolated_v21"
SOURCE_NAME = "r5_qadd_n7_fp32_ingress_compilefix_v20"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_DIR = PACKAGE_ROOT / SOURCE_NAME
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51"
RETURN_REPORT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fp32-ingress-compilefix-v20-return-analysis/report.json"
)
PARSER = ROOT / "tools/qlinearadd_node0007_b_dequant_canonical_v21.py"
VALIDATION = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
EVIDENCE_ROOT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-b-dequant-isolated-v21"
)
RULES = {
    "generation_index": (
        ROOT / ".agents/rules/生成前必读索引.md",
        "db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5",
    ),
    "server_package_rule": (
        ROOT / ".agents/rules/服务器测试包生成规则.md",
        "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48",
    ),
    "qlinearadd_rule": (
        ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
        "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f",
    ),
    "exact_uint8_tail_rule": (
        ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    ),
}


class BuildError(ValueError):
    pass


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def rule_ids(path: Path) -> list[str]:
    return sorted(set(re.findall(r"CDA-[A-Z0-9-]+", path.read_text(encoding="utf-8"))))


def assert_receipts() -> None:
    expected = {SOURCE_ZIP: SOURCE_SHA, **{path: digest for path, digest in RULES.values()}}
    drift = {
        str(path): {"expected": wanted, "actual": sha(path) if path.is_file() else None}
        for path, wanted in expected.items()
        if not path.is_file() or sha(path) != wanted
    }
    if drift:
        raise BuildError(f"immutable receipt drift: {drift}")
    for path in (SOURCE_DIR, RETURN_REPORT, PARSER):
        if not path.exists():
            raise BuildError(f"required input absent: {path}")


def replace_namespace(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".bin", ".npy", ".npz", ".png"}:
            continue
        payload = path.read_bytes()
        path.write_bytes(payload.replace(SOURCE_NAME.encode(), INSTALL_NAME.encode()))


def patch_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise BuildError(f"preimage count differs for {path}: {text.count(old)}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def build_directory(destination: Path) -> Path:
    assert_receipts()
    package = destination / INSTALL_NAME
    if package.exists():
        raise BuildError(f"destination exists: {package}")
    shutil.copytree(SOURCE_DIR, package)
    replace_namespace(package)

    sca_path = package / "workload/runtime/sca_cfg.json"
    sca = json.loads(sca_path.read_text(encoding="utf-8"))
    sca["Repeat_Num"] = 1
    sca["Exec_Length"] = 29
    sca["ExecutionPlan"]["path"] = (
        f"install/cfg_pkg/{INSTALL_NAME}/install/execplan_op_b_dequant.txt"
    )
    write_json(sca_path, sca)

    runtime = package / "package_tools/qlinearadd_node0007_server_runtime.py"
    patch_once(
        runtime,
        'if sca.get("Repeat_Num") != 6 or len(sca_d) != 28:',
        'if sca.get("Repeat_Num") != 1 or len(sca_d) != 28:',
    )
    patch_once(
        runtime,
        'raise RuntimeGateError("six-stage or 28-readback contract differs")',
        'raise RuntimeGateError("isolated-one-stage or 28-readback contract differs")',
    )

    package_parser = package / "package_tools/qlinearadd_progress_canonical_decision.py"
    shutil.copy2(PARSER, package_parser)
    contract_path = package / "diagnostics/progress_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract.update(
        {
            "schema": "qlinearadd-node0007-b-dequant-isolated-localization-v21",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "target_stage": "op_b_dequant",
            "stage_count": 1,
            "heartbeat_cycles": 16384,
            "minimum_monotonic_windows_for_progress": 1,
            "qualified_internal_counters": [
                "mse0_request_accept",
                "mse0_rdata_accept",
                "mse0_to_buffer0_accept",
                "buffer0_write_accept",
                "buffer0_arm_read_accept",
                "buffer0_array_delivery",
                "ga_operand0_capture",
                "ga_consumer_accept",
                "ga_first_output",
            ],
            "level_snapshots_not_counted_as_progress": [
                "buffer0_any_valid",
                "buffer0_arm_ready",
                "unpaired_valid_or_ready",
            ],
            "unique_error_interval": (
                "isolated op_b_dequant start through the VCS INFL_DELTA "
                "frontier near active cycle 154000"
            ),
            "split_execution": {
                "host_precomputed_internal_tensor": False,
                "input": "original B edge payload already present in frozen workload",
                "output": "hardware-produced B_SCALED scratch",
                "final_full_chain_required": True,
            },
        }
    )
    write_json(contract_path, contract)

    runner = package / "PREPARE_AND_RUN.sh"
    patch_once(
        runner,
        "+RETURN_OBS_HEARTBEAT_CYCLES=262144",
        "+RETURN_OBS_HEARTBEAT_CYCLES=16384",
    )
    patch_once(
        runner,
        'timeout --foreground --signal=TERM --kill-after=30s 12h "$simv"',
        'timeout --foreground --signal=TERM --kill-after=30s 2h "$simv"',
    )
    patch_once(
        runner,
        "printf 'timeout --foreground --signal=TERM --kill-after=30s 12h %q'",
        "printf 'timeout --foreground --signal=TERM --kill-after=30s 2h %q'",
    )

    package.joinpath("README.md").write_text(
        "# QLinearAdd node0007 isolated B-dequant diagnostic v21\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "This is DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX. It executes only the frozen "
        "op_b_dequant stage against the original B input, emits the original "
        "hardware B_SCALED scratch, and uses 16,384-cycle low-rate qualified "
        "snapshots. It does not replay a host-precomputed internal tensor. "
        "The full six-stage QLinearAdd chain remains required after the blocker "
        "is closed.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "qlinearadd-node0007-b-dequant-isolated-server-package-v21",
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_READY_NOT_RUN",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "functional_fix": False,
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "isolates the frozen B-dequant stage and localizes its returned "
                "zero-delay frontier; no full QAdd, numeric, E4/E5, production, "
                "performance or functional-RTL claim"
            ),
            "source_package": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_SHA,
                "status": "QUARANTINED_DYNAMIC_ZERO_DELAY_LOOP",
                "numeric_w3_qparams_tail_golden_unchanged": True,
            },
            "successor_reason": {
                "last_proven_good": (
                    "OP_A_DEQUANT_COMP_FINISH_AND_OP_B_DEQUANT_QUALIFIED_PROGRESS"
                ),
                "first_divergence": (
                    "OP_B_DEQUANT_VCS_INFL_DELTA_AT_17020861875PS_"
                    "ABOUT_154000_ACTIVE_CYCLES"
                ),
                "unique_root_cause_proven": False,
                "root_cause_scope": "B_DEQUANT_ZERO_DELAY_FRONTIER",
            },
            "split_execution_v21": {
                "stage": "op_b_dequant",
                "repeat_num": 1,
                "exec_length": 29,
                "selected_execplan": "install/execplan_op_b_dequant.txt",
                "original_input_only": True,
                "host_precomputed_internal_tensor": False,
                "hardware_output": "B_SCALED scratch",
                "heartbeat_cycles": 16384,
                "simulation_timeout_hours": 2,
                "full_chain_required_after_diagnosis": True,
            },
            "configuration_modified": False,
            "execution_scope_modified": True,
            "timeout_modified": True,
            "server_tb_or_observer_entries": 4,
        }
    )
    manifest["canonical_decision_contract"].update(
        {
            "schema": "qlinearadd-node0007-b-dequant-canonical-v21",
            "parser_path": (
                "package_tools/qlinearadd_progress_canonical_decision.py"
            ),
            "parser_sha256": sha(package_parser),
            "ordered_final_stage_scope": True,
            "target_stage": "op_b_dequant",
            "expected_stage_count": 1,
            "individual_mse_progress_is_not_full_qadd_progress": True,
        }
    )
    manifest["provenance"].update(
        {
            "generator": (
                "tools/build_qlinearadd_node0007_"
                "b_dequant_isolated_v21_server_package.py"
            ),
            "v20_return_analysis_report": {
                "path": RETURN_REPORT.relative_to(ROOT).as_posix(),
                "sha256": sha(RETURN_REPORT),
            },
        }
    )
    manifest["final_zip_rule_self_audit"].update(
        {
            "validator": (
                "tools/validate_qlinearadd_node0007_"
                "b_dequant_isolated_v21_server_package.py"
            ),
            "report": (
                "artifacts/operator_config_validation/"
                "r5-qlinearadd-node0007-b-dequant-isolated-v21/"
                "final_zip_self_audit.json"
            ),
            "rule_receipts": {
                key: {
                    "path": path.relative_to(ROOT).as_posix(),
                    "sha256": digest,
                    "current_match": True,
                }
                for key, (path, digest) in RULES.items()
            },
            "applicable_server_rule_ids": rule_ids(RULES["server_package_rule"][0]),
            "applicable_qlinearadd_rule_ids": rule_ids(RULES["qlinearadd_rule"][0]),
            "applicable_exact_tail_rule_ids": rule_ids(
                RULES["exact_uint8_tail_rule"][0]
            ),
        }
    )
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    local_preflight = subprocess.run(
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
    if local_preflight.returncode != 0:
        raise BuildError(f"package-local preflight failed: {local_preflight.stderr}")
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
        with tempfile.TemporaryDirectory(prefix="qadd-v21-repeat-") as raw:
            _, repeat_zip, repeat_records = build_once(Path(raw))
            repeat_sha = sha(repeat_zip)
        digest = sha(output)
        if records != repeat_records or digest != repeat_sha:
            raise BuildError("deterministic rebuild differs")
        sidecar.write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
        receipt = {
            "schema": "qlinearadd-node0007-b-dequant-isolated-build-v21",
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
