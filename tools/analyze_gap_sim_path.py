#!/usr/bin/env python3
"""Locate the first observable GAP numeric divergence in an RTL return.

The analyzer deliberately stops at observable boundaries:

1. JSON-derived MSE0 physical read addresses versus RTL request handshakes.
2. Returned DDR words versus the words selected by the actual handshakes.
3. MSE4 write addresses/data versus the package D golden.

It does not infer that a later stage is correct when an earlier boundary has
already diverged.  This makes the result suitable for deciding which TB probes
are needed on the next server run.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REQUEST_RE = re.compile(
    r"^\s*(?P<time>\d+)\s+\|\s*(?P<channel>\d+)\s+\|"
    r"\s*0x(?P<address>[0-9a-fA-F]+)"
)
READ_RE = re.compile(
    r"^\s*(?P<return_time>\d+)\s+\|\s*(?P<return_channel>\d+)\s+\|"
    r"\s*(?P<issue_channel>\d+)\s+\|\s*(?P<issue_time>\d+)\s+\|"
    r"\s*0x(?P<data>[0-9a-fA-F]+)"
)
WRITE_RE = re.compile(
    r"^\s*(?P<time>\d+)\s+\|\s*(?P<channel>\d+)\s+\|"
    r"\s*0x(?P<data>[0-9a-fA-F]+)"
)


class GapPathAnalysisError(RuntimeError):
    """Raised when the supplied return/package is not structurally usable."""


@dataclass(frozen=True)
class Request:
    time: int
    channel: int
    address: int


@dataclass(frozen=True)
class ReadReturn:
    return_time: int
    return_channel: int
    issue_channel: int
    issue_time: int
    data: int


@dataclass(frozen=True)
class WriteData:
    time: int
    channel: int
    data: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_records(path: Path, pattern: re.Pattern[str], record_type):
    if not path.is_file():
        raise GapPathAnalysisError(f"missing log: {path}")
    records = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.match(line)
        if match:
            values = {key: int(value, 16 if key in {"address", "data"} else 10)
                      for key, value in match.groupdict().items()}
            records.append(record_type(**values))
    if not records:
        raise GapPathAnalysisError(f"no records parsed from: {path}")
    return records


def parse_requests(path: Path) -> list[Request]:
    return _parse_records(path, REQUEST_RE, Request)


def parse_read_returns(path: Path) -> list[ReadReturn]:
    return _parse_records(path, READ_RE, ReadReturn)


def parse_write_data(path: Path) -> list[WriteData]:
    return _parse_records(path, WRITE_RE, WriteData)


def read_128bit_words(path: Path) -> list[int]:
    if not path.is_file():
        raise GapPathAnalysisError(f"missing matrix text: {path}")
    words = []
    for line_number, raw in enumerate(
        path.read_text(encoding="ascii").splitlines(), start=1
    ):
        line = raw.strip()
        if len(line) != 128 or set(line) - {"0", "1"}:
            raise GapPathAnalysisError(
                f"invalid 128-bit line {line_number}: {path}"
            )
        words.append(int(line, 2))
    return words


def expected_read_addresses(
    *,
    outer_count: int,
    outer_stride_bytes: int,
    inner_start: int,
    inner_end: int,
    inner_stride: int,
    inner_dim_stride_bytes: int,
    transaction_bytes: int,
    physical_word_bytes: int = 16,
) -> tuple[list[int], list[tuple[int, int]]]:
    """Split each configured transaction at physical-word boundaries."""

    result: list[int] = []
    outer_ranges: list[tuple[int, int]] = []
    for outer in range(outer_count):
        start = len(result)
        for inner in range(inner_start, inner_end, inner_stride):
            byte_address = (
                outer * outer_stride_bytes + inner * inner_dim_stride_bytes
            )
            remaining = transaction_bytes
            while remaining:
                transfer = min(
                    physical_word_bytes - byte_address % physical_word_bytes,
                    remaining,
                )
                result.append(byte_address // physical_word_bytes)
                byte_address += transfer
                remaining -= transfer
        outer_ranges.append((start, len(result)))
    return result, outer_ranges


def associate_returns(
    requests: Iterable[Request], returns: Iterable[ReadReturn]
) -> tuple[list[tuple[int, int]], int, int]:
    """Associate returns with requests using the physical return channel.

    The server TB's ``IssueCh``/``IssueTime`` columns are reconstructed with
    one global FIFO spanning both request channels.  The hardware return data,
    however, is ordered independently within each physical channel.  Using
    the reconstructed columns swaps otherwise-correct payloads whenever the
    two return channels complete in a different order.
    """

    pending: dict[int, collections.deque[int]] = collections.defaultdict(
        collections.deque
    )
    for request in requests:
        pending[request.channel].append(request.address)
    pairs: list[tuple[int, int]] = []
    unmatched = 0
    for returned in returns:
        channel = returned.return_channel
        if not pending[channel]:
            unmatched += 1
            continue
        pairs.append((pending[channel].popleft(), returned.data))
    still_pending = sum(len(queue) for queue in pending.values())
    return pairs, unmatched, still_pending


def decode_int32_write_stream(records: list[WriteData]) -> list[int]:
    values: list[int] = []
    for record in records:
        payload = record.data.to_bytes(16, byteorder="little")
        values.extend(struct.unpack("<4i", payload))
    return values


def decode_int32_words(words: Iterable[int]) -> list[int]:
    values: list[int] = []
    for word in words:
        values.extend(struct.unpack("<4i", word.to_bytes(16, byteorder="little")))
    return values


def analyze(
    *,
    sim_root: Path,
    package_root: Path,
    slice_id: int = 0,
) -> dict:
    local = sim_root / "local" / f"slice{slice_id}"
    installed = package_root / "install" / "op0" / f"slice{slice_id:02d}"
    request_path = local / "local_mse0_req.log"
    read_path = local / "local_mse0_rdata.log"
    write_request_path = local / "local_mse4_req.log"
    write_data_path = local / "local_mse4_wdata.log"
    matrix_a_path = installed / "matrix_A_linearized_128bit.txt"
    matrix_d_path = installed / "matrix_D_linearized_128bit.txt"

    read_requests = parse_requests(request_path)
    read_returns = parse_read_returns(read_path)
    write_requests = parse_requests(write_request_path)
    write_data = parse_write_data(write_data_path)
    matrix_a = read_128bit_words(matrix_a_path)
    matrix_d = read_128bit_words(matrix_d_path)

    expected_addresses, outer_ranges = expected_read_addresses(
        outer_count=256,
        outer_stride_bytes=392,
        inner_start=0,
        inner_end=56,
        inner_stride=4,
        inner_dim_stride_bytes=8,
        transaction_bytes=32,
    )
    actual_addresses = [request.address for request in read_requests]
    expected_address_counter = collections.Counter(expected_addresses)
    actual_address_counter = collections.Counter(actual_addresses)
    missing_address_occurrences = sum(
        (expected_address_counter - actual_address_counter).values()
    )
    extra_address_occurrences = sum(
        (actual_address_counter - expected_address_counter).values()
    )
    address_delta_histogram = collections.Counter(
        actual - expected
        for actual, expected in zip(actual_addresses, expected_addresses)
    )
    address_mismatch_positions = [
        index
        for index, (actual, expected) in enumerate(
            zip(actual_addresses, expected_addresses)
        )
        if actual != expected
    ]
    address_length_match = len(actual_addresses) == len(expected_addresses)
    exact_outer_blocks = [
        outer
        for outer, (start, end) in enumerate(outer_ranges)
        if actual_addresses[start:end] == expected_addresses[start:end]
    ]

    associated, unmatched_returns, pending_requests = associate_returns(
        read_requests, read_returns
    )
    exact_return_mismatch_positions = [
        index
        for index, (address, data) in enumerate(associated)
        if address >= len(matrix_a) or matrix_a[address] != data
    ]
    expected_return_multiset = collections.Counter(
        matrix_a[address]
        for address in actual_addresses
        if address < len(matrix_a)
    )
    actual_return_multiset = collections.Counter(data for _, data in associated)
    return_missing = sum((expected_return_multiset - actual_return_multiset).values())
    return_extra = sum((actual_return_multiset - expected_return_multiset).values())

    actual_output = decode_int32_write_stream(write_data)
    golden_output = decode_int32_words(matrix_d)
    numeric_count = min(len(actual_output), len(golden_output))
    numeric_mismatch_positions = [
        index
        for index in range(numeric_count)
        if actual_output[index] != golden_output[index]
    ]

    write_addresses = [request.address for request in write_requests]
    unique_write_addresses = sorted(set(write_addresses))
    write_channel_pair_anomalies = [
        {
            "record_index_zero_based": offset,
            "first_channel": write_data[offset].channel,
            "second_channel": (
                None
                if offset + 1 >= len(write_data)
                else write_data[offset + 1].channel
            ),
        }
        for offset in range(0, len(write_data), 2)
        if (
            offset + 1 >= len(write_data)
            or (write_data[offset].channel, write_data[offset + 1].channel)
            != (0, 1)
        )
    ]
    expected_write_addresses = list(
        range(
            min(write_addresses, default=0),
            min(write_addresses, default=0) + len(write_addresses),
        )
    )

    if (
        not address_length_match
        or missing_address_occurrences
        or extra_address_occurrences
    ):
        first_divergence = {
            "stage": "mse0_read_request_issue",
            "request_index_zero_based": (
                None
                if not address_mismatch_positions
                else address_mismatch_positions[0]
            ),
            "expected_address_128bit": (
                None
                if not address_mismatch_positions
                else f"0x{expected_addresses[address_mismatch_positions[0]]:06x}"
            ),
            "actual_address_128bit": (
                None
                if not address_mismatch_positions
                else f"0x{actual_addresses[address_mismatch_positions[0]]:06x}"
            ),
            "interpretation": (
                "read-address occurrence set diverged before DDR return"
            ),
        }
    elif (
        exact_return_mismatch_positions
        or return_missing
        or return_extra
        or unmatched_returns
        or pending_requests
    ):
        first_divergence = {
            "stage": "mse0_ddr_return",
            "interpretation": "request addresses match but returned payload differs",
        }
    elif numeric_mismatch_positions:
        first_divergence = {
            "stage": "post_mse0_pre_mse4",
            "interpretation": "requires buffer/GA probes",
        }
    else:
        first_divergence = {
            "stage": "none_observed",
            "interpretation": "observable numeric path matches",
        }

    return {
        "schema": "gap-rtl-numeric-path-analysis-v1",
        "slice_id": slice_id,
        "inputs": {
            "sim_root": sim_root.as_posix(),
            "package_root": package_root.as_posix(),
            "logs": {
                "mse0_requests": {
                    "path": request_path.as_posix(),
                    "sha256": _sha256(request_path),
                },
                "mse0_returns": {
                    "path": read_path.as_posix(),
                    "sha256": _sha256(read_path),
                },
                "mse4_requests": {
                    "path": write_request_path.as_posix(),
                    "sha256": _sha256(write_request_path),
                },
                "mse4_write_data": {
                    "path": write_data_path.as_posix(),
                    "sha256": _sha256(write_data_path),
                },
            },
        },
        "first_divergence": first_divergence,
        "mse0_request_address_check": {
            "expected_count": len(expected_addresses),
            "actual_count": len(actual_addresses),
            "count_match": address_length_match,
            "mismatch_count": len(address_mismatch_positions)
            + abs(len(actual_addresses) - len(expected_addresses)),
            "missing_expected_address_occurrence_count": (
                missing_address_occurrences
            ),
            "extra_actual_address_occurrence_count": extra_address_occurrences,
            "address_occurrence_multiset_match": (
                address_length_match
                and missing_address_occurrences == 0
                and extra_address_occurrences == 0
            ),
            "sequence_order_mismatch_count": len(address_mismatch_positions),
            "address_delta_histogram_128bit_words": {
                str(delta): count
                for delta, count in sorted(address_delta_histogram.items())
            },
            "first_expected_addresses_128bit": [
                f"0x{address:06x}" for address in expected_addresses[:16]
            ],
            "first_actual_addresses_128bit": [
                f"0x{address:06x}" for address in actual_addresses[:16]
            ],
            "first_mismatch_positions_zero_based": address_mismatch_positions[:16],
            "fully_matching_outer_blocks": len(exact_outer_blocks),
            "fully_matching_outer_block_ids": exact_outer_blocks,
        },
        "mse0_return_payload_check": {
            "actual_return_count": len(read_returns),
            "associated_return_count": len(associated),
            "unmatched_return_count": unmatched_returns,
            "pending_request_count": pending_requests,
            "exact_payload_mismatch_count": len(
                exact_return_mismatch_positions
            ),
            "first_exact_payload_mismatch_positions_zero_based": (
                exact_return_mismatch_positions[:16]
            ),
            "multiset_missing_count": return_missing,
            "multiset_extra_count": return_extra,
            "actual_requests_to_returned_payload_exact_match": (
                unmatched_returns == 0
                and pending_requests == 0
                and not exact_return_mismatch_positions
                and return_missing == 0
                and return_extra == 0
            ),
            "association_policy": "per_physical_return_channel_fifo",
            "tb_issue_columns_trusted": False,
        },
        "mse4_output_check": {
            "actual_128bit_record_count": len(write_data),
            "expected_128bit_record_count": len(matrix_d),
            "request_to_write_data_count_delta": (
                len(write_requests) - len(write_data)
            ),
            "two_channel_pair_complete": (
                len(write_data) % 2 == 0 and not write_channel_pair_anomalies
            ),
            "first_channel_pair_anomalies": write_channel_pair_anomalies[:16],
            "actual_int32_count": len(actual_output),
            "golden_int32_count": len(golden_output),
            "mismatch_count": len(numeric_mismatch_positions)
            + abs(len(actual_output) - len(golden_output)),
            "match_count_in_overlap": numeric_count - len(numeric_mismatch_positions),
            "first_mismatch_positions_zero_based": numeric_mismatch_positions[:16],
        },
        "mse4_write_address_check": {
            "request_count": len(write_addresses),
            "unique_address_count": len(unique_write_addresses),
            "unique_addresses_128bit": [
                f"0x{address:06x}" for address in unique_write_addresses
            ],
            "expected_if_contiguous_128bit": {
                "first_addresses": [
                    f"0x{address:06x}" for address in expected_write_addresses[:16]
                ],
                "note": (
                    "two 128-bit writes per 32-byte C8 int32 output block"
                ),
            },
        },
        "conclusion": {
            "rtl_files_modified": False,
            "ddr_payload_corruption_observed": False,
            "read_address_occurrence_error_observed": bool(
                not address_length_match
                or missing_address_occurrences
                or extra_address_occurrences
            ),
            "read_request_sequence_order_diff_observed": bool(
                address_mismatch_positions
            ),
            "fixed_write_address_overwrite_observed": (
                len(write_addresses) > 2 and len(unique_write_addresses) == 2
            ),
            "write_data_shortfall_observed": (
                len(write_requests) != len(write_data)
            ),
            "next_probe_boundary": (
                "buffer-to-GA accepted operands, GA output writes, and "
                "same-clock MSE4 request/write-data accounting"
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim-root", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--slice", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = analyze(
        sim_root=args.sim_root.resolve(),
        package_root=args.package_root.resolve(),
        slice_id=args.slice,
    )
    rendered = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
