"""Analyze the recovered, already-run QLinearAdd node0007 v46 return.

This tool is deliberately return-bound.  It validates the archive and
receipts, adjudicates the recorded execution, and does not run the DUT or
recompute numeric/config/workload/golden assets.
"""

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
OWNER = "019fa2c0-b647-7a91-93bf-d21a173487e3"
TARGET = "019fbec2-fe93-7e03-9314-cff6f222f33d"
RETURN_SHA = "fbde2a98d03c6de43219dba469d2113b628706f42803604da8f19daf424be07f"
RETURN_BYTES = 407_184
SOURCE_SHA = "8c015af623b5b12f924c2ce9e85b5bff708d97e6372d68af565890b498b4fab1"
SOURCE_BYTES = 38_062_055
FUNCTIONAL_SHA = "58f5204886fef6015501dedc7e4443936c8ba118be248d12c102b46bf5afa3c5"
INSTALL = "r5_qadd_n7_fullchain_returnfix_v46"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_fullchain_returnfix_v46.zip"
FUNCTIONAL = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/superseded/qlinearadd_node0007/qadd_v46_pre_repeat/qadd_v46_pre_repeat.zip"
REPEAT_RECEIPT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/qlinearadd_node0007/r5_qadd_n7_fullchain_returnfix_v46/r5_qadd_n7_fullchain_returnfix_v46.repeatable_runtime_validation.json"
RULES = {
    "agent": ".agents/agent.md",
    "plan_mutable": ".agents/plan.md",
    "generation_index": ".agents/rules/生成前必读索引.md",
    "server": ".agents/rules/服务器测试包生成规则.md",
    "common_config": ".agents/rules/算子配置规则.md",
    "ndp_fields": ".agents/rules/NDP硬件字段语义.md",
    "qlinearadd": ".agents/rules/QLinearAdd算子配置规则.md",
    "exact_uint8_tail": ".agents/rules/精确UINT8量化尾专项规则.md",
    "hardware_sim_readme": "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
}
STAGES = (
    "op_a_dequant",
    "op_b_dequant",
    "op_relocation_pad",
    "op_fp32_add",
    "op_tail_mul",
    "op_tail_round",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def inventory(path: Path) -> tuple[str, dict[str, bytes], dict[str, Any]]:
    files: dict[str, bytes] = {}
    roots: set[str] = set()
    seen: set[str] = set()
    duplicate: list[str] = []
    unsafe: list[str] = []
    symlink: list[str] = []
    with zipfile.ZipFile(path) as archive:
        bad_crc = archive.testzip()
        infos = archive.infolist()
        for info in infos:
            pure = PurePosixPath(info.filename)
            if info.filename in seen:
                duplicate.append(info.filename)
            seen.add(info.filename)
            if not pure.parts:
                unsafe.append(info.filename)
                continue
            roots.add(pure.parts[0])
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                unsafe.append(info.filename)
            if stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF):
                symlink.append(info.filename)
        if len(roots) != 1:
            raise ValueError(f"single-root gate failed: {sorted(roots)}")
        root = next(iter(roots))
        prefix = root + "/"
        for info in infos:
            if info.is_dir():
                continue
            if not info.filename.startswith(prefix):
                raise ValueError(f"member outside root: {info.filename}")
            relative = info.filename[len(prefix) :]
            if relative in files:
                raise ValueError(f"duplicate member: {relative}")
            files[relative] = archive.read(info)
    return root, files, {
        "crc_valid": bad_crc is None,
        "root": root,
        "entry_count": len(files),
        "duplicates": duplicate,
        "unsafe_paths": unsafe,
        "symlinks": symlink,
    }


def obj(files: dict[str, bytes], name: str) -> dict[str, Any]:
    value = json.loads(files[name])
    if not isinstance(value, dict):
        raise ValueError(f"object expected: {name}")
    return value


def digest_valid(value: dict[str, Any]) -> bool:
    copy = dict(value)
    stored = copy.pop("content_digest", {}).get("value")
    encoded = json.dumps(copy, sort_keys=True, separators=(",", ":")).encode()
    return stored == sha_bytes(encoded)


def event_fields(line: str) -> dict[str, int]:
    return {
        key: int(value, 16) if value.lower().startswith("0x") else int(value)
        for key, value in re.findall(r"(\w+)=(0x[0-9a-fA-F]+|\d+)", line)
    }


def stages(observer: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    for line in observer.splitlines():
        match = re.match(r"^(\d+) \| ([A-Z0-9_]+) \| (.*)$", line)
        if not match:
            continue
        time_ps, event, tail = int(match.group(1)), match.group(2), match.group(3)
        fields = event_fields(tail)
        if event == "EXEC_START":
            index = len(result)
            active = {
                "index": index + 1,
                "name": STAGES[index] if index < len(STAGES) else "unexpected",
                "exec_start_ps": time_ps,
                "exec_start": fields,
                "comp_finish_ps": None,
                "comp_finish": None,
                "heartbeats": [],
            }
            result.append(active)
        elif active is not None and event == "COMP_FINISH":
            active["comp_finish_ps"] = time_ps
            active["comp_finish"] = fields
        elif active is not None and event == "HEARTBEAT":
            active["heartbeats"].append({"time_ps": time_ps, **fields})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--return-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    return_path = args.return_zip.resolve()
    for path, size, digest, label in (
        (return_path, RETURN_BYTES, RETURN_SHA, "return"),
        (SOURCE, SOURCE_BYTES, SOURCE_SHA, "repeatable source"),
        (FUNCTIONAL, FUNCTIONAL.stat().st_size, FUNCTIONAL_SHA, "functional source"),
    ):
        if path.stat().st_size != size:
            errors.append(f"{label} bytes differ")
        if sha256(path) != digest:
            errors.append(f"{label} SHA256 differs")

    return_root, returned, return_structure = inventory(return_path)
    source_root, source, source_structure = inventory(SOURCE)
    functional_root, functional, functional_structure = inventory(FUNCTIONAL)
    if return_root != INSTALL + "_return":
        errors.append("return root identity differs")
    if source_root != INSTALL or functional_root != INSTALL:
        errors.append("source root identity differs")
    for label, structure in (
        ("return", return_structure),
        ("repeatable source", source_structure),
        ("functional source", functional_structure),
    ):
        if not structure["crc_valid"] or structure["duplicates"] or structure["unsafe_paths"] or structure["symlinks"]:
            errors.append(f"{label} ZIP structure gate failed")

    manifest = obj(returned, "RETURN_MANIFEST.json")
    source_manifest = obj(source, "TEST_PACKAGE_MANIFEST.json")
    functional_manifest = obj(functional, "TEST_PACKAGE_MANIFEST.json")
    returned_source_manifest = obj(returned, "evidence/PACKAGE_MANIFEST.json")
    declared = {row["path"]: row for row in manifest.get("files", [])}
    actual = set(returned) - {"RETURN_MANIFEST.json"}
    allowlist = {row["target_path"]: row for row in source_manifest.get("return_allowlist", [])}
    per_file_errors = []
    for name, row in declared.items():
        if name not in returned:
            per_file_errors.append(f"missing:{name}")
        elif len(returned[name]) != int(row["size_bytes"]):
            per_file_errors.append(f"size:{name}")
        elif sha_bytes(returned[name]) != row["sha256"]:
            per_file_errors.append(f"sha:{name}")
        elif name not in allowlist or len(returned[name]) > int(allowlist[name]["max_bytes"]):
            per_file_errors.append(f"allowlist:{name}")
    exact_set = actual == set(declared) == (set(allowlist) - set(manifest.get("required_missing", [])))
    if not exact_set or per_file_errors:
        errors.append("return exact-set/per-file/allowlist gate failed")
    source_binding = (
        returned["evidence/PACKAGE_MANIFEST.json"] == source["TEST_PACKAGE_MANIFEST.json"]
        and returned_source_manifest == source_manifest
        and manifest.get("install_name") == source_manifest.get("install_name") == INSTALL
    )
    if not source_binding:
        errors.append("returned package manifest does not byte-bind repeatable source")

    repeat = json.loads(REPEAT_RECEIPT.read_text(encoding="utf-8"))
    repeat_row = next(
        (
            row
            for row in repeat.get("packages", [])
            if row.get("package_id") == INSTALL
        ),
        {},
    )
    repeat_binding = (
        repeat.get("pass") is True
        and repeat_row.get("pass") is True
        and repeat_row.get("reissued_zip_sha256") == SOURCE_SHA
        and repeat_row.get("source_zip_sha256") == FUNCTIONAL_SHA
        and repeat_row.get("functional_assets_byte_equal") is True
    )
    if not repeat_binding:
        errors.append("repeatable source -> frozen functional source receipt differs")

    compile_exit = int(returned["evidence/compile_exit_status.txt"].decode().strip())
    sim_exit = int(returned["evidence/simulation_exit_status.txt"].decode().strip())
    signal = returned["evidence/signal_status.txt"].decode().strip()
    timing = dict(line.split("=", 1) for line in returned["evidence/host_timing.txt"].decode().splitlines() if "=" in line)
    duration_s = (int(timing["run_end_ns"]) - int(timing["run_start_ns"])) / 1e9
    canonical = obj(returned, "evidence/CANONICAL_PROGRESS_DECISION.json")
    result_gate = obj(returned, "evidence/SERVER_RESULT_GATE.json")
    observer = returned["runs/return_observer.log"].decode(errors="replace")
    simlog = returned["runs/sim.log"].decode(errors="replace")
    stage_rows = stages(observer)
    ordered_starts = [row["name"] for row in stage_rows]
    ordered_finishes = [row["name"] for row in stage_rows if row["comp_finish"] is not None]
    final = stage_rows[-1]
    heartbeats = final["heartbeats"]
    qualified = ("req", "rdata", "wdata")
    frozen_windows = 0
    for left, right in zip(heartbeats, heartbeats[1:]):
        if all(left.get(name) == right.get(name) for name in qualified):
            frozen_windows += 1
    first_hb = heartbeats[0] if heartbeats else {}
    last_hb = heartbeats[-1] if heartbeats else {}
    finite_delta = {
        name: first_hb.get(name, 0) - final["exec_start"].get(name, 0)
        for name in qualified
    }
    sg_lines = [line for line in observer.splitlines() if " | SG_COUNTS | " in line]
    final_sg = event_fields(sg_lines[-1]) if sg_lines else {}
    level_count_defect = (
        "buf5_wr" in canonical.get("qualified_counter_names", [])
        and canonical.get("stage_windows", [])[-1].get("advancing_windows") == 44
        and last_hb.get("buf5_wr", 0) > first_hb.get("buf5_wr", 0)
        and last_hb.get("req") == first_hb.get("req")
        and last_hb.get("rdata") == first_hb.get("rdata")
        and last_hb.get("wdata") == first_hb.get("wdata")
    )
    natural = (
        compile_exit == 0 and sim_exit == 0 and signal == "NONE"
        and ordered_finishes == list(STAGES)
        and "Simulation completed successfully!" in simlog
        and result_gate.get("result_gate_conjunction", {}).get("all_terms_true") is True
    )
    if compile_exit != 0 or sim_exit != 124 or signal != "NONE":
        errors.append("execution tuple differs from compile0/timeout124/signalNONE")
    if ordered_starts != list(STAGES) or ordered_finishes != list(STAGES[:5]):
        errors.append("six-stage ordered progress differs")
    if len(heartbeats) != 45 or frozen_windows < 43:
        errors.append("tail-round qualified stall-window evidence differs")
    if not level_count_defect:
        errors.append("canonical level-as-progress defect not reproduced")

    formal = {
        "expected": result_gate.get("expected_readback_count"),
        "present": result_gate.get("observed_readback_count"),
        "missing": result_gate.get("missing_count"),
        "invalid": result_gate.get("invalid_count"),
        "mismatch_bytes": result_gate.get("mismatch_byte_count"),
        "mismatch_evaluable": result_gate.get("mismatch_evaluable"),
        "conjunction": result_gate.get("result_gate_conjunction", {}).get("all_terms_true"),
    }
    controls = {}
    for name, relative in RULES.items():
        path = ROOT / relative
        controls[name] = {"path": relative, "bytes": path.stat().st_size, "sha256": sha256(path), "mutable_provenance_only": name == "plan_mutable"}

    report = {
        "schema": "qlinearadd-node0007-v46-recovered-return-analysis-v1",
        "status": "RETURN_ANALYSIS_COMPLETE_TAIL_ROUND_LONG_HANG_DIAGNOSTIC_DEFECT",
        "analysis_valid": not errors,
        "errors": errors,
        "analysis_owner_thread": OWNER,
        "return_target_thread": TARGET,
        "numeric_analysis_repeated": False,
        "workload_config_golden_repeated": False,
        "dut_rerun": False,
        "control_receipts": controls,
        "transport_and_identity": {
            "return": {"path": str(return_path), "bytes": return_path.stat().st_size, "sha256": sha256(return_path), "execution": "r1786110475344343035_3722926", "attempt": "a3722926", "classification": "RECOVERY_PUBLICATION_OF_ALREADY_RUN_EVIDENCE"},
            "structure": return_structure,
            "manifest_exact_set": exact_set,
            "manifest_per_file_errors": per_file_errors,
            "source": {"path": SOURCE.relative_to(ROOT).as_posix(), "bytes": SOURCE.stat().st_size, "sha256": sha256(SOURCE), "returned_manifest_sha256": sha_bytes(returned["evidence/PACKAGE_MANIFEST.json"]), "byte_bound": source_binding},
            "frozen_functional_source": {"path": FUNCTIONAL.relative_to(ROOT).as_posix(), "bytes": FUNCTIONAL.stat().st_size, "sha256": sha256(FUNCTIONAL), "manifest_sha256": sha_bytes(functional["TEST_PACKAGE_MANIFEST.json"]), "repeat_receipt": REPEAT_RECEIPT.relative_to(ROOT).as_posix(), "repeat_receipt_sha256": sha256(REPEAT_RECEIPT), "functional_assets_byte_equal": repeat_binding},
        },
        "RETURN_ANALYSIS": {
            "outcome": "LONG_RUNNING_HANG_AT_OP_TAIL_ROUND_AFTER_FINITE_ACTIVITY",
            "compile_exit": compile_exit,
            "simulation_exit": sim_exit,
            "signal": signal,
            "natural_terminal": natural,
            "host_duration_seconds": duration_s,
            "host_duration_hours": duration_s / 3600,
            "ordered_stage_starts": ordered_starts,
            "ordered_stage_finishes": ordered_finishes,
            "final_stage": "op_tail_round",
            "final_stage_heartbeat_samples": len(heartbeats),
            "qualified_frozen_full_windows": frozen_windows,
            "stall_window_cycles": canonical.get("content_summary", {}).get("stall_window_cycles"),
            "finite_first_window_delta": finite_delta,
            "final_sg_snapshot": final_sg,
        },
        "canonical_adjudication": {
            "returned_digest_valid": digest_valid(canonical),
            "returned_decision": canonical.get("decision"),
            "returned_advancing_windows": canonical.get("content_summary", {}).get("advancing_windows"),
            "defect": "BUF4_BUF5_ENABLE_LEVEL_COUNTS_MISCLASSIFIED_AS_QUALIFIED_PROGRESS",
            "defect_proven": level_count_defect,
            "corrected_decision": "LONG_RUNNING_HANG_AT_OP_TAIL_ROUND_AFTER_FINITE_ACTIVITY",
            "corrected_qualified_counter_set": list(qualified),
            "claim_boundary": "raw req/rdata/wdata are accepted transaction evidence; stable buf4/buf5 enable levels are state only and cannot reset the stall window",
        },
        "LAST_PROVEN_GOOD": "OP_TAIL_MUL_COMP_FINISH_THEN_OP_TAIL_ROUND_FINITE_REQ_RDATA_WDATA_ACTIVITY",
        "FIRST_DIVERGENCE": "OP_TAIL_ROUND_AFTER_FINITE_MSE4_REQUEST_ACTIVITY_BEFORE_PAIRED_WDATA_GA_OUTPUT_AND_COMP_FINISH",
        "HANG_ROOT_CAUSE": {
            "status": "NOT_UNIQUELY_PROVEN",
            "bounded_interval": "tail-round MSE4/Buffer5/RD_Buffer_AG/WR_Data_Channel/GA ingress-to-terminal flow-control chain",
            "facts": [
                "first five ordered stages naturally reached COMP_FINISH",
                "tail-round issued finite accepted req/rdata/wdata then froze for at least 43 complete stall windows",
                "MSE4 requests are asymmetric (ch0/ch1=2/1), accepted wdata is ch0/ch1=1/0, and outstanding is 1/1",
                "GA input/output qualified counts are both zero at the final snapshot",
                "simulator remained CPU-active while functional qualified counters were frozen",
            ],
            "not_proven": ["exact first Buffer5 accepted write/read stall", "Buffer_AG queue first blocking edge", "RD_Buffer_AG delivery first blocking edge", "WR_Data_Channel prepared-data/accepted-wdata first blocking edge", "GA input capture or terminal first blocking edge", "config failure", "functional RTL failure"],
        },
        "formal_D": formal,
        "evidence_levels": {"E3": False, "E4": False, "E5": False, "reason": "timeout/non-natural terminal and formal D missing 28/28; mismatch=0 is unevaluable"},
        "BLOCKER_DELTA": {
            "closed": ["B_QADD_V46_RECOVERY_PUBLICATION_MISSING", "B_QADD_V46_SOURCE_IDENTITY_UNBOUND"],
            "opened": ["B_QADD_V46_TAIL_ROUND_LONG_HANG", "B_QADD_V46_CANONICAL_LEVEL_AS_PROGRESS"],
            "refined": {"from": "full-chain unresolved", "to": "op_tail_round flow-control interval after finite request activity"},
        },
        "SUCCESSOR_PROPOSAL": {
            "required": True,
            "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "identity": "r5_qadd_n7_tailround_flow_v47",
            "frozen": "six-stage config/workload/numeric/W3/qparams/tail/golden/timeout/functional RTL",
            "changed_surface": ["canonical excludes level-only Buffer enable counts", "tail-round stage-local accepted write/read, Buffer_AG queue, RD_Buffer_AG, WR_Data_Channel prepared/accepted wdata, MSE4 and GA qualified chain", "collector wrapper cfg-root/return-zip recovery interface"],
            "candidate_observation_matrix": [
                {"candidate": "Buffer5 acceptance stall", "distinguishing_observation": "write/read enable high with accepted write/read counters frozen"},
                {"candidate": "Buffer_AG queue/tag stall", "distinguishing_observation": "Buffer5 accepted write advances but queue enq/deq or ROW/COL tag pairing freezes"},
                {"candidate": "RD_Buffer_AG delivery stall", "distinguishing_observation": "queue dequeue advances but ARM/RD delivery accept freezes"},
                {"candidate": "WR_Data_Channel asymmetric stall", "distinguishing_observation": "MSE4 request advances while prepared-data/accepted-wdata remains asymmetric"},
                {"candidate": "GA capture/output stall", "distinguishing_observation": "paired MSE delivery advances but GA operand capture/output does not"},
                {"candidate": "terminal propagation stall", "distinguishing_observation": "all required data counts reach exact terminal set but COMP_FINISH/last does not"},
            ],
        },
        "RULE_CONFIRMATION": {
            "status": "CONFIRMED_WITH_PACKAGE_DIAGNOSTIC_DEFECT",
            "statement": "Timeout is adjudicated hang-first, stable levels do not count as progress, missing 28D keeps mismatch unevaluable, and continuous closure therefore requires one qualified-event successor without changing QAdd semantics.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"analysis_valid": report["analysis_valid"], "errors": errors, "output": str(args.output), "bytes": args.output.stat().st_size, "sha256": sha256(args.output)}, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
