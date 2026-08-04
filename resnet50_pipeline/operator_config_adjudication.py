from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .operator_config_validator import OperatorConfigValidator, TargetProfile


CORE_NATIVE_ARTIFACTS = (
    "mapping_review.json",
    "parsed_bitstream.txt",
    "modules_dump_64b.bin",
    "modules_dump_128b.bin",
)
READ_ONLY_STREAM_FIELDS = (
    "padding_enable",
    "padding_reg_value",
    "idx_padding_range",
    "buf_full_last_index",
)


@dataclass(frozen=True)
class NormalizationChange:
    kind: str
    path: str
    before: Any
    after: Any


@dataclass(frozen=True)
class NativeEncoderRun:
    returncode: int
    mapping_mode: str
    mapping_cache_policy: str
    mapping_cache_source_sha256: str | None
    loaded_cached_mapping: bool
    zero_penalty_mapping: bool
    command: list[str]
    stdout_sha256: str
    stderr_sha256: str
    stdout_tail: list[str]
    stderr_tail: list[str]
    artifact_sha256: dict[str, str]
    artifact_size: dict[str, int]
    detailed_dump_sha256: str | None


@dataclass(frozen=True)
class NativeFieldProbe:
    returncode: int
    command: list[str]
    stdout_sha256: str
    stderr_sha256: str
    stderr_tail: list[str]
    proof_sha256: str | None
    proof: dict[str, Any] | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalize_known_legacy_expressions(
    config: Mapping[str, Any],
) -> tuple[dict[str, Any], list[NormalizationChange]]:
    """Return a normalized copy; never mutate the supplied legacy object."""

    normalized = copy.deepcopy(dict(config))
    changes: list[NormalizationChange] = []
    streams = normalized.get("stream_engine", {})
    if not isinstance(streams, dict):
        return normalized, changes

    for stream_name, stream in streams.items():
        if not isinstance(stream, dict):
            continue
        path = f"$.stream_engine.{stream_name}"
        mode = stream.get("mode")
        if mode == "read" and stream.get("padding_reg_value") is None:
            padding_enable = stream.get("padding_enable")
            if isinstance(padding_enable, list) and any(item == 1 for item in padding_enable):
                changes.append(
                    NormalizationChange(
                        kind="explicit_zero_padding",
                        path=f"{path}.padding_reg_value",
                        before=None,
                        after=0,
                    )
                )
                stream["padding_reg_value"] = 0
        if mode == "write":
            for field_name in READ_ONLY_STREAM_FIELDS:
                if field_name in stream:
                    before = stream.pop(field_name)
                    changes.append(
                        NormalizationChange(
                            kind="remove_write_read_only_field",
                            path=f"{path}.{field_name}",
                            before=before,
                            after="<absent>",
                        )
                    )
        modes = stream.get("mem_idx_mode")
        if isinstance(modes, list):
            for index, item in enumerate(modes):
                if type(item) is int and item == 0:
                    changes.append(
                        NormalizationChange(
                            kind="typed_null_index_mode",
                            path=f"{path}.mem_idx_mode[{index}]",
                            before=0,
                            after=None,
                        )
                    )
                    modes[index] = None
    return normalized, changes


def classify_normalization(changes: Sequence[NormalizationChange]) -> dict[str, Any]:
    kinds = sorted({change.kind for change in changes})
    if not kinds:
        return {
            "legacy_identity": "strict-valid-no-normalization",
            "normalized_identity": "not-created",
            "semantic_blockers": [],
        }
    blockers: list[str] = []
    if "explicit_zero_padding" in kinds:
        blockers.append("operator contract must prove padding byte is exactly zero")
    return {
        "legacy_identity": "legacy-replayable-strict-intentional-reject",
        "normalized_identity": (
            "bit-equivalent-development-candidate-blocked"
            if blockers
            else "bit-equivalent-development-candidate"
        ),
        "semantic_blockers": blockers,
        "normalization_kinds": kinds,
    }


def normalization_adjudication(
    changes: Sequence[NormalizationChange],
    *,
    field_encoding_equivalent: bool,
    padding_contract_validated: bool = False,
) -> dict[str, Any]:
    kinds = {change.kind for change in changes}
    if "explicit_zero_padding" in kinds:
        if padding_contract_validated and kinds == {"explicit_zero_padding"}:
            decision = "approved-explicit-zero-padding-operator-contract"
            reason = (
                "the exact source and normalized identities are bound to a UINT8 "
                "MaxPool contract proving byte zero is the max identity"
            )
        else:
            decision = "blocked-missing-operator-padding-contract"
            reason = "zero is the legacy encoded byte, but the operator contract does not authorize zero padding"
    elif not field_encoding_equivalent:
        decision = "rejected-native-field-encoding-differs"
        reason = "the changed fields do not encode identically in the native encoder"
    elif kinds <= {"remove_write_read_only_field"}:
        decision = "approved-remove-native-ignored-write-fields"
        reason = "WriteStreamEngineConfig.FIELD_MAP does not consume these read-only fields"
    elif kinds <= {"typed_null_index_mode"}:
        decision = "approved-typed-null-native-field-equivalent"
        reason = "the native mem_idx_mode mapper encodes integer 0 and typed null identically"
    else:
        decision = "blocked-mixed-or-unknown-normalization"
        reason = "the normalization set needs a dedicated operator-level decision"
    return {
        "legacy_source_identity": "intentional-reject",
        "normalization_decision": decision,
        "reason": reason,
        "source_rewrite_authorized": False,
        "activation_gate": "R3 full evidence closure and explicit source/generator remediation",
    }


def run_native_encoder_isolated(
    *,
    ndp_sim_root: Path,
    config_path: Path,
    python_executable: Path,
    seed: int,
    heuristic_iterations: int = 10_000,
    heuristic_restarts: int = 10,
    mapping_mode: str = "heuristic",
    mapping_cache_policy: str = "empty",
    timeout_seconds: int = 180,
) -> NativeEncoderRun:
    """Run a disposable copy so native mapping_cache cannot touch ndp-sim."""

    ndp_sim_root = ndp_sim_root.resolve()
    config_path = config_path.resolve()
    python_executable = python_executable.resolve()
    with tempfile.TemporaryDirectory(prefix="operator-config-native-") as temp_text:
        temp = Path(temp_text)
        tool_root = temp / "tool"
        shutil.copytree(
            ndp_sim_root / "bitstream",
            tool_root / "bitstream",
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                "mapping_cache",
                "placement_failed.png",
            ),
        )
        source_mapping_cache = ndp_sim_root / "bitstream" / "config" / "mapping_cache"
        mapping_cache_source_sha256: str | None = None
        if mapping_cache_policy == "copy-frozen":
            cache_files = sorted(source_mapping_cache.glob("*.json"))
            if cache_files:
                mapping_cache_source_sha256 = _tree_identity(cache_files, source_mapping_cache)
                copied_cache = tool_root / "bitstream" / "config" / "mapping_cache"
                copied_cache.mkdir(parents=True, exist_ok=True)
                for cache_file in cache_files:
                    shutil.copy2(cache_file, copied_cache / cache_file.name)
        elif mapping_cache_policy != "empty":
            raise ValueError(f"unsupported mapping_cache_policy: {mapping_cache_policy}")
        output = temp / "output"
        output.mkdir()
        if mapping_mode == "heuristic":
            command = [
                str(python_executable),
                "-m",
                "bitstream.main",
                "-c",
                str(config_path),
                "-o",
                str(output),
                "--seed",
                str(seed),
                "--heuristic-iterations",
                str(heuristic_iterations),
                "--heuristic-restarts",
                str(heuristic_restarts),
                "-q",
            ]
            display_command = [
                "<python>",
                "-m",
                "bitstream.main",
                "-c",
                "<config>",
                "-o",
                "<temp-output>",
                "--seed",
                str(seed),
                "--heuristic-iterations",
                str(heuristic_iterations),
                "--heuristic-restarts",
                str(heuristic_restarts),
                "-q",
            ]
        elif mapping_mode == "direct-differential":
            script = (
                "import sys; from pathlib import Path; "
                "from bitstream.parse import load_config,init_modules,build_entries,write_bitstream,dump_modules_detailed,dump_mapping_review; "
                "cfg=load_config(sys.argv[1]); out=Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True); "
                "mods=init_modules(cfg,use_direct_mapping=True,use_heuristic_search=False,output_dir=str(out)); "
                "dump_mapping_review(str(out/'mapping_review.json')); "
                "dump_modules_detailed(mods,output_file=str(out/'detailed_dump.txt')); "
                "entries=build_entries(mods,output_dir=str(out)); "
                "write_bitstream(entries,config_mask=[int(x) for x in cfg['CONFIG']],output_file=str(out/'parsed_bitstream.txt'),binary_output_file=str(out/'modules_dump.bin'))"
            )
            command = [str(python_executable), "-c", script, str(config_path), str(output)]
            display_command = [
                "<python>",
                "-c",
                "<native direct-mapping differential wrapper>",
                "<config>",
                "<temp-output>",
            ]
        else:
            raise ValueError(f"unsupported mapping_mode: {mapping_mode}")
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
        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        artifact_hashes: dict[str, str] = {}
        artifact_sizes: dict[str, int] = {}
        if completed.returncode == 0:
            missing = [name for name in CORE_NATIVE_ARTIFACTS if not (output / name).is_file()]
            if missing:
                raise RuntimeError(f"native encoder omitted required artifacts: {missing}")
            for name in CORE_NATIVE_ARTIFACTS:
                artifact = output / name
                artifact_hashes[name] = sha256_file(artifact)
                artifact_sizes[name] = artifact.stat().st_size
        detailed = output / "detailed_dump.txt"
        zero_penalty = (
            mapping_mode == "heuristic"
            and completed.returncode == 0
            and "Mapping successful with zero violations" in stdout
            and "Accepting mapping with penalty" not in stdout
        )
        return NativeEncoderRun(
            returncode=completed.returncode,
            mapping_mode=mapping_mode,
            mapping_cache_policy=mapping_cache_policy,
            mapping_cache_source_sha256=mapping_cache_source_sha256,
            loaded_cached_mapping="Loaded cached mapping" in stdout,
            zero_penalty_mapping=zero_penalty,
            command=display_command,
            stdout_sha256=sha256_bytes(completed.stdout),
            stderr_sha256=sha256_bytes(completed.stderr),
            stdout_tail=stdout.splitlines()[-20:],
            stderr_tail=stderr.splitlines()[-20:],
            artifact_sha256=artifact_hashes,
            artifact_size=artifact_sizes,
            detailed_dump_sha256=sha256_file(detailed) if detailed.is_file() else None,
        )


def compare_native_runs(
    original: NativeEncoderRun,
    normalized: NativeEncoderRun,
) -> dict[str, Any]:
    artifact_equal = {
        name: (
            name in original.artifact_sha256
            and name in normalized.artifact_sha256
            and original.artifact_sha256[name] == normalized.artifact_sha256[name]
        )
        for name in CORE_NATIVE_ARTIFACTS
    }
    return {
        "both_succeeded": original.returncode == 0 and normalized.returncode == 0,
        "both_zero_penalty": original.zero_penalty_mapping and normalized.zero_penalty_mapping,
        "artifact_equal": artifact_equal,
        "all_core_artifacts_equal": (
            original.returncode == 0
            and normalized.returncode == 0
            and all(artifact_equal.values())
        ),
        "detailed_dump_equal": original.detailed_dump_sha256 == normalized.detailed_dump_sha256,
    }


def run_native_changed_field_probe(
    *,
    ndp_sim_root: Path,
    original_path: Path,
    normalized_path: Path,
    changes: Sequence[NormalizationChange],
    python_executable: Path,
    timeout_seconds: int = 60,
) -> NativeFieldProbe:
    """Execute ndp-sim's real stream FIELD_MAP encoders for every changed field."""

    ndp_sim_root = ndp_sim_root.resolve()
    original_path = original_path.resolve()
    normalized_path = normalized_path.resolve()
    python_executable = python_executable.resolve()
    with tempfile.TemporaryDirectory(prefix="operator-config-field-probe-") as temp_text:
        temp = Path(temp_text)
        tool_root = temp / "tool"
        shutil.copytree(
            ndp_sim_root / "bitstream",
            tool_root / "bitstream",
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                "mapping_cache",
                "placement_failed.png",
            ),
        )
        changes_path = temp / "changes.json"
        proof_path = temp / "proof.json"
        changes_path.write_text(
            json.dumps([asdict(change) for change in changes], ensure_ascii=False),
            encoding="utf-8",
        )
        script = r'''
import json
import sys
from pathlib import Path
from bitstream.config.stream import ReadStreamEngineConfig, WriteStreamEngineConfig

original = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
normalized = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
changes = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
entries = []
for change in changes:
    parts = change["path"].removeprefix("$.stream_engine.").split(".")
    stream_name = parts[0]
    field_name = parts[1].split("[")[0]
    original_stream = original["stream_engine"][stream_name]
    normalized_stream = normalized["stream_engine"][stream_name]
    module_class = (
        WriteStreamEngineConfig
        if original_stream.get("mode") == "write"
        else ReadStreamEngineConfig
    )
    field_entry = next(
        (entry for entry in module_class.FIELD_MAP if entry[0] == field_name),
        None,
    )
    if field_entry is None:
        entries.append({
            "path": change["path"],
            "native_module": module_class.__name__,
            "native_status": "ignored-not-in-field-map",
            "original_encoded": None,
            "normalized_encoded": None,
            "equal": True,
        })
        continue
    _, width, *rest = field_entry
    mapper = rest[0] if rest else None
    module = module_class(stream_name)
    original_value = original_stream.get(field_name, 0)
    normalized_value = normalized_stream.get(field_name, 0)
    original_encoded = module._encode_field(original_value, mapper, width)
    normalized_encoded = module._encode_field(normalized_value, mapper, width)
    entries.append({
        "path": change["path"],
        "native_module": module_class.__name__,
        "native_status": "encoded-by-field-map",
        "original_encoded": original_encoded,
        "normalized_encoded": normalized_encoded,
        "equal": original_encoded == normalized_encoded,
    })
proof = {
    "schema": "operator-config-native-field-probe-v1",
    "scope": "changed fields only; this is not a full mapping or bitstream proof",
    "entries": entries,
    "all_equivalent": all(item["equal"] for item in entries),
}
Path(sys.argv[4]).write_text(
    json.dumps(proof, sort_keys=True, separators=(",", ":")),
    encoding="utf-8",
)
'''
        command = [
            str(python_executable),
            "-c",
            script,
            str(original_path),
            str(normalized_path),
            str(changes_path),
            str(proof_path),
        ]
        environment = dict(os.environ)
        environment["PYTHONIOENCODING"] = "utf-8"
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
        proof = (
            json.loads(proof_path.read_text(encoding="utf-8"))
            if completed.returncode == 0 and proof_path.is_file()
            else None
        )
        stderr = completed.stderr.decode("utf-8", errors="replace")
        return NativeFieldProbe(
            returncode=completed.returncode,
            command=[
                "<python>",
                "-c",
                "<native FIELD_MAP/_encode_field differential probe>",
                "<original-config>",
                "<normalized-config>",
                "<changes>",
                "<proof-output>",
            ],
            stdout_sha256=sha256_bytes(completed.stdout),
            stderr_sha256=sha256_bytes(completed.stderr),
            stderr_tail=stderr.splitlines()[-20:],
            proof_sha256=sha256_file(proof_path) if proof_path.is_file() else None,
            proof=proof,
        )
def adjudicate_config(
    *,
    source_path: Path,
    ndp_sim_root: Path,
    python_executable: Path,
    seed: int,
    heuristic_iterations: int = 10_000,
    heuristic_restarts: int = 10,
) -> dict[str, Any]:
    original = json.loads(source_path.read_text(encoding="utf-8"))
    original_report = OperatorConfigValidator().validate(original, source=str(source_path))
    normalized, changes = normalize_known_legacy_expressions(original)
    normalized_report = OperatorConfigValidator().validate(
        normalized,
        source=f"{source_path}#normalized-in-memory",
    )
    if original_report.valid:
        raise RuntimeError(f"{source_path.name} is already strict-valid; refusing unnecessary normalization")
    if not changes:
        raise RuntimeError(f"{source_path.name} has no recognized normalization")
    if not normalized_report.valid:
        first = normalized_report.to_dict()["first_error"]
        raise RuntimeError(f"{source_path.name} remains invalid after normalization: {first}")

    with tempfile.TemporaryDirectory(prefix="operator-config-normalized-") as temp_text:
        normalized_path = Path(temp_text) / source_path.name
        normalized_path.write_text(
            json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        original_native = run_native_encoder_isolated(
            ndp_sim_root=ndp_sim_root,
            config_path=source_path,
            python_executable=python_executable,
            seed=seed,
            heuristic_iterations=heuristic_iterations,
            heuristic_restarts=heuristic_restarts,
        )
        normalized_native = run_native_encoder_isolated(
            ndp_sim_root=ndp_sim_root,
            config_path=normalized_path,
            python_executable=python_executable,
            seed=seed,
            heuristic_iterations=heuristic_iterations,
            heuristic_restarts=heuristic_restarts,
        )
        field_probe = run_native_changed_field_probe(
            ndp_sim_root=ndp_sim_root,
            original_path=source_path,
            normalized_path=normalized_path,
            changes=changes,
            python_executable=python_executable,
        )
    heuristic_comparison = compare_native_runs(original_native, normalized_native)
    cached_original: NativeEncoderRun | None = None
    cached_normalized: NativeEncoderRun | None = None
    cached_comparison: dict[str, Any] | None = None
    if not heuristic_comparison["all_core_artifacts_equal"]:
        with tempfile.TemporaryDirectory(prefix="operator-config-normalized-cached-") as cached_temp:
            cached_normalized_path = Path(cached_temp) / source_path.name
            cached_normalized_path.write_text(
                json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            cached_original = run_native_encoder_isolated(
                ndp_sim_root=ndp_sim_root,
                config_path=source_path,
                python_executable=python_executable,
                seed=seed,
                heuristic_iterations=heuristic_iterations,
                heuristic_restarts=heuristic_restarts,
                mapping_cache_policy="copy-frozen",
            )
            cached_normalized = run_native_encoder_isolated(
                ndp_sim_root=ndp_sim_root,
                config_path=cached_normalized_path,
                python_executable=python_executable,
                seed=seed,
                heuristic_iterations=heuristic_iterations,
                heuristic_restarts=heuristic_restarts,
                mapping_cache_policy="copy-frozen",
            )
        cached_comparison = compare_native_runs(cached_original, cached_normalized)

    direct_original: NativeEncoderRun | None = None
    direct_normalized: NativeEncoderRun | None = None
    direct_comparison: dict[str, Any] | None = None
    if not heuristic_comparison["all_core_artifacts_equal"] and not bool(
        cached_comparison and cached_comparison["all_core_artifacts_equal"]
    ):
        with tempfile.TemporaryDirectory(prefix="operator-config-normalized-direct-") as direct_temp:
            direct_normalized_path = Path(direct_temp) / source_path.name
            direct_normalized_path.write_text(
                json.dumps(normalized, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            direct_original = run_native_encoder_isolated(
                ndp_sim_root=ndp_sim_root,
                config_path=source_path,
                python_executable=python_executable,
                seed=seed,
                mapping_mode="direct-differential",
            )
            direct_normalized = run_native_encoder_isolated(
                ndp_sim_root=ndp_sim_root,
                config_path=direct_normalized_path,
                python_executable=python_executable,
                seed=seed,
                mapping_mode="direct-differential",
            )
        direct_comparison = compare_native_runs(direct_original, direct_normalized)

    bit_equivalence_proved = (
        heuristic_comparison["all_core_artifacts_equal"]
        or bool(cached_comparison and cached_comparison["all_core_artifacts_equal"])
        or bool(direct_comparison and direct_comparison["all_core_artifacts_equal"])
    )
    zero_penalty_pair = heuristic_comparison["both_zero_penalty"] or bool(
        cached_comparison and cached_comparison["both_zero_penalty"]
    )
    classification = classify_normalization(changes)
    field_encoding_equivalent = bool(
        field_probe.returncode == 0
        and field_probe.proof
        and field_probe.proof.get("all_equivalent")
    )
    any_native_pair_succeeded = any(
        comparison and comparison["both_succeeded"]
        for comparison in (heuristic_comparison, cached_comparison, direct_comparison)
    )
    if not bit_equivalence_proved and field_encoding_equivalent and not any_native_pair_succeeded:
        classification = {
            **classification,
            "normalized_identity": "native-field-equivalent-mapping-blocked",
            "semantic_blockers": [
                *classification.get("semantic_blockers", []),
                "full bitstream equivalence unresolved because native mapping failed for both forms",
            ],
        }
    elif not bit_equivalence_proved:
        classification = {
            **classification,
            "normalized_identity": "not-bit-equivalent-rejected",
            "semantic_blockers": [
                *classification.get("semantic_blockers", []),
                "native mapping or bitstream differs after normalization",
            ],
        }
    elif not zero_penalty_pair:
        classification = {
            **classification,
            "normalized_identity": "bit-equivalent-development-candidate-mapping-blocked",
            "semantic_blockers": [
                *classification.get("semantic_blockers", []),
                "native mapper did not prove zero penalty for both runs",
            ],
        }
    adjudication = normalization_adjudication(
        changes,
        field_encoding_equivalent=field_encoding_equivalent,
    )
    return {
        "source": source_path.as_posix(),
        "source_sha256": sha256_file(source_path),
        "original_first_error": original_report.to_dict()["first_error"],
        "changes": [asdict(change) for change in changes],
        "classification": classification,
        "adjudication": adjudication,
        "normalized_strict_valid": normalized_report.valid,
        "normalized_sha256": sha256_bytes(
            (json.dumps(normalized, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        ),
        "native": {
            "seed": seed,
            "heuristic_iterations": heuristic_iterations,
            "heuristic_restarts": heuristic_restarts,
            "original": asdict(original_native),
            "normalized": asdict(normalized_native),
            "comparison": heuristic_comparison,
            "changed_field_probe": asdict(field_probe),
            "field_encoding_equivalent": field_encoding_equivalent,
            "frozen_cache_fallback": (
                {
                    "purpose": (
                        "diagnostic replay with a hashed copy of the pre-existing local cache; "
                        "source ndp-sim remains read-only"
                    ),
                    "original": asdict(cached_original),
                    "normalized": asdict(cached_normalized),
                    "comparison": cached_comparison,
                }
                if cached_original is not None and cached_normalized is not None
                else None
            ),
            "direct_fallback": (
                {
                    "purpose": "bit-equivalence only; direct mapping does not prove placement quality",
                    "original": asdict(direct_original),
                    "normalized": asdict(direct_normalized),
                    "comparison": direct_comparison,
                }
                if direct_original is not None and direct_normalized is not None
                else None
            ),
            "bit_equivalence_proved": bit_equivalence_proved,
            "zero_penalty_pair": zero_penalty_pair,
        },
    }


def build_p0_baseline(
    *,
    project_root: Path,
    ndp_sim_root: Path,
    config_paths: Sequence[Path],
    shadow_report: Path,
    component_paths: Sequence[Path],
) -> dict[str, Any]:
    ndp_commit = _read_git_head(ndp_sim_root / ".git")
    source_hashes = {
        path.relative_to(project_root).as_posix(): sha256_file(path)
        for path in sorted(config_paths, key=lambda item: str(item).lower())
    }
    component_hashes = {
        path.relative_to(project_root).as_posix(): sha256_file(path)
        for path in component_paths
    }
    bitstream_sources = sorted((ndp_sim_root / "bitstream").rglob("*.py"))
    mapping_cache_files = sorted(
        (ndp_sim_root / "bitstream" / "config" / "mapping_cache").glob("*.json")
    )
    return {
        "schema": "operator-config-p0-baseline-v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "P0 identity freeze before legacy normalization adjudication",
        "target_profile": asdict(TargetProfile()),
        "ndp_sim": {
            "commit": ndp_commit,
            "bitstream_python_tree_sha256": _tree_identity(bitstream_sources, ndp_sim_root),
            "bitstream_python_files": len(bitstream_sources),
            "local_mapping_cache": {
                "portable": False,
                "files": len(mapping_cache_files),
                "tree_sha256": (
                    _tree_identity(
                        mapping_cache_files,
                        ndp_sim_root / "bitstream" / "config" / "mapping_cache",
                    )
                    if mapping_cache_files
                    else None
                ),
            },
            "known_local_noncode_changes": [
                ".gitignore",
                "README_SERVER_PACKAGE_LOCAL.md",
                "jsons/node0004_accumulate_wave0.json",
                "jsons/node0004_accumulate_wave0_nopp_r1.json",
            ],
        },
        "active_configs": {
            "count": len(source_hashes),
            "sha256": source_hashes,
            "set_sha256": sha256_bytes(
                json.dumps(source_hashes, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ),
        },
        "validator_components": component_hashes,
        "shadow_report": {
            "path": shadow_report.relative_to(project_root).as_posix(),
            "sha256": sha256_file(shadow_report),
        },
    }


def _read_git_head(git_dir: Path) -> str:
    head = (git_dir / "HEAD").read_text(encoding="ascii").strip()
    if not head.startswith("ref: "):
        return head
    reference = head[5:]
    loose = git_dir / Path(*reference.split("/"))
    if loose.is_file():
        return loose.read_text(encoding="ascii").strip()
    packed = git_dir / "packed-refs"
    if packed.is_file():
        suffix = f" {reference}"
        for line in packed.read_text(encoding="ascii").splitlines():
            if line.endswith(suffix):
                return line.split(" ", 1)[0]
    raise RuntimeError(f"cannot resolve git HEAD {reference} in {git_dir}")


def _tree_identity(paths: Sequence[Path], root: Path) -> str:
    entries = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in paths
    }
    return sha256_bytes(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
