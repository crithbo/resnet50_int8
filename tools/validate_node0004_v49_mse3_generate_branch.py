from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path


INSTALL_NAME = "r5_n4_hw_v49_lc9_actual_compilefix"
BEGIN = "// v49 LC9_ACTUAL_COMPILEFIX_TRIGGERED_BEGIN"
END = "// v49 LC9_ACTUAL_COMPILEFIX_TRIGGERED_END"
OLD_BRANCH = "MSE_INST[3].WR_MSE.u_Memory_WR_Stream_Engine"
NEW_BRANCH = "MSE_INST[3].RD_MSE.u_Memory_RD_Stream_Engine"
STREAM_ENGINE_SHA256 = (
    "a8718b4c4b043ffbf8c2bd59842ac677f18861783d70ce5eaa3d809c79ac6365"
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def adjudicate(
    observer: str,
    stream_engine: str,
    *,
    require_occurrences: int = 15,
) -> tuple[bool, list[str], dict[str, object]]:
    errors: list[str] = []
    if observer.count(BEGIN) != 1 or observer.count(END) != 1:
        errors.append("v49 observer span marker differs")
        block = ""
    else:
        block = observer[
            observer.index(BEGIN) : observer.index(END) + len(END)
        ]
    rd_generate = re.search(
        r"for\s*\(MSE_IDX\s*=\s*0;.*?begin\s*:\s*MSE_INST"
        r".*?if\s*\(MSE_IDX\s*<\s*`MEMORY_RD_STREAM_ENGINE_NUM\)"
        r"\s*begin\s*:\s*RD_MSE"
        r".*?Memory_RD_Stream_Engine\s+u_Memory_RD_Stream_Engine\s*\(",
        stream_engine,
        re.DOTALL,
    )
    wr_generate = re.search(
        r"else\s+begin\s*:\s*WR_MSE"
        r".*?Memory_WR_Stream_Engine\s+u_Memory_WR_Stream_Engine\s*\(",
        stream_engine,
        re.DOTALL,
    )
    new_count = block.count(NEW_BRANCH)
    old_count = block.count(OLD_BRANCH)
    sibling_wrong = "MSE_INST[4].RD_MSE.u_Memory_RD_Stream_Engine" in block
    if rd_generate is None or wr_generate is None:
        errors.append("current Stream_Engine generate equation differs")
    if new_count != require_occurrences:
        errors.append("MSE3 RD_MSE occurrence count differs")
    if old_count != 0:
        errors.append("stale MSE3 WR_MSE path remains")
    if sibling_wrong:
        errors.append("wrong MSE4 RD_MSE sibling path present")
    summary = {
        "expected_branch": "RD_MSE",
        "expected_instance": "u_Memory_RD_Stream_Engine",
        "mse_index": 3,
        "rd_path_occurrences": new_count,
        "wr_path_occurrences": old_count,
        "current_rtl_generate_rd_found": rd_generate is not None,
        "current_rtl_generate_wr_found": wr_generate is not None,
    }
    return not errors, errors, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--stream-engine", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with zipfile.ZipFile(args.zip) as archive:
        observer_bytes = archive.read(
            f"{INSTALL_NAME}/tb_probe/native_return_observer.svh"
        )
    stream_bytes = args.stream_engine.read_bytes()
    observer = observer_bytes.decode()
    stream_engine = stream_bytes.decode()
    positive, positive_errors, summary = adjudicate(observer, stream_engine)
    wrong_branch, _, _ = adjudicate(
        observer.replace(NEW_BRANCH, OLD_BRANCH, 1),
        stream_engine,
    )
    missing_branch, _, _ = adjudicate(
        observer.replace(NEW_BRANCH, "", 1),
        stream_engine,
    )
    wrong_sibling, _, _ = adjudicate(
        observer.replace(
            NEW_BRANCH,
            "MSE_INST[4].RD_MSE.u_Memory_RD_Stream_Engine",
            1,
        ),
        stream_engine,
    )
    stale_rtl, _, _ = adjudicate(
        observer,
        stream_engine.replace(
            "Memory_RD_Stream_Engine u_Memory_RD_Stream_Engine",
            "Memory_RD_Stream_Engine u_Memory_RD_Stream_Engine_TYPO",
            1,
        ),
    )
    checks = {
        "stream_engine_sha": sha256(stream_bytes) == STREAM_ENGINE_SHA256,
        "positive_actual_generate_branch": positive,
        "wrong_branch_fail_closed": not wrong_branch,
        "missing_branch_fail_closed": not missing_branch,
        "wrong_sibling_fail_closed": not wrong_sibling,
        "rtl_generate_name_drift_fail_closed": not stale_rtl,
    }
    report = {
        "schema": "node0004-v49-mse3-generate-branch-validation-v1",
        "valid": all(checks.values()),
        "errors": [
            *positive_errors,
            *[name for name, passed in checks.items() if not passed],
        ],
        "checks": checks,
        "observer": {
            "bytes": len(observer_bytes),
            "sha256": sha256(observer_bytes),
        },
        "stream_engine": {
            "path": str(args.stream_engine.resolve()),
            "bytes": len(stream_bytes),
            "sha256": sha256(stream_bytes),
            "generate_for_line": 448,
            "read_branch_line": 449,
            "write_branch_line": 506,
        },
        "positive": summary,
        "negative_controls": {
            "wrong_branch_WR_MSE": not wrong_branch,
            "missing_RD_MSE": not missing_branch,
            "wrong_sibling_MSE4": not wrong_sibling,
            "rtl_generate_name_drift": not stale_rtl,
        },
        "claim_boundary": (
            "Exact final observer MSE3 hierarchy checked against the current "
            "0cc Stream_Engine generate equation. This is focused scope/name "
            "resolution, not full-design VCS elaboration or DUT simulation."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
