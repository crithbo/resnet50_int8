#!/usr/bin/env python3
"""Current exact-final-ZIP first-fresh audit for v98 targeted observer."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_hw_v98b_lcdup_tuple10"


def main() -> int:
    source = ROOT / "tools/audit_node0004_v89b_observerwide_first_fresh.py"
    spec = importlib.util.spec_from_file_location("node0004_v98_first_fresh_base", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PACKAGE_ID = PACKAGE
    module.RULE_IDS = list(module.RULE_IDS) + [
        "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001",
        "NODE0004-LC-BRANCH-DUPLICATION-MAPPER-AB-TARGETED-001",
    ]
    original_run = module.run

    def routed_run(command, *args, **kwargs):
        command = list(command)
        if len(command) > 1 and str(command[1]).endswith("validate_node0004_v89b_observerwide_hdl.py"):
            command[1] = str(ROOT / "tools/validate_node0004_v98b_lcdup_tuple10_hdl.py")
        return original_run(command, *args, **kwargs)

    module.run = routed_run
    result = module.main()
    output = Path(sys.argv[sys.argv.index("--output-dir") + 1]).resolve()
    contract_path = output / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["rule_change"]["epoch_id"] = "node0004-lc-branch-duplication-targeted-v1"
    contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
