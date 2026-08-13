from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.analyze_node0004_v24_return import (
    integer_entry,
    load_json,
    safe_entries,
    sha256_bytes,
    sha256_file,
)


INSTALL = "r5_n4_hw_v60_install_only"
RETURN_ROOT = f"{INSTALL}_return"
RETURN_SHA = "6cd43cd7bbea1c2e2dd37c409b7f4cca7eba2468fd2bca645945f49b4fadf0d2"
SOURCE_SHA = "cb3342e90510e4cd1e66afb9a19977cc5eae725abccf987346757d3d34937ec8"
CLOUD_RTL = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
BITSTREAM_SHA = "cb12f3345c42d89d17188102bd80cbeef224ddff26fd5726ed1a16af49d14e73"
MAPPING_PATH = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-conv-native-four-lane-0cc-p9-tx5-c0/execplan_conv/wave-0/"
    "pipeline_output/config/op_w0/mapping_review.json"
)
FINAL_JSON_PATH = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-conv-native-four-lane-0cc-p9-tx5-c0/execplan_conv/wave-0/"
    "pipeline_output/jsons/op_w0_resnet50_conv_node0004_wave0.json"
)
BITSTREAM_MEMBER = (
    "workload/runtime/runs/c0/install/cfg_pkg/"
    "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
)


def kv(text: str, marker: str) -> dict[str, str]:
    lines = [line for line in text.splitlines() if marker in line]
    return (
        dict(re.findall(r"([A-Za-z0-9_]+)=([^ ]+)", lines[-1]))
        if lines
        else {}
    )


def number(record: dict[str, str], key: str, default: int = -1) -> int:
    try:
        return int(record.get(key, str(default)), 0)
    except ValueError:
        return default


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", required=True, type=Path)
    parser.add_argument("--source-zip", required=True, type=Path)
    parser.add_argument("--source-sidecar", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    ret = args.return_zip.resolve()
    src = args.source_zip.resolve()
    ret_sha = sha256_file(ret)
    src_sha = sha256_file(src)
    if ret_sha != RETURN_SHA:
        errors.append("return SHA mismatch")
    if src_sha != SOURCE_SHA:
        errors.append("source SHA mismatch")
    sidecar_valid = args.source_sidecar.read_text(encoding="ascii").strip() == (
        f"{src_sha}  {src.name}"
    )
    if not sidecar_valid:
        errors.append("source sidecar mismatch")

    entries, ret_errors, ret_meta = safe_entries(ret, RETURN_ROOT)
    source, src_errors, src_meta = safe_entries(src, INSTALL)
    errors += ret_errors + src_errors

    allow = load_json(entries, "RETURN_ALLOWLIST.json")
    returned = load_json(entries, "RETURN_MANIFEST.json")
    records = allow.get("records", [])
    expected = {"RETURN_ALLOWLIST.json", "RETURN_MANIFEST.json"}
    for item in records:
        path = item.get("path")
        if not isinstance(path, str):
            errors.append("allowlist path invalid")
            continue
        expected.add(path)
        payload = entries.get(path)
        if not (
            payload is not None
            and len(payload) == item.get("size_bytes")
            and sha256_bytes(payload) == item.get("sha256")
        ):
            errors.append(f"receipt differs:{path}")
    exact_return_set = set(entries) == expected
    if not exact_return_set:
        errors.append("return exact-set differs")

    source_manifest_bytes = source.get("package_manifest.json", b"")
    returned_manifest_bytes = entries.get(
        "evidence/returned_package_manifest.json", b""
    )
    manifest = json.loads(source_manifest_bytes or b"{}")
    source_bound = (
        returned.get("install_name") == INSTALL
        and returned.get("records") == records
        and returned_manifest_bytes == source_manifest_bytes
    )
    if not source_bound:
        errors.append("return/source manifest binding differs")
    source_files = manifest.get("files", {})
    source_exact = (
        set(source_files) == set(source) - {"package_manifest.json"}
        and all(
            path in source and sha256_bytes(source[path]) == digest
            for path, digest in source_files.items()
        )
    )
    if not source_exact:
        errors.append("source exact-set differs")

    gate = load_json(entries, "evidence/SERVER_RESULT_GATE.json")
    package_preflight = load_json(entries, "evidence/package_preflight.json")
    install_preflight = load_json(entries, "evidence/install_preflight.json")
    observer_preflight = load_json(entries, "evidence/observer_precompile.json")
    feature_binding = load_json(
        entries, "evidence/diagnostic_feature_binding.json"
    )
    root_gate = load_json(entries, "evidence/ndp_root_toplevel_gate.json")
    compile_status = integer_entry(
        entries, "evidence/compile_exit_status.txt", 125
    )
    run_status = integer_entry(entries, "evidence/run_exit_status.txt", 125)
    signal = entries.get("evidence/signal_status.txt", b"MISSING").decode().strip()
    compile_log = entries.get(
        "runs/compile/sim_results/compile.log", b""
    ).decode("utf-8", errors="replace")
    compile_driver = entries.get(
        "runs/compile/sim_results/compile_driver.log", b""
    ).decode("utf-8", errors="replace")
    observer_log = entries.get(
        "runs/c0/return_observer.log", b""
    ).decode("utf-8", errors="replace")
    sim_log = entries.get("runs/c0/sim.log", b"").decode(
        "utf-8", errors="replace"
    )
    argv = entries.get("runs/c0/simulator_argv.txt", b"").decode(
        "utf-8", errors="replace"
    )
    observer_sha = manifest.get("observer_sha256")
    package_ok = package_preflight.get("valid") is True
    install_ok = (
        install_preflight.get("valid") is True
        and install_preflight.get("runtime_d_initially_absent") is True
    )
    root_ok = (
        root_gate.get("valid") is True
        and root_gate.get("ndp_root_toplevel_unchanged") is True
    )
    observer_ok = (
        observer_preflight.get("valid") is True
        and observer_preflight.get("observed_sha256") == observer_sha
        and sha256_bytes(source.get("tb_probe/native_return_observer.svh", b""))
        == observer_sha
    )
    compile_invoked = (
        "vcs" in compile_driver.lower()
        and "native_return_observer.svh" in compile_log
        and "NDP_Top_phy_filelist.f" in compile_driver
    )
    actual_time0_binding = (
        "[RETURN_OBSERVER] enabled" in sim_log
        and "feature=RETURN_OBS_LC13_LC14 enabled=1" in observer_log
        and "LC13_LC14_BOUNDARY_V1" in observer_log
    )
    formal_feature_binding = feature_binding.get("valid") is True
    argv_receipt_omits_features = (
        "+RETURN_OBSERVER" in argv
        and "+RETURN_OBS_LC13_LC14" not in argv
        and all(
            feature.get("time_zero_marker_valid") is True
            for feature in feature_binding.get("features", [])
        )
    )
    if not all(
        (
            package_ok,
            install_ok,
            root_ok,
            observer_ok,
            compile_invoked,
            actual_time0_binding,
            argv_receipt_omits_features,
        )
    ):
        errors.append("preflight/compile/dynamic-boundary evidence differs")

    canonical = kv(observer_log, "CANONICAL_DIAG_DECISION_V1")
    dterm = kv(observer_log, "DTERM_OWNER_BOUNDARY_V1")
    lc_chain_wrong = kv(observer_log, "LC13_LC14_BOUNDARY_V1")
    row4 = kv(observer_log, "ROWLC4_BUFAG_BOUNDARY_V1")
    descriptor = kv(observer_log, "MSE4_DESCRIPTOR_BOUNDARY_V1")
    wrterm = kv(observer_log, "WRTERM2_BOUNDARY_V1")
    dynamic = {
        "same_hang": (
            canonical.get("decision")
            == "LONG_RUNNING_HANG_AT_D_WRITE_DATA_TO_LAST_INDEX0_SLICE_FINISH"
            and number(canonical, "qualified_progress") == 562
            and number(canonical, "qualified_delta") == 0
        ),
        "wrong_physical_lc13_advanced_once": (
            number(lc_chain_wrong, "q13_out") == 1
        ),
        "wrong_physical_lc14_lc15_disabled": (
            lc_chain_wrong.get("cfg14", "").startswith("0,")
            and lc_chain_wrong.get("cfg15", "").startswith("0,")
        ),
        "d_write_not_terminal": (
            number(dterm, "lc9_last0") == 1
            and number(dterm, "desc_push") == 32
            and number(dterm, "desc_pop") == 32
            and number(canonical, "slice_finish") == 0
        ),
        "group4_and_descriptor_progress": (
            number(row4, "buf_push") == 53
            and number(row4, "buf_pop") == 37
            and number(descriptor, "fifo_push") == 32
            and number(descriptor, "fifo_pop") == 32
            and number(wrterm, "post_src_push") == 4
        ),
    }
    if not all(dynamic.values()):
        errors.append("qualified v60 chronology differs")

    mapping = json.loads(MAPPING_PATH.read_text(encoding="utf-8"))
    node_to_resource = {
        item["node"]: item["resource"] for item in mapping["node_to_resource"]
    }
    required_mapping = {
        "DRAM_LC.LC13": "LC6",
        "DRAM_LC.LC14": "LC8",
        "DRAM_LC.LC15": "LC17",
        "DRAM_LC.LC9": "LC18",
    }
    mapping_exact = all(
        node_to_resource.get(node) == resource
        for node, resource in required_mapping.items()
    )
    final_json = json.loads(FINAL_JSON_PATH.read_text(encoding="utf-8"))
    final_chain = {
        key: final_json["dram_loop_configs"][key]
        for key in ("LC13", "LC14", "LC15", "LC9")
    }
    logical_chain_enabled = (
        final_chain["LC13"]["outmost_loop"] == 1
        and final_chain["LC14"]["src_id"] == "DRAM_LC.LC13"
        and final_chain["LC15"]["src_id"] == "DRAM_LC.LC14"
        and final_chain["LC9"]["src_id"] == "DRAM_LC.LC15"
    )
    bitstream_bound = (
        sha256_bytes(source.get(BITSTREAM_MEMBER, b"")) == BITSTREAM_SHA
    )
    if not (mapping_exact and logical_chain_enabled and bitstream_bound):
        errors.append("final mapping/bitstream logical-chain proof differs")

    formal_expected = int(gate.get("formal_d_expected", 320))
    formal_present = int(gate.get("formal_d_present", 0))
    formal_missing = int(gate.get("formal_d_missing", formal_expected))
    formal_mismatch = int(gate.get("formal_d_mismatch", 0))
    natural = gate.get("natural_terminal_observed") is True
    joint = (
        compile_status == 0
        and run_status == 0
        and natural
        and formal_present == formal_expected
        and formal_missing == 0
        and formal_mismatch == 0
        and formal_feature_binding
    )
    cloud = manifest.get("cloud_rtl_authority", {})
    cloud_bound = (
        cloud.get("approved_commit") == CLOUD_RTL
        and cloud.get("local_disk_commit") == CLOUD_RTL
        and cloud.get("identity_difference_blocks_compile_or_simulation") is False
    )

    report = {
        "schema": "node0004-v60-return-analysis-v1",
        "valid": not errors,
        "errors": errors,
        "RETURN_ANALYSIS": {
            "status": "PACKAGE_LOCAL_OBSERVER_MAPPING_AND_ARGV_RECEIPT_DEFECT",
            "return_zip": {
                "path": str(ret),
                "bytes": ret.stat().st_size,
                "sha256": ret_sha,
                "external_sidecar_required": False,
                "transport_policy": "USER_ATTESTED_NO_SIDECAR",
            },
            "source_zip": {
                "path": str(src),
                "bytes": src.stat().st_size,
                "sha256": src_sha,
                "sidecar_valid": sidecar_valid,
            },
            "return_meta": ret_meta,
            "source_meta": src_meta,
            "checks": {
                "crc_root_path": not ret_errors,
                "exact_set_allowlist_receipts": exact_return_set,
                "source_manifest_binding": source_bound,
                "source_exact_set": source_exact,
                "package_preflight": package_ok,
                "install_preflight_runtime_d_absent": install_ok,
                "ndp_root_toplevel_unchanged": root_ok,
                "observer_precompile": observer_ok,
                "compile_invoked": compile_invoked,
                "actual_time0_feature_enable_and_records": actual_time0_binding,
                "formal_diagnostic_feature_binding": formal_feature_binding,
                "simulator_argv_receipt_omits_actual_features":
                    argv_receipt_omits_features,
            },
            "compile_exit": compile_status,
            "run_exit": run_status,
            "signal": signal,
            "natural_terminal": natural,
            "formal_d_expected": formal_expected,
            "formal_d_present": formal_present,
            "formal_d_missing": formal_missing,
            "formal_d_mismatch": formal_mismatch,
            "joint_result_gate": joint,
            "E3": False,
            "E4": False,
            "E5": False,
        },
        "ACTUAL_RTL_IDENTITY": {
            "manifest_cloud_commit": cloud.get("approved_commit"),
            "cloud_identity_bound": cloud_bound,
            "production_compile_root_observed": compile_invoked,
            "separate_immutable_compile_commit_receipt": False,
            "difference_nonblocking_causal_risk": True,
        },
        "LAST_PROVEN_GOOD": (
            "V60_INSTALL_ONLY_LAYOUT_COMPILE_SIM_AND_QUALIFIED_D_WRITE_PROGRESS"
        ),
        "FIRST_DIVERGENCE": (
            "PACKAGE_OBSERVER_LOGICAL_LC_ID_TO_PHYSICAL_RESOURCE_INDEX_BINDING"
        ),
        "HANG_ROOT_CAUSE": {
            "status": "PACKAGE_LOCAL_DIAGNOSTIC_ROOT_CAUSE_UNIQUE",
            "classification": "OBSERVER_LOGICAL_TO_PHYSICAL_LC_MAPPING_BUG",
            "mechanism": (
                "The v51/v60 LC13_LC14 observer indexed physical IGA_LC[13], "
                "[14], and [15] as though they were logical DRAM_LC.LC13, "
                "LC14, and LC15. Final mapper placement is LC13->LC6, "
                "LC14->LC8, LC15->LC17, LC9->LC18. Physical LC14/15 are "
                "unmapped and disabled, so their zero runtime configs are "
                "expected and cannot localize the logical chain."
            ),
            "independent_package_receipt_defect": (
                "PREPARE_AND_RUN records only the base simv argv before the "
                "actual command adds every diagnostic plusarg. Time-zero "
                "markers prove runtime enable, but the formal argv binding "
                "gate correctly fails."
            ),
            "mapping_proof": {
                "path": str(MAPPING_PATH),
                "sha256": sha256_file(MAPPING_PATH),
                "logical_to_physical": required_mapping,
                "exact": mapping_exact,
            },
            "final_json_proof": {
                "path": str(FINAL_JSON_PATH),
                "sha256": sha256_file(FINAL_JSON_PATH),
                "logical_chain": final_chain,
                "enabled_and_connected": logical_chain_enabled,
            },
            "frozen_bitstream": {
                "member": BITSTREAM_MEMBER,
                "sha256": BITSTREAM_SHA,
                "bound": bitstream_bound,
            },
            "functional_rtl_root_cause_proven": False,
            "configuration_root_cause_proven": False,
            "successor_requirement": (
                "Observe physical LC6->LC8->LC17->LC18 and record the exact "
                "actual simulation argv. No DUT/config/numeric change."
            ),
        },
        "QUALIFIED_COUNTERS": {
            "canonical": canonical,
            "dterm_owner": dterm,
            "wrong_physical_lc13_lc14": lc_chain_wrong,
            "dynamic_checks": dynamic,
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_CONV_NODE0004_V60_RUNTIME_INSTALL_LAYOUT",
                "B_CONV_NODE0004_V60_PRODUCTION_COMPILE_AND_SIM_START",
            ],
            "invalidated": [
                "B_CONV_NODE0004_LC13_TO_LC14_TERMINAL_RELEASE_UNOBSERVED"
                "_AS_PHYSICAL_13_14_15",
            ],
            "opened": [
                "B_CONV_NODE0004_LOGICAL_LC13_LC14_LC15_LC9_PHYSICAL_CHAIN"
                "_UNOBSERVED",
                "B_CONV_NODE0004_SIMULATOR_ARGV_FEATURE_RECEIPT_INCOMPLETE",
            ],
            "preserved": [
                "B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL",
                "B_CONV_NODE0004_FORMAL_D_320",
            ],
            "invalidated_not_reopened": (
                "B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED"
            ),
        },
        "RULE_CONFIRMATION": {
            "status": "CURRENT_RULES_CAUGHT_ARGV_RECEIPT_DEFECT",
            "evidence": (
                "The current end-to-end diagnostic feature rule failed the "
                "incomplete argv receipt. Existing mapping/consumer ownership "
                "rules require mapper physical resource identity before XMR."
            ),
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
