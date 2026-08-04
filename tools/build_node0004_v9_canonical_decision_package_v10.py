from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


INSTALL_NAME = "r5_n4_hw_v10_hangloc_canonical"
SOURCE_INSTALL_NAME = "r5_n4_hw_v9_hangloc_qualified"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v9_hangloc_qualified.zip"
)
SOURCE_ZIP_SHA256 = (
    "bce6e7e852885cc3c396a860f8aeb687b245a1137a7943db1b9bdc6cf9bd14ce"
)
BOUND_RETURN_SHA256 = (
    "37e84246a8908c38ec5056c3fc965d90198a2809b049f3c7303215e508d07dcf"
)
PLAN_SHA256 = (
    "21dec7853cf9dc1610e51ede1366550b390bfc301d8dc8d5bf6c560d5ecae545"
)
SERVER_RULE_SHA256 = (
    "ed3990f13c62ce67e5081458b0dfdcf6ca257908fe138fcc05a7000482afd2f8"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


def _configure_base() -> None:
    base.INSTALL_NAME = INSTALL_NAME
    base.SOURCE_INSTALL_NAME = SOURCE_INSTALL_NAME
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_ZIP_SHA256 = SOURCE_ZIP_SHA256
    base.RETURN_ZIP_SHA256 = BOUND_RETURN_SHA256
    base.PLAN_SHA256 = PLAN_SHA256
    base.SERVER_RULE_SHA256 = SERVER_RULE_SHA256
    base.OBSERVER_TAIL = (
        ROOT / "tools/node0004_hang_localization_observer_tail_v10.svh"
    )
    base.RUNTIME_SOURCE = (
        ROOT / "tools/node0004_hang_localization_runtime_v10.py"
    )
    base.SOURCE_PREFIX = f"install/cfg_pkg/{SOURCE_INSTALL_NAME}/"
    base.CURRENT_PREFIX = f"install/cfg_pkg/{INSTALL_NAME}/"


def _readme() -> str:
    return f"""# node0004 v10 canonical-decision hang-localization package

Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

This package reuses the frozen v9 c0 workload without rebuilding node0004
numeric inputs. It preserves qualified-only progress and adds one complete,
versioned canonical decision record. Summary text uses a distinct prefix.
The parser fails closed on duplicate/conflicting candidates and on missing or
inconsistent required fields.

The package does not modify functional RTL or the server TB and cannot
establish E4/E5.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip` and adjacent `.sha256`.
"""


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    _configure_base()
    package, _ = base.build_directory(destination)
    tools_dir = package / "package_tools"
    shutil.copy2(
        ROOT / "tools/node0004_hang_localization_runtime_v7.py",
        tools_dir / "node0004_hang_localization_runtime_v7.py",
    )
    (package / "README.md").write_text(
        _readme(), encoding="utf-8", newline="\n"
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema"] = "resnet50-node0004-hang-localization-package-v10"
    manifest["install_name"] = INSTALL_NAME
    manifest["evidence_level"] = (
        "E2_LOCAL_PLUS_V9_CANONICAL_DECISION_PACKAGE_REPAIR"
    )
    manifest["frozen_source_package"] = {
        "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
        "sha256": SOURCE_ZIP_SHA256,
    }
    manifest.pop("bound_v6_return_sha256", None)
    manifest.pop("bound_v7_return_sha256", None)
    manifest["bound_v7_return_sha256"] = BOUND_RETURN_SHA256
    manifest["active_receipts"] = {
        "plan_mutable_provenance_sha256": PLAN_SHA256,
        "server_package_rule_sha256": SERVER_RULE_SHA256,
        "rules": [
            "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
            "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
            "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
            "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
            "CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001",
            "CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001",
        ],
    }
    manifest["package_side_repair"] = {
        "classification": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
        "first_defect": (
            "v9 emitted a complete decision followed by a summary-only line "
            "using the same DIAG_DECISION machine prefix"
        ),
        "second_defect": (
            "v9 decision record omitted schema/version, explicit decision, "
            "covered window range, and a recomputable counter digest"
        ),
        "repair": (
            "emit exactly one CANONICAL_DIAG_DECISION_V1 record with all "
            "required fields; emit summaries under DIAG_SUMMARY; require "
            "unique, complete, internally consistent canonical input"
        ),
        "functional_semantics_changed": False,
    }
    manifest["unresolved_boundary"] = (
        "v7 evidence bounds the stall after qualified read-data acceptance "
        "and before any Buffer5 write witness; v10 changes only the machine "
        "decision contract used to confirm that interval"
    )
    manifest["progress_contract"].update(
        {
            "default_progress_diagnostics_enabled": True,
            "default_progress_diagnostics_exemption": None,
            "normal_minimum_progress_event": (
                "a qualified external request, read-data, or write-data "
                "handshake on streams 0/1/3/4"
            ),
            "buffer_level_samples_count_as_progress": False,
            "buffer_level_semantics": (
                "raw state only; rising-edge witness is reported separately"
            ),
            "decision_parser_requires_reason_and_boundary": True,
            "canonical_prefix": "CANONICAL_DIAG_DECISION_V1",
            "canonical_record_count": 1,
            "summary_prefix": "DIAG_SUMMARY",
            "canonical_fail_closed_status": (
                "PACKAGE_DIAGNOSTIC_DECISION_AMBIGUOUS"
            ),
        }
    )
    manifest["decision_table"][2] = [
        "READ_DATA_TO_BUFFER4_READ_WITNESS",
        "read data exists, no Buffer4 read-enable rising-edge witness",
    ]
    manifest["decision_table"][3] = [
        "BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS",
        "Buffer4 read witness exists, no Buffer5 write-enable rising edge",
    ]
    manifest["decision_table"][4] = [
        "BUFFER5_WRITE_WITNESS_TO_BUFFER5_READ_WITNESS",
        "Buffer5 write witness exists, no Buffer5 read-enable rising edge",
    ]
    manifest["decision_table"][5] = [
        "BUFFER5_READ_WITNESS_TO_D_WRITE_REQUEST",
        "Buffer5 read witness exists, no qualified D request",
    ]
    manifest["numeric_analysis_repeated"] = False
    manifest["node0004_workload_rebuilt"] = False
    manifest["frozen_c0_inputs_reused_read_only"] = True
    manifest["superseded_diagnostic_package"] = {
        "name": "r5_n4_hw_v9_hangloc_qualified.zip",
        "sha256": SOURCE_ZIP_SHA256,
        "status": "QUARANTINED_CANONICAL_DECISION_CONTRACT_DEFECT",
    }
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    proof = base.preflight(package)
    observer_sha = manifest["observer_binding_four_way"]["source"]["sha256"]
    observer = base.observer_precompile_receipt(package, observer_sha)
    if not observer["valid"]:
        raise base.BuildError(f"observer XMR gate failed: {observer['errors']}")
    return package, {"preflight": proof, "observer": observer}


def _repeat(package: Path, zip_path: Path) -> dict[str, Any]:
    base.deterministic_zip(package, zip_path)
    records = base.package_records(package)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v10-repeat-") as temporary:
        repeat_root = Path(temporary)
        repeat_package, _ = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        if records != base.package_records(repeat_package):
            raise base.BuildError("repeated package trees differ")
        if digest != base.sha256(repeat_zip):
            raise base.BuildError("repeated deterministic ZIPs differ")
    return {
        "package_tree_equal": True,
        "zip_equal": True,
        "repeat_zip_sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    package_path = output / INSTALL_NAME
    zip_path = output / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, validation):
        if path.exists():
            print(f"refusing to overwrite: {path}", file=sys.stderr)
            return 1
    output.mkdir(parents=True, exist_ok=True)
    package, proof = build_directory(output)
    repeated = _repeat(package, zip_path)
    digest = base.sha256(zip_path)
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    receipt = {
        "schema": "node0004-hang-localization-package-validation-v10",
        "status": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX_READY_NOT_RUN",
        "package": str(package),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "source_zip_sha256": SOURCE_ZIP_SHA256,
        "bound_return_sha256": BOUND_RETURN_SHA256,
        "package_file_count": proof["preflight"]["package_file_count"],
        "observer_sha256": proof["preflight"]["observer_sha256"],
        "observer_static_gate": proof["observer"]["xmr_static_gate"],
        "observer_runtime_enabled": True,
        "observer_compile_enable_macro_bound": True,
        "observer_return_allowlisted": True,
        "qualified_progress_only": True,
        "reason_bearing_decision_parser": True,
        "canonical_decision_unique": True,
        "canonical_decision_complete": True,
        "canonical_decision_fail_closed": True,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_action": False,
        "repeated_build": repeated,
    }
    base.write_json(validation, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
