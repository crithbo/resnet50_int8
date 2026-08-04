from __future__ import annotations

import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import numpy as np

from resnet50_pipeline.hashing import canonical_json_bytes, sha256_file


SCHEMA = "resnet50-node0077-dequant-three-party-ledger-v1"
CONTRACT_SCHEMA = "dequant-node0077-config-bound-simulator-contract-v1"
PACKAGE_RELATIVE = Path(
    "artifacts/operator_config_validation/r5-server-test-packages/"
    "dequant_node0077_stockrtl_e5_onecmd_v1.zip"
)
CONFIG_RELATIVE = Path(
    "configs/native_ndp_sim/"
    "resnet50_dequant_node0077_uint8_fp32_strict_v6/config.json"
)
E4_ANALYSIS_RELATIVE = Path(
    "server_returns/dequant_node0077_stockrtl_e4_onecmd_v2_return_analysis_20260727.json"
)
E5_ANALYSIS_RELATIVE = Path(
    "server_returns/dequant_node0077_stockrtl_e5_onecmd_v1_return_analysis_20260727.json"
)
HANDOFF_RELATIVE = Path(
    ".agents/task_records/20260727_test_repair_to_family_threads_handoff.md"
)
ATOMIC_RECORD_RELATIVE = Path(
    ".agents/task_records/20260726_dequant_atomic1_v3_return_analysis.md"
)
ATOMIC_ANALYSIS_RELATIVE = Path(
    "server_returns/dq_node0077_atomic1_stock_v3_return_analysis_20260726.json"
)
E4_RECORD_RELATIVE = Path(
    ".agents/task_records/20260727_dequant_node0077_full_v6_e4_pass.md"
)
E5_RECORD_RELATIVE = Path(
    ".agents/task_records/20260727_dequant_node0077_full_v6_e5_pass.md"
)
E4_RETURN_ROOT = Path(
    "server_returns/dequant_node0077_stockrtl_e4_onecmd_v2_return_20260727/"
    "extracted/dequant_node0077_stockrtl_e4_onecmd_v2_return/readback"
)
E5_RETURN_ROOT = Path(
    "server_returns/dequant_node0077_stockrtl_e5_onecmd_v1_return_20260727/"
    "extracted/dequant_node0077_stockrtl_e5_onecmd_v1_return/readback"
)
OUTPUT_ROOT_RELATIVE = Path(
    "artifacts/operator_config_validation/"
    "r5-dequant-node0077-config-bound-simulator-v1"
)
REPORT_RELATIVE = OUTPUT_ROOT_RELATIVE / "three_party_report.json"
CONTRACT_RELATIVE = Path(
    "contracts/operator_config/dequant_node0077_config_bound_simulator_v1.json"
)
RULE_PATHS = (
    Path(".agents/agent.md"),
    Path(".agents/plan.md"),
    Path(".agents/rules/生成前必读索引.md"),
    Path(".agents/rules/算子配置规则.md"),
    Path(".agents/rules/NDP硬件字段语义.md"),
    Path(".agents/rules/DequantizeLinear算子配置规则.md"),
    Path(".agents/rules/DequantizeLinear原子动态合同规则.md"),
)
SLICE_COUNT = 28
WORDS_PER_SLICE = 752
VALID_WORDS_PER_SLICE = 750
LINES_PER_SLICE = 188


class DequantConfigBoundSimulatorError(RuntimeError):
    pass


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _identity(root: Path, relative: Path) -> dict[str, Any]:
    path = root / relative
    return {
        "path": relative.as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def _json(raw: bytes, label: str) -> dict[str, Any]:
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise DequantConfigBoundSimulatorError(f"{label} is not a JSON object")
    return value


def _decode_lines(raw: bytes, expected: int, label: str) -> bytes:
    if b"\r" in raw:
        raise DequantConfigBoundSimulatorError(f"{label} contains CR")
    lines = raw.decode("ascii").splitlines()
    if (
        len(lines) != expected
        or any(len(line) != 128 or set(line) - {"0", "1"} for line in lines)
        or raw != ("\n".join(lines) + "\n").encode("ascii")
    ):
        raise DequantConfigBoundSimulatorError(f"{label} has invalid 128-bit ABI")
    return b"".join(int(line, 2).to_bytes(16, "little") for line in lines)


def _encode_lines(raw: bytes) -> bytes:
    if len(raw) % 16:
        raise DequantConfigBoundSimulatorError("physical D is not 128-bit aligned")
    return (
        "\n".join(
            f"{int.from_bytes(raw[index:index + 16], 'little'):0128b}"
            for index in range(0, len(raw), 16)
        )
        + "\n"
    ).encode("ascii")


def _fp32_constant(raw: object) -> np.float32:
    if not isinstance(raw, str) or re.fullmatch(r"0x[0-9a-fA-F]{8}", raw) is None:
        raise DequantConfigBoundSimulatorError(f"GA constant is not fp32 bits: {raw!r}")
    return np.frombuffer(struct.pack("<I", int(raw, 16)), dtype=np.float32)[0]


def _execute_pe_graph(config: dict[str, Any], a_raw: bytes) -> bytes:
    """Execute the final JSON PE DAG over one physical A payload.

    The result is derived from config opcodes, constants and src_id edges.  No
    Dequant formula or qparams are accepted as executor inputs.
    """

    if len(a_raw) != WORDS_PER_SLICE:
        raise DequantConfigBoundSimulatorError("physical A byte count differs")
    ga = config.get("general_array", {})
    inport = ga.get("inport", {}).get("inport0", {})
    pe_array = ga.get("PE_array", {})
    if (
        inport.get("uint8tofp32") != "true"
        or ga.get("outport", {}).get("fp32tobf16") != "false"
        or not isinstance(pe_array, dict)
    ):
        raise DequantConfigBoundSimulatorError("final JSON conversion/GA contract differs")
    source = np.frombuffer(a_raw, dtype=np.uint8).astype(np.float32)
    values: dict[str, np.ndarray] = {}
    visiting: set[str] = set()

    def evaluate(name: str) -> np.ndarray:
        if name in values:
            return values[name]
        if name in visiting or name not in pe_array:
            raise DequantConfigBoundSimulatorError(f"invalid GA PE DAG at {name}")
        visiting.add(name)
        node = pe_array[name]
        port = node.get("inport0", {})
        mode = port.get("mode")
        src_id = port.get("src_id")
        if mode == "buffer" and src_id == 0:
            left = source
        elif mode == "buffer" and isinstance(src_id, str) and src_id.startswith("GA_PE."):
            left = evaluate(src_id.split(".", 1)[1])
        else:
            raise DequantConfigBoundSimulatorError(f"unsupported GA source at {name}")
        right = _fp32_constant(node.get("inport1", {}).get("constant"))
        opcode = node.get("alu_opcode")
        if opcode == "add":
            output = np.add(left, right, dtype=np.float32)
        elif opcode == "mul":
            output = np.multiply(left, right, dtype=np.float32)
        else:
            raise DequantConfigBoundSimulatorError(f"unsupported GA opcode {opcode!r}")
        visiting.remove(name)
        values[name] = output
        return output

    first = ("PE00", "PE02", "PE20", "PE22")
    final = ("PE10", "PE12", "PE30", "PE32")
    if set(pe_array) != set(first + final):
        raise DequantConfigBoundSimulatorError("final JSON GA PE set differs")
    lane_outputs = [evaluate(name) for name in final]
    if any(
        not np.array_equal(lane_outputs[0].view(np.uint32), item.view(np.uint32))
        for item in lane_outputs[1:]
    ):
        raise DequantConfigBoundSimulatorError("replicated physical GA lanes disagree")
    return np.ascontiguousarray(lane_outputs[0], dtype=np.float32).tobytes()


def _inverse(payloads: dict[int, bytes], contract: dict[str, Any]) -> bytes:
    if contract.get("logical_shape") != [16, 1000]:
        raise DequantConfigBoundSimulatorError("HIGH4 inverse logical shape differs")
    output = bytearray(16 * 1000 * 4)
    coverage = bytearray(16 * 1000)
    descriptors = contract.get("slices")
    if not isinstance(descriptors, list) or len(descriptors) != SLICE_COUNT:
        raise DequantConfigBoundSimulatorError("HIGH4 inverse descriptor set differs")
    for item in descriptors:
        slice_id = int(item["slice_id"])
        raw = payloads[slice_id]
        for local_sample in range(int(item["sample_count"])):
            for local_feature in range(int(item["feature_count"])):
                src = local_sample * 250 + local_feature
                dst = (
                    (int(item["sample_start"]) + local_sample) * 1000
                    + int(item["feature_start"])
                    + local_feature
                )
                if coverage[dst]:
                    raise DequantConfigBoundSimulatorError("HIGH4 inverse overlaps")
                coverage[dst] = 1
                output[dst * 4 : dst * 4 + 4] = raw[src * 4 : src * 4 + 4]
    if any(value != 1 for value in coverage):
        raise DequantConfigBoundSimulatorError("HIGH4 inverse is incomplete")
    return bytes(output)


def _compare(left: bytes, right: bytes) -> dict[str, Any]:
    if len(left) != len(right) or len(left) % 4:
        raise DequantConfigBoundSimulatorError("comparison payload shape differs")
    a = np.frombuffer(left, dtype=np.float32)
    b = np.frombuffer(right, dtype=np.float32)
    bits_a = a.view(np.uint32)
    bits_b = b.view(np.uint32)
    mismatch = np.flatnonzero(bits_a != bits_b)
    finite = np.isfinite(a) & np.isfinite(b)
    absolute = np.abs(a[finite].astype(np.float64) - b[finite].astype(np.float64))
    return {
        "status": "PASS" if mismatch.size == 0 else "FAIL",
        "element_count": int(a.size),
        "bit_mismatch_count": int(mismatch.size),
        "first_bit_mismatch_index": int(mismatch[0]) if mismatch.size else None,
        "atol": 0.0,
        "rtol": 0.0,
        "max_abs_error": float(absolute.max(initial=0.0)),
        "nan_count_left": int(np.isnan(a).sum()),
        "nan_count_right": int(np.isnan(b).sum()),
        "nan_bit_pattern_match": bool(
            np.array_equal(bits_a[np.isnan(a)], bits_b[np.isnan(b)])
        ),
        "bit_exact": bool(mismatch.size == 0),
    }


def build_three_party_report(root: Path, *, write_physical: bool = False) -> dict[str, Any]:
    root = root.resolve()
    config = json.loads((root / CONFIG_RELATIVE).read_text(encoding="utf-8"))
    package_path = root / PACKAGE_RELATIVE
    e4 = json.loads((root / E4_ANALYSIS_RELATIVE).read_text(encoding="utf-8"))
    e5 = json.loads((root / E5_ANALYSIS_RELATIVE).read_text(encoding="utf-8"))
    atomic = json.loads(
        (root / ATOMIC_ANALYSIS_RELATIVE).read_text(encoding="utf-8")
    )
    if (
        atomic["semantic_conclusion"]["classification"]
        != "ATOMIC_FUNCTIONAL_PASS_OBSERVER_TEMPORAL_EVIDENCE_INCOMPLETE"
        or not atomic["semantic_conclusion"]["atomic_functional_semantics_pass"]
        or atomic["semantic_conclusion"]["atomic_temporal_drain_pass"]
        or atomic["semantic_conclusion"]["counts_as_node0077_e4"]
        or atomic["semantic_conclusion"]["counts_as_node0077_e5"]
        or not atomic["observer"]["does_not_override_formal_readback"]
    ):
        raise DequantConfigBoundSimulatorError("atomic v3 evidence boundary differs")
    if (
        e4["authoritative_classification"] != "FIRST_DYNAMIC_PASS"
        or not e4["counts_as_e4"]
        or e4["counts_as_e5"]
        or e5["authoritative_classification"] != "REPEATED_DYNAMIC_PASS"
        or not e5["counts_as_e5"]
        or not e5["stock_rtl_dynamic_closure"]
    ):
        raise DequantConfigBoundSimulatorError("formal E4/E5 evidence boundary differs")
    with ZipFile(package_path) as archive:
        names = archive.namelist()
        prefix = names[0].split("/", 1)[0] + "/"

        def read(relative: str) -> bytes:
            name = prefix + relative
            if name not in names:
                raise DequantConfigBoundSimulatorError(f"package asset missing: {relative}")
            return archive.read(name)

        strict_raw = read("validation/strict_config.json")
        if json.loads(strict_raw.decode("utf-8")) != config:
            raise DequantConfigBoundSimulatorError("packaged strict JSON differs from final v6")
        source_identity = _json(read("validation/SOURCE_V6_IDENTITY.json"), "source identity")
        mapping = _json(read("validation/mapping_review.json"), "mapping review")
        inverse_contract = _json(
            read("validation/layout_inverse_contract.json"), "inverse contract"
        )
        sca = _json(read("workload/runtime/sca_cfg.json"), "SCA")
        sca_d = _json(read("workload/runtime/sca_cfg_D.json"), "SCA_D")
        execplan = read("workload/runtime/payloads/execplan.txt")
        bitstream = read(
            "workload/runtime/payloads/cfg_pkg/"
            "op0_resnet50_dequant_node0077_uint8_fp32_bitstream_128b.bin"
        )
        # The frozen package canonicalizes text payloads to LF.  SOURCE_V6_IDENTITY
        # points at the pre-package CRLF files, so bind both byte identities by
        # proving the sole transformation is newline normalization.
        if _sha(bitstream.replace(b"\n", b"\r\n")) != source_identity["bitstream"][
            "sha256"
        ]:
            raise DequantConfigBoundSimulatorError("final bitstream identity differs")
        if _sha(execplan.replace(b"\n", b"\r\n")) != source_identity["execplan"][
            "sha256"
        ]:
            raise DequantConfigBoundSimulatorError("final execplan identity differs")
        exec_lines = execplan.decode("ascii").splitlines()
        if len(exec_lines) != int(sca["Exec_Length"]):
            raise DequantConfigBoundSimulatorError("execplan/SCA length differs")
        mapped_ga = {
            item.get("node", "").split(".", 1)[1]
            for item in mapping.get("node_to_resource", [])
            if item.get("node", "").startswith("GA_PE.")
        }
        if mapped_ga != set(config["general_array"]["PE_array"]):
            raise DequantConfigBoundSimulatorError("bitstream mapping PE coverage differs")

        simulator: dict[int, bytes] = {}
        slice_records: list[dict[str, Any]] = []
        physical_root = root / OUTPUT_ROOT_RELATIVE / "physical_d"
        if write_physical:
            physical_root.mkdir(parents=True, exist_ok=True)
        for slice_id in range(SLICE_COUNT):
            a_relative = (
                f"workload/runtime/payloads/op0/slice{slice_id:02d}/"
                "matrix_A_linearized_128bit.txt"
            )
            a_raw = _decode_lines(read(a_relative), 47, a_relative)
            d_raw = _execute_pe_graph(config, a_raw)
            if len(d_raw) != WORDS_PER_SLICE * 4:
                raise DequantConfigBoundSimulatorError("simulator physical D size differs")
            tail = np.frombuffer(d_raw[-8:], dtype=np.uint32)
            if not np.array_equal(tail, np.zeros(2, dtype=np.uint32)):
                raise DequantConfigBoundSimulatorError("simulator D tail is not +0.0f")
            simulator[slice_id] = d_raw
            encoded = _encode_lines(d_raw)
            if len(encoded.decode("ascii").splitlines()) != int(
                sca_d[f"op0_matrixD_slice{slice_id}"]["length"]
            ):
                raise DequantConfigBoundSimulatorError("simulator D/SCA_D length differs")
            output_relative = (
                OUTPUT_ROOT_RELATIVE
                / "physical_d"
                / f"slice{slice_id:02d}_matrix_D_linearized_128bit.txt"
            )
            if write_physical:
                (root / output_relative).write_bytes(encoded)
            slice_records.append(
                {
                    "slice_id": slice_id,
                    "sca_a_base_addr": sca[f"op0_matrixA_slice{slice_id}"]["base_addr"],
                    "sca_d_base_addr": sca_d[f"op0_matrixD_slice{slice_id}"]["base_addr"],
                    "input_sha256": _sha(a_raw),
                    "physical_d_sha256": _sha(d_raw),
                    "physical_d_text_sha256": _sha(encoded),
                    "physical_d_path": output_relative.as_posix(),
                    "valid_word_count": VALID_WORDS_PER_SLICE,
                    "tail_words_hex": ["0x00000000", "0x00000000"],
                }
            )
        golden = read("workload/golden/full_output_fp32.bin")
        logical_simulator = _inverse(simulator, inverse_contract)

    def hardware_payloads(relative_root: Path) -> dict[int, bytes]:
        return {
            slice_id: _decode_lines(
                (
                    root
                    / relative_root
                    / f"slice{slice_id:02d}"
                    / "matrix_D_linearized_128bit.txt"
                ).read_bytes(),
                LINES_PER_SLICE,
                f"{relative_root.as_posix()}/slice{slice_id:02d}",
            )
            for slice_id in range(SLICE_COUNT)
        }

    logical_e4 = _inverse(hardware_payloads(E4_RETURN_ROOT), inverse_contract)
    logical_e5 = _inverse(hardware_payloads(E5_RETURN_ROOT), inverse_contract)
    comparisons = {
        "golden_vs_simulator": _compare(golden, logical_simulator),
        "golden_vs_e4_hardware": _compare(golden, logical_e4),
        "golden_vs_e5_hardware": _compare(golden, logical_e5),
        "simulator_vs_e4_hardware": _compare(logical_simulator, logical_e4),
        "simulator_vs_e5_hardware": _compare(logical_simulator, logical_e5),
        "e4_vs_e5_hardware": _compare(logical_e4, logical_e5),
    }
    if any(item["status"] != "PASS" for item in comparisons.values()):
        raise DequantConfigBoundSimulatorError("three-party comparison failed")
    read_receipt = [
        {**_identity(root, path), "read_scope": "complete_file"} for path in RULE_PATHS
    ]
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "THREE_PARTY_CONFIG_BOUND_CLOSURE_PASS",
        "operator": "DequantizeLinear",
        "node_id": "node0077",
        "config_generation": "v6",
        "candidate_release": True,
        "formal_target_instance_allowed": True,
        "counts_as_formal_resnet_three_party_node": True,
        "project_ledger_delta": {"before": "0/78", "after": "1/78"},
        "executor": {
            "kind": "PROJECT_EQUIVALENT_CONFIG_BOUND_PE_GRAPH_EXECUTOR",
            "ndpfuncmodel_generic_dequant_executor_available": False,
            "consumes_final_strict_json": True,
            "consumes_final_bitstream_and_mapping": True,
            "consumes_execplan_sca_sca_d": True,
            "consumes_physical_a": True,
            "produces_physical_d": True,
            "uses_frozen_high4_inverse": True,
            "software_formula_substitution": False,
            "claim_boundary": "functional config-bound execution; RTL timing is supplied only by formal E4/E5 evidence",
        },
        "read_receipt": read_receipt,
        "source_identity": {
            "config": _identity(root, CONFIG_RELATIVE),
            "e5_package": _identity(root, PACKAGE_RELATIVE),
            "bitstream": {
                "path": source_identity["bitstream"]["path"],
                "size_bytes": len(bitstream),
                "sha256": _sha(bitstream),
            },
            "execplan": {
                "path": source_identity["execplan"]["path"],
                "size_bytes": len(execplan),
                "sha256": _sha(execplan),
            },
            "sca_sha256": _sha(canonical_json_bytes(sca)),
            "sca_d_sha256": _sha(canonical_json_bytes(sca_d)),
            "layout_inverse_sha256": _sha(canonical_json_bytes(inverse_contract)),
            "golden_raw_sha256": _sha(golden),
            "e4_analysis": _identity(root, E4_ANALYSIS_RELATIVE),
            "e5_analysis": _identity(root, E5_ANALYSIS_RELATIVE),
            "e4_return_sha256": e4["return_identity"]["sha256"],
            "e5_return_sha256": e5["return_identity"]["sha256"],
        },
        "hardware_evidence_chain": {
            "handoff": _identity(root, HANDOFF_RELATIVE),
            "atomic_v3": {
                "classification": atomic["semantic_conclusion"]["classification"],
                "role": "MINIMAL_NUMERIC_FUNCTIONAL_PASS_ONLY",
                "formal_d_status": atomic["formal_readback"]["status"],
                "formal_d_bit_exact": atomic["formal_readback"]["all_bit_exact"],
                "observer_temporal_status": atomic["observer"]["status"],
                "observer_does_not_override_formal_d": atomic["observer"][
                    "does_not_override_formal_readback"
                ],
                "counts_as_e4": False,
                "counts_as_e5": False,
                "task_record": _identity(root, ATOMIC_RECORD_RELATIVE),
                "analysis": _identity(root, ATOMIC_ANALYSIS_RELATIVE),
                "return_sha256": atomic["source_return"]["sha256"],
                "source_package_sha256": atomic["package_identity"][
                    "local_zip_sha256"
                ],
            },
            "full_v6_e4": {
                "classification": e4["authoritative_classification"],
                "role": "FORMAL_HARDWARE_FIRST_DYNAMIC_PASS",
                "counts_as_e4": True,
                "counts_as_simulator": False,
                "formal_d_lines": e4["formal_readback"]["total_lines_128bit"],
                "task_record": _identity(root, E4_RECORD_RELATIVE),
                "analysis": _identity(root, E4_ANALYSIS_RELATIVE),
                "return_sha256": e4["return_identity"]["sha256"],
                "source_package_sha256": e4["source_package_identity"]["sha256"],
            },
            "full_v6_e5": {
                "classification": e5["authoritative_classification"],
                "role": "FORMAL_HARDWARE_REPEATED_DYNAMIC_PASS",
                "counts_as_e5": True,
                "counts_as_simulator": False,
                "formal_d_lines": e5["formal_readback"]["total_lines_128bit"],
                "task_record": _identity(root, E5_RECORD_RELATIVE),
                "analysis": _identity(root, E5_ANALYSIS_RELATIVE),
                "return_sha256": e5["return_identity"]["sha256"],
                "source_package_sha256": e5["source_package_identity"]["sha256"],
            },
            "adjudication": (
                "atomic observer temporal incompleteness does not overturn bit-exact "
                "formal D; atomic v3 is not E4/E5; full E4/E5 are hardware evidence "
                "and never substitute for the independent config-bound simulator leg"
            ),
        },
        "physical_layout": {
            "slice_count": SLICE_COUNT,
            "lines_per_slice": LINES_PER_SLICE,
            "fp32_words_per_slice": WORDS_PER_SLICE,
            "valid_fp32_words_per_slice": VALID_WORDS_PER_SLICE,
            "tail_positive_zero_words_per_slice": 2,
            "logical_shape": [16, 1000],
            "simulator_inverse_sha256": _sha(logical_simulator),
        },
        "floating_point_policy": {
            "comparison": "float32 bit-exact per CDA-DEQUANT rules",
            "atol": 0.0,
            "rtol": 0.0,
            "nan_policy": "no NaNs observed; any NaN requires identical payload bits",
            "tail_policy": "two physical tail words per slice are 0x00000000",
        },
        "comparisons": comparisons,
        "physical_d": slice_records,
        "remaining_blockers": [],
        "rule_delta_proposal": (
            "Record a reusable gate requiring config-bound executors to bind final "
            "JSON, encoded bitstream identity, execplan/SCA, physical input/output, "
            "and the same approved inverse before a node enters the three-party ledger."
        ),
        "blocker_delta": {
            "close": ["B_DEQUANT_CONFIG_BOUND_SIMULATOR_LEG"],
            "open": [],
        },
    }
    unsigned = canonical_json_bytes(body)
    body["report_content_sha256"] = _sha(unsigned)
    return body


def write_three_party_evidence(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    root = root.resolve()
    report = build_three_party_report(root, write_physical=True)
    report_path = root / REPORT_RELATIVE
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    contract: dict[str, Any] = {
        "schema": CONTRACT_SCHEMA,
        "status": report["status"],
        "operator": report["operator"],
        "node_id": report["node_id"],
        "config_generation": report["config_generation"],
        "artifact": _identity(root, REPORT_RELATIVE),
        "executor": report["executor"],
        "hardware_evidence_chain": report["hardware_evidence_chain"],
        "comparisons": report["comparisons"],
        "project_ledger_delta": report["project_ledger_delta"],
        "remaining_blockers": report["remaining_blockers"],
        "rule_delta_proposal": report["rule_delta_proposal"],
        "blocker_delta": report["blocker_delta"],
    }
    contract["contract_content_sha256"] = _sha(canonical_json_bytes(contract))
    contract_path = root / CONTRACT_RELATIVE
    contract_path.parent.mkdir(parents=True, exist_ok=True)
    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report, contract


__all__ = [
    "CONTRACT_RELATIVE",
    "REPORT_RELATIVE",
    "DequantConfigBoundSimulatorError",
    "build_three_party_report",
    "write_three_party_evidence",
]
