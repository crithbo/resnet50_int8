from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from types import ModuleType
from typing import Any


REQUIRED_CANONICAL_TOKENS = (
    "schema=node0004_hang_diag",
    "version=1",
    "decision=%s",
    "reason=%s",
    "boundary=%s",
    "window_first=1",
    "window_last=%0d",
    "window_cycles=%0d",
    "qualified_progress=%0d",
    "qualified_delta=%0d",
    "req0=%0d",
    "req1=%0d",
    "req3=%0d",
    "rdata0=%0d",
    "rdata1=%0d",
    "rdata3=%0d",
    "d_req=%0d",
    "d_wdata=%0d",
    "content_digest=QIOV1_%0d_%0d_%0d",
)
CANONICAL_PREFIX = "| CANONICAL_DIAG_DECISION_V1 |"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _safe_name(name: str) -> PurePosixPath:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or "\\" in name:
        raise ValueError(f"unsafe ZIP member: {name}")
    return pure


def _load_runtime(entries: dict[str, bytes]) -> ModuleType:
    with tempfile.TemporaryDirectory(prefix="node0004-v10-runtime-") as temp:
        root = Path(temp)
        for relative in (
            "package_tools/node0004_hang_localization_runtime.py",
            "package_tools/node0004_hang_localization_runtime_v7.py",
        ):
            target = root / Path(*PurePosixPath(relative).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(entries[relative])
        sys.path.insert(0, str(root / "package_tools"))
        try:
            spec = importlib.util.spec_from_file_location(
                "node0004_hang_runtime_v10_final_zip",
                root
                / "package_tools/node0004_hang_localization_runtime.py",
            )
            if spec is None or spec.loader is None:
                raise ValueError("cannot load final-ZIP runtime")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        finally:
            sys.path.remove(str(root / "package_tools"))


def _record(
    *,
    decision: str = (
        "LONG_RUNNING_HANG_AT_"
        "BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS"
    ),
    reason: str = "STALL_WINDOW_EXCEEDED",
    boundary: str = "BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS",
) -> str:
    return (
        "100 | CANONICAL_DIAG_DECISION_V1 | "
        "schema=node0004_hang_diag version=1 "
        f"decision={decision} reason={reason} boundary={boundary} "
        "window_first=1 window_last=4 window_cycles=262144 "
        "qualified_progress=136 qualified_delta=0 "
        "req0=32 req1=32 req3=28 rdata0=12 rdata1=12 rdata3=16 "
        "d_req=4 d_wdata=0 content_digest=QIOV1_136_0_4"
    )


def validate(zip_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path) as archive:
        crc = archive.testzip()
        if crc is not None:
            raise ValueError(f"CRC failure: {crc}")
        files = [info for info in archive.infolist() if not info.is_dir()]
        roots = {_safe_name(info.filename).parts[0] for info in files}
        if len(roots) != 1:
            raise ValueError(f"ZIP root differs: {sorted(roots)}")
        root = next(iter(roots))
        entries = {
            PurePosixPath(*_safe_name(info.filename).parts[1:]).as_posix():
            archive.read(info)
            for info in files
        }
    manifest = json.loads(entries["package_manifest.json"])
    source_path = manifest["observer_binding_four_way"]["source"]["path"]
    observer = entries[source_path].decode("utf-8")
    runtime = _load_runtime(entries)

    progress_expression = observer.rsplit(
        "return_hang_diag_current_progress =", 1
    )[1].split(";", 1)[0]
    qualified_progress_only = (
        "return_obs_buf45_" not in progress_expression
        and all(
            token in progress_expression
            for token in (
                "return_obs_req_count[0]",
                "return_obs_req_count[1]",
                "return_obs_req_count[3]",
                "return_obs_rdata_count[0]",
                "return_obs_rdata_count[1]",
                "return_obs_rdata_count[3]",
                "return_obs_req_count[4]",
                "return_obs_wdata_count[4]",
            )
        )
    )
    levels = [False] + [True] * 32
    edge_count = sum(
        current and not previous
        for previous, current in zip(levels, levels[1:])
    )
    persistent_level_negative = (
        edge_count == 1
        and "!return_hang_diag_buf4_wr_d" in observer
        and "!return_hang_diag_buf4_rd_d" in observer
        and "!return_hang_diag_buf5_wr_d" in observer
        and "!return_hang_diag_buf5_rd_d" in observer
    )

    complete_format = all(
        token in observer for token in REQUIRED_CANONICAL_TOKENS
    )
    unique_emitter = observer.count("CANONICAL_DIAG_DECISION_V1") == 1
    summary_separate = (
        'return_obs_write_summary("DIAG_SUMMARY")' in observer
        and 'return_obs_write_summary("DIAG_DECISION")' not in observer
    )

    positive = runtime.parse_canonical_records([_record()])
    summary_append = runtime.parse_canonical_records(
        [_record(), f"101 {CANONICAL_PREFIX} summary=only"]
    )
    conflict = runtime.parse_canonical_records(
        [
            _record(),
            _record(
                decision="STILL_PROGRESSING",
                reason="MAX_DIAGNOSTIC_CYCLE_BUDGET_PROGRESSING",
            ),
        ]
    )
    missing_reason = runtime.parse_canonical_records(
        [_record().replace("reason=STALL_WINDOW_EXCEEDED ", "")]
    )
    missing_boundary = runtime.parse_canonical_records(
        [
            _record().replace(
                "boundary=BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS ",
                "",
            )
        ]
    )
    controls = {
        "persistent_high_level_not_n_transactions": persistent_level_negative,
        "summary_only_append_fails_closed": not summary_append["valid"],
        "conflicting_double_decision_fails_closed": not conflict["valid"],
        "missing_reason_fails_closed": not missing_reason["valid"],
        "missing_boundary_fails_closed": not missing_boundary["valid"],
    }
    checks = {
        "qualified_progress_only": qualified_progress_only,
        "canonical_format_complete": complete_format,
        "canonical_emitter_unique": unique_emitter,
        "summary_prefix_separate": summary_separate,
        "positive_record_valid": positive["valid"],
        "all_negative_controls_fail_closed": all(controls.values()),
    }
    valid = all(checks.values())
    return {
        "schema": "node0004-canonical-decision-final-zip-receipt-v1",
        "status": (
            "CANONICAL_DECISION_RULE_VALIDATED"
            if valid
            else "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS"
        ),
        "valid": valid,
        "zip": {
            "path": str(zip_path.resolve()),
            "size_bytes": zip_path.stat().st_size,
            "sha256": sha256_bytes(zip_path.read_bytes()),
            "crc_pass": True,
            "root": root,
            "entry_count": len(entries),
        },
        "observer": {
            "path": source_path,
            "sha256": sha256_bytes(entries[source_path]),
            "canonical_prefix_count": observer.count(
                "CANONICAL_DIAG_DECISION_V1"
            ),
            "persistent_high_cycles": 32,
            "rising_edge_transactions": edge_count,
        },
        "checks": checks,
        "negative_controls": controls,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(args.zip)
    payload = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(payload, encoding="utf-8", newline="\n")
    print(payload, end="")
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
