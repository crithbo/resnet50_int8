#!/usr/bin/env python3
"""Independent final-ZIP audit for the node0004 v59 install-subtree successor."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath


EXPECTED_ZIP_SHA256 = (
    "e5023a50e827ae3d4b0fc6bb9ac327c9aa38d9e72db068cc4fd567f8e76a216d"
)
EXPECTED_ROOT = "r5_n4_hw_v59_install_subtree"
EXPECTED_HELPER_SHA256 = (
    "82723ecc427c3e42cfc327eff87cae7d5d935b9f6dccb220e78bfa573d11a9ae"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def normalized_members(archive: zipfile.ZipFile) -> dict[str, str]:
    result: dict[str, str] = {}
    for name in archive.namelist():
        if name.endswith("/"):
            continue
        relative = "/".join(name.split("/")[1:])
        result[relative] = sha256_bytes(archive.read(name))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v53", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--family-report", required=True, type=Path)
    parser.add_argument("--shared-report", required=True, type=Path)
    parser.add_argument("--profile", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    checks: dict[str, bool] = {}
    zip_sha = sha256_file(args.zip)
    checks["zip_identity"] = zip_sha == EXPECTED_ZIP_SHA256
    if not checks["zip_identity"]:
        errors.append(f"ZIP SHA mismatch: {zip_sha}")

    sidecar_text = args.sidecar.read_text(encoding="utf-8").strip()
    checks["sidecar_identity"] = (
        EXPECTED_ZIP_SHA256 in sidecar_text
        and args.zip.name in sidecar_text
    )
    if not checks["sidecar_identity"]:
        errors.append("sidecar does not bind exact ZIP name and SHA")

    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        checks["crc"] = archive.testzip() is None
        checks["no_duplicates"] = len(names) == len(set(names))
        roots = {name.split("/", 1)[0] for name in names}
        checks["single_root"] = roots == {EXPECTED_ROOT}
        unsafe = []
        symlinks = []
        for info in infos:
            pure = PurePosixPath(info.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in info.filename:
                unsafe.append(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                symlinks.append(info.filename)
        checks["safe_paths"] = not unsafe
        checks["no_symlinks"] = not symlinks
        if not all(
            checks[key]
            for key in ("crc", "no_duplicates", "single_root", "safe_paths", "no_symlinks")
        ):
            errors.append("ZIP structural safety gate failed")

        manifest_member = f"{EXPECTED_ROOT}/package_manifest.json"
        manifest = json.loads(archive.read(manifest_member))
        declared = manifest.get("files", {})
        actual = {
            "/".join(name.split("/")[1:]): sha256_bytes(archive.read(name))
            for name in names
            if not name.endswith("/") and name != manifest_member
        }
        checks["manifest_exact_set"] = set(declared) == set(actual)
        checks["manifest_per_file_receipts"] = declared == actual
        if not checks["manifest_exact_set"]:
            errors.append("manifest exact-set mismatch")
        if not checks["manifest_per_file_receipts"]:
            errors.append("manifest per-file SHA mismatch")

        required = {
            "PREPARE_AND_RUN.sh",
            "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
            "package_tools/server_package_runtime_layout.py",
        }
        checks["required_runtime_members"] = required <= set(actual)
        if not checks["required_runtime_members"]:
            errors.append("required runtime-layout member missing")

        helper = archive.read(
            f"{EXPECTED_ROOT}/package_tools/server_package_runtime_layout.py"
        )
        checks["shared_helper_exact"] = (
            sha256_bytes(helper) == EXPECTED_HELPER_SHA256
        )
        if not checks["shared_helper_exact"]:
            errors.append("embedded shared helper SHA mismatch")

        contract = json.loads(
            archive.read(f"{EXPECTED_ROOT}/SERVER_RUNTIME_LAYOUT_CONTRACT.json")
        )
        checks["runtime_contract_identity"] = (
            contract.get("package_id") == EXPECTED_ROOT
            and contract.get("install_name") == EXPECTED_ROOT
        )
        runtime_roots = contract.get("runtime_roots", {})
        checks["runtime_contract_roots"] = (
            runtime_roots.get("cfg_root")
            == f"install/cfg_pkg/{EXPECTED_ROOT}"
            and runtime_roots.get("run_root")
            == f"install/codex_runs/{EXPECTED_ROOT}/{{attempt}}"
            and runtime_roots.get("evidence_root")
            == f"install/codex_runs/{EXPECTED_ROOT}/{{attempt}}/evidence"
            and runtime_roots.get("compile_root")
            == f"install/codex_runs/{EXPECTED_ROOT}/{{attempt}}/compile"
            and contract.get("fixed_result_root")
            == "/home/panqs/ndp/simresult"
            and contract.get("tb_cwd") == "$server_root"
            and contract.get("required_preexisting_parents")
            == ["install", "install/cfg_pkg", "install/codex_runs"]
        )
        if not checks["runtime_contract_identity"]:
            errors.append("runtime contract package identity mismatch")
        if not checks["runtime_contract_roots"]:
            errors.append("runtime contract root formulas mismatch")

        runner = archive.read(f"{EXPECTED_ROOT}/PREPARE_AND_RUN.sh").decode(
            "utf-8"
        )
        checks["runner_fixed_result_only"] = (
            "/home/panqs/ndp/simresult" in runner
            and not re.search(
                r"(?:run_root|evidence_root|compile_root|cfg_root)="
                r"[^\n]*?/home/panqs/ndp/simresult",
                runner,
            )
        )
        if not checks["runner_fixed_result_only"]:
            errors.append("runner uses simresult as package work root")

        v59_members = normalized_members(archive)

    with zipfile.ZipFile(args.source_v53) as source_archive:
        v53_members = normalized_members(source_archive)
    common = set(v53_members) & set(v59_members)
    changed = sorted(
        member for member in common if v53_members[member] != v59_members[member]
    )
    allowed_changed = {
        "PREPARE_AND_RUN.sh",
        "README.md",
        "package_manifest.json",
        "package_tools/node0004_hang_localization_runtime_v7.py",
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    }
    checks["frozen_payload_byte_equal"] = (
        len(common) == 109
        and set(changed) == allowed_changed
        and len([member for member in common if member not in allowed_changed]) == 103
    )
    if not checks["frozen_payload_byte_equal"]:
        errors.append(f"unexpected v53-to-v59 byte changes: {changed}")

    build = load_json(args.build_report)
    family = load_json(args.family_report)
    shared = load_json(args.shared_report)
    profile = load_json(args.profile)
    checks["deterministic_double_build"] = (
        build.get("deterministic_rebuild_equal") is True
    )
    checks["family_validator"] = (
        family.get("valid") is True and not family.get("errors")
    )
    checks["shared_validator"] = (
        shared.get("pass") is True and not shared.get("errors")
    )
    checks["shadow_profile"] = (
        profile.get("contract_valid") is True
        and profile.get("preflight", {}).get("pass") is True
        and not profile.get("preflight", {}).get("errors")
    )
    for key in (
        "deterministic_double_build",
        "family_validator",
        "shared_validator",
        "shadow_profile",
    ):
        if not checks[key]:
            errors.append(f"{key} failed")

    report = {
        "schema": "conv-node0004-v59-final-zip-audit-v1",
        "package_id": EXPECTED_ROOT,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors and all(checks.values()),
        "errors": errors,
        "checks": checks,
        "zip": {
            "path": str(args.zip.resolve()),
            "bytes": args.zip.stat().st_size,
            "sha256": zip_sha,
        },
        "source_v53": {
            "path": str(args.source_v53.resolve()),
            "bytes": args.source_v53.stat().st_size,
            "sha256": sha256_file(args.source_v53),
            "disposition": "PACKAGE_HELD_PRE_SHARED_INSTALL_LAYOUT_GATE",
        },
        "frozen_payload_comparison": {
            "common_members": len(common),
            "byte_equal_common_members": len(common) - len(changed),
            "changed_members": changed,
            "claim": (
                "Only identity, runner/install layout, SCA mechanical path "
                "binding, return contract and validation metadata changed."
            ),
        },
        "release_gate_matrix": [
            {
                "gate_id": "runtime_layout",
                "applicability": "blocking_applicable",
                "status": "PASS" if checks["shared_validator"] else "FAIL",
                "blocking": True,
            },
            {
                "gate_id": "runner_control_flow",
                "applicability": "blocking_applicable",
                "status": "PASS" if checks["family_validator"] else "FAIL",
                "blocking": True,
            },
            {
                "gate_id": "final_zip_content",
                "applicability": "blocking_applicable",
                "status": "PASS" if not errors else "FAIL",
                "blocking": True,
            },
            {
                "gate_id": "frozen_numeric_workload_observer",
                "applicability": "receipt_reuse",
                "status": (
                    "PASS" if checks["frozen_payload_byte_equal"] else "FAIL"
                ),
                "blocking": False,
            },
            {
                "gate_id": "functional_rtl_or_server_action",
                "applicability": "not_applicable",
                "status": "NOT_APPLICABLE",
                "blocking": False,
            },
            {
                "gate_id": "intermediate_report_format",
                "applicability": "record_only",
                "status": "RECORDED",
                "blocking": False,
            },
        ],
        "claim_boundary": (
            "Local package/install/runtime-layout and result-publication "
            "correctness only. No production compile, simulation, natural "
            "terminal, formal-D, E4 or E5 claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "pass": report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"],
                "errors": len(errors),
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0 if report["FINAL_ZIP_RULE_SELF_AUDIT_PASS"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
