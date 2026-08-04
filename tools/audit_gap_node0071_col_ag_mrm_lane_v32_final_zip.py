import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import audit_gap_node0071_col_ag_mrm_lane_v31_final_zip as base


ROOT_NAME = "r5_n71_gap_v32_col_ag_mrm_lane_rulebind"
base.ROOT_NAME = ROOT_NAME
base.RUNNER_REPORT = base.PACKAGE_DIR / f"{ROOT_NAME}.runner.json"
base.SIGNAL_REPORT = base.PACKAGE_DIR / f"{ROOT_NAME}.signal_stub.json"
base.HDL_REPORT = base.PACKAGE_DIR / f"{ROOT_NAME}.hdl_scope.json"
base.OUTPUT = base.PACKAGE_DIR / f"{ROOT_NAME}.final_zip_rule_self_audit.json"
ORIGINAL_CONFIGURE = base.configure


def configure() -> None:
    ORIGINAL_CONFIGURE()
    base.audit.EXTRA_VALIDATORS = [
        (
            "col_ag_mrm_lane_validator_and_controls",
            ROOT / "tools/validate_gap_node0071_col_ag_mrm_lane_v32.py",
            [
                str(base.audit.ZIP),
                "--root-name",
                ROOT_NAME,
                "--runner-report",
                str(base.RUNNER_REPORT),
            ],
        ),
    ]


base.configure = configure

if __name__ == "__main__":
    exit_code = base.main()
    result = json.loads(base.OUTPUT.read_text(encoding="utf-8"))
    result["schema"] = "gap-node0071-v32-col-ag-mrm-final-audit-v1"
    result["diagnostic_contract"]["test_id"] = (
        "r5-gap-node0071-v32-col-ag-mrm-byte-lane-rulebind-diagnostic"
    )
    base.OUTPUT.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    raise SystemExit(exit_code)
