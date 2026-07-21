from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import sys
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Mapping

from .bitstream_binding import (
    BITSTREAM_BINDING_SCHEMA_VERSION,
    BITSTREAM_IDENTITY_FIELDS,
    BitstreamBindingError,
    bitstream_text_identity,
    require_same_logical_bitstream,
    validate_recorded_bitstream_identity,
)
from .conv_execplan_transport import validate_conv_execplan_request
from .conv_instance import FIRST_REAL_CONV_NODE_ID, build_conv_target_request
from .hardware_simulation_frontend import (
    HardwareSimulationPreparationError,
    build_execution_stages,
    load_execplan_commands,
)
from .profile28 import GROUP_SAMPLE_COUNTS
from .topology28 import HIGH_RING_OWNERS


SUPPORTED_NODE_ID = FIRST_REAL_CONV_NODE_ID
FREEZE_RELATIVE = Path("artifacts/w5/hwop-0004-00/hardware_freeze_v10r5")
EXPECTED_FREEZE_MANIFEST_SHA256 = (
    "72e17cb52c2948f86fe6b0e9b2715de57c5404a72a04f9514247f174e8a95550"
)
EXPECTED_FREEZE_ID = "f687debd0215f1d29b6ca94176c4e9cbcf20434d58bce57c430129edb8922d5f"
ALL_SLICES_MASK = (1 << 28) - 1
ROW_BYTES = 1024
FREEZE_SLICE_STRIDE_BYTES = 0x01800000
EXECPLAN_SLICE_SHIFT = 25
AXI_DATA_BYTES = 16
AXI_MAX_BURST_BEATS = 256
AXI_4KB_BYTES = 4096
RUNTIME_BARRIER_OPCODE = 0b110
_PACKAGE_TEXT_SUFFIXES = {".json", ".sh", ".tcl", ".tsv", ".txt"}


class ConvHardwareExecplanError(ValueError):
    """The frozen Conv package cannot be represented by the hardware execplan entry."""


_REGION_RECEIPT_SEAL = object()


class _ValidatedRegionReceipt(dict[str, Any]):
    """JSON-safe file receipt carrying a private, already-parsed payload snapshot."""

    def __init__(
        self,
        public_receipt: Mapping[str, Any],
        region_snapshot: Mapping[Path, Mapping[str, Any]],
        package_snapshot: Mapping[str, Mapping[str, Any]],
    ) -> None:
        super().__init__(public_receipt)
        self._seal = _REGION_RECEIPT_SEAL
        self._region_snapshot = dict(region_snapshot)
        self._package_snapshot = dict(package_snapshot)
        self._public_sha256 = _canonical_json_sha256(self)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_sha256(value: Mapping[str, Any]) -> str:
    try:
        payload = json.dumps(
            dict(value),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ConvHardwareExecplanError("JSON object is not canonicalizable") from error
    return _sha256_bytes(payload)


def _canonical_json_record_list_sha256(
    value: list[Mapping[str, Any]],
) -> str:
    try:
        payload = json.dumps(
            [dict(record) for record in value],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ConvHardwareExecplanError(
            "JSON record list is not canonicalizable"
        ) from error
    return _sha256_bytes(payload)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConvHardwareExecplanError(f"cannot read JSON object: {path}") from error
    if not isinstance(value, dict):
        raise ConvHardwareExecplanError(f"JSON root is not an object: {path}")
    return value


def _resolve_contained_relative_path(
    root: Path,
    relative_value: str,
    *,
    label: str,
) -> Path:
    """Resolve an untrusted relative path while keeping it below ``root``."""

    if not isinstance(relative_value, str) or not relative_value.strip():
        raise ConvHardwareExecplanError(f"{label} must be a non-empty relative path")
    relative = Path(relative_value)
    portable_views = (PurePosixPath(relative_value), PureWindowsPath(relative_value))
    if any(
        path.is_absolute()
        or bool(path.anchor)
        or any(part == ".." for part in path.parts)
        for path in portable_views
    ):
        raise ConvHardwareExecplanError(
            f"{label} must not be absolute or contain '..': {relative_value!r}"
        )
    resolved_root = root.resolve()
    try:
        candidate = (resolved_root / relative).resolve()
        candidate.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError) as error:
        raise ConvHardwareExecplanError(
            f"{label} escapes its root: {relative_value!r}"
        ) from error
    return candidate


def _write_text_lf(path: Path, value: str, *, encoding: str = "utf-8") -> None:
    """Write deterministic text without platform newline translation."""

    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    path.write_bytes(normalized.encode(encoding))


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    _write_text_lf(
        path,
        json.dumps(dict(value), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
    )


def _looks_like_bit_text(payload: bytes) -> bool:
    if not payload:
        return False
    compact = payload.translate(None, b" \t\r\n")
    return bool(compact) and not (set(compact) - {ord("0"), ord("1")})


def _is_package_text_file(path: Path) -> bool:
    if path.suffix.lower() in _PACKAGE_TEXT_SUFFIXES:
        return True
    return path.suffix.lower() == ".bin" and _looks_like_bit_text(path.read_bytes())


def _package_text_paths(root: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and _is_package_text_file(path)
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def _normalize_package_text_files(root: Path) -> list[str]:
    records: list[str] = []
    for path in _package_text_paths(root):
        payload = path.read_bytes()
        if b"\x00" in payload:
            raise ConvHardwareExecplanError(
                f"declared package text contains NUL bytes: {path}"
            )
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ConvHardwareExecplanError(
                f"declared package text is not UTF-8/ASCII: {path}"
            ) from error
        normalized = payload.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if normalized != payload:
            path.write_bytes(normalized)
        records.append(path.relative_to(root).as_posix())
    return records


def _validate_package_text_contract(
    root: Path,
    contract: Mapping[str, Any],
) -> int:
    raw_paths = contract.get("paths")
    if (
        contract.get("encoding") != "utf-8_or_ascii"
        or contract.get("line_ending") != "lf"
        or contract.get("carriage_return_byte_allowed") is not False
        or not isinstance(raw_paths, list)
        or not raw_paths
        or any(not isinstance(item, str) or not item for item in raw_paths)
    ):
        raise ConvHardwareExecplanError("package LF text contract is malformed")
    declared = list(raw_paths)
    if declared != sorted(set(declared)):
        raise ConvHardwareExecplanError("package LF text paths are not unique/sorted")
    actual = [path.relative_to(root).as_posix() for path in _package_text_paths(root)]
    if declared != actual:
        raise ConvHardwareExecplanError(
            "package LF text contract does not match the actual text file set: "
            f"missing={sorted(set(actual) - set(declared))[:5]}, "
            f"extra={sorted(set(declared) - set(actual))[:5]}"
        )
    for relative in declared:
        path = _resolve_contained_relative_path(
            root,
            relative,
            label="package LF text path",
        )
        if not path.is_file() or path.is_symlink():
            raise ConvHardwareExecplanError(
                f"package LF text is missing or is a symlink: {relative}"
            )
        payload = path.read_bytes()
        cr_count = payload.count(b"\r")
        if cr_count:
            raise ConvHardwareExecplanError(
                f"package text is not LF-only: {relative}, cr_byte_count={cr_count}"
            )
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ConvHardwareExecplanError(
                f"package text is not UTF-8/ASCII: {relative}"
            ) from error
    return len(declared)


def _align_up(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def _mask(slice_ids: list[int]) -> int:
    value = 0
    for slice_id in slice_ids:
        if not 0 <= slice_id < 28:
            raise ConvHardwareExecplanError(f"slice id is outside [0, 27]: {slice_id}")
        value |= 1 << slice_id
    return value


def _legacy_fixed_pair_requant_order(
    shards: list[object],
) -> list[dict[str, Any]]:
    """Order independent requant groups for the server's fixed slice0/slice1 TB.

    The immutable server testbench alternates between a slice0 Start_Comp and a
    slice1 completion.  Requant shards that use disjoint slice groups may be
    reordered without changing their data dependencies.  Keep each group's
    local-half order, but place the two observed groups around all neutral
    groups so the final observed pair ends on the final runtime stage.
    """

    normalized: list[dict[str, Any]] = []
    for shard in shards:
        if not isinstance(shard, dict):
            raise ConvHardwareExecplanError("requant shard entry is malformed")
        selected = shard.get("selected_slices")
        if not isinstance(selected, list) or not selected:
            raise ConvHardwareExecplanError(
                "requant shard selected_slices is malformed"
            )
        normalized.append(shard)

    def shard_key(shard: dict[str, Any]) -> tuple[int, int]:
        return int(shard.get("local_half", -1)), int(shard.get("shard_index", -1))

    slice0_group: list[dict[str, Any]] = []
    slice1_group: list[dict[str, Any]] = []
    neutral_groups: list[dict[str, Any]] = []
    for shard in normalized:
        selected = {int(value) for value in shard["selected_slices"]}
        has_slice0 = 0 in selected
        has_slice1 = 1 in selected
        if has_slice0 and has_slice1:
            raise ConvHardwareExecplanError(
                "legacy fixed-pair scheduling requires disjoint slice0/slice1 "
                "requant groups"
            )
        if has_slice0:
            slice0_group.append(shard)
        elif has_slice1:
            slice1_group.append(shard)
        else:
            neutral_groups.append(shard)

    slice0_group.sort(key=shard_key)
    slice1_group.sort(key=shard_key)
    neutral_groups.sort(key=lambda shard: int(shard.get("shard_index", -1)))
    if len(slice0_group) < 2 or len(slice1_group) < 2:
        raise ConvHardwareExecplanError(
            "legacy fixed-pair scheduling needs at least two ordered shards for "
            "both slice0 and slice1"
        )
    ordered = [
        slice0_group[0],
        *neutral_groups,
        slice1_group[0],
        *slice0_group[1:],
        *slice1_group[1:],
    ]
    final = ordered[-1]
    final_selected = [int(value) for value in final["selected_slices"]]
    if 1 not in final_selected or 0 in final_selected or len(final_selected) < 2:
        raise ConvHardwareExecplanError(
            "legacy fixed-pair final requant group cannot be fenced by slice1"
        )
    non_observer_slices = [value for value in final_selected if value != 1]
    common = {**final, "original_selected_slices": final_selected}
    # The immutable TB starts readback after the final observed slice1 finish.
    # Run every other member of the last shard behind its own barrier first,
    # then execute slice1 alone.  The final observer event now proves that all
    # selected slices have completed, rather than merely proving one member of
    # a multi-slice final mask.
    return [
        *ordered[:-1],
        {
            **common,
            "selected_slices": non_observer_slices,
            "runtime_partition": "non_observer_slices",
        },
        {
            **common,
            "selected_slices": [1],
            "runtime_partition": "finish_slice_only",
        },
    ]


def _legacy_fixed_pair_observer_contract(
    operators: list[Any],
) -> dict[str, Any]:
    """Prove the fixed TB's final observed pair is a runtime completion fence."""

    pairs: list[dict[str, int]] = []
    waiting_for_start = True
    start_stage = -1
    for stage_index, operator in enumerate(operators):
        mask = int(operator.used_slices)
        if waiting_for_start and (mask & 0x1):
            start_stage = stage_index
            waiting_for_start = False
        if not waiting_for_start and (mask & 0x2):
            pairs.append(
                {
                    "pair_index": len(pairs),
                    "slice0_start_stage": start_stage,
                    "slice1_finish_stage": stage_index,
                }
            )
            waiting_for_start = True
            start_stage = -1
    if not pairs or not waiting_for_start:
        raise ConvHardwareExecplanError(
            "legacy fixed-pair observer sequence does not close"
        )
    final_stage = len(operators) - 1
    if pairs[-1]["slice1_finish_stage"] != final_stage:
        raise ConvHardwareExecplanError(
            "legacy fixed-pair observer does not finish on the final runtime stage"
        )
    final_operator = operators[-1]
    previous_operator = operators[-2] if len(operators) >= 2 else None
    final_attributes = dict(final_operator.attributes)
    previous_attributes = (
        dict(previous_operator.attributes) if previous_operator is not None else {}
    )
    original_selected = {
        int(value) for value in final_attributes.get("original_selected_slices", [])
    }
    if (
        int(final_operator.used_slices) != (1 << 1)
        or final_attributes.get("runtime_partition") != "finish_slice_only"
        or previous_attributes.get("runtime_partition") != "non_observer_slices"
        or previous_attributes.get("shard_index") != final_attributes.get("shard_index")
        or original_selected != {
            *[int(value) for value in previous_attributes.get("selected_slices", [])],
            1,
        }
    ):
        raise ConvHardwareExecplanError(
            "legacy fixed-pair final stage is not a finish-slice-only completion fence"
        )
    return {
        "mode": "fixed_slice0_start_slice1_finish",
        "start_slice_id": 0,
        "finish_slice_id": 1,
        "repeat_num": len(pairs),
        "runtime_stage_count": len(operators),
        "final_pair_finishes_at_stage": final_stage,
        "all_prior_stages_barrier_ordered": True,
        "final_stage_slice_mask": "0x0000002",
        "final_stage_is_finish_slice_only": True,
        "all_other_final_shard_slices_barrier_completed_before_final_stage": True,
        "readback_after_final_finish_is_full_mask_completion_safe": True,
        "pairs": pairs,
    }


def _insert_runtime_completion_barriers(
    api: Mapping[str, Any], artifact: Any, operators: list[Any]
) -> Any:
    """Call the opt-in native server profile; never reimplement the fence here."""

    insert_barriers = api.get("insert_server_completion_barriers")
    if insert_barriers is None:
        native_src = (
            Path(__file__).resolve().parents[1]
            / "ndp-sim-ref"
            / "model_execplan"
            / "src"
        )
        native_src_text = str(native_src)
        if native_src_text not in sys.path:
            sys.path.insert(0, native_src_text)
        from execution_plan_generator.server_profile import (
            insert_server_completion_barriers as insert_barriers,
        )
    try:
        return insert_barriers(artifact, operators)
    except ValueError as error:
        raise ConvHardwareExecplanError(str(error)) from error


def _accumulate_batch_waves() -> list[dict[str, Any]]:
    """Map the seven physical HIGH rings onto the three local sample slots."""

    starts: list[int] = []
    cursor = 0
    for count in GROUP_SAMPLE_COUNTS:
        starts.append(cursor)
        cursor += count
    waves: list[dict[str, Any]] = []
    for local_sample_index in range(max(GROUP_SAMPLE_COUNTS)):
        group_ids = [
            group_id
            for group_id, count in enumerate(GROUP_SAMPLE_COUNTS)
            if count > local_sample_index
        ]
        slice_ids = [
            slice_id
            for group_id in group_ids
            for slice_id in HIGH_RING_OWNERS[group_id]
        ]
        waves.append(
            {
                "wave_index": local_sample_index,
                "local_sample_index": local_sample_index,
                "group_ids": group_ids,
                "logical_samples": [
                    starts[group_id] + local_sample_index for group_id in group_ids
                ],
                "slice_ids": slice_ids,
                "slice_mask": _mask(slice_ids),
            }
        )
    return waves


def _freeze_local_offset(base_address: int, slice_id: int) -> int:
    expected_floor = slice_id * FREEZE_SLICE_STRIDE_BYTES
    local_offset = base_address - expected_floor
    if not 0 <= local_offset < FREEZE_SLICE_STRIDE_BYTES:
        raise ConvHardwareExecplanError(
            f"freeze address is outside slice {slice_id}: 0x{base_address:08X}"
        )
    return local_offset


def _execplan_address(slice_id: int, local_offset: int) -> int:
    if not 0 <= slice_id < 28 or not 0 <= local_offset < (1 << EXECPLAN_SLICE_SHIFT):
        raise ConvHardwareExecplanError(
            f"cannot encode execplan address: slice={slice_id}, offset={local_offset}"
        )
    return (slice_id << EXECPLAN_SLICE_SHIFT) | local_offset


def _binary_line_count(path: Path, width: int) -> int:
    count = 0
    for line_number, raw_line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        if len(line) != width or set(line) - {"0", "1"}:
            raise ConvHardwareExecplanError(
                f"invalid {width}-bit line at {path}:{line_number}"
            )
        count += 1
    if count == 0:
        raise ConvHardwareExecplanError(f"empty bitstream: {path}")
    return count


def _first_binary_word_hex(path: Path, width: int = 128) -> str:
    for line_number, raw_line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        bits = raw_line.strip()
        if not bits:
            continue
        if len(bits) != width or set(bits) - {"0", "1"}:
            raise ConvHardwareExecplanError(
                f"invalid {width}-bit line at {path}:{line_number}"
            )
        return f"0x{int(bits, 2):0{width // 4}X}"
    raise ConvHardwareExecplanError(f"empty bit-text payload: {path}")


def _write_128bit_binary_text(source: Path, destination: Path) -> tuple[int, str]:
    """Encode raw little-endian memory bytes for the line-oriented SCA loader."""
    raw = source.read_bytes()
    if not raw or len(raw) % 16:
        raise ConvHardwareExecplanError(
            f"SCA input payload must be a non-empty multiple of 16 bytes: {source}"
        )
    lines = [
        f"{int.from_bytes(raw[offset : offset + 16], byteorder='little'):0128b}"
        for offset in range(0, len(raw), 16)
    ]
    _write_text_lf(destination, "\n".join(lines) + "\n", encoding="ascii")
    return len(lines), f"0x{int.from_bytes(raw[:16], byteorder='little'):032X}"


def _write_zero_128bit_binary_text(destination: Path, size_bytes: int) -> int:
    if size_bytes <= 0 or size_bytes % 16:
        raise ConvHardwareExecplanError(
            f"runtime scratch size must be a positive multiple of 16 bytes: {size_bytes}"
    )
    line_count = size_bytes // 16
    _write_text_lf(
        destination,
        ("0" * 128 + "\n") * line_count,
        encoding="ascii",
    )
    return line_count


def _read_128bit_binary_lines(path: Path) -> list[str]:
    """Read one immutable-testbench payload without accepting ambiguous widths."""

    try:
        lines = [line.strip() for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
    except (OSError, UnicodeDecodeError) as error:
        raise ConvHardwareExecplanError(f"cannot read 128-bit SCA payload: {path}") from error
    if not lines:
        raise ConvHardwareExecplanError(f"empty 128-bit SCA payload: {path}")
    for line_number, line in enumerate(lines, 1):
        if len(line) != 128 or set(line) - {"0", "1"}:
            raise ConvHardwareExecplanError(
                f"invalid 128-bit SCA payload line at {path}:{line_number}"
            )
    return lines


def _validate_axi4_burst_sequence(
    base_address: int,
    beat_count: int,
    *,
    label: str,
) -> None:
    """Model the immutable TB's 256-beat loop and enforce AXI's 4-KiB rule."""

    if base_address < 0 or base_address % AXI_DATA_BYTES:
        raise ConvHardwareExecplanError(
            f"{label} base address is not 128-bit aligned: 0x{base_address:X}"
        )
    if beat_count <= 0:
        raise ConvHardwareExecplanError(f"{label} beat count must be positive")
    address = base_address
    remaining = beat_count
    while remaining:
        burst_beats = min(remaining, AXI_MAX_BURST_BEATS)
        final_address = address + burst_beats * AXI_DATA_BYTES - 1
        if address // AXI_4KB_BYTES != final_address // AXI_4KB_BYTES:
            raise ConvHardwareExecplanError(
                f"{label} AXI burst crosses a 4-KiB boundary: "
                f"base=0x{address:08X}, beats={burst_beats}"
            )
        address += burst_beats * AXI_DATA_BYTES
        remaining -= burst_beats


def _head_beats_to_4kb(base_address: int, beat_count: int) -> int | None:
    """Return the short head needed to make all following 256-beat bursts legal."""

    if base_address < 0 or base_address % AXI_DATA_BYTES or beat_count <= 0:
        raise ConvHardwareExecplanError(
            f"invalid AXI transfer boundary: base=0x{base_address:X}, beats={beat_count}"
        )
    address_in_page = base_address % AXI_4KB_BYTES
    if address_in_page == 0:
        return None
    beats_to_page = (AXI_4KB_BYTES - address_in_page) // AXI_DATA_BYTES
    return beats_to_page if beat_count > beats_to_page else None


def _split_payload_path(
    source_relative: str,
    *,
    address_in_page: int,
    part: str,
) -> str:
    source = PurePosixPath(source_relative)
    suffix = source.suffix or ".txt"
    directory = source.parent / (
        f"{source.name}.axi4-{address_in_page:03x}-segments"
    )
    return (directory / f"{part}{suffix}").as_posix()


def _split_sca_preload_transfers(
    sca: Mapping[str, Any],
    root: Path,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, Any]]:
    """Split only an unsafe first burst; page-aligned long tails remain one entry.

    ``ExecutionPlan`` retains its complete semantic path for the Python decoder.
    Its short head is nested between ``base_addr`` and ``path`` so the immutable
    line-oriented TB loads that head at the nested close and does not reload the
    complete file at the outer close.  The tail is an ordinary SCA entry.
    """

    result: dict[str, Any] = {}
    bank_export: dict[str, Any] = {}
    segments_by_semantic: dict[str, list[dict[str, Any]]] = {}
    written: dict[tuple[str, int], tuple[str, str]] = {}

    for key, raw_value in sca.items():
        if not (
            isinstance(raw_value, Mapping)
            and isinstance(raw_value.get("base_addr"), str)
            and isinstance(raw_value.get("path"), str)
        ):
            result[key] = raw_value
            bank_export[key] = raw_value
            continue

        value = dict(raw_value)
        try:
            base_address = int(str(value["base_addr"]).replace("_", ""), 16)
        except ValueError as error:
            raise ConvHardwareExecplanError(f"invalid SCA base address: {key}") from error
        source_path = _resolve_contained_relative_path(
            root,
            str(value["path"]),
            label=f"SCA semantic payload path ({key})",
        )
        source_relative = source_path.relative_to(root.resolve()).as_posix()
        lines = _read_128bit_binary_lines(source_path)
        head_beats = _head_beats_to_4kb(base_address, len(lines))
        if head_beats is None:
            _validate_axi4_burst_sequence(base_address, len(lines), label=f"SCA {key}")
            result[key] = value
            bank_export[key] = value
            segments_by_semantic[key] = [value]
            continue

        cache_key = (source_relative, base_address % AXI_4KB_BYTES)
        cached_paths = written.get(cache_key)
        if cached_paths is None:
            head_relative = _split_payload_path(
                source_relative,
                address_in_page=base_address % AXI_4KB_BYTES,
                part="head",
            )
            tail_relative = _split_payload_path(
                source_relative,
                address_in_page=base_address % AXI_4KB_BYTES,
                part="tail",
            )
            for relative, payload_lines in (
                (head_relative, lines[:head_beats]),
                (tail_relative, lines[head_beats:]),
            ):
                destination = _resolve_contained_relative_path(
                    root,
                    relative,
                    label=f"generated AXI segment path ({key})",
                )
                _write_text_lf(
                    destination,
                    "\n".join(payload_lines) + "\n",
                    encoding="ascii",
                )
            cached_paths = (head_relative, tail_relative)
            written[cache_key] = cached_paths

        segment_count = 2
        head_entry = {
            "axi4_segment_count": segment_count,
            "axi4_segment_index": 0,
            "base_addr": f"0x{base_address:08X}",
            "line_count_128bit": head_beats,
            "path": cached_paths[0],
            "semantic_key": key,
            "semantic_path": source_relative,
        }
        tail_entry = {
            "axi4_segment_count": segment_count,
            "axi4_segment_index": 1,
            "base_addr": f"0x{base_address + head_beats * AXI_DATA_BYTES:08X}",
            "line_count_128bit": len(lines) - head_beats,
            "path": cached_paths[1],
            "semantic_key": key,
            "semantic_path": source_relative,
        }
        _validate_axi4_burst_sequence(
            base_address,
            head_beats,
            label=f"SCA {key} head",
        )
        _validate_axi4_burst_sequence(
            base_address + head_beats * AXI_DATA_BYTES,
            len(lines) - head_beats,
            label=f"SCA {key} tail",
        )
        segments_by_semantic[key] = [head_entry, tail_entry]

        if key == "ExecutionPlan":
            descriptor = dict(value)
            descriptor["chunked_transport"] = head_entry
            result[key] = descriptor
        else:
            result[key] = head_entry
        tail_key = f"{key}__axi4_tail"
        if tail_key in sca or tail_key in result:
            raise ConvHardwareExecplanError(f"duplicate generated SCA key: {tail_key}")
        result[tail_key] = tail_entry
        bank_export[key] = head_entry
        bank_export[tail_key] = tail_entry

    return result, segments_by_semantic, bank_export


def _sca_transport_entries(
    sca: Mapping[str, Any],
) -> list[tuple[str, Mapping[str, Any]]]:
    """Return exactly the transfers performed by the immutable line parser."""

    transfers: list[tuple[str, Mapping[str, Any]]] = []
    for key, value in sca.items():
        if not isinstance(value, Mapping):
            continue
        nested = value.get("chunked_transport")
        if key == "ExecutionPlan" and isinstance(nested, Mapping):
            transfers.append((key, nested))
        elif isinstance(value.get("base_addr"), str) and isinstance(value.get("path"), str):
            transfers.append((key, value))
    return transfers


def _validate_immutable_tb_sca_parser_abi(
    sca_path: Path,
    sca: Mapping[str, Any],
) -> int:
    """Simulate the immutable TB's line parser, including every ``}`` reset."""

    try:
        lines = sca_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ConvHardwareExecplanError("cannot read serialized SCA parser ABI") from error
    observed: list[tuple[int, str]] = []
    has_address = False
    has_path = False
    address = 0
    path = ""
    for line_number, line in enumerate(lines, 1):
        stripped = line.strip().rstrip(",")
        if '"base_addr"' in line:
            try:
                field = json.loads("{" + stripped + "}")
                address = int(str(field["base_addr"]).replace("_", ""), 16)
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise ConvHardwareExecplanError(
                    f"serialized SCA base_addr violates parser ABI at line {line_number}"
                ) from error
            has_address = True
        if '"path"' in line:
            try:
                field = json.loads("{" + stripped + "}")
                path = str(field["path"])
            except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
                raise ConvHardwareExecplanError(
                    f"serialized SCA path violates parser ABI at line {line_number}"
                ) from error
            has_path = bool(path)
        if "}" in line:
            if has_address and has_path:
                observed.append((address, path))
            has_address = False
            has_path = False
            address = 0
            path = ""

    expected = [
        (
            int(str(entry["base_addr"]).replace("_", ""), 16),
            str(entry["path"]),
        )
        for _, entry in _sca_transport_entries(sca)
    ]
    if observed != expected:
        raise ConvHardwareExecplanError(
            "serialized SCA differs from the immutable line-parser ABI: "
            f"expected={len(expected)}, observed={len(observed)}"
        )
    return len(observed)


def _split_sca_d_transfers(sca_d: Mapping[str, Any]) -> dict[str, Any]:
    """Split unsafe readback heads while preserving 84 semantic dump regions."""

    result: dict[str, Any] = {}
    for key, raw_entry in sca_d.items():
        if not isinstance(raw_entry, Mapping):
            raise ConvHardwareExecplanError(f"SCA_D entry is not an object: {key}")
        try:
            base_address = int(str(raw_entry["base_addr"]).replace("_", ""), 16)
            beat_count = int(raw_entry["length"])
            semantic_path = str(raw_entry["path"])
        except (KeyError, TypeError, ValueError) as error:
            raise ConvHardwareExecplanError(f"invalid SCA_D entry: {key}") from error
        head_beats = _head_beats_to_4kb(base_address, beat_count)
        if head_beats is None:
            _validate_axi4_burst_sequence(base_address, beat_count, label=f"SCA_D {key}")
            result[key] = dict(raw_entry)
            continue

        head_path = _split_payload_path(
            semantic_path,
            address_in_page=base_address % AXI_4KB_BYTES,
            part="head",
        )
        tail_path = _split_payload_path(
            semantic_path,
            address_in_page=base_address % AXI_4KB_BYTES,
            part="tail",
        )
        common = {
            "axi4_segment_count": 2,
            "semantic_base_addr": f"0x{base_address:08X}",
            "semantic_key": key,
            "semantic_length": beat_count,
            "semantic_path": semantic_path,
        }
        result[key] = {
            **common,
            "axi4_segment_index": 0,
            "base_addr": f"0x{base_address:08X}",
            "length": head_beats,
            "path": head_path,
        }
        tail_key = f"{key}__axi4_tail"
        result[tail_key] = {
            **common,
            "axi4_segment_index": 1,
            "base_addr": f"0x{base_address + head_beats * AXI_DATA_BYTES:08X}",
            "length": beat_count - head_beats,
            "path": tail_path,
        }
        _validate_axi4_burst_sequence(base_address, head_beats, label=f"SCA_D {key} head")
        _validate_axi4_burst_sequence(
            base_address + head_beats * AXI_DATA_BYTES,
            beat_count - head_beats,
            label=f"SCA_D {key} tail",
        )
    return result


def _build_axi4_4kb_trigger_report(
    root: Path,
    preload_segments: Mapping[str, list[dict[str, Any]]],
    semantic_sca_d: Mapping[str, Any],
    split_sca_d: Mapping[str, Any],
) -> dict[str, Any]:
    """Record whether the conditional 4-KiB risk actually triggered."""

    records: list[dict[str, Any]] = []
    for semantic_key in sorted(preload_segments):
        segments = preload_segments[semantic_key]
        if not segments:
            raise ConvHardwareExecplanError(
                f"preload AXI segment set is empty: {semantic_key}"
            )
        first = segments[0]
        base_address = int(str(first["base_addr"]).replace("_", ""), 16)
        semantic_path = str(first.get("semantic_path", first["path"]))
        source = _resolve_contained_relative_path(
            root, semantic_path, label=f"AXI report preload path ({semantic_key})"
        )
        semantic_lines = _read_128bit_binary_lines(source)
        segment_records: list[dict[str, Any]] = []
        reconstructed: list[str] = []
        for index, segment in enumerate(segments):
            segment_path = _resolve_contained_relative_path(
                root,
                str(segment["path"]),
                label=f"AXI report segment path ({semantic_key})",
            )
            lines = _read_128bit_binary_lines(segment_path)
            reconstructed.extend(lines)
            segment_records.append(
                {
                    "index": index,
                    "base_address": str(segment["base_addr"]),
                    "beat_count": len(lines),
                    "path": segment_path.relative_to(root.resolve()).as_posix(),
                    "logical_payload_sha256": _sha256_bytes(
                        ("\n".join(lines) + "\n").encode("ascii")
                    ),
                }
            )
        if reconstructed != semantic_lines:
            raise ConvHardwareExecplanError(
                f"AXI preload segments do not preserve semantic payload: {semantic_key}"
            )
        trigger_head = _head_beats_to_4kb(base_address, len(semantic_lines))
        triggered = trigger_head is not None
        if triggered != (len(segments) > 1):
            raise ConvHardwareExecplanError(
                f"AXI preload trigger/segment count differs: {semantic_key}"
            )
        records.append(
            {
                "domain": "preload",
                "semantic_key": semantic_key,
                "semantic_path": semantic_path,
                "original_base_address": f"0x{base_address:08X}",
                "original_beat_count": len(semantic_lines),
                "original_size_bytes": len(semantic_lines) * AXI_DATA_BYTES,
                "address_in_4kb_page": base_address % AXI_4KB_BYTES,
                "beats_to_4kb_boundary": (
                    (AXI_4KB_BYTES - base_address % AXI_4KB_BYTES)
                    // AXI_DATA_BYTES
                ),
                "triggered": triggered,
                "original_logical_payload_sha256": _sha256_bytes(
                    ("\n".join(semantic_lines) + "\n").encode("ascii")
                ),
                "reconstructed_logical_payload_sha256": _sha256_bytes(
                    ("\n".join(reconstructed) + "\n").encode("ascii")
                ),
                "segments": segment_records,
            }
        )

    for semantic_key in sorted(semantic_sca_d):
        original = semantic_sca_d[semantic_key]
        base_address = int(str(original["base_addr"]).replace("_", ""), 16)
        beat_count = int(original["length"])
        trigger_head = _head_beats_to_4kb(base_address, beat_count)
        matching = [
            (key, entry)
            for key, entry in split_sca_d.items()
            if key == semantic_key
            or (
                isinstance(entry, Mapping)
                and entry.get("semantic_key") == semantic_key
            )
        ]
        matching.sort(
            key=lambda item: int(item[1].get("axi4_segment_index", 0))
        )
        triggered = trigger_head is not None
        if not matching or triggered != (len(matching) > 1):
            raise ConvHardwareExecplanError(
                f"AXI readback trigger/segment count differs: {semantic_key}"
            )
        records.append(
            {
                "domain": "readback",
                "semantic_key": semantic_key,
                "semantic_path": str(original["path"]),
                "original_base_address": f"0x{base_address:08X}",
                "original_beat_count": beat_count,
                "original_size_bytes": beat_count * AXI_DATA_BYTES,
                "address_in_4kb_page": base_address % AXI_4KB_BYTES,
                "beats_to_4kb_boundary": (
                    (AXI_4KB_BYTES - base_address % AXI_4KB_BYTES)
                    // AXI_DATA_BYTES
                ),
                "triggered": triggered,
                "original_descriptor_sha256": _canonical_json_sha256(original),
                "split_descriptor_sha256": _canonical_json_sha256(
                    {key: dict(entry) for key, entry in matching}
                ),
                "segments": [
                    {
                        "index": index,
                        "key": key,
                        "base_address": str(entry["base_addr"]),
                        "beat_count": int(entry["length"]),
                        "path": str(entry["path"]),
                    }
                    for index, (key, entry) in enumerate(matching)
                ],
            }
        )

    triggered_records = [record for record in records if record["triggered"]]
    return {
        "schema_version": "model-execplan-server-axi4-4kb-report-0.1",
        "status": "triggered" if triggered_records else "not_triggered",
        "risk_classification": (
            "conditional_risk_trigger_confirmed"
            if triggered_records
            else "conditional_risk_not_triggered_for_this_package"
        ),
        "policy": "split_only_transfers_whose_first_256_beat_burst_would_cross_4kb",
        "axi_data_bytes": AXI_DATA_BYTES,
        "axi_max_burst_beats": AXI_MAX_BURST_BEATS,
        "page_bytes": AXI_4KB_BYTES,
        "semantic_transfer_count": len(records),
        "triggered_transfer_count": len(triggered_records),
        "unchanged_transfer_count": len(records) - len(triggered_records),
        "records": records,
    }


def _load_execplan_api(project_root: Path) -> dict[str, Any]:
    source_root = project_root / "ndp-sim-ref/model_execplan/src"
    if not source_root.is_dir():
        raise ConvHardwareExecplanError(f"model_execplan source is missing: {source_root}")
    source_text = str(source_root)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)

    from execution_plan_generator.bank_data_exporter import export_bank_data
    from execution_plan_generator.config_stream_decoder import (
        decode_initial_register_state,
        load_template_config_stream,
    )
    from execution_plan_generator.instruction_generator import InstructionGenerator
    from execution_plan_generator.models import (
        AddressAssignment,
        AddressPlan,
        ExecutionPlanArtifact,
        ExecutionPlanInput,
        InputSource,
        InputSourceType,
        OperatorSpec,
        OperatorTemplate,
        TensorSpec,
    )
    from execution_plan_generator.output_writer import (
        write_install_manifest,
        write_instruction_outputs,
    )
    from execution_plan_generator.register_mapping import load_register_mapping
    from execution_plan_generator.server_profile import (
        insert_server_completion_barriers,
    )

    return locals()


def _verify_freeze(
    freeze_root: Path,
    *,
    expected_node_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    manifest_path = _resolve_contained_relative_path(
        freeze_root,
        "manifest.json",
        label="freeze manifest path",
    )
    manifest_payload = manifest_path.read_bytes()
    manifest_sha = _sha256_bytes(manifest_payload)
    manifest = _read_json_object(manifest_path)
    identity = manifest.get("identity")
    if not isinstance(identity, dict) or identity.get("node_id") != expected_node_id:
        raise ConvHardwareExecplanError("freeze identity differs")
    if expected_node_id == FIRST_REAL_CONV_NODE_ID:
        revision = identity.get("revision")
        if revision is None:
            if manifest_sha != EXPECTED_FREEZE_MANIFEST_SHA256:
                raise ConvHardwareExecplanError(
                    f"freeze manifest SHA differs: {manifest_sha}"
                )
            if manifest.get("freeze_id") != EXPECTED_FREEZE_ID:
                raise ConvHardwareExecplanError("freeze id differs")
        elif (
            not isinstance(revision, str)
            or not revision
            or manifest.get("status") != "manual_hardware_handoff_ready"
        ):
            raise ConvHardwareExecplanError("revised first-Conv freeze identity differs")
    elif manifest.get("status") != "candidate_hardware_freeze_ready":
        raise ConvHardwareExecplanError("candidate freeze status differs")

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ConvHardwareExecplanError("freeze manifest files list is missing")
    expected_files = {"manifest.json"}
    for item in files:
        if not isinstance(item, dict):
            raise ConvHardwareExecplanError("freeze manifest file entry is not an object")
        relative = item.get("path")
        expected_size = item.get("size_bytes")
        expected_sha = item.get("sha256")
        if not isinstance(relative, str) or not isinstance(expected_size, int) or not isinstance(expected_sha, str):
            raise ConvHardwareExecplanError("freeze manifest file entry is malformed")
        if relative in expected_files:
            raise ConvHardwareExecplanError(
                f"freeze manifest contains a duplicate/reserved file path: {relative}"
            )
        expected_files.add(relative)
        path = _resolve_contained_relative_path(
            freeze_root,
            relative,
            label="freeze manifest file path",
        )
        if not path.is_file() or path.stat().st_size != expected_size or _sha256_file(path) != expected_sha:
            raise ConvHardwareExecplanError(f"freeze file differs: {relative}")

    actual_files: set[str] = set()
    for path in freeze_root.rglob("*"):
        if path.is_symlink():
            raise ConvHardwareExecplanError(
                f"freeze contains a symlink: {path.relative_to(freeze_root).as_posix()}"
            )
        if path.is_file():
            actual_files.add(path.relative_to(freeze_root).as_posix())
    if actual_files != expected_files:
        raise ConvHardwareExecplanError(
            "freeze file exact-set differs: "
            f"missing={sorted(expected_files - actual_files)}, "
            f"extra={sorted(actual_files - expected_files)}"
        )

    if identity.get("revision") is not None or expected_node_id != FIRST_REAL_CONV_NODE_ID:
        recorded_freeze_id = manifest.get("freeze_id")
        freeze_body = dict(manifest)
        freeze_body.pop("freeze_id", None)
        computed_freeze_id = _sha256_bytes(
            json.dumps(
                freeze_body, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        )
        if recorded_freeze_id != computed_freeze_id:
            raise ConvHardwareExecplanError(
                "freeze id differs from canonical manifest body"
            )

    _validate_freeze_bitstream_bindings(freeze_root, manifest)

    address_table = _read_json_object(
        _resolve_contained_relative_path(
            freeze_root,
            "address_table.json",
            label="freeze address-table path",
        )
    )
    regions = address_table.get("regions")
    staged_offsets = manifest.get("layout", {}).get("staged_d_offsets")
    if not isinstance(staged_offsets, list) or not staged_offsets:
        raise ConvHardwareExecplanError("freeze staged-D layout is missing")
    expected_regions_per_slice = 11 + len(staged_offsets)
    expected_region_count = 28 * expected_regions_per_slice
    if not isinstance(regions, list) or len(regions) != expected_region_count:
        raise ConvHardwareExecplanError(
            f"freeze address table must contain {expected_region_count} regions"
        )
    by_slice: dict[int, list[dict[str, Any]]] = {slice_id: [] for slice_id in range(28)}
    for region in regions:
        if not isinstance(region, dict):
            raise ConvHardwareExecplanError("address region is not an object")
        slice_id = region.get("slice_id")
        base = region.get("base_address")
        size = region.get("size_bytes")
        if not isinstance(slice_id, int) or not isinstance(base, int) or not isinstance(size, int):
            raise ConvHardwareExecplanError("address region fields are malformed")
        if base % 16 or size <= 0 or size % 16:
            raise ConvHardwareExecplanError(f"address region is not 16-byte aligned: {region}")
        if slice_id not in by_slice:
            raise ConvHardwareExecplanError(f"freeze region slice is outside [0, 27]: {slice_id}")
        by_slice[slice_id].append(region)
    for slice_id, items in by_slice.items():
        if len(items) != expected_regions_per_slice:
            raise ConvHardwareExecplanError(
                f"slice {slice_id} does not contain {expected_regions_per_slice} regions"
            )
        ordered = sorted(items, key=lambda item: int(item["base_address"]))
        for left, right in zip(ordered, ordered[1:]):
            if int(left["base_address"]) + int(left["size_bytes"]) > int(right["base_address"]):
                raise ConvHardwareExecplanError(f"freeze regions overlap on slice {slice_id}")
    return manifest, address_table


def _validate_freeze_bitstream_bindings(
    freeze_root: Path,
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    binding = manifest.get("bitstream_bindings")
    if not isinstance(binding, dict):
        raise ConvHardwareExecplanError("freeze bitstream binding contract is missing")
    records = binding.get("records")
    if (
        binding.get("schema_version") != BITSTREAM_BINDING_SCHEMA_VERSION
        or binding.get("status") != "json_official_encoder_freeze_bound"
        or not isinstance(records, list)
        or not records
        or binding.get("record_count") != len(records)
    ):
        raise ConvHardwareExecplanError("freeze bitstream binding contract differs")
    expected_count = 9 if manifest.get("identity", {}).get("node_id") == FIRST_REAL_CONV_NODE_ID else len(records)
    if len(records) != expected_count:
        raise ConvHardwareExecplanError(
            f"freeze bitstream binding record count differs: {len(records)}"
        )
    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise ConvHardwareExecplanError("freeze bitstream binding record is malformed")
        binding_id = record.get("binding_id")
        config = record.get("config")
        official = record.get("official_encoder")
        frozen = record.get("freeze")
        parsed = record.get("parsed_evidence")
        if (
            not isinstance(binding_id, str)
            or not binding_id
            or binding_id in seen
            or not all(isinstance(value, dict) for value in (config, official, frozen, parsed))
            or record.get("status") != "json_official_encoder_freeze_bound"
        ):
            raise ConvHardwareExecplanError("freeze bitstream binding record is malformed")
        seen.add(binding_id)
        config_path = _resolve_contained_relative_path(
            freeze_root,
            str(config.get("freeze_path", "")),
            label="freeze bound config path",
        )
        if (
            not config_path.is_file()
            or not isinstance(config.get("sha256"), str)
            or _sha256_file(config_path) != config["sha256"]
        ):
            raise ConvHardwareExecplanError(
                f"freeze bound config differs: {binding_id}"
            )
        bitstream_path = _resolve_contained_relative_path(
            freeze_root,
            str(frozen.get("path", "")),
            label="freeze bound bitstream path",
        )
        try:
            observed = validate_recorded_bitstream_identity(
                bitstream_path, frozen, require_raw_identity=True
            )
            require_same_logical_bitstream(
                official, observed, label=f"freeze binding {binding_id}"
            )
        except BitstreamBindingError as error:
            raise ConvHardwareExecplanError(str(error)) from error
        parsed_path = _resolve_contained_relative_path(
            freeze_root,
            str(parsed.get("freeze_path", "")),
            label="freeze parsed-evidence path",
        )
        if (
            not parsed_path.is_file()
            or not isinstance(parsed.get("sha256"), str)
            or _sha256_file(parsed_path) != parsed["sha256"]
        ):
            raise ConvHardwareExecplanError(
                f"freeze parsed evidence differs: {binding_id}"
            )
        if record.get("role") == "accumulate" and observed["line_width_bits"] != 128:
            raise ConvHardwareExecplanError(
                "first Conv accumulate binding must use 128-bit lines"
            )
    return dict(binding)


def _build_package_bitstream_bindings(
    package_root: Path,
    freeze_binding: Mapping[str, Any],
) -> dict[str, Any]:
    records = freeze_binding.get("records")
    if not isinstance(records, list):
        raise ConvHardwareExecplanError("freeze bitstream binding records are missing")
    installed_records: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise ConvHardwareExecplanError("freeze bitstream binding record is malformed")
        frozen = record.get("freeze")
        official = record.get("official_encoder")
        if not isinstance(frozen, dict) or not isinstance(official, dict):
            raise ConvHardwareExecplanError("freeze bitstream binding record is malformed")
        install_relative = f"install/cfg_pkg/{Path(str(frozen['path'])).name}"
        install_path = package_root / install_relative
        try:
            installed = bitstream_text_identity(install_path, line_width_bits=128)
            require_same_logical_bitstream(
                official,
                installed,
                label=f"package install {record.get('binding_id')}",
            )
        except BitstreamBindingError as error:
            raise ConvHardwareExecplanError(str(error)) from error
        installed_records.append(
            {
                "binding_id": record["binding_id"],
                "config_sha256": record["config"]["sha256"],
                "install": {"path": install_relative, **installed},
            }
        )
    return {
        "schema_version": BITSTREAM_BINDING_SCHEMA_VERSION,
        "status": "json_official_encoder_freeze_install_bound",
        "source_freeze_binding_sha256": _canonical_json_sha256(freeze_binding),
        "record_count": len(installed_records),
        "records": installed_records,
    }


def _typed_request_bitstream_bindings(
    package_root: Path,
) -> dict[str, dict[str, Any]]:
    request = _read_json_object(package_root / "source" / "execplan_request.json")
    operators = request.get("operators")
    if not isinstance(operators, list) or not operators:
        raise ConvHardwareExecplanError("typed request operators are missing")
    accumulate_artifacts = operators[0].get("config_artifacts")
    if not isinstance(accumulate_artifacts, list):
        raise ConvHardwareExecplanError("typed request config artifacts are missing")
    by_role = {
        item.get("role"): item
        for item in accumulate_artifacts
        if isinstance(item, dict) and isinstance(item.get("role"), str)
    }
    config = by_role.get("accumulate_config")
    semantic = by_role.get("semantic_contract")
    if not isinstance(config, dict) or not isinstance(semantic, dict):
        raise ConvHardwareExecplanError(
            "typed request accumulate/semantic artifacts are missing"
        )
    try:
        semantic_contract = json.loads(str(semantic["raw_text"]))
        expected_output = semantic_contract["official_encoder"]["outputs"][
            "modules_dump_128b.bin"
        ]
        expected_config_sha = str(config["sha256"])
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ConvHardwareExecplanError(
            "typed request official encoder binding is malformed"
        ) from error
    if not isinstance(semantic_contract, dict) or (
        semantic_contract.get("config", {}).get("sha256") != expected_config_sha
    ):
        raise ConvHardwareExecplanError(
            "typed request config and semantic contract hashes differ"
        )
    bindings = {
        str(operators[0].get("attributes", {}).get("hw_op_id")) + ".accumulate": {
            "role": "accumulate",
            "config_sha256": expected_config_sha,
            "official_encoder": dict(expected_output),
        }
    }
    if len(operators) < 2 or not isinstance(operators[1], Mapping):
        raise ConvHardwareExecplanError("typed request requant operator is missing")
    requant_artifacts = operators[1].get("config_artifacts")
    if not isinstance(requant_artifacts, list):
        raise ConvHardwareExecplanError(
            "typed request requant config artifacts are missing"
        )
    contract_artifacts = [
        item
        for item in requant_artifacts
        if isinstance(item, Mapping)
        and item.get("role") == "requant_encoder_contract"
    ]
    if len(contract_artifacts) != 1:
        raise ConvHardwareExecplanError(
            "typed request must contain exactly one requant encoder contract"
        )
    try:
        encoder_contract = json.loads(str(contract_artifacts[0]["raw_text"]))
        contract_records = encoder_contract["records"]
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ConvHardwareExecplanError(
            "typed request requant encoder contract is malformed"
        ) from error
    if (
        not isinstance(encoder_contract, dict)
        or encoder_contract.get("status") != "official_encoder_double_run_bound"
        or not isinstance(contract_records, list)
        or encoder_contract.get("record_count") != len(contract_records)
    ):
        raise ConvHardwareExecplanError(
            "typed request requant encoder contract differs"
        )
    for record in contract_records:
        if not isinstance(record, Mapping):
            raise ConvHardwareExecplanError(
                "typed request requant encoder record is malformed"
            )
        binding_id = record.get("binding_id")
        config_record = record.get("config")
        outputs = record.get("official_encoder")
        if (
            not isinstance(binding_id, str)
            or not isinstance(config_record, Mapping)
            or not isinstance(outputs, Mapping)
            or not isinstance(outputs.get("modules_dump_128b.bin"), Mapping)
            or not isinstance(outputs.get("parsed_bitstream.txt"), Mapping)
            or record.get("repeat_outputs_identical") is not True
        ):
            raise ConvHardwareExecplanError(
                "typed request requant encoder record is malformed"
            )
        bindings[binding_id] = {
            "role": "requant",
            "config_sha256": config_record.get("sha256"),
            "official_encoder": dict(outputs["modules_dump_128b.bin"]),
            "parsed_evidence": dict(outputs["parsed_bitstream.txt"]),
            "encoder_contract_sha256": str(contract_artifacts[0].get("sha256")),
        }
    return bindings


def _validate_package_bitstream_bindings(
    package_root: Path,
    manifest: Mapping[str, Any],
) -> None:
    package_binding = manifest.get("bitstream_bindings")
    if not isinstance(package_binding, dict):
        raise ConvHardwareExecplanError("package bitstream binding contract is missing")
    source_freeze = _read_json_object(package_root / "source" / "freeze_manifest.json")
    freeze_binding = source_freeze.get("bitstream_bindings")
    if not isinstance(freeze_binding, dict):
        raise ConvHardwareExecplanError("source freeze bitstream binding is missing")
    package_records = package_binding.get("records")
    freeze_records = freeze_binding.get("records")
    if (
        package_binding.get("schema_version") != BITSTREAM_BINDING_SCHEMA_VERSION
        or package_binding.get("status")
        != "json_official_encoder_freeze_install_bound"
        or package_binding.get("source_freeze_binding_sha256")
        != _canonical_json_sha256(freeze_binding)
        or not isinstance(package_records, list)
        or not isinstance(freeze_records, list)
        or package_binding.get("record_count") != len(package_records)
        or len(package_records) != len(freeze_records)
    ):
        raise ConvHardwareExecplanError("package bitstream binding contract differs")
    freeze_by_id = {
        item.get("binding_id"): item
        for item in freeze_records
        if isinstance(item, dict)
    }
    typed_bindings = _typed_request_bitstream_bindings(package_root)
    for package_record in package_records:
        if not isinstance(package_record, dict):
            raise ConvHardwareExecplanError("package bitstream binding record is malformed")
        binding_id = package_record.get("binding_id")
        source_record = freeze_by_id.get(binding_id)
        install = package_record.get("install")
        if not isinstance(source_record, dict) or not isinstance(install, dict):
            raise ConvHardwareExecplanError("package bitstream binding record is malformed")
        if package_record.get("config_sha256") != source_record.get("config", {}).get(
            "sha256"
        ):
            raise ConvHardwareExecplanError(
                f"package bound config hash differs: {binding_id}"
            )
        expected_binding = typed_bindings.get(str(binding_id))
        if not isinstance(expected_binding, Mapping):
            raise ConvHardwareExecplanError(
                f"package bitstream lacks a typed JSON/encoder binding: {binding_id}"
            )
        if package_record.get("config_sha256") != expected_binding.get(
            "config_sha256"
        ):
            raise ConvHardwareExecplanError(
                f"package config differs from the typed encoder contract: {binding_id}"
            )
        install_path = _resolve_contained_relative_path(
            package_root,
            str(install.get("path", "")),
            label="package bound install bitstream path",
        )
        try:
            installed = validate_recorded_bitstream_identity(
                install_path, install, require_raw_identity=True
            )
            require_same_logical_bitstream(
                source_record["official_encoder"],
                installed,
                label=f"package binding {binding_id}",
            )
        except BitstreamBindingError as error:
            raise ConvHardwareExecplanError(str(error)) from error
        if source_record.get("role") == "accumulate":
            official = source_record.get("official_encoder", {})
            expected_accumulate = expected_binding["official_encoder"]
            extended_identity_fields = (
                "raw_size_bytes",
                "raw_sha256",
                "logical_size_bytes",
                "logical_sha256",
                "line_count",
                "line_width_bits",
            )
            declares_extended_identity = any(
                field in expected_accumulate for field in extended_identity_fields
            )
            extended_identity_differs = declares_extended_identity and (
                not all(
                    field in expected_accumulate
                    for field in extended_identity_fields
                )
                or any(
                    official.get(field) != expected_accumulate[field]
                    for field in extended_identity_fields
                )
            )
            if (
                official.get("raw_sha256") != expected_accumulate.get("sha256")
                or official.get("raw_size_bytes")
                != expected_accumulate.get("size_bytes")
                or extended_identity_differs
            ):
                raise ConvHardwareExecplanError(
                    "package accumulate JSON/official encoder/install binding differs"
                )
        elif source_record.get("role") == "requant":
            official = source_record.get("official_encoder", {})
            parsed = source_record.get("parsed_evidence", {})
            if (
                expected_binding.get("role") != "requant"
                or any(
                    official.get(field)
                    != expected_binding["official_encoder"].get(field)
                    for field in BITSTREAM_IDENTITY_FIELDS
                )
                or official.get("encoder_contract_sha256")
                != expected_binding.get("encoder_contract_sha256")
                or parsed.get("sha256")
                != expected_binding["parsed_evidence"].get("sha256")
            ):
                raise ConvHardwareExecplanError(
                    "package requant JSON/official encoder/install binding differs: "
                    f"{binding_id}"
                )
        else:
            raise ConvHardwareExecplanError(
                f"unsupported package bitstream binding role: {binding_id}"
            )


def _region_index(address_table: Mapping[str, Any]) -> dict[tuple[int, str], dict[str, Any]]:
    result: dict[tuple[int, str], dict[str, Any]] = {}
    for region in address_table["regions"]:
        key = (int(region["slice_id"]), str(region["port"]))
        if key in result:
            raise ConvHardwareExecplanError(f"duplicate address region: {key}")
        result[key] = region
    return result


def _assignment(
    api: Mapping[str, Any],
    regions: Mapping[tuple[int, str], Mapping[str, Any]],
    *,
    tensor_name: str,
    port: str,
    slice_ids: list[int],
    shape: tuple[int, int, int],
    local_offset: int | None = None,
    size_bytes: int | None = None,
) -> Any:
    per_slice: dict[int, int] = {}
    for slice_id in slice_ids:
        freeze_base = int(regions[(slice_id, port)]["base_address"])
        region_local = _freeze_local_offset(freeze_base, slice_id)
        effective_local = region_local if local_offset is None else local_offset
        per_slice[slice_id] = _execplan_address(slice_id, effective_local)
    first = regions[(slice_ids[0], port)]
    if local_offset is None:
        local_offset = _freeze_local_offset(int(first["base_address"]), slice_ids[0])
    if size_bytes is None:
        size_bytes = int(first["size_bytes"])
    return api["AddressAssignment"](
        tensor_name=tensor_name,
        base_address=local_offset,
        per_slice_addresses=per_slice,
        size_bytes=size_bytes,
        shape=shape,
    )


def _decode_template_state(
    api: Mapping[str, Any], project_root: Path, parsed_path: Path
) -> tuple[dict[int, int], frozenset[int]]:
    config_root = project_root / "ndp-sim-ref/model_execplan/config"
    register_db = api["load_register_mapping"](
        config_root / "register_map_with_groups1.csv",
        config_root / "config_output.csv",
        reorder_const_fields=True,
        map_const_fields_to_const_addresses=True,
    )
    stream = api["load_template_config_stream"](
        {"bitstream_file": parsed_path.name}, parsed_path.parent, register_db
    )
    state = api["decode_initial_register_state"](stream, register_db)
    return dict(state.register_values), frozenset(state.enabled_register_addresses)


def _copy_load_inputs(
    freeze_root: Path,
    output_root: Path,
    address_table: Mapping[str, Any],
) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for region in address_table["regions"]:
        if region.get("role") != "load_input":
            continue
        file_info = region.get("file")
        if not isinstance(file_info, dict) or not isinstance(file_info.get("path"), str):
            raise ConvHardwareExecplanError("load_input region is missing its frozen file")
        source = _resolve_contained_relative_path(
            freeze_root,
            file_info["path"],
            label="frozen SCA input payload path",
        )
        port = str(region["port"])
        slice_id = int(region["slice_id"])
        relative = Path("install/data") / port / f"slice-{slice_id:02d}.txt"
        destination = output_root / relative
        if _sha256_file(source) != str(file_info["sha256"]):
            raise ConvHardwareExecplanError(f"frozen input differs: {file_info['path']}")
        line_count, first_128bit = _write_128bit_binary_text(source, destination)
        if line_count * 16 != int(region["size_bytes"]):
            raise ConvHardwareExecplanError(
                f"SCA input transport size differs: {relative.as_posix()}"
            )
        entries.append(
            {
                "key": f"freeze_{port}_slice{slice_id}",
                "base_addr": f"0x{_execplan_address(slice_id, _freeze_local_offset(int(region['base_address']), slice_id)):08X}",
                "freeze_base_addr": f"0x{int(region['base_address']):08X}",
                "path": relative.as_posix(),
                "port": port,
                "slice_id": slice_id,
                "size_bytes": int(region["size_bytes"]),
                "line_count_128bit": line_count,
                "expected_first_128bit": first_128bit,
                "source_sha256": str(file_info["sha256"]),
                "transport_sha256": _sha256_file(destination),
            }
        )
    expected_count = len(
        [region for region in address_table["regions"] if region.get("role") == "load_input"]
    )
    if len(entries) != expected_count:
        raise ConvHardwareExecplanError(
            f"expected {expected_count} load inputs, got {len(entries)}"
        )
    return entries


def _validate_payload_intervals(sca: Mapping[str, Any], root: Path) -> None:
    by_slice_bank: dict[tuple[int, int], list[tuple[int, int, str]]] = {}
    segmented: dict[str, list[tuple[int, Mapping[str, Any], bytes]]] = {}
    for key, value in _sca_transport_entries(sca):
        relative = value.get("path")
        if not isinstance(relative, str):
            raise ConvHardwareExecplanError(f"SCA transfer path is missing: {key}")
        path = _resolve_contained_relative_path(
            root,
            relative,
            label=f"SCA payload path ({key})",
        )
        if not path.is_file():
            raise ConvHardwareExecplanError(f"SCA payload is missing: {relative}")
        try:
            address = int(str(value["base_addr"]).replace("_", ""), 16)
        except (KeyError, ValueError) as error:
            raise ConvHardwareExecplanError(f"invalid SCA transfer address: {key}") from error
        lines = _read_128bit_binary_lines(path)
        _validate_axi4_burst_sequence(address, len(lines), label=f"SCA {key}")
        data = b"".join(
            int(line, 2).to_bytes(AXI_DATA_BYTES, byteorder="little")
            for line in lines
        )
        slice_id = (address >> 25) & 0x1F
        bank_id = (address >> 23) & 0x03
        offset = address & ((1 << 23) - 1)
        end = offset + len(data)
        by_slice_bank.setdefault((slice_id, bank_id), []).append((offset, end, key))

        semantic_key = value.get("semantic_key")
        segment_index = value.get("axi4_segment_index")
        if semantic_key is not None or segment_index is not None:
            if (
                not isinstance(semantic_key, str)
                or isinstance(segment_index, bool)
                or not isinstance(segment_index, int)
            ):
                raise ConvHardwareExecplanError(f"invalid AXI segment metadata: {key}")
            segmented.setdefault(semantic_key, []).append((segment_index, value, data))
    for location, intervals in by_slice_bank.items():
        ordered = sorted(intervals)
        for left, right in zip(ordered, ordered[1:]):
            if left[1] > right[0]:
                raise ConvHardwareExecplanError(
                    f"SCA payload overlap at slice/bank {location}: {left[2]} and {right[2]}"
                )

    for semantic_key, segment_records in segmented.items():
        ordered = sorted(segment_records, key=lambda item: item[0])
        try:
            expected_count = int(ordered[0][1]["axi4_segment_count"])
            semantic_path = str(ordered[0][1]["semantic_path"])
        except (KeyError, TypeError, ValueError) as error:
            raise ConvHardwareExecplanError(
                f"incomplete AXI segment metadata: {semantic_key}"
            ) from error
        if (
            expected_count != len(ordered)
            or [index for index, _, _ in ordered] != list(range(expected_count))
            or expected_count != 2
        ):
            raise ConvHardwareExecplanError(
                f"AXI segment set is incomplete: {semantic_key}"
            )
        if any(
            int(record.get("axi4_segment_count", -1)) != expected_count
            or str(record.get("semantic_path")) != semantic_path
            for _, record, _ in ordered
        ):
            raise ConvHardwareExecplanError(
                f"AXI segment metadata differs within {semantic_key}"
            )
        first_address = int(str(ordered[0][1]["base_addr"]).replace("_", ""), 16)
        second_address = int(str(ordered[1][1]["base_addr"]).replace("_", ""), 16)
        if (
            first_address + len(ordered[0][2]) != second_address
            or second_address % AXI_4KB_BYTES
        ):
            raise ConvHardwareExecplanError(
                f"AXI segment boundary is not contiguous/page-aligned: {semantic_key}"
            )
        semantic_file = _resolve_contained_relative_path(
            root,
            semantic_path,
            label=f"semantic SCA payload path ({semantic_key})",
        )
        semantic_data = b"".join(
            int(line, 2).to_bytes(AXI_DATA_BYTES, byteorder="little")
            for line in _read_128bit_binary_lines(semantic_file)
        )
        if b"".join(payload for _, _, payload in ordered) != semantic_data:
            raise ConvHardwareExecplanError(
                f"AXI segments do not reconstruct the semantic payload: {semantic_key}"
            )


def _output_hashes(output_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(output_root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        records.append(
            {
                "path": path.relative_to(output_root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )
    return records


def _physical_tensor_shape(region: Mapping[str, Any]) -> tuple[int, ...]:
    shape = tuple(int(item) for item in region.get("physical_shape", []))
    if len(shape) == 1:
        return (1, 1, shape[0])
    if not shape:
        raise ConvHardwareExecplanError(f"unsupported physical tensor shape: {shape}")
    return shape


def _single_path(paths: list[Path], *, label: str) -> Path:
    if len(paths) != 1 or not paths[0].is_file():
        raise ConvHardwareExecplanError(f"{label} must resolve to one file: {paths}")
    return paths[0]


def generate_conv_hardware_execplan(
    project_root: Path,
    output_root: Path,
    *,
    node_id: str,
    freeze_root: Path,
    execplan_request_path: Path,
    legacy_fixed_pair_observer: bool = False,
) -> dict[str, Any]:
    root = project_root.resolve()
    target_request = build_conv_target_request(root, node_id)
    spec = target_request.spec
    selected_freeze = freeze_root.resolve()
    destination = output_root.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ConvHardwareExecplanError(
            f"output directory is not empty; refusing to mix evidence: {destination}"
        )
    destination.mkdir(parents=True, exist_ok=True)

    freeze_manifest, address_table = _verify_freeze(
        selected_freeze, expected_node_id=node_id
    )
    request_path = execplan_request_path.resolve()
    request = _read_json_object(request_path)
    transport_report = validate_conv_execplan_request(
        request, root, expected_node_id=node_id
    )
    api = _load_execplan_api(root)
    regions = _region_index(address_table)
    requant_manifest = _read_json_object(
        selected_freeze / "configs/requant/manifest.json"
    )
    shards = requant_manifest.get("shards")
    if not isinstance(shards, list) or len(shards) != spec.requant_shard_count:
        raise ConvHardwareExecplanError(
            f"requant freeze must contain {spec.requant_shard_count} shards"
        )
    ordered_shards = (
        _legacy_fixed_pair_requant_order(shards)
        if legacy_fixed_pair_observer
        else shards
    )

    external = api["InputSource"](api["InputSourceType"].EXTERNAL)
    all_slice_ids = list(range(28))
    weight_shape = _physical_tensor_shape(regions[(0, "B")])
    activation_shape = _physical_tensor_shape(regions[(0, "A")])
    bias_shape = _physical_tensor_shape(regions[(0, "bias")])
    p_shape = _physical_tensor_shape(regions[(0, "P")])
    waves = _accumulate_batch_waves()
    if (
        sum(GROUP_SAMPLE_COUNTS) != spec.batch_size
        or activation_shape[0] != len(waves)
        or p_shape[0] != len(waves)
    ):
        raise ConvHardwareExecplanError(
            "physical batch storage differs from the reviewed 3-wave HIGH-ring schedule"
        )
    activation_sample_shape = (1, *activation_shape[1:])
    p_sample_shape = (1, *p_shape[1:])
    activation_slot_bytes = math.prod(activation_sample_shape)
    p_slot_bytes = math.prod(p_sample_shape) * 4
    activation_region_local = _freeze_local_offset(
        int(regions[(0, "A")]["base_address"]), 0
    )
    p_region_local = _freeze_local_offset(int(regions[(0, "P")]["base_address"]), 0)
    if (
        int(regions[(0, "A")]["size_bytes"])
        != activation_slot_bytes * len(waves)
        or int(regions[(0, "P")]["size_bytes"]) != p_slot_bytes * len(waves)
    ):
        raise ConvHardwareExecplanError(
            "physical A/P regions do not contain exactly three local sample slots"
        )
    instance_id = (
        f"conv:{node_id}:{spec.accumulate_hw_op_id}+{spec.requant_hw_op_id}"
    )
    operators: list[Any] = []
    assignments: dict[str, Any] = {}
    io_map: dict[str, str] = {}

    # The physical packer and target stream ABI now share one orientation:
    # stream0/A is Q8xC4 activation, stream1/B is K8xC4 weight, and C is K8
    # bias.  Crossing A/B here would silently reintroduce the v8 mismatch.
    accumulate_ports = {"A": "A", "B": "B", "C": "bias"}
    accumulate_shapes = {
        "A": activation_sample_shape,
        "B": weight_shape,
        "C": bias_shape,
    }
    accumulate_ids: list[str] = []
    runtime_accumulate_waves: list[dict[str, Any]] = []
    for wave in waves:
        wave_index = int(wave["wave_index"])
        slice_ids = list(wave["slice_ids"])
        accumulate_id = f"{spec.accumulate_hw_op_id}.accumulate-wave-{wave_index}"
        accumulate_ids.append(accumulate_id)
        operators.append(
            api["OperatorSpec"](
                op_id=accumulate_id,
                op_type="resnet_qlinearconv_int32_accumulate",
                used_slices=int(wave["slice_mask"]),
                inputs={
                    "A": api["TensorSpec"](
                        activation_sample_shape, dtype="uint8", source=external
                    ),
                    "B": api["TensorSpec"](
                        weight_shape, dtype="int8", source=external
                    ),
                    "C": api["TensorSpec"](
                        bias_shape, dtype="int32", source=external
                    ),
                },
                output=api["TensorSpec"](p_sample_shape, dtype="int32"),
                instance_id=instance_id,
                stage="accumulate",
                attributes={
                    "wave_index": wave_index,
                    "local_sample_index": int(wave["local_sample_index"]),
                    "group_ids": list(wave["group_ids"]),
                    "logical_samples": list(wave["logical_samples"]),
                },
            )
        )
        for input_name, port in accumulate_ports.items():
            tensor_name = f"freeze.{port}.wave-{wave_index}"
            assignment_options: dict[str, Any] = {}
            if port == "A":
                assignment_options = {
                    "local_offset": (
                        activation_region_local + wave_index * activation_slot_bytes
                    ),
                    "size_bytes": activation_slot_bytes,
                }
            assignments[tensor_name] = _assignment(
                api,
                regions,
                tensor_name=tensor_name,
                port=port,
                slice_ids=slice_ids,
                shape=accumulate_shapes[input_name],
                **assignment_options,
            )
            io_map[f"{accumulate_id}.input.{input_name}"] = tensor_name
        p_tensor = f"freeze.P.wave-{wave_index}"
        assignments[p_tensor] = _assignment(
            api,
            regions,
            tensor_name=p_tensor,
            port="P",
            slice_ids=slice_ids,
            shape=p_sample_shape,
            local_offset=p_region_local + wave_index * p_slot_bytes,
            size_bytes=p_slot_bytes,
        )
        io_map[f"{accumulate_id}.output.D"] = p_tensor
        runtime_accumulate_waves.append(
            {
                "operator_id": accumulate_id,
                "wave_index": wave_index,
                "local_sample_index": int(wave["local_sample_index"]),
                "group_ids": list(wave["group_ids"]),
                "logical_samples": list(wave["logical_samples"]),
                "slice_ids": slice_ids,
                "slice_mask": f"0x{int(wave['slice_mask']):07X}",
                "activation_local_offset": (
                    activation_region_local + wave_index * activation_slot_bytes
                ),
                "p_local_offset": p_region_local + wave_index * p_slot_bytes,
                "activation_slot_bytes": activation_slot_bytes,
                "p_slot_bytes": p_slot_bytes,
            }
        )

    runtime_shards: list[dict[str, Any]] = []
    for shard in ordered_shards:
        if not isinstance(shard, dict):
            raise ConvHardwareExecplanError("requant shard entry is malformed")
        shard_index = int(shard["shard_index"])
        slice_ids = [int(value) for value in shard["selected_slices"]]
        original_selected_slices = [
            int(value) for value in shard.get("original_selected_slices", slice_ids)
        ]
        runtime_partition = shard.get("runtime_partition")
        if runtime_partition is not None and runtime_partition not in {
            "non_observer_slices",
            "finish_slice_only",
        }:
            raise ConvHardwareExecplanError("requant runtime partition is invalid")
        local_half = int(shard["local_half"])
        staged_port = f"staged_D_{local_half}"
        staged_shape = _physical_tensor_shape(regions[(slice_ids[0], staged_port)])
        requant_shape = (
            p_shape[0],
            spec.output_height,
            spec.output_width,
            spec.ga_lane_count,
        )
        if staged_shape != requant_shape:
            raise ConvHardwareExecplanError(
                f"requant shard shape differs: expected={requant_shape}, observed={staged_shape}"
            )
        op_id = f"{spec.requant_hw_op_id}.requant-{shard_index:02d}"
        if runtime_partition is not None:
            op_id += f".{runtime_partition}"
        op = api["OperatorSpec"](
            op_id=op_id,
            op_type="resnet_qlinearconv_uint8_requant",
            used_slices=_mask(slice_ids),
            inputs={
                "A": api["TensorSpec"](
                    requant_shape,
                    dtype="int32",
                    source=api["InputSource"](
                        api["InputSourceType"].OPERATOR,
                        operator_id=accumulate_ids[-1],
                    ),
                )
            },
            output=api["TensorSpec"](requant_shape, dtype="uint8"),
            instance_id=instance_id,
            stage="requantize",
            attributes={
                "shard_index": shard_index,
                "selected_slices": slice_ids,
                "original_selected_slices": original_selected_slices,
                "runtime_partition": runtime_partition,
            },
        )
        operators.append(op)
        tensor_suffix = f"shard-{shard_index:02d}"
        if runtime_partition is not None:
            tensor_suffix += f".{runtime_partition}"
        input_tensor = f"freeze.P.{tensor_suffix}"
        output_port = staged_port
        output_tensor = f"freeze.{output_port}.{tensor_suffix}"
        assignments[input_tensor] = _assignment(
            api,
            regions,
            tensor_name=input_tensor,
            port="P",
            slice_ids=slice_ids,
            shape=requant_shape,
            local_offset=int(shard["p_base_offset"]),
            size_bytes=math.prod(requant_shape) * 4,
        )
        assignments[output_tensor] = _assignment(
            api,
            regions,
            tensor_name=output_tensor,
            port=output_port,
            slice_ids=slice_ids,
            shape=requant_shape,
            local_offset=int(shard["staged_d_base_offset"]),
            size_bytes=int(shard["staged_d_size_bytes"]),
        )
        io_map[f"{op_id}.input.A"] = input_tensor
        io_map[f"{op_id}.output.D"] = output_tensor
        runtime_shards.append(
            {
                "operator_id": op_id,
                "shard_index": shard_index,
                "slice_ids": slice_ids,
                "slice_mask": f"0x{_mask(slice_ids):07X}",
                "original_selected_slices": original_selected_slices,
                "runtime_partition": runtime_partition,
                "p_base_offset": int(shard["p_base_offset"]),
                "staged_d_base_offset": int(shard["staged_d_base_offset"]),
                "local_half": local_half,
            }
        )

    testbench_observer = (
        _legacy_fixed_pair_observer_contract(operators)
        if legacy_fixed_pair_observer
        else {
            "mode": "mask_aware_runtime_stage_markers",
            "repeat_num": len(operators),
            "runtime_stage_count": len(operators),
        }
    )

    execution_input = api["ExecutionPlanInput"](
        used_slices=ALL_SLICES_MASK,
        operators=operators,
        schema_version="resnet50-conv-hardware-execplan-0.2",
        plan_id=f"{node_id}-{freeze_manifest['freeze_id']}",
    )

    accumulate_bitstream = _single_path(
        sorted((selected_freeze / "bitstreams/accumulate").glob("*_128b.bin")),
        label="accumulate 128-bit bitstream",
    )
    requant_runtime_order = [int(item["shard_index"]) for item in runtime_shards]
    bitstream_paths = [accumulate_bitstream] * len(accumulate_ids) + [
        selected_freeze / f"bitstreams/requant/shard-{index:02d}_bitstream_128b.bin"
        for index in requant_runtime_order
    ]
    parsed_paths = [
        selected_freeze / "encoder_evidence/accumulate/parsed_bitstream.txt"
    ] * len(accumulate_ids) + [
        selected_freeze
        / f"encoder_evidence/requant/shard-{index:02d}/parsed_bitstream.txt"
        for index in requant_runtime_order
    ]
    config_lengths = [_binary_line_count(path, 128) * 2 for path in bitstream_paths]
    if any(length * 8 > ROW_BYTES for length in config_lengths):
        raise ConvHardwareExecplanError(
            f"config payload exceeds one reserved row: {config_lengths}"
        )

    slice0_end = max(
        int(item["base_address"]) + int(item["size_bytes"])
        for item in address_table["regions"]
        if int(item["slice_id"]) == 0
    )
    config_start = _align_up(slice0_end, ROW_BYTES)
    config_bases = [
        config_start + index * ROW_BYTES for index in range(len(operators))
    ]
    exec_base = config_start + len(operators) * ROW_BYTES
    op_ids = [operator.op_id for operator in operators]
    address_plan = api["AddressPlan"](
        assignments=assignments,
        operator_io_to_tensor=io_map,
        operator_config_base_addresses=dict(zip(op_ids, config_bases)),
        operator_config_lengths=dict(zip(op_ids, config_lengths)),
    )

    templates: dict[str, Any] = {}
    for operator, bitstream_path, parsed_path, config_length in zip(
        operators, bitstream_paths, parsed_paths, config_lengths
    ):
        if not parsed_path.is_file():
            raise ConvHardwareExecplanError(f"parsed encoder evidence is missing: {parsed_path}")
        original_values, enabled_addresses = _decode_template_state(api, root, parsed_path)
        templates[operator.op_id] = api["OperatorTemplate"](
            op_type=operator.op_type,
            config_length=config_length,
            config_bitstream_path=str(bitstream_path),
            should_update_control_registers=False,
            original_register_values=original_values,
            enabled_register_addresses=enabled_addresses,
        )

    artifact = api["InstructionGenerator"]().generate(
        execution_input, address_plan, templates
    )
    artifact = _insert_runtime_completion_barriers(api, artifact, operators)
    if (
        artifact.metadata.get("clock_enable_count") != "1"
        or artifact.metadata.get("load_config_count") != str(len(operators))
        or artifact.metadata.get("start_comp_count") != str(len(operators))
        or artifact.metadata.get("barrier_count") != str(len(operators))
        or artifact.metadata.get("barrier_opcode")
        != f"0b{RUNTIME_BARRIER_OPCODE:03b}"
        or artifact.metadata.get("unresolved_control_names")
    ):
        raise ConvHardwareExecplanError(
            f"generated instruction metadata differs: {artifact.metadata}"
        )

    exec_path, explanation_path = api["write_instruction_outputs"](
        artifact, destination
    )
    sca_path = api["write_install_manifest"](
        execution_input,
        address_plan,
        templates,
        artifact,
        destination,
        exec_base_addr=exec_base,
    )
    load_entries = _copy_load_inputs(selected_freeze, destination, address_table)

    official_sca = _read_json_object(sca_path)
    sca: dict[str, Any] = {
        "Exec_Base": official_sca["Exec_Base"],
        "Exec_Length": official_sca["Exec_Length"],
        "Repeat_Num": int(testbench_observer["repeat_num"]),
        "ExecutionPlan": official_sca["ExecutionPlan"],
    }
    for key, value in official_sca.items():
        if key.endswith("_config"):
            sca[key] = value
    for entry in load_entries:
        sca[entry["key"]] = {
            "base_addr": entry["base_addr"],
            "path": entry["path"],
        }
    sca, preload_segments, bank_export_sca = _split_sca_preload_transfers(
        sca,
        destination,
    )
    _write_json(sca_path, sca)
    _validate_payload_intervals(sca, destination)
    bank_export_sca_path = destination / "sca_cfg.bank-export.json"
    _write_json(bank_export_sca_path, bank_export_sca)
    try:
        bank_paths = api["export_bank_data"](
            bank_export_sca_path,
            destination / "Bank_data",
            line_width_bits=32,
            output_format="binary",
        )
    finally:
        bank_export_sca_path.unlink(missing_ok=True)
    if len(bank_paths) != 28:
        raise ConvHardwareExecplanError(f"expected 28 Bank_data files, got {len(bank_paths)}")

    staged_half_count = len(freeze_manifest["layout"]["staged_d_offsets"])
    scratch_entries: list[dict[str, Any]] = []
    scratch_sca: dict[str, Any] = {}
    zero_path_by_size: dict[int, str] = {}
    for slice_id in all_slice_ids:
        scratch_regions = [("P", regions[(slice_id, "P")])]
        scratch_regions.extend(
            (f"staged_D_{half}", regions[(slice_id, f"staged_D_{half}")])
            for half in range(staged_half_count)
        )
        for port, region in scratch_regions:
            size_bytes = int(region["size_bytes"])
            relative_path = zero_path_by_size.get(size_bytes)
            if relative_path is None:
                relative_path = f"install/runtime_scratch/zero-{size_bytes}-bytes.txt"
                _write_zero_128bit_binary_text(destination / relative_path, size_bytes)
                zero_path_by_size[size_bytes] = relative_path
            local_offset = _freeze_local_offset(int(region["base_address"]), slice_id)
            base_addr = f"0x{_execplan_address(slice_id, local_offset):08X}"
            key = f"runtime_scratch_{port}_slice{slice_id}"
            scratch_sca[key] = {"base_addr": base_addr, "path": relative_path}
            scratch_entries.append(
                {
                    "key": key,
                    "port": port,
                    "slice_id": slice_id,
                    "base_addr": base_addr,
                    "path": relative_path,
                    "size_bytes": size_bytes,
                }
            )
    split_scratch_sca, scratch_segments, _ = _split_sca_preload_transfers(
        scratch_sca,
        destination,
    )
    sca.update(split_scratch_sca)
    preload_segments.update(scratch_segments)
    if len([key for key in sca if key.endswith("_config")]) != len(operators):
        raise ConvHardwareExecplanError(
            f"SCA manifest does not contain {len(operators)} config payloads"
        )
    forbidden_paths = ("physical/P/", "physical/D/", "staged_D", "golden/")
    for value in sca.values():
        if isinstance(value, dict) and isinstance(value.get("path"), str):
            if any(token in value["path"] for token in forbidden_paths):
                raise ConvHardwareExecplanError(f"golden/output payload leaked into SCA: {value}")
    _write_json(sca_path, sca)
    _validate_payload_intervals(sca, destination)

    staged_shapes = [
        list(regions[(0, f"staged_D_{half}")]["physical_shape"])
        for half in range(staged_half_count)
    ]
    physical_d_shape = list(regions[(0, "D")]["physical_shape"])
    dump_contract: dict[str, Any] = {
        "schema_version": "resnet50-conv-hardware-dump-0.1",
        "node_id": node_id,
        "slice_count": len(all_slice_ids),
        "staged_halves_per_slice": staged_half_count,
        "address_encoding": "slave[29:25],bank[24:23],row[22:10],col[9:4],subword[3:0]",
        "P": [],
        "staged_D": [],
        "canonical_D_merge": {
            "input_shapes": staged_shapes,
            "output_shape": physical_d_shape,
            "operation": (
                f"concatenate staged_D_0 through staged_D_{staged_half_count - 1} "
                "along NHWK channel axis, then reshape to "
                "NH-Qblock-Q8-Kblock-K8"
            ),
        },
    }
    for slice_id in all_slice_ids:
        p = regions[(slice_id, "P")]
        p_local = _freeze_local_offset(int(p["base_address"]), slice_id)
        dump_contract["P"].append(
            {
                "slice_id": slice_id,
                "base_addr": f"0x{_execplan_address(slice_id, p_local):08X}",
                "freeze_base_addr": f"0x{int(p['base_address']):08X}",
                "local_offset": p_local,
                "size_bytes": int(p["size_bytes"]),
                "dtype": "int32",
                "shape": list(p["physical_shape"]),
            }
        )
        for half in range(staged_half_count):
            staged = regions[(slice_id, f"staged_D_{half}")]
            staged_local = _freeze_local_offset(int(staged["base_address"]), slice_id)
            dump_contract["staged_D"].append(
                {
                    "slice_id": slice_id,
                    "local_half": half,
                    "base_addr": f"0x{_execplan_address(slice_id, staged_local):08X}",
                    "freeze_base_addr": f"0x{int(staged['base_address']):08X}",
                    "local_offset": staged_local,
                    "size_bytes": int(staged["size_bytes"]),
                    "dtype": "uint8",
                    "shape": list(staged["physical_shape"]),
                }
            )
    _write_json(destination / "dump_contract.json", dump_contract)

    # The model_execplan helper emits one region per active runtime operator.
    # That leaves inactive P padding unobserved and cannot prove that an
    # out-of-mask write did not corrupt it.  The server acceptance package
    # therefore requests each complete semantic P region plus both staged-D
    # halves for every slice.
    sca_d: dict[str, Any] = {}
    for entry in dump_contract["P"]:
        slice_id = int(entry["slice_id"])
        size_bytes = int(entry["size_bytes"])
        if size_bytes % 16:
            raise ConvHardwareExecplanError(
                f"P dump size is not 128-bit aligned: slice={slice_id}, bytes={size_bytes}"
            )
        sca_d[f"final_P_slice{slice_id}"] = {
            "base_addr": entry["base_addr"],
            "length": size_bytes // 16,
            "path": f"install/{spec.accumulate_hw_op_id}/final_P/slice-{slice_id:02d}.txt",
        }
    for entry in dump_contract["staged_D"]:
        slice_id = int(entry["slice_id"])
        local_half = int(entry["local_half"])
        size_bytes = int(entry["size_bytes"])
        if size_bytes % 16:
            raise ConvHardwareExecplanError(
                "staged-D dump size is not 128-bit aligned: "
                f"slice={slice_id}, half={local_half}, bytes={size_bytes}"
            )
        sca_d[f"staged_D{local_half}_slice{slice_id}"] = {
            "base_addr": entry["base_addr"],
            "length": size_bytes // 16,
            "path": (
                f"install/{spec.requant_hw_op_id}/staged_D_{local_half}/"
                f"slice-{slice_id:02d}.txt"
            ),
        }
    semantic_dump_region_count = len(sca_d)
    semantic_sca_d = dict(sca_d)
    sca_d = _split_sca_d_transfers(sca_d)
    _write_json(destination / "sca_cfg_D.json", sca_d)
    axi4_4kb_report = _build_axi4_4kb_trigger_report(
        destination,
        preload_segments,
        semantic_sca_d,
        sca_d,
    )
    _write_json(destination / "axi4_4kb_report.json", axi4_4kb_report)

    minimum_dump_bytes = max(
        _freeze_local_offset(int(region["base_address"]), int(region["slice_id"]))
        + int(region["size_bytes"])
        for region in address_table["regions"]
        if region.get("role") in {"golden_output", "hardware_output"}
    )
    preload_probes = [
        {
            "kind": "input",
            "port": entry["port"],
            "slice_id": entry["slice_id"],
            "base_addr": entry["base_addr"],
            "expected_128bit": entry["expected_first_128bit"],
            "sca_key": entry["key"],
            "source_path": str(preload_segments[entry["key"]][0]["path"]),
        }
        for entry in load_entries
        if entry["port"] in {"A", "B", "bias"}
    ]
    preload_probes.extend(
        {
            "kind": "runtime_scratch_zero",
            "port": entry["port"],
            "slice_id": entry["slice_id"],
            "base_addr": entry["base_addr"],
            "expected_128bit": "0x" + "0" * 32,
            "sca_key": entry["key"],
            "source_path": str(preload_segments[entry["key"]][0]["path"]),
        }
        for entry in scratch_entries
    )
    preload_probes.extend(
        [
            {
                "kind": "accumulate_config",
                "base_addr": f"0x{config_bases[0]:08X}",
                "expected_128bit": _first_binary_word_hex(bitstream_paths[0]),
                "source_path": str(
                    preload_segments[f"{op_ids[0]}_config"][0]["path"]
                ),
            },
            {
                "kind": "execution_plan",
                "base_addr": f"0x{exec_base:08X}",
                "expected_128bit": _first_binary_word_hex(exec_path),
                "source_path": str(preload_segments["ExecutionPlan"][0]["path"]),
            },
        ]
    )
    runner_contract: dict[str, Any] = {
        "schema_version": "resnet50-conv-model-execplan-runner-0.1",
        "preload": {
            "preferred_source": "sca_cfg.json",
            "rule": "load exactly one complete source, then pass every readback probe before starting execution",
            "slice_count": 28,
            "sca_cfg": {
                "source": "sca_cfg.json",
                "data_format": "128-bit binary text",
                "line_regex": "^[01]{128}$",
                "word_byte_order": "little-endian",
                "rule": "iterate every entry containing base_addr/path; input files are text, not raw binary",
                "immutable_tb_parser_abi": {
                    "name": "line-oriented-json-close-resets-entry-v1",
                    "load_trigger": "a line containing } with both prior exact base_addr and path fields",
                    "execution_plan_head": "nested chunked_transport closes before the complete semantic path",
                    "execution_plan_outer_close_loads_semantic_path": False,
                    "serialized_order_is_authoritative": True,
                    "validated_transfer_count": len(_sca_transport_entries(sca)),
                },
                "runtime_scratch_rule": (
                    "load every runtime_scratch entry; zero scratch is deterministic memory initialization, "
                    "not Golden/output preload"
                ),
            },
            "bank_data": {
                "source": "Bank_data/",
                "file_pattern": "sliceXX_Bank00_data.txt",
                "line_width_bits": 32,
                "format": "binary",
                "line_regex": "^[01]{32}$",
                "u32_order_within_128bit": "line0 -> bits[31:0], line3 -> bits[127:96]",
                "word_byte_order": "little-endian",
                "rule": (
                    "zero-initialize the complete Bank RAM (or every runtime_scratch range), then load every "
                    "emitted Bank_data file with a binary parser such as $readmemb; do not use $readmemh"
                ),
                "tail_rule": (
                    "Bank_data encodes declared non-scratch payloads and may end before runtime outputs; "
                    "unwritten tail memory must not remain X"
                ),
            },
            "readback_gate": {
                "timing": (
                    "the immutable testbench performs one full-payload write/read compare "
                    "for every validated SCA transport during preload"
                ),
                "required": True,
                "pre_start_abort_required": False,
                "required_scope": (
                    "exact per-payload PASS accounting and final fail-closed acceptance; "
                    "this does not claim a hard pre-Start_Comp abort capability"
                ),
                "probe_width_bits": 128,
                "probe_count": len(preload_probes),
                "probes": preload_probes,
                "completion_runner_evidence": (
                    "require one strict immutable-testbench full-transfer PASS marker per "
                    "validated SCA transport and re-parse the same markers offline; this is "
                    "post-run fail-closed evidence, not a shell-synthesized pre-start interrupt"
                ),
                "failure_action": (
                    "reject the completed or terminated run unless the console contains "
                    "exactly one full-transfer PASS marker for every validated SCA transport; "
                    "never synthesize missing PASS evidence"
                ),
            },
        },
        "execution": {
            "exec_base": f"0x{exec_base:08X}",
            "exec_length_128bit_beats": len(artifact.commands + ([0] if len(artifact.commands) % 2 else [])) // 2,
            "execplan_path": "install/execplan.txt",
            "rule": "start the model_execplan command engine at exec_base and wait until all commands complete",
            "completion_gate": {
                "expected_runtime_stage_count": len(operators),
                "expected_testbench_repeat_num": int(
                    testbench_observer["repeat_num"]
                ),
                "testbench_observer_mode": testbench_observer["mode"],
                "expected_start_comp_count": len(operators),
                "expected_completion_barrier_count": len(operators),
                "completion_barrier_opcode": f"0b{RUNTIME_BARRIER_OPCODE:03b}",
                "expected_runtime_sequence": op_ids,
                "required_markers": (
                    [
                        "INFO: slice start",
                        "INFO: slice completed after",
                        "Simulation completed successfully!",
                    ]
                    if legacy_fixed_pair_observer
                    else [
                        "RUNTIME_STAGE_COMPLETE",
                        "RUNTIME_ALL_STAGES_COMPLETE",
                    ]
                ),
                "testbench_observer": testbench_observer,
                "rule": "advance only after the current stage completion handshake; a fixed sleep or first Start_Comp is not completion",
                "failure_action": "return timeout stage index, last completed stage, and command-engine status without producing a numeric verdict",
            },
        },
        "simulation_preparation": {
            "command": (
                ".venv/Scripts/python.exe tools/prepare_hardware_simulation.py "
                "--package <hardware-execplan-package> --output <preparation-report.json>"
            ),
            "scope": "decode and validate transport/state only; does not execute numerical kernels",
        },
        "server_preload_verification": {
            "availability": "optional_external_environment_capability",
            "required_for_completion_readiness": False,
            "command": (
                ".venv/Scripts/python.exe tools/verify_hardware_server_preload.py "
                "--package <hardware-execplan-package> --readback-root <pre-start-bank-dump-root> "
                "--output <preload-readback-report.json>"
            ),
            "pass_condition": "status=passed, failed_probe_count=0, execution_authorized=true",
            "capability_boundary": (
                "requires a genuine pre-Start_Comp Bank dump and control point supplied by "
                "the immutable server environment; the shell runner must not fabricate either"
            ),
            "rule": (
                "run only when the external server environment exposes a genuine pre-start "
                "dump; its absence does not invalidate the mandatory post-run fail-closed gate"
            ),
        },
        "post_run_dump": {
            "return_mode": "sca_d_regions",
            "sca_cfg": "sca_cfg_D.json",
            "expected_region_count": len(sca_d),
            "semantic_region_count": semantic_dump_region_count,
            "transfer_segment_count": len(sca_d),
            "file_pattern": "paths declared by sca_cfg_D.json",
            "minimum_bytes_per_slice": minimum_dump_bytes,
            "required_slices": all_slice_ids,
            "contract": "dump_contract.json",
            "rule": (
                "after completion, return every full P and staged-D region declared by "
                "sca_cfg_D.json without reloading initial Bank_data over the result regions"
            ),
            "adapter_command": (
                ".venv/Scripts/python.exe tools/compare_conv_hardware_region_dump.py "
                "--package <hardware-execplan-package> "
                "--return-zip-run1 <raw-run1-return.zip> "
                "--return-zip-run2 <raw-run2-return.zip> "
                "--evidence-root <evidence-root> "
                "--runtime-identity <approved-runtime-identity.json>"
            ),
        },
        "comparison_command": (
            ".venv/Scripts/python.exe tools/compare_conv_hardware_region_dump.py "
            "--package <hardware-execplan-package> "
            "--return-zip-run1 <raw-run1-return.zip> "
            "--return-zip-run2 <raw-run2-return.zip> "
            "--evidence-root <evidence-root> "
            "--runtime-identity <approved-runtime-identity.json>"
        ),
        "required_return_metadata": [
            "server_run_id",
            "execution_environment",
            "board_version",
            "simulator_version",
            "rtl_version",
            "firmware_version",
            "isa_contract",
            "run_command",
            "exit_status",
            "process_exit_status",
            "make_exit_status",
            "tee_exit_status",
            "phase_watchdog_exit_status",
            "raw_phase_watchdog_exit_status",
            "phase_watchdog_done",
            "simulator_exit_status",
            "simulator_exit_status_observed",
            "timeout_status",
            "phase_timeout_status",
            "phase_timeout_phase",
            "phase_last_progress",
            "phase_stall_seconds",
            "phase_failure_reason",
            "termination_kind",
            "preflight_status",
            "wall_time_seconds",
            "freeze_id",
            "freeze_manifest_sha256",
            "package_manifest_sha256",
            "server_source_provenance",
            "preload_readback_report",
            "completed_runtime_stage_count",
            "expected_runtime_stage_count",
            "testbench_observer_mode",
            "expected_testbench_repeat_num",
            "observed_slice0_start_count",
            "observed_slice1_finish_count",
            "reserved_clock_force_marker_count",
            "reserved_clock_failure_marker_count",
            "stage_marker_status",
            "all_stages_marker_status",
            "returned_region_count",
            "expected_region_count",
            "readback_region_contract_status",
            "sca_cfg_sha256",
            "sca_cfg_D_sha256",
            "runner_sha256",
            "runner_identity_sha256",
            "testbench_sha256",
            "readback_contract_sha256",
            "stage_contract_sha256",
            "launch_files_contract_sha256",
            "launch_identity_sha256",
            "run_command_contract_sha256",
            "runtime_make_override_sha256",
            "make_archive_policy",
            "runtime_identity_sha256",
            "wall_timeout",
            "bank_frame_logging_policy",
            "reserved_clock_validation",
            "runtime_log_sink_policy",
            "diagnostic_sink_count",
            "diagnostic_return_file_count",
            "diagnostic_return_total_bytes",
            "diagnostic_file_size_limit_bytes",
            "diagnostic_total_size_limit_bytes",
            "return_file_contract",
            "return_archive_policy",
        ],
    }
    _write_json(destination / "runner_contract.json", runner_contract)

    source_dir = destination / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(request_path, source_dir / "execplan_request.json")
    shutil.copy2(selected_freeze / "manifest.json", source_dir / "freeze_manifest.json")
    shutil.copy2(selected_freeze / "address_table.json", source_dir / "address_table.json")

    try:
        source_freeze_reference = selected_freeze.relative_to(root).as_posix()
    except ValueError:
        source_freeze_reference = str(selected_freeze)

    text_file_paths = sorted(
        [*_normalize_package_text_files(destination), "manifest.json"]
    )
    package_bitstream_bindings = _build_package_bitstream_bindings(
        destination, freeze_manifest["bitstream_bindings"]
    )

    report: dict[str, Any] = {
        "schema_version": "resnet50-conv-hardware-execplan-package-0.1",
        "status": "hardware_execplan_package_validated",
        "node_id": node_id,
        "freeze_id": freeze_manifest["freeze_id"],
        "freeze_manifest_sha256": _sha256_file(selected_freeze / "manifest.json"),
        "source_freeze_reference": source_freeze_reference,
        "typed_request_sha256": _sha256_file(request_path),
        "typed_transport": transport_report,
        "bitstream_bindings": package_bitstream_bindings,
        "address_translation": {
            "reason": "freeze uses candidate 24-MiB linear slice stride; model_execplan uses the approved 5-bit slice/slave field",
            "freeze_formula": "freeze_base = slice_id * 0x01800000 + local_offset",
            "execplan_formula": "execplan_base = (slice_id << 25) | local_offset",
            "local_offsets_preserved": True,
        },
        "runtime_operator_count": len(operators),
        "runtime_sequence": [operator.op_id for operator in operators],
        "testbench_observer": testbench_observer,
        "runtime_serialization": {
            "strategy": "post_start_same_mask_barrier",
            "barrier_opcode": f"0b{RUNTIME_BARRIER_OPCODE:03b}",
            "barrier_count": len(operators),
            "placement": "immediately_after_each_Start_Comp",
            "repeat_num_counts_start_comp_only": not legacy_fixed_pair_observer,
            "repeat_num_semantics": (
                "fixed_slice0_start_slice1_finish_pairs"
                if legacy_fixed_pair_observer
                else "runtime_stage_count"
            ),
            "rtl_basis": (
                "global dispatcher atomically waits for every barrier-mask slice to be "
                "ready; immutable Slice_Execution_Manager consumes opcode 0b110 as a "
                "side-effect-free no-op"
            ),
            "purpose": (
                "prevent a disjoint next-stage Start_Comp from outrunning the immutable "
                "testbench's sequential stage observer"
            ),
        },
        "runtime_operators": [
            {
                "operator_id": operator.op_id,
                "operator_type": operator.op_type,
                "stage": operator.stage,
                "instance_id": operator.instance_id,
                "slice_mask": f"0x{operator.used_slices:07X}",
                "attributes": dict(operator.attributes),
            }
            for operator in operators
        ],
        "runtime_io_bindings": {
            **{
                f"{operator_id}.input.A": (
                    "freeze/A local sample slot (activation -> READ_STREAM0)"
                )
                for operator_id in accumulate_ids
            },
            **{
                f"{operator_id}.input.B": (
                    "freeze/B (weight -> READ_STREAM1)"
                )
                for operator_id in accumulate_ids
            },
            **{
                f"{operator_id}.input.C": (
                    "freeze/bias (bias -> READ_STREAM3)"
                )
                for operator_id in accumulate_ids
            },
            **{
                f"{operator_id}.output.D": (
                    "freeze/P local sample slot (int32 -> WRITE_STREAM0)"
                )
                for operator_id in accumulate_ids
            },
            f"{spec.requant_hw_op_id}.requant-XX.input.A": (
                "freeze/P shard (int32 -> READ_STREAM0)"
            ),
            f"{spec.requant_hw_op_id}.requant-XX.output.D": (
                "freeze/staged_D shard (uint8 -> WRITE_STREAM0)"
            ),
        },
        "runtime_accumulate_waves": runtime_accumulate_waves,
        "runtime_shards": runtime_shards,
        "config_lengths_64bit_words": dict(zip(op_ids, config_lengths)),
        "config_base_addresses": {
            op_id: f"0x{base:08X}" for op_id, base in zip(op_ids, config_bases)
        },
        "exec_base_address": f"0x{exec_base:08X}",
        "exec_128bit_line_count": int(sca["Exec_Length"]),
        "instruction_metadata": dict(artifact.metadata),
        "preloaded_input_count": len(load_entries),
        "preloaded_runtime_scratch_count": len(scratch_entries),
        "preloaded_golden_or_output_count": 0,
        "preload_transfer_segment_count": len(_sca_transport_entries(sca)),
        "semantic_dump_region_count": semantic_dump_region_count,
        "sca_d_transfer_segment_count": len(sca_d),
        "bank_data_file_count": len(bank_paths),
        "axi4_4kb": {
            "report_path": "axi4_4kb_report.json",
            "report_sha256": _sha256_file(destination / "axi4_4kb_report.json"),
            "status": axi4_4kb_report["status"],
            "risk_classification": axi4_4kb_report["risk_classification"],
            "semantic_transfer_count": axi4_4kb_report[
                "semantic_transfer_count"
            ],
            "triggered_transfer_count": axi4_4kb_report[
                "triggered_transfer_count"
            ],
        },
        "entry_files": {
            "execplan": exec_path.relative_to(destination).as_posix(),
            "instructions_explained": explanation_path.relative_to(destination).as_posix(),
            "sca_cfg": sca_path.relative_to(destination).as_posix(),
            "dump_contract": "dump_contract.json",
            "runner_contract": "runner_contract.json",
            "axi4_4kb_report": "axi4_4kb_report.json",
            "bank_data": "Bank_data/",
        },
        "text_file_contract": {
            "schema_version": "resnet50-package-text-abi-0.1",
            "encoding": "utf-8_or_ascii",
            "line_ending": "lf",
            "carriage_return_byte_allowed": False,
            "paths": text_file_paths,
        },
        "files": _output_hashes(destination),
    }
    _write_json(destination / "manifest.json", report)
    _validate_package_text_contract(destination, report["text_file_contract"])
    return report


def _expected_testbench_repeat_num(
    manifest: Mapping[str, Any], runtime_operator_count: int
) -> int:
    observer = manifest.get("testbench_observer")
    if not isinstance(observer, Mapping):
        return runtime_operator_count
    mode = observer.get("mode")
    raw_repeat = observer.get("repeat_num")
    if isinstance(raw_repeat, bool) or not isinstance(raw_repeat, int) or raw_repeat <= 0:
        raise ConvHardwareExecplanError(
            "manifest testbench observer repeat_num is invalid"
        )
    if int(observer.get("runtime_stage_count", -1)) != runtime_operator_count:
        raise ConvHardwareExecplanError(
            "manifest testbench observer runtime stage count differs"
        )
    if mode == "mask_aware_runtime_stage_markers":
        if raw_repeat != runtime_operator_count:
            raise ConvHardwareExecplanError(
                "mask-aware testbench Repeat_Num must equal runtime stage count"
            )
        return raw_repeat
    if mode != "fixed_slice0_start_slice1_finish":
        raise ConvHardwareExecplanError(
            f"unsupported testbench observer mode: {mode!r}"
        )
    pairs = observer.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != raw_repeat:
        raise ConvHardwareExecplanError(
            "fixed-pair testbench observer pair count differs"
        )
    last_finish = -1
    for pair_index, pair in enumerate(pairs):
        if (
            not isinstance(pair, Mapping)
            or int(pair.get("pair_index", -1)) != pair_index
            or not isinstance(pair.get("slice0_start_stage"), int)
            or not isinstance(pair.get("slice1_finish_stage"), int)
            or int(pair["slice0_start_stage"]) < 0
            or int(pair["slice1_finish_stage"]) < int(pair["slice0_start_stage"])
            or int(pair["slice1_finish_stage"]) < last_finish
        ):
            raise ConvHardwareExecplanError(
                "fixed-pair testbench observer ordering is invalid"
            )
        last_finish = int(pair["slice1_finish_stage"])
    if (
        last_finish != runtime_operator_count - 1
        or int(observer.get("final_pair_finishes_at_stage", -1)) != last_finish
        or observer.get("all_prior_stages_barrier_ordered") is not True
        or observer.get("final_stage_slice_mask") != "0x0000002"
        or observer.get("final_stage_is_finish_slice_only") is not True
        or observer.get(
            "all_other_final_shard_slices_barrier_completed_before_final_stage"
        )
        is not True
        or observer.get(
            "readback_after_final_finish_is_full_mask_completion_safe"
        )
        is not True
    ):
        raise ConvHardwareExecplanError(
            "fixed-pair testbench observer does not fence the final runtime stage"
        )
    runtime_operators = manifest.get("runtime_operators")
    if not isinstance(runtime_operators, list) or len(runtime_operators) < 2:
        raise ConvHardwareExecplanError(
            "fixed-pair package lacks the final partitioned runtime stages"
        )
    penultimate = runtime_operators[-2]
    final = runtime_operators[-1]
    if not isinstance(penultimate, Mapping) or not isinstance(final, Mapping):
        raise ConvHardwareExecplanError(
            "fixed-pair final runtime operators are malformed"
        )
    penultimate_attributes = penultimate.get("attributes")
    final_attributes = final.get("attributes")
    if (
        final.get("slice_mask") != "0x0000002"
        or not isinstance(penultimate_attributes, Mapping)
        or not isinstance(final_attributes, Mapping)
        or penultimate_attributes.get("runtime_partition")
        != "non_observer_slices"
        or final_attributes.get("runtime_partition") != "finish_slice_only"
        or penultimate_attributes.get("shard_index")
        != final_attributes.get("shard_index")
    ):
        raise ConvHardwareExecplanError(
            "fixed-pair final runtime schedule is not the proven completion fence"
        )
    return raw_repeat


def _validate_runtime_completion_barrier_contract(
    root: Path,
    manifest: Mapping[str, Any],
    sca: Mapping[str, Any],
    runner: Mapping[str, Any],
) -> None:
    """Decode the shipped execplan once and bind every runtime length/fence claim."""

    def positive_int(value: object, *, label: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ConvHardwareExecplanError(f"{label} must be a positive integer")
        return value

    runtime_operator_count = positive_int(
        manifest.get("runtime_operator_count"),
        label="manifest runtime_operator_count",
    )
    expected_repeat_num = _expected_testbench_repeat_num(
        manifest, runtime_operator_count
    )
    repeat_num = positive_int(sca.get("Repeat_Num"), label="SCA Repeat_Num")
    if repeat_num != expected_repeat_num:
        raise ConvHardwareExecplanError(
            "SCA Repeat_Num must equal the manifest testbench observer count: "
            f"repeat_num={repeat_num}, expected={expected_repeat_num}"
        )

    serialization = manifest.get("runtime_serialization")
    if not isinstance(serialization, Mapping):
        raise ConvHardwareExecplanError(
            "manifest runtime completion barrier contract is missing"
        )
    barrier_count = positive_int(
        serialization.get("barrier_count"),
        label="manifest runtime_serialization.barrier_count",
    )
    barrier_opcode = f"0b{RUNTIME_BARRIER_OPCODE:03b}"
    if (
        serialization.get("strategy") != "post_start_same_mask_barrier"
        or serialization.get("barrier_opcode") != barrier_opcode
        or barrier_count != runtime_operator_count
    ):
        raise ConvHardwareExecplanError(
            "manifest runtime completion barrier contract differs"
        )

    execution = sca.get("ExecutionPlan")
    if not isinstance(execution, Mapping) or not isinstance(
        execution.get("path"), str
    ):
        raise ConvHardwareExecplanError("SCA ExecutionPlan descriptor is invalid")
    exec_length = positive_int(sca.get("Exec_Length"), label="SCA Exec_Length")
    manifest_exec_length = positive_int(
        manifest.get("exec_128bit_line_count"),
        label="manifest exec_128bit_line_count",
    )
    try:
        runner_execution = runner["execution"]
        completion_gate = runner_execution["completion_gate"]
    except (KeyError, TypeError) as error:
        raise ConvHardwareExecplanError(
            "runner runtime completion barrier contract is missing"
        ) from error
    if not isinstance(runner_execution, Mapping) or not isinstance(
        completion_gate, Mapping
    ):
        raise ConvHardwareExecplanError(
            "runner runtime completion barrier contract is invalid"
        )
    runner_exec_length = positive_int(
        runner_execution.get("exec_length_128bit_beats"),
        label="runner execution exec_length_128bit_beats",
    )
    if len({exec_length, manifest_exec_length, runner_exec_length}) != 1:
        raise ConvHardwareExecplanError(
            "runtime execplan length contract differs: "
            f"sca={exec_length}, manifest={manifest_exec_length}, "
            f"runner={runner_exec_length}"
        )

    expected_runner_values = {
        "expected_runtime_stage_count": runtime_operator_count,
        "expected_testbench_repeat_num": expected_repeat_num,
        "expected_start_comp_count": runtime_operator_count,
        "expected_completion_barrier_count": runtime_operator_count,
    }
    for field, expected in expected_runner_values.items():
        observed = positive_int(
            completion_gate.get(field),
            label=f"runner completion_gate.{field}",
        )
        if observed != expected:
            raise ConvHardwareExecplanError(
                "runner runtime completion barrier contract differs: "
                f"{field}={observed}, expected={expected}"
            )
    if completion_gate.get("completion_barrier_opcode") != barrier_opcode:
        raise ConvHardwareExecplanError(
            "runner runtime completion barrier opcode differs"
        )
    observer = manifest.get("testbench_observer")
    if (
        completion_gate.get("testbench_observer_mode")
        != (observer.get("mode") if isinstance(observer, Mapping) else None)
        or completion_gate.get("testbench_observer") != observer
    ):
        raise ConvHardwareExecplanError(
            "runner/manifest testbench observer contract differs"
        )
    manifest_sequence = manifest.get("runtime_sequence")
    runner_sequence = completion_gate.get("expected_runtime_sequence")
    if (
        not isinstance(manifest_sequence, list)
        or len(manifest_sequence) != runtime_operator_count
        or not all(isinstance(value, str) and value for value in manifest_sequence)
        or runner_sequence != manifest_sequence
    ):
        raise ConvHardwareExecplanError(
            "runner/manifest runtime completion sequence differs"
        )

    execplan_path = _resolve_contained_relative_path(
        root,
        str(execution["path"]),
        label="runtime ExecutionPlan path",
    )
    try:
        commands = load_execplan_commands(
            execplan_path,
            expected_beats=exec_length,
        )
        _, stages = build_execution_stages(commands, manifest)
    except HardwareSimulationPreparationError as error:
        raise ConvHardwareExecplanError(
            f"runtime completion barrier execplan is invalid: {error}"
        ) from error

    start_commands = [command for command in commands if command.kind == "start_comp"]
    barrier_commands = [command for command in commands if command.kind == "barrier"]
    if (
        len(stages) != runtime_operator_count
        or len(start_commands) != runtime_operator_count
        or len(barrier_commands) != runtime_operator_count
    ):
        raise ConvHardwareExecplanError(
            "runtime completion barrier command counts differ: "
            f"stages={len(stages)}, start_comp={len(start_commands)}, "
            f"barriers={len(barrier_commands)}, expected={runtime_operator_count}"
        )
    for stage in stages:
        barrier = stage.completion_barrier
        if (
            barrier is None
            or barrier.index != stage.start_command.index + 1
            or int(barrier.fields["slice_mask"]) != stage.slice_mask
        ):
            raise ConvHardwareExecplanError(
                "runtime completion barrier is not immediately after its same-mask "
                f"Start_Comp: stage={stage.index}"
            )


def validate_conv_hardware_execplan_package(output_root: Path) -> dict[str, Any]:
    root = output_root.resolve()
    manifest_path = _resolve_contained_relative_path(
        root,
        "manifest.json",
        label="hardware execplan manifest path",
    )
    manifest = _read_json_object(manifest_path)
    if manifest.get("status") != "hardware_execplan_package_validated":
        raise ConvHardwareExecplanError("hardware execplan package status differs")
    _validate_package_bitstream_bindings(root, manifest)
    text_file_count = _validate_package_text_contract(
        root,
        manifest.get("text_file_contract", {}),
    )
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ConvHardwareExecplanError("hardware execplan package file list is missing")
    expected_file_paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            raise ConvHardwareExecplanError(
                "hardware execplan manifest file entry is not an object"
            )
        relative = item.get("path")
        expected_size = item.get("size_bytes")
        expected_sha = item.get("sha256")
        if (
            not isinstance(relative, str)
            or isinstance(expected_size, bool)
            or not isinstance(expected_size, int)
            or expected_size < 0
            or not isinstance(expected_sha, str)
            or len(expected_sha) != 64
        ):
            raise ConvHardwareExecplanError(
                "hardware execplan manifest file entry is malformed"
            )
        path = _resolve_contained_relative_path(
            root,
            relative,
            label="hardware execplan manifest file path",
        )
        normalized_relative = path.relative_to(root).as_posix()
        if normalized_relative in expected_file_paths:
            raise ConvHardwareExecplanError(
                f"duplicate hardware execplan manifest file path: {relative}"
            )
        expected_file_paths.add(normalized_relative)
        if (
            not path.is_file()
            or path.stat().st_size != expected_size
            or _sha256_file(path) != expected_sha
        ):
            raise ConvHardwareExecplanError(
                f"hardware execplan package file differs: {relative}"
            )
    actual_file_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual_file_paths != expected_file_paths:
        missing = sorted(expected_file_paths - actual_file_paths)
        unlisted = sorted(actual_file_paths - expected_file_paths)
        raise ConvHardwareExecplanError(
            "hardware execplan manifest must enumerate the exact package file set: "
            f"missing={missing[:5]}, unlisted={unlisted[:5]}"
        )
    sca = _read_json_object(root / "sca_cfg.json")
    repeat_num = sca.get("Repeat_Num")
    expected_repeat_num = _expected_testbench_repeat_num(
        manifest, int(manifest["runtime_operator_count"])
    )
    if (
        isinstance(repeat_num, bool)
        or not isinstance(repeat_num, int)
        or repeat_num <= 0
        or repeat_num != expected_repeat_num
    ):
        raise ConvHardwareExecplanError(
            "SCA Repeat_Num must equal the manifest testbench observer count: "
            f"repeat_num={repeat_num!r}, expected={expected_repeat_num}"
        )
    semantic_paths: dict[str, str] = {}
    for key, value in _sca_transport_entries(sca):
        semantic_key = str(value.get("semantic_key", key))
        semantic_path = str(value.get("semantic_path", value.get("path", "")))
        previous = semantic_paths.setdefault(semantic_key, semantic_path)
        if previous != semantic_path:
            raise ConvHardwareExecplanError(
                f"SCA semantic path differs between segments: {semantic_key}"
            )
    paths = list(semantic_paths.values())
    expected_inputs = int(manifest["preloaded_input_count"])
    expected_scratch = int(manifest.get("preloaded_runtime_scratch_count", 0))
    expected_configs = int(manifest["runtime_operator_count"])
    if (
        len([path for path in paths if path.startswith("install/data/")])
        != expected_inputs
        or len([path for path in paths if path.startswith("install/cfg_pkg/")])
        != expected_configs
        or len([path for path in paths if path.startswith("install/runtime_scratch/")])
        != expected_scratch
        or any(token in path for path in paths for token in ("golden/", "physical/P/", "physical/D/", "staged_D"))
    ):
        raise ConvHardwareExecplanError("SCA preload boundary differs")
    _validate_payload_intervals(sca, root)
    serialized_transfer_count = _validate_immutable_tb_sca_parser_abi(
        root / "sca_cfg.json",
        sca,
    )
    if int(manifest.get("preload_transfer_segment_count", -1)) != len(
        _sca_transport_entries(sca)
    ) or serialized_transfer_count != len(_sca_transport_entries(sca)):
        raise ConvHardwareExecplanError("SCA preload transfer segment count differs")

    sca_d = _read_json_object(root / "sca_cfg_D.json")
    recorded_axi4_report = _read_json_object(root / "axi4_4kb_report.json")
    preload_segments_for_report: dict[str, list[dict[str, Any]]] = {}
    for key, entry in _sca_transport_entries(sca):
        semantic_key = str(entry.get("semantic_key", key))
        preload_segments_for_report.setdefault(semantic_key, []).append(dict(entry))
    for segments in preload_segments_for_report.values():
        segments.sort(key=lambda item: int(item.get("axi4_segment_index", 0)))
    readback_groups: dict[str, list[tuple[str, Mapping[str, Any]]]] = {}
    for key, entry in sca_d.items():
        if not isinstance(entry, Mapping):
            raise ConvHardwareExecplanError(f"SCA_D entry is not an object: {key}")
        semantic_key = str(entry.get("semantic_key", key))
        readback_groups.setdefault(semantic_key, []).append((key, entry))
    semantic_sca_d_for_report: dict[str, dict[str, Any]] = {}
    for semantic_key, grouped in readback_groups.items():
        grouped.sort(key=lambda item: int(item[1].get("axi4_segment_index", 0)))
        first = grouped[0][1]
        if "semantic_key" in first:
            semantic_sca_d_for_report[semantic_key] = {
                "base_addr": str(first["semantic_base_addr"]),
                "length": int(first["semantic_length"]),
                "path": str(first["semantic_path"]),
            }
        else:
            semantic_sca_d_for_report[semantic_key] = dict(first)
    recomputed_axi4_report = _build_axi4_4kb_trigger_report(
        root,
        preload_segments_for_report,
        semantic_sca_d_for_report,
        sca_d,
    )
    manifest_axi4 = manifest.get("axi4_4kb")
    if (
        recorded_axi4_report != recomputed_axi4_report
        or not isinstance(manifest_axi4, Mapping)
        or manifest_axi4.get("report_path") != "axi4_4kb_report.json"
        or manifest_axi4.get("report_sha256")
        != _sha256_file(root / "axi4_4kb_report.json")
        or manifest_axi4.get("status") != recorded_axi4_report.get("status")
        or manifest_axi4.get("risk_classification")
        != recorded_axi4_report.get("risk_classification")
        or manifest_axi4.get("semantic_transfer_count")
        != recorded_axi4_report.get("semantic_transfer_count")
        or manifest_axi4.get("triggered_transfer_count")
        != recorded_axi4_report.get("triggered_transfer_count")
    ):
        raise ConvHardwareExecplanError(
            "AXI4 4-KiB conditional-risk trigger report differs"
        )
    runner = _read_json_object(root / "runner_contract.json")
    dump_contract = _read_json_object(root / "dump_contract.json")
    _validate_runtime_completion_barrier_contract(root, manifest, sca, runner)
    try:
        parser_abi = runner["preload"]["sca_cfg"]["immutable_tb_parser_abi"]
        parser_abi_count = int(parser_abi["validated_transfer_count"])
    except (KeyError, TypeError, ValueError) as error:
        raise ConvHardwareExecplanError(
            "runner immutable TB parser ABI contract is missing or invalid"
        ) from error
    if (
        parser_abi.get("name") != "line-oriented-json-close-resets-entry-v1"
        or parser_abi.get("serialized_order_is_authoritative") is not True
        or parser_abi.get("execution_plan_outer_close_loads_semantic_path") is not False
        or parser_abi_count != serialized_transfer_count
    ):
        raise ConvHardwareExecplanError(
            "runner immutable TB parser ABI contract differs"
        )
    try:
        post_run_dump = runner["post_run_dump"]
        return_mode = str(post_run_dump["return_mode"])
        expected_region_count = int(post_run_dump["expected_region_count"])
        semantic_region_count = int(post_run_dump["semantic_region_count"])
        transfer_segment_count = int(post_run_dump["transfer_segment_count"])
    except (KeyError, TypeError, ValueError) as error:
        raise ConvHardwareExecplanError(
            "runner post-run region contract is missing or invalid"
        ) from error
    if (
        return_mode != "sca_d_regions"
        or expected_region_count != len(sca_d)
        or transfer_segment_count != len(sca_d)
    ):
        raise ConvHardwareExecplanError(
            "runner/SCA_D region count differs: "
            f"mode={return_mode!r}, expected={expected_region_count}, actual={len(sca_d)}"
        )
    expected_dump_regions: set[tuple[int, int]] = set()
    for entry in list(dump_contract.get("P", [])) + list(
        dump_contract.get("staged_D", [])
    ):
        if not isinstance(entry, dict):
            raise ConvHardwareExecplanError("dump contract region is not an object")
        expected_dump_regions.add(
            (
                int(str(entry["base_addr"]).replace("_", ""), 16),
                int(entry["size_bytes"]),
            )
        )
    if semantic_region_count != len(expected_dump_regions):
        raise ConvHardwareExecplanError(
            "runner semantic dump-region count differs: "
            f"expected={len(expected_dump_regions)}, actual={semantic_region_count}"
        )
    observed_dump_regions: set[tuple[int, int]] = set()
    observed_paths: set[str] = set()
    segments_by_semantic: dict[
        str, list[tuple[int, int, int, Mapping[str, Any]]]
    ] = {}
    for key, entry in sca_d.items():
        if not isinstance(entry, dict):
            raise ConvHardwareExecplanError(f"SCA_D entry is not an object: {key}")
        try:
            address = int(str(entry["base_addr"]).replace("_", ""), 16)
            size_bytes = int(entry["length"]) * 16
            path = str(entry["path"])
        except (KeyError, TypeError, ValueError) as error:
            raise ConvHardwareExecplanError(f"invalid SCA_D entry: {key}") from error
        if size_bytes <= 0 or not path.startswith("install/hwop-"):
            raise ConvHardwareExecplanError(f"invalid SCA_D region boundary: {key}")
        _validate_axi4_burst_sequence(
            address,
            size_bytes // AXI_DATA_BYTES,
            label=f"SCA_D {key}",
        )
        _resolve_contained_relative_path(
            root,
            path,
            label=f"SCA_D region path ({key})",
        )
        if path in observed_paths:
            raise ConvHardwareExecplanError(f"duplicate SCA_D region or path: {key}")
        observed_paths.add(path)
        semantic_key = str(entry.get("semantic_key", key))
        segment_index_value = entry.get("axi4_segment_index", 0)
        if isinstance(segment_index_value, bool):
            raise ConvHardwareExecplanError(f"invalid SCA_D segment index: {key}")
        try:
            segment_index = int(segment_index_value)
        except (TypeError, ValueError) as error:
            raise ConvHardwareExecplanError(f"invalid SCA_D segment index: {key}") from error
        segments_by_semantic.setdefault(semantic_key, []).append(
            (segment_index, address, size_bytes, entry)
        )

    for semantic_key, records in segments_by_semantic.items():
        ordered = sorted(records, key=lambda item: item[0])
        if len(ordered) == 1 and "semantic_key" not in ordered[0][3]:
            observed_dump_regions.add((ordered[0][1], ordered[0][2]))
            continue
        try:
            expected_segments = int(ordered[0][3]["axi4_segment_count"])
            semantic_base = int(
                str(ordered[0][3]["semantic_base_addr"]).replace("_", ""), 16
            )
            semantic_length = int(ordered[0][3]["semantic_length"])
            semantic_path = str(ordered[0][3]["semantic_path"])
        except (KeyError, TypeError, ValueError) as error:
            raise ConvHardwareExecplanError(
                f"invalid SCA_D semantic segment metadata: {semantic_key}"
            ) from error
        if (
            expected_segments != 2
            or len(ordered) != expected_segments
            or [item[0] for item in ordered] != list(range(expected_segments))
            or semantic_base != ordered[0][1]
            or semantic_length * AXI_DATA_BYTES
            != sum(item[2] for item in ordered)
        ):
            raise ConvHardwareExecplanError(
                f"incomplete SCA_D semantic segment set: {semantic_key}"
            )
        cursor = semantic_base
        for _, segment_address, segment_size, segment in ordered:
            if (
                segment_address != cursor
                or int(segment.get("axi4_segment_count", -1)) != expected_segments
                or str(segment.get("semantic_base_addr"))
                != str(ordered[0][3]["semantic_base_addr"])
                or int(segment.get("semantic_length", -1)) != semantic_length
                or str(segment.get("semantic_path")) != semantic_path
            ):
                raise ConvHardwareExecplanError(
                    f"SCA_D segments are not contiguous/consistent: {semantic_key}"
                )
            cursor += segment_size
        if ordered[1][1] % AXI_4KB_BYTES:
            raise ConvHardwareExecplanError(
                f"SCA_D tail is not page aligned: {semantic_key}"
            )
        observed_dump_regions.add(
            (semantic_base, semantic_length * AXI_DATA_BYTES)
        )
    if observed_dump_regions != expected_dump_regions:
        missing = sorted(expected_dump_regions - observed_dump_regions)
        extra = sorted(observed_dump_regions - expected_dump_regions)
        raise ConvHardwareExecplanError(
            "SCA_D must request every complete semantic P/staged-D region exactly once: "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )
    return {
        "status": "hardware_execplan_package_validated",
        "node_id": manifest["node_id"],
        "runtime_operator_count": manifest["runtime_operator_count"],
        "exec_128bit_line_count": manifest["exec_128bit_line_count"],
        "bank_data_file_count": manifest["bank_data_file_count"],
        "post_run_region_count": len(sca_d),
        "semantic_post_run_region_count": semantic_region_count,
        "axi4_4kb_status": recorded_axi4_report["status"],
        "axi4_4kb_triggered_transfer_count": recorded_axi4_report[
            "triggered_transfer_count"
        ],
        "checked_file_count": len(files),
        "lf_text_file_count": text_file_count,
    }


def _parse_bank_dump(path: Path) -> bytes:
    if path.suffix.lower() == ".bin":
        return path.read_bytes()
    data = bytearray()
    for line_number, raw_line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        tokens = line.split()
        if all(token.lower().startswith("0x") for token in tokens):
            if len(tokens) not in (1, 4):
                raise ConvHardwareExecplanError(
                    f"unsupported hex bank line at {path}:{line_number}"
                )
            ordered = tokens if len(tokens) == 1 else list(reversed(tokens))
            for token in ordered:
                data.extend(int(token, 16).to_bytes(4, byteorder="little", signed=False))
            continue
        bits = "".join(tokens)
        if len(bits) not in (32, 128) or set(bits) - {"0", "1"}:
            raise ConvHardwareExecplanError(
                f"unsupported bank line at {path}:{line_number}"
            )
        data.extend(int(bits, 2).to_bytes(len(bits) // 8, byteorder="little", signed=False))
    return bytes(data)


def _readback_relative_path(relative_value: str, *, label: str) -> Path:
    """Map an original or relocated SCA_D path into returned/readback_regions."""

    if not isinstance(relative_value, str) or not relative_value:
        raise ConvHardwareExecplanError(f"{label} must be a non-empty path")
    posix = PurePosixPath(relative_value)
    windows = PureWindowsPath(relative_value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.anchor)
        or "\\" in relative_value
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise ConvHardwareExecplanError(f"{label} is not a canonical relative path")
    hwop_positions = [
        index for index, part in enumerate(posix.parts) if part.startswith("hwop-")
    ]
    if not hwop_positions:
        raise ConvHardwareExecplanError(
            f"{label} must contain an hwop output root"
        )
    # Relocated SCA_D paths contain the install package name (also hwop-*)
    # before ``install/<actual-output-hwop>/...``.  The last hwop component is
    # therefore the canonical returned readback root.
    relative = Path(*posix.parts[hwop_positions[-1] :])
    if len(relative.parts) < 2:
        raise ConvHardwareExecplanError(f"{label} has no file below its hwop root")
    return relative


def _sca_d_readback_contract(
    sca_d: Mapping[str, Any],
    *,
    label: str,
) -> dict[Path, int]:
    contract: dict[Path, int] = {}
    for key, entry in sca_d.items():
        if not isinstance(entry, Mapping):
            raise ConvHardwareExecplanError(f"{label} entry is not an object: {key}")
        try:
            path = str(entry["path"])
            line_count = int(entry["length"])
        except (KeyError, TypeError, ValueError) as error:
            raise ConvHardwareExecplanError(f"invalid {label} entry: {key}") from error
        relative = _readback_relative_path(path, label=f"{label} path ({key})")
        if line_count <= 0 or relative in contract:
            raise ConvHardwareExecplanError(
                f"duplicate or invalid {label} readback path: {key}"
            )
        contract[relative] = line_count
    return contract


def _validate_readback_region_tree(
    returned: Path,
    expected: Mapping[Path, int],
) -> dict[Path, dict[str, Any]]:
    """Validate and snapshot each returned region in one filesystem pass."""

    region_root = _resolve_contained_relative_path(
        returned,
        "readback_regions",
        label="returned readback-region root",
    )
    if region_root.is_symlink() or not region_root.is_dir():
        raise ConvHardwareExecplanError(
            "returned readback_regions must be a real directory"
        )
    actual_files: set[Path] = set()
    for path in region_root.rglob("*"):
        if path.is_symlink():
            raise ConvHardwareExecplanError(
                f"returned readback_regions contains a symlink: {path}"
            )
        if path.is_file():
            actual_files.add(path.relative_to(region_root))
        elif not path.is_dir():
            raise ConvHardwareExecplanError(
                f"returned readback_regions contains a non-regular entry: {path}"
            )
    expected_files = set(expected)
    if actual_files != expected_files:
        missing = sorted(item.as_posix() for item in expected_files - actual_files)
        extra = sorted(item.as_posix() for item in actual_files - expected_files)
        raise ConvHardwareExecplanError(
            "returned readback-region file set differs: "
            f"missing={missing[:5]}, extra={extra[:5]}"
        )
    snapshot: dict[Path, dict[str, Any]] = {}
    for relative, expected_lines in expected.items():
        path = region_root / relative
        try:
            raw_payload = path.read_bytes()
            text_payload = raw_payload.decode("ascii")
        except (OSError, UnicodeDecodeError) as error:
            raise ConvHardwareExecplanError(
                f"cannot read returned readback-region file: {relative.as_posix()}"
            ) from error
        expected_size = expected_lines * 129
        if len(raw_payload) != expected_size:
            raise ConvHardwareExecplanError(
                "returned readback-region byte size differs: "
                f"{relative.as_posix()} observed={len(raw_payload)} "
                f"expected={expected_size}"
            )
        if not raw_payload.endswith(b"\n"):
            raise ConvHardwareExecplanError(
                "returned readback-region is missing its final LF: "
                f"{relative.as_posix()}"
            )
        if set(raw_payload) - {ord("0"), ord("1"), ord("\n")}:
            raise ConvHardwareExecplanError(
                "returned readback-region contains bytes outside 0/1/LF: "
                f"{relative.as_posix()}"
            )
        raw_lines = raw_payload.split(b"\n")
        if not raw_lines or raw_lines[-1] != b"":
            raise ConvHardwareExecplanError(
                "returned readback-region record framing is invalid: "
                f"{relative.as_posix()}"
            )
        lines = [line.decode("ascii") for line in raw_lines[:-1]]
        payload = bytearray()
        for line_number, line in enumerate(lines, 1):
            if len(line) != 128 or set(line) - {"0", "1"}:
                raise ConvHardwareExecplanError(
                    "invalid 128-bit SCA payload line at "
                    f"{path}:{line_number}"
                )
            payload.extend(int(line, 2).to_bytes(16, byteorder="little"))
        if len(lines) != expected_lines:
            raise ConvHardwareExecplanError(
                "returned readback-region line count differs: "
                f"{relative.as_posix()}"
            )
        snapshot[relative] = {
            "path": path,
            "line_count": len(lines),
            "size_bytes": len(raw_payload),
            "sha256": _sha256_bytes(raw_payload),
            "payload": bytes(payload),
        }
    return snapshot


def _find_bank_dump(bank_root: Path, slice_id: int, bank_id: int) -> Path:
    stem = f"slice{slice_id:02d}_Bank{bank_id:02d}_data"
    candidates = [bank_root / f"{stem}.txt", bank_root / f"{stem}.bin"]
    for path in candidates:
        if path.is_file():
            return path
    raise ConvHardwareExecplanError(
        f"hardware simulator bank dump is missing: {candidates[0]} or {candidates[1]}"
    )


def assemble_conv_hardware_region_dump(
    package_root: Path,
    readback_root: Path,
    simulator_bank_root: Path,
    *,
    validated_region_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Reconstruct comparator-compatible sparse Bank00 images from SCA_D regions."""

    package = package_root.resolve()
    returned = readback_root.resolve()
    output = simulator_bank_root.resolve()
    if output.exists() and any(output.iterdir()):
        raise ConvHardwareExecplanError(
            f"bank output directory is not empty; refusing to mix runs: {output}"
        )
    output.mkdir(parents=True, exist_ok=True)

    package_manifest_sha256 = _sha256_file(package / "manifest.json")
    snapshot_reused = False
    region_snapshot: dict[Path, Mapping[str, Any]] | None = None
    if isinstance(validated_region_receipt, _ValidatedRegionReceipt):
        if (
            getattr(validated_region_receipt, "_seal", None) is _REGION_RECEIPT_SEAL
            and getattr(validated_region_receipt, "_public_sha256", None)
            == _canonical_json_sha256(validated_region_receipt)
            and validated_region_receipt.get("package_manifest_sha256")
            == package_manifest_sha256
            and validated_region_receipt.get("return_root") == str(returned)
        ):
            region_snapshot = dict(validated_region_receipt._region_snapshot)
            snapshot_reused = True

    if snapshot_reused:
        package_snapshot = validated_region_receipt._package_snapshot
        sca_d = package_snapshot.get("sca_cfg_D")
        runner = package_snapshot.get("runner_contract")
        contract = package_snapshot.get("dump_contract")
        if not all(isinstance(item, Mapping) for item in (sca_d, runner, contract)):
            raise ConvHardwareExecplanError(
                "validated region receipt package contract is invalid"
            )
    else:
        validate_conv_hardware_execplan_package(package)
        sca_d = _read_json_object(package / "sca_cfg_D.json")
        runner = _read_json_object(package / "runner_contract.json")
        contract = _read_json_object(package / "dump_contract.json")

    readback_contract = _sca_d_readback_contract(
        sca_d,
        label="package SCA_D",
    )
    if region_snapshot is None:
        region_snapshot = _validate_readback_region_tree(returned, readback_contract)
    elif set(region_snapshot) != set(readback_contract):
        raise ConvHardwareExecplanError(
            "validated region receipt file set differs from package SCA_D"
        )
    try:
        post_run = runner["post_run_dump"]
        minimum_bytes = int(post_run["minimum_bytes_per_slice"])
        required_slices = [int(item) for item in post_run["required_slices"]]
    except (KeyError, TypeError, ValueError) as error:
        raise ConvHardwareExecplanError(
            "runner contract has no valid post-run dump requirement"
        ) from error
    if required_slices != list(range(int(contract.get("slice_count", 0)))):
        raise ConvHardwareExecplanError(
            "runner required slices differ from the dump contract"
        )

    images = {slice_id: bytearray(minimum_bytes) for slice_id in required_slices}
    intervals: dict[tuple[int, int], list[tuple[int, int, str]]] = {}
    consumed: list[dict[str, Any]] = []

    for key, entry in sca_d.items():
        if not isinstance(entry, dict):
            raise ConvHardwareExecplanError(f"SCA_D entry is not an object: {key}")
        try:
            address = int(str(entry["base_addr"]).replace("_", ""), 16)
            length_128bit = int(entry["length"])
            relative_path = str(entry["path"])
        except (KeyError, TypeError, ValueError) as error:
            raise ConvHardwareExecplanError(f"invalid SCA_D entry: {key}") from error
        if length_128bit <= 0:
            raise ConvHardwareExecplanError(f"SCA_D length must be positive: {key}")
        slice_id = (address >> EXECPLAN_SLICE_SHIFT) & 0x1F
        bank_id = (address >> 23) & 0x03
        offset = address & ((1 << 23) - 1)
        if slice_id not in images or bank_id != 0:
            raise ConvHardwareExecplanError(
                f"SCA_D region is outside required Bank00 images: {key}"
            )
        relative = _readback_relative_path(
            relative_path,
            label="returned SCA_D region path",
        )
        region_record = region_snapshot.get(relative)
        if not isinstance(region_record, Mapping):
            raise ConvHardwareExecplanError(
                f"validated SCA_D region is missing: {relative_path!r}"
            )
        path = region_record.get("path")
        payload = region_record.get("payload")
        if not isinstance(path, Path) or not isinstance(payload, bytes):
            raise ConvHardwareExecplanError(
                f"validated SCA_D region receipt is invalid: {relative_path!r}"
            )
        expected_size = length_128bit * 16
        if len(payload) != expected_size:
            raise ConvHardwareExecplanError(
                f"SCA_D region size differs: {key}, bytes={len(payload)}, "
                f"expected={expected_size}"
            )
        end = offset + len(payload)
        if end > minimum_bytes:
            raise ConvHardwareExecplanError(
                f"SCA_D region exceeds declared Bank00 capacity: {key}, end={end}, "
                f"capacity={minimum_bytes}"
            )
        region_intervals = intervals.setdefault((slice_id, bank_id), [])
        for previous_start, previous_end, previous_key in region_intervals:
            if max(offset, previous_start) < min(end, previous_end):
                raise ConvHardwareExecplanError(
                    f"overlapping SCA_D regions: {previous_key} and {key}"
                )
        images[slice_id][offset:end] = payload
        region_intervals.append((offset, end, key))
        consumed.append(
            {
                "key": key,
                "slice_id": slice_id,
                "bank_id": bank_id,
                "local_offset": offset,
                "size_bytes": len(payload),
                "path": str(path),
                "sha256": str(region_record["sha256"]),
            }
        )

    required_regions = list(contract.get("P", [])) + list(contract.get("staged_D", []))
    for entry in required_regions:
        if not isinstance(entry, dict):
            raise ConvHardwareExecplanError("dump contract region is not an object")
        slice_id = int(entry["slice_id"])
        address = int(str(entry["base_addr"]).replace("_", ""), 16)
        bank_id = (address >> 23) & 0x03
        start = address & ((1 << 23) - 1)
        end = start + int(entry["size_bytes"])
        covered = start
        for interval_start, interval_end, _ in sorted(
            intervals.get((slice_id, bank_id), [])
        ):
            if interval_start > covered:
                break
            if interval_end > covered:
                covered = interval_end
            if covered >= end:
                break
        if covered < end:
            raise ConvHardwareExecplanError(
                "returned SCA_D regions do not cover a required output interval: "
                f"slice={slice_id}, bank={bank_id}, range=[{start}, {end}), covered_to={covered}"
            )

    bank_files: list[dict[str, Any]] = []
    for slice_id, image in sorted(images.items()):
        path = output / f"slice{slice_id:02d}_Bank00_data.bin"
        path.write_bytes(image)
        bank_files.append(
            {
                "slice_id": slice_id,
                "bank_id": 0,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
        )

    report: dict[str, Any] = {
        "schema_version": "resnet50-conv-hardware-region-adapter-0.1",
        "status": "hardware_region_dump_assembled",
        "package_manifest_sha256": package_manifest_sha256,
        "readback_root": str(returned),
        "validated_region_receipt_reused": snapshot_reused,
        "consumed_region_count": len(consumed),
        "consumed_regions": consumed,
        "bank_files": bank_files,
    }
    _write_json(output / "region_adapter_manifest.json", report)
    return report


def _parse_runtime_completion_console(
    console_path: Path,
    *,
    expected_preload_transfer_count: int,
    expected_slice_masks: list[str],
    expected_simulator_exit_status: int,
    observer_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-derive the completion verdict from the returned simulator console."""

    stage_pattern = re.compile(
        r"^\[(?P<time>[0-9]+)\] RUNTIME_STAGE_COMPLETE "
        r"stage=(?P<stage>[0-9]+) mask=(?P<mask>0x[0-9a-fA-F]+) "
        r"cycles=(?P<cycles>[0-9]+)$"
    )
    all_stages_pattern = re.compile(
        r"^\[(?P<time>[0-9]+)\] RUNTIME_ALL_STAGES_COMPLETE "
        r"count=(?P<count>[0-9]+)$"
    )
    exit_status_pattern = re.compile(r"^Simulation exit status: (?P<status>[0-9]+)$")
    preload_pass_pattern = re.compile(
        r"^\[[0-9]+\] \*\*\* PASS: Continuous transfer completed successfully!$"
    )
    try:
        console_payload = console_path.read_bytes()
        console_text = console_payload.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ConvHardwareExecplanError(
            "cannot read returned simulator console as UTF-8 text"
        ) from error

    loading_pattern = re.compile(
        r"^\[[0-9]+\] JSON: Loading matrix\[(?P<index>[0-9]+)\]: .+ -> 0x[0-9a-fA-F]+$"
    )
    ordered_load_count = 0
    ordered_pass_count = 0
    preload_pending = False
    runtime_started = False
    for line_number, line in enumerate(console_text.splitlines(), 1):
        if "JSON: Loading matrix[" in line:
            match = loading_pattern.fullmatch(line)
            if (
                match is None
                or runtime_started
                or preload_pending
                or int(match.group("index")) != ordered_load_count
                or ordered_load_count >= expected_preload_transfer_count
            ):
                raise ConvHardwareExecplanError(
                    f"preload loading markers are malformed/non-contiguous: line={line_number}"
                )
            ordered_load_count += 1
            preload_pending = True
        if "PASS: Continuous transfer completed successfully" in line:
            if (
                preload_pass_pattern.fullmatch(line) is None
                or runtime_started
                or not preload_pending
                or ordered_pass_count >= expected_preload_transfer_count
            ):
                raise ConvHardwareExecplanError(
                    f"preload PASS markers are malformed/not paired: line={line_number}"
                )
            ordered_pass_count += 1
            preload_pending = False
        if (
            "INFO: slice start" in line
            or (
                "RUNTIME_STAGE_COMPLETE" in line
                and "RUNTIME_ALL_STAGES_COMPLETE" not in line
            )
        ):
            if (
                preload_pending
                or ordered_load_count != expected_preload_transfer_count
                or ordered_pass_count != expected_preload_transfer_count
            ):
                raise ConvHardwareExecplanError(
                    "runtime execution started before ordered preload completion"
                )
            runtime_started = True
    if (
        preload_pending
        or ordered_load_count != expected_preload_transfer_count
        or ordered_pass_count != expected_preload_transfer_count
    ):
        raise ConvHardwareExecplanError(
            "ordered preload loading/PASS sequence differs from the package contract"
        )

    observer_mode = observer_contract.get("mode")
    if observer_mode == "fixed_slice0_start_slice1_finish":
        preload_lines: list[int] = []
        starts: list[dict[str, int]] = []
        finishes: list[dict[str, int]] = []
        natural_completion_lines: list[int] = []
        reserved_clock_lines: list[int] = []
        exit_status_records: list[dict[str, int]] = []
        start_pattern = re.compile(r"^\[(?P<time>[0-9]+)\] INFO: slice start$")
        finish_pattern = re.compile(
            r"^\[(?P<time>[0-9]+)\] INFO: slice completed after "
            r"(?P<cycles>[0-9]+) cycles$"
        )
        exit_status_pattern = re.compile(
            r"^Simulation exit status: (?P<status>[0-9]+)$"
        )
        preload_pass_pattern = re.compile(
            r"^\[[0-9]+\] \*\*\* PASS: Continuous transfer completed successfully!$"
        )
        reserved_clock_pattern = re.compile(
            r"^(?:ucli%[ \t]*)?RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING$"
        )
        waiting_for_finish = False
        for line_number, line in enumerate(console_text.splitlines(), 1):
            if "PASS: Continuous transfer completed successfully" in line:
                if preload_pass_pattern.fullmatch(line) is None:
                    raise ConvHardwareExecplanError(
                        "malformed preload readback PASS marker in simulator console: "
                        f"line={line_number}"
                    )
                if starts or finishes:
                    raise ConvHardwareExecplanError(
                        "preload readback PASS marker appears after fixed-observer execution started"
                    )
                preload_lines.append(line_number)
            if "INFO: slice start" in line:
                match = start_pattern.fullmatch(line)
                if match is None or waiting_for_finish:
                    raise ConvHardwareExecplanError(
                        "fixed-observer slice-start markers are malformed or not alternating: "
                        f"line={line_number}"
                    )
                starts.append(
                    {"timestamp": int(match.group("time")), "line_number": line_number}
                )
                waiting_for_finish = True
            if "INFO: slice completed after" in line:
                match = finish_pattern.fullmatch(line)
                if match is None or not waiting_for_finish:
                    raise ConvHardwareExecplanError(
                        "fixed-observer slice-finish markers are malformed or not alternating: "
                        f"line={line_number}"
                    )
                finishes.append(
                    {
                        "timestamp": int(match.group("time")),
                        "cycles": int(match.group("cycles")),
                        "line_number": line_number,
                    }
                )
                waiting_for_finish = False
            if "Simulation completed successfully!" in line:
                if line != "Simulation completed successfully!" or waiting_for_finish:
                    raise ConvHardwareExecplanError(
                        "natural-completion marker is malformed or precedes a fixed-observer finish"
                    )
                natural_completion_lines.append(line_number)
            if "RESERVED_AXI_CLOCK_FORCE_FAILED" in line:
                raise ConvHardwareExecplanError(
                    "reserved-clock UCLI reported a force or toggle failure"
                )
            if "RESERVED_AXI_CLOCK_FORCE_APPLIED_AND_TOGGLING" in line:
                if reserved_clock_pattern.fullmatch(line) is None:
                    raise ConvHardwareExecplanError(
                        "reserved-clock UCLI marker is malformed"
                    )
                reserved_clock_lines.append(line_number)
            if "Simulation exit status:" in line:
                match = exit_status_pattern.fullmatch(line)
                if match is None:
                    raise ConvHardwareExecplanError(
                        f"malformed simulation exit status in simulator console: line={line_number}"
                    )
                exit_status_records.append(
                    {"status": int(match.group("status")), "line_number": line_number}
                )

        raw_repeat = observer_contract.get("repeat_num")
        raw_stage_count = observer_contract.get("runtime_stage_count")
        if (
            isinstance(raw_repeat, bool)
            or not isinstance(raw_repeat, int)
            or raw_repeat <= 0
            or isinstance(raw_stage_count, bool)
            or not isinstance(raw_stage_count, int)
            or raw_stage_count <= 0
        ):
            raise ConvHardwareExecplanError("fixed-observer contract counts are invalid")
        if len(preload_lines) != expected_preload_transfer_count:
            raise ConvHardwareExecplanError(
                "simulator console preload readback PASS count differs from the package contract: "
                f"expected={expected_preload_transfer_count}, observed={len(preload_lines)}"
            )
        if waiting_for_finish or len(starts) != raw_repeat or len(finishes) != raw_repeat:
            raise ConvHardwareExecplanError(
                "simulator console fixed-observer pair count differs from the package contract"
            )
        if len(natural_completion_lines) != 1:
            raise ConvHardwareExecplanError(
                "simulator console must contain exactly one natural-completion marker"
            )
        if len(reserved_clock_lines) != 1:
            raise ConvHardwareExecplanError(
                "simulator console must contain exactly one reserved-clock UCLI marker"
            )
        if len(exit_status_records) != 1:
            raise ConvHardwareExecplanError(
                "simulator console must contain exactly one simulation exit status"
            )
        if natural_completion_lines[0] <= finishes[-1]["line_number"]:
            raise ConvHardwareExecplanError(
                "natural-completion marker must follow the final fixed-observer finish"
            )
        if exit_status_records[0]["line_number"] <= natural_completion_lines[0]:
            raise ConvHardwareExecplanError(
                "simulation exit status must follow natural completion"
            )
        console_exit_status = exit_status_records[0]["status"]
        if console_exit_status != expected_simulator_exit_status:
            raise ConvHardwareExecplanError(
                "simulation exit status in console differs from return metadata"
            )
        pairs = [
            {
                "pair_index": pair_index,
                "start": starts[pair_index],
                "finish": finishes[pair_index],
            }
            for pair_index in range(raw_repeat)
        ]
        return {
            "sha256": _sha256_bytes(console_payload),
            "observer_mode": observer_mode,
            "simulation_exit_status": console_exit_status,
            "simulation_exit_status_line": exit_status_records[0]["line_number"],
            "preload_readback_pass_count": len(preload_lines),
            "preload_readback_pass_lines": preload_lines,
            "completed_runtime_stage_count": raw_stage_count,
            "fixed_observer_pair_count": raw_repeat,
            "fixed_observer_pairs": pairs,
            "natural_completion_line": natural_completion_lines[0],
            "reserved_clock_force_marker_count": len(reserved_clock_lines),
            "reserved_clock_force_marker_line": reserved_clock_lines[0],
        }
    if observer_mode != "mask_aware_runtime_stage_markers":
        raise ConvHardwareExecplanError(
            f"unsupported testbench observer mode: {observer_mode!r}"
        )

    expected_mask_values: list[int] = []
    for stage_index, slice_mask in enumerate(expected_slice_masks):
        if not isinstance(slice_mask, str) or re.fullmatch(
            r"0x[0-9a-fA-F]+", slice_mask
        ) is None:
            raise ConvHardwareExecplanError(
                f"package runtime operator slice mask is invalid: stage={stage_index}"
            )
        mask_value = int(slice_mask, 16)
        if mask_value <= 0 or mask_value > ALL_SLICES_MASK:
            raise ConvHardwareExecplanError(
                f"package runtime operator slice mask is outside 28 slices: stage={stage_index}"
            )
        expected_mask_values.append(mask_value)

    stage_markers: list[dict[str, Any]] = []
    all_stages_markers: list[dict[str, int]] = []
    exit_status_records: list[dict[str, int]] = []
    preload_pass_lines: list[int] = []
    for line_number, line in enumerate(console_text.splitlines(), 1):
        if "PASS: Continuous transfer completed successfully" in line:
            if preload_pass_pattern.fullmatch(line) is None:
                raise ConvHardwareExecplanError(
                    f"malformed preload readback PASS marker in simulator console: line={line_number}"
                )
            if stage_markers or all_stages_markers:
                raise ConvHardwareExecplanError(
                    "preload readback PASS marker appears after runtime execution started"
                )
            preload_pass_lines.append(line_number)
        if "RUNTIME_STAGE_COMPLETE" in line:
            match = stage_pattern.fullmatch(line)
            if match is None:
                raise ConvHardwareExecplanError(
                    f"malformed runtime stage marker in simulator console: line={line_number}"
                )
            if all_stages_markers:
                raise ConvHardwareExecplanError(
                    "runtime stage marker appears after the all-stages marker"
                )
            expected_stage_index = len(stage_markers)
            stage_index = int(match.group("stage"))
            if stage_index != expected_stage_index:
                raise ConvHardwareExecplanError(
                    "runtime stage markers are not in exact 0..N-1 order: "
                    f"expected={expected_stage_index}, observed={stage_index}"
                )
            if stage_index >= len(expected_mask_values):
                raise ConvHardwareExecplanError(
                    f"runtime stage marker index exceeds the package contract: {stage_index}"
                )
            observed_mask_value = int(match.group("mask"), 16)
            expected_mask_value = expected_mask_values[stage_index]
            if observed_mask_value != expected_mask_value:
                raise ConvHardwareExecplanError(
                    "runtime stage marker mask differs from the package manifest: "
                    f"stage={stage_index}, expected=0x{expected_mask_value:07X}, "
                    f"observed=0x{observed_mask_value:07X}"
                )
            stage_markers.append(
                {
                    "stage_index": stage_index,
                    "slice_mask": f"0x{observed_mask_value:07X}",
                    "timestamp": int(match.group("time")),
                    "cycles": int(match.group("cycles")),
                    "line_number": line_number,
                }
            )
        elif "RUNTIME_ALL_STAGES_COMPLETE" in line:
            match = all_stages_pattern.fullmatch(line)
            if match is None:
                raise ConvHardwareExecplanError(
                    f"malformed all-stages marker in simulator console: line={line_number}"
                )
            if all_stages_markers:
                raise ConvHardwareExecplanError(
                    "simulator console contains more than one all-stages marker"
                )
            completed_count = int(match.group("count"))
            if len(stage_markers) != len(expected_mask_values):
                raise ConvHardwareExecplanError(
                    "all-stages marker appears before the final runtime stage marker"
                )
            if completed_count != len(expected_mask_values):
                raise ConvHardwareExecplanError(
                    "all-stages marker count differs from the package contract"
                )
            all_stages_markers.append(
                {
                    "count": completed_count,
                    "timestamp": int(match.group("time")),
                    "line_number": line_number,
                }
            )

        if "Simulation exit status:" in line:
            match = exit_status_pattern.fullmatch(line)
            if match is None:
                raise ConvHardwareExecplanError(
                    f"malformed simulation exit status in simulator console: line={line_number}"
                )
            if not all_stages_markers:
                raise ConvHardwareExecplanError(
                    "simulation exit status appears before the all-stages marker"
                )
            exit_status_records.append(
                {"status": int(match.group("status")), "line_number": line_number}
            )

    if len(preload_pass_lines) != expected_preload_transfer_count:
        raise ConvHardwareExecplanError(
            "simulator console preload readback PASS count differs from the package contract: "
            f"expected={expected_preload_transfer_count}, observed={len(preload_pass_lines)}"
        )
    if len(stage_markers) != len(expected_mask_values):
        raise ConvHardwareExecplanError(
            "simulator console runtime stage marker count differs from the package contract"
        )
    if len(all_stages_markers) != 1:
        raise ConvHardwareExecplanError(
            "simulator console must contain exactly one all-stages marker"
        )
    if len(exit_status_records) != 1:
        raise ConvHardwareExecplanError(
            "simulator console must contain exactly one simulation exit status"
        )
    console_exit_status = exit_status_records[0]["status"]
    if console_exit_status != expected_simulator_exit_status:
        raise ConvHardwareExecplanError(
            "simulation exit status in console differs from return metadata"
        )

    return {
        "sha256": _sha256_bytes(console_payload),
        "simulation_exit_status": console_exit_status,
        "simulation_exit_status_line": exit_status_records[0]["line_number"],
        "preload_readback_pass_count": len(preload_pass_lines),
        "preload_readback_pass_lines": preload_pass_lines,
        "completed_runtime_stage_count": len(stage_markers),
        "stage_markers": stage_markers,
        "all_stages_marker": all_stages_markers[0],
    }


def _validate_returned_config_file_set(
    actual_return_files: Mapping[PurePosixPath, Path],
    approved_identity: Mapping[str, Any],
) -> None:
    """Reject missing or extra returned config files before deeper parsing."""

    expected_config_files = {
        PurePosixPath("config/sca_cfg.json"),
        PurePosixPath("config/sca_cfg_D.json"),
        PurePosixPath("config/server_source_inventory.tsv"),
        PurePosixPath("config/metadata/manifest.json"),
        PurePosixPath("config/metadata/runner_contract.json"),
        PurePosixPath("config/metadata/dump_contract.json"),
        PurePosixPath("config/metadata/readback_regions.tsv"),
        PurePosixPath("config/metadata/expected_runtime_stages.tsv"),
        PurePosixPath("config/metadata/runtime_identity.json"),
    }
    for identity_key in (
        "launch_file_contract",
        "launch_identity",
        "runtime_make_override",
        "run_command_contract",
        "runner_identity",
    ):
        approved_record = approved_identity.get(identity_key)
        if not isinstance(approved_record, Mapping) or not isinstance(
            approved_record.get("path"), str
        ):
            raise ConvHardwareExecplanError(
                f"approved runtime identity record is invalid: {identity_key}"
            )
        raw_approved_path = str(approved_record["path"])
        approved_posix_path = PurePosixPath(raw_approved_path)
        approved_windows_path = PureWindowsPath(raw_approved_path)
        if (
            approved_posix_path.is_absolute()
            or approved_windows_path.is_absolute()
            or bool(approved_windows_path.anchor)
            or "\\" in raw_approved_path
            or any(part in {"", ".", ".."} for part in approved_posix_path.parts)
            or "metadata" not in approved_posix_path.parts
        ):
            raise ConvHardwareExecplanError(
                f"approved runtime metadata path is unsafe: {identity_key}"
            )
        metadata_index = max(
            index
            for index, part in enumerate(approved_posix_path.parts)
            if part == "metadata"
        )
        metadata_suffix = approved_posix_path.parts[metadata_index + 1 :]
        if len(metadata_suffix) != 1:
            raise ConvHardwareExecplanError(
                f"approved runtime metadata path has an invalid suffix: {identity_key}"
            )
        expected_config_files.add(
            PurePosixPath("config/metadata") / metadata_suffix[0]
        )
    actual_config_files = {
        relative
        for relative in actual_return_files
        if relative.parts and relative.parts[0] == "config"
    }
    if actual_config_files != expected_config_files:
        raise ConvHardwareExecplanError(
            "returned config/metadata exact set differs from the approved identity: "
            f"missing={sorted(str(path) for path in expected_config_files - actual_config_files)}, "
            f"extra={sorted(str(path) for path in actual_config_files - expected_config_files)}"
        )


def validate_conv_hardware_region_return(
    package_root: Path,
    return_root: Path,
    approved_runtime_identity_path: Path,
) -> dict[str, Any]:
    """Fail closed on server status/provenance before numeric region comparison."""

    package = package_root.resolve()
    returned = return_root.resolve()
    approved_identity_path = approved_runtime_identity_path.resolve()
    try:
        approved_identity_path.relative_to(returned)
    except ValueError:
        pass
    else:
        raise ConvHardwareExecplanError(
            "locally approved runtime identity must be outside the server return root"
        )
    if not approved_identity_path.is_file():
        raise ConvHardwareExecplanError(
            "locally approved runtime identity file is missing: "
            f"{approved_identity_path}"
        )
    approved_identity_file_sha256 = _sha256_file(approved_identity_path)
    approved_identity = _read_json_object(approved_identity_path)
    validate_conv_hardware_execplan_package(package)
    runner = _read_json_object(package / "runner_contract.json")
    package_manifest = _read_json_object(package / "manifest.json")
    package_manifest_sha256 = _sha256_file(package / "manifest.json")
    package_sca = _read_json_object(package / "sca_cfg.json")
    package_sca_d = _read_json_object(package / "sca_cfg_D.json")
    package_dump_contract = _read_json_object(package / "dump_contract.json")
    metadata = _read_json_object(
        _resolve_contained_relative_path(
            returned,
            "run_metadata.json",
            label="server return metadata path",
        )
    )

    return_contract_path = _resolve_contained_relative_path(
        returned,
        "return_file_contract.tsv",
        label="server return whole-tree contract path",
    )
    if return_contract_path.is_symlink() or not return_contract_path.is_file():
        raise ConvHardwareExecplanError(
            "server return whole-tree contract must be a regular file"
        )
    expected_return_files: dict[PurePosixPath, tuple[int, str]] = {}
    try:
        return_contract_lines = return_contract_path.read_text(
            encoding="utf-8"
        ).splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ConvHardwareExecplanError(
            "cannot read server return whole-tree contract"
        ) from error
    if not return_contract_lines:
        raise ConvHardwareExecplanError("server return whole-tree contract is empty")
    for line_number, line in enumerate(return_contract_lines, 1):
        fields = line.split("\t")
        if (
            len(fields) != 3
            or not fields[0]
            or re.fullmatch(r"0|[1-9][0-9]*", fields[1]) is None
            or re.fullmatch(r"[0-9a-f]{64}", fields[2]) is None
        ):
            raise ConvHardwareExecplanError(
                f"malformed server return whole-tree contract line: {line_number}"
            )
        raw_path, raw_size, expected_hash = fields
        posix_path = PurePosixPath(raw_path)
        windows_path = PureWindowsPath(raw_path)
        if (
            posix_path.is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.anchor)
            or "\\" in raw_path
            or any(part in {"", ".", ".."} for part in posix_path.parts)
            or posix_path == PurePosixPath("return_file_contract.tsv")
            or posix_path in expected_return_files
        ):
            raise ConvHardwareExecplanError(
                f"unsafe/duplicate server return contract path: {line_number}"
            )
        expected_return_files[posix_path] = (int(raw_size), expected_hash)
    actual_return_files: dict[PurePosixPath, Path] = {}
    allowed_top_level = {
        "config",
        "diagnostic_allowlist.tsv",
        "preload_readback_report.json",
        "readback_regions",
        "return_archive_policy.json",
        "return_file_contract.tsv",
        "run_metadata.json",
        "run_sim_results",
        "server_source_provenance.json",
        "sim_results",
    }
    for actual_path in returned.rglob("*"):
        relative = PurePosixPath(actual_path.relative_to(returned).as_posix())
        if not relative.parts or relative.parts[0] not in allowed_top_level:
            raise ConvHardwareExecplanError(
                f"server return contains an unapproved top-level path: {relative}"
            )
        if actual_path.is_symlink():
            raise ConvHardwareExecplanError(
                f"server return contains a symlink: {relative}"
            )
        if actual_path.is_dir():
            continue
        if not actual_path.is_file():
            raise ConvHardwareExecplanError(
                f"server return contains a non-regular object: {relative}"
            )
        if relative != PurePosixPath("return_file_contract.tsv"):
            actual_return_files[relative] = actual_path
    if set(actual_return_files) != set(expected_return_files):
        missing = sorted(str(path) for path in set(expected_return_files) - set(actual_return_files))
        extra = sorted(str(path) for path in set(actual_return_files) - set(expected_return_files))
        raise ConvHardwareExecplanError(
            "server return whole-tree exact set differs: "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )
    for relative, (expected_size, expected_hash) in expected_return_files.items():
        actual_path = actual_return_files[relative]
        if actual_path.stat().st_size != expected_size or _sha256_file(actual_path) != expected_hash:
            raise ConvHardwareExecplanError(
                f"server return whole-tree file identity differs: {relative}"
            )

    _validate_returned_config_file_set(actual_return_files, approved_identity)

    required_metadata = runner.get("required_return_metadata")
    if not isinstance(required_metadata, list) or not all(
        isinstance(key, str) and key for key in required_metadata
    ):
        raise ConvHardwareExecplanError("required return metadata contract is invalid")
    missing = [
        key
        for key in required_metadata
        if key not in metadata or metadata[key] in (None, "", [], {})
    ]
    if missing:
        raise ConvHardwareExecplanError(
            "server return metadata is incomplete: " + ", ".join(missing)
        )
    run_command = metadata.get("run_command")
    if not isinstance(run_command, str) or not run_command.strip():
        raise ConvHardwareExecplanError(
            "server return metadata run_command must be a non-empty string"
        )

    def integer_metadata(key: str) -> int:
        value = metadata.get(key)
        if isinstance(value, bool):
            raise ConvHardwareExecplanError(f"return metadata {key} is not an integer")
        try:
            return int(value)
        except (TypeError, ValueError) as error:
            raise ConvHardwareExecplanError(
                f"return metadata {key} is not an integer"
            ) from error

    if integer_metadata("exit_status") != 0:
        raise ConvHardwareExecplanError(
            f"server runner failed with exit status {metadata['exit_status']}"
        )
    if integer_metadata("simulator_exit_status") != 0:
        raise ConvHardwareExecplanError(
            "simulator exit status is non-zero: "
            f"{metadata['simulator_exit_status']}"
        )
    for status_key in (
        "process_exit_status",
        "make_exit_status",
        "tee_exit_status",
        "phase_watchdog_exit_status",
        "raw_phase_watchdog_exit_status",
    ):
        if integer_metadata(status_key) != 0:
            raise ConvHardwareExecplanError(
                f"server process pipeline status is non-zero: {status_key}={metadata[status_key]}"
            )
    if metadata.get("simulator_exit_status_observed") is not True:
        raise ConvHardwareExecplanError(
            "server did not independently observe the simulator exit status"
        )
    expected_status_values = {
        "execution_environment": "rtl_simulation",
        "board_version": "not_applicable_rtl_simulation",
        "firmware_version": "not_applicable_rtl_simulation",
        "isa_contract": "model_execplan_package_manifest_and_execplan_128bit_v1",
        "timeout_status": "not_timed_out",
        "phase_timeout_status": "not_timed_out",
        "phase_timeout_phase": "none",
        "termination_kind": "natural_process_exit",
        "preflight_status": "passed",
        "wall_timeout": "24h",
        "phase_failure_reason": "none",
        "make_archive_policy": "runner_no_archive_target_v1",
        "return_archive_policy": "bounded_exact_set_allowlist_v2",
    }
    for status_key, expected_value in expected_status_values.items():
        if metadata.get(status_key) != expected_value:
            raise ConvHardwareExecplanError(
                "server run status differs from the successful completion contract: "
                f"{status_key}={metadata.get(status_key)!r}"
            )
    server_run_id = metadata.get("server_run_id")
    if server_run_id not in {"run1", "run2"}:
        raise ConvHardwareExecplanError("server run ID is invalid")
    if metadata.get("server_source_provenance") != "server_source_provenance.json":
        raise ConvHardwareExecplanError(
            "server source provenance reference differs from the approved contract"
        )

    server_source_provenance = _read_json_object(
        _resolve_contained_relative_path(
            returned,
            "server_source_provenance.json",
            label="server source provenance path",
        )
    )
    expected_source_provenance_keys = {
        "schema_version",
        "server_run_id",
        "identity_policy",
        "preflight_source_policy",
        "makefile_sha256",
        "testbench_sha256",
        "top_filelist_sha256",
        "source_inventory_sha256",
        "entrypoint_record_count",
        "environment_record_count",
        "dir_home_value_sha256",
    }
    if set(server_source_provenance) != expected_source_provenance_keys:
        raise ConvHardwareExecplanError(
            "server source provenance exact field set differs"
        )
    if (
        server_source_provenance.get("schema_version")
        != "resnet50-server-source-provenance-0.4"
        or server_source_provenance.get("server_run_id") != server_run_id
        or server_source_provenance.get("identity_policy")
        != "logical_entrypoints_and_dir_home_recorded_nonblocking"
        or server_source_provenance.get("preflight_source_policy")
        != "readable_logical_entrypoints_only"
        or server_source_provenance.get("testbench_sha256")
        != metadata.get("testbench_sha256")
    ):
        raise ConvHardwareExecplanError(
            "server source provenance identity differs from return metadata"
        )
    for source_hash_key in (
        "makefile_sha256",
        "testbench_sha256",
        "top_filelist_sha256",
        "source_inventory_sha256",
        "dir_home_value_sha256",
    ):
        if re.fullmatch(
            r"[0-9a-f]{64}", str(server_source_provenance.get(source_hash_key, ""))
        ) is None:
            raise ConvHardwareExecplanError(
                f"server source provenance hash is invalid: {source_hash_key}"
            )
    source_inventory_path = _resolve_contained_relative_path(
        returned,
        "config/server_source_inventory.tsv",
        label="server source inventory path",
    )
    if source_inventory_path.is_symlink() or not source_inventory_path.is_file():
        raise ConvHardwareExecplanError(
            "server source inventory must be a regular file"
        )
    source_inventory_payload = source_inventory_path.read_bytes()
    if (
        not source_inventory_payload
        or not source_inventory_payload.endswith(b"\n")
        or b"\r" in source_inventory_payload
    ):
        raise ConvHardwareExecplanError(
            "server source inventory must be nonempty LF-only text"
        )
    if _sha256_bytes(source_inventory_payload) != server_source_provenance.get(
        "source_inventory_sha256"
    ):
        raise ConvHardwareExecplanError(
            "server source inventory differs from its provenance hash"
        )
    try:
        source_inventory_lines = source_inventory_payload.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise ConvHardwareExecplanError(
            "server source inventory is not UTF-8"
        ) from error
    if source_inventory_lines != sorted(source_inventory_lines):
        raise ConvHardwareExecplanError(
            "server source inventory is not canonically sorted"
        )
    source_inventory_records: dict[str, dict[str, Any]] = {}
    expected_entrypoints = {
        "Makefile.tb_NDP_Top_new_phy": "makefile_sha256",
        "tb_NDP_Top_new_phy.sv": "testbench_sha256",
        "rtl/filelists/NDP_Top_phy_filelist.f": "top_filelist_sha256",
    }
    for line_number, line in enumerate(source_inventory_lines, 1):
        fields = line.split("\t")
        if fields[0] == "entrypoint" if fields else False:
            if (
                len(fields) != 5
                or fields[1] not in expected_entrypoints
                or not fields[2].startswith("physical:/")
                or re.fullmatch(r"[0-9]+", fields[3]) is None
                or re.fullmatch(r"[0-9a-f]{64}", fields[4]) is None
            ):
                raise ConvHardwareExecplanError(
                    f"malformed server source inventory line: {line_number}"
                )
            _, raw_source_path, _, source_size, source_hash = fields
            source_posix_path = PurePosixPath(raw_source_path)
            source_windows_path = PureWindowsPath(raw_source_path)
            if (
                source_posix_path.is_absolute()
                or source_windows_path.is_absolute()
                or bool(source_windows_path.anchor)
                or "\\" in raw_source_path
                or any(part in {"", ".", ".."} for part in source_posix_path.parts)
                or raw_source_path in source_inventory_records
            ):
                raise ConvHardwareExecplanError(
                    f"unsafe/duplicate server source inventory path: {line_number}"
                )
            source_inventory_records[raw_source_path] = {
                "category": "entrypoint",
                "logical_path": raw_source_path,
                "physical_path": fields[2].removeprefix("physical:"),
                "size_bytes": int(source_size),
                "sha256": source_hash,
            }
            continue
        if fields[0] == "environment" if fields else False:
            if (
                len(fields) != 6
                or fields[1] != "DIR_HOME"
                or fields[2] not in {"set", "unset"}
                or not fields[3].startswith("value:")
                or not fields[4].startswith("vendor_physical:")
                or re.fullmatch(r"[0-9a-f]{64}", fields[5]) is None
            ):
                raise ConvHardwareExecplanError(
                    f"malformed server environment inventory line: {line_number}"
                )
            environment_key = "environment:DIR_HOME"
            dir_home_value = fields[3].removeprefix("value:")
            vendor_physical_path = fields[4].removeprefix("vendor_physical:")
            vendor_posix_path = PurePosixPath(vendor_physical_path)
            vendor_windows_path = PureWindowsPath(vendor_physical_path)
            if (
                environment_key in source_inventory_records
                or (fields[2] == "unset" and dir_home_value != "")
                or (
                    vendor_physical_path != "unresolved"
                    and not vendor_posix_path.is_absolute()
                    and not vendor_windows_path.is_absolute()
                    and not bool(vendor_windows_path.anchor)
                )
                or _sha256_bytes(dir_home_value.encode("utf-8")) != fields[5]
            ):
                raise ConvHardwareExecplanError(
                    f"unsafe/duplicate server environment inventory: {line_number}"
                )
            source_inventory_records[environment_key] = {
                "category": "environment",
                "name": "DIR_HOME",
                "state": fields[2],
                "value": dir_home_value,
                "vendor_physical_path": vendor_physical_path,
                "value_sha256": fields[5],
            }
            continue
        raise ConvHardwareExecplanError(
            f"malformed server source inventory line: {line_number}"
        )
    try:
        entrypoint_record_count = int(
            server_source_provenance["entrypoint_record_count"]
        )
        environment_record_count = int(
            server_source_provenance["environment_record_count"]
        )
    except (TypeError, ValueError) as error:
        raise ConvHardwareExecplanError(
            "server entrypoint provenance count is invalid"
        ) from error
    if (
        entrypoint_record_count != 3
        or environment_record_count != 1
        or set(source_inventory_records)
        != {*expected_entrypoints, "environment:DIR_HOME"}
    ):
        raise ConvHardwareExecplanError(
            "server entrypoint provenance exact set differs"
        )
    for entrypoint, provenance_hash_key in expected_entrypoints.items():
        if source_inventory_records[entrypoint]["sha256"] != (
            server_source_provenance.get(provenance_hash_key)
        ):
            raise ConvHardwareExecplanError(
                f"server entrypoint identity differs from provenance: {entrypoint}"
            )
    if source_inventory_records["environment:DIR_HOME"]["value_sha256"] != (
        server_source_provenance.get("dir_home_value_sha256")
    ):
        raise ConvHardwareExecplanError(
            "server DIR_HOME identity differs from provenance"
        )
    if integer_metadata("phase_stall_seconds") != 0:
        raise ConvHardwareExecplanError(
            "successful server return reports a non-zero phase stall duration"
        )
    if metadata.get("phase_watchdog_done") is not True:
        raise ConvHardwareExecplanError(
            "successful server return lacks the watchdog completion sentinel"
        )
    try:
        expected_stages = int(
            runner["execution"]["completion_gate"]["expected_runtime_stage_count"]
        )
        expected_regions = int(runner["post_run_dump"]["expected_region_count"])
    except (KeyError, TypeError, ValueError) as error:
        raise ConvHardwareExecplanError(
            "runner stage/region return contract is invalid"
        ) from error
    runtime_operators = package_manifest.get("runtime_operators")
    if not isinstance(runtime_operators, list) or len(runtime_operators) != expected_stages:
        raise ConvHardwareExecplanError(
            "package runtime operator list differs from the runner stage contract"
        )
    expected_slice_masks: list[str] = []
    for stage_index, operator in enumerate(runtime_operators):
        if not isinstance(operator, Mapping) or not isinstance(
            operator.get("slice_mask"), str
        ):
            raise ConvHardwareExecplanError(
                f"package runtime operator is missing its slice mask: stage={stage_index}"
            )
        expected_slice_masks.append(str(operator["slice_mask"]))
    if (
        integer_metadata("completed_runtime_stage_count") != expected_stages
        or integer_metadata("expected_runtime_stage_count") != expected_stages
    ):
        raise ConvHardwareExecplanError("returned runtime stage count differs")
    observer_contract = package_manifest.get("testbench_observer")
    if not isinstance(observer_contract, Mapping):
        raise ConvHardwareExecplanError("package testbench observer contract is missing")
    observer_mode = observer_contract.get("mode")
    expected_repeat_num = int(observer_contract.get("repeat_num", -1))
    if (
        metadata.get("testbench_observer_mode") != observer_mode
        or integer_metadata("expected_testbench_repeat_num") != expected_repeat_num
    ):
        raise ConvHardwareExecplanError(
            "returned testbench observer identity differs from the package"
        )
    expected_logging_policy = (
        "slice_start_only_plus_runtime_devnull_sinks"
        if observer_mode == "fixed_slice0_start_slice1_finish"
        else "testbench_native"
    )
    expected_reserved_clock_validation = (
        "force_and_low_high_toggle_proof"
        if observer_mode == "fixed_slice0_start_slice1_finish"
        else "testbench_native"
    )
    if (
        metadata.get("bank_frame_logging_policy") != expected_logging_policy
        or metadata.get("reserved_clock_validation")
        != expected_reserved_clock_validation
    ):
        raise ConvHardwareExecplanError(
            "returned server runtime capability policy differs from the package observer mode"
        )
    if observer_mode == "fixed_slice0_start_slice1_finish" and (
        metadata.get("runtime_log_sink_policy")
        != "audited_sinks_unknown_log_guard_v2"
        or integer_metadata("runtime_log_total_size_limit_bytes") != 1073741824
        or integer_metadata("diagnostic_sink_count") != 1037
    ):
        raise ConvHardwareExecplanError(
            "returned runtime log-sink policy differs from the approved contract"
        )
    if observer_mode == "fixed_slice0_start_slice1_finish":
        if (
            integer_metadata("observed_slice0_start_count") != expected_repeat_num
            or integer_metadata("observed_slice1_finish_count") != expected_repeat_num
            or integer_metadata("reserved_clock_force_marker_count") != 1
            or integer_metadata("reserved_clock_failure_marker_count") != 0
        ):
            raise ConvHardwareExecplanError(
                "returned fixed-observer counts differ from the package contract"
            )
    if (
        integer_metadata("returned_region_count") != expected_regions
        or integer_metadata("expected_region_count") != expected_regions
    ):
        raise ConvHardwareExecplanError("returned region count differs")
    for status_key in (
        "stage_marker_status",
        "all_stages_marker_status",
        "readback_region_contract_status",
    ):
        if metadata.get(status_key) != "passed":
            raise ConvHardwareExecplanError(
                f"server return status did not pass: {status_key}"
            )
    expected_identity = {
        "freeze_id": package_manifest.get("freeze_id"),
        "freeze_manifest_sha256": package_manifest.get("freeze_manifest_sha256"),
        "package_manifest_sha256": package_manifest_sha256,
    }
    for key, value in expected_identity.items():
        if metadata.get(key) != value:
            raise ConvHardwareExecplanError(
                f"server return identity differs from the package: {key}"
            )

    preload_reference = metadata.get("preload_readback_report")
    if not isinstance(preload_reference, str):
        raise ConvHardwareExecplanError(
            "preload_readback_report metadata must be a relative path"
        )
    preload_report = _read_json_object(
        _resolve_contained_relative_path(
            returned,
            preload_reference,
            label="server preload/readback report path",
        )
    )

    # Count the immutable line parser's real transport entries, not semantic
    # top-level payloads.  A page-safe ExecutionPlan has a nested head and a
    # page-aligned tail, so the transport and semantic-object counts intentionally
    # differ; the current node-0004 transport count is frozen by the package.
    expected_transfer_count = len(_sca_transport_entries(package_sca))
    try:
        reported_expected_transfers = int(
            preload_report.get("expected_transfer_count", -1)
        )
        reported_passed_transfers = int(
            preload_report.get("passed_transfer_count", -2)
        )
    except (TypeError, ValueError) as error:
        raise ConvHardwareExecplanError(
            "server preload/readback counts are invalid"
        ) from error
    if (
        preload_report.get("status") != "passed"
        or reported_expected_transfers != expected_transfer_count
        or reported_passed_transfers != expected_transfer_count
    ):
        raise ConvHardwareExecplanError("server preload/readback gate did not pass")

    run_results = _resolve_contained_relative_path(
        returned,
        "run_sim_results",
        label="server run-results path",
    )
    console_files = sorted(run_results.glob("*_console.log"))
    if len(console_files) != 1:
        raise ConvHardwareExecplanError(
            "server return must contain exactly one simulator console file"
        )
    raw_console_path = console_files[0]
    if raw_console_path.is_symlink() or not raw_console_path.is_file():
        raise ConvHardwareExecplanError(
            "returned simulator console must be a regular non-symlink file"
        )
    console_path = _resolve_contained_relative_path(
        returned,
        raw_console_path.relative_to(returned).as_posix(),
        label="server simulator console path",
    )
    console_gate = _parse_runtime_completion_console(
        console_path,
        expected_preload_transfer_count=expected_transfer_count,
        expected_slice_masks=expected_slice_masks,
        expected_simulator_exit_status=integer_metadata("simulator_exit_status"),
        observer_contract=observer_contract,
    )
    if observer_mode == "fixed_slice0_start_slice1_finish" and (
        int(console_gate.get("fixed_observer_pair_count", -1)) != expected_repeat_num
        or int(console_gate.get("reserved_clock_force_marker_count", -1)) != 1
    ):
        raise ConvHardwareExecplanError(
            "offline fixed-observer console proof differs from return metadata"
        )
    exit_status_files = sorted(run_results.glob("*_exit_status.txt"))
    if len(exit_status_files) != 1:
        raise ConvHardwareExecplanError(
            "server return must contain exactly one runner exit-status file"
        )
    exit_status_file = _resolve_contained_relative_path(
        returned,
        exit_status_files[0].relative_to(returned).as_posix(),
        label="server runner exit-status path",
    )
    try:
        file_exit_status = int(exit_status_file.read_text(encoding="ascii").strip())
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ConvHardwareExecplanError("invalid runner exit-status file") from error
    if file_exit_status != integer_metadata("exit_status"):
        raise ConvHardwareExecplanError(
            "runner exit-status file differs from return metadata"
        )

    revision_prefix = raw_console_path.name.removesuffix("_console.log")
    if re.fullmatch(r"[A-Za-z0-9_.-]+", revision_prefix) is None:
        raise ConvHardwareExecplanError(
            "server run-results revision prefix is invalid"
        )
    expected_run_result_names = {
        f"{revision_prefix}_console.log",
        f"{revision_prefix}_exit_status.txt",
        f"{revision_prefix}_phase_progress.tsv",
        f"{revision_prefix}_phase_watchdog_done.tsv",
    }
    actual_run_result_names: set[str] = set()
    for run_result_path in run_results.iterdir():
        if run_result_path.is_symlink() or not run_result_path.is_file():
            raise ConvHardwareExecplanError(
                f"server run-results contains a non-regular file: {run_result_path.name}"
            )
        actual_run_result_names.add(run_result_path.name)
    if actual_run_result_names != expected_run_result_names:
        raise ConvHardwareExecplanError(
            "successful server run-results exact set differs: "
            f"missing={sorted(expected_run_result_names - actual_run_result_names)}, "
            f"extra={sorted(actual_run_result_names - expected_run_result_names)}"
        )
    watchdog_done_path = _resolve_contained_relative_path(
        returned,
        f"run_sim_results/{revision_prefix}_phase_watchdog_done.tsv",
        label="server phase-watchdog completion sentinel path",
    )
    try:
        watchdog_done_text = watchdog_done_path.read_text(encoding="ascii")
    except (OSError, UnicodeDecodeError) as error:
        raise ConvHardwareExecplanError(
            "invalid phase-watchdog completion sentinel"
        ) from error
    if watchdog_done_text != "normal_process_exit\t0\n":
        raise ConvHardwareExecplanError(
            "phase-watchdog completion sentinel content differs"
        )

    archive_policy = _read_json_object(
        _resolve_contained_relative_path(
            returned,
            "return_archive_policy.json",
            label="server return archive policy path",
        )
    )
    diagnostic_file_limit = integer_metadata("diagnostic_file_size_limit_bytes")
    diagnostic_total_limit = integer_metadata("diagnostic_total_size_limit_bytes")
    expected_archive_policy = {
        "schema_version": "resnet50-server-return-archive-policy-0.4",
        "server_run_id": server_run_id,
        "policy": "bounded_exact_set_allowlist_v2",
        "diagnostic_allowlist": "diagnostic_allowlist.tsv",
        "diagnostic_file_size_limit_bytes": 1048576,
        "diagnostic_total_size_limit_bytes": 1048576,
        "diagnostic_truncation_policy": "head_bytes_v1",
        "diagnostic_return_file_count": integer_metadata(
            "diagnostic_return_file_count"
        ),
        "diagnostic_return_total_bytes": integer_metadata(
            "diagnostic_return_total_bytes"
        ),
        "runtime_log_sink_policy": "audited_sinks_unknown_log_guard_v2",
        "runtime_log_total_size_limit_bytes": integer_metadata(
            "runtime_log_total_size_limit_bytes"
        ),
        "runtime_log_sink_count": integer_metadata("diagnostic_sink_count"),
        "make_archive_policy": "runner_no_archive_target_v1",
        "run_command_contract_sha256": metadata.get(
            "run_command_contract_sha256"
        ),
        "return_file_contract": "return_file_contract.tsv",
        "full_sim_results_copied": False,
        "waveform_included": False,
        "archive_timeout": "1h",
    }
    if (
        diagnostic_file_limit != 1048576
        or diagnostic_total_limit != 1048576
        or archive_policy != expected_archive_policy
        or metadata.get("return_file_contract") != "return_file_contract.tsv"
    ):
        raise ConvHardwareExecplanError(
            "returned bounded archive policy differs from the approved contract"
        )
    diagnostic_allowlist_path = _resolve_contained_relative_path(
        returned,
        "diagnostic_allowlist.tsv",
        label="server diagnostic allowlist path",
    )
    if diagnostic_allowlist_path.is_symlink() or not diagnostic_allowlist_path.is_file():
        raise ConvHardwareExecplanError(
            "server diagnostic allowlist must be a regular file"
        )
    diagnostic_records: dict[PurePosixPath, tuple[int, int, bool, str]] = {}
    allowed_diagnostic_paths = {
        PurePosixPath("gexec2slice/slice_all/gexec2slice.log")
    }
    try:
        diagnostic_lines = diagnostic_allowlist_path.read_text(
            encoding="utf-8"
        ).splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise ConvHardwareExecplanError(
            "cannot read server diagnostic allowlist"
        ) from error
    for line_number, line in enumerate(diagnostic_lines, 1):
        fields = line.split("\t")
        if (
            len(fields) != 5
            or not fields[1].isdigit()
            or not fields[2].isdigit()
            or fields[3] not in {"true", "false"}
            or re.fullmatch(r"[0-9a-f]{64}", fields[4]) is None
        ):
            raise ConvHardwareExecplanError(
                f"malformed server diagnostic allowlist line: {line_number}"
            )
        diagnostic_path = PurePosixPath(fields[0])
        if (
            diagnostic_path not in allowed_diagnostic_paths
            or diagnostic_path in diagnostic_records
        ):
            raise ConvHardwareExecplanError(
                f"unapproved/duplicate server diagnostic path: {line_number}"
            )
        source_size = int(fields[1])
        returned_size = int(fields[2])
        truncated = fields[3] == "true"
        if (
            returned_size > diagnostic_file_limit
            or (truncated and not (source_size > returned_size == diagnostic_file_limit))
            or (not truncated and source_size != returned_size)
        ):
            raise ConvHardwareExecplanError(
                f"server diagnostic size/truncation contract differs: {diagnostic_path}"
            )
        diagnostic_records[diagnostic_path] = (
            source_size,
            returned_size,
            truncated,
            fields[4],
        )
    diagnostic_root = returned / "sim_results"
    actual_diagnostic_files: dict[PurePosixPath, Path] = {}
    if diagnostic_root.exists():
        for diagnostic_file in diagnostic_root.rglob("*"):
            if diagnostic_file.is_dir():
                continue
            diagnostic_relative = PurePosixPath(
                diagnostic_file.relative_to(diagnostic_root).as_posix()
            )
            if diagnostic_file.is_symlink() or not diagnostic_file.is_file():
                raise ConvHardwareExecplanError(
                    f"returned diagnostic is not a regular file: {diagnostic_relative}"
                )
            actual_diagnostic_files[diagnostic_relative] = diagnostic_file
    if set(actual_diagnostic_files) != set(diagnostic_records):
        raise ConvHardwareExecplanError(
            "returned diagnostic files differ from the diagnostic allowlist"
        )
    diagnostic_total = 0
    for diagnostic_relative, diagnostic_file in actual_diagnostic_files.items():
        _, returned_size, _, expected_hash = diagnostic_records[diagnostic_relative]
        if (
            diagnostic_file.stat().st_size != returned_size
            or _sha256_file(diagnostic_file) != expected_hash
        ):
            raise ConvHardwareExecplanError(
                f"returned diagnostic identity differs: {diagnostic_relative}"
            )
        diagnostic_total += returned_size
    if (
        diagnostic_total > diagnostic_total_limit
        or len(diagnostic_records)
        != integer_metadata("diagnostic_return_file_count")
        or diagnostic_total != integer_metadata("diagnostic_return_total_bytes")
    ):
        raise ConvHardwareExecplanError(
            "returned diagnostic count/total differs from the bounded policy"
        )

    identity_path = _resolve_contained_relative_path(
        returned,
        "config/metadata/runtime_identity.json",
        label="returned runtime identity path",
    )
    identity = _read_json_object(identity_path)
    identity_file_sha256 = _sha256_file(identity_path)
    if identity_file_sha256 != str(metadata["runtime_identity_sha256"]):
        raise ConvHardwareExecplanError("runtime identity hash differs")
    approved_identity_sha256 = _canonical_json_sha256(approved_identity)
    if _canonical_json_sha256(identity) != approved_identity_sha256:
        raise ConvHardwareExecplanError(
            "returned runtime identity differs from the locally approved identity"
        )
    approved_runner = approved_identity.get("runner")
    if (
        not isinstance(approved_runner, Mapping)
        or not isinstance(approved_runner.get("sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", str(approved_runner["sha256"])) is None
        or metadata.get("runner_sha256") != approved_runner["sha256"]
    ):
        raise ConvHardwareExecplanError(
            "return metadata runner hash differs from the locally approved identity"
        )
    for key, value in expected_identity.items():
        if identity.get(key) != value:
            raise ConvHardwareExecplanError(
                f"runtime identity differs from the package: {key}"
            )
    if (
        int(identity.get("expected_runtime_stage_count", -1)) != expected_stages
        or int(identity.get("expected_runtime_transfer_count", -1))
        != expected_transfer_count
        or int(identity.get("expected_region_count", -1)) != expected_regions
    ):
        raise ConvHardwareExecplanError(
            "runtime identity transfer/stage/region count differs"
        )
    if (
        identity.get("make_archive_policy") != "runner_no_archive_target_v1"
        or identity.get("make_environment_policy")
        != "unset_MAKEFLAGS_MAKEFILES_GNUMAKEFLAGS_MFLAGS_MAKELEVEL_before_launch"
        or identity.get("static_install_exact_set_policy")
        != "launch_manifest_plus_four_content_addressed_identity_files"
        or identity.get("return_archive_policy")
        != "bounded_exact_set_allowlist_v2"
        or identity.get("runtime_log_sink_policy")
        != {
            "policy": "audited_sinks_unknown_log_guard_v2",
            "expected_sink_count": 1037,
            "allowed_regular_files": [
                "gexec2slice/slice_all/gexec2slice.log"
            ],
            "runtime_total_size_limit_bytes": 1073741824,
            "overlay_symlinks_allowed": False,
            "return_symlinks_allowed": False,
        }
        or identity.get("diagnostic_limits")
        != {
            "file_size_limit_bytes": 1048576,
            "total_size_limit_bytes": 1048576,
            "truncation_policy": "head_bytes_v1",
        }
    ):
        raise ConvHardwareExecplanError(
            "runtime identity non-HDL execution policies differ"
        )
    required_server_entrypoints = [
        "Makefile.tb_NDP_Top_new_phy",
        "tb_NDP_Top_new_phy.sv",
        "rtl/filelists/NDP_Top_phy_filelist.f",
    ]
    server_source_policy = identity.get("server_source_policy")
    if (
        not isinstance(server_source_policy, Mapping)
        or server_source_policy.get("mode")
        != "readable_logical_entrypoints_with_nonblocking_provenance"
        or server_source_policy.get("content_hash_required") is not False
        or server_source_policy.get("actual_hash_inventory_required")
        != "entrypoints_and_DIR_HOME"
        or server_source_policy.get("include_directory_validation_required")
        is not False
        or server_source_policy.get(
            "external_vendor_include_tree_equivalence_required"
        )
        is not False
        or server_source_policy.get("physical_source_path_inside_server_root_required")
        is not False
        or server_source_policy.get("required_entrypoints")
        != required_server_entrypoints
        or metadata.get("rtl_version") != "server_entrypoint_unpinned"
    ):
        raise ConvHardwareExecplanError(
            "returned server-source entrypoint policy differs from the approved runtime identity"
        )
    rtl_source_provenance = identity.get("rtl_source_provenance")
    if (
        rtl_source_provenance is not None
        and (
            not isinstance(rtl_source_provenance, str)
            or re.fullmatch(r"[0-9a-f]{40}", rtl_source_provenance) is None
        )
    ):
        raise ConvHardwareExecplanError("runtime RTL provenance label is invalid")

    def returned_metadata_record_path(identity_key: str, *, label: str) -> Path:
        record = identity.get(identity_key)
        if not isinstance(record, Mapping) or not isinstance(record.get("path"), str):
            raise ConvHardwareExecplanError(
                f"runtime identity record is invalid: {identity_key}"
            )
        raw_path = str(record["path"])
        posix_path = PurePosixPath(raw_path)
        windows_path = PureWindowsPath(raw_path)
        if (
            posix_path.is_absolute()
            or windows_path.is_absolute()
            or bool(windows_path.anchor)
            or "\\" in raw_path
            or any(part in {"", ".", ".."} for part in posix_path.parts)
            or "metadata" not in posix_path.parts
        ):
            raise ConvHardwareExecplanError(
                f"runtime identity metadata path is not canonical: {identity_key}"
            )
        metadata_index = max(
            index
            for index, part in enumerate(posix_path.parts)
            if part == "metadata"
        )
        metadata_suffix = posix_path.parts[metadata_index + 1 :]
        if len(metadata_suffix) != 1:
            raise ConvHardwareExecplanError(
                f"runtime identity metadata path has an invalid suffix: {identity_key}"
            )
        return _resolve_contained_relative_path(
            returned,
            (PurePosixPath("config/metadata") / metadata_suffix[0]).as_posix(),
            label=label,
        )

    returned_sca = _resolve_contained_relative_path(
        returned,
        "config/sca_cfg.json",
        label="returned relocated SCA path",
    )
    returned_sca_d = _resolve_contained_relative_path(
        returned,
        "config/sca_cfg_D.json",
        label="returned relocated SCA_D path",
    )
    returned_readback_contract = returned_metadata_record_path(
        "readback_region_contract",
        label="returned readback-region contract path",
    )
    if returned_readback_contract.is_symlink() or not returned_readback_contract.is_file():
        raise ConvHardwareExecplanError(
            "returned readback-region contract must be a regular file"
        )
    returned_stage_contract = returned_metadata_record_path(
        "runtime_stage_contract",
        label="returned runtime-stage contract path",
    )
    returned_launch_file_contract = returned_metadata_record_path(
        "launch_file_contract",
        label="returned launch-file contract path",
    )
    returned_launch_identity = returned_metadata_record_path(
        "launch_identity",
        label="returned launch identity path",
    )
    returned_runtime_make_override = returned_metadata_record_path(
        "runtime_make_override",
        label="returned runtime Make override path",
    )
    returned_run_command_contract = returned_metadata_record_path(
        "run_command_contract",
        label="returned run-command argv contract path",
    )
    returned_runner_identity = returned_metadata_record_path(
        "runner_identity",
        label="returned runner self-identity path",
    )
    for contract_name, contract_path in (
        ("relocated SCA", returned_sca),
        ("relocated SCA_D", returned_sca_d),
        ("readback-region contract", returned_readback_contract),
        ("runtime-stage contract", returned_stage_contract),
        ("launch-file contract", returned_launch_file_contract),
        ("launch identity", returned_launch_identity),
        ("runtime Make override", returned_runtime_make_override),
        ("run-command argv contract", returned_run_command_contract),
        ("runner self-identity", returned_runner_identity),
    ):
        if contract_path.is_symlink() or not contract_path.is_file():
            raise ConvHardwareExecplanError(
                f"returned {contract_name} must be a regular file"
            )
    try:
        returned_readback_contract_payload = returned_readback_contract.read_bytes()
        returned_readback_contract_text = returned_readback_contract_payload.decode(
            "utf-8"
        )
    except (OSError, UnicodeDecodeError) as error:
        raise ConvHardwareExecplanError(
            "cannot read returned readback-region contract"
        ) from error
    precomputed_file_hashes = {
        returned_readback_contract: _sha256_bytes(
            returned_readback_contract_payload
        )
    }
    identity_hash_checks = (
        ("relocated_sca_cfg", returned_sca, "sca_cfg_sha256"),
        ("relocated_sca_cfg_D", returned_sca_d, "sca_cfg_D_sha256"),
        ("runner", None, "runner_sha256"),
        (
            "readback_region_contract",
            returned_readback_contract,
            "readback_contract_sha256",
        ),
        (
            "runtime_stage_contract",
            returned_stage_contract,
            "stage_contract_sha256",
        ),
        (
            "launch_file_contract",
            returned_launch_file_contract,
            "launch_files_contract_sha256",
        ),
        (
            "launch_identity",
            returned_launch_identity,
            "launch_identity_sha256",
        ),
        (
            "runtime_make_override",
            returned_runtime_make_override,
            "runtime_make_override_sha256",
        ),
        (
            "run_command_contract",
            returned_run_command_contract,
            "run_command_contract_sha256",
        ),
        (
            "runner_identity",
            returned_runner_identity,
            "runner_identity_sha256",
        ),
    )
    verified_runtime_hashes: dict[str, str] = {}
    for identity_key, file_path, metadata_key in identity_hash_checks:
        record = identity.get(identity_key)
        if not isinstance(record, Mapping) or not isinstance(record.get("sha256"), str):
            raise ConvHardwareExecplanError(
                f"runtime identity record is invalid: {identity_key}"
            )
        expected_hash = str(record["sha256"])
        if re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
            raise ConvHardwareExecplanError(
                f"runtime identity hash is invalid: {identity_key}"
            )
        if file_path is not None:
            actual_hash = precomputed_file_hashes.get(file_path)
            if actual_hash is None:
                actual_hash = _sha256_file(file_path)
            if actual_hash != expected_hash:
                raise ConvHardwareExecplanError(
                    f"returned runtime config differs: {identity_key}"
                )
            verified_runtime_hashes[identity_key] = actual_hash
        if metadata_key is not None and metadata.get(metadata_key) != expected_hash:
            raise ConvHardwareExecplanError(
                f"returned runtime hash differs: {identity_key}"
            )

    approved_runner_path = approved_runner.get("path")
    if not isinstance(approved_runner_path, str):
        raise ConvHardwareExecplanError("approved runner path is invalid")
    expected_runner_identity_text = (
        f"{approved_runner['sha256']}  {PurePosixPath(approved_runner_path).name}\n"
    )
    try:
        returned_runner_identity_text = returned_runner_identity.read_text(
            encoding="ascii"
        )
    except (OSError, UnicodeDecodeError) as error:
        raise ConvHardwareExecplanError(
            "cannot read returned runner self-identity"
        ) from error
    if returned_runner_identity_text != expected_runner_identity_text:
        raise ConvHardwareExecplanError(
            "returned runner self-identity does not bind the approved runner"
        )

    launch_identity_payload = _read_json_object(returned_launch_identity)
    run_command_identity = identity.get("run_command_contract")
    make_override_identity = identity.get("runtime_make_override")
    if (
        not isinstance(run_command_identity, Mapping)
        or not isinstance(make_override_identity, Mapping)
        or launch_identity_payload.get("run_command_contract")
        != {
            "path": run_command_identity.get("path"),
            "sha256": run_command_identity.get("sha256"),
            "argument_count": run_command_identity.get("argument_count"),
        }
        or launch_identity_payload.get("runtime_make_override")
        != {
            "path": make_override_identity.get("path"),
            "sha256": make_override_identity.get("sha256"),
            "target": make_override_identity.get("target"),
        }
    ):
        raise ConvHardwareExecplanError(
            "launch/runtime command identity records differ"
        )
    try:
        run_argv = returned_run_command_contract.read_text(
            encoding="utf-8"
        ).splitlines()
        make_override_text = returned_runtime_make_override.read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeDecodeError) as error:
        raise ConvHardwareExecplanError(
            "cannot read returned command/Make contracts"
        ) from error
    try:
        expected_argument_count = int(run_command_identity.get("argument_count", -1))
    except (TypeError, ValueError) as error:
        raise ConvHardwareExecplanError(
            "approved run-command argument count is invalid"
        ) from error
    no_archive_target = make_override_identity.get("target")
    if (
        not isinstance(no_archive_target, str)
        or re.fullmatch(r"v[a-z0-9]+_sim_no_archive", no_archive_target) is None
        or len(run_argv) != expected_argument_count
        or len(run_argv) < 10
        or run_argv[:4]
        != ["make", "-f", "Makefile.tb_NDP_Top_new_phy", "-f"]
        or run_argv[5:7] != ["compile", no_archive_target]
        or "sim" in run_argv
        or "archive_sim_results" in run_argv
        or metadata.get("run_command") != " | ".join(run_argv)
    ):
        raise ConvHardwareExecplanError(
            "returned execution argv differs from the approved no-archive command"
        )
    required_command_arguments = {
        "DUMP_VCD=0",
        "DUMP_FSDB=0",
        "TB_DUMP_FSDB=0",
    }
    if observer_mode == "fixed_slice0_start_slice1_finish":
        required_command_arguments.add(
            "VCS_EXTRA_OPTS=-debug_access+all +define+BANK_FRAME_LOG_SLICE_START_ONLY"
        )
    if not required_command_arguments.issubset(set(run_argv)) or not any(
        argument.startswith("PLUSARGS=+SCA_CFG=install/cfg_pkg/")
        for argument in run_argv
    ) or (
        observer_mode == "fixed_slice0_start_slice1_finish"
        and not any(
            argument.startswith("SIM_EXTRA_OPTS=-ucli -i install/cfg_pkg/")
            for argument in run_argv
        )
    ):
        raise ConvHardwareExecplanError(
            "returned execution argv lacks required no-wave/runtime arguments"
        )
    if (
        f".PHONY: {no_archive_target}" not in make_override_text
        or f"{no_archive_target}: $(SIMV)" not in make_override_text
        or "$(SIMV) $(SIM_OPTS) $(SIM_EXTRA_OPTS)" not in make_override_text
        or 'echo "Simulation exit status: $$sim_status"' not in make_override_text
        or "archive_sim_results:" in make_override_text
        or re.search(r"(?m)^(?:compile|sim):", make_override_text) is not None
        or ".sv" in make_override_text
        or ".v" in make_override_text
    ):
        raise ConvHardwareExecplanError(
            "returned runtime Make contract exceeds the approved no-archive target"
        )

    testbench_identity = identity.get("testbench")
    if (
        not isinstance(testbench_identity, Mapping)
        or testbench_identity.get("path") != "tb_NDP_Top_new_phy.sv"
        or testbench_identity.get("source")
        != "existing_server_file_not_in_overlay"
        or testbench_identity.get("identity_policy")
        != "record_actual_hash_without_prestart_comparison"
        or "sha256" in testbench_identity
    ):
        raise ConvHardwareExecplanError(
            "runtime testbench entrypoint policy differs from the approved identity"
        )
    returned_testbench_sha256 = metadata.get("testbench_sha256")
    if (
        not isinstance(returned_testbench_sha256, str)
        or re.fullmatch(r"[0-9a-f]{64}", returned_testbench_sha256) is None
    ):
        raise ConvHardwareExecplanError(
            "returned actual server testbench hash is invalid"
        )

    formal_acceptance_ready = identity.get("formal_acceptance_ready")
    if not isinstance(formal_acceptance_ready, bool):
        raise ConvHardwareExecplanError(
            "approved runtime identity lacks an explicit formal-acceptance state"
        )
    capability_attestation = identity.get(
        "immutable_testbench_capability_attestation"
    )
    if formal_acceptance_ready:
        package_observer = package_manifest.get("testbench_observer")
        if not isinstance(package_observer, Mapping):
            raise ConvHardwareExecplanError(
                "package testbench observer contract is missing"
            )
        observer_mode = package_observer.get("mode")
        if observer_mode == "fixed_slice0_start_slice1_finish":
            reserved_axi_clock_policy = "ucli_force_and_low_high_toggle_proof_400mhz"
            bank_frame_logging_policy = (
                "compile_define_plus_runtime_devnull_sinks"
            )
            post_run_evidence = [
                "exact preload PASS count",
                "exact fixed slice0-start/slice1-finish pair count",
                "finish-slice-only final stage after all other final-shard slices barrier",
                "unique Simulation completed successfully marker",
                "exact readback region set",
            ]
        elif observer_mode == "mask_aware_runtime_stage_markers":
            reserved_axi_clock_policy = "testbench_native"
            bank_frame_logging_policy = "testbench_native"
            post_run_evidence = [
                "exact preload PASS count",
                "ordered RUNTIME_STAGE_COMPLETE markers",
                "unique RUNTIME_ALL_STAGES_COMPLETE marker",
                "exact readback region set",
            ]
        else:
            raise ConvHardwareExecplanError(
                f"unsupported package testbench observer mode: {observer_mode!r}"
            )
        expected_capability_policy = {
            "schema_version": "resnet50-server-entrypoint-capability-policy-0.8",
            "identity_policy": "logical_entrypoints_unpinned_source_provenance",
            "required_entrypoints": required_server_entrypoints,
            "prestart_source_hash_required": False,
            "recursive_filelist_validation_required": False,
            "logical_filelist_readability_required": True,
            "include_directory_validation_required": False,
            "external_vendor_include_tree_equivalence_required": False,
            "physical_source_path_inside_server_root_required": False,
            "server_source_content_scan_required": False,
            "transport_contract_source": "package_axi4_4kb_report",
            "observer_mode": observer_mode,
            "reserved_axi_clock_policy": reserved_axi_clock_policy,
            "bank_frame_logging_policy": bank_frame_logging_policy,
            "phase_stall_watchdog_required": True,
            "phase_progress_policy": "complete_line_snapshot_final_revalidation_v2",
            "watchdog_exit_status_required": True,
            "readback_progress_policy": "exact_regular_file_exact_size_v1",
            "make_archive_policy": "runner_no_archive_target_v1",
            "make_effective_command_check_required": False,
            "make_environment_policy": (
                "unset_MAKEFLAGS_MAKEFILES_GNUMAKEFLAGS_MFLAGS_MAKELEVEL_before_launch"
            ),
            "static_install_exact_set_policy": (
                "launch_manifest_plus_four_content_addressed_identity_files"
            ),
            "run_command_identity_required": True,
            "runner_self_identity_required": True,
            "static_install_exact_set_required": True,
            "waveform_disable_args_required": True,
            "return_archive_policy": "bounded_exact_set_allowlist_v2",
            "server_run_id_policy": {
                "environment_variable": "SERVER_RUN_ID",
                "default": "run1",
                "syntax": "run1|run2",
                "required_formal_run_ids": ["run1", "run2"],
                "preserve_distinct_archives": True,
            },
            "return_config_exact_set_required": True,
            "post_run_evidence_required": post_run_evidence,
        }
        if capability_attestation != expected_capability_policy:
            raise ConvHardwareExecplanError(
                "formal runtime identity server-entrypoint capability policy differs"
            )
    formal_blockers = (
        []
        if formal_acceptance_ready
        else ["immutable_testbench_capability_attestation_missing"]
    )

    contract_lines = returned_readback_contract_text.splitlines()
    if not contract_lines:
        raise ConvHardwareExecplanError("returned readback-region contract is empty")
    expected_readback_files: dict[Path, int] = {}
    for line_number, line in enumerate(contract_lines, 1):
        fields = line.split("\t")
        if len(fields) != 2 or not fields[0] or not fields[1].isdigit():
            raise ConvHardwareExecplanError(
                f"malformed returned readback-region contract line: {line_number}"
            )
        path, raw_line_count = fields
        line_count = int(raw_line_count)
        relative = _readback_relative_path(
            path,
            label=f"readback contract path line {line_number}",
        )
        if line_count <= 0 or relative in expected_readback_files:
            raise ConvHardwareExecplanError(
                f"duplicate/invalid returned readback contract path: {line_number}"
            )
        expected_readback_files[relative] = line_count
    package_readback_files = _sca_d_readback_contract(
        package_sca_d,
        label="package SCA_D",
    )
    if expected_readback_files != package_readback_files:
        missing = sorted(
            item.as_posix()
            for item in set(package_readback_files) - set(expected_readback_files)
        )
        extra = sorted(
            item.as_posix()
            for item in set(expected_readback_files) - set(package_readback_files)
        )
        raise ConvHardwareExecplanError(
            "returned readback contract differs from package SCA_D: "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )
    readback_identity = identity.get("readback_region_contract")
    try:
        identity_region_count = (
            int(readback_identity.get("region_count", -1))
            if isinstance(readback_identity, Mapping)
            else -1
        )
    except (TypeError, ValueError) as error:
        raise ConvHardwareExecplanError(
            "approved readback-region identity count is invalid"
        ) from error
    if identity_region_count != len(expected_readback_files):
        raise ConvHardwareExecplanError(
            "approved readback-region identity count differs"
        )
    region_snapshot = _validate_readback_region_tree(
        returned,
        expected_readback_files,
    )

    receipt_files = [
        {
            "path": relative.as_posix(),
            "line_count": int(record["line_count"]),
            "size_bytes": int(record["size_bytes"]),
            "sha256": str(record["sha256"]),
        }
        for relative, record in sorted(region_snapshot.items())
    ]
    validated_region_receipt = _ValidatedRegionReceipt(
        {
            "schema_version": "resnet50-conv-validated-region-receipt-0.1",
            "package_manifest_sha256": package_manifest_sha256,
            "runtime_identity_sha256": identity_file_sha256,
            "readback_contract_sha256": verified_runtime_hashes[
                "readback_region_contract"
            ],
            "return_root": str(returned),
            "region_count": len(receipt_files),
            "files": receipt_files,
        },
        region_snapshot,
        {
            "sca_cfg_D": package_sca_d,
            "runner_contract": runner,
            "dump_contract": package_dump_contract,
        },
    )

    repeated_run_environment_keys = (
        "execution_environment",
        "board_version",
        "simulator_version",
        "rtl_version",
        "firmware_version",
        "isa_contract",
        "run_command",
        "run_command_contract_sha256",
        "runtime_make_override_sha256",
        "make_archive_policy",
        "freeze_id",
        "freeze_manifest_sha256",
        "package_manifest_sha256",
        "sca_cfg_sha256",
        "sca_cfg_D_sha256",
        "runner_sha256",
        "runner_identity_sha256",
        "testbench_sha256",
        "readback_contract_sha256",
        "stage_contract_sha256",
        "launch_files_contract_sha256",
        "launch_identity_sha256",
        "runtime_identity_sha256",
        "wall_timeout",
        "bank_frame_logging_policy",
        "reserved_clock_validation",
        "runtime_log_sink_policy",
        "diagnostic_sink_count",
        "diagnostic_file_size_limit_bytes",
        "diagnostic_total_size_limit_bytes",
        "return_archive_policy",
    )
    repeated_run_environment = {
        key: metadata.get(key) for key in repeated_run_environment_keys
    }
    normalized_source_provenance = dict(server_source_provenance)
    normalized_source_provenance.pop("server_run_id", None)

    return {
        "schema_version": "resnet50-conv-hardware-region-return-gate-0.2",
        "status": (
            "hardware_region_return_validated"
            if formal_acceptance_ready
            else "diagnostic_hardware_region_return_validated_formal_blocked"
        ),
        "formal_acceptance_ready": formal_acceptance_ready,
        "formal_blockers": formal_blockers,
        "package_manifest_sha256": expected_identity["package_manifest_sha256"],
        "runtime_identity_sha256": identity_file_sha256,
        "approved_runtime_identity_sha256": approved_identity_file_sha256,
        "canonical_runtime_identity_sha256": approved_identity_sha256,
        "completed_runtime_stage_count": expected_stages,
        "returned_region_count": expected_regions,
        "wall_time_seconds": integer_metadata("wall_time_seconds"),
        "server_run_id": server_run_id,
        "server_source_provenance": server_source_provenance,
        "normalized_server_source_provenance": normalized_source_provenance,
        "server_source_inventory": [
            source_inventory_records[path]
            for path in sorted(source_inventory_records)
        ],
        "repeated_run_environment": repeated_run_environment,
        "console": {
            "path": console_path.relative_to(returned).as_posix(),
            **console_gate,
        },
        "validated_region_receipt": validated_region_receipt,
    }


def validate_conv_hardware_repeated_region_returns(
    package_root: Path,
    run_roots: Mapping[str, Path],
    approved_runtime_identity_path: Path,
) -> dict[str, Any]:
    """Validate formal run1/run2 returns and require identical physical regions."""

    required_run_ids = {"run1", "run2"}
    if set(run_roots) != required_run_ids:
        raise ConvHardwareExecplanError(
            "formal repeated returns must provide exactly run1 and run2"
        )
    resolved_roots = {run_id: Path(root).resolve() for run_id, root in run_roots.items()}
    if len(set(resolved_roots.values())) != 2:
        raise ConvHardwareExecplanError(
            "formal repeated returns must use two distinct return roots"
        )

    return_gates: dict[str, dict[str, Any]] = {}
    region_records: dict[str, list[dict[str, Any]]] = {}
    source_provenance_records: dict[str, dict[str, Any]] = {}
    source_inventory_records: dict[str, list[dict[str, Any]]] = {}
    environment_records: dict[str, dict[str, Any]] = {}
    for run_id in ("run1", "run2"):
        gate = validate_conv_hardware_region_return(
            package_root,
            resolved_roots[run_id],
            approved_runtime_identity_path,
        )
        if gate.get("server_run_id") != run_id:
            raise ConvHardwareExecplanError(
                f"formal return run ID differs: expected={run_id} "
                f"observed={gate.get('server_run_id')!r}"
            )
        receipt = gate.get("validated_region_receipt")
        files = receipt.get("files") if isinstance(receipt, Mapping) else None
        if not isinstance(files, list) or not files:
            raise ConvHardwareExecplanError(
                f"formal return lacks a validated region receipt: {run_id}"
            )
        return_gates[run_id] = gate
        region_records[run_id] = [dict(record) for record in files]
        normalized_provenance = gate.get("normalized_server_source_provenance")
        source_inventory = gate.get("server_source_inventory")
        repeated_environment = gate.get("repeated_run_environment")
        if (
            not isinstance(normalized_provenance, Mapping)
            or not isinstance(source_inventory, list)
            or not isinstance(repeated_environment, Mapping)
        ):
            raise ConvHardwareExecplanError(
                f"formal return lacks repeated-run provenance: {run_id}"
            )
        source_provenance_records[run_id] = dict(normalized_provenance)
        source_inventory_records[run_id] = [dict(record) for record in source_inventory]
        environment_records[run_id] = dict(repeated_environment)

    if (
        source_provenance_records["run1"] != source_provenance_records["run2"]
        or source_inventory_records["run1"] != source_inventory_records["run2"]
    ):
        raise ConvHardwareExecplanError(
            "formal run1/run2 server entrypoint provenance differs"
        )
    if environment_records["run1"] != environment_records["run2"]:
        differing_environment_keys = sorted(
            key
            for key in set(environment_records["run1"])
            | set(environment_records["run2"])
            if environment_records["run1"].get(key)
            != environment_records["run2"].get(key)
        )
        raise ConvHardwareExecplanError(
            "formal run1/run2 execution environment differs: "
            f"keys={differing_environment_keys[:5]}"
        )

    if region_records["run1"] != region_records["run2"]:
        run1_by_path = {
            str(record.get("path")): record for record in region_records["run1"]
        }
        run2_by_path = {
            str(record.get("path")): record for record in region_records["run2"]
        }
        differing_paths = sorted(
            path
            for path in set(run1_by_path) | set(run2_by_path)
            if run1_by_path.get(path) != run2_by_path.get(path)
        )
        raise ConvHardwareExecplanError(
            "formal run1/run2 physical readback regions differ: "
            f"paths={differing_paths[:3]}"
        )

    return {
        "schema_version": "resnet50-conv-repeated-region-return-gate-0.2",
        "status": "formal_run1_run2_environment_provenance_and_regions_stable",
        "run_ids": ["run1", "run2"],
        "region_count": len(region_records["run1"]),
        "region_receipt_sha256": _canonical_json_record_list_sha256(
            region_records["run1"]
        ),
        "server_source_provenance_sha256": _canonical_json_sha256(
            {
                "provenance": source_provenance_records["run1"],
                "inventory": source_inventory_records["run1"],
            }
        ),
        "execution_environment_sha256": _canonical_json_sha256(
            environment_records["run1"]
        ),
        "return_gates": return_gates,
    }


def extract_conv_hardware_bank_dump(
    package_root: Path,
    simulator_bank_root: Path,
    dump_root: Path,
) -> dict[str, Any]:
    import numpy as np

    package = package_root.resolve()
    bank_root = simulator_bank_root.resolve()
    output = dump_root.resolve()
    validate_conv_hardware_execplan_package(package)
    if output.exists() and any(output.iterdir()):
        raise ConvHardwareExecplanError(
            f"dump output directory is not empty; refusing to mix evidence: {output}"
        )
    output.mkdir(parents=True, exist_ok=True)
    contract = _read_json_object(package / "dump_contract.json")
    p_entries = contract.get("P")
    staged_entries = contract.get("staged_D")
    slice_count = int(contract.get("slice_count", 0))
    staged_half_count = int(contract.get("staged_halves_per_slice", 0))
    if slice_count <= 0 or staged_half_count <= 0:
        raise ConvHardwareExecplanError("dump contract geometry differs")
    if not isinstance(p_entries, list) or len(p_entries) != slice_count:
        raise ConvHardwareExecplanError("dump contract P entries differ")
    if (
        not isinstance(staged_entries, list)
        or len(staged_entries) != slice_count * staged_half_count
    ):
        raise ConvHardwareExecplanError("dump contract staged-D entries differ")

    bank_cache: dict[tuple[int, int], tuple[Path, bytes]] = {}

    def read_region(entry: Mapping[str, Any]) -> bytes:
        address = int(str(entry["base_addr"]).replace("_", ""), 16)
        slice_id = int(entry["slice_id"])
        encoded_slice = (address >> EXECPLAN_SLICE_SHIFT) & 0x1F
        bank_id = (address >> 23) & 0x03
        offset = address & ((1 << 23) - 1)
        if encoded_slice != slice_id:
            raise ConvHardwareExecplanError(
                f"dump contract slice/address mismatch: slice={slice_id}, address=0x{address:08X}"
            )
        key = (slice_id, bank_id)
        if key not in bank_cache:
            path = _find_bank_dump(bank_root, slice_id, bank_id)
            bank_cache[key] = (path, _parse_bank_dump(path))
        image = bank_cache[key][1]
        size = int(entry["size_bytes"])
        if offset + size > len(image):
            raise ConvHardwareExecplanError(
                f"bank dump is too short for slice={slice_id}, bank={bank_id}, "
                f"range=[{offset}, {offset + size}), bytes={len(image)}"
            )
        return image[offset : offset + size]

    p_by_slice = {int(item["slice_id"]): item for item in p_entries}
    staged_by_slice_half = {
        (int(item["slice_id"]), int(item["local_half"])): item
        for item in staged_entries
    }
    for slice_id in range(slice_count):
        p_bytes = read_region(p_by_slice[slice_id])
        p_path = output / "P" / f"slice-{slice_id:02d}.bin"
        p_path.parent.mkdir(parents=True, exist_ok=True)
        p_path.write_bytes(p_bytes)

        halves = [
            np.frombuffer(read_region(staged_by_slice_half[(slice_id, half)]), dtype=np.uint8)
            .reshape(
                tuple(
                    int(item)
                    for item in staged_by_slice_half[(slice_id, half)]["shape"]
                )
            )
            for half in range(staged_half_count)
        ]
        merged_nhwk = np.ascontiguousarray(np.concatenate(halves, axis=-1))
        expected_d_shape = tuple(
            int(item) for item in contract["canonical_D_merge"]["output_shape"]
        )
        if len(expected_d_shape) == 6:
            expected_flat_shape = (
                expected_d_shape[0],
                expected_d_shape[1],
                expected_d_shape[2] * expected_d_shape[3],
                expected_d_shape[4] * expected_d_shape[5],
            )
            if merged_nhwk.shape != expected_flat_shape:
                raise ConvHardwareExecplanError(
                    "merged staged-D NHWK shape differs: "
                    f"{merged_nhwk.shape} != {expected_flat_shape}"
                )
            canonical_d = np.ascontiguousarray(
                merged_nhwk.reshape(expected_d_shape)
            )
        else:
            canonical_d = merged_nhwk
        if canonical_d.shape != expected_d_shape:
            raise ConvHardwareExecplanError(
                f"merged staged-D shape differs: {canonical_d.shape} != {expected_d_shape}"
            )
        d_path = output / "D" / f"slice-{slice_id:02d}.bin"
        d_path.parent.mkdir(parents=True, exist_ok=True)
        d_path.write_bytes(canonical_d.tobytes(order="C"))

    report: dict[str, Any] = {
        "schema_version": "resnet50-conv-hardware-bank-extract-0.1",
        "status": "hardware_bank_dump_extracted",
        "package_manifest_sha256": _sha256_file(package / "manifest.json"),
        "simulator_bank_root": str(bank_root),
        "consumed_bank_files": [
            {
                "slice_id": slice_id,
                "bank_id": bank_id,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256_file(path),
            }
            for (slice_id, bank_id), (path, _) in sorted(bank_cache.items())
        ],
        "files": _output_hashes(output),
    }
    _write_json(output / "extract_manifest.json", report)
    return report


def compare_conv_hardware_bank_dump(
    project_root: Path,
    package_root: Path,
    simulator_bank_root: Path,
    evidence_root: Path,
) -> dict[str, Any]:
    from .conv_1x1_hardware_freeze import compare_hardware_dump

    root = project_root.resolve()
    evidence = evidence_root.resolve()
    if evidence.exists() and any(evidence.iterdir()):
        raise ConvHardwareExecplanError(
            f"evidence directory is not empty; refusing to mix runs: {evidence}"
        )
    evidence.mkdir(parents=True, exist_ok=True)
    extract_report = extract_conv_hardware_bank_dump(
        package_root, simulator_bank_root, evidence / "physical_dump"
    )
    package_manifest = _read_json_object(Path(package_root).resolve() / "manifest.json")
    freeze_reference = package_manifest.get("source_freeze_reference")
    if isinstance(freeze_reference, str):
        freeze_path = Path(freeze_reference)
        if not freeze_path.is_absolute():
            freeze_path = root / freeze_path
    else:
        raise ConvHardwareExecplanError(
            "tested package does not bind an explicit source_freeze_reference"
        )
    freeze_manifest_path = freeze_path / "manifest.json"
    if not freeze_manifest_path.is_file():
        raise ConvHardwareExecplanError(
            f"local comparison freeze manifest is missing: {freeze_manifest_path}"
        )
    local_freeze_manifest = _read_json_object(freeze_manifest_path)
    if (
        _sha256_file(freeze_manifest_path)
        != package_manifest.get("freeze_manifest_sha256")
        or local_freeze_manifest.get("freeze_id")
        != package_manifest.get("freeze_id")
    ):
        raise ConvHardwareExecplanError(
            "local comparison freeze identity differs from the tested package"
        )
    comparison = compare_hardware_dump(
        freeze_path, evidence / "physical_dump"
    )
    report: dict[str, Any] = {
        "schema_version": "resnet50-conv-hardware-execplan-comparison-0.1",
        "status": "passed" if comparison.get("status") == "passed" else "failed",
        "entry": "model_execplan execplan.txt + Bank_data",
        "extract": extract_report,
        "comparison": comparison,
    }
    _write_json(evidence / "comparison.json", report)
    return report
