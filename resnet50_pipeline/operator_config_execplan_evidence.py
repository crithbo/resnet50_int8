from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .operator_config_artifact_validator import (
    ACTIVE_ENCODER_COMMIT,
    OperatorConfigArtifactValidator,
)
from .operator_config_execplan_validator import OperatorConfigExecPlanValidator
from .operator_config_package_validator import OperatorConfigPackageValidator
from .operator_config_request_address_validator import (
    OperatorConfigRequestAddressValidator,
)
from .ndp_patch_toolchain import apply_patchset_in_place, validate_patchset_manifest


NONDETERMINISTIC_OUTPUTS = {"placement.png"}


@dataclass(frozen=True)
class ExecPlanEvidenceBundle:
    output_dir: Path
    manifest_path: Path
    validation_report_path: Path
    valid: bool
    execplan_sha256: str
    deterministic_file_count: int


def create_execplan_evidence_bundle(
    *,
    ndp_sim_root: Path,
    graph_path: Path,
    mapping_bundles: Mapping[str, Path],
    output_dir: Path,
    python_executable: Path,
    semantic_contract_path: Path | None = None,
    expected_encoder_commit: str = ACTIVE_ENCODER_COMMIT,
    timeout_seconds: int = 300,
    patchset_manifest_path: Path | None = None,
) -> ExecPlanEvidenceBundle:
    """Run the native or explicitly patched planner twice from hash-bound mappings.

    The active ``ndp-sim`` checkout remains read-only.  Each run gets a fresh
    disposable copy of the native bitstream and model-execplan sources.  The
    only seeded state is the cache carried by an independently validated,
    zero-penalty mapping evidence bundle.  The emitted planner JSON, mapping,
    bitstream, SCA payload and Load_Config command are then checked as one
    chain, and every deterministic output is compared across the two runs.
    """

    ndp_sim_root = ndp_sim_root.resolve()
    graph_path = graph_path.resolve()
    output_dir = output_dir.resolve()
    python_executable = python_executable.resolve()
    semantic_contract_path = (
        semantic_contract_path.resolve() if semantic_contract_path is not None else None
    )
    patchset_manifest_path = (
        patchset_manifest_path.resolve() if patchset_manifest_path is not None else None
    )
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite execplan evidence bundle: {output_dir}")
    if _is_relative_to(output_dir, ndp_sim_root):
        raise ValueError("execplan evidence bundle must be outside the read-only ndp-sim tree")
    if not graph_path.is_file():
        raise FileNotFoundError(graph_path)
    if not python_executable.is_file():
        raise FileNotFoundError(python_executable)
    if semantic_contract_path is not None and not semantic_contract_path.is_file():
        raise FileNotFoundError(semantic_contract_path)

    patchset: dict[str, Any] | None = None
    if patchset_manifest_path is not None:
        if not patchset_manifest_path.is_file():
            raise FileNotFoundError(patchset_manifest_path)
        patchset = _load_object(patchset_manifest_path)
        validate_patchset_manifest(patchset, ndp_sim_root)

    graph = _load_object(graph_path)
    operators = _graph_operators(graph)
    op_ids = {item["id"] for item in operators}
    if set(mapping_bundles) != op_ids:
        raise ValueError(
            "mapping bundle keys must exactly match graph operator ids; "
            f"expected={sorted(op_ids)}, got={sorted(mapping_bundles)}"
        )

    commit = _git_output(ndp_sim_root, "rev-parse", "HEAD")
    if commit != expected_encoder_commit:
        raise ValueError(f"ndp-sim commit {commit} differs from pinned {expected_encoder_commit}")

    validated: dict[str, dict[str, Any]] = {}
    for op in operators:
        op_id = op["id"]
        bundle = mapping_bundles[op_id].resolve()
        config_path = bundle / "source_config.json"
        evidence_path = bundle / "mapping_evidence.json"
        if not config_path.is_file() or not evidence_path.is_file():
            raise FileNotFoundError(f"incomplete mapping evidence bundle for {op_id}: {bundle}")
        config = _load_object(config_path)
        evidence = _load_object(evidence_path)
        evidence_patchset = evidence.get("encoder", {}).get("patchset")
        if patchset is not None and (
            not isinstance(evidence_patchset, Mapping)
            or evidence_patchset.get("patchset_id") != patchset["patchset_id"]
            or evidence_patchset.get("patchset_sha256") != patchset["patchset_sha256"]
        ):
            raise ValueError(
                f"mapping evidence for {op_id} is not bound to the requested patchset"
            )
        report = OperatorConfigArtifactValidator(
            expected_encoder_commit=expected_encoder_commit
        ).validate(
            config,
            bundle,
            mapping_evidence=evidence,
            source=str(config_path),
        )
        if not report.valid:
            first = report.issues[0]
            raise ValueError(
                f"mapping evidence for {op_id} is invalid: "
                f"{first.code} at {first.path}: {first.message}"
            )
        cache_files = _files(bundle / "mapping_cache")
        if not cache_files:
            raise ValueError(f"mapping evidence for {op_id} carries no portable cache")
        validated[op_id] = {
            "bundle": bundle,
            "config": config_path,
            "evidence": evidence,
            "cache_files": cache_files,
        }

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    source_manifest = _native_source_manifest(ndp_sim_root)
    dirty_status = _git_output(ndp_sim_root, "status", "--short")

    # Keep the disposable tool path short on Windows.  Native placement emits
    # several deeply nested files and can otherwise hit legacy MAX_PATH while
    # the top-level planner still exits successfully after skipping the failed
    # bitstream regeneration.
    with tempfile.TemporaryDirectory(prefix="r3-execplan-") as temp_text:
        temp = Path(temp_text)
        run_outputs: list[Path] = []
        run_logs: list[tuple[bytes, bytes]] = []
        run_reports: list[dict[str, Any]] = []

        for run_index in range(2):
            tool_root = temp / f"run{run_index + 1}" / "tool"
            _copy_native_tool(ndp_sim_root, tool_root)
            if patchset is not None:
                _install_patchset_base_files(
                    source_root=ndp_sim_root,
                    tool_root=tool_root,
                    patchset=patchset,
                )
                applied = apply_patchset_in_place(
                    tool_root,
                    patchset_id=patchset["patchset_id"],
                )
                if applied["patchset_sha256"] != patchset["patchset_sha256"]:
                    raise RuntimeError("applied execplan patch differs from locked manifest")
            _install_validated_configs(tool_root, operators, validated)
            cache_dir = tool_root / "bitstream" / "config" / "mapping_cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            _merge_mapping_caches(validated, cache_dir)

            command = [
                str(python_executable),
                str(tool_root / "model_execplan" / "main.py"),
                str(graph_path),
            ]
            environment = dict(os.environ)
            environment["PYTHONIOENCODING"] = "utf-8"
            environment["PYTHONUTF8"] = "1"
            environment["PYTHONHASHSEED"] = "0"
            environment["MPLBACKEND"] = "Agg"
            completed = subprocess.run(
                command,
                cwd=tool_root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout_seconds,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    f"native planner run {run_index + 1} failed rc={completed.returncode}; "
                    f"stdout_tail={_tail(completed.stdout)}; stderr_tail={_tail(completed.stderr)}"
                )
            graph_root = (
                tool_root / "model_execplan" / "output" / graph_path.stem
            )
            if not graph_root.is_dir():
                raise RuntimeError(f"native planner omitted output directory: {graph_root}")
            graph_withbaseaddr = graph_root / f"{graph_path.stem}_withbaseaddr.json"
            report = _validate_run(
                graph_root=graph_root,
                graph_withbaseaddr=graph_withbaseaddr,
                validated=validated,
            )
            if not report["valid"]:
                first = report.get("first_error") or {}
                raise RuntimeError(
                    "native execplan validation failed: "
                    f"{first.get('code')} at {first.get('path')}: {first.get('message')}; "
                    f"planner_stdout_tail={_tail(completed.stdout)}; "
                    f"planner_stderr_tail={_tail(completed.stderr)}"
                )
            run_outputs.append(graph_root)
            run_logs.append((completed.stdout, completed.stderr))
            run_reports.append(report)

        hashes1 = _deterministic_output_hashes(run_outputs[0])
        hashes2 = _deterministic_output_hashes(run_outputs[1])
        if hashes1 != hashes2:
            changed = sorted(set(hashes1) ^ set(hashes2))
            changed.extend(
                key for key in sorted(set(hashes1) & set(hashes2))
                if hashes1[key] != hashes2[key]
            )
            raise RuntimeError(f"native planner double-run mismatch: {changed[:20]}")

        staged = temp / "bundle"
        staged.mkdir()
        shutil.copy2(graph_path, staged / "graph_input.json")
        shutil.copytree(run_outputs[0], staged / "pipeline_output")
        mapping_root = staged / "mapping_evidence"
        for op_id, item in validated.items():
            shutil.copytree(item["bundle"], mapping_root / op_id)
        for index, (stdout, stderr) in enumerate(run_logs, start=1):
            (staged / f"native_run{index}_stdout.log").write_bytes(stdout)
            (staged / f"native_run{index}_stderr.log").write_bytes(stderr)
        if semantic_contract_path is not None:
            shutil.copy2(semantic_contract_path, staged / "semantic_contract.json")
        (staged / "native_source_manifest.json").write_text(
            json.dumps(source_manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if patchset is not None:
            (staged / "patchset_manifest.json").write_text(
                json.dumps(patchset, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        (staged / "double_run_comparison.json").write_text(
            json.dumps(
                {
                    "schema": "operator-config-execplan-double-run-v1",
                    "equal": True,
                    "excluded_nondeterministic_outputs": sorted(NONDETERMINISTIC_OUTPUTS),
                    "files": hashes1,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        shutil.move(str(staged), str(output_dir))

    final_output = output_dir / "pipeline_output"
    final_mapping = {
        op_id: output_dir / "mapping_evidence" / op_id for op_id in sorted(op_ids)
    }
    final_report = _validate_run(
        graph_root=final_output,
        graph_withbaseaddr=final_output / f"{graph_path.stem}_withbaseaddr.json",
        validated={
            op_id: {
                "bundle": bundle,
                "config": bundle / "source_config.json",
                "evidence": _load_object(bundle / "mapping_evidence.json"),
            }
            for op_id, bundle in final_mapping.items()
        },
    )
    validation_path = output_dir / "execplan_validation_report.json"
    validation_path.write_text(
        json.dumps(final_report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if not final_report["valid"]:
        raise RuntimeError("published execplan evidence failed final validation")

    package_validation: dict[str, Any] | None = None
    package_validation_path = output_dir / "package_validation_report.json"
    if semantic_contract_path is not None:
        semantic_contract = _load_object(output_dir / "semantic_contract.json")
        package_validation = OperatorConfigPackageValidator().validate(
            final_output,
            graph_path=final_output / f"{graph_path.stem}_withbaseaddr.json",
            semantic_contract=semantic_contract,
            require_matrix_files=False,
            provenance_root=output_dir,
        ).to_dict()
        package_validation_path.write_text(
            json.dumps(package_validation, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if not package_validation["valid"]:
            raise RuntimeError("published execplan evidence failed package/semantic validation")

    request_validation = OperatorConfigRequestAddressValidator(
        include_request_rows=False
    ).validate(
        final_output,
        graph_path=final_output / f"{graph_path.stem}_withbaseaddr.json",
        source_configs={
            op_id: bundle / "source_config.json"
            for op_id, bundle in final_mapping.items()
        },
    ).to_dict()
    request_validation_path = output_dir / "request_address_validation_report.json"
    request_validation_path.write_text(
        json.dumps(request_validation, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if not request_validation["valid"]:
        first = request_validation.get("first_error") or {}
        raise RuntimeError(
            "published execplan evidence failed RTL request-address validation: "
            f"{first.get('code')} at {first.get('path')}: {first.get('message')}"
        )

    execplan_path = final_output / "install" / "execplan.txt"
    comparison = _load_object(output_dir / "double_run_comparison.json")
    manifest: dict[str, Any] = {
        "schema": "operator-config-execplan-evidence-bundle-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "read_only_native_source": True,
        "native_repository": {
            "name": "ndp-sim",
            "commit": commit,
            "dirty_status_at_run": dirty_status.splitlines() if dirty_status else [],
            "source_manifest": "native_source_manifest.json",
            "source_manifest_sha256": _sha256_file(
                output_dir / "native_source_manifest.json"
            ),
            "patchset": (
                {
                    "artifact": "patchset_manifest.json",
                    "sha256": _sha256_file(output_dir / "patchset_manifest.json"),
                    "patchset_id": patchset["patchset_id"],
                    "patchset_sha256": patchset["patchset_sha256"],
                }
                if patchset is not None
                else None
            ),
        },
        "graph_input": {
            "artifact": "graph_input.json",
            "sha256": _sha256_file(output_dir / "graph_input.json"),
        },
        "mapping_cache_policy": "portable-zero-penalty-bundle-input",
        "planner_config_policy": (
            "validated mapping source_config installed by operator type in each "
            "disposable tool copy; active ndp-sim remains read-only"
        ),
        "operator_mapping_bundles": {
            op_id: {
                "path": f"mapping_evidence/{op_id}",
                "source_config_sha256": _sha256_file(
                    output_dir / "mapping_evidence" / op_id / "source_config.json"
                ),
                "mapping_evidence_sha256": _sha256_file(
                    output_dir / "mapping_evidence" / op_id / "mapping_evidence.json"
                ),
            }
            for op_id in sorted(op_ids)
        },
        "native_command": ["<python>", "<isolated-native-model-execplan-main>", "<graph-input>"],
        "double_run": {
            "equal": True,
            "comparison": "double_run_comparison.json",
            "deterministic_file_count": len(comparison["files"]),
        },
        "execplan": {
            "artifact": f"pipeline_output/install/execplan.txt",
            "sha256": _sha256_file(execplan_path),
        },
        "validation_report": {
            "artifact": "execplan_validation_report.json",
            "sha256": _sha256_file(validation_path),
            "valid": True,
        },
        "package_validation_report": (
            {
                "artifact": "package_validation_report.json",
                "sha256": _sha256_file(package_validation_path),
                "valid": True,
                "matrix_files_required": False,
            }
            if package_validation is not None
            else None
        ),
        "request_address_validation_report": {
            "artifact": "request_address_validation_report.json",
            "sha256": _sha256_file(request_validation_path),
            "valid": True,
            "request_count_with_multiplicity": request_validation["facts"][
                "request_count_with_multiplicity"
            ],
            "unique_request_address_count": request_validation["facts"][
                "unique_request_address_count"
            ],
        },
        "files": _file_hash_map(output_dir),
    }
    manifest_path = output_dir / "bundle_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return ExecPlanEvidenceBundle(
        output_dir=output_dir,
        manifest_path=manifest_path,
        validation_report_path=validation_path,
        valid=True,
        execplan_sha256=_sha256_file(execplan_path),
        deterministic_file_count=len(comparison["files"]),
    )


def _validate_run(
    *,
    graph_root: Path,
    graph_withbaseaddr: Path,
    validated: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    return OperatorConfigExecPlanValidator().validate(
        graph_root,
        graph_path=graph_withbaseaddr,
        source_configs={op_id: Path(item["config"]) for op_id, item in validated.items()},
        mapping_evidence={op_id: item["evidence"] for op_id, item in validated.items()},
        artifact_dirs={op_id: Path(item["bundle"]) for op_id, item in validated.items()},
    ).to_dict()


def _copy_native_tool(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    shutil.copytree(
        source / "bitstream",
        destination / "bitstream",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "mapping_cache", "placement_failed.png"),
    )
    shutil.copytree(
        source / "jsons",
        destination / "jsons",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    model = destination / "model_execplan"
    model.mkdir()
    shutil.copy2(source / "model_execplan" / "main.py", model / "main.py")
    shutil.copytree(source / "model_execplan" / "src", model / "src")
    shutil.copytree(source / "model_execplan" / "config", model / "config")


def _merge_mapping_caches(
    validated: Mapping[str, Mapping[str, Any]], destination: Path
) -> None:
    for op_id in sorted(validated):
        for source in validated[op_id]["cache_files"]:
            target = destination / source.name
            if target.exists() and target.read_bytes() != source.read_bytes():
                raise ValueError(f"mapping cache filename collision with different bytes: {source.name}")
            if not target.exists():
                shutil.copy2(source, target)


def _install_validated_configs(
    tool_root: Path,
    operators: list[dict[str, str]],
    validated: Mapping[str, Mapping[str, Any]],
) -> None:
    """Make the disposable planner consume the exact mapping-bound config.

    The native graph format selects JSON by operator type, not by an arbitrary
    source path.  Installing the validated source in the disposable checkout
    prevents a legacy JSON with the same type from bypassing strict cleanup.
    """

    by_type: dict[str, bytes] = {}
    for operator in operators:
        op_id, op_type = operator["id"], operator["type"]
        source = Path(validated[op_id]["config"])
        payload = source.read_bytes()
        previous = by_type.get(op_type)
        if previous is not None and previous != payload:
            raise ValueError(
                f"native graph uses one JSON per operator type, but {op_type} "
                "is bound to multiple source configs"
            )
        by_type[op_type] = payload
        target = tool_root / "jsons" / f"{op_type}.json"
        target.write_bytes(payload)


def _graph_operators(graph: Mapping[str, Any]) -> list[dict[str, str]]:
    raw = graph.get("operators")
    if not isinstance(raw, list) or not raw:
        raise ValueError("graph operators must be a non-empty array")
    result: list[dict[str, str]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise ValueError(f"graph operator {index} must be an object")
        op_id, op_type = item.get("id"), item.get("type")
        if not isinstance(op_id, str) or not op_id or not isinstance(op_type, str) or not op_type:
            raise ValueError(f"graph operator {index} requires id and type")
        result.append({"id": op_id, "type": op_type})
    if len({item["id"] for item in result}) != len(result):
        raise ValueError("graph operator ids must be unique")
    return result


def _deterministic_output_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256_file(path)
        for path in _files(root)
        if path.name not in NONDETERMINISTIC_OUTPUTS
    }


def _native_source_manifest(root: Path) -> dict[str, Any]:
    selected: list[Path] = []
    for path in (
        root / "bitstream",
        root / "jsons",
        root / "model_execplan" / "src",
        root / "model_execplan" / "config",
    ):
        selected.extend(_files(path))
    selected.append(root / "model_execplan" / "main.py")
    selected = [
        path for path in selected
        if "__pycache__" not in path.parts
        and "mapping_cache" not in path.parts
        and path.suffix != ".pyc"
    ]
    digest = hashlib.sha256()
    files = []
    for path in sorted(set(selected)):
        relative = path.relative_to(root).as_posix()
        sha = _sha256_file(path)
        size = path.stat().st_size
        files.append({"path": relative, "size": size, "sha256": sha})
        digest.update(f"{relative}\0{sha}\0{size}\n".encode("utf-8"))
    return {
        "schema": "native-execplan-source-manifest-v1",
        "file_count": len(files),
        "tree_sha256": digest.hexdigest(),
        "files": files,
    }


def _file_hash_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "size": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in _files(root)
        if path.name != "bundle_manifest.json"
    }


def _files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _load_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def _git_output(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={root.as_posix()}", "-C", str(root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip())
    return completed.stdout.decode("utf-8", errors="replace").strip()


def _install_patchset_base_files(
    *,
    source_root: Path,
    tool_root: Path,
    patchset: Mapping[str, Any],
) -> None:
    commit = str(patchset["base_commit"])
    for item in patchset["files"]:
        relative = str(item["path"])
        completed = subprocess.run(
            [
                "git",
                "-c",
                f"safe.directory={source_root.as_posix()}",
                "-C",
                str(source_root),
                "show",
                f"{commit}:{relative}",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                completed.stderr.decode("utf-8", errors="replace").strip()
            )
        target = tool_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(completed.stdout)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tail(data: bytes) -> list[str]:
    return data.decode("utf-8", errors="replace").splitlines()[-10:]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
