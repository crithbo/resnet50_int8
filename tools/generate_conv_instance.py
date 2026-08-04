from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from resnet50_pipeline.conv_instance import make_conv_target_request
from resnet50_pipeline.conv_sa_contract import (
    SA_CHANNEL_LANES,
    SA_OUTPUT_LANES,
    SA_SPATIAL_LANES,
    ceil_div,
    validate_conv_3x3_sa_contract,
)
from generate_conv_1x1_real import build_real_1x1
from generate_conv_3x3_real import build_real_3x3
from generate_conv_1x1_requant_real import build_bundle


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "conv_full.json"
BASE_SEMANTICS_PATH = ROOT / "contracts" / "conv_1x1_lc_pe_stream_semantics.json"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _semantic_contract(
    base: dict[str, Any],
    *,
    request,
    config: dict[str, Any],
    config_bytes: bytes,
    encoder_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    spec = request.spec
    contract = deepcopy(base)
    contract["transport_abi"] = "conv_sa_legacy_v1"
    contract["status"] = (
        "official_encoder_passed_high4_selector_resolved_adapter_semantics_candidate"
        if encoder_evidence is not None
        else "candidate_pending_official_encoder"
    )
    contract["instance"] = {
        "node_id": spec.node_id,
        "hw_op_ids": [spec.accumulate_hw_op_id, spec.requant_hw_op_id],
        "activation_shape": list(spec.activation_shape),
        "weight_shape": list(spec.weight_shape),
        "output_shape": list(spec.output_shape),
        "strides": list(spec.strides),
        "pads": list(spec.pads),
        "dilations": list(spec.dilations),
        "group": spec.group,
        "static_json_scope": (
            "one-sample accumulation microprogram; batch-16 and seven HIGH-4 "
            "groups are request-adapter scheduling"
        ),
    }
    loops = config["dram_loop_configs"]
    for item in contract["lc_semantics"]:
        loop = loops[item["lc"]]
        item["range"] = [loop["start"], loop["end"], loop["stride"]]
    streams = config["stream_engine"]
    for item in contract["stream_semantics"]:
        stream = streams[item["stream"]]
        item["byte_stride"] = stream["dim_stride"]
        if item["tail"] is not None:
            bounds = stream["idx_tailing_range"]
            axis = item["tail"]["axis"]
            item["tail"] = {
                "axis": axis,
                "inclusive_valid_range": [
                    next(value for value in bounds["low"] if value is not None),
                    next(value for value in bounds["up"] if value is not None),
                ],
            }
    contract["config"] = {
        "path": request.accumulate_config_relative,
        "sha256": _sha256(config_bytes),
        "generator": "tools/generate_conv_instance.py",
        "source": "conv_full.json",
    }
    if encoder_evidence is None:
        contract["official_encoder"] = {
            "repository_commit": "e299b2804448242d1589b3e58ed7c5a9a5eca09f",
            "status": "pending",
            "connection_count": 46,
        }
    else:
        contract["official_encoder"] = encoder_evidence
    contract["evidence_boundaries"]["not_proven"] = [
        "exact hardware execution and P/D dump for this candidate",
        "cycle-accurate LC/stream/buffer interpretation of the encoded bitstream",
        "execplan typed qparam transport",
    ]
    return contract


def _semantic_contract_3x3(
    *,
    request,
    config: dict[str, Any],
    config_bytes: bytes,
    encoder_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    spec = request.spec
    c_quartets = ceil_div(spec.c_tile, SA_CHANNEL_LANES)
    k_blocks = ceil_div(spec.k_tile, SA_OUTPUT_LANES)
    q_blocks = spec.output_width // SA_SPATIAL_LANES
    halo_height = spec.activation_shape[2] + spec.pads[0] + spec.pads[2]
    halo_width = spec.activation_shape[3] + spec.pads[1] + spec.pads[3]
    halo_width_padded = ceil_div(halo_width, SA_SPATIAL_LANES) * SA_SPATIAL_LANES
    static_report = validate_conv_3x3_sa_contract(
        config,
        output_height=spec.output_height,
        output_width=spec.output_width,
        c_quartets=c_quartets,
        k_blocks=k_blocks,
        halo_width_padded=halo_width_padded,
    )
    contract: dict[str, Any] = {
        "schema_version": "resnet50-conv-3x3-semantics-0.1",
        "status": (
            "official_encoder_double_run_bound_candidate"
            if encoder_evidence is not None
            else "candidate_pending_official_encoder"
        ),
        "transport_abi": "conv_sa_q8k8_v2",
        "instance": {
            "node_id": spec.node_id,
            "hw_op_ids": [spec.accumulate_hw_op_id, spec.requant_hw_op_id],
            "activation_shape": list(spec.activation_shape),
            "weight_shape": list(spec.weight_shape),
            "output_shape": list(spec.output_shape),
            "strides": list(spec.strides),
            "pads": list(spec.pads),
            "dilations": list(spec.dilations),
            "group": spec.group,
            "static_json_scope": (
                "one-storage-sample 3x3 accumulation microprogram; batch16 uses "
                "three typed waves over seven HIGH-4 groups"
            ),
            "runtime_batch_schedule": {
                "storage_sample_count": 3,
                "logical_sample_counts_by_group": [3, 3, 2, 2, 2, 2, 2],
                "accumulate_wave_count": 3,
                "logical_samples_by_wave": [
                    [0, 3, 6, 8, 10, 12, 14],
                    [1, 4, 7, 9, 11, 13, 15],
                    [2, 5],
                ],
            },
        },
        "port_semantics": {
            "A": {
                "logical_role": "activation_uint8",
                "physical_role": "explicit_pad1_halo_q8c4",
                "dtype": "uint8",
                "padding_value": "x_zero_point",
            },
            "B": {
                "logical_role": "weight_int8",
                "physical_role": "RS_PREVring_Cquartet_Kblock_K8_C4",
                "dtype": "int8",
            },
            "C": {
                "logical_role": "bias_int32",
                "physical_role": "Kblock_K8",
                "dtype": "int32",
            },
            "D": {
                "logical_role": "accumulator_P",
                "physical_role": "NH_Qblock_Q8_Kblock_K8",
                "dtype": "int32",
            },
        },
        "activation_halo": {
            "status": "explicitly_staged_before_accumulate",
            "logical_shape": [
                3,
                spec.activation_shape[2],
                spec.activation_shape[3],
                spec.c_tile,
            ],
            "physical_shape": [
                3,
                halo_height,
                c_quartets,
                halo_width_padded,
                SA_CHANNEL_LANES,
            ],
            "axis_order": "N-HaloH-Cquartet-HaloW-C4",
            "halo_extent": [halo_height, halo_width],
            "padded_extent": [halo_height, halo_width_padded],
            "fill": "x_zero_point",
            "dynamic_stream_padding": False,
            "reason": (
                "kernel-s shifted Q8 windows remain contiguous complete 32-byte "
                "transactions without partial four-byte lane masking"
            ),
        },
        "loop_semantics": {
            "LC0": "k_block",
            "LC1": "output_h",
            "LC2": "output_q_block",
            "LC4": "kernel_r",
            "LC5": "kernel_s",
            "LC3": "local_activation_c_quartet",
            "LC6": "HIGH_PREV_ring_step",
            "LC7": "local_weight_c_quartet",
            "LC13_LC14_LC15_LC9": "value-identical_P_write_branch",
            "LC10_LC11_LC12": "per-output-tile_bias_branch",
            "LC8": "unused",
        },
        "lc_pe_semantics": {
            "PE0": "LC2*8+LC5",
            "PE1": "LC1+LC4",
            "PE2": f"LC6*{c_quartets}+LC7",
            "PE3": "LC4*3+LC5",
            "PE4": "LC15*8+LC9",
        },
        "stream_semantics": {
            name: {
                "target": stream["target"],
                "mode": stream["mode"],
                "idx": stream["idx"],
                "idx_size_minus_one": stream["idx_size"],
                "byte_stride": stream["dim_stride"],
                "transaction_bytes": static_report["stream_transaction_bytes"][name],
                "dynamic_padding": False,
            }
            for name, stream in sorted(config["stream_engine"].items())
        },
        "ring_semantics": {
            "domain": "HIGH-4",
            "neighbor_stream": 0,
            "mem_loop": 4,
            "src_slice_sel": 1,
            "dst_slice_sel": 1,
            "activation_order": "destination-relative PREV traversal",
            "weight_order": "prepacked in the same destination-relative PREV order",
        },
        "bias_runtime_contract": {
            "schedule": "one_32B_K8_row_per_Kblock_H_Qblock_tile",
            "transaction_count": static_report["bias_transaction_count"],
            "unique_address_count": static_report["bias_unique_address_count"],
            "sa_handshakes_per_tile": static_report["bias_handshakes_per_tile"],
        },
        "config": {
            "path": request.accumulate_config_relative,
            "sha256": _sha256(config_bytes),
            "generator": "tools/generate_conv_instance.py",
            "source": "conv_full.json",
        },
        "official_encoder": (
            encoder_evidence
            if encoder_evidence is not None
            else {
                "repository_commit": "e299b2804448242d1589b3e58ed7c5a9a5eca09f",
                "status": "pending",
            }
        ),
        "evidence_boundaries": {
            "proven": [
                "typed node-0005 geometry and parameter identity",
                "32-byte A/B/C/D stream transactions",
                "explicit halo physical packing and reversible logical inverse",
                "HIGH-4 selector and buffer ownership",
            ],
            "not_proven": [
                "cycle-accurate target execution",
                "server RTL P/D equality until returned dump is audited",
                "G6/G8 hardware approval",
            ],
        },
    }
    return contract


def build_instance_files(project_root: Path, node_id: str) -> dict[Path, bytes]:
    root = project_root.resolve()
    request = make_conv_target_request(root, node_id)
    if request.spec.node_id == "node-0004":
        raise ValueError("the frozen first instance must use its dedicated generators")
    source = _load(root / "conv_full.json")
    if (
        request.spec.kernel == (1, 1)
        and request.spec.strides == (1, 1)
        and request.spec.pads == (0, 0, 0, 0)
    ):
        config = build_real_1x1(source, request.spec)
        semantic_builder = _semantic_contract
    elif (
        request.spec.kernel == (3, 3)
        and request.spec.strides == (1, 1)
        and request.spec.pads == (1, 1, 1, 1)
        and request.spec.dilations == (1, 1)
    ):
        config = build_real_3x3(source, request.spec)
        semantic_builder = _semantic_contract_3x3
    else:
        raise ValueError(
            "typed Conv generator supports only reviewed 1x1/pad0 or 3x3/pad1 instances"
        )
    config_bytes = _canonical(config)
    evidence_path = (
        root
        / Path(request.accumulate_config_relative).parent
        / "encoder_evidence.json"
    )
    encoder_evidence = _load(evidence_path) if evidence_path.is_file() else None
    if semantic_builder is _semantic_contract:
        semantics = _semantic_contract(
            _load(root / "contracts" / "conv_1x1_lc_pe_stream_semantics.json"),
            request=request,
            config=config,
            config_bytes=config_bytes,
            encoder_evidence=encoder_evidence,
        )
    else:
        semantics = _semantic_contract_3x3(
            request=request,
            config=config,
            config_bytes=config_bytes,
            encoder_evidence=encoder_evidence,
        )
    _manifest, requant_files = build_bundle(
        request.spec,
        config_root_relative=request.requant_root_relative,
    )
    files = {
        root / request.accumulate_config_relative: config_bytes,
        root / request.semantic_contract_relative: _canonical(semantics),
    }
    files.update(
        {request.requant_root / name: payload for name, payload in requant_files.items()}
    )
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one typed real 1x1 Conv instance")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = build_instance_files(ROOT, args.node_id)
    for path, payload in files.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != payload:
                raise SystemExit(f"generated Conv instance differs: {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
