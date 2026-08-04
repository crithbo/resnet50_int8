from __future__ import annotations

import importlib.util
import json
import sys
import types
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .hashing import canonical_json_bytes, sha256_bytes, sha256_file


SCHEMA = "resnet50-gap-int32-mac-bypass-local-contract-v1"
CONTRACT_PATH = "contracts/operator_config/gap_int32_mac_bypass_v1.json"
CGRA_REPORT_PATH = (
    "artifacts/operator_config_validation/gap-int32-mac-bypass-v1/"
    "cgra_sim_reference.json"
)
LOCAL_E2_REPORT_PATH = (
    "artifacts/operator_config_validation/gap-int32-mac-bypass-v1/"
    "local-e2/LOCAL_E2_REPORT.json"
)
MATERIALIZED_CONFIG_ROOT = "configs/gap_int32_mac_bypass_v1"
RULE_PATH = ".agents/rules/GAP_int32_mac_bypass_rules.md"
LOWERING_BUNDLE_PATH = "contracts/resnet50_r5_lowering_bundle.json"
W3_INPUT_PATH = (
    "artifacts/w3/golden_batch16/tensors/"
    "tensor-55360f2ec724d2f3.npy"
)
W3_EXPECTED_PATH = (
    "artifacts/w3/subop_batch16/tensors/"
    "tensor-internal-node-0071-sum.npy"
)
REPOSITORY_LOCK_PATH = "repos.lock.json"

SLICE_COUNT = 16
CHANNEL_BLOCKS_PER_SLICE = 256
CHANNELS_PER_BLOCK = 8
LOGICAL_LEAF_COUNT = 49
PHYSICAL_LEAF_COUNT = 64
INPUT_BLOCK_BYTES = LOGICAL_LEAF_COUNT * CHANNELS_PER_BLOCK
INPUT_LOGICAL_BYTES = CHANNEL_BLOCKS_PER_SLICE * INPUT_BLOCK_BYTES
STAGE1_TRANSACTION_BYTES = CHANNELS_PER_BLOCK
SCRATCH_TRANSACTION_BYTES = CHANNELS_PER_BLOCK * 4
FINAL_LINES_PER_SLICE = 512
LOGICAL_WIDTHS = (49, 25, 13, 7, 4, 2, 1)
PHYSICAL_WIDTHS = (64, 32, 16, 8, 4, 2, 1)

RULE_IDS = (
    "CDA-GAP-INT32MAC-NONTRANSOUT-001",
    "CDA-GAP-INT32MAC-DUAL-INPUT-001",
    "CDA-GAP-INT32MAC-NORMAL-FIFO-001",
    "CDA-GAP-INT32MAC-TREE-001",
    "CDA-GAP-INT32MAC-STAGE-MEMORY-001",
    "CDA-GAP-REPAIR-STRUCTURE-NOT-SEMANTICS-001",
    "CDA-GAP-REPAIR-E2-CLAIM-BOUNDARY-001",
)

RTL_BINDINGS = (
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_Inport/GA_Inport.sv",
    "NDP_copy01/rtl/Slice/General_Array/GA_Inport/GA_Inport_Connect.sv",
    (
        "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Buffer_Manager_Cluster_Connect.sv"
    ),
    "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer.sv",
    (
        "NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/"
        "Memory_Req_Manager.sv"
    ),
    (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/RD_Memory_AG.sv"
    ),
    (
        "NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/"
        "Memory_RD_Stream_Engine/WR_Buffer_AG.sv"
    ),
)
TOOLCHAIN_BINDINGS = (
    "ndp-sim/bitstream/config/stream.py",
)


class GapInt32MacBypassError(ValueError):
    pass


def load_locked_cgra_sum(project_root: Path) -> type:
    """Load SUM without executing CGRA_SIM's torch-dependent package exports."""
    root = project_root.resolve()
    package_paths = {
        "cgra_python": root / "CGRA_SIM/cgra_python",
        "cgra_python.op_lib": root / "CGRA_SIM/cgra_python/op_lib",
        "cgra_python.op_lib.reduce_op": (
            root / "CGRA_SIM/cgra_python/op_lib/reduce_op"
        ),
    }
    for name, path in package_paths.items():
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module
    for name, relative in (
        ("cgra_python.op_lib.base_op", "CGRA_SIM/cgra_python/op_lib/base_op.py"),
        ("cgra_python.op_lib.stream", "CGRA_SIM/cgra_python/op_lib/stream.py"),
        (
            "cgra_python.op_lib.reduce_op.sum",
            "CGRA_SIM/cgra_python/op_lib/reduce_op/sum.py",
        ),
    ):
        spec = importlib.util.spec_from_file_location(name, root / relative)
        if spec is None or spec.loader is None:
            raise GapInt32MacBypassError(
                f"cannot load locked CGRA source: {relative}"
            )
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    return sys.modules["cgra_python.op_lib.reduce_op.sum"].SUM


@dataclass(frozen=True)
class Region:
    name: str
    base: int
    size: int
    dtype: str
    physical_width: int
    logical_width: int

    @property
    def end(self) -> int:
        return self.base + self.size

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "relative_base_bytes": self.base,
            "relative_end_exclusive_bytes": self.end,
            "size_bytes": self.size,
            "dtype": self.dtype,
            "layout": (
                "[c8_block][physical_reduction_index][8_channel_lanes]"
            ),
            "c8_block_count": CHANNEL_BLOCKS_PER_SLICE,
            "physical_width": self.physical_width,
            "logical_width": self.logical_width,
            "transaction_bytes": (
                STAGE1_TRANSACTION_BYTES
                if self.name == "input_uint8_c8_hw"
                else SCRATCH_TRANSACTION_BYTES
            ),
        }


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def _binding(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file():
        raise GapInt32MacBypassError(f"required evidence is missing: {relative}")
    return {
        "path": relative,
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def _address_digest(records: Iterable[tuple[int, ...]]) -> str:
    payload = [list(record) for record in records]
    return sha256_bytes(canonical_json_bytes(payload))


def relative_regions() -> tuple[Region, ...]:
    # Padding substitutes leaves 49..63 after the memory return.  Reads for
    # the last C8 block therefore require an explicit 128-byte guard.
    input_allocation = _align_up(
        (CHANNEL_BLOCKS_PER_SLICE - 1) * INPUT_BLOCK_BYTES
        + PHYSICAL_LEAF_COUNT * CHANNELS_PER_BLOCK,
        16,
    )
    regions: list[Region] = [
        Region(
            name="input_uint8_c8_hw",
            base=0,
            size=input_allocation,
            dtype="uint8",
            physical_width=PHYSICAL_LEAF_COUNT,
            logical_width=LOGICAL_LEAF_COUNT,
        )
    ]
    cursor = _align_up(input_allocation, 4096)
    for stage_index, (physical_width, logical_width) in enumerate(
        zip(PHYSICAL_WIDTHS[1:], LOGICAL_WIDTHS[1:]),
        start=1,
    ):
        size = (
            CHANNEL_BLOCKS_PER_SLICE
            * physical_width
            * SCRATCH_TRANSACTION_BYTES
        )
        name = (
            "final_d_int32"
            if stage_index == 6
            else f"scratch_s{stage_index}_int32"
        )
        regions.append(
            Region(
                name=name,
                base=cursor,
                size=size,
                dtype="int32",
                physical_width=physical_width,
                logical_width=logical_width,
            )
        )
        cursor += size
    return tuple(regions)


def _terminal_tag(block: int, output_index: int, output_width: int) -> tuple[int, int]:
    if output_index != output_width - 1:
        return 0, 15
    return 1, 0 if block == CHANNEL_BLOCKS_PER_SLICE - 1 else 1


def stage_pair_records(stage_index: int) -> list[dict[str, Any]]:
    if stage_index < 1 or stage_index > 6:
        raise GapInt32MacBypassError("stage_index must be in [1, 6]")
    regions = relative_regions()
    previous = regions[stage_index - 1]
    output = regions[stage_index]
    output_width = output.physical_width
    records: list[dict[str, Any]] = []
    for block in range(CHANNEL_BLOCKS_PER_SLICE):
        for output_index in range(output_width):
            left_index = output_index * 2
            right_index = left_index + 1
            if stage_index == 1:
                a_addr = previous.base + block * INPUT_BLOCK_BYTES + left_index * 8
                c_addr = previous.base + block * INPUT_BLOCK_BYTES + right_index * 8
                transaction_bytes = STAGE1_TRANSACTION_BYTES
                buffer_row = (output_index // 4) % 4
                byte_slot = output_index % 4
                buffer_columns = [
                    byte_slot + lane * 4 for lane in range(CHANNELS_PER_BLOCK)
                ]
                a_zero = left_index >= LOGICAL_LEAF_COUNT
                c_zero = right_index >= LOGICAL_LEAF_COUNT
            else:
                a_addr = (
                    previous.base
                    + (block * previous.physical_width + left_index)
                    * SCRATCH_TRANSACTION_BYTES
                )
                c_addr = (
                    previous.base
                    + (block * previous.physical_width + right_index)
                    * SCRATCH_TRANSACTION_BYTES
                )
                transaction_bytes = SCRATCH_TRANSACTION_BYTES
                buffer_row = output_index % 4
                byte_slot = None
                buffer_columns = list(range(SCRATCH_TRANSACTION_BYTES))
                a_zero = left_index >= previous.logical_width
                c_zero = right_index >= previous.logical_width
            last, last_index = _terminal_tag(block, output_index, output_width)
            records.append(
                {
                    "ordinal": len(records),
                    "c8_block": block,
                    "output_index": output_index,
                    "left_index": left_index,
                    "right_index": right_index,
                    "a_relative_address": a_addr,
                    "c_relative_address": c_addr,
                    "transaction_bytes": transaction_bytes,
                    "a_padding_substitute_zero": a_zero,
                    "c_padding_substitute_zero": c_zero,
                    "buffer_row": buffer_row,
                    "buffer_byte_slot": byte_slot,
                    "buffer_columns": buffer_columns,
                    "a_tag": [last, last_index],
                    "c_tag": [last, last_index],
                }
            )
    return records


def stage_output_records(stage_index: int) -> list[dict[str, Any]]:
    if stage_index < 1 or stage_index > 6:
        raise GapInt32MacBypassError("stage_index must be in [1, 6]")
    region = relative_regions()[stage_index]
    records: list[dict[str, Any]] = []
    for block in range(CHANNEL_BLOCKS_PER_SLICE):
        for output_index in range(region.physical_width):
            address = (
                region.base
                + (block * region.physical_width + output_index)
                * SCRATCH_TRANSACTION_BYTES
            )
            last, last_index = _terminal_tag(
                block, output_index, region.physical_width
            )
            records.append(
                {
                    "ordinal": len(records),
                    "c8_block": block,
                    "output_index": output_index,
                    "relative_address": address,
                    "transaction_bytes": SCRATCH_TRANSACTION_BYTES,
                    "tag": [last, last_index],
                    "is_logical_value": output_index < region.logical_width,
                    "is_proven_zero_tail": output_index >= region.logical_width,
                }
            )
    return records


def _stage_summary(stage_index: int) -> dict[str, Any]:
    regions = relative_regions()
    previous = regions[stage_index - 1]
    output = regions[stage_index]
    pairs = stage_pair_records(stage_index)
    writes = stage_output_records(stage_index)
    a_records = [
        (
            item["ordinal"],
            item["c8_block"],
            item["output_index"],
            item["left_index"],
            item["a_relative_address"],
            item["transaction_bytes"],
            int(item["a_padding_substitute_zero"]),
            *item["a_tag"],
        )
        for item in pairs
    ]
    c_records = [
        (
            item["ordinal"],
            item["c8_block"],
            item["output_index"],
            item["right_index"],
            item["c_relative_address"],
            item["transaction_bytes"],
            int(item["c_padding_substitute_zero"]),
            *item["c_tag"],
        )
        for item in pairs
    ]
    pair_records = [
        (
            item["ordinal"],
            item["a_relative_address"],
            item["c_relative_address"],
            *item["a_tag"],
            *item["c_tag"],
        )
        for item in pairs
    ]
    write_records = [
        (
            item["ordinal"],
            item["relative_address"],
            item["transaction_bytes"],
            *item["tag"],
            int(item["is_proven_zero_tail"]),
        )
        for item in writes
    ]
    expected_previous_indices = list(range(previous.physical_width))
    full_pair_coverage = all(
        sorted(
            [
                index
                for item in pairs
                if item["c8_block"] == block
                for index in (item["left_index"], item["right_index"])
            ]
        )
        == expected_previous_indices
        for block in range(CHANNEL_BLOCKS_PER_SLICE)
    )
    output_addresses = [item["relative_address"] for item in writes]
    terminal_pairs = [
        item
        for item in pairs
        if item["a_tag"] == [1, 0] and item["c_tag"] == [1, 0]
    ]
    local_end_pairs = [
        item
        for item in pairs
        if item["a_tag"] == [1, 1] and item["c_tag"] == [1, 1]
    ]
    return {
        "stage_index": stage_index,
        "equation": "D=int32(A*1+C)",
        "opcode": {"name": "int32_mac", "decimal": 14, "transout": False},
        "input_region": previous.name,
        "output_region": output.name,
        "input_dtype": previous.dtype,
        "output_dtype": "int32",
        "logical_width_transition": [
            LOGICAL_WIDTHS[stage_index - 1],
            LOGICAL_WIDTHS[stage_index],
        ],
        "physical_width_transition": [
            PHYSICAL_WIDTHS[stage_index - 1],
            PHYSICAL_WIDTHS[stage_index],
        ],
        "a_stream": {
            "target": "A",
            "physical_read_stream": "READ_STREAM0",
            "buffer": 0,
            "ga_group": 0,
            "transaction_count_per_slice": len(a_records),
            "transaction_bytes": pairs[0]["transaction_bytes"],
            "ordered_occurrence_sha256": _address_digest(a_records),
        },
        "c_stream": {
            "target": "C",
            "physical_read_stream": "READ_STREAM3",
            "buffer": 4,
            "ga_group": 2,
            "transaction_count_per_slice": len(c_records),
            "transaction_bytes": pairs[0]["transaction_bytes"],
            "ordered_occurrence_sha256": _address_digest(c_records),
        },
        "ordered_pair_sha256": _address_digest(pair_records),
        "writeback": {
            "target": "D",
            "physical_write_stream": "WRITE_STREAM0",
            "buffer": 5,
            "transaction_count_per_slice": len(write_records),
            "transaction_bytes": SCRATCH_TRANSACTION_BYTES,
            "ordered_occurrence_sha256": _address_digest(write_records),
        },
        "coverage": {
            "all_256_c8_blocks": len(
                {item["c8_block"] for item in pairs}
            )
            == CHANNEL_BLOCKS_PER_SLICE,
            "previous_physical_indices_exact_once_per_c8": full_pair_coverage,
            "a_c_tag_equal_for_every_pair": all(
                item["a_tag"] == item["c_tag"] for item in pairs
            ),
            "write_addresses_unique": len(set(output_addresses))
            == len(output_addresses),
            "write_region_contiguous": output_addresses
            == list(
                range(
                    output.base,
                    output.end,
                    SCRATCH_TRANSACTION_BYTES,
                )
            ),
            "stage_terminal_pair_count": len(terminal_pairs),
            "c8_local_end_pair_count": len(local_end_pairs),
        },
        "samples": {
            "first_two": pairs[:2],
            "first_padded_tail": next(
                (
                    item
                    for item in pairs
                    if item["a_padding_substitute_zero"]
                    or item["c_padding_substitute_zero"]
                ),
                None,
            ),
            "last_two": pairs[-2:],
            "first_write": writes[0],
            "last_write": writes[-1],
        },
        "candidate_stage_artifacts": {
            "config_json": None,
            "mapping": None,
            "bitstream": None,
            "execplan": None,
            "sca": None,
            "status": "not_materialized_generation_paused",
        },
    }


def validate_memory_plan() -> dict[str, Any]:
    regions = relative_regions()
    if regions[0].size != 100480:
        raise GapInt32MacBypassError("input guard allocation changed")
    if any(left.end > right.base for left, right in zip(regions, regions[1:])):
        raise GapInt32MacBypassError("relative regions overlap")
    stages = [_stage_summary(index) for index in range(1, 7)]
    for stage in stages:
        coverage = stage["coverage"]
        required_true = (
            "all_256_c8_blocks",
            "previous_physical_indices_exact_once_per_c8",
            "a_c_tag_equal_for_every_pair",
            "write_addresses_unique",
            "write_region_contiguous",
        )
        if any(coverage[key] is not True for key in required_true):
            raise GapInt32MacBypassError(
                f"stage {stage['stage_index']} memory coverage differs"
            )
        if coverage["stage_terminal_pair_count"] != 1:
            raise GapInt32MacBypassError(
                f"stage {stage['stage_index']} terminal count differs"
            )
        if coverage["c8_local_end_pair_count"] != 255:
            raise GapInt32MacBypassError(
                f"stage {stage['stage_index']} local-end count differs"
            )
    final_writes = stage_output_records(6)
    final_line_addresses = [
        item["relative_address"] + line_offset
        for item in final_writes
        for line_offset in (0, 16)
    ]
    if len(final_line_addresses) != FINAL_LINES_PER_SLICE:
        raise GapInt32MacBypassError("final 128-bit line count differs")
    if len(set(final_line_addresses)) != FINAL_LINES_PER_SLICE:
        raise GapInt32MacBypassError("final 128-bit lines are not unique")
    return {
        "address_domain": (
            "per-slice relative byte offsets before base-address assignment "
            "and address remapping"
        ),
        "replicated_slice_count": SLICE_COUNT,
        "input_logical_bytes_per_slice": INPUT_LOGICAL_BYTES,
        "input_allocation_bytes_per_slice": regions[0].size,
        "input_guard_bytes_per_slice": regions[0].size - INPUT_LOGICAL_BYTES,
        "regions": [region.to_dict() for region in regions],
        "non_overlapping": True,
        "total_relative_footprint_bytes_per_slice": regions[-1].end,
        "stages": stages,
        "final_d": {
            "transactions_per_slice": len(final_writes),
            "transaction_bytes": SCRATCH_TRANSACTION_BYTES,
            "unique_128bit_lines_per_slice": len(set(final_line_addresses)),
            "required_128bit_lines_per_slice": FINAL_LINES_PER_SLICE,
            "relative_line_address_sha256": _address_digest(
                (address,) for address in final_line_addresses
            ),
            "golden_status": "local_numeric_only_not_formal_readback",
        },
    }


def pairwise_int32_tree(values: Iterable[int]) -> tuple[int, list[int], list[list[int]]]:
    level = [int(value) & 0xFFFFFFFF for value in values]
    if len(level) != LOGICAL_LEAF_COUNT:
        raise GapInt32MacBypassError("exactly 49 values are required")
    level = [
        value - (1 << 32) if value & (1 << 31) else value for value in level
    ]
    logical_widths = [len(level)]
    physical = level + [0] * (PHYSICAL_LEAF_COUNT - len(level))
    physical_levels = [physical.copy()]
    while len(physical) > 1:
        physical = [
            ((physical[index] + physical[index + 1] + (1 << 31)) % (1 << 32))
            - (1 << 31)
            for index in range(0, len(physical), 2)
        ]
        physical_levels.append(physical.copy())
        logical_widths.append((logical_widths[-1] + 1) // 2)
    if tuple(logical_widths) != LOGICAL_WIDTHS:
        raise GapInt32MacBypassError("logical reduction widths changed")
    return physical[0], logical_widths, physical_levels


def _cgra_identity(root: Path) -> dict[str, Any]:
    lock = json.loads((root / REPOSITORY_LOCK_PATH).read_text(encoding="utf-8"))
    repositories = lock.get("repositories", [])
    matches = [
        item
        for item in repositories
        if isinstance(item, dict) and item.get("name") == "CGRA_SIM"
    ]
    if len(matches) != 1:
        raise GapInt32MacBypassError("CGRA_SIM lock identity is missing")
    identity = matches[0]
    if identity.get("path") != "CGRA_SIM":
        raise GapInt32MacBypassError("CGRA_SIM lock path differs")
    result = dict(identity)
    result["sum_source"] = _binding(
        root, "CGRA_SIM/cgra_python/op_lib/reduce_op/sum.py"
    )
    result["base_op_source"] = _binding(
        root, "CGRA_SIM/cgra_python/op_lib/base_op.py"
    )
    return result


def build_contract(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    memory_plan = validate_memory_plan()
    cgra_report_path = root / CGRA_REPORT_PATH
    cgra_report = (
        _binding(root, CGRA_REPORT_PATH)
        if cgra_report_path.is_file()
        else None
    )
    bindings = {
        "rule": _binding(root, RULE_PATH),
        "lowering_bundle": _binding(root, LOWERING_BUNDLE_PATH),
        "w3_input": _binding(root, W3_INPUT_PATH),
        "w3_expected": _binding(root, W3_EXPECTED_PATH),
        "repository_lock": _binding(root, REPOSITORY_LOCK_PATH),
        "cgra_sim": _cgra_identity(root),
        "stock_functional_rtl": [
            _binding(root, relative) for relative in RTL_BINDINGS
        ],
        "stock_stream_encoder": [
            _binding(root, relative) for relative in TOOLCHAIN_BINDINGS
        ],
        "cgra_semantic_report": cgra_report,
    }
    cgra_status = (
        "local_semantic_reference_pass"
        if cgra_report is not None
        else "not_run"
    )
    local_e2_path = root / LOCAL_E2_REPORT_PATH
    local_e2 = (
        json.loads(local_e2_path.read_text(encoding="utf-8"))
        if local_e2_path.is_file()
        else None
    )
    if local_e2 is not None:
        required_counts = {
            "json_stage_count": 6,
            "load_config_count": 6,
            "start_comp_count": 6,
            "completion_barrier_count": 6,
        }
        for key, expected in required_counts.items():
            if local_e2.get(key) != expected:
                raise GapInt32MacBypassError(
                    f"local E2 {key} differs from {expected}"
                )
        if local_e2.get("status") != "pass_local_e2":
            raise GapInt32MacBypassError("local E2 status is not pass")
        if local_e2.get("functional_rtl_modified") is not False:
            raise GapInt32MacBypassError("local E2 modified functional RTL")
        runtime = local_e2.get("runtime", {}).get("runtime_operators", [])
        if len(runtime) != 6:
            raise GapInt32MacBypassError("local E2 runtime stage count differs")
        for stage_index, stage in enumerate(runtime, start=1):
            config = stage.get("config", {})
            config_path = root / str(config.get("path", ""))
            expected_path = (
                root
                / MATERIALIZED_CONFIG_ROOT
                / f"stage-{stage_index}"
                / "config.json"
            )
            if config_path.resolve() != expected_path.resolve():
                raise GapInt32MacBypassError(
                    f"stage {stage_index} config provenance differs"
                )
            if not config_path.is_file():
                raise GapInt32MacBypassError(
                    f"stage {stage_index} config is missing"
                )
            if sha256_file(config_path) != config.get("sha256"):
                raise GapInt32MacBypassError(
                    f"stage {stage_index} config hash differs"
                )
            memory_plan["stages"][stage_index - 1][
                "candidate_stage_artifacts"
            ] = {
                "config_json": config.get("path"),
                "config_sha256": config.get("sha256"),
                "mapping_sha256": config.get("mapping_sha256"),
                "parsed_bitstream_sha256": config.get(
                    "parsed_bitstream_sha256"
                ),
                "bitstream": config.get("installed_bitstream"),
                "bitstream_sha256": config.get(
                    "installed_bitstream_sha256"
                ),
                "execplan": local_e2.get("execplan", {}).get("path"),
                "execplan_sha256": local_e2.get("execplan", {}).get(
                    "sha256"
                ),
                "status": "materialized_and_bound_by_local_e2",
            }
        bindings["local_e2_report"] = _binding(root, LOCAL_E2_REPORT_PATH)
    return {
        "schema": SCHEMA,
        "candidate_release": False,
        "server_package_allowed": local_e2 is not None,
        "functional_rtl_modified": False,
        "status": (
            "local_e2_closed_dynamic_server_route_pending"
            if cgra_report is not None
            else "local_address_semantics_closed_cgra_and_dynamic_pending"
        ),
        "scope": {
            "operator": "r5:hwop-0071-00",
            "equation": "six-stage int32_mac(A,1,C) explicit addition tree",
            "purpose": (
                "stock-RTL pure-configuration bypass feasibility contract"
            ),
            "does_not_generate": [
                "server install/run/return package",
                "RTL patch",
            ],
        },
        "rule_ids": list(RULE_IDS),
        "bindings": bindings,
        "memory_plan": memory_plan,
        "stage_boundary": {
            "ordering": [
                "previous stage final WRITE_STREAM0 handshake is accepted",
                "GA normal outbuffer count is observed empty",
                "scratch writes are visible to the next stage reads",
                "only then may the next stage configuration become active",
            ],
            "configure_clear_clears_ga_outbuffer": False,
            "reason": (
                "GA_PE_Outbuffer pointers/count are reset by rst_n or "
                "slice_rst, not by configure_clear"
            ),
            "dynamic_proof_status": "pending_cycle_level_first_stall_resume",
        },
        "cgra_sim_reference": {
            "status": cgra_status,
            "method": (
                "direct SUM.SUM numpy semantic call; Stream.execute/compute "
                "transport wrapper is intentionally not used"
            ),
            "consumes_config_or_bitstream": False,
            "transport_wrapper_boundary": (
                "SUM.compute calls BaseOP.reshape with an incompatible "
                "argument count in the locked source"
            ),
            "report": cgra_report,
        },
        "local_e2": {
            "status": (
                "pass_materialized_json_bitstream_execplan_and_golden"
                if local_e2 is not None
                else "not_run"
            ),
            "report": (
                _binding(root, LOCAL_E2_REPORT_PATH)
                if local_e2 is not None
                else None
            ),
            "dynamic_rtl_execution": False,
        },
        "blockers": [
            {
                "id": "B_GAP_GA_ACCUM_STATE",
                "status": "still_open_for_original_int32_sum_route",
                "bypass_claim": (
                    "opcode14 avoids the transout path only if the pending "
                    "real JSON and dynamic dual-stream route are proven"
                ),
            },
            {
                "id": "B_GAP_INT32MAC_REAL_STAGE_ARTIFACTS",
                "status": (
                    "closed_local_e2" if local_e2 is not None else "open"
                ),
                "missing": (
                    []
                    if local_e2 is not None
                    else [
                        "six real JSONs",
                        "six mappings",
                        "six bitstreams",
                        "six-stage execplan",
                    ]
                ),
            },
            {
                "id": "B_GAP_INT32MAC_DYNAMIC_DUAL_STREAM",
                "status": "open",
                "missing": (
                    "cycle-level READ_STREAM0/READ_STREAM3 first, skew, "
                    "stall, resume and tag-match evidence"
                ),
            },
            {
                "id": "B_GAP_INT32MAC_STAGE_BARRIER",
                "status": "open",
                "missing": (
                    "dynamic proof that every stage drains buffer5 and the "
                    "normal GA FIFO before reconfiguration"
                ),
            },
            {
                "id": "B_GAP_INT32MAC_FORMAL_READBACK",
                "status": "open",
                "missing": (
                    "16 slices x 512 unique 128-bit D lines and independent "
                    "formal golden comparison"
                ),
            },
        ],
        "release_boundary": {
            "local_formula_is_server_proof": False,
            "local_address_plan_is_real_json_proof": False,
            "cgra_semantic_reference_is_dynamic_routing_proof": False,
            "gap_specialized_validator_required_before_candidate": True,
            "server_e4_e5_gates_closed": True,
        },
    }


def validate_contract(contract: dict[str, Any], project_root: Path) -> None:
    expected = build_contract(project_root)
    if contract != expected:
        raise GapInt32MacBypassError(
            "GAP int32_mac bypass contract differs from current evidence"
        )


def write_contract(
    project_root: Path,
    output_path: Path | None = None,
    *,
    overwrite: bool = False,
) -> Path:
    root = project_root.resolve()
    target = (
        output_path.resolve()
        if output_path is not None
        else (root / CONTRACT_PATH).resolve()
    )
    if target.exists() and not overwrite:
        raise GapInt32MacBypassError(f"refusing to overwrite existing file: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(canonical_json_bytes(build_contract(root)) + b"\n")
    return target
