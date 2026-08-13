from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


PACKAGE = "r5_n4_hw_v73_sourcebound_epoch_diag"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", type=Path, required=True)
    ap.add_argument("--python", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    errors: list[str] = []
    results: dict[str, object] = {}
    with zipfile.ZipFile(args.zip) as archive, tempfile.TemporaryDirectory(prefix="v73-source-bound-trace-") as td:
        root = Path(td)
        prefix = PACKAGE + "/"
        parser_member = prefix + "package_tools/source_bound_causal_parser.py"
        plan_member = prefix + "diagnostics/source_bound_probe_plan.json"
        parser = root / "parser.py"
        parser.write_bytes(archive.read(parser_member))
        plan = json.loads(archive.read(plan_member))
        enabled = [item["boundary_id"] for item in plan["boundaries"]]
        progress_classes = [
            item["class_id"]
            for boundary in plan["boundaries"]
            for item in boundary["classes"]
            if item["progress"] is True
        ]
        allowed_progress_suffixes = (
            "_enqueue_accept", "_enqueue_terminal", "_terminal_enqueue",
            "_dequeue_accept", "_consumer_accept"
        )
        progress_is_qualified = all(name.endswith(allowed_progress_suffixes) for name in progress_classes)
        if not progress_is_qualified:
            errors.append("level/state class is marked as qualified progress")

        def run_case(name: str, mem: bool, buf: bool, *, omit_enable: bool = False, malformed: bool = False):
            lines = [f"CODEX_PROBE_V1 kind=ENABLED boundary={b} instance=dut" for b in enabled]
            if omit_enable:
                lines.pop()
            if mem:
                lines.append("CODEX_PROBE_V1 kind=RING_PROGRESS boundary=mem_terminal instance=dut time=1 mask=1 payload=0 seq=0")
            if buf:
                lines.append("CODEX_PROBE_V1 kind=RING_PROGRESS boundary=buf_terminal instance=dut time=2 mask=1 payload=0 seq=0")
            if malformed:
                lines.append("CODEX_PROBE_V1 kind=SUMMARY boundary=mem_terminal instance=dut bad token")
            log = root / f"{name}.log"
            out = root / f"{name}.json"
            log.write_text("\n".join(lines) + "\n", encoding="utf-8")
            cp = subprocess.run([str(args.python), str(parser), "--log", str(log), "--output", str(out)], text=True, capture_output=True)
            value = json.loads(out.read_text(encoding="utf-8"))
            results[name] = {"exit": cp.returncode, "decision": value["decision"], "errors": value["errors"], "missing_enabled": value["missing_enabled_boundaries"]}
            return cp.returncode, value

        expected = {
            "memory_absent": (False, True, "MEMORY_SOURCE_TERMINAL_ABSENT"),
            "buffer_absent": (True, False, "BUFFER_SOURCE_TERMINAL_ABSENT"),
            "both_present": (True, True, "POST_TERMINAL_TEMPORAL_OWNERSHIP_REQUIRES_RING"),
            "neither_present": (False, False, "BOTH_SOURCE_TERMINALS_ABSENT"),
        }
        for name, (mem, buf, decision) in expected.items():
            rc, value = run_case(name, mem, buf)
            if rc != 0 or value["decision"] != decision:
                errors.append(f"candidate trace failed: {name}")
        rc, value = run_case("missing_enable_negative", True, True, omit_enable=True)
        if rc == 0 or value["decision"] != "EVIDENCE_INCOMPLETE":
            errors.append("missing-enable negative did not fail closed")
        rc, value = run_case("malformed_negative", True, True, malformed=True)
        if rc == 0 or value["decision"] != "EVIDENCE_INCOMPLETE" or not value["errors"]:
            errors.append("malformed-record negative did not fail closed")

    report = {
        "schema": "node0004-v73-source-bound-trace-validation-v1",
        "valid": not errors,
        "errors": errors,
        "checks": {
            "four_candidate_signatures_unique": not any(e.startswith("candidate") for e in errors),
            "missing_enable_fails_closed": "missing-enable negative did not fail closed" not in errors,
            "malformed_record_fails_closed": "malformed-record negative did not fail closed" not in errors,
            "qualified_event_only": progress_is_qualified,
            "natural_terminal_not_claimed": True,
            "formal_d_not_claimed": True,
        },
        "cases": results,
        "zip_sha256": sha(args.zip),
        "claim_boundary": "Generated parser decision signatures only; no DUT execution, numeric, natural-terminal or formal-D claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"valid": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
