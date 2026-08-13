from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


INSTALL = "r5_n71_gap_v49_mse4_maskwide_diag"
SOURCE_RECEIPT_SHA = (
    "e7a4666b7479bf8016faa1798e161562c4b1b1123fb17391f409b1c5900f208f"
)
SOURCE_RUNNER_SHA = (
    "672919c1c343a98f08f98318046af68d5eaeab560982177e20a5e7e7045a7847"
)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", type=Path, required=True)
    parser.add_argument("--source-harness", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_bytes = args.source_harness.read_bytes()
    if digest(source_bytes) != SOURCE_RECEIPT_SHA:
        raise SystemExit("source v49 dynamic harness receipt SHA mismatch")
    source = json.loads(source_bytes)
    with zipfile.ZipFile(args.zip) as archive:
        runner = archive.read(f"{INSTALL}/PREPARE_AND_RUN.sh")
    if digest(runner) != SOURCE_RUNNER_SHA:
        raise SystemExit("final ZIP runner differs from dynamically tested runner")
    result = {
        **source,
        "derived_from_zip_sha256": digest(args.zip.read_bytes()),
        "runner_member_sha256": digest(runner),
        "receipt_reuse": {
            "source": args.source_harness.as_posix(),
            "source_sha256": SOURCE_RECEIPT_SHA,
            "exact_runner_member_byte_equal": True,
            "shared_control_flow": "INSTALL_ONLY_V2_14_OF_14_PASS",
            "changed_only_after_dynamic_harness": [
                "SERVER_RUNTIME_LAYOUT_CONTRACT.json path-budget arithmetic",
                "TEST_PACKAGE_MANIFEST.json path-budget receipt and file SHA",
            ],
            "changed_family_surface_validated_separately": True,
        },
        "claim_boundary": (
            "Exact dynamic normal/preflight/compile/HUP/INT/TERM result is "
            "rebound only because the final ZIP runner member is byte-identical. "
            "The changed path-budget contract and manifest are revalidated by "
            "the exact final-ZIP shared validator."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(json.dumps(result["receipt_reuse"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
