from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (
    build_qlinearadd_node0007_nested_lc_progress_bind_v6_server_package as v6,
)
from tools import build_qlinearadd_node0007_server_package as implementation
from tools.qlinearadd_node0007_server_runtime import (
    file_records,
    preflight as runtime_preflight,
)


INSTALL_NAME = "r5_qadd_n7_progress_canon_v7"
SOURCE_INSTALL_NAME = "r5_qadd_n7_nested_lc_progress_bind_v6"
SOURCE_ZIP_SHA256 = (
    "9a48fb417b34afaa0835f8ee0bab8bb22a337808fb6e88d9e9b1205922f1ce90"
)
CONTRACT_REL = Path(
    "contracts/operator_config/"
    "qlinearadd_node0007_nested_lc_progress_canonical_diagnostic_v7.json"
)
TASK_RECORD_REL = Path(
    ".agents/task_records/"
    "20260730_qlinearadd_node0007_v6_canonical_decision_audit.md"
)
SERVER_RULE_REL = Path(".agents/rules/服务器测试包生成规则.md")
SERVER_RULE_SHA256 = (
    "ed3990f13c62ce67e5081458b0dfdcf6ca257908fe138fcc05a7000482afd2f8"
)
CANONICAL_SOURCE = ROOT / "tools/qlinearadd_progress_canonical_decision.py"
CANONICAL_REL = Path(
    "package_tools/qlinearadd_progress_canonical_decision.py"
)
CANONICAL_SHA256 = (
    "6423f96c6e2647cd30fe20cd4ad1d5291bf5c4751187bbf2dcaf4b923a8145e3"
)
PROGRESS_ALLOWLIST_COUNT = 10


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _return_allowlist(
    readbacks: list[dict[str, object]],
) -> list[dict[str, object]]:
    records = v6._return_allowlist(readbacks)
    records.extend(
        [
            {
                "source_root": "evidence",
                "source_path": "CANONICAL_PROGRESS_DECISION.json",
                "target_path": "evidence/CANONICAL_PROGRESS_DECISION.json",
                "required": True,
                "max_bytes": 8 << 20,
                "missing_meaning": (
                    "unique complete canonical progress decision unavailable"
                ),
            },
            {
                "source_root": "evidence",
                "source_path": "canonical_decision_exit_status.txt",
                "target_path": (
                    "evidence/canonical_decision_exit_status.txt"
                ),
                "required": True,
                "max_bytes": 1 << 20,
                "missing_meaning": (
                    "canonical progress decision parser exit status unavailable"
                ),
            },
        ]
    )
    return records


def _run_script() -> str:
    text = v6._run_script()
    anchor = 'progress_log="$evidence_root/progress_samples.log"\n'
    replacement = (
        anchor
        + 'decision_runtime="$package_root/package_tools/'
        + 'qlinearadd_progress_canonical_decision.py"\n'
        + 'canonical_decision="$evidence_root/'
        + 'CANONICAL_PROGRESS_DECISION.json"\n'
    )
    if text.count(anchor) != 1:
        raise RuntimeError("v6 progress-log anchor differs")
    text = text.replace(anchor, replacement, 1)

    status_anchor = "finalized=0\n"
    if text.count(status_anchor) != 1:
        raise RuntimeError("v6 status anchor differs")
    text = text.replace(
        status_anchor, status_anchor + "canonical_decision_status=125\n", 1
    )

    analyze_anchor = (
        "  printf '%s\\n' \"$simulation_status\" "
        ">\"$evidence_root/simulation_exit_status.txt\"\n"
    )
    decision_block = (
        "  printf '%s\\n' \"$simulation_status\" "
        ">\"$evidence_root/simulation_exit_status.txt\"\n"
        '  python3 "$decision_runtime" \\\n'
        '    --observer-log "$observer_log" \\\n'
        '    --progress-contract "$evidence_root/progress_contract.json" \\\n'
        '    --output "$canonical_decision"\n'
        "  canonical_decision_status=$?\n"
        "  printf '%s\\n' \"$canonical_decision_status\" "
        ">\"$evidence_root/canonical_decision_exit_status.txt\"\n"
    )
    if text.count(analyze_anchor) != 1:
        raise RuntimeError("v6 analyze anchor differs")
    text = text.replace(analyze_anchor, decision_block, 1)

    gate_anchor = (
        '  [ "$final" -ne 0 ] || [ "$analysis_status" -eq 0 ] '
        '|| final="$analysis_status"\n'
    )
    gate_replacement = (
        '  [ "$final" -ne 0 ] || '
        '[ "$canonical_decision_status" -eq 0 ] '
        '|| final="$canonical_decision_status"\n'
        + gate_anchor
    )
    if text.count(gate_anchor) != 1:
        raise RuntimeError("v6 final gate anchor differs")
    return text.replace(gate_anchor, gate_replacement, 1)


_BASE_BUILD_DIRECTORY = v6._build_directory


def _build_directory(destination: Path) -> Path:
    if sha256(CANONICAL_SOURCE) != CANONICAL_SHA256:
        raise RuntimeError("canonical parser SHA256 drifted")
    package = _BASE_BUILD_DIRECTORY(destination)
    canonical_target = package / CANONICAL_REL
    shutil.copyfile(CANONICAL_SOURCE, canonical_target)
    if sha256(canonical_target) != CANONICAL_SHA256:
        raise RuntimeError("packaged canonical parser SHA256 mismatch")

    manifest_path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = implementation.load_json(manifest_path)
    manifest.update(
        {
            "schema": (
                "qlinearadd-node0007-nested-lc-progress-canonical-"
                "server-package-v7"
            ),
            "canonical_decision_contract": {
                "rule_id": (
                    "CDA-SERVER-DIAGNOSTIC-DECISION-"
                    "CANONICAL-RECORD-001"
                ),
                "schema": "qlinearadd-progress-canonical-decision-v1",
                "version": 1,
                "parser_path": CANONICAL_REL.as_posix(),
                "parser_sha256": CANONICAL_SHA256,
                "output_path": (
                    "evidence/CANONICAL_PROGRESS_DECISION.json"
                ),
                "unique_complete_record_required": True,
                "qualified_counters": ["gexec", "req", "rdata", "wdata"],
                "raw_state_excluded_from_progress": [
                    "buf4_wr",
                    "buf4_rd",
                    "buf5_wr",
                    "buf5_rd",
                ],
                "required_fields": [
                    "schema",
                    "version",
                    "decision",
                    "reason",
                    "boundary",
                    "sample_range",
                    "qualified_counter_names",
                    "counter_snapshot",
                    "windows",
                    "content_summary",
                    "content_digest",
                ],
                "ambiguous_state": (
                    "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS"
                ),
                "summary_only_uses_canonical_prefix": False,
            },
            "default_progress_diagnostics": {
                "rule_id": "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
                "enabled_by_default": True,
                "read_only": True,
                "rate_limited": True,
                "partial_return_on_exit_and_signals": True,
                "actual_compile_argv": (
                    "evidence/actual_compile_argv.txt"
                ),
                "actual_simulator_argv": (
                    "evidence/actual_simulator_argv.txt"
                ),
                "observer_time0_receipt": (
                    "evidence/observer_binding.txt"
                ),
                "host_monotonic_wall_clock": "evidence/host_timing.txt",
                "simulation_time_and_stage_state": (
                    "runs/return_observer.log"
                ),
                "qualified_request_data_accept_completion": (
                    "runs/return_observer.log"
                ),
                "write_last_terminal_boundary": (
                    "runs/return_observer.log"
                ),
                "sample_period_seconds": 60,
                "stall_window_cycles": 1048576,
                "canonical_decision": (
                    "evidence/CANONICAL_PROGRESS_DECISION.json"
                ),
                "changes_dut_input": False,
                "changes_ready_or_backpressure": False,
                "changes_timeout": False,
                "changes_formal_readback": False,
            },
            "superseded_diagnostic": {
                "zip": (
                    "artifacts/operator_config_validation/"
                    "r5-server-test-packages/"
                    f"{SOURCE_INSTALL_NAME}.zip"
                ),
                "sha256": SOURCE_ZIP_SHA256,
                "status": (
                    "QUARANTINED_NOT_RUN_CANONICAL_DECISION_MISSING"
                ),
                "functional_workload_unchanged": True,
            },
        }
    )
    manifest["progress_localization"][
        "return_allowlist_entry_count"
    ] = PROGRESS_ALLOWLIST_COUNT
    manifest["files"] = file_records(package)
    implementation.write_json(manifest_path, manifest)
    (package / "README.md").write_text(
        "# QLinearAdd node0007 nested-LC canonical progress diagnostic v7\n\n"
        "Run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
        "```\n\n"
        "This is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. The frozen v6 "
        "workload, observer, timeout, W3 order, six qparams, tail and golden "
        "are unchanged. The only successor change is a package-local parser "
        "that publishes exactly one complete canonical progress decision. "
        "Only qualified handshake counters can establish monotonic progress; "
        "raw levels are retained as non-decisional state.\n",
        encoding="utf-8",
        newline="\n",
    )
    manifest = implementation.load_json(manifest_path)
    manifest["files"] = file_records(package)
    implementation.write_json(manifest_path, manifest)
    runtime_preflight(package)
    return package


def configure() -> None:
    v6.INSTALL_NAME = INSTALL_NAME
    v6.CONTRACT_REL = CONTRACT_REL
    v6.TASK_RECORD_REL = TASK_RECORD_REL
    v6.SERVER_RULE_REL = SERVER_RULE_REL
    v6.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    v6.PROGRESS_ALLOWLIST_COUNT = PROGRESS_ALLOWLIST_COUNT
    v6.configure()

    implementation.INSTALL_NAME = INSTALL_NAME
    implementation.MANIFEST_SCHEMA = (
        "qlinearadd-node0007-nested-lc-progress-canonical-server-package-v7"
    )
    implementation.PACKAGE_DESCRIPTION = (
        "ResNet50 node0007 canonical read-only progress diagnostic"
    )
    implementation.GENERATOR_REL = (
        "tools/"
        "build_qlinearadd_node0007_nested_lc_progress_canonical_v7_"
        "server_package.py"
    )
    implementation.CONTRACT_REL = CONTRACT_REL
    implementation.TASK_RECORD_REL = TASK_RECORD_REL
    implementation.SERVER_RULE_REL = SERVER_RULE_REL
    implementation.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    implementation.SUPERSEDED_IDENTITY = {
        "zip": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_INSTALL_NAME}.zip"
        ),
        "sha256": SOURCE_ZIP_SHA256,
        "reason": (
            "v6 binds the observer but lacks the required unique canonical "
            "decision record and parser negative controls"
        ),
        "functional_workload_unchanged": True,
    }
    implementation._return_allowlist = _return_allowlist
    implementation.run_script = _run_script
    implementation.build_directory = _build_directory


def main() -> int:
    configure()
    result = implementation.main()
    if result:
        return result
    validation_path = (
        implementation.OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json"
    )
    report = json.loads(validation_path.read_text(encoding="utf-8"))
    report.update(
        {
            "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "functional_fix": False,
            "source_v6_quarantined": True,
            "canonical_decision_rule_bound": True,
            "progress_return_allowlist_count": PROGRESS_ALLOWLIST_COUNT,
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
        }
    )
    implementation.write_json(validation_path, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
