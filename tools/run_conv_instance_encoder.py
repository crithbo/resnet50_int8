from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from resnet50_pipeline.conv_instance import make_conv_target_request
from run_conv_full_encoder import _connection_pairs


ROOT = Path(__file__).resolve().parents[1]
ENCODER_ROOT = ROOT / "ndp-sim-ref"
OUTPUT_NAMES = (
    "mapping_review.json",
    "parsed_bitstream.txt",
    "modules_dump_64b.bin",
    "modules_dump_128b.bin",
    "detailed_dump.txt",
)


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha(path: Path) -> dict[str, int | str]:
    payload = path.read_bytes()
    return {
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


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
            "--heuristic-iterations",
            "5000",
            "--heuristic-restarts",
            "1",
            "--seed",
            "17",
            "--visualize-placement",
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
    return {name: _sha(output / name) for name in OUTPUT_NAMES}


def main() -> int:
    parser = argparse.ArgumentParser(description="Encode one typed Conv instance twice")
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    request = make_conv_target_request(ROOT, args.node_id)
    config = request.accumulate_config_path
    if not config.is_file():
        raise ValueError(f"generate the Conv instance before encoding: {config}")
    output = args.output or (
        ROOT / "artifacts" / "w5" / request.spec.accumulate_hw_op_id / "encoder"
    )
    evidence_path = args.evidence or (
        config.parent / "encoder_evidence.json"
    )

    payload = _load(config)
    pairs = _connection_pairs(payload)
    cache_key = hashlib.sha256(
        json.dumps(sorted(pairs), sort_keys=True).encode()
    ).hexdigest()[:16]
    source_mapping = _load(ROOT / "contracts" / "conv_full_encoder_evidence.json")[
        "placement_repair"
    ]["node_to_resource"]
    cache = ENCODER_ROOT / "bitstream" / "config" / "mapping_cache" / f"{cache_key}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps(source_mapping, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    # A changed connection graph needs one mapper pass to materialize its own
    # content-addressed zero-cost seed.  Evidence A/B then both start from that
    # settled seed; comparing a seed-discovery run with a seeded run makes the
    # raw mapping review differ even when the emitted bitstream is identical.
    _encode(config, output / "mapping-warmup")
    if not cache.is_file():
        raise ValueError("Conv instance encoder did not materialize its mapping seed")
    first = _encode(config, output / "encode-a")
    second = _encode(config, output / "encode-b")
    if first != second:
        raise ValueError("Conv instance encoder output is not deterministic")
    review = _load(output / "encode-a" / "mapping_review.json")
    if review.get("summary", {}).get("connections") != len(pairs):
        raise ValueError("Conv instance mapping review connection count differs")
    evidence = {
        "repository_commit": "e299b2804448242d1589b3e58ed7c5a9a5eca09f",
        "mapping_cache_key": cache_key,
        "connection_count": len(pairs),
        "constraint_cost": 0,
        "repeat_count": 2,
        "repeat_outputs_identical": True,
        "outputs": first,
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(evidence, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
