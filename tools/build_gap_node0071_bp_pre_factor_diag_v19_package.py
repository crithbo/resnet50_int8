from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_node0071_complete_server_package import (
    deterministic_zip,
    write_json,
)
from tools.gap_node0071_complete_server_runtime import file_records
from tools import build_gap_node0071_v13_buffer_to_ga_diag_package as base


PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
SOURCE_NAME = "r5_n71_gap_v18_bp_pre_factor_diag"
INSTALL_NAME = "r5_n71_gap_v19_bp_pre_factor_stage_scope"
TEST_ID = "r5-gap-node0071-v19-bp-pre-factor-stage-scope"
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_SHA256 = (
    "00ca26f5ad7d30507ed7889d5f19f1a1072c948475e1280198a43b98324916c7"
)
SERVER_RULE_SHA256 = (
    "1e0b40589dddee3bf2b4d081936d37d9a25f78ea2ceb98bc08f2dcf813438589"
)
CANONICAL_RELATIVE = "package_tools/gap_node0071_canonical_decision.py"
EXPECTED_STAGES = [
    "sum_s1",
    "sum_s2",
    "sum_s3",
    "sum_s4",
    "sum_s5",
    "sum_s6",
    "tail_mul",
    "tail_round",
]
ALLOWED_CHANGED = {
    "TEST_PACKAGE_MANIFEST.json",
    "README.md",
    "PREPARE_AND_RUN.sh",
    CANONICAL_RELATIVE,
    "workload/sca_cfg.json",
    "workload/sca_cfg_D.json",
}


class BuildError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def configure_source() -> None:
    base.SOURCE_NAME = SOURCE_NAME
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"marker differs: {label}")
    return text.replace(old, new, 1)


CANONICAL_V19_OVERRIDE = r'''

# v19 ordered-stage scope override.  The expected stage list is read from the
# package manifest at runtime; the parser does not carry a second package-local
# copy of the eight-stage identity.
FINAL_STAGE_SCOPE_ERROR = "PACKAGE_DIAGNOSTIC_DECISION_FINAL_STAGE_SCOPE_ERROR"


def _stage_scope(
    records: list[dict[str, Any]],
    expected_stages: list[str],
) -> dict[str, Any]:
    errors: list[str] = []
    pairs: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    next_index = 0
    starts = 0
    finishes = 0
    for summary_index, record in enumerate(records):
        event = record["event"]
        if event == "EXEC_START":
            starts += 1
            if active is not None:
                errors.append(
                    f"stage start before prior finish: {active['stage']}"
                )
                continue
            if next_index >= len(expected_stages):
                errors.append("unexpected stage start after expected list")
                continue
            active = {
                "stage": expected_stages[next_index],
                "stage_index": next_index,
                "start_summary_index": summary_index,
                "start_time_ps": record["time_ps"],
            }
        elif event == "COMP_FINISH":
            finishes += 1
            if active is None:
                errors.append("COMP_FINISH without paired EXEC_START")
                continue
            pair = dict(active)
            pair.update(
                {
                    "finish_summary_index": summary_index,
                    "finish_time_ps": record["time_ps"],
                }
            )
            pairs.append(pair)
            active = None
            next_index += 1
    completed = [item["stage"] for item in pairs]
    started = completed + ([active["stage"]] if active is not None else [])
    return {
        "expected_ordered_stage_list": list(expected_stages),
        "started_ordered_stage_list": started,
        "completed_ordered_stage_list": completed,
        "paired_stage_records": pairs,
        "active_unfinished_stage": (
            dict(active) if active is not None else None
        ),
        "exec_start_count": starts,
        "comp_finish_count": finishes,
        "sequence_errors": errors,
        "sequence_valid": not errors,
        "final_stage_completed": (
            not errors
            and active is None
            and completed == expected_stages
            and bool(expected_stages)
        ),
    }


_make_decision_v18 = make_decision


def make_decision(
    observer_text: str,
    sim_text: str,
    signal: str,
    simulation_status: int,
    stall_window_cycles: int,
    heartbeat_cycles: int,
    expected_stages: list[str] | None = None,
) -> dict[str, Any]:
    expected = list(expected_stages or ["diagnostic_stage"])
    records = parse_summaries(observer_text)
    scope = _stage_scope(records, expected)
    terminal_marker = (
        simulation_status == 0
        and "Simulation completed successfully!" in sim_text
    )
    record = _make_decision_v18(
        observer_text,
        sim_text,
        signal,
        simulation_status,
        stall_window_cycles,
        heartbeat_cycles,
    )
    if terminal_marker and not scope["final_stage_completed"]:
        record["decision"] = FINAL_STAGE_SCOPE_ERROR
        record["reason"] = (
            "natural terminal marker exists but the expected ordered final "
            "stage scope is incomplete or invalid"
        )
        record["natural_terminal"] = False
    elif terminal_marker and scope["final_stage_completed"]:
        record["decision"] = "FUNCTIONAL_EXECUTION_COMPLETED"
        record["reason"] = (
            "natural terminal and every expected ordered stage pair, "
            "including the final stage, are complete"
        )
        record["natural_terminal"] = True
    record["expected_ordered_stage_list"] = expected
    record["final_stage_scope"] = scope
    digest_payload = dict(record)
    digest_payload.pop("content_digest")
    record["content_digest"]["decision_payload_sha256"] = digest_bytes(
        canonical_bytes(digest_payload)
    )
    return record


_validate_record_v18 = validate_record


def validate_record(record: Any) -> list[str]:
    errors = _validate_record_v18(record)
    if not isinstance(record, dict):
        return errors
    expected = record.get("expected_ordered_stage_list")
    scope = record.get("final_stage_scope")
    if (
        not isinstance(expected, list)
        or not expected
        or not all(isinstance(item, str) and item for item in expected)
        or len(set(expected)) != len(expected)
    ):
        errors.append("expected ordered stage list differs")
    if not isinstance(scope, dict):
        errors.append("final stage scope absent")
    else:
        required = {
            "expected_ordered_stage_list",
            "started_ordered_stage_list",
            "completed_ordered_stage_list",
            "paired_stage_records",
            "active_unfinished_stage",
            "exec_start_count",
            "comp_finish_count",
            "sequence_errors",
            "sequence_valid",
            "final_stage_completed",
        }
        if not required.issubset(scope):
            errors.append("final stage scope fields differ")
        if scope.get("expected_ordered_stage_list") != expected:
            errors.append("stage scope expected list differs")
    if record.get("natural_terminal") is True:
        if (
            not isinstance(scope, dict)
            or scope.get("final_stage_completed") is not True
        ):
            errors.append("natural terminal lacks final-stage completion")
    return errors


def _summary(time: int, event: str, count: int) -> str:
    return (
        f"{time} | {event} | slice=0 active_cycles={time} "
        f"gexec={count} gconfig={count} req={count} rdata={count} "
        "wdata=0 buf4_wr=0 buf4_rd=0 buf5_wr=0 buf5_rd=0\n"
        f"{time} | SG_COUNTS | event={event} "
        "ga_input=0 ga_output=0 mse4_req0=0 mse4_req1=0 "
        "mse4_wdata0=0 mse4_wdata1=0 "
        "mse4_outstanding0=0 mse4_outstanding1=0"
    )


_negative_controls_v18 = negative_controls


def negative_controls() -> dict[str, Any]:
    controls = _negative_controls_v18()
    expected = ["s1", "s2"]
    full = "\n".join(
        [
            _summary(10, "EXEC_START", 1),
            _summary(20, "COMP_FINISH", 1),
            _summary(30, "EXEC_START", 2),
            _summary(40, "COMP_FINISH", 2),
        ]
    )
    early = "\n".join(
        [_summary(10, "EXEC_START", 1), _summary(20, "COMP_FINISH", 1)]
    )
    later_unfinished = "\n".join(
        [
            _summary(10, "EXEC_START", 1),
            _summary(20, "COMP_FINISH", 1),
            _summary(30, "EXEC_START", 2),
        ]
    )
    unmatched = _summary(10, "COMP_FINISH", 1)
    sim_ok = "Simulation completed successfully!"
    full_record = make_decision(
        full, sim_ok, "NONE", 0, 1000, 100, expected
    )
    early_record = make_decision(
        early, sim_ok, "NONE", 0, 1000, 100, expected
    )
    later_record = make_decision(
        later_unfinished, sim_ok, "NONE", 0, 1000, 100, expected
    )
    unmatched_record = make_decision(
        unmatched, sim_ok, "NONE", 0, 1000, 100, expected
    )
    controls.update(
        {
            "ordered_final_stage_positive": {
                "pass": (
                    full_record["natural_terminal"] is True
                    and full_record["final_stage_scope"][
                        "final_stage_completed"
                    ] is True
                )
            },
            "early_stage_completion": {
                "failed_closed": (
                    early_record["decision"] == FINAL_STAGE_SCOPE_ERROR
                    and early_record["natural_terminal"] is False
                )
            },
            "later_stage_started_not_finished": {
                "failed_closed": (
                    later_record["decision"] == FINAL_STAGE_SCOPE_ERROR
                    and later_record["natural_terminal"] is False
                )
            },
            "unmatched_stage_finish": {
                "failed_closed": (
                    unmatched_record["decision"] == FINAL_STAGE_SCOPE_ERROR
                    and unmatched_record["final_stage_scope"][
                        "sequence_valid"
                    ] is False
                )
            },
        }
    )
    if not all(
        item.get("failed_closed", item.get("pass", False))
        for item in controls.values()
    ):
        raise DecisionError("v19 canonical stage-scope control failed")
    return controls


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    observe = sub.add_parser("observe")
    observe.add_argument("--observer-log", type=Path, required=True)
    observe.add_argument("--sim-log", type=Path, required=True)
    observe.add_argument("--signal", required=True)
    observe.add_argument("--simulation-status", type=int, required=True)
    observe.add_argument("--stall-window-cycles", type=int, required=True)
    observe.add_argument("--heartbeat-cycles", type=int, required=True)
    observe.add_argument("--manifest", type=Path, required=True)
    observe.add_argument("--output", type=Path, required=True)
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.command == "self-test":
        result = {
            "schema":
                "gap-node0071-canonical-decision-self-test-v19-v1",
            "status": "PASS",
            "negative_controls": negative_controls(),
        }
    else:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        expected = manifest.get(
            "canonical_decision_contract", {}
        ).get("expected_ordered_stage_list")
        if not isinstance(expected, list):
            raise DecisionError(
                "manifest expected ordered stage list is absent"
            )
        observer_text = (
            args.observer_log.read_text(encoding="utf-8", errors="replace")
            if args.observer_log.is_file()
            else ""
        )
        sim_text = (
            args.sim_log.read_text(encoding="utf-8", errors="replace")
            if args.sim_log.is_file()
            else ""
        )
        result = make_decision(
            observer_text,
            sim_text,
            args.signal,
            args.simulation_status,
            args.stall_window_cycles,
            args.heartbeat_cycles,
            expected,
        )
        errors = validate_record(result)
        if errors:
            raise DecisionError("; ".join(errors))
        args.output.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
'''


def upgrade_canonical(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    marker = '\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n'
    text = replace_once(
        text,
        marker,
        CANONICAL_V19_OVERRIDE + marker,
        "canonical v19 override",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def upgrade_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '    --heartbeat-cycles 262144 \\\n'
        '    --output "$evidence_root/canonical_decision.json" >/dev/null\n',
        '    --heartbeat-cycles 262144 \\\n'
        '    --manifest "$package_manifest" \\\n'
        '    --output "$evidence_root/canonical_decision.json" >/dev/null\n',
        "canonical manifest binding",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def current_receipts(
    source_manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    for item in source_manifest[
        "final_zip_rule_self_audit_contract"
    ]["read_receipt"]:
        receipt = dict(item)
        receipt["sha256"] = sha256(ROOT / receipt["path"])
        receipt["current_match"] = True
        receipts.append(receipt)
    return receipts


def update_manifest(package: Path, source_manifest: dict[str, Any]) -> None:
    manifest = base.replace_identity(source_manifest)
    receipts = current_receipts(source_manifest)
    receipt_by_path = {item["path"]: item["sha256"] for item in receipts}
    manifest.update(
        {
            "schema":
                "gap-node0071-bp-pre-factor-stage-scope-server-package-v19",
            "test_id": TEST_ID,
            "status": "PACKAGE_READY_NOT_RUN",
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "claim_boundary": (
                "v18 factor observer preserved; package-local canonical "
                "runtime now binds the frozen eight-stage ordered execplan "
                "and final-stage natural-terminal scope"
            ),
            "install_name": INSTALL_NAME,
            "package_name": INSTALL_NAME,
            "run_name": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return",
            "supersedes_package_sha256": SOURCE_SHA256,
            "quarantines_package_sha256": SOURCE_SHA256,
            "numeric_analysis_repeated": False,
            "sum_or_tail_numeric_reexecuted": False,
            "source_numeric_payload_reused_without_rebuild": True,
            "functional_fix": False,
            "candidate_release": False,
            "functional_rtl_modified": False,
            "server_run_performed": False,
            "uploaded": False,
            "lease_acquired": False,
        }
    )
    audit_contract = manifest["final_zip_rule_self_audit_contract"]
    audit_contract.update(
        {
            "read_receipt": receipts,
            "all_current_match": True,
            "plan_sha256_mutable_provenance_only":
                sha256(ROOT / ".agents/plan.md"),
            "final_zip_rule_self_audit_pass":
                "PENDING_EXTERNAL_RELEASE_REPORT",
        }
    )
    rules = manifest["rule_receipts"]
    for path, digest in receipt_by_path.items():
        if path.endswith("生成前必读索引.md"):
            rules["generation_index_sha256"] = digest
        elif path.endswith("算子配置规则.md"):
            rules["common_operator_rule_sha256"] = digest
        elif path.endswith("NDP硬件字段语义.md"):
            rules["ndp_field_rule_sha256"] = digest
        elif path.endswith("服务器测试包生成规则.md"):
            rules["server_rule_sha256"] = digest
        elif path.endswith("GAP_int32_mac_bypass_rules.md"):
            rules["gap_int32_rule_sha256"] = digest
        elif path.endswith("GAP_probe_v7_validator_rules.md"):
            rules["gap_probe_rule_sha256"] = digest
        elif path.endswith("精确UINT8量化尾专项规则.md"):
            rules["exact_uint8_tail_rule_sha256"] = digest
    rules["current_match"] = True
    rules["plan_sha256_mutable_provenance_only"] = sha256(
        ROOT / ".agents/plan.md"
    )
    canonical = manifest["canonical_decision_contract"]
    canonical.update(
        {
            "schema":
                "gap-node0071-canonical-diagnostic-decision-v19-v1",
            "version": 19,
            "expected_ordered_stage_list": EXPECTED_STAGES,
            "stage_identity_source":
                "TEST_PACKAGE_MANIFEST.json canonical_decision_contract",
            "stage_pairing": (
                "ordinal EXEC_START/COMP_FINISH pairs bound to the same "
                "expected stage identity"
            ),
            "final_stage_scope_required": True,
            "natural_terminal_requires_final_expected_stage": True,
            "final_stage_scope_error":
                "PACKAGE_DIAGNOSTIC_DECISION_FINAL_STAGE_SCOPE_ERROR",
            "negative_controls":
                list(canonical["negative_controls"])
                + [
                    "early_stage_completion",
                    "later_stage_started_not_finished",
                    "unmatched_stage_finish",
                ],
            "required_fields":
                list(canonical["required_fields"])
                + [
                    "expected_ordered_stage_list",
                    "final_stage_scope",
                ],
        }
    )
    manifest["generation_provenance"].update(
        {
            "tool":
                "tools/build_gap_node0071_bp_pre_factor_diag_v19_package.py",
            "bound_source_package_sha256": SOURCE_SHA256,
            "numeric_payload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "diagnostic_only": True,
            "package_side_change": (
                "fresh identity plus manifest-sourced eight-stage canonical "
                "decision and final-stage scope validation"
            ),
        }
    )
    manifest["post_generation_rule_drift"] = {
        "source_package": SOURCE_NAME,
        "source_package_sha256": SOURCE_SHA256,
        "old_server_rule_sha256":
            "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025",
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "applicable_rule_id":
            "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
        "content_neutral": False,
        "reason": (
            "the frozen workload is an eight-stage ordered execution while "
            "the v18 parser lacked expected-stage and final-stage scope"
        ),
    }
    manifest["files"] = file_records(package)
    write_json(package / "TEST_PACKAGE_MANIFEST.json", manifest)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_source()
    package = base.extract_source(destination)
    source_manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    source_records = file_records(package, exclude_manifest=False)
    numeric_before = file_records(
        package / "workload", exclude_manifest=False
    )
    numeric_before = {
        path: record
        for path, record in numeric_before.items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    base.rewrite_identity(package)
    upgrade_runner(package / "PREPARE_AND_RUN.sh")
    upgrade_canonical(package / CANONICAL_RELATIVE)
    (package / "README.md").write_text(
        "# GAP node0071 v19 bp-pre factor + ordered-stage diagnostic\n\n"
        f"Test ID: `{TEST_ID}`.\n\n"
        "This package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. The v18 "
        "read-only MSE0/MSE3 factor observer and every frozen numeric/config/"
        "workload/golden/bitstream/execplan byte are preserved. The only "
        "semantic diagnostic change binds canonical decisions to the manifest "
        "stage order `sum_s1..sum_s6, tail_mul, tail_round`; natural terminal "
        "is impossible until the final expected stage is paired.\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n",
        encoding="utf-8",
        newline="\n",
    )
    update_manifest(package, source_manifest)
    numeric_after = file_records(
        package / "workload", exclude_manifest=False
    )
    numeric_after = {
        path: record
        for path, record in numeric_after.items()
        if path not in {"sca_cfg.json", "sca_cfg_D.json"}
    }
    if numeric_before != numeric_after or len(numeric_after) != 73:
        raise BuildError("frozen 73-file numeric/workload tree drifted")
    final_records = file_records(package, exclude_manifest=False)
    if set(source_records) != set(final_records):
        raise BuildError("relative file set changed")
    changed = {
        path
        for path in source_records
        if source_records[path] != final_records[path]
    }
    if changed != ALLOWED_CHANGED:
        raise BuildError(f"changed path set differs: {sorted(changed)}")
    frozen = sorted(set(source_records) - ALLOWED_CHANGED)
    return package, {
        "source_v18_zip_sha256": SOURCE_SHA256,
        "changed_paths": sorted(changed),
        "changed_paths_exact_allowlist": True,
        "frozen_numeric_workload_file_count": len(numeric_after),
        "frozen_numeric_workload_tree_equal": True,
        "frozen_semantic_file_count": len(frozen),
        "frozen_semantic_tree_equal": all(
            source_records[path] == final_records[path] for path in frozen
        ),
        "canonical_sha256": sha256(package / CANONICAL_RELATIVE),
    }


def repeat_build(package: Path, zip_path: Path) -> dict[str, Any]:
    deterministic_zip(package, zip_path, archive_root=INSTALL_NAME)
    digest = sha256(zip_path)
    tree = file_records(package, exclude_manifest=False)
    with tempfile.TemporaryDirectory(
        prefix="gap-node0071-v19-repeat-"
    ) as temp:
        repeated, _ = build_directory(Path(temp))
        repeated_zip = Path(temp) / f"{INSTALL_NAME}.zip"
        deterministic_zip(
            repeated, repeated_zip, archive_root=INSTALL_NAME
        )
        if sha256(repeated_zip) != digest:
            raise BuildError("repeat ZIP differs")
        if file_records(repeated, exclude_manifest=False) != tree:
            raise BuildError("repeat package tree differs")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=PACKAGE_ROOT)
    args = parser.parse_args()
    output_root = args.output_root.resolve()
    package = output_root / INSTALL_NAME
    zip_path = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (package, zip_path, sidecar, validation):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    try:
        package, proof = build_directory(output_root)
        repeated = repeat_build(package, zip_path)
        digest = sha256(zip_path)
        sidecar.write_text(
            f"{digest}  {zip_path.name}\n",
            encoding="ascii",
            newline="\n",
        )
        result = {
            "schema":
                "gap-node0071-bp-pre-factor-stage-scope-v19-build-v1",
            "status": "PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "test_id": TEST_ID,
            "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "package": str(package),
            "zip": str(zip_path),
            "zip_size_bytes": zip_path.stat().st_size,
            "zip_sha256": digest,
            "sidecar": str(sidecar),
            "sidecar_sha256": sha256(sidecar),
            **proof,
            "repeat_build": repeated,
            "numeric_analysis_repeated": False,
            "workload_rebuilt": False,
            "config_semantics_rebuilt": False,
            "functional_rtl_modified": False,
            "server_action": False,
        }
        write_json(validation, result)
    except Exception as error:
        print(f"GAP v19 build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
