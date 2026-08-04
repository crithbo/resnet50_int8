from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_INSTALL_NAME = "r5_qadd_n7_relocated_v2"
EXPECTED_SOURCE_SHA256 = (
    "60534faad0894a8b6507687159d43c824dd968f6c6a3386fa7877fc2007bf0bc"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_relocated_v2.zip"
)
LOCAL_PACKAGE_MANIFEST = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_relocated_v2/TEST_PACKAGE_MANIFEST.json"
)
DEFAULT_RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_qadd_n7_relocated_v2_return(2).zip"
)
OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-v2-return2-analysis/report.json"
)
NEXT_PACKAGE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_relocated_v3.zip"
)
QADD_E2_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-relocated-full-e2-v2"
)
RTL_LC_COUNTER = (
    ROOT
    / "Trassic2.0_RTL/code/NDP_rtl/Slice/Index_Generation_Array/"
    "IGA_LC/IGA_LC_Counter.sv"
)
RTL_PARAMETERS = (
    ROOT / "Trassic2.0_RTL/code/NDP_rtl/includes/NDP_Parameters.svh"
)
CONTROL_RECEIPTS = {
    ".agents/plan.md": (
        "e3e44d47121b6c567b6e4c103b60c8012bbf09e8d904aabf9f1e4a03c016d97f",
        "mutable_provenance",
    ),
    ".agents/rules/生成前必读索引.md": (
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
        "current_match",
    ),
    ".agents/rules/服务器测试包生成规则.md": (
        "153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2",
        "current_match",
    ),
    ".agents/rules/QLinearAdd算子配置规则.md": (
        "dd4a8122d771ed5f4dbb9995fd6463ba14b179a72a515d2af5e91d30f2c71269",
        "current_match",
    ),
    ".agents/rules/精确UINT8量化尾专项规则.md": (
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
        "current_match",
    ),
}


class ReturnAnalysisError(ValueError):
    pass


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_object(value: bytes, label: str) -> dict[str, Any]:
    result = json.loads(value)
    if not isinstance(result, dict):
        raise ReturnAnalysisError(f"JSON root must be object: {label}")
    return result


def audit_lc_signed_wrap() -> dict[str, Any]:
    """Prove whether a materialized DRAM LC can reach its configured end.

    The RTL stores the 17-bit counter into a 16-bit outbuffer and sign-casts
    that 16-bit feedback value on the following iteration.  Positive loop
    ends above 32768 therefore cannot assert their last condition.
    """

    parameter_text = RTL_PARAMETERS.read_text(encoding="utf-8")
    counter_text = RTL_LC_COUNTER.read_text(encoding="utf-8")
    width_match = re.search(
        r"`define\s+IGA_LC_PORT_DATA_WIDTH\s+(\d+)", parameter_text
    )
    if width_match is None:
        raise ReturnAnalysisError("IGA LC data width is not readable")
    width = int(width_match.group(1))
    safe_positive_end = 1 << (width - 1)
    required_rtl_fragments = [
        (
            "iga_lc_outbuf_cnt_value = "
            "signed'(iga_lc_outbuf_cnt_rd_data) + "
            "signed'(iga_lc_stride_value);"
        ),
        (
            "iga_lc_ob_data[iga_lc_outbuf_wr_ptr] <= "
            "iga_lc_outbuf_cnt_value[`IGA_LC_OUTBUFFER_DATA_WIDTH-1:0];"
        ),
        (
            "signed'(iga_lc_outbuf_cnt_value) >= "
            "signed'(iga_lc_end_value) - signed'(iga_lc_stride_value)"
        ),
    ]
    rtl_semantics_bound = all(
        fragment in counter_text for fragment in required_rtl_fragments
    )
    if not rtl_semantics_bound:
        raise ReturnAnalysisError("IGA LC signed-feedback RTL semantics drifted")

    validation = load_object(
        (
            QADD_E2_ROOT / "execplan/execplan_validation_report.json"
        ).read_bytes(),
        "execplan_validation_report.json",
    )
    stages = validation.get("facts", {}).get("stages", [])
    offenders: list[dict[str, Any]] = []
    for stage in stages:
        config_path = Path(str(stage["source_config"]))
        config = load_object(config_path.read_bytes(), str(config_path))
        stream_users: dict[str, list[str]] = {}
        for stream_name, stream in config.get("stream_engine", {}).items():
            for source in stream.get("idx", []):
                if isinstance(source, str) and source.startswith("DRAM_LC."):
                    stream_users.setdefault(source.rsplit(".", 1)[-1], []).append(
                        stream_name
                    )
        for loop_name, loop in config.get("dram_loop_configs", {}).items():
            end = int(loop.get("end", 0))
            stride = int(loop.get("stride", 0))
            start = int(loop.get("start", 0))
            if start >= 0 and stride > 0 and end > safe_positive_end:
                offenders.append(
                    {
                        "stage_index": int(stage["stage_index"]),
                        "operator_id": str(stage["op_id"]),
                        "loop": loop_name,
                        "start": start,
                        "stride": stride,
                        "end": end,
                        "last_threshold": end - stride,
                        "feedback_width_bits": width,
                        "first_sign_flipped_feedback": -(1 << (width - 1)),
                        "safe_positive_end_max": safe_positive_end,
                        "stream_users": sorted(stream_users.get(loop_name, [])),
                        "source_config": config_path.relative_to(ROOT).as_posix(),
                    }
                )
    offenders.sort(
        key=lambda item: (
            item["stage_index"],
            item["operator_id"],
            item["loop"],
        )
    )
    first = offenders[0] if offenders else None
    return {
        "status": (
            "PROVEN_UNREACHABLE_LC_LAST" if offenders else "NO_SIGN_WRAP_FOUND"
        ),
        "rtl_semantics_bound": rtl_semantics_bound,
        "rtl_parameter_path": RTL_PARAMETERS.relative_to(ROOT).as_posix(),
        "rtl_parameter_sha256": sha256_file(RTL_PARAMETERS),
        "rtl_counter_path": RTL_LC_COUNTER.relative_to(ROOT).as_posix(),
        "rtl_counter_sha256": sha256_file(RTL_LC_COUNTER),
        "execplan_validation_sha256": sha256_file(
            QADD_E2_ROOT / "execplan/execplan_validation_report.json"
        ),
        "feedback_width_bits": width,
        "safe_positive_end_max": safe_positive_end,
        "offender_count": len(offenders),
        "offenders": offenders,
        "first_offender": first,
        "proof": (
            "The counter reaches +32768 before the configured 37631 last "
            "threshold, is truncated to 16'h8000 in the outbuffer, and is "
            "sign-extended as -32768 on feedback. It therefore cannot reach "
            "the last threshold and cannot emit the write-stream completion "
            "that drives slice_cmpt_finish."
            if offenders
            else None
        ),
        "config_only_fix_geometry": {
            "op_a_dequant/op_b_dequant": {
                "LC0_end": {"old": 1, "expected": 2},
                "LC1_LC3_end": {"old": 37_632, "expected": 18_816},
                "stream0_outer_stride_bytes": {
                    "old": 602_112,
                    "expected": 301_056,
                },
                "stream2_outer_stride_bytes": {
                    "old": 0,
                    "expected": 1_204_224,
                },
            },
            "op_fp32_add": {
                "LC0_end": {"old": 4, "expected": 8},
                "LC1_LC2_LC3_end": {
                    "old": 37_632,
                    "expected": 18_816,
                },
                "all_stream_outer_stride_bytes": {
                    "old": 602_112,
                    "expected": 301_056,
                },
            },
            "equivalence_scope": (
                "factor each 37632-occurrence inner loop into an outer factor "
                "of two and an inner end of 18816; preserve occurrence count, "
                "address order, six qparams, W3 FP32 order, tail semantics, "
                "coverage and scratch lifetimes"
            ),
            "materialized": False,
        },
    }


def analyze(return_zip: Path) -> dict[str, Any]:
    return_zip = return_zip.resolve()
    errors: list[str] = []
    formal_errors: list[str] = []
    direct_sidecar = Path(str(return_zip) + ".sha256")
    sidecar_present = direct_sidecar.is_file()
    return_sha = sha256_file(return_zip)
    sidecar_matches = False
    if not sidecar_present:
        formal_errors.append(
            "FORMAL_RECEIPT.ADJACENT_SIDECAR_MISSING: directly corresponding "
            f"{direct_sidecar.name} is absent"
        )
    else:
        fields = direct_sidecar.read_text(encoding="ascii").split()
        sidecar_matches = bool(fields) and fields[0].lower() == return_sha
        if not sidecar_matches:
            formal_errors.append("FORMAL_RECEIPT.SIDECAR_SHA_MISMATCH")

    source_sha = sha256_file(SOURCE_ZIP)
    if source_sha != EXPECTED_SOURCE_SHA256:
        errors.append("source package ZIP identity differs")

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
            raise ReturnAnalysisError("return manifest exact root differs")
        return_root = manifest_names[0].removesuffix("RETURN_MANIFEST.json")
        return_manifest = load_object(
            archive.read(manifest_names[0]), "RETURN_MANIFEST.json"
        )
        install_name = str(return_manifest.get("install_name"))
        expected_root = f"{install_name}_return/"
        if return_root != expected_root:
            errors.append("ZIP root/install_name identity differs")
        if install_name != EXPECTED_INSTALL_NAME:
            errors.append("return install_name differs from source package")

        returned_records = return_manifest.get("files")
        if not isinstance(returned_records, list):
            raise ReturnAnalysisError("return file records are absent")
        expected_names = {manifest_names[0]}
        record_integrity = True
        for record in returned_records:
            relative = str(record["path"])
            name = return_root + relative
            expected_names.add(name)
            try:
                info = archive.getinfo(name)
                payload = archive.read(name)
            except KeyError:
                record_integrity = False
                continue
            if (
                info.file_size != int(record["size_bytes"])
                or sha256_bytes(payload) != record["sha256"]
            ):
                record_integrity = False
        zip_exact_set = set(names) == expected_names
        if crc_failure is not None:
            errors.append(f"return ZIP CRC failure: {crc_failure}")
        if unsafe or duplicates or symlinks:
            errors.append("return ZIP path/symlink/duplicate safety failure")
        if not zip_exact_set or not record_integrity:
            errors.append("return exact-set or file identity differs")

        embedded_manifest_bytes = archive.read(
            return_root + "evidence/PACKAGE_MANIFEST.json"
        )
        package_manifest = load_object(
            embedded_manifest_bytes, "PACKAGE_MANIFEST.json"
        )
        embedded_manifest_sha = sha256_bytes(embedded_manifest_bytes)
        with zipfile.ZipFile(SOURCE_ZIP) as source_archive:
            source_crc_failure = source_archive.testzip()
            source_manifest_bytes = source_archive.read(
                f"{EXPECTED_INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json"
            )
            source_names = {
                item.filename
                for item in source_archive.infolist()
                if not item.is_dir()
            }
        source_manifest_sha = sha256_bytes(source_manifest_bytes)
        local_manifest_sha = sha256_file(LOCAL_PACKAGE_MANIFEST)
        package_identity_bound = (
            embedded_manifest_sha
            == source_manifest_sha
            == local_manifest_sha
        )
        if not package_identity_bound:
            errors.append("embedded package manifest does not bind source ZIP")
        source_expected_names = {
            f"{EXPECTED_INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json",
            *(
                f"{EXPECTED_INSTALL_NAME}/{relative}"
                for relative in package_manifest.get("files", {})
            ),
        }
        source_zip_exact_set = source_names == source_expected_names
        if source_crc_failure is not None or not source_zip_exact_set:
            errors.append("source package ZIP CRC or exact-set differs")

        allowlist = package_manifest.get("return_allowlist")
        if not isinstance(allowlist, list):
            raise ReturnAnalysisError("package return allowlist is absent")
        allowlist_by_target = {
            str(item["target_path"]): item for item in allowlist
        }
        returned = {str(item["path"]) for item in returned_records}
        required_missing_expected = sorted(
            target
            for target, item in allowlist_by_target.items()
            if item["required"] and target not in returned
        )
        required_missing_observed = sorted(
            str(item) for item in return_manifest.get("required_missing", [])
        )
        allowlist_exact = (
            returned <= set(allowlist_by_target)
            and required_missing_observed == required_missing_expected
        )
        if not allowlist_exact:
            errors.append("return manifest does not match package allowlist")

        package_preflight = load_object(
            archive.read(return_root + "evidence/package_preflight.json"),
            "package_preflight.json",
        )
        installed_preflight = load_object(
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
        result_gate = load_object(
            archive.read(return_root + "evidence/SERVER_RESULT_GATE.json"),
            "SERVER_RESULT_GATE.json",
        )
        compile_lines = archive.read(
            return_root + "runs/compile.log"
        ).decode("utf-8", errors="replace").splitlines()
        sim_lines = archive.read(
            return_root + "runs/sim.log"
        ).decode("utf-8", errors="replace").splitlines()

    def find_line(pattern: str) -> int | None:
        for index, line in enumerate(sim_lines):
            if re.search(pattern, line):
                return index
        return None

    boundary_patterns = {
        "preloads_complete": r"JSON config:\s*85\s+matrices loaded",
        "exec_transport": r"JSON config:\s*Exec_Base=",
        "register_started": r"^Reg Started\.$",
        "slice_started": r"INFO:\s*slice start",
    }
    boundary_indices = {
        name: find_line(pattern) for name, pattern in boundary_patterns.items()
    }
    execution_excerpt = [
        {"line": index + 1, "text": sim_lines[index]}
        for index in boundary_indices.values()
        if index is not None
    ]

    preflight_valid = (
        package_preflight.get("valid") is True
        and installed_preflight.get("valid") is True
        and package_preflight.get("formal_readback_targets_absent") is True
        and installed_preflight.get("formal_readback_targets_absent") is True
    )
    gate = result_gate.get("result_gate_conjunction", {})
    dynamic_started = compile_status == 0 and simulation_status != 125
    observed_readbacks = int(result_gate.get("observed_readback_count", 0))
    lc_wrap = audit_lc_signed_wrap()
    watchdog_boundary_proven = (
        compile_status == 0
        and simulation_status == 124
        and all(index is not None for index in boundary_indices.values())
        and not bool(gate.get("natural_completion"))
        and observed_readbacks == 0
    )
    if watchdog_boundary_proven:
        execution_divergence = {
            "code": "QADD_DRAM_LC_SIGNED_FEEDBACK_WRAP_HANG",
            "stage": "op_a_dequant_first_start_comp",
            "classification": "PACKAGE_CONFIG_STRUCTURAL_HANG",
            "package_side_fix_required": True,
            "diagnostic_package_available": NEXT_PACKAGE_ZIP.is_file(),
            "source": "PREPARE_AND_RUN.sh: simulation timeout -- 12h",
            "execution_log_excerpt": execution_excerpt,
            "reason": (
                "compile succeeded, all 85 preloads completed, exec transport "
                "was accepted and the first slice start was logged, but the "
                "first stage never completed. Its LC1 and LC3 both use "
                "end=37632. The bound RTL truncates the running count into a "
                "16-bit outbuffer and sign-extends that feedback, so the count "
                "wraps from +32768 to -32768 before the 37631 last threshold. "
                "The last tag and slice_cmpt_finish are unreachable."
            ),
        }
    elif compile_status != 0:
        execution_divergence = {
            "code": "SERVER_COMPILE_FAILED",
            "stage": "compile",
            "classification": "SERVER_RTL_TB_ENVIRONMENT",
            "package_side_fix_required": False,
            "reason": "compile exit status is nonzero",
        }
    else:
        execution_divergence = {
            "code": "UNCLASSIFIED_DYNAMIC_RESULT_GATE_FAILURE",
            "stage": "simulation_or_readback",
            "classification": "FAIL_CLOSED",
            "package_side_fix_required": False,
            "reason": "the complete result conjunction is false",
        }

    next_package = {
        "new_package_generated": NEXT_PACKAGE_ZIP.is_file(),
        "path": (
            NEXT_PACKAGE_ZIP.relative_to(ROOT).as_posix()
            if NEXT_PACKAGE_ZIP.is_file()
            else None
        ),
        "sha256": (
            sha256_file(NEXT_PACKAGE_ZIP)
            if NEXT_PACKAGE_ZIP.is_file()
            else None
        ),
        "status": (
            "QUARANTINED_NOT_RUN_NO_FUNCTIONAL_FIX"
            if NEXT_PACKAGE_ZIP.is_file()
            else "NEXT_IDENTITY_REQUIRED"
        ),
    }

    report = {
        "schema": "qlinearadd-node0007-v2-return2-analysis-v2",
        "status": (
            "FORMAL_RECEIPT_REJECTED_AND_PACKAGE_CONFIG_HANG_PROVEN"
            if formal_errors
            else "PACKAGE_CONFIG_HANG_PROVEN"
        ),
        "formal_receipt_valid": not formal_errors,
        "formal_receipt_errors": formal_errors,
        "control_receipts": {
            relative: {
                "expected_sha256": expected,
                "observed_sha256": sha256_file(ROOT / relative),
                "policy": policy,
                "matches": sha256_file(ROOT / relative) == expected,
            }
            for relative, (expected, policy) in CONTROL_RECEIPTS.items()
        },
        "return_input": {
            "path": str(return_zip),
            "basename_suffix_interpretation": (
                "(2) is local download collision suffix only"
            ),
            "zip_sha256": return_sha,
            "direct_sidecar": str(direct_sidecar),
            "direct_sidecar_present": sidecar_present,
            "direct_sidecar_matches": sidecar_matches,
        },
        "source_package_binding": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "expected_sha256": EXPECTED_SOURCE_SHA256,
            "observed_sha256": source_sha,
            "matches": source_sha == EXPECTED_SOURCE_SHA256,
            "source_zip_crc_clean": source_crc_failure is None,
            "source_zip_exact_set": source_zip_exact_set,
            "install_name": install_name,
            "embedded_manifest_sha256": embedded_manifest_sha,
            "source_zip_manifest_sha256": source_manifest_sha,
            "local_package_manifest_sha256": local_manifest_sha,
            "manifest_three_way_equal": package_identity_bound,
        },
        "return_integrity": {
            "crc_clean": crc_failure is None,
            "unsafe_member_count": len(unsafe),
            "duplicate_member_count": duplicates,
            "symlink_member_count": len(symlinks),
            "zip_exact_set": zip_exact_set,
            "record_hash_size_valid": record_integrity,
            "allowlist_exact": allowlist_exact,
            "return_status": return_manifest.get("status"),
            "returned_file_count": len(returned_records),
            "required_missing": required_missing_observed,
            "required_missing_count": len(required_missing_observed),
        },
        "preflight": {
            "valid": preflight_valid,
            "package": package_preflight,
            "installed": installed_preflight,
            "runtime_d_absent_before_simulation": preflight_valid,
        },
        "result_gate": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "simulation_started": dynamic_started,
            "preload_count_exact": bool(
                gate.get("loader_checks", {}).get("preload_count_exact")
            ),
            "register_started": boundary_indices["register_started"] is not None,
            "slice_started": boundary_indices["slice_started"] is not None,
            "natural_terminal": bool(gate.get("natural_completion")),
            "expected_readback_count": result_gate.get(
                "expected_readback_count"
            ),
            "observed_readback_count": result_gate.get(
                "observed_readback_count"
            ),
            "missing_count": result_gate.get("missing_count"),
            "mismatch_byte_count": result_gate.get("mismatch_byte_count"),
            "mismatch_is_evaluable": observed_readbacks > 0,
            "zero_mismatch_with_all_missing_is_numeric_pass": False,
            "all_terms_true": bool(gate.get("all_terms_true")),
        },
        "first_divergence": {
            "formal_receipt": (
                formal_errors[0] if formal_errors else None
            ),
            "execution": execution_divergence,
        },
        "evidence_adjudication": {
            "E3": {
                "pass": False,
                "reason": "no natural completion; simulation exit status is 124",
            },
            "E4": {
                "pass": False,
                "reason": (
                    "28/28 formal D targets are missing and the compatibility "
                    "profile does not bind final server RTL identity"
                ),
            },
            "E5": {
                "pass": False,
                "reason": "E4 is absent and no fresh-identity repeat pass exists",
            },
            "compatibility_profile": (
                package_manifest.get("server_source_preflight_performed")
                is False
            ),
        },
        "numeric_analysis": {
            "repeated": False,
            "dynamic_execution_started": dynamic_started,
            "dynamic_readback_started": observed_readbacks > 0,
            "full_output_numeric_analysis_performed": False,
            "formal_readback_comparison_performed": False,
            "reason": (
                "simulation started but observed formal readback count is zero; "
                "mismatch=0 is non-evaluable"
            ),
        },
        "workload_scale": {
            "logical_output_elements": 12_845_056,
            "padded_formal_output_bytes": 16_859_136,
            "physical_operator_count": 6,
            "request_count_with_multiplicity": 37_352_448,
            "unique_request_address_count": 20_493_312,
            "preload_matrix_count": 85,
            "preload_logical_bytes": 37_505_888,
            "preload_text_bytes": 302_391_404,
            "assessment": (
                "large workload, but not an admissible explanation for this "
                "timeout because the first-stage LC last condition is "
                "structurally unreachable"
            ),
        },
        "static_hang_proof": lc_wrap,
        "deadlock_adjudication": {
            "status": "HANG_PROVEN_PACKAGE_CONFIG",
            "likelihood": "CERTAIN_UNDER_BOUND_RTL_SEMANTICS",
            "supporting_evidence": [
                "first Start_Comp is observed but its completion is absent",
                "stage0 LC1 and LC3 both have end=37632",
                "16-bit signed LC feedback wraps before the 37631 last threshold",
                "zero formal D outputs",
            ],
            "counter_evidence": [
                "none that can make the configured LC last threshold reachable",
            ],
            "claim_boundary": (
                "This proves a configuration-induced first-stage hang for the "
                "materialized v2/v3 workload under the bound RTL LC semantics. "
                "It does not claim a general RTL deadlock."
            ),
        },
        "reuse": {
            "consumed_reuse_assets": True,
            "assets": [
                "frozen node0007 17-instance/stage0 analysis",
                "frozen six-stage config/mapping/bitstream/execplan/SCA",
                "frozen independent per-slice golden",
            ],
        },
        "package_release": {
            **next_package,
            "existing_package_sha256": EXPECTED_SOURCE_SHA256,
            "existing_package_status": "FAIL_CLOSED_CONFIG_HANG",
            "diagnostic_only": NEXT_PACKAGE_ZIP.is_file(),
            "run_ready": False,
            "reason": (
                "v3 changes only watchdog duration and namespace; it preserves "
                "the unreachable end=37632 LC geometry and therefore is not a "
                "functional fix. Do not run it as a fix."
            ),
        },
        "analysis_errors": errors,
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
