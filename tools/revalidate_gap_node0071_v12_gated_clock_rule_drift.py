from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
ZIP = PACKAGE_DIR / "r5_n71_gap_v12_minruntime.zip"
SIDECAR = Path(str(ZIP) + ".sha256")
OLD_AUDIT = PACKAGE_DIR / (
    "r5_n71_gap_v12_minruntime.final_zip_rule_self_audit.json"
)
OUTPUT = PACKAGE_DIR / (
    "r5_n71_gap_v12_minruntime."
    "rule_drift_content_neutral_revalidation.json"
)
ZIP_SHA256 = (
    "a1e149e7e4a20cd254e84a8fd7199607beeafb11fd71cfe4d548226825b06d06"
)
OLD_RULE_SHA256 = (
    "0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a"
)
NEW_RULE_SHA256 = (
    "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
)
NEW_RULE_ID = "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001"
OBSERVER_MEMBER = (
    "r5_n71_gap_v12_minruntime/"
    "tb_probe/native_return_observer.svh"
)
CLOCK_SOURCE = (
    ROOT
    / "Trassic2.0_RTL_master_1c49bd1_audit"
    / "Trassic2.0_RTL-master/code/NDP_rtl/clk_freq.sv"
)
CLOCK_SOURCE_SHA256 = (
    "c95d81934c9adadb1a2a9762c0c3b2dcf8e09021b4df69f4ef4a212a30a78cdd"
)


class RevalidationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_final_zip() -> tuple[dict[str, bytes], bool]:
    files: dict[str, bytes] = {}
    with zipfile.ZipFile(ZIP) as archive:
        crc_valid = archive.testzip() is None
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
                or info.filename in files
            ):
                raise RevalidationError(
                    f"unsafe or duplicate ZIP member: {info.filename}"
                )
            if not info.is_dir():
                files[info.filename] = archive.read(info)
    return files, crc_valid


def run_validator(name: str, command: list[str]) -> dict[str, Any]:
    process = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    receipt = {
        "name": name,
        "command": command,
        "cwd": str(ROOT),
        "exit_code": process.returncode,
        "stdout_sha256": sha256_bytes(process.stdout.encode("utf-8")),
        "stderr_sha256": sha256_bytes(process.stderr.encode("utf-8")),
        "stdout_size_bytes": len(process.stdout.encode("utf-8")),
        "stderr_size_bytes": len(process.stderr.encode("utf-8")),
        "status": "PASS" if process.returncode == 0 else "FAIL",
    }
    if process.returncode != 0:
        raise RevalidationError(
            f"{name} failed: {process.stderr or process.stdout}"
        )
    return receipt


def audit_observer_clock_domain(observer: str) -> dict[str, Any]:
    always_clocks = re.findall(
        r"always\s*@\(\s*posedge\s+([A-Za-z0-9_.$]+)",
        observer,
    )
    unique_clocks = sorted(set(always_clocks))
    expected_clocks = [
        "u_NDP_Top_new.clk_db",
        "u_NDP_Top_new.clk_sg",
    ]
    if unique_clocks != expected_clocks:
        raise RevalidationError(
            f"observer clock owners differ: {unique_clocks}"
        )
    db_block_start = observer.index(
        "always @(posedge u_NDP_Top_new.clk_db"
    )
    sg_block_start = observer.index(
        "always @(posedge u_NDP_Top_new.clk_sg"
    )
    db_block = observer[db_block_start:sg_block_start]
    heartbeat_uses_db_owned_counter = all(
        token in db_block
        for token in (
            "return_obs_active_cycles++;",
            "return_obs_active_cycles %",
            "return_obs_heartbeat_period",
            'return_obs_write_summary("HEARTBEAT")',
        )
    )
    modulo_counter_names = re.findall(
        r"\(\s*(return_obs_[A-Za-z0-9_]+)\s*%", db_block
    )
    foreign_equality_conditions = re.findall(
        r"if\s*\([^)]*"
        r"(return_obs_(?:sg_|ga_operand|ga_accept)[A-Za-z0-9_]*)"
        r"\s*==",
        db_block,
        re.DOTALL,
    )
    foreign_counter_is_unique_emitter = (
        any(name != "return_obs_active_cycles"
            for name in modulo_counter_names)
        or bool(foreign_equality_conditions)
    )
    sg_counter_names = sorted(
        set(
            re.findall(
                r"(return_obs_(?:sg_[A-Za-z0-9_]+"
                r"|ga_operand[02]_capture_count"
                r"|ga_accept_count))\+\+",
                observer[sg_block_start:],
            )
        )
    )
    if (
        not heartbeat_uses_db_owned_counter
        or foreign_counter_is_unique_emitter
        or not sg_counter_names
    ):
        raise RevalidationError("observer emitter/counter ownership differs")
    return {
        "observer_always_posedge_clocks": unique_clocks,
        "observer_always_posedge_block_count": len(always_clocks),
        "qualified_counter_source_clocks": {
            "db_counters": "u_NDP_Top_new.clk_db",
            "sg_counters": "u_NDP_Top_new.clk_sg",
        },
        "sg_qualified_counter_names": sg_counter_names,
        "heartbeat_emitter_clock": "u_NDP_Top_new.clk_db",
        "heartbeat_modulo_counter": "return_obs_active_cycles",
        "heartbeat_modulo_counter_owner":
            "u_NDP_Top_new.clk_db",
        "all_modulo_counter_names": modulo_counter_names,
        "foreign_equality_condition_counter_names":
            foreign_equality_conditions,
        "foreign_domain_counter_used_as_unique_modulo_or_equality_emitter":
            foreign_counter_is_unique_emitter,
        "gated_leaf_clock_used_by_observer_counter": False,
    }


def audit_clock_source() -> dict[str, Any]:
    if sha256_file(CLOCK_SOURCE) != CLOCK_SOURCE_SHA256:
        raise RevalidationError("frozen clk_freq source identity differs")
    text = CLOCK_SOURCE.read_text(encoding="utf-8")
    checks = {
        "rtlsim_db_free_running": (
            "forever #(CLK_DB_HALF_PERIOD) "
            "clk_db_out = ~clk_db_out;" in text
        ),
        "rtlsim_sg_free_running": (
            "forever #(CLK_SG_HALF_PERIOD) "
            "clk_sg_out = ~clk_sg_out;" in text
        ),
        "non_rtlsim_db_passthrough": "clk_db_out   = clk_db_in;" in text,
        "non_rtlsim_sg_continuous_divider": (
            "always @(posedge clk_db_in or negedge rst_n_db_in)" in text
            and "clk_sg_out <= ~clk_sg_out;" in text
        ),
    }
    if not all(checks.values()):
        raise RevalidationError("frozen clk_freq liveness equation differs")
    return {
        "path": str(CLOCK_SOURCE.relative_to(ROOT)),
        "sha256": CLOCK_SOURCE_SHA256,
        "checks": checks,
        "clk_db_gated": False,
        "clk_sg_gated": False,
        "boundary": (
            "local frozen RTL applicability proof only; v12 user-supplied-root "
            "profile intentionally does not bind server source identity"
        ),
    }


def revalidate() -> dict[str, Any]:
    before_sha = sha256_file(ZIP)
    if before_sha != ZIP_SHA256:
        raise RevalidationError("v12 ZIP identity differs")
    if (
        sha256_file(ROOT / ".agents/rules/服务器测试包生成规则.md")
        != NEW_RULE_SHA256
    ):
        raise RevalidationError("current server rule identity differs")
    sidecar_exact = (
        SIDECAR.read_text(encoding="ascii")
        == f"{ZIP_SHA256}  {ZIP.name}\n"
    )
    if not sidecar_exact:
        raise RevalidationError("v12 sidecar differs")

    files, crc_valid = read_final_zip()
    manifest_member = (
        "r5_n71_gap_v12_minruntime/TEST_PACKAGE_MANIFEST.json"
    )
    manifest = json.loads(files[manifest_member].decode("utf-8"))
    declared = manifest["files"]
    exact_set = {
        f"r5_n71_gap_v12_minruntime/{relative}"
        for relative in declared
    } | {manifest_member} == set(files)
    if not crc_valid or not exact_set:
        raise RevalidationError("v12 ZIP CRC/exact-set differs")
    observer_payload = files[OBSERVER_MEMBER]
    observer = observer_payload.decode("utf-8")
    observer_audit = audit_observer_clock_domain(observer)
    clock_source_audit = audit_clock_source()

    old_audit = json.loads(OLD_AUDIT.read_text(encoding="utf-8"))
    if (
        old_audit.get("FINAL_ZIP_RULE_SELF_AUDIT_PASS") is not True
        or old_audit.get("error_count") != 0
        or old_audit.get("zip_sha256") != ZIP_SHA256
    ):
        raise RevalidationError("original v12 final audit differs")

    validators = [
        (
            "canonical_validator_and_controls",
            [
                sys.executable,
                str(ROOT / "tools/validate_gap_node0071_canonical_package.py"),
                str(ZIP),
            ],
        ),
        (
            "observer_four_way_validator_and_controls",
            [
                sys.executable,
                str(ROOT / "tools/validate_gap_node0071_observer_binding.py"),
                str(ZIP),
            ],
        ),
        (
            "dual_ingress_validator_and_controls",
            [
                sys.executable,
                str(ROOT / "tools/validate_gap_node0071_v8_dual_ingress.py"),
                str(ZIP),
            ],
        ),
        (
            "runner_positive_and_negative_controls",
            [
                sys.executable,
                str(
                    ROOT
                    / "tools/validate_gap_node0071_v12_minimal_runtime_chain.py"
                ),
                "--target-zip",
                str(ZIP),
            ],
        ),
    ]
    command_receipts = [
        run_validator(name, command) for name, command in validators
    ]
    after_sha = sha256_file(ZIP)
    if after_sha != before_sha:
        raise RevalidationError("v12 ZIP changed during receipt-only audit")

    return {
        "schema":
            "gap-node0071-v12-rule-drift-content-neutral-revalidation-v1",
        "status": "RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS",
        "valid": True,
        "errors": [],
        "error_count": 0,
        "old_server_rule_sha256": OLD_RULE_SHA256,
        "new_server_rule_sha256": NEW_RULE_SHA256,
        "new_rule": {
            "rule_id": NEW_RULE_ID,
            "applicability": "NOT_APPLICABLE",
            "reason": (
                "v12 qualified counters are owned only by free-running top "
                "clk_db/clk_sg; no gated leaf clock owns an observer counter, "
                "and heartbeat emission uses a clk_db-owned counter rather "
                "than a foreign-domain counter modulo/equality gate"
            ),
            "zip_content_change_required": False,
            "runner_change_required": False,
            "manifest_machine_contract_change_required": False,
            "negative_control_change_required": False,
            "return_schema_change_required": False,
        },
        "zip": str(ZIP),
        "zip_sha256_before": before_sha,
        "zip_sha256_after": after_sha,
        "zip_bytes_unchanged": before_sha == after_sha,
        "sidecar": str(SIDECAR),
        "sidecar_sha256": sha256_file(SIDECAR),
        "sidecar_content_exact": sidecar_exact,
        "zip_crc_valid": crc_valid,
        "manifest_exact_set_valid": exact_set,
        "observer_sha256": sha256_bytes(observer_payload),
        "observer_clock_domain_audit": observer_audit,
        "clock_source_audit": clock_source_audit,
        "original_final_audit": {
            "path": str(OLD_AUDIT),
            "sha256": sha256_file(OLD_AUDIT),
            "pass": True,
            "errors": 0,
        },
        "command_receipts": command_receipts,
        "all_revalidation_commands_exit_zero": all(
            item["exit_code"] == 0 for item in command_receipts
        ),
        "numeric_analysis_repeated": False,
        "sum_tail_workload_reexecuted": False,
        "package_rebuilt": False,
        "functional_rtl_modified": False,
        "server_action": False,
        "package_release": {
            "identity_preserved": True,
            "status": "PACKAGE_READY_NOT_RUN",
            "zip_sha256": ZIP_SHA256,
            "server_command":
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        },
    }


def main() -> int:
    try:
        result = revalidate()
        OUTPUT.write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as error:
        print(f"v12 rule-drift revalidation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
