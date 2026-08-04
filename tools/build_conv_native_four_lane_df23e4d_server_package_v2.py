from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import (  # noqa: E402
    build_conv_native_four_lane_df23e4d_server_package as v1,
)
from tools import (  # noqa: E402
    conv_native_four_lane_df23e4d_server_runtime_v2 as runtime,
)


INSTALL_NAME = "r5_n4_df23e4d_p4"
OUTPUT_ROOT = (
    ROOT / "artifacts/operator_config_validation/r5-server-test-packages"
)
RUNTIME_SOURCE = (
    ROOT / "tools/conv_native_four_lane_df23e4d_server_runtime_v2.py"
)
RUNTIME_V1_BASE_SOURCE = (
    ROOT / "tools/conv_native_four_lane_df23e4d_server_runtime.py"
)
SOURCE_V1_ZIP = OUTPUT_ROOT / "r5_conv_native_four_lane_df23e4d_perf_v1.zip"
SOURCE_V1_SHA256 = (
    "5cbf05cac96f887c6753d378c7f3f44daf04f60caa6016f1f41eab274cebd62f"
)
RULE_RECEIPTS = {
    ".agents/agent.md": (
        "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f"
    ),
    ".agents/rules/生成前必读索引.md": (
        "93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2"
    ),
    ".agents/rules/服务器测试包生成规则.md": (
        "14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1"
    ),
    ".agents/rules/算子配置规则.md": (
        "cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171"
    ),
    ".agents/rules/NDP硬件字段语义.md": (
        "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055"
    ),
    ".agents/rules/INT8_SA点积专项规则.md": (
        "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce"
    ),
    ".agents/rules/精确UINT8量化尾专项规则.md": (
        "1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e"
    ),
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md": (
        "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7"
    ),
}
SERVER_ROOT_BUDGET_CHARS = 96
ABSOLUTE_PATH_LIMIT_CHARS = 240

_V1_CHECK_INPUTS = v1.check_inputs


def _configure_v1() -> None:
    v1.INSTALL_NAME = INSTALL_NAME
    v1.RULE_RECEIPTS = RULE_RECEIPTS
    v1.runtime = runtime


def check_inputs() -> None:
    _configure_v1()
    if (
        not SOURCE_V1_ZIP.is_file()
        or v1.base.sha256(SOURCE_V1_ZIP) != SOURCE_V1_SHA256
    ):
        raise v1.PackageBuildError("immutable v1 source ZIP identity differs")
    _V1_CHECK_INPUTS()


def run_script() -> str:
    _configure_v1()
    script = v1.run_script()
    old = (
        'mkdir -p "$cfg_root" "$run_root/compile/sim_results" '
        '"$evidence_root/natural_terminal"\n'
        'python3 "$runtime" preflight --package-root "$package_root"   '
        '> "$evidence_root/package_preflight.json" || exit 5\n'
    )
    new = (
        'mkdir -p "$cfg_root" "$run_root/compile/sim_results" '
        '"$evidence_root/natural_terminal"\n'
        'cleanup_empty_preflight_namespaces() {\n'
        '  rmdir "$evidence_root/natural_terminal" "$evidence_root" '
        '2>/dev/null || true\n'
        '  rmdir "$run_root/compile/sim_results" "$run_root/compile" '
        '"$run_root" 2>/dev/null || true\n'
        '  rmdir "$cfg_root" 2>/dev/null || true\n'
        '}\n'
        'python3 "$runtime" path-budget --package-root "$package_root"   '
        '--server-root "$server_root" >/dev/null || '
        '{ cleanup_empty_preflight_namespaces; exit 5; }\n'
        'package_preflight_json="$(python3 "$runtime" preflight   '
        '--package-root "$package_root")" || '
        '{ cleanup_empty_preflight_namespaces; exit 5; }\n'
        'printf "%s\\n" "$package_preflight_json" '
        '> "$evidence_root/package_preflight.json"\n'
    )
    if script.count(old) != 1:
        raise v1.PackageBuildError("v1 runner preflight anchor differs")
    return script.replace(old, new)


def _package_path_stats(package: Path) -> dict[str, Any]:
    files = [
        path
        for path in package.rglob("*")
        if path.is_file() and path.name != "package_manifest.json"
    ]
    inner_records = [
        {
            "path": path.relative_to(package).as_posix(),
            "chars": len(path.relative_to(package).as_posix()),
            "depth": len(path.relative_to(package).parts),
            "max_component_chars": max(len(part) for part in path.relative_to(package).parts),
        }
        for path in files
    ]
    longest_inner = max(inner_records, key=lambda item: int(item["chars"]))
    deepest_inner = max(
        inner_records,
        key=lambda item: (int(item["depth"]), int(item["chars"])),
    )
    longest_component = max(
        inner_records, key=lambda item: int(item["max_component_chars"])
    )
    max_zip_member_chars = max(
        len(f"{INSTALL_NAME}/{record['path']}") for record in inner_records
    )

    projections: list[str] = []
    runtime_root = package / "workload/runtime"
    for path in runtime_root.rglob("*"):
        if path.is_file():
            relative = path.relative_to(runtime_root).as_posix()
            projections.append(
                f"install/cfg_pkg/{INSTALL_NAME}/{relative}"
            )
    manifest = v1.load_json(package / "package_manifest.json")
    for record in manifest.get("readback_checks", []):
        runtime_path = str(record["runtime_path"]).replace("\\", "/")
        projections.append(
            f"{INSTALL_NAME}_return/readbacks/{runtime_path}"
        )
    projections.extend(
        [
            f"run_{INSTALL_NAME}/compile/sim_results/compile_driver.log",
            f"run_{INSTALL_NAME}/t207/return_observer.log",
            f"evidence_{INSTALL_NAME}/natural_terminal/t207.json",
            f"{INSTALL_NAME}_return/runs/t207/return_observer.log",
        ]
    )
    longest_projected = max(projections, key=len)
    projected_absolute = (
        SERVER_ROOT_BUDGET_CHARS + 1 + len(longest_projected)
    )
    if projected_absolute > ABSOLUTE_PATH_LIMIT_CHARS:
        raise v1.PackageBuildError(
            "v2 projected absolute path exceeds current budget"
        )
    repeated_outer = [
        record["path"]
        for record in inner_records
        if INSTALL_NAME in Path(str(record["path"])).parts
    ]
    if repeated_outer:
        raise v1.PackageBuildError("outer identity repeats inside package")
    return {
        "rule_id": "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
        "declared_target_root_max_chars": SERVER_ROOT_BUDGET_CHARS,
        "max_projected_absolute_path_limit_chars": ABSOLUTE_PATH_LIMIT_CHARS,
        "max_projected_absolute_path_chars": projected_absolute,
        "max_projected_relative_path_chars": len(longest_projected),
        "longest_projected_relative_path": longest_projected,
        "max_zip_member_chars": max_zip_member_chars,
        "max_inner_suffix_chars": int(longest_inner["chars"]),
        "longest_inner_member": str(longest_inner["path"]),
        "max_inner_depth": int(deepest_inner["depth"]),
        "deepest_inner_member": str(deepest_inner["path"]),
        "max_inner_component_chars": int(
            longest_component["max_component_chars"]
        ),
        "component_target_chars": 48,
        "component_exceptions": [
            {
                "pattern": "*_bitstream_128b.bin",
                "reason": (
                    "frozen native tool ABI leaf; parent namespaces are "
                    "already shortened and all direct consumers remain exact"
                ),
            }
        ],
        "outer_identity_repeated_inside": False,
        "actual_server_guard": (
            "runtime path-budget recomputes the normalized user root before "
            "compile and removes newly created empty namespaces on failure"
        ),
    }


def _update_readme(package: Path) -> None:
    (package / "README.md").write_text(
        "# Conv node0004 native-four-lane performance candidate v2\n\n"
        "This successor fixes delivery/extraction robustness only. The "
        "numeric workload, config, mapping, bitstream, execplan, SCA/SCA_D, "
        "golden, observer and df23e4d production-leaf expectations remain "
        "frozen from v1.\n\n"
        "Verify and extract the ZIP into a newly created empty parent. Enter "
        "the single archive root directly; do not copy selected members into "
        "an old extraction.\n\n"
        "Run exactly once from that root:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy02\n"
        "```\n\n"
        "The runner verifies the complete package exact-set and path budget "
        "before retaining any install/run/evidence namespace; a preflight "
        "failure removes only the just-created empty task namespaces. This "
        "remains a "
        "non-release performance diagnostic candidate. It carries no "
        "functional RTL and does not inspect server source before compile.\n",
        encoding="utf-8",
        newline="\n",
    )


def augment_package(package: Path) -> Path:
    _configure_v1()
    package = v1.augment_package(package)
    tools_root = package / "package_tools"
    shutil.copy2(
        RUNTIME_V1_BASE_SOURCE,
        tools_root / "node0004_native_four_lane_runtime_v1_base.py",
    )
    _update_readme(package)
    manifest = v1.load_json(package / "package_manifest.json")
    manifest.update(
        {
            "schema": (
                "resnet50-conv-native-four-lane-df23e4d-"
                "server-package-v2"
            ),
            "install_name": INSTALL_NAME,
            "run_namespace": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return.zip",
            "delivery_successor": {
                "source_package": (
                    "r5_conv_native_four_lane_df23e4d_perf_v1.zip"
                ),
                "source_sha256": SOURCE_V1_SHA256,
                "classification": (
                    "FRESH_EXTRACTION_COMPLETENESS_SUCCESSOR"
                ),
                "functional_or_numeric_change": False,
                "changes": [
                    "short outer package/install/run/return identity",
                    "dual no-bytecode entry guard",
                    "path budget before namespace creation",
                    "complete exact-set preflight before namespace creation",
                    "explicit clean-extraction README",
                ],
            },
            "path_length_budget": _package_path_stats(package),
            "package_preflight_order": {
                "path_budget_before_compile": True,
                "complete_exact_set_before_compile": True,
                "single_exact_set_scan": True,
                "failed_preflight_empty_namespaces_removed": True,
            },
            "rule_receipts": RULE_RECEIPTS,
            "server_action": False,
        }
    )
    provenance = manifest.get("workload_provenance", {})
    provenance.update(
        {
            "package_builder": (
                "tools/"
                "build_conv_native_four_lane_df23e4d_server_package_v2.py"
            ),
            "package_builder_sha256": v1.base.sha256(Path(__file__)),
            "command": (
                ".venv/Scripts/python.exe tools/"
                "build_conv_native_four_lane_df23e4d_server_package_v2.py"
            ),
            "source_v1_zip_sha256": SOURCE_V1_SHA256,
        }
    )
    manifest["workload_provenance"] = provenance
    manifest["files"] = runtime.numeric_base.package_records(package)
    v1.base.write_json(package / "package_manifest.json", manifest)
    runtime.preflight(package)
    return package


def build_directory(destination: Path) -> Path:
    _configure_v1()
    v1.base.INSTALL_NAME = INSTALL_NAME
    v1.base.LOCAL_ROOT = v1.LOCAL_ROOT
    v1.base.RUNTIME_SOURCE = RUNTIME_SOURCE
    v1.base.run_script = run_script
    return augment_package(v1.base.build_directory(destination))


def build_reproducible(output_root: Path) -> dict[str, Any]:
    _configure_v1()
    v1.check_inputs = check_inputs
    v1.build_directory = build_directory
    result = v1.build_reproducible(output_root)
    result.update(
        {
            "schema": (
                "conv-native-four-lane-df23e4d-package-build-v2"
            ),
            "install_name": INSTALL_NAME,
            "source_v1_zip_sha256": SOURCE_V1_SHA256,
            "delivery_fix_only": True,
        }
    )
    receipt = output_root / f"{INSTALL_NAME}.validation.json"
    v1.base.write_json(receipt, result)
    return result


def main() -> int:
    sys.dont_write_bytecode = True
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()
    try:
        result = build_reproducible(args.output_root.resolve())
    except Exception as error:
        print(f"package build failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
