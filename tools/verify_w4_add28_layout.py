from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np

from resnet50_pipeline.add28_layout import PORT_ORDER, QLinearAddPhysicalLayout
from resnet50_pipeline.profile28 import (
    GLOBAL_RING28_PROFILE,
    GROUP4X7_BATCH_CHANNEL28_PROFILE,
)


def _shape(raw: list[int | str]) -> tuple[int, ...]:
    return tuple(16 if item == "N" else int(item) for item in raw)


def _micro_case(*, dense_broadcast: bool) -> dict[str, np.ndarray]:
    features = 7
    if dense_broadcast:
        a = np.arange(16 * features, dtype=np.uint16).astype(np.uint8).reshape(
            16, features
        )
        b = (np.arange(features, dtype=np.uint16) * 3 + 11).astype(np.uint8)
    else:
        a = np.arange(16 * features * 2 * 3, dtype=np.uint16).astype(
            np.uint8
        ).reshape(16, features, 2, 3)
        b = (a.astype(np.uint16) * 5 + 17).astype(np.uint8)
    a_scale = np.array([0.03125], np.float32)
    a_zero_point = np.array([111], np.uint8)
    b_scale = np.array([0.0625], np.float32)
    b_zero_point = np.array([123], np.uint8)
    y_scale = np.array([0.046875], np.float32)
    y_zero_point = np.array([97], np.uint8)
    left = (a.astype(np.int32) - int(a_zero_point[0])).astype(np.float32)
    right = (b.astype(np.int32) - int(b_zero_point[0])).astype(np.float32)
    real = left * a_scale[0] + right * b_scale[0]
    output = np.clip(
        np.rint(real / y_scale[0]).astype(np.int64) + int(y_zero_point[0]),
        0,
        255,
    ).astype(np.uint8)
    return {
        "a": a,
        "a_scale": a_scale,
        "a_zero_point": a_zero_point,
        "b": b,
        "b_scale": b_scale,
        "b_zero_point": b_zero_point,
        "y_scale": y_scale,
        "y_zero_point": y_zero_point,
        "output": output,
    }


def _payload_sha256(bundle: Any) -> str:
    digest = hashlib.sha256()
    for port in PORT_ORDER:
        for slice_id in range(bundle.geometry.slice_count):
            digest.update(port.encode("ascii"))
            digest.update(slice_id.to_bytes(2, "little"))
            digest.update(bundle.read(port, slice_id))
    return digest.hexdigest()


def _micro_report(profile_id: str, dense_broadcast: bool) -> dict[str, Any]:
    layout = QLinearAddPhysicalLayout(profile_id)
    values = _micro_case(dense_broadcast=dense_broadcast)
    first = layout.forward(**values)
    second = layout.forward(**values)
    recovered = layout.inverse(first)
    expected = {
        "add_input_a": values["a"],
        "add_a_scale": values["a_scale"],
        "add_a_zero_point": values["a_zero_point"],
        "add_input_b": values["b"],
        "add_b_scale": values["b_scale"],
        "add_b_zero_point": values["b_zero_point"],
        "add_y_scale": values["y_scale"],
        "add_y_zero_point": values["y_zero_point"],
        "add_output": values["output"],
    }
    first_hash = _payload_sha256(first)
    return {
        "layout_id": layout.contract,
        "profile_id": profile_id,
        "broadcast_mode": first.metadata["broadcast_mode"],
        "validation": layout.validate(first),
        "all_inverse_bit_exact": all(
            np.array_equal(recovered[tensor_id], logical)
            for tensor_id, logical in expected.items()
        ),
        "independent_qparams": bool(
            values["a_scale"][0] != values["b_scale"][0]
            and values["a_zero_point"][0] != values["b_zero_point"][0]
        ),
        "deterministic_payload": first_hash == _payload_sha256(second),
        "payload_sha256": first_hash,
    }


def _formal_families(project_root: Path) -> dict[str, Any]:
    graph_path = project_root / "artifacts/w3/model_graph.json"
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    tensors = {item["tensor_id"]: item for item in graph["tensors"]}
    nodes = {item["node_id"]: item for item in graph["nodes"]}
    add_nodes = [item for item in graph["nodes"] if item["op_type"] == "QLinearAdd"]
    families: dict[tuple[tuple[int, ...], tuple[int, ...]], list[dict[str, Any]]] = {}
    all_qparams_independent = True
    producer_pairs: Counter[str] = Counter()
    for node in add_nodes:
        inputs = node["input_tensor_ids"]
        a_shape = _shape(tensors[inputs[0]]["shape"])
        b_shape = _shape(tensors[inputs[3]]["shape"])
        qparam_ids = (inputs[1], inputs[2], inputs[4], inputs[5], inputs[6], inputs[7])
        all_qparams_independent &= len(set(qparam_ids)) == len(qparam_ids)
        a_producer = tensors[inputs[0]]["producer_node_id"]
        b_producer = tensors[inputs[3]]["producer_node_id"]
        a_family = nodes[a_producer]["op_type"] if a_producer else "initializer"
        b_family = nodes[b_producer]["op_type"] if b_producer else "initializer"
        producer_pairs[f"{a_family}+{b_family}"] += 1
        families.setdefault((a_shape, b_shape), []).append(node)

    family_reports: list[dict[str, Any]] = []
    for (a_shape, b_shape), members in sorted(
        families.items(), key=lambda item: (item[0][0], item[0][1])
    ):
        capacities = {
            profile: QLinearAddPhysicalLayout(profile).capacity_report(
                a_shape=a_shape, b_shape=b_shape
            )
            for profile in (
                GROUP4X7_BATCH_CHANNEL28_PROFILE,
                GLOBAL_RING28_PROFILE,
            )
        }
        family_reports.append(
            {
                "a_shape": a_shape,
                "b_shape": b_shape,
                "node_count": len(members),
                "node_ids": [item["node_id"] for item in members],
                "broadcast_mode": next(iter(capacities.values()))["broadcast_mode"],
                "profiles": capacities,
            }
        )
    return {
        "model_sha256": graph["model_sha256"],
        "model_graph_sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
        "add_node_count": len(add_nodes),
        "residual_same_shape_count": sum(
            len(members)
            for (a_shape, b_shape), members in families.items()
            if a_shape == b_shape
        ),
        "dense_vector_broadcast_count": sum(
            len(members)
            for (a_shape, b_shape), members in families.items()
            if len(a_shape) == 2 and len(b_shape) == 1
        ),
        "all_six_qparam_tensor_ids_independent_per_node": all_qparams_independent,
        "producer_family_pairs": dict(sorted(producer_pairs.items())),
        "families": family_reports,
    }


def _alias_policy_report() -> dict[str, Any]:
    layout = QLinearAddPhysicalLayout()
    shape = (16, 5, 2, 2)
    raw = layout.plan(a_shape=shape, b_shape=shape)
    try:
        layout.plan(
            a_shape=shape,
            b_shape=shape,
            input_offsets={"A": 0, "B": 0},
        )
    except ValueError as error:
        overlap_rejected = "overlap" in str(error)
    else:
        overlap_rejected = False
    separated = layout.plan(
        a_shape=shape,
        b_shape=shape,
        input_offsets={"A": 0, "B": 1 << 20},
    )
    return {
        "policy": "reject_any_per_slice_live_range_overlap",
        "overlapping_dual_alias_rejected": overlap_rejected,
        "non_overlapping_dual_alias_accepted": True,
        "ordinary_plan_A_B_non_overlapping": (
            raw["offsets"]["A"] + raw["aligned_sizes"]["A"]
            <= raw["offsets"]["B"]
        ),
        "separated_offsets": {
            "A": separated["offsets"]["A"],
            "B": separated["offsets"]["B"],
        },
    }


def build_report(project_root: Path | None = None) -> dict[str, Any]:
    root = (project_root or Path(__file__).resolve().parents[1]).resolve()
    profiles = {}
    for profile in (
        GROUP4X7_BATCH_CHANNEL28_PROFILE,
        GLOBAL_RING28_PROFILE,
    ):
        profiles[profile] = {
            "same_shape": _micro_report(profile, False),
            "dense_vector_broadcast": _micro_report(profile, True),
        }
    return {
        "schema": "w4_add28_candidate_report_v1",
        "operator": "QLinearAdd",
        "target_family": "rtl28",
        "status": "candidate_unapproved",
        "hardware_approval": False,
        "g4_passed": False,
        "w5_authorized": False,
        "formal_contract": {
            "ports": list(PORT_ORDER),
            "A_B_D_dtype": "uint8",
            "qparams": "three independent scalar float32/uint8 pairs",
            "broadcast_modes": ["same_shape", "dense_vector_broadcast"],
            "unsupported_broadcasts": "fail_closed",
        },
        "profiles": profiles,
        "formal_resnet": _formal_families(root),
        "alias_policy": _alias_policy_report(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic small W4 RTL28 QLinearAdd candidate evidence."
    )
    parser.add_argument("--project-root", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        help="Explicit JSON destination. Without this option no file is written.",
    )
    args = parser.parse_args()
    report = build_report(args.project_root)
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(encoded, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
