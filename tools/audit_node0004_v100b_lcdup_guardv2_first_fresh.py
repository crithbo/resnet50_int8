#!/usr/bin/env python3
"""Route the established observer first-fresh harness to guard-v2 v100."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise RuntimeError(f"first-fresh routing anchor differs: {old!r}")
    return text.replace(old, new)


def main() -> int:
    source = (ROOT / "tools/audit_node0004_v99b_lcdup_guarded_first_fresh.py").read_text(encoding="utf-8")
    source = replace_once(source, 'PACKAGE_ID = "r5_n4_hw_v99b_lcdup_guarded"', 'PACKAGE_ID = "r5_n4_hw_v100b_lcdup_guardv2"')
    source = replace_once(source, 'validate_node0004_v99b_lcdup_guarded_hdl.py', 'validate_node0004_v100b_lcdup_guardv2_hdl.py')
    source = replace_once(source, 'prefix="node0004-v99-firstfresh-"', 'prefix="node0004-v100-firstfresh-"')
    namespace = {"__name__": "node0004_v100_first_fresh_routed", "__file__": str(ROOT / "tools/audit_node0004_v99b_lcdup_guarded_first_fresh.py")}
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    result = int(namespace["main"]())
    output = Path(sys.argv[sys.argv.index("--output-dir") + 1]).resolve()
    contract_path = output / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["rule_change"]["epoch_id"] = "observer-operational-guard-live-tree-v2"
    contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
