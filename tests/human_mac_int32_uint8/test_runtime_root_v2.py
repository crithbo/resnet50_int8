import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


builder = load(
    "human_mac_runtime_root_builder",
    ROOT / "tools/build_human_mac_int32_uint8_runtime_root_v2.py",
)
validator = load(
    "human_mac_runtime_root_validator",
    ROOT / "tools/validate_human_mac_int32_uint8_runtime_root_v2.py",
)


def test_two_fresh_builds_are_identical(tmp_path):
    first = builder.build(tmp_path / "first")
    second = builder.build(tmp_path / "second")
    assert first["zip_sha256"] == second["zip_sha256"]
    assert Path(first["zip"]).read_bytes() == Path(second["zip"]).read_bytes()


def test_variable_root_and_semantic_identity(tmp_path):
    result = builder.build(tmp_path / "candidate")
    report = validator.validate(Path(result["zip"]), builder.SOURCE_ZIP)
    assert report["passed"], report
