from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Mapping

from .hashing import sha256_file
from .maxpool_node0002_semantic_contract import (
    validate_maxpool_node0002_semantic_contract,
)
from .operator_config_package_validator import OperatorConfigPackageValidator


SCHEMA = "resnet50-maxpool-node0002-server-candidate-v1"
STATUS = "local_package_valid_server_execution_not_claimed"


class MaxPoolServerCandidateError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise MaxPoolServerCandidateError(f"JSON root must be an object: {path}")
    return value


def _files(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == "candidate_manifest.json":
            continue
        if path.is_symlink():
            raise MaxPoolServerCandidateError(f"candidate contains a symlink: {path}")
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


def _binding(root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(root.resolve()).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_maxpool_server_candidate(project_root: Path, output_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    output = output_root.resolve()
    if output.exists():
        raise MaxPoolServerCandidateError(f"output must be a fresh path: {output}")
    exec_evidence = (
        root
        / "artifacts/operator_config_validation/r5-patched-execplan-evidence/"
        "maxpool-node0002-guarded-wave0-v5"
    )
    guarded_root = (
        root
        / "artifacts/operator_config_validation/r5-maxpool-node0002-guarded-wave0-v1"
    )
    semantic_path = root / "contracts/maxpool_node0002_guarded_wave0_semantic_contract.json"
    exec_manifest = _load(exec_evidence / "bundle_manifest.json")
    guarded_manifest = _load(guarded_root / "manifest.json")
    semantic = _load(semantic_path)
    if (
        exec_manifest.get("package_validation_report", {}).get("valid") is not True
        or exec_manifest.get("request_address_validation_report", {}).get("valid")
        is not True
        or exec_manifest.get("execplan", {}).get("sha256")
        != "e38004f09cc76062c6d510d0c531588de58eb145e479b39d6b09de93d7ad99cf"
        or exec_manifest.get("files", {}).get("semantic_contract.json", {}).get("sha256")
        != sha256_file(semantic_path)
        or guarded_manifest.get("summary", {}).get("independent_mismatch_count") != 0
    ):
        raise MaxPoolServerCandidateError("source evidence is not the closed v5 candidate")

    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(exec_evidence / "pipeline_output", output)
    shutil.copytree(exec_evidence / "mapping_evidence", output / "mapping_evidence")
    shutil.copy2(semantic_path, output / "semantic_contract.json")
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
    shutil.copy2(guarded_root / "manifest.json", evidence_root / "guarded_transport_manifest.json")
    shutil.copy2(
        root / "contracts/resnet50_r5_resolution_overlay.json",
        evidence_root / "r5_resolution_overlay.json",
    )
    shutil.copy2(
        root / "contracts/resnet50_r5_lowering_bundle.json",
        evidence_root / "r5_lowering_bundle.json",
    )

    records = guarded_manifest.get("records")
    if not isinstance(records, list) or len(records) != 28:
        raise MaxPoolServerCandidateError("guarded transport must contain 28 slices")
    matrix_count = 0
    for record in records:
        if not isinstance(record, Mapping):
            raise MaxPoolServerCandidateError("guarded transport record is malformed")
        slice_id = record.get("slice_id")
        if not isinstance(slice_id, int) or not 0 <= slice_id < 28:
            raise MaxPoolServerCandidateError("guarded transport slice id differs")
        destination = output / "install" / "op0" / f"slice{slice_id:02d}"
        destination.mkdir(parents=True, exist_ok=True)
        for tensor in ("A", "D"):
            item = record.get(tensor)
            if not isinstance(item, Mapping):
                raise MaxPoolServerCandidateError(f"slice {slice_id} {tensor} is missing")
            source = guarded_root / str(item.get("path"))
            if (
                not source.is_file()
                or item.get("sha256") != sha256_file(source)
                or item.get("payload_bytes") not in {201_168, 50_176}
            ):
                raise MaxPoolServerCandidateError(
                    f"slice {slice_id} {tensor} transport differs"
                )
            shutil.copy2(source, destination / source.name)
            matrix_count += 1
    if matrix_count != 56:
        raise MaxPoolServerCandidateError("candidate must contain 56 matrix files")

    graph_path = output / "graph_withbaseaddr.json"
    validate_maxpool_node0002_semantic_contract(
        semantic,
        root,
        graph_withbaseaddr=graph_path,
        mapping_bundle=output / "mapping_evidence/op0",
    )
    package_report = OperatorConfigPackageValidator().validate(
        output,
        graph_path=graph_path,
        semantic_contract=semantic,
        require_matrix_files=True,
        provenance_root=output,
    ).to_dict()
    if not package_report["valid"]:
        raise MaxPoolServerCandidateError(
            f"matrix-complete package rejected: {package_report.get('first_error')}"
        )
    (evidence_root / "matrix_complete_package_validation_report.json").write_text(
        json.dumps(package_report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    request_report = _load(evidence_root / "request_address_validation_report.json")
    if (
        request_report.get("valid") is not True
        or request_report.get("facts", {}).get("graph_sha256") != sha256_file(graph_path)
        or request_report.get("facts", {}).get("request_count_with_multiplicity")
        != 1_517_936
    ):
        raise MaxPoolServerCandidateError("copied request proof is not bound to candidate graph")

    files = _files(output)
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "status": STATUS,
        "candidate_scope": {
            "node_id": "node-0002",
            "hw_op_id": "hwop-0002-00",
            "wave_index": 0,
            "slice_count": 28,
            "remaining_tiles": 36,
            "formal_target_config": False,
            "server_execution_claim": False,
        },
        "source_evidence": _binding(root, exec_evidence / "bundle_manifest.json"),
        "semantic_contract": {
            "path": "semantic_contract.json",
            "sha256": sha256_file(output / "semantic_contract.json"),
            "contract_sha256": semantic["contract_sha256"],
        },
        "execution_payload": {
            "execplan": _binding(output, output / "install/execplan.txt"),
            "sca_cfg": _binding(output, output / "sca_cfg.json"),
            "sca_cfg_D": _binding(output, output / "sca_cfg_D.json"),
            "graph_withbaseaddr": _binding(output, graph_path),
            "matrix_file_count": matrix_count,
            "config_bitstream_count": len(
                list((output / "install/cfg_pkg").glob("*.bin"))
            ),
        },
        "local_validation": {
            "matrix_complete_package_valid": True,
            "request_address_valid": True,
            "request_count_with_multiplicity": 1_517_936,
            "logical_address_mismatch_count": 0,
            "padding_mask_mismatch_count": 0,
            "independent_w3_mismatch_count": 0,
            "mapping_penalty": 0.0,
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
                f"--package {output.relative_to(root).as_posix()} "
                "--output <fresh-return-run1> --run-id run1"
            ),
            "e5": (
                "python tools/run_e4e5_server_protocol.py --protocol <approved.json> "
                f"--package {output.relative_to(root).as_posix()} "
                "--output <fresh-return-run2> --run-id run2"
            ),
        },
        "payload_file_count": len(files),
        "payload_tree_sha256": _tree_sha256(files),
        "files": files,
    }
    (output / "candidate_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    validate_maxpool_server_candidate(root, output)
    return manifest


def validate_maxpool_server_candidate(
    project_root: Path, candidate_root: Path
) -> dict[str, Any]:
    root = project_root.resolve()
    candidate = candidate_root.resolve()
    manifest = _load(candidate / "candidate_manifest.json")
    if manifest.get("schema") != SCHEMA or manifest.get("status") != STATUS:
        raise MaxPoolServerCandidateError("candidate manifest identity differs")
    actual = _files(candidate, exclude_manifest=True)
    if manifest.get("files") != actual:
        raise MaxPoolServerCandidateError("candidate file hashes differ")
    if (
        manifest.get("payload_file_count") != len(actual)
        or manifest.get("payload_tree_sha256") != _tree_sha256(actual)
    ):
        raise MaxPoolServerCandidateError("candidate tree receipt differs")
    source = manifest.get("source_evidence")
    if not isinstance(source, Mapping):
        raise MaxPoolServerCandidateError("candidate source evidence is missing")
    source_path = root / str(source.get("path"))
    if (
        not source_path.is_file()
        or source.get("size_bytes") != source_path.stat().st_size
        or source.get("sha256") != sha256_file(source_path)
    ):
        raise MaxPoolServerCandidateError("candidate source evidence differs")
    semantic = _load(candidate / "semantic_contract.json")
    report = OperatorConfigPackageValidator().validate(
        candidate,
        graph_path=candidate / "graph_withbaseaddr.json",
        semantic_contract=semantic,
        require_matrix_files=True,
        provenance_root=candidate,
    ).to_dict()
    if not report["valid"] or report["facts"].get("missing_matrix_files"):
        raise MaxPoolServerCandidateError("candidate no longer passes package validation")
    lowering = _load(root / "contracts/resnet50_r5_lowering_bundle.json")
    current = [
        item
        for item in lowering.get("effective_resolutions", [])
        if isinstance(item, Mapping)
        and item.get("request_id") == "r5:hwop-0002-00"
    ]
    if len(current) != 1:
        raise MaxPoolServerCandidateError(
            "current MaxPool lowering resolution is missing"
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
        "matrix_file_count": manifest["execution_payload"]["matrix_file_count"],
        "payload_tree_sha256": manifest["payload_tree_sha256"],
        "execplan_sha256": manifest["execution_payload"]["execplan"]["sha256"],
    }


__all__ = [
    "MaxPoolServerCandidateError",
    "build_maxpool_server_candidate",
    "validate_maxpool_server_candidate",
]
