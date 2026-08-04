from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any


try:
    import node0004_assumed_hardware_server_runtime_v2_base as base
except ImportError:
    from tools import node0004_assumed_hardware_server_runtime_v2 as base


OBSERVER_RECEIPT = "observer_precompile.json"
OBSERVER_LOG = "return_observer.log"
OBSERVER_LOG_MAX_BYTES = 8 * 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_allowlisted(
    source: Path,
    target: Path,
    relative: str,
    records: list[dict[str, Any]],
) -> None:
    if not source.is_file():
        return
    if source.stat().st_size > OBSERVER_LOG_MAX_BYTES:
        raise base.RuntimeErrorContract(
            f"observer evidence exceeds 8 MiB: {source}"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    records.append(
        {
            "path": relative,
            "size_bytes": target.stat().st_size,
            "sha256": _sha256(target),
        }
    )


def _repack_return(
    *,
    return_dir: Path,
    return_zip: Path,
    return_sha: Path,
) -> dict[str, Any]:
    allowlist_path = return_dir / "RETURN_ALLOWLIST.json"
    allowlist = base.load_json(allowlist_path)
    records = allowlist.get("records")
    if not isinstance(records, list):
        raise base.RuntimeErrorContract("return allowlist records are missing")
    paths = [str(record.get("path")) for record in records]
    if len(paths) != len(set(paths)):
        raise base.RuntimeErrorContract("return allowlist paths are duplicated")
    records.sort(key=lambda item: str(item["path"]))
    allowlist_path.write_text(
        json.dumps(allowlist, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if return_zip.exists():
        return_zip.unlink()
    with zipfile.ZipFile(
        return_zip, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(
            item for item in return_dir.rglob("*") if item.is_file()
        ):
            archive.write(path, path.relative_to(return_dir.parent).as_posix())
    digest = _sha256(return_zip)
    return_sha.write_text(
        f"{digest}  {return_zip.name}\n", encoding="ascii", newline="\n"
    )
    return {
        "zip": str(return_zip),
        "sha256": digest,
        "allowlisted_file_count": len(records) + 1,
        "observer_precompile_receipt_returned": True,
        "observer_runtime_logs_returned": sum(
            path.endswith(f"/{OBSERVER_LOG}") for path in paths
        ),
    }


def collect(
    server_root: Path,
    install_name: str,
    evidence_root: Path,
    run_root: Path,
    cfg_root: Path,
    package_root: Path,
) -> dict[str, Any]:
    manifest = base.load_json(package_root / "package_manifest.json")
    base.collect(
        server_root,
        install_name,
        evidence_root,
        run_root,
        cfg_root,
        package_root,
    )
    return_dir = server_root / f"{install_name}_return"
    return_zip = return_dir.with_suffix(".zip")
    return_sha = Path(str(return_zip) + ".sha256")
    allowlist_path = return_dir / "RETURN_ALLOWLIST.json"
    allowlist = base.load_json(allowlist_path)
    records = allowlist.get("records")
    if not isinstance(records, list):
        raise base.RuntimeErrorContract("return allowlist records are missing")

    _copy_allowlisted(
        evidence_root / OBSERVER_RECEIPT,
        return_dir / "evidence" / OBSERVER_RECEIPT,
        f"evidence/{OBSERVER_RECEIPT}",
        records,
    )
    run_ids = [
        *manifest.get("conv_run_ids", []),
        *manifest.get("tail_run_ids", []),
    ]
    for run_id in run_ids:
        if not isinstance(run_id, str):
            raise base.RuntimeErrorContract("run id must be a string")
        relative = f"runs/{run_id}/{OBSERVER_LOG}"
        _copy_allowlisted(
            run_root / run_id / OBSERVER_LOG,
            return_dir / "runs" / run_id / OBSERVER_LOG,
            relative,
            records,
        )
    return _repack_return(
        return_dir=return_dir,
        return_zip=return_zip,
        return_sha=return_sha,
    )


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
        value = base.preflight(args.package_root)
    elif args.command == "verify-install":
        value = base.verify_install(args.package_root, args.cfg_root)
    elif args.command == "materialize-tail":
        value = base.materialize_tail_inputs(args.package_root, args.cfg_root)
        args.output.write_text(
            json.dumps(value, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    elif args.command == "analyze":
        value = base.analyze(
            args.package_root, args.cfg_root, args.evidence_root
        )
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
    if args.command == "analyze" and value.get("status") != base.PASS_STATUS:
        return 1
    return 0


if __name__ == "__main__":
    sys.dont_write_bytecode = True
    raise SystemExit(main())
