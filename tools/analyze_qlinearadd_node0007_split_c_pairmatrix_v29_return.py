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
INSTALL = "r5_qadd_n7_split_c_pairmatrix_v29"
RETURN_BYTES = 209242
RETURN_SHA = "3839a9985f18483db4a4a784dbc7169103b4168b2a8eb4d3d11df07a96cbe1ff"
SOURCE_BYTES = 26171333
SOURCE_SHA = "c92985b32e31c30ffcb023a6b637a6b059748e5395e2eabac2a65e3ae79c0af3"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def structure(zf: zipfile.ZipFile) -> dict:
    infos = zf.infolist()
    names = [info.filename for info in infos]
    roots = sorted(
        {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
    )
    return {
        "crc_valid": zf.testzip() is None,
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


def canonical_digest_valid(value: dict) -> bool:
    work = dict(value)
    stored = work.pop("content_digest", {}).get("value")
    packed = json.dumps(work, sort_keys=True, separators=(",", ":")).encode()
    return stored == sha_bytes(packed)


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
        errors.append("source bytes/SHA differ")
    with zipfile.ZipFile(args.return_zip) as returned, zipfile.ZipFile(
        args.source_zip
    ) as source:
        rstruct, sstruct = structure(returned), structure(source)
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
        package_raw = rbytes("evidence/PACKAGE_MANIFEST.json")
        source_package_raw = source.read(f"{sroot}/TEST_PACKAGE_MANIFEST.json")
        package_manifest = json.loads(package_raw)
        declared = {entry["path"]: entry for entry in return_manifest["files"]}
        actual = {
            name[len(rroot) + 1 :]
            for name in returned.namelist()
            if name != f"{rroot}/RETURN_MANIFEST.json" and not name.endswith("/")
        }
        required_missing = set(return_manifest["required_missing"])
        allowlist = {
            entry["target_path"]: entry
            for entry in package_manifest["return_allowlist"]
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
            package_raw == source_package_raw
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
            errors.append("per-file return receipts failed")
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
        starts = [int(value) for value in re.findall(r"^(\d+) \| EXEC_START \|", observer, re.M)]
        finishes = [
            (int(time), int(cycles))
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
        ingress = {
            key: int(value, 0)
            for key, value in re.findall(
                r"(\w+)=(0x[0-9a-fA-F]+|\d+)", ingress_lines[-1][1]
            )
        }
        matrix = {
            key: value
            for key, value in re.findall(r"(\w+)=([^ ]+)", matrix_lines[-1][1])
        }
        actual_rtl_identity = (
            "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d" in compile_log
        )
        observer_binding = (
            feature
            == {
                "feature": "QADD_SPLIT_C_FP32_INGRESS",
                "argv_enabled": "true",
                "time0_marker": "true",
                "returned_snapshot_marker": "true",
            }
            and canonical_digest_valid(canonical)
            and canonical_exit == 0
            and ingress_lines
            and matrix_lines
        )
        if not observer_binding:
            errors.append("observer/feature/canonical binding failed")
        report = {
            "schema": "qlinearadd-node0007-split-c-pairmatrix-v29-return-analysis-v1",
            "status": "RETURN_ANALYSIS_COMPLETE" if not errors else "RETURN_ANALYSIS_FAIL_CLOSED",
            "analysis_valid": not errors,
            "analysis_errors": errors,
            "analysis_owner_thread": OWNER,
            "return_target_thread": TARGET,
            "RETURN_ANALYSIS": "SPLIT_C_REACHED_FP32_ADD_AND_HUNG_BEFORE_FIRST_BUFFER_ARM_ACCEPT",
            "LAST_PROVEN_GOOD": "FP32_ADD_MSE0_MSE1_16B_BUFFER_WRITE_ACCEPTED",
            "FIRST_DIVERGENCE": "FP32_ADD_BUFFER0_BUFFER2_ARM_READ_ACCEPT_REMAINS_ZERO",
            "HANG_ROOT_CAUSE": "UNIQUE_CONFIG_INPUT_BUFFER_TRANSACTION_SUPPLY_MISMATCH_16B_PRODUCED_VS_32B_MASKED_ROW_REQUIRED",
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
                "stage_finishes": [
                    {"time_ps": time, "active_cycles": cycles}
                    for time, cycles in finishes
                ],
                "actual_compiled_rtl_e1fb0f7_proven": actual_rtl_identity,
                "actual_compiled_rtl_claim_boundary": (
                    "compile succeeded, but the return contains no commit/tree receipt"
                    if not actual_rtl_identity
                    else "compile log directly names e1fb0f7"
                ),
            },
            "canonical_adjudication": {
                "decision": canonical.get("decision"),
                "boundary": canonical.get("boundary"),
                "reason": canonical.get("reason"),
                "digest_valid": canonical_digest_valid(canonical),
                "counter_snapshot": canonical.get("counter_snapshot"),
                "qualified_stall_cycles": canonical.get("content_summary", {}).get(
                    "flat_qualified_cycles"
                ),
            },
            "last_ingress_snapshot": ingress,
            "last_pair_matrix_snapshot": matrix,
            "root_cause_proof": {
                "dynamic": {
                    "mse0_mse1_request_accept": [ingress["mse0_req"], ingress["mse1_req"]],
                    "mse0_mse1_rdata_accept": [
                        ingress["mse0_rdata"],
                        ingress["mse1_rdata"],
                    ],
                    "mse0_mse1_buffer_accept": [
                        ingress["mse0_buf"],
                        ingress["mse1_buf"],
                    ],
                    "buffer0_buffer2_write_accept": [
                        ingress["buf0_wr"],
                        ingress["buf2_wr"],
                    ],
                    "buffer0_buffer2_any_valid": ingress["buf_valid"],
                    "buffer0_buffer2_arm_ready": ingress["buf_arm_ready"],
                    "buffer0_buffer2_arm_accept": [
                        ingress["buf0_arm_req"],
                        ingress["buf2_arm_req"],
                    ],
                    "ga_capture_pair_accept_output": [
                        ingress["ga0_capture"],
                        ingress["ga1_capture"],
                        ingress["ga_pair"],
                        ingress["ga_accept"],
                        ingress["ga_output"],
                    ],
                },
                "final_config": {
                    "input_transaction_bytes": 16,
                    "input_buffer_ag_column_windows": [[0, 16]],
                    "buffer_mask_banks": 8,
                },
                "active_rtl_equation": (
                    "buf2arm_rreq_ready = & (~buffer_mask | "
                    "(&valid_buf[bank][row] & ~arm_clear_reg[row]))"
                ),
                "physical_requirement": "8 banks * 4 valid bytes = 32B row",
                "native_fp32_add_crosscheck": (
                    "decode_add_fp32N_fp32N_fp32N.json uses a 32B transaction "
                    "and Buffer_AG columns 0,16 for A, B and D"
                ),
                "authorized_minimal_fix": (
                    "for op_fp32_add, use 32B stream0/1/2 transactions, "
                    "two 16B Buffer_AG columns, and halve inner LC occurrences "
                    "18816->9408 while preserving 8*9408*32=2408448 bytes"
                ),
            },
            "formal_D": {
                "expected": 28,
                "present": gate.get("observed_readback_count"),
                "missing": gate.get("missing_count"),
                "invalid": gate.get("invalid_count"),
                "mismatch_evaluable": False,
                "SERVER_RESULT_GATE": False,
            },
            "E3": False,
            "E4": False,
            "E5": False,
            "BLOCKER_DELTA": {
                "closed": [
                    "B_QADD_SPLIT_C_FP32_TARGET_NOT_REACHED",
                    "B_QADD_SPLIT_C_PAIRED_INGRESS_ROOT_CAUSE_UNRESOLVED",
                ],
                "opened": [
                    "B_QADD_FP32_ADD_INPUT_BUFFER_TRANSACTION_SUPPLY_CONSERVATION"
                ],
                "kept_open": [
                    "B_QADD_SPLIT_C_FP32_PREFIX_DYNAMIC_PASS_UNPROVEN",
                    "B_QADD_NODE0007_FULL_CHAIN_28D_DYNAMIC_PASS_UNPROVEN",
                    "B_QADD_SERVER_ACTUAL_COMPILED_RTL_IDENTITY_UNPROVEN",
                ],
            },
            "successor": {
                "kind": "FRESH_CONFIG_CORRECTION",
                "claim": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
                "must_retain_low_cost_boundary": (
                    "MSE0/MSE1 -> Buffer0/2 arm accept -> GA pair/output"
                ),
            },
            "RULE_DELTA_PROPOSAL": {
                "suggested_id": "CDA-QADD-A-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001",
                "evidence": (
                    "v29 proves one 16B accepted write cannot satisfy an 8-bank "
                    "32B Buffer0/2 ARM read mask"
                ),
                "scope": (
                    "QLinearAdd read-side Buffer0/2 transaction/window/mask "
                    "conservation; symmetric to the existing D-buffer rule"
                ),
                "negative_control": (
                    "restore one [0,16) input window while keeping all-8-bank mask; "
                    "validator must fail closed"
                ),
                "claim_boundary": "proposal only; mainline owns rule publication",
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
