from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from .hashing import sha256_file
from .node0004_semantic_contract import validate_node0004_semantic_contract
from .operator_config_package_validator import OperatorConfigPackageValidator


SCHEMA = "resnet50-node0004-nopp-r1-server-candidate-v1"
STATUS = "experimental_smoke_package_valid_server_execution_not_claimed"


class Node0004ServerCandidateError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Node0004ServerCandidateError(f"JSON root must be an object: {path}")
    return value


def _files(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == "candidate_manifest.json":
            continue
        if path.is_symlink():
            raise Node0004ServerCandidateError(f"candidate contains a symlink: {path}")
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def _tree_sha256(files: Mapping[str, Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(files.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _relative_tree(root: Path) -> dict[str, dict[str, Any]]:
    return _files(root)


def build_node0004_server_candidate(project_root: Path, output_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise Node0004ServerCandidateError(f"output must be a fresh path: {output}")
    exec_evidence = (
        root
        / "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
        "node0004-nopp-r1-v2"
    )
    mapping = (
        root
        / "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
        "node0004-accumulate-wave0-nopp-r1-strict-address-bound-seed42-v1"
    )
    data_root = (
        root
        / "ndp-sim/generate_python_golden/single_op_data/"
        "install_node0004_accumulate_wave0_nopp_r1"
    )
    active_package = (
        root / "ndp-sim/model_execplan/output/node0004_accumulate_wave0_nopp_r1_graph"
    )
    semantic_path = root / "contracts/node0004_accumulate_wave0_nopp_r1_semantic_contract.json"
    exec_manifest = _load(exec_evidence / "bundle_manifest.json")
    input_manifest_path = data_root / "node0004_accumulate_wave0_nopp_r1_input_manifest.json"
    input_manifest = _load(input_manifest_path)
    active_validation = _load(
        active_package / "node0004_accumulate_wave0_nopp_r1_validation.json"
    )
    semantic = _load(semantic_path)
    if (
        exec_manifest.get("package_validation_report", {}).get("valid") is not True
        or exec_manifest.get("request_address_validation_report", {}).get("valid")
        is not True
        or exec_manifest.get("files", {}).get("semantic_contract.json", {}).get("sha256")
        != sha256_file(semantic_path)
        or input_manifest.get("generated_tensor_file_count") != 336
        or active_validation.get("status")
        != "local_zero_pingpong_structure_and_provenance_passed_server_not_yet_run"
        or active_validation.get("same_run_companion_files") != 336
    ):
        raise Node0004ServerCandidateError("node0004 source evidence differs")

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(exec_evidence / "pipeline_output", output)
    shutil.copytree(exec_evidence / "mapping_evidence", output / "mapping_evidence")
    shutil.copytree(data_root / "op0", output / "install/op0")
    if _relative_tree(data_root / "op0") != _relative_tree(output / "install/op0"):
        raise Node0004ServerCandidateError("copied node0004 companion tensors differ")
    shutil.copy2(semantic_path, output / "semantic_contract.json")
    shutil.copy2(input_manifest_path, output / "node0004_accumulate_wave0_nopp_r1_input_manifest.json")
    evidence_root = output / "evidence"
    evidence_root.mkdir()
    for name in (
        "bundle_manifest.json",
        "double_run_comparison.json",
        "execplan_validation_report.json",
        "package_validation_report.json",
        "request_address_validation_report.json",
        "native_source_manifest.json",
        "patchset_manifest.json",
    ):
        shutil.copy2(exec_evidence / name, evidence_root / name)
    shutil.copy2(
        active_package / "node0004_accumulate_wave0_nopp_r1_validation.json",
        evidence_root / "active_matrix_package_validation.json",
    )
    graph_path = output / "graph_input_withbaseaddr.json"
    validate_node0004_semantic_contract(
        semantic,
        root,
        graph_withbaseaddr=graph_path,
        mapping_bundle=mapping,
    )
    report = OperatorConfigPackageValidator().validate(
        output,
        graph_path=graph_path,
        semantic_contract=semantic,
        require_matrix_files=True,
        provenance_root=output,
    ).to_dict()
    if not report["valid"]:
        raise Node0004ServerCandidateError(
            f"matrix-complete node0004 package rejected: {report.get('first_error')}"
        )
    (evidence_root / "matrix_complete_package_validation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    request_report = _load(evidence_root / "request_address_validation_report.json")
    if (
        request_report.get("valid") is not True
        or request_report.get("facts", {}).get("graph_sha256") != sha256_file(graph_path)
        or request_report.get("facts", {}).get("request_count_with_multiplicity")
        != 748_160
    ):
        raise Node0004ServerCandidateError("node0004 request proof differs")
    files = _files(output)
    relative = output.relative_to(root).as_posix()
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "candidate_scope": {
            "node_id": "node-0004",
            "hw_op_id": "hwop-0004-00",
            "revision": "nopp_r1",
            "purpose": "single-stage zero-ping-pong liveness smoke",
            "full_conv_semantics_resolved": False,
            "numeric_pass_claim": False,
            "formal_target_config": False,
            "server_execution_claim": False,
        },
        "execution_payload": {
            "execplan_sha256": sha256_file(output / "install/execplan.txt"),
            "graph_sha256": sha256_file(graph_path),
            "sca_matrix_entry_count": 112,
            "companion_tensor_file_count": 336,
            "slice_count": 28,
        },
        "local_validation": {
            "matrix_complete_package_valid": True,
            "request_address_valid": True,
            "request_count_with_multiplicity": 748_160,
            "mapping_penalty": 0.0,
            "liveness_or_numeric_result": "not_run_requires_server",
        },
        "external_gate": {
            "approved_server_protocol_required": True,
            "e4_run1_required": True,
            "e5_run2_required": True,
            "formal_release_before_e4_e5": False,
        },
        "commands": {
            "e4": (
                "python tools/run_e4e5_server_protocol.py --protocol <approved.json> "
                f"--package {relative} --output <fresh-return-run1> --run-id run1"
            ),
            "e5": (
                "python tools/run_e4e5_server_protocol.py --protocol <approved.json> "
                f"--package {relative} --output <fresh-return-run2> --run-id run2"
            ),
        },
        "payload_file_count": len(files),
        "payload_tree_sha256": _tree_sha256(files),
        "files": files,
    }
    (output / "candidate_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    validate_node0004_server_candidate(root, output)
    return manifest


def validate_node0004_server_candidate(
    project_root: Path, candidate_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    candidate = candidate_root.resolve()
    manifest = _load(candidate / "candidate_manifest.json")
    if manifest.get("schema") != SCHEMA or manifest.get("status") != STATUS:
        raise Node0004ServerCandidateError("node0004 candidate identity differs")
    actual = _files(candidate, exclude_manifest=True)
    if (
        manifest.get("files") != actual
        or manifest.get("payload_file_count") != len(actual)
        or manifest.get("payload_tree_sha256") != _tree_sha256(actual)
    ):
        raise Node0004ServerCandidateError("node0004 candidate tree receipt differs")
    semantic = _load(candidate / "semantic_contract.json")
    mapping = (
        root
        / "artifacts/operator_config_validation/r5-patched-mapping-evidence/"
        "node0004-accumulate-wave0-nopp-r1-strict-address-bound-seed42-v1"
    )
    graph = candidate / "graph_input_withbaseaddr.json"
    report = OperatorConfigPackageValidator().validate(
        candidate,
        graph_path=graph,
        semantic_contract=semantic,
        require_matrix_files=True,
        provenance_root=candidate,
    ).to_dict()
    if not report["valid"] or report["facts"].get("missing_matrix_files"):
        raise Node0004ServerCandidateError("node0004 candidate package is incomplete")
    lowering = _load(root / "contracts/resnet50_r5_lowering_bundle.json")
    current = [
        item
        for item in lowering.get("effective_resolutions", [])
        if isinstance(item, Mapping)
        and item.get("request_id") == "r5:hwop-0004-00"
    ]
    if len(current) != 1:
        raise Node0004ServerCandidateError(
            "current node0004 lowering resolution is missing"
        )
    return {
        "valid": True,
        "validation_scope": "historical_package_integrity_not_current_semantic_release",
        "current_semantics_valid": (
            current[0].get("readiness_axes", {}).get(
                "rtl_semantics_compatible"
            )
            is True
        ),
        "current_semantic_blockers": current[0].get(
            "rtl_semantic_blockers", []
        ),
        "payload_tree_sha256": manifest["payload_tree_sha256"],
        "companion_tensor_file_count": manifest["execution_payload"][
            "companion_tensor_file_count"
        ],
    }


__all__ = [
    "Node0004ServerCandidateError",
    "build_node0004_server_candidate",
    "validate_node0004_server_candidate",
]
