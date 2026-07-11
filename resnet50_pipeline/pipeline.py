from __future__ import annotations

import json
import os
import platform
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .artifacts import ArtifactManager
from .backends import Backend
from .contracts import load_contracts
from .errors import ArtifactError, ManifestVersionError, PipelineError
from .hashing import combined_hash, sha256_file, source_tree_hash
from .manifest import RunManifest, StageAttempt
from .records import mock_object_manifest

STAGES = (
    "prepare",
    "golden",
    "layout",
    "config",
    "simulate",
    "execplan",
    "hardware",
    "compare",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def environment_record() -> dict[str, Any]:
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "cwd": os.getcwd(),
    }


def execute_mock_run(
    project_root: Path,
    output_root: Path,
    backend: Backend,
    *,
    input_path: Path | None = None,
    op: str = "MockIdentity",
    dtype: str = "uint8",
    slice_count: int = 16,
    config_version: str = "mock-0.1",
    resume: bool = False,
) -> RunManifest:
    project_root = project_root.resolve()
    graph_path = project_root / "fixtures" / "mock_graph.json"
    if input_path is None:
        input_path = graph_path
    if not input_path.is_file():
        raise ArtifactError(f"input does not exist: {input_path}")

    contracts = load_contracts(project_root / "contracts")
    repos_path = project_root / "repos.lock.json"
    if not repos_path.is_file():
        raise ArtifactError(f"repository lock does not exist: {repos_path}")
    repositories = json.loads(repos_path.read_text(encoding="utf-8"))
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    objects = mock_object_manifest(graph)
    input_hash = sha256_file(input_path)
    repos_hash = sha256_file(repos_path)
    code_hash = source_tree_hash(project_root / "resnet50_pipeline")
    environment = environment_record()
    environment_hash = combined_hash(
        (
            environment["python"],
            environment["implementation"],
            environment["platform"],
        )
    )
    environment["digest"] = environment_hash
    environment["integration_code_sha256"] = code_hash
    cache_key = combined_hash(
        (
            input_hash,
            contracts.digest,
            repos_hash,
            code_hash,
            environment_hash,
            backend.capabilities.name,
            backend.capabilities.version,
            op,
            dtype,
            str(slice_count),
            config_version,
        )
    )
    if resume:
        reusable = find_reusable_manifest(output_root, cache_key)
        if reusable is not None:
            return reusable
    run_id = f"w0-{uuid.uuid4().hex[:12]}"
    manager = ArtifactManager(output_root / run_id)
    stages = [StageAttempt(name=name) for name in STAGES]
    manifest = RunManifest(
        run_id=run_id,
        created_at=utc_now(),
        status="running",
        cache_key=cache_key,
        environment=environment,
        inputs={"path": str(input_path), "sha256": input_hash},
        contracts={"hashes": contracts.hashes, "digest": contracts.digest},
        repositories={"lock_sha256": repos_hash, "value": repositories},
        objects=objects,
        stages=stages,
    )

    try:
        backend.capabilities.require(op, dtype, slice_count, config_version)
        payload = {
            "op": op,
            "dtype": dtype,
            "slice_count": slice_count,
            "config_version": config_version,
            "input_sha256": input_hash,
        }
        for stage in stages:
            stage.status = "running"
            stage.started_at = utc_now()
            try:
                result = backend.execute(stage.name, payload)
                record = manager.write_json(f"stages/{stage.name}/result.json", result)
                stage.artifacts.append(record)
                stage.status = "succeeded"
            except Exception as error:
                stage.status = "failed"
                stage.error = f"{type(error).__name__}: {error}"
                raise
            finally:
                stage.finished_at = utc_now()
        manifest.status = "succeeded"
    except Exception as error:
        manifest.status = "failed"
        failed_seen = False
        for stage in stages:
            if stage.status == "failed":
                failed_seen = True
            elif stage.status == "pending" and failed_seen:
                stage.status = "blocked"
                stage.error = "blocked by an earlier stage failure"
        if not failed_seen:
            stages[0].status = "failed"
            stages[0].started_at = stages[0].started_at or utc_now()
            stages[0].finished_at = utc_now()
            stages[0].error = f"{type(error).__name__}: {error}"
            for stage in stages[1:]:
                stage.status = "blocked"
                stage.error = "blocked by prepare failure"
    finally:
        manager.write_json("manifest.json", manifest.to_dict())
    return manifest


def manifest_exit_code(manifest: RunManifest) -> int:
    return 0 if manifest.status == "succeeded" else 2


def find_reusable_manifest(output_root: Path, cache_key: str) -> RunManifest | None:
    if not output_root.is_dir():
        return None
    for path in sorted(output_root.glob("w0-*/manifest.json"), reverse=True):
        try:
            manifest = RunManifest.load(path)
        except (OSError, ValueError, ManifestVersionError, json.JSONDecodeError):
            continue
        if manifest.status != "succeeded" or manifest.cache_key != cache_key:
            continue
        manager = ArtifactManager(path.parent)
        if all(manager.verify(item) for stage in manifest.stages for item in stage.artifacts):
            return manifest
    return None
