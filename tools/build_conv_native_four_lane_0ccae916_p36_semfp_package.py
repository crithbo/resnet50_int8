#!/usr/bin/env python3
"""Build the one p36 semantic-fingerprint successor from frozen p35c bytes."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import build_conv_native_four_lane_0ccae916_p35_armknown_package as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p36_semfp"
SOURCE_ID = "r5_n4_0cc_p35c_armknown"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_938_804
SOURCE_SHA256 = "b755592dbd01f05a63f0471ed76ede7673ab987b57a2cf579a8566a3d26f59fc"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p35c_return_analysis/report_v2.json"
ANALYSIS_SHA256 = "467a302034be259a629af67a9547a463f51a83e0046aaea3342803ecec516166"
SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p36_semfp_source_bound"
GENERATED = SOURCE_BOUND / "generated"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p36_semfp/build"
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"
RULE_IDS = [
    "CDA-SERVER-DIAGNOSTIC-EXACT-INSTANCE-IDENTITY-AND-GROUPING-001",
    "CDA-SERVER-DIAGNOSTIC-PAYLOAD-KNOWNNESS-WIDTH-FAIL-CLOSED-001",
    "CDA-SERVER-DIAGNOSTIC-SEMANTIC-FINGERPRINT-FIRST-USE-AUDIT-001",
]
base = prior.base
_old_patch_manifest = prior.patch_manifest
_old_patch_post_sim = prior.patch_post_sim
_old_patch_docs = prior.patch_docs
_old_install_correlator = prior.install_correlator


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def receipt(path: Path, package: Path) -> dict[str, Any]:
    return {"path": path.relative_to(package).as_posix(), "bytes": path.stat().st_size, "sha256": base.sha256(path)}


def configure() -> None:
    prior.SOURCE_ID = SOURCE_ID
    prior.PACKAGE_ID = PACKAGE_ID
    prior.SOURCE_ZIP = SOURCE_ZIP
    prior.SOURCE_BYTES = SOURCE_BYTES
    prior.SOURCE_SHA256 = SOURCE_SHA256
    prior.ANALYSIS = ANALYSIS
    prior.ANALYSIS_SHA256 = ANALYSIS_SHA256
    prior.SOURCE_BOUND = SOURCE_BOUND
    prior.GENERATED = GENERATED
    prior.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    prior.RULE_EPOCH = EPOCH
    prior.configure()


def make_live_fixture(contract: dict[str, Any]) -> str:
    target = contract["target_parent"]
    buffer_instance = target + ".u_Buffer.codex_probe_row2_clear_window_write_owner_inst"
    arm_instance = target + ".u_Array_Request_Manager.codex_probe_arm_row2_accept_token_state_inst"
    widths = {"row2_clear_window_write_owner": 98, "arm_row2_accept_token_state": 45, "final_same_row2_block": 17}
    lines: list[str] = []
    for boundary in contract["required_boundaries"]:
        instance = buffer_instance if boundary == contract["buffer_boundary"] else arm_instance
        if boundary == contract["final_boundary"]:
            instance = target + ".u_Array_Request_Manager.codex_probe_final_same_row2_block_inst"
        lines.append(f"CODEX_PROBE_V1 kind=ENABLED boundary={boundary} instance={instance}")
    lines.append(f"CODEX_PROBE_V1 kind=TRIGGER boundary={contract['buffer_boundary']} instance={buffer_instance} time=100 mask=1 payload=0 seq=0 payload_known=1 payload_width={widths[contract['buffer_boundary']]}")
    for index in range(2):
        time = 110 + index * 10
        values = {
            "arm2buf_req_addr": 2, "arm2buf_req_valid": 255, "arm2buf_req_rw": 1,
            "arm2buf_wvalid": 1, "buf2arm_req_ready": 1, "array_req_addr": 2,
            "array_counter_0": index, "array_counter_1": 0, "array_life_cnt": 0,
            "array2buf_valid_bit": 255, "array2buf_last_bit": 0,
            "array2buf_last_index": 15, "array2buf_same_bit": 0,
            "array_wreq_addr_rst": 0, "arm_addr_update": 1,
            "add_array_counter_0": 1, "add_array_counter_1": 0,
        }
        lines.append(f"CODEX_PROBE_V1 kind=EVENT boundary={contract['buffer_boundary']} instance={buffer_instance} time={time} mask=2 payload=0 seq={index} payload_known=1 payload_width={widths[contract['buffer_boundary']]}")
        lines.append(f"CODEX_PROBE_V1 kind=EVENT boundary={contract['arm_boundary']} instance={arm_instance} time={time} mask=5 payload={prior.encode(contract['arm_payload_layout_msb_to_lsb'], values)} seq={index} payload_known=1 payload_width={widths[contract['arm_boundary']]}")
    final_instance = target + ".u_Array_Request_Manager.codex_probe_final_same_row2_block_inst"
    lines.append(f"CODEX_PROBE_V1 kind=TRIGGER boundary={contract['final_boundary']} instance={final_instance} time=130 mask=1 payload=0 seq=0 payload_known=1 payload_width={widths[contract['final_boundary']]}")
    return "\n".join(lines) + "\n"


def install_correlator(package: Path) -> dict[str, dict[str, Any]]:
    result = _old_install_correlator(package)
    target = package / "diagnostics/exact_instance_identity.json"
    shutil.copyfile(SOURCE_BOUND / "exact_instance_identity.json", target)
    result[target.relative_to(package).as_posix()] = receipt(target, package)
    return result


def patch_post_sim(package: Path) -> dict[str, dict[str, Any]]:
    result = _old_patch_post_sim(package)
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["claim_boundary"] = (
        "p36 c0 exact-instance, binary-known, declared-width ARM token diagnostic only. Core publication remains "
        "independent of plugin success; natural terminal, formal 320D and E3/E4/E5 are unclaimed."
    )
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["package_id"] = PACKAGE_ID
    contract["request_sha256"] = base.sha256(request_path)
    contract["claim_boundary"] = request["claim_boundary"]
    write_json(contract_path, contract)
    result["request"] = receipt(request_path, package)
    result["contract"] = receipt(contract_path, package)
    return result


def patch_docs(package: Path) -> None:
    _old_patch_docs(package)
    layout_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout["claim_boundary"] = "p36 preserves 87 p35c payload/config members and changes only identity plus exact-instance/known-width diagnostics."
    paths = base.projected_paths(package, layout)
    longest = max(paths, key=lambda item: (len(item), item))
    layout["path_budget"]["max_projected_absolute_path_chars"] = layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    write_json(layout_path, layout)
    source_path = package / "diagnostics/source_bound_final_zip_contract.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["claim_boundary"] = "p36 exact canonical target plus binary-known declared-width payload; wrong instance, X/Z and width mismatch fail closed."
    write_json(source_path, source)
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value.update({"schema": "conv-native-four-lane-p36-semfp-pointer-v1", "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN"})
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p36 exact-instance semantic-fingerprint diagnostic\n\n"
        "Fresh successor of tested p35c. All 87 installed payload/config members are frozen. Both undriven ARM add_* leaves are excluded; generated exact-instance and payload-known/width semantics fail closed.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8", newline="\n",
    )


def patch_manifest(package: Path, changed: list[str], generated: dict[str, dict[str, Any]], target: dict[str, dict[str, Any]], runner: dict[str, Any], post_sim: dict[str, dict[str, Any]]) -> None:
    old_analysis, old_sha = prior.ANALYSIS, prior.ANALYSIS_SHA256
    try:
        prior.ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p34b_return_analysis/report.json"
        prior.ANALYSIS_SHA256 = "3c40b9f32dff646387c72ad4bb92a594ecf4c76b6ef3066b9fe991be7f7283aa"
        _old_patch_manifest(package, changed, generated, target, runner, post_sim)
    finally:
        prior.ANALYSIS, prior.ANALYSIS_SHA256 = old_analysis, old_sha
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    if base.sha256(ANALYSIS) != ANALYSIS_SHA256 or analysis.get("valid") is not True or analysis.get("status") != "P35C_PARTIAL_RETURN_VALID_SECOND_UNDRIVEN_PAYLOAD_FAIL_CLOSED_SUCCESSOR_REQUIRED":
        raise BuildError("formal p35c analysis differs")
    value.update({
        "schema": "conv-native-four-lane-0ccae916-p36-semfp-package-v1",
        "package_identity": PACKAGE_ID,
        "install_name": PACKAGE_ID,
        "workload_install_name": PACKAGE_ID,
        "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
        "return_name": f"{PACKAGE_ID}_<execution_id>_return.zip",
    })
    value.pop("source_p34b_formal_return_analysis", None)
    value["source_p35c_formal_return_analysis"] = {
        "path": ANALYSIS.relative_to(ROOT).as_posix(), "sha256": ANALYSIS_SHA256,
        "return_sha256": analysis["return_identity"]["sha256"], "source_zip_sha256": analysis["source_identity"]["sha256"],
        "classification": analysis["classification"], "last_progress_guard": analysis["failure_localization"]["LAST_PROVEN_GOOD"],
        "first_divergence": analysis["failure_localization"]["FIRST_DIVERGENCE"],
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p35c proved a second undriven ARM payload leaf and failed closed; p36 removes it and pins exact-instance/known-width semantics",
        "authorized_config_change": None, "numeric_w3_golden_repeated": False,
    }
    value["rule_change_epoch"] = {
        "epoch_id": EPOCH, "family": "conv_native_four_lane", "package_id": PACKAGE_ID,
        "first_fresh_after_change": True, "notification_acknowledged": True,
        "rule_ids": RULE_IDS, "upload_hold_until": "INDEPENDENT_EXTRA_AUDIT_PASS",
    }
    generation = json.loads((SOURCE_BOUND / "source_bound_generation_report.json").read_text(encoding="utf-8"))
    value["diagnostic_semantics"] = {
        "plan_schema": "server-source-bound-probe-plan-v2",
        "fingerprint_sha256": generation["diagnostic_semantics_sha256"],
        "disposition": "FIRST_USE_AUDITED",
        "exact_instance_identity": target["diagnostics/exact_instance_identity.json"],
    }
    value["release_gate_applicability"].update({
        "materialized_config": "receipt_reuse_byte_equal_p35c",
        "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
        "first_fresh_extra_audit": "blocking_applicable_new_exact_instance_payload_semfp_epoch",
    })
    value["release_gate_matrix"]["materialized_config"].update({"applicability": "receipt_reuse", "blocking": False, "pass": True, "scope": "87 p35c installed payload members byte-equal and SCA identity-normalized equal"})
    value["release_gate_matrix"]["diagnostic_semantics"] = {"applicability": "blocking_applicable", "blocking": True, "pass": None, "fingerprint_sha256": generation["diagnostic_semantics_sha256"], "disposition": "FIRST_USE_AUDITED"}
    value["release_gate_matrix"]["first_fresh_extra_audit"] = {"applicability": "blocking_applicable", "blocking": True, "pass": None, "epoch_id": EPOCH, "upload_hold": True}
    base.refresh_manifest_files(package, value)
    write_json(path, value)


def build_directory(destination: Path):
    configure()
    prior.make_live_fixture = make_live_fixture
    prior.install_correlator = install_correlator
    prior.patch_post_sim = patch_post_sim
    prior.patch_docs = patch_docs
    prior.patch_manifest = patch_manifest
    return prior.build_directory(destination)


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
        raise BuildError("refusing to overwrite p36 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p35c source differs")
    package, receipts = build_directory(output)
    frozen = prior.p34.prior.frozen_checks(package)
    if not frozen["frozen_install_payload_byte_equal"] or not all(frozen["sca_identity_normalized_equal"].values()) or frozen["frozen_install_payload_member_count"] != 87:
        raise BuildError("frozen p35c payload differs")
    with tempfile.TemporaryDirectory(prefix=".p36_repeat_", dir=ROOT) as temporary:
        repeated, _ = build_directory(Path(temporary))
        deterministic = tree_receipt(repeated) == tree_receipt(package)
    if not deterministic:
        raise BuildError("p36 deterministic staging trees differ")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p36-semfp-build-v1",
        "status": "PACKAGE_BUILT_UPLOAD_HELD_PENDING_FINAL_AND_EXTRA_AUDIT",
        "package_identity": PACKAGE_ID,
        "source_p35c_zip_sha256": SOURCE_SHA256,
        "source_p35c_analysis_sha256": ANALYSIS_SHA256,
        "rule_change_epoch_id": EPOCH,
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
