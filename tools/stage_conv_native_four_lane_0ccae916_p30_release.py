#!/usr/bin/env python3
"""Stage p30 immutable ZIP and exact release receipts for storage rotation."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ID = "r5_n4_0cc_p30_bankvalid"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p30_bankvalid"
BUILD = BASE / "build"
STAGE = BASE / "release_stage"
SOURCES = {
    f"{PACKAGE_ID}.zip": BUILD / f"{PACKAGE_ID}.zip",
    f"{PACKAGE_ID}.zip.sha256": BUILD / f"{PACKAGE_ID}.zip.sha256",
    f"{PACKAGE_ID}.build.json": BUILD / f"{PACKAGE_ID}.build.json",
    f"{PACKAGE_ID}.runner_harness.json": BUILD / f"{PACKAGE_ID}.runner_harness.json",
    f"{PACKAGE_ID}.shared_layout.json": BUILD / f"{PACKAGE_ID}.shared_layout.json",
    f"{PACKAGE_ID}.post_sim.json": BUILD / f"{PACKAGE_ID}.post_sim.json",
    f"{PACKAGE_ID}.source_bound_final_zip.json": BUILD / f"{PACKAGE_ID}.source_bound_final_zip.json",
    f"{PACKAGE_ID}.final_zip_audit.json": BASE / f"{PACKAGE_ID}.final_zip_audit.json",
    f"{PACKAGE_ID}.family_audit.json": BASE / "p30_family_audit.json",
    f"{PACKAGE_ID}.build_profile.json": BASE / "server_package_build_profile.json",
    f"{PACKAGE_ID}.build_spec.json": BASE / "server_package_build_spec.json",
}


def main() -> int:
    if STAGE.exists():
        raise RuntimeError("refusing to overwrite p30 release stage")
    if not all(path.is_file() for path in SOURCES.values()):
        raise RuntimeError("p30 release source is absent")
    STAGE.mkdir(parents=True)
    for name, source in SOURCES.items():
        shutil.copyfile(source, STAGE / name)
    print(STAGE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
