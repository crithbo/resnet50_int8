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


SOURCE_NAME = "r5_n4_hw_v19_buffer0_flow_diag"
INSTALL_NAME = "r5_n4_hw_v20_buffer_mode_fix"
SOURCE_ZIP_SHA256 = (
    "0420907934a5a603ea40a127128664affe0182b7d6bc986107e0b0b04303adf3"
)
BOUND_RETURN_SHA256 = (
    "aba139e405f894564ec105e5929a3b02e6d44c6aae1d004d898d6f6106e27205"
)
SERVER_RULE_SHA256 = (
    "507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d"
)
PLAN_MUTABLE_SHA256 = (
    "0e3ec9d2346f9ff9561456cc1c9fb2653385214009a2eaeea46f731c85fc5183"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{SOURCE_NAME}.zip"
)
FRESH_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-buffer-mode-fix-c0-v3"
)
FRESH_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/node0004_buffer_mode_fix_c0_v3/"
    "accumulate_waves/wave-0.json"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


def _safe_extract_source(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise base.BuildError("v19 source ZIP SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise base.BuildError("v19 source ZIP CRC failed")
        roots: set[str] = set()
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or not path.parts
            ):
                raise base.BuildError(f"unsafe v19 ZIP member: {info.filename}")
            roots.add(path.parts[0])
        if roots != {SOURCE_NAME}:
            raise base.BuildError(f"v19 source ZIP root differs: {sorted(roots)}")
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
        raise base.BuildError("fresh buffer-mode local rebuild report missing")
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
    return f"""# node0004 v20 Buffer0/1 row-stationary lifetime fix

Classification: `CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`.

The v19 formal return proved that Buffer0 completed one ARM read, then the
configured `mode=0` advanced `array_req_addr` from populated row0 to unwritten
row1 while row0 remained valid and its four-use lifetime was not consumed.

This package changes exactly two logical leaves:

- `buffer_config.buffer0.mode: 0 -> 1`
- `buffer_config.buffer1.mode: 0 -> 1`

In active RTL mode1 makes lifetime the inner counter.  Each signed-weight row
is therefore read four times, cleared on the fourth accepted read, and only
then advances to the next row.  Mapping, bitstream, execplan, and SCA were
freshly regenerated. Frozen matrices and golden/readback payloads are
byte-identical to v19. Existing qualified progress, canonical decision, ABPE,
A_REUSE, and BUFFER0_FLOW diagnostics remain enabled.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip` and adjacent `.sha256`.
"""


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise base.BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v20-source-") as temp:
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
            "schema": "resnet50-node0004-buffer-mode-config-fix-package-v20",
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
    manifest["v19_return_adjudication"] = {
        "bound_return_sha256": BOUND_RETURN_SHA256,
        "status": "LONG_RUNNING_HANG_AT_BUFFER0_ROW_MODE",
        "last_good": (
            "WR_Buffer_AG enqueued/dequeued both row0 writes and Buffer0 "
            "completed its first ARM read"
        ),
        "first_bad": (
            "ARM mode0 advanced to row1 while row1 was invalid and row0 "
            "remained fully valid"
        ),
        "root_cause": "BUFFER0_1_MODE0_ADVANCES_ROW_BEFORE_LIFETIME",
    }
    manifest["configuration_fix"] = {
        "owner": "Conv signed-A typed materializer",
        "leaf_changes": [
            {
                "path": "buffer_config.buffer0.mode",
                "old": 0,
                "new": 1,
            },
            {
                "path": "buffer_config.buffer1.mode",
                "old": 0,
                "new": 1,
            },
        ],
        "formula": (
            "mode1 => array_req_addr=array_counter_1 and "
            "array_life_cnt=array_counter_0; with logical lifetime4, "
            "row address sequence is 0,0,0,0 then 1"
        ),
        "mode0_counterexample": "row address sequence begins 0,1",
        "functional_rtl_changed": False,
        **injection,
    }
    manifest["superseded_v19_diagnostic"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_ZIP_SHA256,
        "status": "CONSUMED_RETURN_SUPERSEDED_BY_CONFIG_FIX",
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
    with tempfile.TemporaryDirectory(prefix="node0004-v20-repeat-") as temp:
        repeat_root = Path(temp)
        repeat_package = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        repeated = base.sha256(repeat_zip) == digest
    if not repeated:
        raise base.BuildError("v20 deterministic rebuild differs")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-buffer-mode-config-fix-package-validation-v20",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": repeated,
        "source_v19_sha256": SOURCE_ZIP_SHA256,
        "bound_v19_return_sha256": BOUND_RETURN_SHA256,
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
