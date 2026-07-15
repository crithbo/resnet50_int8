from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from resnet50_pipeline.conv_instance import make_conv_target_request
from generate_conv_1x1_real import build_real_1x1
from generate_conv_1x1_requant_real import build_bundle


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "conv_full.json"
BASE_SEMANTICS_PATH = ROOT / "contracts" / "conv_1x1_lc_pe_stream_semantics.json"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _semantic_contract(
    base: dict[str, Any],
    *,
    request,
    config: dict[str, Any],
    config_bytes: bytes,
    encoder_evidence: dict[str, Any] | None,
) -> dict[str, Any]:
    spec = request.spec
    contract = deepcopy(base)
    contract["status"] = (
        "official_encoder_passed_high4_selector_resolved_adapter_semantics_candidate"
        if encoder_evidence is not None
        else "candidate_pending_official_encoder"
    )
    contract["instance"] = {
        "node_id": spec.node_id,
        "hw_op_ids": [spec.accumulate_hw_op_id, spec.requant_hw_op_id],
        "activation_shape": list(spec.activation_shape),
        "weight_shape": list(spec.weight_shape),
        "output_shape": list(spec.output_shape),
        "strides": list(spec.strides),
        "pads": list(spec.pads),
        "dilations": list(spec.dilations),
        "group": spec.group,
        "static_json_scope": (
            "one-sample accumulation microprogram; batch-16 and seven HIGH-4 "
            "groups are request-adapter scheduling"
        ),
    }
    loops = config["dram_loop_configs"]
    for item in contract["lc_semantics"]:
        loop = loops[item["lc"]]
        item["range"] = [loop["start"], loop["end"], loop["stride"]]
    streams = config["stream_engine"]
    for item in contract["stream_semantics"]:
        stream = streams[item["stream"]]
        item["byte_stride"] = stream["dim_stride"]
        if item["tail"] is not None:
            bounds = stream["idx_tailing_range"]
            axis = item["tail"]["axis"]
            item["tail"] = {
                "axis": axis,
                "inclusive_valid_range": [
                    next(value for value in bounds["low"] if value is not None),
                    next(value for value in bounds["up"] if value is not None),
                ],
            }
    contract["config"] = {
        "path": request.accumulate_config_relative,
        "sha256": _sha256(config_bytes),
        "generator": "tools/generate_conv_instance.py",
        "source": "conv_full.json",
    }
    if encoder_evidence is None:
        contract["official_encoder"] = {
            "repository_commit": "e299b2804448242d1589b3e58ed7c5a9a5eca09f",
            "status": "pending",
            "connection_count": 46,
        }
    else:
        contract["official_encoder"] = encoder_evidence
    contract["evidence_boundaries"]["not_proven"] = [
        "exact hardware execution and P/D dump for this candidate",
        "cycle-accurate LC/stream/buffer interpretation of the encoded bitstream",
        "execplan typed qparam transport",
    ]
    return contract


def build_instance_files(project_root: Path, node_id: str) -> dict[Path, bytes]:
    root = project_root.resolve()
    request = make_conv_target_request(root, node_id)
    if request.spec.node_id == "node-0004":
        raise ValueError("the frozen first instance must use its dedicated generators")
    source = _load(root / "conv_full.json")
    config = build_real_1x1(source, request.spec)
    config_bytes = _canonical(config)
    evidence_path = (
        root
        / Path(request.accumulate_config_relative).parent
        / "encoder_evidence.json"
    )
    encoder_evidence = _load(evidence_path) if evidence_path.is_file() else None
    semantics = _semantic_contract(
        _load(root / "contracts" / "conv_1x1_lc_pe_stream_semantics.json"),
        request=request,
        config=config,
        config_bytes=config_bytes,
        encoder_evidence=encoder_evidence,
    )
    _manifest, requant_files = build_bundle(
        request.spec,
        config_root_relative=request.requant_root_relative,
    )
    files = {
        root / request.accumulate_config_relative: config_bytes,
        root / request.semantic_contract_relative: _canonical(semantics),
    }
    files.update(
        {request.requant_root / name: payload for name, payload in requant_files.items()}
    )
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate one typed real 1x1 Conv instance")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    files = build_instance_files(ROOT, args.node_id)
    for path, payload in files.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != payload:
                raise SystemExit(f"generated Conv instance differs: {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
