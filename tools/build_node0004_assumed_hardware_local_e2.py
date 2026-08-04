from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.node0004_assumed_hardware import (  # noqa: E402
    CONFIG_REL,
    ROOT_REL,
    materialize_local_inputs,
    materialize_mappings_and_execplans,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fresh-build node0004 under the user-authorized assumed-hardware profile."
    )
    parser.add_argument("--output", type=Path, default=ROOT / ROOT_REL)
    parser.add_argument("--config-output", type=Path, default=ROOT / CONFIG_REL)
    parser.add_argument(
        "--python",
        type=Path,
        default=Path(
            r"C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime"
            r"\dependencies\python\python.exe"
        ),
    )
    parser.add_argument(
        "--local-only",
        action="store_true",
        help="stop after fresh configs, W3 replay and graph materialization",
    )
    parser.add_argument(
        "--resume-mapping",
        action="store_true",
        help="consume an existing fresh local-only build and add mappings/execplans",
    )
    args = parser.parse_args()
    try:
        if args.resume_mapping:
            first = {
                "numeric": json.loads(
                    (args.output / "local_numeric_report.json").read_text(
                        encoding="utf-8"
                    )
                )
            }
        else:
            first = materialize_local_inputs(
                ROOT, args.output, args.config_output
            )
        second = (
            None
            if args.local_only
            else materialize_mappings_and_execplans(
                ROOT,
                args.output,
                args.config_output,
                python_executable=args.python,
            )
        )
    except Exception as error:
        print(f"node0004 assumed-hardware build failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output": str(args.output),
                "config_output": str(args.config_output),
                "numeric": first["numeric"],
                "execplans": (
                    {
                        "conv": str(second["conv_execplan"]),
                        "tail": str(second["tail_execplan"]),
                        "mapping_count": second["mapping_count"],
                    }
                    if second is not None
                    else None
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
