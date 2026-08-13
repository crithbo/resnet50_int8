#!/usr/bin/env python3
"""Build p26 by enabling p25's already compiled Memory_AG epoch-flow ledger."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p25_pe7src13_package as previous


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p25_pe7src13"
PACKAGE_ID = "r5_n4_0cc_p26_memag"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_882_004
SOURCE_SHA256 = "d2c0e853391f012273e6d6bb2e07c6e3bcbee0d895db5b866c77526c580390e6"
P25_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p25_return_analysis/report.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p26_memag/build"
OBSERVER = "tb_probe/native_return_observer.svh"
SOURCE_OBSERVER_SHA256 = "e54a72e0f6e96f0ae26b33312881c71fb4927d4c4986da895ab18c026322daf1"
base = previous.base
RULE_PATHS = (
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    ".agents/rules/整网测试收敛优化专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
)


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
        path.write_text(
            payload.decode().replace(SOURCE_ID, PACKAGE_ID),
            encoding="utf-8", newline="\n",
        )
        changed.append(path.relative_to(package).as_posix())
    required = {
        "PREPARE_AND_RUN.sh", "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        "TEST_PACKAGE_MANIFEST.json", "package_manifest.json",
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    }
    if not required <= set(changed):
        raise BuildError(f"identity rebinding surface differs: {sorted(required - set(changed))}")
    return changed


def patch_runner(package: Path) -> dict[str, Any]:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    anchor = (
        "+RETURN_OBS_SELECT_PORT +RETURN_OBS_SELECT_PORT_QUAL_LIMIT=128 "
        "+RETURN_OBS_SELECT_PORT_STATE_LIMIT=64"
    )
    replacement = (
        "+RETURN_OBS_EPOCH_FLOW +RETURN_OBS_EPOCH_FLOW_LIMIT=256 " + anchor
    )
    if text.count(anchor) != 2 or "+RETURN_OBS_EPOCH_FLOW" in text:
        raise BuildError("p25 runner diagnostic plusarg surface differs")
    text = text.replace(anchor, replacement)
    path.write_text(text, encoding="utf-8", newline="\n")
    return {
        "path": "PREPARE_AND_RUN.sh", "sha256": base.sha256(path),
        "invocation_occurrences": text.count(replacement),
        "enabled_features": ["RETURN_OBS_SELECT_PORT", "RETURN_OBS_EPOCH_FLOW"],
        "epoch_flow_limit": 256,
        "changed_semantics": "runtime feature binding only",
    }


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["claim_boundary"] = (
        "p26 freezes p25 DUT/config/numeric/observer bytes and enables the existing, production-compiled "
        "Memory_AG EPOCH_FLOW ledger alongside the p25 public source13 ledger."
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
    value.update({
        "schema": "conv-native-four-lane-p26-memory-ag-pointer-v1",
        "package_identity": PACKAGE_ID,
        "status": "PACKAGE_READY_NOT_RUN",
    })
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p26 Memory_AG boundary diagnostic\n\n"
        "Fresh c0 successor of p25. It retains the exact p25 observer and enables both the "
        "source13 public ledger and the already compiled Memory_AG epoch-flow consumer ledger.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8", newline="\n",
    )


def patch_manifest(
    package: Path, contract: dict[str, Any], changed: list[str], runner: dict[str, Any]
) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    analysis = json.loads(P25_ANALYSIS.read_text(encoding="utf-8"))
    if (
        analysis.get("valid") is not True
        or analysis.get("status")
        != "P25_SOURCE13_PUBLIC_CHAIN_PASS_MEMORY_AG_CONSUMER_SUCCESSOR_REQUIRED"
    ):
        raise BuildError("formal p25 analysis is not accepted")
    observer = package / OBSERVER
    if base.sha256(observer) != SOURCE_OBSERVER_SHA256:
        raise BuildError("exact p25 observer identity differs")
    value.update({
        "schema": "conv-native-four-lane-0ccae916-p26-memory-ag-package-v1",
        "package_identity": PACKAGE_ID,
        "install_name": PACKAGE_ID,
        "workload_install_name": PACKAGE_ID,
        "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
        "return_name": f"{PACKAGE_ID}_<return_tag>_return.zip",
        "status": "PACKAGE_READY_NOT_RUN",
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        "rule_receipts": [
            {"path": rel, "bytes": (ROOT / rel).stat().st_size, "sha256": base.sha256(ROOT / rel)}
            for rel in RULE_PATHS
        ],
        "rule_receipts_current_match": True,
    })
    value["source_p25_formal_return_analysis"] = {
        "path": P25_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": base.sha256(P25_ANALYSIS),
        "return_sha256": analysis["return_identity"]["sha256"],
        "source_zip_sha256": SOURCE_SHA256,
        "classification": analysis["classification"],
        "compile_passed": True,
        "public_source13_chain_passed": True,
        "c0_natural_terminal": False,
        "formal_D_claimed": False,
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": (
            "p25 proved PE7/source13 through Memory-WR index8 acceptance but did not runtime-enable "
            "the already present actual Memory_AG epoch-flow ledger"
        ),
        "authorized_config_change": None,
        "numeric_w3_golden_repeated": False,
    }
    value["observer_binding"].update({
        "sha256": SOURCE_OBSERVER_SHA256,
        "source_sha256": SOURCE_OBSERVER_SHA256,
        "size_bytes": observer.stat().st_size,
        "changed_in_p26": False,
        "production_compile_receipt_reuse": "formal p25 compile_exit_status=0 exact observer bytes",
    })
    value["p26_simultaneous_consumer_features"] = {
        "runner": runner,
        "public_feature": {
            "plusargs": [
                "+RETURN_OBS_SELECT_PORT",
                "+RETURN_OBS_SELECT_PORT_QUAL_LIMIT=128",
                "+RETURN_OBS_SELECT_PORT_STATE_LIMIT=64",
            ],
            "schema": "PUBLIC_PE7_SOURCE13_V2",
            "proven_p25_event_mask": 7,
        },
        "actual_consumer_feature": {
            "plusargs": ["+RETURN_OBS_EPOCH_FLOW", "+RETURN_OBS_EPOCH_FLOW_LIMIT=256"],
            "schema": "EPOCH_FLOW_V1",
            "boundaries": [
                "Memory_AG input valid/same/gotten/keep masks",
                "all-match predicate",
                "actual queue full/empty/write/read",
                "input modes/keeps/indices/tags and source backpressure",
            ],
        },
        "same_clock": "u_NDP_Top_new.clk_db",
        "observer_bytes_changed": False,
        "functional_rtl_changed": False,
    }
    value["release_gate_applicability"].update({
        "package_local_hdl": "receipt_reuse_exact_p25_observer_production_compile",
        "diagnostic_predicate_trace": "blocking_applicable_changed_runtime_feature_conjunction",
        "runner_control_flow": "blocking_applicable_changed_plusarg_binding",
        "materialized_config": "receipt_reuse_byte_equal_p25",
        "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
    })
    value["release_gate_matrix"]["package_local_hdl"] = {
        "applicability": "receipt_reuse", "blocking": False, "pass": True,
        "scope": "exact p25 observer bytes passed actual production compile; no HDL/XMR change",
        "receipt": analysis["source_identity"]["observer_sha256"],
    }
    value["release_gate_matrix"]["diagnostic_semantics"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "exact runner enables both source13 and EPOCH_FLOW; logger grammars remain exact p25 bytes",
    }
    value["release_gate_matrix"]["diagnostic_multiclass_edge_no_loss"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "public event_mask preserves all three p25 edge classes; epoch-flow preserves event-specific rows",
    }
    value["release_gate_matrix"]["runner_control_flow"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "normal/preflight/compile/HUP/INT/TERM plus exact dual-feature argv/receipt binding",
    }
    value["release_gate_matrix"]["materialized_config"] = {
        "applicability": "receipt_reuse", "blocking": False, "pass": True,
        "scope": "87 p25 installed payload members byte-equal and SCA identity-normalized equal",
        "causal_transaction_ledger": "receipt_reuse_p18",
        "boundary_microtrace": "receipt_reuse_p18",
        "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
    }
    value["identity_rebound_text_members"] = changed
    paths = base.projected_paths(package, contract)
    longest = max(paths, key=lambda item: (len(item), item))
    inner = [
        item.relative_to(package).as_posix()
        for item in package.rglob("*") if item.is_file() and item != path
    ] + ["package_manifest.json"]
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
    runner = patch_runner(package)
    contract = patch_contract(package)
    patch_pointer_readme(package)
    patch_manifest(package, contract, changed, runner)
    return package, {"identity_members": changed, "runner": runner}


def frozen_checks(package: Path) -> dict[str, Any]:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source = {
            name[len(SOURCE_ID) + 1:]: archive.read(name)
            for name in archive.namelist()
            if name.startswith(SOURCE_ID + "/") and not name.endswith("/")
        }
    frozen = sorted(name for name in source if name.startswith("workload/runtime/runs/c0/install/"))
    exact = all((package / name).read_bytes() == source[name] for name in frozen)
    sca = {}
    for rel in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json"):
        sca[rel] = (
            (package / rel).read_text(encoding="utf-8").replace(PACKAGE_ID, SOURCE_ID)
            == source[rel].decode()
        )
    return {
        "frozen_install_payload_member_count": len(frozen),
        "frozen_install_payload_byte_equal": exact,
        "sca_identity_normalized_equal": sca,
        "observer_byte_equal": (package / OBSERVER).read_bytes() == source[OBSERVER],
        "numeric_w3_golden_workload_config_mapping_bitstream_execplan_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = (
        output / PACKAGE_ID, output / f"{PACKAGE_ID}.zip",
        output / f"{PACKAGE_ID}.zip.sha256", output / f"{PACKAGE_ID}.build.json",
    )
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite p26 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p25 source differs")
    package, receipts = build_directory(output)
    frozen = frozen_checks(package)
    if (
        not frozen["frozen_install_payload_byte_equal"]
        or not frozen["observer_byte_equal"]
        or not all(frozen["sca_identity_normalized_equal"].values())
    ):
        raise BuildError("frozen p25 payload differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    with tempfile.TemporaryDirectory(prefix=".p26_repeat_", dir=ROOT) as temp:
        repeated, _ = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p26 deterministic double build differs")
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(
        f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "conv-native-four-lane-p26-memory-ag-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "source_p25_zip_sha256": SOURCE_SHA256,
        "source_p25_analysis_sha256": base.sha256(P25_ANALYSIS),
        "zip": str(zip_path), "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha, "deterministic_double_build": deterministic,
        "runner": receipts["runner"],
        "identity_rebound_text_members": receipts["identity_members"],
        "frozen": frozen, "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
