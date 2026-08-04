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


INSTALL_NAME = "r5_qadd_n7_bctrl_v24"
SOURCE_NAME = "r5_qadd_n7_bctrl_v23"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_DIR = PACKAGE_ROOT / SOURCE_NAME
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA = "cabc6682be6ca0aa913b5ea3d3d719d88770e0548cf5bf4eb2ec1e4774ecd70f"
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


def replace_namespace(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() in {".bin", ".npy", ".npz", ".png"}:
            continue
        path.write_bytes(
            path.read_bytes().replace(SOURCE_NAME.encode(), INSTALL_NAME.encode())
        )


def build_directory(destination: Path) -> Path:
    expected = {SOURCE_ZIP: SOURCE_SHA, **{path: digest for path, digest in RULES.values()}}
    drift = {
        str(path): {"expected": wanted, "actual": sha(path) if path.is_file() else None}
        for path, wanted in expected.items()
        if not path.is_file() or sha(path) != wanted
    }
    if drift:
        raise BuildError(f"immutable receipt drift: {drift}")
    package = destination / INSTALL_NAME
    if package.exists():
        raise BuildError(f"destination exists: {package}")
    shutil.copytree(SOURCE_DIR, package)
    replace_namespace(package)

    runner = package / "PREPARE_AND_RUN.sh"
    marker = (
        'mkdir -p "$cfg_root" "$run_root/sim_results/return_observer" '
        '"$evidence_root"\n'
    )
    placeholders = marker + (
        "printf '# SIMULATION_NOT_STARTED_COMPILE_NOT_PASSED\\n' "
        '>"$run_root/sim_results/sim.log"\n'
        "printf 'SIMULATION_NOT_STARTED_COMPILE_NOT_PASSED\\n' "
        '>"$evidence_root/actual_simulator_argv.txt"\n'
        "printf '# OBSERVER_NOT_STARTED_COMPILE_NOT_PASSED\\n' "
        '>"$observer_log"\n'
    )
    patch_once(runner, marker, placeholders)
    package.joinpath("README.md").write_text(
        "# QLinearAdd node0007 B-dequant control rulefix v24\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX. B-only execution and all numeric, "
        "configuration, observer HDL, timeout and functional RTL bytes remain "
        "frozen from v23. Before compile, the runner creates explicit "
        "NOT_STARTED_COMPILE_NOT_PASSED receipts for sim.log, simulator argv "
        "and observer log so a compile-stub return is complete and unambiguous; "
        "a real simulation overwrites them.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "qlinearadd-node0007-b-dequant-control-rulefix-server-package-v24",
            "install_name": INSTALL_NAME,
            "source_package": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_SHA,
                "status": "QUARANTINED_COMPILE_STUB_RETURN_REQUIRED_FILES_ABSENT",
                "numeric_w3_qparams_tail_workload_config_golden_unchanged": True,
            },
            "successor_reason": {
                "last_proven_good": (
                    "V23_FINALIZER_STDERR_ZERO_AND_ARTIFACTS_PRESENT"
                ),
                "first_divergence": (
                    "V23_COMPILE_STUB_RETURN_MISSING_SIM_LOG_ARGV_OBSERVER_PLACEHOLDERS"
                ),
                "unique_root_cause_proven": True,
                "root_cause_scope": "PACKAGE_RUNNER_FINALIZER_PLACEHOLDERS_ONLY",
            },
            "runner_finalizer_rulefix_v24": {
                "compile_not_started_sim_log_receipt": True,
                "compile_not_started_simulator_argv_receipt": True,
                "compile_not_started_observer_log_receipt": True,
                "real_simulation_overwrites_receipts": True,
                "functional_rtl_modified": False,
                "execution_scope_modified": False,
                "timeout_modified": False,
            },
        }
    )
    manifest.pop("runner_finalizer_rulefix_v23", None)
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_"
        "b_dequant_control_rulefix_v24_server_package.py"
    )
    audit = manifest["final_zip_rule_self_audit"]
    audit.update(
        {
            "validator": (
                "tools/validate_qlinearadd_node0007_"
                "b_dequant_control_rulefix_v24_server_package.py"
            ),
            "report": (
                "artifacts/operator_config_validation/"
                "r5-qlinearadd-node0007-b-dequant-control-rulefix-v24/"
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
        with tempfile.TemporaryDirectory(prefix="qadd-v24-repeat-") as raw:
            _, repeat_zip, repeat_records = build_once(Path(raw))
            repeat_sha = sha(repeat_zip)
        digest = sha(output)
        if records != repeat_records or digest != repeat_sha:
            raise BuildError("deterministic rebuild differs")
        sidecar.write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
        receipt = {
            "schema": "qlinearadd-node0007-b-dequant-control-rulefix-build-v24",
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
