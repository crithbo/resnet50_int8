"""End-to-end local evidence for ResNet-50 node-0002 / hwop-0002-00."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from .adapters.ndp_rtl28_maxpool import NdpRtl28MaxPoolAdapter
from .errors import PipelineError
from .maxpool_instance import (
    HWOP_ID,
    INPUT_TENSOR_ID,
    NODE_ID,
    OUTPUT_TENSOR_ID,
    load_maxpool_instance,
)
from .pool28_layout import MaxPoolPhysicalLayout
from .profile28 import GROUP4X7_BATCH_CHANNEL28_PROFILE


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes(order="C")).hexdigest()


def _load_formal_operator_inventory(project_root: Path) -> dict[str, Any]:
    path = project_root / "artifacts" / "w3" / "model_graph.json"
    if not path.is_file():
        raise PipelineError("formal W3 model graph is missing")
    graph = json.loads(path.read_text(encoding="utf-8"))
    counts = dict(sorted(Counter(node["op_type"] for node in graph["nodes"]).items()))
    expected = {
        "DequantizeLinear": 2,
        "Flatten": 1,
        "MaxPool": 1,
        "QLinearAdd": 17,
        "QLinearConv": 53,
        "QLinearGlobalAveragePool": 1,
        "QLinearMatMul": 1,
        "QuantizeLinear": 2,
    }
    if counts != expected:
        raise PipelineError(f"formal W3 operator inventory differs: {counts}")
    return {
        "path": str(path.relative_to(project_root)).replace("\\", "/"),
        "sha256": _sha256_file(path),
        "model_sha256": graph["model_sha256"],
        "counts": counts,
    }


def _validate_encoder_evidence(project_root: Path, instance: Any) -> dict[str, Any]:
    evidence_path = (
        project_root
        / "artifacts"
        / "w5"
        / HWOP_ID
        / "maxpool_v1"
        / "encoder_candidate_v2"
        / "evidence.json"
    )
    if not evidence_path.is_file():
        raise PipelineError("MaxPool official encoder evidence is missing")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    if (
        evidence.get("status") != "official_encoder_passed_not_target_executed"
        or evidence.get("wave_count") != 3
        or evidence.get("source_template_sha256")
        != instance.manifest["source_template"]["sha256"]
    ):
        raise PipelineError("MaxPool encoder evidence summary differs")
    expected_hashes = [item["config_sha256"] for item in instance.manifest["waves"]]
    if [item.get("config_sha256") for item in evidence["waves"]] != expected_hashes:
        raise PipelineError("MaxPool encoded config hashes differ from the frozen instance")
    for wave in evidence["waves"]:
        wave_root = evidence_path.parent / f"wave-{wave['wave_index']}"
        for name, record in wave["outputs"].items():
            path = wave_root / name
            if (
                not path.is_file()
                or path.stat().st_size != int(record["size_bytes"])
                or _sha256_file(path) != record["sha256"]
            ):
                raise PipelineError(f"MaxPool encoded artifact differs: {path}")
    return {
        "path": str(evidence_path.relative_to(project_root)).replace("\\", "/"),
        "sha256": _sha256_file(evidence_path),
        "status": evidence["status"],
        "wave_count": evidence["wave_count"],
    }


def _validate_rtl_kernel_proof(project_root: Path) -> dict[str, Any]:
    path = (
        project_root
        / "artifacts"
        / "w5"
        / HWOP_ID
        / "maxpool_v1"
        / "rtl_uint8_kernel_proof.json"
    )
    if not path.is_file():
        raise PipelineError("MaxPool RTL UINT8 arithmetic proof is missing")
    report = json.loads(path.read_text(encoding="utf-8"))
    rtl_path = project_root / report["rtl_source"]["path"]
    if (
        report.get("status") != "passed"
        or report.get("kind") != "rtl_arithmetic_kernel_proof"
        or report["scope"].get("input_pairs") != 65536
        or report["scope"].get("byte_lane_checks") != 262144
        or report["scope"].get("full_operator_target_execution") is not False
        or not rtl_path.is_file()
        or _sha256_file(rtl_path) != report["rtl_source"]["sha256"]
    ):
        raise PipelineError("MaxPool RTL UINT8 arithmetic proof differs")
    return {
        "path": str(path.relative_to(project_root)).replace("\\", "/"),
        "sha256": _sha256_file(path),
        "status": "passed_kernel_only",
        "input_pairs": 65536,
        "byte_lane_checks": 262144,
        "full_operator_target_execution": False,
    }


def _validate_cgra_reference(project_root: Path, golden: np.ndarray) -> dict[str, Any]:
    path = (
        project_root
        / "artifacts/w5/hwop-0002-00/maxpool_v1/cgra_software_reference.json"
    )
    if not path.is_file():
        raise PipelineError("CGRA_SIM MaxPool software reference report is missing")
    report = json.loads(path.read_text(encoding="utf-8"))
    source = project_root / report["operator_source"]["path"]
    fix = project_root / "CGRA_SIM" / report["repository"]["local_import_blocker_fix"]["path"]
    if (
        report.get("status")
        != "passed_extra_software_reference_not_target_execution"
        or report["execution"].get("mismatch_count") != 0
        or report["execution"].get("output_payload_sha256") != _array_sha256(golden)
        or report["evidence_boundary"].get("counts_as_current_28_slice_target_execution")
        is not False
        or not source.is_file()
        or _sha256_file(source) != report["operator_source"]["sha256"]
        or not fix.is_file()
        or _sha256_file(fix)
        != report["repository"]["local_import_blocker_fix"]["sha256"]
    ):
        raise PipelineError("CGRA_SIM MaxPool software reference evidence differs")
    return {
        "path": str(path.relative_to(project_root)).replace("\\", "/"),
        "sha256": _sha256_file(path),
        "status": report["status"],
        "logical_mismatch_count": 0,
        "counts_as_target_execution": False,
    }


def _validate_target_attempt(project_root: Path) -> dict[str, Any]:
    path = project_root / "artifacts/w5/hwop-0002-00/maxpool_v1/complete_target_attempt.json"
    if not path.is_file():
        raise PipelineError("MaxPool complete target attempt report is missing")
    report = json.loads(path.read_text(encoding="utf-8"))
    if (
        report.get("status") != "test_package_ready_target_not_executed"
        or report["attempt"].get("target_process_started") is not False
        or report["attempt"].get("target_output_produced") is not False
        or report["package_readiness"].get("status") != "ready_for_server_run1"
    ):
        raise PipelineError("MaxPool complete target attempt boundary differs")
    return {
        "path": str(path.relative_to(project_root)).replace("\\", "/"),
        "sha256": _sha256_file(path),
        "status": report["status"],
        "package_status": report["package_readiness"]["status"],
        "server_overlay": report["package_readiness"]["server_overlay"],
        "target_process_started": False,
        "target_output_produced": False,
    }


def run_maxpool_preflight(project_root: Path) -> dict[str, Any]:
    project_root = project_root.resolve()
    instance = load_maxpool_instance(
        project_root, project_root / "configs" / "maxpool" / HWOP_ID
    )
    encoder = _validate_encoder_evidence(project_root, instance)
    rtl_kernel = _validate_rtl_kernel_proof(project_root)
    inventory = _load_formal_operator_inventory(project_root)
    tensor_root = project_root / "artifacts" / "w3" / "golden_batch16" / "tensors"
    input_path = tensor_root / f"{INPUT_TENSOR_ID}.npy"
    output_path = tensor_root / f"{OUTPUT_TENSOR_ID}.npy"
    activation = np.load(input_path, allow_pickle=False)
    golden = np.load(output_path, allow_pickle=False)
    if (
        activation.dtype != np.uint8
        or tuple(activation.shape) != (16, 64, 112, 112)
        or golden.dtype != np.uint8
        or tuple(golden.shape) != (16, 64, 56, 56)
    ):
        raise PipelineError("W3 MaxPool tensors differ from the frozen instance")
    cgra_reference = _validate_cgra_reference(project_root, golden)
    target_attempt = _validate_target_attempt(project_root)
    layout = MaxPoolPhysicalLayout(profile_id=GROUP4X7_BATCH_CHANNEL28_PROFILE)
    bundle = layout.forward(
        activation=activation,
        output=golden,
        kernel_shape=(3, 3),
        strides=(2, 2),
        pads=(1, 1, 1, 1),
        dilations=(1, 1),
        spatial_padding_value=0,
        input_tail_value=0,
        output_tail_value=0,
        tensor_ids={"A": INPUT_TENSOR_ID, "D": OUTPUT_TENSOR_ID},
    )
    result = NdpRtl28MaxPoolAdapter(
        project_root / "NDPFuncModel",
        python_executable=project_root / ".venv" / "Scripts" / "python.exe",
        timeout_seconds=300,
    ).run(layout, bundle, instance=instance)
    mismatches = np.argwhere(result.output != golden)
    mismatch_count = int(len(mismatches))
    if mismatch_count:
        first = tuple(int(item) for item in mismatches[0])
        raise PipelineError(
            f"MaxPool config-bound functional output differs at {first}: "
            f"actual={int(result.output[first])}, golden={int(golden[first])}"
        )
    job = result.physical_probe.uint8_maxpool_jobs[0]
    if int(job["physical_mismatch_count"]) != 0:
        raise PipelineError("MaxPool config-bound physical output differs from W3")
    return {
        "schema_version": "0.1",
        "kind": "resnet50_maxpool_local_preflight",
        "status": "config_bound_functional_passed_three_way_not_comparable",
        "identity": instance.manifest["identity"],
        "selection": {
            "chosen_operator": "MaxPool",
            "reason": "one instance, exact C16/H112/W112 target template, no qparams or requantization, reversible 28-slice A/D layout",
            "formal_instance_count": 1,
            "formal_operator_inventory": inventory,
            "non_conv_candidate_boundaries": {
                "MaxPool": "selected: exact upstream template and complete W3/W4 tensors/layout; no requantization",
                "QLinearAdd": "requires two-input affine dequantization plus uint8 requantization",
                "QLinearGlobalAveragePool": "upstream template stops at int32 sum and lacks divide/requantize",
                "QuantizeLinear/DequantizeLinear": "available templates do not match the formal fp32/uint8 contracts",
                "Flatten": "shape-only view is not an arithmetic operator comparison",
                "QLinearMatMul": "no approved INT8 target template",
            },
        },
        "golden": {
            "source": "W3 formal ONNX execution",
            "input_path": str(input_path.relative_to(project_root)).replace("\\", "/"),
            "input_npy_sha256": _sha256_file(input_path),
            "input_payload_sha256": _array_sha256(activation),
            "output_path": str(output_path.relative_to(project_root)).replace("\\", "/"),
            "output_npy_sha256": _sha256_file(output_path),
            "output_payload_sha256": _array_sha256(golden),
        },
        "configuration": {
            "manifest_path": "configs/maxpool/hwop-0002-00/manifest.json",
            "manifest_sha256": _sha256_file(instance.root / "manifest.json"),
            "config_sha256": list(result.config_sha256),
            "wave_active_slice_counts": [
                len(item["active_slices"]) for item in instance.manifest["waves"]
            ],
            "official_encoder": encoder,
        },
        "functional_execution": {
            "repository": "NDPFuncModel",
            "path": [
                "region_backed_physical_image",
                "GeneralPEA",
                "region_backed_physical_image",
            ],
            "logical_element_count": int(golden.size),
            "logical_mismatch_count": mismatch_count,
            "output_payload_sha256": _array_sha256(result.output),
            "physical_slice_count": len(job["outputs"]),
            "physical_mismatch_count": int(job["physical_mismatch_count"]),
            "physical_output_sha256": [
                {"slice_id": item["slice_id"], "sha256": item["sha256"]}
                for item in job["outputs"]
            ],
            "status": result.status,
        },
        "extra_software_reference": cgra_reference,
        "rtl_arithmetic_evidence": rtl_kernel,
        "complete_target_attempt": target_attempt,
        "pairwise_comparison": {
            "w3_golden_vs_config_bound_functional": {
                "status": "passed",
                "mismatch_count": 0,
                "comparison": "bit_exact_uint8",
            },
            "w3_golden_vs_complete_target": {
                "status": "not_comparable",
                "reason": "no complete target simulator or hardware MaxPool output was produced",
            },
            "config_bound_functional_vs_complete_target": {
                "status": "not_comparable",
                "reason": "no complete target simulator or hardware MaxPool output was produced",
            },
        },
        "three_way": {
            "status": "three_way_not_comparable",
            "g6_validated": False,
            "g8_validated": False,
            "supporting_rtl_kernel_proof_is_not_third_leg": True,
        },
    }
