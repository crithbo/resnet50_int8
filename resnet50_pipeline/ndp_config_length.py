from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class NdpConfigLengthError(ValueError):
    pass


def parse_load_config_length(
    instructions_explained: Path, op_id: str
) -> int:
    lines = [
        line
        for line in instructions_explained.read_text(
            encoding="utf-8"
        ).splitlines()
        if f"Load_Config for operator {op_id} " in line
    ]
    if len(lines) != 1:
        raise NdpConfigLengthError(
            f"expected one Load_Config for {op_id}, found {len(lines)}"
        )
    match = re.search(r"config_length_bin=([01]{8})", lines[0])
    if not match:
        raise NdpConfigLengthError(
            f"Load_Config length is missing for {op_id}"
        )
    return int(match.group(1), 2)


def _load_binary_lines(bitstream: Path, width: int) -> list[str]:
    lines = [
        line.strip()
        for line in bitstream.read_text(
            encoding="ascii"
        ).splitlines()
        if line.strip()
    ]
    if (
        not lines
        or any(
            len(line) != width or set(line) - {"0", "1"}
            for line in lines
        )
    ):
        raise NdpConfigLengthError(
            f"config bitstream must contain non-empty {width}-bit binary rows"
        )
    return lines


def analyze_config_length(
    bitstream_64b: Path,
    bitstream_128b: Path,
    programmed_length_64bit_words: int,
) -> dict[str, Any]:
    if programmed_length_64bit_words < 0:
        raise NdpConfigLengthError(
            "programmed config length must be non-negative"
        )
    words = _load_binary_lines(bitstream_64b, 64)
    rows = _load_binary_lines(bitstream_128b, 128)
    expected_rows = []
    for index in range(0, len(words), 2):
        low = words[index]
        high = (
            words[index + 1]
            if index + 1 < len(words)
            else "0" * 64
        )
        expected_rows.append(high + low)
    if rows != expected_rows:
        raise NdpConfigLengthError(
            "128-bit config bitstream is not the exact reordered packing "
            "of the 64-bit source stream"
        )
    odd_word_count = len(words) % 2 == 1
    padding_classification = (
        "ODD_ONE_TRANSPORT_PADDING_HALF"
        if odd_word_count
        else "EVEN_NO_TRANSPORT_PADDING_HALF"
    )
    return {
        "source_64bit_word_count": len(words),
        "physical_128bit_rows": len(rows),
        "physical_64bit_transport_slots": len(rows) * 2,
        "last_row_high_half_is_transport_padding": odd_word_count,
        "padding_classification": padding_classification,
        "packing_matches_64bit_source": True,
        "rtl_meaningful_64bit_word_count": len(words),
        "programmed_load_config_length_64bit_words": (
            programmed_length_64bit_words
        ),
        "matches_rtl_padding_contract": (
            programmed_length_64bit_words == len(words)
        ),
        "rtl_boundary": (
            "global_config_manager sets gconfig_len_sent=len-1, "
            "uses ARLEN=(len-1)>>1, and for odd len suppresses the "
            "final 128-bit beat high half; the 64-bit generator output "
            "owns the meaningful word count"
        ),
    }


__all__ = [
    "NdpConfigLengthError",
    "analyze_config_length",
    "parse_load_config_length",
]
