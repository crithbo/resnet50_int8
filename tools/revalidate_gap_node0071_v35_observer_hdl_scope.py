from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import revalidate_gap_node0071_v33_observer_hdl_scope as prior


INSTALL_NAME = "r5_n71_gap_v36_dbclk_rdready_diag"
OBSERVER_RELATIVE = "tb_probe/native_return_observer.svh"
DECL_ANCHOR = "    // v34: clk_db-owned queue -> WR conjunction -> RD supply diagnostic."
DECL_END = "    // v33: MSE0 Buffer_AG_Idx_Queue input/match/FIFO diagnostic."
SAMPLER_ANCHOR = "    // v34 sampler: all qualified events are sampled in their clk_db owner domain."
SAMPLER_END = "    // v33 sampler: qualified input accepts and FIFO accepts only."
CRITICAL_UPDATE = "return_obs_dbrr_queue_enqueue[dbrr_flow]++;"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def section(text: str, start: str, end: str) -> str:
    left = text.find(start)
    right = text.find(end, left)
    if left < 0 or right <= left:
        raise ValueError(f"focused section absent: {start}")
    return text[left:right]


def run(argv: list[str], cwd: Path) -> dict[str, Any]:
    process = subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)
    return {
        "argv": argv,
        "exit_code": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "stdout_sha256": sha256_bytes(process.stdout.encode()),
        "stderr_sha256": sha256_bytes(process.stderr.encode()),
    }


MOCKS = r'''
module v35_ndp; logic clk, rst_n; endmodule
'''


SIGNALS = r'''
  v35_ndp u_NDP_Top_new();
  bit return_obs_enabled, return_obs_active;
  integer return_obs_fd, return_obs_group_id, return_obs_local_slice_id;
  logic return_obs_rd_req_valid_mon[0:0][0:0][0:1];
  logic return_obs_rd_req_ready_mon[0:0][0:0][0:1];
  logic return_obs_flow_q_wr_mon[0:0][0:0][0:1];
  logic return_obs_flow_q_rd_mon[0:0][0:0][0:1];
  logic return_obs_flow_q_full_mon[0:0][0:0][0:1];
  logic return_obs_flow_q_empty_mon[0:0][0:0][0:1];
  logic [1:0] return_obs_rd_ib_wr_hs_mon[0:0][0:0][0:1];
  logic [1:0] return_obs_rd_ib_rd_hs_mon[0:0][0:0][0:1];
  logic return_obs_rd_prep_wr_mon[0:0][0:0][0:1];
  logic return_obs_rd_prep_rd_mon[0:0][0:0][0:1];
  logic return_obs_flow_ob_wr_mon[0:0][0:0][0:1];
  logic return_obs_flow_ob_bp_mon[0:0][0:0][0:1];
  logic return_obs_bp_data_ready_mon[0:0][0:0][0:1];
  logic return_obs_bp_data_vld_mon[0:0][0:0][0:1];
  logic return_obs_bp_rd_ob_full_mon[0:0][0:0][0:1];
  logic return_obs_bp_ob_full_mon[0:0][0:0][0:1];
  logic return_obs_bp_barrier_mon[0:0][0:0][0:1];
  logic [7:0] return_obs_bp_prepared_count_mon[0:0][0:0][0:1];
  logic [7:0] return_obs_rd_spatial_mon[0:0][0:0][0:1];
'''


def ledger(observer: str) -> dict[str, Any]:
    decl = section(observer, DECL_ANCHOR, DECL_END)
    sampler = section(observer, SAMPLER_ANCHOR, SAMPLER_END)
    used = set(re.findall(r"\breturn_obs_dbrr_[A-Za-z0-9_]+\b", decl + sampler))
    declared = set(
        re.findall(
            r"\b(?:bit|int|longint unsigned)\s+(return_obs_dbrr_[A-Za-z0-9_]+)",
            decl,
        )
    )
    declared.add("return_obs_dbrr_reset")
    undeclared = sorted(used - declared - {"return_obs_dbrr_reset"})
    checks = {
        "owner_clock": "always @(posedge u_NDP_Top_new.clk)" in sampler
        and "clk_sg" not in sampler,
        "owner_reset": "u_NDP_Top_new.rst_n" in sampler,
        "qualified_request": "return_obs_rd_req_valid_mon" in sampler
        and "return_obs_rd_req_ready_mon" in sampler,
        "qualified_queue": "return_obs_flow_q_wr_mon" in sampler
        and "!return_obs_flow_q_full_mon" in sampler
        and "return_obs_flow_q_rd_mon" in sampler
        and "!return_obs_flow_q_empty_mon" in sampler,
        "direct_supply": all(
            token in sampler
            for token in (
                "return_obs_rd_ib_wr_hs_mon",
                "return_obs_rd_ib_rd_hs_mon",
                "return_obs_rd_prep_wr_mon",
                "return_obs_rd_prep_rd_mon",
                "return_obs_bp_data_ready_mon",
                "return_obs_bp_data_vld_mon",
                "return_obs_bp_rd_ob_full_mon",
                "return_obs_bp_ob_full_mon",
                "return_obs_bp_barrier_mon",
            )
        ),
        "critical_update": CRITICAL_UPDATE in sampler,
        "bounded": "return_obs_dbrr_emit_count < return_obs_dbrr_limit" in sampler,
        "record": "DBCLK_RD_READY_EVENT_V1" in sampler,
    }
    return {
        "declared": sorted(declared),
        "used": sorted(used),
        "undeclared": undeclared,
        "checks": checks,
        "valid": not undeclared and all(checks.values()),
    }


def projection(observer: str) -> str:
    decl = section(observer, DECL_ANCHOR, DECL_END)
    sampler = section(observer, SAMPLER_ANCHOR, SAMPLER_END)
    sampler = sampler.replace("return_obs_group_id", "0")
    sampler = sampler.replace("return_obs_local_slice_id", "0")
    return (
        MOCKS
        + "\nmodule v35_dbrr_focus;\n"
        + SIGNALS
        + decl
        + sampler
        + "\nendmodule\n"
    )


def replace_in_sampler(observer: str, old: str, new: str) -> str:
    left, right = observer.split(SAMPLER_ANCHOR, 1)
    return left + SAMPLER_ANCHOR + right.replace(old, new, 1)


def evaluate(observer: str, iverilog: Path, temp: Path, stem: str) -> dict[str, Any]:
    closure = ledger(observer)
    source = projection(observer)
    source_path = temp / f"{stem}.sv"
    source_path.write_text(source, encoding="utf-8", newline="\n")
    compile_result = run(
        [str(iverilog), "-g2012", "-tnull", "-s", "v35_dbrr_focus", str(source_path)],
        temp,
    )
    return {
        "valid": closure["valid"] and compile_result["exit_code"] == 0,
        "ledger": closure,
        "focused_compile": compile_result,
        "projection_sha256": sha256_bytes(source.encode()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-zip", type=Path, required=True)
    parser.add_argument(
        "--iverilog", type=Path, default=Path(r"C:\iverilog\bin\iverilog.exe")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        target = args.target_zip.resolve()
        with zipfile.ZipFile(target) as archive:
            if archive.testzip() is not None:
                raise ValueError("ZIP CRC differs")
            observer_payload = archive.read(
                f"{INSTALL_NAME}/{OBSERVER_RELATIVE}"
            )
        observer = observer_payload.decode("utf-8")
        version = run([str(args.iverilog.resolve()), "-V"], Path.cwd())
        with tempfile.TemporaryDirectory(prefix="gap-v35-hdl-") as temporary:
            temp = Path(temporary)
            positive = evaluate(observer, args.iverilog.resolve(), temp, "positive")
            mutations = [
                (
                    "declaration_removed",
                    observer.replace(
                        "    longint unsigned return_obs_dbrr_queue_enqueue [0:1];\n",
                        "",
                        1,
                    ),
                ),
                (
                    "sampler_use_misspelled",
                    replace_in_sampler(
                        observer,
                        "return_obs_rd_req_ready_mon[return_obs_group_id]",
                        "return_obs_rd_req_ready_typo[return_obs_group_id]",
                    ),
                ),
                (
                    "critical_update_removed",
                    observer.replace(CRITICAL_UPDATE, "/* update removed */", 1),
                ),
                (
                    "owner_clock_reverted",
                    replace_in_sampler(
                        observer,
                        "always @(posedge u_NDP_Top_new.clk)",
                        "always @(posedge u_NDP_Top_new.clk_sg)",
                    ),
                ),
            ]
            controls = []
            for name, mutated in mutations:
                check = evaluate(mutated, args.iverilog.resolve(), temp, name)
                controls.append(
                    {
                        "name": name,
                        "failed_closed": not check["valid"],
                        "compile_exit_code": check["focused_compile"]["exit_code"],
                        "ledger_valid": check["ledger"]["valid"],
                    }
                )
        # Reuse the proven v33 focused XMR projection against the corrected sampler.
        prior.INSTALL_NAME = INSTALL_NAME
        prior.EXPECTED_ZIP_SHA256 = sha256_path(target)
        prior.EXPECTED_ZIP_BYTES = target.stat().st_size
        prior.MOCKS = prior.MOCKS.replace(
            "logic clk_sg, rst_n_sg;", "logic clk, rst_n;"
        )
        original_projection = prior.projection

        def prior_projection(text: str) -> str:
            return original_projection(text).replace(
                "  longint unsigned return_obs_sg_clock_edge_count;\n",
                "  longint unsigned return_obs_sg_clock_edge_count;\n"
                "  longint unsigned return_obs_db_clock_edge_count;\n",
            )

        prior.projection = prior_projection
        with tempfile.TemporaryDirectory(prefix="gap-v35-bq-hdl-") as temporary:
            corrected_bq = prior.evaluate(
                observer, args.iverilog.resolve(), Path(temporary), "corrected_bq"
            )
        passed = (
            version["exit_code"] == 0
            and positive["valid"]
            and corrected_bq["valid"]
            and all(item["failed_closed"] for item in controls)
        )
        result = {
            "schema": "gap-node0071-v35-focused-observer-hdl-v1",
            "status": "PASS" if passed else "FAIL",
            "pass": passed,
            "target_zip": str(target),
            "target_zip_size_bytes": target.stat().st_size,
            "target_zip_sha256": sha256_path(target),
            "observer_member": f"{INSTALL_NAME}/{OBSERVER_RELATIVE}",
            "observer_sha256": sha256_bytes(observer_payload),
            "tool": {
                "path": str(args.iverilog.resolve()),
                "version_exit_code": version["exit_code"],
                "version_stdout": version["stdout"],
                "version_stderr": version["stderr"],
            },
            "new_v35_positive": positive,
            "corrected_v33_queue_positive": corrected_bq,
            "negative_controls": controls,
            "all_negative_controls_fail_closed": all(
                item["failed_closed"] for item in controls
            ),
            "full_design_elaboration_claimed": False,
            "claim_boundary": (
                "exact final package-local v35 declarations/sampler and modified "
                "v33 queue sampler syntax/name-resolution with focused mocks; "
                "production full-design elaboration remains server evidence"
            ),
        }
        exit_code = 0 if passed else 1
    except Exception as error:
        result = {
            "schema": "gap-node0071-v35-focused-observer-hdl-v1",
            "status": "FAIL",
            "pass": False,
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
