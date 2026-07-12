from __future__ import annotations

from typing import Any, Protocol


class LayoutTransform(Protocol):
    name: str

    def forward(self, logical: bytes, metadata: dict[str, Any]) -> bytes: ...

    def inverse(self, physical: bytes, metadata: dict[str, Any]) -> bytes: ...

    def explain_coordinate(self, coordinate: tuple[int, ...]) -> dict[str, Any]: ...

    def validate(self, logical: bytes, metadata: dict[str, Any]) -> None: ...


class IdentityLayout:
    name = "identity"

    def forward(self, logical: bytes, metadata: dict[str, Any]) -> bytes:
        self.validate(logical, metadata)
        return logical

    def inverse(self, physical: bytes, metadata: dict[str, Any]) -> bytes:
        self.validate(physical, metadata)
        return physical

    def explain_coordinate(self, coordinate: tuple[int, ...]) -> dict[str, Any]:
        return {"logical_coordinate": list(coordinate), "mapping": "identity"}

    def validate(self, logical: bytes, metadata: dict[str, Any]) -> None:
        expected = metadata.get("size_bytes")
        if expected is not None and len(logical) != expected:
            raise ValueError(f"identity layout expected {expected} bytes, got {len(logical)}")


from .simple_layout import (  # noqa: E402  (keeps the protocol definitions first)
    DequantizeLinearPhysicalLayout,
    QuantizeLinearPhysicalLayout,
    ZeroCopyViewLayout,
)
from .conv16_layout import ConvBatch16PhysicalLayout  # noqa: E402
from .conv16_ring_layout import ConvRing16PhysicalLayout  # noqa: E402


__all__ = [
    "DequantizeLinearPhysicalLayout",
    "ConvBatch16PhysicalLayout",
    "ConvRing16PhysicalLayout",
    "IdentityLayout",
    "LayoutTransform",
    "QuantizeLinearPhysicalLayout",
    "ZeroCopyViewLayout",
]
