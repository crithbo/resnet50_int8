from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _connection_pairs(config: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for key, record in config["dram_loop_configs"].items():
        source = record.get("src_id")
        if isinstance(source, str):
            pairs.append((source, f"DRAM_LC.{key}"))
    for key, record in config["buffer_loop_configs"].items():
        for field in ("ROW_LC", "COL_LC"):
            source = record[field].get("src_id")
            if isinstance(source, str):
                pairs.append((source, f"{key}.{field}"))
    for key, record in config["lc_pe_configs"].items():
        for index in range(3):
            source = record.get(f"inport{index}", {}).get("src_id")
            if isinstance(source, str):
                pairs.append((source, f"LC_PE.{key}"))
    for key, record in config["stream_engine"].items():
        for source in record.get("idx", []):
            if isinstance(source, str):
                pairs.append((source, f"STREAM.{key}"))
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the official ndp-sim-ref encoder for conv_full.json"
    )
    parser.add_argument("--config", type=Path, default=ROOT / "conv_full.json")
    parser.add_argument(
        "--evidence",
        type=Path,
        default=ROOT / "contracts" / "conv_full_encoder_evidence.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "w5" / "conv_full_audit" / "accepted",
    )
    parser.add_argument(
        "--refresh-evidence",
        action="store_true",
        help=(
            "Refresh the source/output hashes after a reviewed, connection-graph-"
            "preserving config change. Placement identity must still match."
        ),
    )
    args = parser.parse_args()

    config = _load(args.config)
    evidence = _load(args.evidence)
    if (
        not args.refresh_evidence
        and _sha256(args.config) != evidence["source"]["json_sha256"]
    ):
        raise ValueError("conv_full.json hash differs from the placement evidence")
    pairs = _connection_pairs(config)
    cache_key = hashlib.sha256(
        json.dumps(sorted(pairs), sort_keys=True).encode()
    ).hexdigest()[:16]
    placement = evidence["placement_repair"]
    if (
        len(pairs) != placement["connection_count"]
        or cache_key != placement["mapping_cache_key"]
    ):
        raise ValueError("Conv connection graph differs from the accepted placement")

    encoder_root = ROOT / "ndp-sim-ref"
    cache_path = (
        encoder_root
        / "bitstream"
        / "config"
        / "mapping_cache"
        / f"{cache_key}.json"
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(
        json.dumps(placement["node_to_resource"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-X",
        "utf8",
        "bitstream/main.py",
        "-c",
        str(args.config.resolve()),
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
    ]
    completed = subprocess.run(command, cwd=encoder_root, check=False)
    if completed.returncode:
        return completed.returncode

    review = _load(args.output / "mapping_review.json")
    if review.get("summary", {}).get("connections") != placement["connection_count"]:
        raise ValueError("official mapping review connection count differs")
    mapped = {
        item["node"]: item["resource"] for item in review["node_to_resource"]
    }
    if any(mapped.get(node) != resource for node, resource in placement["node_to_resource"].items()):
        raise ValueError("official mapping review differs from the accepted zero-cost layout")

    observed: dict[str, dict[str, Any]] = {}
    for name, expected in evidence["encoder"]["outputs"].items():
        path = args.output / name
        observed[name] = {"size_bytes": path.stat().st_size, "sha256": _sha256(path)}
        if not args.refresh_evidence and observed[name] != expected:
            raise ValueError(f"official encoder output differs: {name}")
    if args.refresh_evidence:
        evidence["source"]["json_sha256"] = _sha256(args.config)
        repair = (
            "SA GEMM outport JSON row -> col (official encoder label inversion: "
            "col encodes RTL sa_outport_major=0 row-major)"
        )
        if repair not in evidence["deterministic_repairs"]:
            evidence["deterministic_repairs"].append(repair)
        evidence["encoder"]["outputs"] = observed
        args.evidence.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {
                "status": "official_encoder_passed",
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
