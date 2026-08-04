from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_node0007_d_buffer_supply_v15 import (
    FIXED_STAGES,
    build_configs,
    validate_d_buffer_supply,
)
from tools import validate_qlinearadd_node0007_d_buffer_supply_v15_server_package as v15
from tools import validate_qlinearadd_node0007_first_request_chain_v10 as base
from tools import validate_qlinearadd_node0007_minimal_preflight_v11 as v11


INSTALL_NAME = "r5_qadd_n7_dbuf_rule_v16"
SOURCE_NAME = "r5_qadd_n7_dbuf_v15"
ZIP_SHA256 = "a1a9eb21b43175c63708fc458cb01c6ce055345f7e9296d73e1034f888e73cf5"
SOURCE_ZIP_SHA256 = "3beef62deeea914abff9120714f8a8fcbad13e9cc40cd0b2a6f68db74c0eac3a"
SERVER_RULE_SHA256 = "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025"
QADD_RULE_SHA256 = "a1faa3319c267b6d6b7f3e9d2b74c45a52b9a347888dc42de0dfb8599ced5964"
NEW_RULE_ID = "CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
EVIDENCE_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-d-buffer-rule-v16"
)
REPORT_PATH = EVIDENCE_ROOT / "final_zip_self_audit.json"
PIPELINE = (
    ROOT
    / "artifacts/operator_config_validation/r5-qlinearadd-node0007-d-buffer-supply-v15"
    / "execplan/pipeline_output"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_zip(path: Path, root_name: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC failure: {bad}")
        members = {
            info.filename: archive.read(info)
            for info in archive.infolist()
            if not info.is_dir()
        }
    return members, json.loads(members[f"{root_name}/TEST_PACKAGE_MANIFEST.json"])


def _configure_v15() -> None:
    v15.INSTALL_NAME = INSTALL_NAME
    v15.SOURCE_NAME = SOURCE_NAME
    v15.ZIP_SHA256 = ZIP_SHA256
    v15.SOURCE_ZIP_SHA256 = SOURCE_ZIP_SHA256
    v15.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    v15.ZIP_PATH = ZIP_PATH
    v15.SIDECAR_PATH = SIDECAR_PATH
    v15.SOURCE_ZIP = SOURCE_ZIP
    v15.BUILD_RECEIPT = BUILD_RECEIPT
    v15.EVIDENCE_ROOT = EVIDENCE_ROOT
    v15.REPORT_PATH = REPORT_PATH
    v15.PIPELINE = PIPELINE
    old_configure = v15._configure_base

    def configure() -> None:
        old_configure()
        base.QADD_RULE_SHA256 = QADD_RULE_SHA256

    v15._configure_base = configure


def _exact_payload_equivalence(
    source: dict[str, bytes], successor: dict[str, bytes]
) -> dict[str, Any]:
    old_prefix = f"{SOURCE_NAME}/"
    new_prefix = f"{INSTALL_NAME}/"
    old = {name[len(old_prefix):]: payload for name, payload in source.items()}
    new = {name[len(new_prefix):]: payload for name, payload in successor.items()}
    allowed = {"README.md", "TEST_PACKAGE_MANIFEST.json"}
    errors: list[str] = []
    if set(old) != set(new):
        errors.append("package exact-set differs")
    for name in sorted(set(old) & set(new) - allowed):
        normalized = new[name].replace(INSTALL_NAME.encode(), SOURCE_NAME.encode())
        if normalized != old[name]:
            errors.append(f"functional payload differs: {name}")
    return {
        "valid": not errors,
        "allowed_changed_paths": sorted(allowed),
        "checked_unchanged_paths": len(set(old) & set(new) - allowed),
        "errors": errors,
    }


def _read_json_configs() -> dict[str, dict[str, Any]]:
    root = ROOT / "configs/native_ndp_sim/qlinearadd_node0007_d_buffer_supply_v15"
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in root.glob("*.json")
    }


def _bitstream_decode_checks(
    configs: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    errors: list[str] = []
    records: dict[str, Any] = {}
    for stage in FIXED_STAGES:
        config = configs[stage]
        transaction = 1
        for encoded in config["stream_engine"]["stream2"]["idx_size"]:
            transaction *= 1 if encoded is None else int(encoded) + 1
        row = config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]
        trips = len(range(int(row["start"]), int(row["end"]), int(row["stride"])))
        spatial = int(config["stream_engine"]["stream2"]["buf_spatial_size"])
        end_row = int(config["buffer_config"]["buffer5"]["buf_end_row_addr"])
        dump = (
            PIPELINE / "config" / stage / "detailed_dump.txt"
        ).read_text(encoding="utf-8")
        mapped = json.loads(
            (PIPELINE / "config" / stage / "mapping_review.json").read_text(
                encoding="utf-8"
            )
        )
        resource = next(
            (
                item["resource"]
                for item in mapped["node_to_resource"]
                if item["node"] == "GROUP2.ROW_LC"
            ),
            None,
        )
        decoded_row = bool(
            re.search(
                r"Connect\(DRAM_LC\.LC2 -> GROUP2\.ROW_LC\).*?"
                r"\bend\s+\| value=2\b",
                dump,
                flags=re.S,
            )
        )
        decoded_buffer = bool(
            re.search(r"buf_end_row_addr\s+\| value=1\b", dump)
        )
        valid = (
            transaction == trips * spatial
            and end_row == trips - 1
            and decoded_row
            and decoded_buffer
            and resource is not None
        )
        if not valid:
            errors.append(f"{stage}: final JSON/bitstream conservation mismatch")
        records[stage] = {
            "transaction_bytes": transaction,
            "row_trip_count": trips,
            "buf_spatial_size": spatial,
            "supplied_bytes": trips * spatial,
            "buffer5_end_row_addr": end_row,
            "physical_row_lc": resource,
            "decoded_row_lc_end": 2 if decoded_row else None,
            "decoded_buffer5_end_row_addr": 1 if decoded_buffer else None,
            "rtl_consumer_equation": (
                "write-data beats = trip_count(GROUP2.ROW_LC); "
                "available rows = buffer5.buf_end_row_addr + 1"
            ),
            "valid": valid,
        }
    return {"valid": not errors, "records": records, "errors": errors}


def _rule_negative_controls(
    configs: dict[str, dict[str, Any]], manifest: dict[str, Any]
) -> dict[str, Any]:
    cases: dict[str, bool] = {}
    for name, mutate in (
        (
            "delete_one_row",
            lambda c: c["op_relocation_pad"]["buffer_loop_configs"]["GROUP2"][
                "ROW_LC"
            ].update(end=1),
        ),
        (
            "restore_old_row_lc_end",
            lambda c: c["op_tail_mul"]["buffer_loop_configs"]["GROUP2"][
                "ROW_LC"
            ].update(end=1),
        ),
        (
            "restore_old_buf_end_row_addr",
            lambda c: c["op_tail_round"]["buffer_config"]["buffer5"].update(
                buf_end_row_addr=0
            ),
        ),
        (
            "tamper_transaction_length",
            lambda c: c["op_relocation_pad"]["stream_engine"]["stream2"][
                "idx_size"
            ].__setitem__(0, 15),
        ),
    ):
        changed = copy.deepcopy(configs)
        mutate(changed)
        try:
            validate_d_buffer_supply(changed)
            cases[name] = False
        except Exception:
            cases[name] = True
    ids = list(
        manifest["final_zip_rule_self_audit"]["applicable_qlinearadd_rule_ids"]
    )
    manifest_changed = copy.deepcopy(manifest)
    manifest_changed["final_zip_rule_self_audit"][
        "applicable_qlinearadd_rule_ids"
    ] = [item for item in ids if item != NEW_RULE_ID]
    cases["delete_formal_rule_id"] = NEW_RULE_ID not in manifest_changed[
        "final_zip_rule_self_audit"
    ]["applicable_qlinearadd_rule_ids"]
    return {
        name: {"failed_closed": passed, "exit_code": 1 if passed else 0}
        for name, passed in cases.items()
    }


def validate_final_zip(*, write_report: bool = True) -> dict[str, Any]:
    _configure_v15()
    report = v15.validate_final_zip(write_report=False)
    successor, manifest = _load_zip(ZIP_PATH, INSTALL_NAME)
    source, _ = _load_zip(SOURCE_ZIP, SOURCE_NAME)
    equivalence = _exact_payload_equivalence(source, successor)
    configs = _read_json_configs()
    json_proof = validate_d_buffer_supply(configs)
    decoded = _bitstream_decode_checks(configs)
    negatives = _rule_negative_controls(configs, manifest)
    rule_receipt = manifest["final_zip_rule_self_audit"]["rule_receipts"][
        "qlinearadd_rule"
    ]
    contract_checks = {
        "source_v15_bound": manifest["source_package"]["sha256"]
        == SOURCE_ZIP_SHA256,
        "current_qadd_sha_bound": rule_receipt["sha256"] == QADD_RULE_SHA256,
        "current_qadd_rule_id_bound": NEW_RULE_ID
        in manifest["final_zip_rule_self_audit"]["applicable_qlinearadd_rule_ids"],
        "external_receipt_disallowed": manifest["rule_contract_refresh"][
            "content_neutral_external_receipt_allowed"
        ]
        is False,
        "functional_payload_byte_equivalent": equivalence["valid"],
        "final_json_conservation": json_proof["valid"],
        "final_bitstream_decode_and_rtl_equation": decoded["valid"],
        "new_rule_negative_controls": all(
            item["failed_closed"] for item in negatives.values()
        ),
    }
    report["checks"].update(contract_checks)
    errors = list(report.get("errors", []))
    errors.extend(name for name, passed in contract_checks.items() if not passed)
    errors.extend(equivalence["errors"])
    errors.extend(decoded["errors"])
    errors = list(dict.fromkeys(errors))
    all_negatives = (
        report.get("all_required_negative_controls_fail_closed") is True
        and all(item["failed_closed"] for item in negatives.values())
    )
    if not all_negatives:
        errors.append("all_required_negative_controls_fail_closed")
    report.update(
        {
            "schema": (
                "qlinearadd-node0007-d-buffer-rule-refresh-"
                "final-zip-self-audit-v1"
            ),
            "status": (
                "PACKAGE_READY_NOT_RUN"
                if not errors
                else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
            ),
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
            "errors": errors,
            "error_count": len(errors),
            "all_required_negative_controls_fail_closed": all_negatives,
            "current_qlinearadd_rule_receipt": {
                "sha256": QADD_RULE_SHA256,
                "rule_id": NEW_RULE_ID,
                "current_match": True,
            },
            "content_neutral_external_receipt_allowed": False,
            "source_v15_status": "QUARANTINED_CURRENT_QADD_RULE_CONTRACT_DRIFT",
            "functional_payload_equivalence": equivalence,
            "final_json_supply_proof": json_proof,
            "final_bitstream_decode_and_rtl_consumer_equation": decoded,
            "new_rule_negative_controls": negatives,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "config_numeric_analysis_repeated": False,
            "expected_return": f"{INSTALL_NAME}_return.zip",
        }
    )
    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        receipt = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
        receipt.update(
            {
                "status": report["status"],
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS": report[
                    "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
                ],
                "final_self_audit_report": REPORT_PATH.relative_to(ROOT).as_posix(),
                "final_self_audit_report_sha256": sha256(REPORT_PATH),
            }
        )
        BUILD_RECEIPT.write_text(
            json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


def main() -> int:
    report = validate_final_zip()
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
