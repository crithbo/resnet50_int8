from __future__ import annotations

import hashlib
import json
import math
import re
import struct
from dataclasses import asdict, dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .operator_config_validator import ConfigState, OperatorConfigValidator, ValidationIssue


ACTIVE_ENCODER_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"


@dataclass(frozen=True)
class EncodedField:
    path: str
    start: int
    end: int
    bits: str


@dataclass(frozen=True)
class EncodedModule:
    section: str
    slot: int
    logical_node: str | None
    resource: str
    bits: str
    fields: tuple[EncodedField, ...]


@dataclass(frozen=True)
class BitRange:
    path: str
    section: str
    slot: int
    chunk: int
    start: int
    end: int


@dataclass
class ArtifactValidationReport:
    source: str
    artifact_dir: str
    valid: bool
    issues: list[ValidationIssue]
    facts: dict[str, Any]
    next_state: ConfigState

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "operator-config-artifact-validation-report-v1",
            "source": self.source,
            "artifact_dir": self.artifact_dir,
            "valid": self.valid,
            "first_error": asdict(self.issues[0]) if self.issues else None,
            "issues": [asdict(issue) for issue in self.issues],
            "facts": self.facts,
            "next_config_state": dict(self.next_state.fingerprints),
        }


SECTION_LAYOUT = (
    ("iga_lc", 0, 1, 20),
    ("iga_row_lc", 0, 1, 5),
    ("iga_col_lc", 0, 1, 5),
    ("iga_pe", 0, 2, 10),
    ("se_rd_mse", 1, 10, 4),
    ("se_wr_mse", 1, 8, 1),
    ("se_nse", 1, 1, 2),
    ("buffer_manager_cluster", 1, 1, 6),
    ("special_array", 2, 1, 1),
    ("ga_inport_group", 3, 1, 3),
    ("ga_outport_group", 3, 1, 1),
    ("ga_pe", 3, 4, 16),
)


class OperatorConfigArtifactValidator:
    """Independent JSON/mapping-to-bit mirror for native ndp-sim artifacts.

    This module intentionally does not import ndp-sim.  It checks the native
    output as data, so a native encoder implementation mistake cannot make the
    checker agree merely because both paths call the same encoder class.
    """

    def __init__(self, *, expected_encoder_commit: str = ACTIVE_ENCODER_COMMIT) -> None:
        self.expected_encoder_commit = expected_encoder_commit
        self._issues: list[ValidationIssue] = []
        self._facts: dict[str, Any] = {}

    def validate(
        self,
        config: Mapping[str, Any],
        artifact_dir: Path,
        *,
        mapping_evidence: Mapping[str, Any] | None,
        source: str = "<memory>",
        previous_state: ConfigState | None = None,
    ) -> ArtifactValidationReport:
        self._issues = []
        self._facts = {}
        artifact_dir = artifact_dir.resolve()

        strict = OperatorConfigValidator().validate(
            config,
            source=source,
            previous_state=previous_state,
        )
        self._facts["json_validation"] = {
            "valid": strict.valid,
            "issue_count": len(strict.issues),
        }
        if not strict.valid:
            first = strict.issues[0]
            self._error(
                "ARTIFACT.INPUT_CONFIG_INVALID",
                first.path,
                f"strict JSON validation failed first with {first.code}: {first.message}",
            )

        mapping_path = artifact_dir / "mapping_review.json"
        mapping_review = self._load_json(mapping_path, "ARTIFACT.MAPPING_PARSE")
        mapping: dict[str, str] = {}
        if isinstance(mapping_review, Mapping):
            mapping = self._validate_mapping_review(config, mapping_review)
        self._validate_mapping_evidence(mapping_path, mapping_evidence, config)

        modules: dict[str, list[EncodedModule]] = {}
        if strict.valid and mapping:
            modules = self._build_modules(config, mapping)
            expected = self._build_artifacts(str(config.get("CONFIG", "")), modules)
            self._facts["mirror"] = {
                "unpadded_bits": len(expected["binary"]),
                "binary_64_lines": len(expected["binary64_lines"]),
                "binary_128_lines": len(expected["binary128_lines"]),
                "bit_range_count": len(expected["ranges"]),
                "bit_ranges": [asdict(item) for item in expected["ranges"]],
            }
            self._compare_parsed(artifact_dir / "parsed_bitstream.txt", expected["parsed_lines"])
            self._compare_binary(
                artifact_dir / "modules_dump_64b.bin",
                expected["binary64_lines"],
                width=64,
                ranges=expected["ranges"],
            )
            self._compare_binary(
                artifact_dir / "modules_dump_128b.bin",
                expected["binary128_lines"],
                width=128,
                ranges=(),
                reordered=True,
            )

        self._facts["issue_count"] = len(self._issues)
        return ArtifactValidationReport(
            source=source,
            artifact_dir=str(artifact_dir),
            valid=not self._issues,
            issues=list(self._issues),
            facts=dict(self._facts),
            next_state=strict.next_state,
        )

    def _error(self, code: str, path: str, message: str) -> None:
        self._issues.append(ValidationIssue(code, path, message))

    def _load_json(self, path: Path, code: str) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            self._error(code, str(path), str(error))
            return None

    def _validate_mapping_evidence(
        self,
        mapping_path: Path,
        evidence: Mapping[str, Any] | None,
        config: Mapping[str, Any],
    ) -> None:
        path = "$.mapping_evidence"
        if not isinstance(evidence, Mapping):
            self._error("MAPPING.EVIDENCE_MISSING", path, "explicit mapping evidence is required")
            return
        schema = evidence.get("schema")
        if schema not in {
            "operator-config-mapping-evidence-v1",
            "operator-config-mapping-evidence-v2",
        }:
            self._error("MAPPING.EVIDENCE_SCHEMA", f"{path}.schema", "unsupported evidence schema")
        if evidence.get("penalty") != 0:
            self._error("MAPPING.NONZERO_PENALTY", f"{path}.penalty", "placement penalty must be exactly zero")
        if evidence.get("fallback_used") is not False:
            self._error("MAPPING.FALLBACK", f"{path}.fallback_used", "sequential-ID or other fallback is forbidden")
        if evidence.get("mapping_mode") not in {"heuristic", "exhaustive", "frozen-zero-penalty"}:
            self._error("MAPPING.MODE", f"{path}.mapping_mode", "mode must prove a constrained zero-penalty mapping")

        encoder = evidence.get("encoder")
        if not isinstance(encoder, Mapping):
            self._error("MAPPING.ENCODER_IDENTITY", f"{path}.encoder", "encoder identity is required")
        elif encoder.get("commit") != self.expected_encoder_commit:
            self._error(
                "MAPPING.ENCODER_IDENTITY",
                f"{path}.encoder.commit",
                f"expected pinned commit {self.expected_encoder_commit}",
            )

        cache = evidence.get("cache")
        if not isinstance(cache, Mapping):
            self._error("MAPPING.CACHE_IDENTITY", f"{path}.cache", "cache identity is required")
        else:
            loaded = cache.get("loaded")
            policy = cache.get("policy")
            if loaded is False and policy not in {"empty", "same-run-generated-not-loaded"}:
                self._error(
                    "MAPPING.CACHE_POLICY",
                    f"{path}.cache.policy",
                    "an unused cache must be empty or generated-but-not-loaded in this run",
                )
            if loaded is True:
                digest = cache.get("sha256")
                seed = cache.get("seed")
                seed_ok = False
                if isinstance(seed, Mapping):
                    artifact = seed.get("artifact")
                    expected_seed_sha = seed.get("sha256")
                    origin = seed.get("origin")
                    origin_ok = (
                        isinstance(origin, Mapping)
                        and isinstance(origin.get("repository"), str)
                        and bool(origin.get("repository"))
                        and isinstance(origin.get("commit"), str)
                        and re.fullmatch(r"[0-9a-f]{40}", origin["commit"])
                        is not None
                        and isinstance(origin.get("path"), str)
                        and bool(origin.get("path"))
                    )
                    if (
                        isinstance(artifact, str)
                        and artifact.startswith("mapping_cache/")
                        and ".." not in Path(artifact).parts
                        and _is_sha256(expected_seed_sha)
                        and origin_ok
                    ):
                        seed_path = mapping_path.parent / artifact
                        seed_ok = (
                            seed_path.is_file()
                            and _sha256_file(seed_path) == expected_seed_sha
                        )
                frozen_ok = (
                    policy == "frozen"
                    and cache.get("loaded_origin") == "frozen-bundled-seed"
                    and cache.get("initial_file_count") == 1
                    and cache.get("final_file_count") == 1
                    and cache.get("bundled") is True
                    and seed_ok
                )
                same_run_ok = (
                    policy == "same-run-generated-loaded"
                    and cache.get("loaded_origin") == "same-run-generated"
                    and cache.get("initial_file_count") == 0
                    and isinstance(cache.get("final_file_count"), int)
                    and cache.get("final_file_count") > 0
                    and cache.get("bundled") is True
                )
                if not (frozen_ok or same_run_ok) or cache.get("portable") is not True or not _is_sha256(digest):
                    self._error(
                        "MAPPING.CACHE_NONPORTABLE",
                        f"{path}.cache",
                        "loaded cache must be frozen or same-run-generated, portable, bundled, and hash-bound",
                    )
            if loaded not in {True, False}:
                self._error("MAPPING.CACHE_IDENTITY", f"{path}.cache.loaded", "must be a boolean")

        expected_hash = evidence.get("mapping_review_sha256")
        actual_hash = _sha256_file(mapping_path) if mapping_path.is_file() else None
        self._facts["mapping_evidence"] = {
            "mapping_review_sha256": actual_hash,
            "penalty": evidence.get("penalty"),
            "mapping_mode": evidence.get("mapping_mode"),
            "cache": dict(cache) if isinstance(cache, Mapping) else None,
            "encoder": dict(encoder) if isinstance(encoder, Mapping) else None,
        }
        if not _is_sha256(expected_hash) or expected_hash != actual_hash:
            self._error(
                "MAPPING.REVIEW_IDENTITY",
                f"{path}.mapping_review_sha256",
                "evidence does not bind the exact mapping_review.json",
            )
        if schema == "operator-config-mapping-evidence-v2":
            self._validate_portable_evidence_v2(mapping_path.parent, evidence, config)

    def _validate_portable_evidence_v2(
        self,
        artifact_dir: Path,
        evidence: Mapping[str, Any],
        config: Mapping[str, Any],
    ) -> None:
        path = "$.mapping_evidence"
        penalty_source = evidence.get("penalty_source")
        state: Mapping[str, Any] | None = None
        if not isinstance(penalty_source, Mapping):
            self._error(
                "MAPPING.PENALTY_SOURCE",
                f"{path}.penalty_source",
                "v2 evidence must bind native_mapping_state.json",
            )
        else:
            state = self._load_bound_json(
                artifact_dir,
                penalty_source.get("artifact"),
                penalty_source.get("sha256"),
                "MAPPING.PENALTY_SOURCE",
                f"{path}.penalty_source",
            )
            if penalty_source.get("json_path") != "$.last_mapping_cost":
                self._error(
                    "MAPPING.PENALTY_SOURCE",
                    f"{path}.penalty_source.json_path",
                    "must identify $.last_mapping_cost",
                )
            if isinstance(state, Mapping) and state.get("last_mapping_cost") != evidence.get("penalty"):
                self._error(
                    "MAPPING.PENALTY_SOURCE",
                    f"{path}.penalty",
                    "top-level penalty differs from the bound native state",
                )
            if isinstance(state, Mapping) and state.get("fallback_nodes") != []:
                self._error(
                    "MAPPING.FALLBACK",
                    f"{path}.penalty_source",
                    "native state contains unmapped/fallback nodes",
                )

        run = evidence.get("run")
        if not isinstance(run, Mapping):
            self._error("MAPPING.RUN_PROVENANCE", f"{path}.run", "v2 run provenance is required")
        else:
            if run.get("returncode") != 0 or not isinstance(run.get("seed"), int):
                self._error(
                    "MAPPING.RUN_PROVENANCE",
                    f"{path}.run",
                    "returncode=0 and an integer seed are required",
                )
            command = run.get("command")
            if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
                self._error(
                    "MAPPING.RUN_PROVENANCE",
                    f"{path}.run.command",
                    "portable display command must be a non-empty string array",
                )
            for key, default_name in (
                ("stdout", "native_stdout.log"),
                ("stderr", "native_stderr.log"),
            ):
                ref = run.get(key)
                if not isinstance(ref, Mapping):
                    self._error(
                        "MAPPING.RUN_PROVENANCE",
                        f"{path}.run.{key}",
                        "log artifact and SHA-256 are required",
                    )
                    continue
                self._verify_bound_file(
                    artifact_dir,
                    ref.get("artifact", default_name),
                    ref.get("sha256"),
                    "MAPPING.RUN_PROVENANCE",
                    f"{path}.run.{key}",
                )

        encoder = evidence.get("encoder")
        if isinstance(encoder, Mapping):
            manifest = self._load_bound_json(
                artifact_dir,
                encoder.get("source_manifest"),
                encoder.get("source_manifest_sha256"),
                "MAPPING.ENCODER_IDENTITY",
                f"{path}.encoder.source_manifest",
            )
            if (
                not isinstance(manifest, Mapping)
                or not _is_sha256(encoder.get("bitstream_tree_sha256"))
                or manifest.get("tree_sha256") != encoder.get("bitstream_tree_sha256")
            ):
                self._error(
                    "MAPPING.ENCODER_IDENTITY",
                    f"{path}.encoder.bitstream_tree_sha256",
                    "encoder source manifest/tree identity is inconsistent",
                )
            patchset_ref = encoder.get("patchset")
            if patchset_ref is not None:
                if not isinstance(patchset_ref, Mapping):
                    self._error(
                        "MAPPING.PATCHSET_IDENTITY",
                        f"{path}.encoder.patchset",
                        "patchset binding must be an object or null",
                    )
                else:
                    patchset = self._load_bound_json(
                        artifact_dir,
                        patchset_ref.get("manifest"),
                        patchset_ref.get("manifest_sha256"),
                        "MAPPING.PATCHSET_IDENTITY",
                        f"{path}.encoder.patchset.manifest",
                    )
                    if (
                        not isinstance(patchset, Mapping)
                        or patchset.get("base_commit") != self.expected_encoder_commit
                        or patchset.get("patchset_id") != patchset_ref.get("patchset_id")
                        or patchset.get("patchset_sha256")
                        != patchset_ref.get("patchset_sha256")
                        or _patchset_digest(patchset) != patchset.get("patchset_sha256")
                        or not _valid_patchset_policy(patchset)
                    ):
                        self._error(
                            "MAPPING.PATCHSET_IDENTITY",
                            f"{path}.encoder.patchset",
                            "patchset manifest identity, digest, base commit, or fail-closed policy is invalid",
                        )

        source_config = evidence.get("source_config")
        if not isinstance(source_config, Mapping):
            self._error(
                "MAPPING.SOURCE_IDENTITY",
                f"{path}.source_config",
                "v2 evidence must bind the copied strict source JSON",
            )
        else:
            source_path = self._verify_bound_file(
                artifact_dir,
                source_config.get("artifact"),
                source_config.get("sha256"),
                "MAPPING.SOURCE_IDENTITY",
                f"{path}.source_config",
            )
            if source_path is not None:
                try:
                    bound_config = json.loads(source_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError) as error:
                    self._error(
                        "MAPPING.SOURCE_IDENTITY",
                        f"{path}.source_config",
                        f"bound source JSON is unreadable: {error}",
                    )
                else:
                    if bound_config != config:
                        self._error(
                            "MAPPING.SOURCE_IDENTITY",
                            f"{path}.source_config",
                            "validated config differs from the hash-bound source_config artifact",
                        )

        artifacts = evidence.get("artifacts")
        if not isinstance(artifacts, Mapping):
            self._error("MAPPING.ARTIFACT_IDENTITY", f"{path}.artifacts", "artifact hash map is required")
        else:
            for name in (
                "mapping_review.json",
                "parsed_bitstream.txt",
                "modules_dump_64b.bin",
                "modules_dump_128b.bin",
            ):
                self._verify_bound_file(
                    artifact_dir,
                    name,
                    artifacts.get(name),
                    "MAPPING.ARTIFACT_IDENTITY",
                    f"{path}.artifacts.{name}",
                )

        cache = evidence.get("cache")
        if isinstance(cache, Mapping):
            initial_count = cache.get("initial_file_count")
            final_count = cache.get("final_file_count")
            expected_initial = 1 if cache.get("policy") == "frozen" else 0
            if (
                initial_count != expected_initial
                or not isinstance(final_count, int)
                or final_count < 0
            ):
                self._error(
                    "MAPPING.CACHE_IDENTITY",
                    f"{path}.cache",
                    "portable v2 runs must bind the expected initial cache and record final count",
                )
            cache_dir = artifact_dir / "mapping_cache"
            if final_count:
                actual_count = len([item for item in cache_dir.rglob("*") if item.is_file()]) if cache_dir.is_dir() else 0
                actual_tree = _sha256_tree(cache_dir) if cache_dir.is_dir() else None
                if (
                    cache.get("bundled") is not True
                    or actual_count != final_count
                    or actual_tree != cache.get("sha256")
                ):
                    self._error(
                        "MAPPING.CACHE_IDENTITY",
                        f"{path}.cache",
                        "bundled same-run cache count/tree hash does not match evidence",
                    )
            elif cache.get("loaded") is True:
                self._error(
                    "MAPPING.CACHE_IDENTITY",
                    f"{path}.cache",
                    "cache cannot be loaded when the final cache is empty",
                )

    def _load_bound_json(
        self,
        root: Path,
        name: Any,
        digest: Any,
        code: str,
        path: str,
    ) -> Mapping[str, Any] | None:
        bound = self._verify_bound_file(root, name, digest, code, path)
        if bound is None:
            return None
        try:
            value = json.loads(bound.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            self._error(code, path, f"bound JSON is unreadable: {error}")
            return None
        if not isinstance(value, Mapping):
            self._error(code, path, "bound JSON must be an object")
            return None
        return value

    def _verify_bound_file(
        self,
        root: Path,
        name: Any,
        digest: Any,
        code: str,
        path: str,
    ) -> Path | None:
        if not isinstance(name, str) or not name or Path(name).is_absolute() or ".." in Path(name).parts:
            self._error(code, path, "artifact path must be a safe relative path")
            return None
        bound = root / name
        if not bound.is_file() or not _is_sha256(digest) or _sha256_file(bound) != digest:
            self._error(code, path, "artifact is missing or its SHA-256 differs")
            return None
        return bound

    def _validate_mapping_review(
        self, config: Mapping[str, Any], review: Mapping[str, Any]
    ) -> dict[str, str]:
        allowed = {"summary", "node_to_resource", "connection_mapping"}
        for key in sorted(set(review) - allowed):
            self._error("MAPPING.UNKNOWN_FIELD", f"$.mapping_review.{key}", "unknown mapping review field")
        rows = review.get("node_to_resource")
        connections = review.get("connection_mapping")
        summary = review.get("summary")
        if not isinstance(rows, list) or not isinstance(connections, list) or not isinstance(summary, Mapping):
            self._error("MAPPING.SCHEMA", "$.mapping_review", "summary and both row arrays are required")
            return {}

        mapping: dict[str, str] = {}
        resource_owner: dict[str, str] = {}
        for index, row in enumerate(rows):
            path = f"$.mapping_review.node_to_resource[{index}]"
            if not isinstance(row, Mapping) or set(row) != {"node", "resource"}:
                self._error("MAPPING.SCHEMA", path, "row must contain exactly node and resource")
                continue
            node, resource = row.get("node"), row.get("resource")
            if not isinstance(node, str) or not isinstance(resource, str):
                self._error("MAPPING.SCHEMA", path, "node and resource must be strings")
                continue
            if node in mapping:
                self._error("MAPPING.DUPLICATE_NODE", path, f"node {node} appears more than once")
            mapping[node] = resource
            if resource != "GENERIC" and resource in resource_owner:
                self._error(
                    "MAPPING.DUPLICATE_RESOURCE",
                    path,
                    f"resource {resource} is shared with {resource_owner[resource]}",
                )
            resource_owner[resource] = node

        expected_nodes = self._expected_nodes(config)
        for node, pattern in expected_nodes.items():
            resource = mapping.get(node)
            if resource is None:
                self._error("MAPPING.UNMAPPED_NODE", f"$.mapping.{node}", "active logical node is not mapped")
            elif re.fullmatch(pattern, resource) is None:
                self._error(
                    "MAPPING.RESOURCE_TYPE",
                    f"$.mapping.{node}",
                    f"resource {resource!r} does not match {pattern}",
                )
        for node in sorted(set(mapping) - set(expected_nodes)):
            self._error(
                "MAPPING.UNEXPECTED_NODE",
                f"$.mapping.{node}",
                "mapping contains a node that is not active in the strict source JSON",
            )

        expected_connections = self._expected_connections(config)
        actual_pairs: list[tuple[str, str]] = []
        for index, row in enumerate(connections):
            path = f"$.mapping_review.connection_mapping[{index}]"
            required = {"src_node", "src_resource", "dst_node", "dst_resource"}
            if not isinstance(row, Mapping) or set(row) != required:
                self._error("MAPPING.SCHEMA", path, "connection row has the wrong fields")
                continue
            src, dst = row.get("src_node"), row.get("dst_node")
            if not isinstance(src, str) or not isinstance(dst, str):
                self._error("MAPPING.SCHEMA", path, "connection node names must be strings")
                continue
            actual_pairs.append((src, dst))
            if row.get("src_resource") != mapping.get(src) or row.get("dst_resource") != mapping.get(dst):
                self._error("MAPPING.CONNECTION_RESOURCE", path, "connection resource does not match node mapping")
            _, reachable = self._connection_value(src, dst, mapping)
            if not reachable:
                self._error("MAPPING.RTL_UNREACHABLE", path, f"{src} -> {dst} has no legal RTL selector")

        if sorted(actual_pairs) != sorted(expected_connections):
            missing = [pair for pair in expected_connections if pair not in actual_pairs]
            extra = [pair for pair in actual_pairs if pair not in expected_connections]
            self._error(
                "MAPPING.CONNECTION_SET",
                "$.mapping_review.connection_mapping",
                f"connection multiset differs; missing={missing[:3]}, extra={extra[:3]}",
            )
        if summary.get("mapped_nodes") != len(rows) or summary.get("connections") != len(connections):
            self._error("MAPPING.SUMMARY", "$.mapping_review.summary", "summary counts do not match row arrays")
        graph_node_count = sum(not re.fullmatch(r"GROUP\d+", node) for node in expected_nodes)
        if summary.get("total_nodes") != graph_node_count:
            self._error(
                "MAPPING.SUMMARY",
                "$.mapping_review.summary.total_nodes",
                f"expected {graph_node_count} active graph nodes",
            )
        self._facts["mapping"] = {
            "mapped_nodes": len(mapping),
            "connections": len(connections),
            "rtl_reachable_connections": sum(
                self._connection_value(src, dst, mapping)[1] for src, dst in actual_pairs
            ),
        }
        return mapping

    def _expected_nodes(self, config: Mapping[str, Any]) -> dict[str, str]:
        result: dict[str, str] = {}
        for key, item in sorted(_mapping(config.get("dram_loop_configs")).items()):
            if isinstance(item, Mapping) and "stride" in item and (
                item.get("stride", 0) != 0 or item.get("src_id") is not None
            ):
                result[f"DRAM_LC.{key}"] = r"LC(?:[0-9]|1[0-9])"
        for key, item in _mapping(config.get("buffer_loop_configs")).items():
            if isinstance(item, Mapping) and ("ROW_LC" in item or "COL_LC" in item):
                result[key] = r"GROUP[0-4]"
                result[f"{key}.ROW_LC"] = r"ROW_LC[0-4]"
                result[f"{key}.COL_LC"] = r"COL_LC[0-4]"
        for key, item in sorted(_mapping(config.get("lc_pe_configs")).items()):
            if isinstance(item, Mapping) and item and ("alu_opcode" in item or "inport" in item):
                result[f"LC_PE.{key}"] = r"PE(?:[0-9])"
        for key, item in sorted(_mapping(config.get("stream_engine")).items()):
            if key == "n2n" or not isinstance(item, Mapping):
                continue
            result[f"STREAM.{key}"] = r"WRITE_STREAM0" if item.get("mode") == "write" else r"READ_STREAM[0-3]"
        ga = _mapping(config.get("general_array"))
        for key, item in _mapping(ga.get("PE_array")).items():
            if isinstance(item, Mapping) and item and ("alu_opcode" in item or "inport0" in item):
                result[f"GA_PE.{key}"] = r"GENERIC"
        return result

    def _expected_connections(self, config: Mapping[str, Any]) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []

        def add(src: Any, dst: str) -> None:
            pair = (src, dst)
            if (
                isinstance(src, str)
                and src.lower() != "buffer"
                and pair not in result
            ):
                result.append(pair)

        for key, item in sorted(_mapping(config.get("dram_loop_configs")).items()):
            if isinstance(item, Mapping) and "stride" in item and (
                item.get("stride", 0) != 0 or item.get("src_id") is not None
            ):
                add(item.get("src_id"), f"DRAM_LC.{key}")
        for key, item in _mapping(config.get("buffer_loop_configs")).items():
            if not isinstance(item, Mapping):
                continue
            row = _mapping(item.get("ROW_LC"))
            col = _mapping(item.get("COL_LC"))
            add(row.get("src_id"), f"{key}.ROW_LC")
            add(col.get("src_id"), f"{key}.COL_LC")
        for key, item in sorted(_mapping(config.get("lc_pe_configs")).items()):
            if not isinstance(item, Mapping):
                continue
            for index in range(3):
                add(_mapping(item.get(f"inport{index}")).get("src_id"), f"LC_PE.{key}")
        for key, item in sorted(_mapping(config.get("stream_engine")).items()):
            if key == "n2n" or not isinstance(item, Mapping):
                continue
            for src in item.get("idx", []):
                add(src, f"STREAM.{key}")
        ga = _mapping(config.get("general_array"))
        for key, item in _mapping(ga.get("PE_array")).items():
            if not isinstance(item, Mapping):
                continue
            for index in range(3):
                add(_mapping(item.get(f"inport{index}")).get("src_id"), f"GA_PE.{key}")
        return result

    def _build_modules(
        self, config: Mapping[str, Any], mapping: Mapping[str, str]
    ) -> dict[str, list[EncodedModule]]:
        result = {
            name: [self._empty_module(name, slot) for slot in range(count)]
            for name, _, _, count in SECTION_LAYOUT
        }

        dram_entries = [
            (key, item)
            for key, item in sorted(_mapping(config.get("dram_loop_configs")).items())
            if isinstance(item, Mapping) and "stride" in item
        ][:20]
        for key, item in dram_entries:
            if item.get("stride", 0) == 0 and item.get("src_id") is None:
                continue
            node = f"DRAM_LC.{key}"
            module = self._encode_dram(node, item, mapping)
            self._place(result["iga_lc"], module, mapping.get(node), "LC")

        for key, item in list(_mapping(config.get("buffer_loop_configs")).items())[:5]:
            if not isinstance(item, Mapping) or not ("ROW_LC" in item or "COL_LC" in item):
                continue
            row_node, col_node = f"{key}.ROW_LC", f"{key}.COL_LC"
            self._place(
                result["iga_row_lc"],
                self._encode_row(row_node, _mapping(item.get("ROW_LC")), mapping),
                mapping.get(row_node),
                "ROW_LC",
            )
            self._place(
                result["iga_col_lc"],
                self._encode_col(col_node, _mapping(item.get("COL_LC")), mapping),
                mapping.get(col_node),
                "COL_LC",
            )

        for key, item in list(sorted(_mapping(config.get("lc_pe_configs")).items()))[:10]:
            if not isinstance(item, Mapping) or not item or (
                "alu_opcode" not in item and "inport" not in item
            ):
                continue
            node = f"LC_PE.{key}"
            self._place(
                result["iga_pe"],
                self._encode_lc_pe(node, item, mapping),
                mapping.get(node),
                "PE",
            )

        streams = [
            (key, item)
            for key, item in sorted(_mapping(config.get("stream_engine")).items())
            if key != "n2n" and isinstance(item, Mapping)
        ][:5]
        for key, item in streams:
            node = f"STREAM.{key}"
            section = "se_wr_mse" if item.get("mode", "read") == "write" else "se_rd_mse"
            prefix = "WRITE_STREAM" if section == "se_wr_mse" else "READ_STREAM"
            self._place(
                result[section],
                self._encode_stream(node, item, mapping),
                mapping.get(node),
                prefix,
            )

        n2n = list(_mapping(config.get("n2n")).items())
        for slot in range(2):
            if slot < len(n2n):
                key, item = n2n[slot]
                if isinstance(item, Mapping):
                    result["se_nse"][slot] = self._encode_neighbor(slot, key, item)

        buffers = _mapping(config.get("buffer_config"))
        implicit_defaults: list[int] = []
        for slot in range(6):
            item = buffers.get(f"buffer{slot}")
            if not isinstance(item, Mapping):
                item = {}
                implicit_defaults.append(slot)
            result["buffer_manager_cluster"][slot] = self._encode_buffer(slot, item)
        self._facts["native_implicit_buffer_defaults"] = implicit_defaults

        result["special_array"][0] = self._encode_special(_mapping(config.get("special_array")))
        ga = _mapping(config.get("general_array"))
        ga_in = _mapping(ga.get("inport"))
        for slot in range(3):
            result["ga_inport_group"][slot] = self._encode_ga_inport(slot, _mapping(ga_in.get(f"inport{slot}")))
        result["ga_outport_group"][0] = self._encode_ga_outport(_mapping(ga.get("outport")))
        pe_array = _mapping(ga.get("PE_array"))
        for slot, key in enumerate(f"PE{row}{col}" for row in range(4) for col in range(4)):
            item = pe_array.get(key)
            if isinstance(item, Mapping) and item and ("alu_opcode" in item or "inport0" in item):
                result["ga_pe"][slot] = self._encode_ga_pe(f"GA_PE.{key}", item, mapping, slot)
        return result

    def _empty_module(self, section: str, slot: int) -> EncodedModule:
        return EncodedModule(section, slot, None, f"{section}[{slot}]", "", ())

    def _place(
        self,
        slots: list[EncodedModule],
        module: EncodedModule,
        resource: str | None,
        prefix: str,
    ) -> None:
        if resource is None or not resource.startswith(prefix):
            return
        suffix = resource[len(prefix) :]
        if not suffix.isdigit() or not 0 <= int(suffix) < len(slots):
            self._error("MAPPING.RESOURCE_RANGE", f"$.mapping.{module.logical_node}", f"invalid {resource}")
            return
        slot = int(suffix)
        slots[slot] = EncodedModule(
            module.section,
            slot,
            module.logical_node,
            resource,
            module.bits,
            module.fields,
        )

    def _module(
        self,
        section: str,
        logical_node: str | None,
        resource: str,
        values: Iterable[tuple[str, Any, int]],
        *,
        slot: int = -1,
    ) -> EncodedModule:
        cursor = 0
        bits: list[str] = []
        fields: list[EncodedField] = []
        for path, value, width in values:
            encoded = _encode_value(value, width)
            bits.append(encoded)
            fields.append(EncodedField(path, cursor, cursor + len(encoded), encoded))
            cursor += len(encoded)
        return EncodedModule(section, slot, logical_node, resource, "".join(bits), tuple(fields))

    def _src(self, value: Any, dst: str, mapping: Mapping[str, str]) -> int:
        if value is None:
            return 0
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            encoded, reachable = self._connection_value(value, dst, mapping)
            if not reachable:
                return 0
            return encoded
        return 0

    def _encode_dram(self, node: str, item: Mapping[str, Any], mapping: Mapping[str, str]) -> EncodedModule:
        base = f"$.dram_loop_configs.{node.split('.')[-1]}"
        return self._module("iga_lc", node, mapping.get(node, "UNMAPPED"), (
            (f"{base}.src_id", self._src(item.get("src_id"), node, mapping), 4),
            (f"{base}.outmost_loop", item.get("outmost_loop", 0), 1),
            (f"{base}.start", item.get("start", 0), 17),
            (f"{base}.stride", item.get("stride", 0), 17),
            (f"{base}.end", item.get("end", 0), 17),
            (f"{base}.last_index", item.get("last_index", 0), 4),
        ))

    def _encode_row(self, node: str, item: Mapping[str, Any], mapping: Mapping[str, str]) -> EncodedModule:
        key = node.split(".")[0]
        base = f"$.buffer_loop_configs.{key}.ROW_LC"
        return self._module("iga_row_lc", node, mapping.get(node, "UNMAPPED"), (
            (f"{base}.src_id", self._src(item.get("src_id"), node, mapping), 4),
            (f"{base}.start", item.get("start", 0), 3),
            (f"{base}.stride", item.get("stride", 0), 3),
            (f"{base}.end", item.get("end", 0), 3),
            (f"{base}.last_index", item.get("last_index", 0), 4),
        ))

    def _encode_col(self, node: str, item: Mapping[str, Any], mapping: Mapping[str, str]) -> EncodedModule:
        key = node.split(".")[0]
        base = f"$.buffer_loop_configs.{key}.COL_LC"
        return self._module("iga_col_lc", node, mapping.get(node, "UNMAPPED"), (
            (f"{base}.src_id", self._src(item.get("src_id"), node, mapping), 4),
            (f"{base}.start", item.get("start", 0), 6),
            (f"{base}.stride", item.get("stride", 0), 6),
            (f"{base}.end", item.get("end", 0), 6),
            (f"{base}.last_index", item.get("last_index", 0), 4),
        ))

    def _encode_lc_pe(self, node: str, item: Mapping[str, Any], mapping: Mapping[str, str]) -> EncodedModule:
        key = node.split(".")[-1]
        base = f"$.lc_pe_configs.{key}"
        opcode = {"add": 0, "mul": 1, "mac": 2}.get(item.get("alu_opcode"), item.get("alu_opcode", 0))
        values: list[tuple[str, Any, int]] = [(f"{base}._padding", 0, 16), (f"{base}.alu_opcode", opcode, 2)]
        for index in (2, 1, 0):
            port = _mapping(item.get(f"inport{index}"))
            values.extend((
                (f"{base}.inport{index}.src_id", self._src(port.get("src_id"), node, mapping), 4),
                (f"{base}.inport{index}.keep_last_index", port.get("keep_last_index", 0), 4),
                (f"{base}.inport{index}.mode", _mode(port.get("mode")), 2),
            ))
        for index in (2, 1, 0):
            port = _mapping(item.get(f"inport{index}"))
            values.append((f"{base}.inport{index}.constant", _constant_bits(port.get("constant", 0)), 16))
        return self._module("iga_pe", node, mapping.get(node, "UNMAPPED"), values)

    def _encode_stream(self, node: str, item: Mapping[str, Any], mapping: Mapping[str, str]) -> EncodedModule:
        key = node.split(".")[-1]
        base = f"$.stream_engine.{key}"
        write = item.get("mode", "read") == "write"
        section = "se_wr_mse" if write else "se_rd_mse"
        idx_size = list(item.get("idx_size", []))
        dim_size = [(idx_size[index] + 1) if index < len(idx_size) and idx_size[index] is not None else 1 for index in range(3)]
        dim0, dim1 = dim_size[0], dim_size[0] * dim_size[1]
        total_size = dim1 * dim_size[2]
        idx_size_log = [int(math.log2(dim0)), int(math.log2(dim1)), 0]
        idx = [self._src(value, node, mapping) for value in item.get("idx", [])]
        remap = item.get("address_remapping")
        remap = list(reversed(remap)) if isinstance(remap, list) else list(range(25, -1, -1))
        stride = item.get("buf_spatial_stride")
        spatial = list(reversed(stride)) if isinstance(stride, list) else None
        if spatial is not None and len(spatial) < 16:
            spatial = [0] * (16 - len(spatial)) + spatial
        values: list[tuple[str, Any, int]] = []
        if write:
            values.append((f"{base}._padding", 0, 3))
        values.extend((
            (f"{base}.mem_idx_mode", [_mode(x) for x in item.get("mem_idx_mode", [])], 6),
            (f"{base}.mem_idx_keep_last_index", item.get("mem_idx_keep_last_index"), 12),
            (f"{base}.idx", idx, 15),
            (f"{base}.mem_idx_constant", item.get("mem_idx_constant"), 24),
            (f"{base}.buf_idx_mode", [_buffer_mode(x) for x in item.get("buf_idx_mode", [])], 2),
            (f"{base}.buf_idx_keep_last_index", item.get("buf_idx_keep_last_index"), 8),
            (f"{base}.ping_pong", item.get("ping_pong", 0), 1),
            (f"{base}.pingpong_last_index", item.get("pingpong_last_index", 0), 4),
            (f"{base}.base_addr", _parse_base_addr(item.get("base_addr")), 30),
            (f"{base}.idx_size", item.get("idx_size"), 24),
            (f"{base}.idx_size_log", idx_size_log, 9),
            (f"{base}.total_size", total_size, 8),
            (f"{base}.dim_stride", item.get("dim_stride"), 60),
            (f"{base}.address_remapping", remap, 130),
        ))
        if not write:
            padding = _mapping(item.get("idx_padding_range"))
            values.extend((
                (f"{base}.padding_reg_value", item.get("padding_reg_value", 0), 8),
                (f"{base}.padding_enable", item.get("padding_enable"), 3),
                (f"{base}.idx_padding_range", list(padding.get("low_bound", [])) + list(padding.get("up_bound", [])), 72),
            ))
        tailing = _mapping(item.get("idx_tailing_range"))
        values.extend((
            (f"{base}.tailing_enable", item.get("tailing_enable"), 3),
            (f"{base}.idx_tailing_range", list(tailing.get("low", [])) + list(tailing.get("up", [])), 72),
            (f"{base}.buf_spatial_stride", spatial, 80),
            (f"{base}.buf_spatial_size", item.get("buf_spatial_size", 0), 5),
        ))
        if not write:
            values.append((f"{base}.buf_full_last_index", item.get("buf_full_last_index", 0), 4))
        return self._module(section, node, mapping.get(node, "UNMAPPED"), values)

    def _encode_neighbor(self, slot: int, key: str, item: Mapping[str, Any]) -> EncodedModule:
        base = f"$.n2n.{key}"
        count = item.get("mem_loop", 0)
        count = count - 1 if isinstance(count, int) and count > 0 else count
        return self._module("se_nse", None, f"NEIGHBOR{slot}", (
            (f"{base}.src_slice_sel", item.get("src_slice_sel", 0), 1),
            (f"{base}.dst_slice_sel", item.get("dst_slice_sel", 0), 1),
            (f"{base}.ping_pong", item.get("ping_pong", 0), 1),
            (f"{base}.mem_loop", count, 5),
        ), slot=slot)

    def _encode_buffer(self, slot: int, item: Mapping[str, Any]) -> EncodedModule:
        base = f"$.buffer_config.buffer{slot}"
        if item.get("enable", 1) == 0:
            return self._empty_module("buffer_manager_cluster", slot)
        lifetime = item.get("buffer_life_time", 0)
        mask = item.get("mask", 0)
        if isinstance(mask, list):
            mask = int("".join(str(x) for x in reversed(mask)), 2)
        return self._module("buffer_manager_cluster", None, f"BUFFER{slot}", (
            (f"{base}.dst_port", item.get("dst_port", 0), 1),
            (f"{base}.buf_full_last_index", item.get("buf_full_last_index", 0), 4),
            (f"{base}.buffer_nbr_cnt", 27 if item.get("buffer_nbr_cnt") is None else item.get("buffer_nbr_cnt"), 5),
            (f"{base}.nbr_enable", item.get("nbr_enable", 0), 1),
            (f"{base}.buffer_life_time", lifetime - 1, 4),
            (f"{base}.mode", item.get("mode", 0), 1),
            (f"{base}.mask", mask, 8),
            (f"{base}.buf_end_row_addr", item.get("buf_end_row_addr", 0), 2),
        ), slot=slot)

    def _encode_special(self, item: Mapping[str, Any]) -> EncodedModule:
        base = "$.special_array"
        values: list[tuple[str, Any, int]] = [
            (f"{base}.mode", 0 if item.get("mode") == "gemm" else 1 if "mode" in item else 0, 1)
        ]
        for index in (2, 1, 0):
            port = _mapping(item.get(f"inport{index}"))
            values.extend((
                (f"{base}.inport{index}.enable", port.get("enable", 0), 1),
                (f"{base}.inport{index}.pingpong_en", port.get("pingpong_en", 0), 1),
                (f"{base}.inport{index}.pingpong_last_index", port.get("pingpong_last_index", 0), 4),
                (f"{base}.inport{index}.nbr_enable", port.get("nbr_enable", 0), 1),
            ))
        values.extend((
            (f"{base}.data_type", {"int8": 0, "fp16": 2, "bf16": 3}.get(item.get("data_type"), item.get("data_type", 0)), 2),
            (f"{base}.transout_last_index", item.get("transout_last_index", 0), 4),
            (f"{base}.bias_enable", item.get("bias_enable", 0), 1),
        ))
        out = _mapping(item.get("outport"))
        values.extend((
            (f"{base}.outport.mode", 0 if out.get("mode") == "col" else 1 if out.get("mode") == "row" else out.get("mode", 0), 1),
            (f"{base}.outport.fp32tofp16", _boolish(out.get("fp32tofp16", 0)), 1),
            (f"{base}.outport.fp32tobf16", _boolish(out.get("fp32tobf16", 0)), 1),
        ))
        return self._module("special_array", None, "SPECIAL0", values, slot=0)

    def _encode_ga_inport(self, slot: int, item: Mapping[str, Any]) -> EncodedModule:
        base = f"$.general_array.inport.inport{slot}"
        mask = item.get("mask", 0)
        if isinstance(mask, list):
            mask = int("".join(str(x) for x in reversed(mask)), 2)
        values: list[tuple[str, Any, int]] = [
            (f"{base}.mask", mask, 8),
            (f"{base}.src_id", item.get("src_id", 0), 1),
            (f"{base}.pingpong_en", item.get("pingpong_en", 0), 1),
            (f"{base}.pingpong_last_index", item.get("pingpong_last_index", 0), 4),
            (f"{base}.nbr_enable", item.get("nbr_enable", 0), 1),
        ]
        for name in ("fp16tofp32", "bf16tofp32", "int32tofp32", "uint8tofp32", "uint8toint32"):
            values.append((f"{base}.{name}", _boolish(item.get(name, 0)), 1))
        return self._module("ga_inport_group", None, f"GA_INPORT{slot}", values, slot=slot)

    def _encode_ga_outport(self, item: Mapping[str, Any]) -> EncodedModule:
        base = "$.general_array.outport"
        mask = item.get("mask", 0)
        if isinstance(mask, list):
            mask = int("".join(str(x) for x in reversed(mask)), 2)
        values: list[tuple[str, Any, int]] = [(f"{base}.mask", mask, 8), (f"{base}.src_id", item.get("src_id", 0), 1)]
        for name in ("fp32tofp16", "fp32tobf16", "int32touint8"):
            values.append((f"{base}.{name}", _boolish(item.get(name, 0)), 1))
        return self._module("ga_outport_group", None, "GA_OUTPORT0", values, slot=0)

    def _encode_ga_pe(
        self, node: str, item: Mapping[str, Any], mapping: Mapping[str, str], slot: int
    ) -> EncodedModule:
        key = node.split(".")[-1]
        base = f"$.general_array.PE_array.{key}"
        opcodes = {
            "add": 0, "sub": 1, "mul": 2, "max": 3, "sum": 4, "summac": 5,
            "mac": 6, "int8_max": 11, "int32_sum": 12, "int32_sub": 13,
            "int32_mac": 14, "rec": 17, "sqrt": 18, "rec_sqrt": 20, "sfu_activation": 24,
        }
        opcode_raw = item.get("alu_opcode")
        values: list[tuple[str, Any, int]] = [
            (f"{base}.alu_opcode", opcodes.get(opcode_raw, opcode_raw if opcode_raw is not None else 0), 5),
            (f"{base}.transout_last_index", 15 if item.get("transout_last_index") is None else item.get("transout_last_index", 0), 4),
        ]
        for index in (2, 1, 0):
            port = _mapping(item.get(f"inport{index}"))
            src = port.get("src_id")
            if isinstance(src, str) and src.lower() == "buffer":
                src = 0
            values.extend((
                (f"{base}.inport{index}.src_id", self._src(src, node, mapping), 3),
                (f"{base}.inport{index}.keep_last_index", port.get("keep_last_index", 0), 4),
                (f"{base}.inport{index}.mode", _mode(port.get("mode")), 2),
            ))
        for index in (0, 1, 2):
            port = _mapping(item.get(f"inport{index}"))
            values.extend((
                (f"{base}._padding{index}", 0, 4),
                (f"{base}.inport{index}.constant", _constant_bits(port.get("constant", 0)), 32),
            ))
        return self._module("ga_pe", node, f"GA_PE{slot}", values, slot=slot)

    def _connection_value(
        self, src: str, dst: str, mapping: Mapping[str, str]
    ) -> tuple[int, bool]:
        src_type, dst_type = _node_type(src), _node_type(dst)
        src_id, dst_id = _physical_id(mapping.get(src)), _physical_id(mapping.get(dst))
        if src_type == "LC" and dst_type == "LC" and src_id is not None and dst_id is not None:
            src_row, dst_row = src_id // 10, dst_id // 10
            diff = src_id % 10 - dst_id % 10
            table = {-2: 5, -1: 6, 1: 7, 2: 8} if src_row == dst_row else {-2: 0, -1: 1, 0: 2, 1: 3, 2: 4}
            return (table.get(diff, 0), diff in table)
        if src_type == "LC" and dst_type == "ROW_LC" and src_id is not None and dst_id is not None:
            candidates = list(range(dst_id * 2 - 2, dst_id * 2 + 4))
            local = src_id % 10
            if local in candidates:
                return candidates.index(local) + (6 if src_id >= 10 else 0), True
            return 0, False
        if src_type == "ROW_LC" and dst_type == "COL_LC":
            return 12, src_id is not None and src_id == dst_id
        if src_type == "LC" and dst_type == "PE" and src_id is not None and dst_id is not None:
            diff = src_id % 10 - dst_id
            table = {-1: 0, 0: 1, 1: 2}
            if diff in table:
                return table[diff] + (3 if src_id >= 10 else 0), True
            return 0, False
        if src_type == "PE" and dst_type == "PE":
            if src.startswith("GA_PE.") and dst.startswith("GA_PE."):
                src_pos, dst_pos = _ga_position(src), _ga_position(dst)
                if src_pos is None or dst_pos is None:
                    return 0, False
                row_diff, col_diff = src_pos[0] - dst_pos[0], src_pos[1] - dst_pos[1]
                table = {(-1, -1): 1, (0, -1): 2, (1, -1): 3, (-1, 0): 4, (1, 0): 5}
                return table.get((row_diff, col_diff), 0), (row_diff, col_diff) in table
            if src_id is not None and dst_id is not None:
                diff = src_id - dst_id
                table = {-2: 6, -1: 7, 1: 8, 2: 9}
                return table.get(diff, 0), diff in table
        if src_type in {"LC", "PE"} and dst_type == "STREAM" and src_id is not None and dst_id is not None:
            dst_resource = mapping.get(dst, "")
            stream_index = dst_id if dst_resource.startswith("READ_STREAM") else 4 if dst_resource == "WRITE_STREAM0" else None
            if stream_index is None:
                return 0, False
            candidates = list(range(stream_index * 2 - 2, stream_index * 2 + 4))
            local = src_id % 10 if src_type == "LC" else src_id
            if local not in candidates:
                return 0, False
            value = candidates.index(local)
            if src_type == "LC":
                value += 6 if src_id >= 10 else 0
            else:
                value += 12
            return value, True
        if (src_type == "STREAM" and dst_type in {"ROW_LC", "COL_LC"}) or (
            src_type in {"ROW_LC", "COL_LC"} and dst_type == "STREAM"
        ):
            stream_node = src if src_type == "STREAM" else dst
            loop_id = dst_id if src_type == "STREAM" else src_id
            stream_resource = mapping.get(stream_node, "")
            stream_id = (
                _physical_id(stream_resource)
                if stream_resource.startswith("READ_STREAM")
                else 4 if stream_resource == "WRITE_STREAM0" else None
            )
            return 0, loop_id is not None and stream_id == loop_id
        return 0, False

    def _build_artifacts(
        self, config_mask: str, modules: Mapping[str, Sequence[EncodedModule]]
    ) -> dict[str, Any]:
        binary = config_mask
        parsed_lines: list[str] = []
        ranges: list[BitRange] = [BitRange(f"$.CONFIG[{i}]", "CONFIG", 0, 0, i, i + 1) for i in range(8)]
        cursor = 8
        for section, mask_index, chunks, _ in SECTION_LAYOUT:
            if config_mask[mask_index] != "1":
                continue
            parsed_lines.append(f"{section}:")
            for module in modules[section]:
                bits = module.bits
                if not bits or set(bits) == {"0"}:
                    for chunk in range(chunks):
                        parsed_lines.append("0")
                        ranges.append(BitRange(f"$bitstream.{section}[{module.slot}].present", section, module.slot, chunk, cursor, cursor + 1))
                        binary += "0"
                        cursor += 1
                    continue
                chunk_width = len(bits) // chunks
                for chunk in range(chunks):
                    chunk_start = chunk * chunk_width
                    payload = bits[chunk_start : chunk_start + chunk_width]
                    parsed_lines.append(f"1 {payload}")
                    ranges.append(BitRange(f"$bitstream.{section}[{module.slot}].present", section, module.slot, chunk, cursor, cursor + 1))
                    cursor += 1
                    for field in module.fields:
                        left, right = max(field.start, chunk_start), min(field.end, chunk_start + chunk_width)
                        if left < right:
                            global_start = cursor + left - chunk_start
                            ranges.append(BitRange(field.path, section, module.slot, chunk, global_start, global_start + right - left))
                    binary += "1" + payload
                    cursor += len(payload)
            parsed_lines.append("")
        padded64 = binary + "0" * ((64 - len(binary) % 64) % 64)
        lines64 = [padded64[index : index + 64] for index in range(0, len(padded64), 64)]
        padded128 = binary + "0" * ((128 - len(binary) % 128) % 128)
        lines128 = [
            padded128[index + 64 : index + 128] + padded128[index : index + 64]
            for index in range(0, len(padded128), 128)
        ]
        return {
            "binary": binary,
            "parsed_lines": parsed_lines,
            "binary64_lines": lines64,
            "binary128_lines": lines128,
            "ranges": ranges,
        }

    def _compare_parsed(self, path: Path, expected: Sequence[str]) -> None:
        try:
            actual = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            self._error("ARTIFACT.PARSED_READ", str(path), str(error))
            return
        while actual and actual[-1] == "":
            actual.pop()
        normalized_expected = list(expected)
        while normalized_expected and normalized_expected[-1] == "":
            normalized_expected.pop()
        if actual != normalized_expected:
            index = next((i for i, pair in enumerate(zip(actual, normalized_expected)) if pair[0] != pair[1]), min(len(actual), len(normalized_expected)))
            got = actual[index] if index < len(actual) else "<missing>"
            want = normalized_expected[index] if index < len(normalized_expected) else "<none>"
            self._error("BITSTREAM.PARSED_MISMATCH", f"{path}:{index + 1}", f"expected {want!r}, got {got!r}")

    def _compare_binary(
        self,
        path: Path,
        expected: Sequence[str],
        *,
        width: int,
        ranges: Sequence[BitRange],
        reordered: bool = False,
    ) -> None:
        try:
            actual = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as error:
            self._error("ARTIFACT.BINARY_READ", str(path), str(error))
            return
        if any(len(line) != width or set(line) - {"0", "1"} for line in actual):
            self._error("BITSTREAM.BINARY_FORMAT", str(path), f"every line must contain exactly {width} bits")
            return
        if actual == list(expected):
            return
        actual_bits, expected_bits = "".join(actual), "".join(expected)
        mismatch = next((i for i, pair in enumerate(zip(actual_bits, expected_bits)) if pair[0] != pair[1]), min(len(actual_bits), len(expected_bits)))
        detail = ""
        if not reordered:
            owner = next((item for item in ranges if item.start <= mismatch < item.end), None)
            if owner:
                detail = f"; owner={owner.path}, section={owner.section}, slot={owner.slot}, chunk={owner.chunk}"
        self._error(
            "BITSTREAM.BINARY_MISMATCH",
            f"{path}:bit[{mismatch}]",
            f"encoded bit differs{detail}",
        )


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _encode_value(value: Any, width: int) -> str:
    if isinstance(value, list):
        if not value:
            return "0" * width
        bits_per_item = max(1, width // len(value))
        return "".join(_uint_bits(0 if item is None else int(item), bits_per_item) for item in value)
    if value is None:
        value = 0
    return _uint_bits(int(value), width)


def _uint_bits(value: int, width: int) -> str:
    return format(value & ((1 << width) - 1), f"0{width}b")


def _mode(value: Any) -> Any:
    return {None: 0, "buffer": 1, "keep": 2, "constant": 3}.get(value, value)


def _buffer_mode(value: Any) -> Any:
    return {"buffer": 0, "keep": 1}.get(value, value)


def _boolish(value: Any) -> Any:
    text = str(value).lower()
    return 1 if text == "true" else 0 if text == "false" else value


def _constant_bits(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        text = value.strip()
        compact = text.replace(" ", "")
        if compact.lower().startswith("0x"):
            try:
                return int(compact, 16)
            except ValueError:
                pass
        if "/" in compact:
            numerator, denominator = compact.split("/", 1)
            try:
                value = float(Fraction(numerator)) / float(Fraction(denominator))
            except (ValueError, ZeroDivisionError):
                pass
        if isinstance(value, str):
            try:
                value = float(Fraction(text))
            except (ValueError, ZeroDivisionError):
                value = float(text)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int.from_bytes(struct.pack("<f", float(value)), byteorder="little", signed=False)
    return int(value)


def _parse_base_addr(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        text = value.strip().replace("_", "")
        if text.startswith(("0b", "0B")):
            return int(text, 2)
        if text and all(char in "01" for char in text):
            return int(text, 2)
        return int(text, 0)
    return int(value)


def _node_type(node: str) -> str:
    if node.startswith("DRAM_LC.LC"):
        return "LC"
    if node.startswith(("LC_PE.PE", "GA_PE.PE")):
        return "PE"
    if "ROW_LC" in node:
        return "ROW_LC"
    if "COL_LC" in node:
        return "COL_LC"
    if node.startswith("STREAM."):
        return "STREAM"
    return "UNKNOWN"


def _physical_id(resource: str | None) -> int | None:
    if not isinstance(resource, str):
        return None
    match = re.search(r"(\d+)$", resource)
    return int(match.group(1)) if match else None


def _ga_position(node: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"GA_PE\.PE(\d)(\d)", node)
    if not match:
        return None
    column, row = int(match.group(1)), int(match.group(2))
    return row, column


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256_file(path).encode("ascii"))
        digest.update(b"\0")
        digest.update(str(path.stat().st_size).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _patchset_digest(manifest: Mapping[str, Any]) -> str | None:
    files = manifest.get("files")
    if not isinstance(files, list):
        return None
    digest = hashlib.sha256()
    for item in files:
        if not isinstance(item, Mapping):
            return None
        path = item.get("path")
        base = item.get("base_sha256_lf")
        patched = item.get("patched_sha256_lf")
        replacements = item.get("replacement_ids")
        if (
            not isinstance(path, str)
            or not _is_sha256(base)
            or not _is_sha256(patched)
            or not isinstance(replacements, list)
            or not all(isinstance(value, str) for value in replacements)
        ):
            return None
        digest.update(
            f"{path}\0{base}\0{patched}\0{','.join(replacements)}\n".encode("utf-8")
        )
    return digest.hexdigest()


def _valid_patchset_policy(manifest: Mapping[str, Any]) -> bool:
    profile = manifest.get("target_profile")
    policy = manifest.get("policy")
    return (
        isinstance(profile, Mapping)
        and profile.get("slices") == 28
        and profile.get("banks_per_slice") == 4
        and profile.get("rows_per_bank") == 6144
        and isinstance(policy, Mapping)
        and policy.get("active_source_read_only") is True
        and policy.get("fail_closed_mapping") is True
        and policy.get("zero_penalty_required") is True
        and policy.get("direct_mapping_is_not_evidence") is True
    )
