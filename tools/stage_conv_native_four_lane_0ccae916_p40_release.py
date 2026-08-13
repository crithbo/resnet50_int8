#!/usr/bin/env python3
"""Stage p40 release receipts next to its immutable ZIP for rotation."""

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p40_dhpubfix"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p40_dhpubfix"
BUILD = BASE / "build"
SOURCES = {
    f"{PACKAGE}.final_zip_audit.json": BASE / f"{PACKAGE}.final_zip_audit.json",
    f"{PACKAGE}.build_profile.json": BASE / "server_package_build_profile_v2.json",
    f"{PACKAGE}.build_spec.json": BASE / "server_package_build_spec_v2.json",
    f"{PACKAGE}.first_fresh_validation.json": BASE / "first_fresh_audit/first_fresh_validation.json",
    f"{PACKAGE}.first_fresh_contract.json": BASE / "first_fresh_audit/contract.json",
}


def main() -> int:
    if not all(path.is_file() for path in SOURCES.values()):
        raise RuntimeError("p40 release evidence is incomplete")
    targets = [BUILD / name for name in SOURCES]
    if any(path.exists() for path in targets):
        raise RuntimeError("refusing to overwrite p40 staged receipt")
    for name, source in SOURCES.items():
        shutil.copyfile(source, BUILD / name)
    print(BUILD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
