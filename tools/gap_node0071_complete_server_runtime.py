#!/usr/bin/env python3
"""Standard-library-only runtime for the node0071 complete GAP package."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST = "TEST_PACKAGE_MANIFEST.json"


class RuntimeGateError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeGateError(f"JSON root must be object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def safe_child(root: Path, relative: str) -> Path:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts:
        raise RuntimeGateError(f"unsafe relative path: {relative}")
    result = root.resolve().joinpath(*rel.parts).resolve()
    if not result.is_relative_to(root.resolve()):
        raise RuntimeGateError(f"path escapes root: {relative}")
    return result


def file_records(root: Path, *, exclude_manifest: bool = True) -> dict[str, Any]:
    records = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST:
            continue
        records[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return records


def decode_128bit(path: Path) -> bytes:
    lines = path.read_bytes().splitlines()
    if not lines:
        raise RuntimeGateError(f"empty 128-bit payload: {path}")
    payload = bytearray()
    for index, line in enumerate(lines, start=1):
        if len(line) != 128 or set(line) - {ord("0"), ord("1")}:
            raise RuntimeGateError(f"invalid 128-bit line: {path}:{index}")
        payload.extend(int(line, 2).to_bytes(16, "little"))
    return bytes(payload)


def preflight(package_root: Path) -> dict[str, Any]:
    root = package_root.resolve()
    manifest = load_json(root / MANIFEST)
    observed = file_records(root)
    if manifest.get("files") != observed:
        expected = manifest.get("files", {})
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        changed = sorted(
            key
            for key in set(expected) & set(observed)
            if expected[key] != observed[key]
        )
        raise RuntimeGateError(
            f"package exact-set differs: missing={missing[:3]} "
            f"extra={extra[:3]} changed={changed[:3]}"
        )
    if (
        manifest.get("status") != "PACKAGE_READY_NOT_RUN"
        or manifest.get("evidence_level") != "E2_LOCAL_COMPLETE_NODE"
        or manifest.get("compile_count") != 1
        or manifest.get("simulation_run_count") != 1
        or manifest.get("server_source_preflight_performed") is not False
        or manifest.get("functional_rtl_modified") is not False
    ):
        raise RuntimeGateError("package claim boundary differs")
    workload = root / "workload"
    sca = load_json(workload / "sca_cfg.json")
    sca_d = load_json(workload / "sca_cfg_D.json")
    if sca.get("Repeat_Num") != 8 or len(sca_d) != 48:
        raise RuntimeGateError("eight-stage or 48-readback contract differs")
    for path in (workload / "sca_cfg.json", workload / "sca_cfg_D.json"):
        value = load_json(path)
        expected_text = (
            json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n"
        )
        if path.read_text(encoding="utf-8") != expected_text:
            raise RuntimeGateError(f"SCA JSON is not canonical pretty JSON: {path}")
    prefix = PurePosixPath(
        "install", "cfg_pkg", str(manifest["install_name"])
    )
    preload_count = 0
    for key, entry in sca.items():
        if not isinstance(entry, dict) or "path" not in entry:
            continue
        rel = PurePosixPath(str(entry["path"]))
        if rel.parts[: len(prefix.parts)] != prefix.parts:
            raise RuntimeGateError(f"SCA path escapes namespace: {key}")
        local = workload.joinpath(*rel.parts[len(prefix.parts) :])
        if not local.is_file():
            raise RuntimeGateError(f"SCA preload missing: {key}")
        if local.suffix in {".txt", ".bin"}:
            decode_128bit(local)
        preload_count += 1
    for key, entry in sca_d.items():
        if not isinstance(entry, dict) or set(entry) != {
            "base_addr",
            "path",
            "length",
        }:
            raise RuntimeGateError(f"readback schema differs: {key}")
        rel = PurePosixPath(str(entry["path"]))
        if rel.parts[: len(prefix.parts)] != prefix.parts:
            raise RuntimeGateError(f"readback path escapes namespace: {key}")
        local = workload.joinpath(*rel.parts[len(prefix.parts) :])
        if local.exists():
            raise RuntimeGateError("formal readback target must be absent")
    for record in manifest["readback_checks"]:
        golden = safe_child(root, str(record["golden_path"]))
        if len(decode_128bit(golden)) != int(record["size_bytes"]):
            raise RuntimeGateError("golden payload length differs")
    allowlist = manifest.get("return_allowlist")
    if not isinstance(allowlist, list) or len(allowlist) != 59:
        raise RuntimeGateError("return manifest allowlist cardinality differs")
    targets = [str(entry.get("target_path")) for entry in allowlist]
    if len(targets) != len(set(targets)):
        raise RuntimeGateError("return manifest allowlist target duplicates")
    for entry in allowlist:
        if (
            entry.get("source_root") not in {"evidence", "run", "cfg"}
            or not isinstance(entry.get("required"), bool)
            or not isinstance(entry.get("max_bytes"), int)
            or entry["max_bytes"] <= 0
            or not isinstance(entry.get("missing_meaning"), str)
        ):
            raise RuntimeGateError("return manifest allowlist entry differs")
        safe_child(root, str(entry["target_path"]))
    return {
        "schema": "gap-node0071-complete-package-preflight-v1",
        "valid": True,
        "file_count": len(observed),
        "preload_count": preload_count,
        "readback_count": len(sca_d),
        "repeat_num": 8,
    }


def preflight_installed(package_root: Path, cfg_root: Path) -> dict[str, Any]:
    package_report = preflight(package_root)
    manifest = load_json(package_root / MANIFEST)
    for record in manifest["readback_checks"]:
        target = safe_child(cfg_root, str(record["runtime_path"]))
        if target.exists():
            raise RuntimeGateError(
                f"PACKAGE_PRESEEDED_READBACK_TARGET: {target}"
            )
    source = file_records(package_root / "workload", exclude_manifest=False)
    installed = file_records(cfg_root, exclude_manifest=False)
    if source != installed:
        raise RuntimeGateError("installed workload differs from package")
    return {
        "schema": "gap-node0071-complete-installed-preflight-v1",
        "valid": True,
        "package_preflight": package_report,
        "installed_file_count": len(installed),
        "formal_readback_targets_absent": True,
        "server_source_files_inspected": False,
    }


def analyze(
    package_root: Path,
    cfg_root: Path,
    evidence_root: Path,
    run_root: Path,
    compile_status: int,
    simulation_status: int,
) -> dict[str, Any]:
    manifest = load_json(package_root / MANIFEST)
    checks = []
    missing = 0
    mismatch_bytes = 0
    for record in manifest["readback_checks"]:
        actual = safe_child(cfg_root, str(record["runtime_path"]))
        golden = safe_child(package_root, str(record["golden_path"]))
        if not actual.is_file():
            missing += 1
            checks.append({**record, "status": "missing"})
            continue
        actual_payload = decode_128bit(actual)
        golden_payload = decode_128bit(golden)
        mismatches = sum(
            left != right
            for left, right in zip(actual_payload, golden_payload, strict=False)
        ) + abs(len(actual_payload) - len(golden_payload))
        mismatch_bytes += mismatches
        checks.append(
            {
                **record,
                "status": "pass" if mismatches == 0 else "mismatch",
                "mismatch_bytes": mismatches,
                "actual_sha256": sha256(actual),
                "golden_sha256": sha256(golden),
            }
        )
    sim_log = run_root / "sim_results/sim.log"
    sim_text = (
        sim_log.read_text(encoding="utf-8", errors="replace")
        if sim_log.is_file()
        else ""
    )
    terminal = "Simulation completed successfully!" in sim_text
    loader = {
        "sca_cfg_echo": (
            f"Using SCA cfg file: install/cfg_pkg/"
            f"{manifest['install_name']}/sca_cfg.json"
        )
        in sim_text,
        "sca_cfg_d_echo": (
            f"Using SCA cfg D file: install/cfg_pkg/"
            f"{manifest['install_name']}/sca_cfg_D.json"
        )
        in sim_text,
        "no_cannot_open": "Cannot open" not in sim_text,
        "no_skip_matrix_readback": "skip matrix readback" not in sim_text,
        "no_softmax_fallback": "sca_cfg_D_softmax.json" not in sim_text,
        "preload_count_exact": bool(
            re.search(r"JSON config:\s*25\s+matrices loaded", sim_text)
        ),
        "formal_dump_count_exact": bool(
            re.search(r"JSON_D config:\s*48\s+matrices dumped", sim_text)
        ),
    }
    passed = (
        compile_status == 0
        and simulation_status == 0
        and terminal
        and all(loader.values())
        and missing == 0
        and mismatch_bytes == 0
    )
    result = {
        "schema": "gap-node0071-complete-server-result-v1",
        "status": (
            "COMPLETE_NODE0071_GAP_PASS"
            if passed
            else "NODE0071_GAP_SERVER_FAILURE"
        ),
        "result_gate_conjunction": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "natural_completion": terminal,
            "loader_checks": loader,
            "formal_readback_exact_set_complete": missing == 0,
            "missing_count_zero": missing == 0,
            "mismatch_count_zero": mismatch_bytes == 0,
            "all_terms_true": passed,
        },
        "readback_count": len(checks),
        "missing_count": missing,
        "mismatch_byte_count": mismatch_bytes,
        "checks": checks,
        "claim_boundary": (
            "dynamic result only; production/E5 requires mainline adjudication "
            "and a bound final Trassic2.0_RTL commit"
        ),
    }
    write_json(evidence_root / "SERVER_RESULT_GATE.json", result)
    return result


def collect(
    server_root: Path,
    install_name: str,
    evidence_root: Path,
    run_root: Path,
    cfg_root: Path,
) -> dict[str, Any]:
    destination = server_root / f"{install_name}_return"
    archive_path = destination.with_suffix(".zip")
    sidecar = Path(str(archive_path) + ".sha256")
    destination.mkdir(parents=True, exist_ok=False)
    manifest = load_json(server_root / "install/cfg_pkg" / install_name / MANIFEST) \
        if (server_root / "install/cfg_pkg" / install_name / MANIFEST).is_file() \
        else None
    if manifest is None:
        # The manifest is deliberately outside the installed workload.
        package_manifest = evidence_root / "PACKAGE_MANIFEST.json"
        if not package_manifest.is_file():
            raise RuntimeGateError("return allowlist manifest receipt missing")
        manifest = load_json(package_manifest)
    collected = []
    missing = []
    roots = {
        "evidence": evidence_root,
        "run": run_root,
        "cfg": cfg_root,
    }
    for entry in manifest["return_allowlist"]:
        source = safe_child(roots[str(entry["source_root"])], str(entry["source_path"]))
        target = safe_child(destination, str(entry["target_path"]))
        if not source.is_file():
            if entry["required"]:
                missing.append(entry["target_path"])
            continue
        if source.stat().st_size > int(entry["max_bytes"]):
            raise RuntimeGateError(f"return allowlist budget exceeded: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        collected.append(
            {
                "path": entry["target_path"],
                "size_bytes": target.stat().st_size,
                "sha256": sha256(target),
            }
        )
    return_manifest = {
        "schema": "gap-node0071-complete-return-manifest-v1",
        "status": "complete" if not missing else "incomplete",
        "install_name": install_name,
        "allowlist_only": True,
        "required_missing": missing,
        "files": collected,
    }
    write_json(destination / "RETURN_MANIFEST.json", return_manifest)
    observed_return = {
        path.relative_to(destination).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in destination.rglob("*") if item.is_file())
        if path.name != "RETURN_MANIFEST.json"
    }
    expected_return = {
        item["path"]: {
            "size_bytes": item["size_bytes"],
            "sha256": item["sha256"],
        }
        for item in collected
    }
    if observed_return != expected_return:
        raise RuntimeGateError("return exact-set differs from manifest allowlist")
    extracted_bytes = sum(
        path.stat().st_size
        for path in destination.rglob("*")
        if path.is_file()
    )
    if extracted_bytes > int(manifest["budgets"]["return_extracted_max_bytes"]):
        raise RuntimeGateError("return extracted-size budget exceeded")
    with zipfile.ZipFile(
        archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in destination.rglob("*") if item.is_file()):
            relative = f"{destination.name}/{path.relative_to(destination).as_posix()}"
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    digest = sha256(archive_path)
    if archive_path.stat().st_size > int(
        manifest["budgets"]["return_zip_max_bytes"]
    ):
        raise RuntimeGateError("return ZIP budget exceeded")
    sidecar.write_text(f"{digest}  {archive_path.name}\n", encoding="ascii")
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = archive.namelist()
        if any(".." in PurePosixPath(name).parts for name in names):
            raise RuntimeGateError("return ZIP path traversal")
    return {
        "zip": str(archive_path),
        "sha256": digest,
        "required_missing": missing,
        "return_manifest": return_manifest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--package-root", type=Path, required=True)
    ins = sub.add_parser("preflight-installed")
    ins.add_argument("--package-root", type=Path, required=True)
    ins.add_argument("--cfg-root", type=Path, required=True)
    ana = sub.add_parser("analyze")
    ana.add_argument("--package-root", type=Path, required=True)
    ana.add_argument("--cfg-root", type=Path, required=True)
    ana.add_argument("--evidence-root", type=Path, required=True)
    ana.add_argument("--run-root", type=Path, required=True)
    ana.add_argument("--compile-status", type=int, required=True)
    ana.add_argument("--simulation-status", type=int, required=True)
    col = sub.add_parser("collect")
    col.add_argument("--server-root", type=Path, required=True)
    col.add_argument("--install-name", required=True)
    col.add_argument("--evidence-root", type=Path, required=True)
    col.add_argument("--run-root", type=Path, required=True)
    col.add_argument("--cfg-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "preflight":
            result = preflight(args.package_root)
        elif args.command == "preflight-installed":
            result = preflight_installed(args.package_root, args.cfg_root)
        elif args.command == "analyze":
            result = analyze(
                args.package_root,
                args.cfg_root,
                args.evidence_root,
                args.run_root,
                args.compile_status,
                args.simulation_status,
            )
        else:
            result = collect(
                args.server_root,
                args.install_name,
                args.evidence_root,
                args.run_root,
                args.cfg_root,
            )
    except Exception as error:
        print(f"node0071 GAP runtime failed: {error}")
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.command == "analyze" and result["status"] != "COMPLETE_NODE0071_GAP_PASS":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
