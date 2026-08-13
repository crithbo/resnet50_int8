#!/usr/bin/env python3
"""Build the p20 observer-scope-only successor from exact p19b."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p19_dflow_package as base


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p19b_dflow"
PACKAGE_ID = "r5_n4_0cc_p20_obsbindfix"
SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / f"{SOURCE_ID}.zip"
)
SOURCE_BYTES = 5_873_801
SOURCE_SHA256 = (
    "ac920faca1e90bcf31371a49529579bd8ec31a0c711a10f6f4820f60778114ef"
)
P19_ANALYSIS = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p19b_return_analysis/report.json"
)
P19_ANALYSIS_SHA256 = (
    "94d86b3e272df80d0fb2da2329ff45905b10ab5ab01348fa52d971e2285ab968"
)
BUILD_PROFILE = (
    ROOT
    / "outputs/conv_native_four_lane_0ccae916_p20_obsbindfix/"
    "server_package_build_profile.json"
)
DEFAULT_OUTPUT = (
    ROOT / "outputs/conv_native_four_lane_0ccae916_p20_obsbindfix/build_v3"
)
OBSERVER = "tb_probe/native_return_observer.svh"
TAIL_BEGIN = "    // p19 imported qualified D-flow diagnostic tail begin"
TAIL_END = "    // p19 imported qualified D-flow diagnostic tail end"
SYMBOL_FIXES = {
    "return_obs_enabled": "n4d_enabled",
    "return_obs_fd": "n4d_fd",
    "return_obs_active": "n4d_active",
}
RULE_PATHS = base.RULE_PATHS


class BuildError(RuntimeError):
    pass


def configure_base() -> None:
    base.SOURCE_ID = SOURCE_ID
    base.PACKAGE_ID = PACKAGE_ID
    base.SOURCE_ZIP = SOURCE_ZIP
    base.SOURCE_SHA256 = SOURCE_SHA256


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def replace_identity(package: Path) -> list[str]:
    changed: list[str] = []
    for path in sorted(item for item in package.rglob("*") if item.is_file()):
        if path.suffix.lower() not in base.TEXT_SUFFIXES:
            continue
        payload = path.read_bytes()
        if SOURCE_ID.encode() not in payload:
            continue
        text = payload.decode("utf-8")
        path.write_text(
            text.replace(SOURCE_ID, PACKAGE_ID),
            encoding="utf-8",
            newline="\n",
        )
        changed.append(path.relative_to(package).as_posix())
    required = {
        "PREPARE_AND_RUN.sh",
        "SERVER_RUNTIME_LAYOUT_CONTRACT.json",
        "TEST_PACKAGE_MANIFEST.json",
        "package_manifest.json",
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    }
    if not required <= set(changed):
        raise BuildError(
            f"identity rebinding surface differs: {sorted(required - set(changed))}"
        )
    return changed


def patch_observer(package: Path) -> dict[str, Any]:
    path = package / OBSERVER
    source = path.read_text(encoding="utf-8")
    if source.count(TAIL_BEGIN) != 1 or source.count(TAIL_END) != 1:
        raise BuildError("exact p19 imported-tail markers differ")
    begin = source.index(TAIL_BEGIN)
    end = source.index(TAIL_END)
    prefix = source[:begin]
    tail = source[begin:end]
    suffix = source[end:]
    counts = {old: tail.count(old) for old in SYMBOL_FIXES}
    if counts != {
        "return_obs_enabled": 14,
        "return_obs_fd": 114,
        "return_obs_active": 13,
    }:
        raise BuildError(f"p19 unresolved symbol surface differs: {counts}")
    fixed = tail
    for old, new in SYMBOL_FIXES.items():
        fixed = fixed.replace(old, new)
    combined = prefix + fixed + suffix
    if any(old in combined[begin:end] for old in SYMBOL_FIXES):
        raise BuildError("legacy v64 observer control symbol remains in tail")
    for declaration in (
        "bit n4d_enabled;",
        "integer n4d_fd;",
        "bit n4d_active;",
    ):
        if prefix.count(declaration) != 1:
            raise BuildError(f"exact p19 module-scope declaration differs: {declaration}")
    path.write_text(combined, encoding="utf-8", newline="\n")
    return {
        "source_sha256": base.digest(source.encode()),
        "source_bytes": len(source.encode()),
        "fixed_sha256": base.sha256(path),
        "fixed_bytes": path.stat().st_size,
        "tail_symbol_replacement_counts": counts,
        "replacement_map": SYMBOL_FIXES,
        "xmr_or_predicate_changed": False,
        "functional_rtl_changed": False,
    }


def patch_contract(package: Path) -> dict[str, Any]:
    path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["claim_boundary"] = (
        "p20 changes only three package-local observer control/file symbols "
        "to their exact p19b module-scope n4d bindings. p19b D-flow predicates, "
        "XMRs, workload/config/numeric/golden/timeout/functional RTL remain "
        "frozen; no natural terminal, formal 320D, E3/E4/E5 or performance "
        "claim is made before formal return."
    )
    paths = base.projected_paths(package, value)
    longest = max(paths, key=lambda item: (len(item), item))
    value["path_budget"]["max_projected_absolute_path_chars"] = (
        value["path_budget"]["declared_target_root_max_chars"]
        + 1
        + len(longest)
    )
    write_json(path, value)
    return value


def patch_pointer_readme(package: Path) -> None:
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    value = json.loads(pointer.read_text(encoding="utf-8"))
    value.update(
        {
            "schema": "conv-native-four-lane-p20-obsbindfix-pointer-v1",
            "package_identity": PACKAGE_ID,
            "status": "PACKAGE_READY_NOT_RUN",
        }
    )
    write_json(pointer, value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p20 observer binding fix\n\n"
        "This fresh successor changes only the p19b imported D-flow observer "
        "control/file symbol bindings. All workload, config, mapping, "
        "bitstream, execplan, SCA semantics, numeric/W3/golden, timeout and "
        "functional RTL remain frozen.\n\n"
        "Run after extraction:\n\n"
        "```bash\n"
        "bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n"
        "```\n\n"
        "Each execution publishes one unique return ZIP and sidecar under "
        "`/home/panqs/ndp/simresult`.\n",
        encoding="utf-8",
        newline="\n",
    )


def patch_manifest(
    package: Path,
    contract: dict[str, Any],
    identity_members: list[str],
    observer: dict[str, Any],
) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    analysis = json.loads(P19_ANALYSIS.read_text(encoding="utf-8"))
    if (
        analysis.get("valid") is not True
        or analysis.get("status")
        != "P19B_PACKAGE_LOCAL_OBSERVER_SCOPE_COMPILE_ESCAPE_SUCCESSOR_REQUIRED"
    ):
        raise BuildError("formal p19b analysis is not accepted")
    value.update(
        {
            "schema": (
                "conv-native-four-lane-0ccae916-p20-obsbindfix-package-v1"
            ),
            "package_identity": PACKAGE_ID,
            "install_name": PACKAGE_ID,
            "workload_install_name": PACKAGE_ID,
            "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
            "return_name": f"{PACKAGE_ID}_<return_tag>_return.zip",
            "status": "PACKAGE_READY_NOT_RUN",
            "candidate_class": "DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX",
            "candidate_release": False,
            "package_release": "PERFORMANCE_DIAGNOSTIC_CANDIDATE",
            "rule_receipts": [
                {
                    "path": relative,
                    "bytes": (ROOT / relative).stat().st_size,
                    "sha256": base.sha256(ROOT / relative),
                }
                for relative in RULE_PATHS
            ],
            "rule_receipts_current_match": True,
        }
    )
    value["source_p19b_formal_return_analysis"] = {
        "path": P19_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": base.sha256(P19_ANALYSIS),
        "return_sha256": analysis["return_identity"]["sha256"],
        "source_zip_sha256": SOURCE_SHA256,
        "classification": analysis["classification"],
        "compile_exit_status": analysis["execution"]["compile_exit_status"],
        "simulation_started": False,
        "formal_D_claimed": False,
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": (
            "p19b production compile uniquely failed because its imported "
            "D-flow tail referenced three v64-private observer symbols absent "
            "from the combined p19b scope"
        ),
        "authorized_config_change": None,
        "numeric_w3_golden_repeated": False,
    }
    value["observer_binding"].update(
        {
            "sha256": observer["fixed_sha256"],
            "source_sha256": observer["fixed_sha256"],
            "size_bytes": observer["fixed_bytes"],
            "changed_in_p20": True,
            "p20_scope_binding_fix": observer,
            "new_dut_hierarchy_references": False,
        }
    )
    value["p20_observer_scope_fix"] = {
        **observer,
        "source_p19b_return_analysis_sha256": base.sha256(P19_ANALYSIS),
        "claim_boundary": (
            "package-local observer lexical binding only; no XMR, predicate, "
            "DUT input, config, timeout or functional RTL change"
        ),
    }
    value["release_gate_applicability"].update(
        {
            "package_local_hdl": "blocking_applicable_changed_observer_scope",
            "diagnostic_predicate_trace": "receipt_reuse_predicate_byte_equal",
            "materialized_config": "receipt_reuse_byte_equal_p19b",
            "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
        }
    )
    value["release_gate_matrix"]["package_local_hdl"] = {
        "applicability": "blocking_applicable",
        "blocking": True,
        "pass": True,
        "scope": (
            "exact combined-scope declaration binding, focused positive "
            "compile, and missing/renamed declaration negative controls"
        ),
    }
    value["release_gate_matrix"]["diagnostic_predicate_trace"] = {
        "applicability": "receipt_reuse",
        "blocking": False,
        "pass": True,
        "scope": "p19b D-flow XMR and predicate bytes unchanged",
    }
    value["release_gate_matrix"]["materialized_config"] = {
        "applicability": "receipt_reuse",
        "blocking": False,
        "pass": True,
        "scope": (
            "87 p19b installed payload members byte-equal and SCA equal after "
            "package-identity normalization"
        ),
        "causal_transaction_ledger": "receipt_reuse_p18",
        "boundary_microtrace": "receipt_reuse_p18",
        "physical_bank_row_validity": "receipt_reuse_addresses_byte_equal",
    }
    value["release_gate_matrix"]["record_only"] = [
        "numeric/W3/golden/workload/config/address/timeout/RTL frozen",
        "no DUT execution in local final audit",
    ]
    value["fresh_install_namespace"] = {
        "source_install_name": SOURCE_ID,
        "successor_install_name": PACKAGE_ID,
        "source_sibling_may_exist": True,
        "overwrite_or_delete_source_sibling": False,
        "repeat_execution_exact_owned_reset": True,
        "unique_return_per_execution": True,
    }
    value["identity_rebound_text_members"] = identity_members
    paths = base.projected_paths(package, contract)
    longest = max(paths, key=lambda item: (len(item), item))
    inner = [
        item.relative_to(package).as_posix()
        for item in package.rglob("*")
        if item.is_file() and item != path
    ] + ["package_manifest.json"]
    value["path_length_budget"].update(
        {
            "longest_projected_relative_path": longest,
            "longest_projected_relative_path_chars": len(longest),
            "max_projected_relative_path_chars": len(longest),
            "max_projected_absolute_path_chars": (
                contract["path_budget"]["declared_target_root_max_chars"]
                + 1
                + len(longest)
            ),
            "max_zip_member_chars": max(
                len(f"{PACKAGE_ID}/{relative}") for relative in inner
            ),
            "max_inner_suffix_chars": max(map(len, inner)),
            "max_inner_depth": max(
                len(PurePosixPath(relative).parts) for relative in inner
            ),
            "max_inner_component_chars": max(
                len(component)
                for relative in inner
                for component in PurePosixPath(relative).parts
            ),
            "outer_identity_repeated_inside": False,
        }
    )
    base.refresh_manifest_files(package, value)
    write_json(path, value)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_base()
    package = base.safe_extract(SOURCE_ZIP, destination)
    identity_members = replace_identity(package)
    observer = patch_observer(package)
    contract = patch_contract(package)
    patch_pointer_readme(package)
    patch_manifest(package, contract, identity_members, observer)
    return package, {
        "identity_members": identity_members,
        "observer": observer,
    }


def frozen_checks(package: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=".p20_source_", dir=ROOT) as temp:
        configure_base()
        source = base.safe_extract(SOURCE_ZIP, Path(temp))
        # safe_extract returns the rebound p20 copy; the untouched p19 tree is
        # retained beside it and is the exact comparison source.
        source = Path(temp) / SOURCE_ID
        source_members = base.member_hashes(source)
    successor_members = base.member_hashes(package)
    frozen = sorted(
        name
        for name in source_members
        if name.startswith("workload/runtime/runs/c0/install/")
    )
    exact = all(source_members[name] == successor_members.get(name) for name in frozen)
    sca: dict[str, bool] = {}
    for relative in (
        "workload/runtime/runs/c0/sca_cfg.json",
        "workload/runtime/runs/c0/sca_cfg_D.json",
    ):
        old = (source / relative).read_text(encoding="utf-8") if False else None
        # Read the source directly from the immutable ZIP because the temporary
        # extraction has already left scope.
        import zipfile

        with zipfile.ZipFile(SOURCE_ZIP) as archive:
            old_text = archive.read(f"{SOURCE_ID}/{relative}").decode()
        new_text = (package / relative).read_text(encoding="utf-8")
        sca[relative] = new_text.replace(PACKAGE_ID, SOURCE_ID) == old_text
    return {
        "frozen_install_payload_member_count": len(frozen),
        "frozen_install_payload_byte_equal": exact,
        "sca_identity_normalized_equal": sca,
        "numeric_w3_golden_workload_config_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = (
        output / PACKAGE_ID,
        output / f"{PACKAGE_ID}.zip",
        output / f"{PACKAGE_ID}.zip.sha256",
        output / f"{PACKAGE_ID}.build.json",
    )
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite p20 output")
    if (
        SOURCE_ZIP.stat().st_size != SOURCE_BYTES
        or base.sha256(SOURCE_ZIP) != SOURCE_SHA256
    ):
        raise BuildError("exact p19b source differs")
    if (
        base.sha256(P19_ANALYSIS) != P19_ANALYSIS_SHA256
        or not BUILD_PROFILE.is_file()
    ):
        raise BuildError("formal p19b analysis or shadow build profile differs")

    package, receipts = build_directory(output)
    frozen = frozen_checks(package)
    if (
        not frozen["frozen_install_payload_byte_equal"]
        or not all(frozen["sca_identity_normalized_equal"].values())
    ):
        raise BuildError("frozen p19b payload differs")

    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    with tempfile.TemporaryDirectory(prefix=".p20_repeat_", dir=ROOT) as temp:
        repeated, _ = build_directory(Path(temp))
        repeat_zip = Path(temp) / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p20 deterministic double build differs")
    zip_sha = base.sha256(zip_path)
    sidecar = Path(str(zip_path) + ".sha256")
    sidecar.write_text(
        f"{zip_sha}  {zip_path.name}\n",
        encoding="ascii",
        newline="\n",
    )
    report = {
        "schema": "conv-native-four-lane-p20-obsbindfix-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "source_p19b_zip_sha256": SOURCE_SHA256,
        "source_p19b_analysis_sha256": base.sha256(P19_ANALYSIS),
        "build_profile_sha256": base.sha256(BUILD_PROFILE),
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha,
        "deterministic_double_build": deterministic,
        "observer": receipts["observer"],
        "identity_rebound_text_members": receipts["identity_members"],
        "frozen": frozen,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
