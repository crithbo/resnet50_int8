#!/usr/bin/env python3
"""Build the frozen Requant node0001 capture-edge SFU numeric diagnostic."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_requant_atomic_onecmd_server_test as base  # noqa: E402


INSTALL_NAME = "rq_node0001_guardonly_sfu_numeric_stock_v1"
DEFAULT_OUTPUT = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / INSTALL_NAME
)
VALIDATION_RECEIPT = DEFAULT_OUTPUT.with_name(f"{INSTALL_NAME}_validation.json")
FROZEN_ATOMIC_PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "rq_node0001_atomic2_stock_v2"
)
FROZEN_ATOMIC_ZIP = FROZEN_ATOMIC_PACKAGE.with_suffix(".zip")
FROZEN_ATOMIC_ZIP_SHA256 = (
    "69a264f4ffca02120f662f1b5749f1a66819f7294bb8af497aa617336cb4e93c"
)
FROZEN_CONFIG_ROOT = (
    ROOT
    / "configs/native_ndp_sim/node0001_requant_single_occurrence_two_stage_v2"
)
PREDECESSOR_PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages"
    / "rq_node0001_guardonly_sfu_ready_stock_v1"
)
PREDECESSOR_PACKAGE_ZIP_SHA256 = (
    "8cb224163271e0ed9166831bf434c88ce10e1f76ed78a42344724f8b5126c2ac"
)
READ_RECEIPT = (
    ROOT
    / ".agents/task_records/"
    "20260727_requant_guardonly_sfu_numeric_v1_read_receipt.json"
)
AUTHORITATIVE_PREDECESSOR_ANALYSIS = (
    ROOT
    / "server_returns/"
    "rq_node0001_guardonly_sfu_ready_stock_v1_return_analysis_20260727.json"
)
AUTHORITATIVE_PREDECESSOR_ANALYSIS_SHA256 = (
    "47f91b2cb25b2e81e1385b35fe0cc6739709717c69a22f3b383bfbbf81be584a"
)
REQUANT_RULE = ROOT / ".agents/rules/RequantizeUint8算子配置规则.md"
REQUANT_RULE_SHA256 = (
    "5f7bc1fc7087d3aafce0b74982588df9c68abeea583a7ea501c87031c3ef9e52"
)
SERVER_RULE = ROOT / ".agents/rules/服务器测试包生成规则.md"
SERVER_RULE_SHA256 = (
    "0fec7a4f72246c9e802fb2e91e972c2f636e2721aaeef1194c2d4d3fba103fbc"
)
MANDATORY_IDENTITIES = (
    (
        "agent entry",
        ROOT / ".agents/agent.md",
        "367f4f4260246d40531d83cc6d24fe94946cb05bce6fbef18c428f05b634c083",
    ),
    (
        "active plan",
        ROOT / ".agents/plan.md",
        "a9f0c3397dad32473f542c82852bef9d244535ca40abdb688623aa3c47f14354",
    ),
    (
        "mandatory-read index",
        ROOT / ".agents/rules/生成前必读索引.md",
        "539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7",
    ),
    (
        "hardware simulation entry",
        ROOT / "NDP_copy01/README_HARDWARE_SIM_ENTRY.md",
        "4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7",
    ),
)
# The transactional installer is an actual package consumer and requires this
# exact basename. A different profile filename caused the frozen v1 package to
# fail before compile.
OBSERVER_TAIL_NAME = "requant_mse4_guard_observer_tail.svh"
ENCODER_GENERAL = (
    ROOT / "ndp-sim-ref/bitstream/config/general.py"
)
ENCODER_GENERAL_EQUIVALENT = (
    ROOT / "native_ring4_repro_20260722/bitstream/config/general.py"
)


class GuardOnlyPackageError(RuntimeError):
    """Raised when the guard-only diagnostic cannot be built deterministically."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _write_json(path: Path, value: Any) -> None:
    base._write_json(path, value)


def _verify_frozen_sources() -> dict[str, Any]:
    if not FROZEN_ATOMIC_PACKAGE.is_dir() or not FROZEN_ATOMIC_ZIP.is_file():
        raise GuardOnlyPackageError("frozen atomic v2 package is missing")
    if _sha256(FROZEN_ATOMIC_ZIP) != FROZEN_ATOMIC_ZIP_SHA256:
        raise GuardOnlyPackageError("frozen atomic v2 ZIP identity differs")
    frozen_manifest = json.loads(
        (FROZEN_ATOMIC_PACKAGE / base.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    if frozen_manifest.get("files") != base._records(
        FROZEN_ATOMIC_PACKAGE, exclude_manifest=True
    ):
        raise GuardOnlyPackageError("frozen atomic v2 package exact set differs")
    identities = {
        "guard_json": (
            FROZEN_CONFIG_ROOT / "guard.json",
            "defeca56b0c248eb1f4915b0338227580687d4e8c92cedf548ad727f6457d5d2",
        ),
        "input_slice00": (
            FROZEN_CONFIG_ROOT / "input_int32_slice00_128b.txt",
            "35f9442ac0cc2a4bfcaaa70e60c83a64845093f98c9c5794abf83fbdaa70bf77",
        ),
        "input_slice01": (
            FROZEN_CONFIG_ROOT / "input_int32_slice01_128b.txt",
            "656e340be25e5862c514d9efd94c64557afe61b10f0d9b1655d6ed1921315714",
        ),
        "guard_golden_slice00": (
            FROZEN_CONFIG_ROOT / "guard_golden_slice00_128b.txt",
            "e9bd06473f6a24efb409725ef938f32c432f39f7db9235c7a080bb561567b85a",
        ),
        "guard_golden_slice01": (
            FROZEN_CONFIG_ROOT / "guard_golden_slice01_128b.txt",
            "3eedd8ed23cd98a973f32c9763a577dfa42978416544aa8ba72dc6be8cf4a2f2",
        ),
        "requant_guard": (
            FROZEN_CONFIG_ROOT / "RequantGuard.txt",
            "19bfa9a258d3199d5280f3829e3a54dd7d06c4d95294f5b419246e5eb8eebf57",
        ),
    }
    result: dict[str, Any] = {}
    for name, (path, expected) in identities.items():
        actual = _sha256(path)
        if actual != expected:
            raise GuardOnlyPackageError(
                f"frozen source identity differs: {name}: {actual}"
            )
        result[name] = {
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": actual,
        }
    guard_native = (
        FROZEN_ATOMIC_PACKAGE / "validation/native/op_w0_s00_guard"
    )
    result["guard_native_tree"] = {
        "source": guard_native.relative_to(ROOT).as_posix(),
        "files": base._records(guard_native),
        "tree_sha256": base._tree_sha256(base._records(guard_native)),
    }
    result["frozen_atomic_package"] = {
        "path": FROZEN_ATOMIC_ZIP.relative_to(ROOT).as_posix(),
        "sha256": FROZEN_ATOMIC_ZIP_SHA256,
        "manifest_sha256": _sha256(
            FROZEN_ATOMIC_PACKAGE / base.MANIFEST_NAME
        ),
    }
    predecessor_zip = PREDECESSOR_PACKAGE.with_suffix(".zip")
    if (
        not PREDECESSOR_PACKAGE.is_dir()
        or not predecessor_zip.is_file()
        or _sha256(predecessor_zip) != PREDECESSOR_PACKAGE_ZIP_SHA256
    ):
        raise GuardOnlyPackageError("frozen guard-only predecessor differs")
    if not READ_RECEIPT.is_file():
        raise GuardOnlyPackageError("mandatory-read receipt is missing")
    for label, path, expected in (
        (
            "authoritative predecessor return analysis",
            AUTHORITATIVE_PREDECESSOR_ANALYSIS,
            AUTHORITATIVE_PREDECESSOR_ANALYSIS_SHA256,
        ),
        ("Requant rule", REQUANT_RULE, REQUANT_RULE_SHA256),
        ("server package rule", SERVER_RULE, SERVER_RULE_SHA256),
        *MANDATORY_IDENTITIES,
    ):
        if not path.is_file() or _sha256(path) != expected:
            raise GuardOnlyPackageError(f"{label} identity differs")
    result["frozen_guard_only_predecessor"] = {
        "path": predecessor_zip.relative_to(ROOT).as_posix(),
        "sha256": PREDECESSOR_PACKAGE_ZIP_SHA256,
    }
    result["mandatory_read_receipt"] = {
        "path": READ_RECEIPT.relative_to(ROOT).as_posix(),
        "sha256": _sha256(READ_RECEIPT),
    }
    result["authoritative_predecessor_return_analysis"] = {
        "path": AUTHORITATIVE_PREDECESSOR_ANALYSIS.relative_to(ROOT).as_posix(),
        "sha256": AUTHORITATIVE_PREDECESSOR_ANALYSIS_SHA256,
    }
    result["requant_rule"] = {
        "path": REQUANT_RULE.relative_to(ROOT).as_posix(),
        "sha256": REQUANT_RULE_SHA256,
    }
    result["server_package_rule"] = {
        "path": SERVER_RULE.relative_to(ROOT).as_posix(),
        "sha256": SERVER_RULE_SHA256,
    }
    result["mandatory_identities"] = {
        label: {
            "path": path.relative_to(ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": expected,
        }
        for label, path, expected in MANDATORY_IDENTITIES
    }
    return result


def _is_frozen_guard_semantic_payload(relative: str) -> bool:
    if relative.startswith("golden/"):
        return True
    if relative.startswith("validation/native/"):
        return True
    if relative.startswith("workload/runtime/payloads/"):
        return True
    return relative in {
        "validation/address_domain_contract.json",
        "validation/expected_mse4_writes.json",
        "validation/generation_receipt.json",
        "validation/guard.json",
        "validation/lifecycle_contract.json",
        "validation/local_contract_report.json",
        "validation/manifest.json",
        "validation/semantic_contract.json",
        "workload/runtime/sca_cfg_D.json",
    }


def _normalize_install_identity(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _normalize_install_identity(item)
            for key, item in sorted(value.items())
        }
    if isinstance(value, list):
        return [_normalize_install_identity(item) for item in value]
    if isinstance(value, str):
        for install_name in (PREDECESSOR_PACKAGE.name, INSTALL_NAME):
            value = value.replace(install_name, "<INSTALL_IDENTITY>")
        return value
    return value


def _semantic_freeze_receipt(package: Path) -> dict[str, Any]:
    predecessor_manifest = json.loads(
        (PREDECESSOR_PACKAGE / base.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    if predecessor_manifest.get("files") != base._records(
        PREDECESSOR_PACKAGE, exclude_manifest=True
    ):
        raise GuardOnlyPackageError("guard-only predecessor exact set differs")
    predecessor_records = {
        relative: identity
        for relative, identity in base._records(PREDECESSOR_PACKAGE).items()
        if _is_frozen_guard_semantic_payload(relative)
    }
    successor_records = {
        relative: identity
        for relative, identity in base._records(package).items()
        if _is_frozen_guard_semantic_payload(relative)
    }
    if predecessor_records != successor_records:
        differing = sorted(set(predecessor_records) ^ set(successor_records))
        differing.extend(
            relative
            for relative in sorted(set(predecessor_records) & set(successor_records))
            if predecessor_records[relative] != successor_records[relative]
        )
        raise GuardOnlyPackageError(
            f"guard semantic payload differs from frozen v4: {differing[:8]}"
        )
    predecessor_sca = json.loads(
        (
            PREDECESSOR_PACKAGE / "workload/runtime/sca_cfg.json"
        ).read_text(encoding="utf-8")
    )
    successor_sca = json.loads(
        (package / "workload/runtime/sca_cfg.json").read_text(encoding="utf-8")
    )
    if _normalize_install_identity(predecessor_sca) != _normalize_install_identity(
        successor_sca
    ):
        raise GuardOnlyPackageError(
            "guard SCA differs beyond the unique install namespace"
        )
    return {
        "schema": "requant-guard-only-sfu-ready-to-numeric-v1-semantic-freeze-v1",
        "status": "pass",
        "predecessor": PREDECESSOR_PACKAGE.relative_to(ROOT).as_posix(),
        "predecessor_zip_sha256": PREDECESSOR_PACKAGE_ZIP_SHA256,
        "semantic_payload_file_count": len(successor_records),
        "semantic_payload_tree_sha256": base._tree_sha256(successor_records),
        "semantic_payload_byte_identical": True,
        "sca_normalized_equal": True,
        "allowed_changes": [
            "unique install/run/return identity",
            "capture-edge-safe SFU numeric observer/runtime/validator evidence coverage",
            "receipts and manifest"
        ],
        "semantic_change": False,
    }


def _guard_execplan() -> str:
    path = (
        FROZEN_ATOMIC_PACKAGE
        / "workload/runtime/payloads/execplan.txt"
    )
    lines = [line.strip() for line in path.read_text(encoding="ascii").splitlines()]
    words: list[int] = []
    for line in lines:
        if len(line) != 128 or set(line) - {"0", "1"}:
            raise GuardOnlyPackageError("frozen execplan is not strict 128-bit text")
        words.extend((int(line[64:], 2), int(line[:64], 2)))
    if words[-1] == 0:
        words.pop()
    guard_words = words[:7]
    if (
        len(guard_words) != 7
        or (guard_words[-2] & 0x7) != 0b101
        or (guard_words[-1] & 0x7) != 0b110
    ):
        raise GuardOnlyPackageError("frozen guard execplan prefix differs")
    packed: list[str] = []
    for index in range(0, len(guard_words), 2):
        low = guard_words[index]
        high = guard_words[index + 1] if index + 1 < len(guard_words) else 0
        packed.append(f"{high:064b}{low:064b}")
    return "\n".join(packed) + "\n"


def _guard_expected_writes() -> dict[str, Any]:
    source = json.loads(
        (
            FROZEN_ATOMIC_PACKAGE
            / "validation/expected_mse4_writes.json"
        ).read_text(encoding="utf-8")
    )
    stages = [stage for stage in source["stages"] if stage["role"] == "guard"]
    if len(stages) != 1 or len(stages[0]["writes"]) != 16:
        raise GuardOnlyPackageError("frozen guard accepted-write set differs")
    return {
        "schema": "requant-guard-only-mse4-write-contract-v1",
        "active_slices": [0, 1],
        "physical_engine": "MSE4_WRITE_STREAM0",
        "address_domains": {
            "word_address_128b": (
                "linear/pre-remap transfer_addr_nooff plus stream base"
            ),
            "transfer_addr_nooff": "pre-remap transfer offset without stream base",
            "post_remap_request_address": (
                "accepted local_req_addr after mse_map_matrix_b"
            ),
            "comparison_rule": (
                "only compare expected word_address_128b with observed "
                "linear_addr; retain post-remap address as separate evidence"
            ),
        },
        "duplicate_or_extra_write_allowed": False,
        "stages": stages,
        "total_expected_accepted_write_count": 16,
    }


def _lifecycle_contract() -> dict[str, Any]:
    return {
        "schema": "requant-node0001-guard-only-lifecycle-v1",
        "logical_occurrence_count": 1,
        "physical_slice_instance_count": 2,
        "active_slices": [0, 1],
        "slice_mask": "0b0000000000000000000000000011",
        "stage_count": 1,
        "repeat_num": 1,
        "stage_sequence": [
            {
                "stage_index": 0,
                "role": "guard",
                "input_base_addr": "0x00000000",
                "output_base_addr": "0x00800000",
                "input_dtype": "int32",
                "output_dtype": "fp32",
                "expected_mse4_accepted_write_beats_per_slice": 8,
                "expected_mse4_accepted_write_beats_total": 16,
            }
        ],
        "stock_tb_completion_observer": {
            "start_sampled_slice": 0,
            "finish_sampled_slice": 1,
            "mask_aware": False,
            "required_sampled_slices_enabled": True,
            "tb_or_rtl_modification_authorized": False,
        },
        "dynamic_acceptance": {
            "stage_start_group_count": 1,
            "stage_comp_finish_group_count": 1,
            "per_slice_start_event_count": 2,
            "per_slice_comp_finish_event_count": 2,
            "mse4_total_accepted_write_beat_count": 16,
            "natural_completion_required": True,
        },
    }


def _diagnostic_profile() -> dict[str, Any]:
    return {
        "schema": "requant-node0001-guard-only-sfu-numeric-runtime-profile-v1",
        "mode": "guard_only",
        "diagnostic_submode": "sfu_numeric_capture_edge",
        "stage_count": 1,
        "exec_lines": 4,
        "exec_word_count": 7,
        "preload_count": 5,
        "formal_readback_count": 2,
        "expected_write_count": 16,
        "observer_plusarg": "REQUANT_GUARD_SFU_NUMERIC_PROBE",
        "observer_log_dir": "requant_guard_sfu_numeric_probe",
        "observer_tail": OBSERVER_TAIL_NAME,
        "capture_edge_safe": True,
        "checkpoint_expected_counts": {
            "PE_SELECTED_INPUT": 64,
            "SFU_PREPROCESS_INPUT_CAPTURE": 64,
            "SFU_BST_RESULT_CAPTURE": 64,
            "SFU_COEFF_CAPTURE": 64,
            "SFU_ALU_INPUT_CAPTURE": 64,
            "SFU_ALU_RESULT_ACCEPTED": 64,
            "SFU_POSTPROCESS_RESULT_ACCEPTED": 64,
            "NORMAL_OUTBUFFER_INPUT_ACCEPTED": 64,
            "NORMAL_OUTBUFFER_WRITE_COMMIT": 64,
            "NORMAL_OUTPORT_ACCEPTED": 64,
            "MSE4_REQ": 16,
            "MSE4_WDATA": 16,
        },
        "checkpoint_observation_only": [],
        "checkpoint_order": [
            "PE_SELECTED_INPUT",
            "SFU_PREPROCESS_INPUT_CAPTURE",
            "SFU_BST_RESULT_CAPTURE",
            "SFU_COEFF_CAPTURE",
            "SFU_ALU_INPUT_CAPTURE",
            "SFU_ALU_RESULT_ACCEPTED",
            "SFU_POSTPROCESS_RESULT_ACCEPTED",
            "NORMAL_OUTBUFFER_INPUT_ACCEPTED",
            "NORMAL_OUTBUFFER_WRITE_COMMIT",
            "NORMAL_OUTPORT_ACCEPTED",
            "MSE4_WDATA",
        ],
        "last_good_input_checkpoint": "SFU_PREPROCESS0_VALID",
        "wide_direct_signal_replay": False,
        "status_summary_mislabeled_as_data_forbidden": True,
    }


def _static_configuration_intent() -> dict[str, Any]:
    guard_path = FROZEN_CONFIG_ROOT / "guard.json"
    dump_path = (
        FROZEN_ATOMIC_PACKAGE
        / "validation/native/op_w0_s00_guard/detailed_dump.txt"
    )
    guard = json.loads(guard_path.read_text(encoding="utf-8"))
    json_value = guard["general_array"]["inport"]["inport0"]["int32tofp32"]
    odd_pe_opcodes = {
        name: value["alu_opcode"]
        for name, value in guard["general_array"]["PE_array"].items()
        if int(name[-1]) % 2 == 1
    }
    encoder_text = ENCODER_GENERAL.read_text(encoding="utf-8")
    encoder_equivalent_text = ENCODER_GENERAL_EQUIVALENT.read_text(
        encoding="utf-8"
    )
    encoder_match = re.search(
        r'(?m)^\s*"sfu_activation":\s*24,\s*$',
        encoder_text,
    )
    dump_text = dump_path.read_text(encoding="utf-8")
    dump_match = re.search(
        r"(?m)^int32tofp32\s+\|\s+value=true\s+\|\s+encoded=\['1'\]\s*$",
        dump_text,
    )
    dump_opcode_matches = re.findall(
        r"(?m)^alu_opcode\s+\|\s+value=sfu_activation\s+"
        r"\|\s+encoded=\['11000'\]\s*$",
        dump_text,
    )
    if (
        json_value != "true"
        or set(odd_pe_opcodes.values()) != {"sfu_activation"}
        or len(odd_pe_opcodes) != 8
        or encoder_match is None
        or encoder_text != encoder_equivalent_text
        or _sha256(ENCODER_GENERAL) != _sha256(ENCODER_GENERAL_EQUIVALENT)
        or dump_match is None
        or len(dump_opcode_matches) != 8
    ):
        raise GuardOnlyPackageError(
            "frozen guard JSON/encoder/parsed bitstream intent differs"
        )
    return {
        "schema": "requant-guard-static-sfu-activation-intent-v2",
        "status": "pass",
        "guard_json": {
            "path": guard_path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(guard_path),
            "field": "general_array.inport.inport0.int32tofp32",
            "value": json_value,
        },
        "parsed_bitstream_evidence": {
            "path": dump_path.relative_to(ROOT).as_posix(),
            "sha256": _sha256(dump_path),
            "decoded_field": "GAInportConfig.int32tofp32",
            "decoded_value": True,
            "encoded_bit": 1,
        },
        "sfu_activation_opcode": {
            "json_odd_pe_count": len(odd_pe_opcodes),
            "json_odd_pe_values": odd_pe_opcodes,
            "encoder_general": {
                "path": ENCODER_GENERAL.relative_to(ROOT).as_posix(),
                "sha256": _sha256(ENCODER_GENERAL),
                "symbol": "sfu_activation",
                "decimal": 24,
                "hex": "0x18",
            },
            "encoder_general_equivalent_copy": {
                "path": (
                    ENCODER_GENERAL_EQUIVALENT.relative_to(ROOT).as_posix()
                ),
                "sha256": _sha256(ENCODER_GENERAL_EQUIVALENT),
                "byte_identical_to_authoritative": True,
            },
            "parsed_bitstream_occurrence_count": len(dump_opcode_matches),
            "parsed_bitstream_encoding_msb_first": "11000",
            "parsed_bitstream_decimal": 24,
            "parsed_bitstream_hex": "0x18",
        },
        "claim_boundary": (
            "static configuration intent only; runtime RTL consumption and "
            "exact 0x18 consumption and propagation remain unproven until "
            "the SFU-readiness observer runs"
        ),
    }


def _observer_tail() -> str:
    return r"""
// Requant node0001 guard-only direct-signal observer v1.
// Read-only: no force/deposit/driver. Enabled by +REQUANT_GUARD_DIRECTSIG_PROBE.
    bit rq_guard_probe_enabled;
    integer rq_guard_fd [0:1];
    longint unsigned rq_guard_cycle;
    integer rq_guard_mkdir_status;

    logic rq_guard_inport_int32tofp32 [0:1][0:7];
    logic rq_guard_inport_convert_decoded [0:1][0:7];
    logic rq_guard_inport_ib_capture [0:1][0:7];
    logic rq_guard_inport_ib_valid [0:1][0:7];
    logic [31:0] rq_guard_inport_ib_data [0:1][0:7];
    logic rq_guard_convert_input_capture [0:1][0:7];
    logic rq_guard_convert_input_valid [0:1][0:7];
    logic [31:0] rq_guard_convert_input_data [0:1][0:7];
    logic rq_guard_convert_registered_capture [0:1][0:7];
    logic rq_guard_convert_registered_valid [0:1][0:7];
    logic [31:0] rq_guard_convert_registered_data [0:1][0:7];
    logic rq_guard_inport_final_capture [0:1][0:7];
    logic [`GA_INPORT_TAG-1:0] rq_guard_inport_final_tag [0:1][0:7];
    logic [31:0] rq_guard_inport_final_data [0:1][0:7];
    logic rq_guard_inport_final_ready [0:1][0:7];

    logic rq_guard_pe_selected_capture [0:1][0:3][0:1];
    logic rq_guard_pe_selected_valid [0:1][0:3][0:1];
    logic [31:0] rq_guard_pe_selected_data [0:1][0:3][0:1];
    logic rq_guard_sfu_input_capture [0:1][0:3][0:1];
    logic rq_guard_sfu_input_valid [0:1][0:3][0:1];
    logic [31:0] rq_guard_sfu_input_data [0:1][0:3][0:1];
    logic rq_guard_sfu_compute_enable [0:1][0:3][0:1];
    logic rq_guard_sfu_lut_capture [0:1][0:3][0:1];
    logic [`GA_SFU_SRAM_ADDR_WIDTH-1:0]
        rq_guard_sfu_lut_addr [0:1][0:3][0:1];
    logic [31:0] rq_guard_sfu_pre2alu_data [0:1][0:3][0:1];
    logic [31:0] rq_guard_sfu_slope_data [0:1][0:3][0:1];
    logic [31:0] rq_guard_sfu_intercept_data [0:1][0:3][0:1];
    logic rq_guard_sfu_output_capture [0:1][0:3][0:1];
    logic [31:0] rq_guard_sfu_alu_data [0:1][0:3][0:1];
    logic [31:0] rq_guard_sfu_output_data [0:1][0:3][0:1];
    logic rq_guard_normal_ob_capture [0:1][0:3][0:1];
    logic [31:0] rq_guard_normal_ob_data [0:1][0:3][0:1];

    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_guard_ag_transfer_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_guard_ag_linear_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    integer rq_guard_req_id_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_guard_req_transfer_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_guard_req_linear_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_guard_req_post_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    integer rq_guard_req_sequence [0:1][0:`MSE_REQ_CHL_NUM-1];
    integer rq_guard_wdata_sequence [0:1][0:`MSE_REQ_CHL_NUM-1];
    logic rq_guard_mse4_ag_wr_hs [0:1][0:`MSE_REQ_CHL_NUM-1];
    logic rq_guard_mse4_ag_bp_pre_barrier [0:1];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_guard_mse4_transfer_addr_nooff [0:1];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_guard_mse4_stream_base_word [0:1];

    generate
        for (genvar rq_sid = 0; rq_sid < 2; rq_sid++) begin : RQ_GUARD_SID
            assign rq_guard_mse4_ag_bp_pre_barrier[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                .u_WR_Memory_AG.mem_ag_ob_bp_pre_barrier;
            assign rq_guard_mse4_transfer_addr_nooff[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                .u_WR_Memory_AG.transfer_addr_nooff;
            assign rq_guard_mse4_stream_base_word[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                .u_WR_Memory_AG.mse_stream_base_addr[
                    `GLOBAL_DDR_ADDR_WIDTH-1:`DDR_ADDR_OFFSET_WIDTH
                ];
            for (genvar rq_ch = 0;
                 rq_ch < `MSE_REQ_CHL_NUM;
                 rq_ch++) begin : RQ_GUARD_MSE4_CH
                assign rq_guard_mse4_ag_wr_hs[rq_sid][rq_ch] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                    .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                    .u_WR_Memory_AG.mem_ag_ob_chl_wr_hs[rq_ch];
            end
            for (genvar rq_lane = 0; rq_lane < 8; rq_lane++) begin : RQ_GUARD_LANE
                assign rq_guard_inport_int32tofp32[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .ga_inport_int32tofp32;
                assign rq_guard_inport_convert_decoded[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_cfg_convert_flag;
                assign rq_guard_inport_ib_capture[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_ib_valid &&
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_convert_enable;
                assign rq_guard_inport_ib_valid[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_ib_valid;
                assign rq_guard_inport_ib_data[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_ib_data;
                assign rq_guard_convert_input_capture[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_convert_enable &&
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_convert_valid_in;
                assign rq_guard_convert_input_valid[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_convert_valid_in;
                assign rq_guard_convert_input_data[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_convert_data_in;
                assign rq_guard_convert_registered_capture[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_convert_valid &&
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_convert_bp_post;
                assign rq_guard_convert_registered_valid[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_convert_valid;
                assign rq_guard_convert_registered_data[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_convert_data;
                assign rq_guard_inport_final_capture[rq_sid][rq_lane] =
                    rq_guard_convert_registered_capture[rq_sid][rq_lane];
                assign rq_guard_inport_final_tag[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_out_tag;
                assign rq_guard_inport_final_data[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_out_data;
                assign rq_guard_inport_final_ready[rq_sid][rq_lane] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_General_Array
                    .GA_INPORT_GROUP[0].u_GA_Inport_Group
                    .GA_INPORT[rq_lane].u_GA_Inport.ga_inport_bp_post;
            end
            for (genvar rq_row = 0; rq_row < 4; rq_row++) begin : RQ_GUARD_ROW
                for (genvar rq_slot = 0; rq_slot < 2; rq_slot++) begin : RQ_GUARD_SLOT
                    assign rq_guard_pe_selected_capture[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_enable[0];
                    assign rq_guard_pe_selected_valid[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Inbuffer.ga_pe_inport_valid_bit[0];
                    assign rq_guard_pe_selected_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_inport_data[0];
                    assign rq_guard_sfu_input_capture[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_inport2pre_valid &&
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_preprocess_pipeline0_enable;
                    assign rq_guard_sfu_input_valid[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_inport2pre_valid;
                    assign rq_guard_sfu_input_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_inport2pre_data;
                    assign rq_guard_sfu_compute_enable[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_compute_en;
                    assign rq_guard_sfu_lut_capture[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Inbuffer
                        .sfu_preprocess_pipeline5_valid_bit &&
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_alu_pipeline0_enable;
                    assign rq_guard_sfu_lut_addr[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_coeffs_addr;
                    assign rq_guard_sfu_pre2alu_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_pre2alu_data;
                    assign rq_guard_sfu_slope_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_slope_data_i;
                    assign rq_guard_sfu_intercept_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_intercept_data_i;
                    assign rq_guard_sfu_output_capture[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Outbuffer.normal_mode_wr_handshake;
                    assign rq_guard_sfu_alu_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_alu2outbuffer_data;
                    assign rq_guard_sfu_output_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_result_data;
                    assign rq_guard_normal_ob_capture[rq_sid][rq_row][rq_slot] =
                        rq_guard_sfu_output_capture[rq_sid][rq_row][rq_slot];
                    assign rq_guard_normal_ob_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Outbuffer.normal_mode_wr_data;
                end
            end
        end
    endgenerate

    initial begin : rq_guard_probe_init
        rq_guard_probe_enabled =
            $test$plusargs("REQUANT_GUARD_DIRECTSIG_PROBE");
        rq_guard_cycle = 0;
        for (int sid = 0; sid < 2; sid++) begin
            rq_guard_fd[sid] = 0;
            for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                rq_guard_ag_transfer_pending[sid][ch].delete();
                rq_guard_ag_linear_pending[sid][ch].delete();
                rq_guard_req_id_pending[sid][ch].delete();
                rq_guard_req_transfer_pending[sid][ch].delete();
                rq_guard_req_linear_pending[sid][ch].delete();
                rq_guard_req_post_pending[sid][ch].delete();
                rq_guard_req_sequence[sid][ch] = 0;
                rq_guard_wdata_sequence[sid][ch] = 0;
            end
        end
        if (rq_guard_probe_enabled) begin
            rq_guard_mkdir_status =
                $system("mkdir -p sim_results/requant_guard_directsig_probe");
            for (int sid = 0; sid < 2; sid++) begin
                rq_guard_fd[sid] = $fopen(
                    $sformatf(
                        "sim_results/requant_guard_directsig_probe/slice%02d.log",
                        sid
                    ),
                    "w"
                );
                if (rq_guard_fd[sid] == 0)
                    $error(
                        "REQUANT_GUARD_DIRECTSIG_PROBE cannot open slice%0d",
                        sid
                    );
                else
                    $fdisplay(
                        rq_guard_fd[sid],
                        "# guard-only direct-signal observer v1"
                    );
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin : rq_guard_probe_sample
        if (!u_NDP_Top_new.rst_n_sg) begin
            rq_guard_cycle = 0;
        end else if (rq_guard_probe_enabled) begin
            rq_guard_cycle++;
            for (int sid = 0; sid < 2; sid++) begin
                for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                    if (local_req_hs[0][sid][0][ch])
                        $fdisplay(
                            rq_guard_fd[sid],
                            "GUARD_PATH boundary=MSE0_REQ cycle=%0d slice=%0d ch=%0d post_remap_addr=0x%0h",
                            rq_guard_cycle, sid, ch,
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                            .u_slice_with_datahub_mc_group
                            .local_req_addr[sid][0][ch]
                        );
                    if (local_rdata_hs[0][sid][0][ch])
                        $fdisplay(
                            rq_guard_fd[sid],
                            "GUARD_PATH boundary=MSE0_RDATA cycle=%0d slice=%0d ch=%0d data=0x%032h",
                            rq_guard_cycle, sid, ch,
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                            .u_slice_with_datahub_mc_group
                            .local_rdata[sid][0][ch]
                        );
                    if (rq_guard_mse4_ag_wr_hs[sid][ch] &&
                        rq_guard_mse4_ag_bp_pre_barrier[sid]) begin
                        rq_guard_ag_transfer_pending[sid][ch].push_back(
                            rq_guard_mse4_transfer_addr_nooff[sid]
                        );
                        rq_guard_ag_linear_pending[sid][ch].push_back(
                            rq_guard_mse4_transfer_addr_nooff[sid] +
                            rq_guard_mse4_stream_base_word[sid]
                        );
                    end
                    if (local_req_hs[0][sid][4][ch]) begin
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] transfer_addr;
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] linear_addr;
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] post_addr;
                        integer metadata_valid;
                        integer req_id;
                        req_id = rq_guard_req_sequence[sid][ch];
                        rq_guard_req_sequence[sid][ch] =
                            rq_guard_req_sequence[sid][ch] + 1;
                        post_addr =
                            return_obs_mse4_local_req_addr_mon[0][sid][ch];
                        metadata_valid = (
                            rq_guard_ag_transfer_pending[sid][ch].size() != 0 &&
                            rq_guard_ag_linear_pending[sid][ch].size() != 0
                        );
                        if (metadata_valid) begin
                            transfer_addr =
                                rq_guard_ag_transfer_pending[sid][ch].pop_front();
                            linear_addr =
                                rq_guard_ag_linear_pending[sid][ch].pop_front();
                        end else begin
                            transfer_addr = 'b0;
                            linear_addr = 'b0;
                            $fdisplay(
                                rq_guard_fd[sid],
                                "PROBE_DIAGNOSTIC kind=missing_pre_remap cycle=%0d slice=%0d ch=%0d req_txn_id=%0d",
                                rq_guard_cycle, sid, ch, req_id
                            );
                        end
                        rq_guard_req_id_pending[sid][ch].push_back(req_id);
                        rq_guard_req_transfer_pending[sid][ch].push_back(
                            transfer_addr
                        );
                        rq_guard_req_linear_pending[sid][ch].push_back(
                            linear_addr
                        );
                        rq_guard_req_post_pending[sid][ch].push_back(post_addr);
                        $fdisplay(
                            rq_guard_fd[sid],
                            "GUARD_PATH boundary=MSE4_REQ cycle=%0d slice=%0d ch=%0d req_txn_id=%0d metadata_valid=%0d transfer_addr=0x%0h linear_addr=0x%0h post_remap_addr=0x%0h",
                            rq_guard_cycle, sid, ch, req_id, metadata_valid,
                            transfer_addr, linear_addr, post_addr
                        );
                    end
                    if (local_wdata_hs[0][sid][4][ch]) begin
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] transfer_addr;
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] linear_addr;
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] post_addr;
                        integer paired_req_valid;
                        integer paired_req_id;
                        integer wdata_id;
                        wdata_id = rq_guard_wdata_sequence[sid][ch];
                        rq_guard_wdata_sequence[sid][ch] =
                            rq_guard_wdata_sequence[sid][ch] + 1;
                        paired_req_valid = (
                            rq_guard_req_id_pending[sid][ch].size() != 0 &&
                            rq_guard_req_transfer_pending[sid][ch].size() != 0 &&
                            rq_guard_req_linear_pending[sid][ch].size() != 0 &&
                            rq_guard_req_post_pending[sid][ch].size() != 0
                        );
                        if (paired_req_valid) begin
                            paired_req_id =
                                rq_guard_req_id_pending[sid][ch].pop_front();
                            transfer_addr =
                                rq_guard_req_transfer_pending[sid][ch].pop_front();
                            linear_addr =
                                rq_guard_req_linear_pending[sid][ch].pop_front();
                            post_addr =
                                rq_guard_req_post_pending[sid][ch].pop_front();
                        end else begin
                            paired_req_id = -1;
                            transfer_addr = 'b0;
                            linear_addr = 'b0;
                            post_addr = 'b0;
                            $fdisplay(
                                rq_guard_fd[sid],
                                "PROBE_DIAGNOSTIC kind=unpaired_wdata cycle=%0d slice=%0d ch=%0d wdata_txn_id=%0d",
                                rq_guard_cycle, sid, ch, wdata_id
                            );
                        end
                        $fdisplay(
                            rq_guard_fd[sid],
                            "MSE4_WRITE | cycle=%0d slice=%0d local_stage=0 role=guard ch=%0d accepted=1 valid=1 ready=1 strobe=0xffff req_txn_id=%0d wdata_txn_id=%0d paired_req_valid=%0d transfer_addr=0x%0h linear_addr=0x%0h addr=0x%0h data=0x%032h",
                            rq_guard_cycle, sid, ch, paired_req_id, wdata_id,
                            paired_req_valid, transfer_addr, linear_addr,
                            post_addr,
                            return_obs_mse4_local_wdata_mon[0][sid][ch]
                        );
                        $fdisplay(
                            rq_guard_fd[sid],
                            "GUARD_PATH boundary=MSE4_WDATA cycle=%0d slice=%0d ch=%0d req_txn_id=%0d wdata_txn_id=%0d paired_req_valid=%0d transfer_addr=0x%0h linear_addr=0x%0h post_remap_addr=0x%0h data=0x%032h",
                            rq_guard_cycle, sid, ch, paired_req_id, wdata_id,
                            paired_req_valid, transfer_addr, linear_addr,
                            post_addr,
                            return_obs_mse4_local_wdata_mon[0][sid][ch]
                        );
                    end
                end
                if (return_obs_mse0_buf_hs_mon[0][sid])
                    $fdisplay(
                        rq_guard_fd[sid],
                        "GUARD_PATH boundary=MSE0_TO_BUFFER cycle=%0d slice=%0d data=0x%032h",
                        rq_guard_cycle, sid,
                        return_obs_mse0_buf_data_mon[0][sid]
                    );
                for (int lane = 0; lane < 8; lane++) begin
                    if (rq_guard_inport_ib_capture[sid][lane]) begin
                        $fdisplay(
                            rq_guard_fd[sid],
                            "GUARD_PATH boundary=GA_INPORT_CONFIG cycle=%0d slice=%0d lane=%0d int32tofp32=%0d convert_decoded=%0d data=0x%08h",
                            rq_guard_cycle, sid, lane,
                            rq_guard_inport_int32tofp32[sid][lane],
                            rq_guard_inport_convert_decoded[sid][lane],
                            {31'b0, rq_guard_inport_int32tofp32[sid][lane]}
                        );
                        $fdisplay(
                            rq_guard_fd[sid],
                            "GUARD_PATH boundary=GA_INPORT_IB cycle=%0d slice=%0d lane=%0d valid=%0d data=0x%08h",
                            rq_guard_cycle, sid, lane,
                            rq_guard_inport_ib_valid[sid][lane],
                            rq_guard_inport_ib_data[sid][lane]
                        );
                    end
                    if (rq_guard_convert_input_capture[sid][lane])
                        $fdisplay(
                            rq_guard_fd[sid],
                            "GUARD_PATH boundary=GA_CONVERT_INPUT cycle=%0d slice=%0d lane=%0d valid=%0d data=0x%08h",
                            rq_guard_cycle, sid, lane,
                            rq_guard_convert_input_valid[sid][lane],
                            rq_guard_convert_input_data[sid][lane]
                        );
                    if (rq_guard_convert_registered_capture[sid][lane])
                        $fdisplay(
                            rq_guard_fd[sid],
                            "GUARD_PATH boundary=GA_CONVERT_REGISTERED cycle=%0d slice=%0d lane=%0d valid=%0d data=0x%08h",
                            rq_guard_cycle, sid, lane,
                            rq_guard_convert_registered_valid[sid][lane],
                            rq_guard_convert_registered_data[sid][lane]
                        );
                    if (rq_guard_inport_final_capture[sid][lane])
                        $fdisplay(
                            rq_guard_fd[sid],
                            "GUARD_PATH boundary=GA_INPORT_FINAL cycle=%0d slice=%0d lane=%0d valid=%0d ready=%0d tag=0x%0h data=0x%08h",
                            rq_guard_cycle, sid, lane,
                            rq_guard_inport_final_tag[sid][lane][
                                `GA_INPORT_TAG-1
                            ],
                            rq_guard_inport_final_ready[sid][lane],
                            rq_guard_inport_final_tag[sid][lane],
                            rq_guard_inport_final_data[sid][lane]
                        );
                end
                for (int row = 0; row < 4; row++) begin
                    for (int slot = 0; slot < 2; slot++) begin
                        if (rq_guard_pe_selected_capture[sid][row][slot])
                            $fdisplay(
                                rq_guard_fd[sid],
                                "GUARD_PATH boundary=PE_SELECTED_INPUT cycle=%0d slice=%0d pe=%0d%0d valid=%0d data=0x%08h",
                                rq_guard_cycle, sid, row, 2*slot+1,
                                rq_guard_pe_selected_valid[sid][row][slot],
                                rq_guard_pe_selected_data[sid][row][slot]
                            );
                        if (rq_guard_sfu_input_capture[sid][row][slot]) begin
                            $fdisplay(
                                rq_guard_fd[sid],
                                "GUARD_PATH boundary=SFU_INPUT cycle=%0d slice=%0d pe=%0d%0d valid=%0d data=0x%08h",
                                rq_guard_cycle, sid, row, 2*slot+1,
                                rq_guard_sfu_input_valid[sid][row][slot],
                                rq_guard_sfu_input_data[sid][row][slot]
                            );
                            $fdisplay(
                                rq_guard_fd[sid],
                                "GUARD_PATH boundary=SFU_COMPUTE cycle=%0d slice=%0d pe=%0d%0d enable=%0d data=0x%08h",
                                rq_guard_cycle, sid, row, 2*slot+1,
                                rq_guard_sfu_compute_enable[sid][row][slot],
                                {31'b0,
                                 rq_guard_sfu_compute_enable[sid][row][slot]}
                            );
                        end
                        if (rq_guard_sfu_lut_capture[sid][row][slot])
                            $fdisplay(
                                rq_guard_fd[sid],
                                "GUARD_PATH boundary=SFU_LUT cycle=%0d slice=%0d pe=%0d%0d lut_addr=0x%0h slope=0x%08h intercept=0x%08h data=0x%08h",
                                rq_guard_cycle, sid, row, 2*slot+1,
                                rq_guard_sfu_lut_addr[sid][row][slot],
                                rq_guard_sfu_slope_data[sid][row][slot],
                                rq_guard_sfu_intercept_data[sid][row][slot],
                                rq_guard_sfu_pre2alu_data[sid][row][slot]
                            );
                        if (rq_guard_sfu_output_capture[sid][row][slot]) begin
                            $fdisplay(
                                rq_guard_fd[sid],
                                "GUARD_PATH boundary=SFU_ALU cycle=%0d slice=%0d pe=%0d%0d data=0x%08h",
                                rq_guard_cycle, sid, row, 2*slot+1,
                                rq_guard_sfu_alu_data[sid][row][slot]
                            );
                            $fdisplay(
                                rq_guard_fd[sid],
                                "GUARD_PATH boundary=SFU_OUTPUT cycle=%0d slice=%0d pe=%0d%0d data=0x%08h",
                                rq_guard_cycle, sid, row, 2*slot+1,
                                rq_guard_sfu_output_data[sid][row][slot]
                            );
                        end
                        if (rq_guard_normal_ob_capture[sid][row][slot])
                            $fdisplay(
                                rq_guard_fd[sid],
                                "GUARD_PATH boundary=NORMAL_OUTBUFFER_WRITE cycle=%0d slice=%0d pe=%0d%0d valid=1 data=0x%08h",
                                rq_guard_cycle, sid, row, 2*slot+1,
                                rq_guard_normal_ob_data[sid][row][slot]
                            );
                    end
                end
                $fflush(rq_guard_fd[sid]);
            end
        end
    end

    final begin : rq_guard_probe_final
        if (rq_guard_probe_enabled)
            for (int sid = 0; sid < 2; sid++)
                if (rq_guard_fd[sid] != 0) begin
                    for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++)
                        $fdisplay(
                            rq_guard_fd[sid],
                            "PROBE_SUMMARY slice=%0d ch=%0d req_count=%0d wdata_count=%0d outstanding_req=%0d outstanding_ag=%0d",
                            sid, ch, rq_guard_req_sequence[sid][ch],
                            rq_guard_wdata_sequence[sid][ch],
                            rq_guard_req_id_pending[sid][ch].size(),
                            rq_guard_ag_transfer_pending[sid][ch].size()
                        );
                    $fclose(rq_guard_fd[sid]);
                end
    end
"""


def _sfu_readiness_observer_tail() -> str:
    return r"""
// Requant node0001 guard-only SFU readiness observer v1.
// Read-only: no force/deposit/driver. Enabled by +REQUANT_GUARD_SFU_READY_PROBE.
    bit rq_ready_probe_enabled;
    integer rq_ready_fd [0:1];
    longint unsigned rq_ready_cycle;
    integer rq_ready_mkdir_status;

    logic rq_ready_pe_selected [0:1][0:3][0:1];
    logic [31:0] rq_ready_pe_selected_data [0:1][0:3][0:1];
    logic [4:0] rq_ready_opcode [0:1][0:3][0:1];
    logic rq_ready_sfu_valid [0:1][0:3][0:1];
    logic rq_ready_compute_en [0:1][0:3][0:1];
    logic rq_ready_post_valid [0:1][0:3][0:1];
    logic rq_ready_matched [0:1][0:3][0:1];
    logic rq_ready_output_valid [0:1][0:3][0:1];
    logic rq_ready_pre0_enable [0:1][0:3][0:1];
    logic rq_ready_pre0_valid [0:1][0:3][0:1];

    logic [4:0] rq_ready_opcode_d [0:1][0:3][0:1];
    logic rq_ready_sfu_valid_d [0:1][0:3][0:1];
    logic rq_ready_compute_en_d [0:1][0:3][0:1];
    logic rq_ready_post_valid_d [0:1][0:3][0:1];
    logic rq_ready_matched_d [0:1][0:3][0:1];
    logic rq_ready_output_valid_d [0:1][0:3][0:1];
    logic rq_ready_pre0_enable_d [0:1][0:3][0:1];
    logic rq_ready_pre0_valid_d [0:1][0:3][0:1];

    logic rq_ready_group_compute_valid [0:1];
    logic rq_ready_lut_initial_en [0:1];
    logic [8:0] rq_ready_lut_initial_addr [0:1];
    logic rq_ready_lut_end_addr [0:1];
    logic rq_ready_slice_rst [0:1];
    logic rq_ready_group_compute_valid_d [0:1];
    logic rq_ready_lut_initial_en_d [0:1];
    logic [8:0] rq_ready_lut_initial_addr_d [0:1];
    logic rq_ready_lut_end_addr_d [0:1];
    logic rq_ready_slice_rst_d [0:1];

    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_ready_ag_transfer_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_ready_ag_linear_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    integer rq_ready_req_id_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_ready_req_transfer_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_ready_req_linear_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_ready_req_post_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    integer rq_ready_req_sequence [0:1][0:`MSE_REQ_CHL_NUM-1];
    integer rq_ready_wdata_sequence [0:1][0:`MSE_REQ_CHL_NUM-1];
    logic rq_ready_mse4_ag_wr_hs [0:1][0:`MSE_REQ_CHL_NUM-1];
    logic rq_ready_mse4_ag_bp_pre_barrier [0:1];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_ready_mse4_transfer_addr_nooff [0:1];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_ready_mse4_stream_base_word [0:1];

    generate
        for (genvar rq_sid = 0; rq_sid < 2; rq_sid++) begin : RQ_READY_SID
            assign rq_ready_group_compute_valid[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                .sfu_compute_valid;
            assign rq_ready_lut_initial_en[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                .u_GA_SFU_LUT.lut_initial_en;
            assign rq_ready_lut_initial_addr[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                .u_GA_SFU_LUT.lut_initial_addr;
            assign rq_ready_lut_end_addr[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                .u_GA_SFU_LUT.end_lut_initial_addr;
            assign rq_ready_slice_rst[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                .u_GA_SFU_LUT.slice_rst;
            assign rq_ready_mse4_ag_bp_pre_barrier[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                .u_WR_Memory_AG.mem_ag_ob_bp_pre_barrier;
            assign rq_ready_mse4_transfer_addr_nooff[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                .u_WR_Memory_AG.transfer_addr_nooff;
            assign rq_ready_mse4_stream_base_word[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                .u_WR_Memory_AG.mse_stream_base_addr[
                    `GLOBAL_DDR_ADDR_WIDTH-1:`DDR_ADDR_OFFSET_WIDTH
                ];
            for (genvar rq_ch = 0;
                 rq_ch < `MSE_REQ_CHL_NUM;
                 rq_ch++) begin : RQ_READY_MSE4_CH
                assign rq_ready_mse4_ag_wr_hs[rq_sid][rq_ch] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                    .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                    .u_WR_Memory_AG.mem_ag_ob_chl_wr_hs[rq_ch];
            end
            for (genvar rq_row = 0; rq_row < 4; rq_row++) begin : RQ_READY_ROW
                for (genvar rq_slot = 0; rq_slot < 2; rq_slot++) begin : RQ_READY_SLOT
                    assign rq_ready_pe_selected[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_enable[0];
                    assign rq_ready_pe_selected_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_inport_data[0];
                    assign rq_ready_opcode[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_alu_opcode;
                    assign rq_ready_sfu_valid[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_valid;
                    assign rq_ready_compute_en[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_compute_en;
                    assign rq_ready_post_valid[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Inbuffer
                        .ga_pe_inbuffer_valid_bit[0];
                    assign rq_ready_matched[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_matched;
                    assign rq_ready_output_valid[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Inbuffer.ib_output_valid_bit;
                    assign rq_ready_pre0_enable[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_preprocess_pipeline0_enable;
                    assign rq_ready_pre0_valid[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Inbuffer
                        .sfu_preprocess_pipeline0_valid_bit;
                end
            end
        end
    endgenerate

    initial begin : rq_ready_probe_init
        rq_ready_probe_enabled =
            $test$plusargs("REQUANT_GUARD_SFU_READY_PROBE");
        rq_ready_cycle = 0;
        for (int sid = 0; sid < 2; sid++) begin
            rq_ready_fd[sid] = 0;
            rq_ready_group_compute_valid_d[sid] = 1'bx;
            rq_ready_lut_initial_en_d[sid] = 1'bx;
            rq_ready_lut_initial_addr_d[sid] = 'x;
            rq_ready_lut_end_addr_d[sid] = 1'bx;
            rq_ready_slice_rst_d[sid] = 1'bx;
            for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                rq_ready_ag_transfer_pending[sid][ch].delete();
                rq_ready_ag_linear_pending[sid][ch].delete();
                rq_ready_req_id_pending[sid][ch].delete();
                rq_ready_req_transfer_pending[sid][ch].delete();
                rq_ready_req_linear_pending[sid][ch].delete();
                rq_ready_req_post_pending[sid][ch].delete();
                rq_ready_req_sequence[sid][ch] = 0;
                rq_ready_wdata_sequence[sid][ch] = 0;
            end
            for (int row = 0; row < 4; row++)
                for (int slot = 0; slot < 2; slot++) begin
                    rq_ready_opcode_d[sid][row][slot] = 'x;
                    rq_ready_sfu_valid_d[sid][row][slot] = 1'bx;
                    rq_ready_compute_en_d[sid][row][slot] = 1'bx;
                    rq_ready_post_valid_d[sid][row][slot] = 1'bx;
                    rq_ready_matched_d[sid][row][slot] = 1'bx;
                    rq_ready_output_valid_d[sid][row][slot] = 1'bx;
                    rq_ready_pre0_enable_d[sid][row][slot] = 1'bx;
                    rq_ready_pre0_valid_d[sid][row][slot] = 1'bx;
                end
        end
        if (rq_ready_probe_enabled) begin
            rq_ready_mkdir_status =
                $system("mkdir -p sim_results/requant_guard_sfu_ready_probe");
            for (int sid = 0; sid < 2; sid++) begin
                rq_ready_fd[sid] = $fopen(
                    $sformatf(
                        "sim_results/requant_guard_sfu_ready_probe/slice%02d.log",
                        sid
                    ),
                    "w"
                );
                if (rq_ready_fd[sid] == 0)
                    $error(
                        "REQUANT_GUARD_SFU_READY_PROBE cannot open slice%0d",
                        sid
                    );
                else
                    $fdisplay(
                        rq_ready_fd[sid],
                        "# guard-only SFU readiness observer v1"
                    );
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin : rq_ready_probe_sample
        if (!u_NDP_Top_new.rst_n_sg) begin
            rq_ready_cycle = 0;
        end else if (rq_ready_probe_enabled) begin
            rq_ready_cycle++;
            for (int sid = 0; sid < 2; sid++) begin
                for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                    if (rq_ready_mse4_ag_wr_hs[sid][ch] &&
                        rq_ready_mse4_ag_bp_pre_barrier[sid]) begin
                        rq_ready_ag_transfer_pending[sid][ch].push_back(
                            rq_ready_mse4_transfer_addr_nooff[sid]
                        );
                        rq_ready_ag_linear_pending[sid][ch].push_back(
                            rq_ready_mse4_transfer_addr_nooff[sid] +
                            rq_ready_mse4_stream_base_word[sid]
                        );
                    end
                    if (local_req_hs[0][sid][4][ch]) begin
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] transfer_addr;
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] linear_addr;
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] post_addr;
                        integer metadata_valid;
                        integer req_id;
                        req_id = rq_ready_req_sequence[sid][ch];
                        rq_ready_req_sequence[sid][ch]++;
                        post_addr =
                            return_obs_mse4_local_req_addr_mon[0][sid][ch];
                        metadata_valid = (
                            rq_ready_ag_transfer_pending[sid][ch].size() != 0 &&
                            rq_ready_ag_linear_pending[sid][ch].size() != 0
                        );
                        if (metadata_valid) begin
                            transfer_addr =
                                rq_ready_ag_transfer_pending[sid][ch].pop_front();
                            linear_addr =
                                rq_ready_ag_linear_pending[sid][ch].pop_front();
                        end else begin
                            transfer_addr = 'b0;
                            linear_addr = 'b0;
                        end
                        rq_ready_req_id_pending[sid][ch].push_back(req_id);
                        rq_ready_req_transfer_pending[sid][ch].push_back(
                            transfer_addr
                        );
                        rq_ready_req_linear_pending[sid][ch].push_back(
                            linear_addr
                        );
                        rq_ready_req_post_pending[sid][ch].push_back(post_addr);
                        $fdisplay(
                            rq_ready_fd[sid],
                            "GUARD_PATH boundary=MSE4_REQ cycle=%0d slice=%0d ch=%0d req_txn_id=%0d metadata_valid=%0d transfer_addr=0x%0h linear_addr=0x%0h post_remap_addr=0x%0h",
                            rq_ready_cycle, sid, ch, req_id, metadata_valid,
                            transfer_addr, linear_addr, post_addr
                        );
                    end
                    if (local_wdata_hs[0][sid][4][ch]) begin
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] transfer_addr;
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] linear_addr;
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] post_addr;
                        integer paired_req_valid;
                        integer paired_req_id;
                        integer wdata_id;
                        wdata_id = rq_ready_wdata_sequence[sid][ch];
                        rq_ready_wdata_sequence[sid][ch]++;
                        paired_req_valid = (
                            rq_ready_req_id_pending[sid][ch].size() != 0 &&
                            rq_ready_req_transfer_pending[sid][ch].size() != 0 &&
                            rq_ready_req_linear_pending[sid][ch].size() != 0 &&
                            rq_ready_req_post_pending[sid][ch].size() != 0
                        );
                        if (paired_req_valid) begin
                            paired_req_id =
                                rq_ready_req_id_pending[sid][ch].pop_front();
                            transfer_addr =
                                rq_ready_req_transfer_pending[sid][ch].pop_front();
                            linear_addr =
                                rq_ready_req_linear_pending[sid][ch].pop_front();
                            post_addr =
                                rq_ready_req_post_pending[sid][ch].pop_front();
                        end else begin
                            paired_req_id = -1;
                            transfer_addr = 'b0;
                            linear_addr = 'b0;
                            post_addr = 'b0;
                        end
                        $fdisplay(
                            rq_ready_fd[sid],
                            "MSE4_WRITE | cycle=%0d slice=%0d local_stage=0 role=guard ch=%0d accepted=1 valid=1 ready=1 strobe=0xffff req_txn_id=%0d wdata_txn_id=%0d paired_req_valid=%0d transfer_addr=0x%0h linear_addr=0x%0h addr=0x%0h data=0x%032h",
                            rq_ready_cycle, sid, ch, paired_req_id, wdata_id,
                            paired_req_valid, transfer_addr, linear_addr,
                            post_addr,
                            return_obs_mse4_local_wdata_mon[0][sid][ch]
                        );
                        $fdisplay(
                            rq_ready_fd[sid],
                            "GUARD_PATH boundary=MSE4_WDATA cycle=%0d slice=%0d ch=%0d data=0x%032h",
                            rq_ready_cycle, sid, ch,
                            return_obs_mse4_local_wdata_mon[0][sid][ch]
                        );
                    end
                end

                if (rq_ready_group_compute_valid[sid] !==
                    rq_ready_group_compute_valid_d[sid])
                    $fdisplay(
                        rq_ready_fd[sid],
                        "GUARD_PATH boundary=SFU_GROUP_COMPUTE_VALID cycle=%0d slice=%0d compute_valid=%0d data=0x%08h",
                        rq_ready_cycle, sid,
                        rq_ready_group_compute_valid[sid],
                        {31'b0, rq_ready_group_compute_valid[sid]}
                    );
                if (rq_ready_lut_initial_en[sid] !==
                    rq_ready_lut_initial_en_d[sid] ||
                    rq_ready_lut_initial_addr[sid] !==
                    rq_ready_lut_initial_addr_d[sid] ||
                    rq_ready_lut_end_addr[sid] !==
                    rq_ready_lut_end_addr_d[sid] ||
                    rq_ready_slice_rst[sid] !== rq_ready_slice_rst_d[sid])
                    $fdisplay(
                        rq_ready_fd[sid],
                        "GUARD_PATH boundary=SFU_LUT_INIT cycle=%0d slice=%0d init_en=%0d init_addr=0x%0h end_addr=%0d slice_rst=%0d data=0x%08h",
                        rq_ready_cycle, sid,
                        rq_ready_lut_initial_en[sid],
                        rq_ready_lut_initial_addr[sid],
                        rq_ready_lut_end_addr[sid],
                        rq_ready_slice_rst[sid],
                        {19'b0, rq_ready_slice_rst[sid],
                         rq_ready_lut_end_addr[sid],
                         rq_ready_lut_initial_en[sid],
                         rq_ready_lut_initial_addr[sid]}
                    );
                rq_ready_group_compute_valid_d[sid] =
                    rq_ready_group_compute_valid[sid];
                rq_ready_lut_initial_en_d[sid] = rq_ready_lut_initial_en[sid];
                rq_ready_lut_initial_addr_d[sid] =
                    rq_ready_lut_initial_addr[sid];
                rq_ready_lut_end_addr_d[sid] = rq_ready_lut_end_addr[sid];
                rq_ready_slice_rst_d[sid] = rq_ready_slice_rst[sid];

                for (int row = 0; row < 4; row++)
                    for (int slot = 0; slot < 2; slot++) begin
                        if (rq_ready_pe_selected[sid][row][slot])
                            $fdisplay(
                                rq_ready_fd[sid],
                                "GUARD_PATH boundary=PE_SELECTED_INPUT cycle=%0d slice=%0d pe=%0d%0d data=0x%08h",
                                rq_ready_cycle, sid, row, 2*slot+1,
                                rq_ready_pe_selected_data[sid][row][slot]
                            );
                        if (rq_ready_post_valid[sid][row][slot] !==
                            rq_ready_post_valid_d[sid][row][slot] ||
                            rq_ready_matched[sid][row][slot] !==
                            rq_ready_matched_d[sid][row][slot] ||
                            rq_ready_output_valid[sid][row][slot] !==
                            rq_ready_output_valid_d[sid][row][slot])
                            $fdisplay(
                                rq_ready_fd[sid],
                                "GUARD_PATH boundary=PE_POST_REGISTER cycle=%0d slice=%0d pe=%0d%0d post_valid=%0d matched=%0d output_valid=%0d data=0x%08h",
                                rq_ready_cycle, sid, row, 2*slot+1,
                                rq_ready_post_valid[sid][row][slot],
                                rq_ready_matched[sid][row][slot],
                                rq_ready_output_valid[sid][row][slot],
                                {29'b0,
                                 rq_ready_output_valid[sid][row][slot],
                                 rq_ready_matched[sid][row][slot],
                                 rq_ready_post_valid[sid][row][slot]}
                            );
                        if (rq_ready_opcode[sid][row][slot] !==
                            rq_ready_opcode_d[sid][row][slot] ||
                            rq_ready_sfu_valid[sid][row][slot] !==
                            rq_ready_sfu_valid_d[sid][row][slot] ||
                            rq_ready_compute_en[sid][row][slot] !==
                            rq_ready_compute_en_d[sid][row][slot])
                            $fdisplay(
                                rq_ready_fd[sid],
                                "GUARD_PATH boundary=SFU_OPCODE_READY cycle=%0d slice=%0d pe=%0d%0d opcode=0x%0h sfu_valid=%0d compute_en=%0d data=0x%08h",
                                rq_ready_cycle, sid, row, 2*slot+1,
                                rq_ready_opcode[sid][row][slot],
                                rq_ready_sfu_valid[sid][row][slot],
                                rq_ready_compute_en[sid][row][slot],
                                {25'b0,
                                 rq_ready_compute_en[sid][row][slot],
                                 rq_ready_sfu_valid[sid][row][slot],
                                 rq_ready_opcode[sid][row][slot]}
                            );
                        if (rq_ready_pre0_enable[sid][row][slot] !==
                            rq_ready_pre0_enable_d[sid][row][slot] ||
                            rq_ready_pre0_valid[sid][row][slot] !==
                            rq_ready_pre0_valid_d[sid][row][slot])
                            $fdisplay(
                                rq_ready_fd[sid],
                                "GUARD_PATH boundary=SFU_PREPROCESS0 cycle=%0d slice=%0d pe=%0d%0d enable=%0d valid=%0d data=0x%08h",
                                rq_ready_cycle, sid, row, 2*slot+1,
                                rq_ready_pre0_enable[sid][row][slot],
                                rq_ready_pre0_valid[sid][row][slot],
                                {30'b0,
                                 rq_ready_pre0_valid[sid][row][slot],
                                 rq_ready_pre0_enable[sid][row][slot]}
                            );
                        rq_ready_opcode_d[sid][row][slot] =
                            rq_ready_opcode[sid][row][slot];
                        rq_ready_sfu_valid_d[sid][row][slot] =
                            rq_ready_sfu_valid[sid][row][slot];
                        rq_ready_compute_en_d[sid][row][slot] =
                            rq_ready_compute_en[sid][row][slot];
                        rq_ready_post_valid_d[sid][row][slot] =
                            rq_ready_post_valid[sid][row][slot];
                        rq_ready_matched_d[sid][row][slot] =
                            rq_ready_matched[sid][row][slot];
                        rq_ready_output_valid_d[sid][row][slot] =
                            rq_ready_output_valid[sid][row][slot];
                        rq_ready_pre0_enable_d[sid][row][slot] =
                            rq_ready_pre0_enable[sid][row][slot];
                        rq_ready_pre0_valid_d[sid][row][slot] =
                            rq_ready_pre0_valid[sid][row][slot];
                    end
                $fflush(rq_ready_fd[sid]);
            end
        end
    end

    final begin : rq_ready_probe_final
        if (rq_ready_probe_enabled)
            for (int sid = 0; sid < 2; sid++)
                if (rq_ready_fd[sid] != 0) begin
                    for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++)
                        $fdisplay(
                            rq_ready_fd[sid],
                            "PROBE_SUMMARY slice=%0d ch=%0d req_count=%0d wdata_count=%0d outstanding_req=%0d outstanding_ag=%0d",
                            sid, ch, rq_ready_req_sequence[sid][ch],
                            rq_ready_wdata_sequence[sid][ch],
                            rq_ready_req_id_pending[sid][ch].size(),
                            rq_ready_ag_transfer_pending[sid][ch].size()
                        );
                    $fclose(rq_ready_fd[sid]);
                end
    end
"""


def _sfu_numeric_observer_tail() -> str:
    return r"""
// Requant node0001 guard-only SFU numeric capture-edge observer v1.
// Read-only: no force/deposit/driver. Every numeric record is emitted only
// when the named RTL enable/handshake captures the displayed payload.
// Enabled by +REQUANT_GUARD_SFU_NUMERIC_PROBE.
    bit rq_num_probe_enabled;
    integer rq_num_fd [0:1];
    longint unsigned rq_num_cycle;
    integer rq_num_mkdir_status;

    logic rq_num_pe_selected_capture [0:1][0:3][0:1];
    logic [31:0] rq_num_pe_selected_data [0:1][0:3][0:1];
    logic rq_num_pre_input_capture [0:1][0:3][0:1];
    logic [31:0] rq_num_pre_input_data [0:1][0:3][0:1];
    logic rq_num_bst_capture [0:1][0:3][0:1];
    logic [31:0] rq_num_bst_result_source [0:1][0:3][0:1];
    logic [`GA_SFU_SRAM_ADDR_WIDTH-1:0]
        rq_num_bst_coeff_addr_next [0:1][0:3][0:1];
    logic rq_num_coeff_capture [0:1][0:3][0:1];
    logic [`GA_SFU_SRAM_ADDR_WIDTH-1:0]
        rq_num_coeff_addr [0:1][0:3][0:1];
    logic [31:0] rq_num_coeff_preprocessed [0:1][0:3][0:1];
    logic [31:0] rq_num_coeff_slope [0:1][0:3][0:1];
    logic [31:0] rq_num_coeff_intercept [0:1][0:3][0:1];
    logic [`GA_PE_ALU_TAG_WIDTH-1:0]
        rq_num_alu_input_tag [0:1][0:3][0:1];
    logic [31:0] rq_num_alu_input0 [0:1][0:3][0:1];
    logic [31:0] rq_num_alu_input1 [0:1][0:3][0:1];
    logic [31:0] rq_num_alu_input2 [0:1][0:3][0:1];
    logic rq_num_normal_wr_hs [0:1][0:3][0:1];
    logic [31:0] rq_num_alu_result [0:1][0:3][0:1];
    logic [`GA_PE_ALU_TAG_WIDTH-1:0]
        rq_num_alu_result_tag [0:1][0:3][0:1];
    logic [31:0] rq_num_postprocess_result [0:1][0:3][0:1];
    logic [31:0] rq_num_normal_wr_data [0:1][0:3][0:1];
    logic [`GA_PE_OUTBUFFER_TAG_WIDTH-1:0]
        rq_num_normal_wr_tag [0:1][0:3][0:1];
    logic rq_num_normal_rd_hs [0:1][0:3][0:1];
    logic [31:0] rq_num_normal_rd_data [0:1][0:3][0:1];
    logic [`GA_PE_OUTBUFFER_TAG_WIDTH-1:0]
        rq_num_normal_rd_tag [0:1][0:3][0:1];

    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_num_ag_transfer_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_num_ag_linear_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    integer rq_num_req_id_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_num_req_transfer_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_num_req_linear_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_num_req_post_pending [0:1][0:`MSE_REQ_CHL_NUM-1][$];
    integer rq_num_req_sequence [0:1][0:`MSE_REQ_CHL_NUM-1];
    integer rq_num_wdata_sequence [0:1][0:`MSE_REQ_CHL_NUM-1];
    logic rq_num_mse4_ag_wr_hs [0:1][0:`MSE_REQ_CHL_NUM-1];
    logic rq_num_mse4_ag_bp_pre_barrier [0:1];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_num_mse4_transfer_addr_nooff [0:1];
    logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0]
        rq_num_mse4_stream_base_word [0:1];

    generate
        for (genvar rq_sid = 0; rq_sid < 2; rq_sid++) begin : RQ_NUM_SID
            assign rq_num_mse4_ag_bp_pre_barrier[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                .u_WR_Memory_AG.mem_ag_ob_bp_pre_barrier;
            assign rq_num_mse4_transfer_addr_nooff[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                .u_WR_Memory_AG.transfer_addr_nooff;
            assign rq_num_mse4_stream_base_word[rq_sid] =
                u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                .u_WR_Memory_AG.mse_stream_base_addr[
                    `GLOBAL_DDR_ADDR_WIDTH-1:`DDR_ADDR_OFFSET_WIDTH
                ];
            for (genvar rq_ch = 0;
                 rq_ch < `MSE_REQ_CHL_NUM;
                 rq_ch++) begin : RQ_NUM_MSE4_CH
                assign rq_num_mse4_ag_wr_hs[rq_sid][rq_ch] =
                    u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                    .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                    .u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine
                    .MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine
                    .u_WR_Memory_AG.mem_ag_ob_chl_wr_hs[rq_ch];
            end
            for (genvar rq_row = 0; rq_row < 4; rq_row++) begin : RQ_NUM_ROW
                for (genvar rq_slot = 0;
                     rq_slot < 2;
                     rq_slot++) begin : RQ_NUM_SLOT
                    assign rq_num_pe_selected_capture[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Inbuffer.ga_pe_inbuffer_enable[0];
                    assign rq_num_pe_selected_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_inport_data[0];
                    assign rq_num_pre_input_capture[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_inport2pre_valid &&
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_preprocess_pipeline0_enable;
                    assign rq_num_pre_input_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_inport2pre_data;
                    assign rq_num_bst_capture[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_preprocess_pipeline5_enable &&
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_SFU_Preprocess
                        .u_binary_search_tree.comparator_valid_5;
                    assign rq_num_bst_result_source[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_SFU_Preprocess
                        .u_binary_search_tree.bst_search_data_5;
                    assign rq_num_bst_coeff_addr_next[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_SFU_Preprocess
                        .u_binary_search_tree.less_than_lower_bound ? 7'h00 :
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_SFU_Preprocess
                        .u_binary_search_tree.greater_than_upper_bound ? 7'h41 :
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_SFU_Preprocess
                        .u_binary_search_tree.gtet_5 ?
                        (
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                            .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                            .u_GA_SFU_PE.u_GA_PE_SFU_Preprocess
                            .u_binary_search_tree.bst_search_addr_5 << 1
                        ) + 2 :
                        (
                            u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                            .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                            .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                            .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                            .u_GA_SFU_PE.u_GA_PE_SFU_Preprocess
                            .u_binary_search_tree.bst_search_addr_5 << 1
                        ) + 1;
                    assign rq_num_coeff_capture[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Inbuffer
                        .sfu_preprocess_pipeline5_valid_bit &&
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_alu_pipeline0_enable;
                    assign rq_num_coeff_addr[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_coeffs_addr;
                    assign rq_num_coeff_preprocessed[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_pre2alu_data;
                    assign rq_num_coeff_slope[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_slope_data_i;
                    assign rq_num_coeff_intercept[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_intercept_data_i;
                    assign rq_num_alu_input_tag[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Inbuffer.ga_pe_alu_input_tag;
                    assign rq_num_alu_input0[rq_sid][rq_row][rq_slot] =
                        rq_num_coeff_preprocessed[rq_sid][rq_row][rq_slot];
                    assign rq_num_alu_input1[rq_sid][rq_row][rq_slot] =
                        rq_num_coeff_slope[rq_sid][rq_row][rq_slot];
                    assign rq_num_alu_input2[rq_sid][rq_row][rq_slot] =
                        rq_num_coeff_intercept[rq_sid][rq_row][rq_slot];
                    assign rq_num_normal_wr_hs[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Outbuffer.normal_mode_wr_handshake;
                    assign rq_num_alu_result[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_alu2outbuffer_data;
                    assign rq_num_alu_result_tag[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_alu_result_tag;
                    assign rq_num_postprocess_result[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.ga_pe_sfu_result_data;
                    assign rq_num_normal_wr_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Outbuffer.normal_mode_wr_data;
                    assign rq_num_normal_wr_tag[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Outbuffer.normal_mode_wr_tag;
                    assign rq_num_normal_rd_hs[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Outbuffer.normal_mode_rd_handshake;
                    assign rq_num_normal_rd_data[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Outbuffer.ga_pe_outbuffer_rd_data;
                    assign rq_num_normal_rd_tag[rq_sid][rq_row][rq_slot] =
                        u_NDP_Top_new.slice_with_datahub_mc_group_gen[0]
                        .u_slice_with_datahub_mc_group.slice_group_gen[rq_sid]
                        .u_slice_wrapper.u_Slice.u_General_Array.u_GA_PE_Group
                        .GA_ROW_PE[rq_row].GA_COL_PE[2*rq_slot+1].GA_SFU_PE
                        .u_GA_SFU_PE.u_GA_PE_Outbuffer.ga_pe_outbuffer_rd_tag;
                end
            end
        end
    endgenerate

    initial begin : rq_num_probe_init
        rq_num_probe_enabled =
            $test$plusargs("REQUANT_GUARD_SFU_NUMERIC_PROBE");
        rq_num_cycle = 0;
        for (int sid = 0; sid < 2; sid++) begin
            rq_num_fd[sid] = 0;
            for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                rq_num_ag_transfer_pending[sid][ch].delete();
                rq_num_ag_linear_pending[sid][ch].delete();
                rq_num_req_id_pending[sid][ch].delete();
                rq_num_req_transfer_pending[sid][ch].delete();
                rq_num_req_linear_pending[sid][ch].delete();
                rq_num_req_post_pending[sid][ch].delete();
                rq_num_req_sequence[sid][ch] = 0;
                rq_num_wdata_sequence[sid][ch] = 0;
            end
        end
        if (rq_num_probe_enabled) begin
            rq_num_mkdir_status =
                $system("mkdir -p sim_results/requant_guard_sfu_numeric_probe");
            for (int sid = 0; sid < 2; sid++) begin
                rq_num_fd[sid] = $fopen(
                    $sformatf(
                        "sim_results/requant_guard_sfu_numeric_probe/slice%02d.log",
                        sid
                    ),
                    "w"
                );
                if (rq_num_fd[sid] == 0)
                    $error(
                        "REQUANT_GUARD_SFU_NUMERIC_PROBE cannot open slice%0d",
                        sid
                    );
                else
                    $fdisplay(
                        rq_num_fd[sid],
                        "# guard-only SFU numeric capture-edge observer v1"
                    );
            end
        end
    end

    always @(posedge u_NDP_Top_new.clk_sg or
             negedge u_NDP_Top_new.rst_n_sg) begin : rq_num_probe_sample
        if (!u_NDP_Top_new.rst_n_sg) begin
            rq_num_cycle = 0;
        end else if (rq_num_probe_enabled) begin
            rq_num_cycle++;
            for (int sid = 0; sid < 2; sid++) begin
                for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++) begin
                    if (rq_num_mse4_ag_wr_hs[sid][ch] &&
                        rq_num_mse4_ag_bp_pre_barrier[sid]) begin
                        rq_num_ag_transfer_pending[sid][ch].push_back(
                            rq_num_mse4_transfer_addr_nooff[sid]
                        );
                        rq_num_ag_linear_pending[sid][ch].push_back(
                            rq_num_mse4_transfer_addr_nooff[sid] +
                            rq_num_mse4_stream_base_word[sid]
                        );
                    end
                    if (local_req_hs[0][sid][4][ch]) begin
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] transfer_addr;
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] linear_addr;
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] post_addr;
                        integer metadata_valid;
                        integer req_id;
                        req_id = rq_num_req_sequence[sid][ch];
                        rq_num_req_sequence[sid][ch]++;
                        post_addr =
                            return_obs_mse4_local_req_addr_mon[0][sid][ch];
                        metadata_valid = (
                            rq_num_ag_transfer_pending[sid][ch].size() != 0 &&
                            rq_num_ag_linear_pending[sid][ch].size() != 0
                        );
                        if (metadata_valid) begin
                            transfer_addr =
                                rq_num_ag_transfer_pending[sid][ch].pop_front();
                            linear_addr =
                                rq_num_ag_linear_pending[sid][ch].pop_front();
                        end else begin
                            transfer_addr = 'b0;
                            linear_addr = 'b0;
                        end
                        rq_num_req_id_pending[sid][ch].push_back(req_id);
                        rq_num_req_transfer_pending[sid][ch].push_back(
                            transfer_addr
                        );
                        rq_num_req_linear_pending[sid][ch].push_back(
                            linear_addr
                        );
                        rq_num_req_post_pending[sid][ch].push_back(post_addr);
                        $fdisplay(
                            rq_num_fd[sid],
                            "GUARD_PATH boundary=MSE4_REQ cycle=%0d slice=%0d ch=%0d witness=accepted_request req_txn_id=%0d metadata_valid=%0d transfer_addr=0x%0h linear_addr=0x%0h post_remap_addr=0x%0h",
                            rq_num_cycle, sid, ch, req_id, metadata_valid,
                            transfer_addr, linear_addr, post_addr
                        );
                    end
                    if (local_wdata_hs[0][sid][4][ch]) begin
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] transfer_addr;
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] linear_addr;
                        logic [`MSE_MEM_REQ_ADDR_WIDTH-1:0] post_addr;
                        integer paired_req_valid;
                        integer paired_req_id;
                        integer wdata_id;
                        wdata_id = rq_num_wdata_sequence[sid][ch];
                        rq_num_wdata_sequence[sid][ch]++;
                        paired_req_valid = (
                            rq_num_req_id_pending[sid][ch].size() != 0 &&
                            rq_num_req_transfer_pending[sid][ch].size() != 0 &&
                            rq_num_req_linear_pending[sid][ch].size() != 0 &&
                            rq_num_req_post_pending[sid][ch].size() != 0
                        );
                        if (paired_req_valid) begin
                            paired_req_id =
                                rq_num_req_id_pending[sid][ch].pop_front();
                            transfer_addr =
                                rq_num_req_transfer_pending[sid][ch].pop_front();
                            linear_addr =
                                rq_num_req_linear_pending[sid][ch].pop_front();
                            post_addr =
                                rq_num_req_post_pending[sid][ch].pop_front();
                        end else begin
                            paired_req_id = -1;
                            transfer_addr = 'b0;
                            linear_addr = 'b0;
                            post_addr = 'b0;
                        end
                        $fdisplay(
                            rq_num_fd[sid],
                            "MSE4_WRITE | cycle=%0d slice=%0d local_stage=0 role=guard ch=%0d accepted=1 valid=1 ready=1 strobe=0xffff req_txn_id=%0d wdata_txn_id=%0d paired_req_valid=%0d transfer_addr=0x%0h linear_addr=0x%0h addr=0x%0h data=0x%032h",
                            rq_num_cycle, sid, ch, paired_req_id, wdata_id,
                            paired_req_valid, transfer_addr, linear_addr,
                            post_addr,
                            return_obs_mse4_local_wdata_mon[0][sid][ch]
                        );
                        $fdisplay(
                            rq_num_fd[sid],
                            "GUARD_PATH boundary=MSE4_WDATA cycle=%0d slice=%0d ch=%0d witness=accepted_wdata data=0x%032h",
                            rq_num_cycle, sid, ch,
                            return_obs_mse4_local_wdata_mon[0][sid][ch]
                        );
                    end
                end
                for (int row = 0; row < 4; row++)
                    for (int slot = 0; slot < 2; slot++) begin
                        if (rq_num_pe_selected_capture[sid][row][slot])
                            $fdisplay(
                                rq_num_fd[sid],
                                "GUARD_PATH boundary=PE_SELECTED_INPUT cycle=%0d slice=%0d pe=%0d%0d witness=input_side_enable data=0x%08h",
                                rq_num_cycle, sid, row, 2*slot+1,
                                rq_num_pe_selected_data[sid][row][slot]
                            );
                        if (rq_num_pre_input_capture[sid][row][slot])
                            $fdisplay(
                                rq_num_fd[sid],
                                "GUARD_PATH boundary=SFU_PREPROCESS_INPUT_CAPTURE cycle=%0d slice=%0d pe=%0d%0d witness=capture_source_at_posedge data=0x%08h",
                                rq_num_cycle, sid, row, 2*slot+1,
                                rq_num_pre_input_data[sid][row][slot]
                            );
                        if (rq_num_bst_capture[sid][row][slot])
                            $fdisplay(
                                rq_num_fd[sid],
                                "GUARD_PATH boundary=SFU_BST_RESULT_CAPTURE cycle=%0d slice=%0d pe=%0d%0d witness=registered_capture_source coeff_addr_next=0x%0h data=0x%08h",
                                rq_num_cycle, sid, row, 2*slot+1,
                                rq_num_bst_coeff_addr_next[sid][row][slot],
                                rq_num_bst_result_source[sid][row][slot]
                            );
                        if (rq_num_coeff_capture[sid][row][slot]) begin
                            $fdisplay(
                                rq_num_fd[sid],
                                "GUARD_PATH boundary=SFU_COEFF_CAPTURE cycle=%0d slice=%0d pe=%0d%0d witness=alu_capture_source coeff_addr=0x%0h slope=0x%08h intercept=0x%08h data=0x%08h",
                                rq_num_cycle, sid, row, 2*slot+1,
                                rq_num_coeff_addr[sid][row][slot],
                                rq_num_coeff_slope[sid][row][slot],
                                rq_num_coeff_intercept[sid][row][slot],
                                rq_num_coeff_preprocessed[sid][row][slot]
                            );
                            $fdisplay(
                                rq_num_fd[sid],
                                "GUARD_PATH boundary=SFU_ALU_INPUT_CAPTURE cycle=%0d slice=%0d pe=%0d%0d witness=alu_pipeline0_capture tag=0x%0h data1=0x%08h data2=0x%08h data=0x%08h",
                                rq_num_cycle, sid, row, 2*slot+1,
                                rq_num_alu_input_tag[sid][row][slot],
                                rq_num_alu_input1[sid][row][slot],
                                rq_num_alu_input2[sid][row][slot],
                                rq_num_alu_input0[sid][row][slot]
                            );
                        end
                        if (rq_num_normal_wr_hs[sid][row][slot]) begin
                            $fdisplay(
                                rq_num_fd[sid],
                                "GUARD_PATH boundary=SFU_ALU_RESULT_ACCEPTED cycle=%0d slice=%0d pe=%0d%0d witness=normal_outbuffer_accept tag=0x%0h data=0x%08h",
                                rq_num_cycle, sid, row, 2*slot+1,
                                rq_num_alu_result_tag[sid][row][slot],
                                rq_num_alu_result[sid][row][slot]
                            );
                            $fdisplay(
                                rq_num_fd[sid],
                                "GUARD_PATH boundary=SFU_POSTPROCESS_RESULT_ACCEPTED cycle=%0d slice=%0d pe=%0d%0d witness=normal_outbuffer_accept tag=0x%0h data=0x%08h",
                                rq_num_cycle, sid, row, 2*slot+1,
                                rq_num_alu_result_tag[sid][row][slot],
                                rq_num_postprocess_result[sid][row][slot]
                            );
                            $fdisplay(
                                rq_num_fd[sid],
                                "GUARD_PATH boundary=NORMAL_OUTBUFFER_INPUT_ACCEPTED cycle=%0d slice=%0d pe=%0d%0d witness=write_handshake tag=0x%0h data=0x%08h",
                                rq_num_cycle, sid, row, 2*slot+1,
                                rq_num_normal_wr_tag[sid][row][slot],
                                rq_num_postprocess_result[sid][row][slot]
                            );
                            $fdisplay(
                                rq_num_fd[sid],
                                "GUARD_PATH boundary=NORMAL_OUTBUFFER_WRITE_COMMIT cycle=%0d slice=%0d pe=%0d%0d witness=write_handshake tag=0x%0h data=0x%08h",
                                rq_num_cycle, sid, row, 2*slot+1,
                                rq_num_normal_wr_tag[sid][row][slot],
                                rq_num_normal_wr_data[sid][row][slot]
                            );
                        end
                        if (rq_num_normal_rd_hs[sid][row][slot])
                            $fdisplay(
                                rq_num_fd[sid],
                                "GUARD_PATH boundary=NORMAL_OUTPORT_ACCEPTED cycle=%0d slice=%0d pe=%0d%0d witness=read_handshake tag=0x%0h data=0x%08h",
                                rq_num_cycle, sid, row, 2*slot+1,
                                rq_num_normal_rd_tag[sid][row][slot],
                                rq_num_normal_rd_data[sid][row][slot]
                            );
                    end
                $fflush(rq_num_fd[sid]);
            end
        end
    end

    final begin : rq_num_probe_final
        if (rq_num_probe_enabled)
            for (int sid = 0; sid < 2; sid++)
                if (rq_num_fd[sid] != 0) begin
                    for (int ch = 0; ch < `MSE_REQ_CHL_NUM; ch++)
                        $fdisplay(
                            rq_num_fd[sid],
                            "PROBE_SUMMARY slice=%0d ch=%0d req_count=%0d wdata_count=%0d outstanding_req=%0d outstanding_ag=%0d",
                            sid, ch, rq_num_req_sequence[sid][ch],
                            rq_num_wdata_sequence[sid][ch],
                            rq_num_req_id_pending[sid][ch].size(),
                            rq_num_ag_transfer_pending[sid][ch].size()
                        );
                    $fclose(rq_num_fd[sid]);
                end
    end
"""


def _build_tree(package: Path, sources: dict[str, Any]) -> dict[str, Any]:
    package.mkdir(parents=True)
    frozen = FROZEN_ATOMIC_PACKAGE
    runtime = package / "workload/runtime"
    payloads = runtime / "payloads"
    cfg_pkg = payloads / "cfg_pkg"
    validation = package / "validation"

    _copy(
        ROOT / "tools/requant_atomic_server_runtime.py",
        package / "package_tools/requant_atomic_server_runtime.py",
    )
    _copy(
        ROOT / "tools/requant_node0001_server_runtime.py",
        package / "package_tools/requant_node0001_server_runtime.py",
    )
    base._write_lf(
        package / "tb_probe" / OBSERVER_TAIL_NAME,
        _sfu_numeric_observer_tail().lstrip(),
    )

    for slice_id in (0, 1):
        _copy(
            frozen / f"golden/guard_slice{slice_id:02d}_128b.txt",
            package / f"golden/guard_slice{slice_id:02d}_128b.txt",
        )
        _copy(
            frozen
            / "workload/runtime/payloads/inputs/op_w0_s00_guard"
            / f"slice{slice_id:02d}/matrix_A_linearized_128bit.txt",
            payloads
            / "inputs/op_w0_s00_guard"
            / f"slice{slice_id:02d}/matrix_A_linearized_128bit.txt",
        )
    guard_cfg_name = (
        "op_w0_s00_guard_resnet50_requant_guard_node0001_bitstream_128b.bin"
    )
    _copy(
        frozen / "workload/runtime/payloads/cfg_pkg" / guard_cfg_name,
        cfg_pkg / guard_cfg_name,
    )
    _copy(
        frozen / "workload/runtime/payloads/cfg_pkg/RequantGuard.txt",
        cfg_pkg / "RequantGuard.txt",
    )
    base._write_lf(payloads / "execplan.txt", _guard_execplan())

    sca = json.loads(
        (frozen / "workload/runtime/sca_cfg.json").read_text(encoding="utf-8")
    )
    sca.pop("op_w0_s00_round_config")
    sca["Exec_Length"] = 4
    sca["Repeat_Num"] = 1
    old_name = "rq_node0001_atomic2_stock_v2"
    for value in sca.values():
        if isinstance(value, dict) and isinstance(value.get("path"), str):
            value["path"] = value["path"].replace(old_name, INSTALL_NAME)
    _write_json(runtime / "sca_cfg.json", sca)
    sca_d = json.loads(
        (frozen / "workload/runtime/sca_cfg_D.json").read_text(encoding="utf-8")
    )
    sca_d = {
        key: value for key, value in sca_d.items() if "_guard_" in key
    }
    _write_json(runtime / "sca_cfg_D.json", sca_d)

    _copy(
        frozen / "validation/guard.json",
        validation / "guard.json",
    )
    shutil.copytree(
        frozen / "validation/native/op_w0_s00_guard",
        validation / "native/op_w0_s00_guard",
    )
    for name in (
        "generation_receipt.json",
        "manifest.json",
        "local_contract_report.json",
        "semantic_contract.json",
    ):
        _copy(frozen / "validation" / name, validation / name)
    _write_json(validation / "expected_mse4_writes.json", _guard_expected_writes())
    _write_json(validation / "lifecycle_contract.json", _lifecycle_contract())
    _write_json(validation / "diagnostic_profile.json", _diagnostic_profile())
    _write_json(
        validation / "guard_only_provenance.json",
        {
            "schema": "requant-node0001-guard-only-sfu-numeric-provenance-v1",
            "status": "frozen_guard_semantics_reused_exactly",
            "source_atomic_package_zip_sha256": FROZEN_ATOMIC_ZIP_SHA256,
            "supersedes_failed_package": {
                "install_name": "rq_node0001_guardonly_stock_v1",
                "failure_class": (
                    "SERVER_TEST_INFRASTRUCTURE_TB_PROBE_TAIL_NAME_MISMATCH"
                ),
                "compile_started": False,
                "simulation_started": False,
            },
            "unpublished_local_predecessor": {
                "install_name": "rq_node0001_guardonly_stock_v2",
                "reason": (
                    "builder self-test isolation changed after materialization; "
                    "identity was retired without server delivery"
                ),
            },
            "supersedes_xmr_failed_package": {
                "install_name": "rq_node0001_guardonly_stock_v3",
                "failure_class": (
                    "SERVER_TEST_INFRASTRUCTURE_OBSERVER_"
                    "XMR_ELABORATION_FAILURE"
                ),
                "compile_started": True,
                "simulation_started": False,
                "counts_as_dynamic_attempt": False,
            },
            "direct_predecessor": {
                "install_name": "rq_node0001_guardonly_sfu_ready_stock_v1",
                "package_zip_sha256": PREDECESSOR_PACKAGE_ZIP_SHA256,
                "return_analysis": (
                    "server_returns/"
                    "rq_node0001_guardonly_sfu_ready_stock_v1_"
                    "return_analysis_20260727.json"
                ),
                "return_analysis_sha256": (
                    AUTHORITATIVE_PREDECESSOR_ANALYSIS_SHA256
                ),
                "authoritative_first_divergence": (
                    "SFU_PREPROCESS0_VALID_PROVEN__"
                    "NUMERIC_PIPELINE_UNOBSERVED__MSE4_ZERO"
                ),
                "evidence_state": (
                    "BOUNDED_UNOBSERVED_NUMERIC_INTERVAL_WITH_DOWNSTREAM_ZERO"
                ),
            },
            "semantic_change": False,
            "diagnostic_scope_change": (
                "readiness/change-only status probe replaced by capture-edge "
                "witnesses for actual SFU/BST/coeff/ALU/postprocess/normal-"
                "outbuffer numeric payloads; one input-side checkpoint and "
                "decoupled MSE4 evidence retained"
            ),
            "frozen_assets": sources,
            "round_only_enabled": False,
            "alias_lifetime_enabled": False,
            "functional_rtl_modified": False,
        },
    )
    _write_json(
        validation / "static_configuration_intent.json",
        _static_configuration_intent(),
    )
    _write_json(
        validation / "address_domain_contract.json",
        {
            "schema": "requant-guard-only-address-domain-contract-v1",
            "linear_expected_field": "word_address_128b",
            "linear_observed_field": "linear_addr",
            "linear_observed_rtl": (
                "WR_Memory_AG.transfer_addr_nooff plus "
                "mse_stream_base_addr>>DDR_ADDR_OFFSET_WIDTH"
            ),
            "transfer_offset_observed_field": "transfer_addr",
            "post_remap_observed_field": "post_remap_addr",
            "post_remap_observed_rtl": "accepted local_req_addr",
            "remap_rtl": "WR_Memory_AG.sv:302-351",
            "direct_cross_domain_comparison_forbidden": True,
        },
    )
    _write_json(
        validation / "semantic_freeze_sfu_ready_v1_to_sfu_numeric_v1.json",
        _semantic_freeze_receipt(package),
    )

    run_script = base._run_script().replace(
        "+REQUANT_ATOMIC_PROBE", "+REQUANT_GUARD_SFU_NUMERIC_PROBE"
    )
    base._write_lf(package / "PREPARE_AND_RUN.sh", run_script)
    base._write_lf(
        package / "README.md",
        (
            "# Requant node0001 guard-only SFU numeric diagnostic v1\n\n"
            "Run exactly one command from the extracted package directory:\n\n"
            "```bash\n"
            "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX\n"
            "```\n\n"
            "This is a FIRST_DYNAMIC guard-path capture-edge-safe SFU numeric "
            "diagnostic only. "
            "It does not "
            "count as node0001 E4/E5, carries no rtl/ files, and leaves "
            "round-only and alias-lifetime disabled.\n"
        ),
    )

    records = base._records(package, exclude_manifest=True)
    manifest = {
        "schema": "requant-node0001-guard-only-sfu-numeric-stockrtl-package-v1",
        "install_name": INSTALL_NAME,
        "run_kind": "FIRST_DYNAMIC_DIAGNOSTIC",
        "dynamic_baseline": "NO_DYNAMIC_BASELINE",
        "candidate_release": False,
        "counts_as_node0001_e4": False,
        "counts_as_node0001_e5": False,
        "functional_rtl_file_count": 0,
        "tb_or_rtl_driver_modification": False,
        "observer_mode": "transactional_read_only_non_rtl_tail",
        "observer_capture_mode": "capture_edge_payload_witness",
        "enabled_atomic_followup": "guard-only",
        "disabled_atomic_followups": ["round-only", "alias-lifetime"],
        "rule_ids": [
            "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
            "CDA-SERVER-ONE-COMMAND-001",
            "CDA-SERVER-RETURN-RECEIPT-001",
            "CDA-SERVER-NO-DYNAMIC-BASELINE-001",
            "CDA-SERVER-OBSERVER-XMR-ELABORATION-CONSTANT-001",
            "CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001",
            "CDA-SERVER-OBSERVER-EVIDENCE-DOMINANCE-001",
            "CDA-SERVER-OBSERVER-CAPTURE-EDGE-WITNESS-001",
            "CDA-REQUANT-ATOMIC-SINGLE-OCCURRENCE-001",
            "CDA-REQUANT-ATOMIC-STOCK-TB-MASK-COMPAT-001",
            "CDA-REQUANT-GUARD-DIAGNOSTIC-EVIDENCE-BOUNDARY-001",
            "CDA-REQUANT-GUARD-CHECKPOINT-ROUTING-001",
            "CDA-REQUANT-GUARD-V4-DYNAMIC-EVIDENCE-001",
            "CDA-REQUANT-DIRECTSIG-V1-DYNAMIC-EVIDENCE-001",
            "CDA-REQUANT-SFU-READY-V1-DYNAMIC-EVIDENCE-001",
        ],
        "payload_tree_sha256": base._tree_sha256(records),
        "files": records,
    }
    _write_json(package / base.MANIFEST_NAME, manifest)
    preflight = base.preflight_package(package, INSTALL_NAME)
    return {"manifest": manifest, "preflight": preflight}


def _validate_probe_transaction(package: Path) -> dict[str, Any]:
    zip_path = package.with_suffix(".zip")
    with tempfile.TemporaryDirectory(prefix="rq-guard-probe-install-") as temporary:
        root = Path(temporary)
        extract_root = root / "extract"
        extract_root.mkdir()
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_root)
        fresh_package = extract_root / INSTALL_NAME
        package_before = base._records(fresh_package)
        ndp_root = root / "NDP_copy_mock"
        evidence = root / "evidence"
        ndp_root.mkdir()
        evidence.mkdir()
        observer = ndp_root / "native_return_observer.svh"
        _copy(ROOT / "NDP_copy01/native_return_observer.svh", observer)
        observer_preimage = observer.read_bytes()
        common_tool = (
            fresh_package
            / "package_tools/requant_node0001_server_runtime.py"
        )
        runtime_tool = (
            fresh_package
            / "package_tools/requant_atomic_server_runtime.py"
        )
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        bootstrap_output = root / "package_preflight.json"
        bootstrap_completed = subprocess.run(
            [
                sys.executable,
                str(runtime_tool),
                "preflight-package",
                "--package-root",
                str(fresh_package),
                "--install-name",
                INSTALL_NAME,
                "--output",
                str(bootstrap_output),
            ],
            cwd=fresh_package,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        if bootstrap_completed.returncode != 0:
            raise GuardOnlyPackageError(
                "fresh-extracted packaged runtime preflight failed: "
                + bootstrap_completed.stderr.strip()
            )
        bootstrap_report = json.loads(
            bootstrap_output.read_text(encoding="utf-8")
        )
        if bootstrap_report.get("status") != "package_preflight_passed":
            raise GuardOnlyPackageError(
                "fresh-extracted runtime did not pass package preflight"
            )

        def run(*arguments: str) -> subprocess.CompletedProcess[str]:
            completed = subprocess.run(
                [sys.executable, str(common_tool), *arguments],
                cwd=fresh_package,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
            if completed.returncode != 0:
                raise GuardOnlyPackageError(
                    "fresh-extracted probe transaction failed: "
                    f"{' '.join(arguments[:1])}: {completed.stderr.strip()}"
                )
            return completed

        run(
            "install-probe",
            "--ndp-root",
            str(ndp_root),
            "--package-root",
            str(fresh_package),
            "--evidence-root",
            str(evidence),
        )
        install_receipt = json.loads(
            (evidence / "tb_probe_install_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        installed_sha256 = _sha256(observer)
        run(
            "verify-probe-installed",
            "--ndp-root",
            str(ndp_root),
            "--evidence-root",
            str(evidence),
            "--output",
            str(evidence / "tb_probe_precompile_receipt.json"),
        )
        verify_receipt = json.loads(
            (evidence / "tb_probe_precompile_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        run(
            "restore-probe",
            "--ndp-root",
            str(ndp_root),
            "--evidence-root",
            str(evidence),
        )
        if observer.read_bytes() != observer_preimage:
            raise GuardOnlyPackageError(
                "probe transaction did not restore observer byte-exact"
            )
        final_receipt = json.loads(
            (evidence / "tb_probe_install_receipt.json").read_text(
                encoding="utf-8"
            )
        )
        package_after = base._records(fresh_package)
        if package_before != package_after:
            raise GuardOnlyPackageError(
                "probe transaction changed the fresh-extracted package tree"
            )
        return {
            "schema": "requant-guard-only-probe-transaction-receipt-v1",
            "status": "pass",
            "fresh_zip_extraction": True,
            "actual_packaged_installer_entry": (
                "package_tools/requant_node0001_server_runtime.py install-probe"
            ),
            "required_tail_basename": OBSERVER_TAIL_NAME,
            "tail_found_and_installed": True,
            "install_receipt_status": install_receipt["status"],
            "installed_sha256": installed_sha256,
            "precompile_verify_passed": True,
            "xmr_elaboration_gate": verify_receipt["xmr_elaboration_gate"],
            "restore_receipt_status": final_receipt["status"],
            "observer_restored_byte_exact": True,
            "package_exact_tree_unchanged": True,
            "bootstrap_immutability": {
                "schema": "requant-guard-sfu-ready-bootstrap-immutability-v1",
                "rule_id": "CDA-SERVER-PACKAGE-BOOTSTRAP-IMMUTABILITY-001",
                "status": "pass",
                "entry": (
                    "package_tools/requant_atomic_server_runtime.py "
                    "preflight-package"
                ),
                "fresh_zip_extraction": True,
                "preflight_output_outside_package": True,
                "python_dont_write_bytecode_environment": True,
                "python_dont_write_bytecode_runtime": True,
                "pycache_or_pyc_allowlisted": False,
                "package_file_count_before": len(package_before),
                "package_file_count_after": len(package_after),
                "package_size_bytes_before": sum(
                    item["size_bytes"] for item in package_before.values()
                ),
                "package_size_bytes_after": sum(
                    item["size_bytes"] for item in package_after.values()
                ),
                "package_tree_sha256_before": base._tree_sha256(
                    package_before
                ),
                "package_tree_sha256_after": base._tree_sha256(
                    package_after
                ),
                "exact_path_size_sha_unchanged": True,
            },
        }


def build_package(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    output = output.resolve()
    if output.name != INSTALL_NAME:
        raise GuardOnlyPackageError(
            f"output directory name must be {INSTALL_NAME}"
        )
    previous_install_name = base.INSTALL_NAME
    base.INSTALL_NAME = INSTALL_NAME
    try:
        base._fresh_final_targets(output)
        sources = _verify_frozen_sources()
        with tempfile.TemporaryDirectory(
            prefix="rq-guard-pkg-a-"
        ) as left_parent, tempfile.TemporaryDirectory(
            prefix="rq-guard-pkg-b-"
        ) as right_parent:
            left = Path(left_parent) / INSTALL_NAME
            right = Path(right_parent) / INSTALL_NAME
            left_report = _build_tree(left, sources)
            _build_tree(right, sources)
            left_zip, left_sha = base._zip_tree(left)
            right_zip, right_sha = base._zip_tree(right)
            if (
                left_sha != right_sha
                or left_zip.read_bytes() != right_zip.read_bytes()
                or base._records(left) != base._records(right)
            ):
                raise GuardOnlyPackageError(
                    "two fresh guard-only package builds differ"
                )
            shutil.copytree(right, output)
            shutil.copyfile(right_zip, output.with_suffix(".zip"))
            shutil.copyfile(
                right_zip.with_suffix(".zip.sha256"),
                output.with_suffix(".zip.sha256"),
            )
        validation = base._validate_zip(output)
        probe_transaction = _validate_probe_transaction(output)
        bootstrap = probe_transaction["bootstrap_immutability"]
        report = {
            "package": output.as_posix(),
            "zip": output.with_suffix(".zip").as_posix(),
            "zip_size_bytes": output.with_suffix(".zip").stat().st_size,
            "zip_sha256": validation["zip_sha256"],
            "sidecar": output.with_suffix(".zip.sha256").as_posix(),
            "payload_tree_sha256": left_report["manifest"]["payload_tree_sha256"],
            "preflight": validation,
            "bootstrap_immutability": bootstrap,
            "probe_transaction": probe_transaction,
            "deterministic_package_build_count": 2,
            "deterministic_zip_byte_identical": True,
            "release_gate": {
                "candidate_release": False,
                "counts_as_node0001_e4": False,
                "counts_as_node0001_e5": False,
                "remaining_blockers": [
                    "B_REQUANT_SERVER_E4_E5",
                    "B_REQUANT_GUARD_DYNAMIC_DATA_PATH",
                ],
            },
            "server_command": (
                "bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX"
            ),
            "expected_return": f"{INSTALL_NAME}_return.zip",
        }
        receipt_path = output.with_name(f"{output.name}_validation.json")
        report["validation_receipt"] = receipt_path.as_posix()
        _write_json(receipt_path, report)
        return report
    finally:
        base.INSTALL_NAME = previous_install_name


def validate_package(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    previous_install_name = base.INSTALL_NAME
    base.INSTALL_NAME = INSTALL_NAME
    try:
        report = base._validate_zip(output.resolve())
        report["probe_transaction"] = _validate_probe_transaction(
            output.resolve()
        )
        report["bootstrap_immutability"] = report["probe_transaction"][
            "bootstrap_immutability"
        ]
        return report
    finally:
        base.INSTALL_NAME = previous_install_name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        report = (
            validate_package(args.output)
            if args.validate_only
            else build_package(args.output)
        )
    except Exception as exc:
        print(f"Requant guard-only package build failed: {exc}")
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
