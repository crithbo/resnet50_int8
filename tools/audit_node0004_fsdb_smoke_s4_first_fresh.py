#!/usr/bin/env python3
"""Run and bind the current first-fresh audit for FSDB quiescence smoke s4."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import audit_node0004_fsdb_smoke_s1_first_fresh as base


base.PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s4"
base.EPOCH = "waveform-retention-fsdb-quiescence-v1-967ef4e72e6c"


if __name__ == "__main__":
    status = base.main()
    output_dir = Path(sys.argv[sys.argv.index("--output-dir") + 1]).resolve()
    contract_path = output_dir / "contract.json"
    if contract_path.is_file():
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract["rule_change"]["rule_ids"].append("CDA-SERVER-FSDB-PROCESS-TREE-WRITER-QUIESCENCE-001")
        contract["rule_change"]["epoch_id"] = base.EPOCH
        contract_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    raise SystemExit(status)
