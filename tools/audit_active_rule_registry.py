#!/usr/bin/env python3
"""Fail-closed audit for the small, orthogonal active-rule surface."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


RULE_ID = re.compile(r"CDA-[A-Z0-9][A-Z0-9_-]+")
RULE_DEFINITION = re.compile(
    r"^(?:规则 ID：\s*`(?P<plain>CDA-[A-Z0-9][A-Z0-9_-]+)`|"
    r"#{2,4}\s+`?(?P<head>CDA-[A-Z0-9][A-Z0-9_-]+)`?(?:\s|$))"
)
VERSION_RESULT = re.compile(
    r"(?:^|\n)(?:当前裁决：|当前状态：)|"
    r"CDA-[A-Z0-9_-]*(?:V[0-9]+|DYNAMIC-PASS)[A-Z0-9_-]*|"
    r"return ZIP 为|PACKAGE_READY_NOT_RUN\s*/\s*V[0-9]+"
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--registry", type=Path, default=Path("contracts/active_rule_registry_v1.json")
    )
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def validate_shape(registry: Any, errors: list[str]) -> None:
    if not isinstance(registry, dict):
        errors.append("registry must be an object")
        return
    if registry.get("schema_id") != "active-rule-registry-v1":
        errors.append("schema_id mismatch")
    if registry.get("version") != 1:
        errors.append("version must be 1")
    if registry.get("active_rule_root") != ".agents/rules":
        errors.append("active_rule_root must be .agents/rules")
    entries = registry.get("exact_active_rules")
    if not isinstance(entries, list) or not entries:
        errors.append("exact_active_rules must be a non-empty array")
    history = registry.get("history")
    if not isinstance(history, dict) or history.get("default_read") is not False:
        errors.append("history.default_read must be false")


def main() -> int:
    args = parse_args()
    root = args.repo_root.resolve()
    registry_path = args.registry
    if not registry_path.is_absolute():
        registry_path = root / registry_path
    errors: list[str] = []
    warnings: list[str] = []

    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception as exc:  # fail closed with a machine-readable report
        registry = {}
        errors.append(f"registry unreadable: {exc}")
    validate_shape(registry, errors)

    entries = registry.get("exact_active_rules", []) if isinstance(registry, dict) else []
    registered_paths = [item.get("path") for item in entries if isinstance(item, dict)]
    if len(registered_paths) != len(set(registered_paths)):
        errors.append("duplicate active rule path in registry")

    active_root = root / ".agents/rules"
    actual_paths = sorted(rel(path, root) for path in active_root.glob("*.md"))
    expected_paths = sorted(path for path in registered_paths if isinstance(path, str))
    if actual_paths != expected_paths:
        errors.append(
            "active rule exact-set mismatch: "
            f"missing={sorted(set(expected_paths) - set(actual_paths))}, "
            f"unexpected={sorted(set(actual_paths) - set(expected_paths))}"
        )

    invariants = registry.get("invariants", {}) if isinstance(registry, dict) else {}
    expected_count = invariants.get("exact_active_rule_count")
    if expected_count != len(expected_paths) or len(actual_paths) != expected_count:
        errors.append(
            f"active rule count mismatch: declared={expected_count}, "
            f"registered={len(expected_paths)}, actual={len(actual_paths)}"
        )

    definitions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    texts: dict[str, str] = {}
    layers: dict[str, str] = {}
    receipt_rows: list[dict[str, Any]] = []
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            errors.append("invalid active-rule entry")
            continue
        path_text = item["path"]
        layers[path_text] = item.get("layer", "")
        path = root / path_text
        if not path.is_file():
            errors.append(f"registered rule absent: {path_text}")
            continue
        actual_sha = sha256(path)
        actual_bytes = path.stat().st_size
        if item.get("sha256") != actual_sha:
            errors.append(
                f"rule SHA mismatch: {path_text}: declared={item.get('sha256')} actual={actual_sha}"
            )
        if item.get("bytes") != actual_bytes:
            errors.append(
                f"rule byte mismatch: {path_text}: declared={item.get('bytes')} actual={actual_bytes}"
            )
        text = path.read_text(encoding="utf-8")
        texts[path_text] = text
        for line_no, line in enumerate(text.splitlines(), 1):
            match = RULE_DEFINITION.match(line)
            if match:
                rule_id = match.group("plain") or match.group("head")
                definitions[rule_id].append({"path": path_text, "line": line_no})
        receipt_rows.append(
            {"path": path_text, "bytes": actual_bytes, "sha256": actual_sha, "layer": item.get("layer")}
        )

    duplicates = {key: value for key, value in definitions.items() if len(value) != 1}
    for rule_id, locations in sorted(duplicates.items()):
        errors.append(f"rule definition owner is not unique: {rule_id}: {locations}")

    router = registry.get("entrypoints", {}).get("router") if isinstance(registry, dict) else None
    if isinstance(router, str):
        router_defs = [rule_id for rule_id, locs in definitions.items() if locs[0]["path"] == router]
        if router_defs:
            errors.append(f"router defines semantic rules: {router_defs}")

    history = registry.get("history", {}) if isinstance(registry, dict) else {}
    archived_names = history.get("archived_active_basenames", []) if isinstance(history, dict) else []
    for path_text, text in texts.items():
        for name in archived_names:
            if name in text:
                errors.append(f"active rule references archived filename: {path_text}: {name}")

    for path_text, text in texts.items():
        if layers.get(path_text) in {"primitive", "family"} and VERSION_RESULT.search(text):
            errors.append(f"version/current result leaked into stable {layers[path_text]} rule: {path_text}")

    entrypoints = registry.get("entrypoints", {}) if isinstance(registry, dict) else {}
    entrypoint_receipts: dict[str, dict[str, Any]] = {}
    for key in ("stable_entry", "current_state", "router", "history_entry"):
        value = entrypoints.get(key) if isinstance(entrypoints, dict) else None
        if not isinstance(value, str) or not (root / value).is_file():
            errors.append(f"entrypoint absent or invalid: {key}={value!r}")
        else:
            entrypoint_receipts[key] = {
                "path": value,
                "bytes": (root / value).stat().st_size,
                "sha256": sha256(root / value),
            }
    if entrypoints.get("stable_entry") in expected_paths or entrypoints.get("current_state") in expected_paths:
        errors.append("agent.md/plan.md must not be stored in active rule exact-set")

    history_root = root / history.get("root", ".agents/history/rules") if isinstance(history, dict) else root
    for name in archived_names:
        matches = list(history_root.rglob(name)) if history_root.is_dir() else []
        if not matches:
            errors.append(f"archived rule missing from history: {name}")
        if (active_root / name).exists():
            errors.append(f"archived rule still active: {name}")

    report = {
        "schema_id": "active-rule-registry-audit-v1",
        "pass": not errors,
        "registry": rel(registry_path, root),
        "registry_sha256": sha256(registry_path) if registry_path.is_file() else None,
        "active_rule_count": len(actual_paths),
        "registered_rule_count": len(expected_paths),
        "rule_definition_count": len(definitions),
        "duplicate_definition_count": len(duplicates),
        "layer_counts": {
            layer: sum(1 for item in entries if isinstance(item, dict) and item.get("layer") == layer)
            for layer in ("router", "core", "primitive", "family", "specialist")
        },
        "archived_active_rule_count": len(archived_names),
        "history_markdown_count": (
            len(list(history_root.rglob("*.md"))) if history_root.is_dir() else 0
        ),
        "entrypoint_receipts": entrypoint_receipts,
        "receipts": receipt_rows,
        "errors": errors,
        "warnings": warnings,
        "claim_boundary": (
            "active rule inventory/identity/definition ownership/history exclusion only; "
            "does not validate operator math, package runtime, RTL, E4 or E5"
        ),
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        output = args.report if args.report.is_absolute() else root / args.report
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
