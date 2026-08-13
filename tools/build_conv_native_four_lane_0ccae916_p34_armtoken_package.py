#!/usr/bin/env python3
"""Build p34 from consumed p33b with live ARM token-state correlation."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p33_wrowner_package as prior


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p33b_wrowner"
PACKAGE_ID = "r5_n4_0cc_p34_armtoken"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_931_155
SOURCE_SHA256 = "62b225be794774e1cd8c9a4f8a8d26e2cf5ecb1795ed44fe3d1ed748d81077df"
ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p33b_return_analysis/report.json"
ANALYSIS_SHA256 = ""
SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p34_armtoken_source_bound"
GENERATED = SOURCE_BOUND / "generated"
PRIOR_FIRST_FRESH = ROOT / "outputs/conv_native_four_lane_0ccae916_p31_postclear/first_fresh_extra_audit/validation.json"
PRIOR_FIRST_FRESH_SHA256 = "48c58b614af0ba1fe311d454e5229d4f000a5b944d711e52a8c43ecc85ab0ec1"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p34_armtoken/build"
base = prior.base


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    prior.write_json(path, value)


def receipt(path: Path, package: Path) -> dict[str, Any]:
    return {"path": path.relative_to(package).as_posix(), "bytes": path.stat().st_size, "sha256": base.sha256(path)}


def configure() -> None:
    prior.SOURCE_ID = SOURCE_ID
    prior.PACKAGE_ID = PACKAGE_ID
    prior.SOURCE_ZIP = SOURCE_ZIP
    prior.SOURCE_BYTES = SOURCE_BYTES
    prior.SOURCE_SHA256 = SOURCE_SHA256
    prior.P32_ANALYSIS = ANALYSIS
    prior.P32_ANALYSIS_SHA256 = base.sha256(ANALYSIS)
    prior.SOURCE_BOUND = SOURCE_BOUND
    prior.GENERATED = GENERATED
    prior.DEFAULT_OUTPUT = DEFAULT_OUTPUT


def install_correlator(package: Path) -> dict[str, dict[str, Any]]:
    for path in (
        package / "diagnostics/target_epoch_write_owner_contract.json",
        package / "package_tools/target_epoch_write_owner_parser.py",
    ):
        if path.exists():
            path.unlink()
    mapping = {
        SOURCE_BOUND / "arm_token_contract.json": package / "diagnostics/arm_token_contract.json",
        ROOT / "tools/conv_native_four_lane_p34_arm_token_parser.py": package / "package_tools/arm_token_parser.py",
    }
    result = {}
    for source, target in mapping.items():
        if not source.is_file():
            raise BuildError(f"p34 correlator source is absent: {source}")
        shutil.copyfile(source, target)
        result[target.relative_to(package).as_posix()] = receipt(target, package)
    return result


def patch_post_sim(package: Path) -> dict[str, dict[str, Any]]:
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if request.get("package_id") != PACKAGE_ID:
        raise BuildError("post-sim request identity differs")
    request["claim_boundary"] = (
        "p34 c0 exact-target live Buffer clear/write plus ARM token/counter/reset diagnostic only. "
        "Core publication remains independent of plugin success; natural terminal, formal 320D and E3/E4/E5 are unclaimed."
    )
    request["core_entries"] = [
        row for row in request["core_entries"]
        if row.get("archive") not in {"evidence/target_epoch_write_owner_decision.json", "evidence/arm_token_decision.json"}
    ]
    request["core_entries"].append({"archive": "evidence/arm_token_decision.json", "required": True, "source": "evidence/arm_token_decision.json", "source_root": "attempt"})
    request["plugins"] = [
        row for row in request["plugins"]
        if row.get("plugin_id") not in {"target_epoch_write_owner_parser", "arm_token_parser"}
    ]
    for row in request["plugins"]:
        if row.get("plugin_id") == "source_bound_parser":
            row["required_for_adjudication"] = False
    request["plugins"].insert(1, {
        "argv": ["python3", "{package_root}/package_tools/arm_token_parser.py", "--log", "{attempt_root}/c0/source_bound_causal.log", "--contract", "{package_root}/diagnostics/arm_token_contract.json", "--output", "{attempt_root}/evidence/arm_token_decision.json"],
        "cwd_root": "attempt", "plugin_id": "arm_token_parser", "required_for_adjudication": True, "timeout_seconds": 120,
    })
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["request_sha256"] = base.sha256(request_path)
    contract["claim_boundary"] = request["claim_boundary"]
    write_json(contract_path, contract)
    helper = package / "package_tools/server_post_sim_return.py"
    expected = "87c78dd8408d75430074f05e07e99ba3d1b7db3bc5907860b9d15969b172b0b8"
    if base.sha256(helper) != expected or contract.get("helper_sha256") != expected:
        raise BuildError("shared post-sim helper identity differs")
    return {"helper": receipt(helper, package), "request": receipt(request_path, package), "contract": receipt(contract_path, package)}


def patch_docs(package: Path) -> None:
    layout_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout["claim_boundary"] = "p34 preserves p33b payload/config and changes identity plus generated live ARM token observation."
    paths = base.projected_paths(package, layout)
    longest = max(paths, key=lambda item: (len(item), item))
    layout["path_budget"]["max_projected_absolute_path_chars"] = layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    write_json(layout_path, layout)
    source_path = package / "diagnostics/source_bound_final_zip_contract.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["claim_boundary"] = "p34 generated live exact-target ARM token/counter/reset observation; no final-block ring dependency."
    source["family_target_correlator"] = {"contract": "diagnostics/arm_token_contract.json", "parser": "package_tools/arm_token_parser.py", "decision": "evidence/arm_token_decision.json"}
    write_json(source_path, source)
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    pointer_value = json.loads(pointer.read_text(encoding="utf-8"))
    pointer_value.update({"schema": "conv-native-four-lane-p34-armtoken-pointer-v1", "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN"})
    write_json(pointer, pointer_value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p34 ARM token-state diagnostic\n\n"
        "Fresh successor of tested p33b. All 87 installed payload members remain frozen. Live exact-target events "
        "correlate the Buffer5 clear/write interval with ARM token counters, reset/wrap, last and same state.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8", newline="\n",
    )


def patch_manifest(package: Path, changed: list[str], generated: dict[str, dict[str, Any]], target: dict[str, dict[str, Any]], runner: dict[str, Any], post_sim: dict[str, dict[str, Any]]) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    analysis_sha = base.sha256(ANALYSIS)
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    if analysis.get("valid") is not True or analysis.get("status") != "P33B_PARTIAL_INTERRUPTED_TARGET_ARM_REWRITE_PROVEN_SUCCESSOR_REQUIRED":
        raise BuildError("formal p33b analysis is not accepted")
    prior_pass = json.loads(PRIOR_FIRST_FRESH.read_text(encoding="utf-8"))
    if base.sha256(PRIOR_FIRST_FRESH) != PRIOR_FIRST_FRESH_SHA256 or prior_pass.get("pass") is not True or prior_pass.get("upload_authorized") is not True:
        raise BuildError("p31 first-fresh PASS differs")
    value.update({
        "schema": "conv-native-four-lane-0ccae916-p34-armtoken-package-v1", "package_identity": PACKAGE_ID,
        "install_name": PACKAGE_ID, "workload_install_name": PACKAGE_ID,
        "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0", "return_name": f"{PACKAGE_ID}_<execution_id>_return.zip",
        "status": "PACKAGE_READY_NOT_RUN", "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False, "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
    })
    value.pop("source_p32b_formal_return_analysis", None)
    value["source_p33b_formal_return_analysis"] = {
        "path": ANALYSIS.relative_to(ROOT).as_posix(), "sha256": analysis_sha,
        "return_sha256": analysis["return_identity"]["sha256"], "source_zip_sha256": analysis["source_identity"]["sha256"],
        "classification": analysis["classification"], "last_progress_guard": analysis["failure_localization"]["LAST_PROVEN_GOOD"],
        "first_divergence": analysis["failure_localization"]["FIRST_DIVERGENCE"],
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p33b proves ARM-only post-clear rewrite; p34 distinguishes advancing tokens, stable replay and reset/wrap with live exact-target records",
        "authorized_config_change": None, "numeric_w3_golden_repeated": False,
    }
    value["rule_change_epoch"] = {"epoch_id": "20260810-first-fresh-extra-audit-v1", "family": "conv_native_four_lane", "package_id": PACKAGE_ID, "first_fresh_after_change": False, "prior_pass_path": PRIOR_FIRST_FRESH.relative_to(ROOT).as_posix(), "prior_pass_sha256": PRIOR_FIRST_FRESH_SHA256, "upload_hold_until": "CURRENT_PACKAGE_FINAL_AUDIT_PASS"}
    value["source_bound_observer_binding"].update({"claim_boundary": "c0 exact-target live ARM token/counter/reset only", "generated_members": generated, "runner": runner, "functional_rtl_changed": False, "target_epoch_correlator_members": target})
    value["post_sim_return_core"].update({"members": post_sim, "runner": {"path": "PREPARE_AND_RUN.sh", "bytes": (package / "PREPARE_AND_RUN.sh").stat().st_size, "sha256": base.sha256(package / "PREPARE_AND_RUN.sh"), "shared_post_sim_invocations": (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8").count('python3 "$post_sim_helper" finalize --request "$post_sim_request"')}, "claim_boundary": json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))["claim_boundary"]})
    value["identity_rebound_text_members"] = changed
    value["release_gate_applicability"].update({"materialized_config": "receipt_reuse_byte_equal_p33b", "numeric_w3_golden": "record_only_byte_equal_receipt_reuse", "first_fresh_extra_audit": "receipt_reuse_same_epoch_p31_pass"})
    value["release_gate_matrix"]["materialized_config"].update({"applicability": "receipt_reuse", "blocking": False, "pass": True, "scope": "87 p33b installed payload members byte-equal and SCA identity-normalized equal"})
    value["release_gate_matrix"]["source_bound_observer_generation"]["pass"] = True
    value["release_gate_matrix"]["source_bound_final_zip"]["pass"] = None
    value["release_gate_matrix"]["post_sim_return_core"]["pass"] = None
    value["release_gate_matrix"]["first_fresh_extra_audit"] = {"applicability": "receipt_reuse", "blocking": False, "pass": True, "epoch_id": "20260810-first-fresh-extra-audit-v1", "prior_package_id": "r5_n4_0cc_p31_postclear", "prior_pass_sha256": PRIOR_FIRST_FRESH_SHA256}
    layout = json.loads((package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(encoding="utf-8"))
    projected = base.projected_paths(package, layout)
    longest = max(projected, key=lambda item: (len(item), item))
    inner = [row.relative_to(package).as_posix() for row in package.rglob("*") if row.is_file() and row != path] + ["package_manifest.json"]
    value["path_length_budget"].update({
        "longest_projected_relative_path": longest, "longest_projected_relative_path_chars": len(longest),
        "max_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest),
        "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{relative}") for relative in inner),
        "max_inner_suffix_chars": max(map(len, inner)), "max_inner_depth": max(len(PurePosixPath(relative).parts) for relative in inner),
        "max_inner_component_chars": max(len(part) for relative in inner for part in PurePosixPath(relative).parts),
        "outer_identity_repeated_inside": False,
    })
    base.refresh_manifest_files(package, value)
    write_json(path, value)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure()
    prior.configure_predecessor()
    package = base.safe_extract(SOURCE_ZIP, destination)
    changed = prior.predecessor.predecessor.p28.replace_identity(package)
    generated = prior.predecessor.predecessor.p28.install_generated(package)
    target = install_correlator(package)
    runner = prior.predecessor.predecessor.p28.patch_runner(package)
    post_sim = patch_post_sim(package)
    patch_docs(package)
    patch_manifest(package, changed, generated, target, runner, post_sim)
    return package, {"identity_members": changed, "generated": generated, "target_correlator": target, "runner": runner, "post_sim": post_sim}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = (output / PACKAGE_ID, output / f"{PACKAGE_ID}.zip", output / f"{PACKAGE_ID}.zip.sha256", output / f"{PACKAGE_ID}.build.json")
    if any(target.exists() for target in targets):
        raise BuildError("refusing to overwrite p34 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p33b source differs")
    package, receipts = build_directory(output)
    frozen = prior.frozen_checks(package)
    if not frozen["frozen_install_payload_byte_equal"] or not all(frozen["sca_identity_normalized_equal"].values()) or frozen["frozen_install_payload_member_count"] != 87:
        raise BuildError("frozen p33b payload differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    with tempfile.TemporaryDirectory(prefix=".p34_repeat_", dir=ROOT) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeat_zip = Path(temporary) / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p34 deterministic double build differs")
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p34-armtoken-build-v1", "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID, "source_p33b_zip_sha256": SOURCE_SHA256,
        "source_p33b_analysis_sha256": base.sha256(ANALYSIS),
        "rule_change_epoch_id": "20260810-first-fresh-extra-audit-v1", "first_fresh_after_change": False,
        "prior_first_fresh_pass_sha256": PRIOR_FIRST_FRESH_SHA256,
        "zip": str(zip_path), "zip_bytes": zip_path.stat().st_size, "zip_sha256": zip_sha,
        "final_zip_count": 1, "deterministic_double_build": deterministic, "receipts": receipts,
        "frozen": frozen, "functional_rtl_modified": False, "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
