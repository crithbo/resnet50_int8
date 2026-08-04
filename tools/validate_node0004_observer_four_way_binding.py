from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


STATUS_PASS = "FOUR_WAY_BINDING_VALIDATED"
STATUS_FAIL = "PACKAGE_OBSERVER_BINDING_INCOMPLETE"
MANIFEST_NAME = "package_manifest.json"
RUNNER_NAME = "PREPARE_AND_RUN.sh"
OBSERVER_MACRO = "+define+NATIVE_RETURN_OBSERVER_ENABLE"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(name: str) -> PurePosixPath:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or "\\" in name:
        raise ValueError(f"unsafe ZIP member: {name}")
    return pure


def load_zip_entries(path: Path) -> tuple[str, dict[str, bytes], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        crc_error = archive.testzip()
        if crc_error is not None:
            raise ValueError(f"ZIP CRC failed at {crc_error}")
        infos = archive.infolist()
        roots = {
            _safe_relative(info.filename).parts[0]
            for info in infos
            if not info.is_dir()
        }
        if len(roots) != 1:
            raise ValueError(f"ZIP root count differs: {sorted(roots)}")
        root = next(iter(roots))
        entries: dict[str, bytes] = {}
        for info in infos:
            if info.is_dir():
                continue
            pure = _safe_relative(info.filename)
            if pure.parts[0] != root:
                raise ValueError(f"member escapes ZIP root: {info.filename}")
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if relative in entries:
                raise ValueError(f"duplicate ZIP member: {relative}")
            entries[relative] = archive.read(info)
    return root, entries, {
        "crc_pass": True,
        "single_root": root,
        "zip_entry_count": len(entries),
    }


def _json(entries: dict[str, bytes], name: str) -> dict[str, Any]:
    if name not in entries:
        raise ValueError(f"missing {name}")
    value = json.loads(entries[name].decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{name} is not a JSON object")
    return value


def _compile_options(runner: str) -> tuple[list[str], str]:
    matches = re.findall(r'VCS_EXTRA_OPTS="([^"]*)"', runner)
    if len(matches) != 1:
        raise ValueError(
            f"expected one VCS_EXTRA_OPTS assignment, observed {len(matches)}"
        )
    return shlex.split(matches[0]), matches[0]


def validate_entries(
    root: str,
    entries: dict[str, bytes],
    zip_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    checks: dict[str, Any] = {
        "source": False,
        "include": False,
        "compile_enable": False,
        "runtime_return": False,
    }
    detail: dict[str, Any] = {}

    try:
        manifest = _json(entries, MANIFEST_NAME)
    except Exception as error:
        manifest = {}
        errors.append(str(error))

    binding = manifest.get("observer_binding_four_way")
    if not isinstance(binding, dict):
        binding = {}
        errors.append("manifest observer_binding_four_way is missing")

    source = binding.get("source")
    if not isinstance(source, dict):
        source = {}
        errors.append("manifest source binding is missing")
    source_path = source.get("path")
    source_size = source.get("size_bytes")
    source_sha = source.get("sha256")
    if (
        not isinstance(source_path, str)
        or not isinstance(source_size, int)
        or not isinstance(source_sha, str)
    ):
        errors.append("source path/size_bytes/sha256 are not fully declared")
    else:
        source_occurrences = sum(
            1 for name in entries if name == source_path
        )
        if source_occurrences != 1:
            errors.append(
                f"observer source occurrence count is {source_occurrences}"
            )
        elif len(entries[source_path]) != source_size:
            errors.append("observer source size differs")
        elif sha256_bytes(entries[source_path]) != source_sha:
            errors.append("observer source SHA256 differs")
        else:
            try:
                with tempfile.TemporaryDirectory(
                    prefix="node0004-four-way-"
                ) as temporary:
                    extract_root = Path(temporary) / root
                    for relative, payload in entries.items():
                        pure = _safe_relative(relative)
                        target = extract_root / Path(*pure.parts)
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(payload)
                    extracted_source = (
                        extract_root / Path(*PurePosixPath(source_path).parts)
                    )
                    if (
                        extracted_source.is_file()
                        and extracted_source.read_bytes()
                        == entries[source_path]
                    ):
                        checks["source"] = True
                    else:
                        errors.append("fresh-extracted observer is not readable")
            except Exception as error:
                errors.append(f"fresh extract failed: {error}")
        detail["source"] = {
            "path": source_path,
            "size_bytes": source_size,
            "sha256": source_sha,
            "occurrences": source_occurrences,
        }

    runner_payload = entries.get(RUNNER_NAME)
    if runner_payload is None:
        errors.append(f"missing {RUNNER_NAME}")
        runner = ""
    else:
        runner = runner_payload.decode("utf-8")

    compile_binding = binding.get("compile")
    if not isinstance(compile_binding, dict):
        compile_binding = {}
        errors.append("manifest compile binding is missing")
    try:
        compile_tokens, compile_text = _compile_options(runner)
    except Exception as error:
        compile_tokens, compile_text = [], ""
        errors.append(str(error))

    incdir_tokens = [
        token for token in compile_tokens if token.startswith("+incdir+")
    ]
    expected_incdir = compile_binding.get("package_local_incdir")
    if not isinstance(expected_incdir, str):
        errors.append("manifest package_local_incdir is missing")
    elif not isinstance(source_path, str):
        errors.append("cannot bind include without source path")
    else:
        expected_parent = PurePosixPath(source_path).parent.as_posix()
        if expected_incdir != expected_parent:
            errors.append("manifest include directory is not source parent")
        expected_shell_token = f"+incdir+$package_root/{expected_incdir}"
        if incdir_tokens != [expected_shell_token]:
            errors.append(
                "compile include token is not the unique normalized "
                "package-local observer directory"
            )
        else:
            normalized = PurePosixPath(expected_incdir)
            if (
                normalized.is_absolute()
                or ".." in normalized.parts
                or "\\" in expected_incdir
            ):
                errors.append("compile include directory escapes package root")
            else:
                checks["include"] = True
    detail["include"] = {
        "compile_options": compile_text,
        "incdir_tokens": incdir_tokens,
        "manifest_package_local_incdir": expected_incdir,
    }

    expected_macro = compile_binding.get("enable_macro")
    macro_count = compile_tokens.count(OBSERVER_MACRO)
    if expected_macro != OBSERVER_MACRO:
        errors.append("manifest enable macro differs")
    elif macro_count != 1:
        errors.append(f"compile enable macro count is {macro_count}")
    else:
        checks["compile_enable"] = True
    detail["compile_enable"] = {
        "expected": OBSERVER_MACRO,
        "count": macro_count,
    }

    runtime_binding = binding.get("runtime_return")
    if not isinstance(runtime_binding, dict):
        runtime_binding = {}
        errors.append("manifest runtime_return binding is missing")
    runtime_path = runtime_binding.get("runtime_source")
    runtime_payload = (
        entries.get(runtime_path) if isinstance(runtime_path, str) else None
    )
    if runtime_payload is None:
        errors.append("runtime source declared by manifest is missing")
        runtime_text = ""
    else:
        runtime_text = runtime_payload.decode("utf-8")

    required_plusargs = runtime_binding.get("simulator_plusargs")
    required_marker = runtime_binding.get("time_zero_enabled_marker")
    required_return_paths = runtime_binding.get("return_allowlist_paths")
    required_signal_names = runtime_binding.get("signal_traps")
    if not isinstance(required_plusargs, list):
        errors.append("simulator_plusargs declaration is missing")
        required_plusargs = []
    if not isinstance(required_marker, str):
        errors.append("time_zero_enabled_marker declaration is missing")
        required_marker = ""
    if not isinstance(required_return_paths, list):
        errors.append("return_allowlist_paths declaration is missing")
        required_return_paths = []
    if not isinstance(required_signal_names, list):
        errors.append("signal_traps declaration is missing")
        required_signal_names = []

    runtime_errors: list[str] = []
    for token in required_plusargs:
        if not isinstance(token, str) or token not in runner:
            runtime_errors.append(f"simulator plusarg missing: {token!r}")
    if (
        not isinstance(source_path, str)
        or source_path not in entries
        or required_marker not in entries.get(source_path, b"").decode(
            "utf-8", errors="replace"
        )
    ):
        runtime_errors.append("time-zero enabled marker is not emitted")
    for relative in required_return_paths:
        if not isinstance(relative, str) or relative not in runtime_text:
            runtime_errors.append(
                f"return allowlist path missing from runtime: {relative!r}"
            )
    for signal_name in required_signal_names:
        trap_pattern = f"trap 'on_signal {signal_name} "
        if not isinstance(signal_name, str) or trap_pattern not in runner:
            runtime_errors.append(f"signal trap missing: {signal_name!r}")
    for token in (
        "trap 'finalize $?' EXIT",
        'python3 "$runtime" collect',
        "finalize \"$2\"",
        "simulator_argv.txt",
        "compile_driver.log",
        "return_observer.log",
        "host_progress.log",
    ):
        if token not in runner and token not in runtime_text:
            runtime_errors.append(f"runtime/return binding missing: {token}")
    if runtime_errors:
        errors.extend(runtime_errors)
    else:
        checks["runtime_return"] = True
    detail["runtime_return"] = {
        "runtime_source": runtime_path,
        "simulator_plusargs": required_plusargs,
        "time_zero_enabled_marker": required_marker,
        "return_allowlist_paths": required_return_paths,
        "signal_traps": required_signal_names,
        "errors": runtime_errors,
    }

    passed = all(checks.values()) and not errors
    result: dict[str, Any] = {
        "schema": "node0004-observer-four-way-binding-receipt-v1",
        "status": STATUS_PASS if passed else STATUS_FAIL,
        "valid": passed,
        "package_root": root,
        "checks": checks,
        "detail": detail,
        "errors": errors,
    }
    if zip_meta:
        result["zip"] = zip_meta
    return result


def validate_zip(path: Path) -> dict[str, Any]:
    root, entries, zip_meta = load_zip_entries(path)
    zip_meta.update(
        {
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
    )
    return validate_entries(root, entries, zip_meta)


def _replace_once(
    entries: dict[str, bytes],
    path: str,
    old: bytes,
    new: bytes,
) -> dict[str, bytes]:
    result = dict(entries)
    payload = result[path]
    if old not in payload:
        raise ValueError(f"negative-control token missing: {path}: {old!r}")
    result[path] = payload.replace(old, new, 1)
    return result


def _replace_all(
    entries: dict[str, bytes],
    path: str,
    old: bytes,
    new: bytes,
) -> dict[str, bytes]:
    result = dict(entries)
    payload = result[path]
    if old not in payload:
        raise ValueError(f"negative-control token missing: {path}: {old!r}")
    result[path] = payload.replace(old, new)
    return result


def run_negative_controls(path: Path) -> dict[str, Any]:
    root, entries, zip_meta = load_zip_entries(path)
    manifest = _json(entries, MANIFEST_NAME)
    binding = manifest["observer_binding_four_way"]
    source_path = binding["source"]["path"]
    runtime_path = binding["runtime_return"]["runtime_source"]

    missing_source = dict(entries)
    del missing_source[source_path]
    variants = {
        "missing_source": missing_source,
        "missing_incdir": _replace_once(
            entries,
            RUNNER_NAME,
            b"+incdir+$package_root/tb_probe",
            b"+incdir+REMOVED",
        ),
        "missing_enable_macro": _replace_once(
            entries,
            RUNNER_NAME,
            b"+define+NATIVE_RETURN_OBSERVER_ENABLE ",
            b"",
        ),
        "missing_runtime_return_binding": _replace_all(
            entries,
            runtime_path,
            b"runs/c0/return_observer.log",
            b"runs/c0/REMOVED.log",
        ),
    }
    records: dict[str, Any] = {}
    for name, mutated in variants.items():
        result = validate_entries(root, mutated, zip_meta)
        records[name] = {
            "status": result["status"],
            "valid": result["valid"],
            "failed_closed": (
                result["status"] == STATUS_FAIL and not result["valid"]
            ),
            "checks": result["checks"],
        }
    all_failed_closed = all(
        record["failed_closed"] for record in records.values()
    )
    return {
        "all_failed_closed": all_failed_closed,
        "records": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--negative-controls", action="store_true")
    args = parser.parse_args()
    result = validate_zip(args.zip)
    if args.negative_controls and result["valid"]:
        negative = run_negative_controls(args.zip)
        result["negative_controls"] = negative
        if not negative["all_failed_closed"]:
            result["status"] = STATUS_FAIL
            result["valid"] = False
            result["errors"].append("negative controls did not all fail closed")
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
