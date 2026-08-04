from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol, runtime_checkable


SLICE_SHIFT = 25
BANK_SHIFT = 23
ROW_SHIFT = 10
SLICE_COUNT = 28
BANK_COUNT = 4
SLICE_MASK_BITS = 28
BANK_OFFSET_MASK = (1 << BANK_SHIFT) - 1
ADDRESS_LIMIT = 1 << 30

OPCODE_LOAD_CONFIG = 0b000
OPCODE_CLOCK_ENABLE = 0b001
OPCODE_WRITE_REG = 0b100
OPCODE_START_COMP = 0b101
OPCODE_BARRIER = 0b110

_BANK_FILE_RE = re.compile(r"^slice(?P<slice>\d+)_Bank(?P<bank>\d+)_data\.(?P<ext>txt|bin)$")


class HardwareSimulationPreparationError(ValueError):
    """A hardware package cannot safely enter the numerical simulator."""


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise HardwareSimulationPreparationError(f"cannot read JSON object: {path}") from error
    if not isinstance(value, dict):
        raise HardwareSimulationPreparationError(f"JSON root is not an object: {path}")
    return value


def _parse_address(value: object, *, location: str) -> int:
    if isinstance(value, int):
        address = value
    elif isinstance(value, str):
        try:
            address = int(value.replace("_", ""), 16)
        except ValueError as error:
            raise HardwareSimulationPreparationError(
                f"invalid hexadecimal address at {location}: {value!r}"
            ) from error
    else:
        raise HardwareSimulationPreparationError(f"missing address at {location}")
    if not 0 <= address < ADDRESS_LIMIT:
        raise HardwareSimulationPreparationError(
            f"address is outside the 30-bit NDP space at {location}: 0x{address:X}"
        )
    return address


@dataclass(frozen=True)
class PhysicalAddress:
    value: int
    slice_id: int
    bank_id: int
    row: int
    column: int
    subword: int
    bank_offset: int

    @classmethod
    def decode(cls, value: int) -> "PhysicalAddress":
        if not 0 <= value < ADDRESS_LIMIT:
            raise HardwareSimulationPreparationError(
                f"physical address is outside the 30-bit NDP space: 0x{value:X}"
            )
        slice_id = (value >> SLICE_SHIFT) & 0x1F
        bank_id = (value >> BANK_SHIFT) & 0x03
        row = (value >> ROW_SHIFT) & 0x1FFF
        column = (value >> 4) & 0x3F
        subword = value & 0x0F
        return cls(
            value=value,
            slice_id=slice_id,
            bank_id=bank_id,
            row=row,
            column=column,
            subword=subword,
            bank_offset=(row << ROW_SHIFT) | (column << 4) | subword,
        )


def _is_binary_text(raw: bytes) -> bool:
    if not raw:
        return False
    try:
        sample = raw[:256].decode("ascii")
    except UnicodeDecodeError:
        return False
    return set(sample) <= set("01\r\n\t ")


def _parse_binary_text(raw: bytes, *, location: str) -> bytes:
    result = bytearray()
    width: int | None = None
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise HardwareSimulationPreparationError(f"non-ASCII bit text at {location}") from error
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        bits = "".join(raw_line.split())
        if not bits:
            continue
        if set(bits) - {"0", "1"}:
            raise HardwareSimulationPreparationError(
                f"invalid bit text at {location}:{line_number}"
            )
        if width is None:
            width = len(bits)
            if width not in (32, 64, 128):
                raise HardwareSimulationPreparationError(
                    f"unsupported bit width {width} at {location}:{line_number}"
                )
        if len(bits) != width:
            raise HardwareSimulationPreparationError(
                f"mixed bit widths at {location}:{line_number}: expected {width}, got {len(bits)}"
            )
        result.extend(int(bits, 2).to_bytes(width // 8, byteorder="little", signed=False))
    return bytes(result)


def _parse_hex_bank_text(raw: bytes, *, location: str) -> bytes:
    result = bytearray()
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise HardwareSimulationPreparationError(f"non-ASCII bank text at {location}") from error
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        tokens = raw_line.split()
        if not tokens:
            continue
        if len(tokens) not in (1, 4) or not all(
            token.lower().startswith("0x") for token in tokens
        ):
            raise HardwareSimulationPreparationError(
                f"unsupported bank line at {location}:{line_number}"
            )
        ordered = tokens if len(tokens) == 1 else list(reversed(tokens))
        for token in ordered:
            try:
                value = int(token, 16)
            except ValueError as error:
                raise HardwareSimulationPreparationError(
                    f"invalid bank word at {location}:{line_number}"
                ) from error
            if not 0 <= value < (1 << 32):
                raise HardwareSimulationPreparationError(
                    f"bank word is outside uint32 at {location}:{line_number}"
                )
            result.extend(value.to_bytes(4, byteorder="little", signed=False))
    return bytes(result)


def load_payload_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise HardwareSimulationPreparationError(f"payload is missing: {path}")
    raw = path.read_bytes()
    if _is_binary_text(raw):
        return _parse_binary_text(raw, location=str(path))
    if path.suffix.lower() == ".txt":
        return _parse_hex_bank_text(raw, location=str(path))
    return raw


def load_bank_image(path: Path) -> bytes:
    if path.suffix.lower() == ".bin":
        return path.read_bytes()
    raw = path.read_bytes()
    if _is_binary_text(raw):
        return _parse_binary_text(raw, location=str(path))
    return _parse_hex_bank_text(raw, location=str(path))


@dataclass
class BankedMemory:
    images: dict[tuple[int, int], bytearray] = field(default_factory=dict)
    source_paths: dict[tuple[int, int], Path] = field(default_factory=dict)

    @classmethod
    def from_directory(cls, bank_root: Path) -> "BankedMemory":
        root = bank_root.resolve()
        if not root.is_dir():
            raise HardwareSimulationPreparationError(f"Bank_data directory is missing: {root}")
        memory = cls()
        for path in sorted(root.iterdir()):
            if not path.is_file():
                continue
            match = _BANK_FILE_RE.fullmatch(path.name)
            if match is None:
                continue
            key = (int(match.group("slice")), int(match.group("bank")))
            if not 0 <= key[0] < SLICE_COUNT or not 0 <= key[1] < BANK_COUNT:
                raise HardwareSimulationPreparationError(
                    f"Bank_data filename has an unsupported location: {path.name}"
                )
            if key in memory.images:
                raise HardwareSimulationPreparationError(
                    f"duplicate Bank_data image for slice/bank {key}"
                )
            memory.images[key] = bytearray(load_bank_image(path))
            memory.source_paths[key] = path
        if not memory.images:
            raise HardwareSimulationPreparationError(f"no Bank_data images found under {root}")
        return memory

    def read(self, address: int, size: int) -> bytes:
        if size < 0:
            raise HardwareSimulationPreparationError(f"negative memory read size: {size}")
        decoded = PhysicalAddress.decode(address)
        key = (decoded.slice_id, decoded.bank_id)
        image = self.images.get(key)
        if image is None:
            raise HardwareSimulationPreparationError(
                f"memory image is missing for slice={decoded.slice_id}, bank={decoded.bank_id}"
            )
        end = decoded.bank_offset + size
        if end > len(image):
            raise HardwareSimulationPreparationError(
                f"memory read exceeds image at slice={decoded.slice_id}, bank={decoded.bank_id}: "
                f"range=[{decoded.bank_offset}, {end}), bytes={len(image)}"
            )
        return bytes(image[decoded.bank_offset:end])

    def write(self, address: int, payload: bytes) -> None:
        decoded = PhysicalAddress.decode(address)
        key = (decoded.slice_id, decoded.bank_id)
        image = self.images.setdefault(key, bytearray())
        end = decoded.bank_offset + len(payload)
        if end > len(image):
            image.extend(b"\x00" * (end - len(image)))
        image[decoded.bank_offset:end] = payload

    def describe(self) -> list[dict[str, Any]]:
        return [
            {
                "slice_id": slice_id,
                "bank_id": bank_id,
                "size_bytes": len(image),
                "sha256": _sha256_bytes(bytes(image)),
                "source_path": str(self.source_paths.get((slice_id, bank_id), "")),
            }
            for (slice_id, bank_id), image in sorted(self.images.items())
        ]


@dataclass(frozen=True)
class DecodedCommand:
    index: int
    beat_index: int
    lane: str
    raw: int
    kind: str
    fields: Mapping[str, int | bool]

    @property
    def opcode(self) -> int:
        return self.raw & 0x07


def decode_command(raw: int, *, index: int, beat_index: int, lane: str) -> DecodedCommand:
    if not 0 <= raw < (1 << 64):
        raise HardwareSimulationPreparationError(f"command is outside uint64: {raw}")
    opcode = raw & 0x07
    if opcode == OPCODE_WRITE_REG:
        if ((raw >> 8) & 0x3FF) != 0:
            raise HardwareSimulationPreparationError(
                f"Write_Reg reserved bits are nonzero at command {index}"
            )
        fields: dict[str, int | bool] = {
            "write_value": (raw >> 32) & 0xFFFFFFFF,
            "write_addr": (raw >> 18) & 0x3FFF,
            "slice_id": (raw >> 3) & 0x1F,
        }
        kind = "write_reg"
    elif opcode == OPCODE_LOAD_CONFIG:
        if ((raw >> 32) & 0x03) != 0:
            raise HardwareSimulationPreparationError(
                f"Load_Config reserved bits are nonzero at command {index}"
            )
        fields = {
            "config_length_64bit_words": (raw >> 56) & 0xFF,
            "ddr_config_address_compressed": (raw >> 34) & 0x3FFFFF,
            "config_address": ((raw >> 34) & 0x3FFFFF) << ROW_SHIFT,
            "config_sfu": bool((raw >> 31) & 0x01),
            "slice_mask": (raw >> 3) & ((1 << SLICE_MASK_BITS) - 1),
        }
        if fields["config_length_64bit_words"] == 0 or fields["slice_mask"] == 0:
            raise HardwareSimulationPreparationError(
                f"Load_Config is empty at command {index}"
            )
        kind = "load_config"
    elif opcode == OPCODE_START_COMP:
        fields = {"slice_mask": (raw >> 3) & ((1 << SLICE_MASK_BITS) - 1)}
        if raw >> 31 or fields["slice_mask"] == 0:
            raise HardwareSimulationPreparationError(
                f"Start_Comp contains invalid high bits or an empty mask at command {index}"
            )
        kind = "start_comp"
    elif opcode == OPCODE_BARRIER:
        fields = {"slice_mask": (raw >> 3) & ((1 << SLICE_MASK_BITS) - 1)}
        if raw >> 31 or fields["slice_mask"] == 0:
            raise HardwareSimulationPreparationError(
                f"Barrier contains invalid high bits or an empty mask at command {index}"
            )
        kind = "barrier"
    elif opcode == OPCODE_CLOCK_ENABLE:
        fields = {
            "slice_mask": (raw >> 3) & ((1 << SLICE_MASK_BITS) - 1),
            "clock_select": (raw >> 31) & 0x0F,
        }
        if raw >> 35 or fields["slice_mask"] == 0 or fields["clock_select"] == 0:
            raise HardwareSimulationPreparationError(
                f"Clock_Enable contains invalid bits at command {index}"
            )
        kind = "clock_enable"
    else:
        raise HardwareSimulationPreparationError(
            f"unsupported opcode 0b{opcode:03b} at command {index}"
        )
    return DecodedCommand(
        index=index,
        beat_index=beat_index,
        lane=lane,
        raw=raw,
        kind=kind,
        fields=fields,
    )


def load_execplan_commands(path: Path, *, expected_beats: int | None = None) -> list[DecodedCommand]:
    if not path.is_file():
        raise HardwareSimulationPreparationError(f"execplan is missing: {path}")
    lines = [line.strip() for line in path.read_text(encoding="ascii").splitlines() if line.strip()]
    if expected_beats is not None and len(lines) != expected_beats:
        raise HardwareSimulationPreparationError(
            f"execplan beat count differs: expected {expected_beats}, got {len(lines)}"
        )
    commands: list[DecodedCommand] = []
    for beat_index, bits in enumerate(lines):
        if len(bits) != 128 or set(bits) - {"0", "1"}:
            raise HardwareSimulationPreparationError(
                f"invalid 128-bit execplan line at {path}:{beat_index + 1}"
            )
        high = int(bits[:64], 2)
        low = int(bits[64:], 2)
        for lane, raw in (("low", low), ("high", high)):
            if raw == 0 and beat_index == len(lines) - 1 and lane == "high":
                continue
            commands.append(
                decode_command(
                    raw,
                    index=len(commands),
                    beat_index=beat_index,
                    lane=lane,
                )
            )
    if not commands:
        raise HardwareSimulationPreparationError(f"execplan contains no commands: {path}")
    return commands


@dataclass(frozen=True)
class LoadedConfig:
    command_index: int
    address: int
    length_64bit_words: int
    config_sfu: bool
    slice_mask: int
    payload: bytes
    sha256: str


@dataclass(frozen=True)
class ExecutionStage:
    index: int
    operator_id: str
    operator_type: str | None
    stage_kind: str | None
    instance_id: str | None
    load_configs: tuple[DecodedCommand, ...]
    register_writes: tuple[DecodedCommand, ...]
    start_command: DecodedCommand
    completion_barrier: DecodedCommand | None
    attributes: Mapping[str, Any]

    @property
    def slice_mask(self) -> int:
        return int(self.start_command.fields["slice_mask"])


@dataclass(frozen=True)
class StageInvocation:
    stage: ExecutionStage
    loaded_configs: Mapping[tuple[int, bool], LoadedConfig]
    register_values: Mapping[tuple[int, int], int]


def _runtime_descriptors(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    detailed = manifest.get("runtime_operators")
    if isinstance(detailed, list):
        result: list[dict[str, Any]] = []
        for index, value in enumerate(detailed):
            if not isinstance(value, dict) or not isinstance(value.get("operator_id"), str):
                raise HardwareSimulationPreparationError(
                    f"runtime_operators[{index}] is malformed"
                )
            result.append(dict(value))
        return result
    sequence = manifest.get("runtime_sequence")
    if isinstance(sequence, list) and all(isinstance(value, str) for value in sequence):
        return [{"operator_id": value} for value in sequence]
    return []


def build_execution_stages(
    commands: list[DecodedCommand], manifest: Mapping[str, Any]
) -> tuple[list[DecodedCommand], list[ExecutionStage]]:
    global_commands: list[DecodedCommand] = []
    raw_stages: list[tuple[list[DecodedCommand], list[DecodedCommand], DecodedCommand]] = []
    barriers: list[DecodedCommand] = []
    serialization_present = "runtime_serialization" in manifest
    serialization = manifest.get("runtime_serialization")
    barrier_required = False
    four_independent_config_loads = False
    if serialization_present:
        if not isinstance(serialization, dict):
            raise HardwareSimulationPreparationError(
                "runtime_serialization must be an object when declared"
            )
        if serialization.get("strategy") != "post_start_same_mask_barrier":
            raise HardwareSimulationPreparationError(
                "runtime_serialization declares an unsupported strategy"
            )
        declared_count = serialization.get("barrier_count")
        if (
            isinstance(declared_count, bool)
            or not isinstance(declared_count, int)
            or declared_count <= 0
        ):
            raise HardwareSimulationPreparationError(
                "runtime_serialization barrier_count must be a positive integer"
            )
        if serialization.get("barrier_opcode") != f"0b{OPCODE_BARRIER:03b}":
            raise HardwareSimulationPreparationError(
                "runtime_serialization barrier_opcode is unsupported"
            )
        configuration_strategy = serialization.get("configuration_strategy")
        if configuration_strategy is not None:
            if (
                configuration_strategy
                != "four_independent_config_loads_then_one_full_ring4_start"
            ):
                raise HardwareSimulationPreparationError(
                    "runtime_serialization configuration_strategy is unsupported"
                )
            four_independent_config_loads = True
        barrier_required = True
    loads: list[DecodedCommand] = []
    writes: list[DecodedCommand] = []
    for command in commands:
        if (
            command.kind != "barrier"
            and (barrier_required or barriers)
            and len(barriers) < len(raw_stages)
        ):
            raise HardwareSimulationPreparationError(
                "execplan command follows Start_Comp before its completion barrier: "
                f"stage={len(raw_stages) - 1}, command={command.index}"
            )
        if command.kind == "clock_enable":
            if loads or writes or raw_stages:
                raise HardwareSimulationPreparationError(
                    f"Clock_Enable appears inside the operator sequence at command {command.index}"
                )
            global_commands.append(command)
        elif command.kind == "load_config":
            if writes:
                raise HardwareSimulationPreparationError(
                    f"Load_Config appears after Write_Reg in a stage at command {command.index}"
                )
            loads.append(command)
        elif command.kind == "write_reg":
            if not loads:
                raise HardwareSimulationPreparationError(
                    f"Write_Reg has no preceding Load_Config at command {command.index}"
                )
            writes.append(command)
        elif command.kind == "start_comp":
            if not loads:
                raise HardwareSimulationPreparationError(
                    f"Start_Comp has no preceding Load_Config at command {command.index}"
                )
            stage_mask = int(command.fields["slice_mask"])
            if four_independent_config_loads:
                load_masks = [int(load.fields["slice_mask"]) for load in loads]
                combined_mask = 0
                for load_mask in load_masks:
                    if load_mask.bit_count() != 1 or combined_mask & load_mask:
                        raise HardwareSimulationPreparationError(
                            "Ring4 Load_Config masks must be disjoint single slices in "
                            f"stage {len(raw_stages)}"
                        )
                    combined_mask |= load_mask
                if len(load_masks) != 4 or combined_mask != stage_mask:
                    raise HardwareSimulationPreparationError(
                        "four Ring4 Load_Config masks must exactly cover Start_Comp in "
                        f"stage {len(raw_stages)}"
                    )
            elif any(int(load.fields["slice_mask"]) != stage_mask for load in loads):
                raise HardwareSimulationPreparationError(
                    f"Load_Config/Start_Comp slice masks differ in stage {len(raw_stages)}"
                )
            if any(not (stage_mask & (1 << int(write.fields["slice_id"]))) for write in writes):
                raise HardwareSimulationPreparationError(
                    f"Write_Reg targets a disabled slice in stage {len(raw_stages)}"
                )
            raw_stages.append((loads, writes, command))
            loads = []
            writes = []
        elif command.kind == "barrier":
            if not barrier_required:
                raise HardwareSimulationPreparationError(
                    "execplan contains a barrier without a runtime_serialization contract"
                )
            if loads or writes or not raw_stages or len(barriers) != len(raw_stages) - 1:
                raise HardwareSimulationPreparationError(
                    f"Barrier is not immediately after one Start_Comp at command {command.index}"
                )
            expected_mask = int(raw_stages[-1][2].fields["slice_mask"])
            observed_mask = int(command.fields["slice_mask"])
            if observed_mask != expected_mask:
                raise HardwareSimulationPreparationError(
                    "Start_Comp/Barrier slice masks differ in stage "
                    f"{len(raw_stages) - 1}"
                )
            barriers.append(command)
    if loads or writes:
        raise HardwareSimulationPreparationError("execplan ends before Start_Comp")
    if barriers and len(barriers) != len(raw_stages):
        raise HardwareSimulationPreparationError(
            "execplan has an incomplete per-stage completion barrier sequence"
        )
    if barrier_required:
        if (
            len(barriers) != len(raw_stages)
            or declared_count != len(raw_stages)
        ):
            raise HardwareSimulationPreparationError(
                "runtime serialization barrier contract differs from the execplan"
            )
    if not global_commands:
        raise HardwareSimulationPreparationError("execplan has no Clock_Enable")

    descriptors = _runtime_descriptors(manifest)
    if descriptors and len(descriptors) != len(raw_stages):
        raise HardwareSimulationPreparationError(
            f"runtime operator count differs from command stages: {len(descriptors)} != {len(raw_stages)}"
        )
    stages: list[ExecutionStage] = []
    for index, (stage_loads, stage_writes, start) in enumerate(raw_stages):
        descriptor = descriptors[index] if descriptors else {"operator_id": f"runtime-op-{index:04d}"}
        expected_mask = descriptor.get("slice_mask")
        if isinstance(expected_mask, str):
            expected_mask = int(expected_mask.replace("_", ""), 16)
        if isinstance(expected_mask, int) and expected_mask != int(start.fields["slice_mask"]):
            raise HardwareSimulationPreparationError(
                f"runtime descriptor slice mask differs for {descriptor['operator_id']}"
            )
        attributes = descriptor.get("attributes")
        stages.append(
            ExecutionStage(
                index=index,
                operator_id=str(descriptor["operator_id"]),
                operator_type=(
                    str(descriptor["operator_type"])
                    if isinstance(descriptor.get("operator_type"), str)
                    else None
                ),
                stage_kind=(
                    str(descriptor["stage"])
                    if isinstance(descriptor.get("stage"), str)
                    else None
                ),
                instance_id=(
                    str(descriptor["instance_id"])
                    if isinstance(descriptor.get("instance_id"), str)
                    else None
                ),
                load_configs=tuple(stage_loads),
                register_writes=tuple(stage_writes),
                start_command=start,
                completion_barrier=(barriers[index] if barriers else None),
                attributes=dict(attributes) if isinstance(attributes, dict) else {},
            )
        )
    return global_commands, stages


def build_stage_invocations(
    stages: list[ExecutionStage], memory: BankedMemory
) -> list[StageInvocation]:
    active_configs: dict[tuple[int, bool], LoadedConfig] = {}
    register_values: dict[tuple[int, int], int] = {}
    invocations: list[StageInvocation] = []
    for stage in stages:
        for command in stage.load_configs:
            address = int(command.fields["config_address"])
            length = int(command.fields["config_length_64bit_words"])
            payload = memory.read(address, length * 8)
            loaded = LoadedConfig(
                command_index=command.index,
                address=address,
                length_64bit_words=length,
                config_sfu=bool(command.fields["config_sfu"]),
                slice_mask=int(command.fields["slice_mask"]),
                payload=payload,
                sha256=_sha256_bytes(payload),
            )
            for slice_id in range(SLICE_COUNT):
                if loaded.slice_mask & (1 << slice_id):
                    active_configs[(slice_id, loaded.config_sfu)] = loaded
        for command in stage.register_writes:
            register_values[
                (int(command.fields["slice_id"]), int(command.fields["write_addr"]))
            ] = int(command.fields["write_value"])
        enabled_slices = [
            slice_id for slice_id in range(SLICE_COUNT) if stage.slice_mask & (1 << slice_id)
        ]
        missing = [
            slice_id for slice_id in enabled_slices if (slice_id, False) not in active_configs
        ]
        if missing:
            raise HardwareSimulationPreparationError(
                f"Start_Comp for {stage.operator_id} has no main config on slices {missing}"
            )
        config_snapshot = {
            key: value
            for key, value in active_configs.items()
            if stage.slice_mask & (1 << key[0])
        }
        register_snapshot = {
            key: value
            for key, value in register_values.items()
            if stage.slice_mask & (1 << key[0])
        }
        invocations.append(
            StageInvocation(
                stage=stage,
                loaded_configs=config_snapshot,
                register_values=register_snapshot,
            )
        )
    return invocations


_LIFECYCLE_DTYPE_BYTES = {
    "fp16": 2,
    "float16": 2,
    "fp32": 4,
    "float32": 4,
    "int8": 1,
    "uint8": 1,
    "int16": 2,
    "uint16": 2,
    "int32": 4,
    "uint32": 4,
}


def _positive_int(value: object, *, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise HardwareSimulationPreparationError(
            f"{location} must be a positive integer"
        )
    return value


def _contained_package_path(
    package_root: Path, relative: object, *, location: str
) -> Path:
    if not isinstance(relative, str) or not relative:
        raise HardwareSimulationPreparationError(f"{location} path is missing")
    root = package_root.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as error:
        raise HardwareSimulationPreparationError(
            f"{location} escapes the package root"
        ) from error
    if not path.is_file():
        raise HardwareSimulationPreparationError(f"{location} is missing: {relative}")
    return path


def _operator_source_id(value: object) -> str | None:
    if isinstance(value, str):
        return value
    if not isinstance(value, Mapping):
        return None
    source_type = value.get("type")
    if source_type not in (None, "operator"):
        return None
    operator_id = value.get("operator_id")
    return operator_id if isinstance(operator_id, str) else None


def _lifecycle_tensor_bytes(tensor: Mapping[str, Any], *, location: str) -> int:
    shape = tensor.get("shape")
    dtype = tensor.get("dtype")
    if (
        not isinstance(shape, list)
        or not shape
        or any(
            isinstance(dimension, bool)
            or not isinstance(dimension, int)
            or dimension <= 0
            for dimension in shape
        )
        or not isinstance(dtype, str)
        or dtype not in _LIFECYCLE_DTYPE_BYTES
    ):
        raise HardwareSimulationPreparationError(
            f"{location} dtype/shape is not concrete"
        )
    elements = 1
    for dimension in shape:
        elements *= dimension
    return elements * _LIFECYCLE_DTYPE_BYTES[dtype]


def validate_runtime_lifecycle(
    *,
    package_root: Path,
    manifest: Mapping[str, Any],
    sca: Mapping[str, Any],
    sca_d: Mapping[str, Any],
    runner: Mapping[str, Any],
    stages: list[ExecutionStage],
    invocations: list[StageInvocation],
) -> dict[str, Any]:
    """Validate an explicitly declared producer-to-consumer stage lifecycle.

    The contract is optional so legacy single-stage packages retain their
    existing preparation behavior.  Once declared, every address, config,
    completion and output claim is fail-closed against materialized files.
    """

    lifecycle = manifest.get("runtime_lifecycle")
    if lifecycle is None:
        return {
            "status": "not_declared",
            "validated": False,
            "stage_count": len(stages),
        }
    if not isinstance(lifecycle, Mapping):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle must be an object when declared"
        )
    if lifecycle.get("strategy") != "producer_output_alias_to_consumer_input_v1":
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle strategy is unsupported"
        )
    stage_count = _positive_int(
        lifecycle.get("stage_count"), location="runtime_lifecycle.stage_count"
    )
    if stage_count != 2 or len(stages) != stage_count or len(invocations) != stage_count:
        raise HardwareSimulationPreparationError(
            "minimal runtime lifecycle must contain exactly two prepared stages"
        )
    runtime_sequence = manifest.get("runtime_sequence")
    observed_sequence = [stage.operator_id for stage in stages]
    if runtime_sequence != observed_sequence:
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle stage sequence differs from the execplan"
        )

    termination = lifecycle.get("termination")
    if not isinstance(termination, Mapping):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle termination contract is missing"
        )
    expected_counts = {
        "start_comp_count": len(stages),
        "completion_barrier_count": len(stages),
        "repeat_num": len(stages),
    }
    for field, expected in expected_counts.items():
        observed = _positive_int(
            termination.get(field), location=f"runtime_lifecycle.termination.{field}"
        )
        if observed != expected:
            raise HardwareSimulationPreparationError(
                f"runtime_lifecycle termination {field} differs"
            )
    if termination.get("completion_operator_ids") != observed_sequence:
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle completion order differs"
        )
    if termination.get("final_barrier_required") is not True:
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle final barrier is not required"
        )
    repeat_num = _positive_int(sca.get("Repeat_Num"), location="sca_cfg.Repeat_Num")
    if repeat_num != len(stages):
        raise HardwareSimulationPreparationError(
            "SCA Repeat_Num differs from the two-stage lifecycle"
        )

    try:
        completion_gate = runner["execution"]["completion_gate"]
    except (KeyError, TypeError) as error:
        raise HardwareSimulationPreparationError(
            "runner lifecycle completion gate is missing"
        ) from error
    if not isinstance(completion_gate, Mapping):
        raise HardwareSimulationPreparationError(
            "runner lifecycle completion gate is malformed"
        )
    runner_expected = {
        "expected_runtime_stage_count": len(stages),
        "expected_testbench_repeat_num": len(stages),
        "expected_start_comp_count": len(stages),
        "expected_completion_barrier_count": len(stages),
    }
    for field, expected in runner_expected.items():
        if _positive_int(
            completion_gate.get(field),
            location=f"runner.execution.completion_gate.{field}",
        ) != expected:
            raise HardwareSimulationPreparationError(
                f"runner lifecycle completion {field} differs"
            )
    if (
        completion_gate.get("completion_barrier_opcode")
        != f"0b{OPCODE_BARRIER:03b}"
        or completion_gate.get("expected_runtime_sequence") != observed_sequence
        or completion_gate.get("final_barrier_required") is not True
    ):
        raise HardwareSimulationPreparationError(
            "runner lifecycle completion sequence/barrier differs"
        )
    for stage in stages:
        barrier = stage.completion_barrier
        if (
            barrier is None
            or barrier.index != stage.start_command.index + 1
            or int(barrier.fields["slice_mask"]) != stage.slice_mask
        ):
            raise HardwareSimulationPreparationError(
                f"runtime lifecycle barrier differs for stage {stage.index}"
            )

    reload_contract = lifecycle.get("config_reload")
    if not isinstance(reload_contract, Mapping) or (
        reload_contract.get("required_each_stage") is not True
        or reload_contract.get("distinct_main_config_address") is not True
        or reload_contract.get("distinct_main_config_payload") is not True
    ):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle config reload contract is incomplete"
        )
    config_records: list[dict[str, Any]] = []
    for invocation in invocations:
        main_loads = [
            command
            for command in invocation.stage.load_configs
            if command.fields.get("config_sfu") is False
        ]
        if len(main_loads) != 1:
            raise HardwareSimulationPreparationError(
                "each lifecycle stage must explicitly load exactly one main config: "
                f"stage={invocation.stage.index}"
            )
        command_index = main_loads[0].index
        loaded_by_command = {
            loaded.command_index: loaded
            for loaded in invocation.loaded_configs.values()
            if not loaded.config_sfu
        }
        loaded = loaded_by_command.get(command_index)
        if loaded is None:
            raise HardwareSimulationPreparationError(
                f"lifecycle main config snapshot is missing for stage {invocation.stage.index}"
            )
        config_records.append(
            {
                "operator_id": invocation.stage.operator_id,
                "command_index": command_index,
                "address": loaded.address,
                "sha256": loaded.sha256,
                "length_64bit_words": loaded.length_64bit_words,
            }
        )
    if (
        len({record["address"] for record in config_records}) != len(stages)
        or len({record["sha256"] for record in config_records}) != len(stages)
    ):
        raise HardwareSimulationPreparationError(
            "two-stage lifecycle main configs are not independently addressed and identified"
        )

    addressed = lifecycle.get("addressed_request")
    if not isinstance(addressed, Mapping):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle addressed request binding is missing"
        )
    addressed_path = _contained_package_path(
        package_root,
        addressed.get("path"),
        location="runtime_lifecycle.addressed_request",
    )
    addressed_sha = addressed.get("sha256")
    if not isinstance(addressed_sha, str) or _sha256_file(addressed_path) != addressed_sha:
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle addressed request identity differs"
        )
    addressed_request = _read_json_object(addressed_path)
    raw_operators = addressed_request.get("operators")
    if not isinstance(raw_operators, list):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle addressed request operators are missing"
        )
    operators = {
        str(operator.get("id")): operator
        for operator in raw_operators
        if isinstance(operator, Mapping) and isinstance(operator.get("id"), str)
    }
    if set(observed_sequence) - set(operators):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle addressed request stage identity differs"
        )

    dependencies = lifecycle.get("dependencies")
    if not isinstance(dependencies, list) or len(dependencies) != 1:
        raise HardwareSimulationPreparationError(
            "minimal runtime lifecycle must declare one producer/consumer dependency"
        )
    dependency = dependencies[0]
    if not isinstance(dependency, Mapping):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle dependency is malformed"
        )
    producer_id = dependency.get("producer_operator_id")
    consumer_id = dependency.get("consumer_operator_id")
    if (
        producer_id != observed_sequence[0]
        or consumer_id != observed_sequence[1]
        or dependency.get("producer_port") != "D"
        or dependency.get("consumer_port") != "A"
        or dependency.get("visibility_fence")
        != "post_start_same_mask_barrier"
    ):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle producer/consumer edge differs"
        )
    producer = operators[str(producer_id)]
    consumer = operators[str(consumer_id)]
    producer_tensor = producer.get("output")
    consumer_inputs = consumer.get("inputs")
    consumer_tensor = (
        consumer_inputs.get("A") if isinstance(consumer_inputs, Mapping) else None
    )
    if not isinstance(producer_tensor, Mapping) or not isinstance(
        consumer_tensor, Mapping
    ):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle addressed D/A ports are missing"
        )
    if _operator_source_id(consumer_tensor.get("source")) != producer_id:
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle consumer A is not sourced from producer D"
        )
    producer_bytes = _lifecycle_tensor_bytes(
        producer_tensor, location=f"{producer_id}.output.D"
    )
    consumer_bytes = _lifecycle_tensor_bytes(
        consumer_tensor, location=f"{consumer_id}.input.A"
    )
    producer_address = _parse_address(
        producer_tensor.get("base_addr"),
        location=f"{producer_id}.output.D.base_addr",
    )
    consumer_address = _parse_address(
        consumer_tensor.get("base_addr"),
        location=f"{consumer_id}.input.A.base_addr",
    )
    if (
        producer_tensor.get("dtype") != consumer_tensor.get("dtype")
        or producer_tensor.get("shape") != consumer_tensor.get("shape")
        or producer_bytes != consumer_bytes
        or producer_address != consumer_address
        or dependency.get("dtype") != producer_tensor.get("dtype")
        or dependency.get("shape") != producer_tensor.get("shape")
        or dependency.get("byte_count") != producer_bytes
        or _parse_address(
            dependency.get("producer_base_addr"),
            location="runtime_lifecycle.dependencies[0].producer_base_addr",
        )
        != producer_address
        or _parse_address(
            dependency.get("consumer_base_addr"),
            location="runtime_lifecycle.dependencies[0].consumer_base_addr",
        )
        != consumer_address
    ):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle D-to-A dtype/shape/bytes/address alias differs"
        )
    producer_sca_d_key = dependency.get("producer_sca_d_key")
    producer_sca_d = (
        sca_d.get(producer_sca_d_key)
        if isinstance(producer_sca_d_key, str)
        else None
    )
    if (
        not isinstance(producer_sca_d, Mapping)
        or _parse_address(
            producer_sca_d.get("base_addr"),
            location=f"sca_cfg_D.{producer_sca_d_key}.base_addr",
        )
        != producer_address
        or _positive_int(
            producer_sca_d.get("length"),
            location=f"sca_cfg_D.{producer_sca_d_key}.length",
        )
        * 16
        != producer_bytes
    ):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle producer D readback contract differs"
        )
    forbidden_preload_key = dependency.get("consumer_preload_sca_key")
    if not isinstance(forbidden_preload_key, str) or forbidden_preload_key in sca:
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle consumer A must not be externally preloaded"
        )
    if stages[0].completion_barrier is None or (
        stages[0].completion_barrier.index >= stages[1].load_configs[0].index
    ):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle producer barrier does not precede consumer configuration"
        )

    outputs = lifecycle.get("outputs")
    if not isinstance(outputs, list) or len(outputs) != len(stages):
        raise HardwareSimulationPreparationError(
            "runtime_lifecycle must bind one formal output per stage"
        )
    output_records: list[dict[str, Any]] = []
    for index, output in enumerate(outputs):
        if not isinstance(output, Mapping):
            raise HardwareSimulationPreparationError(
                f"runtime_lifecycle outputs[{index}] is malformed"
            )
        operator_id = output.get("operator_id")
        if operator_id != observed_sequence[index]:
            raise HardwareSimulationPreparationError(
                "runtime_lifecycle output order differs"
            )
        operator_output = operators[str(operator_id)].get("output")
        if not isinstance(operator_output, Mapping):
            raise HardwareSimulationPreparationError(
                f"runtime_lifecycle output port is missing for {operator_id}"
            )
        byte_count = _lifecycle_tensor_bytes(
            operator_output, location=f"{operator_id}.output.D"
        )
        sca_key = output.get("sca_d_key")
        sca_entry = sca_d.get(sca_key) if isinstance(sca_key, str) else None
        if not isinstance(sca_entry, Mapping):
            raise HardwareSimulationPreparationError(
                f"runtime_lifecycle SCA_D entry is missing for {operator_id}"
            )
        address = _parse_address(
            operator_output.get("base_addr"),
            location=f"{operator_id}.output.D.base_addr",
        )
        golden_path = _contained_package_path(
            package_root,
            output.get("golden_path"),
            location=f"runtime_lifecycle.outputs[{index}].golden",
        )
        golden_sha = output.get("golden_sha256")
        if (
            output.get("dtype") != operator_output.get("dtype")
            or output.get("shape") != operator_output.get("shape")
            or output.get("byte_count") != byte_count
            or _parse_address(
                output.get("base_addr"),
                location=f"runtime_lifecycle.outputs[{index}].base_addr",
            )
            != address
            or _parse_address(
                sca_entry.get("base_addr"),
                location=f"sca_cfg_D.{sca_key}.base_addr",
            )
            != address
            or _positive_int(
                sca_entry.get("length"),
                location=f"sca_cfg_D.{sca_key}.length",
            )
            * 16
            != byte_count
            or golden_path.stat().st_size != byte_count
            or not isinstance(golden_sha, str)
            or _sha256_file(golden_path) != golden_sha
        ):
            raise HardwareSimulationPreparationError(
                f"runtime_lifecycle formal output contract differs for {operator_id}"
            )
        output_records.append(
            {
                "operator_id": operator_id,
                "base_addr": f"0x{address:08X}",
                "byte_count": byte_count,
                "golden_sha256": golden_sha,
            }
        )

    return {
        "status": "validated",
        "validated": True,
        "rule_ids": list(lifecycle.get("rule_ids", [])),
        "stage_count": len(stages),
        "runtime_sequence": observed_sequence,
        "repeat_num": repeat_num,
        "start_comp_count": len(stages),
        "completion_barrier_count": len(stages),
        "final_barrier_command_index": stages[-1].completion_barrier.index,
        "config_reload": config_records,
        "dependency": {
            "producer_operator_id": producer_id,
            "consumer_operator_id": consumer_id,
            "dtype": producer_tensor.get("dtype"),
            "shape": producer_tensor.get("shape"),
            "byte_count": producer_bytes,
            "base_addr": f"0x{producer_address:08X}",
            "consumer_external_preload": False,
            "visibility_fence": "post_start_same_mask_barrier",
        },
        "outputs": output_records,
    }


@runtime_checkable
class HardwareNumericExecutor(Protocol):
    """Operator-family backend plugged in after generic transport preparation."""

    name: str

    def execute_stage(self, invocation: StageInvocation, memory: BankedMemory) -> None:
        """Execute one Start_Comp and write its results back to *memory*."""


@dataclass
class PreparedHardwareSimulation:
    package_root: Path
    manifest: dict[str, Any]
    sca: dict[str, Any]
    sca_d: dict[str, Any]
    runner_contract: dict[str, Any]
    memory: BankedMemory
    commands: list[DecodedCommand]
    global_commands: list[DecodedCommand]
    stages: list[ExecutionStage]
    invocations: list[StageInvocation]
    exec_base: int
    exec_length_128bit_beats: int
    package_manifest_sha256: str
    runtime_lifecycle: dict[str, Any]

    def report(self) -> dict[str, Any]:
        command_counts: dict[str, int] = {}
        for command in self.commands:
            command_counts[command.kind] = command_counts.get(command.kind, 0) + 1

        def unique_configs(invocation: StageInvocation) -> list[LoadedConfig]:
            by_command: dict[int, LoadedConfig] = {}
            for loaded in invocation.loaded_configs.values():
                by_command[loaded.command_index] = loaded
            return [by_command[index] for index in sorted(by_command)]

        return {
            "schema_version": "resnet50-hardware-simulation-preparation-0.1",
            "status": "hardware_simulation_input_prepared",
            "scope": "transport_and_state_only_no_numeric_execution",
            "package_root": str(self.package_root),
            "package_manifest_sha256": self.package_manifest_sha256,
            "package_status": self.manifest.get("status"),
            "node_id": self.manifest.get("node_id"),
            "address_encoding": "slice[29:25],bank[24:23],row[22:10],column[9:4],subword[3:0]",
            "exec_base": f"0x{self.exec_base:08X}",
            "exec_length_128bit_beats": self.exec_length_128bit_beats,
            "command_count": len(self.commands),
            "command_counts": command_counts,
            "bank_images": self.memory.describe(),
            "runtime_stage_count": len(self.stages),
            "runtime_lifecycle": self.runtime_lifecycle,
            "runtime_stages": [
                {
                    "index": invocation.stage.index,
                    "operator_id": invocation.stage.operator_id,
                    "operator_type": invocation.stage.operator_type,
                    "stage": invocation.stage.stage_kind,
                    "instance_id": invocation.stage.instance_id,
                    "slice_mask": f"0x{invocation.stage.slice_mask:07X}",
                    "load_config_count": len(invocation.stage.load_configs),
                    "write_reg_count": len(invocation.stage.register_writes),
                    "completion_barrier_command_index": (
                        invocation.stage.completion_barrier.index
                        if invocation.stage.completion_barrier is not None
                        else None
                    ),
                    "register_snapshot_count": len(invocation.register_values),
                    "configs": [
                        {
                            "config_sfu": loaded.config_sfu,
                            "address": f"0x{loaded.address:08X}",
                            "length_64bit_words": loaded.length_64bit_words,
                            "sha256": loaded.sha256,
                            "slice_mask": f"0x{loaded.slice_mask:07X}",
                        }
                        for loaded in unique_configs(invocation)
                    ],
                    "attributes": dict(invocation.stage.attributes),
                }
                for invocation in self.invocations
            ],
            "numeric_executor": {
                "status": "not_run",
                "interface": "HardwareNumericExecutor.execute_stage(invocation, memory)",
                "required_behavior": "consume loaded config/register state and write candidate outputs back to BankedMemory",
            },
        }


def _validate_package_files(package_root: Path, manifest: Mapping[str, Any]) -> int:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise HardwareSimulationPreparationError("package manifest files list is missing")
    checked = 0
    for index, item in enumerate(files):
        if not isinstance(item, dict):
            raise HardwareSimulationPreparationError(f"manifest files[{index}] is malformed")
        relative = item.get("path")
        size = item.get("size_bytes")
        sha256 = item.get("sha256")
        if not isinstance(relative, str) or not isinstance(size, int) or not isinstance(sha256, str):
            raise HardwareSimulationPreparationError(f"manifest files[{index}] fields are malformed")
        path = package_root / relative
        if not path.is_file() or path.stat().st_size != size or _sha256_file(path) != sha256:
            raise HardwareSimulationPreparationError(f"package file differs: {relative}")
        checked += 1
    return checked


def _validate_sca_payloads(
    package_root: Path, sca: Mapping[str, Any], memory: BankedMemory
) -> int:
    checked = 0
    for key, value in sca.items():
        if not isinstance(value, dict):
            continue
        relative = value.get("path")
        if not isinstance(relative, str):
            continue
        address = _parse_address(value.get("base_addr"), location=f"sca_cfg.{key}.base_addr")
        payload = load_payload_bytes(package_root / relative)
        padded = payload + b"\x00" * ((16 - len(payload) % 16) % 16)
        actual = memory.read(address, len(padded))
        if actual != padded:
            raise HardwareSimulationPreparationError(
                f"Bank_data does not contain SCA payload {key} at 0x{address:08X}"
            )
        checked += 1
    if checked == 0:
        raise HardwareSimulationPreparationError("sca_cfg contains no loadable payloads")
    return checked


def _apply_runtime_scratch(
    package_root: Path, sca: Mapping[str, Any], memory: BankedMemory
) -> None:
    for key, value in sca.items():
        if not key.startswith("runtime_scratch_") or not isinstance(value, Mapping):
            continue
        relative = value.get("path")
        if not isinstance(relative, str):
            raise HardwareSimulationPreparationError(
                f"runtime scratch payload path is missing: sca_cfg.{key}"
            )
        payload = load_payload_bytes(package_root / relative)
        if not payload or any(payload):
            raise HardwareSimulationPreparationError(
                f"runtime scratch payload is not an all-zero non-empty image: sca_cfg.{key}"
            )
        address = _parse_address(value.get("base_addr"), location=f"sca_cfg.{key}.base_addr")
        memory.write(address, payload)


def prepare_hardware_simulation(package_root: Path) -> PreparedHardwareSimulation:
    package = package_root.resolve()
    manifest_path = package / "manifest.json"
    manifest = _read_json_object(manifest_path)
    _validate_package_files(package, manifest)
    sca = _read_json_object(package / "sca_cfg.json")
    sca_d_path = package / "sca_cfg_D.json"
    sca_d = _read_json_object(sca_d_path) if sca_d_path.is_file() else {}
    runner_path = package / "runner_contract.json"
    runner = _read_json_object(runner_path) if runner_path.is_file() else {}
    memory = BankedMemory.from_directory(package / "Bank_data")
    _apply_runtime_scratch(package, sca, memory)
    _validate_sca_payloads(package, sca, memory)

    execution = sca.get("ExecutionPlan")
    if not isinstance(execution, dict) or not isinstance(execution.get("path"), str):
        raise HardwareSimulationPreparationError("sca_cfg.ExecutionPlan is malformed")
    exec_base = _parse_address(sca.get("Exec_Base"), location="sca_cfg.Exec_Base")
    if _parse_address(execution.get("base_addr"), location="sca_cfg.ExecutionPlan.base_addr") != exec_base:
        raise HardwareSimulationPreparationError("Exec_Base and ExecutionPlan.base_addr differ")
    exec_length = sca.get("Exec_Length")
    if not isinstance(exec_length, int) or exec_length <= 0:
        raise HardwareSimulationPreparationError("sca_cfg.Exec_Length is invalid")
    commands = load_execplan_commands(package / execution["path"], expected_beats=exec_length)
    global_commands, stages = build_execution_stages(commands, manifest)
    invocations = build_stage_invocations(stages, memory)
    runtime_lifecycle = validate_runtime_lifecycle(
        package_root=package,
        manifest=manifest,
        sca=sca,
        sca_d=sca_d,
        runner=runner,
        stages=stages,
        invocations=invocations,
    )
    return PreparedHardwareSimulation(
        package_root=package,
        manifest=manifest,
        sca=sca,
        sca_d=sca_d,
        runner_contract=runner,
        memory=memory,
        commands=commands,
        global_commands=global_commands,
        stages=stages,
        invocations=invocations,
        exec_base=exec_base,
        exec_length_128bit_beats=exec_length,
        package_manifest_sha256=_sha256_file(manifest_path),
        runtime_lifecycle=runtime_lifecycle,
    )


def verify_server_preload_readback(
    package_root: Path, readback_root: Path
) -> dict[str, Any]:
    """Compare a server pre-Start_Comp Bank dump against mandatory package probes."""
    prepared = prepare_hardware_simulation(package_root)
    preload = prepared.runner_contract.get("preload")
    if not isinstance(preload, dict):
        raise HardwareSimulationPreparationError("runner preload contract is missing")
    gate = preload.get("readback_gate")
    if not isinstance(gate, dict) or gate.get("required") is not True:
        raise HardwareSimulationPreparationError("mandatory preload readback gate is missing")
    probes = gate.get("probes")
    if not isinstance(probes, list) or gate.get("probe_count") != len(probes) or not probes:
        raise HardwareSimulationPreparationError("preload readback probes are malformed")

    observed_memory = BankedMemory.from_directory(readback_root)
    comparisons: list[dict[str, Any]] = []
    first_failure: dict[str, Any] | None = None
    for index, probe in enumerate(probes):
        if not isinstance(probe, dict):
            raise HardwareSimulationPreparationError(f"preload probe {index} is malformed")
        address = _parse_address(
            probe.get("base_addr"), location=f"runner.preload.readback_gate.probes[{index}]"
        )
        expected = prepared.memory.read(address, 16)
        expected_hex = f"0x{int.from_bytes(expected, byteorder='little'):032X}"
        if probe.get("expected_128bit") != expected_hex:
            raise HardwareSimulationPreparationError(
                f"preload probe {index} differs from packaged Bank_data"
            )
        try:
            observed = observed_memory.read(address, 16)
            error: str | None = None
        except HardwareSimulationPreparationError as read_error:
            observed = b""
            error = str(read_error)
        observed_hex = (
            f"0x{int.from_bytes(observed, byteorder='little'):032X}" if observed else None
        )
        mismatch_count = (
            sum(left != right for left, right in zip(expected, observed))
            if len(observed) == len(expected)
            else len(expected)
        )
        comparison = {
            "index": index,
            "kind": probe.get("kind"),
            "port": probe.get("port"),
            "slice_id": probe.get("slice_id"),
            "base_addr": f"0x{address:08X}",
            "expected_128bit": expected_hex,
            "observed_128bit": observed_hex,
            "mismatch_byte_count": mismatch_count,
            "status": "passed" if mismatch_count == 0 else "failed",
        }
        if error is not None:
            comparison["error"] = error
        comparisons.append(comparison)
        if mismatch_count and first_failure is None:
            first_failure = comparison

    failed = sum(item["status"] == "failed" for item in comparisons)
    return {
        "schema_version": "resnet50-hardware-server-preload-readback-0.1",
        "status": "passed" if failed == 0 else "failed",
        "package": str(prepared.package_root),
        "package_manifest_sha256": prepared.package_manifest_sha256,
        "readback_root": str(readback_root.resolve()),
        "probe_count": len(comparisons),
        "passed_probe_count": len(comparisons) - failed,
        "failed_probe_count": failed,
        "first_failure": first_failure,
        "comparisons": comparisons,
        "execution_authorized": failed == 0,
    }


def run_prepared_simulation(
    prepared: PreparedHardwareSimulation, executor: HardwareNumericExecutor
) -> BankedMemory:
    if not isinstance(executor, HardwareNumericExecutor):
        raise HardwareSimulationPreparationError(
            "numeric executor does not implement HardwareNumericExecutor"
        )
    for invocation in prepared.invocations:
        executor.execute_stage(invocation, prepared.memory)
    return prepared.memory
