#!/usr/bin/env python3
"""Run the exact GAP v54 runner through the isolated safe harness."""
import validate_gap_node0071_v51_runner_harness as base
base.INSTALL=base.V54_INSTALL
if __name__=="__main__":raise SystemExit(base.main())
