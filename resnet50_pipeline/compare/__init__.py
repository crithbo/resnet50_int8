"""Logical tensor result comparison for golden, simulator and hardware outputs."""

from .logical import (
    LogicalTensorSource,
    compare_logical_tensor,
    compare_request,
    load_comparison_request,
)

__all__ = [
    "LogicalTensorSource",
    "compare_logical_tensor",
    "compare_request",
    "load_comparison_request",
]
