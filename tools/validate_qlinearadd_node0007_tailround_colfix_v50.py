"""Validate the changed causal slice of the QAdd node0007 tail-round fix."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-colfix-v50-rebuild"
CFG = ROOT / "configs/native_ndp_sim/qlinearadd_node0007_tailround_colfix_v50_rebuild"
PRE = ROOT / "configs/native_ndp_sim/qlinearadd_node0007_fp32_output32_v36"
NATIVE = ROOT / "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json"
STAGES = ("op_a_dequant", "op_b_dequant", "op_relocation_pad", "op_fp32_add", "op_tail_mul", "op_tail_round")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def leaves(value: Any, prefix: str = "$") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            result.update(leaves(item, f"{prefix}.{key}"))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(leaves(item, f"{prefix}[{index}]"))
        return result
    return {prefix: value}


def main() -> int:
    errors: list[str] = []
    before = {stage: load(PRE / f"{stage}.json") for stage in STAGES}
    after = {stage: load(CFG / f"{stage}.json") for stage in STAGES}
    changed = []
    for stage in STAGES:
        lhs, rhs = leaves(before[stage]), leaves(after[stage])
        for path in sorted(set(lhs) | set(rhs)):
            if lhs.get(path) != rhs.get(path):
                changed.append({"stage": stage, "path": path, "old": lhs.get(path), "new": rhs.get(path)})
    expected = [
        {"stage": "op_tail_round", "path": "$.buffer_loop_configs.GROUP2.COL_LC.end", "old": 32, "new": 4},
        {"stage": "op_tail_round", "path": "$.buffer_loop_configs.GROUP2.COL_LC.stride", "old": 16, "new": 2},
    ]
    if changed != expected:
        errors.append(f"changed leaf set differs: {changed}")

    native = load(NATIVE)
    col = after["op_tail_round"]["buffer_loop_configs"]["GROUP2"]["COL_LC"]
    if col != native["buffer_loop_configs"]["GROUP2"]["COL_LC"]:
        errors.append("corrected COL loop does not match pinned native authority")
    spatial = after["op_tail_round"]["stream_engine"]["stream2"]["buf_spatial_stride"]
    if spatial != native["stream_engine"]["stream2"]["buf_spatial_stride"]:
        errors.append("stream2 spatial stride differs from pinned native authority")

    proof_path = OUT / "tailround_column_window_proof.json"
    proof = load(proof_path)
    if not proof.get("valid") or not all(proof.get("checks", {}).values()):
        errors.append("positive 32-byte transaction proof failed")
    negatives = proof.get("negative_controls", {})
    if len(negatives) != 7 or not all(item.get("exit_code") == 1 and item.get("failed_closed") for item in negatives.values()):
        errors.append("transaction negative controls did not all fail closed")

    mapping = load(OUT / "mapping/op_tail_round/artifact_validation_report.json")
    execplan = load(OUT / "execplan/execplan_validation_report.json")
    if not mapping.get("valid"):
        errors.append("tail_round fresh mapping validation failed")
    if not execplan.get("valid"):
        errors.append("six-stage fresh execplan validation failed")
    pipeline = OUT / "execplan/pipeline_output"
    final_matches = list((pipeline / "jsons").glob("op_tail_round_*.json"))
    if len(final_matches) != 1:
        errors.append("final tail_round JSON cardinality differs")
    else:
        final = load(final_matches[0])
        source_flat, final_flat = leaves(after["op_tail_round"]), leaves(final)
        semantic_diff = []
        for path in sorted(set(source_flat) | set(final_flat)):
            if source_flat.get(path) == final_flat.get(path):
                continue
            if path.endswith(".base_addr") and int(source_flat[path], 0) == int(final_flat[path], 0):
                continue
            semantic_diff.append(path)
        if semantic_diff:
            errors.append(f"final JSON semantic diff: {semantic_diff[:8]}")
    sca = load(pipeline / "sca_cfg.json")
    sca_d = load(pipeline / "sca_cfg_D.json")
    tail_d = [key for key in sca_d if key.startswith("op_tail_round_matrixD_slice")]
    if sca.get("Repeat_Num") != 6 or len(tail_d) != 28:
        errors.append("six-stage/28 tail D SCA contract differs")

    receipt = load(OUT / "build_receipt.json")
    if receipt.get("changed_stage") != "op_tail_round" or receipt.get("numeric_analysis_repeated") is not False:
        errors.append("build receipt claim boundary differs")

    report = {
        "schema": "qlinearadd-node0007-tailround-colfix-v50-validation-v1",
        "valid": not errors,
        "errors": errors,
        "changed_leaves": changed,
        "mapping_valid": bool(mapping.get("valid")),
        "execplan_valid": bool(execplan.get("valid")),
        "formal_D_count": len(tail_d),
        "transaction_positive_checks": proof.get("checks"),
        "transaction_negative_controls": negatives,
        "full_six_stage_request_enumeration_repeated": False,
        "changed_surface_validation": "internal Buffer5 COL/spatial-stride transaction window only",
        "numeric_analysis_repeated": False,
        "server_action": False,
        "artifacts": {
            "build_receipt_sha256": sha(OUT / "build_receipt.json"),
            "proof_sha256": sha(proof_path),
            "mapping_validation_sha256": sha(OUT / "mapping/op_tail_round/artifact_validation_report.json"),
            "execplan_validation_sha256": sha(OUT / "execplan/execplan_validation_report.json"),
        },
    }
    output = OUT / "validation_report.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": report["valid"], "errors": errors, "report": str(output), "sha256": sha(output)}, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
