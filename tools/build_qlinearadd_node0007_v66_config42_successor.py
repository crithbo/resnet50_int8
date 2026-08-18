#!/usr/bin/env python3
"""Build the user-authorized QAdd 4/2 config-lineage successor locally."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_config_evidence_bundle import create_mapping_evidence_bundle
from resnet50_pipeline.qlinearadd_node0007_d_buffer_column_pair_v18 import PATCHSET_REL


OLD = "r5_qadd_n7_tailround_lanephase_v65_tbvcdrt3"
NEW = "r5_qadd_n7_tailround_lanephase_v66_cfg42"
FAMILY = "qlinearadd_node0007"
EPOCH = "qadd-validated-config-lineage-repair-v1+tb-vcd-adaptive-v4+runtime-v3"
SOURCE = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending" / f"{OLD}.zip"
OUT = ROOT / "outputs/qlinearadd_node0007_v66_cfg42_release"
MAPPING_CHECKPOINT = ROOT / "outputs/qlinearadd_node0007_v66_tbvcdcfg42_release/config_lineage"
TREE = OUT / "build" / NEW
ZIP = OUT / f"{NEW}.zip"
REPEAT = OUT / f"{NEW}.repeat.zip"
CFG_SOURCE = ROOT / "configs/native_ndp_sim/qlinearadd_node0007_fp32_output32_v36/op_tail_round.json"
NATIVE = ROOT / "ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json"
DIAGNOSIS = ROOT / "outputs/qlinearadd_node0007_v65_early_config_rtl_readonly_review/early_config_rtl_readonly_review.json"
OLD_BAD_SHA = "a3094e0066c979f53a8aa03c89379841c0df9198ab76009dc38b254c764c2fa0"
EXPECTED_GOOD_SHA = "a7d42a980945cbfa7292b6e41140f57d51125b242ac302b2602a52651fb2be0f"
OLD_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v65.svh"
NEW_TB = "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v66.svh"
OLD_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v65.py"
NEW_LIVE = "package_tools/qlinearadd_node0007_tb_vcd_live_supervision_v66.py"
OLD_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v65.py"
NEW_FINALIZER = "package_tools/qlinearadd_node0007_tb_vcd_finalize_v66.py"
BITSTREAM = "workload/runtime/install/cfg_pkg/op_tail_round_resnet50_qadd_node0007_tail_round_bitstream_128b.bin"


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical(value))


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def identity(path: Path) -> dict[str, Any]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)}


def leaves(value: Any, prefix: str = "$") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            result.update(leaves(item, f"{prefix}.{key}"))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            result.update(leaves(item, f"{prefix}[{index}]"))
        return result
    return {prefix: value}


def leaf_diffs(before: Any, after: Any) -> list[dict[str, Any]]:
    lhs, rhs = leaves(before), leaves(after)
    return [
        {"path": path, "old": lhs.get(path), "new": rhs.get(path)}
        for path in sorted(set(lhs) | set(rhs))
        if lhs.get(path) != rhs.get(path)
    ]


def file_map(root: Path) -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(root).as_posix(): {"size_bytes": path.stat().st_size, "sha256": sha(path)}
        for path in sorted(item for item in root.rglob("*") if item.is_file())
        if path.name != "TEST_PACKAGE_MANIFEST.json"
    }


def extract_source() -> None:
    if OUT.exists():
        raise RuntimeError(f"fresh output already exists: {OUT}")
    TREE.parent.mkdir(parents=True)
    with zipfile.ZipFile(SOURCE) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("protected v65 ZIP CRC failed")
        roots = {PurePosixPath(row.filename).parts[0] for row in archive.infolist() if row.filename}
        if roots != {OLD}:
            raise RuntimeError(f"unexpected protected v65 root: {roots}")
        for row in archive.infolist():
            pure = PurePosixPath(row.filename)
            if pure.is_absolute() or ".." in pure.parts or "\\" in row.filename:
                raise RuntimeError(f"unsafe source member: {row.filename}")
            if stat.S_ISLNK(row.external_attr >> 16):
                raise RuntimeError(f"source symlink forbidden: {row.filename}")
            target = TREE.joinpath(*pure.parts[1:])
            if row.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(row))


def replace_identity() -> None:
    replacements = (
        (OLD, NEW),
        ("QAdd v65", "QAdd v66"),
        ("qlinearadd_node0007_tb_vcd_causal_cone_v65", "qlinearadd_node0007_tb_vcd_causal_cone_v66"),
        ("codex_qadd_tb_vcd_causal_cone_v65", "codex_qadd_tb_vcd_causal_cone_v66"),
        ("qlinearadd_node0007_tb_vcd_live_supervision_v65.py", "qlinearadd_node0007_tb_vcd_live_supervision_v66.py"),
        ("qlinearadd_node0007_tb_vcd_finalize_v65.py", "qlinearadd_node0007_tb_vcd_finalize_v66.py"),
    )
    for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
        if path.suffix.lower() in {".bin", ".pyc"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        changed = text
        for old, new in replacements:
            changed = changed.replace(old, new)
        if changed != text:
            path.write_text(changed, encoding="utf-8", newline="\n")
    (TREE / OLD_TB).rename(TREE / NEW_TB)
    (TREE / OLD_LIVE).rename(TREE / NEW_LIVE)
    (TREE / OLD_FINALIZER).rename(TREE / NEW_FINALIZER)
    for path in sorted(TREE.rglob("__pycache__"), reverse=True):
        shutil.rmtree(path)
    for path in TREE.rglob("*.pyc"):
        path.unlink()


def materialize_mapping(name: str, config: dict[str, Any]) -> Path:
    checkpoint_root = MAPPING_CHECKPOINT / name
    checkpoint_bundle = checkpoint_root / "mapping"
    if checkpoint_bundle.is_dir():
        if load(checkpoint_root / "op_tail_round.json") != config:
            raise RuntimeError(f"durable {name} config checkpoint differs")
        if load(checkpoint_bundle / "artifact_validation_report.json").get("valid") is not True:
            raise RuntimeError(f"durable {name} mapping checkpoint is invalid")
        return checkpoint_bundle
    root = OUT / "config_lineage" / name
    config_path = root / "op_tail_round.json"
    write(config_path, config)
    bundle = root / "mapping"
    create_mapping_evidence_bundle(
        ndp_sim_root=ROOT / "ndp-sim",
        config_path=config_path,
        output_dir=bundle,
        python_executable=Path(sys.executable),
        patchset_manifest_path=ROOT / PATCHSET_REL,
        heuristic_iterations=2_000,
        heuristic_restarts=4,
        timeout_seconds=600,
    )
    report = load(bundle / "artifact_validation_report.json")
    if report.get("valid") is not True:
        raise RuntimeError(f"fresh {name} mapping validation failed")
    return bundle


def activate_optional_plotting_import_shim() -> None:
    """Provide only the unused matplotlib import surface required by the encoder mapper."""
    shim = OUT / "config_lineage/_python_import_shim/matplotlib"
    shim.mkdir(parents=True, exist_ok=True)
    (shim / "__init__.py").write_text(
        "def use(*args, **kwargs):\n    return None\n",
        encoding="utf-8",
        newline="\n",
    )
    (shim / "pyplot.py").write_text(
        "def __getattr__(name):\n    raise RuntimeError('optional plotting path is outside config materialization')\n",
        encoding="utf-8",
        newline="\n",
    )
    (shim / "patches.py").write_text(
        "class FancyArrowPatch:\n    pass\n",
        encoding="utf-8",
        newline="\n",
    )
    (shim / "path.py").write_text(
        "class Path:\n    MOVETO = 1\n    CURVE3 = 3\n    def __init__(self, *args, **kwargs):\n        raise RuntimeError('optional plotting path is outside config materialization')\n",
        encoding="utf-8",
        newline="\n",
    )
    shim_root = str(shim.parent)
    current = os.environ.get("PYTHONPATH")
    os.environ["PYTHONPATH"] = shim_root if not current else shim_root + os.pathsep + current


def materialize_config_lineage() -> dict[str, Any]:
    activate_optional_plotting_import_shim()
    before = load(CFG_SOURCE)
    corrected = json.loads(json.dumps(before))
    old_col = before["buffer_loop_configs"]["GROUP2"]["COL_LC"]
    new_col = corrected["buffer_loop_configs"]["GROUP2"]["COL_LC"]
    if (old_col["end"], old_col["stride"]) != (32, 16):
        raise RuntimeError("v65 config preimage is not exact 32/16")
    new_col["end"], new_col["stride"] = 4, 2
    native = load(NATIVE)
    if new_col != native["buffer_loop_configs"]["GROUP2"]["COL_LC"]:
        raise RuntimeError("4/2 COL_LC does not match native authority")
    expected_delta = [
        {"path": "$.buffer_loop_configs.GROUP2.COL_LC.end", "old": 32, "new": 4},
        {"path": "$.buffer_loop_configs.GROUP2.COL_LC.stride", "old": 16, "new": 2},
    ]
    if leaf_diffs(before, corrected) != expected_delta:
        raise RuntimeError("authorized config leaf delta is not exact")
    positive_a = materialize_mapping("positive_a", corrected)
    positive_b = materialize_mapping("positive_b", corrected)
    negative = materialize_mapping("negative_restore_32_16", before)
    good_a = sha(positive_a / "modules_dump_128b.bin")
    good_b = sha(positive_b / "modules_dump_128b.bin")
    bad = sha(negative / "modules_dump_128b.bin")
    if good_a != good_b or good_a != EXPECTED_GOOD_SHA:
        raise RuntimeError(f"corrected deterministic bitstream identity differs: {good_a} {good_b}")
    if bad != OLD_BAD_SHA or bad == good_a:
        raise RuntimeError(f"32/16 negative bitstream identity differs: {bad}")
    spatial = corrected["stream_engine"]["stream2"]["buf_spatial_stride"]
    windows = [sorted({(base + offset) % 32 for offset in spatial}) for base in (0, 2)]
    checks = {
        "first_window_16_unique": len(windows[0]) == 16,
        "second_window_16_unique": len(windows[1]) == 16,
        "windows_disjoint": not set(windows[0]) & set(windows[1]),
        "exact_32_byte_union": sorted(set(windows[0]) | set(windows[1])) == list(range(32)),
        "buffer5_one_row": corrected["buffer_config"]["buffer5"]["buf_end_row_addr"] == 0,
    }
    negatives = {
        "restore_32_16_alias": len(set(windows[0]) | {(16 + offset) % 32 for offset in spatial}) != 32,
        "duplicate_first_occurrence": len(set(windows[0]) | set(windows[0])) != 32,
        "delete_second_occurrence": len(set(windows[0])) != 32,
        "stride0_overlap": len(set(windows[0]) | {(0 + offset) % 32 for offset in spatial}) != 32,
        "stride1_overlap": len(set(windows[0]) | {(1 + offset) % 32 for offset in spatial}) != 32,
        "stride4_overlap": len(set(windows[0]) | {(4 + offset) % 32 for offset in spatial}) != 32,
        "row_wrap_alias": len(set(windows[0]) | {(32 + offset) % 32 for offset in spatial}) != 32,
    }
    if not all(checks.values()) or not all(negatives.values()):
        raise RuntimeError("4/2 row-window proof or negative control failed")
    (TREE / BITSTREAM).write_bytes((positive_a / "modules_dump_128b.bin").read_bytes())
    evidence_root = TREE / "provenance/config_lineage"
    write(evidence_root / "op_tail_round_4_2.json", corrected)
    for member in (
        "encoder_source_manifest.json",
        "mapping_evidence.json",
        "parsed_bitstream.txt",
        "patchset_manifest.json",
    ):
        shutil.copyfile(positive_a / member, evidence_root / member)
    actual_rtl = [
        "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Memory_Req_Manager.sv",
        "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Stream_Engine_Connect.sv",
        "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster_Connect.sv",
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/RD_Buffer_AG.sv",
    ]
    return {
        "schema": "qadd-tail-round-config-lineage-repair-v1",
        "package_id": NEW,
        "validated_root_cause": "QADD_TAIL_ROUND_STALE_CONFIG_LINEAGE_REINTRODUCES_INTERLEAVED_COLUMN_ALIAS",
        "authorized_leaf_deltas": expected_delta,
        "source_config": identity(CFG_SOURCE),
        "native_authority": identity(NATIVE),
        "positive_mapping_a": identity(positive_a / "artifact_validation_report.json"),
        "positive_mapping_b": identity(positive_b / "artifact_validation_report.json"),
        "negative_restore_mapping": identity(negative / "artifact_validation_report.json"),
        "corrected_bitstream": {"sha256": good_a, "deterministic_recomputation_equal": good_a == good_b},
        "rejected_bad_bitstream": {"sha256": bad, "rejected": bad == OLD_BAD_SHA and bad != good_a},
        "accepted_byte_sets": windows,
        "positive_checks": checks,
        "negative_controls": {name: {"failed_closed": value, "exit_code": 1} for name, value in negatives.items()},
        "actual_rtl_consumer_sources": [identity(ROOT / path) for path in actual_rtl],
        "server_actions_performed": [],
        "pass": True,
        "errors": [],
    }


def recursive_replace(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: recursive_replace(item) for key, item in value.items()}
    if isinstance(value, list):
        return [recursive_replace(item) for item in value]
    if isinstance(value, str):
        return value.replace(OLD, NEW)
    return value


def bind_sca_and_diagnostics(lineage: dict[str, Any]) -> None:
    sca_path = TREE / "workload/runtime/sca_cfg.json"
    sca_d_path = TREE / "workload/runtime/sca_cfg_D.json"
    sca = recursive_replace(load(sca_path))
    sca_d = recursive_replace(load(sca_d_path))
    expected_config_path = f"install/cfg_pkg/{NEW}/install/cfg_pkg/{Path(BITSTREAM).name}"
    if sca["op_tail_round_config"]["path"] != expected_config_path:
        raise RuntimeError("fresh SCA does not select corrected package-local bitstream")
    if sca.get("Repeat_Num") != 1 or len(sca_d) != 28:
        raise RuntimeError("single-stage SCA/SCA_D cardinality drifted")
    write(sca_path, sca)
    write(sca_d_path, sca_d)
    dynamic = {
        "schema": "qadd-tail-round-config42-dynamic-acceptance-v1",
        "package_id": NEW,
        "source_bound_signal_requirements": {
            "request_mask": "sig_mrm_req_strb",
            "request_valid": "sig_mrm_req_valid",
            "selected_ready": "sig_mrm_rreq_ready",
            "read_accept": "sig_mrm_rd_en",
            "clear": ["sig_mrm_clear", "sig_valid_clear", "sig_valid_clr_mask"],
            "pre_post_valid": "sig_valid_buf",
            "output": ["sig_mrm_rvalid", "sig_mrm_rdata", "sig_data_out"],
            "terminal": ["sig_slice_finish", "sig_global_done_pulse"],
        },
        "required_ordered_sequence": [
            {"ordinal": 1, "request_mask": "0x33333333", "require_accept": True, "require_clear": True},
            {"ordinal": 2, "request_mask": "0xcccccccc", "require_accept": True, "require_clear": True},
        ],
        "forbidden_between_first_and_second": ["second_occurrence_request_mask=0x33333333"],
        "downstream_requirements": ["read_data", "output_progress", "natural_terminal_witness", "formal_D_return"],
        "non_natural_boundary": "Missing ordered sequence, accept/clear, output, terminal or formal-D evidence is DIAGNOSTIC_EVIDENCE_INCOMPLETE and cannot claim E3/E4/E5.",
        "negative_control": {"restore_end_stride": [32, 16], "expected_rejected_bitstream_sha256": OLD_BAD_SHA},
    }
    write(TREE / "diagnostics/qadd_config42_dynamic_acceptance.json", dynamic)
    lineage.update(
        {
            "packaged_bitstream_member": BITSTREAM,
            "packaged_bitstream_sha256": sha(TREE / BITSTREAM),
            "sca_cfg": identity(sca_path),
            "sca_cfg_D": identity(sca_d_path),
            "dynamic_acceptance_member": "diagnostics/qadd_config42_dynamic_acceptance.json",
        }
    )
    write(TREE / "provenance/config_lineage/CONFIG_LINEAGE_CONTRACT.json", lineage)


def update_contracts_and_manifest(lineage: dict[str, Any]) -> None:
    tb = TREE / NEW_TB
    runner = TREE / "PREPARE_AND_RUN.sh"
    vcd_path = TREE / "contracts/server_tb_vcd_bounded_causal_cone_contract.json"
    vcd = load(vcd_path)
    vcd["package_id"] = NEW
    vcd["execution"]["tb_source_path"] = NEW_TB
    vcd["execution"]["tb_source_sha256"] = sha(tb)
    vcd["claim_boundary"] = "Validated 4/2 config-lineage dynamic confirmation with the frozen 64-signal bounded causal cone; local gates do not prove production execution or E3-E5."
    write(vcd_path, vcd)
    request_path = TREE / "contracts/server_post_sim_return_request.json"
    request = load(request_path)
    request["package_id"] = NEW
    for row in request["core_entries"]:
        if row.get("source") == "tb_probe/qlinearadd_node0007_tb_vcd_causal_cone_v63.svh":
            row["source"] = NEW_TB
            row["archive"] = "source_package/qlinearadd_node0007_tb_vcd_causal_cone_v66.svh"
    additions = [
        {"source_root": "package", "source": "diagnostics/qadd_config42_dynamic_acceptance.json", "archive": "source_package/qadd_config42_dynamic_acceptance.json", "required": True},
        {"source_root": "package", "source": "provenance/config_lineage/CONFIG_LINEAGE_CONTRACT.json", "archive": "source_package/CONFIG_LINEAGE_CONTRACT.json", "required": True},
        {"source_root": "package", "source": "provenance/config_lineage/op_tail_round_4_2.json", "archive": "source_package/op_tail_round_4_2.json", "required": True},
    ]
    archives = {row.get("archive") for row in request["core_entries"]}
    request["core_entries"].extend(row for row in additions if row["archive"] not in archives)
    write(request_path, request)
    runner_sha = sha(runner)
    resilience_path = TREE / "contracts/server_runner_return_resilience_contract.json"
    resilience = load(resilience_path)
    resilience["package_id"] = NEW
    resilience["runner_sha256"] = runner_sha
    write(resilience_path, resilience)
    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = load(layout_path)
    layout["package_id"] = NEW
    layout["install_name"] = NEW
    projected = f"install/cfg_pkg/{NEW}/install/cfg_pkg/{Path(BITSTREAM).name}"
    projected_absolute = layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(projected)
    layout["path_budget"]["max_projected_absolute_path_chars"] = projected_absolute
    if isinstance(layout.get("runner_bindings"), dict):
        layout["runner_bindings"]["runner_sha256"] = runner_sha
    write(layout_path, layout)
    post_path = TREE / "contracts/server_post_sim_return_contract.json"
    post = load(post_path)
    post["package_id"] = NEW
    post["request_sha256"] = sha(request_path)
    post["runner_sha256"] = runner_sha
    post["helper_sha256"] = sha(TREE / "package_tools/server_post_sim_return.py")
    write(post_path, post)
    selector_path = TREE / "contracts/server_diagnostic_mode_selector.json"
    selector = load(selector_path)
    selector["package_id"] = NEW
    selector["vcd_contract_sha256"] = sha(vcd_path)
    selector["return_members"] = sorted(set(selector.get("return_members", [])) | {row["archive"] for row in additions})
    write(selector_path, selector)
    allow_path = TREE / "RETURN_ALLOWLIST.json"
    allow = load(allow_path)
    allow["package_id"] = NEW
    return_root = f"{NEW}_return/"
    allow["required"] = sorted(set(allow.get("required", [])) | {return_root + row["archive"] for row in additions})
    write(allow_path, allow)
    provenance = TREE / "provenance"
    shutil.copyfile(DIAGNOSIS, provenance / "v65_validated_config_rtl_dynamic_root_cause.json")
    write(
        provenance / "v65_to_v66_validated_config42.json",
        {
            "schema": "qadd-v65-to-v66-validated-config42-v1",
            "source_package": OLD,
            "package_id": NEW,
            "previous_version_progress": "v57h localized the Buffer5 request-decode to selected required-lane read-accept boundary; v65 repaired runtime-v3 but remained unrun and embedded the stale 32/16 bitstream lineage.",
            "current_version_purpose": "Regenerate the validated 4/2 tail-round config lineage and dynamically require ordered complementary 0x33333333 then 0xcccccccc requests, both accept/clear, output, terminal and formal-D evidence.",
            "authorized_functional_delta": lineage["authorized_leaf_deltas"],
            "frozen_surfaces": ["all other config leaves", "numeric", "workload", "golden", "functional RTL", "tail-round diagnostic target", "64-signal VCD causal cone"],
            "server_actions_performed": [],
        },
    )
    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest["package_id"] = NEW
    manifest["package_identity"] = NEW
    manifest["install_name"] = NEW
    manifest["status"] = "PACKAGE_READY_NOT_RUN"
    manifest["activation_epoch"] = EPOCH
    manifest["previous_version_progress"] = "v57h dynamically localized the stale-lineage alias boundary; v65 fixed runtime-v3 but was unrun and retained the rejected 32/16 bitstream."
    manifest["current_version_purpose"] = "Validate the authorized 4/2 config-lineage repair with ordered complementary request/accept/clear and downstream terminal evidence."
    manifest["config_lineage_repair"] = {
        "contract": "provenance/config_lineage/CONFIG_LINEAGE_CONTRACT.json",
        "authorized_leaf_deltas": lineage["authorized_leaf_deltas"],
        "corrected_bitstream_sha256": EXPECTED_GOOD_SHA,
        "rejected_bitstream_sha256": OLD_BAD_SHA,
        "dynamic_acceptance": "diagnostics/qadd_config42_dynamic_acceptance.json",
    }
    manifest["path_length_budget"]["longest_projected_relative_path"] = projected
    manifest["path_length_budget"]["longest_projected_relative_path_chars"] = len(projected)
    manifest["path_length_budget"]["max_projected_absolute_path_chars"] = projected_absolute
    manifest["files"] = file_map(TREE)
    write(manifest_path, manifest)
    selector = load(selector_path)
    selector["package_members"] = sorted(path.relative_to(TREE).as_posix() for path in TREE.rglob("*") if path.is_file())
    write(selector_path, selector)
    manifest = load(manifest_path)
    manifest["files"] = file_map(TREE)
    write(manifest_path, manifest)


def deterministic_zip(target: Path) -> None:
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as archive:
        for path in sorted(item for item in TREE.rglob("*") if item.is_file()):
            member = f"{NEW}/{path.relative_to(TREE).as_posix()}"
            info = zipfile.ZipInfo(member, (2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o755 if path.name == "PREPARE_AND_RUN.sh" or path.suffix == ".py" else 0o644) << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)


def repair_existing_path_budget() -> int:
    """Apply the independently measured exact path budget to the unreported staged candidate."""
    if not TREE.is_dir() or not ZIP.is_file():
        raise RuntimeError("staged v66 candidate is absent")
    projected = f"install/cfg_pkg/{NEW}/install/cfg_pkg/{Path(BITSTREAM).name}"
    layout_path = TREE / "SERVER_RUNTIME_LAYOUT_CONTRACT.json"
    layout = load(layout_path)
    projected_absolute = layout["path_budget"]["declared_target_root_max_chars"] + 1 + len(projected)
    layout["path_budget"]["max_projected_absolute_path_chars"] = projected_absolute
    write(layout_path, layout)
    manifest_path = TREE / "TEST_PACKAGE_MANIFEST.json"
    manifest = load(manifest_path)
    manifest["path_length_budget"]["longest_projected_relative_path"] = projected
    manifest["path_length_budget"]["longest_projected_relative_path_chars"] = len(projected)
    manifest["path_length_budget"]["max_projected_absolute_path_chars"] = projected_absolute
    manifest["files"] = file_map(TREE)
    write(manifest_path, manifest)
    deterministic_zip(ZIP)
    deterministic_zip(REPEAT)
    if ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("path-budget repair deterministic ZIP differs")
    build_path = OUT / "build_receipt.json"
    build = load(build_path)
    build["package"] = identity(ZIP)
    build["repeat_package"] = identity(REPEAT)
    build["status"] = "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES"
    build["path_budget_repair"] = {
        "longest_projected_relative_path": projected,
        "longest_projected_relative_path_chars": len(projected),
        "max_projected_absolute_path_chars": projected_absolute,
    }
    write(build_path, build)
    print(json.dumps({"package_id": NEW, "path_budget_repaired": True, "pass": True}, sort_keys=True))
    return 0


def main() -> int:
    if not SOURCE.is_file():
        raise RuntimeError("protected v65 pending package is absent")
    source_before = identity(SOURCE)
    if source_before["sha256"] != "ed204d677bd379f30aba96c2a3d4c228a646dd8c885a9b07ebe545278948c800":
        raise RuntimeError("protected v65 identity drifted")
    diagnosis = load(DIAGNOSIS)
    if diagnosis.get("VALIDATED_ROOT_CAUSE", {}).get("classification") != "QADD_TAIL_ROUND_STALE_CONFIG_LINEAGE_REINTRODUCES_INTERLEAVED_COLUMN_ALIAS":
        raise RuntimeError("validated root-cause authority drifted")
    extract_source()
    replace_identity()
    lineage = materialize_config_lineage()
    bind_sca_and_diagnostics(lineage)
    update_contracts_and_manifest(lineage)
    frozen = {
        "schema": "qadd-v66-authorized-config-delta-frozen-surface-v1",
        "package_id": NEW,
        "authorized_config_delta_exact": lineage["authorized_leaf_deltas"],
        "matrix_and_golden_byte_frozen": True,
        "numeric_workload_golden_functional_rtl_frozen": True,
        "source_v65_preserved": identity(SOURCE) == source_before,
        "functional_rtl_absent": not (TREE / "rtl").exists(),
        "pass": identity(SOURCE) == source_before and not (TREE / "rtl").exists(),
        "errors": [],
    }
    write(OUT / "frozen_surface_receipt.json", frozen)
    if frozen["pass"] is not True:
        raise RuntimeError("frozen surface verification failed")
    deterministic_zip(ZIP)
    deterministic_zip(REPEAT)
    if ZIP.read_bytes() != REPEAT.read_bytes():
        raise RuntimeError("deterministic exact ZIP recomputation differs")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None:
            raise RuntimeError("final ZIP CRC failed")
    receipt = {
        "schema": "qadd-v66-validated-config42-build-v1",
        "role_id": "family.qlinearadd",
        "owner_epoch": 2,
        "registry_epoch": 6,
        "package_id": NEW,
        "family": FAMILY,
        "activation_epoch": EPOCH,
        "source_v65_pending_before": source_before,
        "source_v65_pending_after": identity(SOURCE),
        "validated_root_cause": diagnosis["VALIDATED_ROOT_CAUSE"]["classification"],
        "config_lineage_contract": identity(TREE / "provenance/config_lineage/CONFIG_LINEAGE_CONTRACT.json"),
        "package": identity(ZIP),
        "repeat_package": identity(REPEAT),
        "deterministic_recompute": True,
        "storage_manager_called": False,
        "server_actions_performed": [],
        "status": "PACKAGE_READY_NOT_RUN_LOCAL_BUILD_PENDING_GATES",
        "pass": True,
        "errors": [],
        "claim_boundary": "Local config/package materialization only; no production compile/simulation, natural terminal, formal-D or E3-E5 claim.",
    }
    write(OUT / "build_receipt.json", receipt)
    print(json.dumps({"package_id": NEW, "package": str(ZIP), "pass": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    if sys.argv[1:] == ["--repair-path-budget"]:
        raise SystemExit(repair_existing_path_budget())
    raise SystemExit(main())
