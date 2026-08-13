#!/usr/bin/env python3
"""Build the p7 cloud-authority, identity-nonblocking c0 successor."""

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
SOURCE_NAME = "r5_n4_e1f_p6_armif"
INSTALL_NAME = "r5_n4_0cc_p7"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = (
    "05fc4f385d544195ad3cbc68256525d70775cc490d4a42ff784e9b9f7c5d34c1"
)
P6_RETURN_ANALYSIS = (
    ROOT / "outputs/conv_native_four_lane_e1fb0f7_p6_return_analysis/report.json"
)
P6_RETURN_ANALYSIS_SHA256 = (
    "de253112fde6a0948bdb9ee2c0eeca01828ecae7b7ebe99573a819d4641a8e67"
)
CLOUD_AUDIT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_cloud_causal_cone/report.json"
)
CLOUD_COMMIT = "0ccae916ef61904a64d6cf8ec1d1931b45e428d8"
LOCAL_COMMIT = "e1fb0f7bb2761d6c804867de0c5d2cb77554c48d"
FORMAL_P6_RETURN_SHA256 = (
    "9c590ae7ae17b55ef3471032dc8b3471bbf949e07eeb1a9dd61b0639fd5ccf59"
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

README_TEXT = """# Conv node0004 native-four-lane cloud-RTL c0 diagnostic p7

This fresh successor preserves the exact p6 c0 workload, materialized config,
bitstream, execplan, SCA and public-interface observer semantics.  It changes
only package/bootstrap identity handling: after a successful production
compile, actual leaf hashes are collected and returned, but any difference
from the local e1fb0f7 provenance hint or the approved cloud 0ccae916 identity
does not prevent simulator launch.

Run exactly once from a cleanly extracted package root:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/server_root
```

This is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`, contains no functional RTL and no
formal 320D payload, and claims no E3/E4/E5.  The sole dynamic question is the
c0 exec-to-slice_finish boundary under the server's actually compiled RTL.
"""


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


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
            pure = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or pure.parts[0] != SOURCE_NAME
                or info.filename in seen
                or stat.S_ISLNK(mode)
            ):
                raise BuildError(f"unsafe source ZIP member: {info.filename}")
            seen.add(info.filename)
        archive.extractall(target)
    source_root = target / SOURCE_NAME
    if not source_root.is_dir():
        raise BuildError("source ZIP did not produce declared root")
    return source_root


def replace_identity(path: Path) -> None:
    payload = path.read_bytes()
    old = SOURCE_NAME.encode()
    if old not in payload:
        raise BuildError(f"source identity absent: {path}")
    path.write_bytes(payload.replace(old, INSTALL_NAME.encode()))


def transform_runtime(path: Path, cloud_leaves: dict[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(SOURCE_NAME, INSTALL_NAME)
    schema_old = "conv-native-four-lane-e1fb0f7-c0diag"
    schema_new = "conv-native-four-lane-0ccae916-c0diag"
    text = text.replace(schema_old, schema_new)

    parsing_anchor = (
        'PARSING_RE = re.compile(r"Parsing design file '
        '[\'\\"]([^\'\\"]+)[\'\\"]")\n'
    )
    cloud_constants = (
        f'CLOUD_AUTHORITY_COMMIT = "{CLOUD_COMMIT}"\n'
        "CLOUD_AUTHORITY_LEAVES = "
        + json.dumps(cloud_leaves, indent=4)
        + "\n"
        + parsing_anchor
    )
    if text.count(parsing_anchor) != 1:
        raise BuildError("runtime parsing anchor differs")
    text = text.replace(parsing_anchor, cloud_constants)

    preflight_old = """        or manifest.get("expected_production_rtl_identity", {}).get("leaves")
        != EXPECTED_LEAVES
    ):
        raise RuntimeErrorContract("p5 diagnostic identity differs")
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
    ):
        raise RuntimeErrorContract("p7 diagnostic identity differs")
"""
    if text.count(preflight_old) != 1:
        raise BuildError("runtime preflight identity block differs")
    text = text.replace(preflight_old, preflight_new)

    start = text.index("def collect_compile_identity(")
    end = text.index("\ndef qualify_run(", start)
    collect_new = '''def collect_compile_identity(
    compile_log: Path, output: Path
) -> dict[str, Any]:
    """Collect actual compile identity without gating simulator launch."""
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
        path = Path(matches[0])
        if not path.is_file():
            collection_errors.append(f"{basename}: compiled path unreadable")
            continue
        observed = sha256(path)
        cloud_expected = CLOUD_AUTHORITY_LEAVES[basename]
        leaves[basename] = {
            "compiled_path": str(path),
            "size_bytes": path.stat().st_size,
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
        authority_classification = "COLLECTION_INCOMPLETE"
    elif differs_cloud:
        authority_classification = "ACTUAL_DIFFERS_CURRENT_CLOUD"
    else:
        authority_classification = "ACTUAL_MATCHES_CURRENT_CLOUD"
    receipt = {
        "schema": (
            "conv-native-four-lane-0ccae916-c0diag-"
            "production-identity-v1"
        ),
        "valid": collection_valid,
        "collection_valid": collection_valid,
        "collection_errors": collection_errors,
        "compile_log": str(compile_log),
        "compile_log_sha256": sha256(compile_log),
        "local_provenance_commit": EXPECTED_COMMIT,
        "cloud_authority_commit": CLOUD_AUTHORITY_COMMIT,
        "actual_differs_local_provenance": differs_local,
        "actual_differs_cloud_authority": differs_cloud,
        "authority_classification": authority_classification,
        "identity_difference_blocks_simulator": False,
        "identity_source": (
            "actual VCS parsing receipts followed by post-compile leaf hashing"
        ),
        "precompile_server_source_preflight": False,
        "leaves": leaves,
    }
    write_json(output, receipt)
    return receipt

'''
    text = text[:start] + collect_new + text[end + 1 :]
    result_old = (
        '            "actual_compile_identity_match": '
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
        raise BuildError("runtime analyze identity result block differs")
    text = text.replace(result_old, result_new)
    path.write_text(text, encoding="utf-8", newline="\n")


def transform_runner(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(SOURCE_NAME, INSTALL_NAME)
    old = """python3 "$runtime" compile-identity   --compile-log "$run_root/compile/sim_results/compile_driver.log"   --output "$evidence_root/production_rtl_identity.json" || exit 8
simv="$run_root/compile/sim_results/simv"
"""
    new = """# Actual/local/cloud SHA differences are post-compile evidence only.
# The identity collector writes a receipt but never gates simulator launch.
python3 "$runtime" compile-identity   --compile-log "$run_root/compile/sim_results/compile_driver.log"   --output "$evidence_root/production_rtl_identity.json" >/dev/null 2>&1 || true
simv="$run_root/compile/sim_results/simv"
"""
    if text.count(old) != 1:
        raise BuildError("runner blocking identity block differs")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def path_budget(package: Path) -> dict[str, Any]:
    runtime = package / "workload/runtime"
    projections = [
        f"install/cfg_pkg/{INSTALL_NAME}/{path.relative_to(runtime).as_posix()}"
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
        "actual_server_guard": (
            "runtime recomputes normalized user-root path budget before "
            "creating install/run/evidence namespaces"
        ),
    }


def update_provenance(
    package: Path,
    local_leaves: dict[str, str],
    cloud_leaves: dict[str, str],
    cloud_audit_sha: str,
) -> None:
    write_json(
        package / "provenance/current_local_rtl_binding.json",
        {
            "schema": (
                "conv-native-four-lane-0ccae916-c0diag-rtl-binding-v1"
            ),
            "local_provenance": {
                "commit": LOCAL_COMMIT,
                "leaves": local_leaves,
                "role": "provenance_hint_only",
                "identity_difference_blocks_simulator": False,
            },
            "cloud_authority": {
                "repository": "xlsjdjdk/Trassic2.0_RTL",
                "branch": "master",
                "approved_commit": CLOUD_COMMIT,
                "leaves": cloud_leaves,
                "causal_audit_sha256": cloud_audit_sha,
                "identity_difference_blocks_simulator": False,
            },
            "receipt_timing": "after actual production compile",
            "precompile_server_source_preflight": False,
            "functional_rtl_in_package": False,
        },
    )


def update_manifest(
    package: Path,
    source_manifest: dict[str, Any],
    cloud_audit: dict[str, Any],
) -> None:
    manifest = json.loads(
        json.dumps(source_manifest).replace(SOURCE_NAME, INSTALL_NAME)
    )
    local_identity = source_manifest["expected_production_rtl_identity"]
    cloud_leaves = {
        name: value["sha256"]
        for name, value in cloud_audit[
            "cloud_expected_compiled_leaves"
        ].items()
    }
    manifest.update(
        {
            "schema": (
                "resnet50-conv-native-four-lane-0ccae916-"
                "c0diag-cloud-nonblocking-server-package-v1"
            ),
            "status": "PACKAGE_READY_NOT_RUN",
            "package_release": "PACKAGE_READY_NOT_RUN",
            "install_name": INSTALL_NAME,
            "run_namespace": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return.zip",
            "files": {},
        }
    )
    manifest["expected_production_rtl_identity"] = {
        "commit": local_identity["commit"],
        "leaves": local_identity["leaves"],
        "role": "local_provenance_hint_only",
        "expected_byte_identity": "immutable Git blob bytes",
        "receipt_timing": "after actual production VCS compile",
        "precompile_server_source_preflight": False,
        "identity_difference_blocks_compile_or_simulation": False,
    }
    manifest["cloud_rtl_authority"] = {
        "rule_id": (
            "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-"
            "NONBLOCKING-DIFF-001"
        ),
        "repository": "xlsjdjdk/Trassic2.0_RTL",
        "branch": "master",
        "approved_commit": CLOUD_COMMIT,
        "base_local_commit": LOCAL_COMMIT,
        "leaves": cloud_leaves,
        "identity_difference_blocks_compile_or_simulation": False,
        "actual_identity_receipt_timing": (
            "after successful production compile, before simulator launch"
        ),
        "classification_timing": "formal return analysis",
    }
    manifest["source_return_analysis"] = {
        "path": P6_RETURN_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": P6_RETURN_ANALYSIS_SHA256,
        "formal_return_sha256": FORMAL_P6_RETURN_SHA256,
        "historical_classification": (
            "TERMINAL_NO_PACKAGE_SERVER_RTL_IDENTITY_MISMATCH"
        ),
        "superseded_by_current_rule": True,
        "current_classification": (
            "SUCCESSOR_REQUIRED_CLOUD_RTL_NONBLOCKING"
        ),
        "claim_boundary": (
            "p6 compiled but did not launch c0; p7 does not reuse p6 as a "
            "dynamic result"
        ),
    }
    manifest["cloud_causal_cone_audit"] = {
        "path": CLOUD_AUDIT.relative_to(ROOT).as_posix(),
        "sha256": sha256(CLOUD_AUDIT),
        "status": cloud_audit["status"],
        "direct_changed_compiled_leaves": [
            name
            for name, value in cloud_audit[
                "cloud_expected_compiled_leaves"
            ].items()
            if value["changed_from_local_base"]
        ],
        "numeric_w3_golden_repeated": False,
        "local_e2_repeated": False,
        "dynamic_claim_boundary": cloud_audit[
            "causal_classification"
        ]["dynamic_claim_boundary"],
    }
    manifest["delivery_successor"] = {
        "source_package": f"{SOURCE_NAME}.zip",
        "source_sha256": SOURCE_ZIP_SHA256,
        "classification": (
            "FRESH_CLOUD_RTL_IDENTITY_NONBLOCKING_SUCCESSOR"
        ),
        "functional_or_numeric_change": False,
        "changes": [
            "fresh short install/run/return identity",
            (
                "actual/local/cloud post-compile SHA differences are returned "
                "and never block simulator launch"
            ),
            "bind approved cloud commit and targeted causal-cone audit",
            "current rule receipts and release-gate applicability",
        ],
    }
    manifest["delivery_and_workload_provenance"].update(
        {
            "source_p6_zip_sha256": SOURCE_ZIP_SHA256,
            "p6_content_relation": (
                "all workload/config/bitstream/execplan/SCA payload bytes "
                "retained; only SCA install identity normalized"
            ),
            "numeric_w3_golden_repeated": False,
            "local_e2_repeated": False,
        }
    )
    observer = package / "tb_probe/native_return_observer.svh"
    manifest["observer_binding"].update(
        {
            "source_sha256": sha256(observer),
            "source_relation_to_p6": "byte_equal",
            "private_state_xmr": False,
        }
    )
    manifest["workload_provenance"].update(
        {
            "package_builder": Path(__file__).relative_to(ROOT).as_posix(),
            "package_builder_sha256": sha256(Path(__file__)),
            "command": (
                ".venv/Scripts/python.exe -B "
                "tools/build_conv_native_four_lane_0ccae916_"
                "p7_cloudnb_package.py"
            ),
            "source_p6_zip_sha256": SOURCE_ZIP_SHA256,
            "cloud_causal_cone_audit_sha256": sha256(CLOUD_AUDIT),
            "observer_source_sha256": sha256(observer),
        }
    )
    manifest["rule_receipts"] = {
        relative: sha256(ROOT / relative) for relative in RULE_PATHS
    }
    manifest["rule_feedback"] = {
        "type": "RULE_CONFIRMATION",
        "confirmed": [
            (
                "successful compile followed by an actual/local/cloud SHA "
                "difference must still launch simulation"
            ),
            (
                "changed cloud RTL is audited only within the current "
                "operator causal cone"
            ),
            (
                "unchanged numeric/W3/golden/materialized config receipts "
                "are reused without repetition"
            ),
            "package-local observer and functional RTL remain byte-frozen",
            "formal 320D and E3/E4/E5 remain outside c0 diagnostic scope",
        ],
        "rule_delta_proposal": [],
    }
    manifest["release_gate_applicability"] = {
        "core_package_bootstrap_path": "applicable",
        "runner_compile_finalizer": "applicable",
        "return_result_joint_gate": "applicable",
        "cloud_identity_nonblocking_positive_control": "applicable",
        "package_local_hdl": "receipt_reuse_byte_equal",
        "materialized_config": (
            "not_applicable_byte_equal_receipt_reuse; "
            "causal ledger and config boundary microtrace not repeated"
        ),
        "diagnostic_predicate_trace": (
            "not_applicable_observer_parser_canonical_byte_equal"
        ),
        "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
    }
    manifest["path_length_budget"] = path_budget(package)
    manifest["files"] = records(package)
    write_json(package / "package_manifest.json", manifest)


def materialize(target: Path) -> tuple[Path, dict[str, Any]]:
    extracted = safe_extract(SOURCE_ZIP, target)
    source_manifest = json.loads(
        (extracted / "package_manifest.json").read_text(encoding="utf-8")
    )
    cloud_audit = json.loads(CLOUD_AUDIT.read_text(encoding="utf-8"))
    if not cloud_audit.get("valid"):
        raise BuildError("cloud causal-cone audit is not valid")
    cloud_leaves = {
        name: value["sha256"]
        for name, value in cloud_audit[
            "cloud_expected_compiled_leaves"
        ].items()
    }
    local_leaves = source_manifest[
        "expected_production_rtl_identity"
    ]["leaves"]

    package = target / INSTALL_NAME
    extracted.rename(package)
    transform_runtime(
        package
        / "package_tools/node0004_assumed_hardware_server_runtime.py",
        cloud_leaves,
    )
    transform_runner(package / "PREPARE_AND_RUN.sh")
    for relative in (
        "TEST_PACKAGE_MANIFEST.json",
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    ):
        replace_identity(package / relative)
    (package / "README.md").write_text(
        README_TEXT, encoding="utf-8", newline="\n"
    )
    update_provenance(
        package, local_leaves, cloud_leaves, sha256(CLOUD_AUDIT)
    )
    update_manifest(package, source_manifest, cloud_audit)

    stale = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
        and path.name != "package_manifest.json"
        and SOURCE_NAME.encode() in path.read_bytes()
    ]
    if stale:
        raise BuildError(f"stale source identity: {stale}")

    source_files = source_manifest["files"]
    target_files = records(package)
    changed = sorted(
        path
        for path in set(source_files) & set(target_files)
        if source_files[path] != target_files[path]
    )
    expected_changed = sorted(
        [
            "PREPARE_AND_RUN.sh",
            "README.md",
            "TEST_PACKAGE_MANIFEST.json",
            (
                "package_tools/"
                "node0004_assumed_hardware_server_runtime.py"
            ),
            "provenance/current_local_rtl_binding.json",
            "workload/runtime/runs/c0/sca_cfg.json",
            "workload/runtime/runs/c0/sca_cfg_D.json",
        ]
    )
    relation = {
        "source_file_count": len(source_files),
        "target_file_count": len(target_files),
        "missing": sorted(set(source_files) - set(target_files)),
        "extra": sorted(set(target_files) - set(source_files)),
        "changed": changed,
        "expected_changed": expected_changed,
        "observer_byte_equal": (
            source_files["tb_probe/native_return_observer.svh"]
            == target_files["tb_probe/native_return_observer.svh"]
        ),
        "workload_payload_change": False,
    }
    relation["valid"] = (
        not relation["missing"]
        and not relation["extra"]
        and changed == expected_changed
        and relation["observer_byte_equal"]
    )
    if not relation["valid"]:
        raise BuildError(f"unexpected p6 relation: {relation}")
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
        raise BuildError("exact p6 source ZIP identity mismatch")
    if sha256(P6_RETURN_ANALYSIS) != P6_RETURN_ANALYSIS_SHA256:
        raise BuildError("p6 return analysis identity mismatch")
    cloud_audit = json.loads(CLOUD_AUDIT.read_text(encoding="utf-8"))
    if (
        not cloud_audit.get("valid")
        or cloud_audit.get("status")
        != "SUCCESSOR_REQUIRED_CLOUD_RTL_NONBLOCKING"
    ):
        raise BuildError("cloud causal-cone audit does not release successor")

    package_path = OUTPUT_ROOT / INSTALL_NAME
    zip_path = OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    receipt_path = OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, receipt_path):
        if path.exists():
            raise BuildError(f"refusing to overwrite: {path}")

    with tempfile.TemporaryDirectory(prefix="n4-p7-a-") as first_name, (
        tempfile.TemporaryDirectory(prefix="n4-p7-b-")
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
        "schema": "conv-native-four-lane-0ccae916-p7-cloudnb-build-v1",
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
        "source_p6_zip_sha256": SOURCE_ZIP_SHA256,
        "p6_return_analysis_sha256": P6_RETURN_ANALYSIS_SHA256,
        "cloud_causal_cone_audit_sha256": sha256(CLOUD_AUDIT),
        "cloud_authority_commit": CLOUD_COMMIT,
        "deterministic_dual_build": True,
        "source_relation": first_relation,
        "functional_or_numeric_change": False,
        "numeric_w3_golden_repeated": False,
        "local_e2_repeated": False,
        "server_action": False,
    }
    write_json(receipt_path, receipt)
    return receipt


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
