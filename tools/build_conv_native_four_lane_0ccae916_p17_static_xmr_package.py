#!/usr/bin/env python3
"""Build p17 with elaboration-constant Buffer5 XMR and a fresh cfg namespace."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import sys
import tempfile
import types
from pathlib import Path, PurePosixPath
from typing import Any


if "jsonschema" not in sys.modules:
    sys.modules["jsonschema"] = types.SimpleNamespace(validate=lambda *_a, **_k: None)

import build_conv_native_four_lane_0ccae916_p16_buffer5_public_package as p16


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p16_b5port"
PACKAGE_ID = "r5_n4_0cc_p17_gxmr"
OLD_INSTALL_NAME = "r5_n4_0cc_p11f_pubord"
WORKLOAD_INSTALL_NAME = PACKAGE_ID
ATTEMPT = "a0"
SOURCE_SHA256 = (
    "b9dfb0d282013e45328c905c19957523afba81d505bbf5b4600dc82ace6c3611"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
SOURCE_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p16_compile_return_analysis"
    / "report.json"
)
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p17_static_xmr"
OBSERVER = "tb_probe/native_return_observer.svh"
OLD_INPUT_PREFIX = f"install/cfg_pkg/{OLD_INSTALL_NAME}/"
INPUT_PREFIX = f"install/cfg_pkg/{WORKLOAD_INSTALL_NAME}/"
OLD_OUTPUT_PREFIX = f"install/codex_runs/{SOURCE_ID}/{ATTEMPT}/c0/d/"
OUTPUT_PREFIX = f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}/c0/d/"
P16_ANCHOR = "// Native Conv p16: public-module-port-only Buffer5 causal observer."
P17_ANCHOR = "// Native Conv p17: genvar-static public Buffer5 causal observer."
ALLOWED_CHANGED_PATHS = {
    "PREPARE_AND_RUN.sh",
    "README.md",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "TEST_PACKAGE_MANIFEST.json",
    "package_manifest.json",
    "package_tools/fixed_simresult_publisher.py",
    "package_tools/node0004_assumed_hardware_server_runtime.py",
    OBSERVER,
    "workload/runtime/runs/c0/sca_cfg.json",
    "workload/runtime/runs/c0/sca_cfg_D.json",
}
TEXT_IDENTITY_MEMBERS = (
    "PREPARE_AND_RUN.sh",
    "README.md",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "TEST_PACKAGE_MANIFEST.json",
    "package_manifest.json",
    "package_tools/fixed_simresult_publisher.py",
    "package_tools/node0004_assumed_hardware_server_runtime.py",
)
RULE_RECEIPTS = {
    ".agents/agent.md": (
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
    ),
    ".agents/plan.md": (
        "e52c64fa74ef5f87e07114f63328632c7772d869932da27ae9e1ae671ab060d9"
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
    return p16.sha256(path)


def write_json(path: Path, value: Any) -> None:
    p16.write_json(path, value)


def configure_base() -> None:
    values = {
        "SOURCE_ID": SOURCE_ID,
        "PACKAGE_ID": PACKAGE_ID,
        "SOURCE_SHA256": SOURCE_SHA256,
        "SOURCE_ZIP": SOURCE_ZIP,
        "DEFAULT_OUTPUT": DEFAULT_OUTPUT,
        "OLD_OUTPUT_PREFIX": OLD_OUTPUT_PREFIX,
        "OUTPUT_PREFIX": OUTPUT_PREFIX,
        "ALLOWED_CHANGED_PATHS": ALLOWED_CHANGED_PATHS,
        "WORKLOAD_INSTALL_NAME": WORKLOAD_INSTALL_NAME,
        "INPUT_PREFIX": INPUT_PREFIX,
    }
    for name, value in values.items():
        setattr(p16.base, name, value)


def validate_rule_receipts() -> list[dict[str, Any]]:
    result = []
    for relative, expected in RULE_RECEIPTS.items():
        path = ROOT / relative
        actual = sha256(path) if path.is_file() else None
        if actual != expected:
            raise BuildError(f"current authority receipt differs: {relative}")
        result.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": actual,
            }
        )
    return result


def replace_identities(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if SOURCE_ID not in text and OLD_INSTALL_NAME not in text:
        raise BuildError(f"identity/install anchor absent: {path}")
    text = text.replace(SOURCE_ID, PACKAGE_ID)
    text = text.replace(OLD_INSTALL_NAME, WORKLOAD_INSTALL_NAME)
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_sca_input(package: Path) -> dict[str, Any]:
    path = package / "workload/runtime/runs/c0/sca_cfg.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    changed = 0

    def walk(value: Any) -> None:
        nonlocal changed
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "path" and isinstance(child, str):
                    if not child.startswith(OLD_INPUT_PREFIX):
                        raise BuildError(f"unexpected p16 SCA input path: {child}")
                    value[key] = INPUT_PREFIX + child[len(OLD_INPUT_PREFIX) :]
                    changed += 1
                else:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(document)
    if changed != 86:
        raise BuildError(f"SCA input path count differs: {changed}")
    write_json(path, document)
    return {
        "changed_path_count": changed,
        "source_prefix": OLD_INPUT_PREFIX,
        "successor_prefix": INPUT_PREFIX,
    }


def static_monitor_preamble() -> str:
    declarations = r"""
logic [`BUFFER_BANK_NUM-1:0] n4b5_arm2buf_req_valid_mon
      [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
logic n4b5_arm2buf_req_rw_mon
      [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
logic [`BUFFER_BANK_ADDR_WIDTH-1:0] n4b5_arm2buf_req_addr_mon
      [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
logic n4b5_buf2arm_req_ready_mon
      [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
logic n4b5_arm2buf_wvalid_mon
      [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
logic [`BUFFER_BANK_NUM-1:0] n4b5_arm2buf_clear_mon
      [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
logic [`BUFFER_BANK_NUM-1:0] n4b5_mrm2buf_req_valid_mon
      [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
logic n4b5_mrm2buf_req_rw_mon
      [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
logic [`BUFFER_BANK_ADDR_WIDTH-1:0] n4b5_mrm2buf_req_addr_mon
      [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
logic [`BUFFER_BANK_NUM-1:0][`BUFFER_STRB_WIDTH-1:0]
      n4b5_mrm2buf_req_strb_mon
      [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
logic n4b5_buf2mrm_req_ready_mon
      [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];
logic [`BUFFER_BANK_NUM-1:0] n4b5_mrm2buf_clear_mon
      [0:`SLICE_GROUP_SIZE-1][0:`SLICE_GROUP_NUM-1];

generate
    for (genvar n4b5_group = 0;
         n4b5_group < `SLICE_GROUP_SIZE;
         n4b5_group++) begin : N4B5_GROUP_GEN
        for (genvar n4b5_slice = 0;
             n4b5_slice < `SLICE_GROUP_NUM;
             n4b5_slice++) begin : N4B5_SLICE_GEN
"""
    ports = (
        "arm2buf_req_valid",
        "arm2buf_req_rw",
        "arm2buf_req_addr",
        "buf2arm_req_ready",
        "arm2buf_wvalid",
        "arm2buf_clear",
        "mrm2buf_req_valid",
        "mrm2buf_req_rw",
        "mrm2buf_req_addr",
        "mrm2buf_req_strb",
        "buf2mrm_req_ready",
        "mrm2buf_clear",
    )
    assignments = []
    for port in ports:
        assignments.append(
            "            assign n4b5_"
            f"{port}_mon[n4b5_group][n4b5_slice] =\n"
            "                u_NDP_Top_new\n"
            "                    .slice_with_datahub_mc_group_gen[n4b5_group]\n"
            "                    .u_slice_with_datahub_mc_group\n"
            "                    .slice_group_gen[n4b5_slice]\n"
            "                    .u_slice_wrapper.u_Slice.u_LSU\n"
            "                    .u_Buffer_Manager_Cluster.BUFFER_MANAGER[5]\n"
            f"                    .u_Buffer_Manager.u_Buffer.{port};\n"
        )
    return (
        declarations
        + "".join(assignments)
        + "        end\n"
        + "    end\n"
        + "endgenerate\n\n"
    )


def make_static_append() -> tuple[str, dict[str, int]]:
    source = p16.OBSERVER_APPEND.lstrip()
    if source.count(P16_ANCHOR) != 1:
        raise BuildError("p16 append anchor differs")
    pattern = re.compile(
        r"u_NDP_Top_new"
        r"\.slice_with_datahub_mc_group_gen\[n4d_group_id\]\s*"
        r"\.u_slice_with_datahub_mc_group\s*"
        r"\.slice_group_gen\[n4d_local_slice_id\]\s*"
        r"\.u_slice_wrapper\.u_Slice\.u_LSU"
        r"\.u_Buffer_Manager_Cluster\s*"
        r"\.BUFFER_MANAGER\[5\]\.u_Buffer_Manager\.u_Buffer"
        r"\.([A-Za-z0-9_]+)",
        flags=re.MULTILINE,
    )
    ports: list[str] = []

    def replace(match: re.Match[str]) -> str:
        port = match.group(1)
        ports.append(port)
        return (
            f"n4b5_{port}_mon"
            "[n4d_group_id][n4d_local_slice_id]"
        )

    transformed = pattern.sub(replace, source)
    if (
        len(ports) != 34
        or len(set(ports)) != 12
        or "slice_with_datahub_mc_group_gen[n4d_group_id]" in transformed
        or "slice_group_gen[n4d_local_slice_id]" in transformed
    ):
        raise BuildError("p16 dynamic hierarchy replacement closure differs")
    transformed = transformed.replace(P16_ANCHOR, P17_ANCHOR, 1)
    comment_end = (
        "// This append reads ports of Buffer u_Buffer and never reads private state.\n"
    )
    if transformed.count(comment_end) != 1:
        raise BuildError("p17 observer comment insertion anchor differs")
    transformed = transformed.replace(
        comment_end,
        comment_end
        + "// Hierarchy is selected only by enclosing genvars; procedural code "
        + "indexes local monitor arrays.\n"
        + static_monitor_preamble(),
        1,
    )
    return transformed, {
        "replaced_dynamic_hierarchy_references": len(ports),
        "unique_public_ports": len(set(ports)),
        "static_continuous_assignments": 12,
    }


def patch_observer(package: Path) -> dict[str, Any]:
    path = package / OBSERVER
    source = path.read_text(encoding="utf-8")
    if source.count(P16_ANCHOR) != 1:
        raise BuildError("exact p16 observer anchor differs")
    baseline, source_append = source.split(P16_ANCHOR, 1)
    source_append = P16_ANCHOR + source_append
    if source_append.strip() != p16.OBSERVER_APPEND.strip():
        raise BuildError("exact p16 observer append bytes/semantics differ")
    append, counts = make_static_append()
    path.write_text(
        baseline.rstrip() + "\n" + append.lstrip(),
        encoding="utf-8",
        newline="\n",
    )
    final = path.read_text(encoding="utf-8")
    if (
        final.count(P17_ANCHOR) != 1
        or final.count("begin : N4B5_GROUP_GEN") != 1
        or final.count("begin : N4B5_SLICE_GEN") != 1
        or "slice_with_datahub_mc_group_gen[n4d_group_id]" in final
        or "slice_group_gen[n4d_local_slice_id]" in final
    ):
        raise BuildError("p17 exact observer static-XMR closure failed")
    return {
        "source_p16_observer_sha256": hashlib.sha256(
            source.encode()
        ).hexdigest(),
        "p17_append_sha256": hashlib.sha256(append.encode()).hexdigest(),
        "final_sha256": sha256(path),
        "final_size_bytes": path.stat().st_size,
        **counts,
    }


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["package_id"] = PACKAGE_ID
    contract["install_name"] = WORKLOAD_INSTALL_NAME
    contract["claim_boundary"] = (
        "p17 package-local genvar-static public Buffer5 c0 causal observer, "
        "fresh install/cfg namespace, actual compile identity and fixed return "
        "only; no numeric, terminal, formal-D, E3, E4 or E5 claim."
    )
    paths = p16.base.projected_paths(package, contract)
    longest = max(paths, key=lambda value: (len(value), value))
    contract["path_budget"]["max_projected_absolute_path_chars"] = (
        p16.base.SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
    )
    write_json(path, contract)
    return contract


def patch_pointer_readme(package: Path) -> None:
    pointer_path = package / "TEST_PACKAGE_MANIFEST.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer.update(
        {
            "schema": "conv-native-four-lane-p17-genvar-xmr-pointer-v1",
            "package_identity": PACKAGE_ID,
            "status": "PACKAGE_READY_NOT_RUN",
        }
    )
    write_json(pointer_path, pointer)
    (package / "README.md").write_text(
        "# Native four-lane Conv p17 genvar-XMR successor\n\n"
        "This fresh diagnostic successor fixes the production VCS p16 XMRE. "
        "Every Buffer5 hierarchy reference is selected in a genvar generate "
        "block; procedural code reads only local monitor arrays. It also uses "
        f"the fresh install namespace `{WORKLOAD_INSTALL_NAME}` so preserved "
        "p11f/p16 server directories do not collide.\n\n"
        "Run after extraction:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n"
        "```\n\n"
        f"Expected return: `/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip` "
        "and its `.sha256` sidecar. This remains a c0 diagnostic and does not "
        "claim natural terminal, formal 320D, performance, E3, E4 or E5.\n",
        encoding="utf-8",
        newline="\n",
    )


def patch_manifest(
    package: Path,
    contract: dict[str, Any],
    observer: dict[str, Any],
    sca_input: dict[str, Any],
    receipts: list[dict[str, Any]],
) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": (
                "conv-native-four-lane-0ccae916-p17-genvar-xmr-package-v1"
            ),
            "package_identity": PACKAGE_ID,
            "install_name": WORKLOAD_INSTALL_NAME,
            "workload_install_name": WORKLOAD_INSTALL_NAME,
            "run_namespace": (
                f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}"
            ),
            "return_name": f"{PACKAGE_ID}_return.zip",
            "status": "PACKAGE_READY_NOT_RUN",
            "candidate_release": False,
            "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
            "rule_receipts": receipts,
            "rule_receipts_current_match": True,
        }
    )
    manifest["source_p16_compile_return_analysis"] = {
        "path": SOURCE_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": sha256(SOURCE_ANALYSIS),
        "classification": (
            "PACKAGE_LOCAL_OBSERVER_DYNAMIC_GENERATE_XMR_COMPILE_FAILURE"
        ),
        "compile_exit_status": 2,
        "simulation_started": False,
    }
    manifest["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": (
            "replace runtime-indexed hierarchical generate selection with "
            "genvar-static monitor assignments and allocate a fresh cfg root"
        ),
        "rule_ids": [
            "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
            "CDA-SERVER-PACKAGE-LOCAL-OBSERVER-HDL-SYNTAX-SCOPE-POSITIVE-001",
            "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
            "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
            "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
        ],
    }
    manifest["observer_binding"].update(
        {
            "source": OBSERVER,
            "source_sha256": observer["final_sha256"],
            "sha256": observer["final_sha256"],
            "size_bytes": observer["final_size_bytes"],
            "p17_append_sha256": observer["p17_append_sha256"],
            "runtime_indexed_instance_paths": 0,
            "genvar_static_public_port_assignments": 12,
            "procedural_monitor_array_indexing": True,
            "private_state_xmr_added_by_p17": False,
            "runtime_enable_p17": "+N4B5_PUBLIC_CAUSAL",
            "p17_feature_marker": "N4B5_FEATURE_ENABLE_V1",
        }
    )
    manifest["fresh_install_namespace"] = {
        "source_install_name": OLD_INSTALL_NAME,
        "successor_install_name": WORKLOAD_INSTALL_NAME,
        "source_sibling_may_exist": True,
        "overwrite_or_delete_source_sibling": False,
        "sca_input_path_rebind": sca_input,
    }
    manifest["ndp_root_toplevel_contract"]["runtime_write_targets"] = [
        f"install/cfg_pkg/{WORKLOAD_INSTALL_NAME}",
        f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}",
    ]
    manifest["ndp_root_toplevel_contract"][
        "manual_server_mkdir_required"
    ] = False
    manifest["release_gate_applicability"].update(
        {
            "package_local_hdl": (
                "blocking_applicable_genvar_static_observer_fix"
            ),
            "materialized_config": (
                "blocking_applicable_mechanical_install_prefix_only"
            ),
            "diagnostic_predicate_trace": (
                "receipt_reuse_predicate_byte_equal_monitor_source_rebind"
            ),
        }
    )
    manifest["release_gate_matrix"]["package_local_hdl"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": True,
        "scope": (
            "exact final observer p17 append: declarations, 12 genvar-static "
            "public Buffer5 assignments, procedural local-array consumers"
        ),
    }
    manifest["release_gate_matrix"]["materialized_config"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": True,
        "scope": (
            "SCA input install-prefix and SCA_D package-run-prefix mechanical "
            "rebind only; matrix/bitstream payload bytes frozen"
        ),
        "causal_transaction_ledger": "receipt_reuse_semantics_byte_equal",
        "boundary_microtrace": "not_applicable_path_prefix_only",
        "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
    }
    paths = p16.base.projected_paths(package, contract)
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
                p16.base.SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
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
    manifest["files"] = p16.base.file_records(package)
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
                "install_name",
                "observer",
                "runner_identity",
                "sca_path_binding",
                "return_identity",
                "storage",
            ],
            "required_validator_gates": [
                "core_identity_bootstrap",
                "package_local_hdl",
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
    if not SOURCE_ANALYSIS.is_file():
        raise BuildError("formal p16 compile return analysis is absent")
    if not SOURCE_ZIP.is_file() or sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p16 source ZIP differs")
    receipts = validate_rule_receipts()
    package = p16.base.safe_extract_source(destination)
    for relative in TEXT_IDENTITY_MEMBERS:
        replace_identities(package / relative)
    sca_input = patch_sca_input(package)
    p16.base.patch_sca_d(package)
    observer = patch_observer(package)
    contract = patch_contract(package)
    patch_pointer_readme(package)
    patch_manifest(package, contract, observer, sca_input, receipts)
    return package, {
        "observer": observer,
        "sca_input": sca_input,
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
        raise BuildError("refusing to overwrite a p17 build target")
    build_profile(output)
    package, receipts = build_directory(output)
    zip_path = output / f"{PACKAGE_ID}.zip"
    p16.base.deterministic_zip(package, zip_path)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix=".p17_repeat_", dir=ROOT) as temp:
        repeat_root = Path(temp)
        repeat, _ = build_directory(repeat_root)
        repeat_zip = repeat_root / f"{PACKAGE_ID}.zip"
        p16.base.deterministic_zip(repeat, repeat_zip)
        deterministic = sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("p17 deterministic double build differs")
    sidecar = output / f"{PACKAGE_ID}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    report = {
        "schema": "conv-native-four-lane-p17-genvar-xmr-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "workload_install_name": WORKLOAD_INSTALL_NAME,
        "source_p16_zip_sha256": SOURCE_SHA256,
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "deterministic_double_build": deterministic,
        "changed_paths": sorted(ALLOWED_CHANGED_PATHS),
        "observer_receipt": receipts["observer"],
        "sca_input_receipt": receipts["sca_input"],
        "functional_rtl_modified": False,
        "numeric_w3_golden_mapping_bitstream_execplan_timeout_changed": False,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
