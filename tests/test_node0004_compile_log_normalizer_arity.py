from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "normalizer_arity",
    ROOT / "tools/validate_node0004_compile_log_normalizer_arity.py",
)
assert SPEC and SPEC.loader
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


def runner(arguments: str, targets: str = "s,d,f,h,t") -> str:
    return f'''#!/usr/bin/env bash
compile_log="$compile_full_log"
python3 - {arguments} <<'PY'
import pathlib,re,sys
{targets}=map(pathlib.Path,sys.argv[1:]); raw=s.read_bytes()
PY
'''


def test_exact_five_argument_normalizer_passes() -> None:
    value = GATE.check_runner(
        runner(
            '"$compile_log" "$compile_driver_log" "$compile_first_error_txt" '
            '"$compile_log_head_txt" "$compile_log_tail_txt"'
        )
    )
    assert value["pass"] is True
    assert value["argument_count"] == value["target_count"] == 5


def test_six_arguments_to_five_targets_fail_closed() -> None:
    value = GATE.check_runner(
        runner(
            '"$compile_log" "$compile_driver_log" "$compile_first_error_txt" '
            '"$compile_log_head_txt" "$compile_log_tail_txt" "$compile_full_log"'
        )
    )
    assert value["pass"] is False
    assert "normalizer argument/target mismatch: 6 != 5" in value["errors"]


def test_five_arguments_to_four_targets_fail_closed() -> None:
    value = GATE.check_runner(
        runner(
            '"$compile_log" "$compile_driver_log" "$compile_first_error_txt" '
            '"$compile_log_head_txt" "$compile_log_tail_txt"',
            targets="s,d,f,h",
        )
    )
    assert value["pass"] is False
    assert "normalizer argument/target mismatch: 5 != 4" in value["errors"]
