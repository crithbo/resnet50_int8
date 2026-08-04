from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .operator_config_artifact_validator import (
    ACTIVE_ENCODER_COMMIT,
    OperatorConfigArtifactValidator,
)
from .ndp_patch_toolchain import (
    PATCHED_FILES,
    apply_patchset_in_place,
    validate_patchset_manifest,
)
from .operator_config_validator import OperatorConfigValidator


CORE_ARTIFACTS = (
    "mapping_review.json",
    "parsed_bitstream.txt",
    "modules_dump_64b.bin",
    "modules_dump_128b.bin",
)
SUPPORT_ARTIFACTS = ("detailed_dump.txt", "native_mapping_state.json")


NATIVE_BUNDLE_WRAPPER = textwrap.dedent(
    r"""
    import json
    import platform
    import random
    import sys
    from pathlib import Path

    from bitstream.config.mapper import NodeGraph
    from bitstream.parse import (
        build_entries,
        dump_mapping_review,
        dump_modules_detailed,
        init_modules,
        load_config,
        write_bitstream,
    )

    config_path = Path(sys.argv[1])
    output = Path(sys.argv[2])
    seed = int(sys.argv[3])
    iterations = int(sys.argv[4])
    restarts = int(sys.argv[5])
    output.mkdir(parents=True, exist_ok=True)
    random.seed(seed)
    config = load_config(str(config_path))
    modules = init_modules(
        config,
        use_direct_mapping=False,
        use_heuristic_search=True,
        heuristic_iterations=iterations,
        heuristic_restarts=restarts,
        seed=seed,
        output_dir=str(output),
    )
    graph = NodeGraph.get()
    mapper = graph.mapping
    dump_mapping_review(str(output / "mapping_review.json"))
    dump_modules_detailed(modules, output_file=str(output / "detailed_dump.txt"))
    entries = build_entries(modules, output_dir=str(output))
    write_bitstream(
        entries,
        config_mask=[int(bit) for bit in config["CONFIG"]],
        output_file=str(output / "parsed_bitstream.txt"),
        binary_output_file=str(output / "modules_dump.bin"),
    )
    mapping = dict(mapper.node_to_resource)
    state = {
        "schema": "native-mapping-state-v1",
        "last_mapping_cost": mapper.get_last_mapping_cost(),
        "fallback_nodes": sorted(node for node in graph.nodes if node not in mapping),
        "graph_nodes": sorted(graph.nodes),
        "connection_count": len(graph.connections),
        "mapping_size": len(mapping),
        "python_version": platform.python_version(),
        "seed": seed,
        "heuristic_iterations": iterations,
        "heuristic_restarts": restarts,
    }
    (output / "native_mapping_state.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    """
).strip()


@dataclass(frozen=True)
class MappingEvidenceBundle:
    output_dir: Path
    evidence_path: Path
    validation_report_path: Path
    manifest_path: Path
    valid: bool
    penalty: float
    mapping_review_sha256: str
    bundle_tree_sha256: str


def create_mapping_evidence_bundle(
    *,
    ndp_sim_root: Path,
    config_path: Path,
    output_dir: Path,
    python_executable: Path,
    seed: int = 42,
    heuristic_iterations: int = 10_000,
    heuristic_restarts: int = 10,
    expected_encoder_commit: str = ACTIVE_ENCODER_COMMIT,
    timeout_seconds: int = 300,
    patchset_manifest_path: Path | None = None,
    frozen_cache_path: Path | None = None,
) -> MappingEvidenceBundle:
    """Generate a self-contained native mapping/bitstream evidence bundle.

    The active ndp-sim tree and source JSON are only read.  Native execution is
    performed in a disposable copy whose mapping cache is verified empty before
    the run, except for an explicitly supplied cache from a pinned Git checkout.
    Such a cache is accepted only if the native mapper loads it and recomputes
    exact zero cost.  Only a zero-penalty, independently validated result is
    published.
    """

    ndp_sim_root = ndp_sim_root.resolve()
    config_path = config_path.resolve()
    output_dir = output_dir.resolve()
    python_executable = python_executable.resolve()
    patchset_manifest_path = (
        patchset_manifest_path.resolve() if patchset_manifest_path is not None else None
    )
    frozen_cache_path = (
        frozen_cache_path.resolve() if frozen_cache_path is not None else None
    )
    frozen_cache_origin: dict[str, str] | None = None
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite evidence bundle: {output_dir}")
    if _is_relative_to(output_dir, ndp_sim_root):
        raise ValueError("evidence bundle must be outside the read-only ndp-sim tree")
    if "ndp-sim-ref" in {part.lower() for part in config_path.parts}:
        raise ValueError("ndp-sim-ref is not an authorized evidence source")
    if not config_path.is_file():
        raise FileNotFoundError(config_path)
    if not python_executable.is_file():
        raise FileNotFoundError(python_executable)
    if frozen_cache_path is not None:
        if not frozen_cache_path.is_file():
            raise FileNotFoundError(frozen_cache_path)
        if not re.fullmatch(r"[0-9a-f]{16}\.json", frozen_cache_path.name):
            raise ValueError("frozen mapping cache filename must be a 16-hex native cache key")
        frozen_payload = json.loads(frozen_cache_path.read_text(encoding="utf-8"))
        if not isinstance(frozen_payload, dict) or not frozen_payload:
            raise ValueError("frozen mapping cache must be a non-empty JSON object")
        frozen_cache_origin = _git_artifact_identity(frozen_cache_path)
        if frozen_cache_origin is None:
            raise ValueError("frozen mapping cache must come from a pinned Git checkout")

    patchset: dict[str, Any] | None = None
    if patchset_manifest_path is not None:
        if not patchset_manifest_path.is_file():
            raise FileNotFoundError(patchset_manifest_path)
        patchset = json.loads(patchset_manifest_path.read_text(encoding="utf-8"))
        validate_patchset_manifest(patchset, ndp_sim_root)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    strict = OperatorConfigValidator().validate(config, source=str(config_path))
    if not strict.valid:
        first = strict.issues[0]
        raise ValueError(f"strict config rejected at {first.path}: {first.code}: {first.message}")

    commit = _git_head(ndp_sim_root)
    if commit != expected_encoder_commit:
        raise ValueError(f"ndp-sim commit {commit} differs from pinned {expected_encoder_commit}")

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="operator-config-evidence-", dir=output_dir.parent
    ) as temp_text:
        temp = Path(temp_text)
        tool_root = temp / "tool"
        shutil.copytree(
            ndp_sim_root / "bitstream",
            tool_root / "bitstream",
            ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "mapping_cache", "placement_failed.png"
            ),
        )
        if patchset is not None:
            _install_patchset_base_files(
                source_root=ndp_sim_root,
                tool_root=tool_root,
                patchset=patchset,
            )
            mapper_path = next(
                spec.relative_path
                for spec in PATCHED_FILES
                if spec.relative_path == "bitstream/config/mapper.py"
            )
            applied = apply_patchset_in_place(
                tool_root,
                patchset_id=patchset["patchset_id"],
                relative_paths=[mapper_path],
            )
            expected_mapper = next(
                item for item in patchset["files"] if item["path"] == mapper_path
            )
            if applied["files"] != [expected_mapper]:
                raise RuntimeError("applied mapper patch differs from locked patchset manifest")
        source_manifest = _tree_manifest(tool_root / "bitstream")
        cache_dir = tool_root / "bitstream/config/mapping_cache"
        initial_cache_files = _files(cache_dir)
        if initial_cache_files:
            raise RuntimeError("isolated tool tree unexpectedly contains an initial mapping cache")
        if frozen_cache_path is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(frozen_cache_path, cache_dir / frozen_cache_path.name)
            initial_cache_files = _files(cache_dir)
            if len(initial_cache_files) != 1:
                raise RuntimeError("frozen mapping cache seed was not installed exactly once")

        native_output = temp / "native-output"
        command = [
            str(python_executable),
            "-c",
            NATIVE_BUNDLE_WRAPPER,
            str(config_path),
            str(native_output),
            str(seed),
            str(heuristic_iterations),
            str(heuristic_restarts),
        ]
        display_command = [
            "<python>",
            "-c",
            "<operator-config-evidence-native-wrapper-v1>",
            "<source-config>",
            "<temporary-output>",
            str(seed),
            str(heuristic_iterations),
            str(heuristic_restarts),
        ]
        environment = dict(os.environ)
        environment["PYTHONIOENCODING"] = "utf-8"
        environment["MPLBACKEND"] = "Agg"
        environment["PYTHONHASHSEED"] = "0"
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
            stdout_tail = completed.stdout.decode("utf-8", errors="replace").splitlines()[-10:]
            stderr_tail = completed.stderr.decode("utf-8", errors="replace").splitlines()[-10:]
            raise RuntimeError(
                f"native evidence run failed rc={completed.returncode}; "
                f"stdout_tail={stdout_tail}; stderr_tail={stderr_tail}"
            )
        missing = [
            name for name in (*CORE_ARTIFACTS, *SUPPORT_ARTIFACTS)
            if not (native_output / name).is_file()
        ]
        if missing:
            raise RuntimeError(f"native evidence run omitted required artifacts: {missing}")

        state = json.loads(
            (native_output / "native_mapping_state.json").read_text(encoding="utf-8")
        )
        penalty = state.get("last_mapping_cost")
        if not isinstance(penalty, (int, float)) or isinstance(penalty, bool) or penalty != 0:
            raise RuntimeError(f"mapping penalty is not zero: {penalty!r}")
        if state.get("fallback_nodes") != []:
            raise RuntimeError(f"native mapping contains fallback nodes: {state.get('fallback_nodes')}")

        final_cache_files = _files(cache_dir)
        stdout_text = completed.stdout.decode("utf-8", errors="replace")
        cache_loaded = "Loaded cached mapping" in stdout_text
        if frozen_cache_path is not None and not cache_loaded:
            raise RuntimeError("frozen mapping cache key was not consumed by the native mapper")
        if cache_loaded and not final_cache_files:
            raise RuntimeError("native stdout reports a cache load but no same-run cache was retained")

        bundle = temp / "bundle"
        bundle.mkdir()
        for name in (*CORE_ARTIFACTS, *SUPPORT_ARTIFACTS):
            shutil.copy2(native_output / name, bundle / name)
        shutil.copy2(config_path, bundle / "source_config.json")
        (bundle / "native_stdout.log").write_bytes(completed.stdout)
        (bundle / "native_stderr.log").write_bytes(completed.stderr)
        (bundle / "encoder_source_manifest.json").write_text(
            json.dumps(source_manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if patchset is not None:
            (bundle / "patchset_manifest.json").write_text(
                json.dumps(patchset, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        if final_cache_files:
            shutil.copytree(cache_dir, bundle / "mapping_cache")

        artifact_hashes = {
            name: _sha256_file(bundle / name) for name in CORE_ARTIFACTS
        }
        cache_tree_sha = (
            _tree_manifest(bundle / "mapping_cache")["tree_sha256"]
            if final_cache_files
            else None
        )
        cache_policy = (
            "frozen"
            if frozen_cache_path is not None
            else "same-run-generated-loaded"
            if cache_loaded
            else "same-run-generated-not-loaded"
            if final_cache_files
            else "empty"
        )
        evidence: dict[str, Any] = {
            "schema": "operator-config-mapping-evidence-v2",
            "mapping_mode": (
                "frozen-zero-penalty" if frozen_cache_path is not None else "heuristic"
            ),
            "penalty": penalty,
            "penalty_source": {
                "artifact": "native_mapping_state.json",
                "json_path": "$.last_mapping_cost",
                "sha256": _sha256_file(bundle / "native_mapping_state.json"),
            },
            "fallback_used": False,
            "mapping_review_sha256": artifact_hashes["mapping_review.json"],
            "encoder": {
                "repository": "ndp-sim",
                "commit": commit,
                "bitstream_tree_sha256": source_manifest["tree_sha256"],
                "source_manifest": "encoder_source_manifest.json",
                "source_manifest_sha256": _sha256_file(bundle / "encoder_source_manifest.json"),
                "patchset": (
                    {
                        "manifest": "patchset_manifest.json",
                        "manifest_sha256": _sha256_file(bundle / "patchset_manifest.json"),
                        "patchset_id": patchset["patchset_id"],
                        "patchset_sha256": patchset["patchset_sha256"],
                    }
                    if patchset is not None
                    else None
                ),
            },
            "source_config": {
                "artifact": "source_config.json",
                "sha256": _sha256_file(bundle / "source_config.json"),
                "original_path": _portable_source_path(config_path, ndp_sim_root),
            },
            "cache": {
                "policy": cache_policy,
                "initial_file_count": len(initial_cache_files),
                "final_file_count": len(final_cache_files),
                "loaded": cache_loaded,
                "loaded_origin": (
                    "frozen-bundled-seed"
                    if frozen_cache_path is not None
                    else "same-run-generated"
                    if cache_loaded
                    else "none"
                ),
                "portable": True,
                "bundled": bool(final_cache_files),
                "sha256": cache_tree_sha,
                "seed": (
                    {
                        "artifact": f"mapping_cache/{frozen_cache_path.name}",
                        "sha256": _sha256_file(bundle / "mapping_cache" / frozen_cache_path.name),
                        "origin": frozen_cache_origin,
                        "validation": "native mapper recomputed total constraint cost as exactly zero",
                    }
                    if frozen_cache_path is not None
                    else None
                ),
            },
            "run": {
                "returncode": completed.returncode,
                "seed": seed,
                "heuristic_iterations": heuristic_iterations,
                "heuristic_restarts": heuristic_restarts,
                "python_version": state.get("python_version"),
                "pythonhashseed": 0,
                "command": display_command,
                "stdout": {
                    "artifact": "native_stdout.log",
                    "sha256": _sha256_file(bundle / "native_stdout.log"),
                },
                "stderr": {
                    "artifact": "native_stderr.log",
                    "sha256": _sha256_file(bundle / "native_stderr.log"),
                },
                "native_wrapper_missing_return_observed": (
                    "Found violations (penalty: inf)" in stdout_text
                    and "Loaded cached mapping" in stdout_text
                ),
            },
            "artifacts": artifact_hashes,
        }
        evidence_path = bundle / "mapping_evidence.json"
        evidence_path.write_text(
            json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        artifact_report = OperatorConfigArtifactValidator(
            expected_encoder_commit=expected_encoder_commit
        ).validate(
            config,
            bundle,
            mapping_evidence=evidence,
            source="source_config.json",
        )
        validation_path = bundle / "artifact_validation_report.json"
        validation_path.write_text(
            json.dumps(artifact_report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if not artifact_report.valid:
            first = artifact_report.issues[0]
            raise RuntimeError(
                f"independent artifact validation failed at {first.path}: {first.code}: {first.message}"
            )

        manifest: dict[str, Any] = {
            "schema": "operator-config-mapping-evidence-bundle-v1",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "read_only_native_source": True,
            "source_config_sha256": _sha256_file(bundle / "source_config.json"),
            "mapping_evidence_sha256": _sha256_file(evidence_path),
            "artifact_validation_report_sha256": _sha256_file(validation_path),
            "summary": {
                "valid": True,
                "penalty": penalty,
                "fallback_used": False,
                "cache_policy": cache_policy,
                "cache_loaded_origin": evidence["cache"]["loaded_origin"],
                "native_wrapper_missing_return_observed": evidence["run"][
                    "native_wrapper_missing_return_observed"
                ],
                "unpadded_bits": artifact_report.facts["mirror"]["unpadded_bits"],
                "bit_range_count": artifact_report.facts["mirror"]["bit_range_count"],
            },
            "files": _file_hash_map(bundle),
        }
        manifest_path = bundle / "bundle_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        shutil.move(str(bundle), str(output_dir))

    final_manifest = output_dir / "bundle_manifest.json"
    final_evidence = output_dir / "mapping_evidence.json"
    final_validation = output_dir / "artifact_validation_report.json"
    return MappingEvidenceBundle(
        output_dir=output_dir,
        evidence_path=final_evidence,
        validation_report_path=final_validation,
        manifest_path=final_manifest,
        valid=True,
        penalty=float(penalty),
        mapping_review_sha256=artifact_hashes["mapping_review.json"],
        bundle_tree_sha256=_tree_manifest(output_dir)["tree_sha256"],
    )


def _git_head(root: Path) -> str:
    completed = subprocess.run(
        [
            "git",
            "-c",
            f"safe.directory={root.as_posix()}",
            "-C",
            str(root),
            "rev-parse",
            "HEAD",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip())
    return completed.stdout.decode("ascii").strip()


def _install_patchset_base_files(
    *,
    source_root: Path,
    tool_root: Path,
    patchset: Mapping[str, Any],
) -> None:
    """Seed disposable patch targets from the locked Git commit.

    The active checkout is intentionally allowed to carry unrelated user
    experiments.  A patchset names an immutable base commit, so applying it to
    a disposable tool must start from those Git blobs rather than from mutable
    worktree bytes.
    """

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


def _git_artifact_identity(path: Path) -> dict[str, str] | None:
    for candidate in (path.parent, *path.parents):
        if (candidate / ".git").exists():
            commit = _git_head(candidate)
            if not re.fullmatch(r"[0-9a-f]{40}", commit):
                return None
            return {
                "repository": candidate.name,
                "commit": commit,
                "path": path.relative_to(candidate).as_posix(),
            }
    return None


def _tree_manifest(root: Path) -> dict[str, Any]:
    files = []
    digest = hashlib.sha256()
    for path in _files(root):
        relative = path.relative_to(root).as_posix()
        sha = _sha256_file(path)
        size = path.stat().st_size
        files.append({"path": relative, "size": size, "sha256": sha})
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha.encode("ascii"))
        digest.update(b"\0")
        digest.update(str(size).encode("ascii"))
        digest.update(b"\n")
    return {
        "schema": "sha256-tree-manifest-v1",
        "root": root.name,
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
    }


def _files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.rglob("*") if path.is_file())


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_source_path(config_path: Path, ndp_sim_root: Path) -> str:
    try:
        return f"ndp-sim/{config_path.relative_to(ndp_sim_root).as_posix()}"
    except ValueError:
        return config_path.name


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
