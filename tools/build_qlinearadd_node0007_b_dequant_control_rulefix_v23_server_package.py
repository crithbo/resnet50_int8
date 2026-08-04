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


INSTALL_NAME = "r5_qadd_n7_bctrl_v23"
SOURCE_NAME = "r5_qadd_n7_b_dequant_control_v22"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_DIR = PACKAGE_ROOT / SOURCE_NAME
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "4a51be0ab59b0ff8c0754de68f11d7f3d1328b6fe012b3945468b787d2b11fd5"
VALIDATION = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
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


def patch_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise BuildError(f"preimage count differs for {path}: {text.count(old)}")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def assert_receipts() -> None:
    expected = {SOURCE_ZIP: SOURCE_SHA, **{path: digest for path, digest in RULES.values()}}
    drift = {
        str(path): {"expected": wanted, "actual": sha(path) if path.is_file() else None}
        for path, wanted in expected.items()
        if not path.is_file() or sha(path) != wanted
    }
    if drift:
        raise BuildError(f"immutable receipt drift: {drift}")
    if not SOURCE_DIR.is_dir():
        raise BuildError("source v22 directory absent")


def replace_namespace(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".bin", ".npy", ".npz", ".png"}:
            continue
        path.write_bytes(
            path.read_bytes().replace(SOURCE_NAME.encode(), INSTALL_NAME.encode())
        )


def build_directory(destination: Path) -> Path:
    assert_receipts()
    package = destination / INSTALL_NAME
    if package.exists():
        raise BuildError(f"destination exists: {package}")
    shutil.copytree(SOURCE_DIR, package)
    replace_namespace(package)

    runner = package / "PREPARE_AND_RUN.sh"
    patch_once(
        runner,
        "  grep -q '+RETURN_OBS_DEEP' "
        '"$evidence_root/actual_simulator_argv.txt" && feature_argv=true',
        "  if [ -s \"$evidence_root/actual_simulator_argv.txt\" ] && "
        "grep -q '+RETURN_OBS_DEEP' "
        '"$evidence_root/actual_simulator_argv.txt"; then feature_argv=true; fi',
    )
    patch_once(
        runner,
        "  grep -q '\\[RETURN_OBSERVER\\] enabled for slice' "
        '"$run_root/sim_results/sim.log" && feature_time0=true',
        "  if [ -s \"$run_root/sim_results/sim.log\" ] && "
        "grep -q '\\[RETURN_OBSERVER\\] enabled for slice' "
        '"$run_root/sim_results/sim.log"; then feature_time0=true; fi',
    )
    patch_once(
        runner,
        "  grep -q '# Native NDP return observer v4' "
        '"$observer_log" && feature_snapshot=true',
        "  if [ -s \"$observer_log\" ] && "
        "grep -q '# Native NDP return observer v4' "
        '"$observer_log"; then feature_snapshot=true; fi',
    )

    parser = package / "package_tools/qlinearadd_progress_canonical_decision.py"
    patch_once(
        parser,
        '    text = observer.read_text(encoding="utf-8", errors="replace")',
        '    text = (observer.read_text(encoding="utf-8", errors="replace") '
        'if observer.is_file() else "")',
    )

    package.joinpath("README.md").write_text(
        "# QLinearAdd node0007 B-dequant control rulefix v23\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX. This is the byte-fresh successor "
        "to quarantined v22. The B-only execution, original B input, hardware "
        "B scratch, v18 base observer, 16,384-cycle cadence, timeout, numeric "
        "assets and functional RTL are unchanged. Only compile-failure "
        "finalizer guards and fail-closed canonical handling for a missing "
        "observer log are repaired. Final-ZIP HDL syntax/scope evidence is "
        "external to the ZIP and is generated from these exact bytes.\n",
        encoding="utf-8",
        newline="\n",
    )

    native = package / "tb_probe/native_return_observer.svh"
    tail = package / "tb_probe/qlinearadd_node0007_first_request_observer_tail_v9.svh"
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "qlinearadd-node0007-b-dequant-control-rulefix-server-package-v23",
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_READY_NOT_RUN",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "functional_fix": False,
            "candidate_release": False,
            "evidence_level": "E2_LOCAL_ONLY",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "repairs v22 package-local finalizer and validation escape only; "
                "B-only observer-regression control semantics remain unchanged"
            ),
            "source_package": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_SHA,
                "status": "QUARANTINED_FINAL_ZIP_AUDIT_OVERCLAIM",
                "numeric_w3_qparams_tail_workload_config_golden_unchanged": True,
            },
            "successor_reason": {
                "last_proven_good": (
                    "V22_B_ONLY_CONTROL_CONTENT_VALID_BUT_RELEASE_AUDIT_INVALID"
                ),
                "first_divergence": (
                    "V22_MISSING_PACKAGE_LOCAL_HDL_GATE_AND_COMPILE_STUB_STDERR_DIAGNOSTICS"
                ),
                "unique_root_cause_proven": True,
                "root_cause_scope": "PACKAGE_RUNNER_AND_FINAL_ZIP_VALIDATOR_ONLY",
            },
            "runner_finalizer_rulefix_v23": {
                "guard_missing_simulator_argv_before_grep": True,
                "guard_missing_sim_log_before_grep": True,
                "guard_missing_observer_log_before_grep": True,
                "missing_observer_canonical_fail_closed": True,
                "functional_rtl_modified": False,
                "execution_scope_modified": False,
                "timeout_modified": False,
            },
            "package_local_hdl_syntax_scope_contract": {
                "rule_id": (
                    "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-"
                    "SYNTAX-SCOPE-POSITIVE-001"
                ),
                "members": [
                    {
                        "relative_path": "tb_probe/native_return_observer.svh",
                        "bytes": native.stat().st_size,
                        "sha256": sha(native),
                        "role": "package-local observer body",
                    },
                    {
                        "relative_path": (
                            "tb_probe/"
                            "qlinearadd_node0007_first_request_observer_tail_v9.svh"
                        ),
                        "bytes": tail.stat().st_size,
                        "sha256": sha(tail),
                        "role": "included first-request qualified tail",
                    },
                ],
                "include_order": [
                    "package-local +incdir tb_probe",
                    "native_return_observer.svh",
                    "qlinearadd_node0007_first_request_observer_tail_v9.svh",
                ],
                "compile_macro_profile": "+define+NATIVE_RETURN_OBSERVER_ENABLE",
                "required_state_prefixes": ["return_obs_", "qadd_fr_"],
                "required_negative_controls": [
                    "delete_declaration",
                    "misspell_consumer_use",
                    "delete_qualified_update",
                ],
            },
        }
    )
    manifest.pop("split_execution_v22", None)
    manifest["split_execution_v23"] = {
        "stage": "op_b_dequant",
        "repeat_num": 1,
        "exec_length": 29,
        "original_input_only": True,
        "host_precomputed_internal_tensor": False,
        "hardware_output": "B_SCALED scratch",
        "heartbeat_cycles": 16384,
        "simulation_timeout_hours": 2,
        "v18_base_observer_retained": True,
        "full_chain_required_after_diagnosis": True,
    }
    manifest["canonical_decision_contract"]["parser_sha256"] = sha(parser)
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_"
        "b_dequant_control_rulefix_v23_server_package.py"
    )
    audit = manifest["final_zip_rule_self_audit"]
    audit.update(
        {
            "validator": (
                "tools/validate_qlinearadd_node0007_"
                "b_dequant_control_rulefix_v23_server_package.py"
            ),
            "report": (
                "artifacts/operator_config_validation/"
                "r5-qlinearadd-node0007-b-dequant-control-rulefix-v23/"
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
        with tempfile.TemporaryDirectory(prefix="qadd-v23-repeat-") as raw:
            _, repeat_zip, repeat_records = build_once(Path(raw))
            repeat_sha = sha(repeat_zip)
        digest = sha(output)
        if records != repeat_records or digest != repeat_sha:
            raise BuildError("deterministic rebuild differs")
        sidecar.write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
        receipt = {
            "schema": "qlinearadd-node0007-b-dequant-control-rulefix-build-v23",
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
