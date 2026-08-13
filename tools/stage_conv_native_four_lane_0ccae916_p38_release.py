#!/usr/bin/env python3
"""Stage the immutable p38 ZIP and exact audit receipts."""

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p38_mse4join"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p38_mse4join"
BUILD = BASE / "build"
STAGE = BASE / "release_stage"
SOURCES = {
    f"{PACKAGE}.zip": BUILD / f"{PACKAGE}.zip",
    f"{PACKAGE}.zip.sha256": BUILD / f"{PACKAGE}.zip.sha256",
    f"{PACKAGE}.build.json": BUILD / f"{PACKAGE}.build.json",
    f"{PACKAGE}.runner_harness.json": BUILD / f"{PACKAGE}.runner_harness.json",
    f"{PACKAGE}.shared_layout.json": BUILD / f"{PACKAGE}.shared_layout.json",
    f"{PACKAGE}.post_sim.json": BUILD / f"{PACKAGE}.post_sim.json",
    f"{PACKAGE}.source_bound_final_zip.json": BUILD / f"{PACKAGE}.source_bound_final_zip.json",
    f"{PACKAGE}.family_audit.json": BASE / "p38_family_audit.json",
    f"{PACKAGE}.final_zip_audit.json": BASE / f"{PACKAGE}.final_zip_audit.json",
    f"{PACKAGE}.build_profile.json": BASE / "server_package_build_profile_v2.json",
    f"{PACKAGE}.build_spec.json": BASE / "server_package_build_spec_v2.json",
}


def main() -> int:
    if STAGE.exists():
        raise RuntimeError("refusing to overwrite p38 release stage")
    if not all(path.is_file() for path in SOURCES.values()):
        raise RuntimeError("p38 release evidence is absent")
    STAGE.mkdir(parents=True)
    for name, source in SOURCES.items():
        shutil.copyfile(source, STAGE / name)
    print(STAGE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
