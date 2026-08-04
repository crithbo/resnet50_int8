from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file
from .operator_config_validator import OperatorConfigValidator
from .strict_config_materialization import validate_materialized_strict_config


SCHEMA = "operator-config-address-bound-materialization-v1"


class AddressBoundConfigError(ValueError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AddressBoundConfigError(f"JSON root must be an object: {path}")
    return value


def _graph_addresses(graph: Mapping[str, Any]) -> dict[str, str | int]:
    operators = graph.get("operators")
    if not isinstance(operators, list) or len(operators) != 1 or not isinstance(operators[0], Mapping):
        raise AddressBoundConfigError("address binding currently requires one graph operator")
    operator = operators[0]
    inputs = operator.get("inputs")
    output = operator.get("output")
    if not isinstance(inputs, Mapping) or not isinstance(output, Mapping):
        raise AddressBoundConfigError("graph input/output mappings are missing")
    tensors = {**inputs, "D": output}
    result: dict[str, str | int] = {}
    for name, tensor in tensors.items():
        if name not in {"A", "B", "B'", "C", "D"} or not isinstance(tensor, Mapping):
            raise AddressBoundConfigError(f"unsupported graph tensor for address binding: {name}")
        address = tensor.get("base_addr")
        if isinstance(address, bool) or not isinstance(address, (str, int)):
            raise AddressBoundConfigError(f"graph tensor {name} has no base_addr")
        try:
            parsed = int(address.replace("_", ""), 0) if isinstance(address, str) else address
        except ValueError as error:
            raise AddressBoundConfigError(f"invalid graph base_addr for {name}: {address!r}") from error
        if parsed < 0 or parsed >= (1 << 30):
            raise AddressBoundConfigError(f"graph base_addr for {name} is outside 30 bits")
        # Native output_writer serializes patched stream bases with lowercase
        # hexadecimal.  Preserve that canonical spelling because the strict
        # pipeline provenance check is intentionally byte-for-byte.
        result[name] = f"0x{parsed:x}"
    return result


def bind_config_addresses(
    config: Mapping[str, Any], graph: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = deepcopy(dict(config))
    addresses = _graph_addresses(graph)
    streams = result.get("stream_engine")
    if not isinstance(streams, dict):
        raise AddressBoundConfigError("config stream_engine is missing")
    seen: set[str] = set()
    changes: list[dict[str, Any]] = []
    for stream_name, stream in streams.items():
        if not isinstance(stream, dict):
            raise AddressBoundConfigError(f"stream {stream_name} is not an object")
        target = stream.get("target")
        if target not in addresses:
            raise AddressBoundConfigError(f"stream {stream_name} target is not in graph: {target!r}")
        if target in seen:
            raise AddressBoundConfigError(f"multiple streams bind graph target {target}")
        seen.add(str(target))
        before = stream.get("base_addr")
        after = addresses[str(target)]
        stream["base_addr"] = after
        if before != after:
            changes.append(
                {
                    "path": f"$.stream_engine.{stream_name}.base_addr",
                    "target": target,
                    "before": before,
                    "after": after,
                }
            )
    if seen != set(addresses):
        raise AddressBoundConfigError(
            f"config streams do not exactly cover graph tensors: streams={sorted(seen)}, graph={sorted(addresses)}"
        )
    return result, changes


def materialize_address_bound_config(
    *,
    project_root: Path,
    strict_materialization_root: Path,
    graph_withbaseaddr: Path,
    output_root: Path,
) -> dict[str, Any]:
    root = project_root.resolve()
    strict_root = strict_materialization_root.resolve()
    graph_path = graph_withbaseaddr.resolve()
    output = output_root.resolve()
    if output.exists():
        raise AddressBoundConfigError(f"output must be a fresh path: {output}")
    strict_manifest = validate_materialized_strict_config(strict_root)
    strict_config_path = strict_root / "config.json"
    strict_config = _load(strict_config_path)
    graph = _load(graph_path)
    bound, changes = bind_config_addresses(strict_config, graph)
    if not changes:
        raise AddressBoundConfigError("graph does not change any config base address")
    report = OperatorConfigValidator().validate(bound, source=str(graph_path))
    if not report.valid:
        first = report.issues[0]
        raise AddressBoundConfigError(
            f"address-bound config is invalid: {first.code} at {first.path}"
        )

    output.mkdir(parents=True)
    config_path = output / "config.json"
    config_path.write_text(
        json.dumps(bound, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "strict_config_bound_to_planner_addresses",
        "source": {
            "artifact": str(strict_config_path.relative_to(root)).replace("\\", "/"),
            "sha256": sha256_file(strict_config_path),
            "materialization_manifest_sha256": sha256_file(strict_root / "manifest.json"),
            "strict_normalization_decision": strict_manifest["adjudication"]["normalization_decision"],
        },
        "graph_withbaseaddr": {
            "artifact": str(graph_path.relative_to(root)).replace("\\", "/"),
            "sha256": sha256_file(graph_path),
        },
        "bound_config": {
            "artifact": "config.json",
            "sha256": sha256_file(config_path),
            "canonical_sha256": sha256_bytes(canonical_json_bytes(bound)),
        },
        "changes": changes,
        "change_set_sha256": sha256_bytes(canonical_json_bytes(changes)),
        "strict_validation": {"valid": True, "issue_count": 0},
        "source_rewrite_performed": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    validate_address_bound_config(output, project_root=root)
    return manifest


def validate_address_bound_config(output_root: Path, *, project_root: Path) -> dict[str, Any]:
    output = output_root.resolve()
    root = project_root.resolve()
    manifest = _load(output / "manifest.json")
    config = _load(output / "config.json")
    if manifest.get("schema") != SCHEMA or manifest.get("status") != "strict_config_bound_to_planner_addresses":
        raise AddressBoundConfigError("address-bound materialization identity differs")
    source = manifest.get("source")
    graph_item = manifest.get("graph_withbaseaddr")
    bound_item = manifest.get("bound_config")
    if not all(isinstance(item, Mapping) for item in (source, graph_item, bound_item)):
        raise AddressBoundConfigError("address-bound manifest bindings are missing")
    source_path = root / str(source["artifact"])
    graph_path = root / str(graph_item["artifact"])
    if (
        not source_path.is_file()
        or source.get("sha256") != sha256_file(source_path)
        or source.get("materialization_manifest_sha256")
        != sha256_file(source_path.parent / "manifest.json")
        or not graph_path.is_file()
        or graph_item.get("sha256") != sha256_file(graph_path)
        or bound_item.get("artifact") != "config.json"
        or bound_item.get("sha256") != sha256_file(output / "config.json")
        or bound_item.get("canonical_sha256") != sha256_bytes(canonical_json_bytes(config))
    ):
        raise AddressBoundConfigError("address-bound artifact hash differs")
    expected, changes = bind_config_addresses(_load(source_path), _load(graph_path))
    if config != expected or manifest.get("changes") != changes:
        raise AddressBoundConfigError("address-bound config content differs")
    if manifest.get("change_set_sha256") != sha256_bytes(canonical_json_bytes(changes)):
        raise AddressBoundConfigError("address-bound change set hash differs")
    report = OperatorConfigValidator().validate(config, source=str(output / "config.json"))
    if not report.valid or manifest.get("source_rewrite_performed") is not False:
        raise AddressBoundConfigError("address-bound strict validation differs")
    return manifest


__all__ = [
    "AddressBoundConfigError",
    "bind_config_addresses",
    "materialize_address_bound_config",
    "validate_address_bound_config",
]
