#!/usr/bin/env python3
"""Build a read-only GAP RTL three-way identity collection bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_gap_probe_test_package import (  # noqa: E402
    _github_reference_identity,
    _reference_server_identity,
)


SCHEMA = "resnet50-gap-rtl-identity-bundle-v1"
BUNDLE_NAME = "gap_rtl_three_way_identity_v1"
DEFAULT_OUTPUT_REL = Path(
    "artifacts/operator_config_validation/r5-server-identity-bundles"
) / BUNDLE_NAME
MANIFEST_NAME = "IDENTITY_BUNDLE_MANIFEST.json"


class GapRtlIdentityBundleError(ValueError):
    """Raised when the identity-only bundle cannot be built safely."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _records(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative == MANIFEST_NAME:
            continue
        if path.is_symlink():
            raise GapRtlIdentityBundleError(
                f"identity bundle contains symlink: {relative}"
            )
        result[relative] = {
            "size_bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
    return result


def _tree_sha256(records: Mapping[str, Mapping[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative, item in sorted(records.items()):
        digest.update(
            f"{relative}\0{item['size_bytes']}\0{item['sha256']}\n".encode()
        )
    return digest.hexdigest()


def _copy_lf(source: Path, destination: Path) -> None:
    text = source.read_text(encoding="utf-8")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        text.replace("\r\n", "\n").replace("\r", "\n"),
        encoding="utf-8",
        newline="\n",
    )


def _write_lf(destination: Path, text: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        text.replace("\r\n", "\n").replace("\r", "\n"),
        encoding="utf-8",
        newline="\n",
    )


def _capture_script() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: bash CAPTURE_ONLY.sh /absolute/path/to/NDP_copyXX [output.json]" >&2
  exit 2
fi

bundle_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ndp_root="$(cd "$1" && pwd)"
output="${2:-${bundle_root}/server_rtl_three_way_identity.json}"

python3 "${bundle_root}/collector/capture_gap_rtl_three_way_identity.py" \
  --ndp-root "${ndp_root}" \
  --identity-manifest "${bundle_root}/IDENTITY_BUNDLE_MANIFEST.json" \
  --output "${output}"

printf 'Identity report: %s\\n' "${output}"
"""


def _readme() -> str:
    return """# GAP RTL three-way identity-only bundle

This bundle only reads identity information. It contains no workload, SCA,
bitstream, observer, testbench, functional RTL, compile command or simulation
command.

It does not modify the server testbench, RTL, install tree or run directories.
It reads:

- the resolved server RTL path and RTL Git identity;
- the existing top testbench, Makefile and active filelist hashes;
- the complete RTL tree aggregate identity;
- raw and canonical-text hashes for 14 GAP-path RTL files;
- per-file GitHub/local/server three-way classifications.

Run:

```bash
bash CAPTURE_ONLY.sh /home/panqs/ndp/NDP_copy02
```

Return only:

```text
server_rtl_three_way_identity.json
```

Canonical text comparison normalizes CRLF/CR to LF and ignores only trailing
blank lines. It preserves every other character.
"""


def _write_deterministic_zip(root: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(
        zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = f"{root.name}/{path.relative_to(root).as_posix()}"
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            mode = 0o100755 if path.name == "CAPTURE_ONLY.sh" else 0o100644
            info.external_attr = (mode & 0xFFFF) << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


def _audit_zip(root: Path, zip_path: Path) -> dict[str, Any]:
    expected = {
        f"{root.name}/{path.relative_to(root).as_posix()}": _sha256(path)
        for path in root.rglob("*")
        if path.is_file()
    }
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise GapRtlIdentityBundleError(
                "identity ZIP exact file set differs from directory"
            )
        for name, expected_hash in expected.items():
            if hashlib.sha256(archive.read(name)).hexdigest() != expected_hash:
                raise GapRtlIdentityBundleError(
                    f"identity ZIP payload hash differs: {name}"
                )
    return {"entry_count": len(expected), "exact_file_set": True}


def build_bundle(project_root: Path, output: Path) -> dict[str, Any]:
    root = project_root.resolve()
    output = output.resolve()
    zip_path = output.with_suffix(".zip")
    sha_path = Path(f"{zip_path}.sha256")
    for target in (output, zip_path, sha_path):
        if target.exists():
            raise GapRtlIdentityBundleError(f"output must be fresh: {target}")

    output.parent.mkdir(parents=True, exist_ok=True)
    _copy_lf(
        root / "tools" / "capture_gap_probe_server_identity.py",
        output / "collector" / "capture_gap_probe_server_identity.py",
    )
    _copy_lf(
        root / "tools" / "capture_gap_rtl_three_way_identity.py",
        output / "collector" / "capture_gap_rtl_three_way_identity.py",
    )
    _write_lf(output / "CAPTURE_ONLY.sh", _capture_script())
    _write_lf(output / "README.md", _readme())

    payload_records = _records(output)
    manifest = {
        "schema": SCHEMA,
        "status": "server_identity_collection_ready",
        "bundle_name": BUNDLE_NAME,
        "operation_policy": {
            "read_only": True,
            "contains_workload": False,
            "contains_sca": False,
            "contains_bitstream": False,
            "contains_observer": False,
            "contains_testbench": False,
            "contains_functional_rtl": False,
            "modifies_testbench_or_rtl": False,
            "starts_compile_or_simulation": False,
        },
        "reference_server_identity": _reference_server_identity(root),
        "github_reference_identity": _github_reference_identity(root),
        "run_entry": "CAPTURE_ONLY.sh",
        "payload_file_count": len(payload_records),
        "payload_tree_sha256": _tree_sha256(payload_records),
        "files": payload_records,
    }
    _write_lf(
        output / MANIFEST_NAME,
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    )

    _write_deterministic_zip(output, zip_path)
    zip_audit = _audit_zip(output, zip_path)
    zip_sha256 = _sha256(zip_path)
    _write_lf(sha_path, f"{zip_sha256}  {zip_path.name}\n")
    return {
        **manifest,
        "directory": output.as_posix(),
        "zip": zip_path.as_posix(),
        "zip_size_bytes": zip_path.stat().st_size,
        "zip_sha256": zip_sha256,
        "zip_audit": zip_audit,
        "sha256_file": sha_path.as_posix(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / DEFAULT_OUTPUT_REL)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    try:
        report = build_bundle(ROOT, output)
    except Exception as error:
        print(
            f"GAP RTL identity bundle generation failed: {error}",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
