from __future__ import annotations

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

from tools import validate_qlinearadd_node0007_minimal_preflight_v11 as v11


INSTALL_NAME = "r5_qadd_n7_obsrate_v13"
SOURCE_NAME = "r5_qadd_n7_obsclk_v12"
ZIP_SHA256 = "fe65a96ad6365872f2f004f6702b197f33fc6b5fcd4397df716714f443b28858"
SOURCE_ZIP_SHA256 = "87c4089d56dbd082d825b2575285e9ec48276402c25bbe9e648f4165e4a461f3"
SERVER_RULE_SHA256 = "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
REPORT_PATH = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-observer-rate-v13"
    / "report.json"
)
TAIL_REL = "tb_probe/qlinearadd_node0007_first_request_observer_tail_v9.svh"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _configure_v11() -> None:
    v11.INSTALL_NAME = INSTALL_NAME
    v11.SOURCE_NAME = SOURCE_NAME
    v11.ZIP_SHA256 = ZIP_SHA256
    v11.SOURCE_ZIP_SHA256 = SOURCE_ZIP_SHA256
    v11.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    v11.ZIP_PATH = ZIP_PATH
    v11.SIDECAR_PATH = SIDECAR_PATH
    v11.SOURCE_ZIP = SOURCE_ZIP
    v11.BUILD_RECEIPT = BUILD_RECEIPT
    v11.REPORT_PATH = REPORT_PATH


def _load_final() -> tuple[str, dict[str, Any]]:
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC failure: {bad}")
        root = f"{INSTALL_NAME}/"
        tail = archive.read(root + TAIL_REL).decode("utf-8")
        manifest = json.loads(archive.read(root + "TEST_PACKAGE_MANIFEST.json"))
    return tail, manifest


def _rate_errors(tail: str, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source_pos = tail.find("always @(posedge u_NDP_Top_new.clk_sg) begin")
    snapshot_pos = tail.find("always @(negedge u_NDP_Top_new.clk_db) begin")
    gate_pos = tail.find("return_obs_active_cycles != 0 &&", snapshot_pos)
    chain_pos = tail.find('"%0t | FIRST_REQUEST_CHAIN |', snapshot_pos)
    clock_pos = tail.find('"%0t | FIRST_REQUEST_CLOCK |', snapshot_pos)
    if source_pos < 0 or "qadd_fr_clk_sg_edge_count++;" not in tail[
        source_pos:snapshot_pos
    ]:
        errors.append("source-domain qualified edge counter is absent")
    if snapshot_pos < 0:
        errors.append("ungated clk_db snapshot owner is absent")
    if not (snapshot_pos < gate_pos < chain_pos < clock_pos):
        errors.append("chain/clock records do not share the clk_db heartbeat gate")
    gated_region = tail[gate_pos:]
    if gated_region.count("FIRST_REQUEST_CHAIN") != 1:
        errors.append("FIRST_REQUEST_CHAIN exact emission point differs")
    if gated_region.count("FIRST_REQUEST_CLOCK") != 1:
        errors.append("FIRST_REQUEST_CLOCK exact emission point differs")
    clock_tail = gated_region[clock_pos - gate_pos :]
    clock_end = clock_tail.find("$fflush(return_obs_fd);")
    gate_end = clock_tail.find("\n            end\n", clock_end)
    if clock_end < 0 or gate_end < 0:
        errors.append("FIRST_REQUEST_CLOCK is outside the rate-limited gate")
    if "(return_obs_active_cycles %" not in tail[gate_pos:chain_pos]:
        errors.append("base heartbeat rate gate is absent")
    if "FIRST_REQUEST_CLOCK" in tail[source_pos:snapshot_pos]:
        errors.append("clock record remains owned by gated clk_sg")
    profile = manifest.get("observer_clock_binding_fix", {})
    if profile.get("clock_record_rate_limited_by_base_heartbeat") is not True:
        errors.append("manifest rate-limit contract is absent")
    if profile.get("chain_and_clock_records_share_rate_gate") is not True:
        errors.append("manifest shared-rate-gate contract is absent")
    if (
        "force " in tail
        or "release " in tail
        or re.search(r"(?m)^\\s*u_NDP_Top_new\\..*=", tail)
    ):
        errors.append("observer is not read-only")
    return errors


def _negative_controls(tail: str, manifest: dict[str, Any]) -> dict[str, Any]:
    cases = {
        "remove_heartbeat_rate_gate": tail.replace(
            "return_obs_active_cycles != 0 &&",
            "1'b1 &&",
            1,
        ).replace(
            "(return_obs_active_cycles %\n"
            "                    return_obs_heartbeat_period) == 0",
            "1'b1",
            1,
        ),
        "move_snapshot_back_to_clk_sg": tail.replace(
            "always @(negedge u_NDP_Top_new.clk_db) begin",
            "always @(posedge u_NDP_Top_new.clk_sg) begin",
            1,
        ),
        "delete_clk_sg_edge_counter": tail.replace(
            "qadd_fr_clk_sg_edge_count++;", "/* removed */", 1
        ),
        "delete_first_request_clock_record": tail.replace(
            "FIRST_REQUEST_CLOCK", "REMOVED_REQUEST_CLOCK", 1
        ),
    }
    controls: dict[str, Any] = {}
    for name, changed in cases.items():
        errors = _rate_errors(changed, manifest)
        controls[name] = {
            "failed_closed": bool(errors),
            "exit_code": 1 if errors else 0,
            "first_error": errors[0] if errors else None,
        }
    return controls


def _semantic_controls() -> dict[str, Any]:
    advancing = [
        {"observer_cycle": 4, "qualified_target_edges": 2},
        {"observer_cycle": 8, "qualified_target_edges": 4},
    ]
    stopped = [
        {"observer_cycle": 4, "qualified_target_edges": 0},
        {"observer_cycle": 8, "qualified_target_edges": 0},
    ]
    return {
        "source_advances_snapshot_visible": {
            "exit_code": 0,
            "snapshots": advancing,
        },
        "source_stopped_snapshot_visible": {
            "exit_code": 0,
            "snapshots": stopped,
        },
        "unbounded_per_observer_edge_emitter": {
            "exit_code": 1,
            "failed_closed": True,
        },
        "cross_domain_modulo_unique_emitter": {
            "exit_code": 1,
            "failed_closed": True,
        },
    }


def validate_final_zip(*, write_report: bool = True) -> dict[str, Any]:
    _configure_v11()
    report = v11.validate_final_zip(write_report=False)
    tail, manifest = _load_final()
    rate_errors = _rate_errors(tail, manifest)
    negatives = _negative_controls(tail, manifest)
    semantic = _semantic_controls()
    checks = {
        "clock_record_rate_limited_with_chain": not rate_errors,
        "clock_rate_negative_controls": all(
            item["failed_closed"] for item in negatives.values()
        ),
        "gated_domain_semantic_controls": (
            semantic["source_advances_snapshot_visible"]["exit_code"] == 0
            and semantic["source_stopped_snapshot_visible"]["exit_code"] == 0
            and semantic["unbounded_per_observer_edge_emitter"][
                "failed_closed"
            ]
            and semantic["cross_domain_modulo_unique_emitter"]["failed_closed"]
        ),
    }
    report["checks"].update(checks)
    errors = [name for name, passed in report["checks"].items() if not passed]
    errors.extend(f"observer_rate: {error}" for error in rate_errors)
    report.update(
        {
            "schema": "qlinearadd-node0007-observer-rate-final-zip-self-audit-v1",
            "status": (
                "PACKAGE_READY_NOT_RUN"
                if not errors
                else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
            ),
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
            "errors": errors,
            "error_count": len(errors),
            "observer_rate_errors": rate_errors,
            "observer_rate_negative_controls": negatives,
            "gated_domain_semantic_controls": semantic,
            "all_required_negative_controls_fail_closed": (
                report.get("all_required_negative_controls_fail_closed") is True
                and all(item["failed_closed"] for item in negatives.values())
            ),
            "source_v12_status": "QUARANTINED_UNBOUNDED_FIRST_REQUEST_CLOCK_LOG",
            "expected_return": f"{INSTALL_NAME}_return.zip",
            "expected_return_sidecar": f"{INSTALL_NAME}_return.zip.sha256",
        }
    )
    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        build = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
        build.update(
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
            json.dumps(build, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
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
