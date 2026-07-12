from __future__ import annotations

from copy import deepcopy
from typing import Any

from resnet50_pipeline.hardware_approval import PROFILE_LAYOUTS


def valid_hardware_approval(profile: str = "batch") -> dict[str, Any]:
    physical_object = {
        "owner": "slice-local SRAM",
        "axis_order": "NCHW",
        "alignment_bytes": 16,
        "tail_rule": "mask inactive lanes",
        "address_unit": "byte",
    }
    return {
        "schema_version": "0.1",
        "contract_type": "hardware_approval",
        "status": "approved",
        "approval_id": "example-hardware-approval-for-tests",
        "authority": {
            "name": "Hardware Owner",
            "organization": "Test Organization",
            "approved_at": "2026-07-12",
        },
        "target_version": {
            "rtl_commit": "0123456789abcdef0123456789abcdef01234567",
            "isa_version": "isa-test-v1",
            "register_map_version": "regmap-test-v1",
        },
        "architecture": {
            "slice_count": 16,
            "pe_array": {"rows": 8, "cols": 8},
            "neighbor_transfer_count": 2,
            "dram": {
                "bank_count": 16,
                "row_count": 16384,
                "col_count": 1024,
                "subword_bytes": 16,
                "address_unit": "byte",
                "address_order": "bank,row,col,subword",
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
            "qparams_transport": "configuration registers",
            "psum_lifecycle": "slice-local until output requantization",
        },
        "isa": {
            "opcodes": {"load": 1, "compute": 2, "store": 3},
            "field_widths": {"opcode": 8, "address": 32, "mask": 16},
            "instruction_mask_semantics": "one bit per active slice",
        },
        "runtime_protocol": {
            "load_config": "write configuration registers",
            "load_data": "DMA source tensors",
            "start": "write start bit",
            "wait": "poll completion bit",
            "status": "read status register",
            "error": "read sticky error register",
            "dump": "DMA requested output buffers",
        },
        "evidence": [
            {
                "uri": "rtl://test-target/commit/0123456789abcdef0123456789abcdef01234567",
                "sha256": "a" * 64,
            }
        ],
    }
