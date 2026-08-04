"""Config-bound functional execution for the frozen node0001 Requant asset.

The upstream NDPFuncModel checkout does not implement the reviewed two-stage
GA guard -> magic-round pipeline as a complete target executor.  This module
therefore provides the project-owned equivalent executor allowed by the
active plan:

* it consumes the 48 final address-bound JSON files, not generator inputs;
* it extracts the active GA opcodes, conversion flags and FP32 constants;
* it replays the frozen HWC8 occurrence/slice layout and address aliases;
* it uses NDPFuncModel's ActivationUnit rounding primitive as an independent
  native-component cross-check;
* it keeps hardware comparisons fail-closed until formal readback exists.

It never edits NDPFuncModel, ndp-sim, CGRA_SIM, or an ``rtl/`` directory and
does not create a server package.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .hashing import canonical_json_bytes, sha256_file
from .requantize_uint8_vertical import (
    ARTIFACT_REL,
    GA_MAC_KEYS,
    GA_SUB_KEYS,
    INPUT_REL,
    LANES,
    OCCURRENCE_COUNT,
    OUTPUT_REL,
    REQUEST_ID,
    ROUND_MAGIC_BITS,
    SHARD_COUNT,
    SPATIAL,
    STAGE_COUNT,
    _assert_stage_config,
    _parse_addr,
    requant_parameters,
    validate_guard_sfu_payload,
)


SCHEMA = "resnet50-node0001-requant-config-bound-simulator-v1"
CONTRACT_SCHEMA = "operator-config-bound-simulator-contract-v1"
OUTPUT_RELATIVE = Path(
    "artifacts/operator_config_validation/"
    "r5-requant-node0001-config-bound-sim-v1/three_way_report.json"
)
CONTRACT_RELATIVE = Path(
    "contracts/operator_config/requant_node0001_config_bound_simulator_v1.json"
)
NATIVE_JSON_RELATIVE = ARTIFACT_REL / "native_evidence/jsons"
TYPED_GRAPH_RELATIVE = ARTIFACT_REL / "typed_graph.json"
ROUNDTRIP_RELATIVE = ARTIFACT_REL / "materialized_roundtrip.json"
NUMERIC_RELATIVE = ARTIFACT_REL / "numeric_evidence.json"
SCA_RELATIVE = ARTIFACT_REL / "native_evidence/sca_cfg.json"
EXECPLAN_RELATIVE = ARTIFACT_REL / "native_evidence/install/execplan.txt"
SFU_RELATIVE = (
    ARTIFACT_REL / "native_evidence/install/cfg_pkg/RequantGuard.txt"
)
RULE_PATHS = (
    Path(".agents/rules/生成前必读索引.md"),
    Path(".agents/rules/算子配置规则.md"),
    Path(".agents/rules/NDP硬件字段语义.md"),
    Path(".agents/rules/RequantizeUint8算子配置规则.md"),
)
NDP_ACTIVATION_RELATIVE = Path("NDPFuncModel/component/ActiUnit.py")
NDP_BUFFER_RELATIVE = Path("NDPFuncModel/component/Buffer.py")
CGRA_ROUND_RELATIVE = Path("CGRA_SIM/cgra_python/op_lib/qnn/qnn_round.py")
RULE_IDS = (
    "CDA-REQUANT-QPARAM-001",
    "CDA-REQUANT-INT32-GUARD-001",
    "CDA-REQUANT-SFU-LUT-001",
    "CDA-REQUANT-TWO-STAGE-001",
    "CDA-REQUANT-ROUND-MAGIC-001",
    "CDA-REQUANT-LAYOUT-HWC8-001",
    "CDA-REQUANT-MATERIALIZED-ROUNDTRIP-001",
    "CDA-REQUANT-CONFIG-BOUND-SIMULATOR-001",
)


class RequantConfigBoundSimulatorError(ValueError):
    """Raised when final configuration or execution evidence is inconsistent."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RequantConfigBoundSimulatorError(
            f"cannot load JSON {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise RequantConfigBoundSimulatorError(f"JSON root is not an object: {path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _file_identity(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise RequantConfigBoundSimulatorError(f"required file is missing: {relative}")
    return {
        "path": relative.as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _repository_identity(root: Path, name: str) -> dict[str, Any]:
    lock = _load_json(root / "repos.lock.json")
    matches = [
        item
        for item in lock.get("repositories", [])
        if isinstance(item, dict) and item.get("name") == name
    ]
    if len(matches) != 1:
        raise RequantConfigBoundSimulatorError(
            f"repository lock identity is not unique: {name}"
        )
    item = matches[0]
    if item.get("path") != name or item.get("dirty") is not False:
        raise RequantConfigBoundSimulatorError(
            f"repository lock is not frozen and clean: {name}"
        )
    return {
        "name": name,
        "path": item["path"],
        "upstream": item.get("upstream"),
        "branch": item.get("branch"),
        "commit": item.get("commit"),
        "dirty": item["dirty"],
    }


def _load_ndp_activation_unit(root: Path) -> tuple[type[Any], dict[str, Any]]:
    repository = (root / "NDPFuncModel").resolve()
    source = (root / NDP_ACTIVATION_RELATIVE).resolve()
    buffer_source = (root / NDP_BUFFER_RELATIVE).resolve()
    if not source.is_file() or not buffer_source.is_file():
        raise RequantConfigBoundSimulatorError(
            "NDPFuncModel ActivationUnit/Buffer source is missing"
        )
    repository_text = str(repository)
    inserted = repository_text not in sys.path
    if inserted:
        sys.path.insert(0, repository_text)
    try:
        module = importlib.import_module("component.ActiUnit")
    finally:
        if inserted:
            sys.path.remove(repository_text)
    observed = Path(module.__file__).resolve()
    if observed != source:
        raise RequantConfigBoundSimulatorError(
            f"ActivationUnit resolved outside frozen NDPFuncModel: {observed}"
        )
    return module.ActivationUnit, {
        "repository": _repository_identity(root, "NDPFuncModel"),
        "component": _file_identity(root, NDP_ACTIVATION_RELATIVE),
        "buffer_dependency": _file_identity(root, NDP_BUFFER_RELATIVE),
        "role": "native tie-to-even cross-check; not a complete two-stage target executor",
    }


def _load_cgra_round(root: Path) -> tuple[Any, dict[str, Any]]:
    path = (root / CGRA_ROUND_RELATIVE).resolve()
    spec = importlib.util.spec_from_file_location(
        "cgra_qnn_round_for_node0001_config_bound", path
    )
    if spec is None or spec.loader is None:
        raise RequantConfigBoundSimulatorError(
            f"cannot load CGRA_SIM rounding reference: {path}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, {
        "repository": _repository_identity(root, "CGRA_SIM"),
        "component": _file_identity(root, CGRA_ROUND_RELATIVE),
        "role": "formula-only rounding reference; does not consume target JSON",
    }


def _active_slices(mask: str) -> list[int]:
    if not isinstance(mask, str) or not mask.startswith("0b"):
        raise RequantConfigBoundSimulatorError(f"invalid slice mask: {mask!r}")
    value = int(mask[2:], 2)
    if value >> 28:
        raise RequantConfigBoundSimulatorError("slice mask exceeds 28 slices")
    return [slice_id for slice_id in range(28) if value & (1 << slice_id)]


def _nchw_shard(
    value: np.ndarray, sample: int, channels: list[int]
) -> np.ndarray:
    if len(channels) != LANES:
        raise RequantConfigBoundSimulatorError("HWC8 shard must have eight channels")
    shard = np.moveaxis(value[sample, channels, :, :], 0, -1)
    return np.ascontiguousarray(shard.reshape(SPATIAL, LANES))


def _first_mismatch(actual: np.ndarray, expected: np.ndarray) -> dict[str, Any] | None:
    mismatch = np.argwhere(actual != expected)
    if not mismatch.size:
        return None
    index = tuple(int(item) for item in mismatch[0])
    return {
        "index": list(index),
        "actual": int(actual[index]),
        "expected": int(expected[index]),
    }


def _hash_record(
    hasher: Any,
    *,
    wave: int,
    shard: int,
    slice_id: int,
    base_address: int,
    payload: bytes,
) -> None:
    header = (
        f"wave={wave};shard={shard};slice={slice_id};"
        f"base=0x{base_address:x};bytes={len(payload)}\n"
    ).encode("ascii")
    hasher.update(header)
    hasher.update(payload)


def _with_self_hash(value: dict[str, Any], field: str) -> dict[str, Any]:
    result = dict(value)
    result[field] = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return result


def build_config_bound_report(root: Path) -> dict[str, Any]:
    """Execute the frozen 48-stage node0001 configuration locally."""

    root = root.resolve()
    graph = _load_json(root / TYPED_GRAPH_RELATIVE)
    roundtrip = _load_json(root / ROUNDTRIP_RELATIVE)
    numeric = _load_json(root / NUMERIC_RELATIVE)
    sca = _load_json(root / SCA_RELATIVE)
    multiplier, zero_point, qparams = requant_parameters(root)
    if zero_point != 0:
        raise RequantConfigBoundSimulatorError("node0001 output zero point is not zero")

    operators = graph.get("operators")
    if not isinstance(operators, list) or len(operators) != STAGE_COUNT:
        raise RequantConfigBoundSimulatorError("typed graph is not the frozen 48-stage plan")
    if [
        operator.get("stage") for operator in operators
    ] != ["guard", "round_saturate"] * OCCURRENCE_COUNT:
        raise RequantConfigBoundSimulatorError(
            "typed graph does not alternate guard and round stages"
        )
    if (
        roundtrip.get("occurrence_count") != OCCURRENCE_COUNT
        or roundtrip.get("stage_count") != STAGE_COUNT
        or roundtrip.get("consumer_intermediate_external_preload_count") != 0
        or roundtrip.get("guard_sfu_load_count") != 1
    ):
        raise RequantConfigBoundSimulatorError(
            "materialized roundtrip lifecycle summary differs"
        )
    if sca.get("Repeat_Num") != STAGE_COUNT:
        raise RequantConfigBoundSimulatorError("SCA Repeat_Num is not 48")
    execplan_lines = (root / EXECPLAN_RELATIVE).read_text(
        encoding="ascii"
    ).splitlines()
    if sca.get("Exec_Length") != len(execplan_lines) or len(execplan_lines) != 317:
        raise RequantConfigBoundSimulatorError(
            "SCA/execplan line count differs from the frozen lifecycle"
        )
    sfu = validate_guard_sfu_payload(
        (root / SFU_RELATIVE).read_text(encoding="ascii")
    )

    json_root = root / NATIVE_JSON_RELATIVE
    expected_paths = {
        f"{operator['id']}_{operator['type']}.json" for operator in operators
    }
    actual_paths = {path.name for path in json_root.glob("*.json")}
    if actual_paths != expected_paths:
        missing = sorted(expected_paths - actual_paths)
        extra = sorted(actual_paths - expected_paths)
        raise RequantConfigBoundSimulatorError(
            f"final JSON exact set differs: missing={missing[:1]}, extra={extra[:1]}"
        )

    records = roundtrip.get("records")
    if not isinstance(records, list) or len(records) != OCCURRENCE_COUNT:
        raise RequantConfigBoundSimulatorError(
            "materialized roundtrip occurrence records differ"
        )
    record_by_key = {
        (int(item["wave_index"]), int(item["shard_index"])): item
        for item in records
    }
    if len(record_by_key) != OCCURRENCE_COUNT:
        raise RequantConfigBoundSimulatorError(
            "materialized occurrence keys are not unique"
        )

    accumulator = np.load(root / INPUT_REL, mmap_mode="r", allow_pickle=False)
    golden = np.load(root / OUTPUT_REL, mmap_mode="r", allow_pickle=False)
    expected_shape = (16, 64, 112, 112)
    if (
        accumulator.shape != expected_shape
        or accumulator.dtype != np.dtype("int32")
        or golden.shape != expected_shape
        or golden.dtype != np.dtype("uint8")
    ):
        raise RequantConfigBoundSimulatorError("node0001 W3 tensor ABI differs")

    activation_unit, ndp_identity = _load_ndp_activation_unit(root)
    cgra_round, cgra_identity = _load_cgra_round(root)
    simulated = np.empty(expected_shape, dtype=np.uint8)
    guarded = np.empty(expected_shape, dtype=np.float32)
    channel_coverage = np.zeros((16, 64), dtype=np.uint8)
    guard_physical_hasher = hashlib.sha256()
    final_physical_hasher = hashlib.sha256()
    pair_summaries: list[dict[str, Any]] = []
    physical_outputs: list[dict[str, Any]] = []
    native_round_mismatch_count = 0
    cgra_round_mismatch_count = 0
    final_mismatch_count = 0
    first_final_mismatch: dict[str, Any] | None = None
    output_regions: set[tuple[int, int, int]] = set()
    guard_aliases: set[tuple[int, int, int]] = set()
    final_json_identities: list[dict[str, Any]] = []

    for occurrence in range(OCCURRENCE_COUNT):
        guard_op = operators[occurrence * 2]
        round_op = operators[occurrence * 2 + 1]
        wave = int(guard_op["attributes"]["wave_index"])
        shard = int(guard_op["attributes"]["shard_index"])
        if (
            round_op["attributes"]["wave_index"] != wave
            or round_op["attributes"]["shard_index"] != shard
            or round_op["inputs"]["A"]["source"]
            != {"type": "operator", "operator_id": guard_op["id"]}
        ):
            raise RequantConfigBoundSimulatorError(
                f"guard/round graph pairing differs at occurrence {occurrence}"
            )
        record = record_by_key[(wave, shard)]
        guard_path = json_root / f"{guard_op['id']}_{guard_op['type']}.json"
        round_path = json_root / f"{round_op['id']}_{round_op['type']}.json"
        if (
            sha256_file(guard_path) != record["guard_json_sha256"]
            or sha256_file(round_path) != record["round_json_sha256"]
        ):
            raise RequantConfigBoundSimulatorError(
                f"final JSON hash differs at occurrence {occurrence}"
            )
        guard_config = _load_json(guard_path)
        round_config = _load_json(round_path)
        guard_audit = _assert_stage_config(
            guard_config,
            role="guard",
            multiplier=multiplier,
            shard=shard,
        )
        round_audit = _assert_stage_config(
            round_config,
            role="round_saturate",
            multiplier=multiplier,
            shard=shard,
        )
        guard_a_base = _parse_addr(
            guard_config["stream_engine"]["stream0"]["base_addr"]
        )
        guard_d_base = _parse_addr(
            guard_config["stream_engine"]["stream2"]["base_addr"]
        )
        round_a_base = _parse_addr(
            round_config["stream_engine"]["stream0"]["base_addr"]
        )
        round_d_base = _parse_addr(
            round_config["stream_engine"]["stream2"]["base_addr"]
        )
        if (
            guard_d_base != round_a_base
            or guard_d_base != _parse_addr(record["producer_output_base_addr"])
            or round_a_base != _parse_addr(record["consumer_input_base_addr"])
        ):
            raise RequantConfigBoundSimulatorError(
                f"producer/consumer address differs at occurrence {occurrence}"
            )

        active_slices = _active_slices(guard_op["used_slices"])
        sample_ids = [int(item) for item in guard_op["attributes"]["sample_ids"]]
        channels = [int(item) for item in guard_op["attributes"]["channels"]]
        if (
            active_slices != _active_slices(round_op["used_slices"])
            or sample_ids != [int(item) for item in record["sample_ids"]]
            or channels != [int(item) for item in record["channels"]]
            or len(active_slices) != len(sample_ids)
        ):
            raise RequantConfigBoundSimulatorError(
                f"slice/sample/channel binding differs at occurrence {occurrence}"
            )

        round_pe = round_config["general_array"]["PE_array"]
        lane_multipliers = np.array(
            [
                round_pe[key]["inport1"]["constant"]
                for key in GA_MAC_KEYS
            ],
            dtype=np.float32,
        )
        lane_magic = np.array(
            [
                round_pe[key]["inport2"]["constant"]
                for key in GA_MAC_KEYS
            ],
            dtype=np.float32,
        )
        lane_subtract = np.array(
            [
                round_pe[key]["inport1"]["constant"]
                for key in GA_SUB_KEYS
            ],
            dtype=np.int64,
        )
        if np.any(lane_subtract != ROUND_MAGIC_BITS):
            raise RequantConfigBoundSimulatorError(
                f"round subtract constant differs at occurrence {occurrence}"
            )

        pair_final_mismatch = 0
        pair_native_mismatch = 0
        pair_cgra_mismatch = 0
        pair_guard_hasher = hashlib.sha256()
        pair_final_hasher = hashlib.sha256()
        for slice_id, sample_id in zip(active_slices, sample_ids, strict=True):
            source = _nchw_shard(accumulator, sample_id, channels)
            guard_value = np.where(
                source < 0,
                np.float32(0.0),
                source.astype(np.float32),
            ).astype(np.float32, copy=False)
            scaled = np.multiply(
                guard_value,
                lane_multipliers.reshape(1, LANES),
                dtype=np.float32,
            )
            biased = np.add(
                scaled,
                lane_magic.reshape(1, LANES),
                dtype=np.float32,
            )
            rounded = (
                biased.view(np.int32).astype(np.int64)
                - lane_subtract.reshape(1, LANES)
            )
            output = np.clip(rounded, 0, 255).astype(np.uint8)
            native_output = np.clip(
                activation_unit.sse2_round_to_int(scaled), 0, 255
            ).astype(np.uint8)
            cgra_output = np.clip(
                cgra_round.sse2_round_to_int(scaled), 0, 255
            ).astype(np.uint8)
            expected = _nchw_shard(golden, sample_id, channels)

            native_mismatch = int(np.count_nonzero(native_output != output))
            cgra_mismatch = int(np.count_nonzero(cgra_output != output))
            final_mismatch = int(np.count_nonzero(output != expected))
            native_round_mismatch_count += native_mismatch
            cgra_round_mismatch_count += cgra_mismatch
            final_mismatch_count += final_mismatch
            pair_native_mismatch += native_mismatch
            pair_cgra_mismatch += cgra_mismatch
            pair_final_mismatch += final_mismatch
            if final_mismatch and first_final_mismatch is None:
                mismatch = _first_mismatch(output, expected)
                first_final_mismatch = {
                    "occurrence_index": occurrence,
                    "wave_index": wave,
                    "shard_index": shard,
                    "slice_id": slice_id,
                    "sample_id": sample_id,
                    **(mismatch or {}),
                }

            simulated[sample_id, channels, :, :] = np.moveaxis(
                output.reshape(112, 112, LANES), -1, 0
            )
            guarded[sample_id, channels, :, :] = np.moveaxis(
                guard_value.reshape(112, 112, LANES), -1, 0
            )
            channel_coverage[sample_id, channels] += 1

            guard_payload = np.ascontiguousarray(guard_value).tobytes()
            final_payload = np.ascontiguousarray(output).tobytes()
            expected_payload = np.ascontiguousarray(expected).tobytes()
            _hash_record(
                guard_physical_hasher,
                wave=wave,
                shard=shard,
                slice_id=slice_id,
                base_address=guard_d_base,
                payload=guard_payload,
            )
            _hash_record(
                final_physical_hasher,
                wave=wave,
                shard=shard,
                slice_id=slice_id,
                base_address=round_d_base,
                payload=final_payload,
            )
            pair_guard_hasher.update(guard_payload)
            pair_final_hasher.update(final_payload)
            guard_aliases.add((slice_id, guard_d_base, len(guard_payload)))
            region = (slice_id, round_d_base, len(final_payload))
            if region in output_regions:
                raise RequantConfigBoundSimulatorError(
                    f"duplicate final physical D region: {region}"
                )
            output_regions.add(region)
            physical_outputs.append(
                {
                    "occurrence_index": occurrence,
                    "wave_index": wave,
                    "shard_index": shard,
                    "slice_id": slice_id,
                    "sample_id": sample_id,
                    "guard_base_addr": f"0x{guard_d_base:08x}",
                    "guard_size_bytes": len(guard_payload),
                    "guard_sha256": hashlib.sha256(guard_payload).hexdigest(),
                    "final_base_addr": f"0x{round_d_base:08x}",
                    "final_size_bytes": len(final_payload),
                    "final_sha256": hashlib.sha256(final_payload).hexdigest(),
                    "expected_sha256": hashlib.sha256(expected_payload).hexdigest(),
                    "final_mismatch_count": final_mismatch,
                }
            )

        pair_summaries.append(
            {
                "occurrence_index": occurrence,
                "wave_index": wave,
                "shard_index": shard,
                "guard_op_id": guard_op["id"],
                "round_op_id": round_op["id"],
                "active_slices": active_slices,
                "sample_ids": sample_ids,
                "channels": channels,
                "guard_a_base_addr": f"0x{guard_a_base:08x}",
                "guard_d_round_a_base_addr": f"0x{guard_d_base:08x}",
                "round_d_base_addr": f"0x{round_d_base:08x}",
                "guard_physical_sha256": pair_guard_hasher.hexdigest(),
                "final_physical_sha256": pair_final_hasher.hexdigest(),
                "native_round_mismatch_count": pair_native_mismatch,
                "cgra_round_mismatch_count": pair_cgra_mismatch,
                "golden_mismatch_count": pair_final_mismatch,
                "guard_config_audit": guard_audit,
                "round_config_audit": round_audit,
            }
        )
        final_json_identities.extend(
            [
                _file_identity(root, guard_path.relative_to(root)),
                _file_identity(root, round_path.relative_to(root)),
            ]
        )

    if not np.all(channel_coverage == 1):
        where = np.argwhere(channel_coverage != 1)
        raise RequantConfigBoundSimulatorError(
            f"logical sample/channel coverage differs first={where[0].tolist()}"
        )
    simulated_sha = hashlib.sha256(
        np.ascontiguousarray(simulated).tobytes()
    ).hexdigest()
    guarded_sha = hashlib.sha256(
        np.ascontiguousarray(guarded).tobytes()
    ).hexdigest()
    golden_sha = hashlib.sha256(
        np.ascontiguousarray(golden).tobytes()
    ).hexdigest()
    if (
        final_mismatch_count
        or native_round_mismatch_count
        or cgra_round_mismatch_count
        or simulated_sha != golden_sha
        or numeric.get("golden_sha256") != golden_sha
        or numeric.get("guard_sha256") != guarded_sha
    ):
        raise RequantConfigBoundSimulatorError(
            "config-bound simulator differs from frozen references: "
            f"final={final_mismatch_count}, native={native_round_mismatch_count}, "
            f"cgra={cgra_round_mismatch_count}, first={first_final_mismatch}"
        )

    read_receipt = [
        {
            **_file_identity(root, relative),
            "reason": "active generation/field rule read before config-bound execution",
        }
        for relative in RULE_PATHS
    ]
    source_identity = {
        "typed_graph": _file_identity(root, TYPED_GRAPH_RELATIVE),
        "materialized_roundtrip": _file_identity(root, ROUNDTRIP_RELATIVE),
        "numeric_evidence": _file_identity(root, NUMERIC_RELATIVE),
        "sca": _file_identity(root, SCA_RELATIVE),
        "execplan": _file_identity(root, EXECPLAN_RELATIVE),
        "guard_sfu": _file_identity(root, SFU_RELATIVE),
        "input": _file_identity(root, INPUT_REL),
        "golden": _file_identity(root, OUTPUT_REL),
        "final_json_count": len(final_json_identities),
        "final_json_set_sha256": hashlib.sha256(
            canonical_json_bytes(final_json_identities)
        ).hexdigest(),
        "final_json_files": final_json_identities,
    }
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "CONFIG_BOUND_SIMULATOR_E2_COMPLETE_HARDWARE_PENDING",
        "request_id": REQUEST_ID,
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "server_package": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "executor": {
            "kind": "PROJECT_EQUIVALENT_CONFIG_BOUND_EXECUTOR",
            "consumes_final_address_bound_json": True,
            "consumes_occurrence_slice_layout": True,
            "consumes_sca_execplan_lifecycle": True,
            "native_ndp_complete_two_stage_executor_available": False,
            "native_ndp_component": ndp_identity,
            "cgra_formula_reference": cgra_identity,
            "claim_boundary": (
                "NDPFuncModel ActivationUnit and CGRA_SIM are cross-checks; "
                "the project executor owns final-JSON binding and is not RTL timing proof"
            ),
        },
        "source_identity": source_identity,
        "read_receipt": read_receipt,
        "rule_ids": list(RULE_IDS),
        "qparams": qparams,
        "lifecycle": {
            "occurrence_count": OCCURRENCE_COUNT,
            "stage_count": STAGE_COUNT,
            "guard_round_alternating": True,
            "sca_repeat_num": sca["Repeat_Num"],
            "execplan_line_count": len(execplan_lines),
            "consumer_external_preload_count": 0,
            "shared_guard_sfu_load_count": 1,
        },
        "physical_layout": {
            "slice_count": 28,
            "active_slice_execution_count": len(physical_outputs),
            "unique_final_d_region_count": len(output_regions),
            "unique_guard_alias_region_count": len(guard_aliases),
            "guard_bytes_per_slice_occurrence": SPATIAL * LANES * 4,
            "final_bytes_per_slice_occurrence": SPATIAL * LANES,
            "logical_sample_channel_coverage_min": int(channel_coverage.min()),
            "logical_sample_channel_coverage_max": int(channel_coverage.max()),
            "guard_physical_stream_sha256": guard_physical_hasher.hexdigest(),
            "final_physical_stream_sha256": final_physical_hasher.hexdigest(),
            "inverse": "slice_to_sample + HWC8 channels -> logical NCHW",
        },
        "numeric": {
            "element_count": int(simulated.size),
            "guard_sha256": guarded_sha,
            "simulator_output_sha256": simulated_sha,
            "golden_sha256": golden_sha,
            "golden_mismatch_count": final_mismatch_count,
            "native_activation_round_mismatch_count": native_round_mismatch_count,
            "cgra_round_reference_mismatch_count": cgra_round_mismatch_count,
            "first_golden_mismatch": first_final_mismatch,
            "bit_exact": True,
        },
        "comparisons": {
            "golden_vs_config_bound_simulator": {
                "status": "PASS",
                "mismatch_count": 0,
                "bit_exact": True,
            },
            "golden_vs_stock_rtl_hardware": {
                "status": "EVIDENCE_MISSING",
                "reason": "no naturally completed formal E4 readback",
            },
            "config_bound_simulator_vs_stock_rtl_hardware": {
                "status": "EVIDENCE_MISSING",
                "reason": "no naturally completed formal E4 readback",
            },
        },
        "occurrences": pair_summaries,
        "physical_outputs": physical_outputs,
        "guard_sfu": sfu,
        "remaining_blockers": ["B_REQUANT_SERVER_E4_E5"],
    }
    return _with_self_hash(body, "report_content_sha256")


def write_config_bound_evidence(
    root: Path,
    *,
    output: Path | None = None,
    contract: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    output_path = (output or root / OUTPUT_RELATIVE).resolve()
    contract_path = (contract or root / CONTRACT_RELATIVE).resolve()
    report = build_config_bound_report(root)
    _write_json(output_path, report)
    artifact = _file_identity(root, output_path.relative_to(root))
    contract_body: dict[str, Any] = {
        "schema": CONTRACT_SCHEMA,
        "status": report["status"],
        "request_id": REQUEST_ID,
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "artifact": artifact,
        "executor_kind": report["executor"]["kind"],
        "rule_ids": report["rule_ids"],
        "final_json_count": report["source_identity"]["final_json_count"],
        "occurrence_count": report["lifecycle"]["occurrence_count"],
        "stage_count": report["lifecycle"]["stage_count"],
        "golden_vs_config_bound_simulator": report["comparisons"][
            "golden_vs_config_bound_simulator"
        ],
        "golden_vs_stock_rtl_hardware": report["comparisons"][
            "golden_vs_stock_rtl_hardware"
        ],
        "config_bound_simulator_vs_stock_rtl_hardware": report["comparisons"][
            "config_bound_simulator_vs_stock_rtl_hardware"
        ],
        "remaining_blockers": report["remaining_blockers"],
    }
    contract_value = _with_self_hash(contract_body, "contract_content_sha256")
    _write_json(contract_path, contract_value)
    return report, contract_value


__all__ = [
    "CONTRACT_RELATIVE",
    "OUTPUT_RELATIVE",
    "RequantConfigBoundSimulatorError",
    "build_config_bound_report",
    "write_config_bound_evidence",
]
