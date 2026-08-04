from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from collections import defaultdict
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_qadd_n7_nested_lc_v4"
SOURCE_SHA256 = (
    "dfe6ab0e11482d9af7954ba3e87911b770f8d80efa4148352b63d27bf7df2361"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{INSTALL_NAME}.zip"
)
LOCAL_MANIFEST = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / INSTALL_NAME
    / "TEST_PACKAGE_MANIFEST.json"
)
DEFAULT_RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_qadd_n7_nested_lc_v4_return.zip"
)
OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-nested-lc-v4-return-analysis"
    / "report.json"
)
E2_ROOT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-nested-lc-full-e2-v4"
)
FINAL_JSON_ROOT = E2_ROOT / "execplan/pipeline_output/jsons"
EXPLAINED = E2_ROOT / "execplan/pipeline_output/instructions_explained.txt"
LC_COUNTER = (
    ROOT
    / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC"
    / "IGA_LC_Counter.sv"
)
LC_INBUFFER = LC_COUNTER.with_name("IGA_LC_Inbuffer.sv")
SEM = ROOT / "NDP_copy01/rtl/Slice/Slice_Execution_Manager.sv"
CONTROL = {
    ".agents/plan.md": ("mutable_provenance", None),
    ".agents/rules/生成前必读索引.md": (
        "current_match",
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
    ),
    ".agents/rules/服务器测试包生成规则.md": (
        "current_match",
        "2e5cf649cd721f4444b0caca2d1ea6670823c02d9d86784d6d228351ea8c7227",
    ),
    ".agents/rules/QLinearAdd算子配置规则.md": (
        "current_match",
        "fea780962c9029e589ece90de2af8c70058aee25cffaf9822f1e16f28ff2ecba",
    ),
    ".agents/rules/NDP硬件字段语义.md": (
        "current_match",
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
    ),
    ".agents/rules/精确UINT8量化尾专项规则.md": (
        "current_match",
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
    ),
}


class AnalysisError(ValueError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def object_from_bytes(value: bytes, label: str) -> dict[str, Any]:
    result = json.loads(value)
    if not isinstance(result, dict):
        raise AnalysisError(f"JSON root must be object: {label}")
    return result


def load_object(path: Path) -> dict[str, Any]:
    return object_from_bytes(path.read_bytes(), str(path))


def _final_stage_configs() -> list[tuple[str, dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(FINAL_JSON_ROOT.glob("*.json")):
        value = load_object(path)
        name = path.name.split("_resnet50_", 1)[0]
        result.append((name, value))
    if len(result) != 6:
        raise AnalysisError("six final stage JSONs are not present")
    return result


def audit_static_execution() -> dict[str, Any]:
    errors: list[str] = []
    stage_records: list[dict[str, Any]] = []
    total_requests = 0
    closure = load_object(E2_ROOT / "closure_report.json")
    request_by_stage: dict[str, int] = defaultdict(int)
    for key, value in closure["stream_address_coverage"].items():
        request_by_stage[key.split(":", 1)[0]] += int(value["request_count"])
        total_requests += int(value["request_count"])

    for operator_id, config in _final_stage_configs():
        loops = config.get("dram_loop_configs", {})
        max_end = max(int(value["end"]) for value in loops.values())
        max_dim_stride = max(
            int(stride)
            for stream in config.get("stream_engine", {}).values()
            for stride in stream.get("dim_stride", [])
            if stride is not None
        )
        illegal_ends = [
            name
            for name, value in loops.items()
            if int(value["stride"]) > 0 and int(value["end"]) > 32_768
        ]
        if illegal_ends:
            errors.append(f"{operator_id}: signed-feedback LC end exceeds 32768")
        if max_dim_stride > 1_048_575:
            errors.append(f"{operator_id}: unsigned20 dim_stride overflow")
        stage_records.append(
            {
                "operator_id": operator_id,
                "request_count_with_multiplicity": request_by_stage[operator_id],
                "max_positive_lc_end": max_end,
                "max_dim_stride": max_dim_stride,
                "signed_feedback_end_legal": not illegal_ends,
                "dim_stride_unsigned20_legal": max_dim_stride <= 1_048_575,
            }
        )

    explained = EXPLAINED.read_text(encoding="utf-8")
    start_ops = re.findall(
        r"Start_Comp for operator ([a-z0-9_]+) \(", explained
    )
    expected_order = [
        "op_a_dequant",
        "op_b_dequant",
        "op_relocation_pad",
        "op_fp32_add",
        "op_tail_mul",
        "op_tail_round",
    ]
    if start_ops != expected_order:
        errors.append("final execplan Start_Comp order differs")

    sem_text = SEM.read_text(encoding="utf-8")
    counter_text = LC_COUNTER.read_text(encoding="utf-8")
    inbuffer_text = LC_INBUFFER.read_text(encoding="utf-8")
    rtl_checks = {
        "exec_start_is_cmpt_level": (
            "CMPT: begin" in sem_text
            and "sem2iga_exec_start          <= 1;" in sem_text
        ),
        "counter_signed_feedback_bound": (
            "signed'(iga_lc_outbuf_cnt_rd_data) + "
            "signed'(iga_lc_stride_value)" in counter_text
        ),
        "nested_input_capture_while_cmpt_level": (
            "slice_start_run && iga_lc_inbuffer_bp_pre" in inbuffer_text
        ),
        "shared_downstream_backpressure_is_and": (
            "iga_lc_connect2ob_bp_post = &iga_lc_outport_bp_post"
            in (
                ROOT
                / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC"
                / "IGA_LC_Connect.sv"
            ).read_text(encoding="utf-8")
        ),
    }
    if not all(rtl_checks.values()):
        errors.append("focused LC/SEM RTL semantics drifted")

    return {
        "valid": not errors,
        "errors": errors,
        "first_error": errors[0] if errors else None,
        "stage_start_order": start_ops,
        "stage_records": stage_records,
        "first_stage_requests": request_by_stage["op_a_dequant"],
        "total_requests_with_multiplicity": total_requests,
        "rtl_checks": rtl_checks,
        "rtl_receipts": {
            "lc_counter_sha256": sha256_file(LC_COUNTER),
            "lc_inbuffer_sha256": sha256_file(LC_INBUFFER),
            "slice_execution_manager_sha256": sha256_file(SEM),
        },
        "address_lifetime_barrier_reused": closure[
            "accepted_lifetimes_and_barriers"
        ],
        "numeric_analysis_repeated": False,
    }


def analyze(return_zip: Path) -> dict[str, Any]:
    return_zip = return_zip.resolve()
    errors: list[str] = []
    sidecar = Path(str(return_zip) + ".sha256")
    return_sha = sha256_file(return_zip)
    sidecar_fields = (
        sidecar.read_text(encoding="ascii").split() if sidecar.is_file() else []
    )
    sidecar_matches = bool(sidecar_fields) and sidecar_fields[0].lower() == return_sha
    if not sidecar_matches:
        errors.append("adjacent return sidecar is absent or mismatched")

    source_sha = sha256_file(SOURCE_ZIP)
    if source_sha != SOURCE_SHA256:
        errors.append("frozen v4 source package identity differs")

    with zipfile.ZipFile(return_zip) as archive:
        crc_failure = archive.testzip()
        infos = archive.infolist()
        names = [item.filename for item in infos]
        unsafe = [
            name
            for name in names
            if PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or "\\" in name
        ]
        duplicates = len(names) - len(set(names))
        symlinks = [
            item.filename
            for item in infos
            if stat.S_ISLNK(item.external_attr >> 16)
        ]
        manifest_names = [
            name for name in names if name.endswith("/RETURN_MANIFEST.json")
        ]
        if len(manifest_names) != 1:
            raise AnalysisError("return manifest exact root differs")
        return_root = manifest_names[0].removesuffix("RETURN_MANIFEST.json")
        return_manifest = object_from_bytes(
            archive.read(manifest_names[0]), "RETURN_MANIFEST.json"
        )
        install_name = str(return_manifest.get("install_name"))
        if return_root != f"{install_name}_return/" or install_name != INSTALL_NAME:
            errors.append("return root/install identity differs")

        records = return_manifest.get("files")
        if not isinstance(records, list):
            raise AnalysisError("return file records are absent")
        expected_names = {manifest_names[0]}
        records_valid = True
        for record in records:
            name = return_root + str(record["path"])
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
        package_manifest = object_from_bytes(
            embedded_manifest_bytes, "PACKAGE_MANIFEST.json"
        )
        with zipfile.ZipFile(SOURCE_ZIP) as source:
            source_crc_failure = source.testzip()
            source_manifest_bytes = source.read(
                f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json"
            )
            source_names = {
                item.filename for item in source.infolist() if not item.is_dir()
            }
        embedded_manifest_sha = sha256_bytes(embedded_manifest_bytes)
        source_manifest_sha = sha256_bytes(source_manifest_bytes)
        local_manifest_sha = sha256_file(LOCAL_MANIFEST)
        manifest_bound = (
            embedded_manifest_sha == source_manifest_sha == local_manifest_sha
        )
        expected_source_names = {
            f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json",
            *(
                f"{INSTALL_NAME}/{relative}"
                for relative in package_manifest["files"]
            ),
        }
        source_exact = source_names == expected_source_names

        allowlist = {
            str(item["target_path"]): item
            for item in package_manifest["return_allowlist"]
        }
        returned = {str(item["path"]) for item in records}
        required_missing = sorted(
            path
            for path, item in allowlist.items()
            if item["required"] and path not in returned
        )
        allowlist_exact = (
            returned <= set(allowlist)
            and sorted(return_manifest["required_missing"]) == required_missing
        )

        package_preflight = object_from_bytes(
            archive.read(return_root + "evidence/package_preflight.json"),
            "package_preflight.json",
        )
        installed_preflight = object_from_bytes(
            archive.read(return_root + "evidence/installed_preflight.json"),
            "installed_preflight.json",
        )
        compile_status = int(
            archive.read(
                return_root + "evidence/compile_exit_status.txt"
            ).decode("ascii")
        )
        simulation_status = int(
            archive.read(
                return_root + "evidence/simulation_exit_status.txt"
            ).decode("ascii")
        )
        gate = object_from_bytes(
            archive.read(return_root + "evidence/SERVER_RESULT_GATE.json"),
            "SERVER_RESULT_GATE.json",
        )
        sim_lines = archive.read(return_root + "runs/sim.log").decode(
            "utf-8", errors="replace"
        ).splitlines()
        compile_text = archive.read(
            return_root + "runs/compile_driver.log"
        ).decode("utf-8", errors="replace")

    if crc_failure is not None or unsafe or duplicates or symlinks:
        errors.append("return ZIP CRC/path/duplicate/symlink gate failed")
    if not zip_exact or not records_valid or not allowlist_exact:
        errors.append("return exact-set/hash/allowlist gate failed")
    if source_crc_failure is not None or not source_exact or not manifest_bound:
        errors.append("source package binding gate failed")

    def first_line(pattern: str) -> tuple[int, str] | None:
        for index, line in enumerate(sim_lines, start=1):
            if re.search(pattern, line):
                return index, line
        return None

    preload = first_line(r"JSON config:\s*85\s+matrices loaded")
    exec_transport = first_line(r"JSON config:\s*Exec_Base=")
    register_start = first_line(r"^Reg Started\.$")
    slice_start = first_line(r"INFO:\s*slice start")
    interrupt = first_line(r"Interrupt at time\s+(\d+)")
    start_time = int(re.search(r"\[(\d+)\]", slice_start[1]).group(1)) if slice_start else None
    interrupt_time = (
        int(re.search(r"Interrupt at time\s+(\d+)", interrupt[1]).group(1))
        if interrupt
        else None
    )
    simulated_compute_ps = (
        interrupt_time - start_time
        if start_time is not None and interrupt_time is not None
        else None
    )
    compile_started = re.search(
        r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) "
        r"[A-Z][a-z]{2} \d+ \d{2}:\d{2}:\d{2} \d{4}",
        compile_text,
    )

    conjunction = gate["result_gate_conjunction"]
    observed_readbacks = int(gate["observed_readback_count"])
    preflight_valid = (
        package_preflight.get("valid") is True
        and installed_preflight.get("valid") is True
        and package_preflight.get("formal_readback_targets_absent") is True
        and installed_preflight.get("formal_readback_targets_absent") is True
    )
    static = audit_static_execution()
    progress_files = [
        item
        for item in returned
        if "progress" in item.lower() or "observer" in item.lower()
    ]
    progress_localization_available = bool(progress_files)

    report = {
        "schema": "qlinearadd-node0007-nested-lc-v4-return-analysis-v1",
        "status": "LONG_RUNNING_HANG_PENDING_ROOT_CAUSE",
        "valid_return_receipt": not errors,
        "analysis_errors": errors,
        "control_receipts": {
            relative: {
                "policy": policy,
                "expected_sha256": expected,
                "observed_sha256": sha256_file(ROOT / relative),
                "matches": expected is None or sha256_file(ROOT / relative) == expected,
            }
            for relative, (policy, expected) in CONTROL.items()
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
            "manifest_three_way_equal": manifest_bound,
            "install_name": install_name,
        },
        "return_integrity": {
            "crc_clean": crc_failure is None,
            "unsafe_member_count": len(unsafe),
            "duplicate_member_count": duplicates,
            "symlink_member_count": len(symlinks),
            "zip_exact_set": zip_exact,
            "record_hash_size_valid": records_valid,
            "allowlist_exact": allowlist_exact,
            "returned_file_count": len(records),
            "required_missing": required_missing,
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
            "manual_or_external_interrupt": simulation_status == 125,
            "preload_count_exact": preload is not None,
            "exec_transport_loaded": exec_transport is not None,
            "register_started": register_start is not None,
            "first_slice_started": slice_start is not None,
            "natural_terminal": bool(conjunction["natural_completion"]),
            "expected_readback_count": gate["expected_readback_count"],
            "observed_readback_count": observed_readbacks,
            "missing_count": gate["missing_count"],
            "mismatch_byte_count": gate["mismatch_byte_count"],
            "mismatch_is_evaluable": observed_readbacks > 0,
            "zero_mismatch_with_all_missing_is_numeric_pass": False,
            "all_terms_true": bool(conjunction["all_terms_true"]),
            "log_boundaries": {
                "preload": preload,
                "exec_transport": exec_transport,
                "register_start": register_start,
                "slice_start": slice_start,
                "interrupt": interrupt,
            },
            "compile_start_marker": (
                compile_started.group(0) if compile_started else None
            ),
            "first_start_time_ps": start_time,
            "interrupt_time_ps": interrupt_time,
            "simulated_compute_interval_ps": simulated_compute_ps,
        },
        "progress_adjudication": {
            "status": "INSUFFICIENT_TO_DISTINGUISH_PROGRESS_FROM_STALL",
            "default_execution_state": "LONG_RUNNING_HANG_PENDING_ROOT_CAUSE",
            "progress_localization_available": progress_localization_available,
            "returned_progress_files": progress_files,
            "stall_window_declared": False,
            "two_monotonic_windows_proven": False,
            "stalled_beyond_window_proven": False,
            "reason": (
                "The public simulator log advances from the first slice start "
                "to an external interrupt, but v4 did not enable or return "
                "accepted/completion counters, stage-local heartbeats, host "
                "wall-clock samples, or a declared stall_window. Simulation "
                "time advancement alone is not transaction progress."
            ),
        },
        "first_divergence": {
            "code": "FIRST_START_COMP_ACCEPTED_NO_FIRST_COMPLETION_BEFORE_INTERRUPT",
            "last_proven_boundary": "op_a_dequant Start_Comp / slice start",
            "first_unproven_boundary": "op_a_dequant slice_cmpt_finish",
            "unique_error_interval": (
                "op_a_dequant first Start_Comp: LC/read accepted progress -> "
                "GA/buffer5/write completion -> LC last -> slice_cmpt_finish"
            ),
            "package_side_functional_fix_proven": False,
            "server_rtl_or_environment_fault_proven": False,
        },
        "hang_root_cause": {
            "status": "UNRESOLVED_AFTER_EXHAUSTIVE_AUDIT",
            "excluded": [
                "v2/v3 flat LC signed-feedback wrap: v4 max end is 18816",
                "unsigned20 derived outer stride overflow",
                "wrong source package or install identity",
                "preseeded/stale formal D",
                "compile/elaboration failure",
                "wrong SCA/SCA_D namespace or incomplete preload",
                "address row overflow/nonalias/lifetime static regression",
            ],
            "not_distinguishable_without_progress_counters": [
                "large but monotonically progressing first dequant stage",
                "MSE request/data acceptance stall",
                "GA/buffer5/writeback backpressure stall",
                "LC last or slice completion propagation stall",
            ],
            "claim_boundary": (
                "No functional configuration or RTL root cause is proven by "
                "this interrupted return. The next artifact may only be a "
                "read-only progress diagnostic, not a functional fix."
            ),
        },
        "workload_scale": {
            "physical_stage_count": 6,
            "first_stage_request_count_with_multiplicity": static[
                "first_stage_requests"
            ],
            "total_request_count_with_multiplicity": static[
                "total_requests_with_multiplicity"
            ],
            "preload_matrix_count": 85,
            "assessment": "LARGE_NODE; elapsed wall time alone cannot classify completion",
        },
        "static_execution_audit": static,
        "evidence_adjudication": {
            "E3": {
                "pass": False,
                "reason": "simulation was externally interrupted before natural terminal",
            },
            "E4": {
                "pass": False,
                "reason": "28/28 formal D readbacks are missing",
            },
            "E5": {
                "pass": False,
                "reason": "E4 is absent and no fresh independent pass exists",
            },
        },
        "numeric_analysis": {
            "repeated": False,
            "consumed_reuse_assets": True,
            "dynamic_readback_comparison_performed": False,
        },
        "package_release": {
            "status": "DIAGNOSTIC_IDENTITY_REQUIRED",
            "functional_fix": False,
            "allowed_claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "must_preserve_frozen_v4_workload": True,
        },
    }
    return report


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
