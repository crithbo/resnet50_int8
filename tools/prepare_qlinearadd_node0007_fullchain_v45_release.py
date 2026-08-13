#!/usr/bin/env python3
"""Create the immutable v45 release report and storage-rotation source set."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_fullchain_v45"
PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-fullchain-v45-package"
)
ZIP = PACKAGE / f"{NAME}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
AUDIT = PACKAGE / "final_zip_self_audit.json"
FAMILY = PACKAGE / "family_validation.json"
SHARED = PACKAGE / "shared_runtime_layout_validation.json"
HARNESS = PACKAGE / "runtime_layout_harness.json"
BUILD = PACKAGE / "build_receipt.json"
LOCAL = ROOT / "artifacts/q38/build_receipt.json"
REPORT = PACKAGE / "release_report.json"
PUBLISH = PACKAGE / "publish_set"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def receipt(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    if REPORT.exists() or PUBLISH.exists():
        raise ValueError("release output already exists")
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    family = json.loads(FAMILY.read_text(encoding="utf-8"))
    shared = json.loads(SHARED.read_text(encoding="utf-8"))
    if (
        audit.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS") is not True
        or audit.get("errors") != []
        or family.get("valid") is not True
        or shared.get("pass") is not True
    ):
        raise ValueError("release gates are not closed")
    report = {
        "schema": "qlinearadd-node0007-fullchain-v45-release-v1",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "package_id": NAME,
        "package_release": "PACKAGE_READY_NOT_RUN",
        "classification": "CONFIG_ONLY_CORRECTNESS_BASELINE",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "server_action": False,
        "zip": receipt(ZIP),
        "sidecar": receipt(SIDECAR),
        "gates": {
            "six_stage_order": [
                "op_a_dequant",
                "op_b_dequant",
                "op_relocation_pad",
                "op_fp32_add",
                "op_tail_mul",
                "op_tail_round",
            ],
            "natural_terminal_required": True,
            "formal_uint8_D_expected": 28,
            "formal_D_initially_absent": True,
            "result_conjunction": (
                "compile0 AND simulation0 AND loader exact AND ordered6 "
                "AND natural terminal exact-once AND formal-D exact-set28 "
                "AND missing0 AND invalid0 AND mismatch0"
            ),
            "runtime_timeout": "8h",
        },
        "frozen_boundary": {
            "v37_split_c_32B_Buffer5_supply": True,
            "numeric_W3_qparams_tail_workload_config_golden": True,
            "DP_topology_and_Requant_strict_dependency": True,
            "observer_hdl_byte_equal_v37": True,
            "functional_rtl_modified": False,
            "numeric_analysis_repeated": False,
            "split_c_repeated": False,
        },
        "receipts": {
            "local_fullchain_assembly": receipt(LOCAL),
            "deterministic_build": receipt(BUILD),
            "family_validation": receipt(FAMILY),
            "runtime_layout_harness": receipt(HARNESS),
            "shared_runtime_layout_validation": receipt(SHARED),
            "final_zip_self_audit": receipt(AUDIT),
        },
        "runtime_layout": {
            "required_preexisting_server_entries": ["install"],
            "package_creates": ["install/cfg_pkg", "install/codex_runs"],
            "ndp_root_direct_name_type_exact_set_unchanged": True,
            "fixed_result_root": "/home/panqs/ndp/simresult",
            "expected_return": (
                "/home/panqs/ndp/simresult/"
                "r5_qadd_n7_fullchain_v45_return.zip"
            ),
            "expected_sidecar": (
                "/home/panqs/ndp/simresult/"
                "r5_qadd_n7_fullchain_v45_return.zip.sha256"
            ),
            "server_command": (
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02"
            ),
        },
        "local_harness_disposition": {
            "host_msys_full_runner_harness": "EXCLUDED_AFTER_BOUNDED_TERMINATION",
            "production_runner_bytes_changed_for_host": False,
            "replacement_receipt": (
                "shared install-only V2 14/14 changed-surface reuse plus "
                "exact-runner layout/compile/sim/trap/finalizer binding"
            ),
        },
        "blocker_delta": {
            "closed": [
                "B_QADD_NODE0007_SPLIT_C_32B_BUFFER5_SUPPLY_AND_STAGE_LOCAL_28D"
            ],
            "open": [
                "B_QADD_NODE0007_FULLCHAIN_PRODUCTION_NATURAL_TERMINAL_AND_UINT8_28D"
            ],
        },
        "rule_confirmation": {
            "status": "RULE_CONFIRMATION",
            "text": (
                "Current install-subtree V2, fixed-simresult, NDP-root "
                "top-level, final-ZIP self-audit, QLinearAdd and storage "
                "rotation rules are sufficient; no non-synonymous delta."
            ),
        },
        "claim_boundary": (
            "Package-local E2 only. No production compile, DUT simulation, "
            "natural terminal, formal returned 28D, E3, E4 or E5 claim."
        ),
    }
    write_json(REPORT, report)
    PUBLISH.mkdir()
    sources = {
        f"{NAME}.zip": ZIP,
        f"{NAME}.zip.sha256": SIDECAR,
        f"{NAME}.build_receipt.json": BUILD,
        f"{NAME}.family_validation.json": FAMILY,
        f"{NAME}.runtime_layout_harness.json": HARNESS,
        f"{NAME}.shared_runtime_layout_validation.json": SHARED,
        f"{NAME}.final_zip_self_audit.json": AUDIT,
        f"{NAME}.release_report.json": REPORT,
    }
    for target_name, source in sources.items():
        shutil.copy2(source, PUBLISH / target_name)
    print(
        json.dumps(
            {
                "package_release": "PACKAGE_READY_NOT_RUN",
                "zip": receipt(ZIP),
                "release_report": receipt(REPORT),
                "publish_members": sorted(sources),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
