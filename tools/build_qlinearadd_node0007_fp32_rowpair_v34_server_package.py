from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_qlinearadd_node0007_fp32_rowpair_v33_server_package as prior

base = prior.base
base.SOURCE_NAME = "r5_qadd_n7_crow32_v33"
base.TARGET_NAME = "r5_qadd_n7_crow32_v34"
base.SOURCE = base.PKG / base.SOURCE_NAME
base.SOURCE_ZIP = base.PKG / f"{base.SOURCE_NAME}.zip"
base.SOURCE_SHA = "e5cf1f83de9d70316daa27b9bf996c3e712ebf60e3fd3af58482dfea38027ad2"
base.TARGET = base.PKG / base.TARGET_NAME
base.ZIP = base.PKG / f"{base.TARGET_NAME}.zip"

PATH_GUARD = """#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--server-root", required=True)
    ns = ap.parse_args()
    value = json.loads(ns.manifest.read_text(encoding="utf-8"))
    budget = value["path_length_budget"]
    paths = budget["projected_relative_paths"]
    if not paths or len(set(paths)) != len(paths):
        print("path budget projections absent or duplicate", file=sys.stderr)
        return 5
    max_rel = max(map(len, paths))
    if max_rel != budget["max_projected_relative_path_chars"]:
        print("path budget relative maximum differs", file=sys.stderr)
        return 5
    actual = len(str(Path(ns.server_root)))
    projected = actual + 1 + max_rel
    if projected > budget["absolute_path_limit_chars"]:
        print(
            f"server root/path budget exceeded: actual_root={actual} "
            f"relative={max_rel} projected={projected} "
            f"limit={budget['absolute_path_limit_chars']}",
            file=sys.stderr,
        )
        return 5
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""


def projected_paths(out: Path, manifest: dict) -> list[str]:
    name = base.TARGET_NAME
    result = {f"{name}/{path}" for path in manifest["files"]}
    for sca_name in ("sca_cfg.json", "sca_cfg_D.json"):
        sca = json.loads(
            (out / "workload/runtime" / sca_name).read_text(encoding="utf-8")
        )
        for record in sca.values():
            if isinstance(record, dict) and isinstance(record.get("path"), str):
                result.add(record["path"])
    result.update(
        {
            f"run_{name}/sim_results/return_observer/return_observer.log",
            f"evidence_{name}/CANONICAL_PROGRESS_DECISION.json",
            f"evidence_{name}/actual_simulator_argv.txt",
            f"{name}_return/RETURN_MANIFEST.json",
            f"{name}_return.zip.sha256",
        }
    )
    return sorted(result)


def materialize(parent: Path) -> Path:
    out = prior.materialize(parent)
    guard = out / "package_tools/package_path_budget_guard_v34.py"
    guard.write_text(PATH_GUARD, encoding="utf-8", newline="\n")
    runner = out / "PREPARE_AND_RUN.sh"
    text = runner.read_text(encoding="utf-8")
    anchor = 'return_sha="${return_zip}.sha256"\n'
    insertion = (
        anchor
        + 'python3 "$package_root/package_tools/package_path_budget_guard_v34.py" '
        + '--manifest "$package_root/TEST_PACKAGE_MANIFEST.json" '
        + '--server-root "$server_root" || exit 5\n'
    )
    if text.count(anchor) != 1:
        raise ValueError("runner path-guard insertion anchor differs")
    runner.write_text(text.replace(anchor, insertion), encoding="utf-8", newline="\n")

    manifest_path = out / "TEST_PACKAGE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = manifest["source_assets"].pop("fp32_rowpair_v32_source_zip")
    manifest["source_assets"]["fp32_rowpair_v33_source_zip"] = record
    manifest["provenance"]["generator"] = (
        "tools/build_qlinearadd_node0007_fp32_rowpair_v34_server_package.py"
    )
    manifest["provenance"]["successor_reason"] = (
        "current server-rule path budget manifest and minimal runtime guard; "
        "v33 config/bitstream/observer and SCA targets frozen"
    )
    server_rule = base.RULES["server"]
    for alias in ("server", "server_package"):
        manifest["rule_receipts"][alias]["sha256"] = base.sha(server_rule)
        manifest["rule_receipts"][alias]["current_match"] = True
    manifest["files"] = base.file_records(out, exclude_manifest=True)
    projections = projected_paths(out, manifest)
    inner = list(manifest["files"])
    components = sorted(
        {
            component
            for path in inner
            for component in path.replace("\\", "/").split("/")
            if len(component) > 48
        }
    )
    manifest["path_length_budget"] = {
        "rule_id": "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
        "declared_target_root_max_chars": 96,
        "absolute_path_limit_chars": 240,
        "max_projected_relative_path_chars": max(map(len, projections)),
        "max_projected_absolute_path_chars": 96 + 1 + max(map(len, projections)),
        "max_zip_member_chars": max(
            len(base.TARGET_NAME + "/" + path) for path in [*inner, "TEST_PACKAGE_MANIFEST.json"]
        ),
        "max_inner_suffix_chars": max(map(len, inner)),
        "max_inner_depth": max(path.count("/") + 1 for path in inner),
        "long_component_exceptions": [
            {"component": value, "reason": "canonical tool/ABI leaf retained"}
            for value in components
        ],
        "projected_relative_paths": projections,
    }
    base.write_json(manifest_path, manifest)
    return out


base.materialize = materialize

if __name__ == "__main__":
    raise SystemExit(base.main())
