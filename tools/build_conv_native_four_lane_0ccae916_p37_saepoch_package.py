#!/usr/bin/env python3
"""Build the single p37 accepted-SA-data successor from frozen p36b bytes."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p36_semfp_package as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p37_saepoch"
SOURCE_ID = "r5_n4_0cc_p36b_semfp"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_942_345
SOURCE_SHA256 = "0111176e62fca03a023bbd83098067191113bdc4a91a7bf5c7e0e37c3d288e0e"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p36b_return_analysis/report.json"
ANALYSIS_SHA256 = "dfd777acd1e426ac3f69952ae03f028e5182d229ef3f67fed047b642d1d050ce"
SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p37_saepoch_source_bound_v4"
GENERATED = SOURCE_BOUND / "generated"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p37_saepoch/build"
EPOCH = "20260811-exact-instance-payload-semantic-fingerprint-v2"
PRIOR_FIRST_FRESH = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p36b_semfp/r5_n4_0cc_p36b_semfp.first_fresh_validation.json"
PRIOR_FIRST_FRESH_SHA256 = "7e7cd5ea7e0ce3fbf0dcd6073dff27dbe0bd0b5abd619ccd67adfbacf02cfc3c"
base = prior.base
_p36_make_live_fixture = prior.make_live_fixture
_p36_install_correlator = prior.install_correlator
_p36_patch_post_sim = prior.patch_post_sim
_p36_patch_docs = prior.patch_docs
_p36_patch_manifest = prior.patch_manifest


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def receipt(path: Path, package: Path) -> dict[str, Any]:
    return {"path": path.relative_to(package).as_posix(), "bytes": path.stat().st_size, "sha256": base.sha256(path)}


def configure() -> None:
    prior.PACKAGE_ID = PACKAGE_ID
    prior.SOURCE_ID = SOURCE_ID
    prior.SOURCE_ZIP = SOURCE_ZIP
    prior.SOURCE_BYTES = SOURCE_BYTES
    prior.SOURCE_SHA256 = SOURCE_SHA256
    prior.ANALYSIS = ANALYSIS
    prior.ANALYSIS_SHA256 = ANALYSIS_SHA256
    prior.SOURCE_BOUND = SOURCE_BOUND
    prior.GENERATED = GENERATED
    prior.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    prior.EPOCH = EPOCH
    prior.configure()


def make_live_fixture(arm_contract: dict[str, Any]) -> str:
    lines = _p36_make_live_fixture(arm_contract).rstrip("\n").splitlines()
    sa = json.loads((SOURCE_BOUND / "sa_epoch_contract.json").read_text(encoding="utf-8"))
    for lane, (boundary, instance) in enumerate(zip(sa["boundary_ids"], sa["expected_instances"])):
        lines.append(f"CODEX_PROBE_V1 kind=ENABLED boundary={boundary} instance={instance}")
        for beat, time in enumerate((110, 120)):
            data = (lane + 1) | (beat << 31)
            payload = (0x5F << 33) | (data << 1) | 1
            lines.append(
                f"CODEX_PROBE_V1 kind=EVENT boundary={boundary} instance={instance} time={time} "
                f"mask=1 payload={payload:x} payload_known=1 payload_width=40 seq={beat}"
            )
    return "\n".join(lines) + "\n"


def install_correlator(package: Path) -> dict[str, dict[str, Any]]:
    result = _p36_install_correlator(package)
    mapping = {
        SOURCE_BOUND / "sa_epoch_contract.json": package / "diagnostics/sa_epoch_contract.json",
        SOURCE_BOUND / "generated_sa_epoch_parser.py": package / "package_tools/sa_epoch_parser.py",
    }
    for source, target in mapping.items():
        shutil.copyfile(source, target)
        result[target.relative_to(package).as_posix()] = receipt(target, package)
    return result


def patch_post_sim(package: Path) -> dict[str, dict[str, Any]]:
    result = _p36_patch_post_sim(package)
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    request["claim_boundary"] = (
        "p37 c0 exact-instance binary-known accepted SA lane data versus p36-proven stable ARM tag diagnostic only. "
        "Equal data remains ambiguous; natural terminal, formal 320D and E3/E4/E5 are unclaimed."
    )
    request["core_entries"] = [row for row in request["core_entries"] if row.get("archive") != "evidence/sa_epoch_decision.json"]
    request["core_entries"].append({
        "archive": "evidence/sa_epoch_decision.json", "required": True,
        "source": "evidence/sa_epoch_decision.json", "source_root": "attempt",
    })
    request["plugins"] = [row for row in request["plugins"] if row.get("plugin_id") != "sa_epoch_parser"]
    request["plugins"].insert(2, {
        "argv": [
            "python3", "{package_root}/package_tools/sa_epoch_parser.py",
            "--log", "{attempt_root}/c0/source_bound_causal.log",
            "--contract", "{package_root}/diagnostics/sa_epoch_contract.json",
            "--output", "{attempt_root}/evidence/sa_epoch_decision.json",
        ],
        "cwd_root": "attempt", "plugin_id": "sa_epoch_parser",
        "required_for_adjudication": True, "timeout_seconds": 120,
    })
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["package_id"] = PACKAGE_ID
    contract["request_sha256"] = base.sha256(request_path)
    contract["claim_boundary"] = request["claim_boundary"]
    live = contract["partial_exit_live_causal_record"]
    live["plugin_dispositions"] = [row for row in live["plugin_dispositions"] if row.get("plugin_id") != "sa_epoch_parser"]
    live["plugin_dispositions"].append({
        "plugin_id": "sa_epoch_parser", "disposition": "LIVE_CAUSAL_FIXTURE",
        "input_root": "attempt", "input_path": "c0/source_bound_causal.log",
        "fixture_member": "diagnostics/live_fixtures/arm_known_event.log",
        "input_kind": "QUALIFIED_LIVE_RECORD", "output_root": "attempt",
        "output_path": "evidence/sa_epoch_decision.json", "expected_exit_code": 0,
        "timeout_seconds": 30,
    })
    write_json(contract_path, contract)
    result["request"] = receipt(request_path, package)
    result["contract"] = receipt(contract_path, package)
    return result


def patch_docs(package: Path) -> None:
    _p36_patch_docs(package)
    layout_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout["claim_boundary"] = "p37 preserves all 87 p36b workload/config members and changes only identity plus generated SA accepted-data diagnostics."
    paths = base.projected_paths(package, layout)
    longest = max(paths, key=lambda item: (len(item), item))
    layout["path_budget"]["max_projected_absolute_path_chars"] = layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    write_json(layout_path, layout)
    source_path = package / "diagnostics/source_bound_final_zip_contract.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["claim_boundary"] = "p37 exact generated Buffer/ARM plus eight exact generated SA lane payloads; wrong-instance/X/Z/width/semantic drift fail closed."
    source["family_target_correlators"] = [
        {"contract": "diagnostics/arm_known_contract.json", "parser": "package_tools/arm_known_parser.py", "decision": "evidence/arm_known_decision.json"},
        {"contract": "diagnostics/sa_epoch_contract.json", "parser": "package_tools/sa_epoch_parser.py", "decision": "evidence/sa_epoch_decision.json"},
    ]
    source.pop("family_target_correlator", None)
    write_json(source_path, source)
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value.update({"schema": "conv-native-four-lane-p37-saepoch-pointer-v1", "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN"})
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p37 accepted-SA-data diagnostic\n\n"
        "Fresh successor of tested p36b. All 87 workload/config members are frozen. The generated observer captures "
        "eight exact public SA_Outport lane acceptances and the required parser compares complete 256-bit beats sharing "
        "the p36-proven ARM tag. Equal beats remain ambiguous.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8", newline="\n",
    )


def patch_manifest(package: Path, changed: list[str], generated: dict[str, dict[str, Any]], target: dict[str, dict[str, Any]], runner: dict[str, Any], post_sim: dict[str, dict[str, Any]]) -> None:
    saved_analysis, saved_sha = prior.ANALYSIS, prior.ANALYSIS_SHA256
    try:
        prior.ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p35c_return_analysis/report_v2.json"
        prior.ANALYSIS_SHA256 = "467a302034be259a629af67a9547a463f51a83e0046aaea3342803ecec516166"
        _p36_patch_manifest(package, changed, generated, target, runner, post_sim)
    finally:
        prior.ANALYSIS, prior.ANALYSIS_SHA256 = saved_analysis, saved_sha
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    if base.sha256(ANALYSIS) != ANALYSIS_SHA256 or analysis.get("valid") is not True or analysis.get("status") != "P36B_PARTIAL_RETURN_VALID_STABLE_ARM_TAG_REACCEPT_PROVEN_SUCCESSOR_REQUIRED":
        raise BuildError("formal p36b analysis differs")
    value.update({
        "schema": "conv-native-four-lane-0ccae916-p37-saepoch-package-v1",
        "package_identity": PACKAGE_ID,
        "install_name": PACKAGE_ID,
        "workload_install_name": PACKAGE_ID,
        "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
        "return_name": f"{PACKAGE_ID}_<execution_id>_return.zip",
        "status": "PACKAGE_READY_NOT_RUN",
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
    })
    for key in list(value):
        if key.startswith("source_p") and key.endswith("_formal_return_analysis"):
            value.pop(key, None)
    value["source_p36b_formal_return_analysis"] = {
        "path": ANALYSIS.relative_to(ROOT).as_posix(), "sha256": ANALYSIS_SHA256,
        "return_sha256": analysis["return_identity"]["sha256"],
        "source_zip_sha256": analysis["source_identity"]["sha256"],
        "classification": analysis["classification"],
        "last_progress_guard": analysis["failure_localization"]["LAST_PROVEN_GOOD"],
        "first_divergence": analysis["failure_localization"]["FIRST_DIVERGENCE"],
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p36b proved two binary-known identical ARM tag/control accepts but did not identify the corresponding complete SA data beats",
        "authorized_config_change": None, "numeric_w3_golden_repeated": False,
    }
    value["rule_change_epoch"] = {
        "epoch_id": EPOCH, "family": "conv_native_four_lane", "package_id": PACKAGE_ID,
        "first_fresh_after_change": False, "notification_acknowledged": True,
        "prior_first_fresh_pass": {
            "package_id": SOURCE_ID,
            "path": PRIOR_FIRST_FRESH.relative_to(ROOT).as_posix(),
            "sha256": PRIOR_FIRST_FRESH_SHA256,
        },
        "rule_ids": prior.RULE_IDS,
        "upload_hold_until": "ALL_EXACT_FINAL_ZIP_GATES_PASS",
    }
    generation = json.loads((SOURCE_BOUND / "source_bound_generation_report.json").read_text(encoding="utf-8"))
    value["diagnostic_semantics"] = {
        "plan_schema": "server-source-bound-probe-plan-v2",
        "fingerprint_sha256": generation["diagnostic_semantics_sha256"],
        "disposition": "FIRST_USE_AUDITED_BY_TYPED_V2_FINAL_ZIP",
        "exact_instance_identity": target["diagnostics/exact_instance_identity.json"],
        "p36b_first_fresh_receipt_reused": True,
    }
    value["release_gate_applicability"].update({
        "materialized_config": "receipt_reuse_byte_equal_p36b",
        "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
        "first_fresh_extra_audit": "receipt_reuse_same_epoch_p36b_pass",
    })
    value["release_gate_matrix"]["materialized_config"].update({
        "applicability": "receipt_reuse", "blocking": False, "pass": True,
        "scope": "87 p36b workload/config members byte-equal and SCA identity-normalized equal",
    })
    value["release_gate_matrix"]["diagnostic_semantics"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": None,
        "fingerprint_sha256": generation["diagnostic_semantics_sha256"],
        "disposition": "FIRST_USE_AUDITED_BY_TYPED_V2_FINAL_ZIP",
    }
    value["release_gate_matrix"]["first_fresh_extra_audit"] = {
        "applicability": "receipt_reuse", "blocking": False, "pass": True,
        "epoch_id": EPOCH, "prior_pass_sha256": PRIOR_FIRST_FRESH_SHA256,
    }
    value["source_bound_observer_binding"].update({
        "claim_boundary": "exact p36b ARM anchor plus eight exact accepted SA lane payloads",
        "generated_members": generated, "runner": runner,
        "functional_rtl_changed": False, "target_epoch_correlator_members": target,
    })
    value["post_sim_return_core"].update({
        "members": post_sim,
        "runner": {
            "path": "PREPARE_AND_RUN.sh", "bytes": (package / "PREPARE_AND_RUN.sh").stat().st_size,
            "sha256": base.sha256(package / "PREPARE_AND_RUN.sh"),
            "shared_post_sim_invocations": (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8").count('python3 "$post_sim_helper" finalize --request "$post_sim_request"'),
        },
        "claim_boundary": json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))["claim_boundary"],
    })
    layout = json.loads((package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(encoding="utf-8"))
    projected = base.projected_paths(package, layout)
    longest = max(projected, key=lambda item: (len(item), item))
    inner = [row.relative_to(package).as_posix() for row in package.rglob("*") if row.is_file() and row != path] + ["package_manifest.json"]
    value["path_length_budget"].update({
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest),
        "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{relative}") for relative in inner),
        "max_inner_suffix_chars": max(map(len, inner)),
        "max_inner_depth": max(len(PurePosixPath(relative).parts) for relative in inner),
        "max_inner_component_chars": max(len(part) for relative in inner for part in PurePosixPath(relative).parts),
        "outer_identity_repeated_inside": False,
    })
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
        raise BuildError("refusing to overwrite p37 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p36b source differs")
    if base.sha256(PRIOR_FIRST_FRESH) != PRIOR_FIRST_FRESH_SHA256:
        raise BuildError("p36b first-fresh PASS receipt differs")
    package, receipts = build_directory(output)
    frozen = prior.prior.p34.prior.frozen_checks(package)
    if not frozen["frozen_install_payload_byte_equal"] or not all(frozen["sca_identity_normalized_equal"].values()) or frozen["frozen_install_payload_member_count"] != 87:
        raise BuildError("frozen p36b payload differs")
    with tempfile.TemporaryDirectory(prefix=".p37_repeat_", dir=ROOT) as temporary:
        repeated, _ = build_directory(Path(temporary))
        deterministic = tree_receipt(repeated) == tree_receipt(package)
    if not deterministic:
        raise BuildError("p37 deterministic staging trees differ")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p37-saepoch-build-v1",
        "status": "PACKAGE_BUILT_UPLOAD_HELD_PENDING_EXACT_FINAL_ZIP_GATES",
        "package_identity": PACKAGE_ID,
        "source_p36b_zip_sha256": SOURCE_SHA256,
        "source_p36b_analysis_sha256": ANALYSIS_SHA256,
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": False,
        "prior_first_fresh_pass_sha256": PRIOR_FIRST_FRESH_SHA256,
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
