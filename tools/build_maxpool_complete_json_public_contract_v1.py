from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5_complete_json_regeneration_v1"
    / "maxpool_uint8"
)
COMPLETE_DIR = OUT / "complete_json"
SOURCE = (
    ROOT
    / "ndp-sim"
    / "jsons"
    / "maxpool_config_16_112_112_stride2_padding1.json"
)
SOURCE_B = (
    ROOT
    / "ndp-sim"
    / "jsons"
    / "maxpool_config_16_16_16_stride2_padding1.json"
)
LOWERING = ROOT / "contracts" / "resnet50_r5_lowering_bundle.json"
AUTHORITY = ROOT / "contracts/operator_config/operator_config_authority_v1.json"
POLICY = ROOT / "contracts/operator_config/complete_json_generation_contract_v1.json"
PADDING_CONTRACT = ROOT / "contracts/maxpool_node0002_zero_padding_contract.json"
CURRENT_ZIP = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5-server-test-packages"
    / "r5_n2_maxpool_ndpsim_native_v5.zip"
)
CURRENT_ROOT = "r5_n2_maxpool_ndpsim_native_v5"
CURRENT_CONFIG_MEMBER = (
    f"{CURRENT_ROOT}/workload/native/jsons/"
    "op0_maxpool_config_16_112_112_stride2_padding1.json"
)
CURRENT_GRAPH_MEMBER = (
    f"{CURRENT_ROOT}/workload/native/"
    "node0002_maxpool_wave0_graph_withbaseaddr.json"
)
CURRENT_MAPPING_MEMBER = (
    f"{CURRENT_ROOT}/workload/native/config/op0/mapping_review.json"
)
CURRENT_BITSTREAM_MEMBER = (
    f"{CURRENT_ROOT}/workload/native/config/op0/"
    "op0_maxpool_config_16_112_112_stride2_padding1_bitstream_128b.bin"
)
CURRENT_EXECPLAN_MEMBER = f"{CURRENT_ROOT}/workload/native/install/execplan.txt"
CURRENT_RETURN_REPORT = (
    ROOT
    / "artifacts"
    / "operator_config_validation"
    / "r5-maxpool-node0002-ndpsim-native-v5-return-analysis"
    / "report.json"
)
CURRENT_RETURN_TASK = (
    ROOT
    / ".agents"
    / "task_records"
    / "20260803_maxpool_node0002_ndpsim_native_v5_return_analysis.md"
)
OUTPUT_WRITER = (
    ROOT
    / "ndp-sim/model_execplan/src/execution_plan_generator/output_writer.py"
)
RD_DATA = (
    ROOT
    / "Trassic2.0_RTL/code/NDP_rtl/Slice/LSU/Stream_Engine/"
    "Memory_Stream_Engine/Memory_RD_Stream_Engine/RD_Data_Channel.sv"
)
GA_INBUFFER = (
    ROOT
    / "Trassic2.0_RTL/code/NDP_rtl/Slice/General_Array/"
    "GA_PE_Group/GA_PE_Inbuffer.sv"
)

CANDIDATE = COMPLETE_DIR / "node0002_hwop-0002-00_maxpool_uint8.json"
CURRENT_CONFIG = OUT / "current_test_consumed_config.json"
DERIVATION = OUT / "target_derivation_receipt.json"
REFERENCE = OUT / "reference_applicability.json"
LEDGER = OUT / "field_provenance_ledger.json"
HANDLER = OUT / "handler_capability.json"
CURRENT_DIFF = OUT / "current_test_diff.json"
COMPOSITION = OUT / "composition_boundary_not_applicable.json"
CONTRACT = OUT / "candidate_contract.json"
FAMILY_SET = OUT / "family_set.json"
REPORT = OUT / "report.json"

NDPSIM_COMMIT = "ec12424516ae0304228dd2321d4e604fe225e04e"
SOURCE_BLOB = "4e8f7bb8906ab58f54f4c6507d2b94822f71bf04"
SOURCE_B_BLOB = "5281f4f49dfd8290ae339a68c6df111286040698"
SOURCE_SHA = "a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1"
PADDING_POINTER = "/stream_engine/stream0/padding_reg_value"
ADDRESS_POINTERS = {
    "/stream_engine/stream0/base_addr",
    "/stream_engine/stream1/base_addr",
}
EXACTNESS_AXES = {
    "op",
    "dtype",
    "shape",
    "layout",
    "qparams",
    "topology",
    "address",
    "schedule",
    "consumer",
}


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any, *, crlf: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=not crlf) + "\n"
    if crlf:
        text = text.replace("\n", "\r\n")
    path.write_bytes(text.encode("utf-8"))


def bound(path: Path) -> dict[str, str]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha(path)}


def git(repo: Path, *args: str) -> str:
    command = [
        "git",
        "-c",
        f"safe.directory={repo.as_posix()}",
        "-C",
        str(repo),
        *args,
    ]
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def leaves(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            yield pointer or "/", value
            return
        for key in sorted(value):
            yield from leaves(value[key], f"{pointer}/{escape(str(key))}")
        return
    if isinstance(value, list):
        if not value:
            yield pointer or "/", value
            return
        for index, item in enumerate(value):
            yield from leaves(item, f"{pointer}/{index}")
        return
    yield pointer or "/", value


def pointer_set(document: Any, pointer: str, value: Any) -> None:
    tokens = pointer.lstrip("/").split("/")
    current = document
    for token in tokens[:-1]:
        token = token.replace("~1", "/").replace("~0", "~")
        current = current[int(token)] if isinstance(current, list) else current[token]
    token = tokens[-1].replace("~1", "/").replace("~0", "~")
    if isinstance(current, list):
        current[int(token)] = value
    else:
        current[token] = value


def zip_member(archive: zipfile.ZipFile, member: str) -> bytes:
    if archive.namelist().count(member) != 1:
        raise RuntimeError(f"ZIP member must occur exactly once: {member}")
    return archive.read(member)


def consumer_equation(pointer: str) -> str:
    top = pointer.split("/")[1]
    equations = {
        "CONFIG": (
            "The native encoder packs the explicit module-enable mask; inactive "
            "blocks remain disabled and no absent field is treated as implicit zero."
        ),
        "dram_loop_configs": (
            "Each enabled LC emits start+n*stride under its selected predecessor "
            "ready/valid relation and asserts last at the configured end."
        ),
        "lc_pe_configs": (
            "Each enabled LC_PE evaluates its configured opcode over selected LC/PE "
            "inputs; only a qualified accepted result reaches an MSE or child LC."
        ),
        "buffer_loop_configs": (
            "ROW/COL LC indices form the physical buffer request; address and "
            "lifetime advance only on an accepted request."
        ),
        "stream_engine": (
            "MSE address = base_addr + accepted selected-index offset; progress "
            "requires qualified index, memory, and buffer handshakes."
        ),
        "buffer_config": (
            "The addressed active-bank row is ready only when its valid/full state "
            "satisfies the request; mode/end_row/lifetime control reuse."
        ),
        "general_array": (
            "Enabled PEs capture selected valid operands and opcode 11 performs "
            "byte-lane int8_max; forward progress also requires active RTL pipeline "
            "ready/clear and outbuffer acceptance."
        ),
    }
    return equations.get(
        top,
        "The final native consumer encodes this exact leaf for the explicitly "
        "enabled block selected by the configuration.",
    )


def owner(pointer: str) -> str:
    if pointer in ADDRESS_POINTERS:
        return "graph address planner"
    if pointer == PADDING_POINTER:
        return "MaxPool UINT8 border semantic materializer"
    return f"pinned native MaxPool source / {pointer.split('/')[1]} consumer"


def exact_axes(*, address: bool = True) -> dict[str, bool]:
    result = {axis: True for axis in EXACTNESS_AXES}
    result["address"] = address
    return result


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    COMPLETE_DIR.mkdir(parents=True, exist_ok=True)

    source_bytes = SOURCE.read_bytes()
    if sha_bytes(source_bytes) != SOURCE_SHA:
        raise RuntimeError("authoritative MaxPool source SHA drift")
    ndpsim = ROOT / "ndp-sim"
    if git(ndpsim, "rev-parse", "HEAD") != NDPSIM_COMMIT:
        raise RuntimeError("ndp-sim commit drift")
    if (
        git(
            ndpsim,
            "rev-parse",
            "HEAD:jsons/maxpool_config_16_112_112_stride2_padding1.json",
        )
        != SOURCE_BLOB
    ):
        raise RuntimeError("authoritative MaxPool source blob drift")

    source = json.loads(source_bytes.decode("utf-8"))
    lowering = read_json(LOWERING)
    request = next(
        item
        for item in lowering["requests"]
        if item["request_id"] == "r5:hwop-0002-00"
    )
    dag = next(
        item
        for item in lowering["node_stage_dags"]
        if item["node_id"] == "node-0002"
    )
    if request["identity"]["hw_op_id"] != "hwop-0002-00":
        raise RuntimeError("MaxPool lowering identity drift")
    if request["identity"]["hw_op_type"] != "MaxPoolUint8":
        raise RuntimeError("MaxPool lowering type drift")
    if dag["stage_ids"] != ["hwop-0002-00"] or dag["internal_edges"]:
        raise RuntimeError("MaxPool lowering stage DAG is no longer single-stage")

    with zipfile.ZipFile(CURRENT_ZIP) as archive:
        current_bytes = zip_member(archive, CURRENT_CONFIG_MEMBER)
        current = json.loads(current_bytes.decode("utf-8"))
        graph_bytes = zip_member(archive, CURRENT_GRAPH_MEMBER)
        graph = json.loads(graph_bytes.decode("utf-8"))
        mapping_bytes = zip_member(archive, CURRENT_MAPPING_MEMBER)
        bitstream_bytes = zip_member(archive, CURRENT_BITSTREAM_MEMBER)
        execplan_bytes = zip_member(archive, CURRENT_EXECPLAN_MEMBER)

    operator = graph["operators"][0]
    candidate = deepcopy(source)
    address_values = {
        "/stream_engine/stream0/base_addr": hex(
            int(operator["inputs"]["A"]["base_addr"], 16)
        ),
        "/stream_engine/stream1/base_addr": hex(
            int(operator["output"]["base_addr"], 16)
        ),
    }
    for pointer, value in address_values.items():
        pointer_set(candidate, pointer, value)
    pointer_set(candidate, PADDING_POINTER, 0)

    write_json(CANDIDATE, candidate, crlf=True)
    CURRENT_CONFIG.write_bytes(current_bytes)
    candidate_sha = sha(CANDIDATE)
    candidate_leaves = dict(leaves(candidate))
    source_leaves = dict(leaves(source))
    current_leaves = dict(leaves(current))
    if not (
        set(candidate_leaves) == set(source_leaves) == set(current_leaves)
    ):
        raise RuntimeError("source/candidate/current leaf sets differ")
    source_diff = {
        pointer
        for pointer in candidate_leaves
        if candidate_leaves[pointer] != source_leaves[pointer]
    }
    if source_diff != ADDRESS_POINTERS | {PADDING_POINTER}:
        raise RuntimeError(f"unexpected source differences: {sorted(source_diff)}")
    current_diff_pointers = {
        pointer
        for pointer in candidate_leaves
        if candidate_leaves[pointer] != current_leaves[pointer]
    }
    if current_diff_pointers != {PADDING_POINTER}:
        raise RuntimeError(
            f"unexpected current differences: {sorted(current_diff_pointers)}"
        )

    rd_text = RD_DATA.read_text(encoding="utf-8")
    padding_equation = (
        "rd_chl_queue_rd_padding_mask[PADDING_INDEX] ? mse_padding_reg_value"
    )
    if padding_equation not in rd_text:
        raise RuntimeError("current RTL padding substitution equation drift")
    graph_sha = sha_bytes(graph_bytes)
    derivation = {
        "schema": "maxpool_complete_json_target_derivation_receipt_v1",
        "family": "maxpool_uint8",
        "candidate_json_sha256": candidate_sha,
        "lowering": bound(LOWERING),
        "source": bound(SOURCE),
        "address_derivations": [
            {
                "json_pointer": pointer,
                "target_value": value,
                "owner": "graph address planner",
                "source_package": bound(CURRENT_ZIP),
                "source_member": CURRENT_GRAPH_MEMBER,
                "source_member_sha256": graph_sha,
                "equation": (
                    "stream0.base_addr = graph.operators[0].inputs.A.base_addr"
                    if pointer.endswith("stream0/base_addr")
                    else "stream1.base_addr = graph.operators[0].output.base_addr"
                ),
            }
            for pointer, value in sorted(address_values.items())
        ],
        "padding_derivation": {
            "json_pointer": PADDING_POINTER,
            "source_value": None,
            "target_value": 0,
            "owner": "MaxPool UINT8 border semantic materializer",
            "legacy_contract": bound(PADDING_CONTRACT),
            "current_rtl": bound(RD_DATA),
            "current_rtl_equation": padding_equation,
            "semantic_equation": (
                "excluded spatial border byte = UINT8 max identity 0; the RTL "
                "padding mask selects mse_padding_reg_value for excluded lanes"
            ),
            "stale_legacy_contract_boundary": (
                "The legacy contract binds a pre-current RD_Data_Channel SHA. "
                "The current direct RTL equation is re-bound here; public rule "
                "refresh remains a separate proposal."
            ),
        },
        "claim_boundary": (
            "Target-only derivation of two planner-owned base addresses and one "
            "strict UINT8 zero-padding byte. No mapping, bitstream, execplan, SCA, "
            "server package, or hardware execution is generated."
        ),
    }
    write_json(DERIVATION, derivation)

    reference = {
        "schema": "maxpool_complete_json_reference_applicability_v1",
        "family": "maxpool_uint8",
        "target_hw_op_types": ["MaxPoolUint8"],
        "target_stages": [
            {
                "node_id": "node-0002",
                "stage_id": "hwop-0002-00",
                "request_id": "r5:hwop-0002-00",
                "equivalence_class": (
                    "maxpool_uint8_nchw_16x64x112x112_k3s2p1_native_c16"
                ),
                "op": "MaxPool",
                "hw_op_type": "MaxPoolUint8",
                "dtype": {"input": "uint8", "output": "uint8"},
                "shape": {
                    "input": [16, 64, 112, 112],
                    "output": [16, 64, 56, 56],
                },
                "layout": {
                    "logical": "NCHW",
                    "native_per_slice": "HWC_C16",
                    "slices": 28,
                    "input": [112, 112, 16],
                    "output": [56, 56, 16],
                },
                "qparams": {
                    "relationship": "same_qdomain_passthrough",
                    "state": "SOURCE_ABSENT_NOT_APPLICABLE",
                },
                "padding_tail": {
                    "kernel": [3, 3],
                    "stride": [2, 2],
                    "pads": [1, 1, 1, 1],
                    "padding_value": 0,
                    "channel_tail": "none",
                },
                "dag": {"stages": ["hwop-0002-00"], "internal_edges": []},
                "lifetime": {
                    "input": "upstream graph tensor storage",
                    "output": "node0002 graph tensor storage",
                    "config": "single native stage",
                },
                "address_owner": "graph address planner",
            }
        ],
        "reference_classes": {
            "A": [
                {
                    "path": SOURCE.relative_to(ROOT).as_posix(),
                    "sha256": sha(SOURCE),
                    "commit": NDPSIM_COMMIT,
                    "blob_oid": SOURCE_BLOB,
                    "applicability": (
                        "Exact op/dtype/shape/layout/qdomain/topology source "
                        "instance; target addresses and strict padding byte are "
                        "separately derived."
                    ),
                }
            ],
            "B": [
                {
                    "path": SOURCE_B.relative_to(ROOT).as_posix(),
                    "sha256": sha(SOURCE_B),
                    "commit": NDPSIM_COMMIT,
                    "blob_oid": SOURCE_B_BLOB,
                    "difference": "native spatial shape 16x16 instead of 112x112",
                    "authority": "REFERENCE_ONLY_NO_GENERALIZATION",
                }
            ],
            "C": [],
            "D": [
                {
                    "glob": (
                        "configs/native_ndp_sim/"
                        "maxpool_config_16_112_112_stride2_padding1*/config.json"
                    ),
                    "authority": "PROJECT_ADDED_OR_UNTRACKED_NOT_UPSTREAM",
                }
            ],
        },
        "claim_boundary": (
            "Only the pinned tracked 112x112 ndp-sim blob is class-A authority. "
            "Project-added strict/guarded files and current test packages are "
            "comparison evidence, not native-reference authority."
        ),
    }
    write_json(REFERENCE, reference)

    ledger_entries: list[dict[str, Any]] = []
    for pointer, target_value in sorted(candidate_leaves.items()):
        if pointer in ADDRESS_POINTERS:
            origin = "ADDRESS_PLANNER_DERIVED"
            applicability_class = "DERIVED_FOR_TARGET"
            source_info = None
            derivation_receipt = bound(DERIVATION)
            axes = exact_axes(address=False)
            control = "MAXPOOL-ADDRESS-PLANNER-BINDING-MUTATION-FAIL"
        elif pointer == PADDING_POINTER:
            origin = "RTL_DERIVED"
            applicability_class = "DERIVED_FOR_TARGET"
            source_info = None
            derivation_receipt = bound(DERIVATION)
            axes = exact_axes()
            control = "MAXPOOL-PADDING-NULL-TO-ZERO-DERIVATION-MUTATION-FAIL"
        else:
            origin = "REFERENCE_EXACT"
            applicability_class = "EXACT_SOURCE_INSTANCE"
            source_info = {
                "path": SOURCE.relative_to(ROOT).as_posix(),
                "commit": NDPSIM_COMMIT,
                "blob_oid": SOURCE_BLOB,
                "file_sha256": SOURCE_SHA,
                "json_pointer": pointer,
                "value": source_leaves[pointer],
            }
            derivation_receipt = None
            axes = exact_axes()
            control = "MAXPOOL-REFERENCE-EXACT-LEAF-MUTATION-FAIL"
        ledger_entries.append(
            {
                "json_pointer": pointer,
                "target_value": target_value,
                "origin": origin,
                "applicability_class": applicability_class,
                "owner": owner(pointer),
                "consumer_equation": consumer_equation(pointer),
                "exactness_axes": axes,
                "negative_control_ids": [control],
                "source": source_info,
                "derivation_receipt": derivation_receipt,
                "status": "RESOLVED",
            }
        )

    source_absences: list[dict[str, Any]] = [
        {
            "target_json_pointer": pointer,
            "state": "TARGET_REQUIRED_DERIVED",
            "reason": (
                "Target graph address planner owns this leaf."
                if pointer in ADDRESS_POINTERS
                else "Enabled UINT8 spatial padding requires an explicit zero byte."
            ),
            "owner": owner(pointer),
        }
        for pointer in sorted(ADDRESS_POINTERS | {PADDING_POINTER})
    ]
    for pointer, value in sorted(candidate_leaves.items()):
        if pointer == PADDING_POINTER:
            continue
        if value is None:
            source_absences.append(
                {
                    "target_json_pointer": pointer,
                    "state": "EXPLICIT_NULL_INACTIVE",
                    "reason": (
                        "The exact native source explicitly disables or leaves "
                        "inactive this optional consumer input."
                    ),
                    "owner": owner(pointer),
                }
            )
        elif value == 0 and not isinstance(value, bool):
            source_absences.append(
                {
                    "target_json_pointer": pointer,
                    "state": "EXPLICIT_ZERO",
                    "reason": (
                        "The exact native source explicitly encodes numeric zero; "
                        "this is not an implicit default."
                    ),
                    "owner": owner(pointer),
                }
            )
    source_absences.extend(
        [
            {
                "target_json_pointer": "/@semantic/qparams",
                "state": "SOURCE_ABSENT_NOT_APPLICABLE",
                "reason": "Same-qdomain MaxPool has no typed qparam leaf.",
                "owner": "model lowering",
            },
            {
                "target_json_pointer": "/@semantic/auxiliary_input",
                "state": "SOURCE_ABSENT_NOT_APPLICABLE",
                "reason": "MaxPool node0002 has exactly one data input.",
                "owner": "model lowering",
            },
            {
                "target_json_pointer": "/@semantic/specialized_array",
                "state": "SOURCE_ABSENT_NOT_APPLICABLE",
                "reason": "This native MaxPool uses GA and does not enable SA.",
                "owner": "native hardware topology",
            },
        ]
    )
    origins = Counter(item["origin"] for item in ledger_entries)
    ledger = {
        "schema": "operator_config_field_provenance_ledger_v1",
        "family": "maxpool_uint8",
        "candidate_json_sha256": candidate_sha,
        "entries": ledger_entries,
        "source_absences": source_absences,
        "claim_boundary": (
            "One entry covers every scalar/null/list leaf in the complete target "
            "JSON. There is no UNRESOLVED leaf or unknown source-absence state."
        ),
    }
    write_json(LEDGER, ledger)

    handler = {
        "schema": "operator_config_handler_capability_v1",
        "family": "maxpool_uint8",
        "handler": {
            "kind": "AUTHORIZED_PATCH",
            "path": OUTPUT_WRITER.relative_to(ROOT).as_posix(),
            "sha256": sha(OUTPUT_WRITER),
            "source_span": "native JSON load plus planner-owned stream base-address patch",
        },
        "capabilities": {
            "exact_replay": {
                "supported": True,
                "evidence": (
                    "The pinned 112x112 source is consumed unchanged except the "
                    "separately proven address and strict padding derivations."
                ),
            },
            "shape": {
                "supported": False,
                "evidence": "No MaxPool shape-generalizing registry/handler exists.",
            },
            "dtype": {
                "supported": False,
                "evidence": "No MaxPool dtype-generalizing handler exists.",
            },
            "qparam": {
                "supported": False,
                "evidence": "Same-qdomain MaxPool has no qparam handler or target leaf.",
            },
            "layout": {
                "supported": False,
                "evidence": "Only the exact native HWC_C16 layout is replayed.",
            },
            "address": {
                "supported": True,
                "evidence": (
                    "output_writer applies address_plan values to selected stream "
                    "base_addr leaves; the exact graph member is bound in the receipt."
                ),
            },
            "cross_stage_schedule": {
                "supported": False,
                "evidence": "node0002 has one stage and no composition edge.",
            },
        },
        "dependent_leaves": [
            {
                "json_pointer": pointer,
                "axes": ["address"],
                "covered_by": OUTPUT_WRITER.relative_to(ROOT).as_posix(),
                "status": "COVERED",
            }
            for pointer in sorted(ADDRESS_POINTERS)
        ],
        "claim_boundary": (
            "Exact source-instance replay and the two planner-owned address patches "
            "are supported. Shape/dtype/qparam/layout/schedule generalization is "
            "explicitly not claimed."
        ),
    }
    write_json(HANDLER, handler)

    diff_entries: list[dict[str, Any]] = []
    for pointer, candidate_value in sorted(candidate_leaves.items()):
        current_value = current_leaves[pointer]
        if candidate_value == current_value:
            classification = "SAME"
            reason = "Candidate and current v5 consumed JSON leaf are identical."
        elif pointer == PADDING_POINTER:
            classification = "SUSPECTED_CURRENT_DEFECT"
            reason = (
                "Current v5 leaves an enabled padding byte null; the strict target "
                "materializes the proven UINT8 max identity 0."
            )
        else:
            raise RuntimeError(f"unclassified current difference: {pointer}")
        diff_entries.append(
            {
                "json_pointer": pointer,
                "candidate_value": candidate_value,
                "current_value_present": True,
                "current_value": current_value,
                "classification": classification,
                "reason": reason,
                "evidence": [
                    CANDIDATE.relative_to(ROOT).as_posix(),
                    CURRENT_CONFIG.relative_to(ROOT).as_posix(),
                    DERIVATION.relative_to(ROOT).as_posix(),
                ],
            }
        )
    current_return = read_json(CURRENT_RETURN_REPORT)
    current_diff = {
        "schema": "operator_config_current_test_diff_v1",
        "family": "maxpool_uint8",
        "candidate_json_sha256": candidate_sha,
        "current_identity": {
            "available": True,
            "path": CURRENT_CONFIG.relative_to(ROOT).as_posix(),
            "sha256": sha(CURRENT_CONFIG),
            "package_or_record": CURRENT_ZIP.relative_to(ROOT).as_posix(),
            "latest_result": (
                "v5 compile/start observed; no natural terminal; 0/28 formal D; "
                "DEFERRED_BY_USER_NATIVE_REUSE_OVERRIDE"
            ),
        },
        "entries": diff_entries,
        "blocker_attribution": [
            {
                "blocker_id": "MAXPOOL_V5_SLICE_START_TO_NO_COMPLETION_OR_D",
                "classification": "INSUFFICIENT_EVIDENCE",
                "candidate_json_pointers": [PADDING_POINTER],
                "reason": (
                    "The strict padding defect is real, but the frozen return lacks "
                    "a qualified boundary that proves it caused the dynamic stop."
                ),
                "evidence": [
                    CURRENT_RETURN_REPORT.relative_to(ROOT).as_posix(),
                    CURRENT_RETURN_TASK.relative_to(ROOT).as_posix(),
                    DERIVATION.relative_to(ROOT).as_posix(),
                ],
            },
            {
                "blocker_id": "B_GA_INT8_MAX_FLOW",
                "classification": "CONFIG_EXCLUDED",
                "candidate_json_pointers": [],
                "reason": (
                    "Current GA_PE_Inbuffer RTL has INT32/FP32 pipeline0 ready "
                    "branches but no INT8 branch; a JSON leaf cannot repair it."
                ),
                "evidence": [GA_INBUFFER.relative_to(ROOT).as_posix()],
            },
            {
                "blocker_id": "MAXPOOL_NATURAL_TERMINAL_AND_FORMAL_D",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [],
                "reason": (
                    "Natural terminal and exact formal D require a future bound "
                    "hardware execution and are outside complete-JSON validation."
                ),
                "evidence": [CURRENT_RETURN_REPORT.relative_to(ROOT).as_posix()],
            },
        ],
        "claim_boundary": (
            "Leaf-complete comparison against the actual v5 consumed JSON. The one "
            "strict padding difference is not promoted to a dynamic root cause."
        ),
    }
    write_json(CURRENT_DIFF, current_diff)

    composition = {
        "schema": "maxpool_complete_json_composition_applicability_v1",
        "family": "maxpool_uint8",
        "required": False,
        "stage_ids": ["hwop-0002-00"],
        "internal_edges": [],
        "reason": "One native MaxPool primitive implements the one lowering stage.",
        "claim_boundary": "No multi-primitive producer/consumer boundary exists.",
    }
    write_json(COMPOSITION, composition)

    contract = {
        "schema": "operator_config_complete_json_candidate_v1",
        "family": "maxpool_uint8",
        "candidate_status": "COMPLETE",
        "reference_class": "A",
        "changed_axes": ["address"],
        "target_hw_op_types": ["MaxPoolUint8"],
        "stage_ids": ["hwop-0002-00"],
        "candidate_json": bound(CANDIDATE),
        "field_provenance_ledger": bound(LEDGER),
        "handler_capability": bound(HANDLER),
        "current_test_diff": bound(CURRENT_DIFF),
        "composition": {"required": False, "boundary": None},
        "artifact_root": OUT.relative_to(ROOT).as_posix(),
        "claim_boundary": (
            "Complete strict JSON for the sole MaxPoolUint8 lowering stage. This "
            "claim excludes mapping, bitstream, execplan, SCA, server packages, "
            "server execution, natural terminal, formal D, E3, E4, and E5."
        ),
    }
    write_json(CONTRACT, contract)
    family_set = {
        "schema": "operator_config_complete_json_family_set_v1",
        "family": "maxpool_uint8",
        "target_hw_op_types": ["MaxPoolUint8"],
        "candidate_contracts": [bound(CONTRACT)],
        "no_config_stages": [],
        "claim_boundary": (
            "The sole MaxPoolUint8 lowering stage hwop-0002-00 is covered exactly "
            "once by one COMPLETE candidate; no metadata-only alias is used."
        ),
    }
    write_json(FAMILY_SET, family_set)

    current_artifact_receipts = {
        "source_package": bound(CURRENT_ZIP),
        "final_json_member": {
            "member": CURRENT_CONFIG_MEMBER,
            "bytes": len(current_bytes),
            "sha256": sha_bytes(current_bytes),
        },
        "graph_member": {
            "member": CURRENT_GRAPH_MEMBER,
            "bytes": len(graph_bytes),
            "sha256": sha_bytes(graph_bytes),
        },
        "mapping_member_read_only": {
            "member": CURRENT_MAPPING_MEMBER,
            "bytes": len(mapping_bytes),
            "sha256": sha_bytes(mapping_bytes),
        },
        "bitstream_member_read_only": {
            "member": CURRENT_BITSTREAM_MEMBER,
            "bytes": len(bitstream_bytes),
            "sha256": sha_bytes(bitstream_bytes),
        },
        "execplan_member_read_only": {
            "member": CURRENT_EXECPLAN_MEMBER,
            "bytes": len(execplan_bytes),
            "sha256": sha_bytes(execplan_bytes),
        },
    }
    validation_receipts: dict[str, Any] = {}
    for name in (
        "operator_config_shadow_validation.json",
        "local_validation_report.json",
        "shared_candidate_validation_report.json",
        "family_set_audit_report.json",
    ):
        path = OUT / name
        if path.is_file():
            validation_receipts[name] = bound(path)

    report = {
        "schema": "maxpool_complete_json_regeneration_report_v1",
        "family": "maxpool_uint8",
        "target_hw_op_types": ["MaxPoolUint8"],
        "status": "COMPLETE",
        "analysis_owner_thread": "019fbe9f-3f2d-7071-806c-1ae72ae96391",
        "upstream_task": "019fd276-14c5-7800-94db-87ebfb9ce632",
        "return_target_thread": "019fbec2-fe93-7e03-9314-cff6f222f33d",
        "coverage": {
            "stage_count": 1,
            "equivalence_class_count": 1,
            "candidate_leaf_count": len(candidate_leaves),
            "unresolved_leaf_count": 0,
            "origin_counts": dict(sorted(origins.items())),
        },
        "candidate": bound(CANDIDATE),
        "candidate_contract": bound(CONTRACT),
        "family_set": bound(FAMILY_SET),
        "source_authority": {
            "path": SOURCE.relative_to(ROOT).as_posix(),
            "bytes": SOURCE.stat().st_size,
            "sha256": sha(SOURCE),
            "commit": NDPSIM_COMMIT,
            "blob_oid": SOURCE_BLOB,
            "reference_class": "A",
        },
        "candidate_vs_source_changed_pointers": sorted(source_diff),
        "candidate_vs_current_changed_pointers": sorted(current_diff_pointers),
        "current_test_artifacts": current_artifact_receipts,
        "current_result_classification": current_return.get(
            "root_cause_adjudication", {}
        ).get("classification"),
        "current_suspected_config_defects": [PADDING_POINTER],
        "current_dynamic_stop_explained_by_config": False,
        "non_config_boundary": {
            "blocker": "B_GA_INT8_MAX_FLOW",
            "evidence": bound(GA_INBUFFER),
        },
        "read_receipts": {
            "index": bound(ROOT / ".agents/rules/生成前必读索引.md"),
            "operator_rule": bound(ROOT / ".agents/rules/算子配置规则.md"),
            "policy": bound(POLICY),
            "authority": bound(AUTHORITY),
            "lowering": bound(LOWERING),
        },
        "validation_receipts": validation_receipts,
        "hard_boundary": {
            "mapping_generated": False,
            "bitstream_generated": False,
            "execplan_generated": False,
            "sca_generated": False,
            "server_package_generated_or_modified": False,
            "server_action": False,
            "functional_rtl_modified": False,
            "plan_or_public_rules_modified": False,
            "numeric_or_golden_repeated": False,
        },
        "rule_delta_proposal": [
            {
                "proposal": (
                    "REFRESH_MAXPOOL_PADDING_RTL_EVIDENCE_CURRENT_IDENTITY"
                ),
                "reason": (
                    "The legacy hash-bound padding contract names a pre-current "
                    "RD_Data_Channel SHA; current RTL preserves the exact padding "
                    "substitution equation and is rebound in the local receipt."
                ),
                "candidate_leaf_error": False,
            },
            {
                "proposal": (
                    "ALIGN_OPERATOR_CONFIG_VALIDATOR_GA_INT8_MAX_NUMERIC_FACT_"
                    "WITH_CURRENT_RULE"
                ),
                "reason": (
                    "Current NDP field rule records "
                    "CDA-GA-INT8-MAX-NUMERIC-001=LOCAL_SOURCE_PASS, while "
                    "OperatorConfigValidator facts still emit the superseded "
                    "unsigned-min/CONTRADICTED statement. The strict validity "
                    "result remains true, but the diagnostic fact must not be "
                    "used as current semantic adjudication."
                ),
                "candidate_leaf_error": False,
            }
        ],
        "claim_boundary": (
            "CONFIG_COMPLETE_LOCAL_ONLY. It proves a leaf-complete strict MaxPool "
            "JSON and whole-family stage coverage, not hardware capability, dynamic "
            "completion, formal D, E3, E4, or E5."
        ),
        "errors": [],
    }
    write_json(REPORT, report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
