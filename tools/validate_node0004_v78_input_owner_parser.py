from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v78_buffer_input_owner_diag"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_parser(parser: Path, lines: list[str], root: Path, name: str) -> tuple[int, dict]:
    log = root / f"{name}.log"
    output = root / f"{name}.json"
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    done = subprocess.run(
        [sys.executable, str(parser), "--log", str(log), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    value = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    return done.returncode, value


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, type=Path)
    ap.add_argument("--v77-return", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()

    errors: list[str] = []
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="n4v78_owner_") as raw:
        root = Path(raw)
        with zipfile.ZipFile(args.zip) as archive:
            names = archive.namelist()
            checks["zip_root"] = {
                PurePosixPath(name).parts[0] for name in names if name
            } == {PACKAGE}
            parser = root / "post_final_buffer_input_owner_parser.py"
            parser.write_bytes(
                archive.read(f"{PACKAGE}/package_tools/post_final_buffer_input_owner_parser.py")
            )
        with zipfile.ZipFile(args.v77_return) as archive:
            member = next(
                name for name in archive.namelist() if name.endswith("/runs/c0/return_observer.log")
            )
            lines = archive.read(member).decode("utf-8", errors="replace").splitlines()

        rc, positive = run_parser(parser, lines, root, "positive")
        checks["positive_unique_owner_boundary"] = (
            rc == 0
            and positive.get("decision")
            == "BUFFER_WRITE_PRECEDES_INPUT_ACK_THEN_NEXT_PAYLOAD_ACCEPTS"
            and positive.get("pairwise_distinguishable") is True
            and len(positive.get("candidate_ids", [])) == 5
        )

        # Missing exact final descriptor must fail closed.
        missing_final = [
            line for line in lines
            if not (
                "TOKEN_ORIGIN_ACCEPT_EDGE_V2" in line
                and "desc_ev=1" in line
                and "desc=18" in line
            )
        ]
        rc_missing, value_missing = run_parser(parser, missing_final, root, "missing_final")
        checks["negative_missing_final_fails_closed"] = (
            rc_missing != 0 and value_missing.get("decision") == "FINAL_DESCRIPTOR_NOT_OBSERVED"
        )

        # Removing the unacknowledged write must not retain the positive classification.
        no_unacked = [
            line for line in lines
            if not (
                "TOKEN_ORIGIN_ACCEPT_EDGE_V2" in line
                and "desc=18" in line
                and "buf_wr_ev=1" in line
                and "buf_bp=0" in line
            )
        ]
        _, value_no_unacked = run_parser(parser, no_unacked, root, "no_unacked")
        checks["negative_drop_unacked_changes_decision"] = (
            value_no_unacked.get("decision")
            != "BUFFER_WRITE_PRECEDES_INPUT_ACK_THEN_NEXT_PAYLOAD_ACCEPTS"
        )

        # Stable ROWLC state alone cannot manufacture a qualified TOKEN edge.
        stable_only = [line for line in lines if "kind=ROWLC4_BUFAG_EDGE_V1" in line]
        rc_stable, value_stable = run_parser(parser, stable_only, root, "stable_only")
        checks["negative_level_only_fails_closed"] = (
            rc_stable != 0 and value_stable.get("decision") == "FINAL_DESCRIPTOR_NOT_OBSERVED"
        )

        # Removing all post-final writes selects residual drain, not the owner mismatch.
        no_post_write: list[str] = []
        for line in lines:
            if (
                "TOKEN_ORIGIN_ACCEPT_EDGE_V2" in line
                and "desc=18" in line
                and "buf_wr_ev=1" in line
            ):
                continue
            no_post_write.append(line)
        _, value_no_post = run_parser(parser, no_post_write, root, "no_post_write")
        checks["negative_no_post_write_changes_decision"] = (
            value_no_post.get("decision") == "FINAL_DESCRIPTOR_WITH_RESIDUAL_DRAIN_ONLY"
        )

        details = {
            "zip": {"path": str(args.zip.resolve()), "bytes": args.zip.stat().st_size, "sha256": sha(args.zip)},
            "v77_return_sha256": sha(args.v77_return),
            "positive": positive,
            "negative_decisions": {
                "missing_final": value_missing.get("decision"),
                "drop_unacked": value_no_unacked.get("decision"),
                "level_only": value_stable.get("decision"),
                "no_post_write": value_no_post.get("decision"),
            },
        }

    errors.extend(name for name, value in checks.items() if not value)
    report = {
        "schema": "conv-node0004-v78-input-owner-parser-validation-v1",
        "pass": not errors,
        "errors": errors,
        "checks": checks,
        "details": details,
        "claim_boundary": "Final-ZIP parser against frozen qualified v77 edges; no DUT, numeric, configuration-correctness, RTL-defect, natural-terminal or formal-D claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"pass": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
