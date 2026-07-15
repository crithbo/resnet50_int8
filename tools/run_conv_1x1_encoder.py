from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from resnet50_pipeline.conv_instance import (
    FIRST_REAL_CONV_NODE_ID,
    build_conv_target_request,
)
from run_conv_full_encoder import _connection_pairs


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild the real 1x1 Conv bitstream")
    parser.add_argument("--node-id", default=FIRST_REAL_CONV_NODE_ID)
    parser.add_argument("--config", type=Path)
    parser.add_argument(
        "--contract",
        type=Path,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "w5" / "conv_1x1_real" / "rebuild",
    )
    args = parser.parse_args()
    request = build_conv_target_request(ROOT, args.node_id)
    config_path = args.config or request.accumulate_config_path
    contract_path = args.contract or request.semantic_contract_path

    config = _load(config_path)
    contract = _load(contract_path)
    if _sha256(config_path) != contract["config"]["sha256"]:
        raise ValueError("real 1x1 Conv config hash differs")
    pairs = _connection_pairs(config)
    cache_key = hashlib.sha256(
        json.dumps(sorted(pairs), sort_keys=True).encode()
    ).hexdigest()[:16]
    encoder_evidence = contract["official_encoder"]
    if (
        cache_key != encoder_evidence["mapping_cache_key"]
        or len(pairs) != encoder_evidence["connection_count"]
    ):
        raise ValueError("real 1x1 Conv connection graph differs")

    source_mapping = _load(ROOT / "contracts" / "conv_full_encoder_evidence.json")[
        "placement_repair"
    ]["node_to_resource"]
    encoder_root = ROOT / "ndp-sim-ref"
    cache = encoder_root / "bitstream" / "config" / "mapping_cache" / f"{cache_key}.json"
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps(source_mapping, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    args.output.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "bitstream/main.py",
            "-c",
            str(config_path.resolve()),
            "-o",
            str(args.output.resolve()),
            "--heuristic-iterations",
            "5000",
            "--heuristic-restarts",
            "1",
            "--seed",
            "17",
            "--visualize-placement",
            "-q",
        ],
        cwd=encoder_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        if completed.stdout:
            print(completed.stdout, file=sys.stderr)
        if completed.stderr:
            print(completed.stderr, file=sys.stderr)
        return completed.returncode

    review = _load(args.output / "mapping_review.json")
    if review.get("summary", {}).get("connections") != len(pairs):
        raise ValueError("official mapping review connection count differs")
    observed: dict[str, dict[str, Any]] = {}
    for name, expected in encoder_evidence["outputs"].items():
        path = args.output / name
        observed[name] = {"size_bytes": path.stat().st_size, "sha256": _sha256(path)}
        if observed[name] != expected:
            raise ValueError(f"official real 1x1 encoder output differs: {name}")
    print(
        json.dumps(
            {
                "status": "official_real_1x1_encoder_passed",
                "mapping_cost": 0,
                "connections": len(pairs),
                "cache_key": cache_key,
                "outputs": observed,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
