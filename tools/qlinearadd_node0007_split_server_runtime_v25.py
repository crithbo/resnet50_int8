#!/usr/bin/env python3
"""Standard-library runtime gate for QLinearAdd node0007 split workloads."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


sys.dont_write_bytecode = True
MANIFEST = "TEST_PACKAGE_MANIFEST.json"


class RuntimeGateError(ValueError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeGateError(f"JSON root must be object: {path}")
    return value


def safe_child(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise RuntimeGateError(f"unsafe relative path: {relative}")
    target = root.resolve().joinpath(*pure.parts).resolve()
    if not target.is_relative_to(root.resolve()):
        raise RuntimeGateError(f"path escapes root: {relative}")
    return target


def file_records(root: Path, *, exclude_manifest: bool = True) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST:
            continue
        result[relative] = {"size_bytes": path.stat().st_size, "sha256": sha256(path)}
    return result


def manifest_value(package_root: Path, key: str) -> str:
    value: Any = load_json(package_root.resolve() / MANIFEST)
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise RuntimeGateError(f"manifest key is absent: {key}")
        value = value[part]
    if not isinstance(value, str) or not value or "\n" in value or "\r" in value:
        raise RuntimeGateError(f"manifest value is not a safe string: {key}")
    return value


def decode_128bit(path: Path) -> bytes:
    lines = path.read_bytes().splitlines()
    if not lines:
        raise RuntimeGateError(f"empty 128-bit payload: {path}")
    output = bytearray()
    for index, line in enumerate(lines, 1):
        if len(line) != 128 or set(line) - {ord("0"), ord("1")}:
            raise RuntimeGateError(f"invalid 128-bit line: {path}:{index}")
        output.extend(int(line, 2).to_bytes(16, "little"))
    return bytes(output)


def _split(manifest: dict[str, Any]) -> dict[str, Any]:
    value = manifest.get("split_segment_contract")
    if not isinstance(value, dict):
        raise RuntimeGateError("split_segment_contract absent")
    return value


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
            f"package exact-set differs: missing={missing} extra={extra} changed={changed}"
        )
    split = _split(manifest)
    stage_names = list(split["stage_names"])
    if (
        not stage_names
        or int(split["expected_stage_count"]) != len(stage_names)
        or split["final_stage"] != stage_names[-1]
    ):
        raise RuntimeGateError("ordered stage contract differs")
    sca = load_json(root / "workload/runtime/sca_cfg.json")
    sca_d = load_json(root / "workload/runtime/sca_cfg_D.json")
    if (
        int(sca["Repeat_Num"]) != len(stage_names)
        or int(sca["Exec_Length"]) != int(split["exec_length"])
    ):
        raise RuntimeGateError("SCA execution scope differs")
    prefix = f"install/cfg_pkg/{manifest['install_name']}/"
    preload_paths = [
        str(value["path"])
        for value in sca.values()
        if isinstance(value, dict) and isinstance(value.get("path"), str)
    ]
    if not preload_paths or any(not path.startswith(prefix) for path in preload_paths):
        raise RuntimeGateError("SCA preload namespace differs")
    for path in preload_paths:
        relative = path.removeprefix(prefix)
        if not safe_child(root / "workload/runtime", relative).is_file():
            raise RuntimeGateError(f"SCA preload absent: {relative}")
    output_checks = list(split["output_checks"])
    if len(output_checks) != int(split["expected_output_count"]):
        raise RuntimeGateError("stage output count differs")
    expected_d = {str(item["sca_key"]) for item in output_checks}
    if set(sca_d) != expected_d:
        raise RuntimeGateError("SCA D exact keys differ")
    for item in output_checks:
        d_record = sca_d[str(item["sca_key"])]
        expected_path = prefix + str(item["runtime_path"])
        if d_record["path"] != expected_path:
            raise RuntimeGateError("SCA D path differs")
        if int(d_record["length"]) * 16 != int(item["decoded_bytes"]):
            raise RuntimeGateError("SCA D length differs")
        if safe_child(root / "workload/runtime", str(item["runtime_path"])).exists():
            raise RuntimeGateError("runtime stage output target must be absent")
    actual_stage_dirs = {
        path.name
        for path in (root / "workload/runtime/install").iterdir()
        if path.is_dir() and path.name.startswith("op_")
    }
    if actual_stage_dirs != set(split["payload_stage_dirs"]):
        raise RuntimeGateError("pruned stage payload directory set differs")
    return {
        "schema": "qlinearadd-node0007-split-package-preflight-v25",
        "valid": True,
        "segment_id": split["segment_id"],
        "stage_names": stage_names,
        "file_count": len(observed),
        "preload_count": len(sca) - 3,
        "readback_count": len(output_checks),
        "formal_readback_targets_absent": True,
        "server_source_files_inspected": False,
    }


def preflight_installed(package_root: Path, cfg_root: Path) -> dict[str, Any]:
    package = preflight(package_root)
    manifest = load_json(package_root.resolve() / MANIFEST)
    split = _split(manifest)
    for relative in ("sca_cfg.json", "sca_cfg_D.json", "install/execplan.txt"):
        if not safe_child(cfg_root, relative).is_file():
            raise RuntimeGateError(f"installed payload absent: {relative}")
    for item in split["output_checks"]:
        if safe_child(cfg_root, str(item["runtime_path"])).exists():
            raise RuntimeGateError("installed output target must initially be absent")
    return {
        "schema": "qlinearadd-node0007-split-installed-preflight-v25",
        "valid": True,
        "package_preflight": package,
        "installed_file_count": len(file_records(cfg_root, exclude_manifest=False)),
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
    split = _split(manifest)
    sim_log = run_root / "sim_results/sim.log"
    text = sim_log.read_text(encoding="utf-8", errors="replace") if sim_log.is_file() else ""
    starts = len(re.findall(r"INFO: slice start", text))
    finishes = len(re.findall(r"INFO: slice completed after \d+ cycles", text))
    natural = text.count("Simulation completed successfully!") == 1
    cfg_rel = f"install/cfg_pkg/{manifest['install_name']}"
    expected_preloads = int(split["expected_preload_count"])
    expected_outputs = int(split["expected_output_count"])
    loader = {
        "sca_cfg_echo_exact": text.count(f"Using SCA cfg file: {cfg_rel}/sca_cfg.json") == 1,
        "sca_cfg_d_echo_exact": text.count(
            f"Using SCA cfg D file: {cfg_rel}/sca_cfg_D.json"
        )
        == 1,
        "preload_count_exact": bool(
            re.search(rf"JSON config:\s*{expected_preloads}\s+matrices loaded", text)
        ),
        "dump_count_exact": bool(
            re.search(rf"JSON_D config:\s*{expected_outputs}\s+matrices dumped", text)
        ),
        "natural_completion_exact": natural,
        "ordered_stage_count_exact": (
            starts == int(split["expected_stage_count"])
            and finishes == int(split["expected_stage_count"])
        ),
        "no_critical_markers": not any(
            marker in text
            for marker in ("Cannot open", "skip matrix readback", "$fatal", "Fatal:")
        ),
    }
    expected_paths = {str(item["runtime_path"]) for item in split["output_checks"]}
    observed_paths = {
        path.relative_to(cfg_root).as_posix()
        for path in cfg_root.rglob("matrix_D_linearized_128bit.txt")
        if path.is_file()
    }
    checks: list[dict[str, Any]] = []
    missing = 0
    mismatch_bytes = 0
    invalid = 0
    for item in split["output_checks"]:
        actual = safe_child(cfg_root, str(item["runtime_path"]))
        if not actual.is_file():
            missing += 1
            checks.append({**item, "status": "missing"})
            continue
        try:
            payload = decode_128bit(actual)
        except RuntimeGateError as exc:
            invalid += 1
            checks.append({**item, "status": "invalid", "error": str(exc)})
            continue
        if len(payload) != int(item["decoded_bytes"]):
            invalid += 1
            checks.append(
                {
                    **item,
                    "status": "invalid_length",
                    "actual_decoded_bytes": len(payload),
                }
            )
            continue
        mismatch = 0
        if split["result_mode"] == "FULL_NUMERIC_28D":
            golden = safe_child(package_root, str(item["golden_path"]))
            golden_payload = decode_128bit(golden)
            mismatch = sum(
                left != right for left, right in zip(payload, golden_payload, strict=False)
            ) + abs(len(payload) - len(golden_payload))
            mismatch_bytes += mismatch
        checks.append(
            {
                **item,
                "status": "pass" if mismatch == 0 else "mismatch",
                "actual_sha256": sha256(actual),
                "mismatch_bytes": mismatch,
            }
        )
    exact_set = observed_paths == expected_paths
    stage_local = split["result_mode"] == "STAGE_LOCAL_STRUCTURAL"
    passed = (
        compile_status == 0
        and simulation_status == 0
        and all(loader.values())
        and exact_set
        and missing == 0
        and invalid == 0
        and mismatch_bytes == 0
    )
    result = {
        "schema": "qlinearadd-node0007-split-server-result-v25",
        "status": (
            "QLINEARADD_NODE0007_SPLIT_STAGE_PASS"
            if passed and stage_local
            else "QLINEARADD_NODE0007_SERVER_PASS"
            if passed
            else "QLINEARADD_NODE0007_SPLIT_SERVER_FAILURE"
        ),
        "segment_id": split["segment_id"],
        "claim_boundary": (
            "stage-local structural output/readback evidence only; no upstream, "
            "cross-segment, numeric, E3, E4 or E5 claim"
            if stage_local
            else "full six-stage plus 28-D dynamic package result; E4/E5 still "
            "requires mainline acceptance and a bound final RTL commit"
        ),
        "result_gate_conjunction": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "loader_checks": loader,
            "output_exact_set_complete": exact_set,
            "missing_count_zero": missing == 0,
            "invalid_count_zero": invalid == 0,
            "mismatch_count_zero": mismatch_bytes == 0,
            "all_terms_true": passed,
        },
        "expected_readback_count": len(expected_paths),
        "observed_readback_count": len(observed_paths),
        "missing_count": missing,
        "invalid_count": invalid,
        "mismatch_byte_count": mismatch_bytes,
        "mismatch_evaluable": not stage_local,
        "checks": checks,
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
        "schema": "qlinearadd-node0007-split-return-manifest-v25",
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
        raise RuntimeGateError("return exact-set differs")
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
    sidecar.write_text(f"{digest}  {archive_path.name}\n", encoding="ascii", newline="\n")
    return {"zip": str(archive_path), "sha256": digest, "required_missing": missing}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    value = sub.add_parser("manifest-value")
    value.add_argument("--package-root", type=Path, required=True)
    value.add_argument("--key", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--package-root", type=Path, required=True)
    installed = sub.add_parser("preflight-installed")
    installed.add_argument("--package-root", type=Path, required=True)
    installed.add_argument("--cfg-root", type=Path, required=True)
    run = sub.add_parser("analyze")
    run.add_argument("--package-root", type=Path, required=True)
    run.add_argument("--cfg-root", type=Path, required=True)
    run.add_argument("--evidence-root", type=Path, required=True)
    run.add_argument("--run-root", type=Path, required=True)
    run.add_argument("--compile-status", type=int, required=True)
    run.add_argument("--simulation-status", type=int, required=True)
    ret = sub.add_parser("collect")
    ret.add_argument("--server-root", type=Path, required=True)
    ret.add_argument("--install-name", required=True)
    ret.add_argument("--package-root", type=Path, required=True)
    ret.add_argument("--evidence-root", type=Path, required=True)
    ret.add_argument("--run-root", type=Path, required=True)
    ret.add_argument("--cfg-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "manifest-value":
            print(manifest_value(args.package_root, args.key))
        elif args.command == "preflight":
            print(json.dumps(preflight(args.package_root)))
        elif args.command == "preflight-installed":
            print(json.dumps(preflight_installed(args.package_root, args.cfg_root)))
        elif args.command == "analyze":
            result = analyze(
                args.package_root,
                args.cfg_root,
                args.evidence_root,
                args.run_root,
                args.compile_status,
                args.simulation_status,
            )
            print(json.dumps(result))
            return 0 if result["result_gate_conjunction"]["all_terms_true"] else 1
        else:
            print(
                json.dumps(
                    collect(
                        args.server_root,
                        args.install_name,
                        args.package_root,
                        args.evidence_root,
                        args.run_root,
                        args.cfg_root,
                    )
                )
            )
    except Exception as exc:
        print(f"split runtime failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
