from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from resnet50_pipeline.hardware_simulation_frontend import (  # noqa: E402
    verify_server_preload_readback,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a server pre-Start_Comp Bank readback against the mandatory "
            "probes in one hardware execplan package."
        )
    )
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--readback-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = verify_server_preload_readback(
        args.package.resolve(), args.readback_root.resolve()
    )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "probe_count": report["probe_count"],
                "failed_probe_count": report["failed_probe_count"],
                "execution_authorized": report["execution_authorized"],
                "output": str(output),
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
