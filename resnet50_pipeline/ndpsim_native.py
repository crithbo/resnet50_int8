from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


MODEL_EXECPLAN_SRC = "ndp-sim/model_execplan/src"
JSON_LOADER_PATH = (
    "ndp-sim/model_execplan/src/"
    "execution_plan_generator/json_loader.py"
)
CONTROL_REGISTERS_PATH = (
    "ndp-sim/model_execplan/src/"
    "execution_plan_generator/control_registers.py"
)
OUTPUT_WRITER_PATH = (
    "ndp-sim/model_execplan/src/"
    "execution_plan_generator/output_writer.py"
)
PIPELINE_PATH = (
    "ndp-sim/model_execplan/src/"
    "execution_plan_generator/pipeline.py"
)


class NdpSimNativeError(RuntimeError):
    pass


def _native_module(project_root: Path, name: str) -> ModuleType:
    root = project_root.resolve()
    source_root = (root / MODEL_EXECPLAN_SRC).resolve()
    if not source_root.is_dir():
        raise NdpSimNativeError(
            f"active ndp-sim model_execplan source is missing: {source_root}"
        )
    source_text = str(source_root)
    if source_text not in sys.path:
        sys.path.insert(0, source_text)
    module = importlib.import_module(name)
    module_file = Path(str(getattr(module, "__file__", ""))).resolve()
    try:
        module_file.relative_to(source_root)
    except ValueError as error:
        raise NdpSimNativeError(
            f"imported {name} from another repository: {module_file}"
        ) from error
    return module


def load_native_execution_plan(
    project_root: Path, graph_path: str | Path
) -> dict[str, Any]:
    loader = _native_module(
        project_root, "execution_plan_generator.json_loader"
    )
    path = Path(graph_path)
    if not path.is_absolute():
        path = project_root.resolve() / path
    try:
        plan = loader.load_execution_plan_json(path)
        value = loader.execution_plan_to_dict(plan)
    except Exception as error:
        raise NdpSimNativeError(
            f"native model_execplan cannot parse {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise NdpSimNativeError("native normalized execution plan is malformed")
    return value


def native_control_handlers(project_root: Path) -> dict[str, str]:
    module = _native_module(
        project_root, "execution_plan_generator.control_registers"
    )
    registry = getattr(module, "OP_CONTROL_REGISTER_FN", None)
    if not isinstance(registry, dict):
        raise NdpSimNativeError(
            "native OP_CONTROL_REGISTER_FN registry is missing"
        )
    result: dict[str, str] = {}
    for op_type, handler in registry.items():
        if not isinstance(op_type, str) or not callable(handler):
            raise NdpSimNativeError(
                "native control-register registry is malformed"
            )
        result[op_type] = str(getattr(handler, "__name__", ""))
    return dict(sorted(result.items()))


__all__ = [
    "CONTROL_REGISTERS_PATH",
    "JSON_LOADER_PATH",
    "MODEL_EXECPLAN_SRC",
    "OUTPUT_WRITER_PATH",
    "PIPELINE_PATH",
    "NdpSimNativeError",
    "load_native_execution_plan",
    "native_control_handlers",
]
