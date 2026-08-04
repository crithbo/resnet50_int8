#!/usr/bin/env python3
"""Audit the senior-authored Conv JSON and build a diagnostic test bundle.

This tool deliberately stops before the formal server-package lifecycle.  The
senior JSON can be repaired enough for deterministic official encoding, but it
does not satisfy the current RTL28 Conv transport contract and therefore must
not be wrapped in a runnable server overlay.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_JSON = ROOT / ".agents" / "conv_full(2).json"
ORIGINAL_PSEUDOCODE = ROOT / ".agents" / "conv_full(2).txt"
REPAIRED_JSON = ROOT / "conv_full.json"
REPAIRED_PSEUDOCODE = ROOT / "conv_full.txt"
ENCODER_EVIDENCE = ROOT / "contracts" / "conv_full_encoder_evidence.json"
MODEL_GRAPH = ROOT / "artifacts" / "w3" / "model_graph.json"
BUNDLE_NAME = "senior_conv_3x3_encoder_test_v1"


class SeniorConvAuditError(ValueError):
    pass


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise SeniorConvAuditError(f"JSON root is not an object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def semantic_leaf_differences(
    left: Any, right: Any, path: str = "$"
) -> list[dict[str, Any]]:
    differences: list[dict[str, Any]] = []
    if type(left) is not type(right):
        return [
            {
                "path": path,
                "kind": "type_changed",
                "original": type(left).__name__,
                "repaired": type(right).__name__,
            }
        ]
    if isinstance(left, dict):
        for key in sorted(set(left) | set(right)):
            child = f"{path}.{key}"
            if key not in left:
                differences.append(
                    {"path": child, "kind": "added", "repaired": right[key]}
                )
            elif key not in right:
                differences.append(
                    {"path": child, "kind": "removed", "original": left[key]}
                )
            else:
                differences.extend(
                    semantic_leaf_differences(left[key], right[key], child)
                )
        return differences
    if isinstance(left, list):
        if len(left) != len(right):
            differences.append(
                {
                    "path": path,
                    "kind": "length_changed",
                    "original": len(left),
                    "repaired": len(right),
                }
            )
        for index, (left_item, right_item) in enumerate(zip(left, right, strict=False)):
            differences.extend(
                semantic_leaf_differences(
                    left_item, right_item, f"{path}[{index}]"
                )
            )
        return differences
    if left != right:
        differences.append(
            {
                "path": path,
                "kind": "value_changed",
                "original": left,
                "repaired": right,
            }
        )
    return differences


def _resolved_shape(shape: Any) -> list[Any]:
    if not isinstance(shape, list):
        return []
    return [16 if item == "N" else item for item in shape]


def matching_resnet_nodes(model_graph: dict[str, Any]) -> list[dict[str, Any]]:
    tensors = {
        item["tensor_id"]: item
        for item in model_graph.get("tensors", [])
        if isinstance(item, dict) and isinstance(item.get("tensor_id"), str)
    }
    matches: list[dict[str, Any]] = []
    expected_attributes = {
        "kernel_shape": [3, 3],
        "strides": [1, 1],
        "pads": [1, 1, 1, 1],
        "dilations": [1, 1],
        "group": 1,
    }
    for node in model_graph.get("nodes", []):
        if not isinstance(node, dict) or node.get("op_type") != "QLinearConv":
            continue
        inputs = node.get("input_tensor_ids", [])
        outputs = node.get("output_tensor_ids", [])
        if len(inputs) < 4 or len(outputs) != 1:
            continue
        activation_shape = _resolved_shape(tensors.get(inputs[0], {}).get("shape"))
        weight_shape = _resolved_shape(tensors.get(inputs[3], {}).get("shape"))
        output_shape = _resolved_shape(tensors.get(outputs[0], {}).get("shape"))
        attributes = node.get("attributes", {})
        if (
            activation_shape != [16, 64, 56, 56]
            or weight_shape != [64, 64, 3, 3]
            or output_shape != [16, 64, 56, 56]
            or any(attributes.get(key) != value for key, value in expected_attributes.items())
        ):
            continue
        matches.append(
            {
                "node_id": node["node_id"],
                "onnx_name": node["onnx_name"],
                "op_type": node["op_type"],
                "activation_shape": activation_shape,
                "weight_shape": weight_shape,
                "output_shape": output_shape,
                "attributes": {key: attributes[key] for key in expected_attributes},
                "lowering": [
                    f"hwop-{node['node_id'].removeprefix('node-')}-00",
                    f"hwop-{node['node_id'].removeprefix('node-')}-01",
                ],
            }
        )
    return matches


def _capture_check(name: str, callback: Callable[[], Any]) -> dict[str, Any]:
    try:
        result = callback()
    except Exception as error:  # The exact fail-closed reason is audit evidence.
        return {
            "check": name,
            "status": "failed",
            "exception": type(error).__name__,
            "reason": str(error),
        }
    return {"check": name, "status": "passed", "result": result}


def current_contract_audit(config: dict[str, Any]) -> list[dict[str, Any]]:
    from resnet50_pipeline.conv_instance import (
        validate_conv_accumulate_config_mask,
        validate_conv_accumulate_neighbor_ring,
        validate_conv_accumulate_output_route,
    )
    from resnet50_pipeline.conv_sa_contract import validate_first_conv_sa_contract

    return [
        _capture_check(
            "special_array_output_route",
            lambda: validate_conv_accumulate_output_route(config),
        ),
        _capture_check(
            "sa_only_presence_mask",
            lambda: validate_conv_accumulate_config_mask(config),
        ),
        _capture_check(
            "high4_neighbor_ring",
            lambda: validate_conv_accumulate_neighbor_ring(
                config, expected_group_size=4
            ),
        ),
        _capture_check(
            "current_q8k8_stream_bias_contract",
            lambda: validate_first_conv_sa_contract(config),
        ),
    ]


def known_issues() -> list[dict[str, str]]:
    return [
        {
            "code": "E_PLACEMENT_ORIGINAL",
            "severity": "blocking",
            "summary": "The original 44-connection graph cannot be placed by the official encoder.",
        },
        {
            "code": "E_INVALID_LC_PE_SOURCE",
            "severity": "blocking",
            "summary": "LC_PE.LC8 is not a valid source; the reviewed repair uses DRAM_LC.LC8.",
        },
        {
            "code": "E_BUFFER_GROUP_CROSS_REFERENCE",
            "severity": "blocking",
            "summary": "GROUP2/GROUP3 column loops cross-reference the other group's row loop.",
        },
        {
            "code": "E_OUTPUT_PRODUCER",
            "severity": "blocking",
            "summary": "buffer5.dst_port=1 selects GeneArray although this is an SA-only program.",
        },
        {
            "code": "E_OUTPUT_MAJOR_LABEL",
            "severity": "blocking",
            "summary": "JSON row encodes RTL col-major; the reviewed GEMM repair uses JSON col / RTL major bit 0.",
        },
        {
            "code": "E_OLD_16_SLICE_RING",
            "severity": "blocking",
            "summary": "neighbor_stream1 uses mem_loop=16 and selector 0, not the approved HIGH-4 4/1/1 contract.",
        },
        {
            "code": "E_NEIGHBOR_BUFFER_PAIR",
            "severity": "blocking",
            "summary": "The selected neighbor stream does not enable both buffers in its ping-pong pair.",
        },
        {
            "code": "E_STREAM_TRANSACTION_ABI",
            "severity": "blocking",
            "summary": "The repaired skeleton still encodes 128B/4B/4B/128B stream transactions instead of the current 32B Q8K8 contract.",
        },
        {
            "code": "E_BIAS_TILE_HANDSHAKE",
            "severity": "blocking",
            "summary": "Bias is K-only with buffer lifetime 1; current RTL requires one row per Kblock/H/Qblock tile and four SA handshakes.",
        },
        {
            "code": "E_PORT_ROLE_ABI",
            "severity": "blocking",
            "summary": "The senior pseudocode treats A as weight and B as activation, opposite to the current project ABI.",
        },
        {
            "code": "E_STATIC_SHAPE_PLACEHOLDERS",
            "severity": "blocking",
            "summary": "Loop ends and base addresses are static placeholders, not a typed node-0005 address plan.",
        },
        {
            "code": "E_INCOMPLETE_QLINEARCONV",
            "severity": "blocking",
            "summary": "The JSON contains only INT8 SA accumulation; it has no node-specific per-channel requant configuration.",
        },
        {
            "code": "E_BATCH_AND_PADDING_TRANSPORT",
            "severity": "blocking",
            "summary": "B=1 pseudocode and its padding coordinates do not implement the batch-16 three-wave RTL28 transport contract.",
        },
    ]


def _run(command: list[str], *, cwd: Path = ROOT) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return {
        "command": command,
        "cwd": str(cwd),
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def summarize_bitstream(path: Path, width: int) -> dict[str, Any]:
    payload = path.read_bytes()
    text = payload.decode("ascii")
    lines = text.splitlines()
    if not lines or any(len(line) != width or set(line) - {"0", "1"} for line in lines):
        raise SeniorConvAuditError(f"invalid {width}-bit bitstream: {path}")
    normalized = ("\n".join(lines) + "\n").encode("ascii")
    return {
        "path": path.name,
        "raw_size_bytes": len(payload),
        "raw_sha256": hashlib.sha256(payload).hexdigest(),
        "line_count": len(lines),
        "line_width_bits": width,
        "normalized_lf_size_bytes": len(normalized),
        "normalized_logical_sha256": hashlib.sha256(normalized).hexdigest(),
    }


def _numeric_probe() -> dict[str, Any]:
    from resnet50_pipeline.adapters.ndp_rtl28_functional import (
        NdpRtl28FunctionalAdapter,
    )
    from resnet50_pipeline.conv_instance import load_conv_instance_spec
    from resnet50_pipeline.w5_conv_preflight import load_conv_instance_execution

    node_id = "node-0005"
    spec = load_conv_instance_spec(ROOT, node_id)
    values, layout, bundle = load_conv_instance_execution(ROOT, spec)
    coordinates = ((0, 0, 0, 0), (0, 0, 0, 55), (0, 0, 27, 27), (15, 63, 55, 55))
    adapter = NdpRtl28FunctionalAdapter(
        ROOT / "NDPFuncModel",
        python_executable=Path(sys.executable),
        timeout_seconds=120,
    )
    result = adapter.run_qlinear_conv_coordinates(
        layout,
        bundle,
        coordinates,
        strides=spec.strides,
        pads=spec.pads,
        dilations=spec.dilations,
    )
    expected_p = layout.inverse_port(bundle, "P")
    expected_d = layout.inverse_port(bundle, "D")
    records = []
    for coordinate, accumulator, output in zip(
        coordinates, result.accumulators, result.outputs, strict=True
    ):
        record = {
            "coordinate": list(coordinate),
            "golden_p": int(expected_p[coordinate]),
            "ndp_p": int(accumulator),
            "golden_d": int(expected_d[coordinate]),
            "ndp_d": int(output),
        }
        record["p_match"] = record["golden_p"] == record["ndp_p"]
        record["d_match"] = record["golden_d"] == record["ndp_d"]
        records.append(record)
    return {
        "status": (
            "passed" if all(item["p_match"] and item["d_match"] for item in records) else "failed"
        ),
        "scope": "geometry/layout/NDP arithmetic only; not target-JSON or bitstream execution",
        "node_id": node_id,
        "onnx_name": spec.onnx_name,
        "geometry": spec.to_dict()["geometry"],
        "records": records,
    }


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _copy_tree_files(source: Path, destination: Path) -> None:
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise SeniorConvAuditError(f"refusing to package symlink: {path}")
        if path.is_file():
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def _readme(report: dict[str, Any]) -> str:
    matches = ", ".join(item["node_id"] for item in report["resnet50_matches"])
    bitstream = report["repaired_encoder"]["bitstream_128b"]
    return f"""Senior Conv 3x3 encoder diagnostic bundle v1

Outcome
=======

The original senior-authored JSON fails the official encoder placement step.
The reviewed structural repair encodes twice with identical output, producing
{bitstream['line_count']} x 128-bit logical lines with normalized SHA-256
{bitstream['normalized_logical_sha256']}.

The declared geometry exactly matches ResNet50 nodes {matches}.  A bounded
node-0005 test using formal W3 values, the RTL28 physical layout, and
NDPFuncModel passes P/D bit-exact at four representative coordinates.

Important boundary
==================

This ZIP is an encoder/diagnostic test bundle, not an NDP server overlay.  The
structurally repaired JSON still violates the current HIGH-4 stream, bias,
batch, padding, typed-address and requant contracts.  The formal project
generator therefore rejects node-0005 before freeze/package creation.  Do not
upload this ZIP as RUN_SERVER input and do not interpret encoder success as
hardware numerical success.

Contents
========

- source/: untouched senior originals plus the reviewed structural repair.
- encoder/original/: expected failed placement evidence.
- encoder/repaired_a and repaired_b/: two official deterministic encoder runs.
- evidence/audit_report.json: full issue, model-match and lifecycle report.
- evidence/numeric_probe.json: bounded Golden/NDP P/D comparison.
- logs/: captured command output.
- MANIFEST.json: exact file size and SHA-256 contract.
"""


def build(output: Path) -> dict[str, Any]:
    output = output.resolve()
    if output.exists():
        raise FileExistsError(f"refusing to replace existing output: {output}")
    output.mkdir(parents=True)
    work = output / "work"
    work.mkdir()

    original_output = work / "original_encoder"
    original_run = _run(
        [
            sys.executable,
            "-X",
            "utf8",
            "bitstream/main.py",
            "-c",
            str(ORIGINAL_JSON),
            "-o",
            str(original_output),
            "--heuristic-iterations",
            "5000",
            "--heuristic-restarts",
            "1",
            "--seed",
            "17",
            "--visualize-placement",
            "-q",
        ],
        cwd=ROOT / "ndp-sim-ref",
    )
    if original_run["exit_code"] == 0:
        raise SeniorConvAuditError("original senior JSON unexpectedly encoded")

    repaired_runs = []
    repaired_outputs = []
    for label in ("a", "b"):
        encoder_output = work / f"repaired_{label}"
        run = _run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(ROOT / "tools" / "run_conv_full_encoder.py"),
                "--output",
                str(encoder_output),
            ]
        )
        if run["exit_code"] != 0:
            raise SeniorConvAuditError(
                f"reviewed repair encoder run {label} failed: {run['stderr']}"
            )
        repaired_runs.append(run)
        repaired_outputs.append(encoder_output)

    names_a = {path.name for path in repaired_outputs[0].iterdir() if path.is_file()}
    names_b = {path.name for path in repaired_outputs[1].iterdir() if path.is_file()}
    if names_a != names_b:
        raise SeniorConvAuditError("repaired A/B encoder output sets differ")
    ab_records = []
    for name in sorted(names_a):
        left = repaired_outputs[0] / name
        right = repaired_outputs[1] / name
        record = {
            "path": name,
            "run_a_sha256": sha256_file(left),
            "run_b_sha256": sha256_file(right),
            "equal": left.read_bytes() == right.read_bytes(),
        }
        ab_records.append(record)
    if not all(item["equal"] for item in ab_records):
        raise SeniorConvAuditError("repaired official encoder A/B outputs differ")

    formal_attempt = _run(
        [
            sys.executable,
            "-X",
            "utf8",
            str(ROOT / "tools" / "generate_conv_instance.py"),
            "--node-id",
            "node-0005",
            "--check",
        ]
    )
    if formal_attempt["exit_code"] == 0:
        raise SeniorConvAuditError(
            "formal node-0005 generator unexpectedly accepted a 3x3 instance"
        )

    original = _load_object(ORIGINAL_JSON)
    repaired = _load_object(REPAIRED_JSON)
    numeric_probe = _numeric_probe()
    if numeric_probe["status"] != "passed":
        raise SeniorConvAuditError("node-0005 bounded numerical probe failed")
    report: dict[str, Any] = {
        "schema_version": "senior-conv-operator-audit-0.1",
        "status": "encoder_candidate_passed_formal_server_package_blocked",
        "branch_scope": "isolated senior 3x3 Conv investigation",
        "source_identity": {
            "original_json_sha256": sha256_file(ORIGINAL_JSON),
            "original_pseudocode_sha256": sha256_file(ORIGINAL_PSEUDOCODE),
            "repaired_json_sha256": sha256_file(REPAIRED_JSON),
            "repaired_pseudocode_sha256": sha256_file(REPAIRED_PSEUDOCODE),
        },
        "semantic_leaf_differences": semantic_leaf_differences(original, repaired),
        "known_issues": known_issues(),
        "current_contract_audit": {
            "original": current_contract_audit(original),
            "structural_repair": current_contract_audit(repaired),
        },
        "original_encoder": {
            "status": "expected_failure_reproduced",
            "exit_code": original_run["exit_code"],
            "connection_count": 44,
            "expected_failure_markers": [
                "mapping violations remain",
                "Source node 'LC_PE.LC8' not found in mapping",
            ],
        },
        "repaired_encoder": {
            "status": "official_encoder_double_run_identical",
            "connection_count": 46,
            "mapping_cost": 0,
            "ab_records": ab_records,
            "bitstream_128b": summarize_bitstream(
                repaired_outputs[0] / "modules_dump_128b.bin", 128
            ),
            "bitstream_64b": summarize_bitstream(
                repaired_outputs[0] / "modules_dump_64b.bin", 64
            ),
        },
        "resnet50_classification": {
            "result": "geometry_matches_three_nodes_but_config_is_not_node_bound",
            "operator_family": "QLinearConv split into ConvInt32Accumulate + RequantizeUint8",
            "complete_qlinearconv": False,
        },
        "resnet50_matches": matching_resnet_nodes(_load_object(MODEL_GRAPH)),
        "numeric_probe": numeric_probe,
        "formal_server_package": {
            "status": "not_generated_fail_closed",
            "attempted_node_id": "node-0005",
            "generator_exit_code": formal_attempt["exit_code"],
            "reason": "real 1x1 generator requires kernel1/stride1/pad0",
            "missing_gates": [
                "typed 3x3 target JSON and semantic contract",
                "current HIGH-4 LC/PE/stream/buffer and padding transport",
                "official encoder candidate bound to node-0005",
                "config-bound Golden/NDP P/D",
                "approved freeze ID",
                "freeze-bound execplan/Bank_data/overlay",
            ],
        },
        "evidence_boundary": (
            "The generated bitstream proves deterministic encoding and zero-cost "
            "placement only. It is not target-JSON numerical execution and is not "
            "authorized for server upload."
        ),
    }
    if [item["node_id"] for item in report["resnet50_matches"]] != [
        "node-0005",
        "node-0009",
        "node-0013",
    ]:
        raise SeniorConvAuditError("formal ResNet50 node classification differs")

    bundle = output / BUNDLE_NAME
    (bundle / "source").mkdir(parents=True)
    shutil.copy2(ORIGINAL_JSON, bundle / "source" / "conv_full_senior_original.json")
    shutil.copy2(
        ORIGINAL_PSEUDOCODE,
        bundle / "source" / "conv_full_senior_original.txt",
    )
    shutil.copy2(REPAIRED_JSON, bundle / "source" / "conv_full_structural_repair.json")
    shutil.copy2(
        REPAIRED_PSEUDOCODE,
        bundle / "source" / "conv_full_structural_repair.txt",
    )
    shutil.copy2(
        ENCODER_EVIDENCE,
        bundle / "source" / "conv_full_encoder_evidence.json",
    )
    _copy_tree_files(original_output, bundle / "encoder" / "original")
    _copy_tree_files(repaired_outputs[0], bundle / "encoder" / "repaired_a")
    _copy_tree_files(repaired_outputs[1], bundle / "encoder" / "repaired_b")
    _write_text(
        bundle / "evidence" / "audit_report.json",
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _write_text(
        bundle / "evidence" / "numeric_probe.json",
        json.dumps(numeric_probe, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
    )
    for name, run in (
        ("original_encoder", original_run),
        ("repaired_encoder_a", repaired_runs[0]),
        ("repaired_encoder_b", repaired_runs[1]),
        ("formal_node_0005_package_attempt", formal_attempt),
    ):
        _write_text(bundle / "logs" / f"{name}.stdout.txt", run["stdout"])
        _write_text(bundle / "logs" / f"{name}.stderr.txt", run["stderr"])
    _write_text(bundle / "README.txt", _readme(report))

    records = []
    for path in sorted(bundle.rglob("*")):
        if path.is_symlink():
            raise SeniorConvAuditError(f"bundle contains symlink: {path}")
        if path.is_file():
            records.append(
                {
                    "path": path.relative_to(bundle).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    manifest = {
        "schema_version": "senior-conv-encoder-test-bundle-0.1",
        "status": report["status"],
        "bundle_name": BUNDLE_NAME,
        "server_runnable": False,
        "hdl_file_count": 0,
        "files": records,
    }
    _write_text(
        bundle / "MANIFEST.json",
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )

    zip_path = output / f"{BUNDLE_NAME}.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(bundle.rglob("*")):
            if path.is_file():
                archive.write(path, f"{BUNDLE_NAME}/{path.relative_to(bundle).as_posix()}")
    zip_sha256 = sha256_file(zip_path)
    sidecar = Path(str(zip_path) + ".sha256")
    sidecar.write_text(f"{zip_sha256}  {zip_path.name}\n", encoding="ascii", newline="\n")
    build_report = {
        "status": report["status"],
        "output": str(output),
        "bundle": str(bundle),
        "zip": str(zip_path),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha256,
        "sidecar": str(sidecar),
        "server_runnable": False,
    }
    _write_text(
        output / "build_report.json",
        json.dumps(build_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return build_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build(args.output)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(
            json.dumps(
                {"status": "failed", "reason": str(error)},
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
