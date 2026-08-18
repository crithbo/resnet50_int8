from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.ndp_patch_toolchain import apply_patchset_in_place  # noqa: E402
from resnet50_pipeline.operator_config_execplan_evidence import (  # noqa: E402
    _copy_native_tool,
    _install_patchset_base_files,
    _install_validated_configs,
    _merge_mapping_caches,
)
from resnet50_pipeline.operator_config_execplan_validator import (  # noqa: E402
    OperatorConfigExecPlanValidator,
)
from resnet50_pipeline.operator_config_request_address_validator import (  # noqa: E402
    OperatorConfigRequestAddressValidator,
)


AB_ROOT = ROOT / (
    "artifacts/operator_config_validation/"
    "r5-node0004-lc-branch-duplication-ab-v2"
)
OUTPUT = AB_ROOT / "B/native_execplan_unadmitted"
GRAPH = AB_ROOT / "graph/wave-0.json"
MAPPING = AB_ROOT / "B/mapping"
PATCHSET = ROOT / "contracts/ndp_patch_toolchain_node0004_assumed_hw_v1.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def lines(path: Path) -> list[str]:
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit(f"fresh output required: {OUTPUT}")
    python = (ROOT / ".venv/Scripts/python.exe").resolve()
    ndp = (ROOT / "ndp-sim").resolve()
    patchset = load(PATCHSET)
    mapping_evidence = load(MAPPING / "mapping_evidence.json")
    cache_files = sorted((MAPPING / "mapping_cache").glob("*.json"))
    validated = {
        "op_w0": {
            "bundle": MAPPING,
            "config": MAPPING / "source_config.json",
            "evidence": mapping_evidence,
            "cache_files": cache_files,
        }
    }
    operators = [{"id": "op_w0", "type": "resnet50_conv_node0004_wave0"}]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="node0004-lcdup-capture-") as temp_text:
        temp = Path(temp_text)
        tool = temp / "tool"
        _copy_native_tool(ndp, tool)
        _install_patchset_base_files(source_root=ndp, tool_root=tool, patchset=patchset)
        applied = apply_patchset_in_place(tool, patchset_id=patchset["patchset_id"])
        if applied["patchset_sha256"] != patchset["patchset_sha256"]:
            raise SystemExit("applied patchset differs")
        _install_validated_configs(tool, operators, validated)
        cache = tool / "bitstream/config/mapping_cache"
        cache.mkdir(parents=True, exist_ok=True)
        _merge_mapping_caches(validated, cache)
        env = dict(os.environ)
        env.update(
            {
                "PYTHONIOENCODING": "utf-8",
                "PYTHONUTF8": "1",
                "PYTHONHASHSEED": "0",
                "MPLBACKEND": "Agg",
            }
        )
        completed = subprocess.run(
            [str(python), str(tool / "model_execplan/main.py"), str(GRAPH)],
            cwd=tool,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300,
            check=False,
        )
        if completed.returncode != 0:
            raise SystemExit(f"native planner failed: {completed.returncode}")
        graph_root = tool / "model_execplan/output/wave-0"
        staged = temp / "staged"
        shutil.copytree(graph_root, staged / "pipeline_output")
        (staged / "native_stdout.log").write_bytes(completed.stdout)
        (staged / "native_stderr.log").write_bytes(completed.stderr)
        shutil.copy2(GRAPH, staged / "graph_input.json")
        shutil.copy2(PATCHSET, staged / "patchset_manifest.json")
        shutil.copytree(MAPPING, staged / "mapping_evidence/op_w0")
        shutil.move(str(staged), str(OUTPUT))

    pipeline = OUTPUT / "pipeline_output"
    graph_withbase = pipeline / "wave-0_withbaseaddr.json"
    shared = OperatorConfigExecPlanValidator().validate(
        pipeline,
        graph_path=graph_withbase,
        source_configs={"op_w0": MAPPING / "source_config.json"},
        mapping_evidence={"op_w0": mapping_evidence},
        artifact_dirs={"op_w0": MAPPING},
    ).to_dict()
    write(OUTPUT / "shared_execplan_validation_expected_failure.json", shared)
    request = OperatorConfigRequestAddressValidator(include_request_rows=False).validate(
        pipeline,
        graph_path=graph_withbase,
        source_configs={"op_w0": MAPPING / "source_config.json"},
    ).to_dict()
    write(OUTPUT / "request_address_validation_report.json", request)

    config_dir = pipeline / "config/op_w0"
    words64 = lines(config_dir / "op_w0_resnet50_conv_node0004_wave0_bitstream_64b.bin")
    rows128 = lines(config_dir / "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin")
    exec_words: list[int] = []
    for row in lines(pipeline / "install/execplan.txt"):
        exec_words.extend((int(row[64:], 2), int(row[:64], 2)))
    if exec_words and exec_words[-1] == 0:
        exec_words.pop()
    load_word = next(word for word in exec_words if word & 0b111 == 0)
    programmed = (load_word >> 56) & 0xFF
    odd = len(words64) % 2 == 1
    padded_high = rows128[-1][:64]
    adjudication = {
        "schema": "node0004-lc-branch-odd-config-length-adjudication-v1",
        "status": "SHARED_VALIDATOR_FALSE_REJECTION_CONFIRMED"
        if (
            not shared["valid"]
            and request["valid"]
            and programmed == len(words64)
            and len(rows128) * 2 == len(words64) + 1
            and odd
            and set(padded_high) == {"0"}
        )
        else "UNEXPECTED",
        "meaningful_config_words_64bit": len(words64),
        "transport_rows_128bit": len(rows128),
        "transport_capacity_words_64bit": len(rows128) * 2,
        "programmed_Load_Config_length_64bit": programmed,
        "odd_final_word": odd,
        "padded_final_high_half_all_zero": set(padded_high) == {"0"},
        "request_address_validation": request["valid"],
        "shared_validator_valid": shared["valid"],
        "shared_validator_first_error": shared.get("first_error"),
        "bitstream_64_sha256": sha256(
            config_dir / "op_w0_resnet50_conv_node0004_wave0_bitstream_64b.bin"
        ),
        "bitstream_128_sha256": sha256(
            config_dir / "op_w0_resnet50_conv_node0004_wave0_bitstream_128b.bin"
        ),
        "claim_boundary": (
            "The native planner and exact 64-bit artifact agree on 71 meaningful words. "
            "The 36-row 128-bit transport contains one zero high-half pad. This does not "
            "authorize bypassing the active shared final gate."
        ),
        "server_action": False,
    }
    write(OUTPUT / "odd_config_length_adjudication.json", adjudication)
    print(json.dumps(adjudication, ensure_ascii=False, indent=2))
    return 0 if adjudication["status"] == "SHARED_VALIDATOR_FALSE_REJECTION_CONFIRMED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
