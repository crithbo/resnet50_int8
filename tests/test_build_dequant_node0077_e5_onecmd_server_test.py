from __future__ import annotations

import json
from pathlib import Path

from tools import build_dequant_node0077_e5_onecmd_server_test as builder
from tools.dequant_node0077_server_runtime import preflight_package


def test_e5_authority_and_frozen_e4_identity() -> None:
    manifest, records = builder._verify_e4_source()
    assert manifest["status"] == "E4_ONE_COMMAND_PACKAGE_READY"
    assert manifest["payload_tree_sha256"] == builder.E4_PAYLOAD_TREE_SHA256
    assert len(records) == 82
    receipt = builder._read_receipt()
    read_paths = {
        item["path"]
        for group in ("mandatory_files", "actual_consumers")
        for item in receipt[group]
    }
    assert builder.E4_RETURN_ANALYSIS.relative_to(builder.ROOT).as_posix() in read_paths
    assert builder.E4_PASS_RECORD.relative_to(builder.ROOT).as_posix() in read_paths
    assert "tools/build_dequant_node0077_e5_onecmd_server_test.py" in read_paths
    assert "tools/dequant_node0077_server_runtime.py" in read_paths


def test_e5_derivation_freezes_workload_and_sets_repeat_gate(
    tmp_path: Path,
) -> None:
    package = tmp_path / builder.INSTALL_NAME
    report = builder._derive_tree(package)
    assert report["frozen_workload_gate"]["status"] == "pass"
    assert report["frozen_workload_gate"]["formal_d_total_128bit_lines"] == 5264
    manifest = json.loads(
        (package / "TEST_PACKAGE_MANIFEST.json").read_text(encoding="utf-8")
    )
    assert manifest["dynamic_run_gate"] == "E5"
    assert manifest["candidate_release"] is False
    assert manifest["remaining_blockers"] == ["B_DEQUANT_SERVER_E5"]
    preflight = preflight_package(package, builder.INSTALL_NAME)
    assert preflight["dynamic_run_gate"] == "E5"
    assert preflight["evidence_level"] == "E4_SERVER_FORMAL_PASS_E5_NOT_RUN"


def test_existing_e4_preflight_boundary_is_unchanged() -> None:
    report = preflight_package(builder.E4_PACKAGE, builder.E4_INSTALL_NAME)
    assert report["dynamic_run_gate"] == "E4"
    assert report["evidence_level"] == "E2_LOCAL_ONLY"
