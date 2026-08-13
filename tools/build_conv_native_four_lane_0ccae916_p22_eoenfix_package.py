#!/usr/bin/env python3
"""Build p22 by correcting the one p21 epoch-owner enable identifier."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p21_epoch_owner_package as previous


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p21_epochowner"
PACKAGE_ID = "r5_n4_0cc_p22_eoenfix"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_876_983
SOURCE_SHA256 = "cd78dd1aa2234bc12e4588b957fa900e71030486bd6eca4c315155451f631c8d"
P21_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p21_return_analysis/report_v2.json"
BUILD_PROFILE = ROOT / "outputs/conv_native_four_lane_0ccae916_p22_eoenfix/server_package_build_profile.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p22_eoenfix/build"
OBSERVER = "tb_probe/native_return_observer.svh"
SOURCE_OBSERVER_SHA256 = "755ee7da53eb9550afaad604c4da5495cd071b26291ce76eb747d49506b0b527"
BAD = "if (return_obs_enabled && n4d_fd != 0) begin"
GOOD = "if (return_obs_eo_enabled && n4d_fd != 0) begin"
RULE_PATHS = previous.RULE_PATHS
base = previous.base


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


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
        path.write_text(payload.decode().replace(SOURCE_ID, PACKAGE_ID), encoding="utf-8", newline="\n")
        changed.append(path.relative_to(package).as_posix())
    required = {
        "PREPARE_AND_RUN.sh", "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        "TEST_PACKAGE_MANIFEST.json", "package_manifest.json",
        "workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json",
    }
    if not required <= set(changed):
        raise BuildError(f"identity rebinding surface differs: {sorted(required - set(changed))}")
    return changed


def fix_observer(package: Path) -> dict[str, Any]:
    path = package / OBSERVER
    payload = path.read_bytes()
    if base.digest(payload) != SOURCE_OBSERVER_SHA256:
        raise BuildError("exact p21 observer identity differs")
    text = payload.decode()
    if text.count(BAD) != 1 or text.count(GOOD) != 1:
        raise BuildError("p21 epoch-owner consumer surface differs")
    fixed = text.replace(BAD, GOOD, 1)
    if "return_obs_enabled" in fixed:
        raise BuildError("legacy undeclared epoch-owner enable symbol remains")
    path.write_text(fixed, encoding="utf-8", newline="\n")
    return {
        "path": OBSERVER, "source_bytes": len(payload), "source_sha256": base.digest(payload),
        "final_bytes": path.stat().st_size, "final_sha256": base.sha256(path),
        "exact_change_count": 1, "from": "return_obs_enabled", "to": "return_obs_eo_enabled",
        "functional_rtl_changed": False, "predicate_semantics_changed": False,
    }


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["claim_boundary"] = (
        "p22 corrects one package-local p21 epoch-owner enable identifier and changes no "
        "predicate, hierarchy reference, runner control flow, workload, config, mapping, "
        "bitstream, execplan, SCA, numeric/W3/golden, timeout or functional RTL semantics. "
        "It remains c0 diagnostic-only until formal server return."
    )
    paths = base.projected_paths(package, value)
    longest = max(paths, key=lambda item: (len(item), item))
    value["path_budget"]["max_projected_absolute_path_chars"] = value["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    write_json(path, value)
    return value


def patch_pointer_readme(package: Path) -> None:
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value.update({"schema": "conv-native-four-lane-p22-eoenfix-pointer-v1", "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN"})
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p22 epoch-owner identifier fix\n\n"
        "Fresh c0 successor of p21. It corrects one package-local observer identifier; "
        "all DUT/config/numeric payload is frozen.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8", newline="\n",
    )


def patch_manifest(package: Path, contract: dict[str, Any], changed: list[str], observer: dict[str, Any]) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    analysis = json.loads(P21_ANALYSIS.read_text(encoding="utf-8"))
    if analysis.get("valid") is not True or analysis.get("status") != "P21_PACKAGE_LOCAL_OBSERVER_IDENTIFIER_ESCAPE_P22_REQUIRED":
        raise BuildError("formal p21 analysis is not accepted")
    value.update({
        "schema": "conv-native-four-lane-0ccae916-p22-eoenfix-package-v1",
        "package_identity": PACKAGE_ID, "install_name": PACKAGE_ID,
        "workload_install_name": PACKAGE_ID, "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
        "return_name": f"{PACKAGE_ID}_<return_tag>_return.zip", "status": "PACKAGE_READY_NOT_RUN",
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX", "candidate_release": False,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        "rule_receipts": [{"path": rel, "bytes": (ROOT / rel).stat().st_size, "sha256": base.sha256(ROOT / rel)} for rel in RULE_PATHS],
        "rule_receipts_current_match": True,
    })
    value["source_p21_formal_return_analysis"] = {
        "path": P21_ANALYSIS.relative_to(ROOT).as_posix(), "sha256": base.sha256(P21_ANALYSIS),
        "return_sha256": analysis["return_identity"]["sha256"], "source_zip_sha256": SOURCE_SHA256,
        "classification": analysis["classification"], "simulation_started": False,
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID, "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p21 production compile found one undeclared epoch-owner enable identifier at the actual time-zero consumer",
        "authorized_config_change": None, "numeric_w3_golden_repeated": False,
    }
    value["observer_binding"].update({
        "sha256": observer["final_sha256"], "source_sha256": observer["final_sha256"],
        "size_bytes": observer["final_bytes"], "changed_in_p22": True,
        "p22_epoch_owner_identifier_fix": observer, "new_dut_hierarchy_references": False,
    })
    value["p22_epoch_owner_identifier_fix"] = {
        **observer,
        "claim_boundary": "one package-local lexical identifier only; no observer predicate, DUT drive, config or RTL change",
    }
    value["release_gate_applicability"].update({
        "package_local_hdl": "blocking_applicable_actual_consumer_scope_fix",
        "diagnostic_predicate_trace": "receipt_reuse_predicate_byte_semantics_equal_p21",
        "runner_control_flow": "blocking_applicable_fresh_identity_only",
        "materialized_config": "receipt_reuse_byte_equal_p21",
        "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
    })
    value["release_gate_matrix"]["package_local_hdl"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "exact corrected declaration/time-zero actual consumer positive compile; missing declaration and mutation-back to p21 typo fail closed",
    }
    value["release_gate_matrix"]["diagnostic_predicate_trace"] = {
        "applicability": "receipt_reuse", "blocking": False, "pass": True,
        "scope": "predicate and event semantics byte-equal except lexical enable identifier repair",
    }
    value["release_gate_matrix"]["runner_control_flow"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "normal/preflight/compile/HUP/INT/TERM repeatable finalizer; identity-only mechanical rebinding",
    }
    value["release_gate_matrix"]["materialized_config"] = {
        "applicability": "receipt_reuse", "blocking": False, "pass": True,
        "scope": "87 p21 installed payload members byte-equal and SCA identity-normalized equal",
        "causal_transaction_ledger": "receipt_reuse_p18", "boundary_microtrace": "receipt_reuse_p18",
        "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
    }
    value["identity_rebound_text_members"] = changed
    paths = base.projected_paths(package, contract)
    longest = max(paths, key=lambda item: (len(item), item))
    inner = [item.relative_to(package).as_posix() for item in package.rglob("*") if item.is_file() and item != path] + ["package_manifest.json"]
    value["path_length_budget"].update({
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest), "max_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": contract["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest),
        "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{rel}") for rel in inner),
        "max_inner_suffix_chars": max(map(len, inner)), "max_inner_depth": max(len(PurePosixPath(rel).parts) for rel in inner),
        "max_inner_component_chars": max(len(part) for rel in inner for part in PurePosixPath(rel).parts),
        "outer_identity_repeated_inside": False,
    })
    base.refresh_manifest_files(package, value)
    write_json(path, value)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_base()
    package = base.safe_extract(SOURCE_ZIP, destination)
    changed = replace_identity(package)
    observer = fix_observer(package)
    contract = patch_contract(package)
    patch_pointer_readme(package)
    patch_manifest(package, contract, changed, observer)
    return package, {"identity_members": changed, "observer": observer}


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
        raise BuildError("refusing to overwrite p22 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p21 source differs")
    profile = json.loads(BUILD_PROFILE.read_text(encoding="utf-8"))
    if profile.get("contract_valid") is not True or profile.get("package_id") != PACKAGE_ID:
        raise BuildError("current p22 shadow build profile is invalid")
    package, receipts = build_directory(output)
    frozen = frozen_checks(package)
    if not frozen["frozen_install_payload_byte_equal"] or not all(frozen["sca_identity_normalized_equal"].values()):
        raise BuildError("frozen p21 payload differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    with tempfile.TemporaryDirectory(prefix=".p22_repeat_", dir=ROOT) as temp:
        repeated, _ = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p22 deterministic double build differs")
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p22-eoenfix-build-v1", "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID, "source_p21_zip_sha256": SOURCE_SHA256,
        "source_p21_analysis_sha256": base.sha256(P21_ANALYSIS), "build_profile_sha256": base.sha256(BUILD_PROFILE),
        "zip": str(zip_path), "zip_bytes": zip_path.stat().st_size, "zip_sha256": zip_sha,
        "deterministic_double_build": deterministic, "observer": receipts["observer"],
        "identity_rebound_text_members": receipts["identity_members"], "frozen": frozen,
        "functional_rtl_modified": False, "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
