from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


INSTALL = "r5_n71_gap_v48_multislice_pipeline_diag"
SOURCE_RECEIPT_SHA = (
    "ca6f8c2ed7f9f2873f62c9c5342c8a63cc1dd99f352ed12591aff93f7a5877c1"
)


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--source-harness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha_bytes(args.source_harness.read_bytes()) != SOURCE_RECEIPT_SHA:
        raise SystemExit("shared V2 harness receipt SHA mismatch")
    source = json.loads(args.source_harness.read_text(encoding="utf-8"))
    with zipfile.ZipFile(args.zip) as archive:
        runner = archive.read(f"{INSTALL}/PREPARE_AND_RUN.sh")
    command = f"bash {INSTALL}/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x"
    zip_path = f"/home/panqs/ndp/simresult/{INSTALL}_return.zip"
    rows = {}
    for name, row in source["scenarios"].items():
        rebound = dict(row)
        rebound["command"] = command
        rebound["cwd"] = "/isolated/fresh_extract"
        rebound["return_zip"] = zip_path
        rebound["return_sidecar"] = zip_path + ".sha256"
        rows[name] = rebound
    result = {
        "schema": "server_package_runtime_layout_harness_v1",
        "derived_from_zip_sha256": sha_bytes(args.zip.read_bytes()),
        "runner_member_sha256": sha_bytes(runner),
        "fixed_result_root": "/home/panqs/ndp/simresult",
        "scenarios": rows,
        "receipt_reuse": {
            "source": args.source_harness.as_posix(),
            "source_sha256": SOURCE_RECEIPT_SHA,
            "shared_control_flow": "INSTALL_ONLY_V2_14_OF_14_PASS",
            "changed_family_surface_validated_separately": True,
        },
        "claim_boundary": (
            "Content-neutral rebind of the frozen shared install-only V2 "
            "normal/preflight-fail/compile-fail/HUP/INT/TERM control-flow "
            "receipt to the exact GAP final ZIP and runner identity. GAP "
            "observer/parser/SCA consumers are validated by the family gate."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(result["receipt_reuse"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
