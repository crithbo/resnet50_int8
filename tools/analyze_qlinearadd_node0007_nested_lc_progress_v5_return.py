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
INSTALL_NAME = "r5_qadd_n7_nested_lc_progress_v5"
SOURCE_SHA256 = (
    "f184410ced99830d4737bea58ccd0590e87ae0525c77d95265b0ef756a184a8e"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{INSTALL_NAME}.zip"
)
SOURCE_MANIFEST = SOURCE_ZIP.with_suffix("") / "TEST_PACKAGE_MANIFEST.json"
DEFAULT_RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_qadd_n7_nested_lc_progress_v5_return.zip"
)
OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-nested-lc-progress-v5-return-analysis"
    / "report.json"
)
CURRENT_CONTROL = {
    ".agents/plan.md": ("mutable_provenance", None),
    ".agents/rules/服务器测试包生成规则.md": (
        "current_match",
        "06ec5cde2920f6aa0f11e4a2ec23d9cec2621015afe706ab8ec83e3d4603089c",
    ),
    ".agents/rules/QLinearAdd算子配置规则.md": (
        "current_match",
        "fea780962c9029e589ece90de2af8c70058aee25cffaf9822f1e16f28ff2ecba",
    ),
    ".agents/rules/NDP硬件字段语义.md": (
        "current_match",
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    ),
}
PROGRESS_TARGETS = {
    "evidence/progress_contract.json",
    "evidence/actual_simulator_argv.txt",
    "evidence/host_timing.txt",
    "evidence/signal_status.txt",
    "evidence/progress_samples.log",
    "evidence/observer_binding.txt",
    "runs/return_observer.log",
}


class AnalysisError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def json_object(payload: bytes, label: str) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise AnalysisError(f"JSON root is not an object: {label}")
    return value


def analyze(return_zip: Path) -> dict[str, Any]:
    return_zip = return_zip.resolve()
    sidecar = Path(str(return_zip) + ".sha256")
    return_sha = sha256_file(return_zip)
    sidecar_fields = (
        sidecar.read_text(encoding="ascii").split() if sidecar.is_file() else []
    )
    sidecar_matches = (
        len(sidecar_fields) == 2
        and sidecar_fields[0].lower() == return_sha
        and sidecar_fields[1] == return_zip.name
    )
    receipt_errors: list[str] = []
    if not sidecar_matches:
        receipt_errors.append("adjacent sidecar is absent or mismatched")

    source_sha = sha256_file(SOURCE_ZIP)
    if source_sha != SOURCE_SHA256:
        receipt_errors.append("frozen v5 source package SHA256 differs")

    with zipfile.ZipFile(return_zip) as archive:
        crc_failure = archive.testzip()
        infos = archive.infolist()
        names = [info.filename for info in infos]
        duplicate_count = len(names) - len(set(names))
        unsafe = [
            name
            for name in names
            if PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or "\\" in name
        ]
        symlinks = [
            info.filename
            for info in infos
            if stat.S_ISLNK(info.external_attr >> 16)
        ]
        manifest_names = [
            name for name in names if name.endswith("/RETURN_MANIFEST.json")
        ]
        if len(manifest_names) != 1:
            raise AnalysisError("return has no unique RETURN_MANIFEST")
        return_manifest_name = manifest_names[0]
        return_root = return_manifest_name.removesuffix("RETURN_MANIFEST.json")
        return_manifest = json_object(
            archive.read(return_manifest_name), "RETURN_MANIFEST"
        )
        if (
            return_manifest.get("install_name") != INSTALL_NAME
            or return_root != f"{INSTALL_NAME}_return/"
        ):
            receipt_errors.append("return root/install identity differs")

        records = return_manifest.get("files")
        if not isinstance(records, list):
            raise AnalysisError("return file records are absent")
        expected_names = {return_manifest_name}
        records_valid = True
        returned: set[str] = set()
        for record in records:
            relative = str(record["path"])
            returned.add(relative)
            name = return_root + relative
            expected_names.add(name)
            try:
                payload = archive.read(name)
                info = archive.getinfo(name)
            except KeyError:
                records_valid = False
                continue
            records_valid &= (
                info.file_size == int(record["size_bytes"])
                and sha256_bytes(payload) == record["sha256"]
            )
        zip_exact = set(names) == expected_names

        embedded_manifest_bytes = archive.read(
            return_root + "evidence/PACKAGE_MANIFEST.json"
        )
        package_manifest = json_object(
            embedded_manifest_bytes, "PACKAGE_MANIFEST"
        )
        with zipfile.ZipFile(SOURCE_ZIP) as source:
            source_crc_failure = source.testzip()
            source_manifest_bytes = source.read(
                f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json"
            )
            source_names = {
                info.filename for info in source.infolist() if not info.is_dir()
            }
        local_manifest_bytes = SOURCE_MANIFEST.read_bytes()
        manifest_three_way = (
            embedded_manifest_bytes
            == source_manifest_bytes
            == local_manifest_bytes
        )
        source_expected = {
            f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json",
            *(
                f"{INSTALL_NAME}/{relative}"
                for relative in package_manifest["files"]
            ),
        }
        source_exact = source_names == source_expected
        allowlist = {
            str(record["target_path"]): record
            for record in package_manifest["return_allowlist"]
        }
        required_missing = sorted(
            path
            for path, record in allowlist.items()
            if record.get("required") is True and path not in returned
        )
        allowlist_exact = (
            returned <= set(allowlist)
            and required_missing
            == sorted(str(value) for value in return_manifest["required_missing"])
        )

        def read_text(relative: str) -> str:
            return archive.read(return_root + relative).decode(
                "utf-8", errors="replace"
            )

        package_preflight = json.loads(
            read_text("evidence/package_preflight.json")
        )
        installed_preflight = json.loads(
            read_text("evidence/installed_preflight.json")
        )
        gate = json.loads(read_text("evidence/SERVER_RESULT_GATE.json"))
        progress_contract = json.loads(
            read_text("evidence/progress_contract.json")
        )
        compile_status = int(read_text("evidence/compile_exit_status.txt"))
        simulation_status = int(
            read_text("evidence/simulation_exit_status.txt")
        )
        host_timing = read_text("evidence/host_timing.txt")
        signal_status = read_text("evidence/signal_status.txt")
        observer_binding = read_text("evidence/observer_binding.txt").strip()
        progress_samples = read_text("evidence/progress_samples.log").splitlines()
        compile_driver = read_text("runs/compile_driver.log")
        compile_log = read_text("runs/compile.log")

    if crc_failure is not None or unsafe or duplicate_count or symlinks:
        receipt_errors.append("return ZIP CRC/path/duplicate/symlink gate failed")
    if not zip_exact or not records_valid or not allowlist_exact:
        receipt_errors.append("return exact-set/hash/allowlist gate failed")
    if source_crc_failure is not None or not source_exact or not manifest_three_way:
        receipt_errors.append("source package binding gate failed")

    timing = {
        key: int(value)
        for key, value in re.findall(r"([a-z_]+)=(\d+)", host_timing)
    }
    host_elapsed_ns = timing["final_epoch_ns"] - timing["package_start_epoch_ns"]
    missing_source = re.search(
        r'Error-\[SFCOR\].*?Source file "([^"]+)" cannot be opened.*?'
        r'"([^"]+tb_NDP_Top_new_phy\.sv)",\s*(\d+)',
        compile_log,
        flags=re.DOTALL,
    )
    compile_macro_enabled = "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_driver
    progress_returned = sorted(PROGRESS_TARGETS & returned)
    progress_missing = sorted(PROGRESS_TARGETS - returned)
    conjunction = gate["result_gate_conjunction"]

    preflight_valid = (
        package_preflight.get("valid") is True
        and installed_preflight.get("valid") is True
        and package_preflight.get("formal_readback_targets_absent") is True
        and installed_preflight.get("formal_readback_targets_absent") is True
    )
    exact_missing_source = (
        missing_source is not None
        and missing_source.group(1) == "native_return_observer.svh"
        and compile_macro_enabled
    )
    return {
        "schema": "qlinearadd-node0007-progress-v5-return-analysis-v1",
        "status": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
        "valid_return_receipt": not receipt_errors,
        "receipt_errors": receipt_errors,
        "control_receipts": {
            relative: {
                "policy": policy,
                "expected_sha256": expected,
                "observed_sha256": sha256_file(ROOT / relative),
                "matches": expected is None
                or sha256_file(ROOT / relative) == expected,
            }
            for relative, (policy, expected) in CURRENT_CONTROL.items()
        },
        "return_input": {
            "path": str(return_zip),
            "size_bytes": return_zip.stat().st_size,
            "sha256": return_sha,
            "sidecar": str(sidecar),
            "sidecar_present": sidecar.is_file(),
            "sidecar_matches": sidecar_matches,
        },
        "source_package_binding": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "expected_sha256": SOURCE_SHA256,
            "observed_sha256": source_sha,
            "matches": source_sha == SOURCE_SHA256,
            "source_crc_clean": source_crc_failure is None,
            "source_exact_set": source_exact,
            "manifest_three_way_equal": manifest_three_way,
        },
        "return_integrity": {
            "crc_clean": crc_failure is None,
            "zip_exact_set": zip_exact,
            "record_hash_size_valid": records_valid,
            "allowlist_exact": allowlist_exact,
            "returned_file_count": len(records),
            "required_missing_count": len(required_missing),
            "required_missing": required_missing,
            "unsafe_member_count": len(unsafe),
            "duplicate_member_count": duplicate_count,
            "symlink_member_count": len(symlinks),
        },
        "preflight": {
            "valid": preflight_valid,
            "package": package_preflight,
            "installed": installed_preflight,
            "runtime_d_absent_before_run": preflight_valid,
        },
        "dynamic_result": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "signal_status": signal_status.strip().splitlines(),
            "simulation_started": False,
            "natural_terminal": False,
            "expected_readback_count": gate["expected_readback_count"],
            "observed_readback_count": gate["observed_readback_count"],
            "missing_count": gate["missing_count"],
            "mismatch_byte_count": gate["mismatch_byte_count"],
            "mismatch_is_evaluable": False,
            "all_terms_true": conjunction["all_terms_true"],
            "dynamic_attempt_counted": False,
        },
        "progress_evidence": {
            "declared_stall_window_cycles": progress_contract[
                "stall_window_cycles"
            ],
            "declared_heartbeat_cycles": progress_contract["heartbeat_cycles"],
            "host_elapsed_ns": host_elapsed_ns,
            "host_elapsed_seconds": host_elapsed_ns / 1_000_000_000,
            "simulation_time": None,
            "stage_or_start_comp": None,
            "qualified_window_count": 0,
            "qualified_accepted_deltas": [],
            "qualified_completion_deltas": [],
            "last_boundary": "compile/include resolution",
            "terminal_boundary": None,
            "observer_binding": observer_binding,
            "progress_samples": progress_samples,
            "progress_targets_returned": progress_returned,
            "progress_targets_missing": progress_missing,
        },
        "progress_adjudication": {
            "status": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
            "still_progressing_proven": False,
            "stalled_beyond_window_proven": False,
            "reason": (
                "The observer-enabled compile failed before simulation because "
                "the selected optional TB include could not resolve "
                "native_return_observer.svh. No qualified progress window exists."
            ),
        },
        "hang_root_cause": {
            "node_execution_status": "UNRESOLVED_NO_NEW_DYNAMIC_EVIDENCE",
            "diagnostic_infrastructure_root_cause": (
                "PACKAGE_OBSERVER_INCLUDE_SOURCE_NOT_BOUND"
            ),
            "functional_qlinearadd_root_cause_proven": False,
        },
        "first_divergence": {
            "code": "OBSERVER_INCLUDE_SOURCE_NOT_FOUND_AT_COMPILE",
            "last_proven_boundary": (
                "package/install preflight and guarded observer macro selection"
            ),
            "first_failed_boundary": (
                "VCS include resolution for native_return_observer.svh"
            ),
            "compile_macro_enabled": compile_macro_enabled,
            "missing_source": missing_source.group(1) if missing_source else None,
            "server_log_path": missing_source.group(2) if missing_source else None,
            "server_log_line": int(missing_source.group(3))
            if missing_source
            else None,
            "exact_package_side_legal_fix": exact_missing_source,
        },
        "evidence_adjudication": {
            "E3": {
                "pass": False,
                "reason": "compile failed; simulation did not start",
            },
            "E4": {
                "pass": False,
                "reason": "28/28 formal D readbacks are missing",
            },
            "E5": {
                "pass": False,
                "reason": "E4 is absent",
            },
        },
        "numeric_analysis": {
            "repeated": False,
            "consumed_reuse_assets": True,
            "dynamic_readback_comparison_performed": False,
        },
        "package_release": {
            "status": (
                "FRESH_DIAGNOSTIC_BINDING_FIX_ALLOWED"
                if exact_missing_source
                else "NONE"
            ),
            "functional_fix": False,
            "allowed_claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "required_change": (
                "carry a read-only observer in a package-local include directory, "
                "bind that directory and the enable macro in the actual compile "
                "command, and preserve the frozen v5 workload and timeout"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, default=DEFAULT_RETURN)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    report = analyze(args.return_zip)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["valid_return_receipt"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
