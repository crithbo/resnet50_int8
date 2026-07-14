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
    Rtl28PhysicalBundle,
    Rtl28PhysicalRegion,
    Rtl28PortPlacement,
    SIMPLE_LAYOUT_IDS,
    VIEW_LAYOUT_IDS,
    ZeroCopyViewLayout,
    ZeroCopyViewProof,
)
from .add28_layout import (  # noqa: E402
    ADD28_LAYOUT_IDS,
    Add28PhysicalBundle,
    QLinearAddPhysicalLayout,
)
from .conv28_layout import (  # noqa: E402
    CONV28_LAYOUT_IDS,
    Conv28PhysicalBundle,
    Conv28PhysicalPlan,
    QLinearConvPhysicalLayout,
)
from .matmul28_layout import (  # noqa: E402
    MATMUL28_LAYOUT_IDS,
    MatMul28PhysicalBundle,
    QLinearMatMulPhysicalLayout,
)
from .pool28_layout import (  # noqa: E402
    GLOBAL_AVERAGE_POOL_LAYOUT_IDS,
    MAXPOOL_LAYOUT_IDS,
    GlobalAveragePoolPhysicalLayout,
    MaxPoolPhysicalLayout,
    PoolPhysicalBundle,
)
__all__ = [
    "ADD28_LAYOUT_IDS",
    "Add28PhysicalBundle",
    "CONV28_LAYOUT_IDS",
    "Conv28PhysicalBundle",
    "Conv28PhysicalPlan",
    "DequantizeLinearPhysicalLayout",
    "GLOBAL_AVERAGE_POOL_LAYOUT_IDS",
    "GlobalAveragePoolPhysicalLayout",
    "IdentityLayout",
    "LayoutTransform",
    "MATMUL28_LAYOUT_IDS",
    "MAXPOOL_LAYOUT_IDS",
    "MatMul28PhysicalBundle",
    "MaxPoolPhysicalLayout",
    "PoolPhysicalBundle",
    "QuantizeLinearPhysicalLayout",
    "QLinearConvPhysicalLayout",
    "QLinearAddPhysicalLayout",
    "QLinearMatMulPhysicalLayout",
    "Rtl28PhysicalBundle",
    "Rtl28PhysicalRegion",
    "Rtl28PortPlacement",
    "SIMPLE_LAYOUT_IDS",
    "VIEW_LAYOUT_IDS",
    "ZeroCopyViewLayout",
    "ZeroCopyViewProof",
]
