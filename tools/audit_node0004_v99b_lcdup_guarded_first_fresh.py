#!/usr/bin/env python3
"""Route the established observer first-fresh harness to guarded v99."""

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
    source = (ROOT / "tools/audit_node0004_v89b_observerwide_first_fresh.py").read_text(encoding="utf-8")
    source = replace_once(source, 'PACKAGE_ID = "r5_n4_hw_v89b_obswide"', 'PACKAGE_ID = "r5_n4_hw_v99b_lcdup_guarded"')
    source = replace_once(source, '"--timeout 21600" in runner_text', '"--timeout 3600" in runner_text')
    source = replace_once(source, 'validate_node0004_v89b_observerwide_hdl.py', 'validate_node0004_v99b_lcdup_guarded_hdl.py')
    source = replace_once(source, 'prefix="node0004-v89-firstfresh-"', 'prefix="node0004-v99-firstfresh-"')
    source = source.replace('"CDA-SERVER-PACKAGE-REPEAT-EXECUTION-EXACT-OWNED-RESET-001",\n]', '"CDA-SERVER-PACKAGE-REPEAT-EXECUTION-EXACT-OWNED-RESET-001",\n    "USER-OBSERVER-OPERATIONAL-GUARD-NO-SILENT-TRUNCATION-001",\n]')
    namespace = {"__name__": "node0004_v99_first_fresh_routed", "__file__": str(ROOT / "tools/audit_node0004_v89b_observerwide_first_fresh.py")}
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    result = int(namespace["main"]())
    output = Path(sys.argv[sys.argv.index("--output-dir") + 1]).resolve()
    contract_path = output / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["rule_change"]["epoch_id"] = "node0004-observer-disk-exhaustion-guard-v1"
    if "USER-OBSERVER-OPERATIONAL-GUARD-NO-SILENT-TRUNCATION-001" not in contract["rule_change"]["rule_ids"]:
        contract["rule_change"]["rule_ids"].append("USER-OBSERVER-OPERATIONAL-GUARD-NO-SILENT-TRUNCATION-001")
    contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
