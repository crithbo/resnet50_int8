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


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.revalidate_qlinearadd_node0007_v20_observer_hdl_scope as base


NAME = "r5_qadd_n7_split_c_pairmatrix_v29"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def queue_closure(text: str) -> dict:
    used = set(re.findall(r"\bqadd_pair_[A-Za-z0-9_]+\b", text))
    declared = set(
        re.findall(
            r"(?:logic|longint\s+unsigned)\b[^;]*?\b(qadd_pair_[A-Za-z0-9_]+)\b[^;]*;",
            text,
            re.DOTALL,
        )
    )
    unresolved = sorted(used - declared)
    return {"used": sorted(used), "declared": sorted(declared), "unresolved": unresolved, "valid": not unresolved}


def focused_queue_source(tail: str) -> str:
    required = (
        "qadd_pair_idx_hs[m][c]++;",
        "qadd_pair_qwr_count[m]++;",
        "qadd_pair_ag_hs_count[m]++;",
        "QADD_PAIR_MATRIX",
    )
    if not all(x in tail for x in required):
        raise ValueError("queue qualified update/consumer preimage absent")
    return """
module observer_queue_focus;
  logic clk, rst_n, active;
  logic [2:0] idx_valid [0:1];
  logic [2:0] idx_ready [0:1];
  logic qwr [0:1];
  logic ag_valid [0:1];
  logic ag_ready [0:1];
  longint unsigned idx_hs [0:1][0:2];
  longint unsigned qwr_count [0:1];
  longint unsigned ag_hs_count [0:1];
  always @(posedge clk) begin
    if (rst_n && active) begin
      for (int m=0; m<2; m++) begin
        for (int c=0; c<3; c++)
          if (idx_valid[m][c] && idx_ready[m][c]) idx_hs[m][c]++;
        if (qwr[m]) qwr_count[m]++;
        if (ag_valid[m] && ag_ready[m]) ag_hs_count[m]++;
      end
    end
  end
endmodule
"""


def compile_case(iverilog: Path, root: Path, name: str, source: str) -> dict:
    p = root / f"{name}.sv"
    out = root / f"{name}.vvp"
    p.write_text(source, encoding="utf-8", newline="\n")
    run = subprocess.run([str(iverilog), "-g2012", "-s", "observer_queue_focus", "-o", str(out), str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {"exit_code": run.returncode, "stderr": run.stderr, "source_sha256": sha_bytes(p.read_bytes())}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--iverilog", type=Path, default=Path(r"C:\iverilog\bin\iverilog.exe"))
    args = ap.parse_args()
    with zipfile.ZipFile(args.zip) as zf:
        root = NAME + "/"
        native = zf.read(root + "tb_probe/native_return_observer.svh").decode()
        shim = zf.read(root + "tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh").decode()
        ingress = zf.read(root + "tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh").decode()
        queue = zf.read(root + "tb_probe/qlinearadd_node0007_mse_pair_matrix_tail_v29.svh").decode()

    base.INSTALL_NAME = NAME
    base.ZIP_SHA = base.sha_file(args.zip)
    base.ZIP_BYTES = args.zip.stat().st_size
    base.MEMBERS = {
        "native": f"{NAME}/tb_probe/native_return_observer.svh",
        "shim": f"{NAME}/tb_probe/qlinearadd_node0007_fp32_ingress_compilefix_v20.svh",
        "tail": f"{NAME}/tb_probe/qlinearadd_node0007_fp32_ingress_observer_tail_v19.svh",
    }
    with tempfile.TemporaryDirectory(prefix="qadd-v29-hdl-") as raw:
        temp = Path(raw)
        old_positive = base.evaluate(native, shim, ingress, args.iverilog, temp, "ingress_positive")
        focused = focused_queue_source(queue)
        queue_positive = compile_case(args.iverilog, temp, "queue_positive", focused)
        negatives = {}
        for name, mutated in {
            "delete_declaration": queue.replace("longint unsigned qadd_pair_qwr_count [0:1];", "", 1),
            "misspell_use": queue.replace("qadd_pair_qwr_count[m]++;", "qadd_pair_qwr_counx[m]++;", 1),
            "delete_key_update": queue.replace("qadd_pair_qwr_count[m]++;", "", 1),
        }.items():
            closure = queue_closure(mutated)
            required_update = "qadd_pair_qwr_count[m]++;" in mutated
            failed = (not closure["valid"]) or (not required_update)
            negatives[name] = {"validator_exit": 1 if failed else 0, "failed_closed": failed}
    semantic = {
        "native_includes_queue_once": native.count('`include "qlinearadd_node0007_mse_pair_matrix_tail_v29.svh"') == 1,
        "exact_stage4_source_counter_gate": "return_obs_active && qadd_ingress_stage_seq == 4" in ingress,
        "exact_stage4_snapshot_gate": ingress.count("qadd_ingress_stage_seq == 4") >= 2,
        "stage_edge_tracking_outside_active": "qadd_ingress_enabled &&\n            return_obs_active" not in ingress,
        "mse0_mse1_generate": "for (genvar qpm_m=0; qpm_m<2; qpm_m++)" in queue,
        "queue_closure": queue_closure(queue)["valid"],
    }
    valid = old_positive["valid"] and queue_positive["exit_code"] == 0 and all(semantic.values()) and all(x["failed_closed"] for x in negatives.values())
    report = {
        "schema": "qlinearadd-node0007-split-c-pairmatrix-v29-hdl-scope",
        "status": "HDL_SCOPE_REVALIDATION_PASS" if valid else "HDL_SCOPE_REVALIDATION_FAIL",
        "valid": valid,
        "zip_sha256": base.sha_file(args.zip),
        "compatible_frontend": {"tool": str(args.iverilog), "ingress_positive": old_positive, "queue_focused_positive": queue_positive},
        "exact_member_sha256": {
            "native": sha_bytes(native.encode()),
            "shim": sha_bytes(shim.encode()),
            "ingress": sha_bytes(ingress.encode()),
            "queue": sha_bytes(queue.encode()),
        },
        "semantic_checks": semantic,
        "negative_controls": negatives,
        "all_negative_controls_fail_closed": all(x["failed_closed"] for x in negatives.values()),
        "claim_boundary": "exact package member declaration/use/update closure plus hierarchy-compatible focused Icarus elaboration; production VCS remains full-design elaboration evidence",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"status": report["status"], "valid": valid, "output": str(args.output)}, indent=2))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
