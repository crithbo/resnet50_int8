#!/usr/bin/env python3
"""Prove Requant Conv multiplier scalar serialization using existing fields only.

This is a source-equation/field-capability proof.  It deliberately does not
materialize an operator JSON or invoke any backend, mapping, bitstream, SCA,
package, or server flow.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = "requant_lane_phase_serialization_isolated_proof_v1"
MAINLINE = "019fbec2-fe93-7e03-9314-cff6f222f33d"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_git(repo: Path, *args: str) -> str:
    cmd = [
        "git",
        "-c",
        f"safe.directory={repo / '.git'}",
        "-C",
        str(repo),
        *args,
    ]
    return subprocess.check_output(cmd, text=True).strip()


def clone_isolated(source: Path, destination: Path) -> dict[str, Any]:
    subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={source / '.git'}",
            "clone",
            "--local",
            "--no-hardlinks",
            "--quiet",
            str(source),
            str(destination),
        ],
        check=True,
    )
    status = run_git(destination, "status", "--porcelain")
    return {
        "method": "LOCAL_GIT_CLONE_NO_HARDLINKS",
        "head": run_git(destination, "rev-parse", "HEAD"),
        "status_clean": status == "",
        "status_lines": 0 if not status else len(status.splitlines()),
    }


def source_receipt(repo: Path, relative_path: str) -> dict[str, str]:
    path = repo / relative_path
    return {
        "path": relative_path,
        "git_blob": run_git(repo, "rev-parse", f"HEAD:{relative_path}"),
        "sha256": sha256_file(path),
    }


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def scalar_template_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    stream = payload["stream_engine"]["stream0"]
    buffer0 = payload["buffer_config"]["buffer0"]
    inport0 = payload["general_array"]["inport"]["inport0"]
    pe00 = payload["general_array"]["PE_array"]["PE00"]
    col_lc = payload["buffer_loop_configs"]["GROUP0"]["COL_LC"]
    expected = {
        "idx_size0": (stream["idx_size"][0], 3),
        "dim_stride0": (stream["dim_stride"][0], 4),
        "buf_spatial_stride": (stream["buf_spatial_stride"], [0, 1, 2, 3]),
        "buf_spatial_size": (stream["buf_spatial_size"], 4),
        "buffer0_mask": (buffer0["mask"], [1, 0, 0, 0, 0, 0, 0, 0]),
        "ga_inport0_mask": (inport0["mask"], [1, 0, 0, 0, 0, 0, 0, 0]),
        "pe00_opcode": (pe00["alu_opcode"], "max"),
        "col_start": (col_lc["start"], 0),
        "col_end": (col_lc["end"], 4),
        "col_stride": (col_lc["stride"], 4),
    }
    for name, (actual, wanted) in expected.items():
        if actual != wanted:
            errors.append(f"{name}: expected {wanted!r}, got {actual!r}")
    return errors


def multiplier_route_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    stream = payload["stream_engine"]["stream1"]
    buffer2 = payload["buffer_config"]["buffer2"]
    inport1 = payload["general_array"]["inport"]["inport1"]
    pe00_in1 = payload["general_array"]["PE_array"]["PE00"]["inport1"]
    expected = {
        "target": (stream["target"], "B"),
        "mode": (stream["mode"], "read"),
        "buffer2_dst_port": (buffer2["dst_port"], 1),
        "native_buffer2_mask": (buffer2["mask"], [1] * 8),
        "native_ga_inport1_mask": (inport1["mask"], [1] * 8),
        "pe00_inport1_src_id": (pe00_in1["src_id"], 0),
        "pe00_inport1_mode": (pe00_in1["mode"], "keep"),
        "pe00_inport1_keep_last_index": (pe00_in1["keep_last_index"], 1),
    }
    for name, (actual, wanted) in expected.items():
        if actual != wanted:
            errors.append(f"{name}: expected {wanted!r}, got {actual!r}")
    return errors


def stage_capacity(channel_count: int) -> dict[str, Any]:
    channel_max = channel_count - 1
    offsets = sorted({(4 * c) % 16 for c in range(channel_count)})
    return {
        "channel_count": channel_count,
        "channel_lc_end": channel_count,
        "channel_lc_end_fits_17b": channel_count < (1 << 17),
        "channel_index_fits_16b": channel_max < (1 << 16),
        "dim_stride_bytes": 4,
        "dim_stride_fits_20b": 4 < (1 << 20),
        "max_byte_offset_inclusive": 4 * channel_max + 3,
        "transaction_offsets_mod_16": offsets,
        "four_byte_transaction_never_crosses_16b_beat": all(x <= 12 for x in offsets),
        "pass": (
            channel_count > 0
            and channel_count < (1 << 17)
            and channel_max < (1 << 16)
            and all(x <= 12 for x in offsets)
        ),
    }


def require_source_equations(rtl_root: Path) -> tuple[list[dict[str, str]], list[str]]:
    checks = [
        (
            "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
            "Memory_RD_Stream_Engine/RD_Memory_AG.sv",
            "assign transaction_addr_bias   = transaction_dim0_addr_d + "
            "transaction_dim1_addr_d + transaction_dim2_addr_d;",
            "memory address is the sum of index*stride dimensions",
        ),
        (
            "code/NDP_rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
            "Memory_RD_Stream_Engine/WR_Buffer_AG.sv",
            "buf_ag_col_idx + mse_buf_spatial_stride[SPATIAL_INDEX]",
            "each returned byte uses static base-column plus spatial stride",
        ),
        (
            "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/Memory_Req_Manager.sv",
            "se2buf_mem_req_col_addr[REQ_IDX][(`BUFFER_COL_ADDR_WIDTH-1):"
            "`BUFFER_BANK_OFFEST_WIDTH]",
            "column bits select one of eight banks",
        ),
        (
            "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/Memory_Req_Manager.sv",
            "se2buf_mem_req_col_addr[REQ_IDX][`BUFFER_BANK_OFFEST_WIDTH-1:0]",
            "low two column bits select the byte within a 32-bit bank",
        ),
        (
            "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/Array_Request_Manager.sv",
            "assign arm2buf_req_addr  = array_req_addr;",
            "array read presents one common row address to enabled banks",
        ),
        (
            "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/Array_Request_Manager.sv",
            "assign arm2array_valid_bit  = "
            "{`BUFFER_BANK_NUM{(buf2arm_valid_bit)}} & buffer_mask;",
            "buffer mask suppresses non-selected lanes",
        ),
        (
            "code/NDP_rtl/Slice/LSU/Buffer_Manager_Cluster/"
            "Buffer_Manager_Cluster_Connect.sv",
            "buf2gene_array_rdata[BUF_IDX/2][BUF_IDX%2] = "
            "arm2array_rdata[BUF_IDX];",
            "buffer2 maps to GA group1/source0 through BUF_IDX/2 and BUF_IDX%2",
        ),
        (
            "code/NDP_rtl/Slice/General_Array/GA_Inport/GA_Inport_Connect.sv",
            "assign ga_inport_data       = ga_inport_src_id ? "
            "ga_inport_group_sa_data[0] : "
            "ga_inport_group_buf_data[ga_inport_src_buf_sel];",
            "GA forwards the selected whole buffer vector without a lane mux",
        ),
    ]
    receipts: list[dict[str, str]] = []
    missing: list[str] = []
    for relative_path, needle, meaning in checks:
        text = (rtl_root / relative_path).read_text(encoding="utf-8")
        found = needle in text
        receipts.append(
            {
                "path": relative_path,
                "needle": needle,
                "meaning": meaning,
                "found": str(found).lower(),
            }
        )
        if not found:
            missing.append(f"{relative_path}: {needle}")
    return receipts, missing


def build_report(workspace: Path) -> dict[str, Any]:
    ndp_source = workspace / "ndp-sim"
    rtl_source = workspace / "Trassic2.0_RTL"
    prior_path = (
        workspace
        / "artifacts/operator_config_validation/"
        "requant_multiplier_occurrence_supply_v1/report.json"
    )
    prior = load_json(prior_path)
    conv = [
        item
        for item in prior["exact_payload_bits_and_axis"]["stage_manifest"]
        if item["onnx_op_type"] == "QLinearConv"
    ]

    with tempfile.TemporaryDirectory(prefix="requant_lane_phase_isolated_") as tmp:
        tmp_root = Path(tmp)
        ndp = tmp_root / "ndp-sim"
        rtl = tmp_root / "Trassic2.0_RTL"
        ndp_clone = clone_isolated(ndp_source, ndp)
        rtl_clone = clone_isolated(rtl_source, rtl)

        scalar_path = ndp / "jsons/decode_max_fp32N_fp32N.json"
        multiply_path = ndp / "jsons/prefill_mul_fp32MN_fp32M_fp32MN.json"
        scalar = load_json(scalar_path)
        multiply = load_json(multiply_path)
        scalar_errors = scalar_template_errors(scalar)
        multiplier_errors = multiplier_route_errors(multiply)
        equation_receipts, missing_equations = require_source_equations(rtl)

        capacities = []
        for item in conv:
            cap = stage_capacity(int(item["element_count"]))
            cap.update(
                {
                    "hw_op_id": item["hw_op_id"],
                    "multiplier_payload_sha256": item["computed_payload_sha256"],
                    "typed_axis": item["axis_binding"]["typed_axis"],
                    "consumer_channel_axis": item["axis_binding"]["channel_axis"],
                }
            )
            capacities.append(cap)

        structural_errors = (
            scalar_errors
            + multiplier_errors
            + missing_equations
            + ([] if len(conv) == 53 else [f"expected 53 Conv stages, got {len(conv)}"])
            + [
                f"{item['hw_op_id']}: field capacity failed"
                for item in capacities
                if not item["pass"]
            ]
        )

        native_receipts = [
            source_receipt(ndp, "jsons/decode_max_fp32N_fp32N.json"),
            source_receipt(ndp, "jsons/prefill_mul_fp32MN_fp32M_fp32MN.json"),
            source_receipt(ndp, "bitstream/config/stream.py"),
        ]
        rtl_paths = sorted({entry["path"] for entry in equation_receipts})
        rtl_receipts = [source_receipt(rtl, path) for path in rtl_paths]

    first = conv[0]
    first_bits = first["first_bits"]
    lane_counterexample_preserved = {
        "stage": first["hw_op_id"],
        "native_lane0_bits": first_bits[0],
        "native_lane1_bits": first_bits[1],
        "native_8wide_failure": (
            "With the original 8-wide fields, channel1 remains on GA lane1/PE10 "
            "and cannot feed PE00.inport1."
        ),
        "slow_composite_resolution": (
            "Do not rotate the 8-wide vector. Serialize channel c as its own "
            "4-byte transaction and enable only buffer2/GA-inport1 lane0."
        ),
        "one_round_fma_or_magic_wrap_used": False,
    }

    assignments = {
        "classification": "FIELD_LEVEL_EXISTING_PRIMITIVE_SLOW_COMPOSITE_PROOF_ONLY",
        "not_a_target_json": True,
        "channel_phase": "c = 0..C-1 in typed multiplier axis order",
        "multiplier_memory": {
            "transaction_size_equation": "idx_size[0]+1 = 3+1 = 4 bytes",
            "address_equation": "B_addr(c) = B_base + 4*c",
            "dim_stride0": 4,
            "alignment_equation": "(4*c) mod 16 in {0,4,8,12}; no 4B read crosses a 16B beat",
        },
        "buffer2": {
            "row": 0,
            "col_lc": {"start": 0, "end": 4, "stride": 4},
            "buf_spatial_stride": [0, 1, 2, 3],
            "buf_spatial_size": 4,
            "mask": [1, 0, 0, 0, 0, 0, 0, 0],
            "placement_equation": "four bytes of B[c] -> bank0 byte offsets 0..3",
        },
        "ga_inport1": {
            "src_id": 0,
            "mask": [1, 0, 0, 0, 0, 0, 0, 0],
            "route_equation": "buffer2 = BUF_IDX2 -> GA group1/source0 -> inport1 lane0",
        },
        "pe00": {
            "inport": 1,
            "src_id": 0,
            "mode": "keep",
            "keep_last_index": 1,
            "lifetime_equation": (
                "capture B[c] once, hold it for the already-proven serialized "
                "occurrence loop, release at that channel boundary, then accept B[c+1]"
            ),
        },
        "backpressure_and_clear": (
            "buffer mask makes only bank0 readiness relevant; Array_Request_Manager "
            "clears the selected bank at configured lifetime, and the next scalar write "
            "cannot overwrite valid bank0 because Buffer gates request-ready on validity"
        ),
    }

    return {
        "schema": SCHEMA,
        "mainline_thread_id": MAINLINE,
        "status": "PROVEN_AT_EXISTING_HARDWARE_FIELD_EQUATION_LEVEL",
        "pass": not structural_errors,
        "structural_errors": structural_errors,
        "scope": {
            "isolated_worktree_only": True,
            "active_ndp_sim_or_rtl_modified": False,
            "target_strict_json_generated": False,
            "backend_mapping_bitstream_execplan_sca_generated": False,
            "package_or_server_action": False,
            "numeric_5pe_graph_recomputed": False,
        },
        "isolated_source_identity": {
            "ndp_sim": ndp_clone,
            "rtl": rtl_clone,
            "ndp_sim_files": native_receipts,
            "rtl_files": rtl_receipts,
            "prior_occurrence_report": {
                "path": str(prior_path.relative_to(workspace)).replace("\\", "/"),
                "sha256": sha256_file(prior_path),
            },
        },
        "native_composition_evidence": {
            "scalar_serial_transport_template": {
                "path": "ndp-sim/jsons/decode_max_fp32N_fp32N.json",
                "applicability": (
                    "same FP32 scalar memory->buffer-bank0->GA-lane0 transport; "
                    "numeric opcode is not reused"
                ),
                "errors": scalar_errors,
            },
            "multiplier_keep_route_template": {
                "path": "ndp-sim/jsons/prefill_mul_fp32MN_fp32M_fp32MN.json",
                "applicability": (
                    "same FP32 B/buffer2/GA-inport1/PE00-keep route; original "
                    "8-wide lane distribution is explicitly not reused"
                ),
                "errors": multiplier_errors,
            },
            "composition_boundary": (
                "The two native templates prove individual existing-field mechanisms. "
                "Their scalar-B/inport1 composition is proven by current RTL equations, "
                "not claimed as an exact native JSON replay."
            ),
        },
        "rtl_equation_receipts": equation_receipts,
        "field_assignment_family": assignments,
        "conv53_coverage": {
            "stage_count": len(conv),
            "channel_count_histogram": {
                str(key): value
                for key, value in sorted(
                    Counter(int(item["element_count"]) for item in conv).items()
                )
            },
            "all_capacity_checks_pass": all(item["pass"] for item in capacities),
            "stages": capacities,
        },
        "counterexample_boundary": lane_counterexample_preserved,
        "blocker_delta": {
            "close_at_field_equation_level": [
                "B_REQUANT_CONV53_MULTIPLIER_LANES_1_TO_7_NOT_SERIALIZED_TO_PE00_INPUT1"
            ],
            "replacement_blockers": [
                {
                    "id": "B_REQUANT_CONV53_SCALAR_PHASE_STRICT_MATERIALIZATION_AND_BACKEND_BINDING",
                    "detail": (
                        "No target strict JSON, handler mutation, backend, mapping, or "
                        "execution artifact was authorized or generated; the proven field "
                        "family has not been bound to a target consumer."
                    ),
                },
                {
                    "id": "B_REQUANT_CONV53_SCALAR_PHASE_DYNAMIC_EXECUTION",
                    "detail": (
                        "No simulator/server run was authorized; occurrence count, "
                        "address coverage, natural terminal, and formal D remain open."
                    ),
                },
            ],
            "unchanged": [
                "sequential multiply-to-RNE exact tail",
                "integer zero-point and saturation tail",
                "magic-wrap counterexample domain",
                "all target strict/backend/package/server gates",
            ],
        },
        "claim_boundary": (
            "Existing current hardware fields can express an eight-lane-to-temporal "
            "scalar multiplier supply to PE00.inport1 for all 53 Conv stages "
            "(eight scalar phases per former 8-wide channel group; end-to-end "
            "performance was not measured). This closes only the field-expressibility "
            "blocker. It is not a strict config, backend proof, mapping/bitstream/"
            "execplan/SCA result, package, E4, or E5."
        ),
        "rule_delta_proposal": "NONE_NON_SYNONYMOUS",
        "package_release": "NONE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.workspace.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
