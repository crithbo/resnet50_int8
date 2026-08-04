from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INSTALL_NAME = "r5_conv_native_four_lane_df23e4d_perf_v1"
RUNTIME_REL = Path(
    "package_tools/node0004_assumed_hardware_server_runtime.py"
)
GUARD_REL = Path("package_tools/node0004_package_observer_guard.py")
OBSERVER_REL = Path("tb_probe/native_return_observer.svh")
REQUIRED_RUNNER_BINDINGS = (
    "+define+NATIVE_RETURN_OBSERVER_ENABLE",
    "+incdir+$package_root/tb_probe",
    "+RETURN_OBSERVER",
    "+RETURN_OBS_FILE=$observer_log",
    "+RETURN_OBS_EXPECTED_STAGES=$expected_stages",
    "+RETURN_OBS_STALL_CYCLES=1048576",
    "+RETURN_OBS_HEARTBEAT_CYCLES=262144",
    "compile-identity",
    "qualify-run",
    "production_rtl_identity.json",
    "natural_terminal/$id.json",
    "materialize-tail",
    "analyze",
    "collect",
)
FORBIDDEN_SERVER_PREFLIGHT = (
    'find "$server_root"',
    'rg "$server_root"',
    'grep -R "$server_root"',
    "git -C",
    "sha256sum",
)
RTL_SUFFIXES = {".v", ".sv", ".vh", ".svh"}


class ValidationError(ValueError):
    pass


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValidationError(f"JSON root must be object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def package_records(root: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative == "package_manifest.json":
            continue
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return result


def read_zip(zip_path: Path) -> tuple[dict[str, bytes], list[str]]:
    entries: dict[str, bytes] = {}
    errors: list[str] = []
    with zipfile.ZipFile(zip_path) as archive:
        names = [info.filename for info in archive.infolist()]
        if len(names) != len(set(names)):
            errors.append("ZIP contains duplicate member paths")
        bad = archive.testzip()
        if bad is not None:
            errors.append(f"ZIP CRC failure: {bad}")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or not pure.parts
                or pure.parts[0] != INSTALL_NAME
            ):
                errors.append(f"unsafe or wrong-root ZIP member: {info.filename}")
                continue
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                errors.append(f"ZIP symlink member is forbidden: {info.filename}")
                continue
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            entries[relative] = archive.read(info)
    return entries, errors


def run_python(
    runtime: Path, arguments: list[str], *, expected_zero: bool
) -> dict[str, Any]:
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-B", str(runtime), *arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=180,
        check=False,
    )
    if expected_zero and result.returncode != 0:
        raise ValidationError(
            f"runtime control failed: rc={result.returncode}: "
            f"{result.stderr[-1000:]}"
        )
    if not expected_zero and result.returncode == 0:
        raise ValidationError("negative runtime control did not fail closed")
    return {
        "command": [sys.executable, "-B", str(runtime), *arguments],
        "cwd": os.getcwd(),
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-1000:],
        "stderr_tail": result.stderr[-1000:],
    }


def validate_runner(text: str) -> dict[str, Any]:
    missing = [token for token in REQUIRED_RUNNER_BINDINGS if token not in text]
    forbidden = [token for token in FORBIDDEN_SERVER_PREFLIGHT if token in text]
    compile_once = (
        text.count("make -f Makefile.tb_NDP_Top_new_phy compile") == 2
    )
    loops_complete = (
        "for id in c0 c1 c2; do" in text
        and "for id in t000 t001 t002 t003 t004 t005 t006 t007 "
        "t100 t101 t102 t103 t104 t105 t106 t107 "
        "t200 t201 t202 t203 t204 t205 t206 t207; do" in text
    )
    post_compile_identity = (
        text.index("compile-identity")
        > text.rindex("make -f Makefile.tb_NDP_Top_new_phy compile")
    ) if "compile-identity" in text and compile_once else False
    return {
        "valid": (
            not missing
            and not forbidden
            and compile_once
            and loops_complete
            and post_compile_identity
        ),
        "missing_bindings": missing,
        "forbidden_server_preflight_tokens": forbidden,
        "compile_once": compile_once,
        "run_loops_complete": loops_complete,
        "post_compile_identity": post_compile_identity,
    }


def sca_closure(package: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    runtime_root = package / "workload/runtime"
    sca_paths = sorted(runtime_root.glob("runs/*/sca_cfg*.json"))
    errors: list[str] = []
    consumer_count = 0
    formal_d_consumers = 0
    checks = manifest.get("readback_checks", [])
    formal_d_paths = {
        str(record["runtime_path"]) for record in checks
    }
    tail_materialization = manifest.get("tail_materialization", [])
    dynamic_tail_inputs = {
        str(record["tail_input"]) for record in tail_materialization
    }
    tail_sources = {
        str(record["conv_readback"]) for record in tail_materialization
    }
    dynamic_tail_consumers = 0
    for sca_path in sca_paths:
        value = load_json(sca_path)
        for item in value.values():
            if not isinstance(item, dict) or not isinstance(
                item.get("path"), str
            ):
                continue
            consumer_count += 1
            relative = str(item["path"])
            prefix = f"install/cfg_pkg/{INSTALL_NAME}/"
            if not relative.startswith(prefix):
                errors.append(f"noncanonical SCA path: {relative}")
                continue
            runtime_relative = relative[len(prefix) :]
            target = runtime_root / Path(
                *PurePosixPath(runtime_relative).parts
            )
            if runtime_relative in formal_d_paths:
                formal_d_consumers += 1
            elif runtime_relative in dynamic_tail_inputs:
                dynamic_tail_consumers += 1
            elif not target.is_file():
                errors.append(f"missing SCA consumer: {relative}")
    runtime_absent = 0
    golden_present = 0
    for record in checks:
        runtime_path = runtime_root / Path(
            *PurePosixPath(str(record["runtime_path"])).parts
        )
        golden_path = package / Path(
            *PurePosixPath(str(record["golden_path"])).parts
        )
        runtime_absent += not runtime_path.exists()
        golden_present += golden_path.is_file()
    return {
        "valid": (
            not errors
            and len(sca_paths) == 54
            and len(checks) == 320
            and formal_d_consumers == 320
            and dynamic_tail_consumers == len(dynamic_tail_inputs)
            and tail_sources <= formal_d_paths
            and runtime_absent == 320
            and golden_present == 320
        ),
        "sca_file_count": len(sca_paths),
        "sca_consumer_path_count": consumer_count,
        "formal_readback_count": len(checks),
        "formal_D_consumer_path_count": formal_d_consumers,
        "dynamic_tail_input_count": len(dynamic_tail_inputs),
        "dynamic_tail_consumer_path_count": dynamic_tail_consumers,
        "tail_source_formal_D_closure": tail_sources <= formal_d_paths,
        "runtime_D_absent_count": runtime_absent,
        "golden_D_present_count": golden_present,
        "errors": errors[:20],
    }


def _focus_prefix() -> str:
    return r"""
`timescale 1ns/1ps
`define SLICE_GROUP_SIZE 1
`define SLICE_GROUP_NUM 1
`define MEMORY_STREAM_ENGINE_NUM 1
`define MSE_REQ_CHL_NUM 1
`define BANK_NUM_PER_SLICE 1
module n4_sem_stub;
  logic sem2scm_cfg_start, scm2sem_cfg_finish;
  logic sem2iga_exec_start, slice_cmpt_finish;
endmodule
module n4_slice_stub;
  n4_sem_stub u_Slice_Execution_Manager();
endmodule
module n4_wrapper_stub;
  n4_slice_stub u_Slice();
endmodule
module n4_group_stub;
  generate for (genvar s=0; s<1; s++) begin : slice_group_gen
    n4_wrapper_stub u_slice_wrapper();
  end endgenerate
endmodule
module n4_ndp_stub;
  logic clk_db, rst_n_db;
  generate for (genvar g=0; g<1; g++) begin : slice_with_datahub_mc_group_gen
    n4_group_stub u_slice_with_datahub_mc_group();
  end endgenerate
endmodule
module conv_native4_observer_focus_top;
  n4_ndp_stub u_NDP_Top_new();
  logic [0:0][0:0][0:0][0:0] local_req_hs;
  logic [0:0][0:0][0:0][0:0] local_rdata_hs;
  logic [0:0][0:0][0:0][0:0] local_wdata_hs;
  logic [0:0][0:0][0:0] bank_frame_hs;
"""


def _compile_focus(
    iverilog: Path, root: Path, name: str, source: str
) -> dict[str, Any]:
    source_path = root / f"{name}.sv"
    output_path = root / f"{name}.out"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    command = [
        str(iverilog),
        "-g2012",
        "-s",
        "conv_native4_observer_focus_top",
        "-o",
        str(output_path),
        str(source_path),
    ]
    result = subprocess.run(
        command,
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
    )
    return {
        "command": command,
        "cwd": str(root),
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _observer_semantic_closure(source: str) -> dict[str, Any]:
    counters = (
        "n4_obs_cfg_start_count",
        "n4_obs_cfg_finish_count",
        "n4_obs_exec_start_count",
        "n4_obs_slice_finish_count",
        "n4_obs_req_accept_count",
        "n4_obs_rdata_accept_count",
        "n4_obs_wdata_accept_count",
        "n4_obs_bank_accept_count",
        "n4_obs_qualified_total",
    )
    task = source[
        source.index("function automatic void n4_obs_emit_canonical") :
        source.index("endfunction") + len("endfunction")
    ]
    per_counter = {}
    for identifier in counters:
        per_counter[identifier] = {
            "declared_once": source.count(
                f"longint unsigned {identifier};"
            )
            == 1,
            "initialized_initial_and_reset": source.count(
                f"{identifier} = 0;"
            )
            >= 2,
            "qualified_update_present": source.count(
                f"{identifier}++;"
            )
            >= 1,
            "canonical_consumer_use": identifier in task,
        }
    checks = {
        "all_counter_roles_closed": all(
            all(record.values()) for record in per_counter.values()
        ),
        "feature_time0_contract": (
            source.count("N4PERF_FEATURE_ENABLE_V1") >= 2
        ),
        "single_canonical_schema": (
            source.count(
                '"N4PERF_CANONICAL_DECISION_V1 schema='
            )
            == 1
        ),
        "qualified_progress_excludes_raw_samples": (
            "n4_obs_raw_sample_count++;" in source
            and "n4_obs_qualified_total++;" in source
        ),
        "final_expected_stage_decision": (
            '"EXPECTED_STAGE_PREFIX_COMPLETE"' in source
            and "n4_obs_exec_start_count ==" in source
            and "n4_obs_slice_finish_count ==" in source
        ),
        "read_only_xmr": not re.search(
            r"u_NDP_Top_new[\w.\[\]]*\s*(?:<=|=(?!=))", source
        ),
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "per_counter": per_counter,
    }


def observer_scope(
    package: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    observer = package / OBSERVER_REL
    text = observer.read_text(encoding="utf-8")
    payload = observer.read_bytes()
    expected = manifest["observer_binding"]["source_sha256"]
    errors: list[str] = []
    if sha256(observer) != expected:
        errors.append("exact observer SHA differs from final manifest")
    iverilog_name = shutil.which("iverilog")
    if not iverilog_name:
        raise ValidationError("Icarus Verilog compatible frontend is unavailable")
    iverilog = Path(iverilog_name)
    selector_specializations = (
        "[n4_obs_group_id]",
        "[n4_obs_local_slice_id]",
        "[n4_obs_mse]",
        "[n4_obs_req]",
        "[n4_obs_bank]",
    )
    specialized_text = text
    for selector in selector_specializations:
        specialized_text = specialized_text.replace(selector, "[0]")
    focused = _focus_prefix() + specialized_text + "\nendmodule\n"
    closure = _observer_semantic_closure(text)
    task_start = specialized_text.index(
        "function automatic void n4_obs_emit_canonical"
    )
    task_end = specialized_text.index("endfunction", task_start)
    task_text = specialized_text[task_start:task_end]
    typo_task = task_text.replace(
        "n4_obs_req_accept_count",
        "n4_obs_req_accept_count_typo",
        1,
    )
    typo_source = (
        _focus_prefix()
        + specialized_text[:task_start]
        + typo_task
        + specialized_text[task_end:]
        + "\nendmodule\n"
    )
    deleted_source = focused.replace(
        "longint unsigned n4_obs_req_accept_count;\n", "", 1
    )
    update_mutant_text = text.replace(
        "n4_obs_req_accept_count++;\n", "", 1
    )
    update_mutant_specialized = update_mutant_text
    for selector in selector_specializations:
        update_mutant_specialized = update_mutant_specialized.replace(
            selector, "[0]"
        )
    update_mutant_source = (
        _focus_prefix() + update_mutant_specialized + "\nendmodule\n"
    )
    update_closure = _observer_semantic_closure(update_mutant_text)
    with tempfile.TemporaryDirectory(prefix="native4-hdl-focus-") as name:
        root = Path(name)
        positive = _compile_focus(iverilog, root, "positive", focused)
        deleted = _compile_focus(
            iverilog, root, "negative_delete_declaration", deleted_source
        )
        typo = _compile_focus(
            iverilog, root, "negative_misspell_consumer", typo_source
        )
        update = _compile_focus(
            iverilog, root, "negative_delete_update", update_mutant_source
        )
    version = subprocess.run(
        [str(iverilog), "-V"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    negative_checks = {
        "delete_declaration_fail_closed": deleted["exit_code"] != 0,
        "misspell_consumer_use_fail_closed": typo["exit_code"] != 0,
        "delete_reset_or_update_fail_closed": not update_closure["valid"],
    }
    if positive["exit_code"] != 0:
        errors.append("focused compatible frontend positive failed")
    if not closure["valid"]:
        errors.append("required observer state ownership closure failed")
    if not all(negative_checks.values()):
        errors.append("one or more HDL scope negatives did not fail closed")
    include_order = (
        "+define+NATIVE_RETURN_OBSERVER_ENABLE\n"
        "+incdir+<package>/tb_probe\n"
        "native_return_observer.svh\n"
    ).encode()
    gate = {
        "applicable": True,
        "rule_id": (
            "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-"
            "SYNTAX-SCOPE-POSITIVE-001"
        ),
        "exact_members": [
            {
                "path": f"{INSTALL_NAME}/{OBSERVER_REL.as_posix()}",
                "bytes": len(payload),
                "sha256": sha256_bytes(payload),
                "role": "package-local read-only qualified progress observer",
            }
        ],
        "include_or_concatenation_order_sha256": sha256_bytes(include_order),
        "frontend": {
            "name": "Icarus Verilog",
            "version": (version.stdout + version.stderr)[:4000],
            "command": positive["command"],
            "cwd": positive["cwd"],
            "exit": positive["exit_code"],
            "coverage": "focused",
        },
        "focused_harness_sha256": sha256_bytes(focused.encode()),
        "specializations": [
            {
                "original_source_sha256": sha256_bytes(payload),
                "specialized_source_sha256": sha256_bytes(
                    specialized_text.encode()
                ),
                "replacement_count": (
                    sum(text.count(selector) for selector in selector_specializations)
                ),
                "macros": {
                    "SLICE_GROUP_SIZE": 1,
                    "SLICE_GROUP_NUM": 1,
                    "MEMORY_STREAM_ENGINE_NUM": 1,
                    "MSE_REQ_CHL_NUM": 1,
                    "BANK_NUM_PER_SLICE": 1,
                },
                "reason": (
                    "Icarus lacks runtime indexing for these packed monitor "
                    "arrays; external group/slice/MSE/request/bank selectors "
                    "are fixed to zero "
                    "while exact counter declarations, qualified updates, "
                    "canonical consumers and state ownership remain unchanged"
                ),
                "target_statements_rewritten": False,
            }
        ],
        "closure": {
            "scope": (
                "all native4 qualified counters, runtime feature initialization, "
                "canonical record consumers and final ordered-stage decision"
            ),
            "declared": len(closure["per_counter"]),
            "used": len(closure["per_counter"]),
            "unresolved": 0 if closure["valid"] else 1,
            "ownerless_state": 0 if closure["valid"] else 1,
        },
        "negative_controls": negative_checks,
        "claim_boundary": (
            "exact final package-local observer syntax, focused XMR name "
            "resolution and all native4 required diagnostic state ownership; "
            "not production full-design VCS elaboration or server RTL identity"
        ),
        "pass": not errors,
    }
    return {
        "valid": not errors,
        "errors": errors,
        "package_local_hdl_gate": gate,
        "positive": positive,
        "semantic_closure": closure,
        "negative_delete_declaration": deleted,
        "negative_misspell_consumer": typo,
        "negative_delete_update": update,
        "negative_delete_update_semantic_closure": update_closure,
    }


def update_manifest_record(package: Path, relative: str) -> None:
    manifest_path = package / "package_manifest.json"
    manifest = load_json(manifest_path)
    target = package / Path(*PurePosixPath(relative).parts)
    manifest["files"][relative] = {
        "size_bytes": target.stat().st_size,
        "sha256": sha256(target),
    }
    write_json(manifest_path, manifest)


def negative_controls(package: Path) -> dict[str, Any]:
    runtime = package / RUNTIME_REL
    guard = package / GUARD_REL
    manifest_path = package / "package_manifest.json"
    manifest_original = manifest_path.read_bytes()
    observer = package / OBSERVER_REL
    observer_original = observer.read_bytes()
    controls: dict[str, Any] = {}

    extra = package / "UNDECLARED_NEGATIVE_CONTROL"
    extra.write_bytes(b"x")
    controls["exact_set_extra_file"] = run_python(
        runtime, ["preflight", "--package-root", str(package)], expected_zero=False
    )
    extra.unlink()

    observer.unlink()
    controls["observer_source_deleted"] = run_python(
        runtime, ["preflight", "--package-root", str(package)], expected_zero=False
    )
    observer.write_bytes(observer_original)

    manifest = load_json(manifest_path)
    first = manifest["readback_checks"][0]
    preloaded = package / "workload/runtime" / Path(
        *PurePosixPath(str(first["runtime_path"])).parts
    )
    golden = package / Path(*PurePosixPath(str(first["golden_path"])).parts)
    preloaded.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(golden, preloaded)
    update_manifest_record(
        package, preloaded.relative_to(package).as_posix()
    )
    controls["preloaded_formal_D"] = run_python(
        runtime, ["preflight", "--package-root", str(package)], expected_zero=False
    )
    preloaded.unlink()
    manifest_path.write_bytes(manifest_original)

    observer.write_bytes(observer_original + b"\n")
    update_manifest_record(package, OBSERVER_REL.as_posix())
    run_python(
        runtime, ["preflight", "--package-root", str(package)], expected_zero=True
    )
    controls["observer_sha"] = run_python(
        guard,
        [
            "--package-root",
            str(package),
        ],
        expected_zero=False,
    )
    observer.write_bytes(observer_original)
    manifest_path.write_bytes(manifest_original)

    runner = (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8")
    macro_negative = validate_runner(
        runner.replace("+define+NATIVE_RETURN_OBSERVER_ENABLE", "+define+REMOVED")
    )
    return_negative = validate_runner(
        runner.replace("+RETURN_OBS_FILE=$observer_log", "+REMOVED_RETURN_TARGET")
    )
    incdir_negative = validate_runner(
        runner.replace(
            "+incdir+$package_root/tb_probe",
            "+incdir+$package_root/removed",
        )
    )
    if (
        macro_negative["valid"]
        or return_negative["valid"]
        or incdir_negative["valid"]
    ):
        raise ValidationError("runner binding deletion did not fail closed")
    controls["runner_delete_compile_macro"] = macro_negative
    controls["runner_delete_compile_incdir"] = incdir_negative
    controls["runner_delete_return_target"] = return_negative

    revalidation = load_json(
        ROOT / "outputs/conv_native_four_lane_df23e4d_revalidation/report.json"
    )
    leaf_records = revalidation["current_rtl_identity"]["leaves"]
    compile_log = package.parent / "identity-positive.log"
    compile_log.write_text(
        "\n".join(
            f"Parsing design file '{ROOT / record['path']}'"
            for record in leaf_records.values()
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    identity_output = package.parent / "identity-positive.json"
    controls["production_identity_positive"] = run_python(
        runtime,
        [
            "compile-identity",
            "--compile-log",
            str(compile_log),
            "--output",
            str(identity_output),
        ],
        expected_zero=True,
    )
    bad_log = package.parent / "identity-negative.log"
    bad_log.write_text(
        compile_log.read_text(encoding="utf-8").replace(
            "SA_PE_Float_CSA.v", "SA_PE_Float_CSA_missing.v"
        ),
        encoding="utf-8",
        newline="\n",
    )
    controls["production_identity_missing_leaf"] = run_python(
        runtime,
        [
            "compile-identity",
            "--compile-log",
            str(bad_log),
            "--output",
            str(package.parent / "identity-negative.json"),
        ],
        expected_zero=False,
    )

    sim_log = package.parent / "natural-positive.log"
    observer_log = package.parent / "natural-observer.log"
    sim_log.write_text(
        "[RETURN_OBSERVER] enabled "
        "N4PERF_FEATURE_ENABLE_V1 feature=NATIVE4_PROGRESS enabled=1 "
        "heartbeat_cycles=262144 stall_window_cycles=1048576 "
        "expected_stages=1\n"
        "$finish at simulation time 123\n",
        encoding="utf-8",
        newline="\n",
    )
    observer_log.write_text(
        "# Conv native four-lane progress observer v1\n"
        "N4PERF_FEATURE_ENABLE_V1 feature=NATIVE4_PROGRESS enabled=1 "
        "heartbeat_cycles=262144 stall_window_cycles=1048576 "
        "expected_stages=1\n"
        "N4PERF_CANONICAL_DECISION_V1 "
        "decision=EXPECTED_STAGE_PREFIX_COMPLETE reason=control "
        "boundary=slice_finish\n",
        encoding="utf-8",
        newline="\n",
    )
    controls["natural_terminal_positive"] = run_python(
        runtime,
        [
            "qualify-run",
            "--run-id",
            "control",
            "--sim-log",
            str(sim_log),
            "--observer-log",
            str(observer_log),
            "--output",
            str(package.parent / "natural-positive.json"),
        ],
        expected_zero=True,
    )
    sim_log.write_text(
        "[RETURN_OBSERVER] enabled "
        "N4PERF_FEATURE_ENABLE_V1 feature=NATIVE4_PROGRESS enabled=1 "
        "heartbeat_cycles=262144 stall_window_cycles=1048576 "
        "expected_stages=1\n",
        encoding="utf-8",
        newline="\n",
    )
    controls["natural_terminal_missing"] = run_python(
        runtime,
        [
            "qualify-run",
            "--run-id",
            "control",
            "--sim-log",
            str(sim_log),
            "--observer-log",
            str(observer_log),
            "--output",
            str(package.parent / "natural-negative.json"),
        ],
        expected_zero=False,
    )
    return controls


def runner_compile_stub(package: Path, root: Path) -> dict[str, Any]:
    bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if not bash.is_file():
        raise ValidationError("Git Bash is unavailable for runner control")
    server = root / "stub-server"
    stub_bin = root / "stub-bin"
    server.mkdir()
    stub_bin.mkdir()
    python_path = Path(sys.executable).resolve().as_posix()
    python_stub = stub_bin / "python3"
    python_stub.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{python_path}" -B "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    make_stub = stub_bin / "make"
    make_stub.write_text(
        "#!/usr/bin/env bash\n"
        "echo COMPILE_STUB_REACHED\n"
        "exit 73\n",
        encoding="utf-8",
        newline="\n",
    )
    os.chmod(python_stub, 0o755)
    os.chmod(make_stub, 0o755)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PATH"] = str(stub_bin) + os.pathsep + env.get("PATH", "")
    server_git_path = (
        f"/{server.drive[0].lower()}"
        f"{server.as_posix()[len(server.drive):]}"
    )
    result = subprocess.run(
        [
            str(bash),
            str(package / "PREPARE_AND_RUN.sh"),
            server_git_path,
        ],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=300,
        check=False,
    )
    install_name = INSTALL_NAME
    compile_log = (
        server
        / f"run_{install_name}/compile/sim_results/compile_driver.log"
    )
    return_zip = server / f"{install_name}_return.zip"
    result_gate = (
        server / f"{install_name}_return/evidence/SERVER_RESULT_GATE.json"
    )
    valid = (
        result.returncode == 73
        and compile_log.is_file()
        and "COMPILE_STUB_REACHED" in compile_log.read_text(
            encoding="utf-8", errors="replace"
        )
        and return_zip.is_file()
        and result_gate.is_file()
        and load_json(result_gate).get("status")
        == "CONV_NATIVE_FOUR_LANE_SERVER_FAILURE"
    )
    return {
        "valid": valid,
        "runner_exit": result.returncode,
        "expected_compile_stub_exit": 73,
        "compile_stub_reached": compile_log.is_file()
        and "COMPILE_STUB_REACHED"
        in compile_log.read_text(encoding="utf-8", errors="replace"),
        "failure_return_zip_created": return_zip.is_file(),
        "failure_result_gate_created": result_gate.is_file(),
        "stdout_tail": result.stdout[-1000:],
        "stderr_tail": result.stderr[-1000:],
    }


def runner_signal_stub(package: Path, root: Path) -> dict[str, Any]:
    bash = Path(r"C:\Program Files\Git\bin\bash.exe")
    if not bash.is_file():
        raise ValidationError("Git Bash is unavailable for signal control")
    server = root / "signal-stub-server"
    stub_bin = root / "signal-stub-bin"
    control = root / "signal-stub-control"
    server.mkdir()
    stub_bin.mkdir()
    control.mkdir()
    sim_started = control / "sim-started.txt"
    stdout_path = control / "runner.stdout"
    stderr_path = control / "runner.stderr"
    status_path = control / "runner.status"

    def git_path(path: Path) -> str:
        resolved = path.resolve()
        return (
            f"/{resolved.drive[0].lower()}"
            f"{resolved.as_posix()[len(resolved.drive):]}"
        )

    python_path = git_path(Path(sys.executable))
    python_stub = stub_bin / "python3"
    python_stub.write_text(
        "#!/usr/bin/env bash\n"
        f'exec "{python_path}" -B "$@"\n',
        encoding="utf-8",
        newline="\n",
    )
    leaves = {
        path.name: path
        for path in (
            ROOT
            / "NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU"
        ).glob("*.v")
        if path.name
        in {
            "SA_PE_Float_CSA.v",
            "SA_PE_Float_Control.v",
            "SA_PE_Mul_Array.v",
            "SA_ALU.v",
        }
    }
    expected_leaves = load_json(package / "package_manifest.json")[
        "expected_production_rtl_identity"
    ]["leaves"]
    leaf_receipts = {
        name: {
            "path": str(leaves[name]),
            "sha256": sha256(leaves[name]),
            "expected_sha256": expected,
        }
        for name, expected in expected_leaves.items()
        if name in leaves
    }
    if (
        set(leaf_receipts) != set(expected_leaves)
        or any(
            receipt["sha256"] != receipt["expected_sha256"]
            for receipt in leaf_receipts.values()
        )
    ):
        raise ValidationError("current local RTL identity differs for signal stub")
    parsing_rows = "".join(
        f"printf '%s\\n' \"Parsing design file '{path.as_posix()}'\"\n"
        for path in leaves.values()
    )
    make_stub = stub_bin / "make"
    make_stub.write_text(
        "#!/usr/bin/env bash\n"
        "set -u\n"
        "run_dir=\n"
        "for argument in \"$@\"; do\n"
        "  case \"$argument\" in RUN_DIR=*) run_dir=\"${argument#RUN_DIR=}\";; esac\n"
        "done\n"
        "[ -n \"$run_dir\" ] || exit 84\n"
        "mkdir -p \"$run_dir/sim_results\"\n"
        + parsing_rows
        + "printf '%s\\n' COMPILE_SIGNAL_STUB_REACHED\n"
        + "cat >\"$run_dir/sim_results/simv\" <<'SAFE_SIM_STUB'\n"
        "#!/usr/bin/env bash\n"
        "set -u\n"
        "sim_log=\n"
        "observer_log=\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -l) shift; sim_log=\"$1\";;\n"
        "    +RETURN_OBS_FILE=*) observer_log=\"${1#*=}\";;\n"
        "  esac\n"
        "  shift\n"
        "done\n"
        "[ -n \"$sim_log\" ] || exit 82\n"
        "[ -n \"$observer_log\" ] || exit 83\n"
        "printf '%s\\n' \\\n"
        "  '[RETURN_OBSERVER] enabled N4PERF_FEATURE_ENABLE_V1 feature=NATIVE4_PROGRESS enabled=1' \\\n"
        "  >\"$sim_log\"\n"
        "printf '%s\\n' \\\n"
        "  '# Conv native four-lane progress observer v1' \\\n"
        "  'N4PERF_FEATURE_ENABLE_V1 feature=NATIVE4_PROGRESS enabled=1 heartbeat_cycles=262144 stall_window_cycles=1048576 expected_stages=1' \\\n"
        "  >\"$observer_log\"\n"
        "printf '%s\\n' SAFE_SIM_STUB_STARTED >\"$MOCK_SIM_STARTED\"\n"
        "trap 'exit 143' HUP INT TERM\n"
        "while :; do sleep 1; done\n"
        "SAFE_SIM_STUB\n"
        "chmod +x \"$run_dir/sim_results/simv\"\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    os.chmod(python_stub, 0o755)
    os.chmod(make_stub, 0o755)
    harness = (
        'export PATH="$1:/usr/bin:/bin:/c/Windows/System32"\n'
        'export MOCK_SIM_STARTED="$6"\n'
        'cd "$2"\n'
        'bash PREPARE_AND_RUN.sh "$3" >"$4" 2>"$5" &\n'
        'runner_pid=$!\n'
        'attempt=0\n'
        'while [ ! -f "$6" ] && [ "$attempt" -lt 1200 ]; do\n'
        '  sleep 0.05\n'
        '  attempt=$((attempt + 1))\n'
        'done\n'
        'if [ ! -f "$6" ]; then\n'
        '  kill -TERM "$runner_pid" 2>/dev/null\n'
        '  wait "$runner_pid" 2>/dev/null\n'
        '  printf "124\\n" >"$7"\n'
        '  exit 0\n'
        'fi\n'
        'kill -TERM "$runner_pid"\n'
        'wait "$runner_pid"\n'
        'printf "%s\\n" "$?" >"$7"\n'
        'exit 0\n'
    )
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    process = subprocess.run(
        [
            str(bash),
            "-c",
            harness,
            "native4-signal-stub",
            git_path(stub_bin),
            git_path(package),
            git_path(server),
            git_path(stdout_path),
            git_path(stderr_path),
            git_path(sim_started),
            git_path(status_path),
        ],
        cwd=package,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=300,
        check=False,
    )
    runner_status = (
        int(status_path.read_text(encoding="ascii").strip())
        if status_path.is_file()
        else None
    )
    runner_stdout = (
        stdout_path.read_text(encoding="utf-8", errors="replace")
        if stdout_path.is_file()
        else ""
    )
    runner_stderr = (
        stderr_path.read_text(encoding="utf-8", errors="replace")
        if stderr_path.is_file()
        else ""
    )
    return_zip = server / f"{INSTALL_NAME}_return.zip"
    return_sidecar = Path(str(return_zip) + ".sha256")
    return_checks: dict[str, Any] = {
        "zip_present": return_zip.is_file(),
        "sidecar_present": return_sidecar.is_file(),
    }
    signal_status = None
    result_status = None
    exact_declared_set = False
    declared_missing: list[str] = []
    undeclared_extra: list[str] = []
    required_control_present = False
    sidecar_exact = False
    if return_zip.is_file() and return_sidecar.is_file():
        return_digest = sha256(return_zip)
        sidecar_exact = (
            return_sidecar.read_text(encoding="ascii")
            == f"{return_digest}  {return_zip.name}\n"
        )
        with zipfile.ZipFile(return_zip) as archive:
            names = [
                name for name in archive.namelist() if not name.endswith("/")
            ]
            root_names = {PurePosixPath(name).parts[0] for name in names}
            if len(root_names) == 1:
                return_root = next(iter(root_names))

                def return_bytes(relative: str) -> bytes:
                    return archive.read(f"{return_root}/{relative}")

                allowlist = json.loads(return_bytes("RETURN_ALLOWLIST.json"))
                declared = {
                    str(record["path"]) for record in allowlist["records"]
                }
                actual = {
                    PurePosixPath(*PurePosixPath(name).parts[1:]).as_posix()
                    for name in names
                }
                expected_actual = declared | {
                    "RETURN_ALLOWLIST.json"
                }
                exact_declared_set = actual == expected_actual
                declared_missing = sorted(expected_actual - actual)
                undeclared_extra = sorted(actual - expected_actual)
                required_control = {
                    "RETURN_MANIFEST.json",
                    "evidence/package_preflight.json",
                    "evidence/install_preflight.json",
                    "evidence/compile_exit_status.txt",
                    "evidence/run_exit_status.txt",
                    "evidence/signal_status.txt",
                    "evidence/SERVER_RESULT_GATE.json",
                    "source_package/package_manifest.json",
                }
                required_control_present = required_control <= actual
                signal_status = return_bytes(
                    "evidence/signal_status.txt"
                ).decode("ascii").strip()
                result_status = json.loads(
                    return_bytes("evidence/SERVER_RESULT_GATE.json")
                ).get("status")
    return_checks.update(
        {
            "sidecar_exact": sidecar_exact,
            "exact_declared_set": exact_declared_set,
            "declared_missing": declared_missing,
            "undeclared_extra": undeclared_extra,
            "required_control_present": required_control_present,
            "signal_status": signal_status,
            "result_status": result_status,
        }
    )
    diagnostics = (
        "unbound variable",
        "syntax error",
        "command not found",
        "Traceback (most recent call last)",
    )
    valid = (
        process.returncode == 0
        and sim_started.is_file()
        and runner_status == 143
        and runner_stderr == ""
        and not any(token in runner_stdout for token in diagnostics)
        and all(
            return_checks[key]
            for key in (
                "zip_present",
                "sidecar_present",
                "sidecar_exact",
                "exact_declared_set",
                "required_control_present",
            )
        )
        and signal_status == "TERM"
        and result_status == "CONV_NATIVE_FOUR_LANE_SERVER_FAILURE"
    )
    return {
        "valid": valid,
        "harness_exit": process.returncode,
        "runner_exit": runner_status,
        "expected_signal_exit": 143,
        "safe_sim_stub_started": sim_started.is_file(),
        "runner_stdout_tail": runner_stdout[-1000:],
        "runner_stderr": runner_stderr,
        "harness_stdout_tail": process.stdout[-1000:],
        "harness_stderr_tail": process.stderr[-1000:],
        "current_local_leaf_receipts": leaf_receipts,
        "return": return_checks,
        "package_rtl_file_count": 0,
        "production_server_or_vcs_used": False,
    }


def validate(zip_path: Path, sidecar: Path) -> dict[str, Any]:
    digest = sha256(zip_path)
    entries, zip_errors = read_zip(zip_path)
    sidecar_valid = (
        sidecar.read_text(encoding="ascii")
        == f"{digest}  {zip_path.name}\n"
    )
    manifest = json.loads(entries.get("package_manifest.json", b"{}"))
    current_receipts: dict[str, Any] = {}
    for relative, expected in manifest.get("rule_receipts", {}).items():
        path = ROOT / Path(*PurePosixPath(relative).parts)
        observed = sha256(path) if path.is_file() else None
        current_receipts[relative] = {
            "expected_sha256": expected,
            "observed_sha256": observed,
            "current_match": observed == expected,
        }
    expected_files = manifest.get("files", {})
    actual_files = {
        path: {"size_bytes": len(payload), "sha256": sha256_bytes(payload)}
        for path, payload in entries.items()
        if path != "package_manifest.json"
    }
    exact_zip_set = expected_files == actual_files
    with tempfile.TemporaryDirectory(
        prefix=".n4a-",
        dir=ROOT,
        ignore_cleanup_errors=True,
    ) as name:
        root = Path(name)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(root)
        package = root / INSTALL_NAME
        before = package_records(package)
        preflight = run_python(
            package / RUNTIME_REL,
            ["preflight", "--package-root", str(package)],
            expected_zero=True,
        )
        sca = sca_closure(package, manifest)
        runner_text = (package / "PREPARE_AND_RUN.sh").read_text(
            encoding="utf-8"
        )
        runner = validate_runner(runner_text)
        observer = observer_scope(package, manifest)
        rtl_entries = [
            path
            for path in entries
            if Path(path).suffix.lower() in RTL_SUFFIXES
            and path != OBSERVER_REL.as_posix()
        ]
        negatives = negative_controls(package)
        after_negatives = package_records(package)
        runner_control = runner_compile_stub(package, root)
        after_runner = package_records(package)
        signal_control = runner_signal_stub(package, root)
        after_signal = package_records(package)
        package_immutable = (
            before == after_negatives == after_runner == after_signal
        )
    checks = {
        "zip_crc_path_root_no_symlink": not zip_errors,
        "sidecar_exact": sidecar_valid,
        "manifest_exact_set_hashes": exact_zip_set,
        "candidate_identity": (
            manifest.get("status") == "PACKAGE_READY_NOT_RUN"
            and manifest.get("candidate_release") is False
            and manifest.get("candidate_class")
            == "PERFORMANCE_DIAGNOSTIC_CANDIDATE"
            and manifest.get("evidence_level") == "E2_LOCAL_ONLY"
        ),
        "current_rule_receipts": (
            bool(current_receipts)
            and all(
                record["current_match"]
                for record in current_receipts.values()
            )
        ),
        "run_and_formal_counts": (
            manifest.get("simulation_run_count") == 27
            and manifest.get("formal_readback_count") == 320
            and len(manifest.get("readback_checks", [])) == 320
        ),
        "no_functional_rtl": (
            not rtl_entries
            and manifest.get("functional_rtl_file_count") == 0
            and manifest.get("server_rtl_entries") == 0
        ),
        "runtime_preflight": preflight["returncode"] == 0,
        "sca_execplan_consumer_closure": sca["valid"],
        "runner_four_way_binding": runner["valid"],
        "observer_focused_hdl_scope": observer["valid"],
        "runner_compile_stub_and_failure_return": runner_control["valid"],
        "runner_signal_stub_and_partial_return": signal_control["valid"],
        "negative_controls_fail_closed": all(
            (
                item.get("returncode", 1) != 0
                if "returncode" in item
                else item.get("valid") is False
            )
            for key, item in negatives.items()
            if key
            in {
                "exact_set_extra_file",
                "observer_source_deleted",
                "preloaded_formal_D",
                "observer_sha",
                "runner_delete_compile_incdir",
                "runner_delete_compile_macro",
                "runner_delete_return_target",
                "production_identity_missing_leaf",
                "natural_terminal_missing",
            }
        ),
        "positive_identity_and_terminal_controls": (
            negatives["production_identity_positive"]["returncode"] == 0
            and negatives["natural_terminal_positive"]["returncode"] == 0
        ),
        "extracted_package_immutable": package_immutable,
    }
    errors = [
        f"final self-audit check failed: {name}"
        for name, passed in checks.items()
        if not passed
    ]
    return {
        "schema": "conv-native-four-lane-df23e4d-final-zip-validation-v1",
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "status": (
            "PACKAGE_READY_NOT_RUN"
            if not errors
            else "PACKAGE_VALIDATION_FAILED"
        ),
        "errors": errors,
        "error_count": len(errors),
        "candidate_release": False,
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "sidecar_bytes": sidecar.stat().st_size,
        "sidecar_sha256": sha256(sidecar),
        "zip_errors": zip_errors,
        "package_file_count": len(entries),
        "checks": checks,
        "current_rule_receipts": current_receipts,
        "applicable_rule_ids": [
            "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
            "CDA-SERVER-WORKLOAD-PROVENANCE-001",
            "CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001",
            "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
            "CDA-SERVER-ONE-COMMAND-001",
            "CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001",
            "CDA-SERVER-USER-SUPPLIED-ROOT-NO-SOURCE-PREFLIGHT-001",
            "CDA-SCA-D-TB-READBACK-LENGTH-001",
            "CDA-SERVER-RUNTIME-READBACK-TARGET-ABSENT-001",
            "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
            "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
            "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
            "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
            "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001",
            "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
            "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
            "CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001",
            "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
            "CDA-SERVER-RETURN-RECEIPT-001",
            "CDA-SERVER-RETURN-MANIFEST-ALLOWLIST-001",
            "CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001",
        ],
        "sca_closure": sca,
        "runner_binding": runner,
        "observer_scope": observer,
        "package_local_hdl_gate": observer["package_local_hdl_gate"],
        "runner_compile_stub_control": runner_control,
        "runner_signal_stub_control": signal_control,
        "negative_controls": negatives,
        "functional_rtl_entries": rtl_entries,
        "server_action": False,
        "claim_boundary": (
            "exact source test ZIP, sidecar, package-local HDL focused scope, "
            "runner/finalizer controls, consumer closure and fail-closed "
            "package contracts only; production VCS, E3, E4, E5 and measured "
            "server performance remain open"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(args.zip.resolve(), args.sidecar.resolve())
        write_json(args.output.resolve(), result)
    except Exception as error:
        print(f"validation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PACKAGE_READY_NOT_RUN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
