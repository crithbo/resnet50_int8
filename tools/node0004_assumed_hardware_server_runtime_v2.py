from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


PASS_STATUS = "THREE_PHASE_NODE0004_PASS"


class RuntimeErrorContract(ValueError):
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
        raise RuntimeErrorContract(f"JSON root must be object: {path}")
    return value


def safe_child(root: Path, relative: str) -> Path:
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts:
        raise RuntimeErrorContract(f"unsafe relative path: {relative}")
    target = (root / Path(*rel.parts)).resolve()
    if not target.is_relative_to(root.resolve()):
        raise RuntimeErrorContract(f"path escapes root: {relative}")
    return target


def package_records(
    root: Path, *, exclude_manifest: bool = True
) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == "package_manifest.json":
            continue
        records[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return records


def _readback_records(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    records = manifest.get("readback_checks")
    if not isinstance(records, list) or len(records) != 320:
        raise RuntimeErrorContract("readback check list must contain 320 records")
    return records


def preflight(package_root: Path) -> dict[str, Any]:
    manifest = load_json(package_root / "package_manifest.json")
    expected = manifest.get("files")
    if not isinstance(expected, dict):
        raise RuntimeErrorContract("package manifest has no file exact-set")
    observed = package_records(package_root)
    if observed != expected:
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        changed = sorted(
            name
            for name in set(expected) & set(observed)
            if expected[name] != observed[name]
        )
        raise RuntimeErrorContract(
            f"package exact-set differs: missing={missing[:3]} "
            f"extra={extra[:3]} changed={changed[:3]}"
        )
    records = _readback_records(manifest)
    preloaded = [
        str(record["runtime_path"])
        for record in records
        if safe_child(
            package_root / "workload/runtime",
            str(record["runtime_path"]),
        ).exists()
    ]
    if preloaded:
        raise RuntimeErrorContract(
            f"runtime D targets must not be packaged: {preloaded[:3]}"
        )
    return {
        "schema": "node0004-assumed-hardware-package-preflight-v2",
        "valid": True,
        "file_count": len(observed),
        "readback_target_count": len(records),
        "preloaded_readback_target_count": 0,
    }


def verify_install(package_root: Path, cfg_root: Path) -> dict[str, Any]:
    source = package_root / "workload/runtime"
    expected = package_records(source, exclude_manifest=False)
    observed = package_records(cfg_root, exclude_manifest=False)
    if observed != expected:
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        changed = sorted(
            name
            for name in set(expected) & set(observed)
            if expected[name] != observed[name]
        )
        raise RuntimeErrorContract(
            f"installed exact-set differs: missing={missing[:3]} "
            f"extra={extra[:3]} changed={changed[:3]}"
        )
    manifest = load_json(package_root / "package_manifest.json")
    preloaded = [
        str(record["runtime_path"])
        for record in _readback_records(manifest)
        if safe_child(cfg_root, str(record["runtime_path"])).exists()
    ]
    if preloaded:
        raise RuntimeErrorContract(
            f"installed D targets must begin absent: {preloaded[:3]}"
        )
    return {
        "schema": "node0004-assumed-hardware-install-preflight-v2",
        "valid": True,
        "file_count": len(observed),
        "preloaded_readback_target_count": 0,
    }


def decode_128bit_text(path: Path) -> bytes:
    lines = path.read_bytes().splitlines()
    if not lines:
        raise RuntimeErrorContract(f"empty 128-bit text: {path}")
    result = bytearray()
    for index, line in enumerate(lines, start=1):
        if len(line) != 128 or set(line) - {ord("0"), ord("1")}:
            raise RuntimeErrorContract(f"invalid 128-bit line: {path}:{index}")
        result.extend(int(line, 2).to_bytes(16, "little"))
    return bytes(result)


def write_128bit_text(path: Path, payload: bytes) -> None:
    if len(payload) % 16:
        raise RuntimeErrorContract(f"payload is not 16-byte aligned: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(
        format(int.from_bytes(payload[offset : offset + 16], "little"), "0128b")
        for offset in range(0, len(payload), 16)
    )
    path.write_text(text + "\n", encoding="ascii", newline="\n")


def materialize_tail_inputs(
    package_root: Path, cfg_root: Path
) -> dict[str, Any]:
    manifest = load_json(package_root / "package_manifest.json")
    records = manifest.get("tail_materialization")
    if not isinstance(records, list) or len(records) != 128:
        raise RuntimeErrorContract("tail materialization must contain 128 records")
    outputs: list[dict[str, Any]] = []
    for record in records:
        source = safe_child(cfg_root, str(record["conv_readback"]))
        destination = safe_child(cfg_root, str(record["tail_input"]))
        payload = decode_128bit_text(source)
        if len(payload) != 200704:
            raise RuntimeErrorContract(
                f"Conv readback length differs: {source}: {len(payload)}"
            )
        lane_half = int(record["lane_half"])
        if lane_half not in (0, 1):
            raise RuntimeErrorContract("lane_half must be 0 or 1")
        selected = b"".join(
            payload[offset + lane_half * 32 : offset + (lane_half + 1) * 32]
            for offset in range(0, len(payload), 64)
        )
        if len(selected) != 100352:
            raise RuntimeErrorContract("tail input length differs")
        write_128bit_text(destination, selected)
        outputs.append(
            {
                "source": str(record["conv_readback"]),
                "destination": str(record["tail_input"]),
                "sha256": sha256(destination),
                "size_bytes": len(selected),
            }
        )
    return {
        "schema": "node0004-hardware-accumulator-to-tail-replay-v2",
        "status": "pass",
        "arithmetic_performed": False,
        "operation": "HWC16 int32 byte relayout to selected HWC8 half",
        "outputs": outputs,
    }


def _status(path: Path) -> int:
    try:
        return int(path.read_text(encoding="ascii").strip())
    except (OSError, UnicodeError, ValueError) as error:
        raise RuntimeErrorContract(f"cannot parse execution status: {path}") from error


def analyze(
    package_root: Path, cfg_root: Path, evidence_root: Path
) -> dict[str, Any]:
    manifest = load_json(package_root / "package_manifest.json")
    records = _readback_records(manifest)
    compile_status = _status(evidence_root / "compile_exit_status.txt")
    run_status = _status(evidence_root / "run_exit_status.txt")
    checks: list[dict[str, Any]] = []
    mismatch_bytes = 0
    missing = 0
    for record in records:
        actual = safe_child(cfg_root, str(record["runtime_path"]))
        golden = safe_child(package_root, str(record["golden_path"]))
        if not actual.is_file():
            missing += 1
            checks.append({**record, "status": "missing"})
            continue
        actual_payload = decode_128bit_text(actual)
        golden_payload = decode_128bit_text(golden)
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
    passed = (
        compile_status == 0
        and run_status == 0
        and missing == 0
        and mismatch_bytes == 0
    )
    result = {
        "schema": "node0004-assumed-hardware-server-result-v2",
        "status": PASS_STATUS if passed else "NODE0004_SERVER_FAILURE",
        "execution_gate": {
            "compile_exit_status": compile_status,
            "run_exit_status": run_status,
            "compile_succeeded": compile_status == 0,
            "all_simulations_exited_zero": run_status == 0,
            "terminal_and_readback_gate_satisfied": passed,
        },
        "readback_count": len(records),
        "missing_count": missing,
        "mismatch_byte_count": mismatch_bytes,
        "checks": checks,
    }
    evidence_root.mkdir(parents=True, exist_ok=True)
    (evidence_root / "SERVER_RESULT_GATE.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def _copy_record(
    source: Path,
    return_dir: Path,
    relative: Path,
    allowlist: list[dict[str, Any]],
) -> None:
    if not source.is_file():
        return
    target = (return_dir / relative).resolve()
    if not target.is_relative_to(return_dir.resolve()):
        raise RuntimeErrorContract(f"return path escapes root: {relative}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())
    allowlist.append(
        {
            "path": relative.as_posix(),
            "size_bytes": target.stat().st_size,
            "sha256": sha256(target),
        }
    )


def collect(
    server_root: Path,
    install_name: str,
    evidence_root: Path,
    run_root: Path,
    cfg_root: Path,
    package_root: Path,
) -> dict[str, Any]:
    manifest = load_json(package_root / "package_manifest.json")
    records = _readback_records(manifest)
    return_dir = server_root / f"{install_name}_return"
    return_zip = return_dir.with_suffix(".zip")
    return_sha = Path(str(return_zip) + ".sha256")
    return_dir.mkdir(parents=True, exist_ok=False)
    allowlist: list[dict[str, Any]] = []

    for name in (
        "package_preflight.json",
        "install_preflight.json",
        "compile_exit_status.txt",
        "run_exit_status.txt",
        "SERVER_RESULT_GATE.json",
        "tail_materialization.json",
    ):
        _copy_record(
            evidence_root / name,
            return_dir,
            Path("evidence") / name,
            allowlist,
        )
    for relative in (
        Path("compile/sim_results/compile_driver.log"),
        Path("compile/sim_results/compile.log"),
    ):
        _copy_record(
            run_root / relative,
            return_dir,
            Path("runs") / relative,
            allowlist,
        )
    run_ids = [
        *manifest.get("conv_run_ids", []),
        *manifest.get("tail_run_ids", []),
    ]
    for run_id in run_ids:
        if not isinstance(run_id, str):
            raise RuntimeErrorContract("run id must be a string")
        _copy_record(
            safe_child(run_root, f"{run_id}/sim.log"),
            return_dir,
            Path("runs") / run_id / "sim.log",
            allowlist,
        )
    for record in records:
        relative = str(record["runtime_path"])
        _copy_record(
            safe_child(cfg_root, relative),
            return_dir,
            Path("readbacks") / Path(*PurePosixPath(relative).parts),
            allowlist,
        )

    allowlist_value = {
        "schema": "node0004-server-return-allowlist-v2",
        "install_name": install_name,
        "records": allowlist,
    }
    allowlist_path = return_dir / "RETURN_ALLOWLIST.json"
    allowlist_path.write_text(
        json.dumps(allowlist_value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    with zipfile.ZipFile(
        return_zip, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(item for item in return_dir.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(return_dir.parent).as_posix())
    digest = sha256(return_zip)
    return_sha.write_text(f"{digest}  {return_zip.name}\n", encoding="ascii")
    return {
        "zip": str(return_zip),
        "sha256": digest,
        "allowlisted_file_count": len(allowlist) + 1,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--package-root", type=Path, required=True)
    ins = sub.add_parser("verify-install")
    ins.add_argument("--package-root", type=Path, required=True)
    ins.add_argument("--cfg-root", type=Path, required=True)
    mat = sub.add_parser("materialize-tail")
    mat.add_argument("--package-root", type=Path, required=True)
    mat.add_argument("--cfg-root", type=Path, required=True)
    mat.add_argument("--output", type=Path, required=True)
    ana = sub.add_parser("analyze")
    ana.add_argument("--package-root", type=Path, required=True)
    ana.add_argument("--cfg-root", type=Path, required=True)
    ana.add_argument("--evidence-root", type=Path, required=True)
    col = sub.add_parser("collect")
    col.add_argument("--server-root", type=Path, required=True)
    col.add_argument("--install-name", required=True)
    col.add_argument("--evidence-root", type=Path, required=True)
    col.add_argument("--run-root", type=Path, required=True)
    col.add_argument("--cfg-root", type=Path, required=True)
    col.add_argument("--package-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "preflight":
        value = preflight(args.package_root)
    elif args.command == "verify-install":
        value = verify_install(args.package_root, args.cfg_root)
    elif args.command == "materialize-tail":
        value = materialize_tail_inputs(args.package_root, args.cfg_root)
        args.output.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    elif args.command == "analyze":
        value = analyze(args.package_root, args.cfg_root, args.evidence_root)
    else:
        value = collect(
            args.server_root,
            args.install_name,
            args.evidence_root,
            args.run_root,
            args.cfg_root,
            args.package_root,
        )
    print(json.dumps(value, ensure_ascii=False))
    if args.command == "analyze" and value["status"] != PASS_STATUS:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
