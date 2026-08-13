#!/usr/bin/env python3
"""Build p30 from the formally consumed p29 diagnostic package."""

from __future__ import annotations

import argparse
import json
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import build_conv_native_four_lane_0ccae916_p28_b5release_package as p28


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "r5_n4_0cc_p29_row2own"
PACKAGE_ID = "r5_n4_0cc_p30_bankvalid"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{SOURCE_ID}.zip"
SOURCE_BYTES = 5_920_486
SOURCE_SHA256 = "43cfd63753ee964a92efec955f1dcba05c772c659406bd0142da8e37d2bd0f49"
P29_ANALYSIS = ROOT / "outputs/conv_native_four_lane_0ccae916_p29_return_analysis/report_v2.json"
P29_ANALYSIS_SHA256 = "7e290b1bcfc83061133996561ba3c04acc2185cd5aee3a63f0680ce35c7fdd98"
SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p30_bankvalid_source_bound_v2"
GENERATED = SOURCE_BOUND / "generated"
DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p30_bankvalid/build"
base = p28.base


class BuildError(RuntimeError):
    pass


def write_json(path: Path, value: Any) -> None:
    p28.write_json(path, value)


def configure_p28() -> None:
    p28.SOURCE_ID = SOURCE_ID
    p28.PACKAGE_ID = PACKAGE_ID
    p28.SOURCE_ZIP = SOURCE_ZIP
    p28.SOURCE_BYTES = SOURCE_BYTES
    p28.SOURCE_SHA256 = SOURCE_SHA256
    p28.SOURCE_BOUND = SOURCE_BOUND
    p28.GENERATED = GENERATED
    p28.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    p28.configure_base()


def receipt(path: Path, package: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(package).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": base.sha256(path),
    }


def patch_post_sim(package: Path) -> dict[str, dict[str, Any]]:
    request_path = package / "contracts/server_post_sim_return_request.json"
    request = json.loads(request_path.read_text(encoding="utf-8"))
    if request.get("package_id") != PACKAGE_ID:
        raise BuildError("post-sim request identity rebinding differs")
    request["claim_boundary"] = (
        "p30 c0 Buffer5 row2 bank-ready and per-bank clear/write diagnostic only. Core publication is "
        "independent of parser/plugin success; natural terminal, formal 320D and E3/E4/E5 remain dynamic and unclaimed."
    )
    write_json(request_path, request)
    contract_path = package / "contracts/server_post_sim_return_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("package_id") != PACKAGE_ID:
        raise BuildError("post-sim contract identity rebinding differs")
    contract["request_sha256"] = base.sha256(request_path)
    contract["claim_boundary"] = request["claim_boundary"]
    write_json(contract_path, contract)
    helper = package / "package_tools/server_post_sim_return.py"
    expected_helper = "87c78dd8408d75430074f05e07e99ba3d1b7db3bc5907860b9d15969b172b0b8"
    if base.sha256(helper) != expected_helper or contract.get("helper_sha256") != expected_helper:
        raise BuildError("shared post-sim helper identity differs")
    return {
        "helper": receipt(helper, package),
        "request": receipt(request_path, package),
        "contract": receipt(contract_path, package),
    }


def patch_contract_docs(package: Path) -> None:
    contract_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["claim_boundary"] = (
        "p30 preserves the p29 workload/config and changes only the generated Buffer5 row2 bank-valid/ready "
        "diagnostic plus fresh identity-bound return contracts."
    )
    paths = base.projected_paths(package, contract)
    longest = max(paths, key=lambda item: (len(item), item))
    contract["path_budget"]["max_projected_absolute_path_chars"] = (
        contract["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest)
    )
    write_json(contract_path, contract)

    source_contract_path = package / "diagnostics/source_bound_final_zip_contract.json"
    source_contract = json.loads(source_contract_path.read_text(encoding="utf-8"))
    source_contract["claim_boundary"] = (
        "p30 source-bound Buffer5 c0 bank-ready and per-bank clear/write diagnostic only; production "
        "compile/simulation, natural terminal, formal D and E3-E5 remain dynamic and unclaimed."
    )
    write_json(source_contract_path, source_contract)

    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    pointer_value = json.loads(pointer.read_text(encoding="utf-8"))
    pointer_value.update({
        "schema": "conv-native-four-lane-p30-bankvalid-pointer-v1",
        "package_identity": PACKAGE_ID,
        "status": "PACKAGE_READY_NOT_RUN",
    })
    write_json(pointer, pointer_value)
    (package / "README.md").write_text(
        "# Native four-lane Conv p30 Buffer5 bank-valid diagnostic\n\n"
        "Fresh successor of tested p29. It preserves all 87 installed payload members and uses the shared "
        "source-bound generator to distinguish a legitimately occupied row2 bank from fully-ready banks with "
        "a low aggregate ARM-ready result.\n\n"
        "```bash\nbash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02\n```\n",
        encoding="utf-8",
        newline="\n",
    )


def patch_manifest(
    package: Path,
    changed: list[str],
    generated: dict[str, dict[str, Any]],
    runner: dict[str, Any],
    post_sim: dict[str, dict[str, Any]],
) -> None:
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    if base.sha256(P29_ANALYSIS) != P29_ANALYSIS_SHA256:
        raise BuildError("formal p29 analysis identity differs")
    analysis = json.loads(P29_ANALYSIS.read_text(encoding="utf-8"))
    if analysis.get("valid") is not True or analysis.get("status") != "P29_COMPETING_WRITER_CLOSED_BANK_VALID_READY_RECOMPUTE_SUCCESSOR_REQUIRED":
        raise BuildError("formal p29 analysis is not accepted")
    value.update({
        "schema": "conv-native-four-lane-0ccae916-p30-bankvalid-package-v1",
        "package_identity": PACKAGE_ID,
        "install_name": PACKAGE_ID,
        "workload_install_name": PACKAGE_ID,
        "run_namespace": f"install/codex_runs/{PACKAGE_ID}/a0",
        "return_name": f"{PACKAGE_ID}_<execution_id>_return.zip",
        "status": "PACKAGE_READY_NOT_RUN",
    })
    value["source_p29_formal_return_analysis"] = {
        "path": P29_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": P29_ANALYSIS_SHA256,
        "return_sha256": analysis["return_identity"]["sha256"],
        "source_zip_sha256": analysis["source_identity"]["sha256"],
        "classification": analysis["classification"],
        "last_progress_guard": analysis["failure_localization"]["LAST_PROVEN_GOOD"],
        "first_divergence": analysis["failure_localization"]["FIRST_DIVERGENCE"],
    }
    value["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "tested",
        "reason": "p29 closes competing row2 writers; p30 distinguishes occupied-bank validity from aggregate-ready recomputation",
        "authorized_config_change": None,
        "numeric_w3_golden_repeated": False,
    }
    value["source_bound_observer_binding"].update({
        "claim_boundary": "c0 Buffer5 row2 bank-ready and per-bank clear/write state only",
        "generated_members": generated,
        "runner": runner,
        "functional_rtl_changed": False,
    })
    value["post_sim_return_core"].update({
        "members": post_sim,
        "runner": {
            "path": "PREPARE_AND_RUN.sh",
            "bytes": (package / "PREPARE_AND_RUN.sh").stat().st_size,
            "sha256": base.sha256(package / "PREPARE_AND_RUN.sh"),
            "shared_post_sim_invocations": (package / "PREPARE_AND_RUN.sh").read_text(encoding="utf-8").count('python3 "$post_sim_helper" finalize --request "$post_sim_request"'),
        },
        "claim_boundary": json.loads((package / "contracts/server_post_sim_return_request.json").read_text(encoding="utf-8"))["claim_boundary"],
    })
    value["identity_rebound_text_members"] = changed
    value["release_gate_applicability"].update({
        "materialized_config": "receipt_reuse_byte_equal_p29",
        "numeric_w3_golden": "record_only_byte_equal_receipt_reuse",
    })
    value["release_gate_matrix"]["materialized_config"].update({
        "applicability": "receipt_reuse",
        "blocking": False,
        "pass": True,
        "scope": "87 p29 installed payload members byte-equal and SCA identity-normalized equal",
    })
    value["release_gate_matrix"]["source_bound_observer_generation"]["pass"] = True
    value["release_gate_matrix"]["source_bound_final_zip"]["pass"] = None
    value["release_gate_matrix"]["post_sim_return_core"]["pass"] = None
    contract = json.loads((package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json").read_text(encoding="utf-8"))
    projected = base.projected_paths(package, contract)
    longest = max(projected, key=lambda item: (len(item), item))
    inner = [item.relative_to(package).as_posix() for item in package.rglob("*") if item.is_file() and item != path] + ["package_manifest.json"]
    value["path_length_budget"].update({
        "longest_projected_relative_path": longest,
        "longest_projected_relative_path_chars": len(longest),
        "max_projected_relative_path_chars": len(longest),
        "max_projected_absolute_path_chars": contract["path_budget"]["declared_target_root_max_chars"] + 1 + len(longest),
        "max_zip_member_chars": max(len(f"{PACKAGE_ID}/{relative}") for relative in inner),
        "max_inner_suffix_chars": max(map(len, inner)),
        "max_inner_depth": max(len(PurePosixPath(relative).parts) for relative in inner),
        "max_inner_component_chars": max(len(part) for relative in inner for part in PurePosixPath(relative).parts),
        "outer_identity_repeated_inside": False,
    })
    base.refresh_manifest_files(package, value)
    write_json(path, value)


def build_directory(destination: Path) -> tuple[Path, dict[str, Any]]:
    configure_p28()
    package = base.safe_extract(SOURCE_ZIP, destination)
    changed = p28.replace_identity(package)
    generated = p28.install_generated(package)
    runner = p28.patch_runner(package)
    post_sim = patch_post_sim(package)
    patch_contract_docs(package)
    patch_manifest(package, changed, generated, runner, post_sim)
    return package, {"identity_members": changed, "generated": generated, "runner": runner, "post_sim": post_sim}


def frozen_checks(package: Path) -> dict[str, Any]:
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        prefix = SOURCE_ID + "/"
        source = {name[len(prefix):]: archive.read(name) for name in archive.namelist() if name.startswith(prefix) and not name.endswith("/")}
    frozen = sorted(name for name in source if name.startswith("workload/runtime/runs/c0/install/"))
    sca = {
        relative: (package / relative).read_text(encoding="utf-8").replace(PACKAGE_ID, SOURCE_ID) == source[relative].decode()
        for relative in ("workload/runtime/runs/c0/sca_cfg.json", "workload/runtime/runs/c0/sca_cfg_D.json")
    }
    return {
        "source_p29_zip_sha256": SOURCE_SHA256,
        "frozen_install_payload_member_count": len(frozen),
        "frozen_install_payload_byte_equal": all((package / name).read_bytes() == source[name] for name in frozen),
        "sca_identity_normalized_equal": sca,
        "numeric_w3_golden_workload_config_mapping_bitstream_execplan_changed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = (output / PACKAGE_ID, output / f"{PACKAGE_ID}.zip", output / f"{PACKAGE_ID}.zip.sha256", output / f"{PACKAGE_ID}.build.json")
    if any(target.exists() for target in targets):
        raise BuildError("refusing to overwrite p30 output")
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or base.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p29 source differs")
    package, receipts = build_directory(output)
    frozen = frozen_checks(package)
    if not frozen["frozen_install_payload_byte_equal"] or not all(frozen["sca_identity_normalized_equal"].values()) or frozen["frozen_install_payload_member_count"] != 87:
        raise BuildError("frozen p29 payload differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    base.deterministic_zip(package, zip_path)
    with tempfile.TemporaryDirectory(prefix=".p30_repeat_", dir=ROOT) as temporary:
        repeated, _ = build_directory(Path(temporary))
        repeat_zip = Path(temporary) / f"{PACKAGE_ID}.zip"
        base.deterministic_zip(repeated, repeat_zip)
        deterministic = repeat_zip.read_bytes() == zip_path.read_bytes()
    if not deterministic:
        raise BuildError("p30 deterministic double build differs")
    zip_sha = base.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{zip_sha}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p30-bankvalid-build-v1",
        "status": "PACKAGE_BUILT_PENDING_FINAL_AUDIT",
        "package_identity": PACKAGE_ID,
        "source_p29_zip_sha256": SOURCE_SHA256,
        "source_p29_analysis_sha256": P29_ANALYSIS_SHA256,
        "zip": str(zip_path),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha,
        "deterministic_double_build": deterministic,
        "receipts": receipts,
        "frozen": frozen,
        "functional_rtl_modified": False,
        "server_action": False,
    }
    write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
