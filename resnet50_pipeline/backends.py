from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .errors import CapabilityError, PipelineError


@dataclass(frozen=True)
class BackendCapabilities:
    name: str
    version: str
    ops: frozenset[str]
    dtypes: frozenset[str]
    slice_counts: frozenset[int]
    config_versions: frozenset[str]
    can_dump_physical_output: bool

    def require(self, op: str, dtype: str, slice_count: int, config_version: str) -> None:
        missing: list[str] = []
        if op not in self.ops:
            missing.append(f"op={op}")
        if dtype not in self.dtypes:
            missing.append(f"dtype={dtype}")
        if slice_count not in self.slice_counts:
            missing.append(f"slice_count={slice_count}")
        if config_version not in self.config_versions:
            missing.append(f"config_version={config_version}")
        if missing:
            raise CapabilityError(
                f"backend {self.name}@{self.version} does not support " + ", ".join(missing)
            )


class Backend(Protocol):
    capabilities: BackendCapabilities

    def execute(self, stage: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class ConfigBackend(Protocol):
    capabilities: BackendCapabilities

    def build_config(self, hw_op: dict[str, Any]) -> dict[str, Any]: ...


class SimulatorBackend(Protocol):
    capabilities: BackendCapabilities

    def run_simulator(self, config: dict[str, Any], physical_inputs: bytes) -> bytes: ...


class HardwareBackend(Protocol):
    capabilities: BackendCapabilities

    def load_start_wait_dump(self, execution: dict[str, Any], physical_inputs: bytes) -> bytes: ...


class MockBackend:
    def __init__(self, fail_stage: str | None = None):
        self.fail_stage = fail_stage
        self.capabilities = BackendCapabilities(
            name="mock",
            version="0.1",
            ops=frozenset({"MockIdentity"}),
            dtypes=frozenset({"uint8"}),
            slice_counts=frozenset({1, 4, 16}),
            config_versions=frozenset({"mock-0.1"}),
            can_dump_physical_output=True,
        )

    def execute(self, stage: str, payload: dict[str, Any]) -> dict[str, Any]:
        if stage == self.fail_stage:
            raise PipelineError(f"mock backend failure requested at stage {stage}")
        return {"stage": stage, "backend": "mock", "payload": payload}

    def build_config(self, hw_op: dict[str, Any]) -> dict[str, Any]:
        return {"config_version": "mock-0.1", "hw_op": hw_op}

    def run_simulator(self, config: dict[str, Any], physical_inputs: bytes) -> bytes:
        del config
        return physical_inputs

    def load_start_wait_dump(self, execution: dict[str, Any], physical_inputs: bytes) -> bytes:
        del execution
        return physical_inputs
