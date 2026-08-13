#!/usr/bin/env python3
"""Build the fresh p6 observer-only successor from the exact p5 ZIP."""

from __future__ import annotations

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
SOURCE_NAME = "r5_n4_e1f_p5_c0diag"
INSTALL_NAME = "r5_n4_e1f_p6_armif"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = (
    "393428f1ac860d89daa56543a8e27521c79e0965d5eaa197c074d81219cc6cb8"
)
RETURN_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_e1fb0f7_p5_return_analysis/report.json"
)
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
SERVER_ROOT_BUDGET_CHARS = 96
ABSOLUTE_PATH_LIMIT_CHARS = 240
README_TEXT = """# Conv node0004 native-four-lane c0 boundary diagnostic p6

This fresh observer-only successor keeps the exact p5 c0 workload/config,
bitstream, execplan and SCA semantics.  It replaces only the package observer's
private `buf2arm_valid_hold` XMR with the interface-derived raw pressure witness
`buf2arm_rvalid & !array2arm_bp_post`; it does not modify functional RTL.

Run exactly once from a cleanly extracted package root:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/server_root
```

The run is bounded to one hour and returns partial evidence on timeout.  It is
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`, contains no formal 320D payload, claims no
E3/E4/E5, and collects actual production RTL identity only after a successful
production compile.
"""


class BuildError(RuntimeError):
    pass


def digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=False) + "\n").encode()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json_bytes(value))


def records(package: Path, include_manifest: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        relative = path.relative_to(package).as_posix()
        if not include_manifest and relative == "package_manifest.json":
            continue
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    return result


def safe_extract(source: Path, target: Path) -> Path:
    with zipfile.ZipFile(source) as archive:
        seen: set[str] = set()
        for info in archive.infolist():
            name = info.filename
            pure = PurePosixPath(name)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in name
                or not pure.parts
                or pure.parts[0] != SOURCE_NAME
                or name in seen
                or stat.S_ISLNK(mode)
            ):
                raise BuildError(f"unsafe source ZIP member: {name}")
            seen.add(name)
        archive.extractall(target)
    source_root = target / SOURCE_NAME
    if not source_root.is_dir():
        raise BuildError("source ZIP did not produce its declared root")
    return source_root


def replace_identity(path: Path) -> None:
    payload = path.read_bytes()
    old = SOURCE_NAME.encode()
    if old not in payload:
        raise BuildError(f"expected source identity absent: {path}")
    path.write_bytes(payload.replace(old, INSTALL_NAME.encode()))


def replace_private_xmr(observer: Path) -> None:
    text = observer.read_text(encoding="utf-8")
    old = """                assign n4d_arm_hold_mon[n4d_group][n4d_slice][n4d_buf] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[n4d_buf]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .buf2arm_valid_hold;
"""
    new = """                // Package-local, interface-derived hold-set pressure.
                // Avoid a production-XMR dependency on the private hold register.
                assign n4d_arm_hold_mon[n4d_group][n4d_slice][n4d_buf] =
                    u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[n4d_buf]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .buf2arm_rvalid &
                    !u_NDP_Top_new
                        .slice_with_datahub_mc_group_gen[n4d_group]
                        .u_slice_with_datahub_mc_group
                        .slice_group_gen[n4d_slice]
                        .u_slice_wrapper.u_Slice.u_LSU
                        .u_Buffer_Manager_Cluster.BUFFER_MANAGER[n4d_buf]
                        .u_Buffer_Manager.u_Array_Request_Manager
                        .array2arm_bp_post;
"""
    if text.count(old) != 1:
        raise BuildError("private observer XMR source block is not unique")
    updated = text.replace(old, new)
    if "buf2arm_valid_hold" in updated:
        raise BuildError("private observer XMR remains after transformation")
    observer.write_text(updated, encoding="utf-8", newline="\n")


def path_budget(package: Path) -> dict[str, Any]:
    runtime = package / "workload/runtime"
    projections = [
        (
            f"install/cfg_pkg/{INSTALL_NAME}/"
            f"{path.relative_to(runtime).as_posix()}"
        )
        for path in runtime.rglob("*")
        if path.is_file()
    ]
    projections.extend(
        [
            f"run_{INSTALL_NAME}/compile/sim_results/compile_driver.log",
            f"run_{INSTALL_NAME}/c0/return_observer.log",
            f"evidence_{INSTALL_NAME}/production_rtl_identity.json",
            f"{INSTALL_NAME}_return/runs/c0/return_observer.log",
        ]
    )
    longest = max(projections, key=len)
    projected = SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
    if projected > ABSOLUTE_PATH_LIMIT_CHARS:
        raise BuildError("projected server path exceeds hard limit")
    inner = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file() and path.name != "package_manifest.json"
    ]
    return {
        "rule_id": "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
        "declared_target_root_max_chars": SERVER_ROOT_BUDGET_CHARS,
        "max_projected_absolute_path_limit_chars": ABSOLUTE_PATH_LIMIT_CHARS,
        "max_projected_absolute_path_chars": projected,
        "max_projected_relative_path_chars": len(longest),
        "longest_projected_relative_path": longest,
        "max_zip_member_chars": max(
            len(f"{INSTALL_NAME}/{relative}") for relative in inner
        ),
        "max_inner_suffix_chars": max(map(len, inner)),
        "max_inner_depth": max(
            len(PurePosixPath(item).parts) for item in inner
        ),
        "max_inner_component_chars": max(
            len(component)
            for item in inner
            for component in PurePosixPath(item).parts
        ),
        "outer_identity_repeated_inside": False,
        "exceptions": [
            {
                "scope": "workload/runtime/runs/c0/install/**",
                "reason": (
                    "exact p5 c0 causal workload and simulator SCA ABI are "
                    "retained; projected absolute maximum remains below 240"
                ),
                "semantic_change_if_renamed": (
                    "would alter exact causal-slice SCA consumer paths"
                ),
            }
        ],
        "actual_server_guard": (
            "runtime recomputes normalized user-root path budget before "
            "creating install/run/evidence namespaces"
        ),
    }


def update_manifest(package: Path, source_manifest: dict[str, Any]) -> None:
    manifest = json.loads(
        json.dumps(source_manifest).replace(SOURCE_NAME, INSTALL_NAME)
    )
    analysis = json.loads(RETURN_ANALYSIS.read_text(encoding="utf-8"))
    observer = package / "tb_probe/native_return_observer.svh"
    manifest.update(
        {
            "schema": (
                "resnet50-conv-native-four-lane-e1fb0f7-"
                "c0diag-armif-server-package-v1"
            ),
            "install_name": INSTALL_NAME,
            "simulation_run_count": 1,
            "run_namespace": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return.zip",
            "files": {},
        }
    )
    manifest["observer_binding"].update(
        {
            "source_sha256": sha256(observer),
            "armhold_semantics": (
                "raw interface-derived hold-set pressure level: "
                "buf2arm_rvalid & !array2arm_bp_post"
            ),
            "private_state_xmr": False,
        }
    )
    manifest["progress_diagnostics"]["qualified_boundaries"] = [
        value.replace(
            "request/response/hold/finish",
            "request/response/finish plus raw interface hold-set pressure",
        )
        for value in manifest["progress_diagnostics"]["qualified_boundaries"]
    ]
    manifest["candidate_decision_matrix"] = [
        {
            **value,
            "distinguishing_result": value["distinguishing_result"].replace(
                "queue full/hold/backpressure",
                "queue full/interface-derived hold-set pressure/backpressure",
            ),
        }
        for value in manifest["candidate_decision_matrix"]
    ]
    manifest["return_allowlist_contract"]["success_required"] = [
        "evidence/production_rtl_identity.json",
        "evidence/feature_binding/c0.json",
        "evidence/natural_terminal/c0.json",
        "runs/c0/simulator_argv.txt",
        "runs/c0/return_observer.log",
    ]
    manifest["source_return_analysis"] = {
        "path": RETURN_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": sha256(RETURN_ANALYSIS),
        "formal_return_sha256": analysis["outer_return_identity"]["sha256"],
        "classification": analysis["classification"],
        "failure_diameter": analysis["failure_localization"]["FD"],
        "claim_boundary": "compile failed before simulation; no c0/320D result",
    }
    manifest["delivery_and_workload_provenance"].update(
        {
            "source_p5_zip_sha256": SOURCE_ZIP_SHA256,
            "p5_content_relation": (
                "all non-manifest members identical except install identity "
                "normalization in runtime/runner/TEST manifest/SCA pair and "
                "the diagnostic README plus the single package observer "
                "private-XMR replacement"
            ),
        }
    )
    manifest["delivery_successor"] = {
        "source_package": f"{SOURCE_NAME}.zip",
        "source_sha256": SOURCE_ZIP_SHA256,
        "source_return_analysis_sha256": sha256(RETURN_ANALYSIS),
        "classification": "FRESH_PACKAGE_OBSERVER_XMR_SUCCESSOR",
        "functional_or_numeric_change": False,
        "changes": [
            "fresh short install/run/return identity",
            (
                "replace observer-only private buf2arm_valid_hold XMR by "
                "buf2arm_rvalid & !array2arm_bp_post"
            ),
            "correct c0-only manifest run/return scope",
        ],
    }
    manifest["workload_provenance"].update(
        {
            "package_builder": Path(__file__).relative_to(ROOT).as_posix(),
            "package_builder_sha256": sha256(Path(__file__)),
            "command": (
                ".venv/Scripts/python.exe -B "
                "tools/build_conv_native_four_lane_e1fb0f7_p6_armif_package.py"
            ),
            "source_p5_zip_sha256": SOURCE_ZIP_SHA256,
            "source_p5_return_analysis_sha256": sha256(RETURN_ANALYSIS),
            "observer_source_sha256": sha256(observer),
        }
    )
    manifest["rule_receipts"] = {
        relative: sha256(ROOT / relative) for relative in RULE_PATHS
    }
    manifest["rule_feedback"] = {
        "type": "RULE_CONFIRMATION",
        "confirmed": [
            "production compile/elaboration evidence stays below simulation claims",
            "fresh successor identity is required after a returned package failure",
            "package-local observer changes do not authorize functional RTL edits",
            "diagnostic c0 scope carries no formal 320D or E3/E4/E5 claim",
            "final-ZIP exact-set, actual-consumer, path-budget and return gates",
        ],
        "rule_delta_proposal": [],
    }
    manifest["path_length_budget"] = path_budget(package)
    manifest["files"] = records(package)
    write_json(package / "package_manifest.json", manifest)


def materialize(target: Path) -> tuple[Path, dict[str, Any]]:
    extracted = safe_extract(SOURCE_ZIP, target)
    source_manifest = json.loads(
        (extracted / "package_manifest.json").read_text(encoding="utf-8")
    )
    package = target / INSTALL_NAME
    extracted.rename(package)
    identity_files = [
        "package_tools/node0004_assumed_hardware_server_runtime.py",
        "PREPARE_AND_RUN.sh",
        "TEST_PACKAGE_MANIFEST.json",
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    ]
    for relative in identity_files:
        replace_identity(package / relative)
    (package / "README.md").write_text(
        README_TEXT, encoding="utf-8", newline="\n"
    )
    replace_private_xmr(package / "tb_probe/native_return_observer.svh")
    update_manifest(package, source_manifest)
    stale_identity = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
        and path.name != "package_manifest.json"
        and SOURCE_NAME.encode() in path.read_bytes()
    ]
    private_hits = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
        and path.name not in {"package_manifest.json", "README.md"}
        and b"buf2arm_valid_hold" in path.read_bytes()
    ]
    if stale_identity or private_hits:
        raise BuildError(
            f"stale source identity/private XMR: {stale_identity}/{private_hits}"
        )
    source_files = source_manifest["files"]
    target_files = records(package)
    changed = sorted(
        path
        for path in set(source_files) & set(target_files)
        if source_files[path] != target_files[path]
    )
    relation = {
        "source_file_count": len(source_files),
        "target_file_count": len(target_files),
        "missing": sorted(set(source_files) - set(target_files)),
        "extra": sorted(set(target_files) - set(source_files)),
        "changed": changed,
        "expected_changed": sorted(
            identity_files
            + ["README.md", "tb_probe/native_return_observer.svh"]
        ),
    }
    relation["valid"] = (
        not relation["missing"]
        and not relation["extra"]
        and relation["changed"] == relation["expected_changed"]
    )
    if not relation["valid"]:
        raise BuildError(f"unexpected source relation: {relation}")
    return package, relation


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(
            item for item in package.rglob("*") if item.is_file()
        ):
            relative = f"{package.name}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, (2026, 8, 5, 0, 0, 0))
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def build() -> dict[str, Any]:
    if sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise BuildError("exact p5 source ZIP identity mismatch")
    analysis = json.loads(RETURN_ANALYSIS.read_text(encoding="utf-8"))
    if not analysis.get("valid"):
        raise BuildError("p5 return analysis is not valid")
    package_path = OUTPUT_ROOT / INSTALL_NAME
    zip_path = OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    receipt_path = OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, receipt_path):
        if path.exists():
            raise BuildError(f"refusing to overwrite: {path}")
    with tempfile.TemporaryDirectory(prefix="n4-p6-a-") as first_name, (
        tempfile.TemporaryDirectory(prefix="n4-p6-b-")
    ) as second_name:
        first, first_relation = materialize(Path(first_name))
        second, second_relation = materialize(Path(second_name))
        first_zip = Path(first_name) / f"{INSTALL_NAME}.zip"
        second_zip = Path(second_name) / f"{INSTALL_NAME}.zip"
        deterministic_zip(first, first_zip)
        deterministic_zip(second, second_zip)
        if (
            sha256(first_zip) != sha256(second_zip)
            or records(first, include_manifest=True)
            != records(second, include_manifest=True)
            or first_relation != second_relation
        ):
            raise BuildError("deterministic dual build differs")
        shutil.copytree(first, package_path)
        shutil.copy2(first_zip, zip_path)
    zip_sha = sha256(zip_path)
    sidecar.write_text(
        f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    receipt = {
        "schema": "conv-native-four-lane-p6-armif-build-v1",
        "status": "PACKAGE_READY_NOT_RUN",
        "valid": True,
        "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "package": str(package_path),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha,
        "sidecar": str(sidecar),
        "sidecar_sha256": sha256(sidecar),
        "source_p5_zip_sha256": SOURCE_ZIP_SHA256,
        "source_p5_return_analysis_sha256": sha256(RETURN_ANALYSIS),
        "deterministic_dual_build": True,
        "source_relation": first_relation,
        "functional_or_numeric_change": False,
        "server_action": False,
    }
    write_json(receipt_path, receipt)
    return receipt


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
