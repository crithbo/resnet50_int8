#!/usr/bin/env python3
"""Build the native-four-lane p15 install-only runtime-layout successor."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p14_install"
PACKAGE_ID = "r5_n4_0cc_p15_installonly"
WORKLOAD_INSTALL_NAME = "r5_n4_0cc_p11f_pubord"
ATTEMPT = "a0"
SOURCE_SHA256 = (
    "e920803ffddbb90dc93470c0b711bfc8bf046ae819012ad89461f36ab9be5427"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/tested"
    / "conv_native_four_lane"
    / SOURCE_ID
    / f"{SOURCE_ID}.zip"
)
DEFAULT_OUTPUT = (
    ROOT / "outputs/conv_native_four_lane_0ccae916_p15_install_only"
)
SHARED_HELPER = ROOT / "tools/server_package_runtime_layout.py"
SHARED_HELPER_SHA256 = (
    "7969ca56e13a7e0a0a83bdfd48d1409d28eef2ae0fd63ad08f0ec5c39e2d848a"
)
LAYOUT_SCHEMA = ROOT / "schemas/server_package_runtime_layout_v1.schema.json"
BUILD_PROFILE = DEFAULT_OUTPUT / f"{PACKAGE_ID}.build_profile.json"
SERVER_RULE_SHA256 = (
    "16f7773796dccf4f27a5e412bb200f7b4190ffb87742d3dd2e466866a7f77dde"
)
INDEX_SHA256 = (
    "68c13cbd1461ca2a506174678d22cfdbfdc5aced25ad80150d4e4cacece7f2be"
)
OPTIMIZER_SHA256 = (
    "f51525f8db7d8b8e79e57ea194c7d9f6624a320e5754df4dfd164ddc5e50687b"
)
SHARED_VALIDATOR_SHA256 = (
    "66f779d9d472dabaf9a3d2f2b09b472d6bb6ea575865e223a8e80c11818813a5"
)
LAYOUT_SCHEMA_SHA256 = (
    "529864182fc57bd3af47fc31dcb5697420b8f656303270e0b0ee862379faf79d"
)
HARNESS_SCHEMA_SHA256 = (
    "9f77cd5921ff3b4e0f692425aaa27c6f6f7a18466c414e7bcc89a00b56ec67c3"
)
BUILD_REGISTRY_SHA256 = (
    "7af29e7d01684db24334365e9e92f0dd0370331c253b2bfb8e58ccf265f93274"
)
DISPATCH_SHA256 = (
    "896c2b5a97409c14bf6596c51823cf9ba4ddfa6fc2e8614d7f48e899b298168b"
)
SOURCE_RETURN_ANALYSIS_SHA256 = (
    "c543ed086309cc949e05e7ea9a7a1054bd4ecb472f91aa020186242eec28a2f4"
)
SERVER_ROOT_BUDGET_CHARS = 96
ABSOLUTE_PATH_LIMIT_CHARS = 240
ATTEMPT_MAX_CHARS = 2
INPUT_PREFIX = f"install/cfg_pkg/{WORKLOAD_INSTALL_NAME}/"
OLD_OUTPUT_PREFIX = f"install/codex_runs/{SOURCE_ID}/{ATTEMPT}/c0/d/"
OUTPUT_PREFIX = f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}/c0/d/"
ALLOWED_CHANGED_PATHS = {
    "PREPARE_AND_RUN.sh",
    "README.md",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "TEST_PACKAGE_MANIFEST.json",
    "package_manifest.json",
    "package_tools/fixed_simresult_publisher.py",
    "package_tools/node0004_assumed_hardware_server_runtime.py",
    "package_tools/server_package_runtime_layout.py",
    "workload/runtime/runs/c0/sca_cfg_D.json",
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


def safe_extract_source(destination: Path) -> Path:
    if not SOURCE_ZIP.is_file() or sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact tested p14 source ZIP differs or is unavailable")
    package = destination / PACKAGE_ID
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        bad = archive.testzip()
        if bad is not None:
            raise BuildError(f"tested p14 source CRC failed at {bad}")
        seen: set[str] = set()
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                info.filename in seen
                or pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or pure.parts[0] != SOURCE_ID
            ):
                raise BuildError(f"unsafe/duplicate p14 source member: {info.filename}")
            seen.add(info.filename)
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:])
            target = package.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))
    return package


def replace_identity(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if SOURCE_ID not in text:
        raise BuildError(f"p14 identity anchor absent: {path}")
    path.write_text(
        text.replace(SOURCE_ID, PACKAGE_ID),
        encoding="utf-8",
        newline="\n",
    )


def patch_sca_d(package: Path) -> None:
    path = package / "workload/runtime/runs/c0/sca_cfg_D.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    changed = 0
    for key, record in document.items():
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise BuildError(f"unexpected SCA_D record: {key}")
        old = record["path"]
        if not old.startswith(OLD_OUTPUT_PREFIX):
            raise BuildError(f"unexpected p14 SCA_D prefix: {old}")
        record["path"] = OUTPUT_PREFIX + old[len(OLD_OUTPUT_PREFIX) :]
        changed += 1
    if changed != 28:
        raise BuildError(f"SCA_D output count differs: {changed}")
    write_json(path, document)


def projected_paths(package: Path, contract: dict[str, Any]) -> set[str]:
    sca = json.loads(
        (package / "workload/runtime/runs/c0/sca_cfg.json").read_text(
            encoding="utf-8"
        )
    )
    sca_d = json.loads(
        (package / "workload/runtime/runs/c0/sca_cfg_D.json").read_text(
            encoding="utf-8"
        )
    )

    def walk(value: Any) -> list[str]:
        rows: list[str] = []
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "path" and isinstance(child, str):
                    rows.append(child)
                else:
                    rows.extend(walk(child))
        elif isinstance(value, list):
            for child in value:
                rows.extend(walk(child))
        return rows

    attempt = "a" * ATTEMPT_MAX_CHARS
    paths = set(walk(sca)) | set(walk(sca_d))
    paths.update(
        path.replace("{attempt}", attempt)
        for path in contract["path_budget"]["additional_projected_paths"]
    )
    paths.update(
        value.replace("{attempt}", attempt)
        for value in contract["runtime_roots"].values()
    )
    return paths


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(path.read_text(encoding="utf-8"))
    encoded = json.dumps(contract, ensure_ascii=False)
    contract = json.loads(encoded.replace(SOURCE_ID, PACKAGE_ID))
    contract["package_id"] = PACKAGE_ID
    contract["shared_layout_helper"]["sha256"] = SHARED_HELPER_SHA256
    contract["required_preexisting_parents"] = ["install"]
    contract["package_creatable_parent_dirs"] = [
        "install/cfg_pkg",
        "install/codex_runs",
    ]
    contract["claim_boundary"] = (
        "Mechanical p14-to-p15 install-only runtime layout, SCA_D path "
        "binding, early partial-return finalizer and fixed-result publication "
        "only; no DUT, numeric, terminal, formal-D, E3, E4 or E5 claim."
    )
    paths = projected_paths(package, contract)
    longest = max(paths, key=lambda value: (len(value), value))
    contract["path_budget"]["max_projected_absolute_path_chars"] = (
        SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
    )
    jsonschema.validate(
        contract,
        json.loads(LAYOUT_SCHEMA.read_text(encoding="utf-8")),
    )
    write_json(path, contract)
    return contract


def file_records(package: Path) -> dict[str, dict[str, Any]]:
    manifest = package / "package_manifest.json"
    return {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path != manifest
    }


def rule_receipts() -> list[dict[str, Any]]:
    rows = [
        (
            ".agents/agent.md",
            "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
            "stable project authority",
        ),
        (
            ".agents/plan.md",
            "43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70",
            "mutable provenance observed before build",
        ),
        (
            ".agents/rules/生成前必读索引.md",
            INDEX_SHA256,
            "current routing authority",
        ),
        (
            ".agents/rules/服务器测试包生成规则.md",
            SERVER_RULE_SHA256,
            "current server package authority",
        ),
        (
            ".agents/rules/整网测试收敛优化专项规则.md",
            OPTIMIZER_SHA256,
            "current changed-surface and shared-regression authority",
        ),
        (
            "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
            "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6",
            "current server compile/simulation entry",
        ),
    ]
    result = []
    for relative, expected, reason in rows:
        path = ROOT / relative
        if not path.is_file() or sha256(path) != expected:
            raise BuildError(f"current rule receipt differs: {relative}")
        result.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": expected,
                "reason": reason,
            }
        )
    return result


def patch_manifest(package: Path, contract: dict[str, Any]) -> None:
    path = package / "package_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest = json.loads(
        json.dumps(manifest, ensure_ascii=False).replace(SOURCE_ID, PACKAGE_ID)
    )
    manifest["package_identity"] = PACKAGE_ID
    manifest["run_namespace"] = (
        f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}"
    )
    manifest["return_name"] = f"{PACKAGE_ID}_return.zip"
    manifest["rule_receipts"] = rule_receipts()
    manifest["rule_receipts_current_match"] = True
    manifest["runner_only_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_package_zip_sha256": SOURCE_SHA256,
        "source_disposition": "tested",
        "source_return_classification": (
            "PACKAGE_LOCAL_PREFLIGHT_CONTRACT_TOO_STRICT"
        ),
        "changed_surfaces": sorted(ALLOWED_CHANGED_PATHS),
        "frozen_surfaces": [
            "all other workload/runtime bytes",
            "config/mapping/bitstream/execplan/SCA input bytes",
            "numeric/W3/golden",
            "diagnostics/tb_probe/observer/timeout",
            "functional RTL/ISA/hardware/active ndp-sim",
        ],
    }
    manifest["source_p14_preflight_return_analysis"] = {
        "path": (
            "outputs/conv_native_four_lane_0ccae916_"
            "p14_preflight_return_analysis/report.json"
        ),
        "sha256": SOURCE_RETURN_ANALYSIS_SHA256,
        "classification": "PACKAGE_LOCAL_PREFLIGHT_CONTRACT_TOO_STRICT",
        "compile_started": False,
        "simulation_started": False,
        "p14_rerun": False,
    }
    manifest["install_only_v2_receipts"] = {
        "server_rule_sha256": SERVER_RULE_SHA256,
        "generation_index_sha256": INDEX_SHA256,
        "optimizer_rule_sha256": OPTIMIZER_SHA256,
        "shared_helper_sha256": SHARED_HELPER_SHA256,
        "shared_validator_sha256": SHARED_VALIDATOR_SHA256,
        "layout_schema_sha256": LAYOUT_SCHEMA_SHA256,
        "harness_schema_sha256": HARNESS_SCHEMA_SHA256,
        "build_registry_sha256": BUILD_REGISTRY_SHA256,
        "two_conv_dispatch_sha256": DISPATCH_SHA256,
    }
    manifest["ndp_root_toplevel_contract"] = {
        "runtime_write_targets": [
            f"install/cfg_pkg/{WORKLOAD_INSTALL_NAME}",
            f"install/codex_runs/{PACKAGE_ID}/{ATTEMPT}",
        ],
        "root_internal_preexisting_parents": ["install"],
        "package_creatable_parent_dirs": [
            "install/cfg_pkg",
            "install/codex_runs",
        ],
        "root_external_write_roots": ["/home/panqs/ndp/simresult"],
        "manual_server_mkdir_required": False,
    }
    manifest["fixed_server_result_publication"] = {
        "result_root": "/home/panqs/ndp/simresult",
        "return_zip": (
            f"/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip"
        ),
        "return_sidecar": (
            f"/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip.sha256"
        ),
        "atomic_same_directory_staging": True,
    }
    manifest["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "reason": (
            "p14 formal preflight exposed the superseded public requirement "
            "that install/codex_runs pre-exist"
        ),
        "sca_d_output_paths": sorted(
            record["path"]
            for record in json.loads(
                (
                    package / "workload/runtime/runs/c0/sca_cfg_D.json"
                ).read_text(encoding="utf-8")
            ).values()
        ),
        "rule_ids": [
            "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
            "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
            "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
            "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
            "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
        ],
    }
    paths = projected_paths(package, contract)
    longest = max(paths, key=lambda value: (len(value), value))
    inner_paths = [
        item.relative_to(package).as_posix()
        for item in package.rglob("*")
        if item.is_file()
    ] + ["package_manifest.json"]
    manifest["path_length_budget"].update(
        {
            "declared_target_root_max_chars": SERVER_ROOT_BUDGET_CHARS,
            "longest_projected_relative_path": longest,
            "longest_projected_relative_path_chars": len(longest),
            "max_projected_relative_path_chars": len(longest),
            "max_projected_absolute_path_chars": (
                SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
            ),
            "absolute_path_limit_chars": ABSOLUTE_PATH_LIMIT_CHARS,
            "max_projected_absolute_path_limit_chars": (
                ABSOLUTE_PATH_LIMIT_CHARS
            ),
            "max_zip_member_chars": max(
                len(f"{PACKAGE_ID}/{relative}") for relative in inner_paths
            ),
            "max_inner_suffix_chars": max(map(len, inner_paths)),
            "max_inner_depth": max(
                len(PurePosixPath(relative).parts) for relative in inner_paths
            ),
            "max_inner_component_chars": max(
                len(component)
                for relative in inner_paths
                for component in PurePosixPath(relative).parts
            ),
            "outer_identity_repeated_inside": False,
            "fixed_result_root": "/home/panqs/ndp/simresult",
        }
    )
    manifest["release_gate_applicability"] = {
        "core_package_bootstrap_path": "blocking_applicable",
        "runner_compile_finalizer": "blocking_applicable",
        "return_result_joint_gate": "blocking_applicable",
        "cloud_identity_nonblocking_positive_control": "blocking_applicable",
        "package_local_hdl": "receipt_reuse_byte_equal",
        "materialized_config": (
            "blocking_applicable_mechanical_sca_d_path_only"
        ),
        "diagnostic_predicate_trace": (
            "not_applicable_observer_parser_canonical_byte_equal"
        ),
        "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
        "runtime_layout": "blocking_applicable_install_only_v2",
    }
    manifest["release_gate_matrix"]["runtime_layout"].update(
        {
            "applicability": "blocking_applicable",
            "pass": True,
            "rule_id": "CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001",
            "semantic_version": "2",
        }
    )
    manifest["files"] = file_records(package)
    write_json(path, manifest)


def patch_pointer_and_readme(package: Path) -> None:
    pointer_path = package / "TEST_PACKAGE_MANIFEST.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["schema"] = "conv-native-four-lane-p15-installonly-pointer-v1"
    pointer["package_identity"] = PACKAGE_ID
    pointer["status"] = "PACKAGE_READY_NOT_RUN"
    write_json(pointer_path, pointer)
    (package / "README.md").write_text(
        "# Native four-lane Conv p15 install-only successor\n\n"
        "This fresh package mechanically replaces tested p14. Only the real, "
        "non-symlink `$server_root/install` directory must pre-exist. The "
        "package safely creates missing `install/cfg_pkg` and "
        "`install/codex_runs` directories and fresh package/attempt leaves; "
        "the user must not create them manually.\n\n"
        "Run after extraction:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n"
        "```\n\n"
        f"Expected return: `/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip` "
        "and its `.sha256` sidecar.\n\n"
        "The workload/config/numeric/golden/observer/timeout/functional RTL "
        "surfaces remain frozen from p14. Local validation does not claim "
        "production compile, DUT simulation, natural terminal, formal 320D, "
        "performance, E3, E4, or E5.\n",
        encoding="utf-8",
        newline="\n",
    )


def build_directory(destination: Path) -> Path:
    if sha256(SHARED_HELPER) != SHARED_HELPER_SHA256:
        raise BuildError("current shared layout helper SHA differs")
    profile = json.loads(BUILD_PROFILE.read_text(encoding="utf-8"))
    if (
        profile.get("package_id") != PACKAGE_ID
        or profile.get("contract_valid") is not True
        or profile.get("mode") != "SHADOW_ONLY_NEXT_FRESH"
    ):
        raise BuildError("fresh p15 compiled build profile is invalid")
    package = safe_extract_source(destination)
    for relative in (
        "PREPARE_AND_RUN.sh",
        "package_tools/fixed_simresult_publisher.py",
        "package_tools/node0004_assumed_hardware_server_runtime.py",
    ):
        replace_identity(package / relative)
    (package / "package_tools/server_package_runtime_layout.py").write_bytes(
        SHARED_HELPER.read_bytes()
    )
    patch_sca_d(package)
    contract = patch_contract(package)
    patch_pointer_and_readme(package)
    patch_manifest(package, contract)
    return package


def deterministic_zip(package: Path, target: Path) -> None:
    with zipfile.ZipFile(
        target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            relative = (Path(PACKAGE_ID) / path.relative_to(package)).as_posix()
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (
                (0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644)
                << 16
            )
            archive.writestr(info, path.read_bytes())


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
    ]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite an existing p15 build target")
    package = build_directory(output)
    zip_path = output / f"{PACKAGE_ID}.zip"
    deterministic_zip(package, zip_path)
    digest = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix=".p15_repeat_", dir=ROOT) as temp:
        repeat_root = Path(temp)
        repeat_profile = repeat_root / BUILD_PROFILE.name
        shutil.copy2(BUILD_PROFILE, repeat_profile)
        original_profile = globals()["BUILD_PROFILE"]
        try:
            globals()["BUILD_PROFILE"] = repeat_profile
            repeat = build_directory(repeat_root)
        finally:
            globals()["BUILD_PROFILE"] = original_profile
        repeat_zip = repeat_root / f"{PACKAGE_ID}.zip"
        deterministic_zip(repeat, repeat_zip)
        deterministic = sha256(repeat_zip) == digest
    if not deterministic:
        raise BuildError("p15 deterministic double build differs")
    sidecar = output / f"{PACKAGE_ID}.zip.sha256"
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    report = {
        "schema": "conv-native-four-lane-p15-install-only-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "workload_install_name": WORKLOAD_INSTALL_NAME,
        "source_p14_zip_sha256": SOURCE_SHA256,
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "deterministic_double_build": deterministic,
        "changed_paths": sorted(ALLOWED_CHANGED_PATHS),
        "functional_rtl_modified": False,
        "config_numeric_w3_golden_observer_timeout_changed": False,
        "sca_d_path_prefix_only_changed": True,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
