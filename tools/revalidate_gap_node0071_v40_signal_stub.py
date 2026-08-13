from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v35_signal_stub as base


ROOT_NAME = "r5_n71_gap_v40_lc_supply_conservation_diag"
TARGET = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{ROOT_NAME}.zip"
)
FEATURE = "RETURN_OBS_LC_SUPPLY_CONSERVATION"
LOCAL_EXPECTED_LEAF_SHA = (
    "b5fc30fa970a4ed38ebdfaf825946a80562ded91d72c600dd1ee89d14103b1ef"
)
MOCK_ACTUAL_LEAF = (
    b"// simulated cloud-current server leaf; deliberately differs from "
    b"local expected\nmodule cloud_identity_only; endmodule\n"
)
MOCK_ACTUAL_LEAF_SHA = hashlib.sha256(MOCK_ACTUAL_LEAF).hexdigest()
PRIOR_WRITE = base.write_mock_tools
PRIOR_VALIDATE_RETURN = base.validate_return


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise ValueError(f"{label}: marker count {text.count(old)}")
    return text.replace(old, new, 1)


def write_mock_tools(root: Path):
    bin_dir, sim_started = PRIOR_WRITE(root)
    (root / "mock_actual_cloud_leaf.sv").write_bytes(MOCK_ACTUAL_LEAF)
    wrapper = bin_dir / "make"
    text = wrapper.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "dbrr=false\ndbrr_limit=false\n",
        "dbrr=false\ndbrr_limit=false\nlcsc=false\nlcsc_limit=false\n",
        "v40 variables",
    )
    text = replace_once(
        text,
        "    +RETURN_OBS_DBCLK_RD_READY_LIMIT=256) dbrr_limit=true;;\n",
        "    +RETURN_OBS_DBCLK_RD_READY_LIMIT=256) dbrr_limit=true;;\n"
        f"    +{FEATURE}) lcsc=true;;\n"
        f"    +{FEATURE}_LIMIT=512) lcsc_limit=true;;\n",
        "v40 argv",
    )
    text = replace_once(
        text,
        '[ "$dbrr_limit" = true ] || exit 67\n',
        '[ "$dbrr_limit" = true ] || exit 67\n'
        '[ "$lcsc" = true ] || exit 64\n'
        '[ "$lcsc_limit" = true ] || exit 65\n',
        "v40 guards",
    )
    text = replace_once(
        text,
        "dbclk_rd_ready=1 dbclk_rd_ready_limit=256'",
        "dbclk_rd_ready=1 dbclk_rd_ready_limit=256 "
        "lc_supply_conservation=1 lc_supply_conservation_limit=512'",
        "v40 time0",
    )
    text = replace_once(
        text,
        "  '0 | DBCLK_RD_READY_WITNESS_V1 | event=SAFE_STUB "
        "ready_low=0:0/0:0 data_vld_low=0:0/0:0 "
        "rd_ob_full=0:0/0:0 wr_ob_full=0:0/0:0 "
        "barrier=0:0/0:0' \\\n"
        "  >\"$observer_log\"\n",
        "  '0 | DBCLK_RD_READY_WITNESS_V1 | event=SAFE_STUB "
        "ready_low=0:0/0:0 data_vld_low=0:0/0:0 "
        "rd_ob_full=0:0/0:0 wr_ob_full=0:0/0:0 "
        "barrier=0:0/0:0' \\\n"
        "  '0 | LC_SUPPLY_CONSERVATION_COUNTS_V1 | event=SAFE_STUB "
        "edge=0 bq_wr=0/0 bq_rd=0/0 mq_wr=0/0 mq_rd=0/0 "
        "req=0/0 records=0 limit=512' \\\n"
        "  '0 | LC_SUPPLY_CONSERVATION_STATE_V1 | event=SAFE_STUB "
        "bq_count=0/0 bq_full=0 bq_empty=3 mq_count=0/0 "
        "mq_full=0 mq_empty=3 mem_tag0=0 mem_tag3=0 mem_bp0=0 "
        "mem_bp3=0 mem_out_vld=0 mem_out_bp=0 req_vld=0 "
        "req_ready=3 buf_out_vld=0 buf_out_bp=0' \\\n"
        "  '0 | LC_SUPPLY_CONSERVATION_WITNESS_V1 | event=SAFE_STUB "
        "bq_full=0:0/0:0 mem_empty=0:0/0:0' \\\n"
        "  >\"$observer_log\"\n",
        "v40 records",
    )
    wrapper.write_text(text, encoding="utf-8", newline="\n")
    wrapper.chmod(0o755)
    return bin_dir, sim_started


def validate_return(package: Path, mock_server: Path):
    result = PRIOR_VALIDATE_RETURN(package, mock_server)
    return_zip = mock_server / f"{ROOT_NAME}_return.zip"
    root = f"{ROOT_NAME}_return"
    with zipfile.ZipFile(return_zip) as archive:
        binding = archive.read(
            f"{root}/evidence/observer_binding.txt"
        ).decode()
        argv = archive.read(
            f"{root}/evidence/actual_simulator_argv.txt"
        ).decode()
    result["lc_supply_conservation_binding"] = {
        "enabled":
            "lc_supply_conservation_enabled=true" in binding,
        "limit_512":
            "lc_supply_conservation_limit=512" in binding,
        "records_returned":
            "lc_supply_conservation_records_returned=true" in binding,
        "actual_argv_enable": f"+{FEATURE}" in argv,
        "actual_argv_limit": f"+{FEATURE}_LIMIT=512" in argv,
    }
    if not all(result["lc_supply_conservation_binding"].values()):
        raise ValueError("v40 feature signal-finalizer binding differs")
    return result


def validate(target_zip: Path, bash: Path):
    base.ROOT_NAME = ROOT_NAME
    base.TARGET = TARGET
    base.ZIP_SHA256 = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    base.write_mock_tools = write_mock_tools
    base.validate_return = validate_return
    result = base.validate(target_zip, bash)
    result["schema"] = (
        "gap-node0071-v40-lc-supply-safe-signal-stub-v1"
    )
    checks = result.setdefault("checks", {})
    checks["lc_supply_conservation_feature_bound"] = all(
        result["return"]["lc_supply_conservation_binding"].values()
    )
    safe_started = bool(checks.get("safe_sim_stub_started"))
    result["cloud_identity_mismatch_nonblocking_positive"] = {
        "local_expected_leaf_sha256": LOCAL_EXPECTED_LEAF_SHA,
        "simulated_server_leaf_sha256": MOCK_ACTUAL_LEAF_SHA,
        "sha_mismatch": MOCK_ACTUAL_LEAF_SHA != LOCAL_EXPECTED_LEAF_SHA,
        "compile_completed": checks.get("compile_completed") is True,
        "safe_simulator_stub_reached": safe_started,
        "runner_did_not_gate_on_identity_mismatch": safe_started,
        "pass": (
            MOCK_ACTUAL_LEAF_SHA != LOCAL_EXPECTED_LEAF_SHA
            and checks.get("compile_completed") is True
            and safe_started
        ),
    }
    checks["cloud_identity_mismatch_nonblocking"] = result[
        "cloud_identity_mismatch_nonblocking_positive"
    ]["pass"]
    result["status"] = "PASS" if all(checks.values()) else "FAIL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--bash",
        type=Path,
        default=Path(r"C:\Program Files\Git\bin\bash.exe"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = validate(args.target_zip.resolve(), args.bash.resolve())
        exit_code = 0 if result["status"] == "PASS" else 1
    except Exception as error:
        result = {
            "schema":
                "gap-node0071-v40-lc-supply-safe-signal-stub-v1",
            "status": "FAIL",
            "error": str(error),
        }
        exit_code = 1
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
