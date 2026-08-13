from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


PACKAGE = "r5_n4_hw_v80_ack_phase_diag"
INSTANCE = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]."
    "u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
    "u_Buffer_AG_Idx_Queue.codex_probe_buf_ack_phase_witness_inst"
)


def line(seq: int, phase: str, *, full: str = "0", bpmask: str = "3", bp: str = "0", gotten: str = "0") -> str:
    return (
        f"CODEX_PROBE_V1 kind=RING_STATE boundary=buf_ack_phase_witness instance={INSTANCE} "
        f"time={100 + seq} mask=0 payload=0 seq={seq} phase={phase} wr=1 full={full} all=1 "
        f"valid=3 same=3 gotten={gotten} keep=3 bpmask={bpmask} bp={bp} mode=2 "
        "row=36 col=75 rowtag=f3 coltag=f3"
    )


def run(parser: Path, root: Path, name: str, lines: list[str]) -> tuple[int, dict]:
    log = root / f"{name}.log"
    out = root / f"{name}.json"
    log.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    done = subprocess.run([sys.executable, str(parser), "--log", str(log), "--output", str(out)], text=True, capture_output=True, check=False)
    return done.returncode, json.loads(out.read_text(encoding="utf-8")) if out.is_file() else {}


def triplet(**stable) -> list[str]:
    return [line(0, "ACTIVE"), line(0, "DELTA", **{k: v for k, v in stable.items() if k != "gotten"}), line(0, "STABLE", **stable)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="n4v80_phase_") as raw:
        root = Path(raw)
        with zipfile.ZipFile(args.zip) as archive:
            parser = root / "buffer_ack_phase_parser.py"
            parser.write_bytes(archive.read(f"{PACKAGE}/package_tools/buffer_ack_phase_parser.py"))
            observer = archive.read(f"{PACKAGE}/tb_probe/buffer_ack_phase_observer.svh").decode()
            runner = archive.read(f"{PACKAGE}/PREPARE_AND_RUN.sh").decode()
        checks["actual_final_hdl_has_active_delta_stable"] = all(token in observer for token in ('codex_emit("ACTIVE"', 'codex_emit("DELTA"', 'codex_emit("STABLE"'))
        checks["actual_final_runner_compiles_phase_observer"] = "$package_root/tb_probe/buffer_ack_phase_observer.svh" in runner
        checks["actual_final_argv_binds_limit"] = runner.count("+RETURN_OBS_BUF_ACK_PHASE_LIMIT=128") == 2

        rc, value = run(parser, root, "settled_consumed", triplet(bp="3", gotten="3"))
        checks["settled_and_consumed"] = rc == 0 and value.get("decision") == "ACTIVE_SAMPLE_TRANSIENT_SETTLES_AND_CONSUMER_ACCEPTS"
        rc, value = run(parser, root, "settled_not_consumed", triplet(bp="3", gotten="0"))
        checks["settled_but_not_consumed"] = rc == 0 and value.get("decision") == "ACK_SETTLES_BUT_INPUT_CONSUMER_DOES_NOT_ACCEPT"
        rc, value = run(parser, root, "persistent", triplet(bp="0", gotten="0"))
        checks["persistent_mismatch"] = rc == 0 and value.get("decision") == "PERSISTENT_PUBLIC_ACK_EQUATION_MISMATCH"
        delta_only = [line(0, "ACTIVE"), line(0, "DELTA", bp="0"), line(0, "STABLE", bp="3", gotten="3")]
        rc, value = run(parser, root, "delta_only", delta_only)
        checks["multi_delta_settle"] = rc == 0 and value.get("decision") == "MULTI_DELTA_SETTLES_BEFORE_HALF_CYCLE"
        operand = [line(0, "ACTIVE"), line(0, "DELTA", bp="0"), line(0, "STABLE", full="1", bp="0")]
        rc, value = run(parser, root, "operand", operand)
        checks["operand_transition"] = rc == 0 and value.get("decision") == "OPERAND_TRANSITION_EXPLAINS_ACTIVE_MISMATCH"
        rc, value = run(parser, root, "missing", [])
        checks["missing_fails_closed"] = rc != 0 and value.get("decision") == "NO_TARGET_PHASE_WITNESS"
        rc, value = run(parser, root, "incomplete", [line(0, "ACTIVE")])
        checks["incomplete_fails_closed"] = rc != 0 and value.get("decision") == "PHASE_WITNESS_INCOMPLETE"
        wrong = line(0, "ACTIVE").replace("MSE_INST[4]", "MSE_INST[3]")
        rc, value = run(parser, root, "wrong_instance", [wrong])
        checks["wrong_instance_fails_closed"] = rc != 0 and value.get("decision") == "NO_TARGET_PHASE_WITNESS"
        rc, value = run(parser, root, "stable_level_only", [line(0, "STABLE", bp="3", gotten="3")])
        checks["stable_level_not_transaction"] = rc != 0 and value.get("decision") == "PHASE_WITNESS_INCOMPLETE"
    errors = [key for key, value in checks.items() if not value]
    report = {
        "schema": "node0004-v80-buffer-ack-phase-validation-v1",
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "claim_boundary": "Exact final package-local HDL/parser and synthetic phase-event traces only; no DUT, numeric, config, natural-terminal or formal-D claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
