from __future__ import annotations

import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURN_ZIP = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_n71_gap_v4_hangloc_return.zip"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_n71_gap_v4_hangloc.zip"
)
OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-gap-node0071-v4-hangloc-return-analysis"
    / "report.json"
)
RETURN_ROOT = "r5_n71_gap_v4_hangloc_return"
SOURCE_ROOT = "r5_n71_gap_v4_hangloc"
EXPECTED_SOURCE_SHA256 = (
    "3c49472421dbf9e7a1cfc9bab42bdc677db6d2dc2781fb4ad18ff119968ac730"
)
SERVER_RULE_SHA256 = (
    "4c960c5cee73355d08f17d9d1a17edb2931b6a0336ae3831372b41f6af4dc8dc"
)
PLAN_SHA256 = (
    "c81e728358f50c4118fba2d4076612caf4ccfb3c28faadb7a0a7f5f9a7540f7f"
)
OBSERVER_SHA256 = (
    "47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49"
)
ENABLE_MACRO = "+define+NATIVE_RETURN_OBSERVER_ENABLE"


class AnalysisError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def object_from_bytes(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AnalysisError(f"invalid JSON: {label}") from error
    if not isinstance(value, dict):
        raise AnalysisError(f"JSON root differs: {label}")
    return value


def object_from_zip(
    archive: zipfile.ZipFile, member: str
) -> dict[str, Any]:
    return object_from_bytes(archive.read(member), member)


def safe_file_names(archive: zipfile.ZipFile) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for info in archive.infolist():
        pure = PurePosixPath(info.filename)
        mode = info.external_attr >> 16
        if (
            pure.is_absolute()
            or ".." in pure.parts
            or "\\" in info.filename
            or info.filename in seen
            or (mode and stat.S_ISLNK(mode))
        ):
            raise AnalysisError(f"unsafe ZIP member: {info.filename}")
        seen.add(info.filename)
        if not info.is_dir():
            names.append(info.filename)
    return names


def status(
    archive: zipfile.ZipFile, member: str
) -> int:
    try:
        return int(archive.read(member).decode("ascii").strip())
    except (KeyError, UnicodeError, ValueError) as error:
        raise AnalysisError(f"invalid status: {member}") from error


def parse_key_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def validate_return_manifest(
    archive: zipfile.ZipFile,
    names: list[str],
    manifest: dict[str, Any],
) -> tuple[set[str], set[str]]:
    prefix = f"{RETURN_ROOT}/"
    manifest_member = prefix + "RETURN_MANIFEST.json"
    records = manifest.get("files")
    if not isinstance(records, list):
        raise AnalysisError("RETURN_MANIFEST files absent")
    declared: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise AnalysisError("return manifest record differs")
        relative = str(record.get("path"))
        member = prefix + relative
        if member in declared or member not in names:
            raise AnalysisError(f"return manifest path differs: {relative}")
        payload = archive.read(member)
        if (
            len(payload) != record.get("size_bytes")
            or sha256_bytes(payload) != record.get("sha256")
        ):
            raise AnalysisError(f"return member receipt differs: {relative}")
        declared.add(member)
    if declared | {manifest_member} != set(names):
        raise AnalysisError("return ZIP exact-set differs")
    missing = manifest.get("required_missing")
    if (
        manifest.get("install_name") != SOURCE_ROOT
        or manifest.get("allowlist_only") is not True
        or manifest.get("status") != "incomplete"
        or not isinstance(missing, list)
    ):
        raise AnalysisError("return manifest boundary differs")
    return declared, {str(item) for item in missing}


def analyze() -> dict[str, Any]:
    sidecar = Path(str(RETURN_ZIP) + ".sha256")
    if not RETURN_ZIP.is_file() or not sidecar.is_file():
        raise AnalysisError("return ZIP or adjacent sidecar absent")
    return_sha = sha256_file(RETURN_ZIP)
    if sidecar.read_text(encoding="ascii") != (
        f"{return_sha}  {RETURN_ZIP.name}\n"
    ):
        raise AnalysisError("adjacent return sidecar differs")
    if sha256_file(SOURCE_ZIP) != EXPECTED_SOURCE_SHA256:
        raise AnalysisError("frozen source package differs")

    with zipfile.ZipFile(SOURCE_ZIP) as source:
        source_names = safe_file_names(source)
        if source.testzip() is not None:
            raise AnalysisError("source ZIP CRC differs")
        source_prefix = f"{SOURCE_ROOT}/"
        source_manifest_bytes = source.read(
            source_prefix + "TEST_PACKAGE_MANIFEST.json"
        )
        source_manifest = object_from_bytes(
            source_manifest_bytes, "source manifest"
        )
        runner = source.read(
            source_prefix + "PREPARE_AND_RUN.sh"
        ).decode("utf-8")
        observer = source.read(
            source_prefix + "tb_probe/native_return_observer.svh"
        )
        source_sca = source.read(
            source_prefix + "workload/sca_cfg.json"
        )
        source_sca_d = source.read(
            source_prefix + "workload/sca_cfg_D.json"
        )

    with zipfile.ZipFile(RETURN_ZIP) as archive:
        names = safe_file_names(archive)
        if archive.testzip() is not None:
            raise AnalysisError("return ZIP CRC differs")
        prefix = f"{RETURN_ROOT}/"
        evidence = prefix + "evidence/"
        return_manifest = object_from_zip(
            archive, prefix + "RETURN_MANIFEST.json"
        )
        declared, required_missing = validate_return_manifest(
            archive, names, return_manifest
        )
        returned_manifest_bytes = archive.read(
            evidence + "PACKAGE_MANIFEST.json"
        )
        returned_manifest = object_from_bytes(
            returned_manifest_bytes, "returned package manifest"
        )
        installed = object_from_zip(
            archive, evidence + "installed_preflight.json"
        )
        observer_precompile = object_from_zip(
            archive, evidence + "observer_precompile.json"
        )
        gate = object_from_zip(
            archive, evidence + "SERVER_RESULT_GATE.json"
        )
        compile_status = status(
            archive, evidence + "compile_exit_status.txt"
        )
        simulation_status = status(
            archive, evidence + "simulation_exit_status.txt"
        )
        runner_status = status(
            archive, evidence + "runner_exit_status.txt"
        )
        signal = parse_key_values(
            archive.read(evidence + "signal_status.txt").decode("utf-8")
        )
        timing = parse_key_values(
            archive.read(evidence + "host_timing.txt").decode("utf-8")
        )
        actual_argv = archive.read(
            evidence + "actual_simulator_argv.txt"
        ).decode("utf-8")
        binding = archive.read(
            evidence + "observer_binding.txt"
        ).decode("utf-8")
        progress_text = archive.read(
            evidence + "progress_samples.log"
        ).decode("utf-8")
        compile_log = archive.read(
            prefix + "logs/compile.log"
        ).decode("utf-8", "replace")
        sim_log = archive.read(
            prefix + "logs/sim.log"
        ).decode("utf-8", "replace")
        returned_sca = archive.read(prefix + "config/sca_cfg.json")
        returned_sca_d = archive.read(prefix + "config/sca_cfg_D.json")

    if (
        returned_manifest_bytes != source_manifest_bytes
        or returned_sca != source_sca
        or returned_sca_d != source_sca_d
    ):
        raise AnalysisError("returned package/SCA identity differs")
    allowlist = returned_manifest.get("return_allowlist")
    if not isinstance(allowlist, list):
        raise AnalysisError("return allowlist absent")
    allowed_targets = {
        str(item["target_path"])
        for item in allowlist
        if isinstance(item, dict)
    }
    returned_targets = {
        item.removeprefix(f"{RETURN_ROOT}/") for item in declared
    }
    if (
        not returned_targets <= allowed_targets
        or required_missing != allowed_targets - returned_targets
    ):
        raise AnalysisError("return allowlist/exact missing delta differs")

    checks = gate.get("checks")
    if not isinstance(checks, list) or len(checks) != 48:
        raise AnalysisError("formal D gate count differs")
    missing_formal = sum(item.get("status") == "missing" for item in checks)
    if (
        compile_status != 0
        or simulation_status != 125
        or runner_status != 125
        or signal.get("signal") != "INT"
        or gate.get("missing_count") != 48
        or missing_formal != 48
        or gate.get("mismatch_byte_count") != 0
        or gate.get("result_gate_conjunction", {}).get("all_terms_true")
        is not False
    ):
        raise AnalysisError("execution/result conjunction differs")
    if (
        installed.get("valid") is not True
        or installed.get("formal_readback_targets_absent") is not True
        or installed.get("package_preflight", {}).get("valid") is not True
    ):
        raise AnalysisError("installed preflight differs")

    package_start_ns = int(timing["package_start_epoch_ns"])
    sim_start_ns = int(timing["sim_start_epoch_ns"])
    final_ns = int(timing["final_epoch_ns"])
    progress_lines = progress_text.splitlines()
    progress_all_absent = (
        len(progress_lines) > 0
        and all(
            "observer_bytes=0" in line
            and "OBSERVER_NOT_CREATED" in line
            for line in progress_lines
        )
    )
    slice_match = re.search(r"\[(\d+)\].*INFO: slice start", sim_log)
    interrupt_match = re.search(r"Interrupt at time\s+(\d+)", sim_log)
    if slice_match is None or interrupt_match is None:
        raise AnalysisError("simulation time milestones absent")
    slice_start_ps = int(slice_match.group(1))
    interrupt_ps = int(interrupt_match.group(1))

    include_term = "+incdir+$package_root/tb_probe"
    runtime_terms = (
        "+RETURN_OBSERVER",
        "+RETURN_OBS_HEARTBEAT_CYCLES=262144",
        "+RETURN_OBS_STALL_CYCLES=1048576",
        "+RETURN_OBS_FILE=$observer_log",
    )
    four_way = {
        "source": {
            "pass": (
                sha256_bytes(observer) == OBSERVER_SHA256
                and observer_precompile.get("identity_match") is True
            ),
            "unique_source_count": sum(
                item.endswith("/tb_probe/native_return_observer.svh")
                for item in source_names
            ),
            "source_sha256": sha256_bytes(observer),
        },
        "include": {
            "pass": include_term in runner and "tb_probe" in compile_log,
            "package_local_incdir_in_runner": include_term in runner,
            "actual_compile_log_incdir": "tb_probe" in compile_log,
        },
        "compile_enable": {
            "pass": (
                ENABLE_MACRO in runner and ENABLE_MACRO in compile_log
            ),
            "runner_contains_enable_macro": ENABLE_MACRO in runner,
            "compile_log_contains_enable_macro": ENABLE_MACRO in compile_log,
        },
        "runtime_return": {
            "pass": (
                all(term.replace("$observer_log", "") in actual_argv
                    for term in runtime_terms[:-1])
                and "+RETURN_OBS_FILE=" in actual_argv
                and "[RETURN_OBSERVER] enabled" in sim_log
                and "observer_enabled_and_returned=true" in binding
                and "runs/return_observer.log" in returned_targets
            ),
            "actual_argv_bound": (
                "+RETURN_OBSERVER" in actual_argv
                and "+RETURN_OBS_FILE=" in actual_argv
            ),
            "time0_enabled_marker": "[RETURN_OBSERVER] enabled" in sim_log,
            "binding_receipt": binding.strip(),
            "observer_log_returned":
                "runs/return_observer.log" in returned_targets,
            "observer_log_required_missing":
                "runs/return_observer.log" in required_missing,
        },
    }
    if (
        four_way["source"]["unique_source_count"] != 1
        or not four_way["source"]["pass"]
        or not four_way["include"]["pass"]
        or four_way["compile_enable"]["pass"]
        or four_way["runtime_return"]["pass"]
        or not progress_all_absent
    ):
        raise AnalysisError("observer four-way diagnosis differs")

    natural_terminal = "Simulation completed successfully!" in sim_log
    formal_dump = bool(
        re.search(r"JSON_D config:\s*48\s+matrices dumped", sim_log)
    )
    result = {
        "schema": "resnet50-gap-node0071-v4-hangloc-return-analysis-v1",
        "status": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
        "return_analysis": {
            "zip": str(RETURN_ZIP),
            "zip_size_bytes": RETURN_ZIP.stat().st_size,
            "zip_sha256": return_sha,
            "sidecar": str(sidecar),
            "sidecar_sha256": sha256_file(sidecar),
            "sidecar_content_exact": True,
            "zip_crc_valid": True,
            "safe_exact_set_valid": True,
            "member_count": len(names),
            "manifest_record_count": len(return_manifest["files"]),
            "allowlist_only": True,
            "allowlist_exact_delta_valid": True,
            "required_missing_count": len(required_missing),
        },
        "bound_source_package": {
            "zip": str(SOURCE_ZIP.relative_to(ROOT).as_posix()),
            "zip_sha256": EXPECTED_SOURCE_SHA256,
            "zip_crc_valid": True,
            "install_name": SOURCE_ROOT,
            "manifest_byte_equal": True,
            "sca_byte_equal": True,
            "sca_d_byte_equal": True,
            "observer_sha256": OBSERVER_SHA256,
        },
        "preflight": {
            "package_valid": True,
            "installed_valid": True,
            "installed_file_count": installed["installed_file_count"],
            "runtime_d_targets_absent_post_install": True,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "runner_exit_status": runner_status,
            "signal": signal.get("signal"),
            "natural_terminal": natural_terminal,
            "formal_dump_48": formal_dump,
            "host_package_seconds":
                (final_ns - package_start_ns) / 1e9,
            "host_simulation_seconds":
                (final_ns - sim_start_ns) / 1e9,
            "slice_start_time_ps": slice_start_ps,
            "interrupt_time_ps": interrupt_ps,
            "post_slice_start_sim_time_ps":
                interrupt_ps - slice_start_ps,
            "post_slice_start_sim_time_ms":
                (interrupt_ps - slice_start_ps) / 1e9,
        },
        "formal_readback": {
            "expected_count": 48,
            "present_count": 0,
            "missing_count": 48,
            "mismatch_byte_count": 0,
            "zero_mismatch_evaluable": False,
            "result_gate_all_terms_true": False,
            "e3": "FAIL",
            "e4": "FAIL",
            "e5": "FAIL",
        },
        "progress_evidence": {
            "host_sample_count": len(progress_lines),
            "all_samples_observer_not_created": progress_all_absent,
            "stage_start_comp_observed": False,
            "qualified_accepted_observed": False,
            "qualified_completion_observed": False,
            "last_terminal_observed": False,
            "stall_window_evaluable": False,
            "simulator_event_time_advanced": True,
        },
        "observer_four_way_binding": four_way,
        "progress_adjudication": {
            "classification": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
            "not_classified_as": [
                "STILL_PROGRESSING_NOT_FINISHED",
                "LONG_RUNNING_HANG_AT_<boundary>",
            ],
            "reason": (
                "The package-local source and +incdir were present and "
                "runtime plusargs were passed, but the compile command omitted "
                "+define+NATIVE_RETURN_OBSERVER_ENABLE. The guarded observer "
                "branch was therefore not selected; no time-0 marker, observer "
                "log, qualified progress counter, or stall-window evidence "
                "exists. Simulator-time advancement and manual INT cannot "
                "distinguish DUT progress from stall."
            ),
        },
        "hang_root_cause":
            "UNRESOLVED_DUE_TO_PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
        "first_divergence": {
            "classification":
                "PACKAGE_OBSERVER_ENABLE_MACRO_NOT_BOUND_AT_COMPILE",
            "boundary": "compile command construction before simulation",
            "expected": ENABLE_MACRO,
            "actual": (
                "VCS_EXTRA_OPTS contained only package-local +incdir; "
                "runtime +RETURN_OBSERVER cannot enable a compile-guarded include"
            ),
        },
        "blocker_delta": {
            "added": [
                "B_GAP_NODE0071_V4_PACKAGE_OBSERVER_COMPILE_ENABLE_MISSING"
            ],
            "reclassified": [
                "B_GAP_NODE0071_LONG_RUNNING_HANG_ROOT_CAUSE -> "
                "UNRESOLVED_DUE_TO_PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
            ],
            "kept": [
                "B_GAP_NODE0071_DYNAMIC_RESULT",
                "B_GAP_SERVER_RTL_IDENTITY_UNBOUND",
                "B_GAP_E4_E5",
            ],
        },
        "rule_delta_proposal": {
            "status": "ALREADY_COVERED",
            "rule":
                "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
            "anti_regression_acceptance": [
                "final ZIP contains exactly one manifest-bound observer source",
                "final compile driver binds package-local +incdir",
                "final compile driver binds the exact enable macro",
                "runtime argv, time-0 marker, observer log, actual argv, "
                "progress summary, allowlist, and signal trap form one receipt",
                "negative controls removing source/include/macro/runtime-return "
                "each fail closed",
            ],
        },
        "rule_receipts": {
            "server_package_rule_sha256": SERVER_RULE_SHA256,
            "plan_sha256_mutable_provenance_only": PLAN_SHA256,
            "four_way_rule":
                "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
        },
        "package_release": {
            "status":
                "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN",
            "install_name": "r5_n71_gap_v5_obsbind",
            "zip":
                "artifacts/operator_config_validation/"
                "r5-server-test-packages/r5_n71_gap_v5_obsbind.zip",
            "zip_size_bytes": 1782093,
            "zip_sha256":
                "159bebac586be3a40ae937736b0368593"
                "ced34c7b8128fde7858930b53ebef8d",
            "functional_fix": False,
            "numeric_workload_file_count": 73,
            "numeric_workload_tree_equal": True,
            "four_way_final_zip_validation": "PASS",
            "negative_control_count": 4,
            "all_negative_controls_fail_closed": True,
            "server_action": False,
        },
        "numeric_analysis_repeated": False,
        "reuse_assets_consumed": [
            "frozen node0071 complete local E2",
            "frozen v4 workload and source package",
        ],
    }
    return result


def main() -> int:
    result = analyze()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
