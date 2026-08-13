#!/usr/bin/env python3
"""Build fresh FSDB smoke s2 with only the package-probe compiler fix."""

from pathlib import Path

import build_node0004_fsdb_smoke_s1 as base


PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s2"
OLD_SMOKE_ID = "r5_n4_hw_fsdbsmoke_s1"

base.PACKAGE_ID = PACKAGE_ID
base.OUT = base.ROOT / "outputs/conv_node0004_fsdb_smoke_s2_release1"
base.BUILD_ROOT = base.OUT / "build" / PACKAGE_ID
base.FINAL_ZIP = base.OUT / f"{PACKAGE_ID}.zip"

for name in ("RUNTIME_HELPER", "README", "RUNNER"):
    setattr(base, name, getattr(base, name).replace(OLD_SMOKE_ID, PACKAGE_ID))
base.README = base.README.replace("smoke s1", "smoke s2")

# Preserve the registered log field name `sequence=` because the parser contract
# consumes it. Rename only the SystemVerilog identifier rejected by production
# VCS; no DUT-facing or functional signal is changed.
probe = base.EVENT_PROBE
probe = probe.replace("integer sequence;", "integer event_seq_id;")
probe = probe.replace(", sequence, $time,", ", event_seq_id, $time,")
probe = probe.replace("sequence = sequence + 1;", "event_seq_id = event_seq_id + 1;")
probe = probe.replace("sequence = 0;", "event_seq_id = 0;")
base.EVENT_PROBE = probe


if __name__ == "__main__":
    raise SystemExit(base.main())
