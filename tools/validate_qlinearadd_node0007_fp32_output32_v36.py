from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.ndp_config_length import (
    analyze_config_length,
    parse_load_config_length,
)
from tools.build_qlinearadd_node0007_fp32_output32_v36 import (
    ADDED_PES,
    OUT_REL,
    REQUIRED_PES,
    output32_config,
    sha,
)
from tools.build_qlinearadd_node0007_fp32_rowpair_v30 import leaf_diffs
from resnet50_pipeline.qlinearadd_node0007_d_buffer_column_pair_v18 import (
    build_configs as build_source_configs,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT / OUT_REL)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT
        / "artifacts/operator_config_validation/"
        "r5-qlinearadd-node0007-fp32-output32-v36/validation.json",
    )
    args = parser.parse_args()
    bundle = args.root.resolve()
    build = json.loads((bundle / "build_receipt.json").read_text(encoding="utf-8"))
    pipeline = bundle / "execplan/pipeline_output"
    final_json_path = (
        pipeline / "jsons/op_fp32_add_resnet50_qadd_node0007_fp32_add.json"
    )
    final_json = json.loads(final_json_path.read_text(encoding="utf-8"))
    source = build_source_configs(ROOT)["op_fp32_add"]
    expected, proof = output32_config(source)
    mapping_report = json.loads(
        (
            bundle
            / "execplan/mapping_evidence/op_fp32_add/artifact_validation_report.json"
        ).read_text(encoding="utf-8")
    )
    exec_report = json.loads(
        (bundle / "execplan/execplan_validation_report.json").read_text(
            encoding="utf-8"
        )
    )
    config_root = pipeline / "config/op_fp32_add"
    bit64 = (
        config_root
        / "op_fp32_add_resnet50_qadd_node0007_fp32_add_bitstream_64b.bin"
    )
    bit128 = (
        config_root
        / "op_fp32_add_resnet50_qadd_node0007_fp32_add_bitstream_128b.bin"
    )
    programmed = parse_load_config_length(
        pipeline / "instructions_explained.txt", "op_fp32_add"
    )
    length = analyze_config_length(bit64, bit128, programmed)
    transport = (
        pipeline
        / "install/cfg_pkg/"
        "op_fp32_add_resnet50_qadd_node0007_fp32_add_bitstream_128b.bin"
    )
    final_pes = sorted(final_json["general_array"]["PE_array"])
    expected_pes = sorted(expected["general_array"]["PE_array"])
    semantic_diffs = [
        record
        for record in leaf_diffs(expected, final_json)
        if not (
            record["path"].endswith(".base_addr")
            and int(record["old"], 0) == int(record["new"], 0)
        )
    ]
    authorized = build["authorized_leaf_deltas"]
    authorized_paths = {record["path"] for record in authorized}
    expected_paths = {f"general_array.PE_array.{name}" for name in ADDED_PES}
    checks = {
        "build_status": build.get("status") == "LOCAL_CONFIG_CORRECTION_MATERIALIZED",
        "proof_valid": proof["valid"] and build["output32_proof"]["valid"],
        "final_exact_semantics": not semantic_diffs,
        "final_eight_pe_set": final_pes == sorted(REQUIRED_PES) == expected_pes,
        "authorized_leaf_set_only": authorized_paths == expected_paths,
        "mapping_valid": mapping_report.get("valid") is True,
        "execplan_valid": exec_report.get("valid") is True,
        "deterministic_execplan": json.loads(
            (bundle / "execplan/double_run_comparison.json").read_text(
                encoding="utf-8"
            )
        ).get("equal")
        is True,
        "config_length_exact_61": (
            length["source_64bit_word_count"] == 61
            and length["physical_128bit_rows"] == 31
            and length["last_row_high_half_is_transport_padding"]
            and length["matches_rtl_padding_contract"]
        ),
        "transport_matches_validated_artifact": sha(transport) == sha(bit128),
        "causal_ledger_valid": (
            build["output32_proof"]["causal_transaction_ledger"][
                "producer_exact_byte_set"
            ]
            == list(range(32))
            and build["output32_proof"]["causal_transaction_ledger"][
                "consumer_required_byte_set"
            ]
            == list(range(32))
        ),
        "microtrace_boundary_exact": [
            record["accepted"]
            for record in build["output32_proof"]["boundary_microtrace"]["events"]
        ]
        == [False, False, False, False, False, True, False],
        "all_negatives_fail_closed": all(
            record["failed_closed"]
            for record in build["output32_proof"]["negative_controls"].values()
        ),
        "address_byte_equal_receipt_reuse": (
            build["output32_proof"]["causal_transaction_ledger"][
                "address_changed"
            ]
            is False
            and build["output32_proof"]["causal_transaction_ledger"][
                "bank_row_receipt_reused"
            ]
            is True
        ),
    }
    errors = [name for name, valid in checks.items() if not valid]
    report = {
        "schema": "qlinearadd-node0007-fp32-output32-validation-v36",
        "valid": not errors,
        "errors": errors,
        "checks": checks,
        "final_json": {
            "path": final_json_path.relative_to(ROOT).as_posix(),
            "bytes": final_json_path.stat().st_size,
            "sha256": sha(final_json_path),
            "pe_names": final_pes,
        },
        "config_length": length,
        "changed_surface": {
            "config": True,
            "mapping": True,
            "execplan": True,
            "addresses": False,
            "numeric": False,
            "workload": False,
            "golden": False,
            "rtl": False,
        },
        "negative_controls": build["output32_proof"]["negative_controls"],
        "numeric_analysis_repeated": False,
        "workload_analysis_repeated": False,
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
                "valid": report["valid"],
                "errors": errors,
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
