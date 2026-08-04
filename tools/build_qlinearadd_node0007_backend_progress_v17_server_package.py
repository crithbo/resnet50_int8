from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import file_records, preflight, write_json
from tools import validate_qlinearadd_node0007_first_request_chain_v10 as base


INSTALL_NAME = "r5_qadd_n7_backend_progress_v17"
SOURCE_NAME = "r5_qadd_n7_dbuf_rule_v16"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_DIR = PACKAGE_ROOT / SOURCE_NAME
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = "a1a9eb21b43175c63708fc458cb01c6ce055345f7e9296d73e1034f888e73cf5"
INDEX = ROOT / ".agents/rules/生成前必读索引.md"
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
INDEX_SHA256 = "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
SERVER_RULE_SHA256 = "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025"
QADD_RULE_SHA256 = "a1faa3319c267b6d6b7f3e9d2b74c45a52b9a347888dc42de0dfb8599ced5964"
OLD_HEARTBEAT_CYCLES = 262_144
HEARTBEAT_CYCLES = 32_768
VALIDATION_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
REPORT_REL = (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-backend-progress-v17/final_zip_self_audit.json"
)


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _assert_receipts() -> None:
    expected = {
        SOURCE_ZIP: SOURCE_ZIP_SHA256,
        INDEX: INDEX_SHA256,
        SERVER_RULE: SERVER_RULE_SHA256,
        QADD_RULE: QADD_RULE_SHA256,
    }
    drift = {
        str(path): {"expected": wanted, "actual": sha256(path)}
        for path, wanted in expected.items()
        if not path.is_file() or sha256(path) != wanted
    }
    if drift:
        raise BuildError(f"immutable receipt drift: {drift}")


def build_directory(destination: Path) -> Path:
    _assert_receipts()
    package = destination / INSTALL_NAME
    if package.exists():
        raise BuildError(f"destination exists: {package}")
    shutil.copytree(SOURCE_DIR, package)

    binary_suffixes = {".bin", ".png", ".npy", ".npz"}
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() in binary_suffixes:
            continue
        payload = path.read_bytes()
        if SOURCE_NAME.encode() in payload:
            path.write_bytes(payload.replace(SOURCE_NAME.encode(), INSTALL_NAME.encode()))

    runner = package / "PREPARE_AND_RUN.sh"
    runner_text = runner.read_text(encoding="utf-8")
    old_arg = f"+RETURN_OBS_HEARTBEAT_CYCLES={OLD_HEARTBEAT_CYCLES}"
    new_arg = f"+RETURN_OBS_HEARTBEAT_CYCLES={HEARTBEAT_CYCLES}"
    if runner_text.count(old_arg) != 1:
        raise BuildError("source runner heartbeat argument is not unique")
    runner.write_text(
        runner_text.replace(old_arg, new_arg),
        encoding="utf-8",
        newline="\n",
    )

    readme = package / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\nBackend progress cadence v17:\n"
        f"- source v16 is byte-frozen at `{SOURCE_ZIP_SHA256}`;\n"
        f"- heartbeat cadence is reduced from {OLD_HEARTBEAT_CYCLES} to "
        f"{HEARTBEAT_CYCLES} active cycles;\n"
        "- records remain package-local, rate-limited and read-only: HEARTBEAT, "
        "SG_COUNTS, INTERNAL_STATE, FIRST_REQUEST_CHAIN and FIRST_REQUEST_CLOCK;\n"
        "- no DUT input/ready/backpressure/timeout/config/workload/golden/RTL "
        "behavior is changed.\n",
        encoding="utf-8",
        newline="\n",
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "qlinearadd-node0007-backend-progress-server-package-v17",
            "install_name": INSTALL_NAME,
            "source_package": {
                "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_ZIP_SHA256,
                "status": "SUPERSEDED_FOR_BACKEND_PROGRESS_OBSERVABILITY",
                "numeric_workload_and_golden_unchanged": True,
            },
            "backend_progress_logging_contract": {
                "schema": "qlinearadd-node0007-backend-progress-logging-v1",
                "frontend_transaction_logging_added": False,
                "observer_output": "runs/return_observer.log",
                "old_heartbeat_cycles": OLD_HEARTBEAT_CYCLES,
                "heartbeat_cycles": HEARTBEAT_CYCLES,
                "stall_window_cycles": 1_048_576,
                "deep_checkpoint_limit": 64,
                "records_per_heartbeat": [
                    "HEARTBEAT",
                    "SG_COUNTS",
                    "INTERNAL_STATE",
                    "FIRST_REQUEST_CHAIN",
                    "FIRST_REQUEST_CLOCK",
                ],
                "qualified_counters": [
                    "MSE0_TO_BUFFER0_ACCEPT",
                    "READ_BUFFER_CONSUME",
                    "GA_INPUT_ACCEPT",
                    "GA_OUTPUT_ACCEPT",
                    "MSE4_REQUEST_ACCEPT_PER_CHANNEL",
                    "MSE4_WRITE_DATA_ACCEPT_PER_CHANNEL",
                    "MSE4_OUTSTANDING_PER_CHANNEL",
                ],
                "stage_markers": ["CFG_START", "CFG_FINISH", "EXEC_START", "COMP_FINISH"],
                "changes_dut_input": False,
                "changes_ready_or_backpressure": False,
                "changes_timeout": False,
                "changes_configuration": False,
                "changes_workload": False,
                "changes_golden": False,
                "changes_functional_rtl": False,
            },
        }
    )
    manifest["progress_localization"]["heartbeat_cycles"] = HEARTBEAT_CYCLES
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_backend_progress_v17_server_package.py"
    )
    audit = manifest["final_zip_rule_self_audit"]
    audit["applicable_server_rule_ids"] = base._rule_ids(SERVER_RULE)
    audit["applicable_qlinearadd_rule_ids"] = base._rule_ids(QADD_RULE)
    audit["validator"] = (
        "tools/validate_qlinearadd_node0007_backend_progress_v17_server_package.py"
    )
    audit["report"] = REPORT_REL
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    preflight(package)
    return package


def _build_once(destination: Path) -> tuple[Path, Path, list[dict[str, Any]]]:
    package = build_directory(destination)
    output = destination / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, output)
    return package, output, file_records(package, exclude_manifest=False)


def main() -> int:
    package = PACKAGE_ROOT / INSTALL_NAME
    output = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(output) + ".sha256")
    for path in (package, output, sidecar, VALIDATION_PATH):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, built, records = _build_once(PACKAGE_ROOT)
        with tempfile.TemporaryDirectory(prefix="qadd-v17-repeat-") as raw:
            _, repeat_zip, repeat_records = _build_once(Path(raw))
            repeated = {
                "package_tree_equal": records == repeat_records,
                "zip_equal": sha256(built) == sha256(repeat_zip),
                "repeat_zip_sha256": sha256(repeat_zip),
            }
        if not all((repeated["package_tree_equal"], repeated["zip_equal"])):
            raise BuildError("deterministic rebuild differs")
        digest = sha256(output)
        sidecar.write_text(f"{digest}  {output.name}\n", encoding="ascii", newline="\n")
        receipt = {
            "schema": "qlinearadd-node0007-backend-progress-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "package": package.relative_to(ROOT).as_posix(),
            "zip": output.relative_to(ROOT).as_posix(),
            "zip_sha256": digest,
            "zip_bytes": output.stat().st_size,
            "sidecar": sidecar.relative_to(ROOT).as_posix(),
            "sidecar_sha256": sha256(sidecar),
            "source_zip": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "source_zip_sha256": SOURCE_ZIP_SHA256,
            "file_count": len(records),
            "repeated_build": repeated,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "config_numeric_analysis_repeated": False,
            "configuration_changed": False,
            "functional_rtl_modified": False,
            "backend_logging_only": True,
            "server_action": False,
        }
        write_json(VALIDATION_PATH, receipt)
    except Exception as exc:
        print(f"package build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
