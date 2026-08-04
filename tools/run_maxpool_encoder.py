from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from resnet50_pipeline.maxpool_instance import load_maxpool_instance
from resnet50_pipeline.target_config_audit import _run_encoder


def main() -> None:
    parser = argparse.ArgumentParser(description="Encode all three frozen MaxPool waves twice")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/w5/hwop-0002-00/maxpool_v1/encoder_candidate_v2"),
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else project_root / args.output
    if output.exists() and any(output.iterdir()):
        raise RuntimeError(f"refusing to overwrite non-empty encoder output: {output}")
    output.mkdir(parents=True, exist_ok=True)
    source_root = project_root / "ndp-sim-ref"
    instance = load_maxpool_instance(
        project_root, project_root / "configs" / "maxpool" / "hwop-0002-00"
    )
    waves = []
    with tempfile.TemporaryDirectory(prefix="maxpool-encoder-repeat-") as temp_text:
        temp = Path(temp_text)
        for wave in instance.manifest["waves"]:
            wave_index = int(wave["wave_index"])
            config_path = instance.root / wave["path"]
            first = _run_encoder(source_root, config_path, output / f"wave-{wave_index}")
            second = _run_encoder(source_root, config_path, temp / f"wave-{wave_index}")
            if first["outputs"] != second["outputs"]:
                raise RuntimeError(f"official MaxPool encoder is non-deterministic for wave {wave_index}")
            waves.append(
                {
                    "wave_index": wave_index,
                    "config_path": str(config_path.relative_to(project_root)).replace("\\", "/"),
                    "config_sha256": wave["config_sha256"],
                    "active_slices": wave["active_slices"],
                    "input_offset": wave["input_offset"],
                    "output_offset": wave["output_offset"],
                    "deterministic_repeat_count": 2,
                    "outputs": first["outputs"],
                    "stdout_sha256": first["stdout_sha256"],
                }
            )
    report = {
        "schema_version": "0.1",
        "kind": "maxpool_official_encoder_evidence",
        "status": "official_encoder_passed_not_target_executed",
        "source_repository": "ndp-sim-ref",
        "source_commit": instance.manifest["source_template"]["commit"],
        "source_template_sha256": instance.manifest["source_template"]["sha256"],
        "wave_count": len(waves),
        "waves": waves,
        "environment": {"PYTHONHASHSEED": "0", "PYTHONUTF8": "1", "seed": 42},
        "target_execution": {
            "status": "not_executed",
            "g6_validated": False,
            "g8_validated": False,
        },
    }
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    payload = text.encode("utf-8")
    evidence_path = output / "evidence.json"
    evidence_path.write_bytes(payload)
    print(
        json.dumps(
            {
                "status": report["status"],
                "evidence": str(evidence_path),
                "evidence_sha256": hashlib.sha256(payload).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
