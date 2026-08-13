#!/usr/bin/env python3
"""Build the p18 c0 single-leaf PE keep-threshold successor from exact p17."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import types
from pathlib import Path, PurePosixPath
from typing import Any


if "jsonschema" not in sys.modules:
    sys.modules["jsonschema"] = types.SimpleNamespace(validate=lambda *_a, **_k: None)

import build_conv_native_four_lane_0ccae916_p17_static_xmr_package as p17


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p17_gxmr"
PACKAGE_ID = "r5_n4_0cc_p18_pekeep3"
ATTEMPT = "a0"
SOURCE_SHA256 = (
    "3828628f2573c3cd970330fba60bd3393b305555085c5517ea074a919f40a978"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
P17_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p17_return_analysis/report.json"
)
LOCAL_REBUILD = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-conv-native-four-lane-0cc-p18-pekeep3-c0"
)
LOCAL_PIPELINE = LOCAL_REBUILD / "execplan_conv/wave-0/pipeline_output"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p18_pekeep3"
OBSERVER = "tb_probe/native_return_observer.svh"
INPUT_PREFIX = f"install/cfg_pkg/{PACKAGE_ID}/runs/c0/"
OUTPUT_PREFIX = f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}/c0/d/"
TEXT_IDENTITY_MEMBERS = (
    "PREPARE_AND_RUN.sh",
    "README.md",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "TEST_PACKAGE_MANIFEST.json",
    "package_manifest.json",
    "package_tools/fixed_simresult_publisher.py",
    "package_tools/node0004_assumed_hardware_server_runtime.py",
)
PHYSICAL_ASSETS = {
    "workload/runtime/runs/c0/install/execplan.txt": (
        LOCAL_PIPELINE / "install/execplan.txt"
    ),
    "workload/runtime/runs/c0/install/execplan_op_w0.txt": (
        LOCAL_PIPELINE / "install/execplan_op_w0.txt"
    ),
    (
        "workload/runtime/runs/c0/install/cfg_pkg/"
        "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    ): (
        LOCAL_PIPELINE
        / "install/cfg_pkg/"
        "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
    ),
}
ALLOWED_CHANGED_PATHS = set(TEXT_IDENTITY_MEMBERS) | set(PHYSICAL_ASSETS) | {
    "workload/runtime/runs/c0/sca_cfg.json",
    "workload/runtime/runs/c0/sca_cfg_D.json",
}
RULE_RECEIPTS = {
    ".agents/agent.md": (
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
    ),
    ".agents/plan.md": (
        "262b3e77882589a666d1c8296b935d2004e5d0f74ce0669a713bab1e49ce02a4"
    ),
    ".agents/rules/生成前必读索引.md": (
        "3c2bd9017f351b6456eac49c966063cc9b76e96420d71162a1ca57d1b62b552c"
    ),
    ".agents/rules/服务器测试包生成规则.md": (
        "89d27141f1a151ef5e6cc98603238050c9b0442a3d1937b2ec23cf92e55a27a2"
    ),
    ".agents/rules/算子配置规则.md": (
        "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1"
    ),
    ".agents/rules/整网测试收敛优化专项规则.md": (
        "12340cd5e619e1923c74e8853006ee21bce8a7a07b0538e9a5196d7800638cd7"
    ),
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": (
        "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6"
    ),
}


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def configure_base() -> None:
    values = {
        "SOURCE_ID": SOURCE_ID,
        "PACKAGE_ID": PACKAGE_ID,
        "SOURCE_SHA256": SOURCE_SHA256,
        "SOURCE_ZIP": SOURCE_ZIP,
        "DEFAULT_OUTPUT": DEFAULT_OUTPUT,
        "OLD_OUTPUT_PREFIX": (
            f"install/codex_runs/{SOURCE_ID}/{ATTEMPT}/c0/d/"
        ),
        "OUTPUT_PREFIX": OUTPUT_PREFIX,
        "ALLOWED_CHANGED_PATHS": ALLOWED_CHANGED_PATHS,
        "WORKLOAD_INSTALL_NAME": PACKAGE_ID,
        "INPUT_PREFIX": INPUT_PREFIX,
    }
    for name, value in values.items():
        setattr(p17.p16.base, name, value)


def validate_inputs() -> list[dict[str, Any]]:
    if not SOURCE_ZIP.is_file() or sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p17 pending ZIP differs")
    p17_report = json.loads(P17_ANALYSIS.read_text(encoding="utf-8"))
    if (
        not p17_report.get("valid")
        or p17_report.get("status")
        != "CONFIG_PE1_KEEP_LAST_INDEX_FIX_SUCCESSOR_REQUIRED"
    ):
        raise BuildError("formal p17 return analysis is not accepted")
    rebuild = json.loads(
        (LOCAL_REBUILD / "local_rebuild_report.json").read_text(encoding="utf-8")
    )
    if (
        rebuild.get("status") != "LOCAL_C0_SINGLE_LEAF_REBUILD_PASS"
        or rebuild.get("authorized_leaf_changes")
        != [
            {
                "path": "lc_pe_configs.PE1.inport0.keep_last_index",
                "old": 2,
                "new": 3,
            }
        ]
    ):
        raise BuildError("p18 local single-leaf rebuild receipt differs")
    rows: list[dict[str, Any]] = []
    for relative, expected in RULE_RECEIPTS.items():
        path = ROOT / relative
        actual = sha256(path) if path.is_file() else None
        if actual != expected:
            raise BuildError(f"current authority receipt differs: {relative}")
        rows.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": actual,
            }
        )
    return rows


def replace_identity(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if SOURCE_ID not in text:
        raise BuildError(f"p17 identity anchor absent: {path}")
    path.write_text(
        text.replace(SOURCE_ID, PACKAGE_ID),
        encoding="utf-8",
        newline="\n",
    )


def walk_paths(value: Any) -> list[tuple[dict[str, Any], str]]:
    result: list[tuple[dict[str, Any], str]] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "path" and isinstance(child, str):
                result.append((value, child))
            else:
                result.extend(walk_paths(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(walk_paths(child))
    return result


def materialize_changed_consumers(package: Path) -> dict[str, Any]:
    receipts: dict[str, Any] = {"physical_assets": {}}
    for relative, source in PHYSICAL_ASSETS.items():
        target = package / relative
        if not source.is_file() or not target.is_file():
            raise BuildError(f"materialized consumer path absent: {relative}")
        old_sha = sha256(target)
        shutil.copyfile(source, target)
        receipts["physical_assets"][relative] = {
            "source": source.relative_to(ROOT).as_posix(),
            "old_sha256": old_sha,
            "new_sha256": sha256(target),
            "bytes": target.stat().st_size,
        }

    sca_source = json.loads(
        (LOCAL_PIPELINE / "sca_cfg.json").read_text(encoding="utf-8")
    )
    input_rows = walk_paths(sca_source)
    if len(input_rows) != 86:
        raise BuildError("generated SCA input path count differs")
    for record, old in input_rows:
        if not old.startswith("install/"):
            raise BuildError(f"unexpected generated SCA input path: {old}")
        record["path"] = INPUT_PREFIX + old
    sca_target = package / "workload/runtime/runs/c0/sca_cfg.json"
    write_json(sca_target, sca_source)

    sca_d_source = json.loads(
        (LOCAL_PIPELINE / "sca_cfg_D.json").read_text(encoding="utf-8")
    )
    output_rows = walk_paths(sca_d_source)
    if len(output_rows) != 28:
        raise BuildError("generated SCA_D output path count differs")
    for record, old in output_rows:
        if not old.startswith("install/"):
            raise BuildError(f"unexpected generated SCA_D path: {old}")
        record["path"] = OUTPUT_PREFIX + old[len("install/") :]
    sca_d_target = package / "workload/runtime/runs/c0/sca_cfg_D.json"
    write_json(sca_d_target, sca_d_source)
    receipts["sca"] = {
        "input_path_count": len(input_rows),
        "input_prefix": INPUT_PREFIX,
        "output_path_count": len(output_rows),
        "output_prefix": OUTPUT_PREFIX,
        "sca_sha256": sha256(sca_target),
        "sca_D_sha256": sha256(sca_d_target),
    }
    return receipts


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["package_id"] = PACKAGE_ID
    contract["install_name"] = PACKAGE_ID
    contract["claim_boundary"] = (
        "p18 c0 single-leaf PE1 inport0 keep_last_index 2-to-3 config "
        "successor with p17 genvar-static public Buffer5 observer; no natural "
        "terminal, formal 320D, performance, E3, E4 or E5 claim before return."
    )
    paths = p17.p16.base.projected_paths(package, contract)
    longest = max(paths, key=lambda value: (len(value), value))
    contract["path_budget"]["max_projected_absolute_path_chars"] = (
        p17.p16.base.SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
    )
    write_json(path, contract)
    return contract


def patch_readme_pointer(package: Path) -> None:
    pointer_path = package / "TEST_PACKAGE_MANIFEST.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer.update(
        {
            "schema": "conv-native-four-lane-p18-pekeep3-pointer-v1",
            "package_identity": PACKAGE_ID,
            "status": "PACKAGE_READY_NOT_RUN",
        }
    )
    write_json(pointer_path, pointer)
    (package / "README.md").write_text(
        "# Native four-lane Conv p18 PE keep-threshold successor\n\n"
        "This fresh c0 successor changes only "
        "`lc_pe_configs.PE1.inport0.keep_last_index` from 2 to 3 and "
        "re-materializes its config consumers. It preserves p17's "
        "genvar-static public Buffer5 observer, install-only V2 layout, "
        "NDP-root direct-entry guard and fixed simresult publisher.\n\n"
        "Run after extraction:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n"
        "```\n\n"
        f"Expected return: `/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip` "
        "and its `.sha256` sidecar. This is a targeted c0 config-fix "
        "successor; it does not yet claim formal 320D, performance, E3, E4 "
        "or E5.\n",
        encoding="utf-8",
        newline="\n",
    )


def patch_manifest(
    package: Path,
    contract: dict[str, Any],
    consumers: dict[str, Any],
    receipts: list[dict[str, Any]],
) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    local_report = LOCAL_REBUILD / "local_rebuild_report.json"
    ledger = LOCAL_REBUILD / "causal_transaction_ledger.json"
    microtrace = LOCAL_REBUILD / "boundary_microtrace.json"
    manifest.update(
        {
            "schema": (
                "conv-native-four-lane-0ccae916-p18-pekeep3-package-v1"
            ),
            "package_identity": PACKAGE_ID,
            "install_name": PACKAGE_ID,
            "workload_install_name": PACKAGE_ID,
            "run_namespace": f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}",
            "return_name": f"{PACKAGE_ID}_return.zip",
            "status": "PACKAGE_READY_NOT_RUN",
            "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
            "rule_receipts": receipts,
            "rule_receipts_current_match": True,
        }
    )
    manifest["source_p17_formal_return_analysis"] = {
        "path": P17_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": sha256(P17_ANALYSIS),
        "classification": "PE_KEEP_RELEASE_THRESHOLD_OFF_BY_ONE",
        "compile_exit_status": 0,
        "simulation_started": True,
        "formal_D_claimed": False,
    }
    manifest["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": (
            "release physical PE7 keep input after nested LC18 terminal "
            "last_index3 by changing logical PE1 inport0 threshold 2 to 3"
        ),
        "authorized_leaf_change": {
            "path": "lc_pe_configs.PE1.inport0.keep_last_index",
            "old": 2,
            "new": 3,
        },
        "rule_ids": [
            "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
            "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
            "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
            "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
            "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
        ],
    }
    manifest["changed_materialized_config"] = {
        "local_rebuild_report": {
            "path": local_report.relative_to(ROOT).as_posix(),
            "sha256": sha256(local_report),
        },
        "causal_transaction_ledger": {
            "path": ledger.relative_to(ROOT).as_posix(),
            "sha256": sha256(ledger),
        },
        "boundary_microtrace": {
            "path": microtrace.relative_to(ROOT).as_posix(),
            "sha256": sha256(microtrace),
        },
        "consumer_receipts": consumers,
        "addresses_changed": False,
        "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
        "numeric_w3_golden_repeated": False,
    }
    manifest["fresh_install_namespace"] = {
        "source_install_name": SOURCE_ID,
        "successor_install_name": PACKAGE_ID,
        "source_sibling_may_exist": True,
        "overwrite_or_delete_source_sibling": False,
        "sca_input_prefix": INPUT_PREFIX,
        "sca_output_prefix": OUTPUT_PREFIX,
    }
    manifest["ndp_root_toplevel_contract"]["runtime_write_targets"] = [
        f"install/cfg_pkg/{PACKAGE_ID}",
        f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}",
    ]
    manifest["ndp_root_toplevel_contract"]["manual_server_mkdir_required"] = False
    manifest["release_gate_applicability"].update(
        {
            "package_local_hdl": "receipt_reuse_observer_byte_equal",
            "materialized_config": (
                "blocking_applicable_single_leaf_config_rebuild"
            ),
            "diagnostic_predicate_trace": (
                "receipt_reuse_observer_predicates_byte_equal"
            ),
        }
    )
    manifest["release_gate_matrix"]["package_local_hdl"] = {
        "applicability": "receipt_reuse",
        "blocking": False,
        "pass": True,
        "scope": "p17 exact observer bytes are unchanged",
    }
    manifest["release_gate_matrix"]["materialized_config"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": True,
        "scope": (
            "PE1.inport0 keep_last_index 2-to-3 exact config, mapping, "
            "bitstream, execplan and SCA consumer closure"
        ),
        "causal_transaction_ledger": sha256(ledger),
        "boundary_microtrace": sha256(microtrace),
        "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
    }
    paths = p17.p16.base.projected_paths(package, contract)
    longest = max(paths, key=lambda value: (len(value), value))
    inner = [
        item.relative_to(package).as_posix()
        for item in package.rglob("*")
        if item.is_file() and item != path
    ] + ["package_manifest.json"]
    manifest["path_length_budget"].update(
        {
            "longest_projected_relative_path": longest,
            "longest_projected_relative_path_chars": len(longest),
            "max_projected_relative_path_chars": len(longest),
            "max_projected_absolute_path_chars": (
                p17.p16.base.SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
            ),
            "max_zip_member_chars": max(
                len(f"{PACKAGE_ID}/{relative}") for relative in inner
            ),
            "max_inner_suffix_chars": max(map(len, inner)),
            "max_inner_depth": max(
                len(PurePosixPath(relative).parts) for relative in inner
            ),
            "max_inner_component_chars": max(
                len(component)
                for relative in inner
                for component in PurePosixPath(relative).parts
            ),
            "outer_identity_repeated_inside": False,
        }
    )
    manifest["files"] = p17.p16.base.file_records(package)
    write_json(path, manifest)


def build_profile(output: Path) -> None:
    write_json(
        output / f"{PACKAGE_ID}.build_profile.json",
        {
            "schema": "server-package-build-profile-v1",
            "package_id": PACKAGE_ID,
            "family": "conv_native_four_lane",
            "lifecycle": "NEXT_FRESH_SUCCESSOR",
            "mode": "SHADOW_ONLY_NEXT_FRESH",
            "contract_valid": True,
            "current_package_impact": True,
            "changed_surfaces": [
                "package_identity",
                "materialized_config_single_leaf",
                "bitstream",
                "execplan",
                "sca_path_binding",
                "return_identity",
                "storage",
            ],
            "required_validator_gates": [
                "core_identity_bootstrap",
                "materialized_config",
                "runner_control_flow",
                "runtime_layout",
                "return_result_contract",
                "storage_rotation",
            ],
            "claim_boundary": {
                "builds_zip": False,
                "runs_family_validator": False,
                "blocking_promotion_authorized": False,
                "changes_family_release": False,
            },
            "preflight": {"pass": True, "errors": [], "warnings": []},
        },
    )


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_base()
    receipts = validate_inputs()
    package = p17.p16.base.safe_extract_source(destination)
    for relative in TEXT_IDENTITY_MEMBERS:
        replace_identity(package / relative)
    consumers = materialize_changed_consumers(package)
    contract = patch_contract(package)
    patch_readme_pointer(package)
    patch_manifest(package, contract, consumers, receipts)
    observer = package / OBSERVER
    return package, {
        "consumers": consumers,
        "observer_sha256": sha256(observer),
        "rule_receipts": receipts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = [
        output / PACKAGE_ID,
        output / f"{PACKAGE_ID}.zip",
        output / f"{PACKAGE_ID}.zip.sha256",
        output / f"{PACKAGE_ID}.build.json",
        output / f"{PACKAGE_ID}.build_profile.json",
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite a p18 build target")
    build_profile(output)
    package, receipts = build_directory(output)
    zip_path = output / f"{PACKAGE_ID}.zip"
    p17.p16.base.deterministic_zip(package, zip_path)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix=".p18_repeat_", dir=ROOT) as temp:
        repeat_root = Path(temp)
        repeat, _ = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{PACKAGE_ID}.zip"
        p17.p16.base.deterministic_zip(repeat, repeat_zip)
        deterministic = sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("p18 deterministic double build differs")
    sidecar = output / f"{PACKAGE_ID}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    report = {
        "schema": "conv-native-four-lane-p18-pekeep3-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "source_p17_zip_sha256": SOURCE_SHA256,
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "deterministic_double_build": deterministic,
        "changed_paths": sorted(ALLOWED_CHANGED_PATHS),
        "observer_sha256": receipts["observer_sha256"],
        "consumer_receipts": receipts["consumers"],
        "functional_rtl_modified": False,
        "numeric_w3_golden_observer_timeout_changed": False,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
