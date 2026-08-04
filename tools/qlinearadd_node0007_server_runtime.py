#!/usr/bin/env python3
"""Standard-library-only runtime gate for the node0007 QLinearAdd package."""

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
PASS_STATUS = "QLINEARADD_NODE0007_SERVER_PASS"


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


def manifest_value(package_root: Path, key: str) -> str:
    manifest = load_json(package_root.resolve() / MANIFEST)
    value: Any = manifest
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise RuntimeGateError(f"manifest key is absent: {key}")
        value = value[part]
    if not isinstance(value, str) or not value:
        raise RuntimeGateError(f"manifest value is not a nonempty string: {key}")
    if "\n" in value or "\r" in value:
        raise RuntimeGateError(f"manifest value contains a line break: {key}")
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
    target = root.resolve().joinpath(*rel.parts).resolve()
    if not target.is_relative_to(root.resolve()):
        raise RuntimeGateError(f"path escapes root: {relative}")
    return target


def file_records(root: Path, *, exclude_manifest: bool = True) -> dict[str, Any]:
    records: dict[str, Any] = {}
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
    result = bytearray()
    for index, line in enumerate(lines, start=1):
        if len(line) != 128 or set(line) - {ord("0"), ord("1")}:
            raise RuntimeGateError(f"invalid 128-bit line: {path}:{index}")
        result.extend(int(line, 2).to_bytes(16, "little"))
    return bytes(result)


def _prefix(manifest: dict[str, Any]) -> PurePosixPath:
    return PurePosixPath("install", "cfg_pkg", str(manifest["install_name"]))


def preflight(package_root: Path) -> dict[str, Any]:
    root = package_root.resolve()
    manifest = load_json(root / MANIFEST)
    observed = file_records(root)
    if manifest.get("files") != observed:
        expected = manifest.get("files", {})
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        changed = sorted(
            name
            for name in set(expected) & set(observed)
            if expected[name] != observed[name]
        )
        raise RuntimeGateError(
            f"package exact-set differs: missing={missing[:3]} "
            f"extra={extra[:3]} changed={changed[:3]}"
        )
    required_claims = {
        "status": "PACKAGE_READY_NOT_RUN",
        "evidence_level": "E2_LOCAL_ONLY",
        "candidate_release": False,
        "compile_count": 1,
        "simulation_run_count": 1,
        "server_source_preflight_performed": False,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
    }
    for key, expected in required_claims.items():
        if manifest.get(key) != expected:
            raise RuntimeGateError(f"package claim differs: {key}")
    budgets = manifest.get("budgets")
    if (
        not isinstance(budgets, dict)
        or int(budgets.get("upload_zip_max_bytes", 0)) < 64 << 20
        or int(budgets.get("upload_extracted_max_bytes", 0)) < 512 << 20
        or int(budgets.get("return_zip_max_bytes", 0)) < 64 << 20
        or int(budgets.get("return_extracted_max_bytes", 0)) < 256 << 20
        or int(budgets.get("formal_readback_sca_d_exact_count", 0)) != 28
        or int(budgets.get("formal_readback_logical_bytes", 0)) != 16_859_136
        or int(budgets.get("formal_readback_text_bytes", 0)) <= 16_859_136
        or not isinstance(budgets.get("large_node_exception_reason"), str)
    ):
        raise RuntimeGateError("upload/return large-readback budget differs")

    workload = root / "workload/runtime"
    sca = load_json(workload / "sca_cfg.json")
    sca_d = load_json(workload / "sca_cfg_D.json")
    if sca.get("Repeat_Num") != 6 or len(sca_d) != 28:
        raise RuntimeGateError("six-stage or 28-readback contract differs")
    prefix = _prefix(manifest)
    preload_count = 0
    sca_payloads: dict[str, dict[str, Any]] = {}
    for key, entry in sca.items():
        if not isinstance(entry, dict) or "path" not in entry:
            continue
        rel = PurePosixPath(str(entry["path"]))
        if rel.parts[: len(prefix.parts)] != prefix.parts:
            raise RuntimeGateError(f"SCA path escapes package namespace: {key}")
        local = workload.joinpath(*rel.parts[len(prefix.parts) :])
        if not local.is_file():
            raise RuntimeGateError(f"SCA preload missing: {key}")
        if local.suffix in {".txt", ".bin"}:
            decode_128bit(local)
        sca_payloads[key] = entry
        preload_count += 1
    preload_contract = manifest.get("config_preload_contract")
    expected_preload_count = 85
    if preload_contract is not None:
        if not isinstance(preload_contract, dict):
            raise RuntimeGateError("config preload contract must be an object")
        expected_preload_count = int(
            preload_contract.get("expected_sca_preload_count", 0)
        )
        entries = preload_contract.get("entries")
        if (
            expected_preload_count <= 0
            or not isinstance(entries, list)
            or not entries
        ):
            raise RuntimeGateError("config preload contract differs")
        seen_keys: set[str] = set()
        seen_bases: set[str] = set()
        seen_paths: set[str] = set()
        for record in entries:
            if not isinstance(record, dict):
                raise RuntimeGateError("config preload record differs")
            key = str(record.get("sca_key", ""))
            base = str(record.get("base_addr", ""))
            path = str(record.get("path", ""))
            if (
                not key
                or not re.fullmatch(r"0x[0-9A-Fa-f]{8}", base)
                or not path
                or key in seen_keys
                or base.lower() in seen_bases
                or path in seen_paths
            ):
                raise RuntimeGateError("config preload identity differs")
            seen_keys.add(key)
            seen_bases.add(base.lower())
            seen_paths.add(path)
            if sca_payloads.get(key) != {"base_addr": base, "path": path}:
                raise RuntimeGateError(
                    f"SCA config preload differs: {key}"
                )
            rel = PurePosixPath(path)
            local = workload.joinpath(*rel.parts[len(prefix.parts) :])
            if sha256(local) != str(record.get("sha256", "")):
                raise RuntimeGateError(
                    f"SCA config preload payload hash differs: {key}"
                )
            if len(local.read_bytes().splitlines()) != int(
                record.get("line_count", 0)
            ):
                raise RuntimeGateError(
                    f"SCA config preload line count differs: {key}"
                )
    if preload_count != expected_preload_count:
        raise RuntimeGateError(f"preload exact-set differs: {preload_count}")

    expected_targets: set[str] = set()
    for key, entry in sca_d.items():
        if not isinstance(entry, dict) or set(entry) != {
            "base_addr",
            "path",
            "length",
        }:
            raise RuntimeGateError(f"formal readback schema differs: {key}")
        rel = PurePosixPath(str(entry["path"]))
        if rel.parts[: len(prefix.parts)] != prefix.parts:
            raise RuntimeGateError(f"readback path escapes namespace: {key}")
        local_rel = PurePosixPath(*rel.parts[len(prefix.parts) :]).as_posix()
        if local_rel in expected_targets:
            raise RuntimeGateError("formal readback path is duplicated")
        expected_targets.add(local_rel)
        if safe_child(workload, local_rel).exists():
            raise RuntimeGateError(
                "formal readback target must be absent from package"
            )

    checks = manifest.get("readback_checks")
    if not isinstance(checks, list) or len(checks) != 28:
        raise RuntimeGateError("readback check exact-set differs")
    if {str(item["runtime_path"]) for item in checks} != expected_targets:
        raise RuntimeGateError("manifest/SCA_D readback exact-set differs")
    for record in checks:
        golden = safe_child(root, str(record["golden_path"]))
        if len(decode_128bit(golden)) != int(record["size_bytes"]):
            raise RuntimeGateError("golden payload length differs")

    allowlist = manifest.get("return_allowlist")
    progress = manifest.get("progress_localization")
    expected_allowlist_count = 38
    if progress is not None:
        if (
            not isinstance(progress, dict)
            or progress.get("enabled_by_default") is not True
            or progress.get("read_only") is not True
            or progress.get("observer_plusarg") != "+RETURN_OBSERVER"
            or int(progress.get("stall_window_cycles", 0)) <= 0
            or int(progress.get("heartbeat_cycles", 0)) <= 0
            or int(progress.get("host_sample_period_seconds", 0)) <= 0
            or progress.get("claim")
            != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
        ):
            raise RuntimeGateError("progress-localization contract differs")
        expected_allowlist_count += int(
            progress.get("return_allowlist_entry_count", 0)
        )
    if (
        not isinstance(allowlist, list)
        or len(allowlist) != expected_allowlist_count
    ):
        raise RuntimeGateError("return allowlist cardinality differs")
    targets = [str(item.get("target_path")) for item in allowlist]
    if len(targets) != len(set(targets)):
        raise RuntimeGateError("return allowlist targets duplicate")
    for item in allowlist:
        if (
            item.get("source_root") not in {"evidence", "run", "cfg"}
            or not isinstance(item.get("required"), bool)
            or not isinstance(item.get("max_bytes"), int)
            or int(item["max_bytes"]) <= 0
            or not isinstance(item.get("missing_meaning"), str)
        ):
            raise RuntimeGateError("return allowlist record differs")
        safe_child(root, str(item["target_path"]))
    return {
        "schema": "qlinearadd-node0007-package-preflight-v1",
        "valid": True,
        "file_count": len(observed),
        "preload_count": preload_count,
        "readback_count": len(sca_d),
        "formal_readback_targets_absent": True,
        "server_source_files_inspected": False,
    }


def preflight_installed(package_root: Path, cfg_root: Path) -> dict[str, Any]:
    package_report = preflight(package_root)
    manifest = load_json(package_root / MANIFEST)
    for record in manifest["readback_checks"]:
        if safe_child(cfg_root, str(record["runtime_path"])).exists():
            raise RuntimeGateError("installed formal D target was preseeded")
    source = file_records(
        package_root / "workload/runtime", exclude_manifest=False
    )
    installed = file_records(cfg_root, exclude_manifest=False)
    if source != installed:
        raise RuntimeGateError("installed workload differs from package")
    return {
        "schema": "qlinearadd-node0007-installed-preflight-v1",
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
    checks: list[dict[str, Any]] = []
    missing = 0
    mismatch_bytes = 0
    expected_paths = {str(item["runtime_path"]) for item in manifest["readback_checks"]}
    observed_paths = {
        path.relative_to(cfg_root).as_posix()
        for path in cfg_root.rglob("matrix_D_linearized_128bit.txt")
        if path.is_file()
    }
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
    text = (
        sim_log.read_text(encoding="utf-8", errors="replace")
        if sim_log.is_file()
        else ""
    )
    cfg_rel = f"install/cfg_pkg/{manifest['install_name']}"
    preload_contract = manifest.get("config_preload_contract", {})
    expected_preload_count = int(
        preload_contract.get("expected_sca_preload_count", 85)
    )
    critical = {
        pattern: text.count(pattern)
        for pattern in (
            "Cannot open",
            "skip matrix readback",
            "sca_cfg_D_softmax.json",
            "$fatal",
            "Fatal:",
        )
    }
    loader = {
        "sca_cfg_echo_exact": text.count(
            f"Using SCA cfg file: {cfg_rel}/sca_cfg.json"
        )
        == 1,
        "sca_cfg_d_echo_exact": text.count(
            f"Using SCA cfg D file: {cfg_rel}/sca_cfg_D.json"
        )
        == 1,
        "preload_count_exact": bool(
            re.search(
                rf"JSON config:\s*{expected_preload_count}\s+matrices loaded",
                text,
            )
        ),
        "formal_dump_count_exact": bool(
            re.search(r"JSON_D config:\s*28\s+matrices dumped", text)
        ),
        "natural_completion_exact": text.count(
            "Simulation completed successfully!"
        )
        == 1,
        "no_critical_markers": sum(critical.values()) == 0,
    }
    exact_set = observed_paths == expected_paths
    passed = (
        compile_status == 0
        and simulation_status == 0
        and all(loader.values())
        and exact_set
        and missing == 0
        and mismatch_bytes == 0
    )
    result = {
        "schema": "qlinearadd-node0007-server-result-v1",
        "status": PASS_STATUS if passed else "QLINEARADD_NODE0007_SERVER_FAILURE",
        "result_gate_conjunction": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "natural_completion": loader["natural_completion_exact"],
            "loader_checks": loader,
            "formal_readback_exact_set_complete": exact_set,
            "missing_count_zero": missing == 0,
            "mismatch_count_zero": mismatch_bytes == 0,
            "all_terms_true": passed,
        },
        "critical_marker_counts": critical,
        "expected_readback_count": len(expected_paths),
        "observed_readback_count": len(observed_paths),
        "missing_count": missing,
        "mismatch_byte_count": mismatch_bytes,
        "checks": checks,
        "claim_boundary": (
            "dynamic package result only; E4/E5 requires mainline acceptance "
            "and a bound final Trassic2.0_RTL commit"
        ),
    }
    write_json(evidence_root / "SERVER_RESULT_GATE.json", result)
    return result


def collect(
    server_root: Path,
    install_name: str,
    package_root: Path,
    evidence_root: Path,
    run_root: Path,
    cfg_root: Path,
) -> dict[str, Any]:
    manifest = load_json(package_root / MANIFEST)
    destination = server_root / f"{install_name}_return"
    archive_path = destination.with_suffix(".zip")
    sidecar = Path(str(archive_path) + ".sha256")
    destination.mkdir(parents=True, exist_ok=False)
    roots = {"evidence": evidence_root, "run": run_root, "cfg": cfg_root}
    collected: list[dict[str, Any]] = []
    missing: list[str] = []
    for item in manifest["return_allowlist"]:
        source = safe_child(roots[str(item["source_root"])], str(item["source_path"]))
        target = safe_child(destination, str(item["target_path"]))
        if not source.is_file():
            if item["required"]:
                missing.append(str(item["target_path"]))
            continue
        if source.stat().st_size > int(item["max_bytes"]):
            raise RuntimeGateError(f"return budget exceeded: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        collected.append(
            {
                "path": str(item["target_path"]),
                "size_bytes": target.stat().st_size,
                "sha256": sha256(target),
            }
        )
    return_manifest = {
        "schema": "qlinearadd-node0007-return-manifest-v1",
        "status": "complete" if not missing else "incomplete",
        "install_name": install_name,
        "allowlist_only": True,
        "required_missing": missing,
        "files": collected,
    }
    write_json(destination / "RETURN_MANIFEST.json", return_manifest)
    observed = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file() and path.name != "RETURN_MANIFEST.json"
    }
    if observed != {str(item["path"]) for item in collected}:
        raise RuntimeGateError("return exact-set differs from manifest allowlist")
    extracted = sum(
        path.stat().st_size for path in destination.rglob("*") if path.is_file()
    )
    if extracted > int(manifest["budgets"]["return_extracted_max_bytes"]):
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
    if archive_path.stat().st_size > int(manifest["budgets"]["return_zip_max_bytes"]):
        raise RuntimeGateError("return ZIP budget exceeded")
    digest = sha256(archive_path)
    sidecar.write_text(f"{digest}  {archive_path.name}\n", encoding="ascii")
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
    identity = sub.add_parser("manifest-value")
    identity.add_argument("--package-root", type=Path, required=True)
    identity.add_argument("--key", required=True)
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
    col.add_argument("--package-root", type=Path, required=True)
    col.add_argument("--evidence-root", type=Path, required=True)
    col.add_argument("--run-root", type=Path, required=True)
    col.add_argument("--cfg-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "manifest-value":
        print(manifest_value(args.package_root, args.key))
        return 0
    if args.command == "preflight":
        value = preflight(args.package_root)
    elif args.command == "preflight-installed":
        value = preflight_installed(args.package_root, args.cfg_root)
    elif args.command == "analyze":
        value = analyze(
            args.package_root,
            args.cfg_root,
            args.evidence_root,
            args.run_root,
            args.compile_status,
            args.simulation_status,
        )
    else:
        value = collect(
            args.server_root,
            args.install_name,
            args.package_root,
            args.evidence_root,
            args.run_root,
            args.cfg_root,
        )
    print(json.dumps(value, ensure_ascii=False))
    if args.command == "analyze" and value["status"] != PASS_STATUS:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
