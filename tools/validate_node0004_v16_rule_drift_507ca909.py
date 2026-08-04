from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ZIP_SHA256 = "e0f6d1effba71e505d22203ec2a43b4a538aaeeb515b806f6953603a342bcec1"
OLD_SERVER_RULE_SHA256 = (
    "0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a"
)
CURRENT_SERVER_RULE_SHA256 = (
    "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
)
NEW_RULE_ID = "CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001"
CONTENT_NEUTRAL_STATUS = "RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS"
OBSERVER_RELATIVE_PATH = "tb_probe/native_return_observer.svh"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_zip(zip_path: Path) -> tuple[str, dict[str, bytes]]:
    with zipfile.ZipFile(zip_path) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise ValueError(f"ZIP CRC failure: {bad}")
        names = archive.namelist()
        roots = {name.split("/", 1)[0] for name in names if name}
        if len(roots) != 1:
            raise ValueError(f"ZIP must have one root, observed {sorted(roots)}")
        root = next(iter(roots))
        entries = {
            name[len(root) + 1 :]: archive.read(name)
            for name in names
            if name != root + "/" and not name.endswith("/")
        }
    return root, entries


def block_containing(text: str, needle: str) -> str:
    needle_at = text.index(needle)
    start = text.rfind("always @(", 0, needle_at)
    if start < 0:
        raise ValueError(f"no always block before {needle}")
    next_block = text.find("\n    always @(", needle_at)
    next_initial = text.find("\n    initial begin", needle_at)
    ends = [item for item in (next_block, next_initial) if item >= 0]
    end = min(ends) if ends else len(text)
    return text[start:end]


def replace_last(text: str, old: str, new: str) -> str:
    at = text.rfind(old)
    if at < 0:
        raise ValueError(f"cannot find final occurrence of {old!r}")
    return text[:at] + new + text[at + len(old) :]


def assess(
    *,
    zip_path: Path,
    sidecar_path: Path,
    rule_path: Path,
    clk_freq_path: Path,
    ndp_top_path: Path,
    observer_override: str | None = None,
    clk_freq_override: str | None = None,
) -> tuple[bool, list[str], dict[str, Any]]:
    errors: list[str] = []
    root, entries = read_zip(zip_path)
    zip_digest = sha256_file(zip_path)
    sidecar_text = sidecar_path.read_text(encoding="utf-8").strip()
    sidecar_parts = sidecar_text.split()
    manifest = json.loads(entries["package_manifest.json"])
    observer = (
        observer_override
        if observer_override is not None
        else entries[OBSERVER_RELATIVE_PATH].decode("utf-8")
    )
    clk_freq = (
        clk_freq_override
        if clk_freq_override is not None
        else clk_freq_path.read_text(encoding="utf-8")
    )
    ndp_top = ndp_top_path.read_text(encoding="utf-8")
    server_rule = rule_path.read_text(encoding="utf-8")

    canonical_block = block_containing(
        observer, "return_hang_diag_sample_index++;"
    )
    primary_counter_block = block_containing(
        observer, "return_obs_req_count[mse]++;"
    )
    canonical_task_start = observer.index(
        "task automatic return_hang_diag_emit_decision"
    )
    canonical_task_end = observer.index("endtask", canonical_task_start)
    canonical_task = observer[canonical_task_start:canonical_task_end]
    current_progress_assignments = re.findall(
        r"return_hang_diag_current_progress\s*=\s*(.*?);",
        canonical_block,
        flags=re.DOTALL,
    )
    progress_rhs = (
        current_progress_assignments[-1] if current_progress_assignments else ""
    )

    cross_domain_unique_emit_patterns = {
        "sg_counter_modulo": re.search(
            r"return_obs_sg_[A-Za-z0-9_\[\]]+\s*%|"
            r"%\s*return_obs_sg_[A-Za-z0-9_\[\]]+",
            canonical_block,
        )
        is not None,
        "sg_counter_equality": re.search(
            r"return_obs_sg_[A-Za-z0-9_\[\]]+\s*==|"
            r"==\s*return_obs_sg_[A-Za-z0-9_\[\]]+",
            canonical_block,
        )
        is not None,
        "sg_counter_in_progress_sum": "return_obs_sg_" in progress_rhs,
        "canonical_emitter_on_sg_clock": (
            "posedge u_NDP_Top_new.clk_sg" in canonical_block
        ),
    }
    forbidden_dut_drive = re.search(
        r"(?m)^\s*u_NDP_Top_new(?:\.[A-Za-z0-9_\[\]]+)+\s*(?:<=|=(?!=))",
        observer,
    )

    checks = {
        "zip_identity_unchanged": zip_digest == ZIP_SHA256,
        "sidecar_matches_unchanged_zip": (
            len(sidecar_parts) >= 2
            and sidecar_parts[0].lower() == ZIP_SHA256
            and sidecar_parts[-1] == zip_path.name
        ),
        "single_expected_root": root == "r5_n4_hw_v16_abpe_runnerpc",
        "manifest_binds_old_rule_receipt": (
            manifest.get("active_receipts", {}).get(
                "server_package_rule_sha256"
            )
            == OLD_SERVER_RULE_SHA256
        ),
        "current_rule_file_match": (
            sha256_file(rule_path) == CURRENT_SERVER_RULE_SHA256
        ),
        "new_rule_present_in_current_text": NEW_RULE_ID in server_rule,
        "content_neutral_escape_present_in_current_text": (
            CONTENT_NEUTRAL_STATUS in server_rule
        ),
        "observer_identity_unchanged": (
            sha256_bytes(entries[OBSERVER_RELATIVE_PATH])
            == manifest["observer_binding_four_way"]["source"]["sha256"]
            == "61dd2dd47558672b4929b8cd30b9147fa3a68c1a12e67dfa4865b33f8e4fb3ee"
        ),
        "canonical_snapshot_owned_by_clk_db": (
            "always @(posedge u_NDP_Top_new.clk_db" in canonical_block
        ),
        "canonical_window_uses_same_domain_active_cycles": (
            "return_obs_active_cycles %" in canonical_block
            and "return_hang_diag_sample_cycles" in canonical_block
        ),
        "qualified_counters_owned_by_clk_db": (
            "always @(posedge u_NDP_Top_new.clk_db"
            in primary_counter_block
            and "return_obs_req_count[mse]++;" in primary_counter_block
            and "return_obs_rdata_count[mse]++;" in primary_counter_block
            and "return_obs_wdata_count[mse]++;" in primary_counter_block
        ),
        "canonical_progress_excludes_sg_domain_counters": (
            "return_obs_sg_" not in progress_rhs
        ),
        "canonical_record_excludes_sg_domain_counters": (
            "return_obs_sg_" not in canonical_task
        ),
        "no_cross_domain_modulo_or_equality_unique_emitter": (
            not any(cross_domain_unique_emit_patterns.values())
        ),
        "rtlsim_clk_db_free_running": (
            "forever #(CLK_DB_HALF_PERIOD) clk_db_out = ~clk_db_out;"
            in clk_freq
        ),
        "rtlsim_clk_sg_free_running": (
            "forever #(CLK_SG_HALF_PERIOD) clk_sg_out = ~clk_sg_out;"
            in clk_freq
        ),
        "top_binds_free_running_clocks": (
            ".clk_db_out  (clk_db)" in ndp_top
            and ".clk_sg_out  (clk_sg)" in ndp_top
        ),
        "observer_is_read_only": forbidden_dut_drive is None,
    }
    for name, passed in checks.items():
        if not passed:
            errors.append(f"content-neutral applicability check failed: {name}")

    details = {
        "checks": checks,
        "cross_domain_unique_emit_patterns": cross_domain_unique_emit_patterns,
        "applicability": {
            "rule_id": NEW_RULE_ID,
            "applies_to_v16_canonical_progress_path": False,
            "reason": (
                "v16 canonical progress counters, snapshot cadence, heartbeat "
                "and canonical decision are all owned/emitted on free-running "
                "clk_db; no gated-domain or clk_sg counter participates in the "
                "monotonic sum or modulo/equality print gate"
            ),
            "auxiliary_clk_sg_scope": (
                "event-limited diagnostic context only; excluded from "
                "monotonic progress and canonical decision; RTLSIM clk_sg is "
                "also generated by a free-running forever loop"
            ),
            "zip_change_required": False,
            "runner_change_required": False,
            "manifest_machine_contract_change_required": False,
            "negative_control_asset_change_required": False,
            "return_schema_change_required": False,
        },
        "source_current_match": {
            "server_rule": {
                "path": str(rule_path),
                "sha256": sha256_file(rule_path),
            },
            "clock_generator": {
                "path": str(clk_freq_path),
                "sha256": sha256_file(clk_freq_path),
            },
            "top": {
                "path": str(ndp_top_path),
                "sha256": sha256_file(ndp_top_path),
            },
        },
    }
    return not errors, errors, details


def negative_controls(
    *,
    zip_path: Path,
    sidecar_path: Path,
    rule_path: Path,
    clk_freq_path: Path,
    ndp_top_path: Path,
) -> dict[str, Any]:
    _, entries = read_zip(zip_path)
    observer = entries[OBSERVER_RELATIVE_PATH].decode("utf-8")
    clk_freq = clk_freq_path.read_text(encoding="utf-8")
    cases: dict[str, tuple[str, str]] = {
        "cross_domain_modulo_as_unique_emitter": (
            replace_last(
                observer,
                "(return_obs_active_cycles %",
                "(return_obs_sg_mse4_req_count[0] %",
            ),
            clk_freq,
        ),
        "sg_counter_injected_into_canonical_progress": (
            re.sub(
                r"(return_hang_diag_current_progress\s*=\s*)"
                r"(return_obs_req_count\[0\]\s*\+)",
                r"\1return_obs_sg_ga_input_count +\n                \2",
                observer,
                count=1,
            ),
            clk_freq,
        ),
        "canonical_emitter_moved_to_sg_domain": (
            observer.replace(
                "always @(posedge u_NDP_Top_new.clk_db or\n"
                "             negedge u_NDP_Top_new.rst_n_db) begin\n"
                "        if (!u_NDP_Top_new.rst_n_db) begin\n"
                "            return_hang_diag_buf4_wr_d = 0;",
                "always @(posedge u_NDP_Top_new.clk_sg or\n"
                "             negedge u_NDP_Top_new.rst_n_db) begin\n"
                "        if (!u_NDP_Top_new.rst_n_db) begin\n"
                "            return_hang_diag_buf4_wr_d = 0;",
                1,
            ),
            clk_freq,
        ),
        "free_running_clk_db_proof_removed": (
            observer,
            clk_freq.replace(
                "forever #(CLK_DB_HALF_PERIOD) clk_db_out = ~clk_db_out;",
                "#(CLK_DB_HALF_PERIOD) clk_db_out = ~clk_db_out;",
                1,
            ),
        ),
    }
    result: dict[str, Any] = {}
    for name, (mutated_observer, mutated_clk_freq) in cases.items():
        valid, errors, _ = assess(
            zip_path=zip_path,
            sidecar_path=sidecar_path,
            rule_path=rule_path,
            clk_freq_path=clk_freq_path,
            ndp_top_path=ndp_top_path,
            observer_override=mutated_observer,
            clk_freq_override=mutated_clk_freq,
        )
        result[name] = {
            "failed_closed": not valid,
            "validator_exit_code": 0 if valid else 1,
            "errors": errors,
        }
    result["all_failed_closed"] = all(
        item["failed_closed"]
        for name, item in result.items()
        if name != "all_failed_closed"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--zip",
        type=Path,
        default=PROJECT_ROOT
        / "artifacts/operator_config_validation/r5-server-test-packages"
        / "r5_n4_hw_v16_abpe_runnerpc.zip",
    )
    parser.add_argument(
        "--sidecar",
        type=Path,
        default=PROJECT_ROOT
        / "artifacts/operator_config_validation/r5-server-test-packages"
        / "r5_n4_hw_v16_abpe_runnerpc.zip.sha256",
    )
    parser.add_argument(
        "--rule",
        type=Path,
        default=PROJECT_ROOT / ".agents/rules/服务器测试包生成规则.md",
    )
    parser.add_argument(
        "--clk-freq",
        type=Path,
        default=PROJECT_ROOT / "NDP_copy01/rtl/clk_freq.sv",
    )
    parser.add_argument(
        "--ndp-top",
        type=Path,
        default=PROJECT_ROOT / "NDP_copy01/rtl/NDP_Top_phy.sv",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    valid, errors, details = assess(
        zip_path=args.zip,
        sidecar_path=args.sidecar,
        rule_path=args.rule,
        clk_freq_path=args.clk_freq,
        ndp_top_path=args.ndp_top,
    )
    negatives = negative_controls(
        zip_path=args.zip,
        sidecar_path=args.sidecar,
        rule_path=args.rule,
        clk_freq_path=args.clk_freq,
        ndp_top_path=args.ndp_top,
    )
    if not negatives["all_failed_closed"]:
        errors.append("one or more clock-domain negative controls did not fail")
        valid = False

    report = {
        "schema": "node0004-v16-rule-drift-content-neutral-revalidation-v1",
        "status": CONTENT_NEUTRAL_STATUS if valid else "RULE_DRIFT_REVALIDATION_FAILED",
        "valid": valid,
        "errors": errors,
        "error_count": len(errors),
        "new_rule_id": NEW_RULE_ID,
        "old_server_rule_sha256": OLD_SERVER_RULE_SHA256,
        "current_server_rule_sha256": CURRENT_SERVER_RULE_SHA256,
        "final_zip": {
            "path": str(args.zip.resolve()),
            "size_bytes": args.zip.stat().st_size,
            "sha256": sha256_file(args.zip),
            "sha256_before": ZIP_SHA256,
            "sha256_after": sha256_file(args.zip),
            "bytes_changed": False,
        },
        "sidecar": {
            "path": str(args.sidecar.resolve()),
            "sha256": sha256_file(args.sidecar),
        },
        **details,
        "negative_controls": negatives,
        "package_release": "PACKAGE_READY_NOT_RUN" if valid else "QUARANTINED",
        "validation_execution": {
            "command": [str(Path(sys.executable).resolve()), *sys.argv],
            "cwd": str(Path.cwd().resolve()),
            "exit_code": 0 if valid else 1,
            "validator": {
                "path": str(Path(__file__).resolve()),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
        },
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "functional_rtl_modified": False,
        "plan_or_public_rules_modified": False,
        "server_action": False,
    }
    text = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
