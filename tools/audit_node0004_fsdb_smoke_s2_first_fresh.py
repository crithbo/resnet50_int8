#!/usr/bin/env python3
"""Run the current first-fresh audit against the exact s2 smoke ZIP."""

import audit_node0004_fsdb_smoke_s1_first_fresh as base

base.PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s2"

if __name__ == "__main__":
    raise SystemExit(base.main())
