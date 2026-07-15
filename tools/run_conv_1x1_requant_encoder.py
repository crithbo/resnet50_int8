from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from resnet50_pipeline.conv_instance import (
    FIRST_REAL_CONV_NODE_ID,
    make_conv_target_request,
)
from generate_conv_1x1_requant_real import build_bundle


ROOT = Path(__file__).resolve().parents[1]
ENCODER_ROOT = ROOT / "ndp-sim-ref"
OUTPUT_NAMES = (
    "parsed_bitstream.txt",
    "modules_dump_64b.bin",
    "modules_dump_128b.bin",
    "detailed_dump.txt",
)


def _sha(path: Path) -> dict[str, int | str]:
    raw = path.read_bytes()
    return {"size_bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _encode(config: Path, output: Path) -> dict[str, dict[str, int | str]]:
    output.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "bitstream/main.py",
            "-c",
            str(config.resolve()),
            "-o",
            str(output.resolve()),
            "--heuristic-search",
            "--heuristic-iterations",
            "10000",
            "--heuristic-restarts",
            "10",
            "--seed",
            "42",
            "-q",
        ],
        cwd=ENCODER_ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        raise RuntimeError(completed.stdout + completed.stderr)
    review = json.loads((output / "mapping_review.json").read_text(encoding="utf-8"))
    if review.get("summary", {}).get("connections") != 21:
        raise ValueError("requant shard mapping connection count differs")
    normalized_review = {
        "summary": review["summary"],
        "node_to_resource": sorted(
            review["node_to_resource"], key=lambda item: (item["node"], item["resource"])
        ),
        "connection_mapping": sorted(
            review["connection_mapping"],
            key=lambda item: (
                item["src_node"],
                item["src_resource"],
                item["dst_node"],
                item["dst_resource"],
            ),
        ),
    }
    review_bytes = json.dumps(normalized_review, sort_keys=True, separators=(",", ":")).encode()
    outputs = {name: _sha(output / name) for name in OUTPUT_NAMES}
    outputs["mapping_review.semantic.json"] = {
        "size_bytes": len(review_bytes),
        "sha256": hashlib.sha256(review_bytes).hexdigest(),
    }
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild all real Conv requant shards twice")
    parser.add_argument("--node-id", default=FIRST_REAL_CONV_NODE_ID)
    parser.add_argument("--config-root", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
    )
    args = parser.parse_args()
    request = make_conv_target_request(ROOT, args.node_id)
    spec = request.spec
    config_root = args.config_root or request.requant_root
    output = args.output or (
        ROOT / "artifacts" / "w5" / "conv_1x1_requant_real"
        if args.node_id == FIRST_REAL_CONV_NODE_ID
        else ROOT / "artifacts" / "w5" / spec.accumulate_hw_op_id / "requant-encoder"
    )
    try:
        config_root_relative = config_root.resolve().relative_to(ROOT).as_posix()
    except ValueError as error:
        raise ValueError("requant config root must stay inside the project root") from error
    _, generated = build_bundle(spec, config_root_relative=config_root_relative)
    for name, expected in generated.items():
        if (config_root / name).read_bytes() != expected:
            raise ValueError(f"checked-in requant output differs: {name}")
    observed = {}
    for shard_index in range(spec.requant_shard_count):
        shard_name = f"shard-{shard_index:02d}"
        config = config_root / f"{shard_name}.json"
        first = _encode(config, output / "encode-a" / shard_name)
        second = _encode(config, output / "encode-b" / shard_name)
        if first != second:
            raise ValueError(f"requant encoder output is not deterministic: {shard_name}")
        observed[shard_name] = first
    print(
        json.dumps(
            {
                "status": "official_real_conv_requant_encoder_passed",
                "shard_count": spec.requant_shard_count,
                "connections_per_shard": 21,
                "mapping_cost": 0,
                "repeat_outputs_identical": True,
                "outputs": observed,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
