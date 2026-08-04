from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import shlex
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import validate_qlinearadd_node0007_minimal_preflight_v11 as runner_validator
from tools import qlinearadd_node0007_fp32_ingress_canonical_v19 as canonical


INSTALL_NAME = "r5_qadd_n7_fp32_ingress_diag_v19"
SOURCE_NAME = "r5_qadd_n7_dbuf_colpair_v18"
PACKAGE_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
ZIP_PATH = PACKAGE_ROOT / f"{INSTALL_NAME}.zip"
SIDECAR_PATH = Path(str(ZIP_PATH) + ".sha256")
SOURCE_ZIP = PACKAGE_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = "570abd6f483f47f144ae9cb9320418e4acd423e2cf011e1f44a0f5b2537edd1a"
BUILD_RECEIPT = PACKAGE_ROOT / f"{INSTALL_NAME}.validation.json"
EVIDENCE_ROOT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-fp32-ingress-diag-v19"
)
REPORT_PATH = EVIDENCE_ROOT / "final_zip_self_audit.json"
INDEX_SHA256 = "f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8"
SERVER_RULE_SHA256 = "7a5383b7881b71043bb99d997c92524cb8c25df304179b53f364219fd7c1b141"
QADD_RULE_SHA256 = "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f"
TAIL_RULE_SHA256 = "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def payload_sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_zip(path: Path, expected_root: str) -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]:
    errors: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad = archive.testzip()
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if bad is not None:
            errors.append(f"CRC failure: {bad}")
        if len(names) != len(set(names)):
            errors.append("duplicate ZIP member")
        for info in infos:
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or not pure.parts
                or pure.parts[0] != expected_root
            ):
                errors.append(f"unsafe/root-mismatched member: {info.filename}")
            mode = info.external_attr >> 16
            if stat.S_ISLNK(mode):
                errors.append(f"symlink member: {info.filename}")
        members = {
            info.filename: archive.read(info)
            for info in infos
            if not info.is_dir()
        }
    manifest_name = f"{expected_root}/TEST_PACKAGE_MANIFEST.json"
    if manifest_name not in members:
        raise ValueError("manifest absent")
    manifest = json.loads(members[manifest_name])
    return members, manifest, {"errors": errors, "entry_count": len(members)}


def relative(members: dict[str, bytes], root: str) -> dict[str, bytes]:
    prefix = root + "/"
    return {name[len(prefix):]: value for name, value in members.items()}


def manifest_file_errors(files: dict[str, bytes], manifest: dict[str, Any]) -> list[str]:
    declared = manifest.get("files")
    if not isinstance(declared, dict):
        return ["manifest files map absent"]
    observed = {
        name: {"size_bytes": len(payload), "sha256": payload_sha256(payload)}
        for name, payload in files.items()
        if name != "TEST_PACKAGE_MANIFEST.json"
    }
    return [] if observed == declared else ["manifest file exact-set/size/SHA differs"]


def payload_equivalence(
    source_members: dict[str, bytes], successor_members: dict[str, bytes]
) -> dict[str, Any]:
    source = relative(source_members, SOURCE_NAME)
    successor = relative(successor_members, INSTALL_NAME)
    allowed_changed = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "TEST_PACKAGE_MANIFEST.json",
        "diagnostics/progress_contract.json",
        "package_tools/qlinearadd_progress_canonical_decision.py",
        "tb_probe/native_return_observer.svh",
        "workload/runtime/sca_cfg.json",
        "workload/runtime/sca_cfg_D.json",
    }
    added = {"tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"}
    errors: list[str] = []
    if set(successor) - set(source) != added:
        errors.append("successor added-file exact-set differs")
    if set(source) - set(successor):
        errors.append("source payload file removed")
    frozen = (set(source) & set(successor)) - allowed_changed
    for name in sorted(frozen):
        normalized = successor[name].replace(
            INSTALL_NAME.encode(), SOURCE_NAME.encode()
        )
        if normalized != source[name]:
            errors.append(f"frozen payload differs: {name}")
    for name in ("workload/runtime/sca_cfg.json", "workload/runtime/sca_cfg_D.json"):
        normalized = successor[name].replace(
            INSTALL_NAME.encode(), SOURCE_NAME.encode()
        )
        if normalized != source[name]:
            errors.append(f"namespace-only SCA payload differs: {name}")
    binary_frozen = [
        name
        for name in frozen
        if name.endswith((".bin", ".txt")) and "workload/runtime/install/" in name
    ]
    return {
        "valid": not errors,
        "errors": errors,
        "added_paths": sorted(added),
        "allowed_changed_paths": sorted(allowed_changed),
        "frozen_payload_count": len(frozen),
        "frozen_execplan_bitstream_golden_count": len(binary_frozen),
    }


def observer_contract(manifest: dict[str, Any], files: dict[str, bytes]) -> dict[str, Any]:
    runner = files["PREPARE_AND_RUN.sh"].decode()
    native = files["tb_probe/native_return_observer.svh"].decode()
    tail = files[
        "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"
    ].decode()
    parser_payload = files[
        "package_tools/qlinearadd_progress_canonical_decision.py"
    ]
    allow_targets = {
        item["target_path"] for item in manifest["return_allowlist"]
    }
    checks = {
        "package_local_incdir": "+incdir+$package_root/tb_probe" in runner,
        "enable_macro": "+define+NATIVE_RETURN_OBSERVER_ENABLE" in runner,
        "native_includes_tail": (
            '`include "qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"'
            in native
        ),
        "feature_plusarg_actual_argv": runner.count("+QADD_FP32_INGRESS_OBSERVER") >= 2,
        "time0_marker_source": "QADD_FP32_INGRESS_OBSERVER_V19_TIME0" in tail,
        "feature_receipt_finalizer": "fp32_ingress_feature_receipt.txt" in runner,
        "feature_receipt_allowlisted": (
            "evidence/fp32_ingress_feature_receipt.txt" in allow_targets
        ),
        "observer_log_allowlisted": "runs/return_observer.log" in allow_targets,
        "qualified_source_clock": "always @(posedge u_NDP_Top_new.clk_sg)" in tail,
        "surviving_snapshot_clock": "always @(posedge u_NDP_Top_new.clk_db)" in tail,
        "rate_limited": "qadd_ingress_snapshot_cycles %" in tail,
        "mse0_mse1_covered": "MSE_INST[0]" in tail and "MSE_INST[1]" in tail,
        "buffer0_buffer2_covered": (
            "QADD_INGRESS_BUF_ID =\n                        qadd_ingress_pair * 2"
            in tail
        ),
        "ga_dual_capture_and_accept": (
            "qadd_ingress_ga_capture[0]" in tail
            and "qadd_ingress_ga_capture[1]" in tail
            and "qadd_ingress_ga_consumer_accept" in tail
            and "qadd_ingress_ga_first_output" in tail
        ),
        "parser_hash_bound": (
            manifest["canonical_decision_contract"]["parser_sha256"]
            == payload_sha256(parser_payload)
        ),
        "ordered_stage_scope_declared": manifest["canonical_decision_contract"][
            "ordered_final_stage_scope"
        ]
        is True,
        "no_timeout_extension": "12h" in runner,
        "trap_safe_exit_and_signals": all(
            token in runner
            for token in (
                "trap 'finalize $?' EXIT",
                "trap 'signal_name=HUP;",
                "trap 'signal_name=INT;",
                "trap 'signal_name=TERM;",
                'final="$original"',
                'exit "$final"',
            )
        ),
    }
    return {"valid": all(checks.values()), "checks": checks}


def synthetic_line(
    *,
    stage: int,
    cycles: int,
    updates: dict[str, int] | None = None,
) -> str:
    values = {name: 0 for name in canonical.QUALIFIED}
    values.update(updates or {})
    fields = [
        "slice=0",
        f"stage_seq={stage}",
        f"snapshot_cycles={cycles}",
        *[f"{name}={values[name]}" for name in canonical.QUALIFIED],
        "buf_valid=0x0",
        "buf_arm_ready=0x3",
    ]
    return f"{cycles} | QADD_FP32_INGRESS | " + " ".join(fields)


def parser_controls() -> dict[str, Any]:
    marker = (
        "# Native NDP return observer v4\n"
        "# QADD_FP32_INGRESS_OBSERVER_V19 enabled=1 "
        "source_clock=clk_sg snapshot_clock=clk_db level_is_progress=0\n"
    )
    # An earlier completed stage followed by a final hanging stage must not
    # be reported as a natural terminal.
    ordered_payload = (
        marker
        + "1 | EXEC_START | x\n"
        + "2 | COMP_FINISH | x\n"
        + "3 | EXEC_START | x\n"
        + synthetic_line(stage=2, cycles=0)
        + "\n"
        + synthetic_line(stage=2, cycles=1_048_576)
        + "\n"
        + synthetic_line(stage=2, cycles=2_097_152)
        + "\n"
    ).encode()
    ordered = canonical.decide(
        ordered_payload,
        stall_window_cycles=1_048_576,
        minimum_progress_windows=3,
    )
    # Repeated MSE0-only events are qualified observations but not paired
    # progress and therefore cannot produce STILL_PROGRESSING.
    unpaired_payload = marker
    for index, value in enumerate((0, 1, 2, 3)):
        unpaired_payload += synthetic_line(
            stage=4,
            cycles=index * 1_048_576,
            updates={"mse0_req": value},
        ) + "\n"
    unpaired = canonical.decide(
        unpaired_payload.encode(),
        stall_window_cycles=1_048_576,
        minimum_progress_windows=3,
    )
    # Three windows with paired MSE0/MSE1 request progress are progress.
    paired_payload = marker
    for index, value in enumerate((0, 1, 2, 3)):
        paired_payload += synthetic_line(
            stage=4,
            cycles=index * 1_048_576,
            updates={"mse0_req": value, "mse1_req": value},
        ) + "\n"
    paired = canonical.decide(
        paired_payload.encode(),
        stall_window_cycles=1_048_576,
        minimum_progress_windows=3,
    )
    missing_marker = canonical.decide(
        synthetic_line(stage=1, cycles=0).encode(),
        stall_window_cycles=1_048_576,
        minimum_progress_windows=3,
    )
    incomplete = copy.deepcopy(ordered)
    incomplete.pop("reason")
    try:
        canonical.validate_record(incomplete)
        incomplete_failed = False
    except canonical.DecisionError:
        incomplete_failed = True
    checks = {
        "ordered_final_scope_not_earlier_finish": (
            ordered["decision"] != "NATURAL_TERMINAL_OBSERVED"
            and ordered["boundary"] == "MSE0_MSE1_REQUEST_ACCEPT"
        ),
        "individual_mse_progress_excluded": (
            unpaired["decision"] != "STILL_PROGRESSING_NOT_FINISHED"
        ),
        "paired_progress_accepted": (
            paired["decision"] == "STILL_PROGRESSING_NOT_FINISHED"
        ),
        "missing_marker_fails_closed": (
            missing_marker["decision"] == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE"
        ),
        "missing_reason_fails_closed": incomplete_failed,
    }
    return {
        "valid": all(checks.values()),
        "checks": checks,
        "ordered_decision": ordered["decision"],
        "unpaired_decision": unpaired["decision"],
        "paired_decision": paired["decision"],
        "negative_controls": {
            name: {"failed_closed": passed, "exit_code": 1 if passed else 0}
            for name, passed in checks.items()
            if name
            in {
                "ordered_final_scope_not_earlier_finish",
                "individual_mse_progress_excluded",
                "missing_marker_fails_closed",
                "missing_reason_fails_closed",
            }
        },
    }


def source_negative_controls(
    manifest: dict[str, Any], files: dict[str, bytes]
) -> dict[str, Any]:
    cases: dict[str, dict[str, bytes]] = {}
    for name, path, needle in (
        ("delete_source_include", "tb_probe/native_return_observer.svh", b'`include "qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh"'),
        ("delete_incdir", "PREPARE_AND_RUN.sh", b"+incdir+$package_root/tb_probe"),
        ("delete_macro", "PREPARE_AND_RUN.sh", b"+define+NATIVE_RETURN_OBSERVER_ENABLE"),
        ("delete_feature_plusarg", "PREPARE_AND_RUN.sh", b"+QADD_FP32_INGRESS_OBSERVER"),
        ("delete_time0_marker", "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh", b"QADD_FP32_INGRESS_OBSERVER_V19_TIME0"),
        ("delete_return_receipt", "PREPARE_AND_RUN.sh", b"fp32_ingress_feature_receipt.txt"),
        ("delete_stage_event", "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh", b"qadd_ingress_ga_consumer_accept"),
    ):
        mutated = dict(files)
        mutated[path] = mutated[path].replace(needle, b"")
        cases[name] = mutated
    results = {}
    for name, mutated in cases.items():
        valid = observer_contract(manifest, mutated)["valid"]
        results[name] = {
            "failed_closed": not valid,
            "exit_code": 1 if not valid else 0,
        }
    return results


def runner_controls() -> dict[str, Any]:
    runner_validator.INSTALL_NAME = INSTALL_NAME
    runner_validator.ZIP_PATH = ZIP_PATH
    runner_validator.SIDECAR_PATH = SIDECAR_PATH
    runner_validator.BUILD_RECEIPT = BUILD_RECEIPT
    runner_validator.REPORT_PATH = REPORT_PATH
    return runner_validator._runner_controls()


def _write_sim_stubs(
    tools: Path, marker: Path, *, wait_for_signal: bool
) -> None:
    tools.mkdir(parents=True)
    python = tools / "python3"
    python.write_text(
        "#!/usr/bin/env bash\n"
        f"exec {shlex.quote(runner_validator._to_bash(Path(sys.executable)))} \"$@\"\n",
        encoding="utf-8",
        newline="\n",
    )
    sim_template = tools / "simv_template"
    runner_pid_file = tools / "runner_pid"
    wait_body = (
        f"while [ ! -s {shlex.quote(runner_validator._to_bash(runner_pid_file))} ]; do sleep 0.1; done\n"
        f"kill -TERM \"$(cat {shlex.quote(runner_validator._to_bash(runner_pid_file))})\"\n"
        "sleep 30\n"
        if wait_for_signal
        else "exit 125\n"
    )
    sim_template.write_text(
        "#!/usr/bin/env bash\n"
        "log=''\nobs=''\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  case \"$1\" in\n"
        "    -l) shift; log=\"$1\" ;;\n"
        "    +RETURN_OBS_FILE=*) obs=\"${1#*=}\" ;;\n"
        "  esac\n"
        "  shift\n"
        "done\n"
        "mkdir -p \"$(dirname \"$log\")\" \"$(dirname \"$obs\")\"\n"
        "printf '# QADD_FP32_INGRESS_OBSERVER_V19_TIME0 enabled=1 source_clock=clk_sg snapshot_clock=clk_db\\n' >\"$log\"\n"
        "printf '# Native NDP return observer v4\\n# QADD_FP32_INGRESS_OBSERVER_V19 enabled=1 source_clock=clk_sg snapshot_clock=clk_db level_is_progress=0\\n' >\"$obs\"\n"
        "printf '1 | EXEC_START | slice=0 active_cycles=0 gexec=1 gconfig=1 req=0 rdata=0 wdata=0 buf4_wr=0 buf4_rd=0 buf5_wr=0 buf5_rd=0\\n' >>\"$obs\"\n"
        "printf '2 | QADD_FP32_INGRESS | slice=0 stage_seq=4 snapshot_cycles=0 mse0_req=1 mse1_req=1 mse0_rdata=1 mse1_rdata=1 mse0_buf=1 mse1_buf=1 buf0_wr=1 buf2_wr=1 buf0_arm_req=1 buf2_arm_req=1 buf0_array=1 buf2_array=1 ga0_capture=1 ga1_capture=1 ga_pair=1 ga_accept=0 ga_output=0 buf_valid=0x3 buf_arm_ready=0x3\\n' >>\"$obs\"\n"
        "printf '3 | QADD_FP32_INGRESS | slice=0 stage_seq=4 snapshot_cycles=1048576 mse0_req=1 mse1_req=1 mse0_rdata=1 mse1_rdata=1 mse0_buf=1 mse1_buf=1 buf0_wr=1 buf2_wr=1 buf0_arm_req=1 buf2_arm_req=1 buf0_array=1 buf2_array=1 ga0_capture=1 ga1_capture=1 ga_pair=1 ga_accept=0 ga_output=0 buf_valid=0x3 buf_arm_ready=0x3\\n' >>\"$obs\"\n"
        f"printf started > {shlex.quote(runner_validator._to_bash(marker))}\n"
        + wait_body,
        encoding="utf-8",
        newline="\n",
    )
    make = tools / "make"
    make.write_text(
        "#!/usr/bin/env bash\n"
        "run_dir=''\n"
        "for arg in \"$@\"; do case \"$arg\" in RUN_DIR=*) run_dir=\"${arg#*=}\";; esac; done\n"
        "[ -n \"$run_dir\" ] || exit 91\n"
        "mkdir -p \"$run_dir/sim_results\"\n"
        f"cp {shlex.quote(runner_validator._to_bash(sim_template))} \"$run_dir/sim_results/simv\"\n"
        "chmod +x \"$run_dir/sim_results/simv\"\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    mkdir = tools / "mkdir"
    mkdir.write_text(
        "#!/usr/bin/env bash\n"
        "args=()\n"
        "for arg in \"$@\"; do [ \"$arg\" = \"-p\" ] || args+=(\"$arg\"); done\n"
        "exec python3 -c 'import os,sys; [os.makedirs(p, exist_ok=True) for p in sys.argv[1:]]' \"${args[@]}\"\n",
        encoding="utf-8",
        newline="\n",
    )
    for path in (python, sim_template, make, mkdir):
        path.chmod(0o755)


def _run_stubbed_runner(
    package: Path,
    server: Path,
    tools: Path,
    *,
    signal_after_start: bool,
) -> subprocess.CompletedProcess[str]:
    package_bash = shlex.quote(runner_validator._to_bash(package))
    server_bash = shlex.quote(runner_validator._to_bash(server))
    tools_bash = shlex.quote(runner_validator._to_bash(tools))
    marker_bash = shlex.quote(runner_validator._to_bash(tools / "sim_started"))
    if signal_after_start:
        runner_pid_file = shlex.quote(
            runner_validator._to_bash(tools / "runner_pid")
        )
        body = (
            f"cd {package_bash}; PATH={tools_bash}:/usr/bin:/bin "
            f"bash PREPARE_AND_RUN.sh {server_bash} & runner_pid=$!; "
            f"printf '%s\\n' \"$runner_pid\" > {runner_pid_file}; "
            "wait \"$runner_pid\""
        )
    else:
        body = (
            f"cd {package_bash}; PATH={tools_bash}:/usr/bin:/bin "
            f"bash PREPARE_AND_RUN.sh {server_bash}"
        )
    return subprocess.run(
        [
            str(runner_validator._git_bash()),
            "--noprofile",
            "--norc",
            "-c",
            body,
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=180,
        check=False,
    )


def exit_and_signal_finalizer_controls() -> dict[str, Any]:
    results: dict[str, Any] = {}
    for name, signal_case in (("exit", False), ("signal_term", True)):
        with tempfile.TemporaryDirectory(
            prefix=f".q19-{name}-", dir=ROOT
        ) as raw:
            temp = Path(raw)
            package = runner_validator._extract(ZIP_PATH, temp / "extract")
            server = temp / "server"
            server.mkdir()
            tools = temp / "tools"
            marker = tools / "sim_started"
            _write_sim_stubs(tools, marker, wait_for_signal=signal_case)
            result = _run_stubbed_runner(
                package,
                server,
                tools,
                signal_after_start=signal_case,
            )
            evidence = server / f"evidence_{INSTALL_NAME}"
            return_zip = server / f"{INSTALL_NAME}_return.zip"
            feature = evidence / "fp32_ingress_feature_receipt.txt"
            canonical_path = evidence / "CANONICAL_PROGRESS_DECISION.json"
            signal_status = evidence / "signal_status.txt"
            feature_text = (
                feature.read_text(encoding="utf-8")
                if feature.is_file()
                else ""
            )
            signal_text = (
                signal_status.read_text(encoding="utf-8")
                if signal_status.is_file()
                else ""
            )
            expected_signal = "signal=TERM" if signal_case else "signal=NONE"
            passed = (
                marker.is_file()
                and return_zip.is_file()
                and canonical_path.is_file()
                and "argv_enabled=true" in feature_text
                and "time0_marker=true" in feature_text
                and "returned_snapshot_marker=true" in feature_text
                and expected_signal in signal_text
                and result.returncode in ({125, 143} if signal_case else {125})
            )
            results[name] = {
                "passed": passed,
                "runner_exit_code": result.returncode,
                "sim_stub_reached": marker.is_file(),
                "return_zip_collected": return_zip.is_file(),
                "canonical_decision_written": canonical_path.is_file(),
                "feature_receipt_complete": all(
                    token in feature_text
                    for token in (
                        "argv_enabled=true",
                        "time0_marker=true",
                        "returned_snapshot_marker=true",
                    )
                ),
                "signal_status": signal_text.strip(),
                "stderr_tail": result.stderr[-1000:],
            }
    results["all_passed"] = all(
        item["passed"] for key, item in results.items() if key != "all_passed"
    )
    return results


def validate_final_zip(*, write_report: bool = True) -> dict[str, Any]:
    successor_members, manifest, structure = load_zip(ZIP_PATH, INSTALL_NAME)
    source_members, _, source_structure = load_zip(SOURCE_ZIP, SOURCE_NAME)
    successor = relative(successor_members, INSTALL_NAME)
    files_errors = manifest_file_errors(successor, manifest)
    equivalence = payload_equivalence(source_members, successor_members)
    observer = observer_contract(manifest, successor)
    parser = parser_controls()
    negatives = source_negative_controls(manifest, successor)
    controls = runner_controls()
    finalizer_controls = exit_and_signal_finalizer_controls()
    sidecar_tokens = SIDECAR_PATH.read_text(encoding="ascii").split()
    receipts = manifest["final_zip_rule_self_audit"]["rule_receipts"]
    applicable = set(
        manifest["final_zip_rule_self_audit"]["applicable_server_rule_ids"]
    )
    runtime_d = [
        name
        for name in successor
        if re.fullmatch(
            r"workload/runtime/install/op_tail_round/slice\d{2}/"
            r"matrix_D_linearized_128bit\.txt",
            name,
        )
    ]
    checks = {
        "zip_structure_crc_root_path": not structure["errors"],
        "source_zip_structure": not source_structure["errors"],
        "sidecar_exact": (
            len(sidecar_tokens) == 2
            and sidecar_tokens[0] == sha256(ZIP_PATH)
            and sidecar_tokens[1] == ZIP_PATH.name
        ),
        "manifest_identity": manifest.get("install_name") == INSTALL_NAME,
        "manifest_file_exact_set": not files_errors,
        "source_v18_bound": (
            sha256(SOURCE_ZIP)
            == SOURCE_ZIP_SHA256
            == manifest["source_package"]["sha256"]
        ),
        "diagnostic_only": (
            manifest.get("package_class")
            == "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"
            and manifest.get("functional_fix") is False
        ),
        "payload_equivalence": equivalence["valid"],
        "runtime_formal_d_absent": not runtime_d,
        "observer_four_way_and_feature_binding": observer["valid"],
        "canonical_parser_controls": parser["valid"],
        "source_negative_controls": all(
            item["failed_closed"] for item in negatives.values()
        ),
        "current_index_receipt": (
            receipts["generation_index"]["sha256"] == INDEX_SHA256
            and receipts["generation_index"]["current_match"] is True
        ),
        "current_server_rule_receipt": (
            receipts["server_package_rule"]["sha256"]
            == SERVER_RULE_SHA256
            and receipts["server_package_rule"]["current_match"] is True
        ),
        "current_qadd_rule_receipt": (
            receipts["qlinearadd_rule"]["sha256"] == QADD_RULE_SHA256
            and receipts["qlinearadd_rule"]["current_match"] is True
        ),
        "current_tail_rule_receipt": (
            receipts["exact_uint8_tail_rule"]["sha256"] == TAIL_RULE_SHA256
            and receipts["exact_uint8_tail_rule"]["current_match"] is True
        ),
        "continuous_closure_rule_bound": (
            "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001"
            in applicable
        ),
        "default_diagnostics_rule_bound": (
            "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001" in applicable
        ),
        "diagnostic_feature_rule_bound": (
            "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001"
            in applicable
        ),
        "safe_compile_stub_positive": controls[
            "safe_compile_stub_positive_control"
        ]["passed"],
        "wrong_identity_precompile_negative": controls[
            "wrong_payload_identity_negative_control"
        ]["passed"],
        "safe_sim_stub_exit_finalizer_positive": finalizer_controls["exit"][
            "passed"
        ],
        "safe_signal_term_finalizer_positive": finalizer_controls[
            "signal_term"
        ]["passed"],
    }
    errors = [name for name, value in checks.items() if not value]
    errors.extend(structure["errors"])
    errors.extend(files_errors)
    errors.extend(equivalence["errors"])
    all_negatives = (
        all(item["failed_closed"] for item in negatives.values())
        and all(
            item["failed_closed"]
            for item in parser["negative_controls"].values()
        )
        and controls["wrong_payload_identity_negative_control"]["passed"]
    )
    if not all_negatives:
        errors.append("all_required_negative_controls_fail_closed")
    errors = list(dict.fromkeys(errors))
    report = {
        "schema": "qlinearadd-node0007-fp32-ingress-v19-final-zip-self-audit-v1",
        "status": (
            "PACKAGE_READY_NOT_RUN"
            if not errors
            else "PACKAGE_FINAL_RULE_SELF_AUDIT_FAILED"
        ),
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "error_count": len(errors),
        "checks": checks,
        "zip_structure": structure,
        "manifest_file_errors": files_errors,
        "payload_equivalence": equivalence,
        "observer_contract": observer,
        "canonical_parser_controls": parser,
        "negative_controls": negatives,
        "runner_control_flow": controls,
        "exit_and_signal_finalizer_controls": finalizer_controls,
        "all_required_negative_controls_fail_closed": all_negatives,
        "zip": ZIP_PATH.relative_to(ROOT).as_posix(),
        "zip_sha256": sha256(ZIP_PATH),
        "zip_bytes": ZIP_PATH.stat().st_size,
        "sidecar": SIDECAR_PATH.relative_to(ROOT).as_posix(),
        "sidecar_sha256": sha256(SIDECAR_PATH),
        "source_zip": SOURCE_ZIP.relative_to(ROOT).as_posix(),
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "server_command": "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX",
        "expected_return": f"{INSTALL_NAME}_return.zip",
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "configuration_changed": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    if write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        build = json.loads(BUILD_RECEIPT.read_text(encoding="utf-8"))
        build.update(
            {
                "status": report["status"],
                "FINAL_ZIP_RULE_SELF_AUDIT_PASS": report[
                    "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
                ],
                "final_self_audit_report": REPORT_PATH.relative_to(
                    ROOT
                ).as_posix(),
                "final_self_audit_report_sha256": sha256(REPORT_PATH),
            }
        )
        BUILD_RECEIPT.write_text(
            json.dumps(build, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return report


def main() -> int:
    report = validate_final_zip()
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
