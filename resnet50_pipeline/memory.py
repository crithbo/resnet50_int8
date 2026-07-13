from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DramCoordinate:
    slice_id: int
    bank_id: int
    row_id: int
    col_id: int
    byte_offset: int


@dataclass(frozen=True)
class ByteProvenance:
    tensor_id: str
    logical_coordinate: tuple[int, ...] | None
    element_byte: int
    semantic: str
    note: str = ""


@dataclass(frozen=True)
class Transfer:
    address: int
    size_bytes: int


@dataclass(frozen=True)
class DramGeometry:
    slice_count: int
    bank_count: int = 4
    row_count: int = 6144
    col_count: int = 64
    subword_bytes: int = 16

    def __post_init__(self) -> None:
        values = (
            self.slice_count,
            self.bank_count,
            self.row_count,
            self.col_count,
            self.subword_bytes,
        )
        if any(value <= 0 for value in values):
            raise ValueError("all DRAM geometry dimensions must be positive")

    @property
    def bytes_per_row(self) -> int:
        return self.col_count * self.subword_bytes

    @property
    def bytes_per_bank(self) -> int:
        return self.row_count * self.bytes_per_row

    @property
    def bytes_per_slice(self) -> int:
        return self.bank_count * self.bytes_per_bank

    @property
    def total_bytes(self) -> int:
        return self.slice_count * self.bytes_per_slice

    def slice_base(self, slice_id: int) -> int:
        if not 0 <= slice_id < self.slice_count:
            raise ValueError(f"slice_id out of range: {slice_id}")
        return slice_id * self.bytes_per_slice

    def decode(self, address: int) -> DramCoordinate:
        if not 0 <= address < self.total_bytes:
            raise ValueError(f"DRAM byte address out of range: {address}")
        slice_id = address // self.bytes_per_slice
        within_slice = address % self.bytes_per_slice
        bank_id = within_slice // self.bytes_per_bank
        within_bank = within_slice % self.bytes_per_bank
        row_id = within_bank // self.bytes_per_row
        within_row = within_bank % self.bytes_per_row
        linear_col = within_row // self.subword_bytes
        linear_byte = within_row % self.subword_bytes
        return DramCoordinate(
            slice_id=slice_id,
            bank_id=bank_id,
            row_id=row_id,
            col_id=self.col_count - 1 - linear_col,
            byte_offset=self.subword_bytes - 1 - linear_byte,
        )

    def encode(self, coordinate: DramCoordinate) -> int:
        if not 0 <= coordinate.slice_id < self.slice_count:
            raise ValueError("slice_id out of range")
        if not 0 <= coordinate.bank_id < self.bank_count:
            raise ValueError("bank_id out of range")
        if not 0 <= coordinate.row_id < self.row_count:
            raise ValueError("row_id out of range")
        if not 0 <= coordinate.col_id < self.col_count:
            raise ValueError("col_id out of range")
        if not 0 <= coordinate.byte_offset < self.subword_bytes:
            raise ValueError("byte_offset out of range")
        linear_col = self.col_count - 1 - coordinate.col_id
        linear_byte = self.subword_bytes - 1 - coordinate.byte_offset
        return (
            coordinate.slice_id * self.bytes_per_slice
            + coordinate.bank_id * self.bytes_per_bank
            + coordinate.row_id * self.bytes_per_row
            + linear_col * self.subword_bytes
            + linear_byte
        )

    def split_aligned(self, address: int, size_bytes: int, alignment: int = 16) -> tuple[Transfer, ...]:
        if alignment <= 0:
            raise ValueError("alignment must be positive")
        if size_bytes < 0 or address < 0 or address + size_bytes > self.total_bytes:
            raise ValueError("transfer range is outside DRAM")
        transfers: list[Transfer] = []
        cursor = address
        remaining = size_bytes
        while remaining:
            boundary = ((cursor // alignment) + 1) * alignment
            chunk = min(remaining, boundary - cursor)
            transfers.append(Transfer(cursor, chunk))
            cursor += chunk
            remaining -= chunk
        return tuple(transfers)

    def strided_transactions(
        self,
        base_address: int,
        transaction_count: int,
        transaction_size: int,
        stride_bytes: int,
    ) -> tuple[Transfer, ...]:
        if transaction_count < 0 or transaction_size < 0 or stride_bytes < 0:
            raise ValueError("transaction parameters must be non-negative")
        transactions = tuple(
            Transfer(base_address + index * stride_bytes, transaction_size)
            for index in range(transaction_count)
        )
        for transfer in transactions:
            if transfer.address < 0 or transfer.address + transfer.size_bytes > self.total_bytes:
                raise ValueError("strided transaction range is outside DRAM")
        return transactions


# Current and legacy call sites use named geometry constants.  ``slice_count``
# is intentionally required on ad-hoc constructions so new target code cannot
# silently inherit the historical 16-slice default.
LEGACY_DRAM_GEOMETRY16 = DramGeometry(
    slice_count=16,
    bank_count=4,
    row_count=6144,
    col_count=64,
    subword_bytes=16,
)
TARGET_DRAM_GEOMETRY28 = DramGeometry(
    slice_count=28,
    bank_count=4,
    row_count=6144,
    col_count=64,
    subword_bytes=16,
)


class SparsePhysicalImage:
    def __init__(self, geometry: DramGeometry):
        self.geometry = geometry
        self._data: dict[int, int] = {}
        self._provenance: dict[int, ByteProvenance] = {}

    def write(
        self,
        address: int,
        payload: bytes,
        provenance: tuple[ByteProvenance, ...],
    ) -> None:
        if len(payload) != len(provenance):
            raise ValueError("payload and provenance lengths differ")
        if address < 0 or address + len(payload) > self.geometry.total_bytes:
            raise ValueError("physical write is outside DRAM")
        overlap = [item for item in range(address, address + len(payload)) if item in self._data]
        if overlap:
            raise ValueError(f"physical write overlaps existing bytes at {overlap[0]}")
        for offset, value in enumerate(payload):
            byte_address = address + offset
            self._data[byte_address] = value
            self._provenance[byte_address] = provenance[offset]

    def read(self, address: int, size_bytes: int) -> bytes:
        if size_bytes < 0:
            raise ValueError("size_bytes must be non-negative")
        missing = [item for item in range(address, address + size_bytes) if item not in self._data]
        if missing:
            raise KeyError(f"physical byte has not been written: {missing[0]}")
        return bytes(self._data[item] for item in range(address, address + size_bytes))

    def overwrite(self, address: int, payload: bytes) -> None:
        """Replace existing physical bytes without changing their provenance."""

        if address < 0 or address + len(payload) > self.geometry.total_bytes:
            raise ValueError("physical overwrite is outside DRAM")
        missing = [item for item in range(address, address + len(payload)) if item not in self._data]
        if missing:
            raise KeyError(f"physical overwrite targets an unwritten byte: {missing[0]}")
        for offset, value in enumerate(payload):
            self._data[address + offset] = value

    def explain(self, address: int) -> tuple[DramCoordinate, ByteProvenance]:
        if address not in self._provenance:
            raise KeyError(f"physical byte has no provenance: {address}")
        return self.geometry.decode(address), self._provenance[address]

    def addresses_for(
        self, tensor_id: str, logical_coordinate: tuple[int, ...]
    ) -> tuple[int, ...]:
        return tuple(
            address
            for address, provenance in sorted(self._provenance.items())
            if provenance.tensor_id == tensor_id
            and provenance.logical_coordinate == logical_coordinate
        )

    @property
    def written_byte_count(self) -> int:
        return len(self._data)
