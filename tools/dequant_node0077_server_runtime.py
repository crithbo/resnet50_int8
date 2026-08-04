#!/usr/bin/env python3
"""Fail-closed server runtime for the DequantizeLinear node0077 E4 package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True


MANIFEST_NAME = "TEST_PACKAGE_MANIFEST.json"
RUNTIME_SCHEMA = "resnet50-dequant-node0077-server-runtime-v2"
RESULT_SCHEMA = "resnet50-dequant-node0077-server-result-gate-v2"
RETURN_SCHEMA = "resnet50-dequant-node0077-server-return-receipt-v2"
IDENTITY_SCHEMA = "resnet50-dequant-node0077-server-identity-v2"
IDENTITY_RECEIPT_SCHEMA = "resnet50-dequant-node0077-stock-rtl-identity-v2"
INSTALL_RECEIPT_SCHEMA = "resnet50-dequant-node0077-tb-probe-install-v2"
PRECOMPILE_RECEIPT_SCHEMA = (
    "resnet50-dequant-node0077-tb-probe-precompile-verification-v2"
)
OBSERVER_RECEIPT_SCHEMA = "resnet50-dequant-node0077-raw-mse4-observer-v1"
OBSERVER_TAIL_RELATIVE = "tb_probe/dequant_node0077_raw_mse4_observer_tail.txt"
SLICE_COUNT = 28
A_LINES = 47
D_LINES = 188
EXEC_LINES = 29
BITSTREAM_LINES = 26
MAX_RETURN_TEXT_BYTES = 2 * 1024 * 1024
MAX_RETURN_EXTRACTED_BYTES = 8 * 1024 * 1024
MAX_RETURN_ZIP_BYTES = 4 * 1024 * 1024
FOCUS_RTL = (
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_RD_Stream_Engine/RD_Memory_AG.sv",
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_RD_Stream_Engine/RD_Data_Channel.sv",
    "rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    "rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_PE_ALU.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_SFU_PE/GA_SFU_PE_Postprocess.sv",
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Memory_AG.sv",
    "rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Memory_WR_Stream_Engine/WR_Data_Channel.sv",
)
SUPPORT_FILES = (
    "tb_NDP_Top_new_phy.sv",
    "native_return_observer.svh",
    "Makefile.tb_NDP_Top_new_phy",
    "rtl/filelists/NDP_Top_phy_filelist.f",
)
FORBIDDEN_PACKAGE_SUFFIXES = {
    ".sv",
    ".svh",
    ".v",
    ".vh",
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


class DequantRuntimeError(RuntimeError):
    """Raised when a package, run, or return gate fails closed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise DequantRuntimeError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
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
        raise DequantRuntimeError(
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


def _safe_relative(value: str) -> PurePosixPath:
    relative = PurePosixPath(value)
    if (
        relative.is_absolute()
        or not relative.parts
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise DequantRuntimeError(f"unsafe relative path: {value!r}")
    return relative


def _inside(root: Path, value: str | PurePosixPath) -> Path:
    relative = _safe_relative(value) if isinstance(value, str) else value
    base = root.resolve()
    target = base.joinpath(*relative.parts).resolve()
    try:
        target.relative_to(base)
    except ValueError as exc:
        raise DequantRuntimeError(f"path escapes root: {relative}") from exc
    return target


def _records(root: Path, *, exclude_manifest: bool = False) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if exclude_manifest and relative == MANIFEST_NAME:
            continue
        records[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return records


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
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode("utf-8")
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
        top = None
    if top is None or top.returncode != 0:
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
        "status_entry_count": len([line for line in status_text.splitlines() if line]),
        "status_sha256": hashlib.sha256(status_text.encode("utf-8")).hexdigest(),
    }


def _validate_128bit_text(path: Path, expected_lines: int) -> list[str]:
    raw = path.read_bytes()
    if b"\r" in raw:
        raise DequantRuntimeError(f"128-bit text contains CR: {path}")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeError as exc:
        raise DequantRuntimeError(f"128-bit text is not ASCII: {path}") from exc
    if len(lines) != expected_lines:
        raise DequantRuntimeError(
            f"128-bit line count differs: {path}: {len(lines)} != {expected_lines}"
        )
    if any(len(line) != 128 or set(line) - {"0", "1"} for line in lines):
        raise DequantRuntimeError(f"invalid 128-bit text: {path}")
    if raw != ("\n".join(lines) + "\n").encode("ascii"):
        raise DequantRuntimeError(f"128-bit text is not LF-canonical: {path}")
    return lines


def _decode_128bit_text(path: Path, expected_lines: int) -> bytes:
    return b"".join(
        int(line, 2).to_bytes(16, byteorder="little")
        for line in _validate_128bit_text(path, expected_lines)
    )


def _runtime_payload_local(
    package: Path, install_name: str, runtime_path: str
) -> Path:
    prefix = f"../install/cfg_pkg/{install_name}/"
    if not runtime_path.startswith(prefix):
        raise DequantRuntimeError(
            f"runtime payload is outside unique namespace: {runtime_path}"
        )
    suffix = _safe_relative(runtime_path[len(prefix) :])
    return _inside(package / "workload/runtime", suffix)


def _indexed_readbacks(sca_d: dict[str, Any]) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for name, entry in sca_d.items():
        match = re.fullmatch(r"op0_matrixD_slice(\d+)", name)
        if match is None or not isinstance(entry, dict):
            raise DequantRuntimeError(f"unexpected SCA_D entry: {name}")
        indexed[int(match.group(1))] = entry
    if set(indexed) != set(range(SLICE_COUNT)):
        raise DequantRuntimeError("SCA_D must cover numeric slices 0..27")
    return indexed


def _load_manifest(package: Path, install_name: str) -> dict[str, Any]:
    manifest = json.loads((package / MANIFEST_NAME).read_text(encoding="utf-8"))
    if manifest.get("install_name") != install_name:
        raise DequantRuntimeError("install name differs from package manifest")
    if manifest.get("files") != _records(package, exclude_manifest=True):
        raise DequantRuntimeError("package payload differs from manifest exact set")
    return manifest


def _dynamic_run_gate(package: Path, install_name: str) -> str:
    """Return the fail-closed E4/E5 gate declared by the exact package manifest."""

    gate = _load_manifest(package, install_name).get("dynamic_run_gate", "E4")
    if gate not in {"E4", "E5"}:
        raise DequantRuntimeError(f"unsupported dynamic run gate: {gate!r}")
    return gate


def _inverse_layout(
    slice_payloads: dict[int, bytes],
    contract: dict[str, Any],
) -> dict[str, Any]:
    logical_shape = contract.get("logical_shape")
    if logical_shape != [16, 1000]:
        raise DequantRuntimeError("layout inverse logical shape differs")
    feature_tile = int(contract.get("feature_tile", 0))
    storage_sample_count = int(contract.get("storage_sample_count", 0))
    if (feature_tile, storage_sample_count) != (250, 3):
        raise DequantRuntimeError("layout inverse physical tile differs")
    descriptors = contract.get("slices")
    if not isinstance(descriptors, list) or len(descriptors) != SLICE_COUNT:
        raise DequantRuntimeError("layout inverse slice descriptor set differs")
    output = bytearray(16 * 1000 * 4)
    coverage = bytearray(16 * 1000)
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise DequantRuntimeError("layout inverse descriptor is not an object")
        slice_id = int(descriptor["slice_id"])
        if slice_id not in slice_payloads:
            raise DequantRuntimeError(f"layout inverse slice{slice_id:02d} missing")
        raw = slice_payloads[slice_id]
        if len(raw) != D_LINES * 16:
            raise DequantRuntimeError(
                f"layout inverse slice{slice_id:02d} byte count differs"
            )
        sample_start = int(descriptor["sample_start"])
        sample_count = int(descriptor["sample_count"])
        feature_start = int(descriptor["feature_start"])
        feature_count = int(descriptor["feature_count"])
        if (
            sample_start < 0
            or sample_count <= 0
            or sample_start + sample_count > 16
            or feature_start < 0
            or feature_count <= 0
            or feature_start + feature_count > 1000
            or feature_count > feature_tile
        ):
            raise DequantRuntimeError(
                f"layout inverse slice{slice_id:02d} range differs"
            )
        for local_sample in range(sample_count):
            for local_feature in range(feature_count):
                source_word = local_sample * feature_tile + local_feature
                target_word = (
                    (sample_start + local_sample) * 1000
                    + feature_start
                    + local_feature
                )
                if coverage[target_word]:
                    raise DequantRuntimeError("layout inverse coverage overlaps")
                coverage[target_word] = 1
                output[target_word * 4 : target_word * 4 + 4] = raw[
                    source_word * 4 : source_word * 4 + 4
                ]
    if any(value != 1 for value in coverage):
        raise DequantRuntimeError("layout inverse coverage is incomplete")
    return {
        "logical_shape": logical_shape,
        "logical_fp32_word_count": len(coverage),
        "coverage_complete": True,
        "coverage_unique": True,
        "raw": bytes(output),
        "sha256": _sha256_bytes(bytes(output)),
    }


def preflight_package(package_root: Path, install_name: str) -> dict[str, Any]:
    package = package_root.resolve()
    manifest = _load_manifest(package, install_name)
    dynamic_run_gate = manifest.get("dynamic_run_gate", "E4")
    if dynamic_run_gate not in {"E4", "E5"}:
        raise DequantRuntimeError(
            f"unsupported dynamic run gate: {dynamic_run_gate!r}"
        )
    forbidden = [
        relative
        for relative in manifest["files"]
        if PurePosixPath(relative).suffix.lower() in FORBIDDEN_PACKAGE_SUFFIXES
    ]
    if forbidden:
        raise DequantRuntimeError(f"forbidden package payload: {forbidden[0]}")
    runtime = package / "workload/runtime"
    sca_path = runtime / "sca_cfg.json"
    sca_d_path = runtime / "sca_cfg_D.json"
    sca = json.loads(sca_path.read_text(encoding="utf-8"))
    sca_d = json.loads(sca_d_path.read_text(encoding="utf-8"))
    for path, value in ((sca_path, sca), (sca_d_path, sca_d)):
        canonical = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
        if path.read_text(encoding="utf-8") != canonical:
            raise DequantRuntimeError(f"SCA must be pretty LF JSON: {path}")
    if sca.get("Exec_Base") != "0x0000_1400" or sca.get("Exec_Length") != EXEC_LINES:
        raise DequantRuntimeError("execution plan base/length differs")
    if sca.get("Repeat_Num") != 1:
        raise DequantRuntimeError("Repeat_Num must equal the one Start_Comp")
    explained = (
        package / "validation/instructions_explained.txt"
    ).read_text(encoding="utf-8")
    if len(re.findall(r"\bStart_Comp for operator op0\b", explained)) != 1:
        raise DequantRuntimeError("instruction evidence must contain one Start_Comp")
    exec_path = _runtime_payload_local(
        package, install_name, sca["ExecutionPlan"]["path"]
    )
    _validate_128bit_text(exec_path, EXEC_LINES)
    packaged_transport = manifest["source_v6"]["packaged_transport"]
    if _sha256(exec_path) != packaged_transport["execplan_lf_sha256"]:
        raise DequantRuntimeError("packaged LF execplan identity differs")
    payload_entries = {
        name: entry
        for name, entry in sca.items()
        if isinstance(entry, dict) and "path" in entry
    }
    if len(payload_entries) != 30:
        raise DequantRuntimeError("SCA must contain 30 preload payloads")
    for slice_id in range(SLICE_COUNT):
        name = f"op0_matrixA_slice{slice_id}"
        entry = payload_entries.get(name)
        if entry is None or int(entry["base_addr"], 16) != slice_id << 25:
            raise DequantRuntimeError(f"slice{slice_id:02d} A address differs")
        a_path = _runtime_payload_local(package, install_name, entry["path"])
        a_raw = _decode_128bit_text(a_path, A_LINES)
        if len(a_raw) != 752 or a_raw[-2:] != b"\x3c\x3c":
            raise DequantRuntimeError(f"slice{slice_id:02d} A padding differs")
    config_entry = payload_entries.get("op0_config")
    if config_entry is None or int(config_entry["base_addr"], 16) != 0x1000:
        raise DequantRuntimeError("config preload address differs")
    config_path = _runtime_payload_local(package, install_name, config_entry["path"])
    _validate_128bit_text(config_path, BITSTREAM_LINES)
    if _sha256(config_path) != packaged_transport["bitstream_lf_sha256"]:
        raise DequantRuntimeError("packaged LF bitstream identity differs")
    indexed = _indexed_readbacks(sca_d)
    if len({int(entry["base_addr"], 16) for entry in indexed.values()}) != SLICE_COUNT:
        raise DequantRuntimeError("formal D readback addresses are not unique")
    golden_payloads: dict[int, bytes] = {}
    for slice_id, entry in sorted(indexed.items()):
        expected_path = (
            f"sim_results/formal_readback/slice{slice_id:02d}/"
            "matrix_D_linearized_128bit.txt"
        )
        if (
            set(entry) != {"base_addr", "path", "length"}
            or int(entry["base_addr"], 16) != (slice_id << 25) + 0x2F0
            or entry["path"] != expected_path
            or entry["length"] != D_LINES
        ):
            raise DequantRuntimeError(f"slice{slice_id:02d} SCA_D differs")
        golden = (
            package
            / f"workload/golden/slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
        )
        raw = _decode_128bit_text(golden, D_LINES)
        if len(raw) != 3008 or raw[-8:] != b"\x00" * 8:
            raise DequantRuntimeError(f"slice{slice_id:02d} golden tail differs")
        golden_payloads[slice_id] = raw
    if any("matrixD" in name for name in payload_entries):
        raise DequantRuntimeError("SCA must not preload formal D")
    inverse_contract = _load_json(
        package / "validation/layout_inverse_contract.json"
    )
    inverse = _inverse_layout(golden_payloads, inverse_contract)
    full_golden = package / "workload/golden/full_output_fp32.bin"
    if not full_golden.is_file() or full_golden.stat().st_size != 64_000:
        raise DequantRuntimeError("independent full-output golden differs")
    if inverse["raw"] != full_golden.read_bytes():
        raise DequantRuntimeError("packaged slice golden layout inverse differs")
    tail_path = _inside(package, OBSERVER_TAIL_RELATIVE)
    if not tail_path.is_file() or not (0 < tail_path.stat().st_size <= 100_000):
        raise DequantRuntimeError("read-only observer tail is missing or oversized")
    tail_text = tail_path.read_text(encoding="utf-8")
    if "+DEQUANT_FULL_E4_PROBE" in tail_text:
        raise DequantRuntimeError("observer plusarg must use $test$plusargs form")
    if '$test$plusargs("DEQUANT_FULL_E4_PROBE")' not in tail_text:
        raise DequantRuntimeError("observer is not independently plusarg-gated")
    for forbidden in ("force ", "deposit ", "$deposit", "assign u_NDP_Top_new"):
        if forbidden in tail_text:
            raise DequantRuntimeError(
                f"observer contains forbidden driver token: {forbidden}"
            )
    xmr_gate = validate_observer_xmr_elaboration(tail_text)
    return {
        "schema": RUNTIME_SCHEMA,
        "status": "package_preflight_passed",
        "candidate_release": False,
        "dynamic_run_gate": dynamic_run_gate,
        "evidence_level": (
            "E4_SERVER_FORMAL_PASS_E5_NOT_RUN"
            if dynamic_run_gate == "E5"
            else "E2_LOCAL_ONLY"
        ),
        "install_name": install_name,
        "slice_count": SLICE_COUNT,
        "preload_count": 30,
        "formal_readback_count": SLICE_COUNT,
        "formal_readback_lines_per_slice": D_LINES,
        "formal_d_preloaded": False,
        "formal_d_addresses_unique": True,
        "layout_inverse_bit_exact": True,
        "layout_inverse_sha256": inverse["sha256"],
        "observer_xmr_elaboration_gate": xmr_gate,
        "repeat_num": 1,
        "start_comp_count": 1,
    }


def preflight_installed(
    package_root: Path, ndp_root: Path, install_name: str
) -> dict[str, Any]:
    report = preflight_package(package_root, install_name)
    source = package_root.resolve() / "workload/runtime"
    installed = ndp_root.resolve() / "install/cfg_pkg" / install_name
    if not installed.is_dir() or _records(source) != _records(installed):
        raise DequantRuntimeError("installed namespace differs byte-for-byte")
    return {
        **report,
        "status": "installed_preflight_passed",
        "installed_file_count": len(_records(installed)),
    }


def install_probe(
    ndp_root: Path, package_root: Path, evidence_root: Path
) -> dict[str, Any]:
    root = ndp_root.resolve()
    package = package_root.resolve()
    evidence = evidence_root.resolve()
    observer = root / "native_return_observer.svh"
    tail = _inside(package, OBSERVER_TAIL_RELATIVE)
    backup = evidence / "native_return_observer.preimage"
    receipt_path = evidence / "tb_probe_install_receipt.json"
    if (
        not observer.is_file()
        or observer.is_symlink()
        or not tail.is_file()
        or tail.is_symlink()
        or backup.exists()
        or receipt_path.exists()
    ):
        raise DequantRuntimeError("TB probe preimage/tail/backup precondition failed")
    original = observer.read_bytes()
    tail_raw = tail.read_bytes()
    separator = b"" if original.endswith(b"\n") else b"\n"
    installed = original + separator + tail_raw
    validate_observer_xmr_elaboration(installed.decode("utf-8"))
    backup.write_bytes(original)
    observer.write_bytes(installed)
    receipt = {
        "schema": INSTALL_RECEIPT_SCHEMA,
        "status": "installed_for_compile_only",
        "target": "native_return_observer.svh",
        "tail_relative_path": OBSERVER_TAIL_RELATIVE,
        "read_only_non_driving": True,
        "functional_rtl_modified": False,
        "preimage_size_bytes": len(original),
        "preimage_sha256": _sha256_bytes(original),
        "tail_size_bytes": len(tail_raw),
        "tail_sha256": _sha256_bytes(tail_raw),
        "installed_size_bytes": len(installed),
        "installed_sha256": _sha256_bytes(installed),
        "restored": False,
    }
    _write_json(receipt_path, receipt)
    return receipt


def verify_probe_installed(
    ndp_root: Path, evidence_root: Path
) -> dict[str, Any]:
    root = ndp_root.resolve()
    evidence = evidence_root.resolve()
    observer = root / "native_return_observer.svh"
    backup = evidence / "native_return_observer.preimage"
    install_receipt_path = evidence / "tb_probe_install_receipt.json"
    if (
        not observer.is_file()
        or observer.is_symlink()
        or not backup.is_file()
        or backup.is_symlink()
        or not install_receipt_path.is_file()
    ):
        raise DequantRuntimeError("TB probe precompile inputs are missing or unsafe")
    receipt = _load_json(install_receipt_path)
    if (
        receipt.get("schema") != INSTALL_RECEIPT_SCHEMA
        or receipt.get("status") != "installed_for_compile_only"
        or receipt.get("restored") is not False
    ):
        raise DequantRuntimeError("TB probe is not in the compile-only installed state")
    observer_size = observer.stat().st_size
    observer_sha256 = _sha256(observer)
    backup_size = backup.stat().st_size
    backup_sha256 = _sha256(backup)
    if (
        observer_size != receipt.get("installed_size_bytes")
        or observer_sha256 != receipt.get("installed_sha256")
        or backup_size != receipt.get("preimage_size_bytes")
        or backup_sha256 != receipt.get("preimage_sha256")
    ):
        raise DequantRuntimeError("TB probe precompile byte identity differs")
    xmr_gate = validate_observer_xmr_elaboration(
        observer.read_text(encoding="utf-8")
    )
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
        "xmr_elaboration_gate": xmr_gate,
        "functional_rtl_modified": False,
        "passed": True,
    }


def restore_probe(ndp_root: Path, evidence_root: Path) -> dict[str, Any]:
    root = ndp_root.resolve()
    evidence = evidence_root.resolve()
    observer = root / "native_return_observer.svh"
    backup = evidence / "native_return_observer.preimage"
    receipt_path = evidence / "tb_probe_install_receipt.json"
    if not backup.is_file() or not receipt_path.is_file() or not observer.is_file():
        raise DequantRuntimeError("TB probe restore inputs are missing")
    receipt = _load_json(receipt_path)
    if _sha256(observer) != receipt.get("installed_sha256"):
        raise DequantRuntimeError("TB probe installed target differs before restore")
    original = backup.read_bytes()
    if _sha256_bytes(original) != receipt.get("preimage_sha256"):
        raise DequantRuntimeError("TB probe backup differs")
    observer.write_bytes(original)
    if _sha256(observer) != receipt.get("preimage_sha256"):
        raise DequantRuntimeError("TB probe byte restore failed")
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
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cfg_root = root / "install/cfg_pkg" / install_name
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
        "installed_runtime": _tree_identity(cfg_root),
        "git": _git_identity(root),
        "rtl_git": _git_identity(root / "rtl"),
    }


def verify_identity(
    paths: list[Path],
    probe_receipt_path: Path,
    precompile_receipt_path: Path,
) -> dict[str, Any]:
    documents = [
        json.loads(path.resolve().read_text(encoding="utf-8")) for path in paths
    ]
    expected_phases = [
        "pre_install",
        "post_probe_install",
        "post_compile",
        "post_run",
        "post_restore",
    ]
    if [item.get("phase") for item in documents] != expected_phases:
        raise DequantRuntimeError("identity phase order differs")
    if any(item.get("schema") != IDENTITY_SCHEMA for item in documents):
        raise DequantRuntimeError("identity schema differs")
    stable_manifest = len(
        {
            item["test_package"]["manifest"]["sha256"]
            for item in documents
        }
    ) == 1
    stable_command = len({item["server_command"] for item in documents}) == 1
    rtl_hashes = [item["rtl_tree"]["tree_sha256"] for item in documents]
    rtl_stable = None not in rtl_hashes and len(set(rtl_hashes)) == 1
    focus_status: dict[str, bool] = {}
    for relative in FOCUS_RTL:
        values = [item["focused_rtl"][relative] for item in documents]
        focus_status[relative] = (
            all(value["exists"] for value in values)
            and len(
                {
                    (value["size_bytes"], value["sha256"])
                    for value in values
                }
            )
            == 1
        )
    probe_receipt = _load_json(probe_receipt_path)
    precompile_receipt = _load_json(precompile_receipt_path)
    precompile_verified = (
        precompile_receipt.get("schema") == PRECOMPILE_RECEIPT_SCHEMA
        and precompile_receipt.get("status")
        == "installed_observer_verified_for_compile"
        and precompile_receipt.get("target_sha256")
        == probe_receipt.get("installed_sha256")
        and precompile_receipt.get("backup_sha256")
        == probe_receipt.get("preimage_sha256")
        and precompile_receipt.get("functional_rtl_modified") is False
        and precompile_receipt.get("passed") is True
    )
    support_status: dict[str, bool] = {}
    for relative in SUPPORT_FILES:
        values = [item["support_files"][relative] for item in documents]
        if relative == "native_return_observer.svh":
            support_status[relative] = (
                values[0]["sha256"] == probe_receipt.get("preimage_sha256")
                and values[1]["sha256"] == probe_receipt.get("installed_sha256")
                and values[2]["sha256"] == probe_receipt.get("preimage_sha256")
                and values[3]["sha256"] == probe_receipt.get("preimage_sha256")
                and values[4]["sha256"] == probe_receipt.get("preimage_sha256")
                and probe_receipt.get("restored") is True
            )
        else:
            support_status[relative] = (
                all(value["exists"] for value in values)
                and len(
                    {
                        (value["size_bytes"], value["sha256"])
                        for value in values
                    }
                )
                == 1
            )
    installed_hashes = [
        item["installed_runtime"]["tree_sha256"] for item in documents
    ]
    install_stable_after_install = (
        installed_hashes[0] is None
        and installed_hashes[1] is not None
        and installed_hashes[1]
        == installed_hashes[2]
        == installed_hashes[3]
        == installed_hashes[4]
    )
    stable = (
        stable_manifest
        and stable_command
        and rtl_stable
        and all(focus_status.values())
        and all(support_status.values())
        and install_stable_after_install
        and precompile_verified
    )
    return {
        "schema": IDENTITY_RECEIPT_SCHEMA,
        "status": (
            "stock_rtl_and_transactional_tb_probe_verified"
            if stable
            else "identity_changed"
        ),
        "candidate_release": False,
        "functional_rtl_mode": "server_original_unmodified",
        "functional_rtl_patch_included": False,
        "identity_phases": expected_phases,
        "manifest_stable": stable_manifest,
        "server_command_stable": stable_command,
        "rtl_tree_stable": rtl_stable,
        "rtl_tree_sha256": rtl_hashes[0],
        "focused_rtl": focus_status,
        "support_files": support_status,
        "installed_namespace_stable_after_install": install_stable_after_install,
        "tb_probe_transactionally_restored": support_status[
            "native_return_observer.svh"
        ],
        "tb_probe_verified_immediately_before_compile": precompile_verified,
        "functional_rtl_unchanged": rtl_stable and all(focus_status.values()),
    }


def _simulation_gate(run_dir: Path, install_name: str, run_status: int) -> dict[str, Any]:
    sim_log = run_dir.resolve() / "sim_results/sim.log"
    text = (
        sim_log.read_text(encoding="utf-8", errors="replace")
        if sim_log.is_file()
        else ""
    )
    expected_sca = f"../install/cfg_pkg/{install_name}/sca_cfg.json"
    expected_sca_d = f"../install/cfg_pkg/{install_name}/sca_cfg_D.json"
    critical_patterns = {
        "fatal": len(re.findall(r"(?i)(?:\\$fatal|\\bfatal\\b)", text)),
        "explicit_error": len(re.findall(r"(?i)(?:\\$error|\\berror:)", text)),
        "timeout": len(re.findall(r"(?i)\\btimeout\\b", text)),
        "oob": len(re.findall(r"(?i)(?:out[- ]of[- ]bounds|\\boob\\b)", text)),
        "cannot_open": len(re.findall(r"(?i)cannot open", text)),
        "apb_slverr": len(re.findall(r"(?i)APB .* SLVERR", text)),
    }
    checks = {
        "process_exit_zero": run_status == 0,
        "sim_log_exists": sim_log.is_file(),
        "sca_echo_exact": text.count(f"Using SCA cfg file: {expected_sca}") == 1,
        "sca_d_echo_exact": text.count(f"Using SCA cfg D file: {expected_sca_d}") == 1,
        "preload_count_exact": bool(
            re.search(r"JSON config:\s*30\s+matrices loaded", text)
        ),
        "formal_dump_count_exact": bool(
            re.search(r"JSON_D config:\s*28\s+matrices dumped", text)
        ),
        "global_start_exact": len(re.findall(r"INFO: slice start", text)) == 1,
        "global_completion_exact": len(
            re.findall(r"INFO: slice completed after\s+\d+\s+cycles", text)
        )
        == 1,
        "natural_finish_exact": text.count("Simulation completed successfully!") == 1,
        "no_critical_markers": sum(critical_patterns.values()) == 0,
    }
    return {
        "status": "pass" if all(checks.values()) else "fail",
        "sim_log_exists": sim_log.is_file(),
        "sim_log_size_bytes": sim_log.stat().st_size if sim_log.is_file() else None,
        "sim_log_sha256": _sha256(sim_log) if sim_log.is_file() else None,
        "critical_marker_counts": critical_patterns,
        **checks,
    }


def _lifecycle_gate(run_dir: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    all_pass = True
    expected_order = ["Start Cfg", "Cfg Finish", "Start Comp", "Comp Finish"]
    for slice_id in range(SLICE_COUNT):
        path = (
            run_dir.resolve()
            / f"sim_results/sem_events/slice{slice_id}/sem_events.log"
        )
        text = (
            path.read_text(encoding="utf-8", errors="replace")
            if path.is_file()
            else ""
        )
        events = [
            event
            for line in text.splitlines()
            for event in expected_order
            if f"| {event} |" in line
        ]
        passed = path.is_file() and events == expected_order
        all_pass = all_pass and passed
        entries.append(
            {
                "slice": slice_id,
                "exists": path.is_file(),
                "events": events,
                "expected_events": expected_order,
                "natural_completion": passed,
                "sha256": _sha256(path) if path.is_file() else None,
                "status": "pass" if passed else "fail",
            }
        )
    return {
        "status": "pass" if all_pass else "fail",
        "slice_count": len(entries),
        "all_28_slices_naturally_completed": all_pass,
        "entries": entries,
    }


def _formal_d_gate(
    run_dir: Path, package_root: Path, install_name: str
) -> dict[str, Any]:
    package = package_root.resolve()
    sca_d = json.loads(
        (package / "workload/runtime/sca_cfg_D.json").read_text(encoding="utf-8")
    )
    entries: list[dict[str, Any]] = []
    all_pass = True
    actual_payloads: dict[int, bytes] = {}
    for slice_id, entry in sorted(_indexed_readbacks(sca_d).items()):
        actual = _inside(run_dir.resolve(), entry["path"])
        golden = (
            package
            / f"workload/golden/slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
        )
        valid = False
        actual_raw = b""
        if actual.is_file():
            try:
                actual_raw = _decode_128bit_text(actual, D_LINES)
                valid = len(actual_raw) == 3008
            except (OSError, DequantRuntimeError):
                valid = False
        golden_raw = _decode_128bit_text(golden, D_LINES)
        full_match = valid and actual_raw == golden_raw
        valid_prefix_match = full_match and actual_raw[:3000] == golden_raw[:3000]
        tail_zero = valid and actual_raw[-8:] == b"\x00" * 8
        passed = full_match and valid_prefix_match and tail_zero
        all_pass = all_pass and passed
        if valid:
            actual_payloads[slice_id] = actual_raw
        entries.append(
            {
                "slice": slice_id,
                "path": entry["path"],
                "base_addr": entry["base_addr"],
                "line_count": D_LINES if valid else None,
                "fp32_word_count": 752 if valid else None,
                "valid_fp32_words": 750 if valid else None,
                "actual_sha256": _sha256(actual) if actual.is_file() else None,
                "golden_sha256": _sha256(golden),
                "first_750_fp32_bit_exact": valid_prefix_match,
                "last_two_fp32_positive_zero": tail_zero,
                "full_3008_bytes_match": full_match,
                "status": "pass" if passed else "fail",
            }
        )
    inverse_contract = _load_json(
        package / "validation/layout_inverse_contract.json"
    )
    inverse_pass = False
    inverse_report: dict[str, Any]
    try:
        inverse = _inverse_layout(actual_payloads, inverse_contract)
        full_golden = package / "workload/golden/full_output_fp32.bin"
        expected_raw = full_golden.read_bytes()
        inverse_pass = (
            len(expected_raw) == 64_000
            and inverse["raw"] == expected_raw
            and inverse["sha256"] == inverse_contract["full_output_raw_sha256"]
        )
        inverse_report = {
            "status": "pass" if inverse_pass else "fail",
            "logical_shape": inverse["logical_shape"],
            "logical_fp32_word_count": inverse["logical_fp32_word_count"],
            "coverage_complete": inverse["coverage_complete"],
            "coverage_unique": inverse["coverage_unique"],
            "actual_inverse_sha256": inverse["sha256"],
            "expected_full_output_sha256": _sha256(full_golden),
            "bit_exact": inverse_pass,
        }
    except (OSError, KeyError, TypeError, ValueError, DequantRuntimeError) as exc:
        inverse_report = {
            "status": "fail",
            "bit_exact": False,
            "error": str(exc),
        }
    all_pass = all_pass and inverse_pass
    return {
        "status": "pass" if all_pass else "fail",
        "slice_count": len(entries),
        "lines_per_slice": D_LINES,
        "total_128bit_lines": SLICE_COUNT * D_LINES,
        "all_28_slices_bit_exact": all_pass,
        "formal_d_addresses_unique": True,
        "formal_d_not_preloaded": True,
        "layout_inverse": inverse_report,
        "entries": entries,
    }


def _observer_temporal_gate(run_dir: Path) -> dict[str, Any]:
    req_re = re.compile(
        r"\|\s*RAW_MSE4_REQ\s*\|.*?"
        r"slice=(\d+).*?ch=(\d+).*?"
        r"domain=post_remap.*?raw_addr=0x([0-9a-fA-FxXzZ]+).*?"
        r"expected_slice_local_base=0x([0-9a-fA-F]+).*?"
        r"expected_global_linear_base=0x([0-9a-fA-F]+)"
    )
    wdata_re = re.compile(
        r"\|\s*RAW_MSE4_WDATA\s*\|.*?"
        r"slice=(\d+).*?ch=(\d+).*?data=0x([0-9a-fA-FxXzZ]+)"
    )
    start_re = re.compile(r"\|\s*STAGE_START\s*\|.*?slice=(\d+)")
    finish_re = re.compile(
        r"\|\s*STAGE_FINISH\s*\|.*?"
        r"slice=(\d+).*?req_total=(\d+).*?wdata_total=(\d+).*?"
        r"req_ch0=(\d+).*?req_ch1=(\d+).*?"
        r"wdata_ch0=(\d+).*?wdata_ch1=(\d+)"
    )
    entries: list[dict[str, Any]] = []
    raw_req_total = 0
    raw_wdata_total = 0
    all_complete = True
    for slice_id in range(SLICE_COUNT):
        path = (
            run_dir.resolve()
            / f"sim_results/dequant_full_e4_probe/slice{slice_id:02d}.log"
        )
        text = (
            path.read_text(encoding="utf-8", errors="replace")
            if path.is_file()
            else ""
        )
        req = [
            match.groups()
            for match in req_re.finditer(text)
            if int(match.group(1)) == slice_id
        ]
        wdata = [
            match.groups()
            for match in wdata_re.finditer(text)
            if int(match.group(1)) == slice_id
        ]
        starts = [
            int(match.group(1))
            for match in start_re.finditer(text)
            if int(match.group(1)) == slice_id
        ]
        finishes = [
            tuple(int(value) for value in match.groups())
            for match in finish_re.finditer(text)
            if int(match.group(1)) == slice_id
        ]
        req_by_channel = [
            sum(1 for item in req if int(item[1]) == channel)
            for channel in range(2)
        ]
        wdata_by_channel = [
            sum(1 for item in wdata if int(item[1]) == channel)
            for channel in range(2)
        ]
        expected_local = 0x2F
        expected_global = (slice_id << 21) + expected_local
        domains_declared = all(
            int(item[3], 16) == expected_local
            and int(item[4], 16) == expected_global
            for item in req
        )
        raw_req_total += len(req)
        raw_wdata_total += len(wdata)
        summary_matches = (
            len(finishes) == 1
            and finishes[0][1] == len(req)
            and finishes[0][2] == len(wdata)
            and list(finishes[0][3:5]) == req_by_channel
            and list(finishes[0][5:7]) == wdata_by_channel
        )
        complete = (
            path.is_file()
            and len(starts) == 1
            and len(req) == D_LINES
            and len(wdata) == D_LINES
            and domains_declared
            and summary_matches
        )
        all_complete = all_complete and complete
        entries.append(
            {
                "slice": slice_id,
                "path": (
                    f"sim_results/dequant_full_e4_probe/"
                    f"slice{slice_id:02d}.log"
                ),
                "exists": path.is_file(),
                "stage_start_count": len(starts),
                "raw_request_count": len(req),
                "raw_wdata_count": len(wdata),
                "raw_request_count_by_channel": req_by_channel,
                "raw_wdata_count_by_channel": wdata_by_channel,
                "finish_summary_count": len(finishes),
                "finish_summary_matches_raw_counts": summary_matches,
                "address_domains": {
                    "slice_local_expected_base_word_128b": f"0x{expected_local:x}",
                    "global_linear_expected_base_word_128b": (
                        f"0x{expected_global:x}"
                    ),
                    "post_remap_observed_but_not_compared_to_linear": True,
                    "frozen_stream_base_word_128b": f"0x{slice_id << 21:x}",
                    "declared_domains_consistent": domains_declared,
                },
                "request_wdata_pairing_attempted": False,
                "accepted_wdata_discarded_due_to_pairing": False,
                "status": "pass" if complete else "evidence_incomplete",
            }
        )
    return {
        "schema": OBSERVER_RECEIPT_SCHEMA,
        "rule_id": "CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001",
        "status": "pass" if all_complete else "OBSERVER_EVIDENCE_INCOMPLETE",
        "orthogonal_to_formal_d_numeric_gate": True,
        "request_wdata_pairing_attempted": False,
        "accepted_wdata_discarded_due_to_pairing": False,
        "post_remap_address_is_not_compared_to_slice_local_or_global_linear": True,
        "raw_request_total": raw_req_total,
        "raw_wdata_total": raw_wdata_total,
        "expected_each": SLICE_COUNT * D_LINES,
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
    evidence = evidence_root.resolve()
    dynamic_run_gate = _dynamic_run_gate(
        package_root.resolve(), install_name
    )
    is_e5 = dynamic_run_gate == "E5"
    identity_path = evidence / "stock_rtl_identity_receipt.json"
    identity = (
        json.loads(identity_path.read_text(encoding="utf-8"))
        if identity_path.is_file()
        else {}
    )
    identity_pass = (
        identity.get("functional_rtl_unchanged") is True
        and identity.get("tb_probe_transactionally_restored") is True
        and identity.get("tb_probe_verified_immediately_before_compile") is True
        and set(identity.get("focused_rtl", {})) == set(FOCUS_RTL)
        and set(identity.get("support_files", {})) == set(SUPPORT_FILES)
        and all(identity.get("focused_rtl", {}).values())
        and all(identity.get("support_files", {}).values())
    )
    simulation = _simulation_gate(run_dir, install_name, run_status)
    lifecycle = _lifecycle_gate(run_dir)
    formal_d = _formal_d_gate(run_dir, package_root, install_name)
    observer = _observer_temporal_gate(run_dir)
    _write_json(evidence / "OBSERVER_TEMPORAL_RECEIPT.json", observer)
    passed = (
        run_status == 0
        and simulation["status"] == "pass"
        and lifecycle["status"] == "pass"
        and formal_d["status"] == "pass"
        and identity_pass
    )
    return {
        "schema": RESULT_SCHEMA,
        "status": (
            f"{dynamic_run_gate}_COMPUTE_PASS_RETURN_PENDING"
            if passed
            else f"{dynamic_run_gate}_FAIL_OR_INCOMPLETE"
        ),
        "classification": (
            "REPEAT_DYNAMIC_RUN" if is_e5 else "FIRST_DYNAMIC_RUN"
        ),
        "dynamic_run_gate": dynamic_run_gate,
        "install_name": install_name,
        "candidate_release": False,
        "release_gate_passed": False,
        "evidence_level": (
            f"{dynamic_run_gate}_SERVER_DYNAMIC"
            if passed
            else "SERVER_INCOMPLETE"
        ),
        "run_exit_status": run_status,
        "semantic_equation": "y=(float32(uint8(x))-60.0f)*scale",
        "scale_fp32_bits": "0x3e01622d",
        "gates": {
            "simulation_and_natural_exit": simulation,
            "all_slice_lifecycle": lifecycle,
            "formal_d_readback": formal_d,
            "observer_temporal_evidence": observer,
            "stock_rtl_identity": {
                "status": "pass" if identity_pass else "fail",
                "functional_rtl_unchanged": identity_pass,
            },
        },
        "remaining_blockers": (
            ["B_DEQUANT_SERVER_E5"]
            if is_e5
            else ["B_DEQUANT_SERVER_E4_E5"]
        ),
        "next_gate": (
            (
                "finalize and verify the allowlist return receipt before "
                f"{dynamic_run_gate} acceptance"
            )
            if passed
            else (
                "classify the earliest failed repeat dynamic E5 gate"
                if is_e5
                else "repair or classify this first dynamic E4 run before E5"
            )
        ),
    }


def _copy_tail(source: Path, destination: Path, limit: int = 200_000) -> None:
    if not source.is_file():
        return
    raw = source.read_bytes()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(raw[-limit:])


def expected_success_return_paths() -> list[str]:
    paths = {
        "RETURN_RECEIPT.json",
        f"package/{MANIFEST_NAME}",
        "config/sca_cfg.json",
        "config/sca_cfg_D.json",
        "logs/compile_driver_tail.log",
        "logs/sim_tail.log",
    }
    paths.update(
        f"evidence/{name}"
        for name in (
            "package_preflight.json",
            "installed_preflight.json",
            "tb_probe_install_receipt.json",
            "tb_probe_precompile_receipt.json",
            "server_identity_pre_install.json",
            "server_identity_post_probe_install.json",
            "server_identity_post_compile.json",
            "server_identity_post_run.json",
            "server_identity_post_restore.json",
            "stock_rtl_identity_receipt.json",
            "OBSERVER_TEMPORAL_RECEIPT.json",
            "SERVER_RESULT_GATE.json",
            "server_command.txt",
            "compile_exit_status.txt",
            "sim_exit_status.txt",
            "run_exit_status.txt",
        )
    )
    for slice_id in range(SLICE_COUNT):
        paths.add(
            f"readback/slice{slice_id:02d}/matrix_D_linearized_128bit.txt"
        )
        paths.add(f"lifecycle/slice{slice_id:02d}/sem_events.log")
        paths.add(f"observer/slice{slice_id:02d}.log")
    return sorted(paths)


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
    dynamic_run_gate = _dynamic_run_gate(package, install_name)
    is_e5 = dynamic_run_gate == "E5"
    evidence = evidence_root.resolve()
    run = run_dir.resolve()
    return_name = f"{install_name}_return"
    staging = root / return_name
    zip_path = root / f"{return_name}.zip"
    sha_path = root / f"{return_name}.zip.sha256"
    for target in (staging, zip_path, sha_path):
        if target.exists():
            raise DequantRuntimeError(f"return target must be fresh: {target}")
    staging.mkdir(parents=True)
    records: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []

    def add(source: Path, relative_value: str, role: str, required: bool = True) -> None:
        relative = _safe_relative(relative_value)
        if set(part.lower() for part in relative.parts) & FORBIDDEN_RETURN_PARTS:
            raise DequantRuntimeError(f"forbidden return directory: {relative}")
        if relative.suffix.lower() in FORBIDDEN_PACKAGE_SUFFIXES:
            raise DequantRuntimeError(f"forbidden return suffix: {relative}")
        if not source.is_file():
            if required:
                missing.append({"path": relative.as_posix(), "role": role})
            return
        if source.stat().st_size > MAX_RETURN_TEXT_BYTES:
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
        "installed_preflight.json",
        "tb_probe_install_receipt.json",
        "tb_probe_precompile_receipt.json",
        "server_identity_pre_install.json",
        "server_identity_post_probe_install.json",
        "server_identity_post_compile.json",
        "server_identity_post_run.json",
        "server_identity_post_restore.json",
        "stock_rtl_identity_receipt.json",
        "OBSERVER_TEMPORAL_RECEIPT.json",
        "server_command.txt",
        "compile_exit_status.txt",
        "sim_exit_status.txt",
        "run_exit_status.txt",
    ):
        add(evidence / name, f"evidence/{name}", "identity_and_gate")
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
    for slice_id in range(SLICE_COUNT):
        add(
            run
            / f"sim_results/formal_readback/slice{slice_id:02d}/"
            "matrix_D_linearized_128bit.txt",
            f"readback/slice{slice_id:02d}/matrix_D_linearized_128bit.txt",
            "formal_d_readback",
        )
        add(
            run / f"sim_results/sem_events/slice{slice_id}/sem_events.log",
            f"lifecycle/slice{slice_id:02d}/sem_events.log",
            "slice_lifecycle",
        )
        add(
            run
            / f"sim_results/dequant_full_e4_probe/slice{slice_id:02d}.log",
            f"observer/slice{slice_id:02d}.log",
            "raw_decoupled_mse4_observer",
        )
    _copy_tail(
        run / "sim_results/compile_driver.log",
        staging / "logs/compile_driver_tail.log",
    )
    _copy_tail(
        run / "sim_results/sim.log",
        staging / "logs/sim_tail.log",
    )
    for name in ("compile_driver_tail.log", "sim_tail.log"):
        path = staging / "logs" / name
        if not path.is_file():
            missing.append({"path": f"logs/{name}", "role": "bounded_log_tail"})
        else:
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
    projected_paths = {item["path"] for item in records}
    projected_paths.update({"evidence/SERVER_RESULT_GATE.json", "RETURN_RECEIPT.json"})
    expected_paths = set(expected_success_return_paths())
    exact_success_set = projected_paths == expected_paths and not missing
    compute_pass = (
        gate.get("status")
        == f"{dynamic_run_gate}_COMPUTE_PASS_RETURN_PENDING"
    )
    final_dynamic_pass = compute_pass and exact_success_set
    gate["gates"] = {
        **dict(gate.get("gates", {})),
        "return_receipt": {
            "status": "pass" if exact_success_set else "fail",
            "allowlist_only": True,
            "expected_exact_set_count": len(expected_paths),
            "projected_exact_set_count": len(projected_paths),
            "exact_set_match": projected_paths == expected_paths,
            "required_missing_before_receipt": list(missing),
        },
    }
    gate["status"] = (
        f"{dynamic_run_gate}_PASS"
        if final_dynamic_pass
        else f"{dynamic_run_gate}_FAIL_OR_INCOMPLETE"
    )
    gate["release_gate_passed"] = False
    gate["remaining_blockers"] = (
        ["B_DEQUANT_SERVER_E5"]
        if is_e5 or final_dynamic_pass
        else ["B_DEQUANT_SERVER_E4_E5"]
    )
    gate["next_gate"] = (
        (
            "independent acceptance of this return may close "
            "B_DEQUANT_SERVER_E5; candidate_release remains false in-package"
            if is_e5
            else "independent acceptance of this return, then fresh-identity E5"
        )
        if final_dynamic_pass
        else (
            "classify the earliest failed repeat dynamic E5 gate"
            if is_e5
            else "classify the earliest failed E4 gate before E5"
        )
    )
    _write_json(gate_path, gate)
    add(gate_path, "evidence/SERVER_RESULT_GATE.json", "identity_and_gate")
    if missing:
        exact_success_set = False
    receipt = {
        "schema": RETURN_SCHEMA,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if exact_success_set else "incomplete",
        "server_result_status": gate.get("status", "missing"),
        "classification": (
            "REPEAT_DYNAMIC_RUN" if is_e5 else "FIRST_DYNAMIC_RUN"
        ),
        "dynamic_run_gate": dynamic_run_gate,
        "install_name": install_name,
        "candidate_release": False,
        "run_exit_status": run_status,
        "server_command": server_command,
        "allowlist_only": True,
        "waveforms_included": False,
        "build_tree_included": False,
        "nested_archive_included": False,
        "required_missing": missing,
        "expected_success_exact_set": expected_success_return_paths(),
        "expected_success_exact_set_count": len(expected_paths),
        "projected_success_exact_set_count": len(projected_paths),
        "expected_success_exact_set_match": exact_success_set,
        "payload_file_count": len(records),
        "payload_size_bytes": sum(item["size_bytes"] for item in records),
        "files": sorted(records, key=lambda item: item["path"]),
    }
    _write_json(staging / "RETURN_RECEIPT.json", receipt)
    extracted = sum(
        path.stat().st_size for path in staging.rglob("*") if path.is_file()
    )
    if extracted > MAX_RETURN_EXTRACTED_BYTES:
        raise DequantRuntimeError("return extracted size exceeds 8 MiB")
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
        raise DequantRuntimeError("return ZIP exceeds 4 MiB")
    digest = _sha256(zip_path)
    sha_path.write_text(
        f"{digest}  {zip_path.name}\n", encoding="ascii", newline="\n"
    )
    return {
        **receipt,
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": digest,
        "sidecar": sha_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    package_preflight = sub.add_parser("preflight-package")
    package_preflight.add_argument("--package-root", type=Path, required=True)
    package_preflight.add_argument("--install-name", required=True)
    package_preflight.add_argument("--output", type=Path, required=True)

    installed_preflight = sub.add_parser("preflight-installed")
    installed_preflight.add_argument("--package-root", type=Path, required=True)
    installed_preflight.add_argument("--ndp-root", type=Path, required=True)
    installed_preflight.add_argument("--install-name", required=True)
    installed_preflight.add_argument("--output", type=Path, required=True)

    capture = sub.add_parser("capture-identity")
    capture.add_argument("--ndp-root", type=Path, required=True)
    capture.add_argument("--package-manifest", type=Path, required=True)
    capture.add_argument("--install-name", required=True)
    capture.add_argument("--phase", required=True)
    capture.add_argument("--server-command", required=True)
    capture.add_argument("--exit-status", type=int)
    capture.add_argument("--output", type=Path, required=True)

    install_probe_parser = sub.add_parser("install-probe")
    install_probe_parser.add_argument("--ndp-root", type=Path, required=True)
    install_probe_parser.add_argument("--package-root", type=Path, required=True)
    install_probe_parser.add_argument("--evidence-root", type=Path, required=True)

    verify_probe_parser = sub.add_parser("verify-probe-installed")
    verify_probe_parser.add_argument("--ndp-root", type=Path, required=True)
    verify_probe_parser.add_argument("--evidence-root", type=Path, required=True)
    verify_probe_parser.add_argument("--output", type=Path, required=True)

    restore_probe_parser = sub.add_parser("restore-probe")
    restore_probe_parser.add_argument("--ndp-root", type=Path, required=True)
    restore_probe_parser.add_argument("--evidence-root", type=Path, required=True)

    verify = sub.add_parser("verify-identity")
    verify.add_argument("--pre-install", type=Path, required=True)
    verify.add_argument("--post-probe-install", type=Path, required=True)
    verify.add_argument("--post-compile", type=Path, required=True)
    verify.add_argument("--post-run", type=Path, required=True)
    verify.add_argument("--post-restore", type=Path, required=True)
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
        elif args.command == "preflight-installed":
            report = preflight_installed(
                args.package_root, args.ndp_root, args.install_name
            )
            _write_json(args.output, report)
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
        elif args.command == "install-probe":
            report = install_probe(
                args.ndp_root, args.package_root, args.evidence_root
            )
        elif args.command == "verify-probe-installed":
            report = verify_probe_installed(args.ndp_root, args.evidence_root)
            _write_json(args.output, report)
        elif args.command == "restore-probe":
            report = restore_probe(args.ndp_root, args.evidence_root)
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
            if (
                not report["functional_rtl_unchanged"]
                or not report["tb_probe_transactionally_restored"]
                or not report["tb_probe_verified_immediately_before_compile"]
            ):
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
            if report["status"].endswith("_FAIL_OR_INCOMPLETE"):
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
            expected_status = (
                f"{report.get('dynamic_run_gate', 'E4')}_PASS"
            )
            if report["server_result_status"] != expected_status:
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 8
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Dequant node0077 runtime failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
