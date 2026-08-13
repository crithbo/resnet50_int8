#!/usr/bin/env python3
"""Family audit for the p28 instance-order-stable Buffer5 diagnostic."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p27_b5release_package as previous
from generate_server_source_bound_observer import validate_final_zip


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p28_b5release"
SOURCE_ID = "r5_n4_0cc_p27_b5release"
SOURCE_SHA256 = "ed8fe444aa1f85c8b845037b29118d6e2aa8410567bad3effaece0f677a5eeae"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
LEGACY_OBSERVER_SHA256 = "e54a72e0f6e96f0ae26b33312881c71fb4927d4c4986da895ab18c026322daf1"
base = previous.base


def output_argument() -> Path:
    for index, value in enumerate(sys.argv):
        if value == "--output" and index + 1 < len(sys.argv):
            return Path(sys.argv[index + 1]).resolve()
    raise base.ValidationError("--output is required")


def zip_argument() -> Path:
    for index, value in enumerate(sys.argv):
        if value == "--zip" and index + 1 < len(sys.argv):
            return Path(sys.argv[index + 1]).resolve()
    raise base.ValidationError("--zip is required")


def parser_trace(parser_bytes: bytes) -> dict[str, object]:
    boundaries = (
        "memory_read_response",
        "buffer5_last_write_state",
        "buffer5_blocked_read_response",
        "buffer5_blocked_output_accept",
        "buffer5_last_write_terminal",
    )
    cases = {
        "no_mrm_read_response": {
            "memory": (0, 0),
            "blocked": (0, 2),
            "expected": "MRM_READ_REQUEST_OR_RESPONSE_ABSENT",
        },
        "prior_mrm_response_only": {
            "memory": (1, 3),
            "blocked": (0, 2),
            "expected": "NO_MRM_RESPONSE_DURING_FINAL_BLOCKED_INTERVAL",
        },
        "mrm_response_during_block_no_terminal": {
            "memory": (1, 3),
            "blocked": (1, 3),
            "expected": "BUFFER_READY_NOT_RELEASED_AFTER_BLOCKED_INTERVAL_READ_RESPONSE",
        },
    }
    results: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="p28_parser_trace_") as temporary:
        root = Path(temporary)
        parser = root / "source_bound_causal_parser.py"
        parser.write_bytes(parser_bytes)
        for name, case in cases.items():
            lines = [
                f"CODEX_PROBE_V1 kind=ENABLED boundary={boundary} instance=tb.dut.{boundary}.probe"
                for boundary in boundaries
            ]
            lines += [
                (
                    "CODEX_PROBE_V1 kind=SUMMARY boundary=buffer5_last_write_state "
                    "instance=tb.dut.b5.probe count=1 state=1 first=10 last=20 maxgap=0 sticky=3 xor=0"
                ),
                (
                    "CODEX_PROBE_V1 kind=SUMMARY boundary=memory_read_response "
                    f"instance=tb.dut.mrm.probe count={case['memory'][0]} state=0 first=1 last=9 maxgap=0 sticky={case['memory'][1]:x} xor=0"
                ),
                (
                    "CODEX_PROBE_V1 kind=SUMMARY boundary=buffer5_blocked_read_response "
                    f"instance=tb.dut.b5.probe count={case['blocked'][0]} state=1 first=20 last=30 maxgap=0 sticky={case['blocked'][1]:x} xor=0"
                ),
            ]
            # A later zero-count sibling must not erase a class seen by the
            # target cone when the generated module is bound to many instances.
            lines += [
                (
                    "CODEX_PROBE_V1 kind=SUMMARY boundary=buffer5_last_write_state "
                    "instance=tb.dut.trailing_buffer.probe count=0 state=0 first=0 last=0 maxgap=0 sticky=0 xor=0"
                ),
                (
                    "CODEX_PROBE_V1 kind=SUMMARY boundary=memory_read_response "
                    "instance=tb.dut.trailing_mrm.probe count=0 state=0 first=0 last=0 maxgap=0 sticky=0 xor=0"
                ),
                (
                    "CODEX_PROBE_V1 kind=SUMMARY boundary=buffer5_blocked_read_response "
                    "instance=tb.dut.trailing_buffer.probe count=0 state=0 first=0 last=0 maxgap=0 sticky=0 xor=0"
                ),
            ]
            log = root / f"{name}.log"
            decision = root / f"{name}.json"
            log.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
            completed = subprocess.run(
                [sys.executable, str(parser), "--log", str(log), "--output", str(decision)],
                capture_output=True,
                text=True,
                check=False,
            )
            value = json.loads(decision.read_text(encoding="utf-8"))
            results[name] = {
                "exit_code": completed.returncode,
                "decision": value.get("decision"),
                "pass": completed.returncode == 0 and value.get("decision") == case["expected"],
            }
        bad = root / "missing_enable.log"
        bad.write_text(
            "CODEX_PROBE_V1 kind=SUMMARY boundary=buffer5_last_write_state instance=tb.dut.b5.probe count=1 state=1 first=1 last=2 maxgap=0 sticky=3 xor=0\n",
            encoding="utf-8",
            newline="\n",
        )
        bad_decision = root / "missing_enable.json"
        completed = subprocess.run(
            [sys.executable, str(parser), "--log", str(bad), "--output", str(bad_decision)],
            capture_output=True,
            text=True,
            check=False,
        )
        bad_value = json.loads(bad_decision.read_text(encoding="utf-8"))
        results["missing_enable_fail_closed"] = {
            "exit_code": completed.returncode,
            "decision": bad_value.get("decision"),
            "pass": completed.returncode != 0 and bad_value.get("decision") == "EVIDENCE_INCOMPLETE",
        }
    return {
        "schema": "conv-native-four-lane-p28-source-bound-parser-trace-v1",
        "cases": results,
        "valid": all(bool(item["pass"]) for item in results.values()),
    }


def main() -> int:
    previous.PACKAGE_ID = PACKAGE_ID
    previous.SOURCE_ID = SOURCE_ID
    previous.SOURCE_ZIP = SOURCE_ZIP
    previous.SOURCE_SHA256 = SOURCE_SHA256
    rc = previous.main()
    output = output_argument()
    report = json.loads(output.read_text(encoding="utf-8"))
    zip_path = zip_argument()
    final_zip = validate_final_zip(zip_path)
    with zipfile.ZipFile(zip_path) as archive, zipfile.ZipFile(SOURCE_ZIP) as source:
        prefix = PACKAGE_ID + "/"
        source_prefix = SOURCE_ID + "/"
        runner = archive.read(prefix + "PREPARE_AND_RUN.sh").decode()
        manifest = json.loads(archive.read(prefix + "package_manifest.json"))
        legacy_observer = archive.read(prefix + "tb_probe/native_return_observer.svh")
        parser_bytes = archive.read(prefix + "package_tools/source_bound_causal_parser.py")
        generation = json.loads(archive.read(prefix + "diagnostics/source_bound_generation_report.json"))
        binding = json.loads(archive.read(prefix + "diagnostics/source_bound_probe_binding.json"))
        frozen_names = sorted(
            name[len(source_prefix) :]
            for name in source.namelist()
            if name.startswith(source_prefix + "workload/runtime/runs/c0/install/") and not name.endswith("/")
        )
        frozen_equal = all(
            archive.read(prefix + relative) == source.read(source_prefix + relative)
            for relative in frozen_names
        )
    trace = parser_trace(parser_bytes)
    source_bound = manifest.get("source_bound_observer_binding", {})
    checks = {
        "inherited_family_audit": report.get("valid") is True and rc == 0,
        "frozen_87_installed_payload": len(frozen_names) == 87 and frozen_equal,
        "legacy_observer_byte_equal": base.digest(legacy_observer) == LEGACY_OBSERVER_SHA256,
        "source_bound_generation_pass": generation.get("pass") is True and not generation.get("errors"),
        "source_bound_final_zip_exact_regeneration": final_zip.get("pass") is True and not final_zip.get("errors"),
        "source_bound_binding_no_xmr": (
            binding.get("private_hierarchical_xmr_generated") is False
            and binding.get("free_form_hdl_identifiers_accepted") is False
        ),
        "runner_compile_binding": (
            runner.count("$source_bound_observer") == 2
            and "source_bound_causal_observer.svh" in runner
        ),
        "runner_runtime_binding": runner.count("+CODEX_CAUSAL_OBSERVER") == 2,
        "runner_parser_return_binding": (
            runner.count('python3 "$source_bound_parser"') == 1
            and "source_bound_causal.log" in runner
            and "source_bound_causal_decision.json" in runner
        ),
        "generated_parser_trace": trace["valid"] is True,
        "manifest_required_next_fresh": (
            source_bound.get("enforcement") == "required_next_fresh"
            and source_bound.get("legacy_observer_byte_equal_p26") is True
            and manifest["release_gate_matrix"]["source_bound_observer_generation"]["pass"] is True
        ),
        "diagnostic_only_claim_boundary": (
            manifest.get("candidate_release") is False
            and manifest.get("candidate_class") == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest["source_p26_formal_return_analysis"]["formal_D_claimed"] is False
        ),
    }
    valid = all(checks.values())
    report.update(
        {
            "schema": "conv-native-four-lane-p28-source-bound-family-audit-v1",
            "status": "PASS" if valid else "FAIL",
            "valid": valid,
            "errors": [name for name, passed in checks.items() if not passed],
            "p28_checks": checks,
            "source_bound_final_zip": final_zip,
            "source_bound_parser_trace": trace,
            "source_scope": {
                "source_package_identity": SOURCE_ID,
                "source_zip_sha256": SOURCE_SHA256,
                "changed_surface": "fresh identity, generated diagnostic observer/parser/binding, and runner four-way binding",
                "installed_payload_or_config_or_rtl_changed": False,
            },
        }
    )
    report["release_gate_matrix"]["source_bound_observer_generation"] = {
        "applicability": "blocking_applicable",
        "enforcement": "required_next_fresh",
        "pass": checks["source_bound_generation_pass"] and checks["generated_parser_trace"],
    }
    report["release_gate_matrix"]["source_bound_final_zip"] = {
        "applicability": "blocking_applicable",
        "enforcement": "required_next_fresh",
        "pass": checks["source_bound_final_zip_exact_regeneration"],
    }
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
