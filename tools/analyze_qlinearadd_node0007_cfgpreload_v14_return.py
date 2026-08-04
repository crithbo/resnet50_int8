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

from resnet50_pipeline.qlinearadd_node0007_d_buffer_supply_v15 import (
    build_configs,
    validate_d_buffer_supply,
)
from resnet50_pipeline.qlinearadd_node0007_nested_lc_v4 import (
    build_configs as build_v14_configs,
)


DEFAULT_RETURN = Path(
    r"C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7"
    r"\msg\file\2026-08\r5_qadd_n7_cfgpreload_v14_return.zip"
)
INSTALL_NAME = "r5_qadd_n7_cfgpreload_v14"
SOURCE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{INSTALL_NAME}.zip"
)
SOURCE_SHA256 = "78f1aa16b2853173c5b263acb2f1a3b42516a08cc7bb2fd5342f3fd55b918282"
REPORT = (
    ROOT
    / "artifacts/operator_config_validation"
    / "r5-qlinearadd-node0007-cfgpreload-v14-return-analysis"
    / "report.json"
)
EVENT_RE = re.compile(
    r"^(?P<time>\d+) \| (?P<event>EXEC_START|COMP_FINISH) \| "
    r"slice=(?P<slice>\d+) active_cycles=(?P<cycles>\d+) "
    r"gexec=(?P<gexec>\d+) gconfig=(?P<gconfig>\d+) "
    r"req=(?P<req>\d+) rdata=(?P<rdata>\d+) wdata=(?P<wdata>\d+)"
)
DEEP_RE = re.compile(
    r"^(?P<time>\d+) \| DEEP_COUNTS \| event=(?P<event>\w+) "
    r"addr_enqueue=(?P<addr>\d+) req_hs=(?P<req>\d+) "
    r"meta=(?P<meta>\d+) consume=(?P<consume>\d+) "
    r"buffer=(?P<buffer>\d+) ga=(?P<ga>\d+) mse4_idx=(?P<mse4>\d+)"
)
SG_RE = re.compile(
    r"^(?P<time>\d+) \| SG_COUNTS \| event=(?P<event>\w+) "
    r"ga_input=(?P<ga_in>\d+) ga_output=(?P<ga_out>\d+) "
    r"mse4_req0=(?P<req0>\d+) mse4_req1=(?P<req1>\d+) "
    r"mse4_wdata0=(?P<wdata0>\d+) mse4_wdata1=(?P<wdata1>\d+) "
    r"mse4_outstanding0=(?P<out0>\d+) mse4_outstanding1=(?P<out1>\d+)"
)
CHAIN_CYCLE_RE = re.compile(
    r"FIRST_REQUEST_CHAIN \| slice=0 active_cycles=(?P<cycles>\d+)"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def safe_member(name: str) -> bool:
    path = PurePosixPath(name)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and "\\" not in name
        and not re.match(r"^[A-Za-z]:", name)
    )


def key_values(payload: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in payload.decode(errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            result[key] = value
    return result


def _old_supply_records() -> dict[str, Any]:
    configs = build_v14_configs(ROOT)
    records: dict[str, Any] = {}
    for stage in ("op_relocation_pad", "op_tail_mul", "op_tail_round"):
        config = configs[stage]
        stream = config["stream_engine"]["stream2"]
        transaction = 1
        for encoded in stream["idx_size"]:
            transaction *= 1 if encoded is None else int(encoded) + 1
        row = config["buffer_loop_configs"]["GROUP2"]["ROW_LC"]
        trips = len(range(int(row["start"]), int(row["end"]), int(row["stride"])))
        spatial = int(stream["buf_spatial_size"])
        records[stage] = {
            "transaction_bytes": transaction,
            "buffer_bytes_per_row": spatial,
            "row_trips": trips,
            "supplied_bytes": trips * spatial,
            "buffer5_end_row_addr": config["buffer_config"]["buffer5"][
                "buf_end_row_addr"
            ],
            "conservation_valid": transaction == trips * spatial,
        }
    return records


def analyze(return_zip: Path = DEFAULT_RETURN) -> dict[str, Any]:
    errors: list[str] = []
    with zipfile.ZipFile(return_zip) as archive:
        bad = archive.testzip()
        infos = archive.infolist()
        names = [info.filename for info in infos]
        members = {
            info.filename: archive.read(info)
            for info in infos
            if not info.is_dir()
        }
    return_root = f"{INSTALL_NAME}_return/"
    roots = sorted({name.split("/", 1)[0] for name in names})
    manifest = json.loads(members[return_root + "RETURN_MANIFEST.json"])
    relative = {
        name.removeprefix(return_root)
        for name in members
        if name.startswith(return_root)
    }
    declared = {item["path"]: item for item in manifest["files"]}
    exact = relative == set(declared) | {"RETURN_MANIFEST.json"}
    hashes = all(
        path in relative
        and sha256_bytes(members[return_root + path]) == item["sha256"]
        and len(members[return_root + path]) == item["size_bytes"]
        for path, item in declared.items()
    )
    with zipfile.ZipFile(SOURCE) as source_archive:
        source_bad = source_archive.testzip()
        source_manifest_bytes = source_archive.read(
            f"{INSTALL_NAME}/TEST_PACKAGE_MANIFEST.json"
        )
    returned_manifest = members[return_root + "evidence/PACKAGE_MANIFEST.json"]
    source_manifest = json.loads(source_manifest_bytes)
    allowlist = {
        item["target_path"]: item for item in source_manifest["return_allowlist"]
    }
    allowlist_only = (
        relative - {"RETURN_MANIFEST.json"}
    ).issubset(allowlist)
    required_missing = sorted(
        path
        for path, item in allowlist.items()
        if item["required"] and path not in relative
    )
    required_missing_consistent = (
        required_missing == sorted(manifest["required_missing"])
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
        members[return_root + "evidence/CANONICAL_PROGRESS_DECISION.json"]
    )
    signal = key_values(members[return_root + "evidence/signal_status.txt"])
    timing = {
        key: int(value)
        for key, value in key_values(
            members[return_root + "evidence/host_timing.txt"]
        ).items()
    }
    observer_lines = members[
        return_root + "runs/return_observer.log"
    ].decode(errors="replace").splitlines()
    events = []
    for line_number, line in enumerate(observer_lines, 1):
        match = EVENT_RE.match(line)
        if match:
            events.append(
                {
                    "line": line_number,
                    **{key: int(value) if key != "event" else value
                       for key, value in match.groupdict().items()},
                }
            )
    exec_events = [item for item in events if item["event"] == "EXEC_START"]
    finishes = [item for item in events if item["event"] == "COMP_FINISH"]
    third_exec_line = exec_events[2]["line"]
    third_deep = []
    third_sg = []
    third_cycles = []
    for line_number, line in enumerate(observer_lines, 1):
        if line_number <= third_exec_line:
            continue
        deep_match = DEEP_RE.match(line)
        if deep_match and deep_match.group("event") == "HEARTBEAT":
            third_deep.append(
                tuple(
                    int(deep_match.group(key))
                    for key in (
                        "addr", "req", "meta", "consume", "buffer", "ga", "mse4"
                    )
                )
            )
        sg_match = SG_RE.match(line)
        if sg_match and sg_match.group("event") == "HEARTBEAT":
            third_sg.append(
                tuple(
                    int(sg_match.group(key))
                    for key in (
                        "ga_in", "ga_out", "req0", "req1",
                        "wdata0", "wdata1", "out0", "out1",
                    )
                )
            )
        cycle_match = CHAIN_CYCLE_RE.search(line)
        if cycle_match:
            third_cycles.append(int(cycle_match.group("cycles")))
    flat = (
        bool(third_deep)
        and len(set(third_deep)) == 1
        and bool(third_sg)
        and len(set(third_sg)) == 1
    )
    flat_cycles = (
        third_cycles[-1] - third_cycles[0] if len(third_cycles) >= 2 else 0
    )
    old_supply = _old_supply_records()
    fixed_supply = validate_d_buffer_supply(build_configs(ROOT))
    conjunction = gate["result_gate_conjunction"]
    formal_integrity = all(
        [
            bad is None,
            len(names) == len(set(names)),
            all(safe_member(name) for name in names),
            roots == [f"{INSTALL_NAME}_return"],
            exact,
            hashes,
            allowlist_only,
            required_missing_consistent,
            sha256(SOURCE) == SOURCE_SHA256,
            source_bad is None,
            returned_manifest == source_manifest_bytes,
            package_preflight.get("valid") is True,
            installed_preflight.get("valid") is True,
            package_preflight.get("formal_readback_targets_absent") is True,
            installed_preflight.get("formal_readback_targets_absent") is True,
        ]
    )
    if not formal_integrity:
        errors.append("formal return integrity check failed")
    if not (len(exec_events) == 3 and len(finishes) == 2 and flat):
        errors.append("dynamic stage-boundary evidence differs")

    return {
        "schema": "qlinearadd-node0007-cfgpreload-v14-return-analysis-v1",
        "status": "QUARANTINED_DYNAMIC_D_BUFFER_UNDERSUPPLY",
        "return_receipt": {
            "path": str(return_zip),
            "sha256": sha256(return_zip),
            "bytes": return_zip.stat().st_size,
            "adjacent_sidecar_exists": Path(str(return_zip) + ".sha256").is_file(),
            "transport_policy": (
                "USER_ATTESTED_NO_SIDECAR; missing sidecar is non-blocking"
            ),
            "formal_internal_receipt_valid": formal_integrity,
        },
        "source_binding": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "expected_sha256": SOURCE_SHA256,
            "actual_sha256": sha256(SOURCE),
            "returned_manifest_byte_equal": returned_manifest == source_manifest_bytes,
        },
        "zip_and_allowlist": {
            "crc_valid": bad is None,
            "root_exact": roots == [f"{INSTALL_NAME}_return"],
            "paths_safe": all(safe_member(name) for name in names),
            "duplicates_absent": len(names) == len(set(names)),
            "return_manifest_exact_set": exact,
            "hashes_and_sizes_valid": hashes,
            "allowlist_only": allowlist_only,
            "required_missing": required_missing,
            "required_missing_consistent": required_missing_consistent,
        },
        "preflight": {
            "package_valid": package_preflight.get("valid"),
            "installed_valid": installed_preflight.get("valid"),
            "preload_count": package_preflight.get("preload_count"),
            "readback_count": package_preflight.get("readback_count"),
            "runtime_d_absent": (
                package_preflight.get("formal_readback_targets_absent") is True
                and installed_preflight.get("formal_readback_targets_absent") is True
            ),
        },
        "execution": {
            "compile_exit_status": int(signal["compile_status"]),
            "simulation_exit_status": int(signal["simulation_status"]),
            "signal": signal["signal"],
            "natural_terminal": conjunction["natural_completion"],
            "simulation_seconds": (
                timing["final_epoch_ns"] - timing["sim_start_epoch_ns"]
            ) / 1e9,
            "exec_start_count": len(exec_events),
            "comp_finish_count": len(finishes),
            "completed_gconfig_words": [item["gconfig"] for item in finishes],
            "third_exec_gconfig": exec_events[2]["gconfig"],
        },
        "progress_adjudication": {
            "classification": "LONG_RUNNING_HANG_AT_OP_RELOCATION_PAD_D_WRITE",
            "third_stage": "op_relocation_pad",
            "first_heartbeat_deep": third_deep[0],
            "last_heartbeat_deep": third_deep[-1],
            "first_heartbeat_sg": third_sg[0],
            "last_heartbeat_sg": third_sg[-1],
            "qualified_counters_flat": flat,
            "flat_active_cycles": flat_cycles,
            "stall_window_cycles": 1_048_576,
            "complete_stall_windows": flat_cycles / 1_048_576,
            "canonical_record_rejected": canonical["decision"]
            == "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
            "canonical_defect": (
                "active_cycles and qualified counters were compared across "
                "three execution epochs; stale MSE input level/counter growth "
                "does not override stage-local flat DEEP/SG counters"
            ),
        },
        "first_divergence": {
            "last_good": (
                "op_a_dequant and op_b_dequant naturally COMP_FINISH; "
                "all six config preloads reached execution"
            ),
            "first_bad": (
                "op_relocation_pad issues MSE4 request channels (2,1), "
                "but write-data channels stop at (1,0), outstanding=(1,1)"
            ),
            "boundary": (
                "32-byte WRITE_STREAM0 transaction -> buffer5 D-row supply "
                "-> WR_Data_Channel"
            ),
        },
        "hang_root_cause": {
            "classification": "QADD_D_BUFFER_TRANSACTION_SUPPLY_UNDERSUPPLY",
            "v14_supply_records": old_supply,
            "causal_equation": "32B transaction != 1 row * 16B = 16B",
            "dynamic_match": (
                "one 16-byte write-data beat is accepted while the peer "
                "channel remains outstanding; index queue fills and GA output "
                "backpressures"
            ),
            "successor_supply_proof": fixed_supply,
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
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "config_numeric_analysis_repeated": False,
        "consumed_reuse_assets": True,
        "errors": errors,
    }


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
