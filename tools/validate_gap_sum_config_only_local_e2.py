#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.gap_sum_config_only import (  # noqa: E402
    ARTIFACT_ROOT,
    CLAIM,
    CONFIG_ROOT,
    CONTRACT,
    BYPASS_ANNOTATION,
    build_contract,
    build_read_receipt,
    build_typed_request,
    run_config_bound_simulator,
    validate_input_replay,
    validate_materialized_configs,
)
from resnet50_pipeline.hashing import canonical_json_bytes, sha256_bytes  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=ROOT)
    args = parser.parse_args()
    root = args.project_root.resolve()
    try:
        artifact = root / ARTIFACT_ROOT
        roundtrip = validate_materialized_configs(root, root / CONFIG_ROOT)
        simulator = run_config_bound_simulator(root, root / CONFIG_ROOT)
        typed = build_typed_request()
        input_replay = validate_input_replay(root, typed)
        stored_typed = json.loads(
            (artifact / "typed_request.json").read_text(encoding="utf-8")
        )
        stored_replay = json.loads(
            (artifact / "input_replay_report.json").read_text(encoding="utf-8")
        )
        if stored_typed != typed or stored_replay != input_replay:
            raise ValueError("typed request or noncomputational replay differs")
        current_receipt = build_read_receipt(root)
        stored_receipt = json.loads(
            (artifact / "read_receipt.json").read_text(encoding="utf-8")
        )
        for value in (current_receipt, stored_receipt):
            for entry in value["read_receipt"]:
                entry.pop("read_at", None)
            value["read_receipt"] = [
                entry
                for entry in value["read_receipt"]
                if entry["path"] != ".agents/plan.md"
            ]
        if stored_receipt != current_receipt:
            raise ValueError("read receipt differs from current rule/source inputs")
        contract = json.loads((root / CONTRACT).read_text(encoding="utf-8"))
        expected = build_contract(root, artifact)
        if contract != expected:
            raise ValueError("machine contract differs from current artifacts")
        report = json.loads(
            (artifact / "validation_report.json").read_text(encoding="utf-8")
        )
        if report["status"] != CLAIM or report["bypass_annotation"] != BYPASS_ANNOTATION:
            raise ValueError("claim or seven-field bypass annotation differs")
        if report["quant_tail_dependency"]["materialized"] is not False:
            raise ValueError("quant tail must remain unmaterialized")
        result = {
            "valid": True,
            "status": CLAIM,
            "materialized_roundtrip_sha256": sha256_bytes(
                canonical_json_bytes(roundtrip)
            ),
            "config_bound_simulator_sha256": sha256_bytes(
                canonical_json_bytes(simulator)
            ),
            "contract_sha256": contract["contract_sha256"],
            "complete_gap_target": False,
        }
    except Exception as error:
        print(f"GAP sum config-only validation failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
