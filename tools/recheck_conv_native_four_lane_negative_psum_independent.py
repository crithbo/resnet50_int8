from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import onnx
from onnx import numpy_helper


MODEL = Path("artifacts/reference_model/resnet50-v1-12-int8.onnx")
ACTIVATION = Path(
    "artifacts/w3/golden_batch16/tensors/tensor-8d2f28c80ac24676.npy"
)
LOWERING = Path("contracts/resnet50_r5_lowering_bundle.json")

MODEL_SHA256 = "c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0"
ACTIVATION_SHA256 = (
    "e4039c779c0083ff3cbe76845b4ba313e9b2e095e4faa72d329cbfa04f6cae1b"
)
LOWERING_SHA256 = (
    "bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432"
)
REQUEST_SHA256 = (
    "258de9630b244851cecd8b9bcb0c19686f4909d82d16cb124d46d42815a34fbd"
)

WEIGHT_NAME = "ConvBnFusion_W_resnetv17_stage1_conv3_weight_quantized"
BIAS_NAME = "ConvBnFusion_BN_B_resnetv17_stage1_batchnorm3_beta_quantized"
WEIGHT_ZP_NAME = "ConvBnFusion_W_resnetv17_stage1_conv3_weight_zero_point"
INITIALIZER_SHA256 = {
    WEIGHT_NAME: "1e151c63b51447135cb5e0efdc122aa8837516119730768bab845d11846179e2",
    BIAS_NAME: "82f0094f044e869a180de66bcf86961f43468cbe9d44bbc3aa07c9b647c3a84f",
    WEIGHT_ZP_NAME: "5341e6b2646979a70e57653007a1f310169421ec9bdd9f1a5648f75ade005af1",
}

SAMPLE = 0
OUTPUT_H = 23
OUTPUT_W = 40
OUTPUT_CHANNEL = 33
K_GROUP = 14
X_ZERO_POINT = 0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def array_sha256(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest()


def s32(value: int) -> int:
    bits = value & 0xFFFFFFFF
    return bits - (1 << 32) if bits >= (1 << 31) else bits


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_initializers(model_path: Path) -> dict[str, np.ndarray]:
    model = onnx.load(model_path, load_external_data=True)
    wanted = {WEIGHT_NAME, BIAS_NAME, WEIGHT_ZP_NAME}
    values = {
        item.name: np.asarray(numpy_helper.to_array(item))
        for item in model.graph.initializer
        if item.name in wanted
    }
    require(set(values) == wanted, "required ONNX initializer is missing")
    return values


def find_request(lowering_path: Path) -> dict[str, Any]:
    lowering = json.loads(lowering_path.read_text(encoding="utf-8"))
    matches = [
        request
        for request in lowering["requests"]
        if request["identity"]["hw_op_id"] == "hwop-0003-00"
    ]
    require(len(matches) == 1, "hwop-0003-00 request identity is not unique")
    request = matches[0]
    require(
        request["request_sha256"] == REQUEST_SHA256,
        "typed request SHA receipt differs",
    )
    return request


def build_report(root: Path) -> dict[str, Any]:
    model_path = root / MODEL
    activation_path = root / ACTIVATION
    lowering_path = root / LOWERING
    require(sha256_file(model_path) == MODEL_SHA256, "ONNX model SHA differs")
    require(
        sha256_file(activation_path) == ACTIVATION_SHA256,
        "W3 activation SHA differs",
    )
    require(
        sha256_file(lowering_path) == LOWERING_SHA256,
        "typed lowering SHA differs",
    )
    request = find_request(lowering_path)

    activation = np.load(activation_path, allow_pickle=False)
    require(activation.dtype == np.uint8, "activation dtype is not uint8")
    require(
        tuple(activation.shape) == (16, 64, 56, 56),
        "activation shape differs",
    )
    initializers = load_initializers(model_path)
    for name, expected_sha in INITIALIZER_SHA256.items():
        require(
            array_sha256(initializers[name]) == expected_sha,
            f"initializer content SHA differs: {name}",
        )

    weight = initializers[WEIGHT_NAME]
    bias = initializers[BIAS_NAME]
    weight_zp = initializers[WEIGHT_ZP_NAME]
    require(weight.dtype == np.int8, "weight dtype is not int8")
    require(bias.dtype == np.int32, "bias dtype is not int32")
    require(weight_zp.dtype == np.int8, "weight zero point dtype is not int8")
    require(tuple(weight.shape) == (256, 64, 1, 1), "weight shape differs")
    require(tuple(bias.shape) == (256,), "bias shape differs")
    require(tuple(weight_zp.shape) == (256,), "weight zero-point shape differs")
    require(np.all(weight_zp == 0), "weight zero point is nonzero")

    activation_k = activation[SAMPLE, :, OUTPUT_H, OUTPUT_W].astype(np.int64)
    corrected_weight_k = (
        weight[OUTPUT_CHANNEL, :, 0, 0].astype(np.int64)
        - int(weight_zp[OUTPUT_CHANNEL])
    )
    corrected_bias = s32(
        int(bias[OUTPUT_CHANNEL])
        - X_ZERO_POINT * int(np.sum(corrected_weight_k, dtype=np.int64))
    )

    groups: list[dict[str, Any]] = []
    psum = corrected_bias
    for group in range(16):
        start = group * 4
        activation_lanes = activation_k[start : start + 4]
        weight_lanes = corrected_weight_k[start : start + 4]
        products = activation_lanes * weight_lanes
        dot4 = int(np.sum(products, dtype=np.int64))
        psum_before = psum
        psum = s32(psum + dot4)
        groups.append(
            {
                "k_group": group,
                "activation_u8_lanes": [int(x) for x in activation_lanes],
                "weight_s8_lanes": [int(x) for x in weight_lanes],
                "lane_products": [int(x) for x in products],
                "dot4_s32": dot4,
                "psum_before_s32": psum_before,
                "psum_after_s32": psum,
            }
        )

    witness = groups[K_GROUP]
    require(corrected_bias == 5687, "corrected bias differs from witness")
    require(
        sum(item["dot4_s32"] for item in groups[:K_GROUP]) == -5692,
        "prefix dot4 sum differs from witness",
    )
    require(
        witness["activation_u8_lanes"] == [21, 24, 24, 26],
        "witness activation lanes differ",
    )
    require(
        witness["weight_s8_lanes"] == [-1, 0, 0, 1],
        "witness weight lanes differ",
    )
    require(witness["dot4_s32"] == 5, "witness dot4 differs")
    require(witness["psum_before_s32"] == -5, "witness psum differs")
    require(witness["psum_after_s32"] == 0, "witness next psum is not zero")

    return {
        "schema": "conv-native-four-lane-mainline-independent-data-recheck-v1",
        "status": "REAL_W3_CONV_BOUNDARY_REPRODUCED",
        "independence": {
            "imports_owner_module": False,
            "uses_owner_scan_output_as_input": False,
            "method": (
                "Direct ONNX initializer and W3 activation extraction; "
                "plain NumPy signed recurrence."
            ),
        },
        "source_receipts": {
            MODEL.as_posix(): MODEL_SHA256,
            ACTIVATION.as_posix(): ACTIVATION_SHA256,
            LOWERING.as_posix(): LOWERING_SHA256,
            WEIGHT_NAME: INITIALIZER_SHA256[WEIGHT_NAME],
            BIAS_NAME: INITIALIZER_SHA256[BIAS_NAME],
            WEIGHT_ZP_NAME: INITIALIZER_SHA256[WEIGHT_ZP_NAME],
            "typed_request_sha256": REQUEST_SHA256,
        },
        "typed_request": {
            "request_id": request["request_id"],
            "identity": request["identity"],
            "logical_geometry": request["logical_geometry"],
        },
        "coordinate": {
            "sample": SAMPLE,
            "output_h": OUTPUT_H,
            "output_w": OUTPUT_W,
            "output_channel": OUTPUT_CHANNEL,
            "k_group": K_GROUP,
        },
        "corrected_bias_s32": corrected_bias,
        "prefix_groups_0_through_13_dot4_sum_s32": sum(
            item["dot4_s32"] for item in groups[:K_GROUP]
        ),
        "witness": witness,
        "full_output_accumulator_s32": psum,
        "all_16_groups": groups,
        "claim_boundary": (
            "One frozen real node0003 Conv occurrence. This independently proves "
            "reachability of psum=-5,dot4=+5; it does not independently recount "
            "the owner's aggregate 528 hits across 19 Conv instances."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["witness"], sort_keys=True))
    print(report["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
