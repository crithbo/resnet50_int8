#!/usr/bin/env python3
"""Build the p8f full-chain/320D successor from the immutable p4 payload."""

from __future__ import annotations

import argparse
import filecmp
import hashlib
import json
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
SOURCE_NAME = "r5_n4_df23e4d_p4"
INSTALL_NAME = "r5_n4_0cc_p8f"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = (
    "c8d42f979b07468e869d077755f987c09c04d017cd1bc6ab50a71a8ee1d0204e"
)
P7_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p7_return_analysis/report.json"
)
CLOUD_AUDIT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_cloud_causal_cone/report.json"
)
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
LOCAL_PROVENANCE_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
SERVER_ROOT_BUDGET_CHARS = 96
ABSOLUTE_PATH_LIMIT_CHARS = 240
RULE_PATHS = [
    ".agents/agent.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
]
LOCAL_LEAVES = {
    "Array_Request_Manager.sv": (
        "d3f100b2a1415ff561791ccafd157b038c4d8e80a80bf18dcedb89c1fec7c4eb"
    ),
    "Buffer_AG_Idx_Queue.sv": (
        "b5fc30fa970a4ed38ebdfaf825946a80562ded91d72c600dd1ee89d14103b1ef"
    ),
    "RD_Data_Channel.sv": (
        "6c612cdd0eb907678a4825215553fd4a1b1b79869b1314fafba9b0e8c072f60e"
    ),
    "Neighbor_Out_AG.sv": (
        "05a6b1eadd2d5fb125a6a9e6b01b03dbbf9cd1bddc32423c01b5b6651cced41e"
    ),
    "SA_PE_Float_CSA.v": (
        "72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3"
    ),
    "SA_PE_Float_Control.v": (
        "00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb"
    ),
    "SA_PE_Mul_Array.v": (
        "135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a"
    ),
    "SA_ALU.v": (
        "c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06"
    ),
}


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BuildError(f"JSON root must be object: {path}")
    return value


def records(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative == "package_manifest.json":
            continue
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return result


def safe_extract(source: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(source) as archive:
        if archive.testzip() is not None:
            raise BuildError("source ZIP CRC failure")
        seen: set[str] = set()
        roots: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or info.filename in seen
                or stat.S_ISLNK(mode)
            ):
                raise BuildError(f"unsafe source member: {info.filename}")
            seen.add(info.filename)
            roots.add(pure.parts[0])
        if roots != {SOURCE_NAME}:
            raise BuildError(f"source root differs: {sorted(roots)}")
        archive.extractall(destination)
    source_root = destination / SOURCE_NAME
    target_root = destination / INSTALL_NAME
    source_root.rename(target_root)
    return target_root


def replace_install_identity(package: Path) -> list[str]:
    old = SOURCE_NAME.encode()
    new = INSTALL_NAME.encode()
    changed: list[str] = []
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        payload = path.read_bytes()
        if old not in payload:
            continue
        path.write_bytes(payload.replace(old, new))
        changed.append(path.relative_to(package).as_posix())
    if "PREPARE_AND_RUN.sh" not in changed:
        raise BuildError("runner did not contain source install identity")
    return changed


def transform_runtime(
    path: Path, cloud_leaves: dict[str, str]
) -> None:
    text = path.read_text(encoding="utf-8")
    expected_start = text.index("EXPECTED_LEAVES = {")
    expected_end = text.index("\nPARSING_RE =", expected_start)
    constants = (
        "EXPECTED_LEAVES = "
        + json.dumps(LOCAL_LEAVES, indent=4)
        + "\n"
        + f'EXPECTED_COMMIT = "{LOCAL_PROVENANCE_COMMIT}"\n'
        + f'CLOUD_AUTHORITY_COMMIT = "{CLOUD_COMMIT}"\n'
        + "CLOUD_AUTHORITY_LEAVES = "
        + json.dumps(cloud_leaves, indent=4)
    )
    text = text[:expected_start] + constants + text[expected_end:]
    text = text.replace(
        'PASS_STATUS = "CONV_NATIVE_FOUR_LANE_DF23E4D_SERVER_PASS"',
        'PASS_STATUS = "CONV_NATIVE_FOUR_LANE_0CCAE916_FULL_SERVER_PASS"',
    )
    preflight_old = """        or manifest.get("expected_production_rtl_identity", {}).get("leaves")
        != EXPECTED_LEAVES
        or manifest.get("formal_readback_count") != 320
    ):
        raise RuntimeErrorContract("native-four-lane package identity differs")
"""
    preflight_new = """        or manifest.get("expected_production_rtl_identity", {}).get("leaves")
        != EXPECTED_LEAVES
        or manifest.get("expected_production_rtl_identity", {}).get("role")
        != "local_provenance_hint_only"
        or manifest.get("cloud_rtl_authority", {}).get("approved_commit")
        != CLOUD_AUTHORITY_COMMIT
        or manifest.get("cloud_rtl_authority", {}).get("leaves")
        != CLOUD_AUTHORITY_LEAVES
        or manifest.get("cloud_rtl_authority", {}).get(
            "identity_difference_blocks_compile_or_simulation"
        )
        is not False
        or manifest.get("formal_readback_count") != 320
    ):
        raise RuntimeErrorContract("native-four-lane p8f identity differs")
"""
    if text.count(preflight_old) != 1:
        raise BuildError("runtime preflight anchor differs")
    text = text.replace(preflight_old, preflight_new)

    collect_start = text.index("def collect_compile_identity(")
    collect_end = text.index("\ndef qualify_run(", collect_start)
    collect_new = '''def collect_compile_identity(
    compile_log: Path, output: Path
) -> dict[str, Any]:
    """Collect actual identity; identity differences never gate simulation."""
    text = compile_log.read_text(encoding="utf-8", errors="replace")
    parsed = [Path(match.group(1)) for match in PARSING_RE.finditer(text)]
    leaves: dict[str, Any] = {}
    collection_errors: list[str] = []
    for basename, local_expected in EXPECTED_LEAVES.items():
        matches = sorted(
            {str(path) for path in parsed if path.name == basename}
        )
        if len(matches) != 1:
            collection_errors.append(
                f"{basename}: expected one compiled path, found {len(matches)}"
            )
            continue
        source = Path(matches[0])
        if not source.is_file():
            collection_errors.append(f"{basename}: compiled path unreadable")
            continue
        observed = numeric_base.sha256(source)
        cloud_expected = CLOUD_AUTHORITY_LEAVES[basename]
        leaves[basename] = {
            "compiled_path": str(source),
            "size_bytes": source.stat().st_size,
            "sha256": observed,
            "local_provenance_sha256": local_expected,
            "cloud_authority_sha256": cloud_expected,
            "matches_local_provenance": observed == local_expected,
            "matches_cloud_authority": observed == cloud_expected,
        }
    collection_valid = not collection_errors and len(leaves) == len(
        EXPECTED_LEAVES
    )
    differs_local = any(
        not leaf["matches_local_provenance"] for leaf in leaves.values()
    )
    differs_cloud = any(
        not leaf["matches_cloud_authority"] for leaf in leaves.values()
    )
    if not collection_valid:
        classification = "COLLECTION_INCOMPLETE"
    elif differs_cloud:
        classification = "ACTUAL_DIFFERS_CURRENT_CLOUD"
    else:
        classification = "ACTUAL_MATCHES_CURRENT_CLOUD"
    receipt = {
        "schema": "conv-native-four-lane-0ccae916-full-production-identity-v1",
        "valid": collection_valid,
        "collection_valid": collection_valid,
        "collection_errors": collection_errors,
        "compile_log": str(compile_log),
        "compile_log_sha256": numeric_base.sha256(compile_log),
        "local_provenance_commit": EXPECTED_COMMIT,
        "cloud_authority_commit": CLOUD_AUTHORITY_COMMIT,
        "actual_differs_local_provenance": differs_local,
        "actual_differs_cloud_authority": differs_cloud,
        "authority_classification": classification,
        "identity_difference_blocks_simulator": False,
        "identity_source": (
            "actual VCS parsing receipts followed by post-compile leaf hashing"
        ),
        "precompile_server_source_preflight": False,
        "leaves": leaves,
    }
    _write(output, receipt)
    return receipt

'''
    text = text[:collect_start] + collect_new + text[collect_end + 1 :]
    result_old = (
        '            "production_rtl_identity_match": '
        'identity.get("valid") is True,\n'
    )
    result_new = (
        '            "actual_compile_identity_collected": '
        'identity.get("collection_valid") is True,\n'
        '            "actual_differs_local_provenance": '
        'identity.get("actual_differs_local_provenance"),\n'
        '            "actual_differs_cloud_authority": '
        'identity.get("actual_differs_cloud_authority"),\n'
        '            "identity_difference_blocks_simulator": False,\n'
    )
    if text.count(result_old) != 1:
        raise BuildError("runtime result identity anchor differs")
    text = text.replace(result_old, result_new)
    path.write_text(text, encoding="utf-8", newline="\n")


def transform_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    old = """python3 "$runtime" compile-identity   --compile-log "$run_root/compile/sim_results/compile_driver.log"   --output "$evidence_root/production_rtl_identity.json" || exit 8
simv="$run_root/compile/sim_results/simv"
"""
    new = """# Actual/local/cloud SHA differences are post-compile evidence only.
# Collection writes the return receipt and never blocks simulator launch.
python3 "$runtime" compile-identity   --compile-log "$run_root/compile/sim_results/compile_driver.log"   --output "$evidence_root/production_rtl_identity.json" >/dev/null 2>&1 || true
simv="$run_root/compile/sim_results/simv"
"""
    if text.count(old) != 1:
        raise BuildError("runner compile-identity anchor differs")
    text = text.replace(old, new)
    if text.count("timeout --foreground --signal=TERM --kill-after=30s 12h") != 1:
        raise BuildError("runner 12h per-run budget differs")
    if "for id in c0 c1 c2" not in text or "for id in t000 t001" not in text:
        raise BuildError("runner full-chain loops differ")
    path.write_text(text, encoding="utf-8", newline="\n")


def path_budget(package: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    runtime_root = package / "workload/runtime"
    projections = [
        f"install/cfg_pkg/{INSTALL_NAME}/{path.relative_to(runtime_root).as_posix()}"
        for path in runtime_root.rglob("*")
        if path.is_file()
    ]
    projections.extend(
        f"{INSTALL_NAME}_return/readbacks/"
        + str(record["runtime_path"]).replace("\\", "/")
        for record in manifest["readback_checks"]
    )
    projections.extend(
        [
            f"run_{INSTALL_NAME}/compile/sim_results/compile_driver.log",
            f"run_{INSTALL_NAME}/t207/return_observer.log",
            f"evidence_{INSTALL_NAME}/natural_terminal/t207.json",
            f"{INSTALL_NAME}_return/runs/t207/return_observer.log",
        ]
    )
    longest = max(projections, key=len)
    absolute = SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
    if absolute > ABSOLUTE_PATH_LIMIT_CHARS:
        raise BuildError("projected server path exceeds hard limit")
    inner = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file() and path.name != "package_manifest.json"
    ]
    deepest = max(inner, key=lambda item: (len(PurePosixPath(item).parts), len(item)))
    longest_inner = max(inner, key=len)
    return {
        "rule_id": "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
        "declared_target_root_max_chars": SERVER_ROOT_BUDGET_CHARS,
        "max_projected_absolute_path_limit_chars": ABSOLUTE_PATH_LIMIT_CHARS,
        "max_projected_absolute_path_chars": absolute,
        "max_projected_relative_path_chars": len(longest),
        "longest_projected_relative_path": longest,
        "max_zip_member_chars": max(
            len(f"{INSTALL_NAME}/{relative}") for relative in inner
        ),
        "max_inner_suffix_chars": len(longest_inner),
        "longest_inner_member": longest_inner,
        "max_inner_depth": len(PurePosixPath(deepest).parts),
        "deepest_inner_member": deepest,
        "max_inner_component_chars": max(
            len(component)
            for item in inner
            for component in PurePosixPath(item).parts
        ),
        "outer_identity_repeated_inside": any(
            INSTALL_NAME in PurePosixPath(item).parts for item in inner
        ),
        "actual_server_guard": (
            "runtime recomputes normalized user-root path budget before compile"
        ),
    }


def update_readme(package: Path) -> None:
    (package / "README.md").write_text(
        "# Conv node0004 native-four-lane full-chain p8f\n\n"
        "This fresh non-release performance diagnostic successor retains the "
        "frozen p4 numeric/config/mapping/bitstream/execplan/SCA/golden/320D "
        "payload. It records actual production RTL identity after compile "
        "without using identity differences as a simulator-launch predicate. "
        "All 27 runs retain a 12-hour per-run wallclock budget.\n\n"
        "Extract into a new empty parent, enter the single archive root, and "
        "run exactly once:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02\n"
        "```\n\n"
        "A formal pass requires 27/27 natural terminals and all 320 D "
        "readbacks present with zero mismatched bytes. The package carries no "
        "functional RTL and claims no server result before formal return.\n",
        encoding="utf-8",
        newline="\n",
    )


def update_manifest(
    package: Path,
    cloud_leaves: dict[str, str],
    changed_identity_files: list[str],
) -> None:
    path = package / "package_manifest.json"
    manifest = load_json(path)
    rule_receipts = {
        relative: sha256(ROOT / relative) for relative in RULE_PATHS
    }
    p7_analysis_sha = sha256(P7_ANALYSIS)
    cloud_audit_sha = sha256(CLOUD_AUDIT)
    manifest.update(
        {
            "schema": "resnet50-conv-native-four-lane-0ccae916-full-p8f-v1",
            "install_name": INSTALL_NAME,
            "run_namespace": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return.zip",
            "status": "PACKAGE_READY_NOT_RUN",
            "package_release": "PACKAGE_READY_NOT_RUN",
            "candidate_release": False,
            "candidate_class": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
            "simulation_run_count": 27,
            "formal_readback_count": 320,
            "natural_terminal_required_count": 27,
            "expected_production_rtl_identity": {
                "commit": LOCAL_PROVENANCE_COMMIT,
                "role": "local_provenance_hint_only",
                "leaves": LOCAL_LEAVES,
                "receipt_timing": "after actual production VCS compile",
            },
            "cloud_rtl_authority": {
                "repository": "xlsjdjdk/Trassic2.0_RTL",
                "branch": "master",
                "approved_commit": CLOUD_COMMIT,
                "leaves": cloud_leaves,
                "identity_difference_blocks_compile_or_simulation": False,
                "causal_cone_audit_sha256": cloud_audit_sha,
            },
            "p7_return_successor": {
                "formal_return_sha256": (
                    "71e7feda390934afec933ddfbfded6d6bebfdb633a66fe3ab00dd1817293f05c"
                ),
                "analysis_sha256": p7_analysis_sha,
                "classification": (
                    "PACKAGE_WALLCLOCK_BUDGET_UNDERPROVISIONED_"
                    "NOT_FUNCTIONAL_HANG"
                ),
                "first_divergence": (
                    "1h runner timeout before first c0 slice_finish"
                ),
                "fix": "restore 12h per-run and advance directly to full chain",
            },
            "full_chain_successor": {
                "source_package": f"{SOURCE_NAME}.zip",
                "source_sha256": SOURCE_ZIP_SHA256,
                "numeric_or_config_change": False,
                "observer_semantic_change": False,
                "functional_rtl_change": False,
                "runner_change": (
                    "actual/local/cloud identity collection is nonblocking"
                ),
                "wallclock_budget": "12h per run",
                "identity_normalized_files": changed_identity_files,
            },
            "materialized_config_receipt_reuse": {
                "source_package_sha256": SOURCE_ZIP_SHA256,
                "address_bytes_changed": False,
                "transaction_ledger": "RECEIPT_REUSE_BYTE_EQUAL",
                "boundary_microtrace": "NOT_APPLICABLE_BYTE_EQUAL",
                "physical_bank_row_validity": "RECEIPT_REUSE_BYTE_EQUAL",
                "numeric_w3_golden_repeated": False,
            },
            "result_gate_contract": {
                "required_natural_terminals": 27,
                "required_formal_D": 320,
                "required_missing_count": 0,
                "required_mismatch_byte_count": 0,
                "identity_difference_blocks_simulator": False,
            },
            "release_gate_matrix": {
                "schema": "conv-native-four-lane-p8f-release-gate-matrix-v1",
                "single_matrix": True,
                "gates": {
                    "core_package_bootstrap_path_runtime_d": {
                        "applicability": "blocking_applicable",
                        "status": "PENDING_FINAL_AUDIT",
                    },
                    "runner_compile_finalizer": {
                        "applicability": "blocking_applicable",
                        "status": "PENDING_FINAL_AUDIT",
                    },
                    "package_local_hdl": {
                        "applicability": "blocking_applicable",
                        "status": "PENDING_FINAL_AUDIT",
                    },
                    "materialized_config": {
                        "applicability": "receipt_reuse",
                        "status": "PASS",
                    },
                    "observer_parser_canonical": {
                        "applicability": "receipt_reuse",
                        "status": "PASS",
                    },
                    "return_result_joint": {
                        "applicability": "blocking_applicable",
                        "status": "PENDING_FINAL_AUDIT",
                    },
                    "numeric_w3_golden": {
                        "applicability": "record_only",
                        "status": "PASS",
                    },
                },
            },
            "rule_receipts": rule_receipts,
            "server_action": False,
            "functional_rtl_modified": False,
            "functional_rtl_file_count": 0,
            "server_rtl_entries": 0,
            "server_source_preflight_performed": False,
        }
    )
    manifest["path_length_budget"] = path_budget(package, manifest)
    provenance = manifest.setdefault("workload_provenance", {})
    provenance.update(
        {
            "package_builder": (
                "tools/"
                "build_conv_native_four_lane_0ccae916_p8f_full_package.py"
            ),
            "package_builder_sha256": sha256(Path(__file__)),
            "source_p4_zip_sha256": SOURCE_ZIP_SHA256,
            "p7_return_analysis_sha256": p7_analysis_sha,
            "cloud_causal_cone_audit_sha256": cloud_audit_sha,
        }
    )
    manifest["files"] = records(package)
    write_json(path, manifest)


def prepare_package(destination: Path) -> Path:
    package = safe_extract(SOURCE_ZIP, destination)
    changed = replace_install_identity(package)
    transform_runtime(
        package / "package_tools/node0004_native_four_lane_runtime_v1_base.py",
        cloud_leaves(),
    )
    transform_runner(package / "PREPARE_AND_RUN.sh")
    update_readme(package)
    update_manifest(package, cloud_leaves(), changed)
    return package


def cloud_leaves() -> dict[str, str]:
    audit = load_json(CLOUD_AUDIT)
    if not audit.get("valid") or audit.get("status") != (
        "SUCCESSOR_REQUIRED_CLOUD_RTL_NONBLOCKING"
    ):
        raise BuildError("cloud causal-cone audit is not valid")
    return {
        name: value["sha256"]
        for name, value in audit["cloud_expected_compiled_leaves"].items()
    }


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = path.relative_to(package).as_posix()
            info = zipfile.ZipInfo(f"{INSTALL_NAME}/{relative}")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            archive.writestr(info, path.read_bytes(), compresslevel=1)


def build(output_root: Path) -> dict[str, Any]:
    if not SOURCE_ZIP.is_file() or sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise BuildError("immutable p4 source ZIP identity differs")
    p7 = load_json(P7_ANALYSIS)
    if (
        not p7.get("valid")
        or p7.get("status")
        != "LONG_RUNNING_PROGRESSING_RUNNER_TIMEOUT_SUCCESSOR_REQUIRED"
    ):
        raise BuildError("p7 return analysis does not release successor")
    target = output_root / INSTALL_NAME
    target_zip = output_root / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(target_zip) + ".sha256")
    receipt = output_root / f"{INSTALL_NAME}.validation.json"
    for path in (target, target_zip, sidecar, receipt):
        if path.exists():
            raise BuildError(f"fresh output required: {path}")

    with tempfile.TemporaryDirectory(prefix="n4-p8f-a-") as first_name, (
        tempfile.TemporaryDirectory(prefix="n4-p8f-b-")
    ) as second_name:
        first_root = Path(first_name)
        second_root = Path(second_name)
        first_package = prepare_package(first_root / "extract")
        second_package = prepare_package(second_root / "extract")
        first_zip = first_root / f"{INSTALL_NAME}.zip"
        second_zip = second_root / f"{INSTALL_NAME}.zip"
        deterministic_zip(first_package, first_zip)
        deterministic_zip(second_package, second_zip)
        deterministic = (
            first_zip.stat().st_size == second_zip.stat().st_size
            and sha256(first_zip) == sha256(second_zip)
            and filecmp.cmp(first_zip, second_zip, shallow=False)
        )
        if not deterministic:
            raise BuildError("dual-build ZIP bytes differ")
        shutil.copytree(first_package, target)
        shutil.copy2(first_zip, target_zip)

    digest = sha256(target_zip)
    sidecar.write_text(
        f"{digest}  {target_zip.name}\n",
        encoding="ascii",
        newline="\n",
    )
    result = {
        "schema": "conv-native-four-lane-0ccae916-p8f-build-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "package_release": "PACKAGE_READY_NOT_RUN",
        "candidate_release": False,
        "install_name": INSTALL_NAME,
        "zip": str(target_zip),
        "zip_bytes": target_zip.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "sidecar_sha256": sha256(sidecar),
        "directory_file_count": len(records(target)) + 1,
        "deterministic_dual_build_byte_equal": True,
        "source_p4_zip_sha256": SOURCE_ZIP_SHA256,
        "p7_return_analysis_sha256": sha256(P7_ANALYSIS),
        "cloud_causal_cone_audit_sha256": sha256(CLOUD_AUDIT),
        "server_action": False,
        "claim_boundary": (
            "package construction only; natural terminal, formal 320D and "
            "performance E3/E4/E5 remain pending formal server return"
        ),
    }
    write_json(receipt, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    try:
        result = build(args.output_root.resolve())
    except Exception as error:
        print(f"package build failed: {error}")
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
