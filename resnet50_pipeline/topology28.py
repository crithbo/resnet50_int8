"""Authoritative 28-slice physical ring topology from ADR-007.

The owner sequences in this module are copied from the selected RTL's
``HIGH_NEXT_MAP`` and ``LOW_NEXT_MAP``.  Navigation follows lookup tables
built from those explicit sequences; numeric slice adjacency is never used.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Mapping


SLICE_COUNT = 28
HIGH_GROUP_COUNT = 7
HIGH_RING_SIZE = 4
LOW_RING_SIZE = 28


class RingKind(str, Enum):
    """RTL neighbor-network selection."""

    HIGH = "high"
    LOW = "low"


class Direction(str, Enum):
    """Direction of travel around a selected physical ring."""

    NEXT = "next"
    PREV = "prev"


# These tuples are the topology truth.  Do not replace them with numeric
# ranges, arithmetic grouping, or modulo-based owner calculations.
HIGH_RING_OWNERS: tuple[tuple[int, ...], ...] = (
    (0, 2, 3, 1),
    (4, 6, 7, 5),
    (8, 10, 11, 9),
    (12, 13, 15, 14),
    (16, 17, 19, 18),
    (20, 21, 23, 22),
    (24, 25, 27, 26),
)

LOW_RING_OWNERS: tuple[int, ...] = (
    0,
    12,
    13,
    15,
    17,
    19,
    21,
    23,
    25,
    27,
    26,
    10,
    11,
    9,
    8,
    24,
    22,
    20,
    18,
    16,
    14,
    2,
    4,
    6,
    7,
    5,
    3,
    1,
)


def _require_integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer, got {value!r}")
    return value


def _coerce_ring_kind(kind: RingKind | str) -> RingKind:
    if isinstance(kind, RingKind):
        return kind
    if not isinstance(kind, str):
        raise TypeError(f"ring kind must be RingKind or str, got {kind!r}")
    try:
        return RingKind(kind)
    except ValueError as exc:
        raise ValueError(f"unsupported ring kind {kind!r}; expected 'high' or 'low'") from exc


def _coerce_direction(direction: Direction | str) -> Direction:
    if isinstance(direction, Direction):
        return direction
    if not isinstance(direction, str):
        raise TypeError(f"direction must be Direction or str, got {direction!r}")
    try:
        return Direction(direction)
    except ValueError as exc:
        raise ValueError(
            f"unsupported direction {direction!r}; expected 'next' or 'prev'"
        ) from exc


@dataclass(frozen=True, slots=True)
class PhysicalRing:
    """An immutable physical owner cycle with explicit forward/reverse maps."""

    name: str
    owners: tuple[int, ...]
    _next_map: Mapping[int, int] = field(init=False, repr=False, compare=False)
    _prev_map: Mapping[int, int] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.owners:
            raise ValueError(f"{self.name} ring must contain at least one owner")
        for owner in self.owners:
            _require_integer(owner, f"{self.name} owner")
        if len(set(self.owners)) != len(self.owners):
            raise ValueError(f"{self.name} ring contains duplicate owners")

        next_map: dict[int, int] = {}
        previous = self.owners[-1]
        for owner in self.owners:
            next_map[previous] = owner
            previous = owner
        prev_map = {target: source for source, target in next_map.items()}
        object.__setattr__(self, "_next_map", MappingProxyType(next_map))
        object.__setattr__(self, "_prev_map", MappingProxyType(prev_map))

    @property
    def size(self) -> int:
        return len(self.owners)

    @property
    def next_map(self) -> Mapping[int, int]:
        return self._next_map

    @property
    def prev_map(self) -> Mapping[int, int]:
        return self._prev_map

    def contains(self, owner: int) -> bool:
        owner = _require_integer(owner, "owner")
        return owner in self._next_map

    def _require_owner(self, owner: int) -> int:
        owner = _require_integer(owner, "owner")
        if owner not in self._next_map:
            raise ValueError(f"owner {owner} is not in {self.name} ring")
        return owner

    def next(self, owner: int) -> int:
        """Return the RTL-defined successor of ``owner``."""

        return self._next_map[self._require_owner(owner)]

    def prev(self, owner: int) -> int:
        """Return the RTL-defined predecessor of ``owner``."""

        return self._prev_map[self._require_owner(owner)]

    def walk(
        self,
        owner: int,
        direction: Direction | str,
        steps: int,
    ) -> int:
        """Walk ``steps`` physical links from ``owner`` in ``direction``."""

        current = self._require_owner(owner)
        steps = _require_integer(steps, "steps")
        if steps < 0:
            raise ValueError(f"steps must be non-negative, got {steps}")
        parsed_direction = _coerce_direction(direction)
        advance = self.next if parsed_direction is Direction.NEXT else self.prev
        for _ in range(steps):
            current = advance(current)
        return current

    def traverse(
        self,
        owner: int,
        direction: Direction | str = Direction.NEXT,
    ) -> tuple[int, ...]:
        """Return every owner once, starting at ``owner``, in ring order."""

        start = self._require_owner(owner)
        parsed_direction = _coerce_direction(direction)
        advance = self.next if parsed_direction is Direction.NEXT else self.prev
        traversal: list[int] = []
        current = start
        while current not in traversal:
            traversal.append(current)
            current = advance(current)
        if current != start or len(traversal) != self.size:
            raise ValueError(f"{self.name} maps do not form one complete cycle")
        return tuple(traversal)

    def validate(self) -> None:
        """Raise ``ValueError`` unless next/prev form one cycle over all owners."""

        owners = set(self.owners)
        if set(self._next_map) != owners or set(self._next_map.values()) != owners:
            raise ValueError(f"{self.name} next map is not a permutation of its owners")
        if set(self._prev_map) != owners or set(self._prev_map.values()) != owners:
            raise ValueError(f"{self.name} prev map is not a permutation of its owners")
        for owner in self.owners:
            if self.prev(self.next(owner)) != owner or self.next(self.prev(owner)) != owner:
                raise ValueError(f"{self.name} next/prev maps are not inverses at {owner}")
        if set(self.traverse(self.owners[0], Direction.NEXT)) != owners:
            raise ValueError(f"{self.name} next traversal does not cover every owner")
        if set(self.traverse(self.owners[0], Direction.PREV)) != owners:
            raise ValueError(f"{self.name} prev traversal does not cover every owner")


@dataclass(frozen=True, slots=True)
class TopologyValidationReport:
    """Stable summary returned by :meth:`Topology28.validate`."""

    slice_count: int
    high_group_count: int
    high_ring_lengths: tuple[int, ...]
    low_ring_length: int


class Topology28:
    """Query API for ADR-007's HIGH and LOW physical rings."""

    __slots__ = ("_high_rings", "_low_ring", "_group_by_slice")

    def __init__(self) -> None:
        self._high_rings = tuple(
            PhysicalRing(f"HIGH G{group}", owners)
            for group, owners in enumerate(HIGH_RING_OWNERS)
        )
        self._low_ring = PhysicalRing("LOW", LOW_RING_OWNERS)
        group_by_slice: dict[int, int] = {}
        for group, ring in enumerate(self._high_rings):
            for owner in ring.owners:
                if owner in group_by_slice:
                    raise ValueError(f"slice {owner} belongs to multiple HIGH groups")
                group_by_slice[owner] = group
        self._group_by_slice = MappingProxyType(group_by_slice)
        self.validate()

    @property
    def high_rings(self) -> tuple[PhysicalRing, ...]:
        return self._high_rings

    @property
    def low_ring(self) -> PhysicalRing:
        return self._low_ring

    def _require_slice(self, slice_id: int) -> int:
        slice_id = _require_integer(slice_id, "slice_id")
        if slice_id < 0 or slice_id >= SLICE_COUNT:
            raise ValueError(f"slice_id must be in [0, {SLICE_COUNT}), got {slice_id}")
        return slice_id

    def _require_group(self, group: int) -> int:
        group = _require_integer(group, "group")
        if group < 0 or group >= HIGH_GROUP_COUNT:
            raise ValueError(
                f"HIGH group must be in [0, {HIGH_GROUP_COUNT}), got {group}"
            )
        return group

    def high_ring_for_group(self, group: int) -> PhysicalRing:
        """Return the HIGH ring selected by its RTL group number."""

        return self._high_rings[self._require_group(group)]

    def group_for_slice(self, slice_id: int) -> int:
        """Return the unique HIGH group containing ``slice_id``."""

        return self._group_by_slice[self._require_slice(slice_id)]

    def high_ring_for_slice(self, slice_id: int) -> PhysicalRing:
        """Return the unique HIGH ring containing ``slice_id``."""

        return self.high_ring_for_group(self.group_for_slice(slice_id))

    def ring_for_slice(
        self,
        slice_id: int,
        kind: RingKind | str,
    ) -> PhysicalRing:
        """Return the selected HIGH or LOW ring containing ``slice_id``."""

        slice_id = self._require_slice(slice_id)
        parsed_kind = _coerce_ring_kind(kind)
        if parsed_kind is RingKind.HIGH:
            return self.high_ring_for_slice(slice_id)
        return self._low_ring

    def next(self, owner: int, kind: RingKind | str) -> int:
        """Return ``owner``'s RTL-defined successor in the selected network."""

        return self.ring_for_slice(owner, kind).next(owner)

    def prev(self, owner: int, kind: RingKind | str) -> int:
        """Return ``owner``'s RTL-defined predecessor in the selected network."""

        return self.ring_for_slice(owner, kind).prev(owner)

    def walk(
        self,
        owner: int,
        kind: RingKind | str,
        direction: Direction | str,
        steps: int,
    ) -> int:
        """Walk from ``owner`` through explicit RTL links."""

        return self.ring_for_slice(owner, kind).walk(owner, direction, steps)

    def traverse(
        self,
        owner: int,
        kind: RingKind | str,
        direction: Direction | str = Direction.NEXT,
    ) -> tuple[int, ...]:
        """Traverse the selected physical ring once from ``owner``."""

        return self.ring_for_slice(owner, kind).traverse(owner, direction)

    def validate(self) -> TopologyValidationReport:
        """Validate all ADR-007 coverage, cycle, and inverse invariants."""

        expected_slices = set(range(SLICE_COUNT))
        if len(self._high_rings) != HIGH_GROUP_COUNT:
            raise ValueError(
                f"expected {HIGH_GROUP_COUNT} HIGH groups, got {len(self._high_rings)}"
            )

        high_owners: list[int] = []
        for group, ring in enumerate(self._high_rings):
            ring.validate()
            if ring.size != HIGH_RING_SIZE:
                raise ValueError(
                    f"HIGH G{group} must contain {HIGH_RING_SIZE} owners, got {ring.size}"
                )
            high_owners.extend(ring.owners)
        if len(high_owners) != len(set(high_owners)):
            raise ValueError("HIGH rings are not mutually exclusive")
        if set(high_owners) != expected_slices:
            raise ValueError("HIGH rings do not cover exactly slices 0..27")
        if set(self._group_by_slice) != expected_slices:
            raise ValueError("HIGH slice-to-group index does not cover exactly slices 0..27")

        self._low_ring.validate()
        if self._low_ring.size != LOW_RING_SIZE:
            raise ValueError(
                f"LOW ring must contain {LOW_RING_SIZE} owners, got {self._low_ring.size}"
            )
        if set(self._low_ring.owners) != expected_slices:
            raise ValueError("LOW ring is not a permutation of slices 0..27")

        return TopologyValidationReport(
            slice_count=SLICE_COUNT,
            high_group_count=HIGH_GROUP_COUNT,
            high_ring_lengths=tuple(ring.size for ring in self._high_rings),
            low_ring_length=self._low_ring.size,
        )


TOPOLOGY28 = Topology28()


__all__ = [
    "Direction",
    "HIGH_GROUP_COUNT",
    "HIGH_RING_OWNERS",
    "HIGH_RING_SIZE",
    "LOW_RING_OWNERS",
    "LOW_RING_SIZE",
    "PhysicalRing",
    "RingKind",
    "SLICE_COUNT",
    "TOPOLOGY28",
    "Topology28",
    "TopologyValidationReport",
]
