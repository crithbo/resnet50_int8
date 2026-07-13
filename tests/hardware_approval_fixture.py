from __future__ import annotations

from copy import deepcopy
from typing import Any

from resnet50_pipeline.hardware_approval import (
    PROFILE_LAYOUTS,
    TARGET_ARCHITECTURE_ID,
    TARGET_ARCHITECTURE_SCHEMA_VERSION,
    TARGET_FILELIST,
    TARGET_RTL_COMMIT,
    TARGET_RTL_REPOSITORY,
    TARGET_TOPOLOGY_ID,
    TARGET_TOP_MODULE,
)
from resnet50_pipeline.profile28 import GROUP4X7_BATCH_CHANNEL28_PROFILE


def valid_hardware_approval(
    profile: str = GROUP4X7_BATCH_CHANNEL28_PROFILE,
) -> dict[str, Any]:
    """Return structurally valid synthetic RTL28 approval data for negative gate tests.

    The fixture proves schema/validator behavior only.  Its planned layout IDs and
    synthetic evidence never make it current-gate eligible.
    """

    physical_object = {
        "owner": "slice-local SRAM",
        "axis_order": "NCHW",
        "alignment_bytes": 16,
        "tail_rule": "mask inactive lanes",
        "address_unit": "byte",
    }
    return {
        "schema_version": "0.2",
        "contract_type": "hardware_approval",
        "status": "approved",
        "approval_id": "synthetic-rtl28-approval-for-structure-tests-only",
        "authority": {
            "name": "Hardware Owner",
            "organization": "Test Organization",
            "approved_at": "2026-07-13",
        },
        "target_version": {
            "repository": TARGET_RTL_REPOSITORY,
            "rtl_commit": TARGET_RTL_COMMIT,
            "top_module": TARGET_TOP_MODULE,
            "filelist": TARGET_FILELIST,
            "architecture_id": TARGET_ARCHITECTURE_ID,
            "architecture_schema_version": TARGET_ARCHITECTURE_SCHEMA_VERSION,
            "isa_version": "trassic2-command64-test-v1",
            "register_map_version": "trassic2-regmap-test-v1",
        },
        "clean_elaboration": {
            "status": "approved",
            "tool": "synthetic-test-elaborator",
            "tool_version": "0.0-test",
            "log_uri": "fixture://clean-elaboration.log",
            "log_sha256": "e" * 64,
        },
        "architecture": {
            "target_family": "rtl28",
            "slice_count": 28,
            "topology_id": TARGET_TOPOLOGY_ID,
            "specialized_array": {"rows": 8, "cols": 8},
            "general_array": {"rows": 4, "cols": 4},
            "instruction_mask_bits": 28,
            "dram": {
                "bank_count": 4,
                "row_count": 6144,
                "col_count": 64,
                "subword_bytes": 16,
                "address_unit": "byte",
                "address_order": "slice_owner, local_bank, row, column, byte_offset",
            },
        },
        "network_profile": profile,
        "operator_layouts": deepcopy(PROFILE_LAYOUTS[profile]),
        "physical_objects": {
            name: deepcopy(physical_object)
            for name in ("activation", "weight", "bias", "qparams", "psum", "output")
        },
        "numeric_semantics": {
            "accumulator_bits": 32,
            "overflow": "saturate",
            "requant": {
                "multiplier_encoding": "signed fixed-point multiplier plus shift",
                "rounding": "nearest_even",
                "saturation": "uint8",
                "zero_point_stage": "after rounding before saturation",
            },
            "qparams_transport": "configuration registers and/or constant streams",
            "psum_lifecycle": "slice-local until output requantization",
        },
        "isa": {
            "opcodes": {"CFG": 0, "CKEN": 1, "WREG": 4, "CMPT": 5, "BARR": 6, "RST": 7},
            "field_widths": {
                "command": 64,
                "slice_mask": 28,
                "wreg_slice_id": 5,
                "wreg_address": 14,
                "wreg_data": 32,
            },
            "instruction_mask_semantics": "one bit per physical slice in bits [30:3]",
        },
        "runtime_protocol": {
            "load_config": "load 128-bit execution beats and referenced 64-bit CFG words",
            "load_data": "host AXI writes to approved logical DRAM addresses",
            "start": "write global_sca_start after base and execution length",
            "wait": "poll fetch finish and intended exec_slice_finish mask",
            "status": "read global status register",
            "error": "check overflow, timeout and approved sticky error sources",
            "dump": "read approved output ranges after completion fence",
        },
        "evidence": [
            {
                "kind": "clean_elaboration",
                "uri": "fixture://clean-elaboration.log",
                "sha256": "e" * 64,
            },
            {
                "kind": "architecture",
                "uri": f"rtl://Trassic2.0_RTL/commit/{TARGET_RTL_COMMIT}",
                "sha256": "a" * 64,
            },
            {
                "kind": "physical_layout",
                "uri": "fixture://rtl28-layout-approval.json",
                "sha256": "b" * 64,
            },
            {
                "kind": "runtime_protocol",
                "uri": "fixture://rtl28-runtime-protocol.md",
                "sha256": "c" * 64,
            },
        ],
    }
