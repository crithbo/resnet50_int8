#!/usr/bin/env python3
"""Package-local observer syntax checks for the version-unbound Requant probe.

This module deliberately contains no server source discovery, hashing, Git,
Makefile, filelist, RTL-tree, focused-RTL, README, or basename logic.
"""

from __future__ import annotations

import re


class RequantRuntimeError(RuntimeError):
    pass


_GENERATED_PATH = re.compile(r"\b[A-Za-z_]\w*_gen\s*\[([^\]]+)\]")
_GENVAR = re.compile(r"\bgenvar\s+([A-Za-z_]\w*)")


def validate_observer_xmr_elaboration(text: str) -> dict[str, object]:
    declared = set(_GENVAR.findall(text))
    references = _GENERATED_PATH.findall(text)
    runtime_indexed: list[str] = []
    for expression in references:
        token = expression.strip()
        if token.isdecimal() or token in declared:
            continue
        runtime_indexed.append(token)
    if runtime_indexed:
        raise RequantRuntimeError(
            "observer contains runtime-indexed generated instance paths"
        )
    return {
        "schema": "server-observer-xmr-elaboration-static-gate-v1",
        "rule_id": "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
        "status": "pass",
        "checked_generated_instance_reference_count": len(references),
        "declared_genvars": sorted(declared),
        "runtime_indexed_generated_instance_reference_count": 0,
        "ordinary_signal_array_runtime_indexing_allowed": True,
    }


__all__ = [
    "RequantRuntimeError",
    "validate_observer_xmr_elaboration",
]
