from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


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


def package_records(root: Path, *, exclude_manifest: bool = True) -> dict[str, Any]:
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
    return {
        "schema": "node0004-assumed-hardware-package-preflight-v1",
        "valid": True,
        "file_count": len(observed),
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


def materialize_tail_inputs(package_root: Path, cfg_root: Path) -> dict[str, Any]:
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
        "schema": "node0004-hardware-accumulator-to-tail-replay-v1",
        "status": "pass",
        "arithmetic_performed": False,
        "operation": "HWC16 int32 byte relayout to selected HWC8 half",
        "outputs": outputs,
    }


def analyze(package_root: Path, cfg_root: Path, evidence_root: Path) -> dict[str, Any]:
    manifest = load_json(package_root / "package_manifest.json")
    records = manifest.get("readback_checks")
    if not isinstance(records, list):
        raise RuntimeErrorContract("readback check list is missing")
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
    result = {
        "schema": "node0004-assumed-hardware-server-result-v1",
        "status": (
            "THREE_PHASE_NODE0004_PASS"
            if missing == 0 and mismatch_bytes == 0
            else "NODE0004_SERVER_FAILURE"
        ),
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


def collect(
    server_root: Path,
    install_name: str,
    evidence_root: Path,
    run_root: Path,
    cfg_root: Path,
) -> dict[str, Any]:
    return_dir = server_root / f"{install_name}_return"
    return_zip = return_dir.with_suffix(".zip")
    return_sha = Path(str(return_zip) + ".sha256")
    return_dir.mkdir(parents=True, exist_ok=False)
    for source_root, prefix in (
        (evidence_root, "evidence"),
        (run_root, "runs"),
    ):
        if source_root.is_dir():
            for source in sorted(item for item in source_root.rglob("*") if item.is_file()):
                relative = Path(prefix) / source.relative_to(source_root)
                target = return_dir / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
    with zipfile.ZipFile(return_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(item for item in return_dir.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(return_dir.parent).as_posix())
    digest = sha256(return_zip)
    return_sha.write_text(f"{digest}  {return_zip.name}\n", encoding="ascii")
    return {"zip": str(return_zip), "sha256": digest}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    pre = sub.add_parser("preflight")
    pre.add_argument("--package-root", type=Path, required=True)
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
    args = parser.parse_args()
    if args.command == "preflight":
        value = preflight(args.package_root)
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
        )
    print(json.dumps(value, ensure_ascii=False))
    if args.command == "analyze" and value["status"] != "THREE_PHASE_NODE0004_PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
