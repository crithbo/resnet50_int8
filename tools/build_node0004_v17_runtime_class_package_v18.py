from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v16_a_reuse_diag_package_v17 as prior  # noqa: E402
import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


INSTALL_NAME = "r5_n4_hw_v18_a_reuse_diag"
QUARANTINED_V17_SHA256 = (
    "dd0f3fa647388be64d601b861fc99728440acf6a5f9cba753b2b870ad8cd0e16"
)
OUTPUT_ROOT = prior.OUTPUT_ROOT


def patch_runtime_classification(package: Path) -> dict[str, str]:
    runtime = package / "package_tools/node0004_hang_localization_runtime.py"
    old_sha = base.sha256(runtime)
    text = runtime.read_text(encoding="utf-8")
    old = '"classification": "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",'
    new = (
        '"classification": json.loads('
        '(package_root / "package_manifest.json").read_text('
        'encoding="utf-8"))["classification"],'
    )
    if text.count(old) != 1:
        raise base.BuildError("v17 runtime classification source shape differs")
    runtime.write_text(
        text.replace(old, new, 1), encoding="utf-8", newline="\n"
    )
    return {
        "path": runtime.relative_to(package).as_posix(),
        "old_sha256": old_sha,
        "new_sha256": base.sha256(runtime),
    }


def build_directory(output: Path) -> Path:
    prior.INSTALL_NAME = INSTALL_NAME
    package = prior.build_directory(output)
    repair = patch_runtime_classification(package)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema"] = "resnet50-node0004-a-reuse-diagnostic-package-v18"
    manifest["install_name"] = INSTALL_NAME
    manifest["runtime_classification_binding"] = {
        "classification": "PACKAGE_LOCAL_RETURN_SCHEMA_FIX",
        "source": "package_manifest.json:classification",
        "expected": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "repair": repair,
    }
    manifest["quarantined_intermediate_v17"] = {
        "name": "r5_n4_hw_v17_a_reuse_diag.zip",
        "sha256": QUARANTINED_V17_SHA256,
        "status": "QUARANTINED_LOCAL_SELF_AUDIT_FAILURE",
        "reason": (
            "return analyzer hard-coded CONFIG_FUNCTIONAL_FIX classification "
            "instead of reading the diagnostic package manifest"
        ),
    }
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    return package


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    package = output / INSTALL_NAME
    zip_path = output / f"{INSTALL_NAME}.zip"
    sidecar = output / f"{INSTALL_NAME}.zip.sha256"
    validation = output / f"{INSTALL_NAME}.validation.json"
    for target in (package, zip_path, sidecar, validation):
        if target.exists():
            raise base.BuildError(f"refusing to overwrite: {target}")
    package = build_directory(output)
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v18-repeat-") as temp:
        repeat_root = Path(temp)
        repeat_package = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        repeated = base.sha256(repeat_zip) == digest
    if not repeated:
        raise base.BuildError("v18 deterministic rebuild differs")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-a-reuse-diagnostic-package-validation-v18",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": repeated,
        "source_v16_sha256": prior.SOURCE_ZIP_SHA256,
        "bound_v16_return_sha256": prior.BOUND_RETURN_SHA256,
        "current_server_rule_sha256": prior.SERVER_RULE_SHA256,
        "quarantined_v17_sha256": QUARANTINED_V17_SHA256,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_action": False,
        "final_zip_rule_self_audit_pending": True,
    }
    base.write_json(validation, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
