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


SOURCE_NAME = "r5_n4_hw_v21_bufkeep_fix"
INSTALL_NAME = "r5_n4_hw_v22_featurebind"
SOURCE_ZIP_SHA256 = (
    "bd9fadb9bdd18c1678461ae055fea7e15be5d414957b76de48f761833e345131"
)
SERVER_RULE_SHA256 = (
    "fb400d016a1328e0de1d576f76af5905f93e77c86361321af39513f329a43025"
)
PLAN_MUTABLE_SHA256 = (
    "23087aee1f7dadd123eebca24d802bd2444f2b26b442cc6a77c764bf85d930f9"
)
NEW_RULE_ID = "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{SOURCE_NAME}.zip"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


class BuildError(RuntimeError):
    pass


def safe_extract(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise BuildError("v21 source ZIP SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("v21 source ZIP CRC failed")
        roots: set[str] = set()
        names: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or info.filename in names
            ):
                raise BuildError(f"unsafe v21 member: {info.filename}")
            names.add(info.filename)
            roots.add(pure.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"v21 root differs: {sorted(roots)}")
        archive.extractall(destination)
    return destination / SOURCE_NAME


def replace_identity(package: Path) -> None:
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


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise BuildError(
            f"patch anchor count differs for {path.name}: {text.count(old)}"
        )
    path.write_text(
        text.replace(old, new, 1),
        encoding="utf-8",
        newline="\n",
    )


def patch_observer(package: Path) -> str:
    path = package / "tb_probe/native_return_observer.svh"
    anchor = """    always @(posedge u_NDP_Top_new.clk_db or
             negedge u_NDP_Top_new.rst_n_db) begin
        if (!u_NDP_Top_new.rst_n_db) begin
            return_obs_active = 1'b0;
            return_obs_total_cycles = 0;
"""
    insertion = """    // Package-local feature binding markers.  The #0 moves
    // the receipt into the inactive region so every independent plusarg
    // initial block has resolved while simulation time remains exactly zero.
    bit return_feature_abpe_enabled;
    bit return_feature_hang_enabled;
    integer return_feature_hang_sample_cycles;
    integer return_feature_hang_stall_windows;
    integer return_feature_hang_max_cycles;
    integer return_feature_plusarg_status;

    initial begin
        return_feature_abpe_enabled =
            $test$plusargs("RETURN_OBS_ABPE");
        return_feature_hang_enabled =
            $test$plusargs("RETURN_HANG_DIAG");
        return_feature_hang_sample_cycles = 262144;
        return_feature_hang_stall_windows = 4;
        return_feature_hang_max_cycles = 8388608;
        return_feature_plusarg_status = $value$plusargs(
            "RETURN_HANG_DIAG_SAMPLE_CYCLES=%d",
            return_feature_hang_sample_cycles
        );
        return_feature_plusarg_status = $value$plusargs(
            "RETURN_HANG_DIAG_STALL_WINDOWS=%d",
            return_feature_hang_stall_windows
        );
        return_feature_plusarg_status = $value$plusargs(
            "RETURN_HANG_DIAG_MAX_CYCLES=%d",
            return_feature_hang_max_cycles
        );
        #0;
        if (return_obs_enabled && return_obs_fd != 0) begin
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_DEEP enabled=%0d limit_name=RETURN_OBS_DEEP_LIMIT limit=%0d",
                return_obs_deep_enabled,
                return_obs_deep_limit
            );
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_OBS_ABPE enabled=%0d budget_name=RETURN_HANG_DIAG_MAX_CYCLES budget=%0d",
                return_feature_abpe_enabled,
                return_feature_hang_max_cycles
            );
            $fdisplay(
                return_obs_fd,
                "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | feature=RETURN_HANG_DIAG enabled=%0d sample_cycles=%0d stall_windows=%0d max_cycles=%0d",
                return_feature_hang_enabled,
                return_feature_hang_sample_cycles,
                return_feature_hang_stall_windows,
                return_feature_hang_max_cycles
            );
            $fflush(return_obs_fd);
            $display(
                "[0] [DIAGNOSTIC_FEATURE_ENABLE_V1] feature=RETURN_OBS_DEEP enabled=%0d limit=%0d",
                return_obs_deep_enabled,
                return_obs_deep_limit
            );
            $display(
                "[0] [DIAGNOSTIC_FEATURE_ENABLE_V1] feature=RETURN_OBS_ABPE enabled=%0d budget=%0d",
                return_feature_abpe_enabled,
                return_feature_hang_max_cycles
            );
            $display(
                "[0] [DIAGNOSTIC_FEATURE_ENABLE_V1] feature=RETURN_HANG_DIAG enabled=%0d sample_cycles=%0d stall_windows=%0d max_cycles=%0d",
                return_feature_hang_enabled,
                return_feature_hang_sample_cycles,
                return_feature_hang_stall_windows,
                return_feature_hang_max_cycles
            );
        end
    end

""" + anchor
    replace_once(path, anchor, insertion)
    return base.sha256(path)


def patch_runtime_wrapper(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime.py"
    anchor = """def analyze(
    package_root: Path, evidence_root: Path, run_root: Path
) -> dict[str, Any]:
"""
    helper = """FEATURE_CONTRACTS = (
    {
        "feature": "RETURN_OBS_DEEP",
        "enable": "+RETURN_OBS_DEEP",
        "limits": ("+RETURN_OBS_DEEP_LIMIT=256",),
        "marker_tokens": (
            "feature=RETURN_OBS_DEEP",
            "enabled=1",
            "limit=256",
        ),
    },
    {
        "feature": "RETURN_OBS_ABPE",
        "enable": "+RETURN_OBS_ABPE",
        "limits": ("+RETURN_HANG_DIAG_MAX_CYCLES=8388608",),
        "marker_tokens": (
            "feature=RETURN_OBS_ABPE",
            "enabled=1",
            "budget=8388608",
        ),
    },
    {
        "feature": "RETURN_HANG_DIAG",
        "enable": "+RETURN_HANG_DIAG",
        "limits": (
            "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144",
            "+RETURN_HANG_DIAG_STALL_WINDOWS=4",
            "+RETURN_HANG_DIAG_MAX_CYCLES=8388608",
        ),
        "marker_tokens": (
            "feature=RETURN_HANG_DIAG",
            "enabled=1",
            "sample_cycles=262144",
            "stall_windows=4",
            "max_cycles=8388608",
        ),
    },
)


def diagnostic_feature_binding(
    evidence_root: Path, run_root: Path
) -> dict[str, Any]:
    compile_status = base._status(evidence_root / "compile_exit_status.txt")
    argv_path = run_root / "c0/simulator_argv.txt"
    observer_path = run_root / "c0/return_observer.log"
    argv = (
        argv_path.read_text(encoding="utf-8", errors="replace")
        if argv_path.is_file()
        else ""
    )
    lines = (
        observer_path.read_text(
            encoding="utf-8", errors="replace"
        ).splitlines()
        if observer_path.is_file()
        else []
    )
    feature_rows = []
    for contract in FEATURE_CONTRACTS:
        markers = [
            line
            for line in lines
            if "| DIAGNOSTIC_FEATURE_ENABLE_V1 |" in line
            and f"feature={contract['feature']}" in line
        ]
        enable_present = contract["enable"] in argv.split()
        limits_present = all(
            token in argv.split() for token in contract["limits"]
        )
        marker_valid = (
            len(markers) == 1
            and markers[0].startswith("0 |")
            and all(token in markers[0] for token in contract["marker_tokens"])
        )
        feature_rows.append(
            {
                "feature": contract["feature"],
                "runtime_enable_parameter": contract["enable"],
                "limit_or_budget_parameters": list(contract["limits"]),
                "simulator_argv_enable_present": enable_present,
                "simulator_argv_limits_present": limits_present,
                "time_zero_marker_schema": "DIAGNOSTIC_FEATURE_ENABLE_V1",
                "time_zero_marker_count": len(markers),
                "time_zero_marker": markers[0] if len(markers) == 1 else None,
                "time_zero_marker_valid": marker_valid,
                "returned_record_target": "runs/c0/return_observer.log",
                "valid": enable_present and limits_present and marker_valid,
            }
        )
    valid = all(row["valid"] for row in feature_rows)
    if compile_status != 0:
        status = "NOT_REACHED_COMPILE_FAILED"
    elif valid:
        status = "DIAGNOSTIC_FEATURE_RUNTIME_BINDING_PASS"
    else:
        status = "PACKAGE_DIAGNOSTIC_FEATURE_BINDING_INCOMPLETE"
    value = {
        "schema": "node0004-diagnostic-feature-runtime-binding-v1",
        "rule_id": (
            "CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001"
        ),
        "valid": valid if compile_status == 0 else False,
        "status": status,
        "compile_exit_status": compile_status,
        "simulator_argv_target": "runs/c0/simulator_argv.txt",
        "feature_record_target": "runs/c0/return_observer.log",
        "return_binding_receipt_target": (
            "evidence/diagnostic_feature_binding.json"
        ),
        "features": feature_rows,
    }
    write_json(evidence_root / "diagnostic_feature_binding.json", value)
    return value


""" + anchor
    replace_once(path, anchor, helper)
    old = """    compile_status = base._status(evidence_root / "compile_exit_status.txt")
    run_status = base._status(evidence_root / "run_exit_status.txt")
"""
    new = """    compile_status = base._status(evidence_root / "compile_exit_status.txt")
    run_status = base._status(evidence_root / "run_exit_status.txt")
    feature_binding = diagnostic_feature_binding(evidence_root, run_root)
"""
    replace_once(path, old, new)
    old_value = """        "canonical_validation": {
            "valid": canonical["valid"],
            "candidate_count": canonical["candidate_count"],
            "parsed_count": canonical["parsed_count"],
            "errors": canonical["errors"],
        },
        "formal_readback_claimed": False,
"""
    new_value = """        "canonical_validation": {
            "valid": canonical["valid"],
            "candidate_count": canonical["candidate_count"],
            "parsed_count": canonical["parsed_count"],
            "errors": canonical["errors"],
        },
        "diagnostic_feature_binding": feature_binding,
        "formal_readback_claimed": False,
"""
    replace_once(path, old_value, new_value)


def patch_runtime_collector(package: Path) -> None:
    path = package / "package_tools/node0004_hang_localization_runtime_v7.py"
    anchor = """        (
            evidence_root / "signal_status.txt",
            "evidence/signal_status.txt",
            False,
        ),
"""
    insertion = """        (
            evidence_root / "signal_status.txt",
            "evidence/signal_status.txt",
            False,
        ),
        (
            evidence_root / "diagnostic_feature_binding.json",
            "evidence/diagnostic_feature_binding.json",
            True,
        ),
"""
    replace_once(path, anchor, insertion)


def readme() -> str:
    return f"""# node0004 v22 diagnostic-feature runtime binding

Classification: `CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`.

This is a content-preserving successor to v21. The v21 configuration fix,
bitstream, execplan, SCA, matrices, golden, and functional RTL binding are
unchanged. Only package-local diagnostic delivery was strengthened for
`CDA-SERVER-DIAGNOSTIC-FEATURE-RUNTIME-ENABLE-END-TO-END-001`.

The independently runtime-gated features are:

- `RETURN_OBS_DEEP`, limit `RETURN_OBS_DEEP_LIMIT=256`;
- `RETURN_OBS_ABPE`, bounded by `RETURN_HANG_DIAG_MAX_CYCLES=8388608`;
- `RETURN_HANG_DIAG`, sample `262144`, stall windows `4`, maximum cycles
  `8388608`.

Each feature now emits a simulation-time-zero
`DIAGNOSTIC_FEATURE_ENABLE_V1` marker. The finalizer always creates and
returns `evidence/diagnostic_feature_binding.json`, which binds actual
simulator argv, the time-zero marker, and the returned observer target.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip`. The runner also creates a local
sidecar; user upload of that sidecar remains optional.
"""


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v22-source-") as temp:
        source = safe_extract(Path(temp))
        shutil.copytree(source, package)
    replace_identity(package)
    observer_sha = patch_observer(package)
    patch_runtime_wrapper(package)
    patch_runtime_collector(package)
    (package / "README.md").write_text(
        readme(), encoding="utf-8", newline="\n"
    )

    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-feature-runtime-binding-package-v22",
            "install_name": INSTALL_NAME,
            "status": "PACKAGE_READY_NOT_RUN",
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": True,
            "configuration_rebuilt_in_this_successor": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
        }
    )
    receipts = manifest["active_receipts"]
    receipts["plan_mutable_provenance_sha256"] = PLAN_MUTABLE_SHA256
    receipts["server_package_rule_sha256"] = SERVER_RULE_SHA256
    for item in receipts["generation_read_receipt"]:
        if item.get("reason") == "common server package gates":
            item["sha256"] = SERVER_RULE_SHA256
    if NEW_RULE_ID not in receipts["rules"]:
        receipts["rules"].append(NEW_RULE_ID)
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"]["sha256"] = observer_sha
    manifest["diagnostic_feature_runtime_binding"] = {
        "rule_id": NEW_RULE_ID,
        "receipt_schema": "node0004-diagnostic-feature-runtime-binding-v1",
        "receipt_return_target": "evidence/diagnostic_feature_binding.json",
        "simulator_argv_return_target": "runs/c0/simulator_argv.txt",
        "feature_record_return_target": "runs/c0/return_observer.log",
        "features": [
            {
                "feature": "RETURN_OBS_DEEP",
                "runtime_enable_parameter": "+RETURN_OBS_DEEP",
                "limit_or_budget_parameters": [
                    "+RETURN_OBS_DEEP_LIMIT=256"
                ],
                "time_zero_marker": (
                    "DIAGNOSTIC_FEATURE_ENABLE_V1 "
                    "feature=RETURN_OBS_DEEP enabled=1 limit=256"
                ),
                "expected_record_schema": "DEEP_COUNTS",
            },
            {
                "feature": "RETURN_OBS_ABPE",
                "runtime_enable_parameter": "+RETURN_OBS_ABPE",
                "limit_or_budget_parameters": [
                    "+RETURN_HANG_DIAG_MAX_CYCLES=8388608"
                ],
                "time_zero_marker": (
                    "DIAGNOSTIC_FEATURE_ENABLE_V1 "
                    "feature=RETURN_OBS_ABPE enabled=1 budget=8388608"
                ),
                "expected_record_schema": "ABPE_BOUNDARY_V1",
            },
            {
                "feature": "RETURN_HANG_DIAG",
                "runtime_enable_parameter": "+RETURN_HANG_DIAG",
                "limit_or_budget_parameters": [
                    "+RETURN_HANG_DIAG_SAMPLE_CYCLES=262144",
                    "+RETURN_HANG_DIAG_STALL_WINDOWS=4",
                    "+RETURN_HANG_DIAG_MAX_CYCLES=8388608",
                ],
                "time_zero_marker": (
                    "DIAGNOSTIC_FEATURE_ENABLE_V1 "
                    "feature=RETURN_HANG_DIAG enabled=1 "
                    "sample_cycles=262144 stall_windows=4 "
                    "max_cycles=8388608"
                ),
                "expected_record_schema": "CANONICAL_DIAG_DECISION_V1",
            },
        ],
        "four_negative_controls_required": [
            "delete_enable",
            "delete_or_tamper_limit",
            "delete_time_zero_marker_contract",
            "delete_feature_return_target",
        ],
    }
    manifest["superseded_v21_package"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_ZIP_SHA256,
        "status": "QUARANTINED_RULE_DRIFT_FEATURE_BINDING_INCOMPLETE",
    }
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    observer_receipt = base.observer_precompile_receipt(package, observer_sha)
    if not observer_receipt["valid"]:
        raise BuildError(
            f"observer XMR gate failed: {observer_receipt['errors']}"
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
            raise BuildError(f"refusing to overwrite: {target}")
    package = build_directory(output)
    base.deterministic_zip(package, zip_path)
    digest = base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v22-repeat-") as temp:
        repeat = Path(temp)
        repeat_package = build_directory(repeat)
        repeat_zip = repeat / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        deterministic = base.sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("v22 deterministic repeat differs")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-feature-runtime-binding-build-v22",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "source_v21_sha256": SOURCE_ZIP_SHA256,
        "current_server_rule_sha256": SERVER_RULE_SHA256,
        "deterministic_rebuild_equal": deterministic,
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": True,
        "configuration_rebuilt_in_this_successor": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    base.write_json(validation, report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
