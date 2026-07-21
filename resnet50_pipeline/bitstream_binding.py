from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Mapping


BITSTREAM_BINDING_SCHEMA_VERSION = "resnet50-config-bitstream-binding-0.1"
BITSTREAM_IDENTITY_FIELDS = (
    "raw_size_bytes",
    "raw_sha256",
    "logical_size_bytes",
    "logical_sha256",
    "line_count",
    "line_width_bits",
)


class BitstreamBindingError(ValueError):
    """A textual bitstream is malformed or differs from its bound identity."""


def bitstream_text_identity(path: Path, *, line_width_bits: int) -> dict[str, Any]:
    """Return raw transport and LF-canonical logical identities for a bitstream."""

    if line_width_bits <= 0:
        raise BitstreamBindingError("bitstream line width must be positive")
    try:
        raw = path.read_bytes()
        text = raw.decode("ascii")
    except (OSError, UnicodeDecodeError) as error:
        raise BitstreamBindingError(f"cannot read ASCII bitstream: {path}") from error
    if not raw:
        raise BitstreamBindingError(f"empty bitstream: {path}")
    lines = text.splitlines()
    if not lines:
        raise BitstreamBindingError(f"empty bitstream: {path}")
    for line_number, line in enumerate(lines, 1):
        if (
            not line
            or len(line) != line_width_bits
            or set(line) - {"0", "1"}
        ):
            raise BitstreamBindingError(
                f"invalid {line_width_bits}-bit line at {path}:{line_number}"
            )
    canonical = ("\n".join(lines) + "\n").encode("ascii")
    return {
        "raw_size_bytes": len(raw),
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "logical_size_bytes": len(canonical),
        "logical_sha256": hashlib.sha256(canonical).hexdigest(),
        "line_count": len(lines),
        "line_width_bits": line_width_bits,
    }


def validate_recorded_bitstream_identity(
    path: Path,
    recorded: Mapping[str, Any],
    *,
    require_raw_identity: bool,
) -> dict[str, Any]:
    """Recompute one identity and reject missing or mismatched recorded fields."""

    try:
        width = int(recorded["line_width_bits"])
    except (KeyError, TypeError, ValueError) as error:
        raise BitstreamBindingError(
            f"recorded bitstream line width is missing or invalid: {path}"
        ) from error
    observed = bitstream_text_identity(path, line_width_bits=width)
    compared = BITSTREAM_IDENTITY_FIELDS if require_raw_identity else (
        "logical_size_bytes",
        "logical_sha256",
        "line_count",
        "line_width_bits",
    )
    for field in compared:
        if recorded.get(field) != observed[field]:
            raise BitstreamBindingError(
                f"bitstream identity differs at {path}: field={field}, "
                f"expected={recorded.get(field)!r}, observed={observed[field]!r}"
            )
    return observed


def require_same_logical_bitstream(
    expected: Mapping[str, Any],
    observed: Mapping[str, Any],
    *,
    label: str,
) -> None:
    """Require parsed line content, order, count, and width to be identical."""

    for field in (
        "logical_size_bytes",
        "logical_sha256",
        "line_count",
        "line_width_bits",
    ):
        if expected.get(field) != observed.get(field):
            raise BitstreamBindingError(
                f"{label} logical bitstream differs: field={field}, "
                f"expected={expected.get(field)!r}, observed={observed.get(field)!r}"
            )
