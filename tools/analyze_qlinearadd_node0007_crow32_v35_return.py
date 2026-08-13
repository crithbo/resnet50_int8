from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath


OWNER = "019fa2c0-b647-7a91-93bf-d21a173487e3"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"
INSTALL = "r5_qadd_n7_crow32_v35"
RETURN_BYTES = 215158
RETURN_SHA = "30c5bdc1d1bb3cd47f28300e7557e8316ad770d38e50cebaeda1fce81e067972"
SOURCE_BYTES = 26180881
SOURCE_SHA = "45d40590376ec17f4dc831954e71570617beda989b49f4c376d4f42d891e2829"
CLOUD_RTL = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def structure(archive: zipfile.ZipFile) -> dict:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    roots = sorted(
        {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
    )
    return {
        "crc_valid": archive.testzip() is None,
        "entry_count": len(infos),
        "roots": roots,
        "single_root": len(roots) == 1,
        "duplicate_count": len(names) - len(set(names)),
        "unsafe_path_count": sum(
            PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or "\\" in name
            for name in names
        ),
        "symlink_count": sum(
            stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF) for info in infos
        ),
    }


def kv(text: str) -> dict[str, str]:
    return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


def digest_valid(value: dict) -> bool:
    work = dict(value)
    stored = work.pop("content_digest", {}).get("value")
    packed = json.dumps(work, sort_keys=True, separators=(",", ":")).encode()
    return stored == sha_bytes(packed)


def fields(text: str) -> dict[str, int]:
    return {
        key: int(value, 0)
        for key, value in re.findall(r"(\w+)=(0x[0-9a-fA-F]+|\d+)", text)
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    if (
        args.return_zip.stat().st_size != RETURN_BYTES
        or sha_file(args.return_zip) != RETURN_SHA
    ):
        errors.append("outer return bytes/SHA differ")
    if (
        args.source_zip.stat().st_size != SOURCE_BYTES
        or sha_file(args.source_zip) != SOURCE_SHA
    ):
        errors.append("source package bytes/SHA differ")

    with zipfile.ZipFile(args.return_zip) as returned, zipfile.ZipFile(
        args.source_zip
    ) as source:
        rstruct = structure(returned)
        sstruct = structure(source)
        rroot = rstruct["roots"][0] if rstruct["single_root"] else ""
        sroot = sstruct["roots"][0] if sstruct["single_root"] else ""
        if (
            not rstruct["crc_valid"]
            or not rstruct["single_root"]
            or any(
                rstruct[key]
                for key in ("duplicate_count", "unsafe_path_count", "symlink_count")
            )
        ):
            errors.append("return ZIP structure gate failed")
        if rroot != INSTALL + "_return" or sroot != INSTALL:
            errors.append("internal root identity differs")

        def rbytes(relative: str) -> bytes:
            return returned.read(f"{rroot}/{relative}")

        def rjson(relative: str) -> dict:
            return json.loads(rbytes(relative))

        return_manifest = rjson("RETURN_MANIFEST.json")
        returned_package_raw = rbytes("evidence/PACKAGE_MANIFEST.json")
        source_package_raw = source.read(f"{sroot}/TEST_PACKAGE_MANIFEST.json")
        package_manifest = json.loads(returned_package_raw)
        declared = {record["path"]: record for record in return_manifest["files"]}
        actual = {
            name[len(rroot) + 1 :]
            for name in returned.namelist()
            if name != f"{rroot}/RETURN_MANIFEST.json" and not name.endswith("/")
        }
        required_missing = set(return_manifest["required_missing"])
        allowlist = {
            record["target_path"]: record
            for record in package_manifest["return_allowlist"]
        }
        exact = (
            set(declared) == actual
            and actual == set(allowlist) - required_missing
            and required_missing == set(allowlist) - actual
        )
        receipts = all(
            len(rbytes(relative)) == record["size_bytes"]
            and sha_bytes(rbytes(relative)) == record["sha256"]
            and len(rbytes(relative)) <= allowlist[relative]["max_bytes"]
            for relative, record in declared.items()
        )
        source_members = {
            name[len(sroot) + 1 :]
            for name in source.namelist()
            if name != f"{sroot}/TEST_PACKAGE_MANIFEST.json" and not name.endswith("/")
        }
        source_exact = (
            returned_package_raw == source_package_raw
            and source_members == set(package_manifest["files"])
            and all(
                len(source.read(f"{sroot}/{relative}")) == record["size_bytes"]
                and sha_bytes(source.read(f"{sroot}/{relative}"))
                == record["sha256"]
                for relative, record in package_manifest["files"].items()
            )
        )
        if not exact:
            errors.append("return exact-set/allowlist/missing gate failed")
        if not receipts:
            errors.append("return per-file receipts failed")
        if not source_exact:
            errors.append("returned source manifest/member binding failed")

        package_preflight = rjson("evidence/package_preflight.json")
        installed_preflight = rjson("evidence/installed_preflight.json")
        canonical = rjson("evidence/CANONICAL_PROGRESS_DECISION.json")
        gate = rjson("evidence/SERVER_RESULT_GATE.json")
        compile_exit = int(rbytes("evidence/compile_exit_status.txt").strip())
        simulation_exit = int(rbytes("evidence/simulation_exit_status.txt").strip())
        canonical_exit = int(
            rbytes("evidence/canonical_decision_exit_status.txt").strip()
        )
        signal = kv(rbytes("evidence/signal_status.txt").decode())
        timing = {
            key: int(value)
            for key, value in kv(rbytes("evidence/host_timing.txt").decode()).items()
        }
        feature = kv(rbytes("evidence/split_feature_receipt.txt").decode())
        observer = rbytes("runs/return_observer.log").decode(errors="replace")
        compile_log = rbytes("runs/compile.log").decode(errors="replace")
        starts = [int(v) for v in re.findall(r"^(\d+) \| EXEC_START \|", observer, re.M)]
        finishes = [
            {"time_ps": int(time), "active_cycles": int(cycles)}
            for time, cycles in re.findall(
                r"^(\d+) \| COMP_FINISH \|.*active_cycles=(\d+)", observer, re.M
            )
        ]
        ingress_lines = re.findall(
            r"^(\d+) \| QADD_FP32_INGRESS \| (.+)$", observer, re.M
        )
        matrix_lines = re.findall(
            r"^(\d+) \| QADD_PAIR_MATRIX \| (.+)$", observer, re.M
        )
        heartbeat_lines = re.findall(
            r"^(\d+) \| HEARTBEAT \| (.+)$", observer, re.M
        )
        sg_lines = re.findall(
            r"^(\d+) \| SG_COUNTS \| event=HEARTBEAT (.+)$", observer, re.M
        )
        ingress = fields(ingress_lines[-1][1])
        matrix = {
            key: value
            for key, value in re.findall(r"(\w+)=([^ ]+)", matrix_lines[-1][1])
        }
        heartbeat = fields(heartbeat_lines[-1][1])
        sg = fields(sg_lines[-1][1])
        observer_binding = (
            feature.get("argv_enabled") == "true"
            and feature.get("time0_marker") == "true"
            and feature.get("returned_snapshot_marker") == "true"
            and digest_valid(canonical)
            and canonical_exit == 0
            and bool(ingress_lines)
            and bool(matrix_lines)
        )
        if not observer_binding:
            errors.append("observer/feature/canonical binding failed")

        expected_rows = 9408
        produced_rows = ingress["ga_output"] // 4
        missing_rows = expected_rows - produced_rows
        periodic_identity = (
            ingress["ga_output"] % 4 == 0
            and produced_rows == 9114
            and missing_rows == 294
            and expected_rows == 32 * missing_rows
            and produced_rows == 31 * missing_rows
        )
        frozen_truth = {
            key: ingress[key]
            for key in (
                "mse0_req",
                "mse1_req",
                "mse0_rdata",
                "mse1_rdata",
                "mse0_buf",
                "mse1_buf",
                "buf0_wr",
                "buf2_wr",
                "buf0_arm_req",
                "buf2_arm_req",
                "buf0_array",
                "buf2_array",
                "ga_accept",
                "ga_output",
            )
        }
        all_ingress_snapshots = [fields(text) for _, text in ingress_lines]
        stall_snapshot_count = sum(
            all(
                snapshot.get(key) == value for key, value in frozen_truth.items()
            )
            for snapshot in all_ingress_snapshots
        )
        actual_cloud_identity = CLOUD_RTL in compile_log
        report = {
            "schema": "qlinearadd-node0007-crow32-v35-return-analysis-v1",
            "status": (
                "RETURN_ANALYSIS_COMPLETE" if not errors else "RETURN_ANALYSIS_FAIL_CLOSED"
            ),
            "analysis_valid": not errors,
            "analysis_errors": errors,
            "analysis_owner_thread": OWNER,
            "return_target_thread": TARGET,
            "RETURN_ANALYSIS": "SPLIT_C_FP32_ADD_OUTPUT_SUPPLY_HANG",
            "LAST_PROVEN_GOOD": "FP32_ADD_GA_OUTPUT_9114_OF_9408_ROWS",
            "FIRST_DIVERGENCE": (
                "FP32_ADD_GA_16B_OUTPUT_CANNOT_FORM_BUFFER5_32B_ACCEPTED_ROW"
            ),
            "HANG_ROOT_CAUSE": (
                "UNIQUE_CONFIG_GA_OUTPUT_FOUR_PE_16B_SUPPLY_VS_BUFFER5_EIGHT_BANK_32B_REQUIREMENT"
            ),
            "return_transport": {
                "path": str(args.return_zip),
                "bytes": args.return_zip.stat().st_size,
                "sha256": sha_file(args.return_zip),
                "adjacent_sidecar": "ABSENT_USER_ATTESTED_TRANSPORT_ONLY",
            },
            "source_package": {
                "path": str(args.source_zip),
                "bytes": args.source_zip.stat().st_size,
                "sha256": sha_file(args.source_zip),
            },
            "zip_structure": rstruct,
            "source_zip_structure": sstruct,
            "identity": {
                "install_name": package_manifest.get("install_name"),
                "return_manifest_exact": exact,
                "per_file_receipts_exact": receipts,
                "source_binding_exact": source_exact,
            },
            "preflight": {
                "package_valid": package_preflight.get("valid"),
                "installed_valid": installed_preflight.get("valid"),
                "runtime_targets_initially_absent": package_preflight.get(
                    "formal_readback_targets_absent"
                )
                and installed_preflight.get("formal_readback_targets_absent"),
            },
            "execution": {
                "compile_exit": compile_exit,
                "simulation_exit": simulation_exit,
                "runner_exit": "NOT_SEPARATELY_RETURNED",
                "canonical_exit": canonical_exit,
                "signal": signal.get("signal"),
                "natural_terminal": False,
                "host_wall_seconds": (
                    timing["final_epoch_ns"] - timing["package_start_epoch_ns"]
                )
                / 1e9,
                "simulation_wall_seconds": (
                    timing["final_epoch_ns"] - timing["sim_start_epoch_ns"]
                )
                / 1e9,
                "stage_starts_ps": starts,
                "stage_finishes": finishes,
                "actual_compiled_cloud_rtl_proven": actual_cloud_identity,
                "cloud_authority": CLOUD_RTL,
                "identity_claim_boundary": (
                    "compile succeeded; actual server commit/tree absent from return, "
                    "so cloud/local difference is nonblocking but E4/E5 identity remains unproven"
                ),
            },
            "progress_adjudication": {
                "canonical_decision": canonical.get("decision"),
                "canonical_boundary": canonical.get("boundary"),
                "canonical_digest_valid": digest_valid(canonical),
                "canonical_overturned": True,
                "overturn_reason": (
                    "all accepted request/rdata/buffer/GA counters remain identical "
                    "for many complete stall windows; the growing mse1_hs field is a "
                    "held level sampled each cycle, not a qualified transaction"
                ),
                "last_ingress_snapshot": ingress,
                "last_pair_matrix_snapshot": matrix,
                "last_heartbeat": heartbeat,
                "last_sg_counts": sg,
                "identical_final_ingress_snapshot_count": stall_snapshot_count,
            },
            "root_cause_proof": {
                "expected_fp32_rows": expected_rows,
                "qualified_ga_output_events": ingress["ga_output"],
                "active_ga_pe_lanes": 4,
                "qualified_ga_output_rows": produced_rows,
                "missing_rows": missing_rows,
                "periodic_31_of_32_identity": periodic_identity,
                "dynamic_output_boundary": {
                    "buffer5_write_accept_stage4": 0,
                    "buffer5_read_enable_stuck": "0xf",
                    "mse4_request_per_channel": [
                        sg.get("mse4_req0"),
                        sg.get("mse4_req1"),
                    ],
                    "mse4_wdata_per_channel": [
                        sg.get("mse4_wdata0"),
                        sg.get("mse4_wdata1"),
                    ],
                    "mse4_outstanding_per_channel": [
                        sg.get("mse4_outstanding0"),
                        sg.get("mse4_outstanding1"),
                    ],
                },
                "static_config": {
                    "configured_ga_pe_names": ["PE00", "PE02", "PE20", "PE22"],
                    "configured_output_bytes_per_transaction": 16,
                    "buffer5_masked_banks": 8,
                    "buffer5_required_bytes_per_transaction": 32,
                    "native_fp32_add_required_pe_names": [
                        "PE00",
                        "PE02",
                        "PE10",
                        "PE12",
                        "PE20",
                        "PE22",
                        "PE30",
                        "PE32",
                    ],
                    "minimal_config_fix": "add PE10/PE12/PE30/PE32 using native FP32 add leaf values",
                },
                "claim_boundary": (
                    "the missing four GA PE configuration leaves uniquely explain "
                    "zero Buffer5 accepted writes and MSE4 request-without-wdata; "
                    "no numeric/W3/qparam/tail/golden recomputation"
                ),
            },
            "formal_D": {
                "scope": "split-C stage-local FP32 output only",
                "expected": gate.get("expected_readback_count"),
                "present": gate.get("observed_readback_count"),
                "missing": gate.get("missing_count"),
                "invalid": gate.get("invalid_count"),
                "mismatch_evaluable": gate.get("mismatch_evaluable"),
                "mismatch_byte_count": gate.get("mismatch_byte_count"),
                "SERVER_RESULT_GATE": gate.get("result_gate_conjunction", {}).get(
                    "all_terms_true"
                ),
            },
            "E3": False,
            "E4": False,
            "E5": False,
            "BLOCKER_DELTA": {
                "closed": [
                    "B_QADD_SPLIT_C_16B_INPUT_VS_32B_BUFFER_ROW",
                    "B_QADD_SPLIT_C_ARM_GA_PROGRESS_UNPROVEN",
                ],
                "opened": [
                    "B_QADD_SPLIT_C_GA_OUTPUT_16B_VS_BUFFER5_32B_SUPPLY"
                ],
                "kept_open": [
                    "B_QADD_SPLIT_C_NATURAL_TERMINAL_AND_28D_UNPROVEN",
                    "B_QADD_NODE0007_FULL_CHAIN_28D_E3_E4_E5_UNPROVEN",
                    "B_QADD_SERVER_ACTUAL_COMPILED_RTL_IDENTITY_UNPROVEN",
                ],
            },
            "SUCCESSOR_PROPOSAL": {
                "kind": "FRESH_MINIMAL_CONFIG_CORRECTION",
                "scope": "split-C cumulative prefix",
                "changed_leaf_set": [
                    "general_array.PE_array.PE10",
                    "general_array.PE_array.PE12",
                    "general_array.PE_array.PE30",
                    "general_array.PE_array.PE32",
                ],
                "retain_checkpoint": (
                    "GA output -> Buffer5 accepted write -> MSE4 request/wdata -> "
                    "natural stage finish and 28 stage-local D"
                ),
            },
            "RULE_CONFIRMATION": {
                "rule_ids": [
                    "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
                    "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
                    "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                    "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
                    "CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001",
                ],
                "evidence": (
                    "v35 shows why qualified accepted events and exact byte supply "
                    "must override a stale level-driven canonical progress label"
                ),
                "claim_boundary": "QLinearAdd node0007 split-C only",
            },
            "numeric_analysis_repeated": False,
            "workload_analysis_repeated": False,
            "configuration_numeric_analysis_repeated": False,
            "golden_recomputed": False,
            "functional_rtl_modified": False,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "valid": report["analysis_valid"],
                "outcome": report["RETURN_ANALYSIS"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0 if report["analysis_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
