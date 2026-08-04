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


INSTALL_NAME = "r5_n4_hw_v9_hangloc_qualified"
SOURCE_INSTALL_NAME = "r5_n4_hw_v8_hangloc_fourway"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v8_hangloc_fourway.zip"
)
SOURCE_ZIP_SHA256 = (
    "44e592e4d6059b22d4ccfa76e17ec5d7a995e6375b1960ed743893e212a70308"
)
BOUND_RETURN_SHA256 = (
    "37e84246a8908c38ec5056c3fc965d90198a2809b049f3c7303215e508d07dcf"
)
PLAN_SHA256 = (
    "256b74e977546c611d6c52f9ca0025f0a5bf677a4c6ed8b245e892e5c1473a51"
)
SERVER_RULE_SHA256 = (
    "4c960c5cee73355d08f17d9d1a17edb2931b6a0336ae3831372b41f6af4dc8dc"
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
        ROOT / "tools/node0004_hang_localization_observer_tail_v9.svh"
    )
    base.RUNTIME_SOURCE = (
        ROOT / "tools/node0004_hang_localization_runtime_v9.py"
    )
    base.SOURCE_PREFIX = f"install/cfg_pkg/{SOURCE_INSTALL_NAME}/"
    base.CURRENT_PREFIX = f"install/cfg_pkg/{INSTALL_NAME}/"


def _readme() -> str:
    return f"""# node0004 v9 qualified-progress hang-localization package

Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`.

This package reuses the frozen v8 c0 workload without rebuilding node0004
numeric inputs. It fixes two package-local diagnostic defects found in the v7
return: persistent Buffer4/5 enable levels no longer count as monotonic
end-to-end progress, and the result parser only consumes reason-bearing
`DIAG_DECISION` records. Buffer level state remains visible as raw samples;
rising-edge witnesses are recorded separately for boundary localization.

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
    manifest["schema"] = "resnet50-node0004-hang-localization-package-v9"
    manifest["install_name"] = INSTALL_NAME
    manifest["evidence_level"] = (
        "E2_LOCAL_PLUS_V7_DYNAMIC_DIAGNOSTIC_PACKAGE_REPAIR"
    )
    manifest["frozen_source_package"] = {
        "path": SOURCE_ZIP.relative_to(ROOT).as_posix(),
        "sha256": SOURCE_ZIP_SHA256,
    }
    manifest.pop("bound_v6_return_sha256", None)
    manifest["bound_v7_return_sha256"] = BOUND_RETURN_SHA256
    manifest["active_receipts"] = {
        "plan_mutable_provenance_sha256": PLAN_SHA256,
        "server_package_rule_sha256": SERVER_RULE_SHA256,
        "rules": [
            "CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001",
            "CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001",
            "CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001",
            "CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001",
        ],
    }
    manifest["package_side_repair"] = {
        "classification": "PACKAGE_PROGRESS_DIAGNOSTIC_FAILURE",
        "first_defect": (
            "v7 progress sum included persistent Buffer4/5 enable-level "
            "samples, producing an artificial +524288 per window while all "
            "qualified IO handshakes were frozen"
        ),
        "second_defect": (
            "v7 parser selected the final summary-only DIAG_DECISION line "
            "instead of the preceding reason-bearing decision"
        ),
        "repair": (
            "progress uses only qualified external IO handshakes; Buffer4/5 "
            "raw levels are excluded and separately edge-witnessed; parser "
            "requires reason= and boundary="
        ),
        "functional_semantics_changed": False,
    }
    manifest["unresolved_boundary"] = (
        "v7 evidence bounds the stall after qualified read-data acceptance "
        "and before any Buffer5 write witness; v9 is the minimum diagnostic "
        "repair needed to confirm that interval under a four-window budget"
    )
    manifest["progress_contract"].update(
        {
            "normal_minimum_progress_event": (
                "a qualified external request, read-data, or write-data "
                "handshake on streams 0/1/3/4"
            ),
            "buffer_level_samples_count_as_progress": False,
            "buffer_level_semantics": (
                "raw state only; rising-edge witness is reported separately"
            ),
            "decision_parser_requires_reason_and_boundary": True,
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
        "name": "r5_n4_hw_v8_hangloc_fourway.zip",
        "sha256": SOURCE_ZIP_SHA256,
        "status": "QUARANTINED_PROGRESS_EVENT_QUALIFICATION_DEFECT",
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
    with tempfile.TemporaryDirectory(prefix="node0004-v9-repeat-") as temporary:
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
        "schema": "node0004-hang-localization-package-validation-v9",
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
