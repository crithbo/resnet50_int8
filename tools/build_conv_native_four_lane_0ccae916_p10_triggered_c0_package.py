#!/usr/bin/env python3
"""Build the p10 bounded triggered-causal native-Conv c0 successor."""

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
SOURCE_NAME = "r5_n4_0cc_p9b_tx5"
INSTALL_NAME = "r5_n4_0cc_p10_trig"
SOURCE_ZIP = OUTPUT_ROOT / "pending" / f"{SOURCE_NAME}.zip"
SOURCE_ZIP_SHA256 = (
    "d85429b61e8270d0c4108bfdcdf3a66bce44a437b8aab96b0412a5555dffb085"
)
RETURN_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p9b_return_analysis/report.json"
)
OBSERVER_APPEND = (
    ROOT
    / "resnet50_pipeline/conv_native_four_lane_triggered_observer_append_v1.svh"
)
TRIGGER_FINALIZER = (
    ROOT
    / "resnet50_pipeline/"
    "conv_native_four_lane_triggered_causal_finalizer_v1.py"
)
TRIGGER_PROFILE = (
    ROOT
    / "contracts/operator_config/"
    "conv_native_four_lane_p10_triggered_causal_observability_v1.json"
)
TRIGGER_PROFILE_VALIDATION = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p9b_return_analysis/"
    "triggered_profile_validation.json"
)
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


def records(package: Path, *, include_manifest: bool = False) -> dict[str, Any]:
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
        raise BuildError("exact p9b source ZIP identity mismatch")
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("p9b source ZIP CRC failed")
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


def update_observer(package: Path) -> None:
    path = package / "tb_probe/native_return_observer.svh"
    base = path.read_text(encoding="utf-8")
    append = OBSERVER_APPEND.read_text(encoding="utf-8")
    marker = "// Native Conv c0 always-on triggered causal observer append."
    if marker in base:
        raise BuildError("source p9b observer already contains p10 append")
    path.write_text(
        base.rstrip() + "\n\n" + append.lstrip(),
        encoding="utf-8",
        newline="\n",
    )


def add_trigger_assets(package: Path) -> None:
    shutil.copy2(
        TRIGGER_FINALIZER,
        package / "package_tools/node0004_triggered_causal_finalizer.py",
    )
    diagnostic = package / "diagnostics"
    diagnostic.mkdir()
    shutil.copy2(TRIGGER_PROFILE, diagnostic / "triggered_profile.json")


def update_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    anchors = {
        (
            'observer_guard="$package_root/package_tools/'
            'node0004_package_observer_guard.py"\n'
        ): (
            'observer_guard="$package_root/package_tools/'
            'node0004_package_observer_guard.py"\n'
            'trigger_finalizer="$package_root/package_tools/'
            'node0004_triggered_causal_finalizer.py"\n'
        ),
        (
            '  printf \'%s\\n\' "$signal_status" > '
            '"$evidence_root/signal_status.txt"\n'
        ): (
            '  printf \'%s\\n\' "$signal_status" > '
            '"$evidence_root/signal_status.txt"\n'
            '  python3 "$trigger_finalizer" '
            '--observer-log "$run_root/c0/triggered_observer.log" '
            '--sim-log "$run_root/c0/sim.log" '
            '--compile-status "$evidence_root/compile_exit_status.txt" '
            '--run-status "$evidence_root/run_exit_status.txt" '
            '--signal-status "$evidence_root/signal_status.txt" '
            '--output "$evidence_root/triggered_causal_summary.json" '
            '>/dev/null 2>&1 || true\n'
        ),
        (
            'observer_log="$run_root/c0/return_observer.log"\n'
        ): (
            'observer_log="$run_root/c0/return_observer.log"\n'
            'trigger_log="$run_root/c0/triggered_observer.log"\n'
        ),
        (
            '+RETURN_OBS_FILE=$observer_log"   '
            '> "$run_root/c0/simulator_argv.txt"\n'
        ): (
            '+RETURN_OBS_FILE=$observer_log +N4T_CAUSAL_PROFILE '
            '+N4T_NO_PROGRESS_CYCLES=1048576 '
            '+N4T_FILE=$trigger_log"   '
            '> "$run_root/c0/simulator_argv.txt"\n'
        ),
        (
            '  "+RETURN_OBS_FILE=$observer_log" &\n'
        ): (
            '  "+RETURN_OBS_FILE=$observer_log" '
            '+N4T_CAUSAL_PROFILE '
            '+N4T_NO_PROGRESS_CYCLES=1048576 '
            '"+N4T_FILE=$trigger_log" &\n'
        ),
        (
            "    observer_bytes=0\n"
            '    [ ! -f "$observer_log" ] || '
            'observer_bytes="$(wc -c < "$observer_log")"\n'
            "    printf 'host_epoch=%s run=c0 observer_bytes=%s\\n' "
            '      "$host_epoch" "$observer_bytes"\n'
        ): (
            "    observer_bytes=0\n"
            "    trigger_bytes=0\n"
            '    [ ! -f "$observer_log" ] || '
            'observer_bytes="$(wc -c < "$observer_log")"\n'
            '    [ ! -f "$trigger_log" ] || '
            'trigger_bytes="$(wc -c < "$trigger_log")"\n'
            "    printf 'host_epoch=%s run=c0 observer_bytes=%s "
            "trigger_bytes=%s\\n' "
            '      "$host_epoch" "$observer_bytes" "$trigger_bytes"\n'
        ),
    }
    for old, new in anchors.items():
        if text.count(old) != 1:
            raise BuildError(f"runner anchor differs: {old[:80]!r}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")


def path_budget(package: Path) -> dict[str, Any]:
    runtime = package / "workload/runtime"
    projected = [
        f"install/cfg_pkg/{INSTALL_NAME}/{path.relative_to(runtime).as_posix()}"
        for path in runtime.rglob("*")
        if path.is_file()
    ]
    projected.extend(
        [
            f"run_{INSTALL_NAME}/compile/sim_results/compile_driver.log",
            f"run_{INSTALL_NAME}/c0/triggered_observer.log",
            f"evidence_{INSTALL_NAME}/triggered_causal_summary.json",
            f"{INSTALL_NAME}_return/evidence/triggered_causal_summary.json",
        ]
    )
    longest = max(projected, key=len)
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
    return f"""# Native Conv node0004 p10 triggered-causal c0 diagnostic

This fresh successor keeps the exact p9b tx5 c0 workload, configuration,
mapping, bitstream, execplan, SCA and numeric payloads.  It adds one bounded,
stage-gated triggered observer over the already exported p9b monitor signals.

Run from a clean extraction:

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/server_root
```

Expected return: `{INSTALL_NAME}_return.zip`.

This non-release diagnostic does not alter functional RTL, DUT inputs,
backpressure, timeout, or internal tensors.  It carries no formal 320D scope
and claims no E3/E4/E5 or production performance.
"""


def update_pointer(package: Path) -> None:
    write_json(
        package / "TEST_PACKAGE_MANIFEST.json",
        {
            "schema": "conv-native-four-lane-p10-triggered-pointer-v1",
            "status": "PACKAGE_READY_NOT_RUN",
            "install_name": INSTALL_NAME,
            "canonical_manifest": "package_manifest.json",
            "candidate_class": (
                "CONFIG_FUNCTIONAL_FIX_WITH_PUBLIC_CAUSAL_DIAGNOSTICS"
            ),
            "candidate_release": False,
            "formal_readback_count": 0,
        },
    )


def update_manifest(
    package: Path, source_manifest: dict[str, Any]
) -> None:
    analysis = json.loads(RETURN_ANALYSIS.read_text(encoding="utf-8"))
    profile_validation = json.loads(
        TRIGGER_PROFILE_VALIDATION.read_text(encoding="utf-8")
    )
    if (
        analysis.get("status")
        != "TX5_CROSSED_OLD_BOUNDARY_C0_TERMINAL_STILL_OPEN"
        or profile_validation.get("valid") is not True
    ):
        raise BuildError("p9b analysis/profile does not authorize p10")
    manifest = json.loads(
        json.dumps(source_manifest).replace(SOURCE_NAME, INSTALL_NAME)
    )
    manifest.update(
        {
            "schema": (
                "resnet50-conv-native-four-lane-0ccae916-"
                "p10-triggered-c0-server-package-v1"
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
            "evidence_level": (
                "E2_RECEIPT_REUSE_PLUS_TRIGGERED_CAUSAL_DIAGNOSTIC"
            ),
            "formal_readback_claimed": False,
            "functional_rtl_modified": False,
            "functional_rtl_file_count": 0,
            "server_rtl_entries": 0,
            "server_action": False,
            "files": {},
        }
    )
    manifest["source_p9b_return_analysis"] = {
        "path": RETURN_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": sha256(RETURN_ANALYSIS),
        "formal_return_sha256": (
            "96a4d9678b92dd5b74eb010de1fe27303dfc26a856f553623b6a162e999fab0d"
        ),
        "status": analysis["status"],
        "last_proven_good": analysis["failure_localization"][
            "LAST_PROVEN_GOOD"
        ],
        "first_divergence": analysis["failure_localization"][
            "FIRST_DIVERGENCE"
        ],
        "root_cause_uniqueness": analysis["failure_localization"][
            "root_cause_uniqueness"
        ],
    }
    manifest["delivery_successor"] = {
        "source_package": f"{SOURCE_NAME}.zip",
        "source_sha256": SOURCE_ZIP_SHA256,
        "changes": [
            "fresh short identity",
            "bounded triggered-causal observer append",
            "signal-safe triggered summary finalizer",
        ],
        "workload_config_mapping_bitstream_execplan_sca_relation": (
            "byte_equal_except_install_identity_in_sca_pair"
        ),
        "numeric_w3_golden_repeated": False,
        "functional_rtl_changed": False,
    }
    manifest["triggered_causal_observability"] = {
        "rule_id": "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
        "profile_path": "diagnostics/triggered_profile.json",
        "profile_sha256": sha256(
            package / "diagnostics/triggered_profile.json"
        ),
        "profile_validation_sha256": sha256(TRIGGER_PROFILE_VALIDATION),
        "observer_append_source": OBSERVER_APPEND.relative_to(ROOT).as_posix(),
        "observer_append_sha256": sha256(OBSERVER_APPEND),
        "finalizer_source": TRIGGER_FINALIZER.relative_to(ROOT).as_posix(),
        "finalizer_sha256": sha256(TRIGGER_FINALIZER),
        "runtime_enable": "+N4T_CAUSAL_PROFILE",
        "no_progress_cycles": 1048576,
        "no_progress_auto_terminate": False,
        "full_wave_dump": False,
        "per_event_text_io": False,
        "drives_dut": False,
        "changes_timeout": False,
        "formal_320d_in_scope": False,
    }
    manifest["diagnostic_features"].append(
        {
            "feature": "NATIVE4_TRIGGERED_CAUSAL",
            "runtime_enable": "+N4T_CAUSAL_PROFILE",
            "time0_marker": (
                "N4T_FEATURE_ENABLE_V1 "
                "feature=NATIVE4_TRIGGERED_CAUSAL enabled=1"
            ),
            "record_schema": "N4T_TRIGGER_V1",
            "return_target": "evidence/triggered_causal_summary.json",
        }
    )
    manifest["observer_binding"].update(
        {
            "source": "tb_probe/native_return_observer.svh",
            "source_sha256": sha256(
                package / "tb_probe/native_return_observer.svh"
            ),
            "p9b_base_sha256": source_manifest["observer_binding"][
                "source_sha256"
            ],
            "triggered_append_sha256": sha256(OBSERVER_APPEND),
            "private_state_xmr_added_by_p10": False,
            "p10_signal_surface": (
                "existing p9b n4d monitor signals only; clk/reset XMR "
                "identical to production-compiled base observer"
            ),
        }
    )
    manifest["return_allowlist"].extend(
        [
            {
                "source_root": "evidence",
                "source_path": "triggered_causal_summary.json",
                "target_path": "evidence/triggered_causal_summary.json",
                "required": True,
                "max_bytes": 2097152,
                "missing_semantics": (
                    "triggered finalizer did not emit its bounded summary"
                ),
            },
            {
                "source_root": "run",
                "source_path": "c0/triggered_observer.log",
                "target_path": "runs/c0/triggered_observer.log",
                "required": False,
                "max_bytes": 16777216,
                "missing_semantics": (
                    "simulator did not reach triggered observer time zero"
                ),
            },
        ]
    )
    manifest["workload_provenance"].update(
        {
            "package_builder": Path(__file__).relative_to(ROOT).as_posix(),
            "package_builder_sha256": sha256(Path(__file__)),
            "command": (
                ".venv/Scripts/python.exe -B "
                "tools/build_conv_native_four_lane_0ccae916_"
                "p10_triggered_c0_package.py"
            ),
            "source_p9b_zip_sha256": SOURCE_ZIP_SHA256,
            "p9b_return_analysis_sha256": sha256(RETURN_ANALYSIS),
            "p10_trigger_profile_sha256": sha256(TRIGGER_PROFILE),
        }
    )
    manifest["rule_receipts"] = {
        relative: sha256(ROOT / relative) for relative in RULE_PATHS
    }
    manifest["release_gate_matrix"] = {
        "schema": "cda-server-local-release-gate-impact-applicability-v1",
        "core_package_bootstrap_path": {
            "applicability": "blocking_applicable",
            "result": "PENDING_FINAL_AUDIT",
        },
        "runner_compile_finalizer": {
            "applicability": "blocking_applicable",
            "reason": "triggered runner/finalizer consumer changed",
        },
        "package_local_hdl": {
            "applicability": "blocking_applicable",
            "reason": "triggered observer append changed",
        },
        "materialized_config": {
            "applicability": "receipt_reuse",
            "reason": (
                "p9b config/address/mapping/bitstream/execplan/SCA are "
                "byte-equal except install identity"
            ),
            "causal_transaction_ledger_sha256": manifest[
                "configuration_fix"
            ]["causal_transaction_ledger_sha256"],
            "boundary_microtrace_sha256": manifest["configuration_fix"][
                "boundary_microtrace_sha256"
            ],
            "physical_bank_row_validity": (
                "receipt_reuse_addresses_byte_equal"
            ),
        },
        "diagnostic_observer_canonical_semantics": {
            "applicability": "blocking_applicable",
            "reason": "new trigger predicates and canonical finalizer",
        },
        "return_result_joint_gate": {
            "applicability": "blocking_applicable",
            "reason": "new triggered evidence return members",
        },
        "numeric_w3_golden": {
            "applicability": "record_only",
            "reason": "all frozen numeric payloads byte-equal",
        },
    }
    manifest["rule_feedback"] = {
        "type": "RULE_CONFIRMATION",
        "confirmed": [
            "CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001",
            "CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001",
            "CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001",
            "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
            "CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001",
            "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
        ],
        "rule_delta_proposal": [],
    }
    manifest["path_length_budget"] = path_budget(package)
    manifest["files"] = records(package)
    write_json(package / "package_manifest.json", manifest)


def source_relation(
    source_manifest: dict[str, Any], package: Path
) -> dict[str, Any]:
    target = records(package)
    source = source_manifest["files"]
    changed = sorted(
        path
        for path in set(source) & set(target)
        if source[path] != target[path]
    )
    expected_changed = sorted(
        [
            "PREPARE_AND_RUN.sh",
            "README.md",
            "TEST_PACKAGE_MANIFEST.json",
            "package_tools/node0004_assumed_hardware_server_runtime.py",
            "tb_probe/native_return_observer.svh",
            "workload/runtime/runs/c0/sca_cfg.json",
            "workload/runtime/runs/c0/sca_cfg_D.json",
        ]
    )
    extra = sorted(set(target) - set(source))
    expected_extra = sorted(
        [
            "diagnostics/triggered_profile.json",
            "package_tools/node0004_triggered_causal_finalizer.py",
        ]
    )
    immutable = [
        path
        for path in source
        if (
            path.startswith("workload/runtime/")
            and path not in {
                "workload/runtime/runs/c0/sca_cfg.json",
                "workload/runtime/runs/c0/sca_cfg_D.json",
            }
        )
    ]
    result = {
        "missing": sorted(set(source) - set(target)),
        "extra": extra,
        "expected_extra": expected_extra,
        "changed": changed,
        "expected_changed": expected_changed,
        "immutable_workload_member_count": len(immutable),
        "immutable_workload_members_byte_equal": all(
            source[path] == target[path] for path in immutable
        ),
    }
    result["valid"] = (
        not result["missing"]
        and extra == expected_extra
        and changed == expected_changed
        and result["immutable_workload_members_byte_equal"]
    )
    return result


def materialize(target: Path) -> tuple[Path, dict[str, Any]]:
    extracted = safe_extract(target)
    source_manifest = json.loads(
        (extracted / "package_manifest.json").read_text(encoding="utf-8")
    )
    package = target / INSTALL_NAME
    extracted.rename(package)
    replace_identity(package)
    update_observer(package)
    add_trigger_assets(package)
    update_runner(package)
    (package / "README.md").write_text(
        readme(), encoding="utf-8", newline="\n"
    )
    update_pointer(package)
    update_manifest(package, source_manifest)
    stale = [
        path.relative_to(package).as_posix()
        for path in package.rglob("*")
        if path.is_file()
        and path.name != "package_manifest.json"
        and path.relative_to(package).as_posix()
        != "diagnostics/triggered_profile.json"
        and SOURCE_NAME.encode() in path.read_bytes()
    ]
    if stale:
        raise BuildError(f"stale p9b identity remains: {stale}")
    relation = source_relation(source_manifest, package)
    if not relation["valid"]:
        raise BuildError(f"unexpected p9b-to-p10 relation: {relation}")
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
    for required in (
        SOURCE_ZIP,
        RETURN_ANALYSIS,
        OBSERVER_APPEND,
        TRIGGER_FINALIZER,
        TRIGGER_PROFILE,
        TRIGGER_PROFILE_VALIDATION,
    ):
        if not required.is_file():
            raise BuildError(f"required current evidence missing: {required}")
    package_path = OUTPUT_ROOT / INSTALL_NAME
    zip_path = OUTPUT_ROOT / f"{INSTALL_NAME}.zip"
    sidecar = Path(str(zip_path) + ".sha256")
    receipt_path = OUTPUT_ROOT / f"{INSTALL_NAME}.validation.json"
    for path in (package_path, zip_path, sidecar, receipt_path):
        if path.exists():
            raise BuildError(f"refusing to overwrite: {path}")
    with tempfile.TemporaryDirectory(prefix="n4-p10-a-") as first_name, (
        tempfile.TemporaryDirectory(prefix="n4-p10-b-")
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
        "schema": (
            "conv-native-four-lane-0ccae916-p10-triggered-c0-build-v1"
        ),
        "status": "PACKAGE_READY_NOT_RUN_PENDING_FINAL_AUDIT",
        "valid": True,
        "candidate_release": False,
        "package": str(package_path),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": str(sidecar),
        "sidecar_sha256": sha256(sidecar),
        "source_p9b_zip_sha256": SOURCE_ZIP_SHA256,
        "p9b_return_analysis_sha256": sha256(RETURN_ANALYSIS),
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
