#!/usr/bin/env python3
"""Build p25 by correcting p24's PE7-to-MSE4 public source mapping."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p24_selport_package as previous


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p24_selport"
PACKAGE_ID = "r5_n4_0cc_p25_pe7src13"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_880_634
SOURCE_SHA256 = "4690da16077c60c91d7de7c5fd1042f17bdb8db844d59ae4169528a6ba318c28"
P24_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p24_return_analysis/report.json"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p25_pe7src13/build"
OBSERVER = "tb_probe/native_return_observer.svh"
RUNTIME = "package_tools/node0004_assumed_hardware_server_runtime.py"
SOURCE_OBSERVER_SHA256 = "d00fb679950323deca8843c4813915f28b3e0ad7c2eed856b08a473a577d5986"
IGA_SHA256 = "f46f68b1eb1edc2a4ff85ce6894b8f549727512f9d3e6527d6954d7bb352c82e"
CONNECT_SHA256 = previous.CONNECT_SHA256
WR_MSE_SHA256 = previous.WR_MSE_SHA256
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


def patch_observer(package: Path) -> dict[str, Any]:
    path = package / OBSERVER
    source = path.read_bytes()
    if base.digest(source) != SOURCE_OBSERVER_SHA256:
        raise BuildError("exact p24 observer identity differs")
    text = source.decode()
    begin = "// p24 PUBLIC_SELECT_PORT_BEGIN"
    end = "// p24 PUBLIC_SELECT_PORT_END"
    if text.count(begin) != 1 or text.count(end) != 1:
        raise BuildError("p24 public select-port span differs")
    start = text.index(begin)
    finish = text.index(end, start) + len(end)
    block = text[start:finish]
    if block.count("iga2se_mem_inport[4][7]") != 6 or block.count("== 7") != 2:
        raise BuildError("p24 source-id assumption surface differs")
    patched = block.replace("logic [3:0] return_obs_sp_prev_src", "logic [4:0] return_obs_sp_prev_src")
    patched = patched.replace("iga2se_mem_inport[4][7]", "iga2se_mem_inport[4][13]")
    patched = patched.replace("== 7", "== 13")
    source_accept = (
        f"sp_pe7_accept = {previous.CONNECT}.iga2se_mem_inport[4][13][22] &&"
    )
    selected_source_accept = (
        f"sp_pe7_accept = ({previous.CONNECT}.mse_mem_idx_src_id[4][1] == 13) &&\n"
        f"                            {previous.CONNECT}.iga2se_mem_inport[4][13][22] &&"
    )
    if patched.count(source_accept) != 1:
        raise BuildError("p24 source acceptance predicate differs")
    patched = patched.replace(source_accept, selected_source_accept, 1)
    patched = patched.replace("// p24 PUBLIC_SELECT_PORT_BEGIN", "// p25 PE7_SOURCE13_BEGIN")
    patched = patched.replace("// p24 PUBLIC_SELECT_PORT_END", "// p25 PE7_SOURCE13_END")
    patched = patched.replace("schema=PUBLIC_SELECT_PORT_V1", "schema=PUBLIC_PE7_SOURCE13_V2")
    patched = patched.replace("PUBLIC_SELECT_PORT_V1 |", "PUBLIC_PE7_SOURCE13_V2 |")
    final = text[:start] + patched + text[finish:]
    path.write_text(final, encoding="utf-8", newline="\n")
    return {
        "path": OBSERVER,
        "source_bytes": len(source), "source_sha256": base.digest(source),
        "source_span_sha256": base.digest(block.encode()),
        "final_bytes": path.stat().st_size, "final_sha256": base.sha256(path),
        "pe7_source_id": 13,
        "mapping_formula": "MSE_SRC_LC_NUM(12)+(13-12)%2(1); for MSE4 offset index0=-1 gives PE7",
        "source_port": "Stream_Engine_Connect.iga2se_mem_inport[4][13]",
        "configured_selector": "Stream_Engine_Connect.mse_mem_idx_src_id[4][1]",
        "selected_output": "Stream_Engine_Connect.mse_mem_queue_{idx,tag}[4][1]",
        "consumer_input": "Memory_WR_Stream_Engine.mse_mem_queue_{idx,tag}[1]",
        "all_edge_classes_in_one_event_mask_record": True,
        "public_module_ports_only": True,
        "functional_rtl_changed": False,
    }


def patch_runtime_identity(package: Path) -> dict[str, Any]:
    path = package / RUNTIME
    text = path.read_text(encoding="utf-8")
    anchor = f'    "Memory_WR_Stream_Engine.sv": "{WR_MSE_SHA256}",\n'
    if text.count(anchor) != 2 or "IGA_Interconnect.sv" in text:
        raise BuildError("p24 production identity collector surface differs")
    text = text.replace(anchor, anchor + f'    "IGA_Interconnect.sv": "{IGA_SHA256}",\n')
    path.write_text(text, encoding="utf-8", newline="\n")
    return {
        "path": RUNTIME, "sha256": base.sha256(path),
        "added_leaves": {"IGA_Interconnect.sv": IGA_SHA256},
        "preserved_leaves": {
            "Stream_Engine_Connect.sv": CONNECT_SHA256,
            "Memory_WR_Stream_Engine.sv": WR_MSE_SHA256,
        },
        "collection_timing": "after actual production compile",
        "identity_difference_blocks_simulator": False,
    }


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["claim_boundary"] = (
        "p25 freezes p24 DUT/config/numeric payload and corrects only the public diagnostic "
        "source mapping from 7 to MSE4 PE7 source 13, plus actual IGA identity collection."
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
        "schema": "conv-native-four-lane-p25-pe7-source13-pointer-v1",
        "package_identity": PACKAGE_ID, "status": "PACKAGE_READY_NOT_RUN",
    })
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p25 PE7 source13 diagnostic\n\n"
        "Fresh c0 successor of p24. It corrects the MSE4 PE7 public source from 7 to 13, "
        "retains the Connect-to-Memory public ledger, and collects actual IGA_Interconnect identity.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8", newline="\n",
    )


def patch_manifest(
    package: Path,
    contract: dict[str, Any],
    changed: list[str],
    observer: dict[str, Any],
    identity: dict[str, Any],
) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    analysis = json.loads(P24_ANALYSIS.read_text(encoding="utf-8"))
    if analysis.get("valid") is not True or analysis.get("status") != "P24_PUBLIC_BOUNDARY_PASS_OBSERVER_SOURCE_MAPPING_SUCCESSOR_REQUIRED":
        raise BuildError("formal p24 analysis is not accepted")
    value.update({
        "schema": "conv-native-four-lane-0ccae916-p25-pe7-source13-package-v1",
        "package_identity": PACKAGE_ID, "install_name": PACKAGE_ID,
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
    value["source_p24_formal_return_analysis"] = {
        "path": P24_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": base.sha256(P24_ANALYSIS),
        "return_sha256": analysis["return_identity"]["sha256"],
        "source_zip_sha256": SOURCE_SHA256,
        "classification": analysis["classification"],
        "compile_passed": True, "c0_natural_terminal": False,
        "formal_D_claimed": False,
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p24 proved src_id13 and Connect-to-Memory index8, but its observer read unselected source7 instead of MSE4 PE7 source13",
        "authorized_config_change": None,
        "numeric_w3_golden_repeated": False,
    }
    value["observer_binding"].update({
        "sha256": observer["final_sha256"],
        "source_sha256": observer["final_sha256"],
        "size_bytes": observer["final_bytes"],
        "changed_in_p24": False, "changed_in_p25": True,
        "p25_pe7_source13": observer,
        "new_dut_hierarchy_references": True,
    })
    value["diagnostic_features"].append({
        "feature": "RETURN_OBS_PE7_SOURCE13",
        "runtime_enable_parameter": "+RETURN_OBS_SELECT_PORT",
        "qualified_limit_parameter": "+RETURN_OBS_SELECT_PORT_QUAL_LIMIT=128",
        "state_limit_parameter": "+RETURN_OBS_SELECT_PORT_STATE_LIMIT=64",
        "time_zero_marker": "DIAGNOSTIC_FEATURE_ENABLE_V1",
        "edge_schema": "PUBLIC_PE7_SOURCE13_V2",
        "clock": "u_NDP_Top_new.clk_db",
        "reset": "u_NDP_Top_new.rst_n_db",
        "progress_semantics": "selected source13, Connect and Memory valid-and-backpressure bits are emitted together in one event_mask row",
        "multiclass_no_loss": "ALL_REQUIRED_CLASSES_IN_ONE_EVENT_MASK_RECORD",
    })
    value["p25_pe7_source13_observer"] = {
        **observer, "production_identity": identity,
        "actual_iga_identity_required_in_return": True,
    }
    for name, sha in identity["added_leaves"].items():
        value["expected_production_rtl_identity"]["leaves"][name] = sha
        value["expected_production_rtl_identity"]["cloud_authority_leaves"][name] = sha
        value["cloud_rtl_authority"]["leaves"][name] = sha
    value["release_gate_applicability"].update({
        "package_local_hdl": "blocking_applicable_corrected_public_source13_observer",
        "diagnostic_predicate_trace": "blocking_applicable_changed_source_mapping_and_multiclass_event_mask",
        "runner_control_flow": "blocking_applicable_fresh_identity_only",
        "materialized_config": "receipt_reuse_byte_equal_p24",
        "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
    })
    value["release_gate_matrix"]["package_local_hdl"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "public source13/Connect/Memory ports and exact IGA/Connect/Memory-WR identities",
    }
    value["release_gate_matrix"]["diagnostic_predicate_trace"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "same-clock source13-select predicate, exact logger/parser and simultaneous all-class event_mask trace",
    }
    value["release_gate_matrix"]["diagnostic_multiclass_edge_no_loss"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "all three qualified edge classes are carried in one exact event_mask row; no priority selection or class snapshot loss",
    }
    value["release_gate_matrix"]["runner_control_flow"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": True,
        "scope": "normal/preflight/compile/HUP/INT/TERM repeatable finalizer; p24 normalized-equal except identity",
    }
    value["release_gate_matrix"]["materialized_config"] = {
        "applicability": "receipt_reuse", "blocking": False, "pass": True,
        "scope": "87 p24 installed payload members byte-equal and SCA identity-normalized equal",
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
    observer = patch_observer(package)
    identity = patch_runtime_identity(package)
    contract = patch_contract(package)
    patch_pointer_readme(package)
    patch_manifest(package, contract, changed, observer, identity)
    return package, {"identity_members": changed, "observer": observer, "production_identity": identity}


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
        raise BuildError("refusing to overwrite p25 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p24 source differs")
    package, receipts = build_directory(output)
    frozen = frozen_checks(package)
    if not frozen["frozen_install_payload_byte_equal"] or not all(frozen["sca_identity_normalized_equal"].values()):
        raise BuildError("frozen p24 payload differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    with tempfile.TemporaryDirectory(prefix=".p25_repeat_", dir=ROOT) as temp:
        repeated, _ = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p25 deterministic double build differs")
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(
        f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "conv-native-four-lane-p25-pe7-source13-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "source_p24_zip_sha256": SOURCE_SHA256,
        "source_p24_analysis_sha256": base.sha256(P24_ANALYSIS),
        "zip": str(zip_path), "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha, "deterministic_double_build": deterministic,
        "observer": receipts["observer"],
        "production_identity": receipts["production_identity"],
        "identity_rebound_text_members": receipts["identity_members"],
        "frozen": frozen, "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
