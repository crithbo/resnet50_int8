from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5_complete_json_regeneration_v1"
    / "global_average_pool"
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def leaves(value: Any, pointer: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            return [(pointer or "/", value)]
        result = []
        for key, child in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            result.extend(leaves(child, pointer + "/" + escaped))
        return result
    if isinstance(value, list):
        if not value:
            return [(pointer or "/", value)]
        result = []
        for index, child in enumerate(value):
            result.extend(leaves(child, pointer + f"/{index}"))
        return result
    return [(pointer or "/", value)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--negative", choices=[
        "deleted-ledger-leaf",
        "stage1-stride4",
        "placeholder-shape",
        "current-bitstream-mismatch",
    ])
    args = parser.parse_args()
    root = args.root.resolve()
    errors = []
    required = [
        root / "stage_inventory.json",
        root / "source_file_receipts.json",
        root / "field_provenance_ledger.json",
        root / "reference_applicability.json",
        root / "handler_capability.json",
        root / "current_test_diff.json",
        root / "validation_report.json",
        root / "report.json",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"missing required file: {path.name}")
    if errors:
        print(json.dumps({"valid": False, "errors": errors}, indent=2))
        return 1

    inventory = load(root / "stage_inventory.json")
    ledger = load(root / "field_provenance_ledger.json")
    capability = load(root / "handler_capability.json")
    diff = load(root / "current_test_diff.json")
    report = load(root / "report.json")
    configs = {
        path.stem: path
        for path in sorted((root / "complete_json").glob("*.json"))
    }
    actual_keys = {
        (stage, pointer)
        for stage, path in configs.items()
        for pointer, _ in leaves(load(path))
    }
    ledger_entries = list(ledger["entries"])

    if args.negative == "deleted-ledger-leaf":
        ledger_entries = ledger_entries[:-1]
    ledger_keys = {
        (entry["stage"], entry["json_pointer"]) for entry in ledger_entries
    }
    if ledger_keys != actual_keys:
        errors.append("field ledger is not the exact JSON leaf set")

    if len(configs) != 8 or inventory["physical_stage_count"] != 8:
        errors.append("physical stage exact-set differs")
    if inventory["materialized_consumer_equivalence_class_count"] != 4:
        errors.append("equivalence class count differs")
    if ledger["summary"]["unresolved_count"] != 0:
        errors.append("UNRESOLVED leaves present")

    s1 = load(configs["sum_s1"])
    if args.negative == "stage1-stride4":
        for group in ("GROUP0", "GROUP1"):
            s1["buffer_loop_configs"][group]["COL_LC"].update(
                {"start": 0, "end": 32, "stride": 4}
            )
    for group in ("GROUP0", "GROUP1"):
        loop = s1["buffer_loop_configs"][group]["COL_LC"]
        if list(range(loop["start"], loop["end"], loop["stride"])) != [0, 1, 2, 3]:
            errors.append(f"{group} does not cover all four stage1 byte lanes")

    placeholder = next(
        row
        for row in capability["rows"]
        if row["primitive"] == "quant_from_buffer_int32MN_uint8MN"
    )
    if args.negative == "placeholder-shape":
        placeholder["capability"]["shape"] = True
    if placeholder["handler_status"] != "PLACEHOLDER":
        errors.append("native quant handler is not marked placeholder")
    if any(
        value
        for name, value in placeholder["capability"].items()
        if name != "exact_replay"
    ):
        errors.append("placeholder handler overclaims generalized capability")

    equal_rows = [row["encoded_byte_equal"] for row in diff["stage_rows"]]
    if args.negative == "current-bitstream-mismatch":
        equal_rows[0] = False
    if not all(equal_rows):
        errors.append("current encoded stage differs")
    if not diff["execplan"]["byte_equal"]:
        errors.append("current execplan differs")
    if not diff["final_d_index_and_coverage"]["exact"]:
        errors.append("D-index/coverage differs")
    if report["server_package_created_or_modified"]:
        errors.append("server package mutation is forbidden")
    if report["numeric_sum_tail_workload_config_golden_recomputed"]:
        errors.append("frozen numeric/config workload was recomputed")

    forbidden_names = {"PREPARE_AND_RUN.sh"}
    forbidden_suffixes = {".zip"}
    for path in root.rglob("*"):
        if path.is_file() and (
            path.name in forbidden_names or path.suffix.lower() in forbidden_suffixes
        ):
            errors.append(f"forbidden server artifact: {path.relative_to(root)}")

    payload = {
        "schema": "global-average-pool-complete-json-regeneration-validator-v1",
        "mode": args.negative or "positive",
        "valid": not errors,
        "errors": errors,
        "stage_count": len(configs),
        "leaf_count": len(actual_keys),
        "unresolved_count": ledger["summary"]["unresolved_count"],
        "report_sha256": sha256_file(root / "report.json"),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
