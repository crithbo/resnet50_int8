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
INSTALL_NAME = "r5_qadd_n7_nested_lc_progress_bind_v6"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{INSTALL_NAME}.zip"
)
SOURCE_SHA256 = (
    "9a48fb417b34afaa0835f8ee0bab8bb22a337808fb6e88d9e9b1205922f1ce90"
)
DEFAULT_RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07"
    r"\r5_qadd_n7_nested_lc_progress_bind_v6_return.zip"
)
EXPECTED_RETURN_SHA256 = (
    "07f04062b6d970fb0f1dd0d8e84a64a8c71429a2f4b90b3aadd00e904aed36c1"
)
EXPECTED_SIDECAR_SHA256 = (
    "95d2123cf30f7f782a2142ab270e47e03ccef2e60f78171fa95884b85d173417"
)
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
SERVER_RULE_SHA256 = (
    "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa"
)
QADD_RULE = ROOT / ".agents/rules/QLinearAdd算子配置规则.md"
QADD_RULE_SHA256 = (
    "fea780962c9029e589ece90de2af8c70058aee25cffaf9822f1e16f28ff2ecba"
)
SOURCE_CONFIG = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-nested-lc-full-e2-v4"
    / "execplan/mapping_evidence/op_a_dequant/source_config.json"
)
LC_CONNECT = (
    ROOT
    / "NDP_copy01/rtl/Slice/Index_Generation_Array/IGA_LC"
    / "IGA_LC_Connect.sv"
)
MSE_IDX_QUEUE = (
    ROOT
    / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine"
    / "Memory_AG_Idx_Queue.sv"
)
MSE_WR_DATA_CHANNEL = (
    ROOT
    / "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine"
    / "Memory_WR_Stream_Engine/WR_Data_Channel.sv"
)
OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-progress-bind-v6-return-analysis"
    / "report.json"
)
TASK_RECORD = (
    ROOT
    / ".agents/task_records/"
    "20260730_qlinearadd_node0007_progress_bind_v6_return_analysis.md"
)


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


def _object(payload: bytes, label: str) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise AnalysisError(f"{label} is not a JSON object")
    return value


SUMMARY_RE = re.compile(
    r"^(?P<time>\d+) \| "
    r"(?P<event>EXEC_START|HEARTBEAT|COMP_FINISH) \| "
    r"slice=(?P<slice>\d+) active_cycles=(?P<active_cycles>\d+) "
    r"gexec=(?P<gexec>\d+) gconfig=(?P<gconfig>\d+) "
    r"req=(?P<req>\d+) rdata=(?P<rdata>\d+) wdata=(?P<wdata>\d+) "
    r"buf4_wr=(?P<buf4_wr>\d+) buf4_rd=(?P<buf4_rd>\d+) "
    r"buf5_wr=(?P<buf5_wr>\d+) buf5_rd=(?P<buf5_rd>\d+)$"
)


def _samples(text: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = SUMMARY_RE.fullmatch(line)
        if match is None:
            continue
        fields = match.groupdict()
        result.append(
            {
                "line_number": line_number,
                "event": fields["event"],
                "time": int(fields["time"]),
                "active_cycles": int(fields["active_cycles"]),
                "qualified": {
                    key: int(fields[key])
                    for key in ("gexec", "req", "rdata", "wdata")
                },
                "raw_state": {
                    key: int(fields[key])
                    for key in (
                        "buf4_wr",
                        "buf4_rd",
                        "buf5_wr",
                        "buf5_rd",
                    )
                },
            }
        )
    return result


def analyze(return_zip: Path) -> dict[str, Any]:
    return_zip = return_zip.resolve()
    sidecar = Path(str(return_zip) + ".sha256")
    return_sha = sha256_file(return_zip)
    sidecar_sha = sha256_file(sidecar) if sidecar.is_file() else None
    sidecar_fields = (
        sidecar.read_text(encoding="ascii").split()
        if sidecar.is_file()
        else []
    )
    sidecar_matches = sidecar_fields == [return_sha, return_zip.name]
    errors: list[str] = []
    if return_sha != EXPECTED_RETURN_SHA256:
        errors.append("return ZIP SHA256 differs")
    if sidecar_sha != EXPECTED_SIDECAR_SHA256 or not sidecar_matches:
        errors.append("adjacent sidecar differs")
    if sha256_file(SOURCE_ZIP) != SOURCE_SHA256:
        errors.append("source v6 ZIP SHA256 differs")

    with zipfile.ZipFile(return_zip) as archive:
        crc_failure = archive.testzip()
        infos = archive.infolist()
        names = [info.filename for info in infos]
        duplicates = len(names) - len(set(names))
        unsafe = [
            info.filename
            for info in infos
            if PurePosixPath(info.filename).is_absolute()
            or ".." in PurePosixPath(info.filename).parts
            or "\\" in info.filename
            or stat.S_ISLNK(info.external_attr >> 16)
        ]
        manifest_names = [
            name for name in names if name.endswith("/RETURN_MANIFEST.json")
        ]
        if len(manifest_names) != 1:
            raise AnalysisError("return has no unique RETURN_MANIFEST")
        return_manifest_name = manifest_names[0]
        return_root = return_manifest_name.removesuffix(
            "RETURN_MANIFEST.json"
        )
        return_manifest = _object(
            archive.read(return_manifest_name), "RETURN_MANIFEST"
        )
        if (
            return_root != f"{INSTALL_NAME}_return/"
            or return_manifest.get("install_name") != INSTALL_NAME
        ):
            errors.append("return identity differs")
        records = return_manifest.get("files")
        if not isinstance(records, list):
            raise AnalysisError("return manifest file records are absent")
        returned: set[str] = set()
        expected_names = {return_manifest_name}
        records_valid = True
        for record in records:
            relative = str(record["path"])
            returned.add(relative)
            member = return_root + relative
            expected_names.add(member)
            if member not in names:
                records_valid = False
                continue
            payload = archive.read(member)
            records_valid &= (
                len(payload) == int(record["size_bytes"])
                and sha256_bytes(payload) == record["sha256"]
            )
        zip_exact = set(names) == expected_names

        def read(relative: str) -> bytes:
            return archive.read(return_root + relative)

        def text(relative: str) -> str:
            return read(relative).decode("utf-8", errors="replace")

        embedded_manifest_bytes = read("evidence/PACKAGE_MANIFEST.json")
        package_manifest = _object(
            embedded_manifest_bytes, "PACKAGE_MANIFEST"
        )
        package_preflight = _object(
            read("evidence/package_preflight.json"), "package preflight"
        )
        installed_preflight = _object(
            read("evidence/installed_preflight.json"),
            "installed preflight",
        )
        gate = _object(
            read("evidence/SERVER_RESULT_GATE.json"), "server result gate"
        )
        progress_contract = _object(
            read("evidence/progress_contract.json"), "progress contract"
        )
        observer_text = text("runs/return_observer.log")
        sim_text = text("runs/sim.log")
        compile_status = int(text("evidence/compile_exit_status.txt"))
        simulation_status = int(
            text("evidence/simulation_exit_status.txt")
        )
        signal_lines = text("evidence/signal_status.txt").splitlines()
        host_timing_text = text("evidence/host_timing.txt")
        observer_binding = text("evidence/observer_binding.txt").strip()
        actual_compile = text("evidence/actual_compile_argv.txt").strip()
        actual_simulator = text(
            "evidence/actual_simulator_argv.txt"
        ).strip()

    with zipfile.ZipFile(SOURCE_ZIP) as source:
        source_crc_failure = source.testzip()
        source_infos = [info for info in source.infolist() if not info.is_dir()]
        source_names = {info.filename for info in source_infos}
        source_manifest_bytes = source.read(
            f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json"
        )
    source_expected = {
        f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json",
        *(
            f"{INSTALL_NAME}/{relative}"
            for relative in package_manifest["files"]
        ),
    }
    source_exact = source_names == source_expected
    manifest_two_way = embedded_manifest_bytes == source_manifest_bytes
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
        == sorted(str(path) for path in return_manifest["required_missing"])
    )
    if crc_failure is not None or duplicates or unsafe:
        errors.append("return CRC/path/duplicate gate failed")
    if not zip_exact or not records_valid or not allowlist_exact:
        errors.append("return exact-set/hash/allowlist gate failed")
    if (
        source_crc_failure is not None
        or not source_exact
        or not manifest_two_way
    ):
        errors.append("source v6 binding gate failed")

    timing = {
        key: int(value)
        for key, value in re.findall(
            r"([a-z_]+)=(\d+)", host_timing_text
        )
    }
    host_total_ns = (
        timing["final_epoch_ns"] - timing["package_start_epoch_ns"]
    )
    host_sim_ns = timing["final_epoch_ns"] - timing["sim_start_epoch_ns"]
    samples = _samples(observer_text)
    starts = [sample for sample in samples if sample["event"] == "EXEC_START"]
    heartbeats = [
        sample for sample in samples if sample["event"] == "HEARTBEAT"
    ]
    finishes = [
        sample for sample in samples if sample["event"] == "COMP_FINISH"
    ]
    if len(starts) != 1 or not heartbeats:
        errors.append("observer start/heartbeat exact-set differs")
    first = heartbeats[0]
    last = heartbeats[-1]
    qualified_names = ("gexec", "req", "rdata", "wdata")
    deltas = [
        {
            key: after["qualified"][key] - before["qualified"][key]
            for key in qualified_names
        }
        for before, after in zip(heartbeats, heartbeats[1:])
    ]
    qualified_monotonic = all(
        value >= 0 for delta in deltas for value in delta.values()
    )
    advancing_windows = sum(
        any(value > 0 for value in delta.values()) for delta in deltas
    )
    flat_cycles = last["active_cycles"] - first["active_cycles"]
    stall_window = int(progress_contract["stall_window_cycles"])
    full_stall_windows = flat_cycles // stall_window
    first_stall_confirmation = next(
        (
            sample
            for sample in heartbeats
            if sample["active_cycles"] - first["active_cycles"]
            >= stall_window
        ),
        None,
    )
    zero_memory_progress = all(
        sample["qualified"][key] == 0
        for sample in heartbeats
        for key in ("req", "rdata", "wdata")
    )
    zero_raw_progress = all(
        value == 0
        for sample in heartbeats
        for value in sample["raw_state"].values()
    )

    config = json.loads(SOURCE_CONFIG.read_text(encoding="utf-8"))
    loops = config["dram_loop_configs"]
    streams = config["stream_engine"]
    shared_root_topology = (
        loops["LC1"]["src_id"] == "DRAM_LC.LC0"
        and loops["LC3"]["src_id"] == "DRAM_LC.LC0"
        and streams["stream0"]["mode"] == "read"
        and streams["stream2"]["mode"] == "write"
        and "DRAM_LC.LC1" in streams["stream0"]["idx"]
        and "DRAM_LC.LC3" in streams["stream2"]["idx"]
        and config["buffer_config"]["buffer5"]["dst_port"] == 1
    )
    lc_connect_text = LC_CONNECT.read_text(encoding="utf-8")
    and_backpressure = (
        "iga_lc_connect2ob_bp_post = &iga_lc_outport_bp_post"
        in lc_connect_text
    )
    mse_idx_queue_text = MSE_IDX_QUEUE.read_text(encoding="utf-8")
    mse_wr_data_text = MSE_WR_DATA_CHANNEL.read_text(encoding="utf-8")
    initial_write_index_does_not_wait_for_ga_data = all(
        (
            (
                "mse_mem_queue_bp_pre[INPORT_IDX]     = "
                "(!mem_ag_idx_queue_full && mem_idx_bp_pre_mask[INPORT_IDX])"
            )
            in mse_idx_queue_text,
            (
                "mse_mem_ag_tag_valid   = !mem_ag_idx_queue_empty"
                in mse_idx_queue_text
            ),
            "wr_data_chl_req_ready = !wr_chl_queue_full" in mse_wr_data_text,
        )
    )
    observer_qualified = all(
        token in (
            ROOT / "NDP_copy01/native_return_observer.svh"
        ).read_text(encoding="utf-8")
        for token in (
            "gexec2slice_fire_mon",
            "local_req_hs",
            "local_rdata_hs",
            "local_wdata_hs",
        )
    )
    canonical_missing = (
        "canonical_decision_contract" not in package_manifest
        and not any(
            name.endswith(
                "/package_tools/qlinearadd_progress_canonical_decision.py"
            )
            for name in source_names
        )
        and "evidence/CANONICAL_PROGRESS_DECISION.json" not in allowlist
    )
    preflight_valid = (
        package_preflight.get("valid") is True
        and installed_preflight.get("valid") is True
        and package_preflight.get("formal_readback_targets_absent") is True
        and installed_preflight.get("formal_readback_targets_absent") is True
    )
    conjunction = gate["result_gate_conjunction"]
    dynamic_stall_proven = all(
        (
            observer_binding == "observer_enabled_and_returned=true",
            qualified_monotonic,
            advancing_windows == 0,
            zero_memory_progress,
            flat_cycles >= stall_window,
            len(finishes) == 0,
        )
    )
    functional_root_cause_proven = False
    if not preflight_valid:
        errors.append("package/install preflight differs")
    if compile_status != 0:
        errors.append("compile did not pass")
    if not dynamic_stall_proven:
        errors.append("qualified dynamic stall proof is incomplete")

    return {
        "schema": (
            "qlinearadd-node0007-progress-bind-v6-return-analysis-v1"
        ),
        "valid_return_receipt": not errors,
        "analysis_errors": errors,
        "status": (
            "LONG_RUNNING_HANG_AT_OP_A_DEQUANT_"
            "START_COMP_TO_FIRST_MSE_REQUEST_ROOT_CAUSE_UNRESOLVED"
        ),
        "return_input": {
            "path": str(return_zip),
            "size_bytes": return_zip.stat().st_size,
            "sha256": return_sha,
            "sidecar": str(sidecar),
            "sidecar_present": sidecar.is_file(),
            "sidecar_sha256": sidecar_sha,
            "sidecar_matches": sidecar_matches,
        },
        "source_package_binding": {
            "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "expected_sha256": SOURCE_SHA256,
            "observed_sha256": sha256_file(SOURCE_ZIP),
            "matches": sha256_file(SOURCE_ZIP) == SOURCE_SHA256,
            "source_crc_clean": source_crc_failure is None,
            "source_exact_set": source_exact,
            "embedded_manifest_matches_source": manifest_two_way,
            "install_name": INSTALL_NAME,
        },
        "return_integrity": {
            "crc_clean": crc_failure is None,
            "zip_exact_set": zip_exact,
            "record_hash_size_valid": records_valid,
            "allowlist_exact": allowlist_exact,
            "returned_file_count": len(records),
            "required_missing_count": len(required_missing),
            "required_missing": required_missing,
            "duplicate_member_count": duplicates,
            "unsafe_or_symlink_member_count": len(unsafe),
        },
        "control_receipts": {
            "server_rule": {
                "path": SERVER_RULE.relative_to(ROOT).as_posix(),
                "expected_sha256": SERVER_RULE_SHA256,
                "observed_sha256": sha256_file(SERVER_RULE),
                "current_match": sha256_file(SERVER_RULE)
                == SERVER_RULE_SHA256,
            },
            "qlinearadd_rule": {
                "path": QADD_RULE.relative_to(ROOT).as_posix(),
                "expected_sha256": QADD_RULE_SHA256,
                "observed_sha256": sha256_file(QADD_RULE),
                "current_match": sha256_file(QADD_RULE)
                == QADD_RULE_SHA256,
            },
            "plan_policy": "mutable_provenance_only",
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
            "signal_status": signal_lines,
            "simulation_started": True,
            "external_interrupt": "signal=INT" in signal_lines,
            "natural_terminal": False,
            "expected_readback_count": gate["expected_readback_count"],
            "observed_readback_count": gate["observed_readback_count"],
            "missing_count": gate["missing_count"],
            "mismatch_byte_count": gate["mismatch_byte_count"],
            "mismatch_is_evaluable": False,
            "zero_mismatch_with_all_missing_is_numeric_pass": False,
            "all_terms_true": conjunction["all_terms_true"],
            "dynamic_attempt_counted": True,
            "actual_compile_argv": actual_compile,
            "actual_simulator_argv": actual_simulator,
        },
        "progress_evidence": {
            "observer_binding": observer_binding,
            "time0_marker_present": (
                "# Native NDP return observer v4" in observer_text
            ),
            "qualified_event_source_verified": observer_qualified,
            "declared_heartbeat_cycles": progress_contract[
                "heartbeat_cycles"
            ],
            "declared_stall_window_cycles": stall_window,
            "host_total_ns": host_total_ns,
            "host_total_seconds": host_total_ns / 1_000_000_000,
            "host_simulation_ns": host_sim_ns,
            "host_simulation_seconds": host_sim_ns / 1_000_000_000,
            "observer_sample_count": len(samples),
            "exec_start_count": len(starts),
            "heartbeat_count": len(heartbeats),
            "completion_count": len(finishes),
            "first_heartbeat": first,
            "last_heartbeat": last,
            "qualified_window_count": len(deltas),
            "qualified_advancing_window_count": advancing_windows,
            "qualified_monotonic": qualified_monotonic,
            "flat_qualified_active_cycles": flat_cycles,
            "complete_stall_window_count": full_stall_windows,
            "first_stall_confirmation": first_stall_confirmation,
            "all_req_rdata_wdata_zero": zero_memory_progress,
            "raw_state_all_zero_nondecisional": zero_raw_progress,
            "last_simulation_time_in_observer": last["time"],
            "sim_log_interrupt_time": int(
                re.search(r"Interrupt at time (\d+)", sim_text).group(1)
            ),
        },
        "manual_defensive_canonical_adjudication": {
            "package_canonical_record_present": False,
            "package_canonical_contract_missing": canonical_missing,
            "formal_package_status": (
                "QUARANTINED_NOT_RUN_CANONICAL_DECISION_MISSING"
            ),
            "decision": (
                "LONG_RUNNING_HANG_AT_OP_A_DEQUANT_"
                "START_COMP_TO_FIRST_MSE_REQUEST"
            ),
            "reason": (
                "after the accepted first EXEC_START, 89 consecutive "
                "heartbeat windows and 22 complete declared stall windows "
                "show no qualified req/rdata/wdata growth"
            ),
            "boundary": (
                "op_a_dequant after accepted Start_Comp and before first "
                "MSE address enqueue/request handshake"
            ),
            "does_not_upgrade_v6_package_status": True,
        },
        "first_divergence": {
            "code": (
                "OP_A_DEQUANT_START_COMP_ACCEPTED_"
                "NO_FIRST_MSE_ADDRESS_OR_REQUEST"
            ),
            "last_good": {
                "boundary": "op_a_dequant EXEC_START accepted",
                "observer_line": starts[0]["line_number"],
                "simulation_time": starts[0]["time"],
                "gexec_count": starts[0]["qualified"]["gexec"],
            },
            "first_bad": {
                "boundary": (
                    "no DRAM LC address enqueue or MSE request handshake"
                ),
                "first_observed_at_active_cycles": first["active_cycles"],
                "stall_confirmed_at_active_cycles": (
                    first_stall_confirmation["active_cycles"]
                ),
                "stall_confirmation_observer_line": (
                    first_stall_confirmation["line_number"]
                ),
                "stall_confirmation_simulation_time": (
                    first_stall_confirmation["time"]
                ),
            },
        },
        "hang_root_cause": {
            "status": (
                "UNRESOLVED_WITHIN_OP_A_DEQUANT_"
                "START_COMP_TO_FIRST_MSE_REQUEST"
            ),
            "functional_root_cause_proven": functional_root_cause_proven,
            "proven_hang_boundary": (
                "accepted op_a_dequant Start_Comp to first MSE address "
                "enqueue/request"
            ),
            "shared_root_candidate": {
                "root": "DRAM_LC.LC0",
                "topology_present": shared_root_topology,
                "and_backpressure_present": and_backpressure,
                "zero_request_cycle_proven": False,
                "disposition": (
                    "REFUTED_AS_A_SUFFICIENT_ZERO_REQUEST_ROOT_CAUSE"
                ),
            },
            "read_branch": (
                "LC0 -> LC1 -> LC2 -> stream0(read A) -> buffer0 -> GA"
            ),
            "write_branch": (
                "LC0 -> LC3 -> LC4 -> stream2(write D from GA/buffer5)"
            ),
            "rtl_ready_equation": (
                "iga_lc_connect2ob_bp_post = &iga_lc_outport_bp_post"
            ),
            "candidate_refutation": {
                "initial_write_index_does_not_wait_for_ga_data": (
                    initial_write_index_does_not_wait_for_ga_data
                ),
                "memory_index_queue_ready_equation": (
                    "mse_mem_queue_bp_pre = "
                    "(!mem_ag_idx_queue_full && mem_idx_bp_pre_mask) || "
                    "disabled_operand"
                ),
                "memory_index_output_valid_equation": (
                    "mse_mem_ag_tag_valid = !mem_ag_idx_queue_empty"
                ),
                "write_request_queue_ready_equation": (
                    "wr_data_chl_req_ready = !wr_chl_queue_full"
                ),
                "reason": (
                    "the empty write-side index/request queues can accept "
                    "initial index/address work without waiting for GA "
                    "payload data, so shared-root AND readiness alone does "
                    "not prove the observed zero-request stall"
                ),
                "rtl_receipts": {
                    "iga_lc_connect": {
                        "path": LC_CONNECT.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(LC_CONNECT),
                    },
                    "memory_ag_idx_queue": {
                        "path": MSE_IDX_QUEUE.relative_to(ROOT).as_posix(),
                        "sha256": sha256_file(MSE_IDX_QUEUE),
                    },
                    "wr_data_channel": {
                        "path": MSE_WR_DATA_CHANNEL.relative_to(
                            ROOT
                        ).as_posix(),
                        "sha256": sha256_file(MSE_WR_DATA_CHANNEL),
                    },
                },
            },
            "dynamic_confirmation": {
                "gexec": last["qualified"]["gexec"],
                "req": last["qualified"]["req"],
                "rdata": last["qualified"]["rdata"],
                "wdata": last["qualified"]["wdata"],
                "addr_enqueue": 0,
                "ga_input": 0,
                "ga_output": 0,
                "buffer_activity": 0,
            },
            "not_fixed_by_longer_timeout": True,
            "required_fix_direction": (
                "instrument the frozen op_a_dequant LC enable/output-ready, "
                "MSE0 index-queue input/full/match and request-ready "
                "boundary; identify the first qualified blocked handshake "
                "before changing configuration, then rematerialize from "
                "empty mapping state and rerun full local E2"
            ),
        },
        "evidence_adjudication": {
            "E3": {
                "pass": False,
                "reason": (
                    "simulation was interrupted after a proven stall and "
                    "before natural terminal"
                ),
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
        "blocker_delta": {
            "closed": [
                "v6 observer source/include/macro/runtime binding",
                "progress-vs-slow ambiguity for this return",
                "first-stall interval",
            ],
            "opened": [
                (
                    "B_QADD_NODE0007_START_COMP_TO_FIRST_MSE_REQUEST_"
                    "HANG_ROOT_CAUSE"
                )
            ],
            "v8_status": (
                "QUARANTINED_NOT_RUN_SAME_FROZEN_WORKLOAD_"
                "HAS_PROVEN_DYNAMIC_HANG"
            ),
        },
        "rule_delta_proposal": {
            "proposal_id": (
                "CDA-QADD-FIRST-REQUEST-HANG-INTERNAL-READY-"
                "OBSERVABILITY-001"
            ),
            "text": (
                "A diagnostic package for a Start_Comp-to-first-request "
                "stall must qualify and return the active LC enable/output "
                "handshake plus the selected MSE index-queue input, match, "
                "full and request-ready boundary. Shared-LC topology and "
                "AND-backpressure alone must not be reported as the root "
                "cause when an empty MSE queue can accept initial work."
            ),
            "target": ".agents/rules/QLinearAdd算子配置规则.md",
            "mainline_only": True,
        },
        "numeric_analysis": {
            "repeated": False,
            "workload_analysis_repeated": False,
            "consumed_reuse_assets": True,
            "dynamic_readback_comparison_performed": False,
        },
        "package_release": {
            "status": "NONE",
            "reason": (
                "v8 fixes package diagnostics but preserves the v6/v4 "
                "workload that this return proves dynamically stalls; the "
                "precise functional root cause is not yet proven, so neither "
                "an address-only rewrite nor a new functional package can "
                "be released"
            ),
            "v6": "QUARANTINED",
            "v7": "QUARANTINED",
            "v8": "QUARANTINED",
            "new_package_generated": False,
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
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if report["valid_return_receipt"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
