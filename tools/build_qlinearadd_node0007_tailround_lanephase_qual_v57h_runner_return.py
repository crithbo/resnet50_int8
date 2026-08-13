#!/usr/bin/env python3
"""Build v57h with exact-frozen diagnostic semantics and v57g runner fixes."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_qlinearadd_node0007_tailround_lanephase_qual_v57g_runner_return as base


TARGET = "r5_qadd_n7_tailround_lanephase_qual_v57h"
LOCAL = base.ROOT / "artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-lanephase-qual-v57h-package"
OUT_ZIP = LOCAL / f"{TARGET}.zip"
EXACT_FROZEN_PREFIXES = (
    "tb_probe/",
    "diagnostics/source_bound_probe_plan.json",
    "diagnostics/source_bound_probe_binding.json",
    "diagnostics/source_bound_observer_generation_report.json",
    "diagnostics/source_bound_observer_generation.json",
    "diagnostics/source_bound_final_zip_contract.json",
    "package_tools/source_bound_causal_parser.py",
    "package_tools/qlinearadd_node0007_source_bound_stage_filter_v57.py",
)


base.TARGET = TARGET
base.LOCAL = LOCAL
base.OUT_ZIP = OUT_ZIP


def replace_identity(package: Path) -> None:
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        relative = path.relative_to(package).as_posix()
        if relative.startswith(EXACT_FROZEN_PREFIXES):
            continue
        if path.suffix.lower() not in base.TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if base.SOURCE_ID in text:
            path.write_text(
                text.replace(base.SOURCE_ID, TARGET),
                encoding="utf-8",
                newline="\n",
            )


def verify_frozen_surface(package: Path, before: dict[str, bytes]) -> dict[str, Any]:
    after_paths = {
        path.relative_to(package).as_posix(): path
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path.relative_to(package).as_posix().startswith(base.FROZEN_PREFIXES)
    }
    errors: list[str] = []
    if set(before) != set(after_paths):
        errors.append("protected exact-set differs")
    identity_changed: list[str] = []
    exact_equal: list[str] = []
    for relative in sorted(set(before) & set(after_paths)):
        if relative.startswith(EXACT_FROZEN_PREFIXES):
            expected = before[relative]
        else:
            expected = before[relative].replace(
                base.SOURCE_ID.encode("ascii"), TARGET.encode("ascii")
            )
        actual = after_paths[relative].read_bytes()
        if actual != expected:
            errors.append(f"protected bytes differ beyond allowed identity: {relative}")
        elif actual == before[relative]:
            exact_equal.append(relative)
        else:
            identity_changed.append(relative)
    return {
        "schema": "qlinearadd-node0007-v57h-frozen-surface-validation-v1",
        "pass": not errors,
        "errors": errors,
        "source_package_id": base.SOURCE_ID,
        "target_package_id": TARGET,
        "source_zip_sha256": base.SOURCE_SHA,
        "protected_file_count": len(before),
        "exact_byte_equal_count": len(exact_equal),
        "identity_only_change_count": len(identity_changed),
        "identity_only_changed_files": identity_changed,
        "diagnostic_observer_parser_plan_binding_exact_byte_equal": not any(
            relative.startswith(EXACT_FROZEN_PREFIXES)
            and after_paths[relative].read_bytes() != before[relative]
            for relative in set(before) & set(after_paths)
        ),
        "config_numeric_workload_rtl_changed": False if not errors else None,
        "claim_boundary": "Exact diagnostic/RTL freeze plus identity-only workload paths; no server or numeric execution claim.",
    }


original_patch_manifest = base.patch_manifest


def patch_manifest(package: Path) -> None:
    original_patch_manifest(package)
    path = package / "TEST_PACKAGE_MANIFEST.json"
    manifest = base.load_json(path)
    manifest["schema"] = "qlinearadd-node0007-tailround-lanephase-server-package-v57h"
    manifest["successor"]["frozen_surface"] = [
        "workload/config/numeric/golden modulo fresh identity paths",
        "source-bound observer/logger/parser/plan/binding exact bytes",
        "2h compile and simulation timeout",
        "functional RTL exact bytes",
    ]
    manifest["provenance"]["generator"] = Path(__file__).relative_to(base.ROOT).as_posix()
    manifest["files"] = base.records(package)
    base.write_json(path, manifest)


base.replace_identity = replace_identity
base.verify_frozen_surface = verify_frozen_surface
base.patch_manifest = patch_manifest


def main() -> int:
    required = [base.SOURCE, *base.RULES.values()]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise base.BuildError(f"missing inputs: {missing}")
    if LOCAL.exists():
        raise base.BuildError(f"fresh output directory required: {LOCAL}")
    LOCAL.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="q57ha-") as first, tempfile.TemporaryDirectory(prefix="q57hb-") as second:
        package_a, frozen_a = base.build_tree(Path(first))
        package_b, frozen_b = base.build_tree(Path(second))
        zip_a = Path(first) / f"{TARGET}.zip"
        zip_b = Path(second) / f"{TARGET}.zip"
        base.deterministic_zip(package_a, zip_a)
        base.deterministic_zip(package_b, zip_b)
        if zip_a.read_bytes() != zip_b.read_bytes() or frozen_a != frozen_b:
            raise base.BuildError("deterministic double build differs")
        shutil.copy2(zip_a, OUT_ZIP)
    sidecar = Path(str(OUT_ZIP) + ".sha256")
    sidecar.write_text(
        f"{base.sha(OUT_ZIP)}  {OUT_ZIP.name}\n",
        encoding="ascii",
        newline="\n",
    )
    base.write_json(LOCAL / f"{TARGET}.frozen_surface.json", frozen_a)
    receipt = {
        "schema": "qlinearadd-node0007-tailround-lanephase-qual-v57h-build-v1",
        "status": "BUILT_UPLOAD_HOLD_PENDING_EXACT_FINAL_ZIP_AND_FIRST_FRESH_AUDIT",
        "package_id": TARGET,
        "zip": {
            "path": OUT_ZIP.relative_to(base.ROOT).as_posix(),
            "bytes": OUT_ZIP.stat().st_size,
            "sha256": base.sha(OUT_ZIP),
        },
        "sidecar": {
            "path": sidecar.relative_to(base.ROOT).as_posix(),
            "bytes": sidecar.stat().st_size,
            "sha256": base.sha(sidecar),
        },
        "source_zip": {
            "path": base.SOURCE.relative_to(base.ROOT).as_posix(),
            "bytes": base.SOURCE_BYTES,
            "sha256": base.SOURCE_SHA,
        },
        "supersedes_failed_local_candidate": {
            "package_id": "r5_qadd_n7_tailround_lanephase_qual_v57g",
            "sha256": "8e527c8e7fcadeb4023a49762da5f29e0cf70f9a2cfeca4e0d01d22ecfd882e7",
        },
        "deterministic_double_build": True,
        "rule_change_epoch_id": base.EPOCH,
        "first_fresh_after_change": True,
        "runner_return_only_successor": True,
        "configuration_changed": False,
        "numeric_workload_golden_repeated": False,
        "diagnostic_semantics_changed": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    base.write_json(LOCAL / f"{TARGET}.build.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
