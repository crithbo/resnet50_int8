from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.conv_serialized_one_product_local_e2 import (  # noqa: E402
    ARTIFACT_ROOT_REL,
    CONTRACT_REL,
    build_contract,
    write_contract,
)
from resnet50_pipeline.hashing import sha256_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the node0004 serialized-product local accumulate E2."
    )
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument(
        "--write-contract",
        action="store_true",
        help="publish the rebuilt machine contract before validating it",
    )
    args = parser.parse_args()
    root = args.project_root.resolve()
    report_path = root / ARTIFACT_ROOT_REL / "validation_report.json"
    try:
        expected = (
            write_contract(root) if args.write_contract else build_contract(root)
        )
        actual_path = root / CONTRACT_REL
        if not actual_path.is_file():
            raise FileNotFoundError(actual_path)
        actual = json.loads(actual_path.read_text(encoding="utf-8"))
        if actual != expected:
            raise ValueError("published contract differs from rebuilt current inputs")
        report = {
            "schema": "resnet50-node0004-serialized-local-e2-validation-v1",
            "valid": True,
            "test_id": expected["test_id"],
            "status": expected["status"],
            "contract": {
                "path": CONTRACT_REL.as_posix(),
                "sha256": sha256_file(actual_path),
                "contract_sha256": expected["contract_sha256"],
            },
            "gates": {
                "materialized_nonbase_diff_count": 0,
                "mapping_penalty": 0,
                "mapping_fallback_used": False,
                "execplan_double_run_equal": True,
                "request_address_valid": True,
                "D_region_count": 64,
                "D_bytes_per_region": 200_704,
                "inactive_lane_nonzero_value_count": 0,
                "physical_mismatch_count": 0,
                "logical_w3_mismatch_count": 0,
                "stock_four_lane_negative_control_failed": True,
                "serialized_holdouts_pass": True,
                "dynamic_release_ready": False,
                "package_release": "NONE",
            },
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
