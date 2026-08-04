from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_qadd_n7_obsclk_v12_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_qadd_n7_obsclk_v12.zip"
)
SOURCE_SHA256 = "87c4089d56dbd082d825b2575285e9ec48276402c25bbe9e648f4165e4a461f3"
INSTALL_NAME = "r5_qadd_n7_obsclk_v12"
REPORT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-observer-clock-v12-return-analysis"
    / "report.json"
)
CLOCK_RE = re.compile(
    r"(?P<time>\d+) \| FIRST_REQUEST_CLOCK \| slice=(?P<slice>\d+) "
    r"active_cycles=(?P<cycles>\d+) clk_sg_edges=(?P<edges>\d+) "
    r"clk_sg_level=(?P<level>[01])"
)


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _key_values(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in payload.decode("utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def analyze(return_zip: Path = DEFAULT_RETURN) -> dict[str, Any]:
    sidecar = Path(str(return_zip) + ".sha256")
    with zipfile.ZipFile(return_zip) as archive:
        bad = archive.testzip()
        names = archive.namelist()
        duplicate_absent = len(names) == len(set(names))
        roots = sorted({name.split("/", 1)[0] for name in names})
        members = {
            name: archive.read(name)
            for name in names
            if not name.endswith("/")
        }
    root = f"{INSTALL_NAME}_return/"
    with zipfile.ZipFile(SOURCE_ZIP) as source:
        source_bad = source.testzip()
        source_manifest_payload = source.read(
            f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json"
        )
        source_tail = source.read(
            f"{INSTALL_NAME}/tb_probe/"
            "qlinearadd_node0007_first_request_observer_tail_v9.svh"
        ).decode("utf-8")
    manifest = json.loads(source_manifest_payload)
    returned_manifest_payload = members[root + "evidence/PACKAGE_MANIFEST.json"]
    expected_allowlist = {
        item["target_path"]: item for item in manifest["return_allowlist"]
    }
    actual_relative = {
        name.removeprefix(root)
        for name in members
        if name.startswith(root)
    }
    missing_required_non_readback = sorted(
        path
        for path, item in expected_allowlist.items()
        if item["required"]
        and not path.startswith("readbacks/")
        and path not in actual_relative
    )
    package_preflight = json.loads(
        members[root + "evidence/package_preflight.json"]
    )
    installed_preflight = json.loads(
        members[root + "evidence/installed_preflight.json"]
    )
    gate = json.loads(members[root + "evidence/SERVER_RESULT_GATE.json"])
    progress_contract = json.loads(
        members[root + "evidence/progress_contract.json"]
    )
    timing = {
        key: int(value)
        for key, value in _key_values(
            members[root + "evidence/host_timing.txt"]
        ).items()
    }
    signal = _key_values(members[root + "evidence/signal_status.txt"])
    progress_text = members[
        root + "evidence/progress_samples.log"
    ].decode("utf-8", errors="replace")
    clock_samples = [
        {
            "time": int(match.group("time")),
            "slice": int(match.group("slice")),
            "active_cycles": int(match.group("cycles")),
            "clk_sg_edges": int(match.group("edges")),
            "clk_sg_level": int(match.group("level")),
        }
        for match in CLOCK_RE.finditer(progress_text)
    ]
    heartbeat = progress_contract["heartbeat_cycles"]
    non_rate_limited = [
        sample for sample in clock_samples if sample["active_cycles"] % heartbeat
    ]
    clock_monotonic = all(
        after["active_cycles"] > before["active_cycles"]
        and after["clk_sg_edges"] > before["clk_sg_edges"]
        for before, after in zip(clock_samples, clock_samples[1:])
    )
    sim_log = members[root + "runs/sim.log"].decode(
        "utf-8", errors="replace"
    )
    formal = gate["result_gate_conjunction"]
    unbounded_static = (
        source_tail.find('"%0t | FIRST_REQUEST_CLOCK |')
        > source_tail.find("            end\n            $fdisplay(")
        and source_tail.count("FIRST_REQUEST_CLOCK") == 1
    )
    last_cycles = clock_samples[-1]["active_cycles"] if clock_samples else 0
    minimum_clock_log_bytes = last_cycles * 80
    single_text_budget = manifest["budgets"]["single_text_max_bytes"]
    errors = []
    if not (
        bad is None
        and duplicate_absent
        and roots == [f"{INSTALL_NAME}_return"]
    ):
        errors.append("return ZIP structure invalid")
    report: dict[str, Any] = {
        "schema": "qlinearadd-node0007-obsclk-v12-return-analysis-v1",
        "status": (
            "RETURN_SNAPSHOT_NONAUTHORITATIVE_AND_"
            "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        ),
        "return_receipt": {
            "path": str(return_zip),
            "sha256": sha256(return_zip),
            "bytes": return_zip.stat().st_size,
            "adjacent_sidecar_exists": sidecar.is_file(),
            "formal_receipt_valid": False,
            "return_manifest_present": root + "RETURN_MANIFEST.json" in members,
        },
        "zip_structure": {
            "crc_valid": bad is None,
            "duplicate_members_absent": duplicate_absent,
            "root_exact": roots == [f"{INSTALL_NAME}_return"],
            "file_member_count": len(members),
        },
        "source_binding": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "expected_sha256": SOURCE_SHA256,
            "actual_sha256": sha256(SOURCE_ZIP),
            "crc_valid": source_bad is None,
            "returned_package_manifest_byte_equal": (
                returned_manifest_payload == source_manifest_payload
            ),
        },
        "allowlist": {
            "authoritative_exact_set_available": False,
            "return_manifest_missing": True,
            "required_non_readback_missing": missing_required_non_readback,
            "observer_claim_text": _key_values(
                members[root + "evidence/observer_binding.txt"]
            ).get("observer_enabled_and_returned"),
            "observer_claim_contradicted_by_zip_exact_set": (
                "runs/return_observer.log" not in actual_relative
            ),
        },
        "preflight": {
            "package_valid": package_preflight.get("valid") is True,
            "installed_valid": installed_preflight.get("valid") is True,
            "package_runtime_d_absent": package_preflight.get(
                "formal_readback_targets_absent"
            )
            is True,
            "installed_runtime_d_absent": installed_preflight.get(
                "formal_readback_targets_absent"
            )
            is True,
            "server_source_files_inspected": (
                package_preflight.get("server_source_files_inspected")
                or installed_preflight.get("server_source_files_inspected")
            ),
        },
        "execution": {
            "compile_exit_status": int(signal["compile_status"]),
            "simulation_exit_status": int(signal["simulation_status"]),
            "signal": signal["signal"],
            "natural_terminal": formal["natural_completion"],
            "host_total_seconds": (
                timing["final_epoch_ns"] - timing["package_start_epoch_ns"]
            )
            / 1e9,
            "simulation_seconds": (
                timing["final_epoch_ns"] - timing["sim_start_epoch_ns"]
            )
            / 1e9,
            "sim_interrupt_time": int(
                re.search(r"Interrupt at time (\d+)", sim_log).group(1)
            ),
        },
        "observer": {
            "clock_sample_count_in_progress_log": len(clock_samples),
            "first_clock_sample": clock_samples[0] if clock_samples else None,
            "last_clock_sample": clock_samples[-1] if clock_samples else None,
            "clock_samples_monotonic": clock_monotonic,
            "clk_sg_proven_alive_after_exec_start": (
                bool(clock_samples)
                and clock_samples[-1]["clk_sg_edges"] > 0
            ),
            "first_request_chain_samples_returned": progress_text.count(
                "FIRST_REQUEST_CHAIN"
            ),
            "full_observer_returned": (
                "runs/return_observer.log" in actual_relative
            ),
            "canonical_decision_returned": (
                "evidence/CANONICAL_PROGRESS_DECISION.json"
                in actual_relative
            ),
            "actual_compile_argv_returned": (
                "evidence/actual_compile_argv.txt" in actual_relative
            ),
            "non_rate_limited_clock_sample_count": len(non_rate_limited),
            "all_clock_samples_violate_heartbeat_modulo": (
                bool(clock_samples)
                and len(non_rate_limited) == len(clock_samples)
            ),
        },
        "package_defect": {
            "classification": "UNBOUNDED_FIRST_REQUEST_CLOCK_LOG",
            "static_source_proof": unbounded_static,
            "dynamic_arbitrary_active_cycle_proof": (
                bool(non_rate_limited)
                and len(non_rate_limited) == len(clock_samples)
            ),
            "minimum_implied_clock_log_bytes": minimum_clock_log_bytes,
            "single_text_budget_bytes": single_text_budget,
            "minimum_budget_multiple": (
                minimum_clock_log_bytes / single_text_budget
                if single_text_budget
                else None
            ),
            "effect": (
                "FIRST_REQUEST_CLOCK is emitted on every clk_db negedge, "
                "not only at heartbeat; required observer/canonical evidence "
                "is therefore not returnable within the declared text budget"
            ),
        },
        "formal_d": {
            "expected_count": gate["expected_readback_count"],
            "observed_count": gate["observed_readback_count"],
            "missing_count": gate["missing_count"],
            "mismatch_byte_count": gate["mismatch_byte_count"],
            "all_terms_true": formal["all_terms_true"],
            "mismatch_zero_not_numeric_pass": True,
        },
        "first_divergence": {
            "last_good": (
                "compile/elaboration, EXEC_START, clk_db snapshot execution, "
                "and monotonically advancing clk_sg edge count"
            ),
            "first_unobserved": (
                "slice_start_run -> LC4 -> LC2/6 -> LC13/18 -> "
                "MSE0/MSE4 -> first request"
            ),
            "downstream_bad": (
                "no natural terminal and formal D observed 0/28"
            ),
        },
        "hang_root_cause": {
            "execution_state": "LONG_RUNNING_HANG_PENDING_ROOT_CAUSE",
            "functional_root_cause": (
                "UNRESOLVED_AFTER_EXEC_START_WITH_CLK_SG_ALIVE_TO_FIRST_REQUEST"
            ),
            "package_root_cause": (
                "DETERMINISTIC_UNBOUNDED_FIRST_REQUEST_CLOCK_EMITTER"
            ),
            "claim_boundary": (
                "clock progress closes the v10 gated-clock-silence hypothesis; "
                "missing qualified chain prevents LC/MSE functional attribution"
            ),
        },
        "stage_gates": {"E3": False, "E4": False, "E5": False},
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "errors": errors,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", nargs="?", type=Path, default=DEFAULT_RETURN)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args(argv)
    report = analyze(args.return_zip)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
