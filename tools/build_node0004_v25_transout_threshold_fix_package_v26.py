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


SOURCE_NAME = "r5_n4_hw_v25_terminal_match_diag"
INSTALL_NAME = "r5_n4_hw_v26_transout_threshold_fix"
SOURCE_ZIP_SHA256 = (
    "e4aaf762a3b434a78dfc4af276b48405f84b6dbaee1dad224282ac7b14fb1eab"
)
BOUND_RETURN_SHA256 = (
    "e6b35bc2f311b9cdf184c65bdd6f8ad834ededf6888ffb390943b83d87d1ac5f"
)
SERVER_RULE_SHA256 = (
    "5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48"
)
INDEX_SHA256 = (
    "db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5"
)
AGENT_SHA256 = (
    "d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721"
)
INT8_SA_SHA256 = (
    "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
)
README_SHA256 = (
    "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7"
)
PLAN_MUTABLE_SHA256 = (
    "c319da9ca373c0a8f72702cd57cd61d651e5de73af7a5a03f88ddab0f5040eed"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / f"{SOURCE_NAME}.zip"
)
FRESH_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-transout-threshold-fix-c0-v5"
)
FRESH_CONFIG = (
    ROOT
    / "configs/native_ndp_sim/node0004_transout_threshold_fix_c0_v5/"
    "accumulate_waves/wave-0.json"
)
OUTPUT_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)


def _safe_extract_source(destination: Path) -> Path:
    if base.sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise base.BuildError("v25 source ZIP SHA differs")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise base.BuildError("v25 source ZIP CRC failed")
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
                raise base.BuildError(
                    f"unsafe/duplicate v25 ZIP member: {info.filename}"
                )
            names.add(info.filename)
            roots.add(path.parts[0])
        if roots != {SOURCE_NAME}:
            raise base.BuildError(
                f"v25 source ZIP root differs: {sorted(roots)}"
            )
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
        raise base.BuildError("fresh transout-threshold rebuild report missing")
    report = json.loads(local_report.read_text(encoding="utf-8"))
    if (
        report.get("status") != "LOCAL_C0_PHYSICAL_REBUILD_PASS"
        or report.get("old_ignored_occurrences") != 256
        or report.get("new_released_occurrences") != 256
    ):
        raise base.BuildError("fresh terminal release proof differs")
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
    return f"""# node0004 v26 transout terminal-threshold config fix

Classification: `CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`.

The v25 formal return recorded 256 qualified A/B terminal accepts with
`all_matched=1` and pipeline enable:

- accepted last-index 5: 192 occurrences;
- accepted last-index 4: 64 occurrences.

The materialized `special_array.transout_last_index=2` made all 256 satisfy
the active RTL `ignore` predicate. None could set matched/out, terminal ALU
tag, PE output or Buffer5 write. This package changes exactly one logical
leaf:

```text
special_array.transout_last_index: 2 -> 5
```

With threshold 5, index 5 is `matched` and index 4 is `out`; both release the
existing outbuffer slot. Mapping, bitstream, execplan and SCA were freshly
regenerated. Numeric inputs, W3, qparams, tail, matrices, golden/readback,
functional RTL and the existing low-cost qualified diagnostics are unchanged.

Server command:

```bash
bash {INSTALL_NAME}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy
```

Expected return: `{INSTALL_NAME}_return.zip`.
"""


def build_directory(output: Path) -> Path:
    package = output / INSTALL_NAME
    if package.exists():
        raise base.BuildError(f"refusing to overwrite: {package}")
    with tempfile.TemporaryDirectory(prefix="node0004-v26-source-") as temp:
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
            "schema": (
                "resnet50-node0004-transout-threshold-config-fix-package-v26"
            ),
            "install_name": INSTALL_NAME,
            "classification": (
                "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
            ),
            "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
            "candidate_release": False,
            "evidence_level": (
                "E2_LOCAL_CONFIG_FIX_PLUS_QUALIFIED_PROGRESS_DIAGNOSTICS"
            ),
            "numeric_analysis_repeated": False,
            "node0004_workload_rebuilt": False,
            "configuration_rebuilt": True,
            "configuration_rebuilt_in_this_successor": True,
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
    current = {
        ".agents/rules/生成前必读索引.md": INDEX_SHA256,
        ".agents/rules/服务器测试包生成规则.md": SERVER_RULE_SHA256,
        ".agents/rules/INT8_SA点积专项规则.md": INT8_SA_SHA256,
        "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": README_SHA256,
    }
    for item in receipts["generation_read_receipt"]:
        if item["path"] in current:
            item["sha256"] = current[item["path"]]
    rules = receipts["rules"]
    for rule in (
        "CDA-SERVER-PACKAGE-OR-RETURN-OWNER-COMPLETION-NOTIFY-RULE-FEEDBACK-001",
        "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
    ):
        if rule not in rules:
            rules.append(rule)
    receipts["agent_sha256"] = AGENT_SHA256

    manifest["v25_return_adjudication"] = {
        "bound_return_sha256": BOUND_RETURN_SHA256,
        "status": "CONFIG_TRANSOUT_THRESHOLD_TOO_LOW",
        "last_proven_good": (
            "QUALIFIED_A_B_TERMINAL_ACCEPT_WITH_ALL_OPERANDS_MATCHED"
        ),
        "first_divergence": (
            "ACCEPTED_TERMINAL_INDEX_TO_TRANSOUT_THRESHOLD_CLASSIFICATION"
        ),
        "root_cause": (
            "all 256 accepted terminal indices 4/5 exceeded configured "
            "transout_last_index 2 and were classified ignore"
        ),
    }
    manifest["configuration_fix"] = {
        "owner": "Conv/SA integration owner",
        "leaf_changes": [
            {
                "path": "special_array.transout_last_index",
                "old": 2,
                "new": 5,
            }
        ],
        "formula": "max accepted A/B terminal last_index",
        "old_counterexample": {
            "index5_occurrences": 192,
            "index4_occurrences": 64,
            "old_ignored_occurrences": 256,
            "new_released_occurrences": 256,
        },
        "functional_rtl_changed": False,
        **injection,
    }
    manifest["superseded_v25_diagnostic"] = {
        "path": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            f"{SOURCE_NAME}.zip"
        ),
        "sha256": SOURCE_ZIP_SHA256,
        "status": "CONSUMED_RETURN_SUPERSEDED_BY_CONFIG_FIX",
    }
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
    observer_sha = base.sha256(
        package / "tb_probe/native_return_observer.svh"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["observer_sha256"] = observer_sha
    manifest["observer_binding_four_way"]["source"]["sha256"] = observer_sha
    manifest["files"] = base.package_records(package)
    base.write_json(manifest_path, manifest)
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
    with tempfile.TemporaryDirectory(prefix="node0004-v26-repeat-") as temp:
        repeat_root = Path(temp)
        repeat_package = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{INSTALL_NAME}.zip"
        base.deterministic_zip(repeat_package, repeat_zip)
        repeated = base.sha256(repeat_zip) == digest
    if not repeated:
        raise base.BuildError("v26 deterministic rebuild differs")
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    report: dict[str, Any] = {
        "schema": "node0004-transout-threshold-fix-build-v26",
        "status": "PACKAGE_BUILT_PENDING_FINAL_ZIP_RULE_SELF_AUDIT",
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "deterministic_rebuild_equal": repeated,
        "source_v25_sha256": SOURCE_ZIP_SHA256,
        "bound_v25_return_sha256": BOUND_RETURN_SHA256,
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
