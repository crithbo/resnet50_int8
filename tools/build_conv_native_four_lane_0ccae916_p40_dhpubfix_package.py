#!/usr/bin/env python3
"""Build the p39-return-driven public-surface compile-fix successor."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import build_conv_native_four_lane_0ccae916_p39_compilecore_package as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p40_dhpubfix"
SOURCE_ID = "r5_n4_0cc_p39_compilecore"
SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p39_compilecore.zip"
SOURCE_BYTES = 5_973_514
SOURCE_SHA256 = "d99d078a53ec88f5dc0374f0b080350d2e62a6e2121237f7da4dbce9a6c6b515"
EPOCH = "20260811-p39-observer-private-xmr-public-surface-successor-v1"
RULE_IDS = [
    "CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001",
    "CDA-SERVER-COMPILEFAIL-CORE-RETURN-ROOT-CAUSE-001",
]
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p40_dhpubfix"
PREBUILD = BASE / "prebuild"
DEFAULT_OUTPUT = BASE / "build"
PYTHON = sys.executable


class BuildError(RuntimeError):
    pass


def configure_prior() -> None:
    prior.PACKAGE_ID = PACKAGE_ID
    prior.SOURCE_ID = SOURCE_ID
    prior.SOURCE_ZIP = SOURCE_ZIP
    prior.SOURCE_BYTES = SOURCE_BYTES
    prior.SOURCE_SHA256 = SOURCE_SHA256
    prior.EPOCH = EPOCH
    prior.RULE_IDS = RULE_IDS
    prior.BASE = BASE
    prior.PREBUILD = PREBUILD
    prior.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    prior.render_runner = render_runner


def render_runner() -> str:
    """p39 already has the required bootstrap runner; only re-identity it."""
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        source = archive.read(f"{SOURCE_ID}/PREPARE_AND_RUN.sh").decode("utf-8")
    runner = source.replace(SOURCE_ID, PACKAGE_ID)
    if runner.count('python3 "$post_sim_helper" finalize --request "$post_sim_request"') != 1:
        raise BuildError("shared post-sim finalizer count changed")
    if 'trap \'finalize $?\' EXIT' not in runner or "compile_core_helper=" not in runner:
        raise BuildError("p39 bootstrap-safe runner contract missing")
    return runner


def patch_first_error_helper(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    start = text.index("def first_error(data: bytes) -> bytes:\n")
    end = text.index("\ndef finalize(args: argparse.Namespace) -> int:\n", start)
    replacement = r'''def first_error(data: bytes) -> bytes:
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines()

    def excerpt(index: int) -> bytes:
        # Put the diagnostic header first, followed by its forward context.
        # This remains useful when a long banner precedes the first error.
        context = [lines[index], *lines[index + 1: index + 7], *lines[max(0, index - 2): index]]
        return (("\n".join(context) + "\n").encode("utf-8"))[:FIRST_ERROR_BYTES]

    structured = re.compile(
        r"(?i)^\s*(?:Error-\[[^]]+\]|Error:|Fatal(?:-|:)|\*\*\s*(?:Error|Fatal)|"
        r"[^:\n]+:\d+(?::\d+)?:\s*(?:fatal\s+error|error):)"
    )
    for index, line in enumerate(lines):
        if structured.search(line):
            return excerpt(index)

    generic = re.compile(
        r"(?i)(^|\s)(fatal|failed|failure|undefined|not found|no rule to make target|"
        r"syntax error|xmre|undeclared identifier|cannot open|permission denied)(\s|:|$)"
    )
    for index, line in enumerate(lines):
        lowered = line.lower()
        if "warning" in lowered or "error message report included" in lowered:
            continue
        if generic.search(line):
            return excerpt(index)
    fallback = "\n".join(lines[-5:]) + ("\n" if lines else "")
    return fallback.encode("utf-8")[:FIRST_ERROR_BYTES]
'''
    path.write_text(text[:start] + replacement + text[end:], encoding="utf-8", newline="\n")


def patch_publisher(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(SOURCE_ID, PACKAGE_ID)
    text = text.replace("conv-native-p39-", "conv-native-p40-")
    text = text.replace("native Conv p39", "native Conv p40")
    text = text.replace("p39 publisher", "p40 publisher")
    path.write_text(text, encoding="utf-8", newline="\n")


def public_surface_observer() -> str:
    member = f"{SOURCE_ID}/tb_probe/native_return_observer.svh"
    with zipfile.ZipFile(SOURCE_ZIP) as archive:
        text = archive.read(member).decode("utf-8").replace(SOURCE_ID, PACKAGE_ID)
    root = (
        "u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group."
        "slice_group_gen[0].u_datahub_top_wrapper.u_datahub_top"
    )
    for channel in (8, 9):
        old_grant = (
            f"dh_grant_{channel} = dh_head_{channel} && {root}.local_req_full_channels[{channel}]."
            "wr_en.u_local_req_full_channel.arb_req_ready[0];"
        )
        new_grant = (
            f"dh_grant_{channel} = dh_head_{channel} && {root}.local_channel2hub_req_valid[{channel}] && "
            f"{root}.local_channel2hub_req_rwflag[{channel}];"
        )
        old_accept = (
            f"dh_accept_{channel} = dh_head_{channel} && {root}.local_req_full_channels[{channel}]."
            "wr_en.u_local_req_full_channel.u_local_wr_req_queue.hub_wr_req_ready;"
        )
        new_accept = f"dh_accept_{channel} = dh_grant_{channel} && {root}.local_channel2hub_req_ready[{channel}];"
        if text.count(old_grant) != 1 or text.count(old_accept) != 1:
            raise BuildError(f"p39 observer site changed for channel {channel}")
        text = text.replace(old_grant, new_grant).replace(old_accept, new_accept)
    if "arb_req_ready[0]" in text:
        raise BuildError("private arb_req_ready XMR remains in p40 observer")
    return text


def command(argv: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, check=False)


def prepare_prebuild() -> dict[str, Any]:
    assets = prior.prepare_prebuild()
    helper = PREBUILD / "compile_core_evidence.py"
    publisher = PREBUILD / "fixed_simresult_publisher.py"
    observer = PREBUILD / "native_return_observer.svh"
    patch_first_error_helper(helper)
    patch_publisher(publisher)
    observer.write_text(public_surface_observer(), encoding="utf-8", newline="\n")

    spec_path = assets["spec"]
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["changed_surfaces"] = [
        "package_identity", "package_local_hdl", "runner", "return_core_contract",
        "return_collector", "storage",
    ]
    spec["rule_change_epoch"] = {
        "epoch_id": EPOCH,
        "first_fresh_after_change": True,
        "prior_audit_receipt": None,
    }
    inputs = [row for row in spec["inputs"] if row.get("surface") != "package_local_hdl"]
    for row in inputs:
        candidate = ROOT / row["path"]
        if candidate.is_file():
            row["bytes"] = candidate.stat().st_size
            row["sha256"] = prior.sha256(candidate)
    inputs.append({
        "path": observer.relative_to(ROOT).as_posix(),
        "surface": "package_local_hdl",
        "bytes": observer.stat().st_size,
        "sha256": prior.sha256(observer),
    })
    spec["inputs"] = inputs
    prior.write_json(spec_path, spec)
    result = command([
        PYTHON, str(prior.PIPELINE), "prepare", "--spec", str(spec_path),
        "--registry", str(prior.GATE_REGISTRY), "--workspace-root", str(ROOT),
        "--output", str(assets["profile"]),
    ])
    if result.returncode:
        raise BuildError(f"p40 shared aggregate failed: {result.stderr}\n{result.stdout}")
    profile = json.loads(assets["profile"].read_text(encoding="utf-8"))
    if profile.get("contract_valid") is not True or profile.get("preflight", {}).get("errors") != []:
        raise BuildError("p40 shared aggregate did not close")
    return assets


def patch_manifest_metadata(package: Path) -> None:
    layout_path = package / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    layout["claim_boundary"] = (
        "p40 changes package identity, package-local Datahub observer public-surface expressions and "
        "compile first-error selection only; p39 config/numeric/workload/functional RTL remain frozen."
    )
    prior.write_json(layout_path, layout)
    pointer = package / "TEST_PACKAGE_MANIFEST.json"
    pointer_value = json.loads(pointer.read_text(encoding="utf-8"))
    pointer_value["schema"] = "conv-native-four-lane-p40-dhpubfix-pointer-v1"
    prior.write_json(pointer, pointer_value)
    manifest_path = package / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema"] = "conv-native-four-lane-0ccae916-p40-dhpubfix-package-v1"
    manifest["delivery_successor"] = {
        "source_package_identity": SOURCE_ID,
        "source_zip_sha256": SOURCE_SHA256,
        "source_disposition_after_consumption": "pending_replaced_by_fresh_successor",
        "reason": "p39 production VCS compile returned two XMRE errors for private observer token arb_req_ready at native_return_observer.svh lines 2462 and 2467",
        "authorized_config_change": None,
        "numeric_w3_golden_repeated": False,
    }
    manifest["rule_change_epoch"] = {
        "epoch_id": EPOCH,
        "family": "conv_native_four_lane",
        "package_id": PACKAGE_ID,
        "first_fresh_after_change": True,
        "notification_acknowledged": True,
        "rule_ids": RULE_IDS,
        "upload_hold_until": "ALL_EXACT_FINAL_ZIP_AND_FIRST_FRESH_GATES_PASS",
    }
    manifest["release_gate_matrix"]["observer_public_surface"] = {
        "applicability": "blocking_applicable", "blocking": True, "pass": None,
    }
    manifest["repair_delta"] = {
        "package_local_observer": "replace private arb_req_ready and queue-ready XMRs for channels 8/9 with datahub_top module-surface valid/rwflag/ready signals",
        "compile_first_error_collector": "prefer structured compiler diagnostics and reject platform-warning false positives",
        "functional_rtl_modified": False,
        "config_numeric_workload_modified": False,
    }
    observer_path = package / "tb_probe/native_return_observer.svh"
    observer_sha = prior.sha256(observer_path)
    binding = manifest["observer_binding"]
    binding.update({
        "sha256": observer_sha,
        "size_bytes": observer_path.stat().st_size,
        "source_sha256": observer_sha,
        "production_compile_receipt_reuse": None,
        "production_compile_status": "UNPROVEN_UNTIL_P40_FORMAL_RETURN",
    })
    binding["p40_datahub_public_surface_fix"] = {
        "path": "tb_probe/native_return_observer.svh",
        "source_p39_sha256": "e54a72e0f6e96f0ae26b33312881c71fb4927d4c4986da895ab18c026322daf1",
        "final_sha256": observer_sha,
        "source_bytes": 373180,
        "final_bytes": observer_path.stat().st_size,
        "replaced_private_token": "local_req_full_channel.arb_req_ready[0]",
        "public_module_surface": [
            "datahub_top.local_channel2hub_req_valid[8:9]",
            "datahub_top.local_channel2hub_req_rwflag[8:9]",
            "datahub_top.local_channel2hub_req_ready[8:9]",
        ],
        "functional_rtl_changed": False,
    }
    manifest["files"] = {
        row.relative_to(package).as_posix(): {"sha256": prior.sha256(row), "size_bytes": row.stat().st_size}
        for row in sorted(package.rglob("*")) if row.is_file() and row != manifest_path
    }
    prior.write_json(manifest_path, manifest)


def materialize(destination: Path, assets: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    package, frozen = prior.materialize(destination, assets)
    shutil.copyfile(PREBUILD / "native_return_observer.svh", package / "tb_probe/native_return_observer.svh")
    prior.refresh_manifest(package, assets)
    patch_manifest_metadata(package)
    frozen.update({
        "package_local_observer_modified": True,
        "observer_private_arb_req_ready_removed": True,
        "config_numeric_workload_functional_rtl_frozen": True,
    })
    return package, frozen


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    configure_prior()
    if SOURCE_ZIP.stat().st_size != SOURCE_BYTES or prior.sha256(SOURCE_ZIP) != SOURCE_SHA256:
        raise BuildError("exact p39 source ZIP differs")
    assets = prepare_prebuild()
    output = args.output_root.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = [output / PACKAGE_ID, output / f"{PACKAGE_ID}.zip", output / f"{PACKAGE_ID}.zip.sha256", output / f"{PACKAGE_ID}.build.json"]
    if any(path.exists() for path in targets):
        raise BuildError("refusing to overwrite p40 build output")
    package, frozen = materialize(output, assets)
    with tempfile.TemporaryDirectory(prefix=".p40_repeat_", dir=ROOT) as temporary:
        repeated, _ = materialize(Path(temporary), assets)
        deterministic = prior.tree_receipt(package) == prior.tree_receipt(repeated)
    if not deterministic:
        raise BuildError("p40 deterministic double staging differs")
    zip_path = output / f"{PACKAGE_ID}.zip"
    prior.deterministic_zip(package, zip_path)
    digest = prior.sha256(zip_path)
    Path(str(zip_path) + ".sha256").write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    report = {
        "schema": "conv-native-four-lane-p40-dhpubfix-build-v1",
        "status": "PACKAGE_BUILT_UPLOAD_HELD_PENDING_EXACT_FINAL_ZIP_GATES",
        "package_identity": PACKAGE_ID,
        "source_p39_zip_sha256": SOURCE_SHA256,
        "p39_return_analysis": "outputs/conv_native_four_lane_0ccae916_p39_return_analysis/report.json",
        "rule_change_epoch_id": EPOCH,
        "first_fresh_after_change": True,
        "prebuild_aggregate_top_level_invocations": 1,
        "final_zip_count": 1,
        "zip": zip_path.relative_to(ROOT).as_posix(),
        "zip_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "deterministic_double_build_tree_equal": deterministic,
        "frozen": frozen,
        "runner_return_resilience_prebuild": {
            "path": assets["report"].relative_to(ROOT).as_posix(),
            "bytes": assets["report"].stat().st_size,
            "sha256": prior.sha256(assets["report"]),
        },
        "shared_aggregate": {
            "path": assets["profile"].relative_to(ROOT).as_posix(),
            "bytes": assets["profile"].stat().st_size,
            "sha256": prior.sha256(assets["profile"]),
        },
        "config_numeric_workload_rtl_frozen": True,
        "server_action": False,
    }
    prior.write_json(output / f"{PACKAGE_ID}.build.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
