from __future__ import annotations

from copy import deepcopy
from typing import Any

from resnet50_pipeline.hardware_approval import (
    APPROVAL_CONTRACT_TYPE,
    APPROVAL_SCHEMA_VERSION,
    APPROVAL_SCOPE,
    EXPECTED_CONTRACT_LAYERS,
    PROFILE_BINDINGS,
    REQUIRED_W5_DEFERRALS,
    TARGET_ARCHITECTURE_ID,
    TARGET_ARCHITECTURE_SCHEMA_VERSION,
    TARGET_CONFIG_COMMIT,
    TARGET_CONFIG_REPOSITORY,
    TARGET_DRAM,
    TARGET_FILELIST,
    TARGET_ISA_VERSION,
    TARGET_REGISTER_MAP_VERSION,
    TARGET_RTL_COMMIT,
    TARGET_RTL_REPOSITORY,
    TARGET_TOPOLOGY_ID,
    TARGET_TOP_MODULE,
)
from resnet50_pipeline.profile28 import DEEPSEEK_HYBRID28_PROFILE


def valid_hardware_approval() -> dict[str, Any]:
    """Return a structurally valid synthetic W4 approval for negative gate tests."""

    return {
        "schema_version": APPROVAL_SCHEMA_VERSION,
        "contract_type": APPROVAL_CONTRACT_TYPE,
        "status": "approved",
        "approval_scope": APPROVAL_SCOPE,
        "approval_id": "synthetic-rtl28-approval-for-structure-tests-only",
        "authority": {
            "kind": "synthetic_fixture",
            "authority_id": "unit_test_fixture",
            "role": "validator test only",
            "recorded_at": "2026-07-14",
        },
        "target_version": {
            "repository": TARGET_RTL_REPOSITORY,
            "rtl_commit": TARGET_RTL_COMMIT,
            "top_module": TARGET_TOP_MODULE,
            "filelist": TARGET_FILELIST,
            "architecture_id": TARGET_ARCHITECTURE_ID,
            "architecture_schema_version": TARGET_ARCHITECTURE_SCHEMA_VERSION,
            "isa_version": TARGET_ISA_VERSION,
            "register_map_version": TARGET_REGISTER_MAP_VERSION,
            "config_repository": TARGET_CONFIG_REPOSITORY,
            "config_commit": TARGET_CONFIG_COMMIT,
        },
        "baseline_confirmation": {
            "status": "operator_confirmed_known_good",
            "basis": "operator_statement_and_completed_deepseek_bringup",
            "inherited_project": "deepseek_full_network",
            "elaboration_log_claimed": False,
            "decision_uri": ".agents/decisions/synthetic.md",
            "decision_sha256": "d" * 64,
        },
        "architecture": {
            "target_family": "rtl28",
            "slice_count": 28,
            "topology_id": TARGET_TOPOLOGY_ID,
            "specialized_array": {"rows": 8, "cols": 8},
            "general_array": {"rows": 4, "cols": 4},
            "instruction_mask_bits": 28,
            "dram": deepcopy(TARGET_DRAM),
        },
        "network_profile": DEEPSEEK_HYBRID28_PROFILE,
        "operator_bindings": deepcopy(PROFILE_BINDINGS[DEEPSEEK_HYBRID28_PROFILE]),
        "contract_layers": {
            name: {**deepcopy(identity), "sha256": character * 64}
            for (name, identity), character in zip(
                EXPECTED_CONTRACT_LAYERS.items(), ("a", "b"), strict=True
            )
        },
        "deferred_to_w5": sorted(REQUIRED_W5_DEFERRALS),
        "evidence": [
            {
                "kind": "synthetic_structure_fixture",
                "uri": "fixture://w4-approval.json",
                "sha256": "c" * 64,
            }
        ],
    }
