from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_qlinearadd_node0007_server_package import deterministic_zip
from tools.qlinearadd_node0007_server_runtime import (
    file_records,
    preflight as runtime_preflight,
    write_json,
)


INSTALL_NAME = "r5_qadd_n7_first_request_chain_v9"
VERSION_TAG = "v9"
SOURCE_INSTALL_NAME = "r5_qadd_n7_progress_canon_v8"
PACKAGE_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_INSTALL_NAME}.zip"
SOURCE_ZIP_SHA256 = (
    "b74b18f906fbf32851ce016906c599889236e7088ad7209607e52368bad69100"
)
INDEX = ROOT / ".agents/rules/生成前必读索引.md"
INDEX_SHA256 = (
    "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f"
)
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
SERVER_RULE_SHA256 = (
    "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa"
)
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
QADD_RULE_SHA256 = (
    "c38935c63469a165ffe6b79c9e3d08de47bbbd9b9e0613cbc16253c138e4b76b"
)
PARSER_SOURCE = ROOT / "tools/qlinearadd_first_request_canonical_decision.py"
TAIL_SOURCE = (
    ROOT / "tools/qlinearadd_node0007_first_request_observer_tail_v9.svh"
)
PARSER_REL = Path("package_tools/qlinearadd_progress_canonical_decision.py")
BASE_OBSERVER_REL = Path("tb_probe/native_return_observer.svh")
TAIL_REL = Path(
    "tb_probe/qlinearadd_node0007_first_request_observer_tail_v9.svh"
)
INCLUDE_LINE = (
    '`include "qlinearadd_node0007_first_request_observer_tail_v9.svh"'
)
VALIDATION_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
VALIDATOR_REL = (
    "tools/validate_qlinearadd_node0007_first_request_chain_v9.py"
)
REPORT_REL = (
    "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-first-request-chain-v9/report.json"
)
LOCAL_SUPERSEDED: dict[str, Any] | None = None


class PackageBuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _rule_ids(path: Path) -> list[str]:
    return re.findall(
        r"规则 ID：`([^`]+)`", path.read_text(encoding="utf-8")
    )


def _assert_receipts() -> None:
    expected = {
        INDEX: INDEX_SHA256,
        SERVER_RULE: SERVER_RULE_SHA256,
        QADD_RULE: QADD_RULE_SHA256,
        SOURCE_ZIP: SOURCE_ZIP_SHA256,
    }
    mismatches = {
        str(path): {"expected": wanted, "actual": sha256(path)}
        for path, wanted in expected.items()
        if not path.is_file() or sha256(path) != wanted
    }
    if mismatches:
        raise PackageBuildError(f"immutable receipt drift: {mismatches}")


def _extract_source(destination: Path) -> Path:
    package = destination / INSTALL_NAME
    if package.exists():
        raise PackageBuildError("successor package path already exists")
    with tempfile.TemporaryDirectory(
        prefix="q-", dir=destination
    ) as staging_name:
        staging = Path(staging_name)
        with zipfile.ZipFile(SOURCE_ZIP) as archive:
            bad = archive.testzip()
            if bad is not None:
                raise PackageBuildError(f"source ZIP CRC failure: {bad}")
            archive.extractall(staging)
        source = staging / SOURCE_INSTALL_NAME
        if not source.is_dir():
            raise PackageBuildError("source ZIP root exact identity differs")
        shutil.move(str(source), str(package))
    return package


def _replace_namespace(path: Path) -> None:
    payload = path.read_text(encoding="utf-8")
    if SOURCE_INSTALL_NAME not in payload:
        return
    path.write_text(
        payload.replace(SOURCE_INSTALL_NAME, INSTALL_NAME),
        encoding="utf-8",
        newline="\n",
    )


def build_directory(destination: Path) -> Path:
    _assert_receipts()
    package = _extract_source(destination)
    for relative in (
        Path("PREPARE_AND_RUN.sh"),
        Path("TEST_PACKAGE_MANIFEST.json"),
        Path("workload/runtime/sca_cfg.json"),
        Path("workload/runtime/sca_cfg_D.json"),
    ):
        _replace_namespace(package / relative)

    shutil.copyfile(PARSER_SOURCE, package / PARSER_REL)
    shutil.copyfile(TAIL_SOURCE, package / TAIL_REL)
    observer_path = package / BASE_OBSERVER_REL
    observer = observer_path.read_text(encoding="utf-8")
    if INCLUDE_LINE in observer:
        raise PackageBuildError("first-request tail was already included")
    observer_path.write_text(
        observer.rstrip() + "\n\n" + INCLUDE_LINE + "\n",
        encoding="utf-8",
        newline="\n",
    )

    progress_path = package / "diagnostics/progress_contract.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    progress.update(
        {
            "schema": (
                "qlinearadd-node0007-first-request-chain-localization-v1"
            ),
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "target_stage": "op_a_dequant",
            "unique_error_interval": (
                "op_a_dequant Start_Comp -> actual slice_start_run -> "
                "mapped physical LC4/(LC2,LC6)/(LC13,LC18) qualified "
                "handshakes -> selected MSE0 index inputs/match/queue -> "
                "address-generator accept -> first request enqueue/accept"
            ),
            "qualified_internal_counters": [
                "slice_start_run",
                "physical_lc2_4_6_13_18_output_handshakes",
                "mse0_selected_index_input_handshakes",
                "mse0_match_queue_write",
                "mse0_address_generator_handshake",
                "mse0_first_request_enqueue",
                "mse4_selected_index_input_handshakes",
                "mse4_match_queue_write",
            ],
            "level_snapshots_not_counted_as_progress": [
                "active_lc_enable_valid_ready",
                "mse0_index_valid_ready_match_empty_full",
                "mse0_address_generator_valid_ready",
                "mse0_request_enqueue_valid_ready",
                "mse4_index_valid_ready_match_empty_full",
            ],
            "outcome_rules": {
                "qualified_internal_windows_advance": (
                    "STILL_PROGRESSING_NOT_FINISHED"
                ),
                "flat_beyond_stall_window": (
                    "LONG_RUNNING_HANG_AT_EXACT_FIRST_REQUEST_BOUNDARY"
                ),
                "first_base_request_accepts": (
                    "FIRST_REQUEST_ACCEPTED_CONTINUE_STANDARD_PROGRESS"
                ),
                "chain_absent_or_ambiguous": (
                    "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
                ),
            },
        }
    )
    write_json(progress_path, progress)

    readme = (
        f"# QLinearAdd node0007 first-request-chain diagnostic {VERSION_TAG}\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "This is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves the "
        "frozen v4/v6 workload and all numerical configuration. The only "
        "change is a read-only, rate-limited observer for the active "
        "op_a_dequant LC/MSE ready chain plus a unique canonical partial "
        "decision parser. Enable/ready/valid levels are snapshots only; "
        "progress requires qualified handshakes or queue writes.\n"
    )
    (package / "README.md").write_text(
        readme, encoding="utf-8", newline="\n"
    )

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    parser_sha = sha256(package / PARSER_REL)
    tail_sha = sha256(package / TAIL_REL)
    base_observer_sha = sha256(package / BASE_OBSERVER_REL)
    manifest.update(
        {
            "schema": (
                "qlinearadd-node0007-first-request-chain-"
                f"diagnostic-server-package-{VERSION_TAG}"
            ),
            "install_name": INSTALL_NAME,
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "read-only localization of the first non-advancing "
                "qualified handshake between op_a_dequant Start_Comp and "
                "the first MSE0 request; no configuration or functional fix"
            ),
            "server_tb_or_observer_entries": 2,
            "superseded_diagnostic": {
                "zip": SOURCE_ZIP.relative_to(ROOT).as_posix(),
                "sha256": SOURCE_ZIP_SHA256,
                "status": "QUARANTINED_PROVEN_DYNAMIC_HANG_NO_INTERNAL_READY",
                "functional_workload_unchanged": True,
            },
            "first_request_internal_observability": {
                "rule_id": (
                    "CDA-QADD-FIRST-REQUEST-HANG-"
                    "INTERNAL-READY-OBSERVABILITY-001"
                ),
                "target_stage": "op_a_dequant",
                "target_slice": 0,
                "read_only": True,
                "rate_limited": True,
                "base_observer_path": BASE_OBSERVER_REL.as_posix(),
                "base_observer_sha256": base_observer_sha,
                "tail_path": TAIL_REL.as_posix(),
                "tail_sha256": tail_sha,
                "tail_include": INCLUDE_LINE,
                "physical_mapping": {
                    "logical_lc0_outer": 4,
                    "logical_lc1": 2,
                    "logical_lc3": 6,
                    "logical_lc2": 13,
                    "logical_lc4": 18,
                    "read_stream": "MSE0",
                    "write_stream": "MSE4",
                },
                "qualified_signal_groups": [
                    "actual_slice_start_run",
                    "lc2_4_6_13_18_enable_output_valid_ready_handshake",
                    "mse0_index_input_valid_ready_handshake",
                    "mse0_match_empty_full_queue_write",
                    "mse0_ag_valid_ready_handshake",
                    "mse0_request_enqueue_valid_ready_handshake",
                    "mse4_index_input_valid_ready_handshake",
                    "mse4_match_empty_full_queue_write",
                ],
                "frozen_workload_and_numeric_semantics_unchanged": True,
            },
            "canonical_decision_contract": {
                "rule_id": (
                    "CDA-SERVER-DIAGNOSTIC-DECISION-"
                    "CANONICAL-RECORD-001"
                ),
                "schema": (
                    "qlinearadd-first-request-canonical-decision-v1"
                ),
                "version": 1,
                "parser_path": PARSER_REL.as_posix(),
                "parser_sha256": parser_sha,
                "output_path": (
                    "evidence/CANONICAL_PROGRESS_DECISION.json"
                ),
                "unique_complete_record_required": True,
                "required_fields": [
                    "schema",
                    "version",
                    "decision",
                    "reason",
                    "boundary",
                    "sample_range",
                    "qualified_counter_names",
                    "counter_snapshot",
                    "windows",
                    "content_summary",
                    "content_digest",
                ],
                "level_snapshots_excluded_from_progress": True,
                "ambiguous_state": (
                    "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
                ),
            },
            "final_zip_rule_self_audit": {
                "rule_id": "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
                "rule_receipts": {
                    "generation_index": {
                        "path": INDEX.relative_to(ROOT).as_posix(),
                        "sha256": INDEX_SHA256,
                        "current_match": True,
                    },
                    "server_package_rule": {
                        "path": SERVER_RULE.relative_to(ROOT).as_posix(),
                        "sha256": SERVER_RULE_SHA256,
                        "current_match": True,
                    },
                    "qlinearadd_rule": {
                        "path": QADD_RULE.relative_to(ROOT).as_posix(),
                        "sha256": QADD_RULE_SHA256,
                        "current_match": True,
                    },
                },
                "applicable_server_rule_ids": _rule_ids(SERVER_RULE),
                "applicable_qlinearadd_rule_ids": _rule_ids(QADD_RULE),
                "direct_final_zip_and_sidecar_validation_required": True,
                "all_required_negative_controls_required": True,
                "pass_field": "FINAL_ZIP_RULE_SELF_AUDIT_PASS",
                "errors_must_equal": 0,
                "validator": (
                    VALIDATOR_REL
                ),
                "report": REPORT_REL,
            },
        }
    )
    if LOCAL_SUPERSEDED is not None:
        manifest["superseded_local_diagnostic"] = LOCAL_SUPERSEDED
    manifest["provenance"]["generation_index"] = {
        "path": INDEX.relative_to(ROOT).as_posix(),
        "sha256": INDEX_SHA256,
    }
    manifest["provenance"]["server_package_rule"] = {
        "path": SERVER_RULE.relative_to(ROOT).as_posix(),
        "sha256": SERVER_RULE_SHA256,
    }
    manifest["provenance"]["qlinearadd_rule"] = {
        "path": QADD_RULE.relative_to(ROOT).as_posix(),
        "sha256": QADD_RULE_SHA256,
    }
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    runtime_preflight(package)
    return package


def _build_once(destination: Path) -> tuple[Path, Path, dict[str, Any]]:
    package = build_directory(destination)
    output_zip = destination / f"{INSTALL_NAME}.zip"
    deterministic_zip(package, output_zip)
    return package, output_zip, file_records(package, exclude_manifest=False)


def main() -> int:
    package_path = PACKAGE_ROOT / INSTALL_NAME
    zip_path = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    for path in (package_path, zip_path, sidecar, VALIDATION_PATH):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    PACKAGE_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        package, built_zip, records = _build_once(PACKAGE_ROOT)
        if built_zip != zip_path:
            raise PackageBuildError("unexpected final ZIP path")
        with tempfile.TemporaryDirectory(prefix="qadd-fr-v9-repeat-") as temp:
            repeat_package, repeat_zip, repeat_records = _build_once(Path(temp))
            repeated = {
                "package_tree_equal": records == repeat_records,
                "zip_equal": sha256(zip_path) == sha256(repeat_zip),
                "repeat_zip_sha256": sha256(repeat_zip),
                "repeat_package_name": repeat_package.name,
            }
        if not repeated["package_tree_equal"] or not repeated["zip_equal"]:
            raise PackageBuildError("deterministic repeated build differs")
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        receipt: dict[str, Any] = {
            "schema": (
                "qlinearadd-node0007-first-request-chain-"
                "package-build-receipt-v1"
            ),
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "functional_fix": False,
            "package": package.relative_to(ROOT).as_posix(),
            "zip": zip_path.relative_to(ROOT).as_posix(),
            "zip_sha256": digest,
            "sidecar": sidecar.relative_to(ROOT).as_posix(),
            "sidecar_sha256": sha256(sidecar),
            "file_count": len(records),
            "repeated_build": repeated,
            "source_zip": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "source_zip_sha256": SOURCE_ZIP_SHA256,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "consumed_reuse_assets": True,
            "server_action": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
        }
        write_json(VALIDATION_PATH, receipt)
    except Exception as exc:
        print(f"package build failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
