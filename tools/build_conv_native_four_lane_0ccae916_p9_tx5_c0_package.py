#!/usr/bin/env python3
"""Build the p9 c0 transout-threshold functional-config successor."""

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
SOURCE_NAME = "r5_n4_0cc_p7"
INSTALL_NAME = "r5_n4_0cc_p9b_tx5"
SOURCE_ZIP = OUTPUT_ROOT / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = (
    "4ff473247a7356af3e6b960430b559e90113b774e27478dbcd41151d8507f8a4"
)
P8F_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p8f_return_analysis/report.json"
)
LOCAL_ROOT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-conv-native-four-lane-0cc-p9-tx5-c0"
)
LOCAL_REPORT = LOCAL_ROOT / "local_rebuild_report.json"
PIPELINE = LOCAL_ROOT / "execplan_conv/wave-0/pipeline_output"
RUN_TIMEOUT_SECONDS = 43200
SERVER_ROOT_BUDGET_CHARS = 96
ABSOLUTE_PATH_LIMIT_CHARS = 240
RULE_PATHS = [
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    ".agents/rules/算子配置规则.md",
    ".agents/rules/NDP硬件字段语义.md",
    ".agents/rules/INT8_SA点积专项规则.md",
    ".agents/rules/精确UINT8量化尾专项规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
]


class BuildError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


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


def safe_extract(target: Path) -> Path:
    if sha256(SOURCE_ZIP) != SOURCE_ZIP_SHA256:
        raise BuildError("exact p7 source ZIP identity mismatch")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("p7 source ZIP CRC failed")
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
    return target / SOURCE_NAME


def replace_identity(package: Path) -> None:
    old = SOURCE_NAME.encode()
    new = INSTALL_NAME.encode()
    for path in package.rglob("*"):
        if not path.is_file() or path.name == "package_manifest.json":
            continue
        payload = path.read_bytes()
        if old in payload:
            path.write_bytes(payload.replace(old, new))


def prefix_sca(path: Path) -> None:
    value = json.loads(path.read_text(encoding="utf-8"))
    prefix = f"install/cfg_pkg/{INSTALL_NAME}/runs/c0/"
    for item in value.values():
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            old = item["path"]
            if not old.startswith("install/") or ".." in PurePosixPath(old).parts:
                raise BuildError(f"unsafe regenerated SCA path: {old}")
            item["path"] = prefix + old
    write_json(path, value)


def inject_physical_assets(package: Path) -> dict[str, Any]:
    report = json.loads(LOCAL_REPORT.read_text(encoding="utf-8"))
    if (
        report.get("status") != "LOCAL_C0_PHYSICAL_REBUILD_PASS"
        or report.get("authorized_leaf_changes")
        != [
            {
                "path": "special_array.transout_last_index",
                "old": 2,
                "new": 5,
            }
        ]
        or report.get("old_ignored_occurrences") != 256
        or report.get("new_released_occurrences") != 256
    ):
        raise BuildError("local physical rebuild report does not release p9")
    run = package / "workload/runtime/runs/c0"
    copied: list[str] = []
    for relative in (
        "install/execplan.txt",
        "install/execplan_op_w0.txt",
        (
            "install/cfg_pkg/"
            "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
        ),
    ):
        source = PIPELINE / relative
        target = run / relative
        if not source.is_file() or not target.is_file():
            raise BuildError(f"physical replacement endpoint missing: {relative}")
        shutil.copy2(source, target)
        copied.append(relative)
    for relative in ("sca_cfg.json", "sca_cfg_D.json"):
        source = PIPELINE / relative
        target = run / relative
        shutil.copy2(source, target)
        prefix_sca(target)
        copied.append(relative)
    return {
        "local_rebuild_report": LOCAL_REPORT.relative_to(ROOT).as_posix(),
        "local_rebuild_report_sha256": sha256(LOCAL_REPORT),
        "causal_transaction_ledger_sha256": sha256(
            LOCAL_ROOT / "causal_transaction_ledger.json"
        ),
        "boundary_microtrace_sha256": sha256(
            LOCAL_ROOT / "boundary_microtrace.json"
        ),
        "copied_physical_assets": copied,
    }


def update_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    old = (
        'timeout --foreground --signal=TERM --kill-after=30s 1h "$simv"'
    )
    new = (
        'timeout --foreground --signal=TERM --kill-after=30s 12h "$simv"'
    )
    if text.count(old) != 1:
        raise BuildError("p7 one-hour simulator timeout anchor differs")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def update_runtime_contract(package: Path) -> None:
    path = (
        package
        / "package_tools/node0004_assumed_hardware_server_runtime.py"
    )
    text = path.read_text(encoding="utf-8")
    old = (
        'manifest.get("candidate_class")\n'
        '        != "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX"'
    )
    new = (
        'manifest.get("candidate_class")\n'
        '        != "CONFIG_FUNCTIONAL_FIX_WITH_PUBLIC_CAUSAL_DIAGNOSTICS"'
    )
    if text.count(old) != 1:
        raise BuildError("runtime candidate-class preflight anchor differs")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def path_budget(package: Path) -> dict[str, Any]:
    runtime = package / "workload/runtime"
    projected_relatives = [
        f"install/cfg_pkg/{INSTALL_NAME}/{path.relative_to(runtime).as_posix()}"
        for path in runtime.rglob("*")
        if path.is_file()
    ]
    projected_relatives.extend(
        [
            f"run_{INSTALL_NAME}/compile/sim_results/compile_driver.log",
            f"run_{INSTALL_NAME}/c0/return_observer.log",
            f"evidence_{INSTALL_NAME}/production_rtl_identity.json",
            f"{INSTALL_NAME}_return/runs/c0/return_observer.log",
        ]
    )
    longest = max(projected_relatives, key=len)
    absolute = SERVER_ROOT_BUDGET_CHARS + 1 + len(longest)
    inner = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file() and path.name != "package_manifest.json"
    ]
    receipt = {
        "rule_id": "CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001",
        "declared_target_root_max_chars": SERVER_ROOT_BUDGET_CHARS,
        "max_projected_absolute_path_limit_chars": ABSOLUTE_PATH_LIMIT_CHARS,
        "max_projected_absolute_path_chars": absolute,
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
            "runtime recomputes normalized user-root path budget before writes"
        ),
    }
    if absolute > ABSOLUTE_PATH_LIMIT_CHARS:
        raise BuildError(f"path budget exceeded: {receipt}")
    return receipt


def readme() -> str:
    return f"""# Conv node0004 native-four-lane p9 terminal-threshold fix

This fresh c0 successor repairs the previously proven terminal classifier
configuration error:

```text
special_array.transout_last_index: 2 -> 5
```

The final config, mapping, bitstream, execplan and SCA were regenerated.  The
only bitstream differences from p7 are offsets 4459, 4460 and 4461.  Frozen
numeric/W3/golden data, matrix payloads, addresses, public-interface observer
and functional RTL are unchanged.  The server timeout is 12 hours so c0 can
reach the historically observed terminal boundary without manual extension.

Run exactly once from a clean extraction:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/server_root
```

Expected return: `{INSTALL_NAME}_return.zip`.

This is a non-release c0 config-functional-fix candidate.  It does not contain
the formal 320D full-chain scope and claims no E3/E4/E5 or measured server
performance.
"""


def update_manifest(
    package: Path,
    source_manifest: dict[str, Any],
    injection: dict[str, Any],
) -> None:
    manifest = json.loads(
        json.dumps(source_manifest).replace(SOURCE_NAME, INSTALL_NAME)
    )
    p8f = json.loads(P8F_ANALYSIS.read_text(encoding="utf-8"))
    if (
        not p8f.get("valid")
        or p8f.get("status")
        != "LONG_RUNNING_HANG_CONFIG_FIX_SUCCESSOR_REQUIRED"
    ):
        raise BuildError("p8f analysis does not authorize successor")
    manifest.update(
        {
            "schema": (
                "resnet50-conv-native-four-lane-0ccae916-"
                "p9-transout5-c0-server-package-v1"
            ),
            "status": "PACKAGE_READY_NOT_RUN",
            "package_release": "PACKAGE_READY_NOT_RUN",
            "install_name": INSTALL_NAME,
            "run_namespace": f"run_{INSTALL_NAME}",
            "return_name": f"{INSTALL_NAME}_return.zip",
            "candidate_class": (
                "CONFIG_FUNCTIONAL_FIX_WITH_PUBLIC_CAUSAL_DIAGNOSTICS"
            ),
            "candidate_release": False,
            "evidence_level": "E2_RECEIPT_REUSE_PLUS_CONFIG_BOUND_REBUILD",
            "formal_readback_claimed": False,
            "functional_rtl_modified": False,
            "server_rtl_entries": 0,
            "server_action": False,
            "files": {},
        }
    )
    manifest["progress_diagnostics"]["run_timeout_seconds"] = (
        RUN_TIMEOUT_SECONDS
    )
    manifest["source_p8f_return_analysis"] = {
        "path": P8F_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": sha256(P8F_ANALYSIS),
        "formal_return_sha256": (
            "7a2de4c7551f40ed8ab4c82bd6a6efddd985c8e70a6704e9cdc451d2a4d870b9"
        ),
        "status": p8f["status"],
        "last_proven_good": p8f["failure_localization"]["LAST_PROVEN_GOOD"],
        "first_divergence": p8f["failure_localization"]["FIRST_DIVERGENCE"],
        "root_cause_uniqueness": p8f["failure_localization"][
            "root_cause_uniqueness"
        ],
    }
    manifest["configuration_fix"] = {
        "logical_leaf_changes": [
            {
                "path": "special_array.transout_last_index",
                "old": 2,
                "new": 5,
            }
        ],
        "historical_accepted_terminal_histogram": {"4": 64, "5": 192},
        "old_threshold2": {"released": 0, "ignored": 256},
        "new_threshold5": {"released": 256, "ignored": 0},
        "bitstream_changed_offsets": [4459, 4460, 4461],
        "addresses_changed": False,
        "matrix_payloads_changed": False,
        **injection,
    }
    manifest["successor_candidate_matrix"] = {
        "same_early_public_boundary_freeze": (
            "actual ARM/source path remains first dynamic divergence"
        ),
        "reaches_sa_output_or_buffer5": (
            "terminal threshold repair crossed the old boundary"
        ),
        "natural_c0_terminal": (
            "advance one fresh successor to full 27/320 formal scope"
        ),
    }
    manifest["delivery_successor"] = {
        "source_package": f"{SOURCE_NAME}.zip",
        "source_sha256": SOURCE_ZIP_SHA256,
        "changes": [
            "fresh short identity",
            "transout_last_index 2 to 5 and regenerated physical consumers",
            "simulator timeout 1h to 12h",
        ],
        "public_observer_relation": "byte_equal",
        "numeric_w3_golden_repeated": False,
        "functional_rtl_changed": False,
    }
    manifest["workload_provenance"].update(
        {
            "package_builder": Path(__file__).relative_to(ROOT).as_posix(),
            "package_builder_sha256": sha256(Path(__file__)),
            "command": (
                ".venv/Scripts/python.exe -B "
                "tools/build_conv_native_four_lane_0ccae916_"
                "p9_tx5_c0_package.py"
            ),
            "source_p7_zip_sha256": SOURCE_ZIP_SHA256,
            "p8f_return_analysis_sha256": sha256(P8F_ANALYSIS),
            "p9_local_rebuild_report_sha256": sha256(LOCAL_REPORT),
        }
    )
    manifest["observer_binding"].update(
        {
            "source_relation_to_p7": "byte_equal",
            "private_state_xmr": False,
        }
    )
    manifest["rule_receipts"] = {
        relative: sha256(ROOT / relative) for relative in RULE_PATHS
    }
    manifest["release_gate_matrix"] = {
        "schema": "cda-server-local-release-gate-impact-applicability-v1",
        "core_package_bootstrap_path": {
            "applicability": "blocking_applicable",
            "result": "PASS",
        },
        "runner_compile_finalizer": {
            "applicability": "blocking_applicable",
            "reason": "simulator timeout changed; exact runner tests required",
        },
        "package_local_hdl": {
            "applicability": "receipt_reuse",
            "reason": "public observer is byte-equal to production-compiled p7",
        },
        "materialized_config": {
            "applicability": "blocking_applicable",
            "result": "PASS",
            "causal_transaction_ledger_sha256": injection[
                "causal_transaction_ledger_sha256"
            ],
            "boundary_microtrace_sha256": injection[
                "boundary_microtrace_sha256"
            ],
            "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
        },
        "diagnostic_observer_canonical_semantics": {
            "applicability": "receipt_reuse",
            "reason": "observer/parser/canonical predicates byte-equal to p7",
        },
        "return_result_joint_gate": {
            "applicability": "blocking_applicable",
            "reason": "fresh namespace and finalizer return must be verified",
        },
        "numeric_w3_golden": {
            "applicability": "record_only",
            "reason": "all frozen numeric payloads byte-equal",
        },
    }
    manifest["rule_feedback"] = {
        "type": "RULE_CONFIRMATION",
        "confirmed": [
            "CDA-CONFIG-CAUSAL-TRANSACTION-LEDGER-001",
            "CDA-CONFIG-BOUNDARY-MICROTRACE-001",
            "CDA-CONFIG-PHYSICAL-BANK-ROW-VALIDITY-001",
            "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
            "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
            "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
        ],
        "rule_delta_proposal": [],
    }
    manifest["path_length_budget"] = path_budget(package)
    manifest["files"] = records(package)
    write_json(package / "package_manifest.json", manifest)


def materialize(target: Path) -> tuple[Path, dict[str, Any]]:
    extracted = safe_extract(target)
    source_manifest = json.loads(
        (extracted / "package_manifest.json").read_text(encoding="utf-8")
    )
    package = target / INSTALL_NAME
    extracted.rename(package)
    replace_identity(package)
    update_runtime_contract(package)
    update_runner(package)
    injection = inject_physical_assets(package)
    (package / "README.md").write_text(
        readme(), encoding="utf-8", newline="\n"
    )
    update_manifest(package, source_manifest, injection)
    stale = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
        and path.name != "package_manifest.json"
        and SOURCE_NAME.encode() in path.read_bytes()
    ]
    if stale:
        raise BuildError(f"stale p7 identity remains: {stale}")
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
            "package_tools/node0004_assumed_hardware_server_runtime.py",
            (
                "workload/runtime/runs/c0/install/cfg_pkg/"
                "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
            ),
            "workload/runtime/runs/c0/sca_cfg.json",
            "workload/runtime/runs/c0/sca_cfg_D.json",
        ]
    )
    relation = {
        "missing": sorted(set(source_files) - set(target_files)),
        "extra": sorted(set(target_files) - set(source_files)),
        "changed": changed,
        "expected_changed": expected_changed,
        "observer_byte_equal": (
            source_files["tb_probe/native_return_observer.svh"]
            == target_files["tb_probe/native_return_observer.svh"]
        ),
        "execplan_byte_equal": (
            source_files["workload/runtime/runs/c0/install/execplan.txt"]
            == target_files["workload/runtime/runs/c0/install/execplan.txt"]
        ),
        "matrix_payloads_byte_equal": all(
            source_files[path] == target_files[path]
            for path in source_files
            if "matrix_" in path
        ),
    }
    relation["valid"] = (
        not relation["missing"]
        and not relation["extra"]
        and changed == expected_changed
        and relation["observer_byte_equal"]
        and relation["execplan_byte_equal"]
        and relation["matrix_payloads_byte_equal"]
    )
    if not relation["valid"]:
        raise BuildError(f"unexpected p7-to-p9 relation: {relation}")
    return package, relation


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sorted(
            item for item in package.rglob("*") if item.is_file()
        ):
            relative = f"{INSTALL_NAME}/{path.relative_to(package).as_posix()}"
            info = zipfile.ZipInfo(relative, (2026, 8, 6, 0, 0, 0))
            mode = 0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644
            info.external_attr = mode << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())


def build() -> dict[str, Any]:
    for required in (P8F_ANALYSIS, LOCAL_REPORT):
        if not required.is_file():
            raise BuildError(f"required evidence missing: {required}")
    package_path = OUTPUT_ROOT / INSTALL_NAME
    zip_path = OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    receipt_path = OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, receipt_path):
        if path.exists():
            raise BuildError(f"refusing to overwrite: {path}")
    with tempfile.TemporaryDirectory(prefix="n4-p9-a-") as first_name, (
        tempfile.TemporaryDirectory(prefix="n4-p9-b-")
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
    digest = sha256(zip_path)
    sidecar.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    receipt = {
        "schema": "conv-native-four-lane-0ccae916-p9-tx5-build-v1",
        "status": "PACKAGE_READY_NOT_RUN_PENDING_FINAL_AUDIT",
        "valid": True,
        "candidate_class": (
            "CONFIG_FUNCTIONAL_FIX_WITH_PUBLIC_CAUSAL_DIAGNOSTICS"
        ),
        "candidate_release": False,
        "package": str(package_path),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "sidecar_sha256": sha256(sidecar),
        "source_p7_zip_sha256": SOURCE_ZIP_SHA256,
        "p8f_return_analysis_sha256": sha256(P8F_ANALYSIS),
        "local_rebuild_report_sha256": sha256(LOCAL_REPORT),
        "deterministic_dual_build": True,
        "source_relation": first_relation,
        "numeric_w3_golden_repeated": False,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(receipt_path, receipt)
    return receipt


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
