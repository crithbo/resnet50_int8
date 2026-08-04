#!/usr/bin/env python3
"""Verify that a GAP decision run kept the server functional RTL unchanged."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCHEMA = "resnet50-gap-stock-rtl-identity-receipt-v1"
IDENTITY_SCHEMA = "resnet50-gap-probe-server-identity-v3"
EXPECTED_PHASES = (
    "pre_install",
    "post_install",
    "post_run",
    "post_restore",
)
REQUIRED_FOCUS_RTL = {
    "rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv",
    "rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv",
}
STABLE_ARTIFACTS = ("makefile", "active_filelist")


class GapStockRtlIdentityError(ValueError):
    """Raised when server identity inputs are incomplete or malformed."""


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GapStockRtlIdentityError(
            f"cannot load server identity {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise GapStockRtlIdentityError(f"identity root must be an object: {path}")
    return value


def _file_fingerprint(identity: dict[str, Any]) -> tuple[Any, ...]:
    return (
        identity.get("exists"),
        identity.get("size_bytes"),
        identity.get("sha256"),
        identity.get("canonical_text_sha256"),
    )


def _plain_file_fingerprint(identity: dict[str, Any]) -> tuple[Any, ...]:
    return (
        identity.get("exists"),
        identity.get("size_bytes"),
        identity.get("sha256"),
    )


def build_receipt(identity_paths: list[Path]) -> dict[str, Any]:
    if len(identity_paths) != len(EXPECTED_PHASES):
        raise GapStockRtlIdentityError(
            f"expected {len(EXPECTED_PHASES)} identity files"
        )
    documents = [_load(path.resolve()) for path in identity_paths]
    phases = tuple(document.get("phase") for document in documents)
    if phases != EXPECTED_PHASES:
        raise GapStockRtlIdentityError(
            f"identity phase order differs: {phases!r}"
        )
    if any(document.get("schema") != IDENTITY_SCHEMA for document in documents):
        raise GapStockRtlIdentityError("server identity schema differs")

    install_names = {
        document.get("test_package", {}).get("install_name")
        for document in documents
    }
    manifest_hashes = {
        document.get("test_package", {})
        .get("manifest", {})
        .get("sha256")
        for document in documents
    }
    server_commands = {document.get("server_command") for document in documents}
    if len(install_names) != 1 or None in install_names:
        raise GapStockRtlIdentityError("install identity is not stable")
    if len(manifest_hashes) != 1 or None in manifest_hashes:
        raise GapStockRtlIdentityError("test-package manifest identity is not stable")
    if len(server_commands) != 1 or None in server_commands:
        raise GapStockRtlIdentityError("server command identity is not stable")

    rtl_tree_hashes = [
        document.get("rtl_tree", {}).get("tree_sha256")
        for document in documents
    ]
    rtl_tree_stable = (
        all(value is not None for value in rtl_tree_hashes)
        and len(set(rtl_tree_hashes)) == 1
    )

    focus_maps = [
        document.get("artifacts", {}).get("focus_rtl_files", {})
        for document in documents
    ]
    focus_key_sets = [set(mapping) for mapping in focus_maps]
    if any(not isinstance(mapping, dict) for mapping in focus_maps):
        raise GapStockRtlIdentityError("focused RTL identity is malformed")
    if len({frozenset(keys) for keys in focus_key_sets}) != 1:
        raise GapStockRtlIdentityError("focused RTL file set changed between phases")
    focus_keys = focus_key_sets[0]
    if not REQUIRED_FOCUS_RTL.issubset(focus_keys):
        missing = sorted(REQUIRED_FOCUS_RTL - focus_keys)
        raise GapStockRtlIdentityError(
            f"required GAP RTL focus files are missing: {missing}"
        )

    focus_results: dict[str, dict[str, Any]] = {}
    for relative in sorted(focus_keys):
        fingerprints = [
            _file_fingerprint(mapping[relative]) for mapping in focus_maps
        ]
        stable = (
            all(fingerprint[0] is True for fingerprint in fingerprints)
            and all(fingerprint[2] is not None for fingerprint in fingerprints)
            and len(set(fingerprints)) == 1
        )
        focus_results[relative] = {
            "stable": stable,
            "fingerprint": {
                "exists": fingerprints[0][0],
                "size_bytes": fingerprints[0][1],
                "sha256": fingerprints[0][2],
                "canonical_text_sha256": fingerprints[0][3],
            },
        }
    all_focus_stable = all(item["stable"] for item in focus_results.values())

    artifact_results: dict[str, dict[str, Any]] = {}
    for name in STABLE_ARTIFACTS:
        fingerprints = [
            _plain_file_fingerprint(document.get("artifacts", {}).get(name, {}))
            for document in documents
        ]
        stable = (
            all(fingerprint[0] is True for fingerprint in fingerprints)
            and all(fingerprint[2] is not None for fingerprint in fingerprints)
            and len(set(fingerprints)) == 1
        )
        artifact_results[name] = {
            "stable": stable,
            "sha256": fingerprints[0][2],
        }
    stable_support_files = all(
        item["stable"] for item in artifact_results.values()
    )

    post_prepare_testbench_fingerprints = [
        _plain_file_fingerprint(
            document.get("artifacts", {}).get("testbench", {})
        )
        for document in documents[1:]
    ]
    testbench_stable_after_prepare = (
        all(
            fingerprint[0] is True
            for fingerprint in post_prepare_testbench_fingerprints
        )
        and len(set(post_prepare_testbench_fingerprints)) == 1
    )

    stable = (
        rtl_tree_stable
        and all_focus_stable
        and stable_support_files
        and testbench_stable_after_prepare
    )
    return {
        "schema": SCHEMA,
        "status": "rtl_unchanged" if stable else "rtl_identity_changed",
        "install_name": next(iter(install_names)),
        "functional_rtl_mode": "server_original_unmodified",
        "functional_rtl_write_requested": False,
        "functional_rtl_patch_included": False,
        "restore_required": False,
        "post_restore_phase_semantics": (
            "final_identity_capture_after_noop_rtl_action"
        ),
        "identity_phases": list(EXPECTED_PHASES),
        "test_package_manifest_sha256": next(iter(manifest_hashes)),
        "server_command": next(iter(server_commands)),
        "rtl_tree": {
            "stable": rtl_tree_stable,
            "sha256": rtl_tree_hashes[0],
            "phase_hashes": dict(zip(EXPECTED_PHASES, rtl_tree_hashes)),
        },
        "focused_rtl": {
            "stable": all_focus_stable,
            "required_gap_files": sorted(REQUIRED_FOCUS_RTL),
            "files": focus_results,
        },
        "support_files": artifact_results,
        "testbench_stable_after_observer_prepare": (
            testbench_stable_after_prepare
        ),
        "functional_rtl_unchanged": stable,
        "absolute_server_local_or_github_match_required": False,
        "release_claim": {
            "candidate_release": False,
            "evidence_level": "SERVER_RECEIPT_ONLY",
            "numeric_and_ga_dynamic_gates_still_required": True,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-install", type=Path, required=True)
    parser.add_argument("--post-install", type=Path, required=True)
    parser.add_argument("--post-run", type=Path, required=True)
    parser.add_argument("--post-restore", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        report = build_receipt(
            [
                args.pre_install,
                args.post_install,
                args.post_run,
                args.post_restore,
            ]
        )
    except Exception as error:
        print(f"GAP stock RTL identity verification failed: {error}", file=sys.stderr)
        return 1
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return 0 if report["functional_rtl_unchanged"] else 6


if __name__ == "__main__":
    raise SystemExit(main())
