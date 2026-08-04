from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


CORPUS_SCHEMA = "ndpsim-operator-config-corpus-v1"
HARDWARE_EVIDENCE_SCHEMA = "ndpsim-operator-config-hardware-evidence-v1"
CONFIG_AUTHORITY_SCHEMA = "operator-config-user-authority-v1"
CONFIG_AUTHORITY_DECISION = (
    ".agents/decisions/ADR-021-scope-config-authority-by-upstream-provenance.md"
)


class OperatorConfigCorpusError(ValueError):
    pass


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OperatorConfigCorpusError(f"cannot parse JSON: {path}: {error}") from error


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def flatten_json(value: Any, path: str = "$") -> dict[str, Any]:
    """Return stable leaf paths without changing list order or scalar values."""

    result: dict[str, Any] = {}
    if isinstance(value, Mapping):
        for key in sorted(value):
            result.update(flatten_json(value[key], f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.update(flatten_json(item, f"{path}[{index}]"))
    else:
        result[path] = value
    return result


def normalized_leaf_path(path: str) -> str:
    return re.sub(r"\[\d+\]", "[]", path)


def _structural_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _structural_value(item)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_structural_value(item) for item in value]
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    return type(value).__name__


def structural_signature(value: Any) -> str:
    """Serialize only object shape, list arity and scalar JSON types."""

    return canonical_json_bytes(_structural_value(value)).decode("utf-8")


def structural_sha256(value: Any) -> str:
    return sha256_bytes(structural_signature(value).encode("utf-8"))


def _operator_family(name: str, config: Mapping[str, Any]) -> str:
    if name.startswith("maxpool_config_"):
        return "maxpool"
    if name.startswith("avgpool_config_"):
        return "avgpool"
    if "gemm" in name:
        return "gemm"
    if "gemv" in name:
        return "gemv"
    if name.startswith("quant_"):
        return "quantize"
    if name.startswith("add_dequant"):
        return "add_dequant"
    if name.startswith("decode_"):
        return "deepseek_decode"
    if name.startswith("prefill_"):
        return "deepseek_prefill"
    if name.startswith("node0004_"):
        return "resnet_conv_accumulate"
    if config.get("special_array"):
        return "special_array"
    if config.get("general_array"):
        return "general_array"
    return "other"


def _feature_summary(config: Mapping[str, Any]) -> dict[str, Any]:
    opcodes: Counter[str] = Counter()
    conversions: Counter[str] = Counter()
    general = config.get("general_array")
    if isinstance(general, Mapping):
        for value in general.values():
            if not isinstance(value, Mapping):
                continue
            opcode = value.get("alu_opcode")
            if isinstance(opcode, str):
                opcodes[opcode] += 1
            for key, enabled in value.items():
                if isinstance(key, str) and "to" in key and enabled:
                    conversions[key] += 1
    streams = config.get("stream_engine")
    padding_streams = 0
    tailing_streams = 0
    pingpong_streams = 0
    if isinstance(streams, Mapping):
        for stream in streams.values():
            if not isinstance(stream, Mapping):
                continue
            padding_streams += int(any(stream.get("padding_enable") or []))
            tailing_streams += int(any(stream.get("tailing_enable") or []))
            pingpong_streams += int(bool(stream.get("ping_pong")))
    special = config.get("special_array")
    sa_types: Counter[str] = Counter()
    if isinstance(special, Mapping):
        for value in special.values():
            if isinstance(value, Mapping) and isinstance(value.get("data_type"), str):
                sa_types[str(value["data_type"])] += 1
    return {
        "config_mask": config.get("CONFIG"),
        "has_special_array": bool(special),
        "has_general_array": bool(general),
        "has_n2n": bool(config.get("n2n")),
        "ga_opcodes": dict(sorted(opcodes.items())),
        "dtype_conversions": dict(sorted(conversions.items())),
        "sa_data_types": dict(sorted(sa_types.items())),
        "padding_stream_count": padding_streams,
        "tailing_stream_count": tailing_streams,
        "pingpong_stream_count": pingpong_streams,
    }


def _iter_operator_type_references(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, Mapping):
        operator_id = value.get("id")
        operator_type = value.get("type")
        if (
            isinstance(operator_id, str)
            and isinstance(operator_type, str)
            and ("inputs" in value or "output" in value)
        ):
            yield operator_type, f"{path}:{operator_id}"
        for key, item in value.items():
            yield from _iter_operator_type_references(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _iter_operator_type_references(item, f"{path}[{index}]")


def _scan_graph_references(project_root: Path) -> dict[str, list[dict[str, str]]]:
    roots = [
        project_root / "ndp-sim/model_execplan/op_json",
        project_root / "ndp-sim/generate_python_golden/model_execplan/op_json",
    ]
    result: dict[str, list[dict[str, str]]] = defaultdict(list)
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                value = _load_json(path)
            except OperatorConfigCorpusError:
                continue
            for operator_type, location in _iter_operator_type_references(value):
                result[operator_type].append(
                    {"path": _relative(path, project_root), "location": location}
                )
    return {key: value for key, value in sorted(result.items())}


def _scan_server_package_instances(
    project_root: Path,
) -> dict[str, list[dict[str, Any]]]:
    """Associate user-provided server package graphs with specialized JSON files."""

    package_root = project_root / "jsons"
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if not package_root.is_dir():
        return {}
    for graph_path in sorted(package_root.rglob("*withbaseaddr.json")):
        try:
            graph = _load_json(graph_path)
        except OperatorConfigCorpusError:
            continue
        operators = graph.get("operators") if isinstance(graph, Mapping) else None
        if not isinstance(operators, list):
            continue
        instance_dir = graph_path.parent / "jsons"
        for operator in operators:
            if not isinstance(operator, Mapping):
                continue
            operator_id = operator.get("id")
            operator_type = operator.get("type")
            if not isinstance(operator_id, str) or not isinstance(operator_type, str):
                continue
            candidates = (
                sorted(instance_dir.glob(f"{operator_id}_{operator_type}.json"))
                if instance_dir.is_dir()
                else []
            )
            if not candidates and instance_dir.is_dir():
                candidates = sorted(instance_dir.glob(f"{operator_id}_*.json"))
            result[operator_type].append(
                {
                    "package_graph": _relative(graph_path, project_root),
                    "operator_id": operator_id,
                    "instance_config": (
                        _relative(candidates[0], project_root) if len(candidates) == 1 else None
                    ),
                    "instance_config_sha256": (
                        sha256_file(candidates[0]) if len(candidates) == 1 else None
                    ),
                }
            )
    return {key: value for key, value in sorted(result.items())}


def _historical_inventory(project_root: Path) -> dict[str, dict[str, Any]]:
    path = project_root / "contracts/target_config_authority_audit.json"
    if not path.is_file():
        return {}
    value = _load_json(path)
    templates = value.get("inventory", {}).get("templates", [])
    result: dict[str, dict[str, Any]] = {}
    for item in templates:
        if not isinstance(item, Mapping) or not isinstance(item.get("path"), str):
            continue
        result[Path(str(item["path"])).name] = dict(item)
    return result


def _is_operator_config(value: Any) -> bool:
    return (
        isinstance(value, Mapping)
        and "CONFIG" in value
        and any(
            key in value
            for key in (
                "dram_loop_configs",
                "stream_engine",
                "special_array",
                "general_array",
            )
        )
    )


def _git_output(repo: Path, *args: str) -> bytes:
    command = [
        "git",
        "-c",
        f"safe.directory={repo.resolve().as_posix()}",
        "-C",
        str(repo.resolve()),
        *args,
    ]
    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise OperatorConfigCorpusError(
            f"cannot inspect pinned ndp-sim repository: {args}: {message}"
        )
    return result.stdout


def _ndpsim_upstream_inventory(project_root: Path) -> dict[str, Any]:
    repo = project_root / "ndp-sim"
    patch_contract_path = project_root / "contracts/ndp_patch_toolchain_v1.json"
    patch_contract = _load_json(patch_contract_path)
    expected_commit = patch_contract.get("base_commit")
    expected_repository = patch_contract.get("base_repository")
    if not isinstance(expected_commit, str) or not isinstance(
        expected_repository, str
    ):
        raise OperatorConfigCorpusError(
            "ndp patch contract lacks base_commit/base_repository"
        )
    head = _git_output(repo, "rev-parse", "HEAD").decode("ascii").strip()
    if head != expected_commit:
        raise OperatorConfigCorpusError(
            f"active ndp-sim HEAD differs from pinned commit: {head}"
        )
    tree_blobs: dict[str, str] = {}
    for line in (
        _git_output(repo, "ls-tree", "-r", expected_commit, "--", "jsons")
        .decode("utf-8")
        .splitlines()
    ):
        metadata, separator, repo_relative = line.partition("\t")
        fields = metadata.split()
        if (
            not separator
            or len(fields) != 3
            or fields[1] != "blob"
            or not repo_relative.endswith(".json")
        ):
            continue
        tree_blobs[repo_relative] = fields[2]
    changed_paths = {
        item.strip()
        for item in _git_output(
            repo, "diff", "--name-only", expected_commit, "--", "jsons"
        )
        .decode("utf-8")
        .splitlines()
        if item.strip().endswith(".json")
    }
    exact_paths: dict[str, dict[str, Any]] = {}
    modified_paths: dict[str, dict[str, Any]] = {}
    for repo_relative, blob_oid in sorted(tree_blobs.items()):
        disk_path = repo / repo_relative
        if not disk_path.is_file():
            raise OperatorConfigCorpusError(
                f"pinned upstream JSON is missing from checkout: {repo_relative}"
            )
        current_bytes = disk_path.read_bytes()
        record = {
            "repository_path": repo_relative,
            "pinned_commit": expected_commit,
            "pinned_git_blob_oid": blob_oid,
            "working_tree_content_sha256": sha256_bytes(current_bytes),
            "git_worktree_matches_pinned_blob": repo_relative not in changed_paths,
        }
        project_relative = f"ndp-sim/{repo_relative}"
        if record["git_worktree_matches_pinned_blob"]:
            exact_paths[project_relative] = record
        else:
            modified_paths[project_relative] = record
    return {
        "repository": expected_repository,
        "commit": expected_commit,
        "contract": {
            "path": _relative(patch_contract_path, project_root),
            "sha256": sha256_file(patch_contract_path),
        },
        "exact_paths": exact_paths,
        "modified_paths": modified_paths,
    }


def build_operator_config_authority(project_root: Path) -> dict[str, Any]:
    """Classify authorized references without conflating later project additions."""

    root = project_root.resolve()
    upstream = _ndpsim_upstream_inventory(root)
    decision_path = root / CONFIG_AUTHORITY_DECISION
    if not decision_path.is_file():
        raise OperatorConfigCorpusError(
            f"configuration authority decision is missing: {CONFIG_AUTHORITY_DECISION}"
        )
    source_specs = (
        ("ndp-sim/jsons", False),
        ("jsons", True),
    )
    records: list[dict[str, Any]] = []
    inventory_root_counts: Counter[str] = Counter()
    authorized_root_counts: Counter[str] = Counter()
    for source_root, recursive in source_specs:
        directory = root / source_root
        if not directory.is_dir():
            raise OperatorConfigCorpusError(
                f"authorized configuration root is missing: {source_root}"
            )
        paths = (
            sorted(directory.rglob("*.json"))
            if recursive
            else sorted(directory.glob("*.json"))
        )
        for path in paths:
            value = _load_json(path)
            if not _is_operator_config(value):
                continue
            relative = _relative(path, root)
            if source_root == "jsons":
                provenance = {
                    "kind": "user_supplied_root_reference",
                    "user_authorized_as_correct": True,
                }
                correctness = "user_authorized_correct_reference"
                evidence_class = "high_strength_hardware_validated_baseline"
                allowed_uses = [
                    "configuration_semantics",
                    "rule_extraction",
                    "exact_reference_reproduction",
                    "derived_candidate_seed",
                ]
            elif relative in upstream["exact_paths"]:
                provenance = {
                    "kind": "pinned_upstream_exact_blob",
                    **upstream["exact_paths"][relative],
                }
                correctness = "user_authorized_correct_reference"
                evidence_class = (
                    "high_strength_upstream_hardware_tested_baseline"
                )
                allowed_uses = [
                    "configuration_semantics",
                    "rule_extraction",
                    "exact_reference_reproduction",
                    "derived_candidate_seed",
                ]
            else:
                modified = upstream["modified_paths"].get(relative)
                provenance = {
                    "kind": (
                        "pinned_upstream_path_locally_modified"
                        if modified is not None
                        else "project_added_after_pinned_upstream"
                    ),
                    **(modified or {}),
                }
                correctness = "not_authorized_as_tested_reference"
                evidence_class = (
                    "project_added_candidate_requires_independent_validation"
                )
                allowed_uses = [
                    "identity_audit",
                    "failure_analysis",
                    "static_hypothesis_only",
                ]
            records.append(
                {
                    "path": relative,
                    "source_root": source_root,
                    "sha256": sha256_file(path),
                    "size_bytes": path.stat().st_size,
                    "provenance": provenance,
                    "configuration_correctness": correctness,
                    "evidence_class": evidence_class,
                    "allowed_uses": allowed_uses,
                    "derived_candidate_requires_validation": True,
                }
            )
            inventory_root_counts[source_root] += 1
            if correctness == "user_authorized_correct_reference":
                authorized_root_counts[source_root] += 1
    if inventory_root_counts != Counter({"ndp-sim/jsons": 55, "jsons": 12}):
        raise OperatorConfigCorpusError(
            "configuration inventory differs: "
            f"{dict(inventory_root_counts)}"
        )
    if authorized_root_counts != Counter({"ndp-sim/jsons": 53, "jsons": 12}):
        raise OperatorConfigCorpusError(
            "authorized configuration classification differs: "
            f"{dict(authorized_root_counts)}"
        )
    authorized_count = sum(
        item["configuration_correctness"]
        == "user_authorized_correct_reference"
        for item in records
    )
    excluded_records = [
        item for item in records
        if item["configuration_correctness"]
        != "user_authorized_correct_reference"
    ]
    payload: dict[str, Any] = {
        "schema": CONFIG_AUTHORITY_SCHEMA,
        "status": "provenance_scoped_reference_configuration_authority",
        "authority": {
            "decision": {
                "path": CONFIG_AUTHORITY_DECISION,
                "sha256": sha256_file(decision_path),
                "size_bytes": decision_path.stat().st_size,
            },
            "statement_scope": [
                "jsons operator configurations",
                "ndp-sim/jsons configurations present unchanged in the pinned upstream commit",
            ],
            "reference_configuration_correctness_accepted": True,
            "per_file_raw_receipt_required_for_rule_extraction": False,
            "later_project_additions_are_not_implicitly_authorized": True,
        },
        "pinned_ndpsim_upstream": {
            "repository": upstream["repository"],
            "commit": upstream["commit"],
            "contract": upstream["contract"],
            "exact_operator_config_count": len(upstream["exact_paths"]),
            "modified_operator_config_count": len(upstream["modified_paths"]),
        },
        "policy": {
            "reference_config_may_seed_semantic_rules": True,
            "reference_config_may_seed_derived_candidates": True,
            "derived_shape_address_constant_or_topology_is_not_preapproved": True,
            "project_package_execution_is_separate_evidence": True,
            "formal_resnet50_release_still_requires_e4_e5": True,
        },
        "summary": {
            "inventory_operator_config_count": len(records),
            "authorized_operator_config_count": authorized_count,
            "not_authorized_as_tested_reference_count": len(excluded_records),
            "source_root_inventory_counts": dict(
                sorted(inventory_root_counts.items())
            ),
            "source_root_authorized_counts": dict(
                sorted(authorized_root_counts.items())
            ),
            "all_inventory_records_authorized_correct": all(
                item["configuration_correctness"]
                == "user_authorized_correct_reference"
                for item in records
            ),
            "excluded_paths": [item["path"] for item in excluded_records],
        },
        "records": records,
    }
    payload["authority_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


_EXACT_EVIDENCE: dict[str, dict[str, Any]] = {
    "decode_summac_fp32N_fp32N.json": {
        "status": "server_natural_completion_user_reported",
        "evidence_level": "E3-reported",
        "positive_hardware_test": True,
        "numeric_hardware_test": False,
        "sources": [".agents/decisions/ADR-010-operator-config-rule-r0-identity-evidence.md"],
    },
    "decode_max_fp32N_fp32N.json": {
        "status": "server_natural_completion_raw_log_readback_missing",
        "evidence_level": "E3",
        "positive_hardware_test": True,
        "numeric_hardware_test": False,
        "sources": [
            "server_returns/decode_max_fp32_simresults_1/simresults/sim.log"
        ],
    },
    "maxpool_config_16_112_112_stride2_padding1.json": {
        "status": "server_non_completion_write_data_absent",
        "evidence_level": "hardware-negative",
        "positive_hardware_test": False,
        "numeric_hardware_test": False,
        "sources": [".agents/agent.md", ".agents/plan.md"],
    },
    "node0004_accumulate_wave0.json": {
        "status": "server_non_completion_suspected_deadlock",
        "evidence_level": "hardware-negative",
        "positive_hardware_test": False,
        "numeric_hardware_test": False,
        "sources": [".agents/agent.md", ".agents/plan.md"],
    },
    "node0004_accumulate_wave0_nopp_r1.json": {
        "status": "server_attempt_invalid_missing_preload_files_and_bitstream",
        "evidence_level": "hardware-attempt-invalid",
        "positive_hardware_test": False,
        "numeric_hardware_test": False,
        "sources": [
            ".agents/agent.md",
            ".agents/plan.md",
            "server_returns/node0004_nopp_r1_sim_results_2/sim_results/终端.txt",
        ],
    },
}


def _validate_known_receipt(source: str, payload: str) -> list[str]:
    required: list[str] = []
    if source.endswith("decode_max_fp32_simresults_1/simresults/sim.log"):
        required = [
            "+SCA_CFG=install/cfg_pkg/decode_max_fp32N_fp32N_graph/sca_cfg.json",
            "INFO: slice start",
            "INFO: slice completed after",
            "Simulation completed successfully!",
            "skip matrix readback",
        ]
    elif source.endswith("node0004_nopp_r1_sim_results_2/sim_results/终端.txt"):
        required = [
            "ERROR: Cannot open file install/op0/",
            "ERROR: Cannot open file install/cfg_pkg/"
            "op0_node0004_accumulate_wave0_nopp_r1_bitstream_128b.bin",
            "100000000000 ps",
        ]
    missing = [marker for marker in required if marker not in payload]
    if missing:
        raise OperatorConfigCorpusError(
            f"hardware receipt no longer supports its evidence classification: "
            f"{source}: {missing}"
        )
    return required


def build_operator_config_corpus(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    authority = build_operator_config_authority(root)
    authority_by_path = {item["path"]: item for item in authority["records"]}
    config_root = root / "ndp-sim/jsons"
    paths = sorted(config_root.glob("*.json"))
    if not paths:
        raise OperatorConfigCorpusError("ndp-sim/jsons contains no JSON files")
    historical = _historical_inventory(root)
    graph_refs = _scan_graph_references(root)
    package_instances = _scan_server_package_instances(root)

    templates: list[dict[str, Any]] = []
    normalized_paths: set[str] = set()
    family_counts: Counter[str] = Counter()
    for path in paths:
        value = _load_json(path)
        if not isinstance(value, Mapping):
            raise OperatorConfigCorpusError(f"operator JSON root must be an object: {path}")
        leaves = flatten_json(value)
        normalized_paths.update(normalized_leaf_path(item) for item in leaves)
        family = _operator_family(path.stem, value)
        family_counts[family] += 1
        historical_item = historical.get(path.name)
        instances = package_instances.get(path.stem, [])
        relative_path = _relative(path, root)
        authority_record = authority_by_path.get(relative_path)
        if authority_record is None:
            raise OperatorConfigCorpusError(
                f"active template lacks provenance classification: {relative_path}"
            )
        templates.append(
            {
                "template_id": path.stem,
                "path": relative_path,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "family": family,
                "top_level_keys": sorted(value),
                "leaf_count": len(leaves),
                "normalized_leaf_path_count": len(
                    {normalized_leaf_path(item) for item in leaves}
                ),
                "structural_sha256": structural_sha256(value),
                "features": _feature_summary(value),
                "graph_references": graph_refs.get(path.stem, []),
                "server_package_instances": instances,
                "configuration_authority": {
                    "status": authority_record["configuration_correctness"],
                    "evidence_class": authority_record["evidence_class"],
                    "provenance": authority_record["provenance"],
                    "accepted_as_correct_reference": (
                        authority_record["configuration_correctness"]
                        == "user_authorized_correct_reference"
                    ),
                    "derived_candidate_requires_validation": authority_record[
                        "derived_candidate_requires_validation"
                    ],
                },
                "historical_inventory": (
                    {
                        "present": True,
                        "classification": historical_item.get("classification"),
                        "recorded_sha256": historical_item.get("sha256"),
                        "same_sha256": historical_item.get("sha256") == sha256_file(path),
                    }
                    if historical_item is not None
                    else {"present": False}
                ),
            }
        )

    payload: dict[str, Any] = {
        "schema": CORPUS_SCHEMA,
        "source_root": "ndp-sim/jsons",
        "configuration_authority": {
            "schema": authority["schema"],
            "authority_sha256": authority["authority_sha256"],
            "decision": authority["authority"]["decision"],
        },
        "summary": {
            "template_count": len(templates),
            "historical_inventory_count": len(historical),
            "historical_overlap_count": sum(
                item["historical_inventory"]["present"] for item in templates
            ),
            "normalized_leaf_path_count": len(normalized_paths),
            "family_counts": dict(sorted(family_counts.items())),
            "graph_referenced_template_count": sum(
                bool(item["graph_references"]) for item in templates
            ),
            "server_package_instance_template_count": sum(
                bool(item["server_package_instances"]) for item in templates
            ),
            "user_authorized_correct_template_count": sum(
                item["configuration_authority"]["status"]
                == "user_authorized_correct_reference"
                for item in templates
            ),
            "project_added_or_modified_template_count": sum(
                not item["configuration_authority"][
                    "accepted_as_correct_reference"
                ]
                for item in templates
            ),
        },
        "normalized_leaf_paths": sorted(normalized_paths),
        "templates": templates,
    }
    payload["corpus_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def build_hardware_evidence_audit(
    project_root: Path, corpus: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    root = project_root.resolve()
    corpus_value = dict(corpus or build_operator_config_corpus(root))
    records: list[dict[str, Any]] = []
    for template in corpus_value["templates"]:
        name = f"{template['template_id']}.json"
        exact = dict(
            _EXACT_EVIDENCE.get(
                name,
                {
                    "status": "no_per_template_hardware_receipt_in_repository",
                    "evidence_level": "unproven-per-template",
                    "positive_hardware_test": False,
                    "numeric_hardware_test": False,
                    "sources": [],
                },
            )
        )
        receipts = []
        for source in exact.get("sources", []):
            source_path = root / source
            if source_path.is_file():
                required_markers: list[str] = []
                if source_path.suffix.lower() in {".log", ".txt"}:
                    try:
                        text = source_path.read_text(encoding="utf-8")
                    except UnicodeError as error:
                        raise OperatorConfigCorpusError(
                            f"cannot decode hardware receipt: {source}: {error}"
                        ) from error
                    required_markers = _validate_known_receipt(source, text)
                receipts.append(
                    {
                        "path": source,
                        "sha256": sha256_file(source_path),
                        "size_bytes": source_path.stat().st_size,
                        "required_markers": required_markers,
                    }
                )
        exact["source_receipts"] = receipts
        inherited = template["historical_inventory"]
        package_instances = template["server_package_instances"]
        accepted_reference = bool(
            template["configuration_authority"][
                "accepted_as_correct_reference"
            ]
        )
        records.append(
            {
                "template_id": template["template_id"],
                "path": template["path"],
                "sha256": template["sha256"],
                "family": template["family"],
                "exact_config_evidence": exact,
                "reference_configuration_correctness": {
                    "status": template["configuration_authority"]["status"],
                    "evidence_class": template["configuration_authority"][
                        "evidence_class"
                    ],
                    "provenance": template["configuration_authority"][
                        "provenance"
                    ],
                    "accepted_for_rule_extraction": accepted_reference,
                    "accepted_as_correct_reference": accepted_reference,
                    "derived_candidate_requires_validation": True,
                    "execution_receipt_is_separate": True,
                },
                "inherited_deepseek_baseline_member": bool(
                    inherited.get("present")
                    and inherited.get("classification") == "deepseek_transformer"
                ),
                "inherited_baseline_note": (
                    "Membership supports common physical-method inheritance; "
                    "it is not a per-file execution receipt."
                ),
                "server_package_instances": package_instances,
                "server_package_note": (
                    "The user-provided package is reported runnable, but its specialized "
                    "instance may differ from this source template and raw run logs are absent."
                    if package_instances
                    else None
                ),
                "positive_hardware_test_proven": bool(
                    exact.get("positive_hardware_test")
                ),
                "numeric_hardware_test_proven": bool(
                    exact.get("numeric_hardware_test")
                ),
            }
        )

    positive = sum(item["positive_hardware_test_proven"] for item in records)
    numeric = sum(item["numeric_hardware_test_proven"] for item in records)
    negative = sum(
        item["exact_config_evidence"]["evidence_level"] == "hardware-negative"
        for item in records
    )
    invalid_attempts = sum(
        item["exact_config_evidence"]["evidence_level"] == "hardware-attempt-invalid"
        for item in records
    )
    inherited_count = sum(
        item["inherited_deepseek_baseline_member"] for item in records
    )
    package_count = sum(bool(item["server_package_instances"]) for item in records)
    authorized_correct = sum(
        item["reference_configuration_correctness"][
            "accepted_as_correct_reference"
        ]
        for item in records
    )
    payload: dict[str, Any] = {
        "schema": HARDWARE_EVIDENCE_SCHEMA,
        "scope": "all top-level ndp-sim/jsons operator templates",
        "evidence_policy": {
            "package_presence_is_not_execution_receipt": True,
            "operator_confirmation_is_reported_evidence": True,
            "server_natural_completion_is_not_numeric_equality": True,
            "negative_runs_are_preserved": True,
            "user_authorized_reference_correctness_is_accepted": True,
            "reference_correctness_is_separate_from_project_run_receipts": True,
            "project_added_configs_are_not_implicitly_authorized": True,
        },
        "summary": {
            "template_count": len(records),
            "exact_positive_hardware_test_count": positive,
            "exact_numeric_hardware_test_count": numeric,
            "exact_hardware_negative_count": negative,
            "invalid_hardware_attempt_count": invalid_attempts,
            "inherited_deepseek_baseline_member_count": inherited_count,
            "server_package_instance_template_count": package_count,
            "user_authorized_correct_reference_count": authorized_correct,
            "all_templates_authorized_correct_references": (
                authorized_correct == len(records)
            ),
            "all_templates_positive_hardware_test_proven": positive == len(records),
            "all_templates_numeric_hardware_test_proven": numeric == len(records),
            "conclusion": (
                "The 53 ndp-sim templates that exactly match the pinned upstream "
                "commit are accepted as correct hardware-tested references. The two "
                "project-added node0004 templates are not covered by that authority "
                "and retain their negative/invalid test evidence. Exact run receipts "
                "remain a separate audit dimension for all configurations."
            ),
        },
        "records": records,
    }
    payload["audit_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def write_json_contract(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "CONFIG_AUTHORITY_SCHEMA",
    "CORPUS_SCHEMA",
    "HARDWARE_EVIDENCE_SCHEMA",
    "OperatorConfigCorpusError",
    "build_hardware_evidence_audit",
    "build_operator_config_authority",
    "build_operator_config_corpus",
    "flatten_json",
    "normalized_leaf_path",
    "structural_sha256",
    "write_json_contract",
]
