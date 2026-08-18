#!/usr/bin/env python3
"""Route the exact first-fresh audit from v101 to canonical-guard v102."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = (ROOT / "tools/audit_node0004_v101b_lcdup_guardprocfix_first_fresh.py").read_text(encoding="utf-8")
    source = source.replace("r5_n4_hw_v101b_lcdup_guardprocfix", "r5_n4_hw_v102b_lcdup_guardprocfs")
    source = source.replace("validate_node0004_v101b_lcdup_guardprocfix_hdl.py", "validate_node0004_v102b_lcdup_guardprocfs_hdl.py")
    source = source.replace("node0004-v101-firstfresh-", "node0004-v102-firstfresh-")
    source = source.replace("observer-operational-guard-live-tree-v2-self-enumerator-fix-local", "observer-guard-process-identity-v3")
    namespace = {"__name__": "node0004_v102_first_fresh_routed", "__file__": str(ROOT / "tools/audit_node0004_v101b_lcdup_guardprocfix_first_fresh.py")}
    exec(compile(source, namespace["__file__"], "exec"), namespace)
    return int(namespace["main"]())


if __name__ == "__main__":
    raise SystemExit(main())
