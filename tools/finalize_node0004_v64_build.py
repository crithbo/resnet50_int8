from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path


import tools.build_node0004_v63_dskew_successor_v64 as builder


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--output-root", required=True, type=Path)
    args = p.parse_args()
    output = args.output_root.resolve()
    zip_path = output / f"{builder.INSTALL}.zip"
    sidecar = output / f"{builder.INSTALL}.zip.sha256"
    report_path = output / f"{builder.INSTALL}.validation.json"
    if not zip_path.is_file() or zip_path.stat().st_size == 0:
        raise builder.BuildError("primary v64 ZIP missing/incomplete")
    if sidecar.exists() or report_path.exists():
        raise builder.BuildError("refusing to overwrite v64 finalization receipts")
    digest = builder.base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v64-repeat-") as temp:
        repeat = builder.build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{builder.INSTALL}.zip"
        builder.base.deterministic_zip(repeat, repeat_zip)
        repeat_digest = builder.base.sha256(repeat_zip)
    deterministic = repeat_digest == digest
    if not deterministic:
        raise builder.BuildError(
            f"v64 deterministic rebuild differs:{digest}:{repeat_digest}"
        )
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report = {
        "schema": "node0004-v63-to-v64-dskew-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_AUDITS",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": True,
        "source_v63_sha256": builder.SOURCE_SHA,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "recovery_note": (
            "The initial caller timed out after writing the complete primary "
            "ZIP; this independent finalizer performed the required fresh "
            "second build and exact digest comparison."
        ),
    }
    builder.base.write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
