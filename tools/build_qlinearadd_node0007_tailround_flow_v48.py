"""Build the fresh QAdd v48 tail-round diagnostic release successor.

v47 is an unreleased local build whose functional/diagnostic payload is kept,
but whose exact runner predates the current stderr-visibility gate.  v48 changes
only identity, runner error visibility, exact path-budget receipts and manifest.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_NAME = "r5_qadd_n7_tailround_flow_v47"
TARGET = "r5_qadd_n7_tailround_flow_v48"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v47-package/r5_qadd_n7_tailround_flow_v47.zip"
SOURCE_SHA = "bdd18c65a1c45239e2081efd5d030d7d95d279c650c1f3d0d71ef2792bd9ecf3"
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v48-package"
OUT_ZIP = OUT / f"{TARGET}.zip"


class BuildError(RuntimeError):
    pass


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def extract(destination: Path) -> Path:
    if sha(SOURCE) != SOURCE_SHA:
        raise BuildError("exact unreleased v47 source differs")
    with zipfile.ZipFile(SOURCE) as archive:
        if archive.testzip() is not None:
            raise BuildError("source CRC failed")
        seen: set[str] = set()
        roots: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename or info.filename in seen or stat.S_ISLNK(mode):
                raise BuildError(f"unsafe source member: {info.filename}")
            seen.add(info.filename)
            roots.add(pure.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"source root differs: {sorted(roots)}")
        archive.extractall(destination)
    source = destination / SOURCE_NAME
    target = destination / TARGET
    source.rename(target)
    return target


def replace_identity(package: Path) -> None:
    suffixes = {".json", ".txt", ".md", ".py", ".sh", ".sv", ".svh", ".v", ".vh"}
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        if path.suffix.lower() not in suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(text.replace(SOURCE_NAME, TARGET), encoding="utf-8", newline="\n")


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    anchor = 'attempt="a$$"\n'
    if text.count(anchor) != 1:
        raise BuildError("runner helper insertion anchor differs")
    helper = """attempt="a$$"
runner_fail() {
  code="$1"
  shift
  message="$*"
  printf 'RUNNER_ERROR package=%s code=%s message=%s\\n' "$package_id" "$code" "$message" >&2
  exit "$code"
}
"""
    text = text.replace(anchor, helper, 1)
    replacements = {
        '  echo "Usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x" >&2\n  exit 2':
            '  runner_fail 2 "expected exactly one absolute server root argument; usage: bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x"',
        'case "$1" in /*) ;; *) echo "server_root must be absolute" >&2; exit 2;; esac':
            'case "$1" in /*) ;; *) runner_fail 2 "server root argument is not absolute";; esac',
        '  command -v "$tool" >/dev/null 2>&1 || exit 3':
            '  command -v "$tool" >/dev/null 2>&1 || runner_fail 3 "required runtime tool is unavailable: $tool"',
        'package_root="$(cd "$package_root" && pwd -P)" || exit 2':
            'package_root="$(cd "$package_root" && pwd -P)" || runner_fail 2 "package root cannot be resolved"',
        'server_root="$(cd "$1" 2>/dev/null && pwd -P)" || exit 2':
            'server_root="$(cd "$1" 2>/dev/null && pwd -P)" || runner_fail 2 "server root cannot be resolved"',
        'mkdir -p -- "$result_root" || exit 9':
            'mkdir -p -- "$result_root" || runner_fail 9 "fixed result root cannot be created"',
        '[ -d "$result_root" ] && [ -w "$result_root" ] || exit 9':
            '[ -d "$result_root" ] && [ -w "$result_root" ] || runner_fail 9 "fixed result root is not writable"',
        '[ "$(cd "$result_root" && pwd -P)" = "$result_root" ] || exit 9':
            '[ "$(cd "$result_root" && pwd -P)" = "$result_root" ] || runner_fail 9 "fixed result root resolves elsewhere"',
        '[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || exit 10':
            '[ ! -e "$return_zip" ] && [ ! -e "$return_sha" ] || runner_fail 10 "fixed return target already exists"',
        'root_pre="$(python3 "$root_guard" snapshot --server-root "$server_root")" || exit 12':
            'root_pre="$(python3 "$root_guard" snapshot --server-root "$server_root")" || runner_fail 12 "NDP root pre-snapshot failed"',
        'layout_values="$(python3 "$layout_helper" prepare   --server-root "$server_root" --package-id "$package_id"   --install-name "$install_name" --attempt "$attempt" --format shell)" || exit 13':
            'layout_values="$(python3 "$layout_helper" prepare   --server-root "$server_root" --package-id "$package_id"   --install-name "$install_name" --attempt "$attempt" --format shell)" || runner_fail 13 "install-subtree layout preparation failed"',
        'python3 "$runtime" preflight --package-root "$package_root"   >"$evidence_root/package_preflight.json" || exit 5':
            'python3 "$runtime" preflight --package-root "$package_root"   >"$evidence_root/package_preflight.json" || runner_fail 5 "package manifest preflight failed"',
        'python3 "$runtime" preflight-installed --package-root "$package_root"   --cfg-root "$cfg_root" --run-root "$run_root"   >"$evidence_root/installed_preflight.json" || exit 6':
            'python3 "$runtime" preflight-installed --package-root "$package_root"   --cfg-root "$cfg_root" --run-root "$run_root"   >"$evidence_root/installed_preflight.json" || runner_fail 6 "installed payload preflight failed"',
        '[ "$compile_status" -eq 0 ] || exit "$compile_status"':
            '[ "$compile_status" -eq 0 ] || runner_fail "$compile_status" "production compile failed; see compile_driver.log"',
        '[ "$simulation_status" -eq 0 ] || exit "$simulation_status"':
            '[ "$simulation_status" -eq 0 ] || runner_fail "$simulation_status" "production simulation did not complete naturally; inspect formal return evidence"',
    }
    for old, new in replacements.items():
        if text.count(old) != 1:
            raise BuildError(f"runner failure anchor differs: {old}")
        text = text.replace(old, new, 1)
    final_anchor = '  exit "$final"\n}'
    if text.count(final_anchor) != 1:
        raise BuildError("runner final status anchor differs")
    text = text.replace(final_anchor, '  printf \'RUNNER_FINAL_STATUS package=%s exit=%s\\n\' "$package_id" "$final" >&2\n' + final_anchor, 1)
    path.write_text(text, encoding="utf-8", newline="\n")


def walk_paths(value: Any):
    if isinstance(value, dict):
        for item in value.values():
            yield from walk_paths(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_paths(item)
    elif isinstance(value, str) and value.startswith("install/"):
        yield value


def update_path_budget(package: Path) -> None:
    contract_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    attempt = "a" * int(contract["path_budget"]["attempt_max_chars"])
    candidates: set[str] = set()
    for mount in contract["payload_mounts"]:
        source = mount["source_prefix"]
        target = mount["runtime_prefix"]
        for path in package.rglob("*"):
            if path.is_file():
                member = path.relative_to(package).as_posix()
                if member.startswith(source):
                    candidates.add(target + member[len(source):])
    for value in contract["runtime_roots"].values():
        candidates.add(value.replace("{attempt}", attempt))
    for value in contract["path_budget"]["additional_projected_paths"]:
        candidates.add(value.replace("{attempt}", attempt))
    longest = max(candidates, key=lambda value: (len(value), value))
    root_max = int(contract["path_budget"]["declared_target_root_max_chars"])
    projected = root_max + 1 + len(longest)
    contract["path_budget"]["max_projected_absolute_path_chars"] = projected
    write_json(contract_path, contract)
    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["path_length_budget"] = {
        "declared_target_root_max_chars": root_max,
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": projected,
        "absolute_path_limit_chars": int(contract["path_budget"]["absolute_path_limit_chars"]),
    }
    write_json(manifest_path, manifest)


def records(package: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        rel = path.relative_to(package).as_posix()
        if rel != "TEST_PACKAGE_MANIFEST.json":
            result[rel] = {"size_bytes": path.stat().st_size, "sha256": sha(path)}
    return result


def update_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["install_name"] = TARGET
    manifest["successor"]["unreleased_intermediate_source"] = {"install_name": SOURCE_NAME, "sha256": SOURCE_SHA, "status": "QUARANTINED_LOCAL_FINAL_AUDIT_FAILED"}
    manifest["successor"]["changed_surface"] = ["runner error visibility", "exact path budget", "identity/manifest/README"]
    manifest["final_zip_rule_self_audit"] = {"required": True, "status": "PENDING_EXACT_ZIP_AUDIT"}
    manifest["provenance"]["generator"] = Path(__file__).relative_to(ROOT).as_posix()
    manifest["files"] = records(package)
    write_json(path, manifest)


def update_package(package: Path) -> None:
    replace_identity(package)
    patch_runner(package)
    readme = package / "README.md"
    text = readme.read_text(encoding="utf-8")
    readme.write_text(text + "\nV48 changes only runner fail-path visibility and exact local release receipts; diagnostic and functional payloads remain frozen.\n", encoding="utf-8", newline="\n")
    update_path_budget(package)
    update_manifest(package)


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            info = zipfile.ZipInfo(f"{TARGET}/{path.relative_to(package).as_posix()}", (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def main() -> int:
    if OUT_ZIP.exists() or (OUT / "build_receipt.json").exists():
        raise BuildError(f"fresh output exists: {OUT}")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="q48a-") as first, tempfile.TemporaryDirectory(prefix="q48b-") as second:
        a = extract(Path(first)); b = extract(Path(second))
        update_package(a); update_package(b)
        za = Path(first) / f"{TARGET}.zip"; zb = Path(second) / f"{TARGET}.zip"
        deterministic_zip(a, za); deterministic_zip(b, zb)
        if za.read_bytes() != zb.read_bytes():
            raise BuildError("deterministic double build differs")
        shutil.copy2(za, OUT_ZIP)
    sidecar = Path(str(OUT_ZIP) + ".sha256")
    sidecar.write_text(f"{sha(OUT_ZIP)}  {OUT_ZIP.name}\n", encoding="ascii", newline="\n")
    receipt = {"schema": "qadd-tailround-flow-v48-build-v1", "status": "BUILT_PENDING_FINAL_AUDIT", "zip": {"path": OUT_ZIP.relative_to(ROOT).as_posix(), "bytes": OUT_ZIP.stat().st_size, "sha256": sha(OUT_ZIP)}, "sidecar": {"path": sidecar.relative_to(ROOT).as_posix(), "bytes": sidecar.stat().st_size, "sha256": sha(sidecar)}, "source_v47_sha256": SOURCE_SHA, "deterministic_double_build": True, "functional_diagnostic_payload_frozen": True, "numeric_workload_config_golden_repeated": False, "server_action": False}
    write_json(OUT / "build_receipt.json", receipt)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
