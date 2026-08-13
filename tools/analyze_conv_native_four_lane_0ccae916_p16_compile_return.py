#!/usr/bin/env python3
"""Adjudicate the formal p16 compile-failure receipt.

The server return itself remains on the server.  This analyzer binds the
operator-provided fixed-simresult receipt to the exact p16 source package and
the returned VCS XMRE excerpt.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p16_b5port"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{PACKAGE_ID}.zip"
)
SOURCE_SHA256 = (
    "b9dfb0d282013e45328c905c19957523afba81d505bbf5b4600dc82ace6c3611"
)
ATTACHMENT = Path(
    r"C:\Users\15383\.codex\attachments"
    r"\6b3ee168-49b0-4f52-9a95-1191927a0a46\pasted-text.txt"
)
ATTACHMENT_SHA256 = (
    "8aae4eef836a2a45a556c3df0d347a99fa5d5bb9ed328563306f00ea70e30ee2"
)
OUTPUT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p16_compile_return_analysis"
    / "report.json"
)


class AnalysisError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise AnalysisError(f"refusing to overwrite analysis: {path}")
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    if not SOURCE_ZIP.is_file() or sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise AnalysisError("exact p16 source ZIP differs or is absent")
    if not ATTACHMENT.is_file() or sha256(ATTACHMENT) != ATTACHMENT_SHA256:
        raise AnalysisError("exact operator-provided XMRE receipt differs")
    text = ATTACHMENT.read_text(encoding="utf-8", errors="replace")
    first = re.search(
        r"native_return_observer\.svh,\s*(\d+).*?"
        r"token '([^']+)'.*?Originating module\s+'([^']+)'",
        text,
        flags=re.DOTALL,
    )
    if first is None:
        raise AnalysisError("first XMRE receipt cannot be parsed")
    dynamic_group = len(
        re.findall(
            r"slice_with_datahub_mc_group_gen\[n4d_group_id\]", text
        )
    )
    dynamic_slice = len(
        re.findall(r"slice_group_gen\[n4d_local_slice_id\]", text)
    )
    if (
        first.group(2) != "slice_with_datahub_mc_group_gen"
        or first.group(3) != "tb_NDP_Top_new_phy"
        or dynamic_group == 0
        or dynamic_slice == 0
    ):
        raise AnalysisError("XMRE receipt does not bind the p16 escape")

    report = {
        "schema": (
            "conv-native-four-lane-0ccae916-p16-compile-return-analysis-v1"
        ),
        "status": "SUCCESSOR_REQUIRED_PACKAGE_LOCAL_OBSERVER_FIX",
        "classification": (
            "PACKAGE_LOCAL_OBSERVER_DYNAMIC_GENERATE_XMR_COMPILE_FAILURE"
        ),
        "source_package": {
            "identity": PACKAGE_ID,
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_ZIP.stat().st_size,
            "sha256": SOURCE_SHA256,
        },
        "formal_server_receipt": {
            "fixed_return_zip": (
                "/home/panqs/ndp/simresult/"
                "r5_n4_0cc_p16_b5port_return.zip"
            ),
            "return_zip_bytes": 791191,
            "return_zip_sha256": (
                "80521819781eacb2cd066e26c2095624527907c55e9f4e951a3c1de16af09192"
            ),
            "duplicate_absent": True,
            "publication_state": "ATOMIC_PUBLISHED_VERIFIED",
            "compile_exit_status": 2,
            "run_exit_status": 125,
            "signal_status": "NONE",
            "production_compile_started": True,
            "compile_succeeded": False,
            "dut_simulation_started": False,
            "formal_d_claimed": False,
        },
        "xmre_excerpt": {
            "path": str(ATTACHMENT),
            "bytes": ATTACHMENT.stat().st_size,
            "sha256": ATTACHMENT_SHA256,
            "first_source_line": int(first.group(1)),
            "first_token": first.group(2),
            "originating_module": first.group(3),
            "dynamic_group_reference_occurrences_in_excerpt": dynamic_group,
            "dynamic_slice_reference_occurrences_in_excerpt": dynamic_slice,
            "vcs_reported_error_count": 10,
            "make_compile_exit": 255,
        },
        "localization": {
            "last_proven_progress": (
                "production VCS parsed the package-local observer and reached "
                "cross-module-reference elaboration"
            ),
            "first_divergence": (
                "native_return_observer.svh line 1871 resolves Buffer5 public "
                "ports through generate arrays indexed by runtime integers"
            ),
            "root_cause": (
                "SystemVerilog hierarchical generate-array selection must be "
                "an elaboration-time constant; p16 used n4d_group_id and "
                "n4d_local_slice_id inside a procedural task/always path"
            ),
            "dut_or_config_implicated": False,
            "server_environment_implicated": False,
        },
        "claim_boundary": {
            "natural_terminal": False,
            "formal_320d": False,
            "numeric_failure": False,
            "e3": False,
            "e4": False,
            "e5": False,
        },
        "successor_contract": {
            "required": True,
            "identity": "fresh",
            "observer_fix": (
                "move all Buffer5 hierarchy references under genvar static "
                "assignments and let procedural code index local monitor arrays"
            ),
            "fresh_install_namespace": True,
            "frozen": [
                "workload",
                "numeric",
                "W3",
                "golden",
                "mapping",
                "bitstream",
                "execplan",
                "timeout",
                "functional RTL",
            ],
        },
        "rule_feedback": {
            "type": "RULE_CONFIRMATION",
            "confirmed": [
                "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
                "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            ],
            "delta": None,
        },
        "server_action": False,
    }
    write_json(OUTPUT, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
