#!/usr/bin/env python3
"""Build fresh s3 with the s1 compiler fix and exact operator root receipt."""

import build_node0004_fsdb_smoke_s2 as fixed


base = fixed.base
PACKAGE_ID = "r5_n4_hw_fsdbsmoke_s3"
OLD_ID = "r5_n4_hw_fsdbsmoke_s2"

base.PACKAGE_ID = PACKAGE_ID
base.OUT = base.ROOT / "outputs/conv_node0004_fsdb_smoke_s3_release1"
base.BUILD_ROOT = base.OUT / "build" / PACKAGE_ID
base.FINAL_ZIP = base.OUT / f"{PACKAGE_ID}.zip"
for name in ("RUNTIME_HELPER", "README", "RUNNER"):
    setattr(base, name, getattr(base, name).replace(OLD_ID, PACKAGE_ID))
base.README = base.README.replace("smoke s2", "smoke s3")


if __name__ == "__main__":
    raise SystemExit(base.main())
