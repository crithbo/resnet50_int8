#!/usr/bin/env python3
"""Gate p42's package-local vector valid/ready overlap predicate."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


PACKAGE = "r5_n4_0cc_p42_vecjoinfix"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    errors: list[str] = []
    plan_member = f"{PACKAGE}/diagnostics/source_bound_probe_plan.json"
    catalog_member = f"{PACKAGE}/diagnostics/source_bound_probe_catalog.json"
    observer_member = f"{PACKAGE}/tb_probe/source_bound_causal_observer.svh"
    manifest_member = f"{PACKAGE}/package_manifest.json"
    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist()
        names = [row.filename for row in infos]
        safe = all(
            not PurePosixPath(row.filename).is_absolute()
            and ".." not in PurePosixPath(row.filename).parts
            and "\\" not in row.filename
            and not stat.S_ISLNK(row.external_attr >> 16)
            for row in infos
        )
        if archive.testzip() is not None or not safe or len(names) != len(set(names)):
            errors.append("exact ZIP is corrupt, unsafe or contains duplicate members")
        required = (plan_member, catalog_member, observer_member, manifest_member)
        if not all(member in names for member in required):
            errors.append("required vector-predicate member absent")
            plan: dict[str, Any] = {}
            catalog: dict[str, Any] = {}
            manifest: dict[str, Any] = {}
            observer = b""
        else:
            plan = json.loads(archive.read(plan_member))
            catalog = json.loads(archive.read(catalog_member))
            observer = archive.read(observer_member)
            manifest = json.loads(archive.read(manifest_member))
    boundaries = {row.get("boundary_id"): row for row in plan.get("boundaries", [])}
    target = boundaries.get("mse4_wdata_output_accept", {})
    target_classes = target.get("classes", [])
    predicate = target_classes[0].get("predicate", {}) if len(target_classes) == 1 else {}
    symbol_ids = predicate.get("symbol_ids")
    if predicate.get("op") != "BIT_AND_NONZERO" or not isinstance(symbol_ids, list) or len(symbol_ids) != 2:
        errors.append("mse4 wdata predicate is not a two-symbol BIT_AND_NONZERO")
    symbols = {row.get("symbol_id"): row for row in catalog.get("symbols", [])}
    widths = [symbols.get(symbol_id, {}).get("width_bits") for symbol_id in symbol_ids or []]
    if widths != [2, 2]:
        errors.append(f"mse4 wdata operands are not the frozen 2-bit vectors: {widths}")
    text = observer.decode("utf-8", "replace")
    marker = "module codex_probe_mse4_wdata_output_accept"
    start = text.find(marker)
    end = text.find("endmodule", start)
    module = text[start:end] if start >= 0 and end > start else ""
    if "((|(p_0 & p_2)) === 1'b1)" not in module:
        errors.append("generated mse4 module lacks reduction-OR vector overlap")
    if "((p_0 === 1'b1) && (p_2 === 1'b1))" in module:
        errors.append("generated mse4 module retains scalar case equality")
    files = manifest.get("files", {})
    declared = files.get("tb_probe/source_bound_causal_observer.svh", {})
    if declared != {"sha256": sha256(observer), "size_bytes": len(observer)}:
        errors.append("manifest observer receipt mismatch")
    report = {
        "schema": "conv-native-four-lane-p42-vector-join-predicate-validation-v1",
        "package_id": PACKAGE,
        "pass": not errors,
        "errors": errors,
        "predicate": predicate,
        "operand_widths": widths,
        "observer_sha256": sha256(observer),
        "claim_boundary": "Exact-ZIP package-local diagnostic gate; no dynamic server claim and no server action.",
    }
    write(args.output, report)
    print(json.dumps({"pass": not errors, "errors": errors, "output": str(args.output)}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
