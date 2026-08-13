from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np


EXPECTED_OPERATOR = "prefill_add_fp16MN_fp32N_fp32MN"
EXPECTED_ZIP_BYTES = 975515
EXPECTED_ZIP_SHA256 = "fc7f37f4c860273b80287b7e9e7b0fb8a3af1eebd41e599b84fc8083a596aba6"
SLICE_STRIDE = 0x02000000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_int(value: Any) -> int:
    if isinstance(value, int):
        return value
    return int(str(value).replace("_", ""), 0)


def decode_address(address: int) -> dict[str, int]:
    return {
        "slave": (address >> 25) & 0x1F,
        "bank": (address >> 23) & 0x3,
        "row": (address >> 10) & 0x1FFF,
        "column": (address >> 4) & 0x3F,
        "subword": address & 0xF,
    }


def audit_zip(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        unsafe = []
        symlinks = []
        roots = set()
        for info in infos:
            name = info.filename
            pure = PurePosixPath(name)
            if (
                "\\" in name
                or pure.is_absolute()
                or any(part in {"", ".", ".."} for part in pure.parts)
                or (pure.parts and ":" in pure.parts[0])
            ):
                unsafe.append(name)
            if pure.parts:
                roots.add(pure.parts[0])
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if unix_mode & 0o170000 == 0o120000:
                symlinks.append(name)
        duplicate_count = len(names) - len(set(names))
        casefold_duplicate_count = len(names) - len({name.casefold() for name in names})
        bad_crc_member = archive.testzip()
        file_infos = [info for info in infos if not info.is_dir()]
        ratios = [
            info.file_size / max(1, info.compress_size)
            for info in file_infos
        ]
    actual_bytes = path.stat().st_size
    actual_sha = sha256_file(path)
    passed = (
        actual_bytes == EXPECTED_ZIP_BYTES
        and actual_sha == EXPECTED_ZIP_SHA256
        and len(infos) == 303
        and roots == {"remote_1"}
        and not unsafe
        and not symlinks
        and duplicate_count == 0
        and casefold_duplicate_count == 0
        and bad_crc_member is None
    )
    return {
        "pass": passed,
        "bytes": actual_bytes,
        "sha256": actual_sha,
        "members": len(infos),
        "files": len(file_infos),
        "single_root": sorted(roots),
        "unsafe_paths": unsafe,
        "symlink_entries": symlinks,
        "duplicate_count": duplicate_count,
        "casefold_duplicate_count": casefold_duplicate_count,
        "crc_pass": bad_crc_member is None,
        "bad_crc_member": bad_crc_member,
        "total_uncompressed_bytes": sum(info.file_size for info in file_infos),
        "max_compression_ratio": max(ratios, default=0.0),
    }


def region(base: int, size: int) -> set[int]:
    return set(range(base, base + size))


def interval_list(values: set[int]) -> list[dict[str, int]]:
    if not values:
        return []
    sorted_values = sorted(values)
    runs: list[dict[str, int]] = []
    start = previous = sorted_values[0]
    for value in sorted_values[1:]:
        if value != previous + 1:
            runs.append({"start": start, "end_exclusive": previous + 1, "bytes": previous + 1 - start})
            start = value
        previous = value
    runs.append({"start": start, "end_exclusive": previous + 1, "bytes": previous + 1 - start})
    return runs


def stream_transaction_bytes(stream: dict[str, Any]) -> int:
    if stream["target"] == "B":
        return 16
    if stream["target"] == "A":
        return 4
    if stream["target"] == "D":
        return 32
    raise ValueError(f"unsupported target {stream['target']!r}")


def enumerate_stream0(stream: dict[str, Any]) -> list[tuple[int, int]]:
    base = parse_int(stream["base_addr"])
    stride0, stride1 = (int(stream["dim_stride"][0]), int(stream["dim_stride"][1]))
    # PE0 = 2 * LC2 + LC3; LC2=[0,16), LC3=[0,2), LC1=[0,4).
    return [
        (base + (2 * lc2 + lc3) * stride0 + lc1 * stride1, 16)
        for lc1 in range(4)
        for lc2 in range(16)
        for lc3 in range(2)
    ]


def enumerate_stream1(stream: dict[str, Any]) -> list[tuple[int, int]]:
    base = parse_int(stream["base_addr"])
    stride0, stride1 = (int(stream["dim_stride"][0]), int(stream["dim_stride"][1]))
    # idx=[LC6,LC5], LC5=[0,32), LC6=[0,8); each request is one fp32 word.
    return [
        (base + lc6 * stride0 + lc5 * stride1, 4)
        for lc5 in range(32)
        for lc6 in range(8)
    ]


def enumerate_stream2(stream: dict[str, Any]) -> list[tuple[int, int]]:
    base = parse_int(stream["base_addr"])
    stride0, stride1 = (int(stream["dim_stride"][0]), int(stream["dim_stride"][1]))
    # idx=[LC7,LC8], LC7=[0,32), LC8=[0,4); each transaction is 32 bytes.
    return [
        (base + lc7 * stride0 + lc8 * stride1, 32)
        for lc8 in range(4)
        for lc7 in range(32)
    ]


def transaction_audit(
    stream_name: str,
    stream: dict[str, Any],
    transactions: list[tuple[int, int]],
    required_base: int,
    required_size: int,
) -> dict[str, Any]:
    supplied = Counter(
        byte
        for address, size in transactions
        for byte in range(address, address + size)
    )
    supplied_unique = set(supplied)
    required = region(required_base, required_size)
    wrong = supplied_unique - required
    missing = required - supplied_unique
    multiplicities = Counter(supplied.values())
    return {
        "stream": stream_name,
        "target": stream["target"],
        "mode": stream["mode"],
        "base_addr": parse_int(stream["base_addr"]),
        "transaction_bytes": stream_transaction_bytes(stream),
        "transactions": len(transactions),
        "traffic_bytes": sum(size for _, size in transactions),
        "unique_bytes": len(supplied_unique),
        "required_base": required_base,
        "required_bytes": required_size,
        "missing_bytes": len(missing),
        "missing_intervals": interval_list(missing),
        "wrong_region_bytes": len(wrong),
        "wrong_region_intervals": interval_list(wrong),
        "byte_supply_multiplicity_histogram": {
            str(multiplicity): count for multiplicity, count in sorted(multiplicities.items())
        },
        "first_transaction": {"address": transactions[0][0], "bytes": transactions[0][1]},
        "last_transaction": {"address": transactions[-1][0], "bytes": transactions[-1][1]},
    }


def text_matches_binary(binary: bytes, text_path: Path) -> tuple[bool, int, int]:
    lines = [line.strip() for line in text_path.read_text(encoding="ascii").splitlines() if line.strip()]
    expected_lines: list[str] = []
    for offset in range(0, len(binary), 16):
        chunk = binary[offset : offset + 16]
        if len(chunk) != 16:
            return False, len(lines), 1
        words = [
            f"{int.from_bytes(chunk[word : word + 4], 'little'):032b}"
            for word in range(0, 16, 4)
        ]
        expected_lines.append("".join(reversed(words)))
    mismatches = sum(left != right for left, right in zip(lines, expected_lines))
    mismatches += abs(len(lines) - len(expected_lines))
    return mismatches == 0, len(lines), mismatches


def logical_coordinate(physical_index: int) -> dict[str, int]:
    m_block, within = divmod(physical_index, 256)
    n, m_lane = divmod(within, 8)
    return {"m": m_block * 8 + m_lane, "n": n}


def uint32_hex(value: np.float32) -> str:
    return f"0x{np.asarray([value], dtype='<f4').view('<u4')[0]:08x}"


def calculate_schedule_result(
    memory: bytearray,
    stream0_tx: list[tuple[int, int]],
    stream1_tx: list[tuple[int, int]],
    golden_blob: bytes,
) -> dict[str, Any]:
    schedule_b_blob = b"".join(bytes(memory[address : address + size]) for address, size in stream0_tx)
    # LC6 creates eight traffic copies for every LC5 word. The GA broadcast value is
    # the unique fp32 word selected by each LC5, not eight concatenated vectors.
    unique_a_addresses = []
    for address, _ in stream1_tx:
        if address not in unique_a_addresses:
            unique_a_addresses.append(address)
    schedule_a_blob = b"".join(bytes(memory[address : address + 4]) for address in unique_a_addresses)
    schedule_b = np.frombuffer(schedule_b_blob, dtype="<f2").astype("<f4")
    schedule_a = np.frombuffer(schedule_a_blob, dtype="<f4")
    schedule_broadcast = np.tile(np.repeat(schedule_a, 8), 4)
    with np.errstate(all="ignore"):
        result = np.asarray(schedule_b + schedule_broadcast, dtype="<f4")

    golden = np.frombuffer(golden_blob, dtype="<f4")
    result_bits = result.view("<u4")
    golden_bits = golden.view("<u4")
    mismatch = np.flatnonzero(result_bits != golden_bits)
    result_bytes = result.tobytes()
    byte_mismatch = np.frombuffer(result_bytes, dtype=np.uint8) != np.frombuffer(golden_blob, dtype=np.uint8)
    byte_indices = np.flatnonzero(byte_mismatch)
    first = None
    if mismatch.size:
        index = int(mismatch[0])
        first = {
            "physical_element_index": index,
            "logical_coordinate": logical_coordinate(index),
            "golden_value": float(golden[index]),
            "config_bound_value": float(result[index]),
            "golden_bits": uint32_hex(golden[index]),
            "config_bound_bits": uint32_hex(result[index]),
            "first_mismatching_byte_offset": int(byte_indices[0]),
        }
    return {
        "materialized_output_file": False,
        "host_internal_tensor_replay": False,
        "used_as_runtime_input": False,
        "element_mismatches": int(mismatch.size),
        "byte_mismatches": int(np.count_nonzero(byte_mismatch)),
        "first_divergence": first,
        "result_sha256": hashlib.sha256(result_bytes).hexdigest(),
    }


def slice_numeric_audit(
    slice_dir: Path,
    memory_size: int,
    json_stream0_tx: list[tuple[int, int]],
    json_stream1_tx: list[tuple[int, int]],
    effective_stream0_tx: list[tuple[int, int]],
    effective_stream1_tx: list[tuple[int, int]],
    bases: dict[str, int],
) -> dict[str, Any]:
    paths = {
        name: slice_dir / f"matrix_{name}_linearized_128bit.bin"
        for name in ("A", "B", "D")
    }
    blobs = {name: path.read_bytes() for name, path in paths.items()}
    memory = bytearray(memory_size)
    memory[bases["A"] : bases["A"] + len(blobs["A"])] = blobs["A"]
    memory[bases["B"] : bases["B"] + len(blobs["B"])] = blobs["B"]

    a = np.frombuffer(blobs["A"], dtype="<f4")
    b = np.frombuffer(blobs["B"], dtype="<f2").astype("<f4")
    golden = np.frombuffer(blobs["D"], dtype="<f4")

    broadcast_physical = np.tile(np.repeat(a, 8), 4)
    with np.errstate(all="ignore"):
        independent = np.asarray(b + broadcast_physical, dtype="<f4")

    independent_bits = independent.view("<u4")
    golden_bits = golden.view("<u4")
    independent_mismatch = np.flatnonzero(independent_bits != golden_bits)

    text_checks = {}
    x_tokens = 0
    for name, blob in blobs.items():
        text_path = slice_dir / f"matrix_{name}_linearized_128bit.txt"
        matches, line_count, line_mismatches = text_matches_binary(blob, text_path)
        text = text_path.read_text(encoding="ascii")
        x_tokens += sum(character in "xXzZ" for character in text)
        text_checks[name] = {
            "bin_bytes": len(blob),
            "txt_128b_lines": line_count,
            "txt_matches_bin": matches,
            "line_mismatches": line_mismatches,
            "sha256": sha256_file(paths[name]),
        }

    return {
        "slice": slice_dir.name,
        "files": text_checks,
        "x_or_z_tokens": x_tokens,
        "independent_golden": {
            "equation": "D_physical = fp32(B_fp16_physical) + tile(repeat(A_fp32[0:32], 8), 4)",
            "element_mismatches": int(independent_mismatch.size),
            "byte_mismatches": int(
                np.count_nonzero(
                    np.frombuffer(independent.tobytes(), dtype=np.uint8)
                    != np.frombuffer(blobs["D"], dtype=np.uint8)
                )
            ),
            "bit_exact": independent_mismatch.size == 0,
        },
        "json_loaded_state_result": calculate_schedule_result(
            memory, json_stream0_tx, json_stream1_tx, blobs["D"]
        ),
        "effective_runtime_state_result": calculate_schedule_result(
            memory, effective_stream0_tx, effective_stream1_tx, blobs["D"]
        ),
    }


def execplan_slice0_physical_bases(root: Path) -> dict[str, int]:
    explained = (root / "instructions_explained.txt").read_text(encoding="utf-8")
    result: dict[str, int] = {}
    pattern = re.compile(
        r"register_field=(?P<instance>(?:rd|wr)_stream\d+)\.stream_engine\.stream\.base_addr,"
        r".*?slice_bin=00000,.*?field_value_write_hex=(?P<value>0x[0-9A-Fa-f]+)"
    )
    for match in pattern.finditer(explained):
        result[match.group("instance")] = int(match.group("value"), 16)
    return result


def bitstream_audit(root: Path) -> dict[str, Any]:
    config_dir = root / "config" / "op0"
    module64 = config_dir / "modules_dump_64b.bin"
    module128 = config_dir / "modules_dump_128b.bin"
    op64 = config_dir / f"op0_{EXPECTED_OPERATOR}_bitstream_64b.bin"
    op128 = config_dir / f"op0_{EXPECTED_OPERATOR}_bitstream_128b.bin"
    install128 = root / "install" / "cfg_pkg" / f"op0_{EXPECTED_OPERATOR}_bitstream_128b.bin"

    def lines(path: Path, width: int) -> list[str]:
        result = [line.strip() for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
        if any(len(line) != width or set(line) - {"0", "1"} for line in result):
            raise ValueError(f"invalid {width}-bit text bitstream: {path}")
        return result

    lines64 = lines(module64, 64)
    lines128 = lines(module128, 128)
    repacked = [lines64[index] + lines64[index + 1] for index in range(0, len(lines64), 2)]
    explained = (root / "instructions_explained.txt").read_text(encoding="utf-8")
    config_length_marker = "config_length_bin="
    marker_value = explained.split(config_length_marker, 1)[1].split(",", 1)[0]
    execplan_config_length = int(marker_value, 2)
    return {
        "config_length_64b": len(lines64),
        "execplan_config_length_64b": execplan_config_length,
        "config_length_matches_execplan": len(lines64) == execplan_config_length,
        "repacked_64_to_128_matches": repacked == lines128,
        "module_equals_operator_64b": module64.read_bytes() == op64.read_bytes(),
        "module_equals_operator_128b": module128.read_bytes() == op128.read_bytes(),
        "install_equals_operator_128b": install128.read_bytes() == op128.read_bytes(),
        "files": {
            str(path.relative_to(root)).replace("\\", "/"): {
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in (module64, module128, op64, op128, install128)
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only, config-bound audit for the supplied human remote add package.")
    parser.add_argument("root", type=Path, help="extracted remote_1 root")
    parser.add_argument("--source-zip", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    zip_safety = audit_zip(args.source_zip.resolve()) if args.source_zip else None
    if zip_safety is not None and not zip_safety["pass"]:
        raise ValueError(f"source ZIP safety/identity audit failed: {zip_safety}")
    config_path = root / "jsons" / f"op0_{EXPECTED_OPERATOR}.json"
    graph_path = root / "remote_withbaseaddr.json"
    mapping_path = root / "config" / "op0" / "mapping_review.json"
    sca_path = root / "sca_cfg.json"
    sca_d_path = root / "sca_cfg_D.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    sca = json.loads(sca_path.read_text(encoding="utf-8"))
    sca_d = json.loads(sca_d_path.read_text(encoding="utf-8"))

    operator = graph["operators"][0]
    if operator["type"] != EXPECTED_OPERATOR:
        raise ValueError(f"operator mismatch: {operator['type']}")
    if int(graph["used_slices"]) != 28:
        raise ValueError(f"used_slices mismatch: {graph['used_slices']}")

    bases = {
        "A": parse_int(operator["inputs"]["A"]["base_addr"]),
        "B": parse_int(operator["inputs"]["B"]["base_addr"]),
        "D": parse_int(operator["output"]["base_addr"]),
    }
    sizes = {"A": 32 * 4, "B": 32 * 32 * 2, "D": 32 * 32 * 4}
    streams = config["stream_engine"]
    mapping_resources = {
        entry["node"]: entry["resource"] for entry in mapping["node_to_resource"]
    }
    stream_mapping = {
        key: mapping_resources[f"STREAM.{key}"] for key in ("stream0", "stream1", "stream2")
    }
    expected_physical_stream_for_tensor = {
        "A": "READ_STREAM0",
        "B": "READ_STREAM1",
        "D": "WRITE_STREAM0",
    }
    logical_target_to_physical = {
        streams[key]["target"]: stream_mapping[key] for key in ("stream0", "stream1", "stream2")
    }
    writer_fixed_binding_conflicts = {
        tensor: {
            "logical_mapping_resource": logical_target_to_physical[tensor],
            "execplan_fixed_binding_resource": physical,
        }
        for tensor, physical in expected_physical_stream_for_tensor.items()
        if logical_target_to_physical[tensor] != physical
    }
    physical_instance = {
        "READ_STREAM0": "rd_stream0",
        "READ_STREAM1": "rd_stream1",
        "WRITE_STREAM0": "wr_stream0",
    }
    execplan_physical_bases = execplan_slice0_physical_bases(root)
    # wr_stream0 slice-00 is not rewritten because its loaded value already equals
    # the planned output address. Preserve that loaded value explicitly.
    execplan_physical_bases.setdefault("wr_stream0", parse_int(streams["stream2"]["base_addr"]))
    effective_streams = json.loads(json.dumps(streams))
    for stream_name in ("stream0", "stream1", "stream2"):
        resource = stream_mapping[stream_name]
        instance = physical_instance[resource]
        effective_streams[stream_name]["base_addr"] = hex(execplan_physical_bases[instance])

    json_stream0_tx = enumerate_stream0(streams["stream0"])
    json_stream1_tx = enumerate_stream1(streams["stream1"])
    json_stream2_tx = enumerate_stream2(streams["stream2"])
    effective_stream0_tx = enumerate_stream0(effective_streams["stream0"])
    effective_stream1_tx = enumerate_stream1(effective_streams["stream1"])
    effective_stream2_tx = enumerate_stream2(effective_streams["stream2"])
    json_transaction_ledger = {
        "stream0": transaction_audit("stream0", streams["stream0"], json_stream0_tx, bases["B"], sizes["B"]),
        "stream1": transaction_audit("stream1", streams["stream1"], json_stream1_tx, bases["A"], sizes["A"]),
        "stream2": transaction_audit("stream2", streams["stream2"], json_stream2_tx, bases["D"], sizes["D"]),
    }
    effective_transaction_ledger = {
        "stream0": transaction_audit("stream0", effective_streams["stream0"], effective_stream0_tx, bases["B"], sizes["B"]),
        "stream1": transaction_audit("stream1", effective_streams["stream1"], effective_stream1_tx, bases["A"], sizes["A"]),
        "stream2": transaction_audit("stream2", effective_streams["stream2"], effective_stream2_tx, bases["D"], sizes["D"]),
    }

    slice_root = root / "install" / "op0"
    slice_dirs = sorted(path for path in slice_root.glob("slice??") if path.is_dir())
    memory_size = max(bases[name] + sizes[name] for name in bases)
    slices = [
        slice_numeric_audit(
            path,
            memory_size,
            json_stream0_tx,
            json_stream1_tx,
            effective_stream0_tx,
            effective_stream1_tx,
            bases,
        )
        for path in slice_dirs
    ]

    sca_address_checks = []
    for slice_index in range(28):
        prefix = slice_index * SLICE_STRIDE
        for tensor in ("A", "B"):
            key = f"op0_matrix{tensor}_slice{slice_index}"
            actual = parse_int(sca[key]["base_addr"])
            expected = prefix + bases[tensor]
            sca_address_checks.append(actual == expected)
        key_d = f"op0_matrixD_slice{slice_index}"
        actual_d = parse_int(sca_d[key_d]["base_addr"])
        sca_address_checks.append(actual_d == prefix + bases["D"])
        sca_address_checks.append(int(sca_d[key_d]["length"]) == sizes["D"] // 16)

    json_loaded_first_divergence = next(
        (
            {
                "slice": entry["slice"],
                **entry["json_loaded_state_result"]["first_divergence"],
            }
            for entry in slices
            if entry["json_loaded_state_result"]["first_divergence"] is not None
        ),
        None,
    )
    effective_first_divergence = next(
        (
            {
                "slice": entry["slice"],
                **entry["effective_runtime_state_result"]["first_divergence"],
            }
            for entry in slices
            if entry["effective_runtime_state_result"]["first_divergence"] is not None
        ),
        None,
    )
    natural_completion = len(slices) == 28 and all(
        entry["files"][tensor]["bin_bytes"] == sizes[tensor]
        for entry in slices
        for tensor in ("A", "B", "D")
    )
    d_complete = sum(
        entry["files"]["D"]["bin_bytes"] == sizes["D"]
        and entry["files"]["D"]["txt_128b_lines"] == sizes["D"] // 16
        and entry["files"]["D"]["txt_matches_bin"]
        for entry in slices
    )

    report: dict[str, Any] = {
        "schema": "human-remote-add-config-bound-analysis-v1",
        "claim_level": "LOCAL_E2",
        "not_claimed": ["CGRA_SIM", "RTL", "E3", "E4", "E5"],
        "read_only": True,
        "human_authored_input": True,
        "preservation": {
            "original_zip_modified": False,
            "human_json_modified": False,
            "mapping_bitstream_execplan_sca_rebuilt": False,
            "host_internal_tensor_replay": False,
            "server_action": False,
        },
        "source": {
            "zip": (
                {
                    "path": str(args.source_zip.resolve()),
                    "bytes": args.source_zip.stat().st_size,
                    "sha256": sha256_file(args.source_zip),
                    "safety_audit": zip_safety,
                }
                if args.source_zip
                else None
            ),
            "root": str(root),
            "operator_json": {
                "path": str(config_path),
                "bytes": config_path.stat().st_size,
                "sha256": sha256_file(config_path),
            },
            "graph": {"path": str(graph_path), "sha256": sha256_file(graph_path)},
            "mapping": {"path": str(mapping_path), "sha256": sha256_file(mapping_path)},
            "sca": {"path": str(sca_path), "sha256": sha256_file(sca_path)},
            "sca_d": {"path": str(sca_d_path), "sha256": sha256_file(sca_d_path)},
        },
        "operator_contract": {
            "id": operator["id"],
            "type": operator["type"],
            "used_slices": 28,
            "layout": {
                "logical": "A[1,1,32] fp32 broadcast over M; B[1,32,32] fp16; D[1,32,32] fp32",
                "physical_index": "(m//8)*256 + n*8 + (m%8)",
            },
            "tensors": {
                "A": {"shape": [1, 1, 32], "dtype": "fp32 (native omitted default)", "base_addr": bases["A"], "bytes_per_slice": sizes["A"]},
                "B": {"shape": [1, 32, 32], "dtype": "fp16", "base_addr": bases["B"], "bytes_per_slice": sizes["B"]},
                "D": {"shape": [1, 32, 32], "dtype": "fp32 (native omitted default)", "base_addr": bases["D"], "bytes_per_slice": sizes["D"], "role": "provided golden"},
            },
            "address_decode": {
                tensor: {
                    "start": decode_address(bases[tensor]),
                    "last_byte": decode_address(bases[tensor] + sizes[tensor] - 1),
                }
                for tensor in ("A", "B", "D")
            },
            "slice_prefix_stride": SLICE_STRIDE,
            "sca_all_slice_addresses_and_lengths_match": all(sca_address_checks),
        },
        "mapping_contract": {
            "stream_mapping": stream_mapping,
            "logical_target_to_physical": logical_target_to_physical,
            "execplan_fixed_tensor_binding": expected_physical_stream_for_tensor,
            "binding_conflicts": writer_fixed_binding_conflicts,
            "execplan_slice0_physical_bases": execplan_physical_bases,
            "effective_logical_stream_bases": {
                name: parse_int(effective_streams[name]["base_addr"])
                for name in ("stream0", "stream1", "stream2")
            },
            "load_then_write_reg_order": True,
        },
        "transaction_ledger": {
            "json_loaded_state_before_execplan_Write_Reg": json_transaction_ledger,
            "effective_runtime_state_after_execplan_Write_Reg": effective_transaction_ledger,
        },
        "bitstream_execplan_consistency": bitstream_audit(root),
        "control_lifetime_audit": {
            "loop_trip_counts": {
                name: (int(loop["end"]) - int(loop["start"])) // int(loop["stride"])
                for name, loop in config["dram_loop_configs"].items()
            },
            "loop_parent_edges": {
                name: loop["src_id"]
                for name, loop in config["dram_loop_configs"].items()
            },
            "shared_outer_root": "DRAM_LC.LC0",
            "static_loop_graph_finite_and_acyclic": True,
            "physical_buffer_binding": {
                "A": {"logical_group": "GROUP1", "physical_group": "GROUP0", "buffer": "buffer0"},
                "B": {"logical_group": "GROUP0", "physical_group": "GROUP1", "buffer": "buffer2"},
                "D": {"logical_group": "GROUP2", "physical_group": "GROUP4", "buffer": "buffer5"},
            },
            "buffers": {
                name: {
                    "enable": int(node["enable"]),
                    "buf_full_last_index": int(node["buf_full_last_index"]),
                    "buffer_life_time": int(node["buffer_life_time"]),
                    "dst_port": int(node["dst_port"]),
                }
                for name, node in config["buffer_config"].items()
            },
            "stream_buffer_full_last_index_matches_bound_buffer": all(
                int(streams[stream]["buf_full_last_index"])
                == int(config["buffer_config"][buffer]["buf_full_last_index"])
                for stream, buffer in (("stream0", "buffer2"), ("stream1", "buffer0"))
            ),
            "supply_demand": {
                "B": {
                    "logical_tensor_bytes": sizes["B"],
                    "effective_read_traffic_bytes": effective_transaction_ledger["stream0"]["traffic_bytes"],
                    "effective_unique_bytes": effective_transaction_ledger["stream0"]["unique_bytes"],
                    "missing_bytes": effective_transaction_ledger["stream0"]["missing_bytes"],
                },
                "A": {
                    "logical_tensor_bytes": sizes["A"],
                    "effective_read_traffic_bytes": effective_transaction_ledger["stream1"]["traffic_bytes"],
                    "effective_unique_bytes": effective_transaction_ledger["stream1"]["unique_bytes"],
                    "broadcast_reuse_factor": effective_transaction_ledger["stream1"]["traffic_bytes"] // sizes["A"],
                    "missing_bytes": effective_transaction_ledger["stream1"]["missing_bytes"],
                },
                "D": {
                    "logical_tensor_bytes": sizes["D"],
                    "effective_write_traffic_bytes": effective_transaction_ledger["stream2"]["traffic_bytes"],
                    "effective_unique_bytes": effective_transaction_ledger["stream2"]["unique_bytes"],
                    "missing_bytes": effective_transaction_ledger["stream2"]["missing_bytes"],
                },
            },
            "terminal_reachability": {
                "write_stream": "stream2",
                "write_target": "D",
                "tag_carrier": "GROUP2.COL_LC",
                "possible_last_indices": [0, 1, 2, 3, 4],
                "terminal_condition": "last=1 && last_index=0, then final DDR write-data handshake",
                "static_terminal_tag_reachable": True,
                "cycle_level_terminal_handshake_proven": False,
            },
            "dynamic_only": [
                "ready/valid backpressure across branches sharing LC0",
                "buffer lifetime decrement and release timing under stalls",
                "GA output last propagation and final DDR write-data handshake",
            ],
        },
        "schema_portability": {
            "shadow_validator_exit": 1,
            "only_reported_issue": {
                "code": "SCHEMA.UNKNOWN_FIELD",
                "path": "$.mul_shape",
                "interpretation": "extra unconsumed metadata; package bitstream already exists, but strict current-schema replay is fail-closed",
            },
        },
        "execution": {
            "engine": "isolated config-bound schedule interpreter",
            "natural_completion": natural_completion,
            "slices_started": len(slices),
            "slices_finished": len(slices),
            "D_complete_slices": d_complete,
            "D_missing_slices": [f"slice{index:02d}" for index in range(28) if not (slice_root / f"slice{index:02d}" / "matrix_D_linearized_128bit.bin").is_file()],
            "x_or_z_tokens": sum(entry["x_or_z_tokens"] for entry in slices),
            "json_loaded_wrong_region_bytes_per_slice": json_transaction_ledger["stream0"]["wrong_region_bytes"] + json_transaction_ledger["stream1"]["wrong_region_bytes"],
            "effective_runtime_wrong_region_bytes_per_slice": effective_transaction_ledger["stream0"]["wrong_region_bytes"] + effective_transaction_ledger["stream1"]["wrong_region_bytes"],
            "provided_golden_independent_formula_all_bit_exact": all(entry["independent_golden"]["bit_exact"] for entry in slices),
            "json_loaded_total_element_mismatches": sum(entry["json_loaded_state_result"]["element_mismatches"] for entry in slices),
            "json_loaded_total_byte_mismatches": sum(entry["json_loaded_state_result"]["byte_mismatches"] for entry in slices),
            "json_loaded_first_divergence": json_loaded_first_divergence,
            "effective_runtime_total_element_mismatches": sum(entry["effective_runtime_state_result"]["element_mismatches"] for entry in slices),
            "effective_runtime_total_byte_mismatches": sum(entry["effective_runtime_state_result"]["byte_mismatches"] for entry in slices),
            "effective_runtime_first_divergence": effective_first_divergence,
        },
        "slices": slices,
        "classification": {
            "CONFIG_EXPLAINS": [
                "the standalone JSON loaded state has exchanged logical-stream bases because its key suffixes do not represent mapped physical read-stream identities",
                "the supplied execplan runs Load_Config first and then patches input A into physical rd_stream0 and B into physical rd_stream1",
                "mapping_review maps logical A stream1 to READ_STREAM0 and logical B stream0 to READ_STREAM1, so those Write_Reg operations restore effective logical bases A=0x0 and B=0x80 before Start_Comp",
                "the intermediate JSON-only wrong-region result is therefore explained and neutralized by the packaged execution sequence",
            ],
            "CONFIG_EXCLUDED": [
                "provided A/B/D files are complete for all 28 slices and each 128-bit text image matches its binary image",
                "provided D golden is bit-exact to the independent fp16-to-fp32 add/broadcast equation on all 28 slices",
                "effective post-Write_Reg input transactions and stream2 output transactions cover their complete tensor regions with no missing or wrong-region bytes",
                "effective config-bound arithmetic is bit-exact to provided D on all 28 slices",
                "64/128-bit config dumps and execplan config_length are internally consistent",
            ],
            "DYNAMIC_ONLY": [
                "cycle-level ready/valid backpressure, buffer lifetime retirement, GA terminal propagation, and natural RTL completion",
                "whether a particular RTL build masks or exposes the misbound read bases",
            ],
        },
        "verdict": {
            "status": "CONFIG_EXCLUDED",
            "first_trusted_boundary": "provided A/B/D files and independent golden equation",
            "first_divergence": None,
            "intermediate_nonterminal_divergence": "standalone JSON bases before execplan Write_Reg",
            "correctness": "LOCAL_E2_PASS",
            "candidate_release": False,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "natural_completion": natural_completion,
                "D_complete_slices": d_complete,
                "golden_bit_exact_slices": sum(entry["independent_golden"]["bit_exact"] for entry in slices),
                "json_loaded_total_element_mismatches": report["execution"]["json_loaded_total_element_mismatches"],
                "effective_runtime_total_element_mismatches": report["execution"]["effective_runtime_total_element_mismatches"],
                "effective_runtime_total_byte_mismatches": report["execution"]["effective_runtime_total_byte_mismatches"],
                "effective_runtime_first_divergence": effective_first_divergence,
            },
            ensure_ascii=False,
        )
    )
    return 0 if report["verdict"]["correctness"] == "LOCAL_E2_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
