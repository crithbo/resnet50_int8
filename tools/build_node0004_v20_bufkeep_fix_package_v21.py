from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v7_four_way_binding_package_v8 as base  # noqa: E402


SOURCE_NAME = "r5_n4_hw_v20_buffer_mode_fix"
INSTALL_NAME = "r5_n4_hw_v21_bufkeep_fix"
SOURCE_ZIP_SHA256 = (
    "e67775aed87d2065f51190049a9a7ba05fb98de9ba08a4362901612248f92ead"
)
BOUND_RETURN_SHA256 = (
    "b8a1ac0a9f7c9d705b21f332b010a3eaa59d131f85fd1eae524a2d2f26b57b55"
)
SERVER_RULE_SHA256 = (
    "88fcc7e87da9d92d281b8096389e31f1735b0e99ce3b13dd37635a8b96c0a7c6"
)
PLAN_MUTABLE_SHA256 = (
    "1bd1179a48b38e6000e44c5584ab0457d4e1aa37cd26166458ff4a5cb6a593e3"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{SOURCE_NAME}.zip"
)
FRESH_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/r5-node0004-bufkeep-fix-c0-v4"
)
FRESH_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/node0004_bufkeep_fix_c0_v4/"
    "accumulate_waves/wave-0.json"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


def _safe_extract_source(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise base.BuildError("v20 source ZIP SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise base.BuildError("v20 source ZIP CRC failed")
        roots: set[str] = set()
        names: set[str] = set()
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or not path.parts
                or info.filename in names
            ):
                raise base.BuildError(f"unsafe v20 ZIP member: {info.filename}")
            names.add(info.filename)
            roots.add(path.parts[0])
        if roots != {SOURCE_NAME}:
            raise base.BuildError(f"v20 source ZIP root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE_NAME


def _replace_text_identity(package: Path) -> None:
    for path in package.rglob("*"):
        if not path.is_file() or path.suffix.lower() == ".bin":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SOURCE_NAME in text:
            path.write_text(
                text.replace(SOURCE_NAME, INSTALL_NAME),
                encoding="utf-8",
                newline="\n",
            )


def _prefix_sca(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    prefix = f"install/cfg_pkg/{INSTALL_NAME}/runs/c0/"
    for item in value.values():
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            old = item["path"]
            if not old.startswith("install/") or ".." in PurePosixPath(old).parts:
                raise base.BuildError(f"unsafe fresh SCA path: {old}")
            item["path"] = prefix + old
    base.write_json(path, value)


def _inject_fresh_c0_physical_assets(package: Path) -> dict[str, Any]:
    pipeline = FRESH_ROOT / "execplan_conv/wave-0/pipeline_output"
    local_report = FRESH_ROOT / "local_rebuild_report.json"
    if not local_report.is_file():
        raise base.BuildError("fresh Buffer-AG keep local rebuild report missing")
    run = package / "workload/runtime/runs/c0"
    copied: list[str] = []
    for name in (
        "execplan.txt",
        "execplan_op_w0.txt",
        "cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin",
    ):
        source = pipeline / "install" / name
        target = run / "install" / name
        if not source.is_file() or not target.is_file():
            raise base.BuildError(f"C0 replacement endpoint missing: {name}")
        shutil.copy2(source, target)
        copied.append(name)
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        source = pipeline / name
        target = run / name
        if not source.is_file() or not target.is_file():
            raise base.BuildError(f"C0 SCA replacement endpoint missing: {name}")
        shutil.copy2(source, target)
        _prefix_sca(target)
        copied.append(name)
    return {
        "fresh_local_root": FRESH_ROOT.relative_to(ROOT).as_posix(),
        "fresh_local_report_sha256": base.sha256(local_report),
        "fresh_config_path": FRESH_CONFIG.relative_to(ROOT).as_posix(),
        "fresh_config_sha256": base.sha256(FRESH_CONFIG),
        "copied_physical_assets": copied,
    }


def _readme() -> str:
    return f"""# node0004 v21 Buffer-AG ROW keep-threshold fix

Classification: `CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`.

The v20 formal return proved that each memory stream's WR_Buffer_AG accepted
only the first row's two COL entries and then remained empty. Active RTL
releases a kept ROW only when:

```text
buffered_col_last_index <= row_keep_last_index
```

All five v20 ROW thresholds were one smaller than their associated COL
terminal. This package changes only:

- stream0/1/2/4 `buf_idx_keep_last_index[0]: 4 -> 5`
- stream3 `buf_idx_keep_last_index[0]: 3 -> 4`

The new value is exactly `GROUPn.COL_LC.last_index`. Mapping, bitstream,
execplan, and SCA were freshly regenerated. Frozen matrices, numeric oracle,
golden/readback payloads, functional RTL, and the existing low-overhead
qualified diagnostics are unchanged.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

The runner creates `{INSTALL_NAME}_return.zip` plus a server-local sidecar.
Under `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`, the user
normally returns only the ZIP.
"""


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise base.BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v21-source-") as temp:
        source = _safe_extract_source(Path(temp))
        shutil.copytree(source, package)
    _replace_text_identity(package)
    injection = _inject_fresh_c0_physical_assets(package)
    (package / "README.md").write_text(
        _readme(), encoding="utf-8", newline="\n"
    )

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-buffer-ag-keep-config-fix-package-v21",
            "install_name": INSTALL_NAME,
            "classification": "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",
            "status": "PACKAGE_READY_NOT_RUN",
            "candidate_release": False,
            "evidence_level": (
                "E2_LOCAL_CONFIG_FIX_PLUS_QUALIFIED_PROGRESS_DIAGNOSTICS"
            ),
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": True,
            "frozen_c0_inputs_reused_read_only": True,
            "formal_readback_claimed": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    receipts = manifest["active_receipts"]
    receipts["plan_mutable_provenance_sha256"] = PLAN_MUTABLE_SHA256
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    for item in receipts["generation_read_receipt"]:
        if item["path"] == ".agents/rules/服务器测试包生成规则.md":
            item["sha256"] = SERVER_RULE_SHA256
    rules = receipts["rules"]
    new_rule = "CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001"
    if new_rule not in rules:
        rules.append(new_rule)

    manifest["v20_return_adjudication"] = {
        "bound_return_sha256": BOUND_RETURN_SHA256,
        "status": "LONG_RUNNING_HANG_AT_BUFFER_AG_ROW_KEEP_RELEASE",
        "last_good": (
            "each stream WR_Buffer_AG enqueued and dequeued the first row's "
            "two COL entries; Buffer0 supplied four accepted SA reads"
        ),
        "first_bad": (
            "no next-row Buffer-AG enqueue after COL terminal because the "
            "ROW keep threshold was one smaller than COL last_index"
        ),
        "root_cause": "BUFFER_AG_ROW_KEEP_THRESHOLD_LT_COL_TERMINAL",
    }
    leaf_changes = []
    for index in range(5):
        old = 3 if index == 3 else 4
        new = 4 if index == 3 else 5
        leaf_changes.append(
            {
                "path": (
                    f"stream_engine.stream{index}."
                    "buf_idx_keep_last_index[0]"
                ),
                "old": old,
                "new": new,
            }
        )
    manifest["configuration_fix"] = {
        "owner": "Conv signed-A typed materializer",
        "leaf_changes": leaf_changes,
        "formula": (
            "stream_engine.streamN.buf_idx_keep_last_index[0] = "
            "buffer_loop_configs.GROUPN.COL_LC.last_index"
        ),
        "v20_counterexample": (
            "buffered COL terminal is larger than ROW keep threshold for all "
            "five streams, so Buffer_AG_Idx_Queue row release is false"
        ),
        "functional_rtl_changed": False,
        **injection,
    }
    manifest["superseded_v20_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_ZIP_SHA256,
        "status": "CONSUMED_RETURN_SUPERSEDED_BY_CONFIG_FIX",
    }
    manifest["return_transport_policy"] = {
        "rule_id": new_rule,
        "runner_generates_local_sidecar": True,
        "user_upload_sidecar_required": False,
        "user_transfer_identity_attested": True,
        "analysis_recomputes_return_zip_sha256": True,
        "internal_manifest_allowlist_and_source_binding_unchanged": True,
    }
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    observer_sha = manifest["observer_binding_four_way"]["source"]["sha256"]
    observer = base.observer_precompile_receipt(package, observer_sha)
    if not observer["valid"]:
        raise base.BuildError(
            f"observer XMR gate failed after C0 injection: {observer['errors']}"
        )
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
    with tempfile.TemporaryDirectory(prefix="node0004-v21-repeat-") as temp:
        repeat_root = Path(temp)
        repeat_package = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        repeated = base.sha256(repeat_zip) == digest
    if not repeated:
        raise base.BuildError("v21 deterministic rebuild differs")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-buffer-ag-keep-config-fix-package-validation-v21",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": repeated,
        "source_v20_sha256": SOURCE_ZIP_SHA256,
        "bound_v20_return_sha256": BOUND_RETURN_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": True,
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
