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
RETURN_ROOT = "r5_qadd_n7_fp32_ingress_diag_v19_return"
SOURCE_ROOT = "r5_qadd_n7_fp32_ingress_diag_v19"
SOURCE_ZIP = ROOT / (
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_fp32_ingress_diag_v19.zip"
)
RETURN_SHA = "548bb94b570f80878d6b45305b69a4f6a51df7e1ea9157a1788c123b35ca610c"
RETURN_BYTES = 45_494
SOURCE_SHA = "f32abc4b2b91bf5e854ab113aa98fd1f7925e68a3bd8958f2454762a524709ba"
SOURCE_BYTES = 38_038_498


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
    result: dict[str, bytes] = {}
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
            if not rel or rel in result:
                raise AnalysisError(f"empty/duplicate path: {info.filename}")
            result[rel] = archive.read(info)
    if roots != {root}:
        raise AnalysisError(f"root exact-set differs: {sorted(roots)}")
    return result, {
        "crc_valid": True,
        "root": root,
        "single_exact_root": True,
        "file_count": len(result),
        "duplicates": 0,
        "symlinks": 0,
        "unsafe_paths": 0,
    }


def json_obj(files: dict[str, bytes], name: str) -> dict[str, Any]:
    value = json.loads(files[name])
    if not isinstance(value, dict):
        raise AnalysisError(f"{name} is not an object")
    return value


def manifest_records(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    value = manifest.get("files")
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {
            item["path"]: {
                "size_bytes": item["size_bytes"],
                "sha256": item["sha256"],
            }
            for item in value
        }
    raise AnalysisError("RETURN_MANIFEST files absent")


def extract_once(files: dict[str, bytes], destination: Path) -> dict[str, Any]:
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for name, payload in sorted(files.items()):
        target = destination.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != payload:
            raise AnalysisError(f"existing extraction differs: {target}")
        if not target.exists():
            target.write_bytes(payload)
        records.append({"path": name, "size_bytes": len(payload), "sha256": sha_bytes(payload)})
    return {
        "path": str(destination),
        "file_count": len(records),
        "tree_receipt_sha256": sha_bytes(
            json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
        ),
    }


def parse_status(text: str) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in text.splitlines()
        if "=" in line
    )


def analyze(return_zip: Path, extract_root: Path) -> dict[str, Any]:
    if return_zip.stat().st_size != RETURN_BYTES or sha_file(return_zip) != RETURN_SHA:
        raise AnalysisError("return transport bytes/SHA differ")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or sha_file(SOURCE_ZIP) != SOURCE_SHA:
        raise AnalysisError("frozen source package bytes/SHA differ")
    returned, return_structure = load_zip(return_zip, RETURN_ROOT)
    source, source_structure = load_zip(SOURCE_ZIP, SOURCE_ROOT)
    ret_manifest = json_obj(returned, "RETURN_MANIFEST.json")
    source_manifest = json_obj(source, "TEST_PACKAGE_MANIFEST.json")
    declared = manifest_records(ret_manifest)
    observed = {
        name: {"size_bytes": len(payload), "sha256": sha_bytes(payload)}
        for name, payload in returned.items()
        if name != "RETURN_MANIFEST.json"
    }
    manifest_exact = observed == declared
    allowlist = {item["target_path"] for item in source_manifest["return_allowlist"]}
    allowlist_exact = set(observed) <= allowlist
    source_manifest_returned = returned["evidence/PACKAGE_MANIFEST.json"]
    source_binding = source_manifest_returned == source["TEST_PACKAGE_MANIFEST.json"]

    preflight = json_obj(returned, "evidence/package_preflight.json")
    install_preflight = json_obj(returned, "evidence/installed_preflight.json")
    gate = json_obj(returned, "evidence/SERVER_RESULT_GATE.json")
    canonical = json_obj(returned, "evidence/CANONICAL_PROGRESS_DECISION.json")
    compile_status = parse_status(returned["evidence/compile_exit_status.txt"].decode())
    sim_status = parse_status(returned["evidence/simulation_exit_status.txt"].decode())
    signal_status = parse_status(returned["evidence/signal_status.txt"].decode())
    feature = parse_status(returned["evidence/fp32_ingress_feature_receipt.txt"].decode())
    compile_text = (
        returned["runs/compile.log"].decode(errors="replace")
        + "\n"
        + returned["runs/compile_driver.log"].decode(errors="replace")
    )
    error_match = re.search(
        r"Error-\[IND\] Identifier not declared.*?"
        r"qlinearadd_node0007_fp32_ingress_observer_tail_v19\.svh,\s*240.*?"
        r"Identifier '([^']+)' has not been declared yet\.",
        compile_text,
        re.S,
    )
    if not error_match or error_match.group(1) != "return_obs_ga_operand_capture_mon":
        raise AnalysisError("unique returned compile error does not match frozen diagnosis")

    required_missing = sorted(set(ret_manifest["required_missing"]))
    formal_d_missing = sorted(name for name in required_missing if "matrix_D_linearized" in name)
    runtime_d = [
        name for name in source
        if re.search(r"workload/runtime/install/.+/matrix_D_linearized_128bit\.txt$", name)
    ]
    compile_exit = int(returned["evidence/compile_exit_status.txt"].decode().strip())
    simulation_exit = int(returned["evidence/simulation_exit_status.txt"].decode().strip())
    mismatch = int(gate.get("mismatch_byte_count", 0))
    natural = bool(gate.get("natural_terminal", False))
    expected = int(gate.get("expected_readback_count", 28))
    present = int(gate.get("observed_readback_count", 0))
    missing = int(gate.get("missing_count", 28))
    result_gate = (
        compile_exit == 0
        and simulation_exit == 0
        and natural
        and present == expected
        and missing == 0
        and mismatch == 0
    )
    checks = {
        "return_manifest_exact_set_size_sha": manifest_exact,
        "return_allowlist_subset": allowlist_exact,
        "returned_source_manifest_byte_binding": source_binding,
        "package_preflight_valid": preflight.get("valid") is True,
        "installed_preflight_valid": install_preflight.get("valid") is True,
        "runtime_formal_d_initially_absent": not runtime_d,
        "compile_failed_before_simulation": compile_exit == 2 and simulation_exit == 125,
        "signal_none": signal_status.get("signal") == "NONE",
        "no_natural_terminal": not natural,
        "formal_d_28_all_missing": expected == 28 and present == 0 and missing == 28 and len(formal_d_missing) == 28,
        "mismatch_zero_unevaluable": mismatch == 0 and missing > 0,
        "feature_not_started": all(feature.get(key) == "false" for key in ("argv_enabled", "time0_marker", "returned_snapshot_marker")),
        "canonical_fail_closed_at_feature_marker": (
            canonical.get("decision") == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
            and canonical.get("boundary") == "FP32_INGRESS_FEATURE_TIME0_MARKER"
        ),
        "server_result_gate_false": result_gate is False,
    }
    if not all(checks.values()):
        raise AnalysisError(f"formal return checks failed: {[k for k, v in checks.items() if not v]}")
    return {
        "schema": "qlinearadd-node0007-v19-return-analysis-v1",
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
            "new_status": "QUARANTINED_OBSERVER_COMPILE_IDENTIFIER_UNDECLARED",
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
            "signal": signal_status.get("signal"),
            "natural_terminal": natural,
            "simulation_started": False,
            "compile_error_file": "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh",
            "compile_error_line": 240,
            "undeclared_identifier": error_match.group(1),
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
        "LAST_PROVEN_GOOD": "VCS_PARSED_QADD_FP32_INGRESS_OBSERVER_THROUGH_LINE_239",
        "FIRST_DIVERGENCE": "OBSERVER_V19_LINE_240_UNDECLARED_RETURN_OBS_GA_OPERAND_CAPTURE_MON",
        "HANG_ROOT_CAUSE": "NOT_APPLICABLE_COMPILE_FAILED_BEFORE_SIMULATION",
        "package_root_cause": (
            "v19 tail consumes return_obs_ga_operand_capture_mon without a "
            "declaration/XMR binding; the functional workload was never run"
        ),
        "blocker_delta": {
            "opened": ["B_QADD_V19_OBSERVER_GA_OPERAND_CAPTURE_MON_UNDECLARED"],
            "kept_open": ["B_QADD_NODE0007_FP32_DUAL_INGRESS_FIRST_ACCEPT_UNRESOLVED"],
            "closed": [],
        },
        "successor_required": "FRESH_PACKAGE_LOCAL_OBSERVER_COMPILE_FIX",
        "rule_delta_proposal": "NONE_CURRENT_RULES_SUFFICIENT",
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "configuration_changed": False,
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
    print(json.dumps({"status": report["status"], "report": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
