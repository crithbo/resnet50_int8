from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .conv_native_package import build_strict_configs
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .node0004_assumed_hardware import (
    WAVE_SAMPLES,
    WAVE_SLICE_COUNTS,
    build_fresh_accumulate_base,
    build_tail_configs,
    load_fresh_w3_values,
    local_numeric_report,
)


SCHEMA = "resnet50-conv-native-four-lane-df23e4d-local-e2-v1"
TEST_ID = "r5_conv_native_four_lane_df23e4d_local_e2_v1"
NODE_ID = "node-0004"
REQUEST_ID = "r5:hwop-0004-00"
REQUEST_SHA256 = (
    "e27e10169168f3889df4c03bf15cb21de074abf3f3767dc4bee288425165874b"
)
RTL_COMMIT = "df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727"
RTL_LEAVES = {
    "SA_PE_Float_CSA.v": (
        "72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3"
    ),
    "SA_PE_Float_Control.v": (
        "00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb"
    ),
    "SA_PE_Mul_Array.v": (
        "135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a"
    ),
    "SA_ALU.v": (
        "c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06"
    ),
}

ARTIFACT_REL = Path(
    "artifacts/operator_config_validation/r5-conv-native-four-lane-df23e4d-v1"
)
CONFIG_REL = Path(
    "configs/native_ndp_sim/r5_conv_native_four_lane_df23e4d_v1"
)
CONTRACT_REL = Path(
    "contracts/operator_config/r5_conv_native_four_lane_df23e4d_local_e2_v1.json"
)
REVALIDATION_REL = Path(
    "outputs/conv_native_four_lane_df23e4d_revalidation/report.json"
)
RAW_REACHABILITY_REL = Path(
    "outputs/conv_native_four_lane_df23e4d_revalidation/"
    "all53_raw_reachability.json"
)
SERIALIZED_CONTRACT_REL = Path(
    "contracts/operator_config/"
    "r5_conv_node0004_serialized_one_product_local_e2_v1.json"
)
W3_ACCUMULATOR_REL = Path(
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0004-accumulate.npy"
)
W3_OUTPUT_REL = Path(
    "artifacts/w3/golden_batch16/tensors/"
    "tensor-ec3c4cd13e5f6a9e.npy"
)

RULE_PATHS = (
    Path(".agents/rules/生成前必读索引.md"),
    Path(".agents/rules/算子配置规则.md"),
    Path(".agents/rules/NDP硬件字段语义.md"),
    Path(".agents/rules/服务器测试包生成规则.md"),
    Path(".agents/rules/INT8_SA点积专项规则.md"),
    Path(".agents/rules/精确UINT8量化尾专项规则.md"),
)


class NativeFourLaneE2Error(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise NativeFourLaneE2Error(f"JSON root must be object: {path}")
    return value


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _s32(value: int) -> int:
    bits = int(value) & 0xFFFFFFFF
    return bits - (1 << 32) if bits & 0x80000000 else bits


def _read_128bit_payload(path: Path) -> bytes:
    lines = [
        line.strip()
        for line in path.read_text(encoding="ascii").splitlines()
        if line.strip()
    ]
    if not lines or any(
        len(line) != 128 or set(line) - {"0", "1"} for line in lines
    ):
        raise NativeFourLaneE2Error(f"invalid 128-bit payload: {path}")
    return b"".join(int(line, 2).to_bytes(16, "little") for line in lines)


def _first_mismatch(
    actual: np.ndarray, expected: np.ndarray
) -> dict[str, Any] | None:
    indices = np.argwhere(actual != expected)
    if not indices.size:
        return None
    index = tuple(int(item) for item in indices[0])
    return {
        "index": list(index),
        "actual": int(actual[index]),
        "expected": int(expected[index]),
    }


def native_dot4_holdouts() -> dict[str, Any]:
    cases = [
        ("positive", [3, 5, 7, 11, 13], [2, 4, 6, 8, 10], 0, 17),
        ("negative", [-3, 5, -7, 11, -13], [2, 4, 6, 8, 10], 0, -19),
        ("k_tail_1", [127], [255], 0, 0),
        ("k_tail_2", [127, -128], [255, 255], 0, 0),
        ("k_tail_3", [127, -128, 1], [255, 255, 1], 0, 0),
        ("nonzero_xzp", [-8, 3, 5, -2, 7], [9, 11, 13, 15, 17], 11, 23),
        ("bias_wrap", [127, 127], [255, 255], 0, 0x7FFFFFF0),
        ("signed18_min", [-128, -128, -128, -128], [255] * 4, 0, 0),
        ("signed18_max", [127, 127, 127, 127], [255] * 4, 0, 0),
        ("exact_cancel", [-1, 0, 0, 1], [21, 24, 24, 26], 0, -5),
    ]
    rows: list[dict[str, Any]] = []
    for case_id, weights, activations, x_zero_point, bias in cases:
        corrected = _s32(bias - x_zero_point * sum(weights))
        psum = corrected
        occurrences: list[dict[str, Any]] = []
        for offset in range(0, len(weights), 4):
            lane_w = list(weights[offset : offset + 4])
            lane_x = list(activations[offset : offset + 4])
            useful = len(lane_w)
            lane_w.extend([0] * (4 - useful))
            lane_x.extend([x_zero_point] * (4 - useful))
            dot4 = sum(w * x for w, x in zip(lane_w, lane_x, strict=True))
            next_psum = _s32(psum + dot4)
            occurrences.append(
                {
                    "k_group": offset // 4,
                    "weight_s8_lanes": lane_w,
                    "activation_u8_lanes": lane_x,
                    "useful_lane_count": useful,
                    "dot4": dot4,
                    "psum_in": psum,
                    "psum_out": next_psum,
                }
            )
            psum = next_psum
        target = _s32(
            bias
            + sum(
                w * (x - x_zero_point)
                for w, x in zip(weights, activations, strict=True)
            )
        )
        if psum != target:
            raise NativeFourLaneE2Error(f"native holdout differs: {case_id}")
        rows.append(
            {
                "case_id": case_id,
                "k": len(weights),
                "x_zero_point": x_zero_point,
                "bias_s32": _s32(bias),
                "corrected_initial_psum": corrected,
                "target_s32": target,
                "result_s32": psum,
                "occurrences": occurrences,
            }
        )
    by_id = {row["case_id"]: row for row in rows}
    if (
        by_id["signed18_min"]["occurrences"][0]["dot4"] != -130_560
        or by_id["signed18_max"]["occurrences"][0]["dot4"] != 129_540
        or by_id["exact_cancel"]["result_s32"] != 0
    ):
        raise NativeFourLaneE2Error("named native boundary differs")
    return {
        "packing": (
            "original K in consecutive groups of four; tail weight=0 and "
            "tail activation=x_zero_point"
        ),
        "initial_psum": "s32(bias-x_zero_point*sum(logical weights))",
        "recurrence": "s32(psum+sum4(s8_weight*u8_activation))",
        "cases": rows,
        "all_pass": True,
    }


def _config_semantics(root: Path) -> dict[str, Any]:
    config_root = root / CONFIG_REL
    manifest_path = config_root / "accumulate_waves/manifest.json"
    manifest = _load(manifest_path)
    records: list[dict[str, Any]] = []
    canonical: list[str] = []
    for wave in range(3):
        path = config_root / f"accumulate_waves/wave-{wave}.json"
        config = _load(path)
        loops = config["dram_loop_configs"]
        stream_by_target = {
            value["target"]: value
            for value in config["stream_engine"].values()
            if isinstance(value, dict) and value.get("target")
        }
        required_targets = {"A", "B", "B'", "C", "D"}
        if set(stream_by_target) != required_targets:
            raise NativeFourLaneE2Error("native Conv stream target closure differs")
        if (
            loops["LC4"]["end"] - loops["LC4"]["start"] != 4
            or loops["LC6"]["end"] - loops["LC6"]["start"] != 4
            or config["special_array"]["mode"] != "gemm"
            or config["special_array"]["data_type"] != "int8"
            or config["special_array"]["bias_enable"] != 1
            or stream_by_target["B"]["base_addr"]
            != stream_by_target["B'"]["base_addr"]
        ):
            raise NativeFourLaneE2Error("native four-lane config semantics differ")
        canonical_hash = sha256_bytes(canonical_json_bytes(config))
        canonical.append(canonical_hash)
        records.append(
            {
                "wave": wave,
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "canonical_sha256": canonical_hash,
                "active_slice_count": WAVE_SLICE_COUNTS[wave],
                "sample_ids": list(WAVE_SAMPLES[wave]),
                "reduction_groups_per_output": 16,
                "streams": {
                    target: {
                        "base_addr": stream_by_target[target]["base_addr"],
                        "idx_size": stream_by_target[target]["idx_size"],
                        "dim_stride": stream_by_target[target]["dim_stride"],
                    }
                    for target in sorted(required_targets)
                },
            }
        )

    base_first = build_fresh_accumulate_base(root)
    base_second = build_fresh_accumulate_base(root)
    if canonical_json_bytes(base_first) != canonical_json_bytes(base_second):
        raise NativeFourLaneE2Error("accumulate base double build differs")
    generated, generated_manifest = build_strict_configs(
        root,
        source_config_rel=(
            CONFIG_REL / "accumulate_base.json"
        ),
        reuse_wave_addresses=True,
    )
    generated_again, generated_manifest_again = build_strict_configs(
        root,
        source_config_rel=(
            CONFIG_REL / "accumulate_base.json"
        ),
        reuse_wave_addresses=True,
    )
    if (
        canonical_json_bytes(generated)
        != canonical_json_bytes(generated_again)
        or canonical_json_bytes(generated_manifest)
        != canonical_json_bytes(generated_manifest_again)
    ):
        raise NativeFourLaneE2Error("native wave double build differs")
    tail_first, tail_manifest_first = build_tail_configs(root)
    tail_second, tail_manifest_second = build_tail_configs(root)
    tail_first_serializable = {
        f"{kind}_w{wave}_s{shard:02d}": value
        for (kind, wave, shard), value in sorted(tail_first.items())
    }
    tail_second_serializable = {
        f"{kind}_w{wave}_s{shard:02d}": value
        for (kind, wave, shard), value in sorted(tail_second.items())
    }
    if (
        canonical_json_bytes(tail_first_serializable)
        != canonical_json_bytes(tail_second_serializable)
        or canonical_json_bytes(tail_manifest_first)
        != canonical_json_bytes(tail_manifest_second)
    ):
        raise NativeFourLaneE2Error("tail config double build differs")
    return {
        "manifest": {
            "path": manifest_path.relative_to(root).as_posix(),
            "sha256": sha256_file(manifest_path),
            "schema": manifest["schema"],
        },
        "records": records,
        "all_wave_canonical_hashes_equal": len(set(canonical)) == 1,
        "deterministic_double_build": {
            "accumulate_base_equal": True,
            "accumulate_waves_equal": True,
            "tail_48_configs_equal": True,
        },
    }


def _transport_simulation(root: Path) -> dict[str, Any]:
    transport_root = root / ARTIFACT_REL / "conv_transport"
    manifest_path = transport_root / "manifest.json"
    manifest = _load(manifest_path)
    records = manifest.get("records")
    if not isinstance(records, list) or len(records) != 64:
        raise NativeFourLaneE2Error("native transport record count differs")
    logical = np.empty((16, 64, 56, 56), dtype=np.int32)
    owners: set[tuple[int, int]] = set()
    payload_hash = hashlib.sha256()
    lane_product_nonzero = 0
    lane_product_total = 0
    first_corruption_detected = False
    for record in records:
        matrices: dict[str, Any] = record["matrices"]
        payloads: dict[str, bytes] = {}
        for role in ("A", "B", "C", "D"):
            item = matrices[role]
            path = transport_root / item["path"]
            if sha256_file(path) != item["sha256"]:
                raise NativeFourLaneE2Error(
                    f"transport receipt differs: {item['path']}"
                )
            payload = _read_128bit_payload(path)
            if len(payload) != item["payload_bytes"]:
                raise NativeFourLaneE2Error(
                    f"transport payload length differs: {item['path']}"
                )
            payloads[role] = payload
        weight = np.frombuffer(payloads["A"], dtype=np.int8).reshape(
            16, 16, 4
        )
        activation = np.frombuffer(payloads["B"], dtype=np.uint8).reshape(
            56, 7, 16, 8, 4
        )
        bias = np.frombuffer(payloads["C"], dtype="<i4")
        expected = np.frombuffer(payloads["D"], dtype="<i4").reshape(
            56, 7, 8, 16
        )
        wide = np.einsum(
            "hwgql,gkl->hwqk",
            activation.astype(np.int64),
            weight.astype(np.int64),
            optimize=True,
        )
        wide += bias
        simulated = wide.astype(np.uint32).view(np.int32)
        mismatch = _first_mismatch(simulated, expected)
        if mismatch is not None:
            raise NativeFourLaneE2Error(
                f"transport config-bound mismatch: {record['op_id']} "
                f"slice{record['slice_id']:02d} {mismatch}"
            )
        corrupted = expected.copy()
        corrupted.reshape(-1)[0] ^= np.int32(1)
        first_corruption_detected = (
            first_corruption_detected
            or _first_mismatch(simulated, corrupted) is not None
        )
        sample = int(record["sample_id"])
        step = int(record["owner_step"])
        owner = (sample, step)
        if owner in owners:
            raise NativeFourLaneE2Error("transport logical owner is duplicated")
        owners.add(owner)
        logical[sample, step * 16 : (step + 1) * 16] = (
            simulated.reshape(56, 56, 16).transpose(2, 0, 1)
        )
        payload_hash.update(simulated.tobytes())
        lane_product_nonzero += int(
            np.count_nonzero(
                activation[:, :, :, :, None, :]
                * weight[None, None, :, None, :, :]
            )
        )
        lane_product_total += int(simulated.size) * 16 * 4
    expected_owners = {
        (sample, step) for sample in range(16) for step in range(4)
    }
    if owners != expected_owners:
        raise NativeFourLaneE2Error("transport logical owner coverage differs")
    w3 = np.load(root / W3_ACCUMULATOR_REL)
    mismatch = _first_mismatch(logical, w3)
    if mismatch is not None:
        raise NativeFourLaneE2Error(f"native inverse W3 mismatch: {mismatch}")
    if not first_corruption_detected:
        raise NativeFourLaneE2Error("transport corruption negative did not fail")
    return {
        "consumer_inputs": {
            "transport_manifest": {
                "path": manifest_path.relative_to(root).as_posix(),
                "sha256": sha256_file(manifest_path),
            },
            "record_count": len(records),
            "matrix_file_count": len(records) * 4,
        },
        "physical_inverse": (
            "A[g16,k16,lane4], B[h56,wblock7,g16,q8,lane4], "
            "C[k16] -> D[h56,wblock7,q8,k16] -> logical NCHW"
        ),
        "native_occurrence_count": int(logical.size) * 16,
        "logical_product_count": int(logical.size) * 64,
        "lanes_per_occurrence": 4,
        "useful_lane_slots_per_occurrence": 4,
        "maximum_useful_lane_utilization_percent": 100.0,
        "observed_nonzero_product_lane_fraction": (
            lane_product_nonzero / lane_product_total
        ),
        "physical_mismatch_count": 0,
        "logical_w3_mismatch_count": 0,
        "logical_output_payload_sha256": hashlib.sha256(
            np.ascontiguousarray(logical).tobytes()
        ).hexdigest(),
        "physical_record_output_sha256": payload_hash.hexdigest(),
        "w3_npy_file_sha256": sha256_file(root / W3_ACCUMULATOR_REL),
        "fail_closed_negative_controls": {
            "single_formal_D_bit_flip_detected": first_corruption_detected,
            "real_W3_all_64_logical_owners_consumed": True,
        },
    }


def _tail_config_bound_simulation(root: Path) -> dict[str, Any]:
    values = load_fresh_w3_values(root)
    config_root = root / CONFIG_REL / "tail"
    multipliers = np.empty(64, dtype=np.float32)
    seen: set[int] = set()
    config_records: list[dict[str, Any]] = []
    for wave in range(3):
        for shard in range(8):
            mul_path = config_root / f"mul_w{wave}_s{shard:02d}.json"
            round_path = config_root / f"round_w{wave}_s{shard:02d}.json"
            mul = _load(mul_path)
            rounded = _load(round_path)
            if (
                mul["general_array"]["inport"]["inport0"]["int32tofp32"]
                != "true"
                or rounded["general_array"]["outport"]["int32touint8"]
                != "true"
            ):
                raise NativeFourLaneE2Error("tail conversion flags differ")
            active_mul = [
                pe
                for pe in mul["general_array"]["PE_array"].values()
                if pe.get("alu_opcode") == "mul"
            ]
            if len(active_mul) != 8:
                raise NativeFourLaneE2Error("tail multiplier lane count differs")
            channels = list(range(shard * 8, shard * 8 + 8))
            constants = np.asarray(
                [pe["inport1"]["constant"] for pe in active_mul],
                dtype=np.float32,
            )
            for channel, value in zip(channels, constants, strict=True):
                if channel in seen and multipliers[channel].view(np.uint32) != value.view(
                    np.uint32
                ):
                    raise NativeFourLaneE2Error("tail multiplier differs by wave")
                multipliers[channel] = value
                seen.add(channel)
            config_records.append(
                {
                    "wave": wave,
                    "shard": shard,
                    "mul_sha256": sha256_file(mul_path),
                    "round_sha256": sha256_file(round_path),
                    "channels": channels,
                }
            )
    if seen != set(range(64)):
        raise NativeFourLaneE2Error("tail multiplier coverage differs")
    scaled = np.multiply(
        values["P"].astype(np.float32),
        multipliers.reshape(1, 64, 1, 1),
        dtype=np.float32,
    )
    magic = np.float32(12_582_912.0)
    rounded = (
        (scaled + magic).view(np.int32).astype(np.int64)
        - int(magic.view(np.uint32))
    )
    final = np.clip(rounded, 0, 255).astype(np.uint8)
    mismatch = _first_mismatch(final, values["D"])
    if mismatch is not None:
        raise NativeFourLaneE2Error(f"tail config-bound mismatch: {mismatch}")
    return {
        "config_count": len(config_records) * 2,
        "occurrence_pair_count": len(config_records),
        "records": config_records,
        "multiplier_payload_sha256": hashlib.sha256(
            multipliers.tobytes()
        ).hexdigest(),
        "output_payload_sha256": hashlib.sha256(
            np.ascontiguousarray(final).tobytes()
        ).hexdigest(),
        "formal_W3_output_payload_sha256": hashlib.sha256(
            np.ascontiguousarray(values["D"]).tobytes()
        ).hexdigest(),
        "mismatch_count": 0,
        "scaled_finite": bool(np.isfinite(scaled).all()),
        "requant_semantics": (
            "int32->fp32, fp32 multiplier, magic-bias RNE extraction, "
            "clip[0,255], uint8"
        ),
    }


def _verify_files(bundle: Path, manifest: dict[str, Any]) -> None:
    for relative, receipt in manifest.get("files", {}).items():
        path = bundle / relative
        if (
            not path.is_file()
            or sha256_file(path) != receipt["sha256"]
            or path.stat().st_size != receipt["size"]
        ):
            raise NativeFourLaneE2Error(
                f"bundle file receipt differs: {bundle / relative}"
            )


def _native_roundtrip(root: Path) -> dict[str, Any]:
    artifact = root / ARTIFACT_REL
    mapping_records: list[dict[str, Any]] = []
    mapping_dirs = [
        *[
            artifact / "mapping/conv" / f"op_w{wave}"
            for wave in range(3)
        ],
        *[
            artifact / "mapping/tail" / f"op_{kind}_w{wave}_s{shard:02d}"
            for wave in range(3)
            for shard in range(8)
            for kind in ("mul", "round")
        ],
    ]
    for bundle in mapping_dirs:
        path = bundle / "bundle_manifest.json"
        manifest = _load(path)
        summary = manifest.get("summary", {})
        if (
            summary.get("valid") is not True
            or float(summary.get("penalty", -1)) != 0.0
            or summary.get("fallback_used") is not False
        ):
            raise NativeFourLaneE2Error(f"mapping is not exact: {bundle}")
        _verify_files(bundle, manifest)
        mapping_records.append(
            {
                "op_id": bundle.name,
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "source_config_sha256": manifest["source_config_sha256"],
                "mapping_evidence_sha256": manifest[
                    "mapping_evidence_sha256"
                ],
            }
        )

    exec_dirs = [
        *[
            artifact / "execplan_conv" / f"wave-{wave}"
            for wave in range(3)
        ],
        *[
            artifact
            / "execplan_tail"
            / f"wave-{wave}-shard-{shard:02d}"
            for wave in range(3)
            for shard in range(8)
        ],
    ]
    exec_records: list[dict[str, Any]] = []
    sca_count = 0
    for bundle in exec_dirs:
        path = bundle / "bundle_manifest.json"
        manifest = _load(path)
        package_validation = manifest.get("package_validation_report")
        if (
            manifest.get("double_run", {}).get("equal") is not True
            or manifest.get("validation_report", {}).get("valid") is not True
            or (
                package_validation is not None
                and (
                    not isinstance(package_validation, dict)
                    or package_validation.get("valid") is not True
                )
            )
            or manifest.get("request_address_validation_report", {}).get(
                "valid"
            )
            is not True
        ):
            raise NativeFourLaneE2Error(f"execplan is not exact: {bundle}")
        _verify_files(bundle, manifest)
        for name in ("sca_cfg.json", "sca_cfg_D.json"):
            sca_path = bundle / "pipeline_output" / name
            if not sca_path.is_file():
                raise NativeFourLaneE2Error(f"SCA is missing: {sca_path}")
            sca_count += 1
        exec_records.append(
            {
                "run": bundle.name,
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "execplan_sha256": manifest["execplan"]["sha256"],
                "request_count_with_multiplicity": manifest[
                    "request_address_validation_report"
                ]["request_count_with_multiplicity"],
                "deterministic_file_count": manifest["double_run"][
                    "deterministic_file_count"
                ],
            }
        )
    return {
        "mapping_count": len(mapping_records),
        "execplan_count": len(exec_records),
        "sca_file_count": sca_count,
        "mapping": mapping_records,
        "execplan": exec_records,
        "json_mapping_bitstream_execplan_sca": "PASS",
        "all_mapping_penalty_zero": True,
        "all_mapping_fallback_false": True,
        "all_execplan_double_run_equal": True,
        "exact_consumer_file_receipts": True,
    }


def _conv_address_and_performance(
    root: Path, simulation: dict[str, Any]
) -> dict[str, Any]:
    artifact = root / ARTIFACT_REL
    totals = {"A": 0, "B": 0, "B'": 0, "C": 0, "D": 0}
    d_records = 0
    request_count = 0
    for wave in range(3):
        report_path = (
            artifact
            / "execplan_conv"
            / f"wave-{wave}"
            / "request_address_validation_report.json"
        )
        report = _load(report_path)
        if report.get("valid") is not True:
            raise NativeFourLaneE2Error("Conv address report is not valid")
        request_count += int(
            report["facts"]["request_count_with_multiplicity"]
        )
        stages = report["facts"]["stages"]
        if len(stages) != 1:
            raise NativeFourLaneE2Error("Conv execplan stage count differs")
        for stream in stages[0]["streams"]:
            target = stream["target"]
            totals[target] += int(
                stream["logical_payload_byte_count_with_multiplicity"]
            )
            if target == "D":
                if (
                    stream["logical_payload_byte_count_with_multiplicity"]
                    != 200_704
                    or stream["request_count_with_multiplicity"] != 12_544
                    or stream["unique_request_count"] != 12_544
                ):
                    raise NativeFourLaneE2Error("native D endpoint differs")
                d_records += 1
    if (
        totals
        != {
            "A": 65_536,
            "B": 12_845_056,
            "B'": 12_845_056,
            "C": 1_605_632,
            "D": 12_845_056,
        }
        or d_records != 64
    ):
        raise NativeFourLaneE2Error(
            f"native Conv address totals differ: {totals}/{d_records}"
        )
    serialized = _load(root / SERIALIZED_CONTRACT_REL)
    serialized_sim = serialized["config_bound_simulator"]
    serialized_traffic = serialized["address_lifetime_terminal"][
        "stream_payload_bytes_with_multiplicity"
    ]
    native_occurrences = int(simulation["native_occurrence_count"])
    serialized_occurrences = int(
        serialized_sim["serialized_occurrence_count"]
    )
    if (
        simulation["logical_output_payload_sha256"]
        != serialized_sim["logical_output_payload_sha256"]
    ):
        raise NativeFourLaneE2Error("native and serialized payloads differ")
    return {
        "address_request_count_with_multiplicity": request_count,
        "stream_payload_bytes_with_multiplicity": totals,
        "D_endpoint_records": d_records,
        "terminal_conservation": {
            "slice_schedule_count": 64,
            "unique_logical_output_tiles": 64,
            "D_regions_written_exactly_once": 64,
            "D_bytes_per_region": 200_704,
            "typed_output_bytes": 12_845_056,
            "native_reduction_groups_per_output": 16,
            "products_per_output": 64,
            "bias_initializations_per_output": 1,
            "terminal_writes_per_output": 1,
        },
        "actual_performance_inversion": {
            "logical_products": simulation["logical_product_count"],
            "serialized_occurrences": serialized_occurrences,
            "native_occurrences": native_occurrences,
            "compute_occurrence_reduction": (
                serialized_occurrences / native_occurrences
            ),
            "serialized_maximum_useful_lane_utilization_percent": 25.0,
            "native_maximum_useful_lane_utilization_percent": 100.0,
            "weight_payload_bytes": {
                "serialized": int(serialized_traffic["A"]),
                "native": totals["A"],
                "reduction": int(serialized_traffic["A"]) / totals["A"],
            },
            "activation_payload_bytes": {
                "serialized_single_B": int(serialized_traffic["B"]),
                "native_B": totals["B"],
                "native_B_prime": totals["B'"],
                "native_total_physical": totals["B"] + totals["B'"],
                "per_producer_reduction": int(serialized_traffic["B"])
                / totals["B"],
                "total_physical_reduction": int(serialized_traffic["B"])
                / (totals["B"] + totals["B'"]),
            },
            "bias_payload_bytes_unchanged": (
                int(serialized_traffic["C"]) == totals["C"]
            ),
            "D_payload_bytes_unchanged": (
                int(serialized_traffic["D"]) == totals["D"]
            ),
        },
        "three_way_accumulator": {
            "native_transport_sha256": simulation[
                "logical_output_payload_sha256"
            ],
            "serialized_baseline_sha256": serialized_sim[
                "logical_output_payload_sha256"
            ],
            "W3_formal_sha256": local_numeric_report(root)[
                "accumulator_sha256"
            ],
            "all_equal": True,
        },
    }


def build_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    revalidation = _load(root / REVALIDATION_REL)
    if (
        revalidation.get("status")
        != "RTL_AND_ALL53_REACHABILITY_REVALIDATION_PASS"
        or revalidation.get("current_rtl_identity", {}).get("commit")
        != RTL_COMMIT
    ):
        raise NativeFourLaneE2Error("df23e4d RTL revalidation is not closed")
    config = _config_semantics(root)
    simulation = _transport_simulation(root)
    tail = _tail_config_bound_simulation(root)
    roundtrip = _native_roundtrip(root)
    address = _conv_address_and_performance(root, simulation)
    holdouts = native_dot4_holdouts()
    numeric = local_numeric_report(root)
    if (
        numeric["accumulate_mismatch_count"] != 0
        or numeric["tail_mismatch_count"] != 0
        or tail["mismatch_count"] != 0
        or tail["output_payload_sha256"] != numeric["output_sha256"]
    ):
        raise NativeFourLaneE2Error("three-way accumulate/tail numeric gate differs")
    contract: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "LOCAL_E2_PASS",
        "candidate_class": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
        "candidate_release": False,
        "package_release": "NONE",
        "test_id": TEST_ID,
        "scope": {
            "node_id": NODE_ID,
            "request_id": REQUEST_ID,
            "request_sha256": REQUEST_SHA256,
            "hw_op_type": "ConvInt32Accumulate",
            "frozen_instance": {
                "x": ["uint8", [16, 64, 56, 56]],
                "w": ["int8", [64, 64, 1, 1]],
                "bias": ["int32", [64]],
                "accumulator": ["int32", [16, 64, 56, 56]],
                "output": ["uint8", [16, 64, 56, 56]],
                "x_zero_point": 0,
                "weight_zero_points": "all zero",
            },
            "claim_boundary": (
                "config-bound local E2 for frozen node0004 under the exact "
                "df23e4d arithmetic leaf identity; not server dynamic, "
                "natural-terminal, formal-D, performance, E4 or E5 evidence"
            ),
        },
        "current_rtl_identity": {
            "commit": RTL_COMMIT,
            "leaves": RTL_LEAVES,
            "revalidation": {
                "path": REVALIDATION_REL.as_posix(),
                "sha256": sha256_file(root / REVALIDATION_REL),
            },
            "all53_raw_reachability": {
                "path": RAW_REACHABILITY_REL.as_posix(),
                "sha256": sha256_file(root / RAW_REACHABILITY_REL),
            },
        },
        "serialized_correctness_baseline": {
            "path": SERIALIZED_CONTRACT_REL.as_posix(),
            "sha256": sha256_file(root / SERIALIZED_CONTRACT_REL),
            "preserved_read_only": True,
        },
        "config_semantics": config,
        "config_bound_accumulator_simulator": simulation,
        "config_bound_requant_tail_simulator": tail,
        "native_holdouts": holdouts,
        "native_roundtrip": roundtrip,
        "address_lifetime_terminal": address,
        "direct_ONNX_W3_numeric_replay": numeric,
        "stage_gates": {
            "rtl_named_boundaries": True,
            "all53_reachability_covered": True,
            "config_bound_E2": True,
            "native_vs_serialized_vs_W3": True,
            "mapping_bitstream_execplan_SCA": True,
            "server_dynamic_release_ready": False,
        },
        "blocker_delta": {
            "close": [
                "B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE",
                "B_CONV_NATIVE_FOUR_LANE_RTL_IDENTITY_AND_E2_PENDING",
            ],
            "keep": [
                "B_CONV_NATIVE_FOUR_LANE_SERVER_NATURAL_TERMINAL",
                "B_CONV_NATIVE_FOUR_LANE_SERVER_FORMAL_D_320",
                "B_CONV_NATIVE_FOUR_LANE_SERVER_PRODUCTION_RTL_IDENTITY",
            ],
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SA-INT8-RTL-COMPATIBILITY-001",
                "CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001",
                "config-bound E2 and exact consumer-closure gates",
                "server package release remains separate from E2",
            ],
            "rule_delta_proposal": [],
        },
        "read_receipts": {
            path.as_posix(): sha256_file(root / path) for path in RULE_PATHS
        },
        "server_action": False,
        "functional_rtl_modified": False,
        "serialized_assets_modified": False,
    }
    contract["contract_sha256"] = sha256_bytes(
        canonical_json_bytes(contract)
    )
    return contract


def write_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    contract = build_contract(root)
    _write(root / CONTRACT_REL, contract)
    return contract


__all__ = [
    "ARTIFACT_REL",
    "CONFIG_REL",
    "CONTRACT_REL",
    "NativeFourLaneE2Error",
    "build_contract",
    "native_dot4_holdouts",
    "write_contract",
]
