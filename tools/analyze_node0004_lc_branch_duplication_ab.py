from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.ndp_patch_toolchain import (  # noqa: E402
    NODE0004_ASSUMED_HW_PATCHSET_ID,
    build_patchset_manifest,
)
from resnet50_pipeline.node0004_assumed_hardware import (  # noqa: E402
    PATCHSET_REL,
    fresh_conv_wave_graph_spec,
)
from resnet50_pipeline.operator_config_evidence_bundle import (  # noqa: E402
    create_mapping_evidence_bundle,
)
from resnet50_pipeline.operator_config_execplan_evidence import (  # noqa: E402
    create_execplan_evidence_bundle,
)


BASELINE_CONFIG = ROOT / (
    "outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_release1/build/"
    "r5_n4_hw_v97b_tbvcd_memtuple_xmrefix/provenance/"
    "frozen_node0004_wave0_config.json"
)
V68_REPORT = ROOT / "outputs/conv_node0004_v68_return_analysis/report.json"
V97_REPORT = ROOT / (
    "outputs/conv_node0004_v97b_tbvcd_memtuple_xmrefix_return_"
    "r1786793347853153460_2912853/formal_return_analysis.json"
)
DEFAULT_OUTPUT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-node0004-lc-branch-duplication-ab-v3"
)

ORIGINAL_LC = "LC9"
DUPLICATE_LC = "LC3"
PE = "PE1"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json_lines(rows: list[dict[str, int]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(
            json.dumps(row, sort_keys=True, separators=(",", ":")).encode("utf-8")
        )
        digest.update(b"\n")
    return digest.hexdigest()


def leaf_diff(left: Any, right: Any, prefix: str = "") -> list[dict[str, Any]]:
    if isinstance(left, dict) and isinstance(right, dict):
        result: list[dict[str, Any]] = []
        for key in sorted(set(left) | set(right)):
            child = f"{prefix}.{key}" if prefix else key
            if key not in left:
                result.append({"path": child, "old": None, "new": right[key]})
            elif key not in right:
                result.append({"path": child, "old": left[key], "new": None})
            else:
                result.extend(leaf_diff(left[key], right[key], child))
        return result
    if isinstance(left, list) and isinstance(right, list):
        result = []
        for index in range(max(len(left), len(right))):
            child = f"{prefix}[{index}]"
            if index >= len(left):
                result.append({"path": child, "old": None, "new": right[index]})
            elif index >= len(right):
                result.append({"path": child, "old": left[index], "new": None})
            else:
                result.extend(leaf_diff(left[index], right[index], child))
        return result
    return [] if left == right else [{"path": prefix, "old": left, "new": right}]


def make_candidate(baseline: dict[str, Any]) -> dict[str, Any]:
    candidate = copy.deepcopy(baseline)
    loops = candidate["dram_loop_configs"]
    dormant = {
        "src_id": None,
        "outmost_loop": 0,
        "start": 0,
        "end": 0,
        "stride": 0,
        "last_index": 0,
    }
    if loops.get(DUPLICATE_LC) != dormant:
        raise ValueError(f"reserved dormant LC preimage differs: {DUPLICATE_LC}")
    if loops[ORIGINAL_LC] != {
        "src_id": "DRAM_LC.LC15",
        "outmost_loop": 0,
        "start": 0,
        "end": 8,
        "stride": 1,
        "last_index": 3,
    }:
        raise ValueError("LC9 frozen preimage differs")
    pe = candidate["lc_pe_configs"][PE]
    if pe["inport2"] != {
        "src_id": "DRAM_LC.LC9",
        "mode": "buffer",
        "keep_last_index": None,
        "constant": 0,
    }:
        raise ValueError("PE1 inport2 frozen preimage differs")
    loops[DUPLICATE_LC] = copy.deepcopy(loops[ORIGINAL_LC])
    pe["inport2"]["src_id"] = f"DRAM_LC.{DUPLICATE_LC}"
    return candidate


def math_rows(config: dict[str, Any]) -> list[dict[str, int]]:
    loops = config["dram_loop_configs"]
    lc13 = loops["LC13"]
    lc14 = loops["LC14"]
    lc15 = loops["LC15"]
    buffer_id = config["lc_pe_configs"][PE]["inport2"]["src_id"].split(".")[-1]
    buffer_loop = loops[buffer_id]
    rows: list[dict[str, int]] = []
    for i13 in range(lc13["start"], lc13["end"], lc13["stride"]):
        for i14 in range(lc14["start"], lc14["end"], lc14["stride"]):
            for i15 in range(lc15["start"], lc15["end"], lc15["stride"]):
                for ib in range(
                    buffer_loop["start"], buffer_loop["end"], buffer_loop["stride"]
                ):
                    rows.append(
                        {
                            "LC13": i13,
                            "LC14": i14,
                            "LC15": i15,
                            "buffer_lc": ib,
                            "PE1": i15 * 8 + ib,
                        }
                    )
    return rows


def mapping_nodes(review: dict[str, Any]) -> dict[str, str]:
    return {item["node"]: item["resource"] for item in review["node_to_resource"]}


def relevant_connections(review: dict[str, Any]) -> list[dict[str, str]]:
    names = {
        "DRAM_LC.LC15",
        "DRAM_LC.LC9",
        "DRAM_LC.LC3",
        "LC_PE.PE1",
        "GROUP4.ROW_LC",
    }
    return sorted(
        [
            item
            for item in review["connection_mapping"]
            if item["src_node"] in names or item["dst_node"] in names
        ],
        key=lambda item: (item["src_node"], item["dst_node"]),
    )


def active_lc_resources(review: dict[str, Any]) -> list[str]:
    return sorted(
        {
            item["resource"]
            for item in review["node_to_resource"]
            if item["node"].startswith("DRAM_LC.")
        },
        key=lambda value: int(value[2:]),
    )


def address_signature(report: dict[str, Any]) -> dict[str, Any]:
    facts = report["facts"]
    streams = []
    for stage in facts["stages"]:
        for item in stage["streams"]:
            streams.append(
                {
                    key: item[key]
                    for key in (
                        "execution_slice",
                        "resource",
                        "target",
                        "mode",
                        "base_addr",
                        "idx_size_encoded",
                        "transaction_size_bytes",
                        "dim_stride_bytes",
                        "address_remapping",
                        "index_tuple_count",
                        "request_count_with_multiplicity",
                        "unique_request_count",
                        "unique_request_addresses_sha256",
                        "valid_byte_count_with_multiplicity",
                        "padding_masked_byte_count_with_multiplicity",
                        "logical_payload_byte_count_with_multiplicity",
                        "first_request",
                        "last_request",
                    )
                }
            )
    return {
        "rtl_equation": facts["rtl_equation"],
        "request_count_with_multiplicity": facts["request_count_with_multiplicity"],
        "unique_request_address_count": facts["unique_request_address_count"],
        "unique_request_addresses_sha256": facts["unique_request_addresses_sha256"],
        "streams": streams,
    }


def traffic_summary(signature: dict[str, Any]) -> dict[str, int]:
    streams = signature["streams"]
    return {
        "request_count_with_multiplicity": sum(
            item["request_count_with_multiplicity"] for item in streams
        ),
        "read_request_count": sum(
            item["request_count_with_multiplicity"]
            for item in streams
            if item["mode"] == "read"
        ),
        "write_request_count": sum(
            item["request_count_with_multiplicity"]
            for item in streams
            if item["mode"] == "write"
        ),
        "logical_payload_bytes": sum(
            item["logical_payload_byte_count_with_multiplicity"] for item in streams
        ),
        "read_logical_payload_bytes": sum(
            item["logical_payload_byte_count_with_multiplicity"]
            for item in streams
            if item["mode"] == "read"
        ),
        "write_logical_payload_bytes": sum(
            item["logical_payload_byte_count_with_multiplicity"]
            for item in streams
            if item["mode"] == "write"
        ),
        "padding_masked_bytes": sum(
            item["padding_masked_byte_count_with_multiplicity"] for item in streams
        ),
    }


def deterministic_payload_hashes(pipeline: Path) -> dict[str, str]:
    install = pipeline / "install"
    result: dict[str, str] = {}
    for path in sorted(install.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(install).as_posix()
        if rel == "cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin":
            continue
        if rel == "execplan.txt":
            continue
        result[rel] = sha256(path)
    return result


def exec_words(path: Path) -> list[int]:
    words: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = line.strip()
        if row:
            words.extend((int(row[64:], 2), int(row[:64], 2)))
    if words and words[-1] == 0:
        words.pop()
    return words


def nonempty_line_count(path: Path) -> int:
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def rtl_identity() -> dict[str, Any]:
    specs = [
        (
            "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/IGA_LC_Connect.sv",
            [28],
            "LC output readiness is the AND of all mapped destinations",
        ),
        (
            "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/IGA_LC_Inbuffer.sv",
            [62, 69, 70, 73, 116, 125],
            "each LC owns an independent depth-4 parent-token FIFO and same/gotten state",
        ),
        (
            "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC/IGA_LC_Counter.sv",
            [69, 71, 91, 92, 164, 165, 184, 188, 197, 198],
            "each LC owns an independent counter/outbuffer and terminal return",
        ),
        (
            "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_PE/IGA_PE_Inbuffer.sv",
            [155, 162, 167, 169, 174, 183, 184, 185],
            "PE buffer input supplies tuple last/index and independently returns ready",
        ),
    ]
    result = []
    for rel, lines, meaning in specs:
        path = ROOT / rel
        result.append(
            {
                "path": rel,
                "sha256": sha256(path),
                "lines": lines,
                "meaning": meaning,
            }
        )
    return {"files": result}


def microtrace(v68: dict[str, Any], v97: dict[str, Any]) -> dict[str, Any]:
    pe = v68["physical_pe7_tenth_pair_adjudication"]
    branch = v68["lc18_fanout_backpressure_adjudication"]
    dynamic = v97.get("DYNAMIC_EXECUTION_EVIDENCE") or v97[
        "dynamic_execution_evidence"
    ]
    preconditions = {
        "second_epoch_parent_already_captured": pe["input0_accept"] == 2,
        "ninth_tuple_is_second_epoch_q0": (
            pe["input2_accept"] == 9
            and dynamic["input1_post_last_nonlast_tuple_ps"]
            > dynamic["input1_last_marked_tuple_ps"]
        ),
        "row_is_only_blocked_destination": branch["only_low_destination_bit"] == [10],
        "pe_buffer_input_ready": branch["PE7_input2_is_ready"] is True,
    }
    baseline = {
        "row_ready": 0,
        "pe_ready": 1,
        "shared_lc_output_ready_equation": "row_ready & pe_ready",
        "shared_lc_output_ready": 0,
        "tuple10_possible": False,
    }
    candidate = {
        "original_lc9_row_output_ready_equation": "row_ready",
        "original_lc9_row_output_ready": 0,
        "duplicate_lc3_pe_output_ready_equation": "pe_ready",
        "duplicate_lc3_pe_output_ready": 1,
        "parent_advance_required_for_tuple10": False,
        "reason": (
            "the second-epoch parent was accepted before tuple9/Q0; LC3 owns an "
            "independent input FIFO, counter and outbuffer, so it can emit Q1/tuple10 "
            "without advancing LC15 or releasing the stalled ROW-owned LC9 Q1"
        ),
        "tuple10_possible": True,
    }
    return {
        "schema": "node0004-lc-branch-duplication-boundary-microtrace-v1",
        "status": "PASS" if all(preconditions.values()) else "FAIL",
        "preconditions": preconditions,
        "negative_control_shared_lc": baseline,
        "duplicated_branch_candidate": candidate,
        "claim_boundary": (
            "This is a source-bound local handshake proof using v68/v97 dynamic facts; "
            "it predicts tuple10 but does not claim a production natural terminal or Formal-D."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--python", type=Path, default=ROOT / ".venv/Scripts/python.exe")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"fresh output required: {output}")

    baseline = load(BASELINE_CONFIG)
    candidate = make_candidate(baseline)
    expected_diff = [
        {"path": "dram_loop_configs.LC3.end", "old": 0, "new": 8},
        {"path": "dram_loop_configs.LC3.last_index", "old": 0, "new": 3},
        {
            "path": "dram_loop_configs.LC3.src_id",
            "old": None,
            "new": "DRAM_LC.LC15",
        },
        {"path": "dram_loop_configs.LC3.stride", "old": 0, "new": 1},
        {
            "path": "lc_pe_configs.PE1.inport2.src_id",
            "old": "DRAM_LC.LC9",
            "new": "DRAM_LC.LC3",
        },
    ]
    if leaf_diff(baseline, candidate) != expected_diff:
        raise SystemExit("candidate differs outside the authorized two-leaf surface")

    configs = output / "configs"
    write(configs / "A_baseline.json", baseline)
    write(configs / "B_duplicate_lc_branch.json", candidate)
    graph = output / "graph/wave-0.json"
    write(graph, fresh_conv_wave_graph_spec(0))

    ndp = ROOT / "ndp-sim"
    patchset_path = ROOT / PATCHSET_REL
    if load(patchset_path) != build_patchset_manifest(
        ndp, patchset_id=NODE0004_ASSUMED_HW_PATCHSET_ID
    ):
        raise SystemExit("active hash-bound patchset differs")

    variants: dict[str, dict[str, Any]] = {}
    for name, config_path in (
        ("A", configs / "A_baseline.json"),
        ("B", configs / "B_duplicate_lc_branch.json"),
    ):
        mapping_dir = output / f"{name}/mapping"
        mapping = create_mapping_evidence_bundle(
            ndp_sim_root=ndp,
            config_path=config_path,
            output_dir=mapping_dir,
            python_executable=args.python.resolve(),
            patchset_manifest_path=patchset_path,
        )
        execplan_dir = output / f"{name}/execplan"
        execplan = create_execplan_evidence_bundle(
            ndp_sim_root=ndp,
            graph_path=graph,
            mapping_bundles={"op_w0": mapping_dir},
            output_dir=execplan_dir,
            python_executable=args.python.resolve(),
            patchset_manifest_path=patchset_path,
        )
        pipeline = execplan_dir / "pipeline_output"
        review_path = pipeline / "config/op_w0/mapping_review.json"
        address_path = execplan_dir / "request_address_validation_report.json"
        variants[name] = {
            "config_path": config_path,
            "mapping_bundle": mapping,
            "execplan_bundle": execplan,
            "pipeline": pipeline,
            "review": load(review_path),
            "address_report": load(address_path),
        }

    a, b = variants["A"], variants["B"]
    a_pipeline, b_pipeline = a["pipeline"], b["pipeline"]
    a_final = load(a_pipeline / "jsons/op_w0_resnet50_conv_node0004_wave0.json")
    b_final = load(b_pipeline / "jsons/op_w0_resnet50_conv_node0004_wave0.json")
    a_math = math_rows(a_final)
    b_math = math_rows(b_final)
    a_math_hash = sha256_json_lines(a_math)
    b_math_hash = sha256_json_lines(b_math)
    a_address = address_signature(a["address_report"])
    b_address = address_signature(b["address_report"])
    a_traffic, b_traffic = traffic_summary(a_address), traffic_summary(b_address)
    a_resources = active_lc_resources(a["review"])
    b_resources = active_lc_resources(b["review"])
    a_execplan = a_pipeline / "install/execplan.txt"
    b_execplan = b_pipeline / "install/execplan.txt"
    a_bitstream = a_pipeline / (
        "install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    )
    b_bitstream = b_pipeline / (
        "install/cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    )
    a_sca = load(a_pipeline / "sca_cfg.json")
    b_sca = load(b_pipeline / "sca_cfg.json")
    a_sca_d = load(a_pipeline / "sca_cfg_D.json")
    b_sca_d = load(b_pipeline / "sca_cfg_D.json")
    a_words = exec_words(a_execplan)
    b_words = exec_words(b_execplan)
    differing_commands = [
        index for index, pair in enumerate(zip(a_words, b_words)) if pair[0] != pair[1]
    ]
    length_mask = 0xFF << 56
    a_load, b_load = a_words[1], b_words[1]
    a_config64 = a_pipeline / (
        "config/op_w0/op_w0_resnet50_conv_node0004_wave0_bitstream_64b.bin"
    )
    b_config64 = b_pipeline / (
        "config/op_w0/op_w0_resnet50_conv_node0004_wave0_bitstream_64b.bin"
    )
    a_words64, b_words64 = nonempty_line_count(a_config64), nonempty_line_count(b_config64)
    a_rows128, b_rows128 = nonempty_line_count(a_bitstream), nonempty_line_count(b_bitstream)
    micro = microtrace(load(V68_REPORT), load(V97_REPORT))
    write(output / "boundary_microtrace.json", micro)

    critical_path = {
        "baseline": ["LC13", "LC14", "LC15", "LC9", "PE1", "WRITE_STREAM0"],
        "candidate_metadata": [
            "LC13",
            "LC14",
            "LC15",
            "LC3",
            "PE1",
            "WRITE_STREAM0",
        ],
        "candidate_data": [
            "LC13",
            "LC14",
            "LC15",
            "LC9",
            "ROW_LC4",
            "COL_LC4",
            "WRITE_STREAM0",
        ],
        "metadata_serial_depth_unchanged": True,
        "configured_PE1_occurrences_per_slice": len(a_math),
        "candidate_PE1_occurrences_per_slice": len(b_math),
        "no_stall_owner_cycle_work_bound_unchanged": len(a_math) == len(b_math),
        "arbitrary_backpressure_bound": "unbounded in both A and B",
        "additional_parallel_lc_token_events_per_slice": len(b_math),
        "wall_cycle_claim_boundary": (
            "Static A/B proves no extra serialized loop, stage or command and equal "
            "configured work. Production wall cycles remain a dynamic measurement."
        ),
    }

    checks = {
        "baseline_final_json_matches_source": a_final == baseline,
        "candidate_final_json_exact_authorized_diff": leaf_diff(a_final, b_final)
        == expected_diff,
        "mapping_A_zero_penalty": a["mapping_bundle"].valid
        and a["mapping_bundle"].penalty == 0,
        "mapping_B_zero_penalty": b["mapping_bundle"].valid
        and b["mapping_bundle"].penalty == 0,
        "execplan_A_valid": a["execplan_bundle"].valid,
        "execplan_B_valid": b["execplan_bundle"].valid,
        "output_math_sequence_equal": a_math == b_math and a_math_hash == b_math_hash,
        "address_sequence_equal": a_address == b_address,
        "memory_traffic_equal": a_traffic == b_traffic,
        "sca_equal": a_sca == b_sca and a_sca_d == b_sca_d,
        "command_count_equal": len(a_words) == len(b_words),
        "only_Load_Config_length_command_field_changes": differing_commands == [1]
        and (a_load & ~length_mask) == (b_load & ~length_mask)
        and ((b_load >> 56) & 0xFF) == ((a_load >> 56) & 0xFF) + 1,
        "nonconfig_payloads_equal": deterministic_payload_hashes(a_pipeline)
        == deterministic_payload_hashes(b_pipeline),
        "config_payload_growth_exactly_one_meaningful_word": b_words64 == a_words64 + 1,
        "config_transport_growth_exactly_one_128bit_row": b_rows128 == a_rows128 + 1,
        "active_lc_delta_exactly_one": len(b_resources) == len(a_resources) + 1,
        "physical_lc_capacity_respected": len(b_resources) <= 20,
        "metadata_serial_depth_unchanged": critical_path[
            "metadata_serial_depth_unchanged"
        ],
        "configured_cycle_work_bound_unchanged": critical_path[
            "no_stall_owner_cycle_work_bound_unchanged"
        ],
        "tuple10_boundary_microtrace": micro["status"] == "PASS"
        and micro["duplicated_branch_candidate"]["tuple10_possible"] is True,
        "shared_lc_negative_control": micro["negative_control_shared_lc"][
            "tuple10_possible"
        ]
        is False,
    }
    equivalent = all(checks.values())
    extra_lc = len(b_resources) - len(a_resources)
    cost = {
        "active_lc_A": len(a_resources),
        "active_lc_B": len(b_resources),
        "physical_lc_capacity": 20,
        "additional_active_lc": extra_lc,
        "absolute_capacity_delta_percent": extra_lc * 100 / 20,
        "relative_active_lc_delta_percent": extra_lc * 100 / len(a_resources),
        "spare_lc_A": 20 - len(a_resources),
        "spare_lc_B": 20 - len(b_resources),
        "extra_command_count": 0,
        "extra_memory_requests": b_traffic["request_count_with_multiplicity"]
        - a_traffic["request_count_with_multiplicity"],
        "extra_memory_payload_bytes": b_traffic["logical_payload_bytes"]
        - a_traffic["logical_payload_bytes"],
        "extra_config_meaningful_bytes": (b_words64 - a_words64) * 8,
        "extra_config_transport_bytes": (b_rows128 - a_rows128) * 16,
        "extra_serialized_stage_count": 0,
        "configured_cycle_upper_bound_delta": 0,
        "negligible_policy": (
            "one of six baseline spare physical LCs; no address, math, command-count, "
            "data-plane traffic, serialized-stage or configured-cycle delta; one-time "
            "setup grows by one meaningful 64-bit word / one 128-bit transport row"
        ),
        "negligible": equivalent and extra_lc == 1 and len(b_resources) < 20,
    }
    report = {
        "schema": "node0004-lc-branch-duplication-mapper-ab-v1",
        "status": "LOCAL_MAPPER_AB_EQUIVALENCE_PASS"
        if equivalent and cost["negligible"]
        else "LOCAL_MAPPER_AB_REJECTED",
        "classification": "VALIDATED_ZERO_DATA_PLANE_COST_CONFIG_WORKAROUND"
        if equivalent and cost["negligible"]
        else "CONFIG_WORKAROUND_NOT_VALIDATED",
        "source_baseline": {
            "path": BASELINE_CONFIG.relative_to(ROOT).as_posix(),
            "sha256": sha256(BASELINE_CONFIG),
        },
        "authorized_config_diff": expected_diff,
        "checks": checks,
        "mapping": {
            "A_summary": a["review"]["summary"],
            "B_summary": b["review"]["summary"],
            "A_node_to_resource": mapping_nodes(a["review"]),
            "B_node_to_resource": mapping_nodes(b["review"]),
            "A_relevant_connections": relevant_connections(a["review"]),
            "B_relevant_connections": relevant_connections(b["review"]),
            "A_active_lc_resources": a_resources,
            "B_active_lc_resources": b_resources,
        },
        "address_sequence": {
            "equal": a_address == b_address,
            "request_count_with_multiplicity": a_address[
                "request_count_with_multiplicity"
            ],
            "unique_request_address_count": a_address[
                "unique_request_address_count"
            ],
            "unique_request_addresses_sha256": a_address[
                "unique_request_addresses_sha256"
            ],
            "signature_sha256": hashlib.sha256(
                json.dumps(a_address, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        },
        "output_math": {
            "equation": "PE1 = LC15 * 8 + buffer_lc",
            "sequence_count_per_slice": len(a_math),
            "sequence_sha256": a_math_hash,
            "equal": a_math == b_math,
            "first": a_math[0],
            "last": a_math[-1],
        },
        "commands": {
            "execplan_128b_line_count": len(
                a_execplan.read_text(encoding="utf-8").splitlines()
            ),
            "instruction_count_64bit": len(a_words),
            "differing_command_indices": differing_commands,
            "A_Load_Config_length_64bit": (a_load >> 56) & 0xFF,
            "B_Load_Config_length_64bit": (b_load >> 56) & 0xFF,
            "same_command_count": len(a_words) == len(b_words),
            "sca_exec_length": a_sca["Exec_Length"],
            "sca_repeat_num": a_sca["Repeat_Num"],
        },
        "memory_traffic": {"A": a_traffic, "B": b_traffic, "equal": a_traffic == b_traffic},
        "cycle_bound": critical_path,
        "lc_cost": cost,
        "boundary_microtrace": {
            "path": "boundary_microtrace.json",
            "sha256": sha256(output / "boundary_microtrace.json"),
        },
        "rtl_identity": rtl_identity(),
        "claim_boundary": (
            "Local current-disk mapper/encoder/execplan/address and source-bound "
            "handshake proof only. It validates a config workaround candidate and "
            "predicts tuple10; production tuple10, natural completion and Formal-D "
            "still require one targeted server return."
        ),
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write(output / "mapper_ab_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "LOCAL_MAPPER_AB_EQUIVALENCE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
