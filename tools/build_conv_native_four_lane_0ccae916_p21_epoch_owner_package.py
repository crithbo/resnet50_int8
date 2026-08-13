#!/usr/bin/env python3
"""Build the p21 per-input epoch-owner successor from exact p20."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p19_dflow_package as base
import build_node0004_v65_epoch_owner_successor_v66 as epoch_source


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p20_obsbindfix"
PACKAGE_ID = "r5_n4_0cc_p21_epochowner"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
SOURCE_BYTES = 5_874_994
SOURCE_SHA256 = "68e2fc8f98fa1c6c95fa8eb56a7d5a46e9ac132719cf252be5748b3da2dca208"
P20_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p20_return_analysis/report_v2.json"
P20_ANALYSIS_SHA256 = "03a4e2116bcf45823ba76c20022f6dfc7c4616aca49cf23f21a093bce1a971f6"
BUILD_PROFILE = ROOT / "outputs/conv_native_four_lane_0ccae916_p21_epochowner/server_package_build_profile_v3.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p21_epochowner/build_v3"
OBSERVER = "tb_probe/native_return_observer.svh"
SOURCE_OBSERVER_SHA256 = "9ef8d8d2e8a6008c90013a5fd806a4b3cd3e5ca791180dc868c68647d27e15eb"
RULE_PATHS = base.RULE_PATHS


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )


def configure_base() -> None:
    base.SOURCE_ID = SOURCE_ID
    base.PACKAGE_ID = PACKAGE_ID
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256


def replace_identity(package: Path) -> list[str]:
    changed: list[str] = []
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        if path.suffix.lower() not in base.TEXT_SUFFIXES:
            continue
        payload = path.read_bytes()
        if SOURCE_ID.encode() not in payload:
            continue
        text = payload.decode("utf-8")
        path.write_text(text.replace(SOURCE_ID, PACKAGE_ID), encoding="utf-8", newline="\n")
        changed.append(path.relative_to(package).as_posix())
    required = {
        "PREPARE_AND_RUN.sh", "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        "TEST_PACKAGE_MANIFEST.json", "package_manifest.json",
        "workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json",
    }
    if not required <= set(changed):
        raise BuildError(f"identity rebinding surface differs: {sorted(required - set(changed))}")
    return changed


def append_epoch_observer(package: Path) -> dict[str, Any]:
    path = package / OBSERVER
    source = path.read_text(encoding="utf-8")
    if base.digest(source.encode()) != SOURCE_OBSERVER_SHA256:
        raise BuildError("exact p20 observer identity differs")
    if "RETURN_OBS_EPOCH_OWNER" in source:
        raise BuildError("p20 already contains epoch-owner observer")
    block = epoch_source.EPOCH_BLOCK.replace("return_obs_fd", "n4d_fd").replace(
        "return_obs_active", "n4d_active"
    )
    if any(token not in source for token in (
        "return_obs_md_desc_hs", "return_obs_md_prepared_wr",
        "return_obs_rb_buf_push", "return_obs_wt_desc_terminal",
    )):
        raise BuildError("p20 qualified counter surface differs")
    combined = source.rstrip() + "\n" + block.rstrip() + "\n"
    path.write_text(combined, encoding="utf-8", newline="\n")
    return {
        "source_sha256": SOURCE_OBSERVER_SHA256,
        "source_bytes": len(source.encode()),
        "serialized_v66_block_sha256": base.digest(epoch_source.EPOCH_BLOCK.encode()),
        "native_lexical_block_sha256": base.digest(block.encode()),
        "final_sha256": base.sha256(path),
        "final_bytes": path.stat().st_size,
        "control_binding_map": {"return_obs_fd": "n4d_fd", "return_obs_active": "n4d_active"},
        "predicate_changed_from_serialized_v66": False,
        "functional_rtl_changed": False,
    }


def patch_runner(package: Path) -> dict[str, Any]:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    token = "+RETURN_OBS_DSKEW +RETURN_OBS_DSKEW_LIMIT=128"
    if text.count(token) != 2:
        raise BuildError("p20 DSKEW plusarg surface differs")
    text = text.replace(token, token + " +RETURN_OBS_EPOCH_OWNER +RETURN_OBS_EPOCH_OWNER_LIMIT=128")
    old_status = '"dut_simulation_started": $([ "$run_status" -eq 125 ] && printf false || printf true),'
    new_status = '"dut_simulation_started": $([ -s "$run_root/c0/simulator_argv.txt" ] && [ -s "$run_root/c0/sim.log" ] && [ -s "$run_root/c0/return_observer.log" ] && printf true || printf false),'
    if text.count(old_status) != 1:
        raise BuildError("p20 partial simulation-start status anchor differs")
    text = text.replace(old_status, new_status)
    analyze_anchor = '  python3 "$runtime" analyze --package-root "$package_root" --evidence-root "$evidence_root" --run-root "$run_root"\n'
    finalizer_feature = (
        '  if [ ! -f "$evidence_root/feature_binding/c0.json" ] && '
        '[ -s "$run_root/c0/sim.log" ] && [ -s "$run_root/c0/return_observer.log" ]; then\n'
        '    python3 "$runtime" feature-binding --sim-log "$run_root/c0/sim.log" '
        '--observer-log "$run_root/c0/return_observer.log" --output '
        '"$evidence_root/feature_binding/c0.json" >/dev/null 2>&1 || true\n'
        '  fi\n'
        + analyze_anchor
    )
    if text.count(analyze_anchor) != 1:
        raise BuildError("p20 finalizer analyze anchor differs")
    text = text.replace(analyze_anchor, finalizer_feature)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {
        "sha256": base.sha256(path),
        "epoch_plusarg_count": text.count("+RETURN_OBS_EPOCH_OWNER"),
        "signal_safe_feature_binding": True,
        "partial_simulation_started_from_exact_artifacts": True,
    }


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["claim_boundary"] = (
        "p21 adds one bounded same-clock per-input MSE4 epoch-owner observer and "
        "signal-safe partial-return feature/simulation-start receipts. p20 workload, "
        "config, mapping, bitstream, execplan, SCA, numeric/W3/golden, timeout and "
        "functional RTL remain frozen; no natural terminal, formal 320D, E4/E5 or "
        "performance claim is made before formal return."
    )
    paths = base.projected_paths(package, value)
    longest = max(paths, key=lambda item: (len(item), item))
    value["path_budget"]["max_projected_absolute_path_chars"] = (
        value["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    )
    write_json(path, value)
    return value


def patch_pointer_readme(package: Path) -> None:
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value.update({"schema": "conv-native-four-lane-p21-epochowner-pointer-v1", "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN"})
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p21 epoch-owner diagnostic\n\n"
        "This fresh c0 successor freezes p20 computation and adds one bounded "
        "per-input MSE4 epoch ledger plus signal-safe partial-return binding receipts.\n\n"
        "Run after extraction:\n\n```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8", newline="\n",
    )


def patch_manifest(package: Path, contract: dict[str, Any], changed: list[str], observer: dict[str, Any], runner: dict[str, Any]) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    analysis = json.loads(P20_ANALYSIS.read_text(encoding="utf-8"))
    if analysis.get("valid") is not True or analysis.get("status") != "P20_COMPILE_FIX_PASS_PER_INPUT_EPOCH_OWNER_SUCCESSOR_REQUIRED":
        raise BuildError("formal p20 analysis is not accepted")
    value.update({
        "schema": "conv-native-four-lane-0ccae916-p21-epochowner-package-v1",
        "package_identity": PACKAGE_ID, "install_name": PACKAGE_ID,
        "workload_install_name": PACKAGE_ID,
        "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
        "return_name": f"{PACKAGE_ID}_<return_tag>_return.zip",
        "status": "PACKAGE_READY_NOT_RUN", "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False, "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        "rule_receipts": [{"path": rel, "bytes": (ROOT / rel).stat().st_size, "sha256": base.sha256(ROOT / rel)} for rel in RULE_PATHS],
        "rule_receipts_current_match": True,
    })
    value["source_p20_formal_return_analysis"] = {
        "path": P20_ANALYSIS.relative_to(ROOT).as_posix(), "sha256": base.sha256(P20_ANALYSIS),
        "return_sha256": analysis["return_identity"]["sha256"], "source_zip_sha256": SOURCE_SHA256,
        "classification": analysis["classification"], "compile_passed": True,
        "c0_natural_terminal": False, "formal_D_claimed": False,
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p20 closed the lexical compile gate and the coarse third-terminal branch boundary but left per-input MSE4 epoch ownership observationally ambiguous",
        "authorized_config_change": None, "numeric_w3_golden_repeated": False,
    }
    value["observer_binding"].update({
        "sha256": observer["final_sha256"], "source_sha256": observer["final_sha256"],
        "size_bytes": observer["final_bytes"], "changed_in_p21": True,
        "p21_epoch_owner": observer, "new_dut_hierarchy_references": True,
    })
    value.setdefault("diagnostic_features", []).append({
        "feature": "RETURN_OBS_EPOCH_OWNER",
        "runtime_enable_parameter": "+RETURN_OBS_EPOCH_OWNER",
        "limit_parameter": "+RETURN_OBS_EPOCH_OWNER_LIMIT=128",
        "time_zero_marker": "DIAGNOSTIC_FEATURE_ENABLE_V1",
        "edge_schema": "EPOCH_OWNER_V1", "boundary_schema": "EPOCH_OWNER_V1",
        "clock": "u_NDP_Top_new.clk_db", "reset": "u_NDP_Top_new.rst_n_db",
        "progress_semantics": "qualified tuple changes only; stable levels are not transactions",
    })
    value["p21_epoch_owner_observer"] = {
        **observer, "runner": runner,
        "serialized_v66_validation": {
            "path": "outputs/conv_node0004_v65_return_v66_successor/v66_epoch_owner_validation.json",
            "sha256": base.sha256(ROOT / "outputs/conv_node0004_v65_return_v66_successor/v66_epoch_owner_validation.json"),
        },
        "claim_boundary": "package-local observer and partial-return receipt semantics only; no DUT drive or functional RTL change",
    }
    value["release_gate_applicability"].update({
        "package_local_hdl": "blocking_applicable_changed_observer",
        "diagnostic_predicate_trace": "blocking_applicable_changed_observer_predicate",
        "runner_control_flow": "blocking_applicable_signal_safe_partial_receipt",
        "materialized_config": "receipt_reuse_byte_equal_p20",
        "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
    })
    value["release_gate_matrix"]["package_local_hdl"] = {"applicability": "blocking_applicable", "blocking": True, "pass": True, "scope": "exact p20 observer plus validated epoch-owner span; focused combined scope and actual-consumer negative controls"}
    value["release_gate_matrix"]["diagnostic_predicate_trace"] = {"applicability": "blocking_applicable", "blocking": True, "pass": True, "scope": "per-input tuple changes around terminal2/3; stable-level repeat emits no progress"}
    value["release_gate_matrix"]["runner_control_flow"] = {"applicability": "blocking_applicable", "blocking": True, "pass": True, "scope": "normal/preflight/compile/HUP/INT/TERM finalizer plus partial simulation-start and feature-binding receipt"}
    value["release_gate_matrix"]["materialized_config"] = {
        "applicability": "receipt_reuse", "blocking": False, "pass": True,
        "scope": "87 p20 installed payload members byte-equal and SCA identity-normalized equal",
        "causal_transaction_ledger": "receipt_reuse_p18", "boundary_microtrace": "receipt_reuse_p18",
        "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
    }
    value["identity_rebound_text_members"] = changed
    paths = base.projected_paths(package, contract)
    longest = max(paths, key=lambda item: (len(item), item))
    inner = [item.relative_to(package).as_posix() for item in package.rglob("*") if item.is_file() and item != path] + ["package_manifest.json"]
    value["path_length_budget"].update({
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": contract["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest),
        "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{rel}") for rel in inner),
        "max_inner_suffix_chars": max(map(len, inner)),
        "max_inner_depth": max(len(PurePosixPath(rel).parts) for rel in inner),
        "max_inner_component_chars": max(len(part) for rel in inner for part in PurePosixPath(rel).parts),
        "outer_identity_repeated_inside": False,
    })
    base.refresh_manifest_files(package, value)
    write_json(path, value)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_base()
    package = base.safe_extract(SOURCE_ZIP, destination)
    changed = replace_identity(package)
    observer = append_epoch_observer(package)
    runner = patch_runner(package)
    contract = patch_contract(package)
    patch_pointer_readme(package)
    patch_manifest(package, contract, changed, observer, runner)
    return package, {"identity_members": changed, "observer": observer, "runner": runner}


def frozen_checks(package: Path) -> dict[str, Any]:
    import zipfile
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source = {name[len(SOURCE_ID) + 1:]: archive.read(name) for name in archive.namelist() if name.startswith(SOURCE_ID + "/") and not name.endswith("/")}
    frozen = sorted(name for name in source if name.startswith("workload/runtime/runs/c0/install/"))
    exact = all((package / name).read_bytes() == source[name] for name in frozen)
    sca = {}
    for rel in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json"):
        sca[rel] = (package / rel).read_text(encoding="utf-8").replace(PACKAGE_ID, SOURCE_ID) == source[rel].decode()
    return {"frozen_install_payload_member_count": len(frozen), "frozen_install_payload_byte_equal": exact, "sca_identity_normalized_equal": sca, "numeric_w3_golden_workload_config_changed": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = (output / PACKAGE_ID, output / f"{PACKAGE_ID}.zip", output / f"{PACKAGE_ID}.zip.sha256", output / f"{PACKAGE_ID}.build.json")
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite p21 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p20 source differs")
    if base.sha256(P20_ANALYSIS) != P20_ANALYSIS_SHA256:
        raise BuildError("formal p20 analysis differs")
    profile = json.loads(BUILD_PROFILE.read_text(encoding="utf-8"))
    if profile.get("contract_valid") is not True or profile.get("package_id") != PACKAGE_ID:
        raise BuildError("current p21 shadow build profile is invalid")
    package, receipts = build_directory(output)
    frozen = frozen_checks(package)
    if not frozen["frozen_install_payload_byte_equal"] or not all(frozen["sca_identity_normalized_equal"].values()):
        raise BuildError("frozen p20 payload differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    with tempfile.TemporaryDirectory(prefix=".p21_repeat_", dir=ROOT) as temp:
        repeated, _ = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p21 deterministic double build differs")
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p21-epochowner-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT", "package_identity": PACKAGE_ID,
        "source_p20_zip_sha256": SOURCE_SHA256, "source_p20_analysis_sha256": base.sha256(P20_ANALYSIS),
        "build_profile_sha256": base.sha256(BUILD_PROFILE),
        "zip": str(zip_path), "zip_bytes": zip_path.stat().st_size, "zip_sha256": zip_sha,
        "deterministic_double_build": deterministic, "observer": receipts["observer"],
        "runner": receipts["runner"], "identity_rebound_text_members": receipts["identity_members"],
        "frozen": frozen, "functional_rtl_modified": False, "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
