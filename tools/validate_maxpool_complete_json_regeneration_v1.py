from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.maxpool_padding_contract import (  # noqa: E402
    CURRENT_PADDING_RTL_RECEIPT,
    validate_maxpool_padding_rtl_current_receipt,
    validate_maxpool_zero_padding_contract,
)
from resnet50_pipeline.operator_config_validator import OperatorConfigValidator  # noqa: E402

from tools.regenerate_maxpool_node0002_complete_json_v1 import (  # noqa: E402
    CANDIDATE,
    CURRENT_BITSTREAM_MEMBER,
    CURRENT_CONFIG_MEMBER,
    CURRENT_GRAPH_MEMBER,
    CURRENT_MAPPING_MEMBER,
    CURRENT_ZIP,
    NDPSIM_COMMIT,
    OUT,
    RTL_COMMIT,
    SOURCE,
    SOURCE_BLOB,
    _leaf_map,
    _load_json,
    _sha256_bytes,
    _sha256_file,
)


ALLOWED_ORIGINS = {
    "REFERENCE_EXACT",
    "MODEL_DERIVED",
    "RTL_DERIVED",
    "ENCODER_DERIVED",
    "ADDRESS_PLANNER_DERIVED",
    "SCHEDULE_DERIVED",
    "EXPLICIT_DISABLED",
    "UNRESOLVED",
}
ADDRESS_POINTERS = {
    "/stream_engine/stream0/base_addr",
    "/stream_engine/stream1/base_addr",
}
PADDING_CONTRACT = ROOT / "contracts/maxpool_node0002_zero_padding_contract.json"
RD_DATA = (
    ROOT
    / "Trassic2.0_RTL"
    / "code"
    / "NDP_rtl"
    / "Slice"
    / "LSU"
    / "Stream_Engine"
    / "Memory_Stream_Engine"
    / "Memory_RD_Stream_Engine"
    / "RD_Data_Channel.sv"
)
PADDING_ASSIGNMENT = (
    "rd_chl_queue_rd_padding_mask[PADDING_INDEX] ? mse_padding_reg_value"
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_candidate_bundle(
    *,
    candidate: dict[str, Any],
    ledger: dict[str, Any],
    applicability: dict[str, Any],
    capability: dict[str, Any],
    diff: dict[str, Any],
    current: dict[str, Any],
    graph: dict[str, Any],
) -> dict[str, Any]:
    source = _load_json(SOURCE)
    source_leaves = _leaf_map(source)
    candidate_leaves = _leaf_map(candidate)
    current_leaves = _leaf_map(current)
    entries = ledger.get("entries")
    _assert(isinstance(entries, list), "ledger entries missing")
    _assert(set(candidate_leaves) == set(source_leaves), "candidate/source leaf set differs")
    _assert(set(candidate_leaves) == set(current_leaves), "candidate/current leaf set differs")
    _assert(len(entries) == len(candidate_leaves), "ledger leaf coverage differs")
    _assert(
        {entry.get("json_pointer") for entry in entries} == set(candidate_leaves),
        "ledger pointer exact-set differs",
    )
    _assert(
        all(entry.get("origin") in ALLOWED_ORIGINS for entry in entries),
        "ledger contains forbidden origin",
    )
    _assert(
        all(entry.get("origin") != "UNRESOLVED" for entry in entries),
        "ledger contains unresolved target leaf",
    )
    by_pointer = {entry["json_pointer"]: entry for entry in entries}
    for pointer, target_value in candidate_leaves.items():
        entry = by_pointer[pointer]
        _assert(entry.get("target_value") == target_value, f"ledger value differs: {pointer}")
        _assert(entry.get("status") == "RESOLVED", f"ledger status differs: {pointer}")
        source_info = entry.get("source", {})
        _assert(source_info.get("repo") == "ndp-sim", f"source repo differs: {pointer}")
        _assert(
            source_info.get("commit") == NDPSIM_COMMIT,
            f"source commit differs: {pointer}",
        )
        _assert(source_info.get("blob") == SOURCE_BLOB, f"source blob differs: {pointer}")
        _assert(
            source_info.get("json_pointer") == pointer,
            f"source pointer differs: {pointer}",
        )
        _assert(
            source_info.get("value") == source_leaves[pointer],
            f"source value differs: {pointer}",
        )
        _assert(
            isinstance(entry.get("current_consumer_equation"), str)
            and bool(entry["current_consumer_equation"].strip()),
            f"consumer equation missing: {pointer}",
        )
        if pointer in ADDRESS_POINTERS:
            _assert(
                entry.get("origin") == "ADDRESS_PLANNER_DERIVED",
                f"address leaf origin differs: {pointer}",
            )
            _assert(
                entry.get("derivation", {}).get("kind") == "TARGET_REQUIRED_DERIVED",
                f"address derivation kind differs: {pointer}",
            )
        else:
            _assert(
                entry.get("origin") == "REFERENCE_EXACT",
                f"exact leaf origin differs: {pointer}",
            )
            _assert(
                target_value == source_leaves[pointer],
                f"exact replay leaf value differs: {pointer}",
            )

    op = graph["operators"][0]
    _assert(
        candidate_leaves["/stream_engine/stream0/base_addr"]
        == hex(int(op["inputs"]["A"]["base_addr"], 16)),
        "input base address derivation differs",
    )
    _assert(
        candidate_leaves["/stream_engine/stream1/base_addr"]
        == hex(int(op["output"]["base_addr"], 16)),
        "output base address derivation differs",
    )
    _assert(candidate == current, "candidate differs from current consumed final JSON")
    _assert(
        applicability.get("target_hw_op_types") == ["MaxPoolUint8"],
        "reference target_hw_op_types differs",
    )
    _assert(
        capability.get("target_hw_op_types") == ["MaxPoolUint8"],
        "capability target_hw_op_types differs",
    )
    _assert(
        capability["capabilities"]["shape"]["status"]
        == "UNSUPPORTED_FOR_DERIVATION",
        "shape capability is overstated",
    )
    _assert(
        not capability["registry_entry_present"]
        and not capability["operator_specific_control_handler_present"],
        "MaxPool handler presence is overstated",
    )
    grades = applicability["template_classes"]
    _assert(
        len(grades["A_exact_replay"]) == 1
        and grades["A_exact_replay"][0]["source_blob"] == SOURCE_BLOB,
        "A-grade authority differs",
    )
    _assert(
        all(item["grade"] == "D" for item in grades["D_project_added_or_untracked"]),
        "project-added JSON was promoted to upstream authority",
    )
    _assert(
        diff["candidate_vs_current_consumed_final_json"]["suspected_current_defect"]
        == [],
        "current config defect is asserted without a candidate/current diff",
    )
    _assert(
        not diff["candidate_vs_current_consumed_final_json"]["dynamic_only"][0][
            "config_difference_can_explain"
        ],
        "dynamic stop is incorrectly attributed to a config difference",
    )
    return {
        "leaf_count": len(candidate_leaves),
        "reference_exact_count": len(candidate_leaves) - len(ADDRESS_POINTERS),
        "address_derived_count": len(ADDRESS_POINTERS),
        "unresolved_count": 0,
    }


def _negative_controls(
    base: dict[str, Any],
) -> list[dict[str, Any]]:
    controls: list[tuple[str, Any]] = []

    missing_entry = deepcopy(base)
    missing_entry["ledger"]["entries"].pop()
    controls.append(("delete_one_ledger_leaf", missing_entry))

    unresolved = deepcopy(base)
    unresolved["ledger"]["entries"][0]["origin"] = "UNRESOLVED"
    controls.append(("mark_one_leaf_unresolved", unresolved))

    false_exact = deepcopy(base)
    false_exact["candidate"]["dram_loop_configs"]["LC0"]["end"] += 1
    false_exact["current"]["dram_loop_configs"]["LC0"]["end"] += 1
    false_exact["ledger"]["entries"][
        next(
            index
            for index, item in enumerate(false_exact["ledger"]["entries"])
            if item["json_pointer"] == "/dram_loop_configs/LC0/end"
        )
    ]["target_value"] += 1
    controls.append(("tamper_reference_exact_leaf", false_exact))

    wrong_base = deepcopy(base)
    wrong_base["candidate"]["stream_engine"]["stream0"]["base_addr"] = "0x10"
    wrong_base["current"]["stream_engine"]["stream0"]["base_addr"] = "0x10"
    wrong_base["ledger"]["entries"][
        next(
            index
            for index, item in enumerate(wrong_base["ledger"]["entries"])
            if item["json_pointer"] == "/stream_engine/stream0/base_addr"
        )
    ]["target_value"] = "0x10"
    controls.append(("tamper_planner_owned_base", wrong_base))

    promote_d = deepcopy(base)
    promote_d["applicability"]["template_classes"]["D_project_added_or_untracked"][0][
        "grade"
    ] = "A"
    controls.append(("promote_project_json_to_A_authority", promote_d))

    false_dynamic = deepcopy(base)
    false_dynamic["diff"]["candidate_vs_current_consumed_final_json"]["dynamic_only"][0][
        "config_difference_can_explain"
    ] = True
    controls.append(("attribute_dynamic_stop_to_zero_config_diff", false_dynamic))

    results = []
    for name, value in controls:
        try:
            _validate_candidate_bundle(**value)
        except Exception as error:  # expected fail-closed path
            results.append(
                {
                    "name": name,
                    "expected_exit": 1,
                    "observed_exit": 1,
                    "failed_closed": True,
                    "reason": str(error),
                }
            )
        else:
            results.append(
                {
                    "name": name,
                    "expected_exit": 1,
                    "observed_exit": 0,
                    "failed_closed": False,
                    "reason": "negative mutation was accepted",
                }
            )
    return results


def _encoder_replay(candidate_path: Path, expected_bitstream: bytes) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="maxpool-complete-json-") as temp_text:
        temp = Path(temp_text)
        command = [
            sys.executable,
            str(ROOT / "ndp-sim/bitstream/main.py"),
            "--visualize-placement",
            "-c",
            str(candidate_path),
            "-o",
            str(temp),
            "-q",
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT / "ndp-sim",
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        candidates = sorted(temp.glob("*bitstream_128b.bin"))
        generated = candidates[0].read_bytes() if len(candidates) == 1 else b""
        return {
            "command": command,
            "exit_code": completed.returncode,
            "stdout_sha256": _sha256_bytes(completed.stdout.encode("utf-8")),
            "stderr_sha256": _sha256_bytes(completed.stderr.encode("utf-8")),
            "generated_128b_count": len(candidates),
            "generated_128b_sha256": _sha256_bytes(generated) if generated else None,
            "current_consumed_128b_sha256": _sha256_bytes(expected_bitstream),
            "byte_equal_to_current_consumed_bitstream": generated == expected_bitstream,
        }


def main() -> int:
    ledger = _load_json(OUT / "field_provenance_ledger.json")
    applicability = _load_json(OUT / "reference_applicability.json")
    capability = _load_json(OUT / "handler_capability.json")
    diff = _load_json(OUT / "current_test_diff.json")
    report = _load_json(OUT / "report.json")
    candidate = _load_json(CANDIDATE)
    with zipfile.ZipFile(CURRENT_ZIP) as archive:
        current_bytes = archive.read(CURRENT_CONFIG_MEMBER)
        current = json.loads(current_bytes.decode("utf-8"))
        graph = json.loads(archive.read(CURRENT_GRAPH_MEMBER).decode("utf-8"))
        mapping = json.loads(archive.read(CURRENT_MAPPING_MEMBER).decode("utf-8"))
        bitstream = archive.read(CURRENT_BITSTREAM_MEMBER)

    base = {
        "candidate": candidate,
        "ledger": ledger,
        "applicability": applicability,
        "capability": capability,
        "diff": diff,
        "current": current,
        "graph": graph,
    }
    summary = _validate_candidate_bundle(**base)
    schema_report = OperatorConfigValidator().validate_file(CANDIDATE).to_dict()
    _assert(schema_report["valid"], "operator config shadow validator rejected candidate")
    _assert(CANDIDATE.read_bytes() == current_bytes, "candidate/current bytes differ")
    _assert(report["target_hw_op_types"] == ["MaxPoolUint8"], "report type binding differs")

    forbidden = [
        path.relative_to(OUT).as_posix()
        for path in OUT.rglob("*")
        if path.is_file()
        and (
            path.suffix.lower() == ".zip"
            or path.name in {"PREPARE_AND_RUN.sh", "TEST_PACKAGE_MANIFEST.json"}
        )
    ]
    _assert(not forbidden, f"server-package artifact found: {forbidden}")

    encoder = _encoder_replay(CANDIDATE, bitstream)
    _assert(encoder["exit_code"] == 0, "native encoder replay failed")
    _assert(encoder["generated_128b_count"] == 1, "native encoder output count differs")
    _assert(
        encoder["byte_equal_to_current_consumed_bitstream"],
        "native encoder bitstream differs from current consumed bitstream",
    )
    _assert(mapping["summary"]["total_nodes"] == 28, "mapping node count differs")
    _assert(
        {item["resource"] for item in mapping["node_to_resource"]}
        >= {"READ_STREAM0", "WRITE_STREAM0", "GROUP0", "GROUP4"},
        "mapping consumer resources differ",
    )

    padding_contract_value = validate_maxpool_zero_padding_contract(
        ROOT, PADDING_CONTRACT
    )
    padding_receipt_path = ROOT / CURRENT_PADDING_RTL_RECEIPT
    padding_receipt = validate_maxpool_padding_rtl_current_receipt(
        ROOT, padding_receipt_path
    )
    padding_contract = {
        "validator_pass": True,
        "status": "PASS_WITH_CURRENT_RTL_RECEIPT",
        "contract_path": PADDING_CONTRACT.relative_to(ROOT).as_posix(),
        "contract_sha256": _sha256_file(PADDING_CONTRACT),
        "contract_internal_sha256": padding_contract_value["contract_sha256"],
        "current_receipt_path": padding_receipt_path.relative_to(ROOT).as_posix(),
        "current_receipt_sha256": _sha256_file(padding_receipt_path),
        "current_rd_data_path": RD_DATA.relative_to(ROOT).as_posix(),
        "current_rd_data_sha256": _sha256_file(RD_DATA),
        "current_rtl_commit": RTL_COMMIT,
        "padding_equation_preserved": PADDING_ASSIGNMENT
        in RD_DATA.read_text(encoding="utf-8"),
        "current_receipt_status": padding_receipt["status"],
        "candidate_leaf_error": False,
    }
    _assert(
        padding_contract["validator_pass"]
        and padding_contract["padding_equation_preserved"],
        "padding contract/current RTL receipt validation failed",
    )

    negatives = _negative_controls(base)
    _assert(
        all(item["failed_closed"] for item in negatives),
        "one or more negative controls did not fail closed",
    )

    validation = {
        "schema": "maxpool-complete-json-local-validation-v1",
        "family": "maxpool_uint8",
        "target_hw_op_types": ["MaxPoolUint8"],
        "status": "PASS",
        "strict_complete_json_valid": True,
        "provenance_coverage_valid": True,
        "current_consumer_equivalence_valid": True,
        "native_encoder_replay_valid": True,
        "summary": summary,
        "operator_config_shadow_validation": schema_report,
        "native_encoder_replay": encoder,
        "current_mapping_summary": mapping["summary"],
        "legacy_padding_contract": padding_contract,
        "negative_controls": negatives,
        "negative_control_count": len(negatives),
        "all_negative_controls_failed_closed": True,
        "artifact_root_forbidden_files": forbidden,
        "unified_public_gate": "PENDING_MAINLINE_SCHEMA_SYNC",
        "rule_delta_proposal": [],
        "errors": [],
    }
    _write_json(OUT / "validation_report.json", validation)
    print(json.dumps(validation, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
