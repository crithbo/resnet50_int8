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
IDENTITY = "r5_n71_gap_v36_dbclk_rdready_diag"
RETURN_ROOT = f"{IDENTITY}_return"
RETURN_SIZE = 50471
RETURN_SHA256 = (
    "2f8a425164bfb4dbe193e644b3a5c040a8b15b92feb62e5edc197902599852ff"
)
SOURCE_SIZE = 1826295
SOURCE_SHA256 = (
    "8835bcad4b54f6c0ec5ad225976d71631492477430e73e77f838df1d76cbf1dd"
)
OWNER = "019fa366-cb1f-7ae2-880c-f527be0680cd"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"
OBSERVER_MEMBER = "tb_probe/native_return_observer.svh"
BAD_IDENTIFIER = "return_obs_rd_spatial_mon"
GOOD_IDENTIFIER = "return_obs_rd_spatial_size_mon"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def object_json(data: bytes) -> dict[str, Any]:
    value = json.loads(data.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root is not an object")
    return value


def analyze(return_zip: Path, source_zip: Path) -> dict[str, Any]:
    errors: list[str] = []
    if return_zip.stat().st_size != RETURN_SIZE:
        errors.append("return size differs")
    if sha256_file(return_zip) != RETURN_SHA256:
        errors.append("return SHA256 differs")
    if source_zip.stat().st_size != SOURCE_SIZE:
        errors.append("source size differs")
    if sha256_file(source_zip) != SOURCE_SHA256:
        errors.append("source SHA256 differs")

    with zipfile.ZipFile(source_zip) as source:
        source_bad_crc = source.testzip()
        source_manifest_bytes = source.read(
            f"{IDENTITY}/TEST_PACKAGE_MANIFEST.json"
        )
        source_manifest = object_json(source_manifest_bytes)
        source_sca = source.read(f"{IDENTITY}/workload/sca_cfg.json")
        source_sca_d = source.read(f"{IDENTITY}/workload/sca_cfg_D.json")
        source_observer = source.read(f"{IDENTITY}/{OBSERVER_MEMBER}").decode(
            "utf-8", errors="replace"
        )

    with zipfile.ZipFile(return_zip) as archive:
        bad_crc = archive.testzip()
        infos = archive.infolist()
        names = [item.filename for item in infos]
        duplicates = sorted(
            name for name in set(names) if names.count(name) != 1
        )
        unsafe: list[str] = []
        symlinks: list[str] = []
        roots: set[str] = set()
        for item in infos:
            path = PurePosixPath(item.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in item.filename
                or not path.parts
            ):
                unsafe.append(item.filename)
            else:
                roots.add(path.parts[0])
            mode = (item.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                symlinks.append(item.filename)
        if bad_crc is not None:
            errors.append(f"CRC failed at {bad_crc}")
        if source_bad_crc is not None:
            errors.append(f"source CRC failed at {source_bad_crc}")
        if duplicates:
            errors.append("duplicate ZIP entries")
        if unsafe:
            errors.append("unsafe ZIP paths")
        if symlinks:
            errors.append("symlink ZIP entries")
        if roots != {RETURN_ROOT}:
            errors.append("return root differs")

        def read(relative: str) -> bytes:
            return archive.read(f"{RETURN_ROOT}/{relative}")

        return_manifest = object_json(read("RETURN_MANIFEST.json"))
        returned_manifest_bytes = read("evidence/PACKAGE_MANIFEST.json")
        returned_manifest = object_json(returned_manifest_bytes)
        gate = object_json(read("evidence/SERVER_RESULT_GATE.json"))
        canonical = object_json(read("evidence/canonical_decision.json"))
        canonical_self_test = object_json(
            read("evidence/canonical_decision_self_test.json")
        )
        preflight = object_json(read("evidence/installed_preflight.json"))
        observer_precompile = object_json(
            read("evidence/observer_precompile.json")
        )
        compile_log = read("logs/compile.log").decode(
            "utf-8", errors="replace"
        )
        actual_compile = read("evidence/actual_compile_argv.txt").decode(
            "utf-8", errors="replace"
        )
        binding = read("evidence/observer_binding.txt").decode(
            "utf-8", errors="replace"
        )
        signal_status = read("evidence/signal_status.txt").decode(
            "utf-8", errors="replace"
        )
        compile_status = int(
            read("evidence/compile_exit_status.txt").decode().strip()
        )
        simulation_status = int(
            read("evidence/simulation_exit_status.txt").decode().strip()
        )
        runner_status = int(
            read("evidence/runner_exit_status.txt").decode().strip()
        )
        listed = return_manifest.get("files", [])
        listed_paths = [item.get("path") for item in listed]
        expected_set = {
            f"{RETURN_ROOT}/RETURN_MANIFEST.json",
            *(
                f"{RETURN_ROOT}/{path}"
                for path in listed_paths
                if isinstance(path, str)
            ),
        }
        actual_set = set(names)
        if actual_set != expected_set:
            errors.append("RETURN_MANIFEST exact set differs")
        receipt_errors: list[str] = []
        for item in listed:
            path = item.get("path")
            if not isinstance(path, str):
                receipt_errors.append("return file path record malformed")
                continue
            data = read(path)
            if len(data) != item.get("size_bytes"):
                receipt_errors.append(f"return size receipt differs: {path}")
            if sha256_bytes(data) != item.get("sha256"):
                receipt_errors.append(f"return SHA receipt differs: {path}")
        errors.extend(receipt_errors)
        allowlist = {
            item["target_path"]: item
            for item in source_manifest["return_allowlist"]
        }
        outside_allowlist = [
            path for path in listed_paths if path not in allowlist
        ]
        if outside_allowlist:
            errors.append("returned file outside source allowlist")
        required_missing = sorted(return_manifest.get("required_missing", []))
        expected_missing = sorted(
            path for path, item in allowlist.items()
            if item["required"] and path not in listed_paths
        )
        if required_missing != expected_missing:
            errors.append("required_missing differs from source allowlist")
        if returned_manifest_bytes != source_manifest_bytes:
            errors.append("returned package manifest differs from source")
        sca_equal = read("config/sca_cfg.json") == source_sca
        sca_d_equal = read("config/sca_cfg_D.json") == source_sca_d
        if not sca_equal:
            errors.append("returned SCA differs from source")
        if not sca_d_equal:
            errors.append("returned SCA_D differs from source")

    compile_error_pattern = re.compile(
        r"Error-\[IND\] Identifier not declared.*?"
        r"native_return_observer\.svh,\s*(\d+).*?"
        r"Identifier '([^']+)' has not been declared",
        re.DOTALL,
    )
    compile_errors = compile_error_pattern.findall(compile_log)
    unique_compile_errors = sorted(set(compile_errors))
    bad_identifier_hits = source_observer.count(BAD_IDENTIFIER)
    good_identifier_hits = source_observer.count(GOOD_IDENTIFIER)
    typo_unique = (
        unique_compile_errors == [("4614", BAD_IDENTIFIER)]
        and bad_identifier_hits == 1
        and good_identifier_hits >= 4
    )
    observer_returned = (
        f"{RETURN_ROOT}/runs/return_observer.log" in set(names)
    )
    simulator_argv_returned = (
        f"{RETURN_ROOT}/evidence/actual_simulator_argv.txt" in set(names)
    )
    result_terms = gate["result_gate_conjunction"]

    return {
        "schema": "gap-node0071-v36-return-analysis-v1",
        "status": "ADJUDICATED_FRESH_PACKAGE_CORRECTION_REQUIRED",
        "analysis_owner_thread": OWNER,
        "return_target_thread": TARGET,
        "return_analysis": {
            "return_path": str(return_zip),
            "return_size_bytes": return_zip.stat().st_size,
            "return_sha256": sha256_file(return_zip),
            "adjacent_sidecar_present": False,
            "transport_policy":
                "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
            "crc_valid": bad_crc is None,
            "single_root": roots == {RETURN_ROOT},
            "path_safe": not unsafe,
            "duplicate_free": not duplicates,
            "symlink_free": not symlinks,
            "return_manifest_exact_set": actual_set == expected_set,
            "allowlist_only": not outside_allowlist,
            "required_missing_exact": required_missing == expected_missing,
            "returned_file_receipts_valid": not receipt_errors,
        },
        "source_binding": {
            "source_path": str(source_zip),
            "source_size_bytes": source_zip.stat().st_size,
            "source_sha256": sha256_file(source_zip),
            "source_crc_valid": source_bad_crc is None,
            "returned_manifest_byte_equal":
                returned_manifest_bytes == source_manifest_bytes,
            "package_identity": returned_manifest.get("package_name"),
            "install_identity": returned_manifest.get("install_name"),
            "run_identity": returned_manifest.get("run_name"),
            "return_identity": returned_manifest.get("return_name"),
            "sca_byte_equal": sca_equal,
            "sca_d_byte_equal": sca_d_equal,
        },
        "runtime_binding": {
            "installed_preflight_valid": preflight.get("valid") is True,
            "runtime_d_initially_absent": preflight.get(
                "formal_readback_targets_absent"
            ) is True,
            "observer_precompile_valid":
                observer_precompile.get("valid") is True,
            "observer_source_identity_match":
                observer_precompile.get("identity_match") is True,
            "compile_argv": actual_compile.strip(),
            "compile_macro_present":
                "+define+NATIVE_RETURN_OBSERVER_ENABLE" in actual_compile,
            "package_local_incdir_present":
                f"/{IDENTITY}/tb_probe" in actual_compile,
            "simulator_argv_returned": simulator_argv_returned,
            "observer_log_returned": observer_returned,
            "observer_binding_reports_enabled":
                "observer_enabled_and_returned=true" in binding,
            "dbclk_feature_binding_reports_enabled":
                "dbclk_rd_ready_enabled=true" in binding,
            "zero_counts_evaluable": False,
            "reason": (
                "VCS compilation failed before simulator launch; no time-0 "
                "feature marker or owner-clock qualified record exists."
            ),
        },
        "execution": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "simulation_started": False,
            "runner_exit_status": runner_status,
            "signal": (
                "NONE" if "signal=NONE" in signal_status else "UNKNOWN"
            ),
            "natural_terminal": False,
            "canonical_decision": canonical.get("decision"),
            "canonical_boundary": canonical.get("boundary"),
            "canonical_decision_accepted_as_functional_evidence": False,
            "canonical_self_test_pass":
                canonical_self_test.get("status") == "PASS",
        },
        "compile_first_failure": {
            "classification":
                "PACKAGE_LOCAL_DELIVERY_SELF_AUDIT_ESCAPE_BEFORE_SIMULATION",
            "vcs_error_code": "Error-[IND]",
            "member": OBSERVER_MEMBER,
            "line": 4614,
            "identifier": BAD_IDENTIFIER,
            "declared_identifier": GOOD_IDENTIFIER,
            "compile_log_unique_errors": [
                {"line": int(line), "identifier": identifier}
                for line, identifier in unique_compile_errors
            ],
            "bad_identifier_source_hit_count": bad_identifier_hits,
            "good_identifier_source_hit_count": good_identifier_hits,
            "unique_package_side_root": typo_unique,
            "functional_rtl_implicated": False,
            "config_implicated": False,
        },
        "qualified_path_evidence": {
            "dbclk_feature_started": False,
            "owner_clock_qualified_records": 0,
            "records_evaluable": False,
            "queue_to_wr_to_rd_factors_adjudicated": False,
            "stable_levels_count_as_progress": False,
        },
        "formal_d": {
            "expected_count": gate.get("readback_count"),
            "present_count": (
                gate.get("readback_count", 0)
                - gate.get("missing_count", 0)
            ),
            "missing_count": gate.get("missing_count"),
            "mismatch_byte_count": gate.get("mismatch_byte_count"),
            "mismatch_zero_evaluable": False,
            "exact_set_complete":
                result_terms.get("formal_readback_exact_set_complete"),
            "server_result_gate_all_terms_true":
                result_terms.get("all_terms_true"),
            "server_result_status": gate.get("status"),
        },
        "last_proven_good": (
            "The return/source/package identities, installed preflight, "
            "runtime-D-absent check and actual VCS compile invocation are "
            "proven. VCS parsed the active RTL/TB and entered the exact "
            "package-local observer before failing."
        ),
        "first_divergence": (
            "PACKAGE_LOCAL_OBSERVER_IDENTIFIER_TYPO_"
            "RETURN_OBS_RD_SPATIAL_MON_BEFORE_SIMULATION"
        ),
        "hang_root_cause": "NOT_APPLICABLE_COMPILE_FAILED_BEFORE_SIMULATION",
        "root_cause_scope": {
            "unique": typo_unique,
            "owner": "package-local observer",
            "minimal_fix": (
                f"replace the single `{BAD_IDENTIFIER}` consumer token with "
                f"the declared `{GOOD_IDENTIFIER}` token"
            ),
            "claim_boundary": (
                "This determines only the v36 compile failure. It does not "
                "adjudicate queue/WR/RD functional factors or active RTL."
            ),
        },
        "e3_e4_e5": {
            "E3": False,
            "E4": False,
            "E5": False,
            "reason": (
                "compile=2; simulation never started; natural terminal is "
                "false; formal D is 0/48 and mismatch=0 is unevaluable."
            ),
        },
        "blocker_delta": {
            "opened": "B_GAP_NODE0071_V36_PACKAGE_OBSERVER_IDENTIFIER_TYPO",
            "held": [
                "B_GAP_NODE0071_RD_DATA_READY_LOW_PENDING_PREPARED_DATA_SUPPLY_OR_OUTPUT_FULL_CLK_DB_QUALIFIED_LEAF",
                "B_GAP_NODE0071_DYNAMIC_NATURAL_TERMINAL",
                "B_GAP_NODE0071_FORMAL_D_48",
            ],
            "not_adjudicated": (
                "No functional GAP blocker may close or move because the "
                "simulator did not start."
            ),
        },
        "successor": {
            "required": True,
            "class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "change": (
                "fresh identity plus one package-local observer identifier "
                "correction; preserve the full v36 information-gain matrix"
            ),
            "config_change": False,
            "timeout_change": False,
            "backpressure_change": False,
            "functional_rtl_change": False,
        },
        "rule_confirmation": [
            "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
            "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
            "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
        ],
        "rule_delta_proposal": {
            "status": "PROPOSED",
            "suggested_id":
                "CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001",
            "evidence": (
                "The v36 final audit reported focused HDL PASS and declaration/"
                "consumer/update negatives, yet an unchanged required consumer "
                "token was undeclared in production VCS."
            ),
            "proposal": (
                "The misspelled-use negative and positive scoped closure must "
                "be seeded from each actual required consumer expression in "
                "the exact final member, not only from a declared expected "
                "identifier inventory. A consumer that resolves to no "
                "declaration must fail the positive gate."
            ),
            "claim_boundary": (
                "Package-local changed/required diagnostic identifiers only; "
                "does not require full-design local elaboration."
            ),
        },
        "numeric_sum_tail_workload_config_golden_repeated": False,
        "errors": errors,
        "valid_receipt": not errors and typo_unique,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", type=Path)
    parser.add_argument("source_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = analyze(args.return_zip.resolve(), args.source_zip.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["valid_receipt"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
