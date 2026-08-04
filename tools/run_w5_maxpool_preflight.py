from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from resnet50_pipeline.w5_maxpool_preflight import run_maxpool_preflight


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the real ResNet-50 MaxPool local preflight")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/w5/hwop-0002-00/maxpool_v1/preflight.json"),
    )
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    output = args.output if args.output.is_absolute() else project_root / args.output
    if output.exists():
        raise RuntimeError(f"refusing to overwrite MaxPool preflight report: {output}")
    report = run_maxpool_preflight(project_root)
    text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    payload = text.encode("utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(payload)
    print(
        json.dumps(
            {
                "status": report["status"],
                "output": str(output),
                "sha256": hashlib.sha256(payload).hexdigest(),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
