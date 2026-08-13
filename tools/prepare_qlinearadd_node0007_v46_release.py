"""Prepare v45 RETURN→v46 release receipts before storage rotation."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
NAME = "r5_qadd_n7_fullchain_returnfix_v46"
OUT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-fullchain-v46-returnfix-package"
)
ZIP = OUT / f"{NAME}.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-v45-return-analysis"
    / "report.json"
)
TASK = (
    ROOT
    / ".agents/task_records"
    / "20260807_qlinearadd_node0007_v45_return_v46_release.md"
)
RECEIPT_TARGET = (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    f"pending_receipts/qlinearadd_node0007/{NAME}/"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def file_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def main() -> int:
    sources = {
        "build_receipt": OUT / "build_receipt.json",
        "family_validation": OUT / "family_validation.json",
        "runtime_layout_harness": OUT / "runtime_layout_harness.json",
        "shared_runtime_layout_validation": OUT
        / "shared_runtime_layout_validation.json",
        "final_zip_self_audit": OUT / "final_zip_self_audit.json",
    }
    for key, source in sources.items():
        target = OUT / f"{NAME}.{key}.json"
        if target.exists():
            raise ValueError(f"release receipt target exists: {target}")
        shutil.copy2(source, target)
    audit = json.loads(sources["final_zip_self_audit"].read_text(encoding="utf-8"))
    if (
        audit.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS") is not True
        or audit.get("errors")
    ):
        raise ValueError("final ZIP audit is not releaseable")
    report_path = OUT / f"{NAME}.release_report.json"
    release = {
        "schema": "qlinearadd-node0007-v45-return-v46-release-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "package_id": NAME,
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "source_return_analysis": file_record(ANALYSIS),
        "source_v45": {
            "package_sha256": (
                "913e6831d47b9673f4c50e0efe28ba95fce14a2b685278c9e19755c5797f113a"
            ),
            "formal_return_sha256": (
                "3e0404ee7a88429859fc19bc275866d070a1a11c16faf9a21162be08a3f322f3"
            ),
            "disposition_after_rotation": "tested",
            "dynamic_status": (
                "PARTIAL_INTERRUPTED_EXTERNAL_HUP_WITH_PACKAGE_RETURN_"
                "CONTRACT_DEFECT"
            ),
        },
        "package": {
            "pending_path": (
                "artifacts/operator_config_validation/"
                "r5-server-test-packages/pending/"
                f"{NAME}.zip"
            ),
            "bytes": ZIP.stat().st_size,
            "sha256": sha256(ZIP),
            "sidecar_pending_receipt_path": RECEIPT_TARGET
            + f"{NAME}.zip.sha256",
        },
        "receipts_after_rotation": {
            key: RECEIPT_TARGET + f"{NAME}.{key}.json"
            for key in sources
        },
        "final_zip_rule_self_audit": {
            "pass": True,
            "errors": 0,
            "sha256": sha256(sources["final_zip_self_audit"]),
        },
        "server_command": (
            f"bash {NAME}/PREPARE_AND_RUN.sh "
            "/absolute/path/to/NDP_copy0x"
        ),
        "fixed_return": (
            f"/home/panqs/ndp/simresult/{NAME}_return.zip"
        ),
        "fixed_return_sidecar": (
            f"/home/panqs/ndp/simresult/{NAME}_return.zip.sha256"
        ),
        "semantic_scope": {
            "frozen": (
                "six-stage config/workload/numeric/W3/qparams/tail/golden/"
                "observer/8h timeout/functional RTL"
            ),
            "changed": (
                "identity, exact return source paths, package/source receipt, "
                "HUP/INT/TERM process/log liveness"
            ),
        },
        "blocker_delta": {
            "closed": "B_QADD_V45_RETURN_ALLOWLIST_SOURCE_PATH_DRIFT",
            "open_dynamic": [
                "B_QADD_FULLCHAIN_NATURAL_TERMINAL",
                "B_QADD_FULLCHAIN_FORMAL_UINT8_28D",
                "B_QADD_V45_FIRST_STAGE_QUALIFIED_PROGRESS_UNOBSERVED",
            ],
        },
        "rule_confirmation": (
            "CONFIRMED: current partial-return, continuous-closure, "
            "install-only, fixed-simresult, NDP-root direct-set, generated-"
            "heredoc and storage gates are necessary and sufficient for this "
            "runner/evidence-only successor."
        ),
        "numeric_analysis_repeated": False,
        "workload_config_golden_repeated": False,
        "server_action": False,
    }
    write_json(report_path, release)
    release_record = file_record(report_path)
    task = f"""# QLinearAdd node0007 v45 RETURN → v46 release

Date: 2026-08-07

## Provenance

- analysis_owner_thread: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return_target_thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- numeric/workload/config/golden repeated: `false`
- server action: `false`

## RETURN_ANALYSIS

- v45 return SHA256: `3e0404ee7a88429859fc19bc275866d070a1a11c16faf9a21162be08a3f322f3`
- CRC/root/exact-set/per-file receipts: PASS
- package/install preflight: PASS
- compile exit: `0`
- simulation exit: `125`
- signal: `HUP`
- natural terminal: `false`
- ordered stages: start `1`, finish `0`
- formal D: expected `28`, present `0`, missing `28`,
  mismatch_evaluable=`false`
- E3/E4/E5: `false/false/false`

The host sampler covered about 80.48 minutes. Its last about 43.48 minutes
repeated one unchanged `DEEP_MSE4_INDEX` level at sim time 16129418000.
That level is not qualified progress. Because the raw sim/observer logs were
not returned, the functional root cause remains bounded but not unique.

Machine report:
`{ANALYSIS.relative_to(ROOT).as_posix()}`  
SHA256: `{sha256(ANALYSIS)}`

## FIRST_DIVERGENCE

`op_a_dequant EXEC_START → first proven qualified progress/COMP_FINISH`,
terminated by external HUP.

The deterministic package-side defect is separate: v45 retained stale split-C
return source paths for compile/sim/observer and 28 final D files. It also
required receipts it never generated. Therefore v45 could not prove a full
result even if the DUT later completed.

## PACKAGE_RELEASE

- state: `PACKAGE_READY_NOT_RUN`
- identity: `{NAME}`
- pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/{NAME}.zip`
- bytes: `{ZIP.stat().st_size}`
- SHA256: `{sha256(ZIP)}`
- command: `bash {NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`
- fixed return: `/home/panqs/ndp/simresult/{NAME}_return.zip`

The six-stage config/workload/numeric/W3/qparams/tail/golden/observer, 8-hour
timeout and functional RTL are frozen. Only identity, return source paths,
source/package receipt and low-rate process/log liveness changed.

## Validation

- deterministic double build: PASS
- family validator: PASS
- shared exact-ZIP runtime validator: PASS
- generated heredoc syntax: PASS
- same-shell HUP/INT/TERM unit: PASS
- return-path and missing-receipt negatives: all fail closed
- package-local HDL: byte-equal receipt reuse
- FINAL_ZIP_RULE_SELF_AUDIT_PASS: `true`
- errors: `0`

Release report:
`{RECEIPT_TARGET}{NAME}.release_report.json`  
pre-rotation SHA256: `{release_record['sha256']}`

## BLOCKER_DELTA

- CLOSED: `B_QADD_V45_RETURN_ALLOWLIST_SOURCE_PATH_DRIFT`
- OPEN: full-chain natural terminal, exact UINT8 28D, and the bounded first
  stage qualified-progress interval.

## RULE_CONFIRMATION

Current partial-return, continuous-closure, install-only, fixed-simresult,
NDP-root direct-set, generated-heredoc and storage rules are confirmed. No
new synonymous rule is proposed.
"""
    TASK.write_text(task, encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "release_report": file_record(report_path),
                "task_record": file_record(TASK),
                "package_sha256": sha256(ZIP),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
