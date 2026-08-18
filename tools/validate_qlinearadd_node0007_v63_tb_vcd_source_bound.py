#!/usr/bin/env python3
"""Recompute QAdd v63 actual-source catalog bindings from the exact final ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_qadd_n7_tailround_lanephase_v63_tbvcd"
CONTRACT = f"{PACKAGE}/contracts/server_tb_vcd_bounded_causal_cone_contract.json"
TB = f"{PACKAGE}/tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_span(data: bytes, name: str) -> str | None:
    rows = data.decode("utf-8", errors="strict").splitlines()
    matches = [row.strip() for row in rows if re.search(rf"\b{re.escape(name)}\b", row) and not row.lstrip().startswith("//")]
    return hashlib.sha256(matches[0].encode("utf-8")).hexdigest() if matches else None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=ROOT / "NDP_copy01")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    with zipfile.ZipFile(args.zip) as archive:
        names = archive.namelist()
        roots = {PurePosixPath(name).parts[0] for name in names if PurePosixPath(name).parts}
        if roots != {PACKAGE} or archive.testzip() is not None:
            errors.append("zip_identity_or_crc")
        contract = json.loads(archive.read(CONTRACT))
        tb_data = archive.read(TB)
    tb_text = tb_data.decode("utf-8", errors="strict")
    buffer_prefix = next(row["exact_hierarchy"].rsplit(".", 1)[0] for row in contract.get("signals", []) if row.get("signal_id") == "sig_valid_buf")
    exact_buffer_dump = f"$dumpvars(0, {buffer_prefix});" in tb_text
    source_cache: dict[str, bytes] = {}
    rows = []
    for signal in contract.get("signals", []):
        signal_id = signal.get("signal_id", "")
        hierarchy = signal.get("exact_hierarchy", "")
        source_rel = signal.get("source_path", "")
        source_path = (args.source_root / source_rel).resolve()
        try:
            source_path.relative_to(args.source_root.resolve())
        except ValueError:
            errors.append(f"{signal_id}:source_escape")
            continue
        if not source_path.is_file():
            errors.append(f"{signal_id}:source_missing:{source_rel}")
            continue
        data = source_cache.setdefault(source_rel, source_path.read_bytes())
        leaf = hierarchy.rsplit(".", 1)[-1]
        checks = {
            "source_sha": sha(data) == signal.get("source_sha256"),
            "declaration_span": source_span(data, leaf) == signal.get("declaration_span_sha256"),
            "binding_present": (
                (f".{signal_id}(" in tb_text and hierarchy.removeprefix("tb_NDP_Top_new_phy.") in tb_text)
                or (exact_buffer_dump and hierarchy.startswith(buffer_prefix + "."))
            ),
            "width_positive": isinstance(signal.get("width_bits"), int) and signal.get("width_bits", 0) > 0,
            "actual_read_only": signal.get("source_binding") == "ACTUAL_SOURCE_NET" and signal.get("derived_expected_equation") is False and signal.get("drives_dut") is False,
        }
        if not all(checks.values()):
            errors.extend(f"{signal_id}:{name}" for name, passed in checks.items() if not passed)
        rows.append({"signal_id": signal_id, "source_path": source_rel, "exact_hierarchy": hierarchy, "width_bits": signal.get("width_bits"), "checks": checks})
    candidates = [row.get("candidate_id") for row in contract.get("candidates", [])]
    boundaries = [row.get("boundary_id") for row in contract.get("boundaries", [])]
    matrix_pairs = {(row.get("candidate_id"), row.get("boundary_id")) for row in contract.get("candidate_boundary_matrix", [])}
    matrix_complete = matrix_pairs == {(candidate, boundary) for candidate in candidates for boundary in boundaries}
    signatures = [json.dumps(row.get("expected_signature"), sort_keys=True) for row in contract.get("candidate_boundary_matrix", [])]
    matrix_distinguishable = len(signatures) == len(set(signatures))
    if not matrix_complete:
        errors.append("candidate_boundary_matrix_incomplete")
    if not matrix_distinguishable:
        errors.append("candidate_boundary_matrix_not_pairwise_distinguishable")
    report = {
        "schema": "qadd-node0007-v63-tb-vcd-source-bound-validation-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "all_errors_collected": True,
        "signal_count": len(rows),
        "role_count": len(contract.get("role_coverage", [])),
        "source_files": {name: sha(data) for name, data in sorted(source_cache.items())},
        "signals": rows,
        "candidate_matrix": {"candidate_count": len(candidates), "boundary_count": len(boundaries), "row_count": len(matrix_pairs), "complete": matrix_complete, "pairwise_distinguishable": matrix_distinguishable},
        "tb_source_sha256": sha(tb_data),
        "claim_boundary": "Exact-final-ZIP bindings independently recomputed against the frozen local NDP_copy01 source snapshot; production provider selection/elaboration remains unclaimed.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
