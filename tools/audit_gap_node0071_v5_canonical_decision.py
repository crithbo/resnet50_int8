from __future__ import annotations

import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n71_gap_v5_obsbind.zip"
)
EXPECTED_SHA256 = (
    "159bebac586be3a40ae937736b0368593ced34c7b8128fde7858930b53ebef8d"
)
ROOT_NAME = "r5_n71_gap_v5_obsbind"
OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n71_gap_v5_obsbind.quarantine.json"
)
SERVER_RULE_SHA256 = (
    "ed3990f13c62ce67e5081458b0dfdcf6ca257908fe138fcc05a7000482afd2f8"
)
PLAN_SHA256 = (
    "21dec7853cf9dc1610e51ede1366550b390bfc301d8dc8d5bf6c560d5ecae545"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_files(archive: zipfile.ZipFile) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in info.filename
            or info.filename in files
            or (mode and stat.S_ISLNK(mode))
        ):
            raise ValueError(f"unsafe ZIP member: {info.filename}")
        if not info.is_dir():
            files[info.filename] = archive.read(info)
    return files


def analyze() -> dict[str, Any]:
    if sha256(ZIP) != EXPECTED_SHA256:
        raise ValueError("v5 ZIP identity differs")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise ValueError("v5 ZIP CRC differs")
        files = safe_files(archive)
    prefix = f"{ROOT_NAME}/"
    manifest = json.loads(
        files[prefix + "TEST_PACKAGE_MANIFEST.json"].decode("utf-8")
    )
    contract = json.loads(
        files[prefix + "diagnostics/progress_contract.json"].decode("utf-8")
    )
    observer = files[
        prefix + "tb_probe/native_return_observer.svh"
    ].decode("utf-8")
    allowlist = manifest.get("return_allowlist", [])
    targets = {
        item.get("target_path")
        for item in allowlist
        if isinstance(item, dict)
    }
    monotonic = set(contract.get("monotonic_counters", []))
    unqualified = sorted(
        monotonic
        & {
            "buf4_wr",
            "buf4_rd",
            "buf5_wr",
            "buf5_rd",
            "deep_addr_enqueue",
            "deep_meta",
            "deep_consume",
            "deep_buffer",
            "deep_ga",
            "deep_mse4_idx",
            "sg_ga_input",
            "sg_ga_output",
        }
    )
    level_witness = {
        "buf45_wr_incremented_from_level_enable": (
            "if (|return_obs_buf45_wr_en_mon" in observer
            and "return_obs_buf45_wr_count[slot]++" in observer
        ),
        "buf45_rd_incremented_from_level_enable": (
            "if (|return_obs_buf45_rd_en_mon" in observer
            and "return_obs_buf45_rd_count[slot]++" in observer
        ),
        "sg_ga_input_incremented_from_valid_level": (
            "return_obs_ga_input_valid_mon" in observer
            and "return_obs_sg_ga_input_count++" in observer
        ),
        "sg_ga_output_incremented_from_valid_level": (
            "return_obs_ga_ob_valid_mon" in observer
            and "return_obs_sg_ga_output_count++" in observer
        ),
    }
    canonical_targets = {
        target
        for target in targets
        if isinstance(target, str) and "canonical_decision" in target
    }
    canonical_tools = [
        name for name in files if "canonical_decision" in name
    ]
    failures = [
        "monotonic progress includes level/unqualified counters",
        "no unique complete canonical decision generator/parser",
        "no canonical decision return allowlist target",
        "no canonical decision negative-control receipt",
    ]
    return {
        "schema":
            "gap-node0071-v5-canonical-decision-receipt-audit-v1",
        "status": "QUARANTINED_PACKAGE_DIAGNOSTIC_DECISION_NONCANONICAL",
        "package_zip": str(ZIP.relative_to(ROOT).as_posix()),
        "package_sha256": EXPECTED_SHA256,
        "zip_crc_valid": True,
        "zip_member_count": len(files),
        "decision": "CANONICAL_DECISION_RULE_NOT_SATISFIED",
        "qualified_progress": {
            "pass": False,
            "declared_monotonic_counters": sorted(monotonic),
            "unqualified_or_level_counters": unqualified,
            "source_witness": level_witness,
        },
        "canonical_record": {
            "pass": False,
            "package_members": canonical_tools,
            "return_allowlist_targets": sorted(canonical_targets),
            "required_fields": [
                "schema/version",
                "decision",
                "reason",
                "boundary",
                "sample/window range",
                "qualified counter snapshot/delta",
                "content digest",
            ],
        },
        "negative_controls": {
            "pass": False,
            "continuous_high_level": "ABSENT",
            "summary_only_append": "ABSENT",
            "conflicting_double_decision": "ABSENT",
            "missing_reason": "ABSENT",
            "missing_boundary": "ABSENT",
        },
        "failures": failures,
        "package_action": {
            "v5_zip_modified": False,
            "v5_status": "QUARANTINED_DO_NOT_RUN",
            "successor_required": True,
        },
        "rule_receipts": {
            "server_rule_sha256": SERVER_RULE_SHA256,
            "plan_sha256_mutable_provenance_only": PLAN_SHA256,
            "rule_id":
                "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
            "default_progress_rule":
                "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
        },
        "numeric_analysis_repeated": False,
        "workload_reexecuted": False,
    }


def main() -> int:
    result = analyze()
    OUTPUT.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
