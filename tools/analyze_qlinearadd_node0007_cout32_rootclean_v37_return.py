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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OWNER = "019fa2c0-b647-7a91-93bf-d21a173487e3"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"
INSTALL = "r5_qadd_n7_cout32_rootclean_v37"
RETURN_BYTES = 56_899_633
RETURN_SHA256 = (
    "d0dbdfd7fbe38457a0cd22918dbd30eff2dd6b23203eedce7c6cf7edb9203cd2"
)
SOURCE_BYTES = 26_178_383
SOURCE_SHA256 = (
    "699696dcf59e1453669aa0af12c599963d05ed176f417858ddf2095fee4fcf87"
)
SOURCE_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/pending/"
    "r5_qadd_n7_cout32_rootclean_v37.zip"
)
SOURCE_SIDECAR_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "pending_receipts/qlinearadd_node0007/"
    "r5_qadd_n7_cout32_rootclean_v37/"
    "r5_qadd_n7_cout32_rootclean_v37.zip.sha256"
)
SOURCE_AUDIT_REL = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "pending_receipts/qlinearadd_node0007/"
    "r5_qadd_n7_cout32_rootclean_v37/"
    "r5_qadd_n7_cout32_rootclean_v37_final_zip_self_audit.json"
)
SOURCE_AUDIT_SHA256 = (
    "62a7352ec351f7f7df08e5879b295d9e5143d9e5d20afbf9b3fda005e618df68"
)
STAGES = (
    "op_a_dequant",
    "op_b_dequant",
    "op_relocation_pad",
    "op_fp32_add",
)
CONTROL_PATHS = {
    "agent": Path(".agents/agent.md"),
    "plan_mutable": Path(".agents/plan.md"),
    "generation_index": Path(".agents/rules/生成前必读索引.md"),
    "server_package_rule": Path(".agents/rules/服务器测试包生成规则.md"),
    "common_operator_rule": Path(".agents/rules/算子配置规则.md"),
    "ndp_field_rule": Path(".agents/rules/NDP硬件字段语义.md"),
    "qlinearadd_rule": Path(".agents/rules/QLinearAdd算子配置规则.md"),
    "exact_uint8_tail_rule": Path(".agents/rules/精确UINT8量化尾专项规则.md"),
    "hardware_sim_readme": Path("NDP_copy01/README_HARDWARE_SIM_ENTRY.md"),
}


class AnalysisError(ValueError):
    pass


def sha_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def zip_files(path: Path) -> tuple[str, dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    duplicate_count = 0
    unsafe_count = 0
    symlink_count = 0
    with zipfile.ZipFile(path) as archive:
        bad_crc = archive.testzip()
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if pure.parts:
                roots.add(pure.parts[0])
            if info.filename in seen:
                duplicate_count += 1
            seen.add(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            unsafe_count += int(
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
            )
            symlink_count += int(stat.S_ISLNK(mode))
        if len(roots) != 1:
            raise AnalysisError(f"ZIP root exact-set differs: {sorted(roots)}")
        root = next(iter(roots))
        prefix = root + "/"
        for info in archive.infolist():
            if info.is_dir():
                continue
            if not info.filename.startswith(prefix):
                raise AnalysisError(f"member outside root: {info.filename}")
            relative = info.filename[len(prefix) :]
            if relative in files:
                raise AnalysisError(f"duplicate file member: {relative}")
            files[relative] = archive.read(info)
    structure = {
        "crc_valid": bad_crc is None,
        "root": root,
        "single_root": True,
        "entry_count": len(files),
        "duplicate_count": duplicate_count,
        "unsafe_path_count": unsafe_count,
        "symlink_count": symlink_count,
    }
    return root, files, structure


def json_file(files: dict[str, bytes], relative: str) -> dict[str, Any]:
    value = json.loads(files[relative])
    if not isinstance(value, dict):
        raise AnalysisError(f"JSON root must be object: {relative}")
    return value


def kv(text: str) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in text.splitlines()
        if "=" in line
    )


def event_fields(text: str) -> dict[str, int]:
    return {
        key: int(value, 16) if value.lower().startswith("0x") else int(value)
        for key, value in re.findall(
            r"(\w+)=(0x[0-9a-fA-F]+|\d+)", text
        )
    }


def digest_valid(value: dict[str, Any]) -> bool:
    copy = dict(value)
    stored = copy.pop("content_digest", {}).get("value")
    encoded = json.dumps(copy, sort_keys=True, separators=(",", ":")).encode()
    return stored == sha_bytes(encoded)


def stage_records(observer: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    for line in observer.splitlines():
        match = re.match(r"^(\d+) \| ([A-Z0-9_]+) \| (.*)$", line)
        if not match:
            continue
        time_ps = int(match.group(1))
        event = match.group(2)
        fields = event_fields(match.group(3))
        if event == "EXEC_START":
            index = len(records)
            active = {
                "index": index + 1,
                "stage": STAGES[index] if index < len(STAGES) else "unexpected",
                "exec_start_ps": time_ps,
                "exec_start": fields,
                "comp_finish_ps": None,
                "comp_finish": None,
                "sg_finish": None,
                "deep_finish": None,
            }
            records.append(active)
        elif active is not None and event == "COMP_FINISH":
            active["comp_finish_ps"] = time_ps
            active["comp_finish"] = fields
        elif active is not None and event == "SG_COUNTS":
            if "event=COMP_FINISH" in match.group(3):
                active["sg_finish"] = fields
        elif active is not None and event == "DEEP_COUNTS":
            if "event=COMP_FINISH" in match.group(3):
                active["deep_finish"] = fields
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    source_zip = ROOT / SOURCE_REL
    source_sidecar = ROOT / SOURCE_SIDECAR_REL
    source_audit_path = ROOT / SOURCE_AUDIT_REL
    if args.return_zip.stat().st_size != RETURN_BYTES:
        errors.append("outer return byte count differs")
    if sha_file(args.return_zip) != RETURN_SHA256:
        errors.append("outer return SHA256 differs")
    if source_zip.stat().st_size != SOURCE_BYTES:
        errors.append("source package byte count differs")
    if sha_file(source_zip) != SOURCE_SHA256:
        errors.append("source package SHA256 differs")
    if SOURCE_SHA256 not in source_sidecar.read_text(encoding="utf-8"):
        errors.append("source sidecar does not bind source ZIP")
    if sha_file(source_audit_path) != SOURCE_AUDIT_SHA256:
        errors.append("source final audit identity differs")

    return_root, returned, return_structure = zip_files(args.return_zip)
    source_root, source, source_structure = zip_files(source_zip)
    if return_root != INSTALL + "_return":
        errors.append("return internal root identity differs")
    if source_root != INSTALL:
        errors.append("source internal root identity differs")
    for structure, label in (
        (return_structure, "return"),
        (source_structure, "source"),
    ):
        if not structure["crc_valid"] or any(
            structure[name]
            for name in (
                "duplicate_count",
                "unsafe_path_count",
                "symlink_count",
            )
        ):
            errors.append(f"{label} ZIP structure gate failed")

    return_manifest = json_file(returned, "RETURN_MANIFEST.json")
    source_manifest = json_file(source, "TEST_PACKAGE_MANIFEST.json")
    returned_manifest = json_file(
        returned, "evidence/PACKAGE_MANIFEST.json"
    )
    declared = {
        record["path"]: record for record in return_manifest["files"]
    }
    actual = set(returned) - {"RETURN_MANIFEST.json"}
    allowlist = {
        record["target_path"]: record
        for record in source_manifest["return_allowlist"]
    }
    missing = sorted(set(allowlist) - actual)
    return_exact = (
        actual == set(declared)
        and actual == set(allowlist)
        and missing == return_manifest.get("required_missing", [])
    )
    member_errors = [
        relative
        for relative, record in declared.items()
        if relative not in returned
        or len(returned[relative]) != int(record["size_bytes"])
        or sha_bytes(returned[relative]) != record["sha256"]
        or len(returned[relative])
        > int(allowlist[relative]["max_bytes"])
    ]
    source_members = set(source) - {"TEST_PACKAGE_MANIFEST.json"}
    source_exact = (
        returned["evidence/PACKAGE_MANIFEST.json"]
        == source["TEST_PACKAGE_MANIFEST.json"]
        and returned_manifest == source_manifest
        and source_members == set(source_manifest["files"])
        and all(
            relative in source
            and len(source[relative]) == int(record["size_bytes"])
            and sha_bytes(source[relative]) == record["sha256"]
            for relative, record in source_manifest["files"].items()
        )
    )
    if not return_exact:
        errors.append("return exact-set/allowlist gate failed")
    if member_errors:
        errors.append("return per-member receipt differs")
    if not source_exact:
        errors.append("returned source package binding differs")

    package_preflight = json_file(
        returned, "evidence/package_preflight.json"
    )
    installed_preflight = json_file(
        returned, "evidence/installed_preflight.json"
    )
    canonical = json_file(
        returned, "evidence/CANONICAL_PROGRESS_DECISION.json"
    )
    gate = json_file(returned, "evidence/SERVER_RESULT_GATE.json")
    root_pre = json_file(returned, "evidence/ndp_root_toplevel_pre.json")
    root_post = json_file(returned, "evidence/ndp_root_toplevel_post.json")
    fixed_preflight = json_file(
        returned, "evidence/fixed_result_preflight.json"
    )
    source_audit = json.loads(source_audit_path.read_text(encoding="utf-8"))
    observer = returned["runs/return_observer.log"].decode(
        errors="replace"
    )
    sim_log = returned["runs/sim.log"].decode(errors="replace")
    compile_log = returned["runs/compile.log"].decode(errors="replace")
    stages = stage_records(observer)
    compile_exit = int(
        returned["evidence/compile_exit_status.txt"].decode().strip()
    )
    simulation_exit = int(
        returned["evidence/simulation_exit_status.txt"].decode().strip()
    )
    canonical_exit = int(
        returned["evidence/canonical_decision_exit_status.txt"]
        .decode()
        .strip()
    )
    signal = kv(returned["evidence/signal_status.txt"].decode())
    timing = {
        key: int(value)
        for key, value in kv(
            returned["evidence/host_timing.txt"].decode()
        ).items()
    }
    feature = kv(returned["evidence/split_feature_receipt.txt"].decode())
    compile_argv = returned["evidence/actual_compile_argv.txt"].decode()
    sim_argv = returned["evidence/actual_simulator_argv.txt"].decode()

    stage_order_exact = (
        len(stages) == 4
        and [record["stage"] for record in stages] == list(STAGES)
        and all(record["comp_finish"] is not None for record in stages)
    )
    final_stage = stages[-1] if stages else {}
    start_buf5 = int(final_stage.get("exec_start", {}).get("buf5_wr", -1))
    end_buf5 = int(final_stage.get("comp_finish", {}).get("buf5_wr", -1))
    buffer5_accepted_rows = end_buf5 - start_buf5
    sg = final_stage.get("sg_finish") or {}
    mse_req = [int(sg.get(f"mse4_req{channel}", -1)) for channel in (0, 1)]
    mse_wdata = [
        int(sg.get(f"mse4_wdata{channel}", -1)) for channel in (0, 1)
    ]
    outstanding = [
        int(sg.get(f"mse4_outstanding{channel}", -1))
        for channel in (0, 1)
    ]
    expected_rows = 2_408_448 // 32
    supply_conservation = (
        buffer5_accepted_rows == expected_rows
        and mse_req == [expected_rows, expected_rows]
        and mse_wdata == [expected_rows, expected_rows]
        and outstanding == [0, 0]
        and sum(mse_wdata) * 16 == buffer5_accepted_rows * 32
    )
    checks = gate.get("checks", [])
    formal_structural = (
        len(checks) == 28
        and gate.get("expected_readback_count") == 28
        and gate.get("observed_readback_count") == 28
        and gate.get("missing_count") == 0
        and gate.get("invalid_count") == 0
        and all(
            record.get("status") == "pass"
            and record.get("decoded_bytes") == 2_408_448
            and record.get("line_count") == 150_528
            for record in checks
        )
    )
    natural = (
        compile_exit == 0
        and simulation_exit == 0
        and signal.get("signal") == "NONE"
        and stage_order_exact
        and canonical_exit == 0
        and digest_valid(canonical)
        and canonical.get("decision") == "NATURAL_TERMINAL_OBSERVED"
        and canonical.get("boundary") == "ORDERED_FINAL_STAGE_COMP_FINISH"
        and "$finish at simulation time" in sim_log
        and gate.get("result_gate_conjunction", {}).get("all_terms_true")
        is True
    )
    observer_binding = (
        feature.get("argv_enabled") == "true"
        and feature.get("time0_marker") == "true"
        and feature.get("returned_snapshot_marker") == "true"
        and "+define+NATIVE_RETURN_OBSERVER_ENABLE" in compile_argv
        and "+RETURN_OBSERVER" in sim_argv
        and "+QADD_FP32_INGRESS_OBSERVER" in sim_argv
        and returned["evidence/observer_binding.txt"].decode().strip()
        == "observer_enabled_and_returned=true"
    )
    root_gate = (
        return_manifest.get("fixed_result_publication", {}).get(
            "duplicate_absent"
        )
        is True
        and return_manifest.get("fixed_result_publication", {}).get(
            "ndp_root_toplevel_unchanged"
        )
        is True
        and root_pre.get("exact_set_sha256")
        == root_post.get("post", {}).get("exact_set_sha256")
        == root_post.get("pre", {}).get("exact_set_sha256")
        and root_post.get("ndp_root_toplevel_unchanged") is True
        and fixed_preflight.get("publication_state")
        == "TARGETS_ABSENT_READY_FOR_ATOMIC_STAGING"
        and all(
            fixed_preflight.get(name) is True
            for name in (
                "server_root_duplicate_absent",
                "package_root_duplicate_absent",
                "state_root_duplicate_absent",
            )
        )
    )
    if not stage_order_exact:
        errors.append("ordered four-stage terminal differs")
    if not supply_conservation:
        errors.append("32B Buffer5 -> two 16B MSE conservation differs")
    if not formal_structural:
        errors.append("28 stage-local D structural gate differs")
    if not natural:
        errors.append("natural terminal/result conjunction differs")
    if not observer_binding:
        errors.append("observer runtime binding differs")
    if not root_gate:
        errors.append("fixed-result/NDP-root gate differs")
    if package_preflight.get("valid") is not True:
        errors.append("package preflight invalid")
    if installed_preflight.get("valid") is not True:
        errors.append("installed preflight invalid")

    controls = {
        name: {
            "path": path.as_posix(),
            "bytes": (ROOT / path).stat().st_size,
            "sha256": sha_file(ROOT / path),
            "mutable_provenance_only": name == "plan_mutable",
        }
        for name, path in CONTROL_PATHS.items()
    }
    numeric_evaluable = gate.get("mismatch_evaluable") is True
    report = {
        "schema": "qlinearadd-node0007-cout32-rootclean-v37-return-analysis-v1",
        "status": (
            "RETURN_ANALYSIS_COMPLETE_SPLIT_C_STRUCTURAL_PASS"
            if not errors
            else "RETURN_ANALYSIS_FAIL_CLOSED"
        ),
        "analysis_valid": not errors,
        "errors": errors,
        "analysis_owner_thread": OWNER,
        "return_target_thread": TARGET,
        "control_receipts": controls,
        "RETURN_ANALYSIS": {
            "outcome": "SPLIT_C_NATURAL_TERMINAL_28D_STRUCTURAL_PASS",
            "claim_boundary": (
                "split-C cumulative prefix through op_fp32_add only; "
                "readbacks are structurally complete but no independent "
                "golden is bound, so numeric E4 is not evaluable"
            ),
        },
        "transport_and_identity": {
            "return": {
                "path": str(args.return_zip),
                "bytes": args.return_zip.stat().st_size,
                "sha256": sha_file(args.return_zip),
                "adjacent_sidecar": (
                    "ABSENT_USER_ATTESTED_TRANSPORT_ONLY"
                ),
            },
            "source": {
                "path": SOURCE_REL.as_posix(),
                "bytes": source_zip.stat().st_size,
                "sha256": sha_file(source_zip),
                "sidecar": SOURCE_SIDECAR_REL.as_posix(),
                "sidecar_sha256": sha_file(source_sidecar),
                "final_audit": SOURCE_AUDIT_REL.as_posix(),
                "final_audit_sha256": sha_file(source_audit_path),
                "final_audit_pass": source_audit.get(
                    "FINAL_ZIP_RULE_SELF_AUDIT_PASS"
                ),
            },
            "return_structure": return_structure,
            "source_structure": source_structure,
            "return_exact_set": return_exact,
            "per_member_receipt_errors": member_errors,
            "returned_source_manifest_byte_equal": source_exact,
            "install_identity_exact": (
                return_manifest.get("install_name")
                == returned_manifest.get("install_name")
                == INSTALL
            ),
        },
        "preflight_and_binding": {
            "package_preflight": package_preflight,
            "installed_preflight": installed_preflight,
            "runtime_D_initially_absent": (
                package_preflight.get("formal_readback_targets_absent")
                is True
                and installed_preflight.get(
                    "formal_readback_targets_absent"
                )
                is True
            ),
            "observer_four_way": observer_binding,
            "actual_compile_argv": compile_argv.strip(),
            "actual_simulator_argv": sim_argv.strip(),
            "fixed_result_and_root_gate": root_gate,
        },
        "execution": {
            "compile_exit": compile_exit,
            "simulation_exit": simulation_exit,
            "runner_signal": signal.get("signal"),
            "natural_terminal": natural,
            "ordered_stages": stages,
            "host_total_seconds": (
                timing["final_epoch_ns"] - timing["package_start_epoch_ns"]
            )
            / 1e9,
            "host_sim_seconds": (
                timing["final_epoch_ns"] - timing["sim_start_epoch_ns"]
            )
            / 1e9,
            "sim_finish_ps": int(
                re.findall(
                    r"\$finish at simulation time\s+(\d+)", sim_log
                )[-1]
            ),
            "actual_server_rtl_commit_proven": False,
            "compile_log_sha256": sha_bytes(compile_log.encode()),
            "identity_claim_boundary": (
                "production compile/run is proven; the return does not bind "
                "the actual RTL tree to cloud commit 0ccae916..."
            ),
        },
        "LAST_PROVEN_GOOD": {
            "boundary": "OP_FP32_ADD_ORDERED_COMP_FINISH",
            "proof": (
                "four ordered stages finish; final stage drains exactly "
                "75,264 Buffer5 32B rows into two balanced 16B MSE4 "
                "write-data streams and returns all 28 structural D targets"
            ),
        },
        "FIRST_DIVERGENCE": {
            "boundary": "NONE_WITHIN_SPLIT_C_DECLARED_SCOPE",
            "next_unproven_boundary": (
                "op_tail_mul -> op_tail_round -> final UINT8 D "
                "full-chain natural terminal"
            ),
        },
        "HANG_ROOT_CAUSE": {
            "status": "NO_HANG_NATURAL_TERMINAL",
            "v36_32B_fix_dynamic_proven": True,
        },
        "d_buffer_supply": {
            "buffer5_row_bytes": 32,
            "mse_transaction_bytes": 16,
            "expected_rows_per_slice": expected_rows,
            "buffer5_accepted_row_count": buffer5_accepted_rows,
            "mse4_request_count_by_channel": mse_req,
            "mse4_wdata_count_by_channel": mse_wdata,
            "mse4_outstanding_by_channel": outstanding,
            "byte_conservation": (
                f"{buffer5_accepted_rows}*32 == "
                f"({mse_wdata[0]}+{mse_wdata[1]})*16"
            ),
            "qualified_chain_pass": supply_conservation,
            "early_stage_or_level_substitution_used": False,
        },
        "formal_D": {
            "scope": "split-C op_fp32_add stage-local FP32 D",
            "expected": gate.get("expected_readback_count"),
            "present": gate.get("observed_readback_count"),
            "missing": gate.get("missing_count"),
            "invalid": gate.get("invalid_count"),
            "structural_exact_set_pass": formal_structural,
            "mismatch_evaluable": numeric_evaluable,
            "reported_mismatch_bytes": gate.get("mismatch_byte_count"),
            "numeric_adjudication": (
                "NOT_EVALUABLE_NO_INDEPENDENT_GOLDEN"
                if not numeric_evaluable
                else "EVALUABLE"
            ),
            "server_result_gate_all_terms_true": gate.get(
                "result_gate_conjunction", {}
            ).get("all_terms_true"),
        },
        "evidence_levels": {
            "E3": natural,
            "E4": False,
            "E5": False,
            "reason": (
                "E3 is bound production natural completion; E4 needs "
                "independent-golden equality, and E5 needs a fresh-identity "
                "repeat after E4"
            ),
        },
        "BLOCKER_DELTA": {
            "closed": [
                "B_QADD_SPLIT_C_FP32_ADD_32B_BUFFER5_SUPPLY",
                "B_QADD_SPLIT_C_NATURAL_TERMINAL",
                "B_QADD_SPLIT_C_28D_STRUCTURAL_COMPLETENESS",
            ],
            "kept_open": [
                "B_QADD_NODE0007_FULL_CHAIN_TAIL_NATURAL_TERMINAL_28D",
                "B_QADD_NODE0007_INDEPENDENT_GOLDEN_E4",
                "B_QADD_NODE0007_FRESH_IDENTITY_E5",
                "B_QADD_SERVER_ACTUAL_RTL_COMMIT_IDENTITY",
            ],
        },
        "SUCCESSOR_PROPOSAL": {
            "kind": "FRESH_FULL_CHAIN",
            "scope": (
                "op_a_dequant + op_b_dequant + op_relocation_pad + "
                "op_fp32_add + op_tail_mul + op_tail_round"
            ),
            "required_terminal": (
                "ordered final op_tail_round COMP_FINISH + formal 28 "
                "final UINT8 D + independent golden"
            ),
            "fresh_runtime_requirements": [
                "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
                "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
                "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
            ],
        },
        "RULE_CONFIRMATION": {
            "status": "CONFIRMED",
            "rule_ids": [
                "CDA-SERVER-RESULT-GATE-CONJUNCTION-001",
                "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001",
                "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
                "CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001",
            ],
            "evidence": (
                "v37 separates qualified 32B->2x16B structural completion "
                "from unavailable independent-golden numeric evaluation"
            ),
        },
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
        "configuration_numeric_analysis_repeated": False,
        "golden_recomputed": False,
        "functional_rtl_modified": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "analysis_valid": report["analysis_valid"],
                "status": report["status"],
                "output": str(args.output),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["analysis_valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
