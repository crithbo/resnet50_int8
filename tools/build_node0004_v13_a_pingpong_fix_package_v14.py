from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.build_node0004_v12_abpe_boundary_package_v13 as prior  # noqa: E402


INSTALL_NAME = "r5_n4_hw_v14_a_pingpong_fix"
PLAN_SHA256 = "68cf915698b905c24f8e346dca0fac7b2012df3eaf18e563c9799685e9043025"
SERVER_RULE_SHA256 = (
    "7672b44bbcb7e130792d6b288188caa2509dc72b1ea3962bf44ffb82588009aa"
)
SOURCE_V13_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_n4_hw_v13_abpe_boundary.zip"
)
SOURCE_V13_SHA256 = (
    "a9e941dbb108f3672d05005ce04e02314dbfb87b410626a0233f1e07c830e5c9"
)
FRESH_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-a-pingpong-fix-c0-v2"
)
FRESH_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/node0004_a_pingpong_fix_c0_v2/"
    "accumulate_waves/wave-0.json"
)
OUTPUT_ROOT = ROOT / "artifacts/operator_config_validation/r5-server-test-packages"


def _configure_prior() -> None:
    prior.INSTALL_NAME = INSTALL_NAME
    prior.PLAN_SHA256 = PLAN_SHA256
    prior.SERVER_RULE_SHA256 = SERVER_RULE_SHA256


def _prefix_sca(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    prefix = f"install/cfg_pkg/{INSTALL_NAME}/runs/c0/"
    for item in value.values():
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            old = item["path"]
            if not old.startswith("install/") or ".." in Path(old).parts:
                raise prior.prior.base.BuildError(f"unsafe fresh SCA path: {old}")
            item["path"] = prefix + old
    prior.prior.base.write_json(path, value)


def _inject_fresh_c0_physical_assets(package: Path) -> dict[str, Any]:
    pipeline = FRESH_ROOT / "execplan_conv/wave-0/pipeline_output"
    if not (FRESH_ROOT / "local_rebuild_report.json").is_file():
        raise prior.prior.base.BuildError("fresh local rebuild report missing")
    run = package / "workload/runtime/runs/c0"
    source_install = pipeline / "install"
    target_install = run / "install"
    copied: list[str] = []
    for name in (
        "execplan.txt",
        "execplan_op_w0.txt",
        "cfg_pkg/op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin",
    ):
        source = source_install / name
        target = target_install / name
        if not source.is_file() or not target.is_file():
            raise prior.prior.base.BuildError(f"C0 replacement endpoint missing: {name}")
        shutil.copy2(source, target)
        copied.append(name)
    for name in ("sca_cfg.json", "sca_cfg_D.json"):
        shutil.copy2(pipeline / name, run / name)
        _prefix_sca(run / name)
        copied.append(name)
    return {
        "fresh_local_root": FRESH_ROOT.relative_to(ROOT).as_posix(),
        "fresh_local_report_sha256": prior.prior.base.sha256(
            FRESH_ROOT / "local_rebuild_report.json"
        ),
        "fresh_config_path": FRESH_CONFIG.relative_to(ROOT).as_posix(),
        "fresh_config_sha256": prior.prior.base.sha256(FRESH_CONFIG),
        "copied_physical_assets": copied,
    }


def _patch_package_local_runtime_classification(package: Path) -> list[str]:
    changed: list[str] = []
    helper = (
        package
        / "package_tools/node0004_hang_localization_runtime_v7.py"
    )
    helper_text = helper.read_text(encoding="utf-8")
    old_gate = (
        'if manifest.get("classification") != '
        '"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX":'
    )
    new_gate = (
        'if manifest.get("classification") not in {'
        '"DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX", '
        '"CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"}:'
    )
    if helper_text.count(old_gate) != 1:
        raise prior.prior.base.BuildError("v7 runtime classification gate differs")
    helper_text = helper_text.replace(old_gate, new_gate)
    helper_text = helper_text.replace(
        '"classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",',
        '"classification": manifest.get("classification"),',
        1,
    )
    helper.write_text(helper_text, encoding="utf-8", newline="\n")
    changed.append(helper.relative_to(package).as_posix())

    runtime = package / "package_tools/node0004_hang_localization_runtime.py"
    runtime_text = runtime.read_text(encoding="utf-8")
    token = '"classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",'
    if runtime_text.count(token) != 1:
        raise prior.prior.base.BuildError("v12 runtime classification output differs")
    runtime_text = runtime_text.replace(
        token,
        '"classification": '
        '"CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",',
        1,
    )
    runtime.write_text(runtime_text, encoding="utf-8", newline="\n")
    changed.append(runtime.relative_to(package).as_posix())
    return changed


def _readme() -> str:
    return f"""# node0004 v14 matched A ping-pong configuration fix

Classification: `CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`.

The frozen v13 C0 configuration enabled SA inport0 ping-pong between physical
buffers 0/1, while MSE stream0 remained fixed on buffer0.  After the first
terminal-tag-4 acceptance, the consumer selected unwritten buffer1 and the
producer kept refilling buffer0.  This package changes exactly two logical
configuration leaves: `stream0.ping_pong: 0 -> 1` and
`stream0.pingpong_last_index: null -> 4`.

The final C0 mapping, bitstream, execplan and SCA were regenerated from that
corrected configuration. Frozen A/B/C matrices and golden/readback payloads
are byte-identical to v13; numeric W3 analysis was not repeated.  Existing
qualified progress, canonical-decision, ABPE and fail-closed return diagnostics
remain enabled.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip` and adjacent `.sha256`.
"""


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    _configure_prior()
    package, source_proof = prior.build_directory(destination)
    injection = _inject_fresh_c0_physical_assets(package)
    runtime_changes = _patch_package_local_runtime_classification(package)
    (package / "README.md").write_text(
        _readme(), encoding="utf-8", newline="\n"
    )
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "resnet50-node0004-a-pingpong-config-fix-package-v14",
            "install_name": INSTALL_NAME,
            "classification": "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS",
            "status": "PACKAGE_READY_NOT_RUN",
            "evidence_level": "E2_LOCAL_CONFIG_FIX_PLUS_DYNAMIC_PROGRESS_DIAGNOSTICS",
            "candidate_release": False,
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
    manifest["active_receipts"]["plan_mutable_provenance_sha256"] = PLAN_SHA256
    manifest["active_receipts"]["server_package_rule_sha256"] = (
        SERVER_RULE_SHA256
    )
    for item in manifest["active_receipts"]["generation_read_receipt"]:
        if item["path"].endswith("md") and "09aa" in item["sha256"]:
            item["sha256"] = SERVER_RULE_SHA256
    manifest["configuration_fix"] = {
        "first_divergence": (
            "MSE0 producer selector stayed on buffer0 while SA inport0 "
            "consumer selector switched to unwritten buffer1 at terminal tag 4"
        ),
        "owner": "Conv signed-A local materializer",
        "leaf_changes": [
            {
                "path": "stream_engine.stream0.ping_pong",
                "old": 0,
                "new": 1,
            },
            {
                "path": "stream_engine.stream0.pingpong_last_index",
                "old": None,
                "new": 4,
            },
        ],
        "formula": (
            "stream0.ping_pong = special_array.inport0.pingpong_en; "
            "stream0.pingpong_last_index = "
            "special_array.inport0.pingpong_last_index"
        ),
        "functional_rtl_changed": False,
        "package_local_runtime_classification_files": runtime_changes,
        **injection,
    }
    manifest["superseded_diagnostic_package"] = {
        "path": SOURCE_V13_ZIP.relative_to(ROOT).as_posix(),
        "sha256": SOURCE_V13_SHA256,
        "status": "QUARANTINED_DETERMINISTIC_CONFIGURATION_ERROR",
    }
    manifest["files"] = prior.prior.base.package_records(package)
    prior.prior.base.write_json(manifest_path, manifest)
    observer_sha = manifest["observer_binding_four_way"]["source"]["sha256"]
    observer = prior.prior.base.observer_precompile_receipt(package, observer_sha)
    if not observer["valid"]:
        raise prior.prior.base.BuildError(
            f"observer XMR gate failed after C0 injection: {observer['errors']}"
        )
    return package, {
        "preflight": source_proof["preflight"],
        "observer": observer,
        "post_injection_final_zip_audit_required": True,
    }


def _repeat(package: Path, zip_path: Path) -> dict[str, Any]:
    prior.prior.base.deterministic_zip(package, zip_path)
    records = prior.prior.base.package_records(package)
    digest = prior.prior.base.sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="node0004-v14-repeat-") as temporary:
        repeat_root = Path(temporary)
        repeat_package, _ = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        prior.prior.base.deterministic_zip(repeat_package, repeat_zip)
        if records != prior.prior.base.package_records(repeat_package):
            raise prior.prior.base.BuildError("repeated package trees differ")
        if digest != prior.prior.base.sha256(repeat_zip):
            raise prior.prior.base.BuildError("repeated deterministic ZIPs differ")
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
            print(f"refusing to overwrite: {path}")
            return 1
    output.mkdir(parents=True, exist_ok=True)
    package, proof = build_directory(output)
    repeated = _repeat(package, zip_path)
    digest = prior.prior.base.sha256(zip_path)
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    receipt = {
        "schema": "node0004-a-pingpong-fix-package-validation-v14",
        "status": "PACKAGE_BUILT_PENDING_FINAL_RULE_SELF_AUDIT",
        "package": str(package),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "preflight": proof["preflight"],
        "observer": proof["observer"],
        "numeric_analysis_repeated": False,
        "node0004_workload_rebuilt": False,
        "configuration_rebuilt": True,
        "functional_rtl_modified": False,
        "server_rtl_entries": 0,
        "server_action": False,
        "repeated_build": repeated,
        "final_zip_rule_self_audit_pending": True,
    }
    prior.prior.base.write_json(validation, receipt)
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
