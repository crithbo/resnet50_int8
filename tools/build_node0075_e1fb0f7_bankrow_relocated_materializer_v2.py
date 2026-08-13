#!/usr/bin/env python3
"""Build a fresh node0075 materialization outside disabled physical DDR rows.

The arithmetic, mapping, eight-pass A schedule, weights and golden tensors are
reused byte-for-byte from the frozen node0075 materializer.  Only the formal-D
base is changed; the active ndp-sim allocator consequently regenerates the
address-bound JSON, CONFIG bitstreams, execplan and SCA in a fresh namespace.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "tools/build_node0075_df23e4d_materializer.py"
TEST_ID = "r5-node0075-e1fb0f7-bankrow-relocated-eight-pass-materializer-v2"
TARGET_STEM = "node0075_e1fb0f7_bankrow_relocated_eight_pass_target_v2"
FINAL_D_LOCAL_BASE = 0x002A4800


def _load_base():
    spec = importlib.util.spec_from_file_location("node0075_materializer_base", BASE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load base materializer: {BASE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build() -> dict:
    module = _load_base()
    module.TEST_ID = TEST_ID
    module.TARGET_STEM = TARGET_STEM
    module.OUT = ROOT / "artifacts/operator_config_validation" / TEST_ID
    module.TARGET = module.OUT / f"{TARGET_STEM}.json"
    module.PIPELINE_OUT = module.NDP / "model_execplan/output" / TARGET_STEM
    module.FINAL_D_LOCAL_BASE = FINAL_D_LOCAL_BASE

    # These templates are frozen node0075-owned inputs and are already present.
    # Return their identities without rewriting the active shared files.
    module._materialize_accumulate_template = lambda: (
        module.NDP / "jsons/MatMulInt32Accumulate.json"
    )
    module._materialize_scale_template = lambda: (
        module.NDP / "jsons/Node0075RequantScaleInt32ToFp32.json"
    )
    module._materialize_round_template = lambda: (
        module.NDP / "jsons/Node0075RequantRoundFp32ToUint8.json"
    )

    report = module.build()
    report_path = module.OUT / "materializer_report.json"
    persisted = json.loads(report_path.read_text(encoding="utf-8"))
    persisted["schema"] = "node0075-e1fb0f7-bankrow-relocated-materializer-report-v2"
    persisted["address_repair"] = {
        "cause": (
            "v5 SCA placed D/CONFIG/execplan in bank2 rows >= 0x1800; "
            "the production PHY model rejected those rows before CONFIG execution"
        ),
        "old_final_d_local_base": "0x01700000",
        "new_final_d_local_base": f"0x{FINAL_D_LOCAL_BASE:08x}",
        "changed_causal_surface": [
            "final D physical base",
            "address-bound round-stage JSON",
            "round CONFIG bitstreams",
            "generated CONFIG/execplan/SCA placement",
        ],
        "arithmetic_mapping_and_a_schedule_changed": False,
        "functional_rtl_modified": False,
    }
    persisted["release"] = {
        "candidate_release": False,
        "package_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "package_release": "NONE_PENDING_INTEGRATION_AND_FINAL_ZIP_AUDIT",
        "server_uploaded": False,
        "server_run": False,
        "lease_taken": False,
    }
    module._write_json(report_path, persisted)
    return persisted


def main() -> int:
    try:
        report = build()
    except Exception as exc:
        print(f"NODE0075_BANKROW_RELOCATED_MATERIALIZER_FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report.get("status") == "CONFIG_BOUND_LOCAL_E2_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
