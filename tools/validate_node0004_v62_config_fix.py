from __future__ import annotations

import argparse
import hashlib
import json
import stat
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
INSTALL = "r5_n4_hw_v62_pekeep_fix"
SOURCE = "r5_n4_hw_v61_lcmap_argv_fix"
EXPECTED_ZIP_SHA = "613eb2a6e4dc14f65065c1a4cd880f0f42828b25a6ebde8383ae78f6d2bdec40"
EXPECTED_SOURCE_SHA = "c78e62cde4f8e185f801900773117017982920b9a479996a1c31af8a1dae1e96"
EXPECTED_BITSTREAM_SHA = (
    "2f79247677c0ae8a8f89ac1bca7f381d757e28d049c7eef88e8f0bfae75d90fa"
)
BITSTREAM = (
    "workload/runtime/runs/c0/install/cfg_pkg/"
    "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
)
LOCAL_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-pe1-keep-last-index-fix-c0-v62/local_rebuild_report.json"
)
BOUNDARY = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-pe1-keep-last-index-fix-c0-v62/boundary_microtrace.json"
)
LEDGER = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-node0004-pe1-keep-last-index-fix-c0-v62/"
    "causal_transaction_ledger.json"
)


def sha_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_zip(path: Path, root: str) -> tuple[dict[str, bytes], list[str]]:
    errors: list[str] = []
    result: dict[str, bytes] = {}
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            errors.append("CRC failed")
        seen: set[str] = set()
        for item in archive.infolist():
            pure = PurePosixPath(item.filename)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in item.filename
                or item.filename in seen
                or stat.S_ISLNK((item.external_attr >> 16) & 0xFFFF)
            ):
                errors.append(f"unsafe/duplicate member:{item.filename}")
                continue
            seen.add(item.filename)
            if pure.parts and pure.parts[0] != root:
                errors.append(f"root differs:{item.filename}")
            if not item.is_dir():
                result[PurePosixPath(*pure.parts[1:]).as_posix()] = archive.read(
                    item
                )
    return result, errors


def keep_ready(last_bit: int, last_index: int, keep: int) -> int:
    return int(bool(last_bit) and not (last_index > keep))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--source-v61", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    errors: list[str] = []
    checks: dict[str, bool] = {}
    checks["zip_identity"] = sha_file(args.zip) == EXPECTED_ZIP_SHA
    checks["source_identity"] = sha_file(args.source_v61) == EXPECTED_SOURCE_SHA
    current, current_errors = read_zip(args.zip, INSTALL)
    previous, previous_errors = read_zip(args.source_v61, SOURCE)
    errors.extend(current_errors + previous_errors)
    manifest = json.loads(current.get("package_manifest.json", b"{}"))
    checks["manifest_fix_exact"] = (
        manifest.get("classification")
        == "CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS"
        and manifest.get("configuration_fix", {}).get("leaf_changes")
        == [
            {
                "path": "lc_pe_configs.PE1.inport0.keep_last_index",
                "old": 2,
                "new": 3,
            }
        ]
        and manifest.get("configuration_rebuilt") is True
        and manifest.get("functional_rtl_modified") is False
    )
    checks["final_bitstream_bound"] = (
        BITSTREAM in current
        and sha_bytes(current[BITSTREAM]) == EXPECTED_BITSTREAM_SHA
        and BITSTREAM in previous
        and sum(
            left != right
            for left, right in zip(previous[BITSTREAM], current[BITSTREAM])
        )
        == 1
        and [
            index
            for index, (left, right) in enumerate(
                zip(previous[BITSTREAM], current[BITSTREAM])
            )
            if left != right
        ]
        == [1301]
    )
    frozen_binary = sorted(
        name
        for name in set(previous) & set(current)
        if (
            "matrix_" in name
            or name.endswith(".golden")
            or name.endswith(".bin")
        )
        and name != BITSTREAM
    )
    checks["numeric_matrices_golden_frozen"] = (
        bool(frozen_binary)
        and all(previous[name] == current[name] for name in frozen_binary)
    )
    sca = json.loads(current["workload/runtime/runs/c0/sca_cfg.json"])
    sca_d = json.loads(current["workload/runtime/runs/c0/sca_cfg_D.json"])
    checks["sca_input_root_exact"] = all(
        not isinstance(value, dict)
        or "path" not in value
        or value["path"].startswith(f"install/cfg_pkg/{INSTALL}/runs/c0/")
        for value in sca.values()
    )
    checks["sca_output_root_exact"] = all(
        not isinstance(value, dict)
        or "path" not in value
        or value["path"].startswith(
            f"install/codex_runs/{INSTALL}/{{attempt}}/c0/"
        )
        for value in sca_d.values()
    )
    local = json.loads(LOCAL_REPORT.read_text(encoding="utf-8"))
    boundary = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    checks["local_physical_closure"] = (
        local.get("status") == "LOCAL_C0_PHYSICAL_REBUILD_PASS"
        and local.get("mapping", {}).get("unchanged") is True
        and local.get("execplan", {}).get("unchanged") is True
        and local.get("sca", {}).get("address_semantics_unchanged") is True
        and local.get("bitstream", {}).get("changed_offsets") == [1301]
    )
    checks["causal_ledger_and_boundary"] = (
        boundary.get("status") == "PASS"
        and ledger.get("status") == "PASS"
        and ledger.get("address_surface_changed") is False
    )
    negatives = {
        "old_keep2_terminal3_fails": keep_ready(1, 3, 2) == 0,
        "new_keep3_terminal3_passes": keep_ready(1, 3, 3) == 1,
        "nonterminal_does_not_release": keep_ready(0, 3, 3) == 0,
        "outer_terminal_index2_releases": keep_ready(1, 2, 3) == 1,
    }
    checks["negative_controls"] = all(negatives.values())
    for name, passed in checks.items():
        if not passed:
            errors.append(f"{name} failed")
    report = {
        "schema": "node0004-v62-config-fix-validation-v1",
        "valid": not errors,
        "errors": sorted(set(errors)),
        "checks": checks,
        "negative_controls": negatives,
        "zip_sha256": sha_file(args.zip),
        "source_v61_sha256": sha_file(args.source_v61),
        "bitstream": {
            "member": BITSTREAM,
            "sha256": sha_bytes(current.get(BITSTREAM, b"")),
            "changed_offsets": [1301],
        },
        "frozen_binary_count": len(frozen_binary),
        "local_report_sha256": sha_file(LOCAL_REPORT),
        "boundary_microtrace_sha256": sha_file(BOUNDARY),
        "causal_transaction_ledger_sha256": sha_file(LEDGER),
        "claim_boundary": (
            "Local changed-config consumer closure only; no DUT natural "
            "terminal, formal D, E4, or E5 claim."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"valid": not errors, "errors": errors}))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
