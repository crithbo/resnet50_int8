from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


# The package entry must suppress bytecode before importing any package-local
# dependency. PREPARE_AND_RUN.sh also exports PYTHONDONTWRITEBYTECODE=1; both
# guards are intentional and independently audited.
sys.dont_write_bytecode = True

try:
    import node0004_native_four_lane_runtime_v1_base as base
except ImportError:
    from tools import conv_native_four_lane_df23e4d_server_runtime as base


RuntimeErrorContract = base.RuntimeErrorContract
numeric_base = base.numeric_base
EXPECTED_LEAVES = base.EXPECTED_LEAVES
PASS_STATUS = base.PASS_STATUS
preflight = base.preflight
collect_compile_identity = base.collect_compile_identity
qualify_run = base.qualify_run
analyze = base.analyze
collect = base.collect


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeErrorContract(f"JSON root must be object: {path}")
    return value


def path_budget(package_root: Path, server_root: Path) -> dict[str, Any]:
    package = package_root.resolve()
    server = server_root.resolve()
    manifest = load_json(package / "package_manifest.json")
    budget = manifest.get("path_length_budget")
    if not isinstance(budget, dict):
        raise RuntimeErrorContract("package path-length budget is missing")
    relative_chars = budget.get("max_projected_relative_path_chars")
    limit = budget.get("max_projected_absolute_path_limit_chars")
    longest = budget.get("longest_projected_relative_path")
    if (
        not isinstance(relative_chars, int)
        or relative_chars <= 0
        or not isinstance(limit, int)
        or limit <= 0
        or not isinstance(longest, str)
        or len(longest) != relative_chars
    ):
        raise RuntimeErrorContract("package path-length budget is malformed")
    projected = len(str(server)) + 1 + relative_chars
    valid = projected <= limit
    receipt = {
        "schema": "conv-native-four-lane-path-budget-runtime-v1",
        "valid": valid,
        "server_root": str(server),
        "server_root_chars": len(str(server)),
        "max_projected_relative_path_chars": relative_chars,
        "max_projected_absolute_path_chars": projected,
        "max_projected_absolute_path_limit_chars": limit,
        "longest_projected_relative_path": longest,
        "required_shortening_chars": max(0, projected - limit),
    }
    if not valid:
        raise RuntimeErrorContract(
            "server root exceeds package path budget: "
            f"projected={projected} limit={limit} "
            f"shorten_by={projected - limit} path={longest}"
        )
    return receipt


def _path_budget_main(arguments: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--server-root", type=Path, required=True)
    args = parser.parse_args(arguments)
    value = path_budget(args.package_root, args.server_root)
    print(json.dumps(value, ensure_ascii=False))
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "path-budget":
        return _path_budget_main(sys.argv[2:])
    return base.main()


if __name__ == "__main__":
    raise SystemExit(main())
