from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Mapping, Sequence

from .deepseek_silu_holdout import _compute_native_mapping_penalty
from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


MAPPING_SEED = 42
PYTHON_HASH_SEED = 0


class DeepSeekNativeE2Error(ValueError):
    pass


def _write_object(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekNativeE2Error(
            f"cannot parse native E2 JSON: {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise DeepSeekNativeE2Error(f"JSON root must be an object: {path}")
    return value


def _relative_binding(base: Path, path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(base).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _copy_tree_without_runtime_state(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", "*.pyo", "mapping_cache", "output"
        ),
    )


def _build_tool_copy(
    root: Path,
    run_dir: Path,
    operator_types: Sequence[str],
    source_overlays: Mapping[str, str],
) -> tuple[Path, dict[str, Any]]:
    tool_root = run_dir / "t"
    tool_root.mkdir(parents=True)
    _copy_tree_without_runtime_state(
        root / "ndp-sim/bitstream", tool_root / "bitstream"
    )
    _copy_tree_without_runtime_state(
        root / "ndp-sim/model_execplan/src",
        tool_root / "model_execplan/src",
    )
    _copy_tree_without_runtime_state(
        root / "ndp-sim/model_execplan/config",
        tool_root / "model_execplan/config",
    )
    shutil.copy2(
        root / "ndp-sim/model_execplan/main.py",
        tool_root / "model_execplan/main.py",
    )
    json_root = tool_root / "jsons"
    json_root.mkdir()
    for op_type in sorted(set(operator_types)):
        source = root / "ndp-sim/jsons" / f"{op_type}.json"
        if not source.is_file():
            raise DeepSeekNativeE2Error(
                f"trusted native JSON is missing: {source}"
            )
        shutil.copy2(source, json_root / source.name)

    overlay_receipts: list[dict[str, Any]] = []
    for target_relative, source_relative in sorted(
        source_overlays.items()
    ):
        source = (root / source_relative).resolve()
        target = (tool_root / target_relative).resolve()
        if (
            not source.is_file()
            or not target.is_file()
            or not target.is_relative_to(tool_root.resolve())
        ):
            raise DeepSeekNativeE2Error(
                "isolated tool overlay source/target differs: "
                f"{source_relative} -> {target_relative}"
            )
        preimage = {
            "size_bytes": target.stat().st_size,
            "sha256": sha256_file(target),
        }
        shutil.copy2(source, target)
        overlay_receipts.append(
            {
                "source": _relative_binding(root, source),
                "target": target.relative_to(tool_root).as_posix(),
                "target_preimage": preimage,
                "target_postimage": {
                    "size_bytes": target.stat().st_size,
                    "sha256": sha256_file(target),
                },
            }
        )

    cache_dir = tool_root / "bitstream/config/mapping_cache"
    initial_cache = (
        [path for path in cache_dir.iterdir() if path.is_file()]
        if cache_dir.is_dir()
        else []
    )
    if initial_cache:
        raise DeepSeekNativeE2Error(
            "isolated native tool copy contains mapping-cache files"
        )
    source_files = sorted(
        path for path in tool_root.rglob("*") if path.is_file()
    )
    manifest: dict[str, Any] = {
        "schema": "deepseek-native-e2-tool-copy-v1",
        "source_checkout": {
            "path": "ndp-sim",
            "active_checkout_mutated": False,
        },
        "operator_types": list(operator_types),
        "isolated_overlays": overlay_receipts,
        "cache_initial_file_count": 0,
        "files": [
            _relative_binding(tool_root, path) for path in source_files
        ],
    }
    manifest["manifest_sha256"] = sha256_bytes(
        canonical_json_bytes(manifest)
    )
    _write_object(run_dir / "tool_source_manifest.json", manifest)
    return tool_root, manifest


def _required_output_paths(
    graph_name: str,
    operator_types: Sequence[str],
    sfu_types: Sequence[str],
) -> set[str]:
    required = {
        "install/execplan.txt",
        "instructions_explained.txt",
        "sca_cfg.json",
        "sca_cfg_D.json",
        f"{graph_name}_withbaseaddr.json",
    }
    for index, op_type in enumerate(operator_types):
        op_id = f"op{index}"
        stem = f"{op_id}_{op_type}"
        required.update(
            {
                f"jsons/{stem}.json",
                f"config/{op_id}/parsed_bitstream.txt",
                f"config/{op_id}/mapping_review.json",
                f"config/{op_id}/detailed_dump.txt",
                f"config/{op_id}/placement.png",
                f"config/{op_id}/modules_dump_64b.bin",
                f"config/{op_id}/modules_dump_128b.bin",
                f"config/{op_id}/{stem}_bitstream_64b.bin",
                f"config/{op_id}/{stem}_bitstream_128b.bin",
                f"install/execplan_{op_id}.txt",
                f"install/cfg_pkg/{stem}_bitstream_128b.bin",
            }
        )
    required.update(
        f"install/cfg_pkg/{sfu_type}.txt" for sfu_type in sfu_types
    )
    return required


def _validate_required_outputs(
    output_dir: Path,
    graph_name: str,
    operator_types: Sequence[str],
    sfu_types: Sequence[str],
) -> None:
    if not output_dir.is_dir():
        raise DeepSeekNativeE2Error(
            f"native output directory is missing: {output_dir}"
        )
    actual = {
        path.relative_to(output_dir).as_posix()
        for path in output_dir.rglob("*")
        if path.is_file()
    }
    missing = sorted(
        _required_output_paths(
            graph_name, operator_types, sfu_types
        )
        - actual
    )
    if missing:
        raise DeepSeekNativeE2Error(
            f"native output set is incomplete: {missing}"
        )


def _run_once(
    root: Path,
    artifact_root: Path,
    graph_name: str,
    graph: Mapping[str, Any],
    operator_types: Sequence[str],
    sfu_types: Sequence[str],
    run_name: str,
    python_executable: Path,
    mapping_seed: int,
    inject_bitstream_seed: bool,
    source_overlays: Mapping[str, str],
) -> dict[str, Any]:
    run_dir = artifact_root / run_name
    if run_dir.exists():
        raise DeepSeekNativeE2Error(
            f"isolated run target already exists: {run_dir}"
        )
    run_dir.mkdir(parents=True)
    tool_root, source_manifest = _build_tool_copy(
        root, run_dir, operator_types, source_overlays
    )
    input_dir = tool_root / "input"
    input_dir.mkdir()
    graph_path = input_dir / f"{graph_name}.json"
    _write_object(graph_path, graph)

    seed_hook_dir = run_dir / "seed_hook"
    seed_hook_dir.mkdir()
    seed_hook = seed_hook_dir / "sitecustomize.py"
    seed_hook_source = (
        "import random\n"
        f"random.seed({mapping_seed})\n"
    )
    if inject_bitstream_seed:
        seed_hook_source += (
            "import subprocess\n"
            "_ndp_original_run = subprocess.run\n"
            "def _ndp_seeded_run(*args, **kwargs):\n"
            "    command = args[0] if args else kwargs.get('args')\n"
            "    if isinstance(command, (list, tuple)) and any(\n"
            "        str(item).replace('\\\\', '/').endswith("
            "'bitstream/main.py') for item in command\n"
            "    ) and '--seed' not in command:\n"
            "        command = list(command) + "
            f"['--seed', '{mapping_seed}']\n"
            "        if args:\n"
            "            args = (command, *args[1:])\n"
            "        else:\n"
            "            kwargs['args'] = command\n"
            "    return _ndp_original_run(*args, **kwargs)\n"
            "subprocess.run = _ndp_seeded_run\n"
        )
    seed_hook.write_text(seed_hook_source, encoding="utf-8")
    env = {
        **os.environ,
        "PYTHONUTF8": "1",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": str(PYTHON_HASH_SEED),
        "PYTHONPATH": os.pathsep.join(
            filter(
                None,
                (
                    str(seed_hook_dir.resolve()),
                    os.environ.get("PYTHONPATH"),
                ),
            )
        ),
    }
    command = [
        str(python_executable),
        str(tool_root / "model_execplan/main.py"),
        str(graph_path),
    ]
    completed = subprocess.run(
        command,
        cwd=tool_root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    stdout_path = run_dir / "native_stdout.log"
    stderr_path = run_dir / "native_stderr.log"
    stdout_path.write_text(completed.stdout, encoding="utf-8")
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        raise DeepSeekNativeE2Error(
            f"native model_execplan failed in {run_name}: "
            f"rc={completed.returncode}"
        )
    if f"Parsed operators: {len(operator_types)}" not in completed.stdout:
        raise DeepSeekNativeE2Error(
            f"native pipeline did not complete {len(operator_types)} "
            f"operators in {run_name}"
        )

    output_dir = tool_root / "model_execplan/output" / graph_name
    _validate_required_outputs(
        output_dir, graph_name, operator_types, sfu_types
    )
    penalties: dict[str, float] = {}
    for index in range(len(operator_types)):
        op_id = f"op{index}"
        review = _load_object(
            output_dir / "config" / op_id / "mapping_review.json"
        )
        penalty = _compute_native_mapping_penalty(root, review)
        if penalty != 0:
            raise DeepSeekNativeE2Error(
                f"{op_id} mapping penalty is {penalty}, expected 0"
            )
        penalties[op_id] = penalty

    cache_dir = tool_root / "bitstream/config/mapping_cache"
    cache_files = (
        sorted(path for path in cache_dir.iterdir() if path.is_file())
        if cache_dir.is_dir()
        else []
    )
    if not cache_files:
        raise DeepSeekNativeE2Error(
            "native pipeline did not publish mapping-cache receipts"
        )
    receipt: dict[str, Any] = {
        "schema": "deepseek-native-e2-run-receipt-v1",
        "run_name": run_name,
        "returncode": completed.returncode,
        "parsed_operator_count": len(operator_types),
        "mapping_exact_penalties": penalties,
        "mapping_determinism": {
            "random_seed": mapping_seed,
            "python_hash_seed": PYTHON_HASH_SEED,
            "mechanism": (
                "isolated PYTHONPATH sitecustomize hook with explicit "
                "bitstream --seed injection"
                if inject_bitstream_seed
                else "isolated PYTHONPATH sitecustomize hook"
            ),
            "explicit_bitstream_seed_injected": inject_bitstream_seed,
            "native_source_modified": False,
            "isolated_tool_overlay_applied": bool(source_overlays),
            "isolated_tool_overlays": source_manifest[
                "isolated_overlays"
            ],
            "hook": _relative_binding(run_dir, seed_hook),
        },
        "initial_mapping_cache_file_count": 0,
        "post_run_mapping_cache": [
            _relative_binding(tool_root, path) for path in cache_files
        ],
        "tool_source_manifest": {
            "path": "tool_source_manifest.json",
            "sha256": source_manifest["manifest_sha256"],
        },
        "stdout": _relative_binding(run_dir, stdout_path),
        "stderr": _relative_binding(run_dir, stderr_path),
        "output_root": output_dir.relative_to(run_dir).as_posix(),
        "output_files": [
            _relative_binding(output_dir, path)
            for path in sorted(output_dir.rglob("*"))
            if path.is_file()
        ],
    }
    receipt["receipt_sha256"] = sha256_bytes(
        canonical_json_bytes(receipt)
    )
    _write_object(run_dir / "native_run_receipt.json", receipt)
    return receipt


def _file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _compare_outputs(
    output_a: Path, output_b: Path
) -> dict[str, Any]:
    files_a = _file_map(output_a)
    files_b = _file_map(output_b)
    if set(files_a) != set(files_b):
        raise DeepSeekNativeE2Error(
            "isolated native output file sets differ"
        )
    exclusions = {
        path
        for path in files_a
        if path.startswith("config/") and path.endswith("/placement.png")
    }
    deterministic = sorted(set(files_a) - exclusions)
    mismatches = [
        path
        for path in deterministic
        if files_a[path] != files_b[path]
    ]
    if mismatches:
        raise DeepSeekNativeE2Error(
            f"isolated native deterministic outputs differ: {mismatches}"
        )
    return {
        "same_relative_file_set": True,
        "relative_file_count": len(files_a),
        "deterministic_file_count": len(deterministic),
        "deterministic_files_byte_identical": True,
        "registered_visualization_exclusions": sorted(exclusions),
        "visualizations_byte_identical": all(
            files_a[path] == files_b[path] for path in exclusions
        ),
    }


def run_double_isolated_native_graph(
    *,
    project_root: Path,
    artifact_root_relative: str,
    graph_name: str,
    graph: Mapping[str, Any],
    operator_types: Sequence[str],
    sfu_types: Sequence[str] = (),
    python_executable: Path,
    mapping_seed: int = MAPPING_SEED,
    inject_bitstream_seed: bool = False,
    source_overlays: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    root = project_root.resolve()
    artifact_root = root / artifact_root_relative
    if artifact_root.exists():
        raise DeepSeekNativeE2Error(
            f"artifact root already exists: {artifact_root}"
        )
    artifact_root.mkdir(parents=True)
    graph_path = artifact_root / f"{graph_name}.json"
    _write_object(graph_path, graph)
    overlays = dict(source_overlays or {})
    run_a = _run_once(
        root,
        artifact_root,
        graph_name,
        graph,
        operator_types,
        sfu_types,
        "a",
        python_executable,
        mapping_seed,
        inject_bitstream_seed,
        overlays,
    )
    run_b = _run_once(
        root,
        artifact_root,
        graph_name,
        graph,
        operator_types,
        sfu_types,
        "b",
        python_executable,
        mapping_seed,
        inject_bitstream_seed,
        overlays,
    )
    output_a = (
        artifact_root / "a/t/model_execplan/output" / graph_name
    )
    output_b = (
        artifact_root / "b/t/model_execplan/output" / graph_name
    )
    return {
        "graph": _relative_binding(root, graph_path),
        "run_a_receipt_sha256": run_a["receipt_sha256"],
        "run_b_receipt_sha256": run_b["receipt_sha256"],
        "comparison": _compare_outputs(output_a, output_b),
        "output_a": output_a.relative_to(root).as_posix(),
        "output_b": output_b.relative_to(root).as_posix(),
    }


__all__ = [
    "DeepSeekNativeE2Error",
    "MAPPING_SEED",
    "PYTHON_HASH_SEED",
    "run_double_isolated_native_graph",
]
