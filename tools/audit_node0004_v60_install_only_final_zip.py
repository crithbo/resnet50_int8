#!/usr/bin/env python3
"""Independent final-ZIP audit for node0004 v60 install-only successor."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v60_install_only"
SOURCE = "r5_n4_hw_v59_install_subtree"
ZIP_SHA = "cb3342e90510e4cd1e66afb9a19977cc5eae725abccf987346757d3d34937ec8"
HELPER_SHA = "7969ca56e13a7e0a0a83bdfd48d1409d28eef2ae0fd63ad08f0ec5c39e2d848a"
ALLOWED_CHANGED = {
    "PREPARE_AND_RUN.sh",
    "README.md",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "package_manifest.json",
    "package_tools/server_package_runtime_layout.py",
    "workload/runtime/runs/c0/sca_cfg.json",
    "workload/runtime/runs/c0/sca_cfg_D.json",
}


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def members(archive: zipfile.ZipFile) -> dict[str, bytes]:
    return {
        "/".join(name.split("/")[1:]): archive.read(name)
        for name in archive.namelist()
        if not name.endswith("/")
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--source-v59", type=Path, required=True)
    parser.add_argument("--build-report", type=Path, required=True)
    parser.add_argument("--family-report", type=Path, required=True)
    parser.add_argument("--shared-report", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    errors: list[str] = []
    checks: dict[str, bool] = {}
    current_sha = sha_file(args.zip)
    checks["zip_identity"] = current_sha == ZIP_SHA
    sidecar = args.sidecar.read_text(encoding="ascii").strip().split()
    checks["sidecar_identity"] = sidecar == [ZIP_SHA, args.zip.name]

    with zipfile.ZipFile(args.zip) as archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        checks["crc"] = archive.testzip() is None
        checks["no_duplicates"] = len(names) == len(set(names))
        checks["single_root"] = {
            name.split("/", 1)[0] for name in names
        } == {PACKAGE}
        checks["safe_paths"] = all(
            not PurePosixPath(item.filename).is_absolute()
            and ".." not in PurePosixPath(item.filename).parts
            and "\\" not in item.filename
            for item in infos
        )
        checks["no_symlinks"] = all(
            not stat.S_ISLNK((item.external_attr >> 16) & 0xFFFF)
            for item in infos
        )
        current = members(archive)
        manifest = json.loads(current["package_manifest.json"])
        actual = {
            name: sha_bytes(value)
            for name, value in current.items()
            if name != "package_manifest.json"
        }
        checks["manifest_exact_set"] = set(manifest["files"]) == set(actual)
        checks["manifest_per_file_receipts"] = manifest["files"] == actual
        checks["shared_helper_exact"] = (
            sha_bytes(current["package_tools/server_package_runtime_layout.py"])
            == HELPER_SHA
        )
        contract = json.loads(current["SERVER_RUNTIME_LAYOUT_CONTRACT.json"])
        roots = contract["runtime_roots"]
        checks["runtime_contract_v2"] = (
            contract["package_id"] == PACKAGE
            and contract["install_name"] == PACKAGE
            and contract["required_preexisting_parents"] == ["install"]
            and contract["package_creatable_parent_dirs"]
            == ["install/cfg_pkg", "install/codex_runs"]
            and roots["cfg_root"] == f"install/cfg_pkg/{PACKAGE}"
            and roots["run_root"]
            == f"install/codex_runs/{PACKAGE}/{{attempt}}"
            and roots["evidence_root"]
            == f"install/codex_runs/{PACKAGE}/{{attempt}}/evidence"
            and roots["compile_root"]
            == f"install/codex_runs/{PACKAGE}/{{attempt}}/compile"
            and contract["fixed_result_root"] == "/home/panqs/ndp/simresult"
            and contract["tb_cwd"] == "$server_root"
        )
        runner = current["PREPARE_AND_RUN.sh"].decode("utf-8")
        checks["runner_install_only_and_fixed_return"] = (
            "--server-root" in runner
            and "server_package_runtime_layout.py" in runner
            and "/home/panqs/ndp/simresult" in runner
            and 'cfg_root="$(printf' not in runner
            and 'run_root="$(printf' not in runner
        )

    with zipfile.ZipFile(args.source_v59) as archive:
        previous = members(archive)
    common = set(previous) & set(current)
    changed = sorted(
        name for name in common if previous[name] != current[name]
    )
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    checks["changed_surface_exact"] = (
        set(changed) == ALLOWED_CHANGED
        and added == ["provenance/v59_to_v60_install_only.json"]
        and not removed
    )
    frozen = common - ALLOWED_CHANGED
    checks["frozen_payload_byte_equal"] = all(
        previous[name] == current[name] for name in frozen
    )
    checks["sca_identity_only"] = all(
        previous[name].replace(SOURCE.encode(), PACKAGE.encode())
        == current[name]
        for name in (
            "workload/runtime/runs/c0/sca_cfg.json",
            "workload/runtime/runs/c0/sca_cfg_D.json",
        )
    )

    build = load(args.build_report)
    family = load(args.family_report)
    shared = load(args.shared_report)
    profile = load(args.profile)
    checks["deterministic_double_build"] = (
        build.get("deterministic_rebuild_equal") is True
        and build.get("numeric_analysis_repeated") is False
        and build.get("node0004_workload_rebuilt") is False
        and build.get("configuration_rebuilt") is False
        and build.get("observer_rebuilt") is False
        and build.get("functional_rtl_modified") is False
        and build.get("server_action") is False
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
    for name, passed in checks.items():
        if not passed:
            errors.append(f"{name} failed")

    report = {
        "schema": "conv-node0004-v60-final-zip-audit-v1",
        "package_id": PACKAGE,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {
            "path": str(args.zip.resolve()),
            "bytes": args.zip.stat().st_size,
            "sha256": current_sha,
        },
        "source_v59": {
            "path": str(args.source_v59.resolve()),
            "bytes": args.source_v59.stat().st_size,
            "sha256": sha_file(args.source_v59),
            "disposition": "SUPERSEDED_NEVER_RUN",
        },
        "frozen_payload_comparison": {
            "source_member_count": len(previous),
            "target_member_count": len(current),
            "common_members": len(common),
            "frozen_byte_equal_members": len(frozen),
            "changed_members": changed,
            "added_members": added,
            "removed_members": removed,
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
                "gate_id": "frozen_numeric_workload_config_observer",
                "applicability": "receipt_reuse",
                "status": "PASS"
                if checks["frozen_payload_byte_equal"]
                else "FAIL",
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
            "Local package/install/runtime-layout, exact 86-input open, "
            "finalizer and fixed-result publication correctness only. "
            "No production compile, simulation, natural terminal, formal-D, "
            "E4 or E5 claim."
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
                "pass": not errors,
                "errors": len(errors),
                "output": str(args.output.resolve()),
            },
            sort_keys=True,
        )
    )
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
