#!/usr/bin/env python3
"""Validate final package release admission from staging and exact ZIP bytes.

This is a local, family-agnostic companion to the existing final-ZIP and
first-fresh gates.  It executes only the package-declared Python preflight;
it does not probe server files, invoke production compilation, build a ZIP,
rotate storage, or perform a server action.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.metadata
import json
import os
import py_compile
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


SCHEMA = "server-package-release-admission-v1"
READY = "PACKAGE_READY_NOT_RUN"
PENDING = "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES"
MARKER = "package claim boundary differs"
HEX64 = set("0123456789abcdef")
CONTRACT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[1]
    / "schemas/server_package_release_admission_v1.schema.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in HEX64 for ch in value)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")


def resolve_workspace(path_value: Any, workspace: Path, kind: str) -> Path:
    if not isinstance(path_value, str) or not path_value:
        raise ValueError(f"{kind} path must be a non-empty relative string")
    candidate = (workspace / path_value).resolve()
    candidate.relative_to(workspace.resolve())
    return candidate


def json_pointer(value: Any, pointer: str) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise KeyError(pointer)
    current = value
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current[token]
        elif isinstance(current, list):
            current = current[int(token)]
        else:
            raise KeyError(pointer)
    return current


def set_json_pointer(value: Any, pointer: str, replacement: Any) -> None:
    tokens = pointer.split("/")[1:]
    current = value
    for raw in tokens[:-1]:
        token = raw.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    last = tokens[-1].replace("~1", "/").replace("~0", "~")
    if isinstance(current, list):
        current[int(last)] = replacement
    else:
        current[last] = replacement


def tree_snapshot(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        result[relative] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
    return result


def python_source_snapshot(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(
        item for item in root.rglob("*")
        if item.is_file() and item.suffix.lower() == ".py"
    ):
        relative = path.relative_to(root).as_posix()
        result[relative] = {
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    return result


def validate_schema_runtime(
    contract: dict[str, Any], errors: list[str]
) -> dict[str, Any]:
    control: dict[str, Any] = {
        "runtime_executable": sys.executable,
        "dependency": "jsonschema",
        "dependency_available": False,
        "dependency_version": None,
        "schema_path": str(CONTRACT_SCHEMA_PATH),
        "schema_sha256": (
            sha256_file(CONTRACT_SCHEMA_PATH)
            if CONTRACT_SCHEMA_PATH.is_file()
            else None
        ),
        "schema_validation_performed": False,
        "schema_validation_pass": False,
        "skip_allowed": False,
    }
    try:
        jsonschema = importlib.import_module("jsonschema")
    except (ImportError, ModuleNotFoundError) as exc:
        errors.append(
            "schema-enabled gate dependency unavailable: jsonschema; "
            "fail closed (skip/pass is forbidden)"
        )
        control["error"] = str(exc)
        return control

    control["dependency_available"] = True
    try:
        control["dependency_version"] = importlib.metadata.version("jsonschema")
    except importlib.metadata.PackageNotFoundError:
        control["dependency_version"] = "UNKNOWN"
    try:
        schema = load_json(CONTRACT_SCHEMA_PATH)
        validator = jsonschema.Draft202012Validator(schema)
        schema_errors = sorted(
            validator.iter_errors(contract),
            key=lambda item: tuple(str(value) for value in item.absolute_path),
        )
        control["schema_validation_performed"] = True
        if schema_errors:
            for item in schema_errors:
                location = "/" + "/".join(
                    str(value) for value in item.absolute_path
                )
                errors.append(
                    f"release-admission contract JSON schema violation at "
                    f"{location}: {item.message}"
                )
        else:
            control["schema_validation_pass"] = True
    except Exception as exc:
        errors.append(
            "release-admission JSON schema could not be executed; "
            f"fail closed: {exc}"
        )
        control["error"] = str(exc)
    return control


def compile_python_exact_set(
    package_root: Path, bytecode_root: Path
) -> dict[str, Any]:
    before = tree_snapshot(package_root)
    sources = python_source_snapshot(package_root)
    records: list[dict[str, Any]] = []
    compile_errors: list[str] = []
    bytecode_root.mkdir(parents=True, exist_ok=True)
    for index, (relative, identity) in enumerate(sources.items()):
        source = package_root / PurePosixPath(relative)
        bytecode = bytecode_root / f"{index:06d}.pyc"
        error: str | None = None
        try:
            py_compile.compile(
                str(source),
                cfile=str(bytecode),
                doraise=True,
            )
        except (OSError, py_compile.PyCompileError) as exc:
            error = str(exc)
            compile_errors.append(f"{relative}: {error}")
        records.append(
            {
                "path": relative,
                **identity,
                "compiled": error is None,
                "error": error,
            }
        )
    after = tree_snapshot(package_root)
    return {
        "python_member_count": len(sources),
        "compiled_count": sum(1 for item in records if item["compiled"]),
        "members": records,
        "errors": compile_errors,
        "package_tree_unchanged": before == after,
        "bytecode_written_inside_package": before != after,
        "pass": not compile_errors and before == after,
    }


def safe_extract(source: Path, destination: Path, expected_root: str) -> Path:
    with zipfile.ZipFile(source) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if not names or len(names) != len(set(names)):
            raise ValueError("exact final ZIP is empty or has duplicate members")
        if archive.testzip() is not None:
            raise ValueError("exact final ZIP CRC failed")
        roots: set[str] = set()
        for info in infos:
            name = info.filename
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or "\\" in name:
                raise ValueError(f"unsafe ZIP member: {name}")
            if pure.parts:
                roots.add(pure.parts[0])
            unix_mode = (info.external_attr >> 16) & 0o170000
            if unix_mode == 0o120000:
                raise ValueError(f"ZIP symlink member is forbidden: {name}")
        if roots != {expected_root}:
            raise ValueError(f"exact final ZIP root differs: {sorted(roots)}")
        archive.extractall(destination)
    extracted = destination / expected_root
    if not extracted.is_dir():
        raise ValueError("exact final ZIP package root is absent")
    return extracted


def run_preflight(package_root: Path, runtime_member: str, timeout: int) -> dict[str, Any]:
    runtime = (package_root / runtime_member).resolve()
    runtime.relative_to(package_root.resolve())
    if not runtime.is_file():
        raise ValueError(f"runtime preflight member is absent: {runtime_member}")
    command = [sys.executable, "-B", str(runtime), "preflight", "--package-root", str(package_root)]
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    before = tree_snapshot(package_root)
    try:
        completed = subprocess.run(
            command, cwd=package_root, env=environment, text=True,
            capture_output=True, timeout=timeout, check=False,
        )
        exit_code: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        exit_code = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        timed_out = True
    after = tree_snapshot(package_root)
    return {
        "command": command,
        "cwd": str(package_root),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "stdout": stdout,
        "stdout_bytes": len(stdout.encode("utf-8")),
        "stdout_sha256": sha256_text(stdout),
        "stderr": stderr,
        "stderr_bytes": len(stderr.encode("utf-8")),
        "stderr_sha256": sha256_text(stderr),
        "tree_unchanged": before == after,
    }


def validate_failure_core(
    receipt: dict[str, Any], package_id: str, zip_sha: str, runner_sha: str
) -> list[str]:
    errors: list[str] = []
    if receipt.get("schema") != "server-precompile-preflight-failure-core-v1":
        errors.append("precompile failure core schema mismatch")
    if receipt.get("package_id") != package_id:
        errors.append("precompile failure core package identity mismatch")
    if receipt.get("final_zip_sha256") != zip_sha:
        errors.append("precompile failure core final ZIP identity mismatch")
    if receipt.get("runner_member_sha256") != runner_sha:
        errors.append("precompile failure core runner identity mismatch")
    preflight = receipt.get("preflight") if isinstance(receipt.get("preflight"), dict) else {}
    if not isinstance(preflight.get("exit_code"), int) or isinstance(preflight.get("exit_code"), bool) or preflight.get("exit_code") == 0:
        errors.append("precompile failure core lacks a nonzero preflight exit code")
    for field in ("stdout", "stderr"):
        if field not in preflight or not isinstance(preflight.get(field), str):
            errors.append(f"precompile failure core does not retain preflight {field}")
    if receipt.get("compile_started") is not False or receipt.get("simulation_started") is not False:
        errors.append("precompile failure must remain compile-not-started and simulation-not-started")
    core = receipt.get("core_return") if isinstance(receipt.get("core_return"), dict) else {}
    if core.get("published") is not True or core.get("classification") != "COMPILE_NOT_STARTED":
        errors.append("compile-not-started core was not published")
    required = {"preflight_stdout", "preflight_stderr", "preflight_exit", "compile_not_started"}
    evidence = core.get("required_evidence") if isinstance(core.get("required_evidence"), list) else []
    if set(evidence) != required:
        errors.append("compile-not-started core evidence exact-set differs")
    if not isinstance(receipt.get("claim_boundary"), str) or not receipt.get("claim_boundary"):
        errors.append("precompile failure core claim boundary is absent")
    return errors


def validate_contract(contract: dict[str, Any], workspace: Path) -> dict[str, Any]:
    errors: list[str] = []
    checks: dict[str, bool] = {}
    controls: dict[str, Any] = {}
    if contract.get("schema") != SCHEMA:
        errors.append(f"schema must be {SCHEMA}")

    schema_runtime = validate_schema_runtime(contract, errors)
    controls["schema_runtime"] = schema_runtime
    checks["schema_runtime_available"] = bool(
        schema_runtime.get("dependency_available") is True
    )
    checks["contract_schema_valid"] = bool(
        schema_runtime.get("schema_validation_performed") is True
        and schema_runtime.get("schema_validation_pass") is True
    )

    python_schema_spec = (
        contract.get("python_schema_runtime")
        if isinstance(contract.get("python_schema_runtime"), dict)
        else {}
    )
    expected_python_schema_spec = {
        "package_python_source_suffixes": [".py"],
        "exact_set_compile": True,
        "compile_staging_and_clean_exact_zip": True,
        "bytecode_destination": "OUTSIDE_PACKAGE_TEMPORARY_DIRECTORY",
        "schema_validation_enabled": True,
        "schema_dependency": "jsonschema",
        "missing_dependency_disposition": "FAIL_CLOSED",
        "skip_allowed": False,
    }
    checks["python_schema_contract"] = (
        python_schema_spec == expected_python_schema_spec
    )
    if not checks["python_schema_contract"]:
        errors.append("package Python/schema runtime contract differs")

    package = contract.get("package") if isinstance(contract.get("package"), dict) else {}
    package_id = package.get("package_id")
    zip_root = package.get("zip_root_member")
    try:
        staging = resolve_workspace(package.get("staging_root"), workspace, "staging_root")
        package_zip = resolve_workspace((package.get("final_zip") or {}).get("path"), workspace, "final_zip")
        release_path = resolve_workspace((contract.get("release_receipt") or {}).get("path"), workspace, "release_receipt")
        failure_path = resolve_workspace((contract.get("precompile_failure_core") or {}).get("path"), workspace, "precompile_failure_core")
    except (ValueError, KeyError) as exc:
        errors.append(str(exc))
        staging = package_zip = release_path = failure_path = workspace / "__absent__"

    if not staging.is_dir():
        errors.append("final staging root is absent")
    if not package_zip.is_file():
        errors.append("exact final ZIP is absent")
    zip_sha = sha256_file(package_zip) if package_zip.is_file() else ""
    final_zip = package.get("final_zip") if isinstance(package.get("final_zip"), dict) else {}
    checks["final_zip_identity"] = bool(
        package_zip.is_file() and final_zip.get("bytes") == package_zip.stat().st_size
        and final_zip.get("sha256") == zip_sha and is_sha256(zip_sha)
    )
    if not checks["final_zip_identity"]:
        errors.append("exact final ZIP bytes/SHA differ")

    manifest_spec = contract.get("manifest") if isinstance(contract.get("manifest"), dict) else {}
    runtime_spec = contract.get("runtime_preflight") if isinstance(contract.get("runtime_preflight"), dict) else {}
    if manifest_spec.get("ready_status") != READY or manifest_spec.get("nonfinal_status") != PENDING:
        errors.append("manifest ready/nonfinal status vocabulary differs")
    expected_command = ["{python}", "{runtime_member}", "preflight", "--package-root", "{package_root}"]
    if runtime_spec.get("command_template") != expected_command:
        errors.append("runtime preflight command template differs")
    if runtime_spec.get("expected_exit") != 0 or runtime_spec.get("nonfinal_rejection_marker") != MARKER or runtime_spec.get("non_mutating") is not True:
        errors.append("runtime preflight exit/marker/non-mutation contract differs")
    timeout = runtime_spec.get("timeout_seconds") if isinstance(runtime_spec.get("timeout_seconds"), int) else 60
    manifest_member = manifest_spec.get("member")
    runtime_member = runtime_spec.get("runtime_member")
    runner_member = package.get("runner_member")

    tree_positive: dict[str, Any] = {}
    zip_positive: dict[str, Any] = {}
    status_negative: dict[str, Any] = {}
    tree_manifest: dict[str, Any] = {}
    zip_manifest: dict[str, Any] = {}
    extracted_snapshot: dict[str, Any] = {}
    staging_python: dict[str, Any] = {}
    zip_python: dict[str, Any] = {}
    staging_python_compile: dict[str, Any] = {}
    zip_python_compile: dict[str, Any] = {}
    try:
        tree_manifest = load_json(staging / str(manifest_member))
        tree_positive = run_preflight(staging, str(runtime_member), timeout)
        with tempfile.TemporaryDirectory(prefix="release-admission-") as raw:
            audit_root = Path(raw)
            positive_root = safe_extract(package_zip, Path(raw) / "positive", str(zip_root))
            zip_manifest = load_json(positive_root / str(manifest_member))
            extracted_snapshot = tree_snapshot(positive_root)
            staging_python = python_source_snapshot(staging)
            zip_python = python_source_snapshot(positive_root)
            staging_python_compile = compile_python_exact_set(
                staging, audit_root / "staging-bytecode"
            )
            zip_python_compile = compile_python_exact_set(
                positive_root, audit_root / "zip-bytecode"
            )
            zip_positive = run_preflight(positive_root, str(runtime_member), timeout)
            negative_root = safe_extract(package_zip, Path(raw) / "negative", str(zip_root))
            negative_manifest_path = negative_root / str(manifest_member)
            negative_manifest = load_json(negative_manifest_path)
            set_json_pointer(negative_manifest, str(manifest_spec.get("status_pointer")), PENDING)
            write_json(negative_manifest_path, negative_manifest)
            status_negative = run_preflight(negative_root, str(runtime_member), timeout)
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        errors.append(f"runtime preflight conjunction failed: {exc}")

    staging_snapshot = tree_snapshot(staging) if staging.is_dir() else {}
    checks["staging_equals_clean_exact_zip"] = bool(staging_snapshot and staging_snapshot == extracted_snapshot)
    if not checks["staging_equals_clean_exact_zip"]:
        errors.append("final staging tree and clean exact-ZIP extraction differ")

    checks["package_python_exact_set"] = staging_python == zip_python
    if not checks["package_python_exact_set"]:
        errors.append(
            "package-local Python exact-set/bytes differ between staging and clean exact ZIP"
        )
    checks["staging_package_python_compile"] = bool(
        staging_python_compile.get("pass") is True
    )
    checks["clean_zip_package_python_compile"] = bool(
        zip_python_compile.get("pass") is True
    )
    if not checks["staging_package_python_compile"]:
        errors.append("package-local Python staging exact-set py_compile failed")
        errors.extend(
            f"staging package-local Python compile: {message}"
            for message in staging_python_compile.get("errors", [])
        )
    if not checks["clean_zip_package_python_compile"]:
        errors.append("package-local Python clean exact-ZIP py_compile failed")
        errors.extend(
            f"clean exact-ZIP package-local Python compile: {message}"
            for message in zip_python_compile.get("errors", [])
        )
    controls["package_python_exact_set_compile"] = {
        "source_suffixes": [".py"],
        "staging_exact_set": staging_python,
        "clean_exact_zip_set": zip_python,
        "staging": staging_python_compile,
        "clean_exact_zip": zip_python_compile,
        "bytecode_destination": "OUTSIDE_PACKAGE_TEMPORARY_DIRECTORY",
    }

    status_pointer = str(manifest_spec.get("status_pointer", ""))
    id_pointer = str(manifest_spec.get("package_id_pointer", ""))
    try:
        tree_status = json_pointer(tree_manifest, status_pointer)
        zip_status = json_pointer(zip_manifest, status_pointer)
        tree_id = json_pointer(tree_manifest, id_pointer)
        zip_id = json_pointer(zip_manifest, id_pointer)
    except (KeyError, ValueError, IndexError) as exc:
        errors.append(f"manifest pointer resolution failed: {exc}")
        tree_status = zip_status = tree_id = zip_id = None
    checks["manifest_status_promoted"] = tree_status == READY and zip_status == READY
    if not checks["manifest_status_promoted"]:
        errors.append("package claim boundary differs: embedded manifest status is not PACKAGE_READY_NOT_RUN")
    checks["manifest_package_identity"] = tree_id == package_id and zip_id == package_id
    if not checks["manifest_package_identity"]:
        errors.append("embedded manifest package identity differs")

    checks["staging_runtime_preflight"] = bool(
        tree_positive.get("exit_code") == 0 and not tree_positive.get("timed_out") and tree_positive.get("tree_unchanged") is True
    )
    checks["clean_zip_runtime_preflight"] = bool(
        zip_positive.get("exit_code") == 0 and not zip_positive.get("timed_out") and zip_positive.get("tree_unchanged") is True
    )
    if not checks["staging_runtime_preflight"]:
        errors.append("package-specific runtime preflight failed or mutated final staging tree")
    if not checks["clean_zip_runtime_preflight"]:
        errors.append("package-specific runtime preflight failed or mutated clean exact-ZIP extraction")
    combined_negative = str(status_negative.get("stdout", "")) + str(status_negative.get("stderr", ""))
    checks["nonfinal_status_negative"] = bool(status_negative.get("exit_code") not in (None, 0) and MARKER in combined_negative)
    if not checks["nonfinal_status_negative"]:
        errors.append("nonfinal manifest status did not fail closed with package claim boundary differs")
    controls["runtime_preflight"] = {"staging": tree_positive, "clean_exact_zip": zip_positive, "nonfinal_status": status_negative}

    release_spec = contract.get("release_receipt") if isinstance(contract.get("release_receipt"), dict) else {}
    try:
        release = load_json(release_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        release = {}
        errors.append(f"release receipt unreadable: {exc}")
    checks["release_receipt_sha"] = bool(release_path.is_file() and sha256_file(release_path) == release_spec.get("sha256"))
    if not checks["release_receipt_sha"]:
        errors.append("release receipt SHA differs")
    release_expectations = (
        ("package_id_pointer", package_id, "release package identity differs"),
        ("status_pointer", READY, "release status is not PACKAGE_READY_NOT_RUN"),
        ("pass_pointer", True, "release pass is not true"),
        ("final_zip_sha256_pointer", zip_sha, "release final ZIP identity differs"),
        ("claim_boundary_pointer", release_spec.get("expected_claim_boundary"), "release claim boundary differs"),
    )
    release_ok = True
    for pointer_field, expected, message in release_expectations:
        try:
            actual = json_pointer(release, str(release_spec.get(pointer_field)))
        except (KeyError, ValueError, IndexError):
            actual = object()
        if actual != expected:
            release_ok = False
            errors.append(message)
    checks["release_receipt_exact_binding"] = release_ok

    semantics = contract.get("build_receipt_semantics") if isinstance(contract.get("build_receipt_semantics"), dict) else {}
    positive = semantics.get("positive_assertions") if isinstance(semantics.get("positive_assertions"), list) else []
    negative = semantics.get("negative_observations") if isinstance(semantics.get("negative_observations"), list) else []
    if semantics.get("aggregate_mode") != "POSITIVE_ASSERTIONS_AND_EXPECTED_POLARITY_MATCH":
        errors.append("build receipt aggregate mode differs")
    fact_ids = [item.get("fact_id") for item in positive + negative if isinstance(item, dict)]
    duplicate_fact_ids = sorted({fact_id for fact_id in fact_ids if fact_ids.count(fact_id) > 1})
    if duplicate_fact_ids:
        errors.append(f"build receipt fact IDs overlap or repeat: {duplicate_fact_ids}")
    positive_failures = [item.get("fact_id") for item in positive if not isinstance(item, dict) or item.get("required") is not True or item.get("observed") is not True]
    negative_mismatches = [item.get("fact_id") for item in negative if not isinstance(item, dict) or item.get("required") is not False or item.get("observed") is not False]
    checks["positive_assertions"] = bool(positive) and not positive_failures
    checks["negative_observation_polarity"] = bool(negative) and not negative_mismatches
    if not checks["positive_assertions"]:
        errors.append(f"positive build assertions failed: {positive_failures}")
    if not checks["negative_observation_polarity"]:
        errors.append(f"observed-negative fact polarity mismatch: {negative_mismatches}")
    controls["build_receipt_semantics"] = {
        "aggregate_mode": semantics.get("aggregate_mode"),
        "positive_assertion_count": len(positive),
        "positive_failures": positive_failures,
        "negative_observation_count": len(negative),
        "negative_mismatches": negative_mismatches,
        "naive_all_boolean_values_forbidden": True,
    }

    runner_path = staging / str(runner_member)
    runner_sha = sha256_file(runner_path) if runner_path.is_file() else ""
    try:
        failure_receipt = load_json(failure_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        failure_receipt = {}
        errors.append(f"precompile failure core unreadable: {exc}")
    failure_spec = contract.get("precompile_failure_core") if isinstance(contract.get("precompile_failure_core"), dict) else {}
    checks["precompile_failure_core_sha"] = bool(failure_path.is_file() and sha256_file(failure_path) == failure_spec.get("sha256"))
    if not checks["precompile_failure_core_sha"]:
        errors.append("precompile failure core SHA differs")
    failure_errors = validate_failure_core(failure_receipt, str(package_id), zip_sha, runner_sha)
    checks["precompile_failure_core"] = not failure_errors
    errors.extend(failure_errors)
    if not isinstance(contract.get("claim_boundary"), str) or not contract.get("claim_boundary"):
        errors.append("release-admission claim boundary is absent")

    return {
        "schema": "server-package-release-admission-validation-v1",
        "package_id": package_id,
        "family": package.get("family"),
        "final_zip": {"path": final_zip.get("path"), "bytes": package_zip.stat().st_size if package_zip.is_file() else None, "sha256": zip_sha},
        "checks": checks,
        "controls": controls,
        "pass": not errors and all(checks.values()),
        "errors": errors,
        "rule_adjudication": {
            "classification": "EXISTING_RULE_IMPLEMENTATION_ESCAPE",
            "disposition": "NARROW_EXISTING_RULE_IMPLEMENTATION_HARDENING",
            "confirmed_rule_ids": [
                "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
                "CDA-SERVER-RULE-CHANGE-FIRST-FRESH-INDEPENDENT-REAUDIT-001",
                "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
                "CDA-SERVER-COMPILEFAIL-CORE-RETURN-ROOT-CAUSE-001",
            ],
        },
        "claim_boundary": "Local exact staging/ZIP release admission only; no production compile, simulation, natural terminal, formal D, E3, E4 or E5 claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    contract = load_json(args.contract)
    report = validate_contract(contract, args.workspace_root.resolve())
    write_json(args.output, report)
    print(json.dumps({"pass": report["pass"], "errors": len(report["errors"]), "output": str(args.output)}, sort_keys=True))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
