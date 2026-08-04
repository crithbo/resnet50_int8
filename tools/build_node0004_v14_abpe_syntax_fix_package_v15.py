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

import tools.build_node0004_v13_a_pingpong_fix_package_v14 as prior  # noqa: E402
import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


INSTALL_NAME = "r5_n4_hw_v15_abpe_syntax_fix"
PLAN_SHA256 = "558dce2c256f91bcf537750262b717db00c97ea415849d544cc13d365049a47e"
SOURCE_V14 = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v14_a_pingpong_fix.zip"
)
SOURCE_V14_SHA256 = (
    "4bf890b5ad57d8952226125de4979e96e0c00a1d347d2fb59aec7cabb1cf44b2"
)
BOUND_V14_RETURN_SHA256 = (
    "5a075ae69e0f89aa2da356c9968ea79de099ec7b38e1ba20b19c8a6757d2525d"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


def _patch_observer(package: Path, old_sha: str) -> dict[str, Any]:
    path = package / "tb_probe/native_return_observer.svh"
    text = path.read_text(encoding="utf-8")
    declaration = """    logic [`SLICE_GROUP_SIZE-1:0][`SLICE_GROUP_NUM-1:0]
          [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][1:0]
          return_obs_abpe_masked_valid_mon;
"""
    replacement_declaration = declaration + """    logic [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_abpe_masked_a_mon
          [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
    logic [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0]
          return_obs_abpe_masked_b_mon
          [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
"""
    if text.count(declaration) != 1:
        raise base.BuildError("ABPE packed monitor declaration differs")
    text = text.replace(declaration, replacement_declaration)

    assignment = """                                .u_SA_PE.u_SA_PE_Control_Block
                                .sa_pe_inport_valid_bit_masked[1:0];
"""
    replacement_assignment = assignment + """                        assign return_obs_abpe_masked_a_mon
                            [return_obs_abpe_group][return_obs_abpe_slice]
                            [return_obs_abpe_row][return_obs_abpe_col] =
                            return_obs_abpe_masked_valid_mon
                                [return_obs_abpe_group][return_obs_abpe_slice]
                                [return_obs_abpe_row][return_obs_abpe_col][0];
                        assign return_obs_abpe_masked_b_mon
                            [return_obs_abpe_group][return_obs_abpe_slice]
                            [return_obs_abpe_row][return_obs_abpe_col] =
                            return_obs_abpe_masked_valid_mon
                                [return_obs_abpe_group][return_obs_abpe_slice]
                                [return_obs_abpe_row][return_obs_abpe_col][1];
"""
    if text.count(assignment) != 1:
        raise base.BuildError("ABPE masked-valid assignment differs")
    text = text.replace(assignment, replacement_assignment)

    old_a = """                    return_obs_abpe_masked_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][0],
"""
    new_a = """                    return_obs_abpe_masked_a_mon
                        [return_obs_group_id][return_obs_local_slice_id],
"""
    old_b = """                    return_obs_abpe_masked_valid_mon
                        [return_obs_group_id][return_obs_local_slice_id]
                        [`SA_ROW_PE_NUM-1:0][`SA_COL_PE_NUM-1:0][1],
"""
    new_b = """                    return_obs_abpe_masked_b_mon
                        [return_obs_group_id][return_obs_local_slice_id],
"""
    if text.count(old_a) != 1 or text.count(old_b) != 1:
        raise base.BuildError("ABPE VCS-failing display expressions differ")
    text = text.replace(old_a, new_a).replace(old_b, new_b)
    path.write_text(text, encoding="utf-8", newline="\n")
    new_sha = base.sha256(path)

    runner = package / "PREPARE_AND_RUN.sh"
    runner_text = runner.read_text(encoding="utf-8")
    if old_sha not in runner_text:
        raise base.BuildError("old observer SHA is not bound in runner")
    runner.write_text(
        runner_text.replace(old_sha, new_sha),
        encoding="utf-8",
        newline="\n",
    )
    return {
        "path": path.relative_to(package).as_posix(),
        "old_sha256": old_sha,
        "new_sha256": new_sha,
        "size_bytes": path.stat().st_size,
        "repair": (
            "replace VCS-invalid post-index multidimensional packed slicing "
            "with elaboration-time per-PE A/B aggregate monitor arrays"
        ),
    }


def _readme() -> str:
    return f"""# node0004 v15 ABPE observer syntax fix

Classification: `CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`.

The v14 return stopped before simulation because VCS rejected the package-local
observer expression that indexed two packed dimensions after runtime group and
slice selects.  This package keeps the exact v14 Conv configuration, mapping,
bitstream, execplan, SCA, frozen matrices and golden payloads.  It only replaces
that observer snapshot expression with two elaboration-time per-PE aggregate
arrays for masked A and masked B.  The observer remains read-only and does not
enter qualified progress.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip` and adjacent `.sha256`.
"""


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    prior.INSTALL_NAME = INSTALL_NAME
    prior.PLAN_SHA256 = PLAN_SHA256
    package, source_proof = prior.build_directory(destination)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    old_observer_sha = manifest["observer_binding_four_way"]["source"]["sha256"]
    repair = _patch_observer(package, old_observer_sha)

    (package / "README.md").write_text(
        _readme(), encoding="utf-8", newline="\n"
    )
    manifest["schema"] = "resnet50-node0004-abpe-syntax-fix-package-v15"
    manifest["install_name"] = INSTALL_NAME
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["evidence_level"] = (
        "E2_LOCAL_CONFIG_FIX_PLUS_V14_COMPILE_FAILURE_PACKAGE_REPAIR"
    )
    manifest["active_receipts"]["plan_mutable_provenance_sha256"] = PLAN_SHA256
    manifest["observer_binding_four_way"]["source"].update(
        {
            "size_bytes": repair["size_bytes"],
            "sha256": repair["new_sha256"],
        }
    )
    manifest["observer_sha256"] = repair["new_sha256"]
    manifest["observer_compile_repair"] = {
        "classification": "PACKAGE_LOCAL_READ_ONLY_OBSERVER_SYNTAX_FIX",
        "bound_return_sha256": BOUND_V14_RETURN_SHA256,
        "first_divergence": (
            "VCS syntax error at v14 package-local observer line 2405, "
            "before elaboration and simulation"
        ),
        "source_package": {
            "path": SOURCE_V14.relative_to(ROOT).as_posix(),
            "sha256": SOURCE_V14_SHA256,
        },
        "functional_semantics_changed": False,
        "qualified_progress_changed": False,
        **repair,
    }
    manifest["superseded_compile_failed_package"] = {
        "path": SOURCE_V14.relative_to(ROOT).as_posix(),
        "sha256": SOURCE_V14_SHA256,
        "status": "QUARANTINED_PACKAGE_OBSERVER_SYNTAX_COMPILE_FAILURE",
    }
    manifest["numeric_analysis_repeated"] = False
    manifest["node0004_workload_rebuilt"] = False
    manifest["configuration_rebuilt"] = False
    manifest["functional_rtl_modified"] = False
    manifest["server_rtl_entries"] = 0
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)

    observer = base.observer_precompile_receipt(
        package, repair["new_sha256"]
    )
    if not observer["valid"]:
        raise base.BuildError(
            f"v15 observer receipt failed: {observer['errors']}"
        )
    return package, {
        "preflight": source_proof["preflight"],
        "observer": observer,
        "post_observer_patch_final_zip_audit_required": True,
    }


def _repeat(package: Path, zip_path: Path) -> dict[str, Any]:
    base.deterministic_zip(package, zip_path)
    records = base.package_records(package)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v15-repeat-") as temporary:
        repeat_root = Path(temporary)
        repeat_package, _ = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        if records != base.package_records(repeat_package):
            raise base.BuildError("repeated v15 package trees differ")
        if digest != base.sha256(repeat_zip):
            raise base.BuildError("repeated v15 ZIPs differ")
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
    package = output / INSTALL_NAME
    zip_path = output / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    validation = output / f"{INSTALL_NAME}.validation.json"
    for path in (package, zip_path, sidecar, validation):
        if path.exists():
            print(f"refusing to overwrite: {path}")
            return 1
    output.mkdir(parents=True, exist_ok=True)
    package, proof = build_directory(output)
    repeated = _repeat(package, zip_path)
    digest = base.sha256(zip_path)
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    receipt = {
        "schema": "node0004-abpe-syntax-fix-package-validation-v15",
        "status": "PACKAGE_BUILT_PENDING_FINAL_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "source_v14_sha256": SOURCE_V14_SHA256,
        "bound_v14_return_sha256": BOUND_V14_RETURN_SHA256,
        "preflight": proof["preflight"],
        "observer": proof["observer"],
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": False,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_action": False,
        "repeated_build": repeated,
        "final_zip_rule_self_audit_pending": True,
    }
    base.write_json(validation, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
