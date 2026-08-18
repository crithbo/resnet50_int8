#!/usr/bin/env python3
"""Re-run the current independent observer audit for fresh v91."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_hw_v91b_normfix"


def main() -> int:
    source = ROOT / "tools/audit_node0004_v89b_observerwide_first_fresh.py"
    spec = importlib.util.spec_from_file_location("node0004_first_fresh_base", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PACKAGE_ID = PACKAGE_ID
    module.RULE_IDS = list(module.RULE_IDS) + [
        "CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001"
    ]
    original_run = module.run

    def routed_run(command, *args, **kwargs):
        command = list(command)
        if len(command) > 1 and str(command[1]).endswith(
            "validate_node0004_v89b_observerwide_hdl.py"
        ):
            command[1] = str(ROOT / "tools/validate_node0004_v91b_normalizerfix_hdl.py")
        return original_run(command, *args, **kwargs)

    module.run = routed_run
    result = module.main()
    output = Path(sys.argv[sys.argv.index("--output-dir") + 1]).resolve()
    contract_path = output / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["rule_change"]["epoch_id"] = "node0004-compile-normalizer-arity-fix-v1"
    contract["rule_change"]["rule_ids"].append(
        "PACKAGE_LOCAL_COMPILE_LOG_NORMALIZER_ARITY_NEGATIVE"
    )
    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


if __name__ == "__main__":
    raise SystemExit(main())
