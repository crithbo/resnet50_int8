from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from resnet50_pipeline.bitstream_binding import bitstream_text_identity
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


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError as error:
        raise ValueError(f"encoder evidence must stay inside the project: {path}") from error


def _locked_encoder_commit() -> str:
    locks = json.loads((ROOT / "repos.lock.json").read_text(encoding="utf-8"))
    for repository in locks.get("repositories", []):
        if repository.get("name") == "ndp-sim-ref":
            commit = repository.get("commit")
            if isinstance(commit, str) and len(commit) == 40:
                return commit
    raise ValueError("repos.lock.json lacks the official ndp-sim-ref encoder commit")


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
    parser.add_argument(
        "--contract-output",
        type=Path,
        help="Write the JSON/config/official-output binding contract here.",
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
    contract_output = (args.contract_output or (config_root / "encoder_contract.json")).resolve()
    try:
        config_root_relative = config_root.resolve().relative_to(ROOT).as_posix()
    except ValueError as error:
        raise ValueError("requant config root must stay inside the project root") from error
    _, generated = build_bundle(spec, config_root_relative=config_root_relative)
    for name, expected in generated.items():
        if (config_root / name).read_bytes() != expected:
            raise ValueError(f"checked-in requant output differs: {name}")
    observed = {}
    contract_records = []
    for shard_index in range(spec.requant_shard_count):
        shard_name = f"shard-{shard_index:02d}"
        config = config_root / f"{shard_name}.json"
        encode_a = output / "encode-a" / shard_name
        encode_b = output / "encode-b" / shard_name
        first = _encode(config, encode_a)
        second = _encode(config, encode_b)
        if first != second:
            raise ValueError(f"requant encoder output is not deterministic: {shard_name}")
        observed[shard_name] = first
        modules_a = bitstream_text_identity(
            encode_a / "modules_dump_128b.bin", line_width_bits=128
        )
        modules_b = bitstream_text_identity(
            encode_b / "modules_dump_128b.bin", line_width_bits=128
        )
        if modules_a != modules_b:
            raise ValueError(f"requant logical bitstream differs between runs: {shard_name}")
        contract_records.append(
            {
                "binding_id": f"{spec.requant_hw_op_id}.{shard_name}",
                "shard_index": shard_index,
                "config": {"path": _relative(config), **_sha(config)},
                "encode_a_root": _relative(encode_a),
                "encode_b_root": _relative(encode_b),
                "repeat_outputs_identical": True,
                "official_encoder": {
                    "modules_dump_128b.bin": modules_a,
                    "modules_dump_64b.bin": _sha(encode_a / "modules_dump_64b.bin"),
                    "parsed_bitstream.txt": _sha(encode_a / "parsed_bitstream.txt"),
                    "mapping_review.semantic.json": first[
                        "mapping_review.semantic.json"
                    ],
                },
            }
        )
    contract = {
        "schema_version": "resnet50-conv-requant-encoder-contract-0.1",
        "status": "official_encoder_double_run_bound",
        "node_id": spec.node_id,
        "hw_op_id": spec.requant_hw_op_id,
        "encoder_repository": {
            "name": "ndp-sim-ref",
            "commit": _locked_encoder_commit(),
        },
        "encoder_command": {
            "entrypoint": "bitstream/main.py",
            "heuristic_search": True,
            "heuristic_iterations": 10000,
            "heuristic_restarts": 10,
            "seed": 42,
        },
        "record_count": len(contract_records),
        "records": contract_records,
    }
    contract_output.parent.mkdir(parents=True, exist_ok=True)
    contract_output.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": "official_real_conv_requant_encoder_passed",
                "shard_count": spec.requant_shard_count,
                "connections_per_shard": 21,
                "mapping_cost": 0,
                "repeat_outputs_identical": True,
                "encoder_contract": _relative(contract_output),
                "encoder_contract_sha256": _sha(contract_output)["sha256"],
                "outputs": observed,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
