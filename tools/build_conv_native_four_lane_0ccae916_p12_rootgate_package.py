#!/usr/bin/env python3
"""Build a runner-only p12 replacement from the exact held p11f ZIP."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p11f_pubord"
PACKAGE_ID = "r5_n4_0cc_p12_rootgate"
WORKLOAD_INSTALL_NAME = SOURCE_ID
SOURCE_SHA256 = (
    "3198b62bf609f213f9355f8ddaa45df90dd05ea61443fe859247d0b9f3cd0acf"
)
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "pending"
    / f"{SOURCE_ID}.zip"
)
OUTPUT_ROOT = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p11f_rootgate_replacement"
)
ROOT_GATE_SOURCE = (
    ROOT
    / "resnet50_pipeline/ndp_root_toplevel_exact_set_gate_v1.py"
)
RULE_PATHS = (
    ".agents/agent.md",
    ".agents/plan.md",
    ".agents/rules/生成前必读索引.md",
    ".agents/rules/服务器测试包生成规则.md",
    "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
)


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
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def file_records(package: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(package).as_posix(): {
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(item for item in package.rglob("*") if item.is_file())
        if path.name != "package_manifest.json"
    }


def extract_exact_source(target: Path) -> Path:
    if not SOURCE_ZIP.is_file() or sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact held p11f source ZIP differs or is unavailable")
    package = target / PACKAGE_ID
    package.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        if archive.testzip() is not None:
            raise BuildError("held p11f source ZIP CRC differs")
        for info in archive.infolist():
            pure = PurePosixPath(info.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in info.filename
                or not pure.parts
                or pure.parts[0] != SOURCE_ID
            ):
                raise BuildError(f"unsafe held p11f member: {info.filename}")
            if info.is_dir():
                continue
            relative = PurePosixPath(*pure.parts[1:])
            output = package.joinpath(*relative.parts)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(archive.read(info))
    return package


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if text.count(old) != 1:
        raise BuildError(f"{label} anchor count differs: {text.count(old)}")
    return text.replace(old, new)


def patch_publisher(package: Path) -> None:
    path = package / "package_tools/fixed_simresult_publisher.py"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '    result_root = RESULT_ROOT\n',
        (
            '    package_identity = manifest.get("package_identity")\n'
            "    if (\n"
            "        not isinstance(package_identity, str)\n"
            "        or not package_identity\n"
            "        or package_identity != "
            f'"{PACKAGE_ID}"\n'
            "    ):\n"
            '        raise PublishError("package release identity differs")\n'
            "    result_root = RESULT_ROOT\n"
        ),
        "publisher release identity",
    )
    text = replace_once(
        text,
        '    final_zip = result_root / f"{install_name}_return.zip"\n',
        '    final_zip = result_root / f"{package_identity}_return.zip"\n',
        "publisher final ZIP",
    )
    text = replace_once(
        text,
        '    return_dir = stage_root / f"{install_name}_return"\n',
        '    return_dir = stage_root / f"{package_identity}_return"\n',
        "publisher return directory",
    )
    identity_anchor = '        "install_name": install_name,\n'
    if text.count(identity_anchor) != 2:
        raise BuildError(
            "publisher return identity anchor count differs: "
            f"{text.count(identity_anchor)}"
        )
    text = text.replace(
        identity_anchor,
        (
            '        "package_identity": package_identity,\n'
            '        "workload_install_name": install_name,\n'
        ),
    )
    text = replace_once(
        text,
        (
            "    publication_preflight = load_json(\n"
            '        evidence_root / "publication_preflight.json"\n'
            "    )\n"
        ),
        (
            "    publication_preflight = load_json(\n"
            '        evidence_root / "publication_preflight.json"\n'
            "    )\n"
            "    root_gate = load_json(\n"
            '        evidence_root / "ndp_root_toplevel_gate.json"\n'
            "    )\n"
            "    required_root_gate_keys = (\n"
            '        "server_root",\n'
            '        "pre_snapshot_sha256",\n'
            '        "post_snapshot_sha256",\n'
            '        "pre_exact_set_sha256",\n'
            '        "post_exact_set_sha256",\n'
            '        "ndp_root_toplevel_unchanged",\n'
            '        "root_internal_preexisting_parents",\n'
            "    )\n"
            "    if (\n"
            "        root_gate.get(\"schema\")\n"
            '        != "ndp-root-toplevel-exact-set-gate-v1"\n'
            "        or any(key not in root_gate for key in "
            "required_root_gate_keys)\n"
            "    ):\n"
            '        raise PublishError("NDP root top-level gate receipt differs")\n'
        ),
        "publisher root gate load",
    )
    text = replace_once(
        text,
        '        "server_result_status": result.get("status"),\n',
        (
            '        "server_result_status": result.get("status"),\n'
            '        "ndp_root_toplevel_gate": {\n'
            '            key: root_gate[key]\n'
            '            for key in required_root_gate_keys\n'
            "        },\n"
        ),
        "publisher return root gate receipt",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def patch_runner(package: Path) -> None:
    path = package / "PREPARE_AND_RUN.sh"
    text = path.read_text(encoding="utf-8")
    text = replace_once(
        text,
        f'install_name="{SOURCE_ID}"\n',
        (
            f'install_name="{WORKLOAD_INSTALL_NAME}"\n'
            f'package_identity="{PACKAGE_ID}"\n'
            'root_gate="$package_root/package_tools/'
            'ndp_root_toplevel_exact_set_gate.py"\n'
        ),
        "runner identities",
    )
    text = text.replace(
        f"/{SOURCE_ID}_return.zip", f"/{PACKAGE_ID}_return.zip"
    )
    text = text.replace(
        f".{SOURCE_ID}.run.$$", f".{PACKAGE_ID}.run.$$"
    )
    text = text.replace(
        '"$duplicate_root/${install_name}_return.zip"',
        '"$duplicate_root/${package_identity}_return.zip"',
    )
    text = text.replace(
        '"$duplicate_root/${install_name}_return.zip.sha256"',
        '"$duplicate_root/${package_identity}_return.zip.sha256"',
    )
    text = replace_once(
        text,
        'mkdir -p -- "$result_root" || exit 9\n',
        (
            'pre_snapshot_json="$(python3 "$root_gate" snapshot '
            '--server-root "$server_root")" || exit 12\n'
            'parent_preflight_json="$(python3 "$root_gate" '
            'validate-parents --server-root "$server_root" '
            '--manifest "$package_root/package_manifest.json")" || exit 12\n'
            'mkdir -p -- "$result_root" || exit 9\n'
        ),
        "runner pre-write root snapshot",
    )
    text = replace_once(
        text,
        (
            'mkdir -p "$cfg_root" "$run_root/compile/sim_results" '
            '"$evidence_root/natural_terminal" '
            '"$evidence_root/feature_binding"\n'
        ),
        (
            'mkdir -p "$cfg_root" "$run_root/compile/sim_results" '
            '"$evidence_root/natural_terminal" '
            '"$evidence_root/feature_binding"\n'
            "printf '%s\\n' \"$pre_snapshot_json\" > "
            '"$evidence_root/ndp_root_toplevel_pre.json"\n'
            "printf '%s\\n' \"$parent_preflight_json\" > "
            '"$evidence_root/ndp_root_parent_preflight.json"\n'
        ),
        "runner pre snapshot receipt",
    )
    text = replace_once(
        text,
        "sim_pid=\nprogress_pid=\nfinalize() {\n",
        (
            "sim_pid=\n"
            "progress_pid=\n"
            "root_gate_status=125\n"
            "finalize() {\n"
        ),
        "runner root gate status",
    )
    text = replace_once(
        text,
        (
            '  [ -z "$progress_pid" ] || wait "$progress_pid" '
            "2>/dev/null\n"
            "  printf '%s\\n' \"$compile_status\" > "
            '"$evidence_root/compile_exit_status.txt"\n'
        ),
        (
            '  [ -z "$progress_pid" ] || wait "$progress_pid" '
            "2>/dev/null\n"
            '  post_snapshot_json="$(python3 "$root_gate" snapshot '
            '--server-root "$server_root")"\n'
            "  post_capture=$?\n"
            '  [ "$post_capture" -ne 0 ] || printf \'%s\\n\' '
            '"$post_snapshot_json" > '
            '"$evidence_root/ndp_root_toplevel_post.json"\n'
            '  [ "$post_capture" -eq 0 ] || printf \'%s\\n\' '
            '\'{\"schema\":\"ndp-root-toplevel-post-capture-error\"}\' > '
            '"$evidence_root/ndp_root_toplevel_post.json"\n'
            '  python3 "$root_gate" compare '
            '--pre "$evidence_root/ndp_root_toplevel_pre.json" '
            '--post "$evidence_root/ndp_root_toplevel_post.json" '
            '--manifest "$package_root/package_manifest.json" '
            '--output "$evidence_root/ndp_root_toplevel_gate.json" '
            ">/dev/null 2>&1\n"
            "  root_gate_status=$?\n"
            "  printf '%s\\n' \"$compile_status\" > "
            '"$evidence_root/compile_exit_status.txt"\n'
        ),
        "runner post snapshot and compare",
    )
    text = replace_once(
        text,
        (
            '  [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] '
            '|| final="$collection"\n'
        ),
        (
            '  [ "$final" -ne 0 ] || [ "$collection" -eq 0 ] '
            '|| final="$collection"\n'
            '  [ "$final" -ne 0 ] || [ "$root_gate_status" -eq 0 ] '
            '|| final="$root_gate_status"\n'
        ),
        "runner root gate exit conjunction",
    )
    path.write_text(text, encoding="utf-8", newline="\n")


def update_manifest(package: Path) -> None:
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update(
        {
            "schema": "conv-native-four-lane-p12-rootgate-package-v1",
            "package_identity": PACKAGE_ID,
            "workload_install_name": WORKLOAD_INSTALL_NAME,
            "install_name": WORKLOAD_INSTALL_NAME,
            "return_name": f"{PACKAGE_ID}_return.zip",
            "run_namespace": f"run_{PACKAGE_ID}",
            "status": "PACKAGE_READY_NOT_RUN",
            "package_release": "PACKAGE_READY_NOT_RUN",
            "candidate_release": False,
            "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "functional_rtl_modified": False,
            "server_action": False,
        }
    )
    manifest["runner_only_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_package_zip_sha256": SOURCE_SHA256,
        "changed_surfaces": [
            "PREPARE_AND_RUN.sh",
            "package_manifest.json",
            "TEST_PACKAGE_MANIFEST.json",
            "README.md",
            "package_tools/fixed_simresult_publisher.py",
            "package_tools/ndp_root_toplevel_exact_set_gate.py",
        ],
        "frozen_surfaces": [
            "workload/runtime",
            "diagnostics",
            "tb_probe",
            "numeric",
            "golden",
            "observer",
            "timeout",
            "functional RTL",
        ],
    }
    manifest["ndp_root_toplevel_contract"] = {
        "rule_id": "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
        "server_root_source": "single exact runner argument",
        "pre_snapshot_before_any_write": True,
        "post_snapshot_in_shared_finalizer": True,
        "snapshot_scope": "sorted direct-child names and lstat types",
        "runtime_write_targets": [],
        "root_internal_preexisting_parents": [],
        "root_external_write_roots": [
            "/home/panqs/ndp/simresult",
            f"/home/panqs/ndp/simresult/.{PACKAGE_ID}.run.<pid>",
        ],
        "drift_fail_closed": True,
        "unknown_entry_auto_delete_forbidden": True,
    }
    additions = [
        {
            "source_root": "evidence",
            "source_path": "ndp_root_toplevel_pre.json",
            "target_path": "evidence/ndp_root_toplevel_pre.json",
            "required": True,
            "max_bytes": 2 * 1024 * 1024,
            "missing_semantics": "pre-write root exact-set snapshot unavailable",
        },
        {
            "source_root": "evidence",
            "source_path": "ndp_root_toplevel_post.json",
            "target_path": "evidence/ndp_root_toplevel_post.json",
            "required": True,
            "max_bytes": 2 * 1024 * 1024,
            "missing_semantics": "shared-finalizer root exact-set snapshot unavailable",
        },
        {
            "source_root": "evidence",
            "source_path": "ndp_root_parent_preflight.json",
            "target_path": "evidence/ndp_root_parent_preflight.json",
            "required": True,
            "max_bytes": 2 * 1024 * 1024,
            "missing_semantics": "declared root parent preflight unavailable",
        },
        {
            "source_root": "evidence",
            "source_path": "ndp_root_toplevel_gate.json",
            "target_path": "evidence/ndp_root_toplevel_gate.json",
            "required": True,
            "max_bytes": 2 * 1024 * 1024,
            "missing_semantics": "root direct-child exact-set conjunction unavailable",
        },
    ]
    targets = {item["target_path"] for item in manifest["return_allowlist"]}
    manifest["return_allowlist"].extend(
        item for item in additions if item["target_path"] not in targets
    )
    manifest["fixed_server_result_publication"].update(
        {
            "result_root": "/home/panqs/ndp/simresult",
            "return_zip": (
                f"/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip"
            ),
            "return_sidecar": (
                f"/home/panqs/ndp/simresult/{PACKAGE_ID}_return.zip.sha256"
            ),
            "configurable": False,
            "ndp_root_duplicate_absent_required": True,
        }
    )
    manifest["release_gate_matrix"] = {
        "core_always": {
            "applicability": "blocking_applicable",
            "pass": True,
            "changed_surface": ["fresh outer package identity"],
            "blocking": True,
        },
        "runner": {
            "applicability": "blocking_applicable",
            "pass": True,
            "changed_surface": [
                "pre-write root snapshot",
                "shared-finalizer post snapshot",
                "root exact-set exit conjunction",
            ],
            "evidence": [
                "normal/compile-fail/HUP/INT/TERM exact-runner harness",
                "new-root-directory/new-root-file/drift/missing-parent negatives",
            ],
            "blocking": True,
        },
        "package_local_hdl": {
            "applicability": "receipt_reuse",
            "pass": True,
            "changed_surface": [],
            "evidence": ["p11f observer byte equality"],
            "blocking": False,
        },
        "materialized_config": {
            "applicability": "receipt_reuse",
            "pass": True,
            "changed_surface": [],
            "evidence": ["p11f workload/runtime byte equality"],
            "blocking": False,
        },
        "diagnostic_semantics": {
            "applicability": "receipt_reuse",
            "pass": True,
            "changed_surface": [],
            "evidence": ["p11f diagnostics/finalizers byte equality"],
            "blocking": False,
        },
        "return_result": {
            "applicability": "blocking_applicable",
            "pass": True,
            "changed_surface": [
                "p12 fixed result identity",
                "root exact-set receipts in return allowlist",
            ],
            "blocking": True,
        },
        "record_only": [
            "numeric/W3/golden/address/config/observer/timeout/RTL are frozen"
        ],
    }
    manifest["rule_receipts"] = [
        {
            "path": relative,
            "size_bytes": (ROOT / relative).stat().st_size,
            "sha256": sha256(ROOT / relative),
            "reason": (
                "mutable provenance"
                if relative == ".agents/plan.md"
                else "current runner/package generation authority"
            ),
        }
        for relative in RULE_PATHS
    ]
    manifest["rule_receipts_current_match"] = True
    rule_ids = set(
        manifest.get("delivery_successor", {}).get("rule_ids", [])
    )
    rule_ids.update(
        {
            "CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001",
            "CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001",
            "CDA-SERVER-PACKAGE-STORAGE-ROTATION-001",
            "CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001",
        }
    )
    manifest.setdefault("delivery_successor", {})["rule_ids"] = sorted(rule_ids)
    paths = sorted(file_records(package))
    budget = manifest.setdefault("path_length_budget", {})
    budget.update(
        {
            "max_zip_member_chars": max(
                len(f"{PACKAGE_ID}/{relative}") for relative in paths
            ),
            "max_inner_suffix_chars": max(map(len, paths)),
            "max_inner_depth": max(
                len(PurePosixPath(relative).parts) for relative in paths
            ),
            "max_inner_component_chars": max(
                len(part)
                for relative in paths
                for part in PurePosixPath(relative).parts
            ),
            "fixed_result_root": "/home/panqs/ndp/simresult",
        }
    )
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)
    manifest["files"] = file_records(package)
    write_json(manifest_path, manifest)


def update_test_manifest(package: Path) -> None:
    path = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value.update(
        {
            "schema": "conv-native-four-lane-p12-rootgate-pointer-v1",
            "package_identity": PACKAGE_ID,
            "install_name": WORKLOAD_INSTALL_NAME,
            "candidate_release": False,
            "formal_readback_count": 0,
        }
    )
    write_json(path, value)


def update_readme(package: Path) -> None:
    (package / "README.md").write_text(
        "# Native Conv node0004 p12 root-top-level gate replacement\n\n"
        "This fresh runner-only identity preserves p11f workload/config, "
        "numeric/golden data, observer, timeout, and functional RTL bytes. "
        "It adds a pre-write and shared-finalizer post-write exact-set check "
        "over the direct child names and lstat types of the supplied NDP "
        "server root. All run and return writes remain under the fixed "
        "server path `/home/panqs/ndp/simresult` outside that root.\n\n"
        "Server command:\n\n"
        "`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`\n\n"
        "Expected return:\n\n"
        "`/home/panqs/ndp/simresult/"
        f"{PACKAGE_ID}_return.zip`\n",
        encoding="utf-8",
        newline="\n",
    )


def build_directory(target: Path) -> Path:
    package = extract_exact_source(target)
    shutil.copy2(
        ROOT_GATE_SOURCE,
        package
        / "package_tools/ndp_root_toplevel_exact_set_gate.py",
    )
    patch_publisher(package)
    patch_runner(package)
    update_test_manifest(package)
    update_readme(package)
    update_manifest(package)
    return package


def deterministic_zip(package: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(
            item for item in package.rglob("*") if item.is_file()
        ):
            relative = (
                Path(PACKAGE_ID) / path.relative_to(package)
            ).as_posix()
            info = zipfile.ZipInfo(relative, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (
                (0o100755 if path.name == "PREPARE_AND_RUN.sh" else 0o100644)
                << 16
            )
            archive.writestr(info, path.read_bytes())


def main() -> int:
    targets = (
        OUTPUT_ROOT / PACKAGE_ID,
        OUTPUT_ROOT / f"{PACKAGE_ID}.zip",
        OUTPUT_ROOT / f"{PACKAGE_ID}.zip.sha256",
        OUTPUT_ROOT / f"{PACKAGE_ID}.build.json",
        OUTPUT_ROOT / "p11f_hold_revalidation.json",
    )
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite an existing p12 target")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(
        OUTPUT_ROOT / "p11f_hold_revalidation.json",
        {
            "schema": "conv-native-four-lane-p11f-rootgate-revalidation-v1",
            "source_package_identity": SOURCE_ID,
            "source_zip": SOURCE_ZIP.relative_to(ROOT).as_posix(),
            "source_zip_sha256": SOURCE_SHA256,
            "status": "PACKAGE_HELD_NDP_ROOT_TOPLEVEL_GATE_REQUIRED",
            "content_neutral_revalidation_possible": False,
            "evidence": {
                "pre_write_root_snapshot_present": False,
                "post_finalize_root_snapshot_present": False,
                "root_exact_set_hash_present": False,
                "root_drift_exit_conjunction_present": False,
                "first_write_before_snapshot": (
                    "mkdir -p -- /home/panqs/ndp/simresult"
                ),
            },
            "disposition": "FRESH_RUNNER_ONLY_REPLACEMENT_REQUIRED",
            "claim_boundary": (
                "read-only exact p11f ZIP audit; no DUT run or numeric claim"
            ),
        },
    )
    package = build_directory(OUTPUT_ROOT)
    zip_path = OUTPUT_ROOT / f"{PACKAGE_ID}.zip"
    deterministic_zip(package, zip_path)
    value = sha256(zip_path)
    with tempfile.TemporaryDirectory(prefix="native4-p12-repeat-") as temp:
        repeat_package = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{PACKAGE_ID}.zip"
        deterministic_zip(repeat_package, repeat_zip)
        deterministic = sha256(repeat_zip) == value
    if not deterministic:
        raise BuildError("p12 deterministic double build differs")
    sidecar = OUTPUT_ROOT / f"{PACKAGE_ID}.zip.sha256"
    sidecar.write_text(
        f"{value}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    result = {
        "schema": "conv-native-four-lane-p12-rootgate-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "workload_install_name": WORKLOAD_INSTALL_NAME,
        "source_p11f_zip_sha256": SOURCE_SHA256,
        "package": str(package),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": value,
        "sidecar": str(sidecar),
        "deterministic_double_build": deterministic,
        "functional_rtl_modified": False,
        "config_numeric_w3_golden_observer_timeout_changed": False,
        "server_action": False,
    }
    write_json(OUTPUT_ROOT / f"{PACKAGE_ID}.build.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
