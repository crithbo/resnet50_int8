#!/usr/bin/env python3
"""Build the single first-fresh p35 package from frozen p34b bytes."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p34_armtoken_package as p34


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p34b_armtoken"
PACKAGE_ID = "r5_n4_0cc_p35_armknown"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_934_761
SOURCE_SHA256 = "98d9f8b23824d2b5ec9e90f87fdfa1a3ee6bc61df5c9edca81ff19cf5f5b5fd1"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p34b_return_analysis/report.json"
ANALYSIS_SHA256 = "3c40b9f32dff646387c72ad4bb92a594ecf4c76b6ef3066b9fe991be7f7283aa"
SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p35_armknown_source_bound"
GENERATED = SOURCE_BOUND / "generated"
PARSER = ROOT / "tools/conv_native_four_lane_p35_arm_known_parser.py"
HELPER = ROOT / "tools/server_post_sim_return.py"
HELPER_SHA256 = "19bea6cc8bb5bd6247f7d2da67de3df967a562f1193c82a2f1a1ddb1ae483e6f"
RULE_EPOCH = "20260811-native-live-causal-partial-exit-v1"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p35_armknown/build"
base = p34.base


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def receipt(path: Path, package: Path) -> dict[str, Any]:
    return {"path": path.relative_to(package).as_posix(), "bytes": path.stat().st_size, "sha256": base.sha256(path)}


def configure() -> None:
    p34.SOURCE_ID = SOURCE_ID
    p34.PACKAGE_ID = PACKAGE_ID
    p34.SOURCE_ZIP = SOURCE_ZIP
    p34.SOURCE_BYTES = SOURCE_BYTES
    p34.SOURCE_SHA256 = SOURCE_SHA256
    p34.ANALYSIS = ANALYSIS
    p34.SOURCE_BOUND = SOURCE_BOUND
    p34.GENERATED = GENERATED
    p34.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    p34.configure()


def encode(layout: list[dict[str, Any]], values: dict[str, int]) -> str:
    payload = 0
    for field in layout:
        width = int(field["width_bits"])
        payload = (payload << width) | (int(values.get(field["name"], 0)) & ((1 << width) - 1))
    return f"{payload:x}"


def make_live_fixture(contract: dict[str, Any]) -> str:
    target = contract["target_parent"]
    buffer_instance = target + ".u_Buffer.codex_probe_row2_clear_window_write_owner_inst"
    arm_instance = target + ".u_Array_Request_Manager.codex_probe_arm_row2_accept_token_state_inst"
    lines = []
    for boundary in contract["required_boundaries"]:
        instance = buffer_instance if boundary == contract["buffer_boundary"] else arm_instance
        lines.append(f"CODEX_PROBE_V1 kind=ENABLED boundary={boundary} instance={instance}")
    lines.append(f"CODEX_PROBE_V1 kind=TRIGGER boundary={contract['buffer_boundary']} instance={buffer_instance} time=100 mask=1 payload=0 seq=0")
    for index in range(2):
        time = 110 + index * 10
        values = {
            "arm2buf_req_addr": 2, "arm2buf_req_valid": 255, "arm2buf_req_rw": 1,
            "arm2buf_wvalid": 1, "buf2arm_req_ready": 1, "array_req_addr": 2,
            "array_counter_0": index, "array_counter_1": 0, "array_life_cnt": 0,
            "array2buf_valid_bit": 255, "array2buf_last_bit": 0,
            "array2buf_last_index": 15, "array2buf_same_bit": 0,
            "array_wreq_addr_rst": 0, "arm_addr_update": 1,
            "add_array_counter_0": 1, "add_array_counter_1": 0, "add_array_life_cnt": 0,
        }
        lines.append(f"CODEX_PROBE_V1 kind=EVENT boundary={contract['buffer_boundary']} instance={buffer_instance} time={time} mask=2 payload=0 seq={index}")
        lines.append(f"CODEX_PROBE_V1 kind=EVENT boundary={contract['arm_boundary']} instance={arm_instance} time={time} mask=5 payload={encode(contract['arm_payload_layout_msb_to_lsb'], values)} seq={index}")
    lines.append(f"CODEX_PROBE_V1 kind=TRIGGER boundary={contract['final_boundary']} instance={arm_instance} time=130 mask=1 payload=0 seq=0")
    return "\n".join(lines) + "\n"


def install_correlator(package: Path) -> dict[str, dict[str, Any]]:
    for path in (
        package / "diagnostics/arm_token_contract.json",
        package / "package_tools/arm_token_parser.py",
        package / "diagnostics/arm_known_contract.json",
        package / "package_tools/arm_known_parser.py",
    ):
        if path.exists():
            path.unlink()
    mapping = {
        SOURCE_BOUND / "arm_known_contract.json": package / "diagnostics/arm_known_contract.json",
        PARSER: package / "package_tools/arm_known_parser.py",
        SOURCE_BOUND / "rule_change_ack.json": package / "diagnostics/rule_change_ack.json",
    }
    result: dict[str, dict[str, Any]] = {}
    for source, target in mapping.items():
        if not source.is_file():
            raise BuildError(f"p35 correlator source is absent: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        result[target.relative_to(package).as_posix()] = receipt(target, package)
    contract = json.loads((package / "diagnostics/arm_known_contract.json").read_text(encoding="utf-8"))
    fixture = package / "diagnostics/live_fixtures/arm_known_event.log"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(make_live_fixture(contract), encoding="utf-8", newline="\n")
    result[fixture.relative_to(package).as_posix()] = receipt(fixture, package)
    return result


def patch_post_sim(package: Path) -> dict[str, dict[str, Any]]:
    helper = package / "package_tools/server_post_sim_return.py"
    shutil.copyfile(HELPER, helper)
    if base.sha256(helper) != HELPER_SHA256:
        raise BuildError("current shared post-sim helper identity differs")
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["package_id"] = PACKAGE_ID
    request["claim_boundary"] = (
        "p35 c0 exact-target binary-known live Buffer/ARM token diagnostic only. Core publication remains "
        "independent of plugin success; natural terminal, formal 320D and E3/E4/E5 are unclaimed."
    )
    request["core_entries"] = [
        row for row in request["core_entries"]
        if row.get("archive") not in {"evidence/arm_token_decision.json", "evidence/arm_known_decision.json"}
    ]
    request["core_entries"].append({"archive": "evidence/arm_known_decision.json", "required": True, "source": "evidence/arm_known_decision.json", "source_root": "attempt"})
    request["plugins"] = [
        row for row in request["plugins"]
        if row.get("plugin_id") not in {"arm_token_parser", "arm_known_parser"}
    ]
    for row in request["plugins"]:
        row["required_for_adjudication"] = False
    request["plugins"].insert(1, {
        "argv": ["python3", "{package_root}/package_tools/arm_known_parser.py", "--log", "{attempt_root}/c0/source_bound_causal.log", "--contract", "{package_root}/diagnostics/arm_known_contract.json", "--output", "{attempt_root}/evidence/arm_known_decision.json"],
        "cwd_root": "attempt", "plugin_id": "arm_known_parser", "required_for_adjudication": True, "timeout_seconds": 120,
    })
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract.update(
        {
            "package_id": PACKAGE_ID,
            "helper_sha256": HELPER_SHA256,
            "request_sha256": base.sha256(request_path),
            "claim_boundary": request["claim_boundary"],
            "partial_exit_live_causal_record": {
                "rule_id": "CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001",
                "enforcement": "required_next_fresh",
                "required_signals": ["INT", "TERM"],
                "final_block_ring_sole_input_forbidden": True,
                "plugin_dispositions": [
                    {
                        "plugin_id": "arm_known_parser",
                        "disposition": "LIVE_CAUSAL_FIXTURE",
                        "input_root": "attempt",
                        "input_path": "c0/source_bound_causal.log",
                        "fixture_member": "diagnostics/live_fixtures/arm_known_event.log",
                        "input_kind": "QUALIFIED_LIVE_RECORD",
                        "output_root": "attempt",
                        "output_path": "evidence/arm_known_decision.json",
                        "expected_exit_code": 0,
                        "timeout_seconds": 30,
                    }
                ],
            },
        }
    )
    write_json(contract_path, contract)
    return {"helper": receipt(helper, package), "request": receipt(request_path, package), "contract": receipt(contract_path, package)}


def patch_docs(package: Path) -> None:
    layout_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout["claim_boundary"] = "p35 preserves 87 p34b payload/config members and changes only identity plus binary-known live diagnostics."
    paths = base.projected_paths(package, layout)
    longest = max(paths, key=lambda item: (len(item), item))
    layout["path_budget"]["max_projected_absolute_path_chars"] = layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    write_json(layout_path, layout)
    source_path = package / "diagnostics/source_bound_final_zip_contract.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["claim_boundary"] = "p35 generated binary-known live exact-target ARM state; X/Z must fail closed."
    source["family_target_correlator"] = {"contract": "diagnostics/arm_known_contract.json", "parser": "package_tools/arm_known_parser.py", "decision": "evidence/arm_known_decision.json"}
    write_json(source_path, source)
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value.update({"schema": "conv-native-four-lane-p35-armknown-pointer-v1", "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN"})
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p35 binary-known ARM diagnostic\n\n"
        "Fresh successor of tested p34b. The 87 installed payload/config members remain frozen. The required parser consumes live EVENT rows, excludes the undriven p34 leaf, and rejects any X/Z payload.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8", newline="\n",
    )


def patch_manifest(package: Path, changed: list[str], generated: dict[str, dict[str, Any]], target: dict[str, dict[str, Any]], runner: dict[str, Any], post_sim: dict[str, dict[str, Any]]) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    if base.sha256(ANALYSIS) != ANALYSIS_SHA256 or analysis.get("status") != "P34B_PARTIAL_RETURN_VALID_PACKAGE_PARSER_FAIL_OPEN_SUCCESSOR_REQUIRED" or analysis.get("valid") is not True:
        raise BuildError("formal p34b analysis differs")
    value.update(
        {
            "schema": "conv-native-four-lane-0ccae916-p35-armknown-package-v1",
            "package_identity": PACKAGE_ID,
            "install_name": PACKAGE_ID,
            "workload_install_name": PACKAGE_ID,
            "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
            "return_name": f"{PACKAGE_ID}_<execution_id>_return.zip",
            "status": "PACKAGE_READY_NOT_RUN",
            "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        }
    )
    for key in ("source_p33b_formal_return_analysis", "source_p32b_formal_return_analysis"):
        value.pop(key, None)
    value["source_p34b_formal_return_analysis"] = {
        "path": ANALYSIS.relative_to(ROOT).as_posix(), "sha256": ANALYSIS_SHA256,
        "return_sha256": analysis["return_identity"]["sha256"], "source_zip_sha256": analysis["source_identity"]["sha256"],
        "classification": analysis["classification"], "last_progress_guard": analysis["failure_localization"]["LAST_PROVEN_GOOD"],
        "first_divergence": analysis["failure_localization"]["FIRST_DIVERGENCE"],
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p34b payload contains Z and its parser failed open; p35 excludes the undriven leaf and rejects every non-binary accepted payload",
        "authorized_config_change": None, "numeric_w3_golden_repeated": False,
    }
    value["rule_change_epoch"] = {
        "epoch_id": RULE_EPOCH, "family": "conv_native_four_lane", "package_id": PACKAGE_ID,
        "first_fresh_after_change": True, "notification_acknowledged": True,
        "rule_ids": ["CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001"],
        "upload_hold_until": "INDEPENDENT_EXTRA_AUDIT_PASS",
    }
    value["source_bound_observer_binding"].update({"claim_boundary": "c0 binary-known exact-target live ARM state only", "generated_members": generated, "runner": runner, "functional_rtl_changed": False, "target_epoch_correlator_members": target})
    value["post_sim_return_core"].update({"members": post_sim, "runner": {"path": "PREPARE_AND_RUN.sh", "bytes": (package / "PREPARE_AND_RUN.sh").stat().st_size, "sha256": base.sha256(package / "PREPARE_AND_RUN.sh"), "shared_post_sim_invocations": (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8").count('python3 "$post_sim_helper" finalize --request "$post_sim_request"')}, "claim_boundary": json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))["claim_boundary"]})
    value["identity_rebound_text_members"] = changed
    value["release_gate_applicability"].update({"materialized_config": "receipt_reuse_byte_equal_p34b", "numeric_w3_golden": "record_only_byte_equal_receipt_reuse", "first_fresh_extra_audit": "blocking_applicable_new_live_causal_rule_epoch"})
    value["release_gate_matrix"]["materialized_config"].update({"applicability": "receipt_reuse", "blocking": False, "pass": True, "scope": "87 p34b installed payload members byte-equal and SCA identity-normalized equal"})
    value["release_gate_matrix"]["source_bound_observer_generation"]["pass"] = True
    value["release_gate_matrix"]["source_bound_final_zip"]["pass"] = None
    value["release_gate_matrix"]["post_sim_return_core"]["pass"] = None
    value["release_gate_matrix"]["first_fresh_extra_audit"] = {"applicability": "blocking_applicable", "blocking": True, "pass": None, "epoch_id": RULE_EPOCH, "upload_hold": True}
    layout = json.loads((package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(encoding="utf-8"))
    projected = base.projected_paths(package, layout)
    longest = max(projected, key=lambda item: (len(item), item))
    inner = [row.relative_to(package).as_posix() for row in package.rglob("*") if row.is_file() and row != path] + ["package_manifest.json"]
    value["path_length_budget"].update(
        {
            "longest_projected_relative_path": longest,
            "longest_projected_relative_path_chars": len(longest),
            "max_projected_relative_path_chars": len(longest),
            "max_projected_absolute_path_chars": layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest),
            "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{relative}") for relative in inner),
            "max_inner_suffix_chars": max(map(len, inner)),
            "max_inner_depth": max(len(PurePosixPath(relative).parts) for relative in inner),
            "max_inner_component_chars": max(len(part) for relative in inner for part in PurePosixPath(relative).parts),
            "outer_identity_repeated_inside": False,
        }
    )
    base.refresh_manifest_files(package, value)
    write_json(path, value)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure()
    p34.prior.configure_predecessor()
    package = base.safe_extract(SOURCE_ZIP, destination)
    changed = p34.prior.predecessor.predecessor.p28.replace_identity(package)
    generated = p34.prior.predecessor.predecessor.p28.install_generated(package)
    target = install_correlator(package)
    runner = p34.prior.predecessor.predecessor.p28.patch_runner(package)
    post_sim = patch_post_sim(package)
    patch_docs(package)
    patch_manifest(package, changed, generated, target, runner, post_sim)
    return package, {"identity_members": changed, "generated": generated, "target_correlator": target, "runner": runner, "post_sim": post_sim}


def tree_receipt(package: Path) -> dict[str, dict[str, Any]]:
    return {row.relative_to(package).as_posix(): {"bytes": row.stat().st_size, "sha256": base.sha256(row)} for row in sorted(package.rglob("*")) if row.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = (output / PACKAGE_ID, output / f"{PACKAGE_ID}.zip", output / f"{PACKAGE_ID}.zip.sha256", output / f"{PACKAGE_ID}.build.json")
    if any(target.exists() for target in targets):
        raise BuildError("refusing to overwrite p35 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p34b source differs")
    package, receipts = build_directory(output)
    frozen = p34.prior.frozen_checks(package)
    if not frozen["frozen_install_payload_byte_equal"] or not all(frozen["sca_identity_normalized_equal"].values()) or frozen["frozen_install_payload_member_count"] != 87:
        raise BuildError("frozen p34b payload differs")
    with tempfile.TemporaryDirectory(prefix=".p35_repeat_", dir=ROOT) as temporary:
        repeated, _ = build_directory(Path(temporary))
        deterministic = tree_receipt(repeated) == tree_receipt(package)
    if not deterministic:
        raise BuildError("p35 deterministic staging trees differ")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p35-armknown-build-v1",
        "status": "PACKAGE_BUILT_UPLOAD_HELD_PENDING_FINAL_AND_EXTRA_AUDIT",
        "package_identity": PACKAGE_ID,
        "source_p34b_zip_sha256": SOURCE_SHA256,
        "source_p34b_analysis_sha256": ANALYSIS_SHA256,
        "rule_change_epoch_id": RULE_EPOCH,
        "first_fresh_after_change": True,
        "prebuild_aggregate_top_level_invocations": 1,
        "final_zip_count": 1,
        "zip": str(zip_path), "zip_bytes": zip_path.stat().st_size, "zip_sha256": zip_sha,
        "deterministic_double_build_tree_equal": deterministic,
        "receipts": receipts, "frozen": frozen,
        "functional_rtl_modified": False, "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
