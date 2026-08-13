#!/usr/bin/env python3
"""Independent deterministic validation for the relocated node0075 materializer."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tools/validate_node0075_df23e4d_materializer.py"
BUILDER = ROOT / "tools/build_node0075_e1fb0f7_bankrow_relocated_materializer_v2.py"
PYTHON = Path(sys.executable).resolve()
TEST_ID = "r5-node0075-e1fb0f7-bankrow-relocated-eight-pass-materializer-v2"
TARGET_STEM = "node0075_e1fb0f7_bankrow_relocated_eight_pass_target_v2"
FINAL_D_LOCAL_BASE = 0x002A4800


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_base():
    spec = importlib.util.spec_from_file_location("node0075_validator_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base validator: {BASE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.TEST_ID = TEST_ID
    module.REPORT_ROOT = ROOT / "artifacts/operator_config_validation" / TEST_ID
    module.REPORT = module.REPORT_ROOT / "materializer_report.json"
    module.TARGET = module.REPORT_ROOT / f"{TARGET_STEM}.json"
    module.OUTPUT = module.NDP / "model_execplan/output" / TARGET_STEM
    module.VALIDATION = (
        module.REPORT_ROOT / "determinism_and_config_binding_validation.json"
    )
    def relocated_inventory_paths():
        report = module._json(module.REPORT)
        sca = module._json(module.OUTPUT / "sca_cfg.json")
        paths = [
            module.REPORT,
            module.TARGET,
            module.REPORT_ROOT / "normalized_target.json",
            module.REPORT_ROOT / "pipeline.stdout.log",
            module.REPORT_ROOT / "pipeline.stderr.log",
            module.OUTPUT / "install/execplan.txt",
            module.OUTPUT / "instructions_explained.txt",
            module.OUTPUT / "sca_cfg.json",
            module.OUTPUT / "sca_cfg_D.json",
            module.OUTPUT / f"{TARGET_STEM}_withbaseaddr.json",
        ]
        paths.extend(ROOT / item["path"] for item in report["templates"])
        paths.extend(sorted((module.OUTPUT / "jsons").glob("*.json")))
        paths.extend(sorted((module.OUTPUT / "config").glob("*/mapping_review.json")))
        paths.extend(sorted((module.OUTPUT / "config").glob("*/*bitstream_128b.bin")))
        paths.extend(sorted((module.OUTPUT / "config").glob("*/*bitstream_64b.bin")))
        for value in sca.values():
            if isinstance(value, dict) and isinstance(value.get("path"), str):
                candidate = module.OUTPUT / value["path"]
                if candidate.is_file():
                    paths.append(candidate)
        unique = sorted(set(paths), key=lambda path: path.as_posix())
        module._fail_unless(
            all(path.is_file() for path in unique),
            "relocated inventory contains a missing file",
        )
        return unique
    module._inventory_paths = relocated_inventory_paths
    return module


def decode_local(byte_addr: int) -> dict[str, int | bool]:
    line = byte_addr >> 4
    col = line & 0x3F
    row = (line >> 6) & 0x1FFF
    bank = (line >> 19) & 0x3
    return {"bank": bank, "row": row, "col": col, "valid": row < 6144}


def run_builder() -> None:
    completed = subprocess.run(
        [str(PYTHON), str(BUILDER)],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"relocated materializer failed: {completed.stderr[-3000:]}")


def validate() -> dict:
    module = load_base()
    static = module._validate_static_binding()
    before = module._inventory()
    run_builder()
    module._validate_static_binding()
    after = module._inventory()
    if before != after:
        differing = sorted(
            path for path in set(before) | set(after) if before.get(path) != after.get(path)
        )
        raise RuntimeError("deterministic inventory differs: " + ", ".join(differing[:32]))

    target = module._json(module.TARGET)
    sca = module._json(module.OUTPUT / "sca_cfg.json")
    sca_d = module._json(module.OUTPUT / "sca_cfg_D.json")
    round_ops = target["operators"][16:24]
    bases = [
        int(op["attributes"]["physical_bindings"]["output"]
            ["per_slice_base_addresses"]["0"], 16)
        for op in round_ops
    ]
    if bases != [FINAL_D_LOCAL_BASE + index * 128 for index in range(8)]:
        raise RuntimeError("fresh final-D address sequence differs")

    critical = {
        "final_d_first": FINAL_D_LOCAL_BASE,
        "final_d_last_line": FINAL_D_LOCAL_BASE + 1024 - 16,
        "exec_first": int(sca["Exec_Base"], 16),
        "exec_last_line": int(sca["Exec_Base"], 16) + int(sca["Exec_Length"]) * 16 - 16,
    }
    for key, item in sca.items():
        if key.endswith("_config") and isinstance(item, dict):
            critical[f"{key}_first"] = int(item["base_addr"], 16)
    for name, address in critical.items():
        if not decode_local(address)["valid"]:
            raise RuntimeError(f"physical bank-row invalid: {name}=0x{address:08x}")
    for key, item in sca_d.items():
        if not decode_local(int(item["base_addr"], 16))["valid"]:
            raise RuntimeError(f"formal D physical bank-row invalid: {key}")

    result = {
        "schema": "node0075-e1fb0f7-bankrow-relocated-materializer-validation-v2",
        "test_id": TEST_ID,
        "status": "DETERMINISTIC_CONFIG_BOUND_LOCAL_E2_PASS",
        "passed": True,
        "static_binding": static,
        "determinism": {
            "comparison_build_count": 2,
            "validator_triggered_rebuild_count": 1,
            "exact_inventory_equal": True,
            "inventory_file_count": len(after),
            "inventory_sha256": hashlib.sha256(
                json.dumps(after, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        },
        "physical_bank_row_validation": {
            "address_unit_bytes": 16,
            "bank_bits": 2,
            "row_bits": 13,
            "column_bits": 6,
            "enabled_rows_per_bank": 6144,
            "critical_addresses": [
                {"name": name, "address": f"0x{address:08x}", **decode_local(address)}
                for name, address in sorted(critical.items())
            ],
            "formal_d_fragment_count": len(sca_d),
            "all_valid": True,
        },
        "claim_boundary": {
            "local_config_bound_e2": True,
            "server_actual_acceptance": False,
            "natural_terminal": False,
            "formal_d_runtime_match": False,
            "candidate_release": False,
        },
    }
    module._write_json(module.VALIDATION, result)
    result["validation_identity"] = {
        "path": module.VALIDATION.relative_to(ROOT).as_posix(),
        "bytes": module.VALIDATION.stat().st_size,
        "sha256": sha256(module.VALIDATION),
    }
    return result


def main() -> int:
    try:
        result = validate()
    except Exception as exc:
        print(f"NODE0075_BANKROW_RELOCATED_VALIDATION_FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
