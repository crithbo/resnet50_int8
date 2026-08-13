#!/usr/bin/env python3
"""Run the exact v52 runner through the inherited isolated safe harness."""

from __future__ import annotations

import validate_gap_node0071_v51_runner_harness as harness


harness.INSTALL = harness.V52_INSTALL


if __name__ == "__main__":
    raise SystemExit(harness.main())
