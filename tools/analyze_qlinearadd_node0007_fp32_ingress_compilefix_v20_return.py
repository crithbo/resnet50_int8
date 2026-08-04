from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURN_ROOT = "r5_qadd_n7_fp32_ingress_compilefix_v20_return"
SOURCE_ROOT = "r5_qadd_n7_fp32_ingress_compilefix_v20"
SOURCE_ZIP = ROOT / (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_fp32_ingress_compilefix_v20.zip"
)
RETURN_SHA = "fd874e7d0f2ded42a31288bfa273c9fe32323c15455d256fb2cb01e66d0563d7"
RETURN_BYTES = 179_242
SOURCE_SHA = "13aabd82d62eb1fa25145919c08aa3402de648ac42e401f21e3199f91d53da51"
SOURCE_BYTES = 38_041_268


class AnalysisError(ValueError):
    pass


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_zip(path: Path, root: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise AnalysisError(f"CRC failure: {bad}")
        names = [item.filename for item in archive.infolist()]
        if len(names) != len(set(names)):
            raise AnalysisError("duplicate ZIP member")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or stat.S_ISLNK(mode)
            ):
                raise AnalysisError(f"unsafe ZIP member: {info.filename}")
            if info.is_dir():
                continue
            prefix = root + "/"
            if not info.filename.startswith(prefix):
                raise AnalysisError(f"root mismatch: {info.filename}")
            rel = info.filename[len(prefix) :]
            if not rel or rel in files:
                raise AnalysisError(f"empty/duplicate path: {info.filename}")
            files[rel] = archive.read(info)
    if roots != {root}:
        raise AnalysisError(f"root exact-set differs: {sorted(roots)}")
    return files, {
        "crc_valid": True,
        "root": root,
        "single_exact_root": True,
        "file_count": len(files),
        "duplicates": 0,
        "symlinks": 0,
        "unsafe_paths": 0,
    }


def json_obj(files: dict[str, bytes], name: str) -> dict[str, Any]:
    value = json.loads(files[name])
    if not isinstance(value, dict):
        raise AnalysisError(f"{name} is not an object")
    return value


def records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    value = manifest.get("files")
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {
            item["path"]: {
                "sha256": item["sha256"],
                "size_bytes": item["size_bytes"],
            }
            for item in value
        }
    raise AnalysisError("manifest files absent")


def parse_kv(payload: bytes) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in payload.decode(errors="replace").splitlines()
        if "=" in line
    )


def extract_once(files: dict[str, bytes], destination: Path) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    receipt = []
    for name, payload in sorted(files.items()):
        target = destination.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != payload:
            raise AnalysisError(f"existing extraction differs: {target}")
        if not target.exists():
            target.write_bytes(payload)
        receipt.append(
            {"path": name, "size_bytes": len(payload), "sha256": sha_bytes(payload)}
        )
    return {
        "path": str(destination),
        "file_count": len(receipt),
        "tree_receipt_sha256": sha_bytes(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        ),
    }


def analyze(return_zip: Path, extract_root: Path) -> dict[str, Any]:
    if return_zip.stat().st_size != RETURN_BYTES or sha_file(return_zip) != RETURN_SHA:
        raise AnalysisError("return transport bytes/SHA differ")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or sha_file(SOURCE_ZIP) != SOURCE_SHA:
        raise AnalysisError("frozen source package bytes/SHA differ")

    returned, return_structure = load_zip(return_zip, RETURN_ROOT)
    source, source_structure = load_zip(SOURCE_ZIP, SOURCE_ROOT)
    ret_manifest = json_obj(returned, "RETURN_MANIFEST.json")
    source_manifest = json_obj(source, "TEST_PACKAGE_MANIFEST.json")
    declared = records(ret_manifest)
    observed = {
        name: {"sha256": sha_bytes(payload), "size_bytes": len(payload)}
        for name, payload in returned.items()
        if name != "RETURN_MANIFEST.json"
    }
    manifest_exact = declared == observed
    allowlist = {item["target_path"] for item in source_manifest["return_allowlist"]}
    allowlist_exact = set(observed) <= allowlist
    source_binding = (
        returned["evidence/PACKAGE_MANIFEST.json"]
        == source["TEST_PACKAGE_MANIFEST.json"]
    )

    preflight = json_obj(returned, "evidence/package_preflight.json")
    installed = json_obj(returned, "evidence/installed_preflight.json")
    gate = json_obj(returned, "evidence/SERVER_RESULT_GATE.json")
    canonical = json_obj(returned, "evidence/CANONICAL_PROGRESS_DECISION.json")
    feature = parse_kv(returned["evidence/fp32_ingress_feature_receipt.txt"])
    signal = parse_kv(returned["evidence/signal_status.txt"])
    timing = {
        key: int(value)
        for key, value in parse_kv(returned["evidence/host_timing.txt"]).items()
    }
    sim_text = returned["runs/sim.log"].decode(errors="replace")
    observer = returned["runs/return_observer.log"].decode(errors="replace")
    compile_exit = int(returned["evidence/compile_exit_status.txt"].decode().strip())
    simulation_exit = int(
        returned["evidence/simulation_exit_status.txt"].decode().strip()
    )
    stage_starts = [int(v) for v in re.findall(r"\[(\d+)\] INFO: slice start", sim_text)]
    stage_finishes = [
        (int(t), int(c))
        for t, c in re.findall(
            r"\[(\d+)\] INFO: slice completed after (\d+) cycles", sim_text
        )
    ]
    delta_match = re.search(
        r"Possible zero delay loop\..*?time\s+(\d+) ps", sim_text, re.S
    )
    interrupt_match = re.search(r"Interrupt at time (\d+)", sim_text)
    if len(stage_starts) != 2 or len(stage_finishes) != 1 or not delta_match:
        raise AnalysisError("returned stage/delta-loop signature differs")

    warning_ps = int(delta_match.group(1))
    interrupt_ps = int(interrupt_match.group(1)) if interrupt_match else None
    stage2_start_ps = stage_starts[1]
    clock_ps = 1250
    active_cycles_to_warning = (warning_ps - stage2_start_ps) / clock_ps
    qadd_samples = re.findall(
        r"(?m)^(\d+) \| QADD_FP32_INGRESS \| (.+)$", observer
    )
    exec_samples = re.findall(
        r"(?m)^(\d+) \| (EXEC_START|COMP_FINISH|HEARTBEAT) \| (.+)$",
        observer,
    )
    if not qadd_samples or not exec_samples:
        raise AnalysisError("qualified observer evidence absent")

    expected = int(gate["expected_readback_count"])
    present = int(gate["observed_readback_count"])
    missing = int(gate["missing_count"])
    mismatch = int(gate["mismatch_byte_count"])
    conjunction = gate.get("result_gate_conjunction", {})
    natural = bool(
        gate.get("natural_terminal", conjunction.get("natural_completion", False))
    )
    formal_missing = [
        name
        for name in ret_manifest["required_missing"]
        if "matrix_D_linearized_128bit.txt" in name
    ]
    runtime_d = [
        name
        for name in source
        if re.search(
            r"workload/runtime/install/.+/matrix_D_linearized_128bit\.txt$", name
        )
    ]
    result_gate = (
        compile_exit == 0
        and simulation_exit == 0
        and natural
        and present == expected
        and missing == 0
        and mismatch == 0
    )
    wall_seconds = (
        timing["final_epoch_ns"] - timing["sim_start_epoch_ns"]
    ) / 1_000_000_000
    checks = {
        "return_manifest_exact_set_size_sha": manifest_exact,
        "return_allowlist_subset": allowlist_exact,
        "returned_source_manifest_byte_binding": source_binding,
        "package_preflight_valid": preflight.get("valid") is True,
        "installed_preflight_valid": installed.get("valid") is True,
        "runtime_formal_d_initially_absent": not runtime_d,
        "compile_passed": compile_exit == 0,
        "simulation_interrupted": simulation_exit == 125,
        "signal_int": signal.get("signal") == "INT",
        "no_natural_terminal": not natural,
        "formal_d_28_all_missing": (
            expected == 28
            and present == 0
            and missing == 28
            and len(formal_missing) == 28
        ),
        "mismatch_zero_unevaluable": mismatch == 0 and missing > 0,
        "observer_four_way_active": all(
            feature.get(key) == "true"
            for key in ("argv_enabled", "time0_marker", "returned_snapshot_marker")
        ),
        "a_dequant_completed": stage_finishes[0][1] == 559_628,
        "b_dequant_started_and_progressed": warning_ps > stage2_start_ps,
        "vcs_zero_delay_warning": bool(delta_match),
        "server_result_gate_false": result_gate is False,
    }
    if not all(checks.values()):
        raise AnalysisError(
            f"formal return checks failed: {[k for k, v in checks.items() if not v]}"
        )

    return {
        "schema": "qlinearadd-node0007-v20-return-analysis-v1",
        "analysis_owner_thread": "019fa2c0-b647-7a91-93bf-d21a173487e3",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "status": "RETURN_ANALYSIS_COMPLETE",
        "return_transport": {
            "path": str(return_zip),
            "bytes": RETURN_BYTES,
            "sha256": RETURN_SHA,
            "adjacent_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY",
            "rule_id": "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
        },
        "source_package": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "bytes": SOURCE_BYTES,
            "sha256": SOURCE_SHA,
            "new_status": "QUARANTINED_DYNAMIC_ZERO_DELAY_LOOP",
        },
        "zip_structure": return_structure,
        "source_zip_structure": source_structure,
        "identity": {
            "return_root": RETURN_ROOT,
            "install_name": source_manifest["install_name"],
            "return_manifest_exact_set": manifest_exact,
            "allowlist_valid": allowlist_exact,
            "returned_source_manifest_byte_equal": source_binding,
        },
        "checks": checks,
        "execution": {
            "compile_exit": compile_exit,
            "simulation_exit": simulation_exit,
            "runner_exit": simulation_exit,
            "signal": signal.get("signal"),
            "natural_terminal": natural,
            "simulation_started": True,
            "sim_wall_seconds": wall_seconds,
            "stage_starts_ps": stage_starts,
            "stage_completions": [
                {"time_ps": time, "active_cycles": cycles}
                for time, cycles in stage_finishes
            ],
            "vcs_infl_delta_time_ps": warning_ps,
            "interrupt_time_ps": interrupt_ps,
            "op_b_active_cycles_to_delta_warning": active_cycles_to_warning,
        },
        "observer": {
            "feature_receipt": feature,
            "qualified_samples": len(qadd_samples),
            "base_event_samples": len(exec_samples),
            "canonical_record_returned": canonical,
            "canonical_record_adjudication": (
                "REJECTED_STAGE_SCOPE: stage 2 is op_b_dequant, not fp32_add; "
                "single-sided MSE0/Buffer0/GA activity cannot close the frozen "
                "dual-ingress FP32-add boundary"
            ),
            "deep_counter_cap_is_not_stall": True,
        },
        "formal_d": {
            "expected": expected,
            "present": present,
            "missing": missing,
            "mismatch_byte_count": mismatch,
            "mismatch_evaluable": False,
        },
        "SERVER_RESULT_GATE": result_gate,
        "E3": False,
        "E4": False,
        "E5": False,
        "LAST_PROVEN_GOOD": (
            "OP_A_DEQUANT_COMP_FINISH_AND_OP_B_DEQUANT_QUALIFIED_PROGRESS"
        ),
        "FIRST_DIVERGENCE": (
            "OP_B_DEQUANT_VCS_INFL_DELTA_AT_17020861875PS_"
            "ABOUT_154000_ACTIVE_CYCLES"
        ),
        "HANG_ROOT_CAUSE": (
            "UNRESOLVED_ZERO_DELAY_LOOP_WITHIN_OP_B_DEQUANT_AFTER_"
            "QUALIFIED_PROGRESS"
        ),
        "split_execution_adjudication": {
            "approved_strategy": [
                "A_DEQUANT",
                "B_DEQUANT",
                "RELOCATION_PAD",
                "FP32_ADD",
                "EXACT_UINT8_TAIL",
            ],
            "next_minimal_segment": "B_DEQUANT_ONLY",
            "reason": (
                "A completed; B is independent and consumes the original B input, "
                "so isolating B removes repeated A runtime without replaying a "
                "host-precomputed internal tensor"
            ),
            "final_full_chain_still_required": True,
        },
        "blocker_delta": {
            "opened": ["B_QADD_NODE0007_OP_B_DEQUANT_ZERO_DELAY_LOOP"],
            "kept_open": [
                "B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED"
            ],
            "closed": ["B_QADD_V19_OBSERVER_GA_OPERAND_CAPTURE_MON_UNDECLARED"],
        },
        "successor_required": "B_DEQUANT_ONLY_NARROW_DIAGNOSTIC",
        "rule_confirmation": {
            "status": "CURRENT_RULES_SUFFICIENT",
            "evidence": (
                "ordered-stage canonical and qualified-event rules already reject "
                "the returned one-sided stage-2 sample as FP32-add success; the "
                "continuous-closure rule requires the isolated B successor"
            ),
        },
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "configuration_recomputed": False,
        "functional_rtl_modified": False,
        "extraction": extract_once(returned, extract_root),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extract-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = analyze(args.return_zip, args.extract_root)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as exc:
        print(f"analysis failed: {exc}")
        return 1
    print(json.dumps({"status": report["status"], "report": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
