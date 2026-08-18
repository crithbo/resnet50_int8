#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["preflight"])
    parser.add_argument("--package-root", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.package_root / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "PACKAGE_READY_NOT_RUN":
        print("package claim boundary differs")
        return 19
    if manifest.get("test_id") != args.package_root.name:
        print("package identity differs")
        return 20
    print(json.dumps({"schema": "synthetic-package-runtime-preflight-v1", "valid": True}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
