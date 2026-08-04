from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_corpus import (
    build_operator_config_corpus,
    flatten_json,
)


SCHEMA = "ndpsim-operator-config-rule-evidence-v1"


class OperatorConfigRuleError(ValueError):
    pass


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise OperatorConfigRuleError(f"cannot parse JSON: {path}: {error}") from error
    if not isinstance(value, dict):
        raise OperatorConfigRuleError(f"JSON root must be an object: {path}")
    return value


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _change_class(path: str) -> str:
    leaf = path.rsplit(".", 1)[-1]
    if leaf == "base_addr":
        return "address_relocation"
    if any(
        token in path
        for token in (
            ".src_id",
            ".target",
            ".mode",
            ".enable",
            ".idx[",
            ".CONFIG",
        )
    ):
        return "topology"
    if any(
        token in path
        for token in (
            ".start",
            ".stride",
            ".end",
            ".last_index",
            ".idx_size",
            ".dim_stride",
            ".padding_",
            ".idx_padding_range",
            ".tailing_",
            ".idx_tailing_range",
            ".buf_",
            ".ping_pong",
            ".pingpong_",
        )
    ):
        return "schedule_or_boundary"
    if any(
        token in path
        for token in (
            ".constant",
            ".alu_opcode",
            ".data_type",
            "tofp",
            "toint",
            "touint",
            ".bias_",
        )
    ):
        return "numeric_semantics"
    return "other"


def compare_configs(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> list[dict[str, Any]]:
    left_leaves = flatten_json(left)
    right_leaves = flatten_json(right)
    differences: list[dict[str, Any]] = []
    for path in sorted(set(left_leaves) | set(right_leaves)):
        left_present = path in left_leaves
        right_present = path in right_leaves
        if left_present and right_present and left_leaves[path] == right_leaves[path]:
            continue
        differences.append(
            {
                "path": path,
                "class": _change_class(path),
                "left_present": left_present,
                "right_present": right_present,
                "left": left_leaves.get(path),
                "right": right_leaves.get(path),
            }
        )
    return differences


def _pair_record(
    root: Path,
    left_path: Path,
    right_path: Path,
    *,
    relation: str,
    parameters: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    differences = compare_configs(_load_object(left_path), _load_object(right_path))
    classes = Counter(item["class"] for item in differences)
    return {
        "relation": relation,
        "left": {
            "path": _relative(left_path, root),
            "sha256": sha256_file(left_path),
        },
        "right": {
            "path": _relative(right_path, root),
            "sha256": sha256_file(right_path),
        },
        "parameters": dict(parameters or {}),
        "difference_count": len(differences),
        "change_class_counts": dict(sorted(classes.items())),
        "relocation_only": bool(differences)
        and set(classes) == {"address_relocation"},
        "topology_changes": classes["topology"] > 0,
        "differences": differences,
    }


def build_operator_config_rule_evidence(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    corpus = build_operator_config_corpus(root)
    template_root = root / "ndp-sim/jsons"
    pairs: list[dict[str, Any]] = []

    maxpool_small = template_root / "maxpool_config_16_16_16_stride2_padding1.json"
    maxpool_large = template_root / "maxpool_config_16_112_112_stride2_padding1.json"
    if maxpool_small.is_file() and maxpool_large.is_file():
        pairs.append(
            _pair_record(
                root,
                maxpool_small,
                maxpool_large,
                relation="same_operator_family_different_spatial_shape",
                parameters={
                    "left": {
                        "channels": 16,
                        "height": 16,
                        "width": 16,
                        "stride": 2,
                        "padding": 1,
                    },
                    "right": {
                        "channels": 16,
                        "height": 112,
                        "width": 112,
                        "stride": 2,
                        "padding": 1,
                    },
                },
            )
        )

    for template in corpus["templates"]:
        source_path = root / template["path"]
        for instance in template["server_package_instances"]:
            instance_name = instance.get("instance_config")
            if not isinstance(instance_name, str):
                continue
            instance_path = root / instance_name
            if not instance_path.is_file():
                continue
            pairs.append(
                _pair_record(
                    root,
                    source_path,
                    instance_path,
                    relation="source_template_to_server_package_instance",
                    parameters={
                        "template_id": template["template_id"],
                        "package_graph": instance["package_graph"],
                        "operator_id": instance["operator_id"],
                    },
                )
            )

    class_counts: Counter[str] = Counter()
    for pair in pairs:
        class_counts.update(pair["change_class_counts"])
    maxpool_pair = next(
        (
            pair
            for pair in pairs
            if pair["relation"] == "same_operator_family_different_spatial_shape"
        ),
        None,
    )
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "source_corpus_sha256": corpus["corpus_sha256"],
        "summary": {
            "pair_count": len(pairs),
            "change_class_counts": dict(sorted(class_counts.items())),
            "relocation_only_pair_count": sum(pair["relocation_only"] for pair in pairs),
            "topology_changing_pair_count": sum(
                pair["topology_changes"] for pair in pairs
            ),
            "maxpool_shape_difference_count": (
                maxpool_pair["difference_count"] if maxpool_pair else None
            ),
        },
        "inference_policy": {
            "derive_formulas_from_shape_and_dataflow": True,
            "do_not_interpolate_register_values_blindly": True,
            "address_relocation_may_be_bound_late": True,
            "topology_change_requires_schedule_rule": True,
            "numeric_semantic_change_requires_typed_parameter_contract": True,
            "every_rule_must_reproduce_known_configs": True,
        },
        "pairs": pairs,
    }
    payload["evidence_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def write_operator_config_rule_evidence(
    path: Path, value: Mapping[str, Any]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "OperatorConfigRuleError",
    "build_operator_config_rule_evidence",
    "compare_configs",
    "write_operator_config_rule_evidence",
]
