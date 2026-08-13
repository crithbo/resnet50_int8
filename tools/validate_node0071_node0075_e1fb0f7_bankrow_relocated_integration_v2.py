#!/usr/bin/env python3
"""Independent validation of the bank-row-relocated joint integration."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEST_ID = "r5-node0071-node0075-e1fb0f7-bankrow-relocated-integration-v2"
OUT = ROOT / "artifacts/operator_config_validation" / TEST_ID
WORKLOAD = OUT / "workload"
N71 = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n71_gap_v37_dbclk_rdready_compilefix"
)
N75_STEM = "node0075_e1fb0f7_bankrow_relocated_eight_pass_target_v2"
N75_PIPELINE = ROOT / "ndp-sim/model_execplan/output" / N75_STEM
N75_VALIDATION = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0075-e1fb0f7-bankrow-relocated-eight-pass-materializer-v2/"
    "determinism_and_config_binding_validation.json"
)
RETURN_ANALYSIS = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0071-node0075-e1fb0f7-native-v5-return-analysis/report.json"
)
HELPER = ROOT / "tools/validate_node0071_node0075_e1fb0f7_native_ordering_integration.py"
EXEC_BASE = 0x002ACC00
N71_CONFIG_BASE = 0x002AAC00
FINAL_D_BASE = 0x002A4800
PREFIX = f"install/cfg_pkg/{TEST_ID}/"
BITS128 = re.compile(r"[01]{128}")
SLICE_BYTES = 1 << 25


class ValidationError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"JSON root differs: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def decode_128(path: Path) -> bytes:
    chunks: list[bytes] = []
    for number, line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        if not BITS128.fullmatch(line):
            raise ValidationError(f"128-bit ABI differs: {path}:{number}")
        chunks.append(int(line, 2).to_bytes(16, "little"))
    if not chunks:
        raise ValidationError(f"empty 128-bit payload: {path}")
    return b"".join(chunks)


def physical(byte_addr: int) -> dict[str, int | bool]:
    local = byte_addr & (SLICE_BYTES - 1)
    line = local >> 4
    return {
        "bank": (line >> 19) & 3,
        "row": (line >> 6) & 0x1FFF,
        "column": line & 0x3F,
        "valid": ((line >> 6) & 0x1FFF) < 6144,
    }


def load_helper():
    spec = importlib.util.spec_from_file_location("integration_validator_helper", HELPER)
    if spec is None or spec.loader is None:
        raise ValidationError(f"cannot load helper: {HELPER}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.N71_CONFIG_RELOC_BASE = N71_CONFIG_BASE
    return module


def fail(condition: bool, message: str, errors: list[str]) -> None:
    if condition:
        errors.append(message)


def validate() -> dict[str, Any]:
    errors: list[str] = []
    required = [
        OUT / "composite_target.json",
        OUT / "mapping_manifest.json",
        OUT / "bitstream_manifest.json",
        OUT / "execplan_manifest.json",
        OUT / "golden_manifest.json",
        OUT / "causal_transaction_ledger.json",
        OUT / "boundary_microtrace.json",
        OUT / "report.json",
        OUT / "artifact_manifest.json",
        WORKLOAD / "sca_cfg.json",
        WORKLOAD / "sca_cfg_D.json",
        WORKLOAD / "install/execplan.txt",
        N75_VALIDATION,
        RETURN_ANALYSIS,
    ]
    fail(any(not path.is_file() for path in required), "required file missing", errors)
    if errors:
        raise ValidationError("; ".join(errors))

    target = load_json(OUT / "composite_target.json")
    report = load_json(OUT / "report.json")
    ledger = load_json(OUT / "causal_transaction_ledger.json")
    trace = load_json(OUT / "boundary_microtrace.json")
    artifact_manifest = load_json(OUT / "artifact_manifest.json")
    sca = load_json(WORKLOAD / "sca_cfg.json")
    sca_d = load_json(WORKLOAD / "sca_cfg_D.json")
    n75_validation = load_json(N75_VALIDATION)
    return_analysis = load_json(RETURN_ANALYSIS)

    fail(target.get("candidate_release") is not False, "candidate release widened", errors)
    fail(target.get("functional_rtl_modified") is not False, "functional RTL claim differs", errors)
    fail(len(target.get("ordered_stages", [])) != 32, "ordered stage count differs", errors)
    handoff = target.get("handoff", {})
    fail(handoff.get("a_preload_count") != 0, "A preload present", errors)
    fail(
        handoff.get("host_copy_precompute_relayout_replay") is not False,
        "host replay permitted",
        errors,
    )
    fail(handoff.get("explicit_barrier_claim") is not False, "explicit barrier claimed", errors)
    fail(handoff.get("opcode110_is_barrier") is not False, "opcode110 barrier claimed", errors)

    helper = load_helper()
    n71_lines = (
        N71 / "workload/install/execplan.txt"
    ).read_text(encoding="ascii").splitlines()
    n75_lines = (
        N75_PIPELINE / "install/execplan.txt"
    ).read_text(encoding="ascii").splitlines()
    expected_lines = helper.expected_relocated_prefix(n71_lines) + n75_lines
    combined_lines = (WORKLOAD / "install/execplan.txt").read_text(
        encoding="ascii"
    ).splitlines()
    fail(combined_lines != expected_lines, "combined execplan byte sequence differs", errors)
    counts = helper.exec_counts(combined_lines)
    fail(
        counts != {"lines": 518, "start_comp": 32, "opcode110": 8},
        "combined execplan counts differ",
        errors,
    )

    fail(int(str(sca.get("Exec_Base", "0")).replace("_", ""), 16) != EXEC_BASE,
         "Exec_Base differs", errors)
    fail(sca.get("Exec_Length") != 518, "Exec_Length differs", errors)
    fail(sca.get("Repeat_Num") != 32, "Repeat_Num differs", errors)
    dynamic = {
        key: item
        for key, item in sca.items()
        if key not in {"Exec_Base", "Exec_Length", "Repeat_Num", "ExecutionPlan"}
    }
    input_keys = [key for key in dynamic if key.startswith("node0071_input_slice")]
    n71_cfg = [key for key in dynamic if key.startswith("node0071_stage") and key.endswith("_config")]
    n75_cfg = [key for key in dynamic if key.startswith("node0075_") and key.endswith("_config")]
    b_keys = [key for key in dynamic if "_matrixB_" in key]
    a_keys = [key for key in dynamic if "_matrixA_" in key]
    fail(len(input_keys) != 16, "external input count differs", errors)
    fail(len(n71_cfg) != 8, "node0071 config count differs", errors)
    fail(len(n75_cfg) != 24, "node0075 config count differs", errors)
    fail(len(b_keys) != 128, "B preload count differs", errors)
    fail(bool(a_keys), "forbidden A preload present", errors)

    intervals: list[tuple[int, int, str]] = []
    all_physical_valid = True
    all_sca = {**dynamic, "ExecutionPlan": sca["ExecutionPlan"]}
    for key, item in all_sca.items():
        path = str(item.get("path", ""))
        fail(not path.startswith(PREFIX), f"SCA path escapes namespace: {key}", errors)
        if not path.startswith(PREFIX):
            continue
        payload = WORKLOAD / path[len(PREFIX) :]
        fail(not payload.is_file(), f"SCA payload missing: {key}", errors)
        if not payload.is_file():
            continue
        size = len(decode_128(payload))
        begin = int(str(item["base_addr"]).replace("_", ""), 16)
        end = begin + size
        intervals.append((begin, end, key))
        all_physical_valid &= physical(begin)["valid"] and physical(end - 16)["valid"]
    ordered = sorted(intervals)
    for left, right in zip(ordered, ordered[1:]):
        fail(right[0] < left[1], f"preload overlap: {left[2]}/{right[2]}", errors)
    fail(not all_physical_valid, "SCA physical bank-row invalid", errors)

    fail(len(sca_d) != 144, "formal D count differs", errors)
    runtime_paths = [str(item.get("path", "")) for item in sca_d.values()]
    fail(len(runtime_paths) != len(set(runtime_paths)), "formal D path collision", errors)
    fail(any(not path.startswith("sim_results/") for path in runtime_paths),
         "formal D path is not runtime-scoped", errors)
    fail(any((OUT / path).exists() for path in runtime_paths),
         "formal D runtime target preseeded", errors)
    for key, item in sca_d.items():
        begin = int(item["base_addr"], 16)
        end = begin + int(item["length"]) * 16
        fail(
            not physical(begin)["valid"] or not physical(end - 16)["valid"],
            f"formal D physical bank-row invalid: {key}",
            errors,
        )
    n75_first = int(sca_d["node0075_final_uint8_pass00_slice0"]["base_addr"], 16)
    fail(n75_first != FINAL_D_BASE, "node0075 relocated D base differs", errors)

    fail(ledger.get("status") != "PASS" or ledger.get("passed") is not True,
         "causal ledger failed", errors)
    fail(trace.get("status") != "PASS" or trace.get("passed") is not True,
         "boundary microtrace failed", errors)
    controls = trace.get("threshold_and_negative_controls", [])
    fail(
        any(item.get("valid") != item.get("expected") for item in controls),
        "boundary negative control escaped",
        errors,
    )
    fail(n75_validation.get("status") != "DETERMINISTIC_CONFIG_BOUND_LOCAL_E2_PASS",
         "node0075 deterministic E2 not pass", errors)
    fail(
        return_analysis.get("status")
        != "RETURN_ANALYSIS_PASS_SUCCESSOR_REQUIRED_BANKROW_RELOCATION",
        "v5 return predecessor analysis not pass",
        errors,
    )
    fail(
        report.get("status") != "CONFIG_BOUND_NATIVE_ORDERING_INTEGRATION_E2_PASS",
        "integration report status differs",
        errors,
    )
    coverage = report.get("a_consumer_configured_coverage", {})
    fail(coverage.get("reload_pass_count") != 8, "reload count differs", errors)
    fail(coverage.get("occurrence_count") != 8192, "A occurrence budget differs", errors)
    fail(coverage.get("traffic_bytes") != 262144, "A traffic budget differs", errors)
    fail(coverage.get("unique_bytes") != 32768, "A unique bytes differ", errors)

    node71_goldens = len(list((WORKLOAD / "golden/node0071").rglob("matrix_D_128bit.txt")))
    node75_goldens = len(list((WORKLOAD / "golden/node0075").rglob("matrix_D_128bit.txt")))
    fail(node71_goldens != 48, "node0071 golden file count differs", errors)
    fail(node75_goldens != 384, "node0075 golden file count differs", errors)

    records = artifact_manifest.get("files")
    fail(not isinstance(records, list), "artifact manifest records differ", errors)
    if isinstance(records, list):
        for item in records:
            path = OUT / str(item.get("path", ""))
            fail(not path.is_file(), f"manifest file missing: {path}", errors)
            if path.is_file():
                fail(path.stat().st_size != item.get("bytes"), f"size differs: {path}", errors)
                fail(sha256(path) != item.get("sha256"), f"hash differs: {path}", errors)

    result = {
        "schema": "node0071-node0075-bankrow-relocated-independent-validation-v2",
        "test_id": TEST_ID,
        "status": (
            "CONFIG_BOUND_NATIVE_ORDERING_INTEGRATION_E2_VALIDATION_PASS"
            if not errors
            else "CONFIG_BOUND_NATIVE_ORDERING_INTEGRATION_E2_VALIDATION_FAIL"
        ),
        "passed": not errors,
        "errors": errors,
        "checks": {
            "ordered_stage_count": 32,
            "execplan_lines": counts["lines"],
            "start_comp_count": counts["start_comp"],
            "opcode110_count": counts["opcode110"],
            "a_preload_count": len(a_keys),
            "b_preload_count": len(b_keys),
            "configured_a_occurrences": coverage.get("occurrence_count"),
            "configured_a_traffic_bytes": coverage.get("traffic_bytes"),
            "formal_d_count": len(sca_d),
            "node0071_golden_count": node71_goldens,
            "node0075_golden_count": node75_goldens,
            "all_sca_physical_bank_rows_valid": all_physical_valid,
            "causal_ledger": ledger.get("status"),
            "boundary_microtrace": trace.get("status"),
        },
        "claim_boundary": {
            "local_config_bound_e2": not errors,
            "server_actual_acceptance": False,
            "natural_terminal": False,
            "formal_d_runtime_match": False,
            "candidate_release": False,
        },
    }
    write_json(OUT / "validation.json", result)
    return result


def main() -> int:
    try:
        result = validate()
    except Exception as exc:
        print(f"BANKROW_RELOCATED_INTEGRATION_VALIDATION_FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
