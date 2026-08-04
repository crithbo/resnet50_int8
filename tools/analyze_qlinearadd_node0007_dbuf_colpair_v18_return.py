from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
RETURN_ROOT = "r5_qadd_n7_dbuf_colpair_v18_return"
SOURCE_ROOT = "r5_qadd_n7_dbuf_colpair_v18"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_dbuf_colpair_v18.zip"
)
SOURCE_ZIP_SHA256 = (
    "570abd6f483f47f144ae9cb9320418e4acd423e2cf011e1f44a0f5b2537edd1a"
)
SOURCE_ZIP_BYTES = 38_035_285
SOURCE_SIDECAR = SOURCE_ZIP.with_suffix(".zip.sha256")
SOURCE_FINAL_AUDIT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-d-buffer-column-pair-v18/"
    "final_zip_self_audit.json"
)
SOURCE_FINAL_AUDIT_SHA256 = (
    "9b562b6e0c11b696f1c0a53abff4fd9800ba8b010c3a79b5ec72e4e1b193ecaa"
)
RETURN_SHA256 = (
    "ee21c207e9e3244eaea4993ab0b05bc3907af6dbe633f904ad0a1088118cd7aa"
)
RETURN_BYTES = 278_142
STAGES = (
    "op_a_dequant",
    "op_b_dequant",
    "op_relocation_pad",
    "op_fp32_add",
    "op_tail_mul",
    "op_tail_round",
)
RULE_RECEIPTS = {
    "agent": (
        ROOT / ".agents/agent.md",
        "5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0",
        False,
    ),
    "plan": (
        ROOT / ".agents/plan.md",
        "07196fe91d362f6379681fe21bf7ef3a9a6a7661048dfe0284680d16c4529f68",
        True,
    ),
    "generation_index": (
        ROOT / ".agents/rules/生成前必读索引.md",
        "12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f",
        False,
    ),
    "server_package_rule": (
        ROOT / ".agents/rules/服务器测试包生成规则.md",
        "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025",
        False,
    ),
    "common_operator_rule": (
        ROOT / ".agents/rules/算子配置规则.md",
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171",
        False,
    ),
    "ndp_field_rule": (
        ROOT / ".agents/rules/NDP硬件字段语义.md",
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
        False,
    ),
    "qlinearadd_rule": (
        ROOT / ".agents/rules/QLinearAdd算子配置规则.md",
        "aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f",
        False,
    ),
    "exact_uint8_tail_rule": (
        ROOT / ".agents/rules/精确UINT8量化尾专项规则.md",
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e",
        False,
    ),
}


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


def read_zip(path: Path, expected_root: str) -> tuple[dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    member_count = 0
    with zipfile.ZipFile(path) as archive:
        bad_crc = archive.testzip()
        if bad_crc is not None:
            raise AnalysisError(f"ZIP CRC differs: {bad_crc}")
        prefix = f"{expected_root}/"
        for info in archive.infolist():
            member_count += 1
            pure = PurePosixPath(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or (mode and stat.S_ISLNK(mode))
            ):
                raise AnalysisError(f"unsafe ZIP member: {info.filename}")
            if info.is_dir():
                continue
            if not info.filename.startswith(prefix):
                raise AnalysisError(f"member outside bound root: {info.filename}")
            relative = info.filename[len(prefix) :]
            if not relative or relative in files:
                raise AnalysisError(f"empty/duplicate ZIP member: {info.filename}")
            files[relative] = archive.read(info)
    if roots != {expected_root}:
        raise AnalysisError(f"ZIP root exact-set differs: {sorted(roots)}")
    return files, {
        "crc_valid": True,
        "single_exact_root": True,
        "root": expected_root,
        "archive_member_count": member_count,
        "file_count": len(files),
        "duplicate_member_count": 0,
        "symlink_member_count": 0,
        "unsafe_path_count": 0,
    }


def extract_read_only(files: dict[str, bytes], output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for relative, payload in sorted(files.items()):
        target = output.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if not target.is_file() or target.read_bytes() != payload:
                raise AnalysisError(f"existing extraction differs: {target}")
        else:
            target.write_bytes(payload)
        records.append(
            {
                "path": relative,
                "size_bytes": len(payload),
                "sha256": sha256_bytes(payload),
            }
        )
    digest = sha256_bytes(
        json.dumps(records, sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    return {
        "path": str(output),
        "file_count": len(records),
        "tree_receipt_sha256": digest,
        "files": records,
    }


def json_payload(files: dict[str, bytes], path: str) -> dict[str, Any]:
    value = json.loads(files[path])
    if not isinstance(value, dict):
        raise AnalysisError(f"{path} is not a JSON object")
    return value


def kv(line: str) -> dict[str, str]:
    return dict(re.findall(r"\b([A-Za-z0-9_]+)=([^\s|]+)", line))


def int_value(value: str) -> int:
    return int(value, 0)


def epoch_map(payload: str) -> dict[str, int]:
    return {
        key.strip(): int(value.strip())
        for line in payload.splitlines()
        if "=" in line
        for key, value in [line.split("=", 1)]
    }


def parse_stages(observer_text: str) -> tuple[list[dict[str, Any]], Counter[str]]:
    stage_records: list[dict[str, Any]] = []
    event_counts: Counter[str] = Counter()
    active: dict[str, Any] | None = None
    for line_number, line in enumerate(observer_text.splitlines(), start=1):
        match = re.match(r"^(\d+) \| ([A-Z0-9_]+) \|(.*)$", line)
        if not match:
            continue
        timestamp = int(match.group(1))
        event = match.group(2)
        values = kv(match.group(3))
        event_counts[event] += 1
        if event == "EXEC_START":
            index = len(stage_records)
            active = {
                "stage_index": index + 1,
                "stage": STAGES[index] if index < len(STAGES) else f"unknown_{index}",
                "exec_start_ps": timestamp,
                "exec_start_line": line_number,
                "exec_start_snapshot": values,
                "comp_finish_ps": None,
                "comp_finish_line": None,
                "comp_finish_snapshot": None,
                "event_counts": Counter(),
                "heartbeats": [],
                "deep_counts": [],
                "sg_counts": [],
                "chains": [],
            }
            stage_records.append(active)
        if active is None:
            continue
        active["event_counts"][event] += 1
        item = {"ps": timestamp, "line": line_number, **values}
        if event == "COMP_FINISH":
            active["comp_finish_ps"] = timestamp
            active["comp_finish_line"] = line_number
            active["comp_finish_snapshot"] = values
        elif event == "HEARTBEAT":
            active["heartbeats"].append(item)
        elif event == "DEEP_COUNTS":
            active["deep_counts"].append(item)
        elif event == "SG_COUNTS":
            active["sg_counts"].append(item)
        elif event == "FIRST_REQUEST_CHAIN":
            active["chains"].append(item)

    summaries: list[dict[str, Any]] = []
    for record in stage_records:
        compact = {
            key: value
            for key, value in record.items()
            if key not in {"heartbeats", "deep_counts", "sg_counts", "chains"}
        }
        compact["event_counts"] = dict(record["event_counts"])
        for name in ("heartbeats", "deep_counts", "sg_counts", "chains"):
            values = record[name]
            compact[f"{name}_count"] = len(values)
            compact[f"{name}_first"] = values[0] if values else None
            compact[f"{name}_last"] = values[-1] if values else None
        summaries.append(compact)
    return summaries, event_counts


def verify_rule_receipts() -> dict[str, Any]:
    receipts: dict[str, Any] = {}
    for name, (path, expected, mutable) in RULE_RECEIPTS.items():
        actual = sha256_file(path)
        if actual != expected and not mutable:
            raise AnalysisError(
                f"immutable rule receipt differs: {path} {actual} != {expected}"
            )
        receipts[name] = {
            "path": str(path.relative_to(ROOT)),
            "expected_sha256": expected,
            "actual_sha256": actual,
            "current_match": actual == expected,
            "mutable_provenance_only": mutable,
        }
    return receipts


def analyze(return_zip: Path, extraction_root: Path) -> dict[str, Any]:
    receipts = verify_rule_receipts()
    if return_zip.stat().st_size != RETURN_BYTES:
        raise AnalysisError("return ZIP byte count differs")
    if sha256_file(return_zip) != RETURN_SHA256:
        raise AnalysisError("return ZIP SHA256 differs")
    if SOURCE_ZIP.stat().st_size != SOURCE_ZIP_BYTES:
        raise AnalysisError("source ZIP byte count differs")
    if sha256_file(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise AnalysisError("source ZIP SHA256 differs")
    if sha256_file(SOURCE_FINAL_AUDIT) != SOURCE_FINAL_AUDIT_SHA256:
        raise AnalysisError("source final audit SHA256 differs")
    sidecar_text = SOURCE_SIDECAR.read_text(encoding="utf-8").strip()
    if SOURCE_ZIP_SHA256 not in sidecar_text:
        raise AnalysisError("source sidecar does not declare source ZIP SHA256")

    returned, return_structure = read_zip(return_zip, RETURN_ROOT)
    source, source_structure = read_zip(SOURCE_ZIP, SOURCE_ROOT)
    extraction = extract_read_only(returned, extraction_root)

    return_manifest = json_payload(returned, "RETURN_MANIFEST.json")
    source_manifest = json_payload(source, "TEST_PACKAGE_MANIFEST.json")
    returned_package_manifest = json_payload(
        returned, "evidence/PACKAGE_MANIFEST.json"
    )
    declared = {item["path"]: item for item in return_manifest["files"]}
    returned_exact_set = set(returned) == set(declared) | {"RETURN_MANIFEST.json"}
    member_receipt_errors = [
        path
        for path, item in declared.items()
        if path not in returned
        or len(returned[path]) != int(item["size_bytes"])
        or sha256_bytes(returned[path]) != item["sha256"]
    ]
    allowlist = {
        item["target_path"]: item for item in source_manifest["return_allowlist"]
    }
    unexpected_targets = sorted(set(declared) - set(allowlist))
    required_paths = {
        path for path, item in allowlist.items() if item.get("required") is True
    }
    missing_required = sorted(required_paths - set(declared))
    declared_required_missing = sorted(return_manifest.get("required_missing", []))
    required_missing_exact = missing_required == declared_required_missing
    manifest_byte_equal = (
        returned["evidence/PACKAGE_MANIFEST.json"]
        == source["TEST_PACKAGE_MANIFEST.json"]
    )
    manifest_semantic_equal = returned_package_manifest == source_manifest

    package_preflight = json_payload(
        returned, "evidence/package_preflight.json"
    )
    installed_preflight = json_payload(
        returned, "evidence/installed_preflight.json"
    )
    gate = json_payload(returned, "evidence/SERVER_RESULT_GATE.json")
    canonical = json_payload(
        returned, "evidence/CANONICAL_PROGRESS_DECISION.json"
    )
    progress_contract = json_payload(
        returned, "evidence/progress_contract.json"
    )
    final_audit = json.loads(SOURCE_FINAL_AUDIT.read_text(encoding="utf-8"))

    compile_status = int(
        returned["evidence/compile_exit_status.txt"].decode().strip()
    )
    simulation_status = int(
        returned["evidence/simulation_exit_status.txt"].decode().strip()
    )
    canonical_status = int(
        returned["evidence/canonical_decision_exit_status.txt"].decode().strip()
    )
    signal_values = kv(returned["evidence/signal_status.txt"].decode())
    host = epoch_map(returned["evidence/host_timing.txt"].decode())
    sim_wall_seconds = (
        host["final_epoch_ns"] - host["sim_start_epoch_ns"]
    ) / 1e9
    total_wall_seconds = (
        host["final_epoch_ns"] - host["package_start_epoch_ns"]
    ) / 1e9

    observer_text = returned["runs/return_observer.log"].decode(
        "utf-8", errors="replace"
    )
    sim_text = returned["runs/sim.log"].decode("utf-8", errors="replace")
    stages, event_counts = parse_stages(observer_text)
    slice_starts = [
        int(value)
        for value in re.findall(r"\[(\d+)\] INFO: slice start", sim_text)
    ]
    interrupts = [
        int(value) for value in re.findall(r"Interrupt at time (\d+)", sim_text)
    ]
    if len(stages) != 4 or len(slice_starts) != 4 or not interrupts:
        raise AnalysisError("expected four started stages and a final interrupt")
    if [stage["comp_finish_ps"] is not None for stage in stages] != [
        True,
        True,
        True,
        False,
    ]:
        raise AnalysisError("stage completion pattern differs")

    stage3 = stages[2]
    stage4 = stages[3]
    stage4_heartbeats = [
        item
        for item in (
            record
            for record in _stage_items(observer_text, stage4["exec_start_line"])
        )
        if item["event"] == "HEARTBEAT"
    ]
    stage4_deep = [
        item
        for item in _stage_items(observer_text, stage4["exec_start_line"])
        if item["event"] == "DEEP_COUNTS"
        and item.get("event_tag") == "HEARTBEAT"
    ]
    stage4_sg = [
        item
        for item in _stage_items(observer_text, stage4["exec_start_line"])
        if item["event"] == "SG_COUNTS"
        and item.get("event_tag") == "HEARTBEAT"
    ]
    if not stage4_heartbeats or not stage4_deep or not stage4_sg:
        raise AnalysisError("stage4 heartbeat/deep/SG evidence absent")
    flat_base_names = ("req", "rdata", "wdata")
    flat_deep_names = (
        "addr_enqueue",
        "req_hs",
        "meta",
        "consume",
        "buffer",
        "ga",
        "mse4_idx",
    )
    flat_sg_names = (
        "ga_input",
        "ga_output",
        "mse4_req0",
        "mse4_req1",
        "mse4_wdata0",
        "mse4_wdata1",
        "mse4_outstanding0",
        "mse4_outstanding1",
    )
    base_flat = all(
        len({int_value(item[name]) for item in stage4_heartbeats}) == 1
        for name in flat_base_names
    )
    deep_flat = all(
        len({int_value(item[name]) for item in stage4_deep}) == 1
        for name in flat_deep_names
    )
    sg_flat = all(
        len({int_value(item[name]) for item in stage4_sg}) == 1
        for name in flat_sg_names
    )
    stall_window = int(progress_contract["stall_window_cycles"])
    active_cycle_span = (
        int_value(stage4_heartbeats[-1]["active_cycles"])
        - int_value(stage4_heartbeats[0]["active_cycles"])
    )
    complete_flat_windows = active_cycle_span // stall_window

    canonical_without_digest = dict(canonical)
    canonical_digest = canonical_without_digest.pop("content_digest")
    canonical_digest_valid = (
        sha256_bytes(
            json.dumps(
                canonical_without_digest, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        )
        == canonical_digest["value"]
    )
    canonical_terminal_conflict = (
        canonical.get("decision") == "NATURAL_TERMINAL_OBSERVED"
        and event_counts["EXEC_START"] > event_counts["COMP_FINISH"]
        and simulation_status != 0
    )

    compile_argv = returned["evidence/actual_compile_argv.txt"].decode().strip()
    simulator_argv = (
        returned["evidence/actual_simulator_argv.txt"].decode().strip()
    )
    observer_four_way = {
        "source_packaged": (
            "tb_probe/native_return_observer.svh" in source_manifest["files"]
            and "tb_probe/qlinearadd_node0007_first_request_observer_tail_v9.svh"
            in source_manifest["files"]
        ),
        "package_local_incdir_in_actual_compile_argv": (
            f"/{SOURCE_ROOT}/tb_probe" in compile_argv
        ),
        "enable_macro_in_actual_compile_argv": (
            "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_argv
        ),
        "runtime_plusarg_in_actual_simulator_argv": (
            "+RETURN_OBSERVER" in simulator_argv
        ),
        "runtime_feature_args_in_actual_simulator_argv": all(
            token in simulator_argv
            for token in (
                "+RETURN_OBS_SLICE=0",
                "+RETURN_OBS_STALL_CYCLES=1048576",
                "+RETURN_OBS_HEARTBEAT_CYCLES=262144",
                "+RETURN_OBS_DEEP",
                "+RETURN_OBS_DEEP_LIMIT=64",
                "+RETURN_OBS_FILE=",
            )
        ),
        "time0_marker_and_runtime_log_present": (
            observer_text.startswith("# Native NDP return observer v4")
            and returned["evidence/observer_binding.txt"].decode().strip()
            == "observer_enabled_and_returned=true"
        ),
        "return_allowlist_and_trap_evidence_present": all(
            path in returned
            for path in (
                "evidence/observer_binding.txt",
                "runs/return_observer.log",
                "evidence/progress_samples.log",
                "evidence/signal_status.txt",
            )
        ),
    }

    stage3_sg_finish = _last_tagged_snapshot(
        observer_text,
        stage3["exec_start_line"],
        "SG_COUNTS",
        "COMP_FINISH",
    )
    stage4_deep_last = {
        name: int_value(stage4_deep[-1][name]) for name in flat_deep_names
    }
    stage4_sg_last = {
        name: int_value(stage4_sg[-1][name]) for name in flat_sg_names
    }
    stage4_base_last = {
        name: int_value(stage4_heartbeats[-1][name]) for name in flat_base_names
    }

    internal_errors: list[str] = []
    if not returned_exact_set:
        internal_errors.append("return exact-set differs")
    if member_receipt_errors:
        internal_errors.append("RETURN_MANIFEST member receipt differs")
    if unexpected_targets:
        internal_errors.append("return contains non-allowlisted target")
    if not required_missing_exact:
        internal_errors.append("required_missing exact-set differs")
    if not manifest_byte_equal or not manifest_semantic_equal:
        internal_errors.append("returned/source package manifest differs")
    if package_preflight.get("valid") is not True:
        internal_errors.append("package preflight invalid")
    if installed_preflight.get("valid") is not True:
        internal_errors.append("installed preflight invalid")
    if compile_status != 0:
        internal_errors.append("compile failed")
    if not all(observer_four_way.values()):
        internal_errors.append("observer four-way binding differs")

    return {
        "schema": "qlinearadd-node0007-dbuf-colpair-v18-return-analysis-v1",
        "status": "ANALYSIS_COMPLETE",
        "valid_internal_return_evidence": not internal_errors,
        "internal_evidence_errors": internal_errors,
        "control_receipts": receipts,
        "transport_receipt": {
            "path": str(return_zip),
            "transport_filename": return_zip.name,
            "download_suffix_identity_effect": "NONE",
            "size_bytes": return_zip.stat().st_size,
            "sha256": sha256_file(return_zip),
            "adjacent_sidecar_present": return_zip.with_suffix(
                return_zip.suffix + ".sha256"
            ).is_file(),
            "adjudication": "USER_ATTESTED_NO_SIDECAR_CONTENT_NEUTRAL",
            "rule_id": "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
        },
        "source_binding": {
            "zip": str(SOURCE_ZIP.relative_to(ROOT)),
            "zip_size_bytes": SOURCE_ZIP.stat().st_size,
            "zip_sha256": sha256_file(SOURCE_ZIP),
            "sidecar": str(SOURCE_SIDECAR.relative_to(ROOT)),
            "sidecar_sha256": sha256_file(SOURCE_SIDECAR),
            "sidecar_declares_zip_sha256": True,
            "final_audit": str(SOURCE_FINAL_AUDIT.relative_to(ROOT)),
            "final_audit_sha256": sha256_file(SOURCE_FINAL_AUDIT),
            "final_audit_pass": final_audit["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
            "final_audit_error_count": final_audit["error_count"],
            "returned_manifest_byte_equal": manifest_byte_equal,
            "returned_manifest_semantic_equal": manifest_semantic_equal,
        },
        "zip_integrity_and_allowlist": {
            "return": return_structure,
            "source": source_structure,
            "return_manifest_schema": return_manifest["schema"],
            "return_manifest_install_name": return_manifest["install_name"],
            "return_exact_set": returned_exact_set,
            "member_receipt_errors": member_receipt_errors,
            "unexpected_allowlist_targets": unexpected_targets,
            "required_missing_declared": declared_required_missing,
            "required_missing_computed": missing_required,
            "required_missing_exact": required_missing_exact,
            "returned_file_count_excluding_manifest": len(declared),
            "formal_d_missing_in_return_manifest": len(
                [
                    path
                    for path in declared_required_missing
                    if path.startswith("readbacks/")
                ]
            ),
        },
        "extraction_receipt": extraction,
        "identity_and_preflight": {
            "package_schema": source_manifest["schema"],
            "package_status_before_run": source_manifest["status"],
            "package_install_name": source_manifest["install_name"],
            "return_install_name": return_manifest["install_name"],
            "identity_exact": (
                source_manifest["install_name"]
                == return_manifest["install_name"]
                == SOURCE_ROOT
            ),
            "actual_compile_argv_install_bound": SOURCE_ROOT in compile_argv,
            "actual_simulator_argv_install_bound": SOURCE_ROOT in simulator_argv,
            "package_preflight": package_preflight,
            "installed_preflight": installed_preflight,
            "runtime_formal_d_initially_absent": (
                package_preflight.get("formal_readback_targets_absent") is True
                and installed_preflight.get("formal_readback_targets_absent")
                is True
            ),
            "sca_cfg_bound": (
                f"+SCA_CFG=install/cfg_pkg/{SOURCE_ROOT}/sca_cfg.json"
                in simulator_argv
            ),
            "sca_cfg_d_bound": (
                f"+SCA_CFG_D=install/cfg_pkg/{SOURCE_ROOT}/sca_cfg_D.json"
                in simulator_argv
            ),
            "preload_count_expected": source_manifest["config_preload_contract"][
                "expected_sca_preload_count"
            ],
            "gate_loader_checks": gate["result_gate_conjunction"][
                "loader_checks"
            ],
            "server_source_files_inspected": False,
        },
        "observer_and_canonical": {
            "four_way_binding": observer_four_way,
            "four_way_binding_all_true": all(observer_four_way.values()),
            "canonical_parser_exit_status": canonical_status,
            "canonical_content_digest_valid": canonical_digest_valid,
            "returned_canonical_decision": canonical["decision"],
            "returned_canonical_boundary": canonical["boundary"],
            "returned_canonical_reason": canonical["reason"],
            "runtime_semantics_valid": not canonical_terminal_conflict,
            "canonical_terminal_conflict": canonical_terminal_conflict,
            "conflict_reason": (
                "parser treats any earlier COMP_FINISH as final terminal although "
                "a later fourth EXEC_START has no COMP_FINISH and simulation exits "
                "125/INT"
            ),
            "level_or_non_transaction_counters_excluded_from_adjudication": [
                "buf5_rd level/read-enable sampling",
                "mse0_in2 valid&&ready without one-to-one consumer capture",
                "mse4_in0 valid&&ready without one-to-one queue consumption",
                "DEEP_RD_REQ_HANDSHAKE records whose hs field equals zero",
            ],
        },
        "execution": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "runner_signal": signal_values.get("signal"),
            "natural_terminal": False,
            "host_sim_wall_seconds": sim_wall_seconds,
            "host_total_wall_seconds": total_wall_seconds,
            "host_sim_wall_hours": sim_wall_seconds / 3600,
            "host_total_wall_hours": total_wall_seconds / 3600,
            "sim_interrupt_ps": interrupts[-1],
            "slice_start_ps": slice_starts,
            "exec_start_count": event_counts["EXEC_START"],
            "comp_finish_count": event_counts["COMP_FINISH"],
            "event_counts": dict(event_counts),
            "stage_timeline": stages,
        },
        "d_buffer_window_proof": {
            "static_final_zip_proof": final_audit["d_buffer_supply_proof"],
            "static_final_zip_window_proof": final_audit["d_buffer_window_proof"],
            "static_proof_current_rule_match": (
                final_audit["d_buffer_window_proof"]["rule_sha256"]
                == receipts["qlinearadd_rule"]["actual_sha256"]
            ),
            "op_relocation_pad_dynamic_completion": True,
            "op_relocation_pad_sg_finish": stage3_sg_finish,
            "op_relocation_pad_request_wdata_balanced": all(
                int_value(stage3_sg_finish[f"mse4_req{channel}"])
                == int_value(stage3_sg_finish[f"mse4_wdata{channel}"])
                and int_value(stage3_sg_finish[f"mse4_outstanding{channel}"])
                == 0
                for channel in (0, 1)
            ),
            "op_tail_mul_dynamic_reached": False,
            "op_tail_round_dynamic_reached": False,
            "accepted_row_col_tag_payload_returned": False,
            "dynamic_claim_boundary": (
                "relocation natural completion plus balanced accepted MSE4 "
                "request/write-data counters closes the old stage3 hang; the "
                "return does not expose accepted ROW/COL tag payloads and does "
                "not reach either tail stage"
            ),
        },
        "progress_adjudication": {
            "decision": "LONG_RUNNING_HANG_AT_OP_FP32_ADD_PRE_GA_INPUT",
            "hang_stage": "op_fp32_add",
            "stage4_base_qualified_flat": base_flat,
            "stage4_deep_downstream_flat": deep_flat,
            "stage4_sg_downstream_flat": sg_flat,
            "stage4_first_heartbeat_active_cycles": int_value(
                stage4_heartbeats[0]["active_cycles"]
            ),
            "stage4_last_heartbeat_active_cycles": int_value(
                stage4_heartbeats[-1]["active_cycles"]
            ),
            "stage4_flat_active_cycle_span": active_cycle_span,
            "stall_window_cycles": stall_window,
            "complete_flat_stall_windows": complete_flat_windows,
            "stage4_last_base": stage4_base_last,
            "stage4_last_deep": stage4_deep_last,
            "stage4_last_sg": stage4_sg_last,
            "interrupt_classification": (
                "MANUAL_INTERRUPT_AFTER_PROVEN_STALL_NOT_MERE_SLOW_COMPLETION"
            ),
        },
        "last_proven_good": {
            "boundary": "OP_RELOCATION_PAD_COMP_FINISH",
            "proof": (
                "op_a_dequant, op_b_dequant and op_relocation_pad each emit "
                "ordered EXEC_START->COMP_FINISH; relocation reaches balanced "
                "MSE4 request/write-data counts with zero outstanding"
            ),
            "v16_stage3_blocker_closed": True,
        },
        "first_divergence": {
            "boundary": "OP_FP32_ADD_AFTER_FINITE_READ_ACTIVITY_BEFORE_GA_INPUT_ACCEPT",
            "last_positive_events": {
                "deep_read_addr_enqueue_records": stage4_deep_last[
                    "addr_enqueue"
                ],
                "deep_read_consume_records": stage4_deep_last["consume"],
                "mse0_to_buffer0_accept": stage4_deep_last["buffer"],
            },
            "first_nonprogress_chain": {
                "ga_input_accept": stage4_sg_last["ga_input"],
                "ga_output_accept": stage4_sg_last["ga_output"],
                "mse4_request_accept": [
                    stage4_sg_last["mse4_req0"],
                    stage4_sg_last["mse4_req1"],
                ],
                "mse4_write_data_accept": [
                    stage4_sg_last["mse4_wdata0"],
                    stage4_sg_last["mse4_wdata1"],
                ],
                "mse4_outstanding": [
                    stage4_sg_last["mse4_outstanding0"],
                    stage4_sg_last["mse4_outstanding1"],
                ],
            },
        },
        "hang_root_cause": {
            "functional_root_cause_unique": False,
            "localized_interval": (
                "op_fp32_add dual read ingress / Buffer0+Buffer2 paired "
                "readiness -> GA input accept"
            ),
            "excluded_as_root_cause": [
                "slow-but-progressing execution",
                "old op_relocation_pad D-buffer ROW-only supply",
                "missing config preload",
                "first DRAM request absence",
                "formal D numeric mismatch",
            ],
            "unresolved_candidates": [
                "unobserved stream1/MSE1 accepted read path",
                "Buffer2 accepted write/row-bank valid state",
                "Buffer0+Buffer2 paired GA input tag/mask readiness",
                "GA input consumer capture/backpressure before first accepted input",
            ],
            "diagnostic_package_defect_independent_of_functional_hang": (
                "canonical parser is not final-stage scoped and individual "
                "MSE input valid&&ready counters lack one-to-one transaction proof"
            ),
        },
        "formal_d_and_result_gate": {
            "expected": gate["expected_readback_count"],
            "present": gate["observed_readback_count"],
            "missing": gate["missing_count"],
            "mismatch_byte_count": gate["mismatch_byte_count"],
            "mismatch_zero_evaluable": False,
            "reason": "all 28 formal D targets are missing",
            "server_result_gate_conjunction": gate["result_gate_conjunction"],
            "server_result_gate_all_terms_true": gate["result_gate_conjunction"][
                "all_terms_true"
            ],
            "server_result_status": gate["status"],
        },
        "evidence_gate": {
            "E3": False,
            "E4": False,
            "E5": False,
            "reason": (
                "simulation=125/INT, no natural terminal, canonical conflict, "
                "28/28 formal D missing"
            ),
        },
        "blocker_delta": {
            "close": [
                "B_QADD_NODE0007_STAGE3_RELOCATION_D_BUFFER_ROW_ONLY_SUPPLY"
            ],
            "open": [
                {
                    "id": "B_QADD_NODE0007_FP32_ADD_PRE_GA_INPUT_HANG",
                    "scope": (
                        "op_fp32_add finite read activity -> Buffer0/Buffer2 "
                        "paired readiness -> first qualified GA input"
                    ),
                },
                {
                    "id": "B_QADD_V18_CANONICAL_FINAL_STAGE_SCOPE",
                    "scope": (
                        "runtime canonical record conflicts with later unfinished "
                        "EXEC_START and simulation 125/INT"
                    ),
                },
            ],
        },
        "rule_delta_proposal": [
            {
                "proposal": (
                    "multi-stage canonical terminal must bind the expected ordered "
                    "stage list and may report natural terminal only when the last "
                    "expected EXEC_START has its own COMP_FINISH"
                ),
                "reason": (
                    "v18 parser line of reasoning `elif finish` accepted three "
                    "earlier finishes despite an unfinished fourth stage"
                ),
            },
            {
                "proposal": (
                    "QAdd progress validators must reject individual MSE input "
                    "valid&&ready level counts as monotonic progress unless a "
                    "one-to-one queue write/dequeue or transaction-id witness is bound"
                ),
                "reason": (
                    "stage4 individual input counters grow while queue/AG/base "
                    "accepted counters remain flat for 189 complete stall windows"
                ),
            },
        ],
        "successor_proposal_or_none": {
            "status": "PROPOSAL_ONLY_NOT_GENERATED",
            "class": "NARROW_OBSERVER_ONLY",
            "required_boundary": (
                "op_fp32_add stream0+stream1 MSE accepted read -> Buffer0/2 "
                "row-bank valid/write accept -> paired GA tag/mask readiness -> "
                "GA input consumer capture"
            ),
            "frozen_payload_requirement": (
                "no numeric/W3/qparam/tail/workload/config/golden change"
            ),
        },
        "package_release": {
            "status": "NONE",
            "source_v18_status": (
                "QUARANTINED_DYNAMIC_OP_FP32_ADD_HANG_AND_CANONICAL_CONFLICT"
            ),
            "successor_generated": False,
        },
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "config_numeric_analysis_repeated": False,
        "golden_recomputed": False,
        "functional_rtl_modified": False,
        "server_inspected_or_run": False,
    }


def _stage_items(observer_text: str, start_line: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line_number, line in enumerate(observer_text.splitlines(), start=1):
        if line_number < start_line:
            continue
        match = re.match(r"^(\d+) \| ([A-Z0-9_]+) \|(.*)$", line)
        if not match:
            continue
        if line_number > start_line and match.group(2) == "EXEC_START":
            break
        values = kv(match.group(3))
        if "event" in values:
            values["event_tag"] = values.pop("event")
        items.append(
            {
                "ps": int(match.group(1)),
                "line": line_number,
                "event": match.group(2),
                **values,
            }
        )
    return items


def _last_tagged_snapshot(
    observer_text: str, start_line: int, event: str, tag: str
) -> dict[str, str]:
    matches = [
        item
        for item in _stage_items(observer_text, start_line)
        if item["event"] == event and item.get("event_tag") == tag
    ]
    if not matches:
        raise AnalysisError(f"missing {event}/{tag} snapshot")
    return {
        key: value
        for key, value in matches[-1].items()
        if key not in {"event", "event_tag"}
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--extract-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = analyze(
            args.return_zip.resolve(),
            args.extract_root.resolve(),
        )
    except Exception as error:
        print(f"QAdd v18 return analysis failed: {error}")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "valid_internal_return_evidence": report[
                    "valid_internal_return_evidence"
                ],
                "progress": report["progress_adjudication"]["decision"],
                "first_divergence": report["first_divergence"]["boundary"],
                "package_release": report["package_release"]["status"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0 if report["valid_internal_return_evidence"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
