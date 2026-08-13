from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5_complete_json_regeneration_v1/qlinearadd"
)
PUBLIC = OUT / "complete_json"
INVENTORY = OUT / "stage_inventory.json"
DETAILED_LEDGER = OUT / "field_provenance_ledger.json"
CURRENT_CONFIG = (
    ROOT / "configs/native_ndp_sim/qlinearadd_node0007_fp32_output32_v36"
)
LOWERING = ROOT / "contracts/resnet50_r5_lowering_bundle.json"
V35_REPORT = (
    ROOT
    / "artifacts/operator_config_validation/"
    "r5-qlinearadd-node0007-v35-return-analysis/report.json"
)
V36_PACKAGE = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/"
    "r5_qadd_n7_cout32_v36.zip"
)
PHYSICAL_STAGES = (
    "op_a_dequant",
    "op_b_dequant",
    "op_relocation_pad",
    "op_fp32_add",
    "op_tail_mul",
    "op_tail_round",
)
LOGICAL_KEYS = (
    "identity",
    "op",
    "dtypes",
    "shapes",
    "qparams",
    "padding_tail",
    "layout",
    "dag",
    "edges",
)
PUBLIC_AXES = (
    "op",
    "dtype",
    "shape",
    "layout",
    "qparams",
    "topology",
    "address",
    "schedule",
    "consumer",
)
CHANGED_AXES = (
    "shape",
    "dtype",
    "qparam",
    "layout",
    "address",
    "cross_stage_schedule",
)


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def bound(path: Path) -> dict[str, str]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha(path),
    }


def escape(token: str) -> str:
    return token.replace("~", "~0").replace("/", "~1")


def leaves(value: Any, pointer: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        if not value:
            yield pointer or "/", value
        for key in sorted(value):
            yield from leaves(value[key], f"{pointer}/{escape(str(key))}")
    elif isinstance(value, list):
        if not value:
            yield pointer or "/", value
        for index, item in enumerate(value):
            yield from leaves(item, f"{pointer}/{index}")
    else:
        yield pointer or "/", value


def pointer_value(value: Any, pointer: str) -> tuple[bool, Any]:
    current = value
    for raw in pointer.split("/")[1:]:
        token = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, list):
            try:
                current = current[int(token)]
            except (ValueError, IndexError):
                return False, None
        elif isinstance(current, dict) and token in current:
            current = current[token]
        else:
            return False, None
    return True, current


def nullify(value: Any) -> Any:
    if isinstance(value, dict):
        if not value:
            return None
        return {key: nullify(item) for key, item in value.items()}
    if isinstance(value, list):
        if not value:
            return None
        return [nullify(item) for item in value]
    return None


def exactness(resolved: bool) -> dict[str, bool]:
    if resolved:
        return {axis: True for axis in PUBLIC_AXES}
    return {
        "op": True,
        "dtype": False,
        "shape": False,
        "layout": False,
        "qparams": False,
        "topology": False,
        "address": False,
        "schedule": False,
        "consumer": True,
    }


def build_candidate(inventory: dict[str, Any]) -> dict[str, Any]:
    configs = {
        stage: load(CURRENT_CONFIG / f"{stage}.json")
        for stage in PHYSICAL_STAGES
    }
    targets: dict[str, Any] = {}
    for plan in inventory["targets"]:
        target_id = plan["identity"]["hw_op_id"]
        target = {key: plan[key] for key in LOGICAL_KEYS}
        target["physical_stages"] = {
            stage: {"strict_hardware_json": nullify(configs[stage])}
            for stage in PHYSICAL_STAGES
        }
        targets[target_id] = target
    return {"targets": targets}


def build_projection(candidate: dict[str, Any]) -> dict[str, Any]:
    target_id = "hwop-0007-00"
    target = json.loads(json.dumps(candidate["targets"][target_id]))
    for stage in PHYSICAL_STAGES:
        target["physical_stages"][stage]["strict_hardware_json"] = load(
            CURRENT_CONFIG / f"{stage}.json"
        )
    return {"targets": {target_id: target}}


def main() -> int:
    outputs = {
        "candidate": PUBLIC / "blocked_candidate_schema.json",
        "ledger": PUBLIC / "public_field_provenance_ledger.json",
        "handler": PUBLIC / "public_handler_capability.json",
        "diff": PUBLIC / "public_current_test_diff.json",
        "composition": PUBLIC / "composition_boundary.json",
        "receipt": PUBLIC / "derivation_receipt.json",
        "projection": PUBLIC / "current_test_projection.json",
        "contract": PUBLIC / "candidate_contract.json",
        "family_set": OUT / "family_set.json",
    }
    existing = [
        str(path)
        for key, path in outputs.items()
        if key in {"contract", "family_set"} and path.exists()
    ]
    if existing:
        raise ValueError(f"fresh public contract outputs required: {existing}")

    inventory = load(INVENTORY)
    detailed = load(DETAILED_LEDGER)
    lowering = load(LOWERING)
    stage_ids = [
        request["identity"]["hw_op_id"]
        for request in lowering["requests"]
        if request["identity"]["hw_op_type"] == "QLinearAddUint8"
    ]
    if len(stage_ids) != 17 or stage_ids != [
        item["identity"]["hw_op_id"] for item in inventory["targets"]
    ]:
        raise ValueError("QLinearAdd lowering/inventory stage binding mismatch")

    receipt = {
        "schema": "qlinearadd-complete-json-derivation-receipt-v1",
        "pass": True,
        "family": "qlinearadd",
        "target_hw_op_types": ["QLinearAddUint8"],
        "stage_ids": stage_ids,
        "inputs": {
            "lowering": bound(LOWERING),
            "inventory": bound(INVENTORY),
            "detailed_ledger": bound(DETAILED_LEDGER),
            "v35_return_report": bound(V35_REPORT),
            "v36_source_package": bound(V36_PACKAGE),
            "v36_current_configs": {
                stage: bound(CURRENT_CONFIG / f"{stage}.json")
                for stage in PHYSICAL_STAGES
            },
        },
        "claim_boundary": (
            "Typed logical/DAG provenance and fail-closed blocked schema only; "
            "no strict target hardware JSON, mapping, bitstream, execplan, SCA, "
            "server package, server action, numeric rerun, or golden rerun."
        ),
    }
    write(outputs["receipt"], receipt)

    candidate = build_candidate(inventory)
    write(outputs["candidate"], candidate)
    candidate_sha = sha(outputs["candidate"])
    candidate_leaves = dict(leaves(candidate))
    detailed_by_pointer = {
        item["json_pointer"]: item for item in detailed["records"]
    }
    if set(candidate_leaves) != set(detailed_by_pointer):
        missing = sorted(set(candidate_leaves) - set(detailed_by_pointer))
        extra = sorted(set(detailed_by_pointer) - set(candidate_leaves))
        raise ValueError(
            f"candidate/detailed-ledger leaf mismatch: "
            f"missing={missing[:3]}; extra={extra[:3]}"
        )

    public_entries = []
    absences = []
    unresolved_pointers = []
    for pointer, target_value in candidate_leaves.items():
        source = detailed_by_pointer[pointer]
        unresolved = source["status"] == "UNRESOLVED"
        origin = source["origin"]
        if origin == "REFERENCE_EXACT":
            origin = "MODEL_DERIVED"
        entry = {
            "json_pointer": pointer,
            "target_value": target_value,
            "origin": "UNRESOLVED" if unresolved else origin,
            "applicability_class": (
                "UNRESOLVED" if unresolved else "DERIVED_FOR_TARGET"
            ),
            "exactness_axes": exactness(not unresolved),
            "owner": source["owner"],
            "consumer_equation": source["current_consumer_equation"],
            "derivation_receipt": (
                None if unresolved else bound(outputs["receipt"])
            ),
            "source": source["source"],
            "negative_control_ids": [
                (
                    "QADD-UNKNOWN-LEAF-IMPLICIT-ZERO-FAIL"
                    if unresolved
                    else "QADD-DERIVED-LEAF-MUTATION-FAIL"
                )
            ],
            "status": "UNRESOLVED" if unresolved else "RESOLVED",
        }
        public_entries.append(entry)
        state = (
            "SOURCE_ABSENT_UNKNOWN_FOR_TARGET"
            if unresolved
            else "TARGET_REQUIRED_DERIVED"
        )
        absences.append(
            {
                "target_json_pointer": pointer,
                "state": state,
                "reason": (
                    "Current project v36 value is comparison-only and no "
                    "authorized target handler/consumer derivation proves it."
                    if unresolved
                    else "Typed target value is derived from the bound lowering/"
                    "DAG receipt rather than copied from a native template."
                ),
                "owner": source["owner"],
            }
        )
        if unresolved:
            unresolved_pointers.append(pointer)

    ledger = {
        "schema": "operator_config_field_provenance_ledger_v1",
        "family": "qlinearadd",
        "candidate_json_sha256": candidate_sha,
        "entries": public_entries,
        "source_absences": absences,
        "unresolved_leaf_count": len(unresolved_pointers),
        "unresolved_leaf_ordered_sha256": hashlib.sha256(
            "\n".join(unresolved_pointers).encode("utf-8")
        ).hexdigest(),
        "claim_boundary": (
            "One entry for every blocked candidate leaf. Null hardware leaves "
            "mean unknown-for-target, never implicit zero or inactive."
        ),
    }
    write(outputs["ledger"], ledger)

    handler = {
        "schema": "operator_config_handler_capability_v1",
        "family": "qlinearadd",
        "handler": {
            "kind": "NONE",
            "path": None,
            "sha256": None,
            "source_span": None,
        },
        "capabilities": {
            axis: {
                "supported": False,
                "evidence": (
                    "No native QLinearAddUint8 composite handler proves this "
                    "axis for the 17 target instances."
                ),
            }
            for axis in (
                "exact_replay",
                "shape",
                "dtype",
                "qparam",
                "layout",
                "address",
                "cross_stage_schedule",
            )
        },
        "dependent_leaves": [
            {
                "json_pointer": pointer,
                "axes": list(CHANGED_AXES),
                "covered_by": "NONE_NO_AUTHORIZED_COMPOSITE_HANDLER",
                "status": "UNCOVERED",
            }
            for pointer in unresolved_pointers
        ],
        "claim_boundary": (
            "Capability denial for target generalization. Primitive placeholder/"
            "example handlers and project v36 JSON do not become authority."
        ),
    }
    write(outputs["handler"], handler)

    boundaries = []
    for plan in inventory["targets"]:
        target_id = plan["identity"]["hw_op_id"]
        shape = json.dumps(plan["shapes"]["y"], separators=(",", ":"))
        logical_bytes = f"0..4*product({shape})"
        for boundary_id, producer, consumer, dtype, qparam in (
            (
                "a_scaled_to_fp32_add",
                "op_a_dequant",
                "op_fp32_add",
                "float32",
                "a_zero_point/a_scale W3 order",
            ),
            (
                "b_scaled_to_relocation",
                "op_b_dequant",
                "op_relocation_pad",
                "float32",
                "b_zero_point/b_scale W3 order",
            ),
            (
                "relocation_to_fp32_add",
                "op_relocation_pad",
                "op_fp32_add",
                "float32",
                "node0076 modulo-1000 replay; identity otherwise",
            ),
            (
                "sum_to_tail_mul",
                "op_fp32_add",
                "op_tail_mul",
                "float32",
                "exact FP32 division by y_scale",
            ),
            (
                "tail_mul_to_round",
                "op_tail_mul",
                "op_tail_round",
                "float32",
                "RNE then y_zero_point then uint8 saturation",
            ),
        ):
            byte_set = (
                "B_SCALED typed [0,4000), physical [0,4032), replay modulo 1000"
                if target_id == "r5:hwop-0076-00"
                and boundary_id in {
                    "b_scaled_to_relocation",
                    "relocation_to_fp32_add",
                }
                else logical_bytes
            )
            boundaries.append(
                {
                    "boundary_id": f"{target_id}:{boundary_id}",
                    "producer": producer,
                    "consumer": consumer,
                    "producer_dtype": dtype,
                    "consumer_dtype": dtype,
                    "shape": shape,
                    "layout": plan["layout"]["layout_id"],
                    "producer_byte_set": byte_set,
                    "consumer_required_byte_set": byte_set,
                    "transaction_bytes": 32,
                    "tag_last": "UNRESOLVED target occurrence/terminal carrier",
                    "clock_handshake": "UNRESOLVED target accepted handshake",
                    "lifetime_visibility": "UNRESOLVED target address/barrier lifetime",
                    "qparam_rounding": qparam,
                    "status": "UNRESOLVED",
                    "evidence": [
                        INVENTORY.relative_to(ROOT).as_posix(),
                        DETAILED_LEDGER.relative_to(ROOT).as_posix(),
                    ],
                }
            )
    composition = {
        "schema": "operator_config_composition_boundary_v1",
        "family": "qlinearadd",
        "boundaries": boundaries,
        "claim_boundary": (
            "The 85 logical inter-stage boundaries preserve typed/W3 intent, "
            "but target hardware byte-set carriers, addresses, accepted "
            "handshakes, visibility, and terminals remain unresolved."
        ),
    }
    write(outputs["composition"], composition)

    projection = build_projection(candidate)
    write(outputs["projection"], projection)
    diff_entries = []
    for pointer, candidate_value in candidate_leaves.items():
        present, current_value = pointer_value(projection, pointer)
        if not present:
            classification = "CURRENT_ABSENT"
            reason = "No current tested configuration exists for this target stage."
        elif current_value == candidate_value:
            classification = "SAME"
            reason = "Projection value equals the blocked candidate schema value."
        else:
            classification = "NEW_CANDIDATE_DEFECT"
            reason = (
                "Candidate hardware leaf is intentionally unresolved/null while "
                "current node0007 v36 has a project value; candidate is not runnable."
            )
        diff_entries.append(
            {
                "json_pointer": pointer,
                "candidate_value": candidate_value,
                "current_value_present": present,
                "current_value": current_value if present else None,
                "classification": classification,
                "reason": reason,
                "evidence": [
                    outputs["candidate"].relative_to(ROOT).as_posix(),
                    outputs["projection"].relative_to(ROOT).as_posix(),
                ],
            }
        )
    ga_fix_pointers = [
        pointer
        for pointer in candidate_leaves
        if pointer.startswith(
            "/targets/hwop-0007-00/physical_stages/op_fp32_add/"
            "strict_hardware_json/general_array/PE_array/"
        )
        and any(f"/{pe}/" in pointer for pe in ("PE10", "PE12", "PE30", "PE32"))
    ]
    current_diff = {
        "schema": "operator_config_current_test_diff_v1",
        "family": "qlinearadd",
        "candidate_json_sha256": candidate_sha,
        "current_identity": {
            "available": True,
            "path": outputs["projection"].relative_to(ROOT).as_posix(),
            "sha256": sha(outputs["projection"]),
            "package_or_record": (
                "node0007 v36 read-only projection; source package "
                f"{sha(V36_PACKAGE)}"
            ),
            "latest_result": (
                "v35 CONFIG_EXPLAINS; v36 PACKAGE_READY_NOT_RUN_SPLIT_C_ONLY"
            ),
        },
        "entries": diff_entries,
        "blocker_attribution": [
            {
                "blocker_id": "V35_FP32_GA_16B_VS_BUFFER5_32B",
                "classification": "CONFIG_EXPLAINS",
                "candidate_json_pointers": ga_fix_pointers,
                "reason": (
                    "v35 four 4B GA lanes supplied 16B; v36 adds four lanes for "
                    "32B. The latest v35 return directly localizes this mismatch."
                ),
                "evidence": [
                    V35_REPORT.relative_to(ROOT).as_posix(),
                    V36_PACKAGE.relative_to(ROOT).as_posix(),
                ],
            },
            {
                "blocker_id": "V36_DYNAMIC_SPLIT_C_AND_FULL_CHAIN",
                "classification": "DYNAMIC_ONLY",
                "candidate_json_pointers": [],
                "reason": (
                    "Buffer5 accepted write, MSE wdata, natural terminal, "
                    "stage-local D and full-chain 28D require a formal return."
                ),
                "evidence": [V36_PACKAGE.relative_to(ROOT).as_posix()],
            },
            {
                "blocker_id": "HISTORICAL_OBSERVER_PACKAGE_RTL_CAUSES",
                "classification": "CONFIG_EXCLUDED",
                "candidate_json_pointers": [],
                "reason": (
                    "Historical observer/runner/transport/RTL identity issues "
                    "do not explain the v35 consumer-equation supply mismatch."
                ),
                "evidence": [V35_REPORT.relative_to(ROOT).as_posix()],
            },
        ],
        "claim_boundary": (
            "Leaf-complete comparison against an explicitly identified "
            "read-only node0007 v36 projection. Other 16 stages are "
            "CURRENT_ABSENT. This is not a runnable candidate."
        ),
    }
    write(outputs["diff"], current_diff)

    contract = {
        "schema": "operator_config_complete_json_candidate_v1",
        "family": "qlinearadd",
        "candidate_status": "BLOCKED",
        "reference_class": "D",
        "changed_axes": list(CHANGED_AXES),
        "target_hw_op_types": ["QLinearAddUint8"],
        "stage_ids": stage_ids,
        "candidate_json": bound(outputs["candidate"]),
        "field_provenance_ledger": bound(outputs["ledger"]),
        "handler_capability": bound(outputs["handler"]),
        "current_test_diff": bound(outputs["diff"]),
        "composition": {
            "required": True,
            "boundary": bound(outputs["composition"]),
        },
        "artifact_root": OUT.relative_to(ROOT).as_posix(),
        "claim_boundary": (
            "17-stage fail-closed blocked schema and exact unresolved leaf set. "
            "No materialized strict target JSON or downstream/server artifact."
        ),
    }
    write(outputs["contract"], contract)
    family_set = {
        "schema": "operator_config_complete_json_family_set_v1",
        "family": "qlinearadd",
        "target_hw_op_types": ["QLinearAddUint8"],
        "candidate_contracts": [bound(outputs["contract"])],
        "no_config_stages": [],
        "claim_boundary": (
            "All 17 QLinearAddUint8 lowering stages occur exactly once in one "
            "BLOCKED family contract; none is treated as metadata-only."
        ),
    }
    write(outputs["family_set"], family_set)

    print(
        json.dumps(
            {
                "status": "BLOCKED_PUBLIC_CONTRACT_WRITTEN",
                "stage_count": len(stage_ids),
                "candidate_leaf_count": len(candidate_leaves),
                "unresolved_leaf_count": len(unresolved_pointers),
                "composition_boundary_count": len(boundaries),
                "contract": bound(outputs["contract"]),
                "family_set": bound(outputs["family_set"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
