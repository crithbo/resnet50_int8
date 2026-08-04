from __future__ import annotations

import json
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .ndpsim_native import (
    NdpSimNativeError,
    load_native_execution_plan,
    native_control_handlers,
)
from .operator_config_corpus import build_operator_config_corpus


SCHEMA = "deepseek-hardware-stage-ir-crosswalk-v1"
CORPUS_PATH = "contracts/operator_config/ndpsim_json_corpus_v1.json"
BASE_INFO_PATH = "ndp-sim/model_execplan/config/operator_base_info.json"
DEEPSEEK_FAMILIES = {
    "deepseek_decode",
    "deepseek_prefill",
    "gemm",
    "gemv",
}


class DeepSeekStageIRError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise DeepSeekStageIRError(f"cannot parse JSON: {path}: {error}") from error


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise DeepSeekStageIRError(f"required DeepSeek evidence is missing: {relative}")
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _optional_binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative,
        "exists": path.is_file(),
        "sha256": sha256_file(path) if path.is_file() else None,
        "size_bytes": path.stat().st_size if path.is_file() else None,
    }


def _declared_operator(
    graph: Mapping[str, Any], operator_id: str, operator_type: str
) -> Mapping[str, Any]:
    operators = graph.get("operators")
    if isinstance(operators, list):
        values = operators
    elif isinstance(operators, Mapping):
        values = list(operators.values())
    else:
        raise DeepSeekStageIRError("native graph has no operators collection")
    matches = [
        item
        for item in values
        if isinstance(item, Mapping)
        and item.get("id") == operator_id
        and item.get("type") == operator_type
    ]
    if len(matches) != 1:
        raise DeepSeekStageIRError(
            f"graph declaration does not identify one stage: "
            f"{operator_id}:{operator_type}"
        )
    return matches[0]


def _source_kind(source: Any) -> str:
    if source is None:
        return "unspecified"
    if isinstance(source, str):
        if source == "external":
            return "external"
        if source.startswith("op-"):
            return "relative_predecessor"
        if source.startswith("op"):
            return "local_stage"
        return "named_source"
    if isinstance(source, Mapping):
        if source.get("type") == "external":
            return "external"
        return "structured_source"
    return "malformed"


def _input_records(operator: Mapping[str, Any]) -> list[dict[str, Any]]:
    inputs = operator.get("inputs")
    if not isinstance(inputs, Mapping):
        raise DeepSeekStageIRError(
            f"operator inputs are malformed: {operator.get('id')}"
        )
    records = []
    for port, value in sorted(inputs.items()):
        if not isinstance(value, Mapping):
            raise DeepSeekStageIRError(
                f"operator input is malformed: {operator.get('id')}:{port}"
            )
        source = deepcopy(value.get("source"))
        records.append(
            {
                "port": str(port),
                "shape": deepcopy(value.get("shape")),
                "dtype": value.get("dtype"),
                "partition_type": value.get("type"),
                "source": source,
                "source_kind": _source_kind(source),
                "remapping": deepcopy(value.get("remapping")),
                "write_reg_hint": value.get("write_reg_hint"),
            }
        )
    return records


def _output_record(operator: Mapping[str, Any]) -> dict[str, Any]:
    output = operator.get("output")
    if not isinstance(output, Mapping):
        raise DeepSeekStageIRError(
            f"operator output is malformed: {operator.get('id')}"
        )
    return {
        "shape": deepcopy(output.get("shape")),
        "dtype": output.get("dtype"),
        "partition_type": output.get("type"),
        "remapping": deepcopy(output.get("remapping")),
        "write_reg_hint": output.get("write_reg_hint"),
    }


def _base_info_record(
    root: Path, stage_type: str, base_info: Mapping[str, Any]
) -> dict[str, Any] | None:
    item = base_info.get(stage_type)
    if not isinstance(item, Mapping):
        return None
    stream_file = item.get("initial_config_stream", {}).get("bitstream_file")
    declared_bitstream = item.get("config_bitstream_path")
    result = {
        "config_length": item.get("config_length"),
        "ddr_config_addr": item.get("ddr_config_addr"),
        "config_bitstream_addr": item.get("config_bitstream_addr"),
        "config_bitstream_path": declared_bitstream,
        "initial_size": deepcopy(item.get("initial_size")),
        "config_sfu": item.get("config_sfu"),
        "initial_config_stream": deepcopy(item.get("initial_config_stream")),
    }
    if isinstance(stream_file, str):
        result["parsed_bitstream"] = _optional_binding(
            root, f"ndp-sim/model_execplan/config/{stream_file}"
        )
    if isinstance(declared_bitstream, str):
        result["packed_bitstream"] = _optional_binding(
            root, f"ndp-sim/model_execplan/{declared_bitstream}"
        )
    return result


def _instance_records(
    root: Path, values: Any
) -> list[dict[str, Any]]:
    if not isinstance(values, list):
        raise DeepSeekStageIRError("server package instance list is malformed")
    result = []
    for item in values:
        if not isinstance(item, Mapping):
            raise DeepSeekStageIRError("server package instance is malformed")
        graph_relative = str(item.get("package_graph"))
        graph = _optional_binding(root, graph_relative)
        instance_relative = item.get("instance_config")
        instance = (
            _optional_binding(root, str(instance_relative))
            if isinstance(instance_relative, str)
            else None
        )
        if (
            instance is not None
            and item.get("instance_config_sha256") != instance.get("sha256")
        ):
            raise DeepSeekStageIRError(
                f"server instance identity differs: {instance_relative}"
            )
        result.append(
            {
                "operator_id": item.get("operator_id"),
                "package_graph": graph,
                "instance_config": instance,
            }
        )
    return result


def build_deepseek_stage_ir(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    corpus_path = root / CORPUS_PATH
    corpus = _load(corpus_path)
    rebuilt_corpus = build_operator_config_corpus(root)
    if corpus != rebuilt_corpus:
        raise DeepSeekStageIRError("checked operator configuration corpus is stale")
    base_info_value = _load(root / BASE_INFO_PATH)
    base_info = base_info_value.get("operators")
    if not isinstance(base_info, Mapping):
        raise DeepSeekStageIRError("operator_base_info operators are missing")

    templates = [
        item
        for item in corpus.get("templates", [])
        if isinstance(item, Mapping)
        and item.get("family") in DEEPSEEK_FAMILIES
    ]
    if len(templates) != 47:
        raise DeepSeekStageIRError(
            f"DeepSeek template inventory differs: {len(templates)}"
        )

    graph_cache: dict[str, Any] = {}
    native_graph_cache: dict[str, dict[str, Any] | None] = {}
    graph_bindings: dict[str, dict[str, Any]] = {}
    stage_records: list[dict[str, Any]] = []
    template_to_stage_ids: dict[str, list[str]] = defaultdict(list)
    seen_stage_keys: set[tuple[str, str, str]] = set()
    template_crosswalk: dict[str, Any] = {}

    for template in sorted(templates, key=lambda item: str(item["template_id"])):
        template_id = str(template["template_id"])
        template_path = str(template["path"])
        authority = template.get("configuration_authority")
        if (
            not isinstance(authority, Mapping)
            or authority.get("accepted_as_correct_reference") is not True
            or authority.get("provenance", {}).get("kind")
            != "pinned_upstream_exact_blob"
        ):
            raise DeepSeekStageIRError(
                f"DeepSeek template is not an authorized upstream reference: {template_id}"
            )
        if template.get("sha256") != sha256_file(root / template_path):
            raise DeepSeekStageIRError(
                f"DeepSeek template identity differs: {template_id}"
            )
        references = template.get("graph_references")
        if not isinstance(references, list):
            raise DeepSeekStageIRError(
                f"DeepSeek graph reference list is malformed: {template_id}"
            )
        instances = _instance_records(
            root, template.get("server_package_instances", [])
        )
        base_record = _base_info_record(root, template_id, base_info)
        for reference in references:
            if not isinstance(reference, Mapping):
                raise DeepSeekStageIRError(
                    f"DeepSeek graph reference is malformed: {template_id}"
                )
            graph_relative = str(reference.get("path"))
            location = str(reference.get("location"))
            graph = graph_cache.get(graph_relative)
            if graph is None:
                graph = _load(root / graph_relative)
                graph_cache[graph_relative] = graph
                try:
                    native_graph_cache[graph_relative] = (
                        load_native_execution_plan(root, graph_relative)
                    )
                except NdpSimNativeError:
                    # Some op_json files are native graph fragments whose
                    # parameter environment is supplied only after
                    # gen_layer0_oplist assembles the executable graph.
                    native_graph_cache[graph_relative] = None
                graph_bindings[graph_relative] = _binding(
                    root, graph_relative
                )
            operator_id = location.rsplit(":", maxsplit=1)[-1]
            native_graph = native_graph_cache[graph_relative]
            if native_graph is not None:
                native_matches = [
                    operator
                    for operator in native_graph.get("operators", [])
                    if isinstance(operator, Mapping)
                    and operator.get("id") == operator_id
                    and operator.get("type") == template_id
                ]
                if len(native_matches) != 1:
                    raise DeepSeekStageIRError(
                        "native model_execplan parser does not identify one "
                        f"stage: {graph_relative}:{location}:{template_id}"
                    )
            if not isinstance(graph, Mapping):
                raise DeepSeekStageIRError(
                    f"graph root is not an object: {graph_relative}"
                )
            operator = _declared_operator(
                graph, operator_id, template_id
            )
            key = (graph_relative, location, template_id)
            if key in seen_stage_keys:
                raise DeepSeekStageIRError(
                    f"duplicate DeepSeek stage reference: {key}"
                )
            seen_stage_keys.add(key)
            stage_payload = {
                "graph_path": graph_relative,
                "graph_sha256": graph_bindings[graph_relative]["sha256"],
                "graph_location": location,
                "operator_id": operator["id"],
                "stage_type": template_id,
                "template_path": template_path,
                "template_sha256": template["sha256"],
                "template_family": template["family"],
                "graph_params": deepcopy(graph.get("params"))
                if isinstance(graph, Mapping)
                else None,
                "graph_shape_bindings": deepcopy(
                    graph.get("shape_bindings")
                )
                if isinstance(graph, Mapping)
                else None,
                "graph_used_slices": deepcopy(graph.get("used_slices"))
                if isinstance(graph, Mapping)
                else None,
                "stage_used_slices": deepcopy(operator.get("used_slices")),
                "inputs": _input_records(operator),
                "output": _output_record(operator),
                "operator_base_info": deepcopy(base_record),
            }
            stage_id = (
                "ds:"
                + sha256_bytes(canonical_json_bytes(stage_payload))[:20]
            )
            stage_records.append(
                {
                    "stage_id": stage_id,
                    **stage_payload,
                    "stage_sha256": sha256_bytes(
                        canonical_json_bytes(stage_payload)
                    ),
                }
            )
            template_to_stage_ids[template_id].append(stage_id)
        template_crosswalk[template_id] = {
            "family": template["family"],
            "template": _binding(root, template_path),
            "configuration_authority": deepcopy(authority),
            "graph_reference_count": len(references),
            "stage_ids": [],
            "operator_base_info": deepcopy(base_record),
            "server_package_instances": instances,
            "reverse_reproduction": {
                "exact_template_identity_bound": True,
                "graph_shape_contract_available": bool(references),
                "operator_base_info_available": base_record is not None,
                "address_bound_instance_count": sum(
                    item["instance_config"] is not None
                    for item in instances
                ),
                "derived_changes_require_independent_validation": True,
            },
        }

    stage_records.sort(
        key=lambda item: (
            item["graph_path"],
            item["graph_location"],
            item["stage_type"],
        )
    )
    for template_id, value in template_crosswalk.items():
        value["stage_ids"] = sorted(template_to_stage_ids[template_id])

    family_counts = Counter(item["template_family"] for item in stage_records)
    source_kinds = Counter(
        input_record["source_kind"]
        for item in stage_records
        for input_record in item["inputs"]
    )
    no_graph = sorted(
        template_id
        for template_id, value in template_crosswalk.items()
        if value["graph_reference_count"] == 0
    )
    native_handlers = native_control_handlers(root)
    referenced_stage_types = {
        item["stage_type"] for item in stage_records
    }
    missing_native_handlers = sorted(
        referenced_stage_types - set(native_handlers)
    )
    if missing_native_handlers:
        raise DeepSeekStageIRError(
            "native model_execplan lacks control-register handlers: "
            + ",".join(missing_native_handlers)
        )
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "deepseek_stage_to_authorized_json_crosswalk_complete",
        "inputs": {
            "configuration_corpus": _binding(root, CORPUS_PATH),
            "operator_base_info": _binding(root, BASE_INFO_PATH),
        },
        "policy": {
            "stage_type_must_exactly_match_template_id": True,
            "template_must_be_pinned_upstream_authorized": True,
            "graph_location_must_identify_exactly_one_stage": True,
            "shape_expressions_are_preserved_not_evaluated": True,
            "address_instance_does_not_authorize_derived_semantics": True,
            "resnet_reuse_requires_exact_or_structural_delta_classification": True,
        },
        "summary": {
            "deepseek_template_count": len(templates),
            "graph_referenced_template_count": len(templates) - len(no_graph),
            "template_without_graph_count": len(no_graph),
            "unique_graph_count": len(graph_bindings),
            "stage_occurrence_count": len(stage_records),
            "unique_stage_type_count": len(
                {item["stage_type"] for item in stage_records}
            ),
            "stage_family_counts": dict(sorted(family_counts.items())),
            "source_kind_counts": dict(sorted(source_kinds.items())),
            "operator_base_info_template_count": sum(
                value["operator_base_info"] is not None
                for value in template_crosswalk.values()
            ),
            "server_package_instance_count": sum(
                len(value["server_package_instances"])
                for value in template_crosswalk.values()
            ),
            "address_bound_instance_count": sum(
                value["reverse_reproduction"][
                    "address_bound_instance_count"
                ]
                for value in template_crosswalk.values()
            ),
        },
        "templates_without_graph": no_graph,
        "graphs": [
            graph_bindings[path] for path in sorted(graph_bindings)
        ],
        "template_crosswalk": {
            key: template_crosswalk[key]
            for key in sorted(template_crosswalk)
        },
        "stage_records": stage_records,
    }
    payload["crosswalk_sha256"] = sha256_bytes(canonical_json_bytes(payload))
    return payload


def validate_deepseek_stage_ir(
    value: Mapping[str, Any], project_root: Path
) -> None:
    if value != build_deepseek_stage_ir(project_root):
        raise DeepSeekStageIRError(
            "DeepSeek stage IR crosswalk differs from current evidence"
        )


def write_deepseek_stage_ir(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "SCHEMA",
    "DeepSeekStageIRError",
    "build_deepseek_stage_ir",
    "validate_deepseek_stage_ir",
    "write_deepseek_stage_ir",
]
