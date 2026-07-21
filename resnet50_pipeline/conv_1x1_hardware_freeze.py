from __future__ import annotations

import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any

import numpy as np

from .bitstream_binding import (
    BITSTREAM_BINDING_SCHEMA_VERSION,
    BitstreamBindingError,
    bitstream_text_identity,
    require_same_logical_bitstream,
)
from .conv_instance import (
    FIRST_REAL_CONV_NODE_ID,
    ConvTargetRequest,
    build_conv_target_request,
)
from .conv28_layout import (
    CONV28_HARDWARE_LAYOUT_ABI,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
    QLinearConvPhysicalLayout,
)
from .typed_config_parameters import validate_typed_config_parameter_contract
from .w5_conv_preflight import (
    _bind_native_encoder_candidate,
    _initializer,
    _initializer_values,
    _load_json,
    _load_npy,
    validate_conv_hardware_quantization_preconditions,
    validate_w5_first_conv_preflight,
)


FREEZE_SCHEMA_VERSION = "0.1"
FREEZE_CONTRACT_TYPE = "conv_1x1_manual_hardware_handoff"
CANDIDATE_FREEZE_CONTRACT_TYPE = "conv_instance_candidate_hardware_freeze"
INPUT_PORTS = {
    "A",
    "B",
    "bias",
    "w_scale",
    "w_zero_point",
    "x_scale",
    "x_zero_point",
    "y_scale",
    "y_zero_point",
}
OUTPUT_PORTS = {"P", "D"}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _prepare_empty_output_root(path: Path) -> None:
    if path.exists():
        if path.is_symlink() or not path.is_dir():
            raise ValueError(f"hardware freeze output must be a regular directory: {path}")
        if any(path.iterdir()):
            raise ValueError(f"hardware freeze output directory is not empty: {path}")
        return
    path.mkdir(parents=True, exist_ok=False)


def _freeze_id(manifest: dict[str, Any]) -> str:
    body = dict(manifest)
    body.pop("freeze_id", None)
    payload = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256(payload)


def _write_bytes(path: Path, payload: bytes) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "path": path.as_posix(),
        "size_bytes": len(payload),
        "sha256": _sha256(payload),
    }


def _write_relative(root: Path, relative: str, payload: bytes) -> dict[str, Any]:
    record = _write_bytes(root / relative, payload)
    record["path"] = relative
    return record


def _copy_relative(root: Path, source: Path, relative: str) -> dict[str, Any]:
    if not source.is_file():
        raise FileNotFoundError(f"frozen handoff source is missing: {source}")
    destination = root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return {
        "path": relative,
        "size_bytes": destination.stat().st_size,
        "sha256": _sha256(destination.read_bytes()),
    }


def _selected_bundle(
    project_root: Path,
    request: ConvTargetRequest | None = None,
):
    request = request or build_conv_target_request(project_root)
    spec = request.spec
    typed = _load_json(project_root / "contracts" / "typed_config_parameter_contract.json")
    validate_typed_config_parameter_contract(typed)
    runtime_root = project_root / "artifacts" / "w3" / "golden_batch16"
    subop_root = project_root / "artifacts" / "w3" / "subop_batch16"
    runtime_manifest = _load_json(runtime_root / "manifest.json")
    subop_manifest = _load_json(subop_root / "manifest.json")
    initializers = _initializer_values(
        project_root / "artifacts" / "reference_model" / "resnet50-v1-12-int8.onnx"
    )
    descriptors = {
        name: spec.tensor(name).descriptor()
        for name in (
            "A",
            "B",
            "bias",
            "w_scale",
            "w_zero_point",
            "x_scale",
            "x_zero_point",
            "y_scale",
            "y_zero_point",
            "P",
            "D",
        )
    }
    values = {
        "A": _load_npy(
            runtime_root,
            runtime_manifest,
            runtime_manifest["tensors"][descriptors["A"]["tensor_id"]],
        ),
        "P": _load_npy(
            subop_root,
            subop_manifest,
            subop_manifest["internal_tensors"][descriptors["P"]["tensor_id"]],
        ),
        "D": _load_npy(
            runtime_root,
            runtime_manifest,
            runtime_manifest["tensors"][descriptors["D"]["tensor_id"]],
        ),
    }
    for port in INPUT_PORTS - {"A"}:
        values[port] = _initializer(
            initializers,
            runtime_manifest,
            descriptors[port],
        )
    validate_conv_hardware_quantization_preconditions(values)
    layout = QLinearConvPhysicalLayout(
        profile_id=GROUP4X7_BATCH_CHANNEL28_PROFILE,
        layout_abi=CONV28_HARDWARE_LAYOUT_ABI,
    )
    bundle = layout.forward(
        activation=values["A"],
        weight=values["B"],
        bias=values["bias"],
        w_scale=values["w_scale"],
        w_zero_point=values["w_zero_point"],
        x_scale=values["x_scale"],
        x_zero_point=values["x_zero_point"],
        y_scale=values["y_scale"],
        y_zero_point=values["y_zero_point"],
        accumulator=values["P"],
        output=values["D"],
        strides=spec.strides,
        pads=spec.pads,
        dilations=spec.dilations,
        group=spec.group,
        tensor_ids={name: descriptor["tensor_id"] for name, descriptor in descriptors.items()},
    )
    layout.validate(bundle)
    return values, bundle


def _validate_freeze_source_preflight(
    request: ConvTargetRequest,
    preflight: dict[str, Any],
) -> tuple[str, str, str]:
    """Validate the evidence boundary without promoting candidates to hardware-passed."""

    spec = request.spec
    if spec.node_id == FIRST_REAL_CONV_NODE_ID:
        validate_w5_first_conv_preflight(preflight)
        if preflight["gate_state"].get("single_operator_manual_hardware_handoff_ready") is not True:
            raise ValueError("W5 report does not authorize the manual hardware handoff")
        return (
            "manual_hardware_handoff_ready",
            str(preflight["ndp_conv_simulator_first_coordinate"]["source_commit"]),
            str(preflight["ndp_target_config_comparison"]["request_schema"]),
        )

    identity = preflight.get("identity")
    gates = preflight.get("gate_state")
    config_bound = preflight.get("config_bound_comparison")
    source_identity = preflight.get("source_identity")
    if (
        preflight.get("schema_version") != "0.1"
        or preflight.get("status") != "candidate_config_and_config_bound_pd_passed"
        or not isinstance(identity, dict)
        or identity.get("node_id") != spec.node_id
        or identity.get("hw_op_ids")
        != [spec.accumulate_hw_op_id, spec.requant_hw_op_id]
        or preflight.get("instance_spec") != spec.to_dict()
        or not isinstance(gates, dict)
        or gates.get("e1_candidate_passed") is not True
        or gates.get("execplan_typed_transport_passed") is not True
        or any(gates.get(key) is not False for key in ("hardware_passed", "g5_passed", "g6_passed", "g8_passed"))
        or not isinstance(config_bound, dict)
        or config_bound.get("status")
        != "accumulate_and_requant_configs_passed_with_execution_boundary"
        or config_bound.get("request_schema") != "0.3"
        or not isinstance(source_identity, dict)
        or not isinstance(source_identity.get("ndp_source_commit"), str)
    ):
        raise ValueError(f"candidate Conv preflight is not freeze-ready: {spec.node_id}")
    return (
        "candidate_hardware_freeze_ready",
        str(source_identity["ndp_source_commit"]),
        str(config_bound["request_schema"]),
    )


def _encoder_sources(
    project_root: Path,
    request: ConvTargetRequest,
    accumulate_encoder_root: Path | None = None,
    requant_encoder_root: Path | None = None,
) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]]]:
    spec = request.spec
    if spec.node_id == FIRST_REAL_CONV_NODE_ID:
        if accumulate_encoder_root is not None:
            encoder_root = accumulate_encoder_root.resolve()
            if requant_encoder_root is None:
                raise ValueError(
                    "revised first-Conv freeze requires an explicit requant_encoder_root"
                )
            selected_requant_root = requant_encoder_root.resolve()
            bitstreams = [
                (
                    (
                        encoder_root / f"modules_dump_{width}.bin"
                        if (encoder_root / f"modules_dump_{width}.bin").is_file()
                        else encoder_root / f"conv_1x1_real_bitstream_{width}.bin"
                    ),
                    f"bitstreams/accumulate/conv_1x1_real_bitstream_{width}.bin",
                )
                for width in ("128b", "64b")
            ]
            for shard_index in range(spec.requant_shard_count):
                bitstreams.extend(
                    (
                        selected_requant_root
                        / f"shard-{shard_index:02d}"
                        / f"modules_dump_{width}.bin",
                        f"bitstreams/requant/shard-{shard_index:02d}_bitstream_{width}.bin",
                    )
                    for width in ("128b", "64b")
                )
            parsed = [
                (
                    encoder_root / "parsed_bitstream.txt",
                    "encoder_evidence/accumulate/parsed_bitstream.txt",
                )
            ]
            parsed.extend(
                (
                    selected_requant_root
                    / f"shard-{shard_index:02d}"
                    / "parsed_bitstream.txt",
                    f"encoder_evidence/requant/shard-{shard_index:02d}/parsed_bitstream.txt",
                )
                for shard_index in range(spec.requant_shard_count)
            )
            return bitstreams, parsed
        bitstreams = [
            (
                project_root
                / "artifacts"
                / "w5"
                / "conv_1x1_real"
                / "encode_a"
                / f"conv_1x1_real_bitstream_{width}.bin",
                f"bitstreams/accumulate/conv_1x1_real_bitstream_{width}.bin",
            )
            for width in ("128b", "64b")
        ]
        for shard_index in range(spec.requant_shard_count):
            bitstreams.extend(
                (
                    project_root
                    / "artifacts"
                    / "w5"
                    / "conv_1x1_requant_real"
                    / f"shard-{shard_index:02d}"
                    / f"shard-{shard_index:02d}_bitstream_{width}.bin",
                    f"bitstreams/requant/shard-{shard_index:02d}_bitstream_{width}.bin",
                )
                for width in ("128b", "64b")
            )
        return bitstreams, []

    evidence_root = project_root / "artifacts" / "w5" / spec.accumulate_hw_op_id
    bitstreams = [
        (
            evidence_root / "encoder" / "encode-a" / f"accumulate_bitstream_{width}.bin",
            f"bitstreams/accumulate/accumulate_bitstream_{width}.bin",
        )
        for width in ("128b", "64b")
    ]
    parsed = [
        (
            evidence_root / "encoder" / "encode-a" / "parsed_bitstream.txt",
            "encoder_evidence/accumulate/parsed_bitstream.txt",
        )
    ]
    for shard_index in range(spec.requant_shard_count):
        shard_root = (
            evidence_root / "requant-encoder" / "encode-a" / f"shard-{shard_index:02d}"
        )
        bitstreams.extend(
            (
                shard_root / f"shard-{shard_index:02d}_bitstream_{width}.bin",
                f"bitstreams/requant/shard-{shard_index:02d}_bitstream_{width}.bin",
            )
            for width in ("128b", "64b")
        )
        parsed.append(
            (
                shard_root / "parsed_bitstream.txt",
                f"encoder_evidence/requant/shard-{shard_index:02d}/parsed_bitstream.txt",
            )
        )
    return bitstreams, parsed


def _candidate_encoder_sources(
    candidate_root: Path,
    request: ConvTargetRequest,
) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]]]:
    """Select run-A outputs from one independently validated native candidate."""

    manifest = _load_json(candidate_root / "candidate_manifest.json")
    records = manifest.get("records", [])
    by_artifact = {
        record.get("artifact_id"): record
        for record in records
        if isinstance(record, dict)
    }
    spec = request.spec
    expected = {"hwop-0004-00.config"} | {
        f"hwop-0004-01.shard-{index:02d}" for index in range(spec.requant_shard_count)
    }
    if set(by_artifact) != expected:
        raise ValueError("native encoder candidate artifact set differs")

    bitstreams: list[tuple[Path, str]] = []
    parsed: list[tuple[Path, str]] = []
    accumulate_root = candidate_root / by_artifact["hwop-0004-00.config"]["run_a_root"]
    for width in ("128b", "64b"):
        bitstreams.append(
            (
                accumulate_root / f"modules_dump_{width}.bin",
                f"bitstreams/accumulate/conv_1x1_real_bitstream_{width}.bin",
            )
        )
    parsed.append(
        (
            accumulate_root / "parsed_bitstream.txt",
            "encoder_evidence/accumulate/parsed_bitstream.txt",
        )
    )
    for shard_index in range(spec.requant_shard_count):
        record = by_artifact[f"hwop-0004-01.shard-{shard_index:02d}"]
        shard_root = candidate_root / record["run_a_root"]
        for width in ("128b", "64b"):
            bitstreams.append(
                (
                    shard_root / f"modules_dump_{width}.bin",
                    f"bitstreams/requant/shard-{shard_index:02d}_bitstream_{width}.bin",
                )
            )
        parsed.append(
            (
                shard_root / "parsed_bitstream.txt",
                f"encoder_evidence/requant/shard-{shard_index:02d}/parsed_bitstream.txt",
            )
        )
    return bitstreams, parsed


def _copy_native_candidate_tree(
    output_root: Path,
    candidate_root: Path,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for source in sorted(path for path in candidate_root.rglob("*") if path.is_file()):
        relative = source.relative_to(candidate_root).as_posix()
        records.append(
            _copy_relative(
                output_root,
                source,
                f"encoder_candidate/{relative}",
            )
        )
    return records


def _project_reference(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _build_bitstream_bindings(
    project_root: Path,
    output_root: Path,
    request: ConvTargetRequest,
    bitstream_sources: list[tuple[Path, str]],
    parsed_sources: list[tuple[Path, str]],
) -> dict[str, Any]:
    """Bind each current JSON to official encoder, freeze, and parsed evidence."""

    spec = request.spec
    source_by_relative = {relative: source for source, relative in bitstream_sources}
    parsed_by_relative = {relative: source for source, relative in parsed_sources}
    requant_manifest = _load_json(request.requant_manifest_path)
    encoder_contract_records: dict[int, dict[str, Any]] = {}
    requant_encoder_contract_sha256: str | None = None
    if spec.node_id == FIRST_REAL_CONV_NODE_ID:
        requant_encoder_contract = _load_json(request.requant_encoder_contract_path)
        encoder_contract_records = {
            int(item["shard_index"]): item
            for item in requant_encoder_contract.get("records", [])
            if isinstance(item, dict) and isinstance(item.get("shard_index"), int)
        }
        if len(encoder_contract_records) != spec.requant_shard_count:
            raise ValueError("requant encoder contract shard coverage differs")
        requant_encoder_contract_sha256 = _sha256(
            request.requant_encoder_contract_path.read_bytes()
        )
    shard_records = {
        int(item["shard_index"]): item for item in requant_manifest.get("shards", [])
    }
    records: list[dict[str, Any]] = []

    if spec.node_id == FIRST_REAL_CONV_NODE_ID:
        semantic_contract = _load_json(request.semantic_contract_path)
        expected_config = semantic_contract.get("config", {})
        expected_outputs = semantic_contract.get("official_encoder", {}).get(
            "outputs", {}
        )
        config_sha = _sha256(request.accumulate_config_path.read_bytes())
        if config_sha != expected_config.get("sha256"):
            raise ValueError("accumulate JSON differs from its semantic contract")
        accumulate_relative = (
            "bitstreams/accumulate/conv_1x1_real_bitstream_128b.bin"
        )
        source = source_by_relative[accumulate_relative]
        source_identity = bitstream_text_identity(source, line_width_bits=128)
        expected_bitstream = expected_outputs.get("modules_dump_128b.bin", {})
        extended_identity_fields = (
            "raw_size_bytes",
            "raw_sha256",
            "logical_size_bytes",
            "logical_sha256",
            "line_count",
            "line_width_bits",
        )
        declares_extended_identity = any(
            field in expected_bitstream for field in extended_identity_fields
        )
        extended_identity_differs = declares_extended_identity and (
            not all(field in expected_bitstream for field in extended_identity_fields)
            or any(
                source_identity[field] != expected_bitstream[field]
                for field in extended_identity_fields
            )
        )
        if (
            source_identity["raw_sha256"] != expected_bitstream.get("sha256")
            or source_identity["raw_size_bytes"] != expected_bitstream.get("size_bytes")
            or extended_identity_differs
        ):
            raise ValueError(
                "accumulate official encoder output differs from the semantic contract"
            )
        parsed_relative = "encoder_evidence/accumulate/parsed_bitstream.txt"
        parsed_source = parsed_by_relative[parsed_relative]
        expected_parsed = expected_outputs.get("parsed_bitstream.txt", {})
        if (
            _sha256(parsed_source.read_bytes()) != expected_parsed.get("sha256")
            or parsed_source.stat().st_size != expected_parsed.get("size_bytes")
        ):
            raise ValueError(
                "accumulate parsed evidence differs from the semantic contract"
            )
        frozen_identity = bitstream_text_identity(
            output_root / accumulate_relative, line_width_bits=128
        )
        require_same_logical_bitstream(
            source_identity, frozen_identity, label="accumulate freeze copy"
        )
        records.append(
            {
                "binding_id": f"{spec.accumulate_hw_op_id}.accumulate",
                "role": "accumulate",
                "config": {
                    "source_path": request.accumulate_config_relative,
                    "freeze_path": "configs/conv_1x1_real.json",
                    "sha256": config_sha,
                },
                "official_encoder": {
                    "source_path": _project_reference(project_root, source),
                    **source_identity,
                    "contract_raw_sha256": expected_bitstream["sha256"],
                },
                "parsed_evidence": {
                    "source_path": _project_reference(project_root, parsed_source),
                    "freeze_path": parsed_relative,
                    "sha256": _sha256(parsed_source.read_bytes()),
                },
                "freeze": {"path": accumulate_relative, **frozen_identity},
                "status": "json_official_encoder_freeze_bound",
            }
        )

    for shard_index in range(spec.requant_shard_count):
        relative = (
            f"bitstreams/requant/shard-{shard_index:02d}_bitstream_128b.bin"
        )
        source = source_by_relative[relative]
        official_modules = source.with_name("modules_dump_128b.bin")
        source_identity = bitstream_text_identity(source, line_width_bits=128)
        modules_identity = bitstream_text_identity(
            official_modules, line_width_bits=128
        )
        require_same_logical_bitstream(
            modules_identity,
            source_identity,
            label=f"requant shard-{shard_index:02d} encoder alias",
        )
        config_path = request.requant_root / f"shard-{shard_index:02d}.json"
        config_sha = _sha256(config_path.read_bytes())
        if config_sha != shard_records[shard_index].get("config_sha256"):
            raise ValueError(
                f"requant shard-{shard_index:02d} JSON differs from its manifest"
            )
        parsed_relative = (
            f"encoder_evidence/requant/shard-{shard_index:02d}/parsed_bitstream.txt"
        )
        parsed_source = parsed_by_relative[parsed_relative]
        if spec.node_id == FIRST_REAL_CONV_NODE_ID:
            encoder_contract_record = encoder_contract_records[shard_index]
            contract_config = encoder_contract_record.get("config", {})
            contract_outputs = encoder_contract_record.get("official_encoder", {})
            contract_modules = contract_outputs.get("modules_dump_128b.bin", {})
            contract_parsed = contract_outputs.get("parsed_bitstream.txt", {})
            if (
                encoder_contract_record.get("binding_id")
                != f"{spec.requant_hw_op_id}.shard-{shard_index:02d}"
                or encoder_contract_record.get("repeat_outputs_identical") is not True
                or contract_config.get("sha256") != config_sha
                or modules_identity != contract_modules
                or _sha256(parsed_source.read_bytes()) != contract_parsed.get("sha256")
                or parsed_source.stat().st_size != contract_parsed.get("size_bytes")
            ):
                raise ValueError(
                    f"requant shard-{shard_index:02d} differs from its independent encoder contract"
                )
        frozen_identity = bitstream_text_identity(
            output_root / relative, line_width_bits=128
        )
        require_same_logical_bitstream(
            source_identity,
            frozen_identity,
            label=f"requant shard-{shard_index:02d} freeze copy",
        )
        records.append(
            {
                "binding_id": f"{spec.requant_hw_op_id}.shard-{shard_index:02d}",
                "role": "requant",
                "shard_index": shard_index,
                "config": {
                    "source_path": request.requant_config_paths[shard_index]
                    .relative_to(project_root)
                    .as_posix(),
                    "freeze_path": f"configs/requant/shard-{shard_index:02d}.json",
                    "sha256": config_sha,
                },
                "official_encoder": {
                    "source_path": _project_reference(project_root, official_modules),
                    **modules_identity,
                    **(
                        {"encoder_contract_sha256": requant_encoder_contract_sha256}
                        if requant_encoder_contract_sha256 is not None
                        else {}
                    ),
                },
                "parsed_evidence": {
                    "source_path": _project_reference(project_root, parsed_source),
                    "freeze_path": parsed_relative,
                    "sha256": _sha256(parsed_source.read_bytes()),
                },
                "freeze": {"path": relative, **frozen_identity},
                "status": "json_official_encoder_freeze_bound",
            }
        )
    return {
        "schema_version": BITSTREAM_BINDING_SCHEMA_VERSION,
        "status": "json_official_encoder_freeze_bound",
        "record_count": len(records),
        "records": records,
    }


def export_hardware_freeze(
    project_root: Path,
    output_root: Path,
    *,
    node_id: str = FIRST_REAL_CONV_NODE_ID,
    preflight_path: Path | None = None,
    accumulate_encoder_root: Path | None = None,
    requant_encoder_root: Path | None = None,
    encoder_candidate_path: Path | None = None,
    revision: str | None = None,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    output_root = output_root.resolve()
    request = build_conv_target_request(project_root, node_id)
    spec = request.spec
    if spec.node_id == FIRST_REAL_CONV_NODE_ID and revision is None:
        frozen_v1_root = (
            project_root
            / "artifacts"
            / "w5"
            / spec.accumulate_hw_op_id
            / "hardware_freeze"
        )
        frozen_v1_manifest = _load_json(frozen_v1_root / "manifest.json")
        raw_identity = frozen_v1_manifest.get("identity")
        if not isinstance(raw_identity, dict):
            raise ValueError("first Conv frozen v1 identity is missing")
        if output_root != frozen_v1_root.resolve():
            _prepare_empty_output_root(output_root)
            shutil.copytree(frozen_v1_root, output_root, dirs_exist_ok=True)
        return frozen_v1_manifest
    if revision is not None and (not revision or "/" in revision or "\\" in revision):
        raise ValueError("hardware freeze revision must be one path-safe token")
    if encoder_candidate_path is not None and (
        accumulate_encoder_root is not None or requant_encoder_root is not None
    ):
        raise ValueError(
            "choose one encoder source: native candidate or legacy encoder roots"
        )
    if (
        spec.node_id == FIRST_REAL_CONV_NODE_ID
        and encoder_candidate_path is None
        and accumulate_encoder_root is None
    ):
        raise ValueError(
            "revised first-Conv freeze requires an explicit accumulate_encoder_root or native candidate"
        )
    if (
        spec.node_id == FIRST_REAL_CONV_NODE_ID
        and encoder_candidate_path is None
        and requant_encoder_root is None
    ):
        raise ValueError(
            "revised first-Conv freeze requires an explicit requant_encoder_root or native candidate"
        )
    _prepare_empty_output_root(output_root)
    selected_preflight = (preflight_path or request.preflight_path).resolve()
    preflight_payload = selected_preflight.read_bytes()
    preflight = json.loads(preflight_payload)
    freeze_status, ndp_source_commit, request_schema = _validate_freeze_source_preflight(
        request, preflight
    )
    native_candidate_binding: dict[str, Any] | None = None
    candidate_root: Path | None = None
    if encoder_candidate_path is not None:
        selected_candidate = encoder_candidate_path.resolve()
        candidate_root = (
            selected_candidate.parent if selected_candidate.is_file() else selected_candidate
        )
        typed_request_sha256 = str(
            preflight.get("target_configuration", {})
            .get("typed_execplan_transport", {})
            .get("sha256", "")
        )
        native_candidate_binding = _bind_native_encoder_candidate(
            project_root,
            project_root / "ndp-sim-ref",
            candidate_root,
            expected_node_id=spec.node_id,
            expected_typed_request_sha256=typed_request_sha256,
        )
        preflight_binding = preflight.get("native_encoder_candidate")
        required_match_fields = (
            "candidate_id",
            "manifest_sha256",
            "validation_report_id",
            "validation_report_sha256",
            "candidate_tree_sha256",
            "candidate_tree_file_count",
            "typed_request_sha256",
            "native_source_tree_sha256",
            "address_plan_sha256",
            "address_plan_size_bytes",
            "record_count",
        )
        if not isinstance(preflight_binding, dict) or any(
            preflight_binding.get(field) != native_candidate_binding.get(field)
            for field in required_match_fields
        ):
            raise ValueError(
                "config-bound preflight is not bound to the selected native candidate"
            )

    values, bundle = _selected_bundle(project_root, request)
    files: list[dict[str, Any]] = []
    regions: list[dict[str, Any]] = []
    for region in bundle.regions:
        relative = f"physical/{region.port}/slice-{region.slice_id:02d}.bin"
        file_record = _write_relative(
            output_root,
            relative,
            bundle.read(region.port, region.slice_id),
        )
        files.append(file_record)
        regions.append(
            {
                "port": region.port,
                "slice_id": region.slice_id,
                "role": "load_input" if region.port in INPUT_PORTS else "golden_output",
                "base_address": region.base_address,
                "base_address_hex": f"0x{region.base_address:08x}",
                "payload_bytes": region.payload_bytes,
                "size_bytes": region.size_bytes,
                "physical_shape": list(region.physical_shape),
                "dtype": bundle.plan.port(region.port).dtype,
                "sample_start": region.sample_start,
                "sample_count": region.sample_count,
                "logical_start": region.logical_start,
                "logical_count": region.logical_count,
                "file": file_record,
            }
        )

    requant_manifest = _load_json(request.requant_manifest_path)
    staged_base = int(requant_manifest["physical_layout"]["staged_d_offset"])
    staged_bytes = int(requant_manifest["physical_layout"]["staged_half_bytes"])
    staged_offsets = [
        staged_base + index * staged_bytes
        for index in range(spec.requant_shards_per_owner)
    ]
    for slice_id in range(bundle.plan.geometry.slice_count):
        slice_base = bundle.plan.geometry.slice_base(slice_id)
        for local_half, offset in enumerate(staged_offsets):
            regions.append(
                {
                    "port": f"staged_D_{local_half}",
                    "slice_id": slice_id,
                    "role": "hardware_output",
                    "base_address": slice_base + offset,
                    "base_address_hex": f"0x{slice_base + offset:08x}",
                    "payload_bytes": requant_manifest["physical_layout"]["staged_half_bytes"],
                    "size_bytes": requant_manifest["physical_layout"]["staged_half_bytes"],
                    "physical_shape": [
                        spec.first_group_sample_count,
                        spec.output_height,
                        spec.output_width,
                        spec.ga_lane_count,
                    ],
                    "dtype": "uint8",
                }
            )

    canonical_golden: dict[str, Any] = {}
    for port in ("P", "D"):
        value = np.ascontiguousarray(values[port])
        record = _write_relative(
            output_root,
            f"golden/canonical_{port}.bin",
            value.tobytes(order="C"),
        )
        record.update({"dtype": str(value.dtype), "shape": list(value.shape)})
        canonical_golden[port] = record
        files.append(record)

    comparison_root = preflight.get("ndp_target_config_comparison")
    if not isinstance(comparison_root, dict):
        comparison_root = preflight.get("config_bound_comparison", {})
    ordered_comparisons = comparison_root.get("ordered_comparisons", [])
    full_operator = next(
        (
            item
            for item in ordered_comparisons
            if isinstance(item, dict) and item.get("name") == "full_operator"
        ),
        None,
    )
    if not isinstance(full_operator, dict):
        raise ValueError("preflight lacks the full-operator NDP comparison")
    config_bound_ndp: dict[str, Any] = {
        "preflight_sha256": _sha256(preflight_payload),
        "comparison_name": "full_operator",
        "ports": {},
        "status": "golden_and_ndp_bit_exact",
    }
    for port in ("P", "D"):
        ndp_record = full_operator.get(port)
        golden_record = canonical_golden[port]
        if (
            not isinstance(ndp_record, dict)
            or int(ndp_record.get("mismatch_count", -1)) != 0
            or ndp_record.get("actual_sha256") != ndp_record.get("golden_sha256")
            or ndp_record.get("golden_sha256") != golden_record["sha256"]
            or int(ndp_record.get("element_count", -1))
            != math.prod(int(value) for value in golden_record["shape"])
        ):
            raise ValueError(
                f"preflight full-operator NDP {port} differs from the frozen golden"
            )
        config_bound_ndp["ports"][port] = dict(ndp_record)
    preflight_record = _copy_relative(
        output_root, selected_preflight, "evidence/source_preflight.json"
    )
    files.append(preflight_record)

    config_records = []
    accumulate_config_relative = (
        "configs/conv_1x1_real.json"
        if spec.node_id == FIRST_REAL_CONV_NODE_ID
        else "configs/accumulate.json"
    )
    config_sources = [
        (request.accumulate_config_path, accumulate_config_relative),
        (
            request.requant_manifest_path,
            "configs/requant/manifest.json",
        ),
        *[
            (
                request.requant_root / f"shard-{index:02d}.json",
                f"configs/requant/shard-{index:02d}.json",
            )
            for index in range(spec.requant_shard_count)
        ],
    ]
    if spec.node_id == FIRST_REAL_CONV_NODE_ID:
        config_sources.append(
            (
                request.requant_encoder_contract_path,
                "configs/requant/encoder_contract.json",
            )
        )
    for source, relative in config_sources:
        record = _copy_relative(output_root, source, relative)
        config_records.append(record)
        files.append(record)

    bitstream_records = []
    if candidate_root is not None:
        candidate_records = _copy_native_candidate_tree(output_root, candidate_root)
        validation_report_path = (
            candidate_root.parent / f"{candidate_root.name}.validation.json"
        )
        validation_record = _copy_relative(
            output_root,
            validation_report_path,
            "encoder_candidate/validation_report.json",
        )
        if (
            native_candidate_binding is None
            or validation_record["sha256"]
            != native_candidate_binding["validation_report_sha256"]
        ):
            raise ValueError(
                "copied native candidate validation report differs from preflight"
            )
        candidate_records.append(validation_record)
        files.extend(candidate_records)
        bitstream_sources, parsed_sources = _candidate_encoder_sources(
            candidate_root, request
        )
    else:
        candidate_records = []
        bitstream_sources, parsed_sources = _encoder_sources(
            project_root,
            request,
            accumulate_encoder_root,
            requant_encoder_root,
        )
    for source, relative in bitstream_sources:
        record = _copy_relative(output_root, source, relative)
        bitstream_records.append(record)
        files.append(record)
    encoder_evidence_records = []
    for source, relative in parsed_sources:
        record = _copy_relative(output_root, source, relative)
        encoder_evidence_records.append(record)
        files.append(record)
    try:
        bitstream_bindings = _build_bitstream_bindings(
            project_root,
            output_root,
            request,
            bitstream_sources,
            parsed_sources,
        )
    except BitstreamBindingError as error:
        raise ValueError(str(error)) from error

    address_payload = (
        json.dumps(
            {"schema_version": "0.1", "regions": regions},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    if native_candidate_binding is not None and (
        _sha256(address_payload) != native_candidate_binding["address_plan_sha256"]
        or len(address_payload) != native_candidate_binding["address_plan_size_bytes"]
    ):
        raise ValueError(
            "freeze address table differs from the native candidate address plan"
        )
    address_table = _write_relative(output_root, "address_table.json", address_payload)
    files.append(address_table)

    comparison_tool_path = project_root / "tools" / "compare_conv_1x1_hardware_dump.py"
    comparison_tool = {
        "path": "tools/compare_conv_1x1_hardware_dump.py",
        "sha256": _sha256(comparison_tool_path.read_bytes()),
        "dump_convention": "<dump-root>/P/slice-XX.bin and <dump-root>/D/slice-XX.bin",
    }
    identity = {
        "node_id": spec.node_id,
        "hw_op_ids": [spec.accumulate_hw_op_id, spec.requant_hw_op_id],
        "preflight_sha256": _sha256(preflight_payload),
        "ndp_source_commit": ndp_source_commit,
        "request_schema": request_schema,
    }
    if revision is not None:
        identity["revision"] = revision
    if native_candidate_binding is not None:
        identity.update(
            {
                "native_encoder_candidate_id": native_candidate_binding[
                    "candidate_id"
                ],
                "native_encoder_source_tree_sha256": native_candidate_binding[
                    "native_source_tree_sha256"
                ],
                "native_address_plan_sha256": native_candidate_binding[
                    "address_plan_sha256"
                ],
            }
        )
    manifest = {
        "schema_version": FREEZE_SCHEMA_VERSION,
        "contract_type": (
            FREEZE_CONTRACT_TYPE
            if spec.node_id == FIRST_REAL_CONV_NODE_ID and revision is None
            else CANDIDATE_FREEZE_CONTRACT_TYPE
        ),
        "status": freeze_status,
        "identity": identity,
        "layout": {
            "profile_id": bundle.plan.profile_id,
            "slice_count": bundle.plan.geometry.slice_count,
            "per_slice_used_bytes": bundle.plan.per_slice_used_bytes,
            "staged_d_offsets": staged_offsets,
            "staged_half_bytes": staged_bytes,
        },
        "configs": config_records,
        "bitstreams": bitstream_records,
        "bitstream_bindings": bitstream_bindings,
        "address_table": address_table,
        "canonical_golden": canonical_golden,
        "config_bound_ndp": config_bound_ndp,
        "comparison_tool": comparison_tool,
        "files": sorted(files, key=lambda item: item["path"]),
    }
    if native_candidate_binding is not None:
        manifest["native_encoder_candidate"] = {
            **native_candidate_binding,
            "freeze_root": "encoder_candidate/",
            "frozen_file_count": len(candidate_records),
        }
    if encoder_evidence_records:
        manifest["encoder_evidence"] = encoder_evidence_records
    manifest["freeze_id"] = _freeze_id(manifest)
    manifest_payload = (
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    _write_bytes(output_root / "manifest.json", manifest_payload)
    expected_files = {str(item["path"]) for item in manifest["files"]}
    if len(expected_files) != len(manifest["files"]):
        raise ValueError("generated hardware freeze contains duplicate manifest file paths")
    expected_files.add("manifest.json")
    actual_files: set[str] = set()
    for path in output_root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"generated hardware freeze contains a symlink: {path}")
        if path.is_file():
            actual_files.add(path.relative_to(output_root).as_posix())
    if actual_files != expected_files:
        raise ValueError(
            "generated hardware freeze file exact-set differs: "
            f"missing={sorted(expected_files - actual_files)}, "
            f"extra={sorted(actual_files - expected_files)}"
        )
    return manifest


def _inverse_port(
    manifest: dict[str, Any],
    dump_root: Path,
    port: str,
) -> np.ndarray:
    golden = manifest["canonical_golden"][port]
    dtype = np.dtype(golden["dtype"])
    shape = tuple(int(item) for item in golden["shape"])
    result = np.zeros(shape, dtype=dtype)
    filled = np.zeros(shape, dtype=np.bool_)
    address_table = json.loads(
        (Path(manifest["_freeze_root"]) / manifest["address_table"]["path"]).read_text(
            encoding="utf-8"
        )
    )
    for region in address_table["regions"]:
        if region["port"] != port:
            continue
        path = dump_root / port / f"slice-{int(region['slice_id']):02d}.bin"
        payload = path.read_bytes()
        if len(payload) != int(region["size_bytes"]):
            raise ValueError(f"hardware dump size differs: {path}")
        local = np.frombuffer(
            payload[: int(region["payload_bytes"])], dtype=dtype
        ).reshape(tuple(int(item) for item in region["physical_shape"]))
        n_start = int(region["sample_start"])
        n_count = int(region["sample_count"])
        k_start = int(region["logical_start"])
        k_count = int(region["logical_count"])
        if local.ndim == 6:
            # Hardware P/D is NH-Qblock-Q8-Kblock-K8.  Reconstruct the
            # canonical NCHW tensor while discarding only explicit Q/K tails.
            flat = local.reshape(
                local.shape[0],
                local.shape[1],
                local.shape[2] * local.shape[3],
                local.shape[4] * local.shape[5],
            )
            logical = flat[
                :n_count,
                : shape[2],
                : shape[3],
                :k_count,
            ].transpose(0, 3, 1, 2)
        else:
            logical = local[:n_count, ..., :k_count].transpose(0, 3, 1, 2)
        target = np.s_[
            n_start : n_start + n_count,
            k_start : k_start + k_count,
            :,
            :,
        ]
        if np.any(filled[target]):
            raise ValueError(f"hardware dump overlaps canonical {port}")
        result[target] = logical
        filled[target] = True
    if not np.all(filled):
        raise ValueError(f"hardware dump does not cover canonical {port}")
    return result


def compare_hardware_dump(freeze_root: Path, dump_root: Path) -> dict[str, Any]:
    freeze_root = freeze_root.resolve()
    manifest = json.loads((freeze_root / "manifest.json").read_text(encoding="utf-8"))
    raw_file_records = manifest.get("files")
    if not isinstance(raw_file_records, list):
        raise ValueError("freeze manifest file identities are missing")
    file_identities: dict[str, dict[str, Any]] = {}
    for item in raw_file_records:
        if not isinstance(item, dict):
            raise ValueError("freeze manifest file identity is malformed")
        relative = item.get("path")
        if not isinstance(relative, str) or relative in file_identities:
            raise ValueError("freeze manifest file identity path is malformed")
        file_identities[relative] = item
    manifest["_freeze_root"] = str(freeze_root)
    comparisons = {}
    for port in ("P", "D"):
        actual = np.ascontiguousarray(_inverse_port(manifest, dump_root.resolve(), port))
        golden_record = manifest["canonical_golden"][port]
        golden_payload = (freeze_root / golden_record["path"]).read_bytes()
        if _sha256(golden_payload) != golden_record["sha256"]:
            raise ValueError(f"frozen canonical {port} hash differs")
        golden = np.frombuffer(golden_payload, dtype=np.dtype(golden_record["dtype"])).reshape(
            tuple(int(item) for item in golden_record["shape"])
        )
        mismatches = np.argwhere(actual != golden)
        first = None
        if mismatches.size:
            coordinate = tuple(int(item) for item in mismatches[0])
            first = {
                "coordinate": list(coordinate),
                "actual": int(actual[coordinate]),
                "golden": int(golden[coordinate]),
            }
        comparisons[port] = {
            "element_count": int(actual.size),
            "mismatch_count": int(len(mismatches)),
            "actual_sha256": _sha256(actual.tobytes(order="C")),
            "golden_sha256": golden_record["sha256"],
            "first_mismatch": first,
        }
    physical_comparisons: dict[str, Any] = {}
    for port in ("P", "D"):
        records: list[dict[str, Any]] = []
        total_bytes = 0
        mismatch_bytes = 0
        for slice_id in range(int(manifest["layout"]["slice_count"])):
            expected_relative = f"physical/{port}/slice-{slice_id:02d}.bin"
            expected_path = freeze_root / expected_relative
            actual_path = dump_root.resolve() / port / f"slice-{slice_id:02d}.bin"
            expected_payload = expected_path.read_bytes()
            actual_payload = actual_path.read_bytes()
            expected_identity = file_identities.get(expected_relative)
            expected_sha256 = _sha256(expected_payload)
            if (
                not isinstance(expected_identity, dict)
                or expected_identity.get("size_bytes") != len(expected_payload)
                or expected_identity.get("sha256") != expected_sha256
            ):
                raise ValueError(
                    f"frozen physical {port} identity differs: {expected_relative}"
                )
            if len(actual_payload) != len(expected_payload):
                raise ValueError(f"physical hardware dump size differs: {actual_path}")
            local_mismatch = sum(
                left != right
                for left, right in zip(expected_payload, actual_payload, strict=True)
            )
            first_offset = next(
                (
                    offset
                    for offset, (left, right) in enumerate(
                        zip(expected_payload, actual_payload, strict=True)
                    )
                    if left != right
                ),
                None,
            )
            records.append(
                {
                    "slice_id": slice_id,
                    "size_bytes": len(actual_payload),
                    "mismatch_byte_count": local_mismatch,
                    "actual_sha256": _sha256(actual_payload),
                    "golden_sha256": expected_sha256,
                    "first_mismatch_byte_offset": first_offset,
                }
            )
            total_bytes += len(actual_payload)
            mismatch_bytes += local_mismatch
        physical_comparisons[port] = {
            "slice_count": len(records),
            "byte_count": total_bytes,
            "mismatch_byte_count": mismatch_bytes,
            "slices": records,
        }
    ndp_binding = manifest.get("config_bound_ndp")
    if (
        not isinstance(ndp_binding, dict)
        or ndp_binding.get("status") != "golden_and_ndp_bit_exact"
        or not isinstance(ndp_binding.get("ports"), dict)
    ):
        raise ValueError("freeze lacks a verified config-bound NDP comparison")
    three_way: dict[str, Any] = {}
    for port in ("P", "D"):
        ndp_record = ndp_binding["ports"].get(port)
        hardware_record = comparisons[port]
        if (
            not isinstance(ndp_record, dict)
            or int(ndp_record.get("mismatch_count", -1)) != 0
            or ndp_record.get("actual_sha256") != hardware_record["golden_sha256"]
        ):
            raise ValueError(f"freeze config-bound NDP {port} identity differs")
        three_way[port] = {
            "golden_vs_ndp": {
                "mismatch_count": int(ndp_record["mismatch_count"]),
                "golden_sha256": ndp_record["golden_sha256"],
                "ndp_sha256": ndp_record["actual_sha256"],
            },
            "golden_vs_hardware": {
                "mismatch_count": hardware_record["mismatch_count"],
                "golden_sha256": hardware_record["golden_sha256"],
                "hardware_sha256": hardware_record["actual_sha256"],
            },
            "ndp_vs_hardware": {
                "mismatch_count": hardware_record["mismatch_count"],
                "ndp_sha256": ndp_record["actual_sha256"],
                "hardware_sha256": hardware_record["actual_sha256"],
                "basis": "golden_ndp_bit_exact_then_direct_hardware_golden_compare",
            },
        }
    passed = (
        all(item["mismatch_count"] == 0 for item in comparisons.values())
        and all(
            item["mismatch_byte_count"] == 0
            for item in physical_comparisons.values()
        )
    )
    return {
        "status": "passed" if passed else "mismatch",
        "freeze_id": manifest["freeze_id"],
        "comparisons": comparisons,
        "physical_byte_comparisons": physical_comparisons,
        "three_way_comparisons": three_way,
    }


__all__ = [
    "FREEZE_CONTRACT_TYPE",
    "CANDIDATE_FREEZE_CONTRACT_TYPE",
    "FREEZE_SCHEMA_VERSION",
    "compare_hardware_dump",
    "export_hardware_freeze",
]
