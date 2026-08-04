from __future__ import annotations

import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.qlinearadd_progress_canonical_decision import (
    CanonicalDecisionError,
    decide,
    load_unique_record,
)


INSTALL_NAME = "r5_qadd_n7_progress_canon_v7"
SOURCE_NAME = "r5_qadd_n7_nested_lc_progress_bind_v6"
PACKAGE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
)
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = ZIP_PATH.with_suffix(".zip.sha256")
ZIP_SHA256 = (
    "1ed2ed3cb1015e62b585a77dbff0b82b45e592a27695ddd9331b47eb1196df1f"
)
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = (
    "9a48fb417b34afaa0835f8ee0bab8bb22a337808fb6e88d9e9b1205922f1ce90"
)
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
SERVER_RULE_SHA256 = (
    "ed3990f13c62ce67e5081458b0dfdcf6ca257908fe138fcc05a7000482afd2f8"
)
CANONICAL_REL = "package_tools/qlinearadd_progress_canonical_decision.py"
CANONICAL_SHA256 = (
    "6423f96c6e2647cd30fe20cd4ad1d5291bf5c4751187bbf2dcaf4b923a8145e3"
)
OBSERVER_REL = "tb_probe/native_return_observer.svh"
OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
REPORT_PATH = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-progress-canonical-v7"
    / "report.json"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_zip(
    path: Path, install_name: str
) -> tuple[dict[str, bytes], dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"CRC failed: {path.name}")
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValueError(f"duplicate members: {path.name}")
        for info in infos:
            member = PurePosixPath(info.filename)
            if (
                member.is_absolute()
                or ".." in member.parts
                or "\\" in info.filename
                or stat.S_ISLNK(info.external_attr >> 16)
            ):
                raise ValueError(f"unsafe member: {info.filename}")
        members = {info.filename: archive.read(info) for info in infos}
    root = f"{install_name}/"
    manifest = json.loads(members[root + "TEST_PACKAGE_MANIFEST.json"])
    return members, manifest


def _workload_equivalent(
    source: dict[str, bytes], successor: dict[str, bytes]
) -> dict[str, Any]:
    old_prefix = f"{SOURCE_NAME}/workload/runtime/"
    new_prefix = f"{INSTALL_NAME}/workload/runtime/"
    old = {
        name[len(old_prefix) :]: payload
        for name, payload in source.items()
        if name.startswith(old_prefix)
    }
    new = {
        name[len(new_prefix) :]: payload
        for name, payload in successor.items()
        if name.startswith(new_prefix)
    }
    missing = sorted(set(old) - set(new))
    extra = sorted(set(new) - set(old))
    changed: list[str] = []
    old_name = SOURCE_NAME.encode()
    new_name = INSTALL_NAME.encode()
    for name in sorted(set(old) & set(new)):
        normalized = new[name].replace(new_name, old_name)
        if normalized != old[name]:
            changed.append(name)
    return {
        "valid": not missing and not extra and not changed,
        "missing": missing,
        "extra": extra,
        "changed_after_namespace_normalization": changed,
        "file_count": len(old),
        "namespace_only_normalization": True,
    }


def _canonical_negative_controls() -> dict[str, dict[str, Any]]:
    marker = "# Native NDP return observer v4\n"

    def heartbeat(time: int, cycles: int, *, req: int, raw: int) -> str:
        return (
            f"{time} | HEARTBEAT | slice=0 active_cycles={cycles} "
            f"gexec=1 gconfig=0 req={req} rdata=0 wdata=0 "
            f"buf4_wr={raw} buf4_rd=0 buf5_wr=0 buf5_rd=0\n"
        )

    high = (
        marker
        + heartbeat(10, 10, req=0, raw=1)
        + heartbeat(20, 20, req=0, raw=1)
        + heartbeat(30, 30, req=0, raw=1)
    ).encode()
    high_record = decide(
        high, stall_window_cycles=100, minimum_monotonic_windows=2
    )
    sustained_high = {
        "decision": high_record["decision"],
        "failed_closed": (
            high_record["decision"] != "STILL_PROGRESSING_NOT_FINISHED"
            and high_record["counter_snapshot"][
                "max_consecutive_advancing_windows"
            ]
            == 0
        ),
    }

    progress = (
        marker
        + heartbeat(10, 10, req=1, raw=0)
        + heartbeat(20, 20, req=2, raw=0)
        + heartbeat(30, 30, req=3, raw=0)
    ).encode()
    record = decide(
        progress, stall_window_cycles=100, minimum_monotonic_windows=2
    )

    def rejected(payload: bytes) -> bool:
        try:
            load_unique_record(payload)
        except CanonicalDecisionError:
            return True
        return False

    summary_append = rejected(
        json.dumps(record).encode() + b"\nSUMMARY_ONLY decision=HANG\n"
    )
    conflict = dict(record)
    conflict["decision"] = "LONG_RUNNING_HANG_AT_MSE_REQUEST_ACCEPTED"
    dual = rejected(json.dumps([record, conflict]).encode())
    missing_reason = dict(record)
    missing_reason.pop("reason")
    missing_boundary = dict(record)
    missing_boundary.pop("boundary")
    return {
        "sustained_high_level_without_qualified_growth": sustained_high,
        "summary_only_append": {"failed_closed": summary_append},
        "conflicting_dual_decisions": {"failed_closed": dual},
        "missing_reason": {
            "failed_closed": rejected(json.dumps(missing_reason).encode())
        },
        "missing_boundary": {
            "failed_closed": rejected(json.dumps(missing_boundary).encode())
        },
    }


def validate_final_zip() -> dict[str, Any]:
    members, manifest = _load_zip(ZIP_PATH, INSTALL_NAME)
    source_members, source_manifest = _load_zip(SOURCE_ZIP, SOURCE_NAME)
    root = f"{INSTALL_NAME}/"
    source_root = f"{SOURCE_NAME}/"
    runner = members[root + "PREPARE_AND_RUN.sh"].decode()
    observer = members[root + OBSERVER_REL]
    parser_payload = members[root + CANONICAL_REL]
    allowlist = manifest["return_allowlist"]
    required_targets = {
        item["target_path"]
        for item in allowlist
        if item.get("required") is True
    }
    canonical = manifest.get("canonical_decision_contract", {})
    defaults = manifest.get("default_progress_diagnostics", {})

    v6_has_canonical = any(
        name.endswith("/qlinearadd_progress_canonical_decision.py")
        for name in source_members
    ) or "canonical_decision_contract" in source_manifest
    v6_allowlist = {
        item["target_path"] for item in source_manifest["return_allowlist"]
    }
    v6_audit = {
        "zip_sha256": sha256_file(SOURCE_ZIP),
        "expected_sha256": SOURCE_ZIP_SHA256,
        "four_way_binding_prior_receipt_preserved": True,
        "canonical_parser_present": v6_has_canonical,
        "canonical_return_present": (
            "evidence/CANONICAL_PROGRESS_DECISION.json" in v6_allowlist
        ),
        "status": "QUARANTINED_NOT_RUN_CANONICAL_DECISION_MISSING",
    }

    runner_binding = all(
        token in runner
        for token in (
            'decision_runtime="$package_root/package_tools/'
            'qlinearadd_progress_canonical_decision.py"',
            'canonical_decision="$evidence_root/'
            'CANONICAL_PROGRESS_DECISION.json"',
            'python3 "$decision_runtime"',
            '--observer-log "$observer_log"',
            '--progress-contract "$evidence_root/progress_contract.json"',
            '--output "$canonical_decision"',
            "canonical_decision_status=$?",
            "canonical_decision_exit_status.txt",
            "trap 'finalize $?' EXIT",
            "trap 'signal_name=HUP; simulation_status=125; finalize 125' HUP",
            "trap 'signal_name=INT; simulation_status=125; finalize 125' INT",
            "trap 'signal_name=TERM; simulation_status=125; finalize 125' TERM",
        )
    )
    canonical_manifest = (
        canonical.get("rule_id")
        == "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001"
        and canonical.get("schema")
        == "qlinearadd-progress-canonical-decision-v1"
        and canonical.get("parser_path") == CANONICAL_REL
        and canonical.get("parser_sha256") == CANONICAL_SHA256
        and canonical.get("unique_complete_record_required") is True
        and canonical.get("qualified_counters")
        == ["gexec", "req", "rdata", "wdata"]
        and canonical.get("raw_state_excluded_from_progress")
        == ["buf4_wr", "buf4_rd", "buf5_wr", "buf5_rd"]
        and canonical.get("ambiguous_state")
        == "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS"
    )
    canonical_return = {
        "evidence/CANONICAL_PROGRESS_DECISION.json",
        "evidence/canonical_decision_exit_status.txt",
    }.issubset(required_targets)
    old_four_way = (
        sha256_bytes(observer) == OBSERVER_SHA256
        and "+incdir+$package_root/tb_probe" in runner
        and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in runner
        and "+RETURN_OBSERVER" in runner
        and "runs/return_observer.log" in required_targets
        and "evidence/observer_binding.txt" in required_targets
    )
    default_progress = (
        defaults.get("rule_id")
        == "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001"
        and defaults.get("enabled_by_default") is True
        and defaults.get("read_only") is True
        and defaults.get("rate_limited") is True
        and defaults.get("partial_return_on_exit_and_signals") is True
        and defaults.get("changes_dut_input") is False
        and defaults.get("changes_ready_or_backpressure") is False
        and defaults.get("changes_timeout") is False
        and defaults.get("changes_formal_readback") is False
        and all(
            target in required_targets
            for target in (
                "evidence/actual_compile_argv.txt",
                "evidence/actual_simulator_argv.txt",
                "evidence/host_timing.txt",
                "evidence/progress_samples.log",
                "evidence/signal_status.txt",
                "runs/return_observer.log",
                "evidence/CANONICAL_PROGRESS_DECISION.json",
            )
        )
    )
    runtime_d_absent = not any(
        "/workload/runtime/" in name
        and "matrix_D_linearized_128bit" in name
        for name in members
    )
    workload = _workload_equivalent(source_members, members)
    controls = _canonical_negative_controls()
    controls_valid = all(
        item["failed_closed"] for item in controls.values()
    )
    sidecar_exact = SIDECAR_PATH.read_text(encoding="ascii").split() == [
        ZIP_SHA256,
        ZIP_PATH.name,
    ]
    zip_exact = sha256_file(ZIP_PATH) == ZIP_SHA256
    rule_exact = sha256_file(SERVER_RULE) == SERVER_RULE_SHA256
    parser_exact = sha256_bytes(parser_payload) == CANONICAL_SHA256
    v6_quarantined = (
        v6_audit["zip_sha256"] == SOURCE_ZIP_SHA256
        and not v6_audit["canonical_parser_present"]
        and not v6_audit["canonical_return_present"]
    )
    valid = all(
        (
            zip_exact,
            sidecar_exact,
            rule_exact,
            parser_exact,
            runner_binding,
            canonical_manifest,
            canonical_return,
            old_four_way,
            default_progress,
            runtime_d_absent,
            workload["valid"],
            controls_valid,
            v6_quarantined,
            manifest.get("server_rtl_entries") == 0,
            manifest.get("server_tb_or_observer_entries") == 1,
            manifest.get("functional_fix") is False,
            manifest.get("package_class")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        )
    )
    return {
        "schema": "qlinearadd-node0007-canonical-decision-final-zip-v1",
        "valid": valid,
        "status": (
            "CANONICAL_DECISION_RULE_VALIDATED"
            if valid
            else "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS"
        ),
        "zip": ZIP_PATH.relative_to(ROOT).as_posix(),
        "zip_sha256": sha256_file(ZIP_PATH),
        "expected_zip_sha256": ZIP_SHA256,
        "sidecar_exact": sidecar_exact,
        "server_rule_sha256": sha256_file(SERVER_RULE),
        "server_rule_current_match": rule_exact,
        "canonical_parser_sha256": sha256_bytes(parser_payload),
        "canonical_parser_exact": parser_exact,
        "runner_signal_parser_return_binding": runner_binding,
        "canonical_manifest_exact": canonical_manifest,
        "canonical_return_allowlist_exact_subset": canonical_return,
        "four_way_observer_binding_preserved": old_four_way,
        "default_progress_diagnostics_validated": default_progress,
        "runtime_formal_d_targets_absent": runtime_d_absent,
        "source_v6_audit": v6_audit,
        "source_v6_quarantined": v6_quarantined,
        "frozen_workload_equivalence": workload,
        "negative_controls": controls,
        "all_canonical_negative_controls_fail_closed": controls_valid,
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "package_rebuilt_from_frozen_assets": True,
        "server_action": False,
    }


def main() -> int:
    report = validate_final_zip()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
