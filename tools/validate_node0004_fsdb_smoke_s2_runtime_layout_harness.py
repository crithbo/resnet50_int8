#!/usr/bin/env python3
"""Run the exact s2 FSDB smoke through the established isolated harness."""

import validate_node0004_fsdb_smoke_s1_runtime_layout_harness as base

base.PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s2"

if __name__ == "__main__":
    raise SystemExit(base.main())
