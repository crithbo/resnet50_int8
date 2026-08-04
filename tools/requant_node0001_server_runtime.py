#!/usr/bin/env python3
"""Fail-closed server runtime for the node0001 two-stage Requant E4 package."""

from __future__ import annotations

import argparse
import hashlib
import json
import lzma
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


MANIFEST_NAME = "TEST_PACKAGE_MANIFEST.json"
RUNTIME_SCHEMA = "resnet50-requant-node0001-server-runtime-v1"
RESULT_SCHEMA = "resnet50-requant-node0001-server-result-gate-v1"
RETURN_SCHEMA = "resnet50-requant-node0001-server-return-receipt-v1"
IDENTITY_SCHEMA = "resnet50-requant-node0001-server-identity-v1"
IDENTITY_RECEIPT_SCHEMA = "resnet50-requant-node0001-stock-rtl-identity-v1"
INSTALL_RECEIPT_SCHEMA = "resnet50-requant-node0001-tb-probe-install-v1"
PRECOMPILE_RECEIPT_SCHEMA = (
    "resnet50-requant-node0001-tb-probe-precompile-verification-v1"
)
MATERIALIZATION_SCHEMA = "resnet50-requant-node0001-input-materialization-v1"
SLICE_COUNT = 28
OCCURRENCE_COUNT = 24
STAGE_COUNT = 48
SPATIAL = 112 * 112
CHANNELS = 64
SHARD_CHANNELS = 8
INPUT_LINES = 25_088
GUARD_LINES = 25_088
ROUND_LINES = 6_272
EXEC_LINES = 317
FORBIDDEN_RTL_PARTS = {"rtl"}
FORBIDDEN_ARCHIVE_SUFFIXES = {
    ".zip",
    ".tar",
    ".tgz",
    ".gz",
    ".7z",
    ".vcd",
    ".fsdb",
    ".vpd",
    ".wlf",
}
FORBIDDEN_RETURN_PARTS = {"build", "csrc", "simv.daidir", "waves", "wave"}
MAX_RETURN_FILE_BYTES = 2 * 1024 * 1024
MAX_RETURN_EXTRACTED_BYTES = 12 * 1024 * 1024
MAX_RETURN_ZIP_BYTES = 6 * 1024 * 1024
FOCUS_RTL = (
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_RD_Stream_Engine/RD_Memory_AG.sv",
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_RD_Stream_Engine/RD_Data_Channel.sv",
    "rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv",
    "rtl/Slice/General_Array/GA_Inport/GA_Inport.sv",
    "rtl/Slice/General_Array/GA_Inport/GA_Inport_Connect.sv",
    "rtl/Slice/General_Array/GA_Inport/GA_Inport_Group.sv",
    "rtl/Slice/General_Array/GA_Inport/GA_Inport_Group_Config.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_PE_Group_Interconnect.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_PE_ALU.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_LUT.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE_Preprocess.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE_Postprocess.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/Comparator.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/Binary_Search_Tree.sv",
    "rtl/Slice/General_Array/GA_Outport/GA_Outport.sv",
    "rtl/Slice/General_Array/GA_Outport/GA_Outport_Connect.sv",
    "rtl/Slice/General_Array/GA_Outport/GA_Outport_Group.sv",
    "rtl/Slice/General_Array/GA_Outport/GA_Outport_Group_Config.sv",
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Memory_AG.sv",
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
)
SUPPORT_FILES = (
    "tb_NDP_Top_new_phy.sv",
    "native_return_observer.svh",
    "Makefile.tb_NDP_Top_new_phy",
    "rtl/filelists/NDP_Top_phy_filelist.f",
)
TB_TARGET_RELATIVE_PATH = "native_return_observer.svh"


class RequantRuntimeError(RuntimeError):
    """Raised when a package, run, identity, or return gate fails closed."""


_GENERATED_INSTANCE_ARRAY_NAMES = frozenset(
    {
        "slice_with_datahub_mc_group_gen",
        "slice_group_gen",
        "MSE_INST",
        "GA_INPORT_GROUP",
        "GA_INPORT",
        "GA_ROW_PE",
        "GA_COL_PE",
    }
)
_GENERATED_INSTANCE_REFERENCE_RE = re.compile(
    r"\.(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\[\s*(?P<expression>[^\[\]]+?)\s*\]"
)


def validate_observer_xmr_elaboration(text: str) -> dict[str, Any]:
    """Reject runtime-indexed generated hierarchy while allowing signal arrays."""

    without_block_comments = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    active_text = "\n".join(
        line.split("//", 1)[0] for line in without_block_comments.splitlines()
    )
    genvars = set(
        re.findall(r"\bgenvar\s+([A-Za-z_][A-Za-z0-9_]*)", active_text)
    )
    checked: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    for match in _GENERATED_INSTANCE_REFERENCE_RE.finditer(active_text):
        name = match.group("name")
        if name not in _GENERATED_INSTANCE_ARRAY_NAMES and not name.endswith("_gen"):
            continue
        expression = match.group("expression").strip()
        identifiers = set(
            re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", expression)
        )
        runtime_identifiers = sorted(identifiers - genvars)
        item = {
            "line": active_text.count("\n", 0, match.start()) + 1,
            "instance_array": name,
            "index_expression": expression,
            "genvar_identifiers": sorted(identifiers & genvars),
            "runtime_or_unknown_identifiers": runtime_identifiers,
        }
        checked.append(item)
        if runtime_identifiers:
            violations.append(item)
    if violations:
        first = violations[0]
        raise RequantRuntimeError(
            "observer generated-instance XMR uses a runtime/unknown index: "
            f"line {first['line']} .{first['instance_array']}"
            f"[{first['index_expression']}]"
        )
    return {
        "schema": "server-observer-xmr-elaboration-static-gate-v1",
        "rule_id": "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
        "status": "pass",
        "checked_generated_instance_reference_count": len(checked),
        "declared_genvars": sorted(genvars),
        "runtime_indexed_generated_instance_reference_count": 0,
        "ordinary_signal_array_runtime_indexing_allowed": True,
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _safe_relative(value: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise RequantRuntimeError(f"unsafe relative path: {value!r}")
    return relative


def _inside(root: Path, value: str | PurePosixPath) -> Path:
    relative = _safe_relative(value) if isinstance(value, str) else value
    base = root.resolve()
    target = base.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise RequantRuntimeError(f"path escapes root: {relative}") from exc
    return target


def _resolve_tb_target(
    ndp_root: Path, relative_value: str | None
) -> tuple[Path, Path, bool]:
    """Resolve exactly one manifest-bound observer target under the given root."""

    explicit = relative_value is not None
    value = relative_value or TB_TARGET_RELATIVE_PATH
    root = ndp_root.resolve(strict=True)
    relative = _safe_relative(value)
    if relative.as_posix() != TB_TARGET_RELATIVE_PATH:
        raise RequantRuntimeError("manifest-bound TB relative path differs")
    literal = root.joinpath(*relative.parts)
    if literal.is_symlink():
        raise RequantRuntimeError("TB target symlink is forbidden")
    target = literal.resolve(strict=True)
    if target != literal or root not in target.parents:
        raise RequantRuntimeError("TB target escapes or differs from root/relative")
    return root, target, explicit


def _probe_target_isolation(
    *,
    root: Path,
    target: Path,
    argument_was_explicit: bool,
    preimage_size: int,
    preimage_sha256: str,
) -> dict[str, Any]:
    return {
        "rule_id": "CDA-SERVER-TB-TARGET-DIRECTORY-ISOLATION-001",
        "normalized_target_root": root.as_posix(),
        "normalized_unique_target_path": target.as_posix(),
        "manifest_relative_path": TB_TARGET_RELATIVE_PATH,
        "command_argument_was_explicit": argument_was_explicit,
        "candidate_write_path_count": 1,
        "target_equals_root_plus_manifest_relative_path": True,
        "basename_find_glob_rglob_used": False,
        "preimage_size_bytes": preimage_size,
        "preimage_sha256": preimage_sha256,
    }


def _verify_probe_target_receipt(
    receipt: dict[str, Any],
    *,
    root: Path,
    target: Path,
    require_explicit: bool,
) -> dict[str, Any]:
    isolation = receipt.get("target_directory_isolation", {})
    if (
        isolation.get("normalized_target_root") != root.as_posix()
        or isolation.get("normalized_unique_target_path") != target.as_posix()
        or isolation.get("manifest_relative_path") != TB_TARGET_RELATIVE_PATH
        or isolation.get("candidate_write_path_count") != 1
        or isolation.get("target_equals_root_plus_manifest_relative_path") is not True
        or isolation.get("basename_find_glob_rglob_used") is not False
        or (
            require_explicit
            and isolation.get("command_argument_was_explicit") is not True
        )
    ):
        raise RequantRuntimeError(
            "probe install/verify/restore target-directory identity differs"
        )
    return isolation


def _records(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return result


def _tree_identity(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        return {
            "exists": False,
            "file_count": 0,
            "size_bytes": 0,
            "tree_sha256": None,
        }
    records = _records(root)
    digest = hashlib.sha256()
    for relative, item in records.items():
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode()
        )
    return {
        "exists": True,
        "file_count": len(records),
        "size_bytes": sum(item["size_bytes"] for item in records.values()),
        "tree_sha256": digest.hexdigest(),
    }


def _file_identity(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "size_bytes": None, "sha256": None}
    return {
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _git_identity(root: Path) -> dict[str, Any]:
    try:
        top = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"available": False, "requested_path": root.resolve().as_posix()}
    if top.returncode != 0:
        return {"available": False, "requested_path": root.resolve().as_posix()}
    head = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    status = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    status_text = status.stdout if status.returncode == 0 else ""
    return {
        "available": True,
        "requested_path": root.resolve().as_posix(),
        "top_level": top.stdout.strip(),
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "dirty": bool(status_text),
        "status_entry_count": len(status_text.splitlines()),
        "status_sha256": _sha256_bytes(status_text.encode()),
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_pretty_json(path: Path) -> Any:
    value = _load_json(path)
    canonical = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path.read_text(encoding="utf-8") != canonical:
        raise RequantRuntimeError(f"JSON is not canonical pretty LF: {path}")
    return value


def _validate_128bit_text(path: Path, expected_lines: int) -> list[str]:
    raw = path.read_bytes()
    if b"\r" in raw:
        raise RequantRuntimeError(f"128-bit text contains CR: {path}")
    lines = raw.decode("ascii").splitlines()
    if len(lines) != expected_lines:
        raise RequantRuntimeError(
            f"128-bit line count differs: {path}: {len(lines)} != {expected_lines}"
        )
    if any(len(line) != 128 or set(line) - {"0", "1"} for line in lines):
        raise RequantRuntimeError(f"invalid 128-bit text: {path}")
    if raw != ("\n".join(lines) + "\n").encode("ascii"):
        raise RequantRuntimeError(f"128-bit text is not LF canonical: {path}")
    return lines


def _decode_128bit_text(path: Path, expected_lines: int) -> bytes:
    return b"".join(
        int(line, 2).to_bytes(16, "little")
        for line in _validate_128bit_text(path, expected_lines)
    )


def _runtime_payload_local(
    package: Path, install_name: str, runtime_path: str
) -> Path:
    prefix = f"../install/cfg_pkg/{install_name}/"
    if not runtime_path.startswith(prefix):
        raise RequantRuntimeError(
            f"runtime payload is outside unique namespace: {runtime_path}"
        )
    return _inside(package / "workload/runtime", runtime_path[len(prefix) :])


def _load_manifest(package: Path, install_name: str) -> dict[str, Any]:
    manifest = _load_json(package / MANIFEST_NAME)
    if manifest.get("install_name") != install_name:
        raise RequantRuntimeError("install name differs from package manifest")
    if manifest.get("files") != _records(package, exclude_manifest=True):
        raise RequantRuntimeError("package payload differs from manifest exact set")
    return manifest


def _iter_payload_entries(sca: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for name, value in sca.items():
        if isinstance(value, dict) and "path" in value:
            yield name, value


def _read_compact(path: Path, expected_size: int, expected_sha256: str) -> bytes:
    raw = lzma.decompress(path.read_bytes())
    if len(raw) != expected_size or _sha256_bytes(raw) != expected_sha256:
        raise RequantRuntimeError(f"compact payload identity differs: {path}")
    return raw


def preflight_package(package_root: Path, install_name: str) -> dict[str, Any]:
    package = package_root.resolve()
    manifest = _load_manifest(package, install_name)
    forbidden_rtl = [
        relative
        for relative in manifest["files"]
        if "rtl" in {part.lower() for part in PurePosixPath(relative).parts}
    ]
    if forbidden_rtl:
        raise RequantRuntimeError(f"functional RTL payload forbidden: {forbidden_rtl[0]}")
    nested = [
        relative
        for relative in manifest["files"]
        if PurePosixPath(relative).suffix.lower() in FORBIDDEN_ARCHIVE_SUFFIXES
    ]
    if nested:
        raise RequantRuntimeError(f"nested archive/waveform forbidden: {nested[0]}")
    if manifest["rtl_policy"] != {
        "functional_rtl_modified": False,
        "rtl_directory_write_allowed": False,
        "rtl_patch_included": False,
        "read_only_tb_probe_included": True,
        "tb_probe_transactional_restore_required": True,
    }:
        raise RequantRuntimeError("RTL/TB policy differs")

    runtime = package / "workload/runtime"
    sca = _validate_pretty_json(runtime / "sca_cfg.json")
    sca_d = _validate_pretty_json(runtime / "sca_cfg_D.json")
    layout = _validate_pretty_json(runtime / "layout_contract.json")
    coverage = _validate_pretty_json(package / "validation/coverage_contract.json")
    if (
        sca.get("Exec_Base") != "0x0180_C400"
        or sca.get("Exec_Length") != EXEC_LINES
        or sca.get("Repeat_Num") != STAGE_COUNT
    ):
        raise RequantRuntimeError("Exec_Base/Exec_Length/Repeat_Num differs")
    if layout.get("occurrence_count") != OCCURRENCE_COUNT:
        raise RequantRuntimeError("occurrence count differs")
    if layout.get("stage_count") != STAGE_COUNT:
        raise RequantRuntimeError("stage count differs")
    if len(layout.get("records", [])) != OCCURRENCE_COUNT:
        raise RequantRuntimeError("layout record count differs")
    if len(layout.get("input_bindings", [])) != 128:
        raise RequantRuntimeError("input binding count differs")
    masks = layout.get("stage_masks", [])
    if len(masks) != STAGE_COUNT:
        raise RequantRuntimeError("48 stage masks are required")
    if any(masks[index] != masks[index ^ 1] for index in range(0, STAGE_COUNT, 2)):
        raise RequantRuntimeError("guard/round same-mask pairing differs")
    address_ranges = layout.get("address_ranges", [])
    if len(address_ranges) != 384:
        raise RequantRuntimeError("128 input + 256 output address ranges are required")
    if any(
        item.get("start_row", 6144) < 0
        or item.get("end_row", 6144) < item.get("start_row", 6144)
        or item.get("end_row", 6144) >= 6144
        for item in address_ranges
    ):
        raise RequantRuntimeError("every address range must stay below row 6144")
    if layout.get("maximum_address_row") != max(
        item["end_row"] for item in address_ranges
    ):
        raise RequantRuntimeError("maximum address row receipt differs")
    if layout.get("producer_consumer_same_address_count") != 128:
        raise RequantRuntimeError("producer/consumer same-address count differs")
    if layout.get("consumer_intermediate_preload_count") != 0:
        raise RequantRuntimeError("consumer intermediate preload must be zero")
    if layout.get("shared_requant_guard_load_count") != 1:
        raise RequantRuntimeError("RequantGuard must be loaded once")

    payloads = dict(_iter_payload_entries(sca))
    if len(payloads) != 178:
        raise RequantRuntimeError(f"SCA preload count differs: {len(payloads)}")
    if len([name for name in payloads if "sfu_config" in name]) != 1:
        raise RequantRuntimeError("SCA must contain exactly one SFU payload load")
    if any("round_matrixA" in name for name in payloads):
        raise RequantRuntimeError("consumer intermediate appears in external preload")
    exec_path = _runtime_payload_local(
        package, install_name, sca["ExecutionPlan"]["path"]
    )
    _validate_128bit_text(exec_path, EXEC_LINES)
    for name, entry in payloads.items():
        if "matrixA" in name:
            continue
        path = _runtime_payload_local(package, install_name, entry["path"])
        if not path.is_file():
            raise RequantRuntimeError(f"missing packaged payload: {name}")
        if name == "ExecutionPlan":
            continue
        expected = 50 if "sfu_config" in name else None
        if expected is not None:
            _validate_128bit_text(path, expected)
        elif "config" in name:
            lines = path.read_text(encoding="ascii").splitlines()
            if len(lines) not in {25, 34}:
                raise RequantRuntimeError(f"config line count differs: {name}")

    input_meta = manifest["compact_data"]["input"]
    output_meta = manifest["compact_data"]["golden"]
    _read_compact(
        runtime / input_meta["path"],
        input_meta["raw_size_bytes"],
        input_meta["raw_sha256"],
    )
    _read_compact(
        package / output_meta["path"],
        output_meta["raw_size_bytes"],
        output_meta["raw_sha256"],
    )
    if coverage.get("counts") != {
        "negative": 3246544,
        "minus_one": 80,
        "zero": 112,
        "positive": 9598400,
        "round_half_even_tie": 16,
        "lower_saturation": 3246656,
        "upper_saturation": 0,
    }:
        raise RequantRuntimeError("frozen W3 coverage counts differ")
    if coverage.get("all_64_channel_multipliers_covered") is not True:
        raise RequantRuntimeError("64-channel multiplier coverage differs")

    if len(sca_d) != 156:
        raise RequantRuntimeError("SCA_D must contain 128 final and 28 resident guard reads")
    roles = {"guard_resident": 0, "round_final": 0}
    for name, entry in sca_d.items():
        role = "guard_resident" if "_guard_" in name else "round_final"
        roles[role] += 1
        expected_lines = GUARD_LINES if role == "guard_resident" else ROUND_LINES
        if (
            set(entry) != {"base_addr", "path", "length"}
            or entry["length"] != expected_lines
            or not entry["path"].startswith("sim_results/formal_readback/")
        ):
            raise RequantRuntimeError(f"SCA_D entry differs: {name}")
    if roles != {"guard_resident": 28, "round_final": 128}:
        raise RequantRuntimeError(f"SCA_D role counts differ: {roles}")

    tail = package / "tb_probe/requant_mse4_guard_observer_tail.svh"
    if not tail.is_file() or tail.stat().st_size > 64 * 1024:
        raise RequantRuntimeError("read-only TB probe tail is missing or oversized")
    tail_text = tail.read_text(encoding="utf-8")
    active_lines = [
        line.split("//", 1)[0]
        for line in tail_text.splitlines()
        if not line.lstrip().startswith("//")
    ]
    active_text = "\n".join(active_lines)
    for forbidden in ("force ", "<=", "deposit", "release "):
        if forbidden in active_text:
            raise RequantRuntimeError(f"TB probe contains forbidden driver token: {forbidden}")
    if "+REQUANT_GUARD_PROBE" not in tail_text:
        raise RequantRuntimeError("TB probe is not independently gated")
    return {
        "schema": RUNTIME_SCHEMA,
        "status": "package_preflight_passed",
        "candidate_release": False,
        "evidence_level": "E2_LOCAL_ONLY",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "install_name": install_name,
        "occurrence_count": OCCURRENCE_COUNT,
        "start_comp_count": STAGE_COUNT,
        "same_mask_fence_count": STAGE_COUNT,
        "preload_count": 178,
        "formal_readback_count": 156,
        "historical_guard_probe_count": 128,
        "functional_rtl_file_count": 0,
        "tb_probe_file_count": 1,
    }


def _word128_line(payload: bytes) -> bytes:
    if len(payload) != 16:
        raise RequantRuntimeError("128-bit payload size differs")
    return f"{int.from_bytes(payload, 'little'):0128b}\n".encode("ascii")


def _extract_shard(
    raw: bytes, sample: int, channels: list[int], item_size: int
) -> Iterable[bytes]:
    if len(channels) != SHARD_CHANNELS:
        raise RequantRuntimeError("HWC8 shard must contain eight channels")
    sample_stride = CHANNELS * SPATIAL * item_size
    channel_stride = SPATIAL * item_size
    base = sample * sample_stride
    for spatial in range(SPATIAL):
        row = bytearray()
        for channel in channels:
            offset = base + channel * channel_stride + spatial * item_size
            row.extend(raw[offset : offset + item_size])
        yield bytes(row)


def materialize_installed(
    package_root: Path,
    ndp_root: Path,
    install_name: str,
    output: Path,
) -> dict[str, Any]:
    package = package_root.resolve()
    root = ndp_root.resolve()
    preflight_package(package, install_name)
    installed = root / "install/cfg_pkg" / install_name
    layout = _load_json(installed / "layout_contract.json")
    manifest = _load_json(package / MANIFEST_NAME)
    meta = manifest["compact_data"]["input"]
    raw = _read_compact(
        installed / meta["path"],
        meta["raw_size_bytes"],
        meta["raw_sha256"],
    )
    records: list[dict[str, Any]] = []
    for binding in layout["input_bindings"]:
        target = _inside(installed, binding["installed_relative_path"])
        if target.exists():
            raise RequantRuntimeError(f"materialized input target exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        line_count = 0
        with target.open("wb") as stream:
            pending = bytearray()
            for row in _extract_shard(
                raw, binding["sample_id"], binding["channels"], item_size=4
            ):
                pending.extend(row)
                while len(pending) >= 16:
                    line = _word128_line(bytes(pending[:16]))
                    del pending[:16]
                    stream.write(line)
                    digest.update(line)
                    line_count += 1
            if pending:
                raise RequantRuntimeError("int32 HWC8 materialization is not aligned")
        if line_count != INPUT_LINES:
            raise RequantRuntimeError("input materialization line count differs")
        records.append(
            {
                "sca_key": binding["sca_key"],
                "path": target.relative_to(installed).as_posix(),
                "sample_id": binding["sample_id"],
                "channels": binding["channels"],
                "line_count": line_count,
                "size_bytes": target.stat().st_size,
                "sha256": digest.hexdigest(),
            }
        )
    receipt = {
        "schema": MATERIALIZATION_SCHEMA,
        "status": "materialized",
        "install_name": install_name,
        "input_binding_count": len(records),
        "input_line_count": sum(item["line_count"] for item in records),
        "records": records,
    }
    _write_json(output, receipt)
    return receipt


def preflight_installed(
    package_root: Path,
    ndp_root: Path,
    install_name: str,
    materialization_receipt: Path,
) -> dict[str, Any]:
    report = preflight_package(package_root, install_name)
    installed = ndp_root.resolve() / "install/cfg_pkg" / install_name
    receipt = _load_json(materialization_receipt)
    if (
        receipt.get("schema") != MATERIALIZATION_SCHEMA
        or receipt.get("input_binding_count") != 128
    ):
        raise RequantRuntimeError("input materialization receipt differs")
    for item in receipt["records"]:
        path = _inside(installed, item["path"])
        if (
            not path.is_file()
            or path.stat().st_size != item["size_bytes"]
            or _sha256(path) != item["sha256"]
        ):
            raise RequantRuntimeError(f"materialized input differs: {item['path']}")
    return {
        **report,
        "status": "installed_preflight_passed",
        "materialized_input_count": 128,
        "installed_tree": _tree_identity(installed),
    }


def install_probe(
    ndp_root: Path,
    package_root: Path,
    evidence_root: Path,
    tb_relative_path: str | None = None,
) -> dict[str, Any]:
    root, observer, explicit = _resolve_tb_target(ndp_root, tb_relative_path)
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    tail = package / "tb_probe/requant_mse4_guard_observer_tail.svh"
    backup = evidence / "native_return_observer.preimage"
    receipt_path = evidence / "tb_probe_install_receipt.json"
    if not observer.is_file() or not tail.is_file() or backup.exists():
        raise RequantRuntimeError("TB probe preimage/tail/backup precondition failed")
    original = observer.read_bytes()
    tail_raw = tail.read_bytes()
    separator = b"" if original.endswith(b"\n") else b"\n"
    installed = original + separator + tail_raw
    backup.write_bytes(original)
    observer.write_bytes(installed)
    receipt = {
        "schema": INSTALL_RECEIPT_SCHEMA,
        "status": "installed_for_compile_only",
        "target": "native_return_observer.svh",
        "read_only_non_driving": True,
        "functional_rtl_modified": False,
        "preimage_size_bytes": len(original),
        "preimage_sha256": _sha256_bytes(original),
        "tail_size_bytes": len(tail_raw),
        "tail_sha256": _sha256_bytes(tail_raw),
        "installed_size_bytes": len(installed),
        "installed_sha256": _sha256_bytes(installed),
        "restored": False,
        "target_directory_isolation": _probe_target_isolation(
            root=root,
            target=observer,
            argument_was_explicit=explicit,
            preimage_size=len(original),
            preimage_sha256=_sha256_bytes(original),
        ),
    }
    _write_json(receipt_path, receipt)
    return receipt


def verify_probe_installed(
    ndp_root: Path,
    evidence_root: Path,
    tb_relative_path: str | None = None,
) -> dict[str, Any]:
    root, observer, explicit = _resolve_tb_target(ndp_root, tb_relative_path)
    evidence = evidence_root.resolve()
    backup = evidence / "native_return_observer.preimage"
    install_receipt_path = evidence / "tb_probe_install_receipt.json"
    if (
        not observer.is_file()
        or observer.is_symlink()
        or not backup.is_file()
        or not install_receipt_path.is_file()
    ):
        raise RequantRuntimeError("TB probe precompile inputs are missing or unsafe")
    receipt = _load_json(install_receipt_path)
    if (
        receipt.get("schema") != INSTALL_RECEIPT_SCHEMA
        or receipt.get("status") != "installed_for_compile_only"
        or receipt.get("restored") is not False
    ):
        raise RequantRuntimeError("TB probe is not in the compile-only installed state")
    isolation = _verify_probe_target_receipt(
        receipt,
        root=root,
        target=observer,
        require_explicit=explicit,
    )
    observer_size = observer.stat().st_size
    observer_sha256 = _sha256(observer)
    xmr_elaboration_gate = validate_observer_xmr_elaboration(
        observer.read_text(encoding="utf-8")
    )
    backup_size = backup.stat().st_size
    backup_sha256 = _sha256(backup)
    if (
        observer_size != receipt.get("installed_size_bytes")
        or observer_sha256 != receipt.get("installed_sha256")
        or backup_size != receipt.get("preimage_size_bytes")
        or backup_sha256 != receipt.get("preimage_sha256")
    ):
        raise RequantRuntimeError("TB probe precompile byte identity differs")
    return {
        "schema": PRECOMPILE_RECEIPT_SCHEMA,
        "status": "installed_observer_verified_for_compile",
        "target": "native_return_observer.svh",
        "target_is_regular_file": True,
        "target_is_symlink": False,
        "target_size_bytes": observer_size,
        "target_sha256": observer_sha256,
        "backup_size_bytes": backup_size,
        "backup_sha256": backup_sha256,
        "expected_installed_sha256": receipt["installed_sha256"],
        "explicit_vcs_include_directory": root.as_posix(),
        "xmr_elaboration_gate": xmr_elaboration_gate,
        "target_directory_isolation": isolation,
        "functional_rtl_modified": False,
        "passed": True,
    }


def restore_probe(
    ndp_root: Path,
    evidence_root: Path,
    tb_relative_path: str | None = None,
) -> dict[str, Any]:
    root, observer, explicit = _resolve_tb_target(ndp_root, tb_relative_path)
    evidence = evidence_root.resolve()
    backup = evidence / "native_return_observer.preimage"
    receipt_path = evidence / "tb_probe_install_receipt.json"
    if not backup.is_file() or not receipt_path.is_file() or not observer.is_file():
        raise RequantRuntimeError("TB probe restore inputs are missing")
    receipt = _load_json(receipt_path)
    _verify_probe_target_receipt(
        receipt,
        root=root,
        target=observer,
        require_explicit=explicit,
    )
    if _sha256(observer) != receipt["installed_sha256"]:
        raise RequantRuntimeError("TB probe installed target differs before restore")
    original = backup.read_bytes()
    if _sha256_bytes(original) != receipt["preimage_sha256"]:
        raise RequantRuntimeError("TB probe backup differs")
    observer.write_bytes(original)
    if _sha256(observer) != receipt["preimage_sha256"]:
        raise RequantRuntimeError("TB probe byte restore failed")
    receipt["status"] = "restored_byte_exact"
    receipt["restored"] = True
    receipt["restored_sha256"] = _sha256(observer)
    _write_json(receipt_path, receipt)
    return receipt


def capture_identity(
    ndp_root: Path,
    package_manifest: Path,
    install_name: str,
    phase: str,
    server_command: str,
    exit_status: int | None,
) -> dict[str, Any]:
    root = ndp_root.resolve()
    manifest_path = package_manifest.resolve()
    manifest = _load_json(manifest_path)
    return {
        "schema": IDENTITY_SCHEMA,
        "phase": phase,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "server_command": server_command,
        "exit_status": exit_status,
        "test_package": {
            "manifest": _file_identity(manifest_path),
            "schema": manifest.get("schema"),
            "install_name": manifest.get("install_name"),
            "payload_tree_sha256": manifest.get("payload_tree_sha256"),
        },
        "rtl_tree": _tree_identity(root / "rtl"),
        "focused_rtl": {
            relative: _file_identity(root / relative) for relative in FOCUS_RTL
        },
        "support_files": {
            relative: _file_identity(root / relative) for relative in SUPPORT_FILES
        },
        "installed_runtime": _tree_identity(root / "install/cfg_pkg" / install_name),
        "git": _git_identity(root),
        "rtl_git": _git_identity(root / "rtl"),
    }


def verify_identity(
    paths: list[Path],
    probe_receipt_path: Path,
    precompile_receipt_path: Path,
) -> dict[str, Any]:
    documents = [_load_json(path.resolve()) for path in paths]
    phases = [
        "pre_install",
        "post_probe_install",
        "post_compile",
        "post_run",
        "post_restore",
    ]
    if [item.get("phase") for item in documents] != phases:
        raise RequantRuntimeError("identity phase order differs")
    if any(item.get("schema") != IDENTITY_SCHEMA for item in documents):
        raise RequantRuntimeError("identity schema differs")
    receipt = _load_json(probe_receipt_path)
    precompile_receipt = _load_json(precompile_receipt_path)
    precompile_verified = (
        precompile_receipt.get("schema") == PRECOMPILE_RECEIPT_SCHEMA
        and precompile_receipt.get("status")
        == "installed_observer_verified_for_compile"
        and precompile_receipt.get("target_sha256")
        == receipt.get("installed_sha256")
        and precompile_receipt.get("backup_sha256")
        == receipt.get("preimage_sha256")
        and precompile_receipt.get("functional_rtl_modified") is False
        and precompile_receipt.get("passed") is True
    )
    stable_manifest = len(
        {item["test_package"]["manifest"]["sha256"] for item in documents}
    ) == 1
    stable_command = len({item["server_command"] for item in documents}) == 1
    rtl_hashes = [item["rtl_tree"]["tree_sha256"] for item in documents]
    rtl_stable = None not in rtl_hashes and len(set(rtl_hashes)) == 1
    focused = {
        relative: len(
            {
                (
                    item["focused_rtl"][relative]["exists"],
                    item["focused_rtl"][relative]["size_bytes"],
                    item["focused_rtl"][relative]["sha256"],
                )
                for item in documents
            }
        )
        == 1
        and documents[0]["focused_rtl"][relative]["exists"]
        for relative in FOCUS_RTL
    }
    stable_support = {}
    for relative in SUPPORT_FILES:
        values = [item["support_files"][relative] for item in documents]
        if relative == "native_return_observer.svh":
            stable_support[relative] = (
                values[0]["sha256"] == receipt["preimage_sha256"]
                and values[1]["sha256"] == receipt["installed_sha256"]
                and values[2]["sha256"] == receipt["preimage_sha256"]
                and values[3]["sha256"] == receipt["preimage_sha256"]
                and values[4]["sha256"] == receipt["preimage_sha256"]
                and receipt.get("restored") is True
            )
        else:
            stable_support[relative] = (
                all(value["exists"] for value in values)
                and len(
                    {(value["size_bytes"], value["sha256"]) for value in values}
                )
                == 1
            )
    installed = [item["installed_runtime"]["tree_sha256"] for item in documents]
    installed_stable = (
        installed[0] is None
        and installed[1] is not None
        and installed[1] == installed[2] == installed[3] == installed[4]
    )
    passed = (
        stable_manifest
        and stable_command
        and rtl_stable
        and all(focused.values())
        and all(stable_support.values())
        and installed_stable
        and precompile_verified
    )
    return {
        "schema": IDENTITY_RECEIPT_SCHEMA,
        "status": "stock_rtl_and_transactional_tb_probe_verified" if passed else "fail",
        "functional_rtl_unchanged": rtl_stable and all(focused.values()),
        "tb_probe_transactionally_restored": stable_support[
            "native_return_observer.svh"
        ],
        "tb_probe_verified_immediately_before_compile": precompile_verified,
        "package_manifest_stable": stable_manifest,
        "server_command_stable": stable_command,
        "installed_namespace_stable": installed_stable,
        "focused_rtl": focused,
        "support_files": stable_support,
        "phases": phases,
    }


def _simulation_gate(run_dir: Path, install_name: str, run_status: int) -> dict[str, Any]:
    path = run_dir.resolve() / "sim_results/sim.log"
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    required = {
        "sca_path": f"../install/cfg_pkg/{install_name}/sca_cfg.json",
        "sca_d_path": f"../install/cfg_pkg/{install_name}/sca_cfg_D.json",
        "preload_count": "JSON config: 178 matrices loaded",
        "readback_count": "JSON_D config: 156 matrices dumped",
        "success": "Simulation completed successfully!",
    }
    found = {name: marker in text for name, marker in required.items()}
    start_count = text.count("INFO: slice start")
    completion_count = text.count("INFO: slice completed after")
    first_sfu = text.find("RequantGuard.txt")
    first_start = text.find("INFO: slice start")
    sfu_load_count = text.count("RequantGuard.txt ->")
    forbidden = [
        token
        for token in (
            "Cannot open",
            "skip matrix readback",
            "SIMULATION TIMEOUT",
            "$fatal",
            "Error-[",
        )
        if token in text
    ]
    passed = (
        path.is_file()
        and run_status == 0
        and all(found.values())
        and start_count == STAGE_COUNT
        and completion_count == STAGE_COUNT
        and first_sfu >= 0
        and first_start > first_sfu
        and sfu_load_count == 1
        and not forbidden
    )
    return {
        "status": "pass" if passed else "fail",
        "sim_log_exists": path.is_file(),
        "run_exit_status": run_status,
        "required_markers": found,
        "start_count": start_count,
        "completion_count": completion_count,
        "requant_guard_load_count": sfu_load_count,
        "requant_guard_loaded_before_first_start": first_sfu >= 0
        and first_start > first_sfu,
        "forbidden_markers": forbidden,
        "sim_log_sha256": _sha256(path) if path.is_file() else None,
    }


def _sem_groups(run_dir: Path, event: str) -> list[dict[str, Any]]:
    groups: dict[int, set[int]] = {}
    pattern = re.compile(rf"^\s*(\d+)\s+\|\s+{re.escape(event)}\s+\|")
    for slice_id in range(SLICE_COUNT):
        path = (
            run_dir.resolve()
            / f"sim_results/sem_events/slice{slice_id}/sem_events.log"
        )
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = pattern.match(line)
            if match:
                groups.setdefault(int(match.group(1)), set()).add(slice_id)
    return [
        {
            "time": time,
            "slices": sorted(slices),
            "mask": sum(1 << slice_id for slice_id in slices),
        }
        for time, slices in sorted(groups.items())
    ]


def _lifecycle_gate(run_dir: Path, package_root: Path) -> dict[str, Any]:
    layout = _load_json(package_root.resolve() / "workload/runtime/layout_contract.json")
    expected_masks = [int(value, 2) for value in layout["stage_masks"]]
    starts = _sem_groups(run_dir, "Start Comp")
    finishes = _sem_groups(run_dir, "Comp Finish")
    fences: list[dict[str, Any]] = []
    for index in range(STAGE_COUNT):
        start = starts[index] if index < len(starts) else {}
        finish = finishes[index] if index < len(finishes) else {}
        expected = expected_masks[index]
        passed = (
            start.get("mask") == expected
            and finish.get("mask") == expected
            and isinstance(start.get("time"), int)
            and isinstance(finish.get("time"), int)
            and finish["time"] > start["time"]
            and (
                index == STAGE_COUNT - 1
                or index + 1 >= len(starts)
                or starts[index + 1]["time"] >= finish["time"]
            )
        )
        fences.append(
            {
                "stage_index": index,
                "role": "guard" if index % 2 == 0 else "round_saturate",
                "expected_mask": f"0b{expected:028b}",
                "start_mask": (
                    f"0b{start['mask']:028b}" if "mask" in start else None
                ),
                "finish_mask": (
                    f"0b{finish['mask']:028b}" if "mask" in finish else None
                ),
                "start_time": start.get("time"),
                "finish_time": finish.get("time"),
                "same_mask_completion_fence": passed,
            }
        )
    passed = (
        len(starts) == STAGE_COUNT
        and len(finishes) == STAGE_COUNT
        and all(item["same_mask_completion_fence"] for item in fences)
    )
    return {
        "status": "pass" if passed else "fail",
        "start_group_count": len(starts),
        "finish_group_count": len(finishes),
        "same_mask_fence_pass_count": sum(
            item["same_mask_completion_fence"] for item in fences
        ),
        "all_48_stages_naturally_completed": passed,
        "fences": fences,
    }


def _expected_guard(raw_input: bytes, record: dict[str, Any], slice_id: int) -> bytes:
    sample = record["slice_to_sample"][str(slice_id)]
    result = bytearray()
    for row in _extract_shard(raw_input, sample, record["channels"], item_size=4):
        for offset in range(0, len(row), 4):
            value = struct.unpack_from("<i", row, offset)[0]
            result.extend(struct.pack("<f", float(max(value, 0))))
    return bytes(result)


def _expected_round(raw_output: bytes, record: dict[str, Any], slice_id: int) -> bytes:
    sample = record["slice_to_sample"][str(slice_id)]
    return b"".join(
        _extract_shard(raw_output, sample, record["channels"], item_size=1)
    )


def _probe_guard_gate(
    run_dir: Path, package_root: Path, raw_input: bytes
) -> dict[str, Any]:
    package = package_root.resolve()
    layout = _load_json(package / "workload/runtime/layout_contract.json")
    expected_by_slice: dict[int, list[dict[str, Any]]] = {
        slice_id: [] for slice_id in range(SLICE_COUNT)
    }
    for record in layout["records"]:
        for slice_id in record["active_slices"]:
            expected_by_slice[slice_id].append(record)
    line_re = re.compile(
        r"GUARD_WRITE\s+\|.*local_stage=(\d+).*ch=(\d+).*"
        r"accepted=1\s+valid=1\s+ready=1\s+strobe=0xffff\s+"
        r"addr=0x([0-9a-fA-F]+)\s+data=0x([0-9a-fA-F]{32})"
    )
    entries: list[dict[str, Any]] = []
    all_pass = True
    for slice_id in range(SLICE_COUNT):
        path = (
            run_dir.resolve()
            / f"sim_results/requant_guard_probe/slice{slice_id:02d}.log"
        )
        by_stage: dict[int, dict[int, bytes]] = {}
        errors: list[str] = []
        if path.is_file():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if "PROBE_ERROR" in line:
                    errors.append(line[-240:])
                match = line_re.search(line)
                if not match:
                    continue
                local_stage = int(match.group(1))
                address = int(match.group(3), 16)
                payload = int(match.group(4), 16).to_bytes(16, "little")
                stage_map = by_stage.setdefault(local_stage, {})
                if address in stage_map:
                    errors.append(f"duplicate address stage={local_stage} addr={address:#x}")
                stage_map[address] = payload
        expected_records = expected_by_slice[slice_id]
        for local_occurrence, record in enumerate(expected_records):
            local_stage = local_occurrence * 2
            address_map = by_stage.get(local_stage, {})
            addresses = sorted(address_map)
            expected = _expected_guard(raw_input, record, slice_id)
            actual = b"".join(address_map[address] for address in addresses)
            expected_first = int(record["guard_base_addr"], 16) // 16
            contiguous = (
                len(addresses) == GUARD_LINES
                and addresses == list(range(expected_first, expected_first + GUARD_LINES))
            )
            mismatch = None
            if len(actual) == len(expected) and actual != expected:
                for index, (left, right) in enumerate(zip(actual, expected)):
                    if left != right:
                        mismatch = index
                        break
            passed = contiguous and actual == expected and not errors
            all_pass = all_pass and passed
            entries.append(
                {
                    "slice": slice_id,
                    "global_occurrence": record["occurrence_index"],
                    "local_stage": local_stage,
                    "line_count": len(addresses),
                    "first_address": f"0x{addresses[0]:x}" if addresses else None,
                    "last_address": f"0x{addresses[-1]:x}" if addresses else None,
                    "addresses_contiguous": contiguous,
                    "actual_payload_sha256": _sha256_bytes(actual),
                    "expected_payload_sha256": _sha256_bytes(expected),
                    "first_mismatch_byte": mismatch,
                    "status": "pass" if passed else "fail",
                }
            )
    return {
        "status": "pass" if all_pass and len(entries) == 128 else "fail",
        "evidence_kind": "same_clock_read_only_mse4_write_observer",
        "historical_guard_entry_count": len(entries),
        "expected_historical_guard_entry_count": 128,
        "all_historical_guard_values_bit_exact": all_pass and len(entries) == 128,
        "entries": entries,
    }


def _formal_readback_gate(
    run_dir: Path,
    package_root: Path,
    raw_input: bytes,
    raw_output: bytes,
) -> dict[str, Any]:
    package = package_root.resolve()
    sca_d = _load_json(package / "workload/runtime/sca_cfg_D.json")
    layout = _load_json(package / "workload/runtime/layout_contract.json")
    by_name = {record["occurrence_name"]: record for record in layout["records"]}
    entries: list[dict[str, Any]] = []
    all_pass = True
    for name, item in sca_d.items():
        actual_path = _inside(run_dir.resolve(), item["path"])
        role = "guard_resident" if "_guard_" in name else "round_final"
        match = re.fullmatch(r"(op_w\d+_s\d+_(?:guard|round))_matrixD_slice(\d+)", name)
        if match is None:
            raise RequantRuntimeError(f"unexpected SCA_D key: {name}")
        occurrence_name, slice_text = match.groups()
        record = by_name[occurrence_name.rsplit("_", 1)[0]]
        slice_id = int(slice_text)
        expected = (
            _expected_guard(raw_input, record, slice_id)
            if role == "guard_resident"
            else _expected_round(raw_output, record, slice_id)
        )
        line_count = GUARD_LINES if role == "guard_resident" else ROUND_LINES
        actual = b""
        valid = False
        if actual_path.is_file():
            try:
                actual = _decode_128bit_text(actual_path, line_count)
                valid = True
            except (OSError, UnicodeError, RequantRuntimeError):
                valid = False
        mismatch = None
        if valid and actual != expected:
            for index, (left, right) in enumerate(zip(actual, expected)):
                if left != right:
                    mismatch = index
                    break
        passed = valid and actual == expected
        all_pass = all_pass and passed
        entries.append(
            {
                "name": name,
                "role": role,
                "slice": slice_id,
                "occurrence": record["occurrence_index"],
                "base_addr": item["base_addr"],
                "line_count": line_count if valid else None,
                "actual_file_sha256": (
                    _sha256(actual_path) if actual_path.is_file() else None
                ),
                "actual_payload_sha256": _sha256_bytes(actual) if valid else None,
                "expected_payload_sha256": _sha256_bytes(expected),
                "first_mismatch_byte": mismatch,
                "status": "pass" if passed else "fail",
            }
        )
    role_counts = {
        role: sum(item["role"] == role for item in entries)
        for role in ("guard_resident", "round_final")
    }
    passed = (
        all_pass
        and role_counts == {"guard_resident": 28, "round_final": 128}
    )
    return {
        "status": "pass" if passed else "fail",
        "formal_readback_entry_count": len(entries),
        "role_counts": role_counts,
        "all_128_final_uint8_bit_exact": all(
            item["status"] == "pass"
            for item in entries
            if item["role"] == "round_final"
        )
        and role_counts["round_final"] == 128,
        "all_28_resident_guard_bit_exact": all(
            item["status"] == "pass"
            for item in entries
            if item["role"] == "guard_resident"
        )
        and role_counts["guard_resident"] == 28,
        "entries": entries,
    }


def analyze(
    ndp_root: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    run_status: int,
) -> dict[str, Any]:
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    manifest = _load_json(package / MANIFEST_NAME)
    input_meta = manifest["compact_data"]["input"]
    output_meta = manifest["compact_data"]["golden"]
    raw_input = _read_compact(
        package / "workload/runtime" / input_meta["path"],
        input_meta["raw_size_bytes"],
        input_meta["raw_sha256"],
    )
    raw_output = _read_compact(
        package / output_meta["path"],
        output_meta["raw_size_bytes"],
        output_meta["raw_sha256"],
    )
    identity_path = evidence / "stock_rtl_identity_receipt.json"
    identity = _load_json(identity_path) if identity_path.is_file() else {}
    identity_pass = (
        identity.get("status") == "stock_rtl_and_transactional_tb_probe_verified"
        and identity.get("functional_rtl_unchanged") is True
        and identity.get("tb_probe_transactionally_restored") is True
    )
    simulation = _simulation_gate(run_dir, install_name, run_status)
    lifecycle = _lifecycle_gate(run_dir, package)
    guard_probe = _probe_guard_gate(run_dir, package, raw_input)
    formal = _formal_readback_gate(run_dir, package, raw_input, raw_output)
    coverage = _load_json(package / "validation/coverage_contract.json")
    coverage_pass = (
        coverage.get("all_64_channel_multipliers_covered") is True
        and coverage.get("counts", {}).get("round_half_even_tie", 0) > 0
        and coverage.get("counts", {}).get("lower_saturation", 0) > 0
        and coverage.get("counts", {}).get("negative", 0) > 0
        and coverage.get("counts", {}).get("minus_one", 0) > 0
        and coverage.get("counts", {}).get("zero", 0) > 0
        and coverage.get("counts", {}).get("positive", 0) > 0
    )
    passed = (
        run_status == 0
        and simulation["status"] == "pass"
        and lifecycle["status"] == "pass"
        and guard_probe["status"] == "pass"
        and formal["status"] == "pass"
        and identity_pass
        and coverage_pass
    )
    formal_path = evidence / "FORMAL_READBACK_RECEIPT.json"
    probe_path = evidence / "GUARD_PROBE_RECEIPT.json"
    lifecycle_path = evidence / "LIFECYCLE_RECEIPT.json"
    _write_json(formal_path, formal)
    _write_json(probe_path, guard_probe)
    _write_json(lifecycle_path, lifecycle)
    return {
        "schema": RESULT_SCHEMA,
        "status": "E4_PASS" if passed else "E4_FAIL_OR_INCOMPLETE",
        "classification": "FIRST_DYNAMIC_RUN" if passed else "FIRST_DYNAMIC_FAILURE",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "install_name": install_name,
        "candidate_release": False,
        "formal_target_instance_allowed": False,
        "release_gate_passed": False,
        "evidence_level": "E4_SERVER_DYNAMIC" if passed else "SERVER_INCOMPLETE",
        "run_exit_status": run_status,
        "gates": {
            "simulation_and_natural_exit": simulation,
            "same_mask_lifecycle": {
                "status": lifecycle["status"],
                "start_group_count": lifecycle["start_group_count"],
                "finish_group_count": lifecycle["finish_group_count"],
                "same_mask_fence_pass_count": lifecycle[
                    "same_mask_fence_pass_count"
                ],
            },
            "historical_guard_same_clock_observer": {
                "status": guard_probe["status"],
                "entry_count": guard_probe["historical_guard_entry_count"],
                "all_bit_exact": guard_probe[
                    "all_historical_guard_values_bit_exact"
                ],
            },
            "formal_d_readback": {
                "status": formal["status"],
                "entry_count": formal["formal_readback_entry_count"],
                "all_128_final_uint8_bit_exact": formal[
                    "all_128_final_uint8_bit_exact"
                ],
                "all_28_resident_guard_bit_exact": formal[
                    "all_28_resident_guard_bit_exact"
                ],
            },
            "boundary_and_multiplier_coverage": {
                "status": "pass" if coverage_pass else "fail",
                "counts": coverage["counts"],
                "all_64_channel_multipliers_covered": coverage[
                    "all_64_channel_multipliers_covered"
                ],
            },
            "stock_rtl_and_tb_probe_identity": {
                "status": "pass" if identity_pass else "fail",
                "functional_rtl_unchanged": identity_pass,
            },
        },
        "guard_readback_claim_boundary": {
            "historical_occurrences": "same-clock read-only MSE4 write observer",
            "resident_end_of_run": "28 unique-address formal D readbacks",
            "duplicate_alias_dumps_used_as_evidence": False,
        },
        "remaining_blockers": (
            ["B_REQUANT_SERVER_E5"] if passed else ["B_REQUANT_SERVER_E4_E5"]
        ),
        "next_gate": (
            "fresh package/install/run/return identity E5 after independent E4 acceptance"
            if passed
            else "classify the earliest first-dynamic E4 divergence before E5"
        ),
    }


def _copy_tail(source: Path, destination: Path, limit: int = 200_000) -> None:
    if not source.is_file():
        return
    raw = source.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw[-limit:])


def collect_return(
    ndp_root: Path,
    package_root: Path,
    install_name: str,
    evidence_root: Path,
    run_dir: Path,
    run_status: int,
    server_command: str,
) -> dict[str, Any]:
    root = ndp_root.resolve()
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    run = run_dir.resolve()
    return_name = f"{install_name}_return"
    staging = root / return_name
    zip_path = root / f"{return_name}.zip"
    sidecar = root / f"{return_name}.zip.sha256"
    for target in (staging, zip_path, sidecar):
        if target.exists():
            raise RequantRuntimeError(f"return target must be fresh: {target}")
    staging.mkdir(parents=True)
    records: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    def add(source: Path, relative_value: str, role: str, required: bool = True) -> None:
        relative = _safe_relative(relative_value)
        if set(part.lower() for part in relative.parts) & FORBIDDEN_RETURN_PARTS:
            raise RequantRuntimeError(f"forbidden return path: {relative}")
        if relative.suffix.lower() in FORBIDDEN_ARCHIVE_SUFFIXES:
            raise RequantRuntimeError(f"forbidden return suffix: {relative}")
        if not source.is_file() or source.stat().st_size > MAX_RETURN_FILE_BYTES:
            if required:
                missing.append({"path": relative.as_posix(), "role": role})
            return
        target = _inside(staging, relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        records.append(
            {
                "path": relative.as_posix(),
                "role": role,
                "size_bytes": target.stat().st_size,
                "sha256": _sha256(target),
            }
        )

    add(package / MANIFEST_NAME, f"package/{MANIFEST_NAME}", "package_identity")
    for name in (
        "package_preflight.json",
        "input_materialization_receipt.json",
        "installed_preflight.json",
        "tb_probe_install_receipt.json",
        "tb_probe_precompile_receipt.json",
        "server_identity_pre_install.json",
        "server_identity_post_probe_install.json",
        "server_identity_post_compile.json",
        "server_identity_post_run.json",
        "server_identity_post_restore.json",
        "stock_rtl_identity_receipt.json",
        "FORMAL_READBACK_RECEIPT.json",
        "GUARD_PROBE_RECEIPT.json",
        "LIFECYCLE_RECEIPT.json",
        "SERVER_RESULT_GATE.json",
        "server_command.txt",
        "compile_exit_status.txt",
        "sim_exit_status.txt",
        "run_exit_status.txt",
        "termination_signal.txt",
    ):
        add(evidence / name, f"evidence/{name}", "identity_and_gate", name != "termination_signal.txt")
    add(
        root / f"install/cfg_pkg/{install_name}/sca_cfg.json",
        "config/sca_cfg.json",
        "runtime_sca",
    )
    add(
        root / f"install/cfg_pkg/{install_name}/sca_cfg_D.json",
        "config/sca_cfg_D.json",
        "runtime_sca_d",
    )
    _copy_tail(run / "sim_results/compile.log", staging / "logs/compile_tail.log")
    _copy_tail(
        run / "sim_results/compile_driver.log",
        staging / "logs/compile_driver_tail.log",
    )
    _copy_tail(run / "sim_results/sim.log", staging / "logs/sim_tail.log")
    for name in ("compile_tail.log", "compile_driver_tail.log", "sim_tail.log"):
        path = staging / "logs" / name
        if path.is_file():
            records.append(
                {
                    "path": f"logs/{name}",
                    "role": "bounded_log_tail",
                    "size_bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    gate_path = evidence / "SERVER_RESULT_GATE.json"
    gate = _load_json(gate_path) if gate_path.is_file() else {}
    receipt = {
        "schema": RETURN_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if not missing else "incomplete",
        "server_result_status": gate.get("status", "missing"),
        "classification": gate.get("classification", "FIRST_DYNAMIC_FAILURE"),
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "install_name": install_name,
        "candidate_release": False,
        "run_exit_status": run_status,
        "server_command": server_command,
        "allowlist_only": True,
        "raw_readback_included": False,
        "raw_guard_probe_included": False,
        "raw_large_evidence_location": run.as_posix(),
        "raw_large_evidence_omission_reason": (
            "about 350 MiB of deterministic text remains in the isolated RUN_DIR; "
            "the return carries per-entry line counts, hashes, mismatch offsets and "
            "the fixed analyzer/package identities"
        ),
        "waveforms_included": False,
        "build_tree_included": False,
        "nested_archive_included": False,
        "required_missing": missing,
        "payload_file_count": len(records),
        "payload_size_bytes": sum(item["size_bytes"] for item in records),
        "files": sorted(records, key=lambda item: item["path"]),
    }
    _write_json(staging / "RETURN_RECEIPT.json", receipt)
    extracted = sum(path.stat().st_size for path in staging.rglob("*") if path.is_file())
    if extracted > MAX_RETURN_EXTRACTED_BYTES:
        raise RequantRuntimeError("return extracted size exceeds 12 MiB")
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in staging.rglob("*") if item.is_file()):
            relative = f"{return_name}/{path.relative_to(staging).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100644 & 0xFFFF) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    if zip_path.stat().st_size > MAX_RETURN_ZIP_BYTES:
        raise RequantRuntimeError("return ZIP exceeds 6 MiB")
    digest = _sha256(zip_path)
    sidecar.write_text(f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n")
    return {
        **receipt,
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": sidecar.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    package_preflight = sub.add_parser("preflight-package")
    package_preflight.add_argument("--package-root", type=Path, required=True)
    package_preflight.add_argument("--install-name", required=True)
    package_preflight.add_argument("--output", type=Path, required=True)
    materialize = sub.add_parser("materialize-installed")
    materialize.add_argument("--package-root", type=Path, required=True)
    materialize.add_argument("--ndp-root", type=Path, required=True)
    materialize.add_argument("--install-name", required=True)
    materialize.add_argument("--output", type=Path, required=True)
    installed = sub.add_parser("preflight-installed")
    installed.add_argument("--package-root", type=Path, required=True)
    installed.add_argument("--ndp-root", type=Path, required=True)
    installed.add_argument("--install-name", required=True)
    installed.add_argument("--materialization-receipt", type=Path, required=True)
    installed.add_argument("--output", type=Path, required=True)
    probe_install = sub.add_parser("install-probe")
    probe_install.add_argument("--ndp-root", type=Path, required=True)
    probe_install.add_argument("--package-root", type=Path, required=True)
    probe_install.add_argument("--evidence-root", type=Path, required=True)
    probe_install.add_argument("--tb-relative-path")
    probe_precompile = sub.add_parser("verify-probe-installed")
    probe_precompile.add_argument("--ndp-root", type=Path, required=True)
    probe_precompile.add_argument("--evidence-root", type=Path, required=True)
    probe_precompile.add_argument("--tb-relative-path")
    probe_precompile.add_argument("--output", type=Path, required=True)
    probe_restore = sub.add_parser("restore-probe")
    probe_restore.add_argument("--ndp-root", type=Path, required=True)
    probe_restore.add_argument("--evidence-root", type=Path, required=True)
    probe_restore.add_argument("--tb-relative-path")
    capture = sub.add_parser("capture-identity")
    capture.add_argument("--ndp-root", type=Path, required=True)
    capture.add_argument("--package-manifest", type=Path, required=True)
    capture.add_argument("--install-name", required=True)
    capture.add_argument("--phase", required=True)
    capture.add_argument("--server-command", required=True)
    capture.add_argument("--exit-status", type=int)
    capture.add_argument("--output", type=Path, required=True)
    verify = sub.add_parser("verify-identity")
    for name in (
        "pre-install",
        "post-probe-install",
        "post-compile",
        "post-run",
        "post-restore",
    ):
        verify.add_argument(f"--{name}", type=Path, required=True)
    verify.add_argument("--probe-receipt", type=Path, required=True)
    verify.add_argument("--precompile-receipt", type=Path, required=True)
    verify.add_argument("--output", type=Path, required=True)
    analyze_parser = sub.add_parser("analyze")
    analyze_parser.add_argument("--ndp-root", type=Path, required=True)
    analyze_parser.add_argument("--package-root", type=Path, required=True)
    analyze_parser.add_argument("--install-name", required=True)
    analyze_parser.add_argument("--evidence-root", type=Path, required=True)
    analyze_parser.add_argument("--run-dir", type=Path, required=True)
    analyze_parser.add_argument("--run-status", type=int, required=True)
    analyze_parser.add_argument("--output", type=Path, required=True)
    collect = sub.add_parser("collect")
    collect.add_argument("--ndp-root", type=Path, required=True)
    collect.add_argument("--package-root", type=Path, required=True)
    collect.add_argument("--install-name", required=True)
    collect.add_argument("--evidence-root", type=Path, required=True)
    collect.add_argument("--run-dir", type=Path, required=True)
    collect.add_argument("--run-status", type=int, required=True)
    collect.add_argument("--server-command", required=True)
    args = parser.parse_args()
    try:
        if args.command == "preflight-package":
            report = preflight_package(args.package_root, args.install_name)
            _write_json(args.output, report)
        elif args.command == "materialize-installed":
            report = materialize_installed(
                args.package_root, args.ndp_root, args.install_name, args.output
            )
        elif args.command == "preflight-installed":
            report = preflight_installed(
                args.package_root,
                args.ndp_root,
                args.install_name,
                args.materialization_receipt,
            )
            _write_json(args.output, report)
        elif args.command == "install-probe":
            report = install_probe(
                args.ndp_root,
                args.package_root,
                args.evidence_root,
                args.tb_relative_path,
            )
        elif args.command == "verify-probe-installed":
            report = verify_probe_installed(
                args.ndp_root, args.evidence_root, args.tb_relative_path
            )
            _write_json(args.output, report)
        elif args.command == "restore-probe":
            report = restore_probe(
                args.ndp_root, args.evidence_root, args.tb_relative_path
            )
        elif args.command == "capture-identity":
            report = capture_identity(
                args.ndp_root,
                args.package_manifest,
                args.install_name,
                args.phase,
                args.server_command,
                args.exit_status,
            )
            _write_json(args.output, report)
        elif args.command == "verify-identity":
            report = verify_identity(
                [
                    args.pre_install,
                    args.post_probe_install,
                    args.post_compile,
                    args.post_run,
                    args.post_restore,
                ],
                args.probe_receipt,
                args.precompile_receipt,
            )
            _write_json(args.output, report)
            if report["status"] != "stock_rtl_and_transactional_tb_probe_verified":
                return 6
        elif args.command == "analyze":
            report = analyze(
                args.ndp_root,
                args.package_root,
                args.install_name,
                args.evidence_root,
                args.run_dir,
                args.run_status,
            )
            _write_json(args.output, report)
            if report["status"] != "E4_PASS":
                return 7
        else:
            report = collect_return(
                args.ndp_root,
                args.package_root,
                args.install_name,
                args.evidence_root,
                args.run_dir,
                args.run_status,
                args.server_command,
            )
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Requant node0001 runtime failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
