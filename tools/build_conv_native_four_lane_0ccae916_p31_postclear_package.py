#!/usr/bin/env python3
"""Build p31 from the formally consumed p30 diagnostic package."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p30_bankvalid_package as predecessor


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p30_bankvalid"
PACKAGE_ID = "r5_n4_0cc_p31_postclear"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_943_878
SOURCE_SHA256 = "8229b380c9b33f99c8bd27d3eb21ce2ce17aae1b5eb0278926f27307887cbf34"
P30_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p30_return_analysis/report.json"
P30_ANALYSIS_SHA256 = "88a629d28ab67cdb223e0e579a59c46928751ca387faab1850df8c5971f6fb39"
SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p31_postclear_source_bound_v2"
GENERATED = SOURCE_BOUND / "generated"
EPOCH_ACK = SOURCE_BOUND / "first_fresh_epoch_ack.json"
EPOCH_ACK_SHA256 = "7bab0622ccf1522c66704a1387fe5a490d7cd41bae5f53b5a27eda7baa0d018e"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p31_postclear/build"
base = predecessor.base


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    predecessor.write_json(path, value)


def receipt(path: Path, package: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(package).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": base.sha256(path),
    }


def configure_predecessor() -> None:
    predecessor.SOURCE_ID = SOURCE_ID
    predecessor.PACKAGE_ID = PACKAGE_ID
    predecessor.SOURCE_ZIP = SOURCE_ZIP
    predecessor.SOURCE_BYTES = SOURCE_BYTES
    predecessor.SOURCE_SHA256 = SOURCE_SHA256
    predecessor.P29_ANALYSIS = P30_ANALYSIS
    predecessor.P29_ANALYSIS_SHA256 = P30_ANALYSIS_SHA256
    predecessor.SOURCE_BOUND = SOURCE_BOUND
    predecessor.GENERATED = GENERATED
    predecessor.DEFAULT_OUTPUT = DEFAULT_OUTPUT


def patch_post_sim(package: Path) -> dict[str, dict[str, Any]]:
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if request.get("package_id") != PACKAGE_ID:
        raise BuildError("post-sim request identity rebinding differs")
    request["claim_boundary"] = (
        "p31 c0 immediate final-row2 same-bit and blocked-bank-state diagnostic only. Core publication is "
        "independent of parser/plugin success; natural terminal, formal 320D and E3/E4/E5 remain unclaimed."
    )
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("package_id") != PACKAGE_ID:
        raise BuildError("post-sim contract identity rebinding differs")
    contract["request_sha256"] = base.sha256(request_path)
    contract["claim_boundary"] = request["claim_boundary"]
    write_json(contract_path, contract)
    helper = package / "package_tools/server_post_sim_return.py"
    expected = "87c78dd8408d75430074f05e07e99ba3d1b7db3bc5907860b9d15969b172b0b8"
    if base.sha256(helper) != expected or contract.get("helper_sha256") != expected:
        raise BuildError("shared post-sim helper identity differs")
    return {
        "helper": receipt(helper, package),
        "request": receipt(request_path, package),
        "contract": receipt(contract_path, package),
    }


def patch_contract_docs(package: Path) -> None:
    layout_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout["claim_boundary"] = (
        "p31 preserves p30 workload/config and changes only fresh identity plus generated immediate "
        "final-row2 candidate triggers and identity-bound return contracts."
    )
    paths = base.projected_paths(package, layout)
    longest = max(paths, key=lambda item: (len(item), item))
    layout["path_budget"]["max_projected_absolute_path_chars"] = (
        layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    )
    write_json(layout_path, layout)
    source_contract_path = package / "diagnostics/source_bound_final_zip_contract.json"
    source_contract = json.loads(source_contract_path.read_text(encoding="utf-8"))
    source_contract["claim_boundary"] = (
        "p31 source-bound final same-bit row2 marker and candidate-decomposed blocked bank state only; "
        "production compile/simulation, natural terminal, formal D and E3-E5 remain dynamic."
    )
    write_json(source_contract_path, source_contract)
    pointer_path = package / "TEST_PACKAGE_MANIFEST.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer.update(
        {
            "schema": "conv-native-four-lane-p31-postclear-pointer-v1",
            "package_identity": PACKAGE_ID,
            "status": "PACKAGE_READY_NOT_RUN",
        }
    )
    write_json(pointer_path, pointer)
    (package / "README.md").write_text(
        "# Native four-lane Conv p31 final post-clear diagnostic\n\n"
        "Fresh successor of tested p30. All 87 installed payload members are frozen. Generated, "
        "source-bound immediate triggers distinguish the same-bit final row2 block with bank-ready "
        "00/0f/f0/ff/other without depending on simulator final blocks.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8",
        newline="\n",
    )


def patch_manifest(
    package: Path,
    changed: list[str],
    generated: dict[str, dict[str, Any]],
    runner: dict[str, Any],
    post_sim: dict[str, dict[str, Any]],
) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if base.sha256(P30_ANALYSIS) != P30_ANALYSIS_SHA256:
        raise BuildError("formal p30 analysis identity differs")
    analysis = json.loads(P30_ANALYSIS.read_text(encoding="utf-8"))
    if analysis.get("valid") is not True or analysis.get("status") != "P30_PARTIAL_INTERRUPTED_FINAL_BANK_STATE_EVIDENCE_ESCAPE_SUCCESSOR_REQUIRED":
        raise BuildError("formal p30 analysis is not accepted")
    if base.sha256(EPOCH_ACK) != EPOCH_ACK_SHA256:
        raise BuildError("first-fresh epoch acknowledgment differs")
    value.update(
        {
            "schema": "conv-native-four-lane-0ccae916-p31-postclear-package-v1",
            "package_identity": PACKAGE_ID,
            "install_name": PACKAGE_ID,
            "workload_install_name": PACKAGE_ID,
            "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
            "return_name": f"{PACKAGE_ID}_<execution_id>_return.zip",
            "status": "PACKAGE_READY_NOT_RUN",
        }
    )
    value["source_p30_formal_return_analysis"] = {
        "path": P30_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": P30_ANALYSIS_SHA256,
        "return_sha256": analysis["return_identity"]["sha256"],
        "source_zip_sha256": analysis["source_identity"]["sha256"],
        "classification": analysis["classification"],
        "last_progress_guard": analysis["failure_localization"]["LAST_PROVEN_GOOD"],
        "first_divergence": analysis["failure_localization"]["FIRST_DIVERGENCE"],
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p30 loses exact final bank state on INT; p31 publishes candidate-specific triggers immediately",
        "authorized_config_change": None,
        "numeric_w3_golden_repeated": False,
    }
    value["rule_change_epoch"] = {
        "epoch_id": "20260810-first-fresh-extra-audit-v1",
        "family": "conv_native_four_lane",
        "package_id": PACKAGE_ID,
        "first_fresh_after_change": True,
        "notification_acknowledged": True,
        "ack_path": EPOCH_ACK.relative_to(ROOT).as_posix(),
        "ack_sha256": EPOCH_ACK_SHA256,
        "upload_hold_until": "EXTRA_AUDIT_PASS",
    }
    value["source_bound_observer_binding"].update(
        {
            "claim_boundary": "c0 final same-bit row2 marker and immediate blocked bank-ready candidates",
            "generated_members": generated,
            "runner": runner,
            "functional_rtl_changed": False,
        }
    )
    value["post_sim_return_core"].update(
        {
            "members": post_sim,
            "runner": {
                "path": "PREPARE_AND_RUN.sh",
                "bytes": (package / "PREPARE_AND_RUN.sh").stat().st_size,
                "sha256": base.sha256(package / "PREPARE_AND_RUN.sh"),
                "shared_post_sim_invocations": (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8").count(
                    'python3 "$post_sim_helper" finalize --request "$post_sim_request"'
                ),
            },
            "claim_boundary": json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))["claim_boundary"],
        }
    )
    value["identity_rebound_text_members"] = changed
    value["release_gate_applicability"].update(
        {
            "materialized_config": "receipt_reuse_byte_equal_p30",
            "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
            "first_fresh_extra_audit": "blocking_applicable_external_clean_extract_required",
        }
    )
    value["release_gate_matrix"]["materialized_config"].update(
        {
            "applicability": "receipt_reuse",
            "blocking": False,
            "pass": True,
            "scope": "87 p30 installed payload members byte-equal and SCA identity-normalized equal",
        }
    )
    value["release_gate_matrix"]["source_bound_observer_generation"]["pass"] = True
    value["release_gate_matrix"]["source_bound_final_zip"]["pass"] = None
    value["release_gate_matrix"]["post_sim_return_core"]["pass"] = None
    value["release_gate_matrix"]["first_fresh_extra_audit"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "causal_classes": ["server_start", "actual_input", "state_safety", "return"],
        "pass": None,
        "scope": "external independent clean extraction of the one exact final ZIP",
    }
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
    configure_predecessor()
    predecessor.patch_post_sim = patch_post_sim
    predecessor.patch_contract_docs = patch_contract_docs
    predecessor.patch_manifest = patch_manifest
    return predecessor.build_directory(destination)


def frozen_checks(package: Path) -> dict[str, Any]:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        prefix = SOURCE_ID + "/"
        source = {name[len(prefix):]: archive.read(name) for name in archive.namelist() if name.startswith(prefix) and not name.endswith("/")}
    frozen = sorted(name for name in source if name.startswith("workload/runtime/runs/c0/install/"))
    sca = {
        relative: (package / relative).read_text(encoding="utf-8").replace(PACKAGE_ID, SOURCE_ID) == source[relative].decode()
        for relative in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json")
    }
    return {
        "source_p30_zip_sha256": SOURCE_SHA256,
        "frozen_install_payload_member_count": len(frozen),
        "frozen_install_payload_byte_equal": all((package / name).read_bytes() == source[name] for name in frozen),
        "sca_identity_normalized_equal": sca,
        "numeric_w3_golden_workload_config_mapping_bitstream_execplan_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = (output / PACKAGE_ID, output / f"{PACKAGE_ID}.zip", output / f"{PACKAGE_ID}.zip.sha256", output / f"{PACKAGE_ID}.build.json")
    if any(target.exists() for target in targets):
        raise BuildError("refusing to overwrite p31 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p30 source differs")
    package, receipts = build_directory(output)
    frozen = frozen_checks(package)
    if not frozen["frozen_install_payload_byte_equal"] or not all(frozen["sca_identity_normalized_equal"].values()) or frozen["frozen_install_payload_member_count"] != 87:
        raise BuildError("frozen p30 payload differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    with tempfile.TemporaryDirectory(prefix=".p31_repeat_", dir=ROOT) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeat_zip = Path(temporary) / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p31 deterministic double build differs")
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p31-postclear-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AND_EXTRA_AUDIT",
        "package_identity": PACKAGE_ID,
        "source_p30_zip_sha256": SOURCE_SHA256,
        "source_p30_analysis_sha256": P30_ANALYSIS_SHA256,
        "rule_change_epoch_id": "20260810-first-fresh-extra-audit-v1",
        "first_fresh_after_change": True,
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha,
        "final_zip_count": 1,
        "deterministic_double_build": deterministic,
        "receipts": receipts,
        "frozen": frozen,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
