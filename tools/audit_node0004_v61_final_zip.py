#!/usr/bin/env python3
"""Independent final-ZIP audit for node0004 v61 mapped-loop successor."""

from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


PACKAGE = "r5_n4_hw_v61_lcmap_argv_fix"
SOURCE = "r5_n4_hw_v60_install_only"
EXPECTED_ZIP_SHA = (
    "c78e62cde4f8e185f801900773117017982920b9a479996a1c31af8a1dae1e96"
)
EXPECTED_SOURCE_SHA = (
    "cb3342e90510e4cd1e66afb9a19977cc5eae725abccf987346757d3d34937ec8"
)
SUBSTANTIVE_CHANGED = {
    "PREPARE_AND_RUN.sh",
    "README.md",
    "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
    "package_manifest.json",
    "tb_probe/native_return_observer.svh",
}


def sha_file(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


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


def identity_normalized(value: bytes) -> bytes:
    return value.replace(PACKAGE.encode(), SOURCE.encode())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--source-v60", required=True, type=Path)
    parser.add_argument("--build-report", required=True, type=Path)
    parser.add_argument("--family-report", required=True, type=Path)
    parser.add_argument("--shared-report", required=True, type=Path)
    parser.add_argument("--observer-report", required=True, type=Path)
    parser.add_argument("--predicate-report", required=True, type=Path)
    parser.add_argument("--return-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    errors: list[str] = []
    checks: dict[str, bool] = {}
    zip_sha = sha_file(args.zip)
    checks["zip_identity"] = zip_sha == EXPECTED_ZIP_SHA
    checks["source_identity"] = sha_file(args.source_v60) == EXPECTED_SOURCE_SHA
    sidecar = args.sidecar.read_text(encoding="ascii").strip().split()
    checks["sidecar_identity"] = sidecar == [EXPECTED_ZIP_SHA, args.zip.name]

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
        checks["manifest_identity"] = manifest["install_name"] == PACKAGE
        contract = json.loads(current["SERVER_RUNTIME_LAYOUT_CONTRACT.json"])
        checks["install_only_v2_contract"] = (
            contract["package_id"] == PACKAGE
            and contract["install_name"] == PACKAGE
            and contract["required_preexisting_parents"] == ["install"]
            and contract["package_creatable_parent_dirs"]
            == ["install/cfg_pkg", "install/codex_runs"]
            and contract["runtime_roots"]["cfg_root"]
            == f"install/cfg_pkg/{PACKAGE}"
            and contract["runtime_roots"]["run_root"]
            == f"install/codex_runs/{PACKAGE}/{{attempt}}"
            and contract["fixed_result_root"] == "/home/panqs/ndp/simresult"
            and contract["tb_cwd"] == "$server_root"
            and contract["path_budget"]["max_projected_absolute_path_chars"]
            == 218
        )
        runner = current["PREPARE_AND_RUN.sh"].decode()
        checks["runner_exact_argv_receipt"] = (
            "simulator_argv.txt" in runner
            and "+RETURN_OBS_DTERM_OWNER" in runner
            and "+RETURN_OBS_LC13_LC14" in runner
            and "+RETURN_OBS_LC9_ACTUAL" in runner
            and "+RETURN_HANG_DIAG" in runner
        )

    with zipfile.ZipFile(args.source_v60) as archive:
        previous = members(archive)
    common = set(previous) & set(current)
    added = sorted(set(current) - set(previous))
    removed = sorted(set(previous) - set(current))
    normalized_differences = sorted(
        name
        for name in common
        if identity_normalized(current[name]) != previous[name]
    )
    permitted_normalized = SUBSTANTIVE_CHANGED | {
        "provenance/v60_to_v61_lcmap_argv_fix.json"
    }
    checks["member_set_delta_exact"] = (
        added == ["provenance/v60_to_v61_lcmap_argv_fix.json"]
        and not removed
    )
    checks["normalized_changed_surface_bounded"] = (
        set(normalized_differences) <= SUBSTANTIVE_CHANGED
    )
    binary_names = sorted(
        name for name in common
        if name.endswith(".bin")
        or "matrix_" in name
        or name.endswith(".golden")
    )
    checks["binary_numeric_workload_golden_frozen"] = (
        bool(binary_names)
        and all(previous[name] == current[name] for name in binary_names)
    )
    frozen_normalized = sorted(
        common - SUBSTANTIVE_CHANGED
    )
    checks["all_other_members_identity_only_or_equal"] = all(
        identity_normalized(current[name]) == previous[name]
        for name in frozen_normalized
    )

    build = load(args.build_report)
    family = load(args.family_report)
    shared = load(args.shared_report)
    observer = load(args.observer_report)
    predicate = load(args.predicate_report)
    return_report = load(args.return_report)
    checks["deterministic_double_build"] = (
        build.get("deterministic_rebuild_equal") is True
        and build.get("numeric_analysis_repeated") is False
        and build.get("node0004_workload_rebuilt") is False
        and build.get("configuration_rebuilt") is False
        and build.get("mapping_rebuilt") is False
        and build.get("bitstream_rebuilt") is False
        and build.get("functional_rtl_modified") is False
        and build.get("server_action") is False
    )
    checks["family_runner_validation"] = (
        family.get("valid") is True and not family.get("errors")
    )
    checks["shared_runtime_layout_validation"] = (
        shared.get("pass") is True and not shared.get("errors")
    )
    checks["changed_observer_validation"] = (
        observer.get("valid") is True and not observer.get("errors")
    )
    checks["predicate_trace_validation"] = (
        predicate.get("valid") is True and not predicate.get("errors")
    )
    checks["v60_return_analysis_valid"] = (
        return_report.get("valid") is True and not return_report.get("errors")
    )
    for name, passed in checks.items():
        if not passed:
            errors.append(f"{name} failed")

    report = {
        "schema": "conv-node0004-v61-final-zip-audit-v1",
        "package_id": PACKAGE,
        "classification": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
        "candidate_release": False,
        "FINAL_ZIP_RULE_SELF_AUDIT_PASS": not errors,
        "errors": errors,
        "checks": checks,
        "zip": {
            "path": str(args.zip.resolve()),
            "bytes": args.zip.stat().st_size,
            "sha256": zip_sha,
        },
        "source_v60": {
            "path": str(args.source_v60.resolve()),
            "bytes": args.source_v60.stat().st_size,
            "sha256": sha_file(args.source_v60),
            "disposition": "TESTED_RETURN_CONSUMED",
        },
        "frozen_payload_comparison": {
            "source_member_count": len(previous),
            "target_member_count": len(current),
            "common_members": len(common),
            "binary_frozen_members": len(binary_names),
            "identity_normalized_frozen_members": len(frozen_normalized),
            "normalized_substantive_changes": normalized_differences,
            "added_members": added,
            "removed_members": removed,
        },
        "release_gate_matrix": [
            {
                "gate_id": "package_bootstrap_path_runtime_d",
                "applicability": "blocking_applicable",
                "status": "PASS"
                if checks["family_runner_validation"] else "FAIL",
                "blocking": True,
            },
            {
                "gate_id": "runtime_layout_and_sca_open",
                "applicability": "blocking_applicable",
                "status": "PASS"
                if checks["shared_runtime_layout_validation"] else "FAIL",
                "blocking": True,
            },
            {
                "gate_id": "changed_package_local_hdl",
                "applicability": "blocking_applicable",
                "status": "PASS"
                if checks["changed_observer_validation"] else "FAIL",
                "blocking": True,
            },
            {
                "gate_id": "changed_observer_canonical_semantics",
                "applicability": "blocking_applicable",
                "status": "PASS"
                if checks["predicate_trace_validation"] else "FAIL",
                "blocking": True,
            },
            {
                "gate_id": "return_result_conjunction",
                "applicability": "blocking_applicable",
                "status": "PASS"
                if checks["v60_return_analysis_valid"] else "FAIL",
                "blocking": True,
            },
            {
                "gate_id": "materialized_config",
                "applicability": "receipt_reuse",
                "status": "PASS"
                if checks["binary_numeric_workload_golden_frozen"]
                else "FAIL",
                "blocking": False,
            },
            {
                "gate_id": "functional_rtl",
                "applicability": "not_applicable",
                "status": "NOT_APPLICABLE",
                "blocking": False,
            },
            {
                "gate_id": "report_style",
                "applicability": "record_only",
                "status": "RECORDED",
                "blocking": False,
            },
        ],
        "rule_receipts_post_generation": {
            "agent": "32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f",
            "plan_mutable": "43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70",
            "index": "68c13cbd1461ca2a506174678d22cfdbfdc5aced25ad80150d4e4cacece7f2be",
            "server": "16f7773796dccf4f27a5e412bb200f7b4190ffb87742d3dd2e466866a7f77dde",
            "common_config": "dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1",
            "ndp_fields": "603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055",
            "int8_sa": "54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce",
            "hardware_readme": "0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6",
        },
        "claim_boundary": (
            "Local package correctness and diagnostic fidelity only. No "
            "production compile, DUT natural terminal, formal D, E4, or E5 "
            "claim is made for v61 before a server return."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"pass": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
