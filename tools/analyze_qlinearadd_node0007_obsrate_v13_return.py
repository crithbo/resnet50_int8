from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-07\r5_qadd_n7_obsrate_v13_return.zip"
)
SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "r5_qadd_n7_obsrate_v13.zip"
)
SOURCE_SHA256 = "fe65a96ad6365872f2f004f6702b197f33fc6b5fcd4397df716714f443b28858"
INSTALL_NAME = "r5_qadd_n7_obsrate_v13"
REPORT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-observer-rate-v13-return-analysis"
    / "report.json"
)
INSTRUCTIONS = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-nested-lc-full-e2-v4"
    / "execplan/pipeline_output/instructions_explained.txt"
)
RTL_LC_CONFIG = (
    ROOT
    / "Trassic2.0_RTL/code/NDP_rtl/Slice/Index_Generation_Array"
    / "IGA_LC/IGA_LC_Config.sv"
)

EXPECTED_CONFIGS = {
    "op_a_dequant": (52, 0x34AC, 0x00D2B000),
    "op_b_dequant": (52, 0x34AD, 0x00D2B400),
    "op_relocation_pad": (50, 0x34AE, 0x00D2B800),
    "op_fp32_add": (52, 0x34AF, 0x00D2BC00),
    "op_tail_mul": (50, 0x34B0, 0x00D2C000),
    "op_tail_round": (68, 0x34B1, 0x00D2C400),
}
CHAIN_RE = re.compile(
    r"FIRST_REQUEST_CHAIN \| slice=(?P<slice>\d+) "
    r"active_cycles=(?P<cycles>\d+) slice_start=(?P<slice_start>\d+) "
    r"lc_enable=(?P<enable>0x[0-9a-f]+) "
    r"lc_valid=(?P<valid>0x[0-9a-f]+) "
    r"lc_ready=(?P<ready>0x[0-9a-f]+) "
    r"lc_hs=(?P<lc_hs>[0-9,]+).*?"
    r"mse0_in_hs=(?P<mse0_hs>[0-9,]+).*?"
    r"mse0_queue_wr=(?P<mse0_queue>\d+).*?"
    r"mse0_ag_hs=(?P<mse0_ag>\d+).*?"
    r"mse0_req_enq=(?P<mse0_req>\d+).*?"
    r"mse4_in_hs=(?P<mse4_hs>[0-9,]+).*?"
    r"mse4_queue_wr=(?P<mse4_queue>\d+)"
)
CLOCK_RE = re.compile(
    r"FIRST_REQUEST_CLOCK \| slice=(?P<slice>\d+) "
    r"active_cycles=(?P<cycles>\d+) "
    r"clk_sg_edges=(?P<edges>\d+) clk_sg_level=(?P<level>[01])"
)
LOAD_RE = re.compile(
    r"Load_Config for operator (?P<stage>\w+).*?"
    r"config_length_bin=(?P<length>[01]+), "
    r"ddr_config_addr_bin=(?P<address>[01]+)"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def key_values(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in payload.decode("utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and not re.match(r"^[A-Za-z]:", name)
    )


def analyze(return_zip: Path = DEFAULT_RETURN) -> dict[str, Any]:
    errors: list[str] = []
    adjacent_sidecar = Path(str(return_zip) + ".sha256")
    with zipfile.ZipFile(return_zip) as archive:
        bad_member = archive.testzip()
        names = archive.namelist()
        members = {
            name: archive.read(name)
            for name in names
            if not name.endswith("/")
        }
    return_root = f"{INSTALL_NAME}_return/"
    roots = sorted({name.split("/", 1)[0] for name in names})
    root_exact = roots == [f"{INSTALL_NAME}_return"]
    crc_valid = bad_member is None
    duplicates_absent = len(names) == len(set(names))
    paths_safe = all(safe_member(name) for name in names)

    with zipfile.ZipFile(SOURCE) as source_archive:
        source_bad_member = source_archive.testzip()
        source_manifest_bytes = source_archive.read(
            f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json"
        )
        source_sca_bytes = source_archive.read(
            f"{INSTALL_NAME}/workload/runtime/sca_cfg.json"
        )
        source_names = set(source_archive.namelist())
    source_manifest = json.loads(source_manifest_bytes)
    sca = json.loads(source_sca_bytes)

    return_manifest = json.loads(members[return_root + "RETURN_MANIFEST.json"])
    returned_manifest_bytes = members[
        return_root + "evidence/PACKAGE_MANIFEST.json"
    ]
    relative_members = {
        name.removeprefix(return_root)
        for name in members
        if name.startswith(return_root)
    }
    declared_files = {
        item["path"]: item for item in return_manifest["files"]
    }
    declared_exact = set(declared_files) | {"RETURN_MANIFEST.json"}
    manifest_hashes_valid = all(
        path in relative_members
        and sha256_bytes(members[return_root + path]) == item["sha256"]
        and len(members[return_root + path]) == item["size_bytes"]
        for path, item in declared_files.items()
    )
    return_exact_set = relative_members == declared_exact
    package_allowlist = {
        item["target_path"]: item for item in source_manifest["return_allowlist"]
    }
    allowed_actual = (
        relative_members - {"RETURN_MANIFEST.json"}
    ).issubset(package_allowlist)
    required_missing_expected = sorted(
        path
        for path, item in package_allowlist.items()
        if item["required"] and path not in relative_members
    )
    required_missing_declared = sorted(return_manifest["required_missing"])
    required_missing_consistent = (
        required_missing_expected == required_missing_declared
    )

    package_preflight = json.loads(
        members[return_root + "evidence/package_preflight.json"]
    )
    installed_preflight = json.loads(
        members[return_root + "evidence/installed_preflight.json"]
    )
    gate = json.loads(
        members[return_root + "evidence/SERVER_RESULT_GATE.json"]
    )
    canonical = json.loads(
        members[
            return_root + "evidence/CANONICAL_PROGRESS_DECISION.json"
        ]
    )
    canonical_exit = int(
        members[
            return_root + "evidence/canonical_decision_exit_status.txt"
        ]
    )
    signal = key_values(
        members[return_root + "evidence/signal_status.txt"]
    )
    timing = {
        key: int(value)
        for key, value in key_values(
            members[return_root + "evidence/host_timing.txt"]
        ).items()
    }
    observer = members[
        return_root + "runs/return_observer.log"
    ].decode("utf-8", errors="replace")
    chain_samples = [
        {
            "slice": int(match.group("slice")),
            "active_cycles": int(match.group("cycles")),
            "slice_start": int(match.group("slice_start")),
            "lc_enable": int(match.group("enable"), 16),
            "lc_valid": int(match.group("valid"), 16),
            "lc_ready": int(match.group("ready"), 16),
            "lc_hs": [int(value) for value in match.group("lc_hs").split(",")],
            "mse0_in_hs": [
                int(value) for value in match.group("mse0_hs").split(",")
            ],
            "mse0_queue_wr": int(match.group("mse0_queue")),
            "mse0_ag_hs": int(match.group("mse0_ag")),
            "mse0_req_enq": int(match.group("mse0_req")),
            "mse4_in_hs": [
                int(value) for value in match.group("mse4_hs").split(",")
            ],
            "mse4_queue_wr": int(match.group("mse4_queue")),
        }
        for match in CHAIN_RE.finditer(observer)
    ]
    clock_samples = [
        {
            "slice": int(match.group("slice")),
            "active_cycles": int(match.group("cycles")),
            "clk_sg_edges": int(match.group("edges")),
            "clk_sg_level": int(match.group("level")),
        }
        for match in CLOCK_RE.finditer(observer)
    ]
    paired_rate_limited = (
        len(chain_samples) == len(clock_samples)
        and len(chain_samples) > 0
        and [
            sample["active_cycles"] for sample in chain_samples
        ]
        == [sample["active_cycles"] for sample in clock_samples]
        and all(
            sample["active_cycles"]
            % source_manifest["progress_localization"]["heartbeat_cycles"]
            == 0
            for sample in clock_samples
        )
    )
    chain_qualified_zero = all(
        not any(
            sample["lc_hs"]
            + sample["mse0_in_hs"]
            + [
                sample["mse0_queue_wr"],
                sample["mse0_ag_hs"],
                sample["mse0_req_enq"],
            ]
            + sample["mse4_in_hs"]
            + [sample["mse4_queue_wr"]]
        )
        for sample in chain_samples
    )
    clock_alive = all(
        after["clk_sg_edges"] > before["clk_sg_edges"]
        for before, after in zip(clock_samples, clock_samples[1:])
    ) and bool(clock_samples)

    instructions_text = INSTRUCTIONS.read_text(
        encoding="utf-8", errors="replace"
    ).replace("\n", " ")
    decoded = {
        match.group("stage"): {
            "config_length_64b": int(match.group("length"), 2),
            "ddr_config_addr": int(match.group("address"), 2),
            "base_addr": int(match.group("address"), 2) << 10,
        }
        for match in LOAD_RE.finditer(instructions_text)
    }
    config_bindings = {}
    for stage, (length, ddr_addr, base_addr) in EXPECTED_CONFIGS.items():
        suffix = f"{stage}_config"
        source_config_keys = [
            key for key in sca if key == suffix
        ]
        bitstream_members = sorted(
            name
            for name in source_names
            if name.startswith(f"{INSTALL_NAME}/workload/runtime/install/cfg_pkg/")
            and stage in name
            and name.endswith("_bitstream_128b.bin")
        )
        config_bindings[stage] = {
            "expected_sca_key": suffix,
            "sca_entry_present": bool(source_config_keys),
            "bitstream_member_present": len(bitstream_members) == 1,
            "bitstream_member": (
                bitstream_members[0] if len(bitstream_members) == 1 else None
            ),
            "load_config_decoded": decoded.get(stage),
            "expected": {
                "config_length_64b": length,
                "ddr_config_addr": ddr_addr,
                "base_addr": base_addr,
                "address_equation": "base_addr = ddr_config_addr << 10",
            },
            "load_config_matches_expected": decoded.get(stage)
            == {
                "config_length_64b": length,
                "ddr_config_addr": ddr_addr,
                "base_addr": base_addr,
            },
        }
    all_config_preloads_missing = all(
        not item["sca_entry_present"] for item in config_bindings.values()
    )
    all_payloads_packaged = all(
        item["bitstream_member_present"] for item in config_bindings.values()
    )
    all_load_configs_bound = all(
        item["load_config_matches_expected"] for item in config_bindings.values()
    )
    rtl_text = RTL_LC_CONFIG.read_text(encoding="utf-8", errors="replace")
    rtl_enable_equation_present = (
        "iga_lc_configure_inport_valid && iga_lc_configure_inport_enable"
        in rtl_text
        and "iga_lc_enable <= 1;" in rtl_text
    )

    conjunction = gate["result_gate_conjunction"]
    compile_status = int(signal["compile_status"])
    simulation_status = int(signal["simulation_status"])
    formal_receipt_valid = adjacent_sidecar.is_file()
    if formal_receipt_valid:
        sidecar_text = adjacent_sidecar.read_text(
            encoding="utf-8", errors="replace"
        ).strip().split()[0].lower()
        formal_receipt_valid = sidecar_text == sha256(return_zip)
    diagnostics_valid = all(
        [
            crc_valid,
            duplicates_absent,
            paths_safe,
            root_exact,
            return_exact_set,
            manifest_hashes_valid,
            allowed_actual,
            required_missing_consistent,
            sha256(SOURCE) == SOURCE_SHA256,
            source_bad_member is None,
            returned_manifest_bytes == source_manifest_bytes,
            package_preflight.get("valid") is True,
            installed_preflight.get("valid") is True,
            package_preflight.get("formal_readback_targets_absent") is True,
            installed_preflight.get("formal_readback_targets_absent") is True,
            compile_status == 0,
            canonical_exit == 0,
            paired_rate_limited,
            clock_alive,
            chain_qualified_zero,
            all_config_preloads_missing,
            all_payloads_packaged,
            all_load_configs_bound,
            rtl_enable_equation_present,
        ]
    )
    if not diagnostics_valid:
        errors.append("one or more diagnostic-integrity checks failed")

    report: dict[str, Any] = {
        "schema": "qlinearadd-node0007-obsrate-v13-return-analysis-v1",
        "status": "QUARANTINED_MISSING_SCA_CONFIG_PRELOADS",
        "return_receipt": {
            "path": str(return_zip),
            "sha256": sha256(return_zip),
            "bytes": return_zip.stat().st_size,
            "adjacent_sidecar": str(adjacent_sidecar),
            "adjacent_sidecar_exists": adjacent_sidecar.is_file(),
            "formal_receipt_valid": formal_receipt_valid,
            "diagnostic_evidence_consumable": diagnostics_valid,
        },
        "source_binding": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "expected_sha256": SOURCE_SHA256,
            "actual_sha256": sha256(SOURCE),
            "crc_valid": source_bad_member is None,
            "returned_package_manifest_byte_equal": (
                returned_manifest_bytes == source_manifest_bytes
            ),
        },
        "zip_and_allowlist": {
            "crc_valid": crc_valid,
            "duplicate_members_absent": duplicates_absent,
            "paths_safe": paths_safe,
            "root_exact": root_exact,
            "file_member_count": len(members),
            "return_manifest_exact_set": return_exact_set,
            "return_manifest_hashes_and_sizes_valid": manifest_hashes_valid,
            "package_allowlist_only": allowed_actual,
            "required_missing_consistent": required_missing_consistent,
            "required_missing_count": len(required_missing_expected),
        },
        "preflight": {
            "package_valid": package_preflight.get("valid") is True,
            "installed_valid": installed_preflight.get("valid") is True,
            "package_file_count": package_preflight.get("file_count"),
            "installed_file_count": installed_preflight.get(
                "installed_file_count"
            ),
            "preload_count": package_preflight.get("preload_count"),
            "formal_readback_count": package_preflight.get("readback_count"),
            "package_runtime_d_absent": package_preflight.get(
                "formal_readback_targets_absent"
            )
            is True,
            "installed_runtime_d_absent": installed_preflight.get(
                "formal_readback_targets_absent"
            )
            is True,
            "server_source_files_inspected": False,
        },
        "execution": {
            "compile_exit_status": compile_status,
            "simulation_exit_status": simulation_status,
            "signal": signal.get("signal"),
            "natural_terminal": conjunction["natural_completion"],
            "host_total_seconds": (
                timing["final_epoch_ns"] - timing["package_start_epoch_ns"]
            )
            / 1e9,
            "simulation_seconds": (
                timing["final_epoch_ns"] - timing["sim_start_epoch_ns"]
            )
            / 1e9,
            "hang_first_applied": simulation_status != 0
            and not conjunction["natural_completion"],
        },
        "qualified_first_request_chain": {
            "chain_sample_count": len(chain_samples),
            "clock_sample_count": len(clock_samples),
            "shared_heartbeat_gate": paired_rate_limited,
            "clock_monotonically_alive": clock_alive,
            "first_active_cycles": (
                chain_samples[0]["active_cycles"] if chain_samples else None
            ),
            "last_active_cycles": (
                chain_samples[-1]["active_cycles"] if chain_samples else None
            ),
            "first_clk_sg_edges": (
                clock_samples[0]["clk_sg_edges"] if clock_samples else None
            ),
            "last_clk_sg_edges": (
                clock_samples[-1]["clk_sg_edges"] if clock_samples else None
            ),
            "slice_start_seen": all(
                sample["slice_start"] == 1 for sample in chain_samples
            ),
            "lc_enable_always_zero": all(
                sample["lc_enable"] == 0 for sample in chain_samples
            ),
            "lc_ready_always_all_five": all(
                sample["lc_ready"] == 0x1F for sample in chain_samples
            ),
            "all_qualified_downstream_counters_zero": chain_qualified_zero,
            "level_snapshots_used_as_progress": False,
            "canonical_decision": canonical["decision"],
            "canonical_boundary": canonical["boundary"],
            "canonical_reason": canonical["reason"],
            "canonical_exit_status": canonical_exit,
            "flat_qualified_cycles": canonical["counter_snapshot"][
                "flat_qualified_cycles"
            ],
            "stall_window_cycles": canonical["content_summary"][
                "stall_window_cycles"
            ],
        },
        "first_divergence": {
            "last_good": (
                "compile/elaboration, configuration and execution commands, "
                "actual slice_start_run, alive clk_sg observer domain"
            ),
            "first_bad": (
                "physical LC2/4/6/13/18 enable remains 0; therefore LC4 "
                "outer handshake never occurs"
            ),
            "downstream": (
                "MSE0/MSE4 inputs, match, queue writes, AG, request enqueue, "
                "base request accept, terminal, and all 28 D readbacks absent"
            ),
        },
        "hang_root_cause": {
            "classification": "SCA_CONFIG_PRELOAD_MATERIALIZATION_OMISSION",
            "sca_preload_object_count_observed": package_preflight.get(
                "preload_count"
            ),
            "missing_config_preload_count": len(EXPECTED_CONFIGS),
            "all_six_config_preloads_missing": all_config_preloads_missing,
            "all_six_bitstream_files_packaged": all_payloads_packaged,
            "all_six_execplan_load_config_commands_valid": (
                all_load_configs_bound
            ),
            "config_bindings": config_bindings,
            "instructions_path": INSTRUCTIONS.relative_to(ROOT).as_posix(),
            "instructions_sha256": sha256(INSTRUCTIONS),
            "rtl_consumer_path": RTL_LC_CONFIG.relative_to(ROOT).as_posix(),
            "rtl_consumer_sha256": sha256(RTL_LC_CONFIG),
            "rtl_enable_equation_present": rtl_enable_equation_present,
            "causal_chain": (
                "execplan Load_Config reads six reserved DRAM config slots; "
                "v13 sca_cfg.json never preloads those slots, so LC config "
                "valid/enable is never established and all observed LC "
                "enable bits remain zero after slice_start"
            ),
            "not_attributed_to": [
                "shared-LC topology/backpressure",
                "numeric/W3/qparam/tail/golden",
                "mapping or frozen workload semantics",
                "server RTL functional defect",
            ],
        },
        "formal_d_and_result_gate": {
            "expected_count": gate["expected_readback_count"],
            "observed_count": gate["observed_readback_count"],
            "missing_count": gate["missing_count"],
            "mismatch_byte_count": gate["mismatch_byte_count"],
            "mismatch_zero_not_numeric_pass": True,
            "all_terms_true": conjunction["all_terms_true"],
            "E3": False,
            "E4": False,
            "E5": False,
        },
        "package_release": {
            "v13": "QUARANTINED_MISSING_SCA_CONFIG_PRELOADS",
            "successor": "r5_qadd_n7_cfgpreload_v14.zip",
            "successor_status": "PACKAGE_READY_NOT_RUN",
            "successor_sha256": (
                "78f1aa16b2853173c5b263acb2f1a3b42516a08cc7bb2fd5342f3fd55b918282"
            ),
        },
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "config_numeric_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "errors": errors,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("return_zip", nargs="?", type=Path, default=DEFAULT_RETURN)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args(argv)
    report = analyze(args.return_zip)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
