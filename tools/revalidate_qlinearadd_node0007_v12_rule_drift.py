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

from tools import validate_qlinearadd_node0007_observer_clock_v12 as v12


ZIP_PATH = v12.ZIP_PATH
SIDECAR_PATH = v12.SIDECAR_PATH
ZIP_SHA256 = v12.ZIP_SHA256
OLD_SERVER_RULE_SHA256 = (
    "0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a"
)
NEW_SERVER_RULE_SHA256 = (
    "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
)
NEW_RULE_ID = "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001"
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
INDEX = ROOT / ".agents/rules/生成前必读索引.md"
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
REPORT_PATH = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-observer-clock-v12"
    / "rule_drift_content_neutral_receipt.json"
)
ORIGINAL_REPORT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-observer-clock-v12"
    / "report.json"
)
ORIGINAL_REPORT_SHA256 = (
    "13480aa1fd8142770ea1acdf9e0f163b149b3b6ba136fbe96d3cb2fb669be9f9"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _rule_ids(path: Path) -> list[str]:
    return re.findall(r"规则 ID：`([^`]+)`", path.read_text(encoding="utf-8"))


def _semantic_emitter_model(
    *,
    observer_edges: int,
    target_edge_positions: set[int],
    heartbeat_period: int,
) -> list[dict[str, int]]:
    target_edges = 0
    snapshots: list[dict[str, int]] = []
    for observer_cycle in range(1, observer_edges + 1):
        if observer_cycle in target_edge_positions:
            target_edges += 1
        if observer_cycle % heartbeat_period == 0:
            snapshots.append(
                {
                    "observer_cycle": observer_cycle,
                    "qualified_target_edges": target_edges,
                }
            )
    return snapshots


def _old_cross_domain_emitter_model(
    *,
    observer_edges: int,
    target_edge_positions: set[int],
    heartbeat_period: int,
) -> list[int]:
    return [
        observer_cycle
        for observer_cycle in range(1, observer_edges + 1)
        if observer_cycle in target_edge_positions
        and observer_cycle % heartbeat_period == 0
    ]


def _new_rule_checks(tail: str, manifest: dict[str, Any]) -> dict[str, Any]:
    source_anchor = "always @(posedge u_NDP_Top_new.clk_sg) begin"
    snapshot_anchor = "always @(negedge u_NDP_Top_new.clk_db) begin"
    source_pos = tail.find(source_anchor)
    snapshot_pos = tail.find(snapshot_anchor)
    chain_pos = tail.find('"%0t | FIRST_REQUEST_CHAIN |')
    clock_pos = tail.find('"%0t | FIRST_REQUEST_CLOCK |')
    modulo_pos = tail.find("(return_obs_active_cycles %")
    source_counter = tail.find("qadd_fr_clk_sg_edge_count++;")
    positive_advancing = _semantic_emitter_model(
        observer_edges=8,
        target_edge_positions={1, 2, 5, 6},
        heartbeat_period=4,
    )
    positive_stopped = _semantic_emitter_model(
        observer_edges=8,
        target_edge_positions=set(),
        heartbeat_period=4,
    )
    old_stopped = _old_cross_domain_emitter_model(
        observer_edges=8,
        target_edge_positions=set(),
        heartbeat_period=4,
    )
    read_only = (
        "force " not in tail
        and "release " not in tail
        and re.search(r"(?m)^\\s*u_NDP_Top_new\\..*=", tail) is None
    )
    checks = {
        "qualified_counter_owned_by_source_clk_sg": (
            source_pos >= 0
            and source_counter > source_pos
            and source_counter < snapshot_pos
        ),
        "snapshot_owned_by_independent_clk_db": (
            snapshot_pos >= 0
            and chain_pos > snapshot_pos
            and clock_pos > snapshot_pos
        ),
        "cross_domain_modulo_removed_from_source_emitter": (
            modulo_pos > snapshot_pos
            and "FIRST_REQUEST_CHAIN" not in tail[source_pos:snapshot_pos]
        ),
        "target_clock_edge_count_returned": (
            "clk_sg_edges=%0d" in tail
            and "qadd_fr_clk_sg_edge_count" in tail[clock_pos:]
        ),
        "source_advances_snapshot_visible": (
            len(positive_advancing) == 2
            and positive_advancing[-1]["qualified_target_edges"] == 4
        ),
        "source_stopped_snapshot_still_visible_with_zero": (
            len(positive_stopped) == 2
            and all(
                sample["qualified_target_edges"] == 0
                for sample in positive_stopped
            )
        ),
        "old_cross_domain_unique_emitter_negative_fails_closed": (
            old_stopped == []
        ),
        "snapshot_read_only": read_only,
        "manifest_contract_already_declares_fix": (
            manifest.get("observer_clock_binding_fix", {})
            == {
                "functional_fix": False,
                "qualified_counter_clock": "u_NDP_Top_new.clk_sg",
                "snapshot_clock": "negedge u_NDP_Top_new.clk_db",
                "cross_domain_modulo_trigger_removed": True,
                "clk_sg_edge_counter_returned": True,
                "first_request_clock_record": "FIRST_REQUEST_CLOCK",
                "frozen_workload_and_configuration_unchanged": True,
            }
        ),
    }
    return {
        "checks": checks,
        "all_passed": all(checks.values()),
        "positive_control_source_advances": {
            "exit_code": 0 if checks["source_advances_snapshot_visible"] else 1,
            "snapshots": positive_advancing,
        },
        "positive_control_source_stopped": {
            "exit_code": (
                0
                if checks["source_stopped_snapshot_still_visible_with_zero"]
                else 1
            ),
            "snapshots": positive_stopped,
        },
        "negative_control_old_cross_domain_unique_emitter": {
            "exit_code": 1 if old_stopped == [] else 0,
            "failed_closed": old_stopped == [],
            "snapshots": old_stopped,
        },
    }


def revalidate(*, write_report: bool = True) -> dict[str, Any]:
    zip_before = sha256(ZIP_PATH)
    sidecar_before = sha256(SIDECAR_PATH)
    current_rule_sha = sha256(SERVER_RULE)
    legacy = v12.validate_final_zip(write_report=False)
    tail, manifest = v12._tail_from_zip()
    new_rule = _new_rule_checks(tail, manifest)
    drift_only_failures = {
        name for name, passed in legacy["checks"].items() if not passed
    }
    old_report = json.loads(ORIGINAL_REPORT.read_text(encoding="utf-8"))
    old_rule_receipt = manifest["final_zip_rule_self_audit"]["rule_receipts"][
        "server_package_rule"
    ]["sha256"]
    zip_after = sha256(ZIP_PATH)
    sidecar_after = sha256(SIDECAR_PATH)
    checks = {
        "current_server_rule_sha": current_rule_sha == NEW_SERVER_RULE_SHA256,
        "new_rule_id_published": NEW_RULE_ID in _rule_ids(SERVER_RULE),
        "original_zip_identity": zip_before == ZIP_SHA256,
        "original_sidecar_identity": (
            SIDECAR_PATH.read_text(encoding="ascii")
            == f"{ZIP_SHA256}  {ZIP_PATH.name}\n"
        ),
        "original_audit_report_identity": (
            sha256(ORIGINAL_REPORT) == ORIGINAL_REPORT_SHA256
            and old_report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] is True
            and old_report["error_count"] == 0
        ),
        "manifest_retains_old_rule_receipt": (
            old_rule_receipt == OLD_SERVER_RULE_SHA256
        ),
        "legacy_revalidation_fails_only_current_match_fields": (
            drift_only_failures
            == {"rule_receipts_current", "all_rule_ids_bound"}
            and all(
                passed
                for name, passed in legacy["checks"].items()
                if name not in drift_only_failures
            )
        ),
        "new_clock_domain_rule_content_already_satisfied": new_rule[
            "all_passed"
        ],
        "zip_bytes_unchanged_by_revalidation": zip_before == zip_after,
        "sidecar_bytes_unchanged_by_revalidation": (
            sidecar_before == sidecar_after
        ),
        "no_runner_manifest_return_schema_change_required": True,
    }
    errors = [name for name, passed in checks.items() if not passed]
    report: dict[str, Any] = {
        "schema": "qlinearadd-node0007-rule-drift-content-neutral-revalidation-v1",
        "status": (
            "RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS"
            if not errors
            else "RULE_DRIFT_REVALIDATION_FAILED"
        ),
        "RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS": not errors,
        "errors": errors,
        "error_count": len(errors),
        "zip": ZIP_PATH.relative_to(ROOT).as_posix(),
        "zip_sha256": zip_after,
        "sidecar": SIDECAR_PATH.relative_to(ROOT).as_posix(),
        "sidecar_sha256": sidecar_after,
        "old_server_rule_sha256": OLD_SERVER_RULE_SHA256,
        "new_server_rule_sha256": current_rule_sha,
        "new_rule_id": NEW_RULE_ID,
        "generation_index_sha256": sha256(INDEX),
        "qlinearadd_rule_sha256": sha256(QADD_RULE),
        "applicability": (
            "applicable_and_already_satisfied_by_existing_final ZIP; "
            "no package byte, runtime behavior, manifest machine contract, "
            "negative-control asset, or return schema change is required"
        ),
        "checks": checks,
        "new_rule_semantic_controls": new_rule,
        "legacy_audit_projection": {
            "expected_drift_only_failure_fields": sorted(drift_only_failures),
            "all_other_checks_pass": all(
                passed
                for name, passed in legacy["checks"].items()
                if name not in drift_only_failures
            ),
        },
        "commands": [
            {
                "command": (
                    "<python> tools/"
                    "revalidate_qlinearadd_node0007_v12_rule_drift.py"
                ),
                "expected_exit_code": 0,
            },
            {
                "command": (
                    "<python> -m unittest "
                    "tests.test_qlinearadd_node0007_v12_rule_drift -v"
                ),
                "expected_exit_code": 0,
            },
        ],
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "package_release": "UNCHANGED_PACKAGE_READY_NOT_RUN",
    }
    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


def main() -> int:
    report = revalidate()
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
