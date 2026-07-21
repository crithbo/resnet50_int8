from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_execplan_hardware import (
    ConvHardwareExecplanError,
    assemble_conv_hardware_region_dump,
    compare_conv_hardware_bank_dump,
    validate_conv_hardware_repeated_region_returns,
)  # noqa: E402


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _extract_return_archive(
    archive_path: Path,
    destination: Path,
    *,
    expected_run_id: str,
) -> tuple[Path, dict[str, object]]:
    archive_file = archive_path.resolve()
    if not archive_file.is_file():
        raise ConvHardwareExecplanError(
            f"server return ZIP is missing: {archive_file}"
        )
    destination.mkdir(parents=True, exist_ok=False)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive_file) as archive:
        infos = archive.infolist()
        if not infos:
            raise ConvHardwareExecplanError("server return ZIP is empty")
        seen: set[str] = set()
        roots: set[str] = set()
        prepared: list[tuple[zipfile.ZipInfo, tuple[str, ...]]] = []
        for info in infos:
            raw_name = info.filename
            if (
                not raw_name
                or "\\" in raw_name
                or "\x00" in raw_name
                or raw_name.startswith("/")
            ):
                raise ConvHardwareExecplanError(
                    f"unsafe server return ZIP entry: {raw_name!r}"
                )
            logical = PurePosixPath(raw_name)
            parts = logical.parts
            if (
                not parts
                or any(part in {"", ".", ".."} for part in parts)
                or ":" in parts[0]
                or logical.as_posix() != raw_name.rstrip("/")
            ):
                raise ConvHardwareExecplanError(
                    f"unsafe server return ZIP entry: {raw_name!r}"
                )
            normalized = logical.as_posix()
            if normalized in seen:
                raise ConvHardwareExecplanError(
                    f"duplicate server return ZIP entry: {normalized}"
                )
            seen.add(normalized)
            roots.add(parts[0])
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            file_type = stat.S_IFMT(unix_mode)
            if info.is_dir():
                if file_type not in (0, stat.S_IFDIR):
                    raise ConvHardwareExecplanError(
                        f"non-directory ZIP object uses a directory name: {normalized}"
                    )
            elif file_type not in (0, stat.S_IFREG):
                raise ConvHardwareExecplanError(
                    f"server return ZIP contains a non-regular object: {normalized}"
                )
            prepared.append((info, parts))
        if len(roots) != 1:
            raise ConvHardwareExecplanError(
                f"server return ZIP must contain one root directory: {sorted(roots)}"
            )
        for info, parts in prepared:
            target = destination.joinpath(*parts)
            if not target.resolve().is_relative_to(destination_root):
                raise ConvHardwareExecplanError(
                    f"server return ZIP entry escapes extraction root: {info.filename}"
                )
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)

    return_root = destination / next(iter(roots))
    metadata_path = return_root / "run_metadata.json"
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConvHardwareExecplanError(
            f"server return ZIP lacks readable run_metadata.json: {metadata_path}"
        ) from exc
    if not isinstance(metadata, dict) or metadata.get("server_run_id") != expected_run_id:
        raise ConvHardwareExecplanError(
            "server return ZIP run ID differs: "
            f"expected={expected_run_id} observed={metadata.get('server_run_id') if isinstance(metadata, dict) else None}"
        )
    return return_root, {
        "kind": "return_zip",
        "archive_name": archive_file.name,
        "archive_size_bytes": archive_file.stat().st_size,
        "archive_sha256": _sha256(archive_file),
        "archive_root": return_root.name,
        "server_run_id": expected_run_id,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the fail-closed server return, assemble complete SCA_D semantic "
            "regions into Bank00 images, and run the frozen Conv P/D comparison."
        )
    )
    parser.add_argument("--package", type=Path, required=True)
    run1_source = parser.add_mutually_exclusive_group(required=True)
    run1_source.add_argument(
        "--readback-root-run1",
        type=Path,
        help="extracted run1 return root containing run_metadata.json",
    )
    run1_source.add_argument(
        "--return-zip-run1",
        type=Path,
        help="raw run1 return ZIP; safely extracted below the evidence root",
    )
    run2_source = parser.add_mutually_exclusive_group(required=True)
    run2_source.add_argument(
        "--readback-root-run2",
        type=Path,
        help="extracted run2 return root containing run_metadata.json",
    )
    run2_source.add_argument(
        "--return-zip-run2",
        type=Path,
        help="raw run2 return ZIP; safely extracted below the evidence root",
    )
    parser.add_argument(
        "--runtime-identity",
        type=Path,
        required=True,
        help="locally approved runtime_identity.json used to build the server run",
    )
    parser.add_argument("--evidence-root", type=Path, required=True)
    args = parser.parse_args()

    evidence = args.evidence_root.resolve()
    if evidence.exists() and any(evidence.iterdir()):
        raise ConvHardwareExecplanError(
            f"evidence directory is not empty; refusing to mix runs: {evidence}"
        )
    evidence.mkdir(parents=True, exist_ok=True)
    return_sources: dict[str, dict[str, object]] = {}
    if args.return_zip_run1 is not None:
        run1_root, return_sources["run1"] = _extract_return_archive(
            args.return_zip_run1,
            evidence / "returned_archives" / "run1",
            expected_run_id="run1",
        )
    else:
        run1_root = args.readback_root_run1.resolve()
        return_sources["run1"] = {
            "kind": "extracted_directory",
            "root_name": run1_root.name,
            "server_run_id": "run1",
        }
    if args.return_zip_run2 is not None:
        run2_root, return_sources["run2"] = _extract_return_archive(
            args.return_zip_run2,
            evidence / "returned_archives" / "run2",
            expected_run_id="run2",
        )
    else:
        run2_root = args.readback_root_run2.resolve()
        return_sources["run2"] = {
            "kind": "extracted_directory",
            "root_name": run2_root.name,
            "server_run_id": "run2",
        }
    repeated_return_gate = validate_conv_hardware_repeated_region_returns(
        args.package,
        {
            "run1": run1_root,
            "run2": run2_root,
        },
        args.runtime_identity,
    )
    return_gate = repeated_return_gate["return_gates"]["run1"]
    adapter = assemble_conv_hardware_region_dump(
        args.package,
        run1_root,
        evidence / "assembled_bank_dump",
        validated_region_receipt=return_gate["validated_region_receipt"],
    )
    comparison = compare_conv_hardware_bank_dump(
        ROOT,
        args.package,
        evidence / "assembled_bank_dump",
        evidence / "comparison",
    )
    report = {
        "schema_version": "resnet50-conv-hardware-region-comparison-0.2",
        "status": "passed" if comparison.get("status") == "passed" else "failed",
        "return_sources": return_sources,
        "repeated_return_gate": repeated_return_gate,
        "adapter": adapter,
        "comparison": comparison,
    }
    (evidence / "region_comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
