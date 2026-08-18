#!/usr/bin/env python3
"""Fail-closed gate for persistent-family dispatch and package diagnostic mode."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from tools.validate_server_diagnostic_mode_selector import validate_selector
except ModuleNotFoundError:  # direct script execution places tools/ on sys.path
    from validate_server_diagnostic_mode_selector import validate_selector


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "server_family_dispatch_mode_binding_v1.schema.json"
SCHEMA = "server-family-dispatch-mode-binding-v1"
MODES = {"OBSERVER_ONLY_WIDE_CAUSAL", "TB_VCD_BOUNDED_CAUSAL_CONE"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json_bytes(data: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"{label} is not valid UTF-8 JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def load_json(path: Path) -> dict[str, Any]:
    return load_json_bytes(path.read_bytes(), path.as_posix())


def _safe_repo_path(repo_root: Path, relative: str, label: str) -> Path:
    candidate = PurePosixPath(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"{label} must be a safe repository-relative path")
    root = repo_root.resolve()
    resolved = (root / Path(*candidate.parts)).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes repository root") from exc
    return resolved


def _schema_errors(binding: dict[str, Any]) -> list[str]:
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema dependency is required; binding schema validation may not be skipped"]
    schema = load_json(SCHEMA_PATH)
    validator = jsonschema.Draft202012Validator(schema)
    errors: list[str] = []
    for item in sorted(validator.iter_errors(binding), key=lambda error: list(error.path)):
        where = "/".join(str(part) for part in item.path) or "$"
        errors.append(f"schema:{where}: {item.message}")
    return errors


def _active_role(registry: dict[str, Any], role_id: str) -> tuple[dict[str, Any] | None, list[str]]:
    rows = [
        row for row in registry.get("roles", [])
        if isinstance(row, dict) and row.get("role_id") == role_id and row.get("status") == "ACTIVE"
    ]
    if len(rows) != 1:
        return None, [f"registry must contain exactly one ACTIVE {role_id} row; found {len(rows)}"]
    return rows[0], []


def validate_binding(binding: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    errors = _schema_errors(binding)
    if binding.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")
    if errors:
        return {"pass": False, "errors": errors, "diagnostic_mode": binding.get("diagnostic_mode")}

    owner = binding["owner_binding"]
    authority = binding["mode_authority"]
    try:
        registry_path = _safe_repo_path(repo_root, owner["registry_path"], "owner registry")
        authority_path = _safe_repo_path(repo_root, authority["path"], "mode authority")
        authority_source_path = _safe_repo_path(repo_root, authority["source_path"], "mode authority source")
        dispatch_path = _safe_repo_path(repo_root, authority["selector_dispatch_path"], "selector dispatch")
    except ValueError as exc:
        errors.append(str(exc))
        return {"pass": False, "errors": errors, "diagnostic_mode": binding.get("diagnostic_mode")}

    for path, expected, label in (
        (registry_path, owner["registry_sha256"], "owner registry"),
        (authority_path, authority["sha256"], "mode authority"),
        (authority_source_path, authority["source_sha256"], "mode authority source"),
        (dispatch_path, authority["selector_dispatch_sha256"], "selector dispatch"),
    ):
        if not path.is_file():
            errors.append(f"{label} is absent: {path}")
        elif sha256_file(path) != expected:
            errors.append(f"{label} SHA256 differs from dispatch binding")

    authority_receipt: dict[str, Any] = {}
    if authority_path.is_file():
        try:
            authority_receipt = load_json(authority_path)
        except Exception as exc:
            errors.append(f"mode authority receipt unreadable: {exc}")
    if authority_receipt:
        expected_authority = {
            "schema": "server-family-diagnostic-mode-authority-v1",
            "effective_scope": "NEXT_FRESH_AFTER_ACTIVATION",
            "package_id": binding["package_id"],
            "family_role_id": binding["family_role_id"],
            "diagnostic_mode": binding["diagnostic_mode"],
        }
        for field, expected in expected_authority.items():
            if authority_receipt.get(field) != expected:
                errors.append(f"mode authority receipt {field} differs from dispatch binding")
        source = authority_receipt.get("source")
        if not isinstance(source, dict):
            errors.append("mode authority receipt source must be an object")
        else:
            if source.get("kind") != authority["kind"]:
                errors.append("mode authority receipt source kind differs from dispatch binding")
            if source.get("path") != authority["source_path"]:
                errors.append("mode authority receipt source path differs from dispatch binding")
            if source.get("sha256") != authority["source_sha256"]:
                errors.append("mode authority receipt source SHA256 differs from dispatch binding")

    registry: dict[str, Any] = {}
    if registry_path.is_file():
        try:
            registry = load_json(registry_path)
        except Exception as exc:
            errors.append(f"owner registry unreadable: {exc}")
    if registry:
        if registry.get("registry_epoch") != owner["registry_epoch"]:
            errors.append("owner registry epoch differs from dispatch binding")
        family_row, family_errors = _active_role(registry, binding["family_role_id"])
        errors.extend(family_errors)
        if family_row:
            if family_row.get("thread_id") != owner["owner_thread_id"]:
                errors.append("family owner thread differs from current ACTIVE registry row")
            if family_row.get("owner_epoch") != owner["owner_epoch"]:
                errors.append("family owner epoch differs from current ACTIVE registry row")
        mainline_row, mainline_errors = _active_role(registry, "mainline.control")
        errors.extend(mainline_errors)
        if mainline_row and mainline_row.get("thread_id") != binding["issued_by"]["thread_id"]:
            errors.append("issuing mainline thread differs from current ACTIVE registry row")

    if owner.get("dispatch_mechanism") != "PERSISTENT_REGISTERED_THREAD":
        errors.append("registered family work must use PERSISTENT_REGISTERED_THREAD")
    if owner.get("temporary_subagent_role_substitution") is not False:
        errors.append("temporary subagent may not substitute for a registered family role")
    if binding.get("diagnostic_mode") not in MODES:
        errors.append("diagnostic mode is unsupported")

    return {
        "schema": "server-family-dispatch-mode-binding-validation-v1",
        "pass": not errors,
        "family_role_id": binding.get("family_role_id"),
        "owner_thread_id": owner.get("owner_thread_id"),
        "dispatch_mechanism": owner.get("dispatch_mechanism"),
        "diagnostic_mode": binding.get("diagnostic_mode"),
        "errors": errors,
        "claim_boundary": "Local dispatch/owner/mode identity only; no package runtime or server claim.",
    }


def _validate_package_documents(
    binding: dict[str, Any], expected_binding_bytes: bytes, binding_bytes: bytes,
    selector_bytes: bytes, manifest_bytes: bytes,
) -> list[str]:
    errors: list[str] = []
    try:
        packaged_binding = load_json_bytes(binding_bytes, "packaged dispatch binding")
        selector = load_json_bytes(selector_bytes, "packaged diagnostic selector")
        manifest = load_json_bytes(manifest_bytes, "package manifest")
    except ValueError as exc:
        return [str(exc)]

    if binding_bytes != expected_binding_bytes:
        errors.append("packaged dispatch binding is not byte-equal to dispatched binding")
    if packaged_binding != binding:
        errors.append("packaged dispatch binding semantic content differs")

    selector_report = validate_selector(selector)
    errors.extend(f"selector:{item}" for item in selector_report["errors"])
    mode = binding["diagnostic_mode"]
    if selector.get("selected_mode") != mode:
        errors.append("selector diagnostic mode differs from dispatched mode")
    if selector.get("package_id") != binding["package_id"]:
        errors.append("selector package identity differs from dispatch binding")
    expected_family = binding["family_role_id"].split("family.", 1)[-1]
    if selector.get("family") not in {binding["family_role_id"], expected_family}:
        errors.append("selector family differs from dispatch binding")
    if manifest.get("diagnostic_mode") != mode:
        errors.append("manifest diagnostic mode differs from dispatched mode")
    if manifest.get("package_id") != binding["package_id"]:
        errors.append("manifest package identity differs from dispatch binding")
    return errors


def validate_package_tree(binding_path: Path, repo_root: Path, package_root: Path) -> dict[str, Any]:
    binding = load_json(binding_path)
    expected_binding_bytes = binding_path.read_bytes()
    report = validate_binding(binding, repo_root)
    errors = list(report["errors"])
    contract = binding.get("package_contract", {})
    paths = {
        "binding": package_root / contract.get("binding_member", "__missing__"),
        "selector": package_root / contract.get("selector_member", "__missing__"),
        "manifest": package_root / contract.get("manifest_member", "__missing__"),
    }
    for label, path in paths.items():
        if not path.is_file():
            errors.append(f"package {label} member is absent: {path}")
    if all(path.is_file() for path in paths.values()):
        errors.extend(_validate_package_documents(
            binding, expected_binding_bytes, paths["binding"].read_bytes(),
            paths["selector"].read_bytes(), paths["manifest"].read_bytes()
        ))
    report.update({"pass": not errors, "errors": errors, "package_root": package_root.as_posix()})
    return report


def validate_final_zip(binding_path: Path, repo_root: Path, zip_path: Path) -> dict[str, Any]:
    binding = load_json(binding_path)
    expected_binding_bytes = binding_path.read_bytes()
    report = validate_binding(binding, repo_root)
    errors = list(report["errors"])
    contract = binding.get("package_contract", {})
    try:
        with zipfile.ZipFile(zip_path) as archive:
            files = [info.filename for info in archive.infolist() if not info.is_dir()]
            for name in files:
                pure = PurePosixPath(name)
                if pure.is_absolute() or ".." in pure.parts:
                    errors.append(f"unsafe ZIP member: {name}")
            roots = {PurePosixPath(name).parts[0] for name in files if PurePosixPath(name).parts}
            if len(roots) != 1:
                errors.append(f"final ZIP must contain one package root; found {sorted(roots)}")
            if len(roots) == 1:
                root = next(iter(roots))
                names = {
                    key: f"{root}/{contract.get(field, '__missing__')}"
                    for key, field in (
                        ("binding", "binding_member"),
                        ("selector", "selector_member"),
                        ("manifest", "manifest_member"),
                    )
                }
                for label, name in names.items():
                    if name not in files:
                        errors.append(f"final ZIP {label} member is absent: {name}")
                if all(name in files for name in names.values()):
                    errors.extend(_validate_package_documents(
                        binding, expected_binding_bytes, archive.read(names["binding"]),
                        archive.read(names["selector"]), archive.read(names["manifest"])
                    ))
    except Exception as exc:
        errors.append(f"final ZIP unreadable: {exc}")
    report.update({
        "pass": not errors,
        "errors": errors,
        "final_zip": zip_path.as_posix(),
        "final_zip_sha256": sha256_file(zip_path) if zip_path.is_file() else None,
    })
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--package-root", type=Path)
    group.add_argument("--zip", type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = (
            validate_package_tree(args.binding, args.repo_root, args.package_root)
            if args.package_root else validate_final_zip(args.binding, args.repo_root, args.zip)
        )
    except Exception as exc:
        report = {
            "schema": "server-family-dispatch-mode-binding-validation-v1",
            "pass": False,
            "errors": [f"validation input unreadable: {exc}"],
        }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
