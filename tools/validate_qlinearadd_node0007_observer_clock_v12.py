from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_minimal_preflight_v11 as v11


INSTALL_NAME = "r5_qadd_n7_obsclk_v12"
SOURCE_NAME = "r5_qadd_n7_minpre_v11"
ZIP_SHA256 = "87c4089d56dbd082d825b2575285e9ec48276402c25bbe9e648f4165e4a461f3"
SOURCE_ZIP_SHA256 = "d8a20d54ca83d0607a79740be79f632fce6115f9d1b6e58fb1e9f40d60c828d1"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
REPORT_PATH = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-observer-clock-v12"
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
    v11.ZIP_PATH = ZIP_PATH
    v11.SIDECAR_PATH = SIDECAR_PATH
    v11.SOURCE_ZIP = SOURCE_ZIP
    v11.BUILD_RECEIPT = BUILD_RECEIPT
    v11.REPORT_PATH = REPORT_PATH


def _tail_from_zip() -> tuple[str, dict[str, Any]]:
    with zipfile.ZipFile(ZIP_PATH) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC failure: {bad}")
        root = f"{INSTALL_NAME}/"
        tail = archive.read(root + TAIL_REL).decode("utf-8")
        manifest = json.loads(
            archive.read(root + "TEST_PACKAGE_MANIFEST.json")
        )
    return tail, manifest


def _clock_binding_errors(tail: str, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    profile = manifest.get("observer_clock_binding_fix", {})
    counter_anchor = "always @(posedge u_NDP_Top_new.clk_sg) begin"
    snapshot_anchor = "always @(negedge u_NDP_Top_new.clk_db) begin"
    counter_pos = tail.find(counter_anchor)
    snapshot_pos = tail.find(snapshot_anchor)
    chain_pos = tail.find('"%0t | FIRST_REQUEST_CHAIN |')
    clock_pos = tail.find('"%0t | FIRST_REQUEST_CLOCK |')
    if counter_pos < 0:
        errors.append("qualified counter clk_sg owner is absent")
    if "qadd_fr_clk_sg_edge_count++;" not in tail:
        errors.append("clk_sg qualified edge counter is absent")
    if snapshot_pos < 0:
        errors.append("ungated clk_db snapshot owner is absent")
    if chain_pos < snapshot_pos or clock_pos < snapshot_pos:
        errors.append("first-request records are not owned by clk_db snapshot block")
    if (
        "return_obs_active_cycles != 0 &&" not in tail[snapshot_pos:]
        or "(return_obs_active_cycles %" not in tail[snapshot_pos:]
    ):
        errors.append("rate-limited snapshot gate is absent")
    if (
        snapshot_pos >= 0
        and "FIRST_REQUEST_CHAIN" in tail[counter_pos:snapshot_pos]
    ):
        errors.append("FIRST_REQUEST_CHAIN remains inside gated clk_sg block")
    expected_profile = {
        "functional_fix": False,
        "qualified_counter_clock": "u_NDP_Top_new.clk_sg",
        "snapshot_clock": "negedge u_NDP_Top_new.clk_db",
        "cross_domain_modulo_trigger_removed": True,
        "clk_sg_edge_counter_returned": True,
        "first_request_clock_record": "FIRST_REQUEST_CLOCK",
        "frozen_workload_and_configuration_unchanged": True,
    }
    if profile != expected_profile:
        errors.append("observer clock-binding manifest contract differs")
    return errors


def _negative_controls(tail: str, manifest: dict[str, Any]) -> dict[str, Any]:
    cases = {
        "move_snapshot_back_to_gated_clk_sg": tail.replace(
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
        "move_chain_print_into_counter_region": tail.replace(
            '"%0t | FIRST_REQUEST_CHAIN |',
            '"%0t | MOVED_REQUEST_CHAIN |',
            1,
        ),
    }
    controls: dict[str, Any] = {}
    for name, changed in cases.items():
        errors = _clock_binding_errors(changed, manifest)
        controls[name] = {
            "failed_closed": bool(errors),
            "exit_code": 1 if errors else 0,
            "first_error": errors[0] if errors else None,
        }
    return controls


def validate_final_zip(*, write_report: bool = True) -> dict[str, Any]:
    _configure_v11()
    report = v11.validate_final_zip(write_report=False)
    tail, manifest = _tail_from_zip()
    binding_errors = _clock_binding_errors(tail, manifest)
    negatives = _negative_controls(tail, manifest)
    checks = {
        "observer_snapshot_on_ungated_clk_db": not binding_errors,
        "observer_clock_binding_negative_controls": all(
            item["failed_closed"] for item in negatives.values()
        ),
    }
    report["checks"].update(checks)
    errors = [name for name, passed in report["checks"].items() if not passed]
    errors.extend(f"observer_clock: {error}" for error in binding_errors)
    report.update(
        {
            "schema": "qlinearadd-node0007-observer-clock-final-zip-self-audit-v1",
            "status": (
                "PACKAGE_READY_NOT_RUN"
                if not errors
                else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
            ),
            "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
            "errors": errors,
            "error_count": len(errors),
            "observer_clock_binding_errors": binding_errors,
            "observer_clock_binding_negative_controls": negatives,
            "all_required_negative_controls_fail_closed": (
                report.get("all_required_negative_controls_fail_closed") is True
                and all(item["failed_closed"] for item in negatives.values())
            ),
            "source_v11_status": (
                "QUARANTINED_FIRST_REQUEST_OBSERVER_CLOCK_DOMAIN_BINDING"
            ),
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
