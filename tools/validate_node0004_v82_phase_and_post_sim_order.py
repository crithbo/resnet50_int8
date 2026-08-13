from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


TARGET = (
    "tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[13]."
    "u_slice_with_datahub_mc_group.slice_group_gen[1].u_slice_wrapper.u_Slice."
    "u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine."
    "u_Buffer_AG_Idx_Queue"
)
PHASES = ("ACTIVE", "INACTIVE", "POSTNBA", "HALF", "NEXT")
WIDTHS = {
    "wr": 1, "full": 1, "all": 1, "valid": 2, "same": 2,
    "gotten": 2, "keep": 2, "bpmask": 2, "bp": 2, "mode": 2,
    "row": 2, "col": 5, "rowtag": 7, "coltag": 7,
}


def payload(fields: dict[str, str]) -> str:
    value = 0
    for name, width in WIDTHS.items():
        value = (value << width) | int(fields[name], 16)
    return format(value, "x")


def fixture() -> str:
    rows = []
    values = {
        "ACTIVE": ("0", "0"),
        "INACTIVE": ("0", "0"),
        "POSTNBA": ("3", "3"),
        "HALF": ("3", "3"),
        "NEXT": ("3", "3"),
    }
    for index, phase in enumerate(PHASES):
        gotten, bp = values[phase]
        fields = {
            "wr": "1", "full": "0", "all": "1", "valid": "3", "same": "3",
            "gotten": gotten, "keep": "3", "bpmask": "3", "bp": bp, "mode": "2",
            "row": "1", "col": "1f", "rowtag": "7f", "coltag": "7f",
        }
        rows.append(
            "CODEX_PROBE_V1 kind=EVENT boundary=buf_ack_phase_target "
            f"instance={TARGET} time={100 + index} mask=1 payload={payload(fields)} "
            f"payload_known=1 payload_width=38 seq=0 phase={phase} "
            + " ".join(f"{name}={fields[name]}" for name in WIDTHS)
        )
    return "\n".join(rows) + "\n"


def run_parser(python: Path, parser: Path, root: Path, name: str, text: str):
    log = root / f"{name}.log"
    output = root / f"{name}.json"
    log.write_text(text, encoding="utf-8")
    done = subprocess.run(
        [str(python), str(parser), "--log", str(log), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    value = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    return done.returncode, value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parser", type=Path, required=True)
    ap.add_argument("--plugin", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    checks = {}
    with tempfile.TemporaryDirectory(prefix="n4v82-phase-order-") as raw:
        root = Path(raw)
        positive = fixture()
        rc, value = run_parser(Path(sys.executable), args.parser, root, "positive", positive)
        checks["positive_exact_target_complete"] = (
            rc == 0
            and value.get("decision") == "POSTNBA_SETTLE_WITH_SAME_CYCLE_CONSUMER_ACCEPT"
            and value.get("complete_sequence_count") == 1
        )
        rc, value = run_parser(
            Path(sys.executable), args.parser, root, "wrong_instance", positive.replace("[13]", "[12]")
        )
        checks["wrong_instance_fails_closed"] = (
            rc != 0
            and value.get("decision") == "NO_EXACT_TARGET_LIVE_EVENT"
            and value.get("foreign_event_count") == 5
        )
        rc, value = run_parser(
            Path(sys.executable), args.parser, root, "unknown_payload", positive.replace("bp=3", "bp=x", 1)
        )
        checks["xz_payload_fails_closed"] = (
            rc != 0
            and value.get("decision") == "UNKNOWN_OR_WIDTH_INVALID_PAYLOAD_FAIL_CLOSED"
        )
        rc, value = run_parser(
            Path(sys.executable), args.parser, root, "knownness_zero", positive.replace("payload_known=1", "payload_known=0", 1)
        )
        checks["payload_known_zero_fails_closed"] = (
            rc != 0 and value.get("decision") == "UNKNOWN_OR_WIDTH_INVALID_PAYLOAD_FAIL_CLOSED"
        )
        rc, value = run_parser(
            Path(sys.executable), args.parser, root, "payload_width_wrong", positive.replace("payload_width=38", "payload_width=37", 1)
        )
        checks["payload_width_mismatch_fails_closed"] = (
            rc != 0 and value.get("decision") == "UNKNOWN_OR_WIDTH_INVALID_PAYLOAD_FAIL_CLOSED"
        )
        rc, value = run_parser(
            Path(sys.executable), args.parser, root, "width_overflow", positive.replace("row=1", "row=4", 1)
        )
        checks["declared_width_overflow_fails_closed"] = (
            rc != 0
            and value.get("decision") == "UNKNOWN_OR_WIDTH_INVALID_PAYLOAD_FAIL_CLOSED"
        )
        rc, value = run_parser(
            Path(sys.executable),
            args.parser,
            root,
            "incomplete",
            "\n".join(positive.splitlines()[:-1]) + "\n",
        )
        checks["incomplete_phase_sequence_fails_closed"] = (
            rc != 0 and value.get("decision") == "INCOMPLETE_EXACT_TARGET_PHASE_SEQUENCE"
        )

        package = root / "package"
        attempt = root / "attempt"
        (package / "package_tools").mkdir(parents=True)
        (attempt / "c0").mkdir(parents=True)
        (attempt / "evidence").mkdir(parents=True)
        shutil.copy2(args.parser, package / "package_tools/buffer_ack_phase_parser.py")
        shutil.copy2(args.plugin, package / "package_tools/node0004_v82_post_sim_plugin.py")
        stub = package / "package_tools/node0004_v79_post_sim_plugin.py"
        stub.write_text(
            "from pathlib import Path\n"
            "import argparse\n"
            "p=argparse.ArgumentParser();p.add_argument('--package-root');p.add_argument('--attempt-root');a=p.parse_args()\n"
            "Path(a.attempt_root,'c0','sim.log').write_text('BOUNDED\\n',encoding='utf-8')\n"
            "print('stub bounded collector complete')\n",
            encoding="utf-8",
        )
        sim_log = attempt / "c0/sim.log"
        sim_log.write_text(positive, encoding="utf-8")
        input_sha = hashlib.sha256(sim_log.read_bytes()).hexdigest()
        (attempt / "evidence/compile_exit_status.txt").write_text("0\n", encoding="ascii")
        decision = attempt / "c0/buffer_ack_phase_decision.json"
        done = subprocess.run(
            [
                sys.executable,
                str(package / "package_tools/node0004_v82_post_sim_plugin.py"),
                "--package-root",
                str(package),
                "--attempt-root",
                str(attempt),
                "--phase-live-log",
                str(sim_log),
                "--phase-output",
                str(decision),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        receipt_path = attempt / "evidence/buffer_ack_phase_parser_receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
        checks["phase_persisted_before_mutating_collector"] = (
            done.returncode == 0
            and decision.is_file()
            and sim_log.read_text(encoding="utf-8") == "BOUNDED\n"
            and receipt.get("parsed_before_frozen_bounded_collector") is True
            and receipt.get("raw_phase_input_sha256_before_bounded_projection") == input_sha
            and receipt.get("complete_sequence_count") == 1
        )

    result = {
        "schema": "conv-node0004-v82-phase-and-post-sim-order-validation-v1",
        "pass": all(checks.values()),
        "errors": [name for name, passed in checks.items() if not passed],
        "checks": checks,
        "claim_boundary": (
            "Package-local exact-instance, binary-known declared-width phase parser and parse-before-"
            "projection ordering only; no DUT, config, numeric, natural-terminal or formal-D claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
