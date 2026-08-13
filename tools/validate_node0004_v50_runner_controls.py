from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tools.validate_node0004_v48_runner_controls as prior


base = prior.base
ORIGINAL_WRITE_STUBS = prior.write_stubs
base.FEATURES = {
    **base.FEATURES,
    "RETURN_OBS_DTERM_OWNER": (
        "+RETURN_OBS_DTERM_OWNER",
        "+RETURN_OBS_DTERM_OWNER_LIMIT=96",
    ),
}


def write_stubs(stub_root: Path, python: Path) -> None:
    ORIGINAL_WRITE_STUBS(stub_root, python)
    make = stub_root / "make"
    text = make.read_text(encoding="utf-8")
    anchor = (
        "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | "
        "feature=RETURN_OBS_LC9_ACTUAL enabled=1 "
        "limit_name=RETURN_OBS_LC9_ACTUAL_LIMIT limit=192 "
        "schema=LC9_ACTUAL\n"
    )
    addition = anchor + (
        "0 | DIAGNOSTIC_FEATURE_ENABLE_V1 | "
        "feature=RETURN_OBS_DTERM_OWNER enabled=1 "
        "limit_name=RETURN_OBS_DTERM_OWNER_LIMIT limit=96 "
        "schema=DTERM_OWNER\n"
    )
    if text.count(anchor) != 1:
        raise ValueError("safe-stub LC9 actual marker anchor differs")
    make.write_text(
        text.replace(anchor, addition, 1), encoding="utf-8", newline="\n"
    )


base.write_stubs = write_stubs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--sidecar", required=True, type=Path)
    parser.add_argument("--bash", required=True, type=Path)
    parser.add_argument("--python", required=True, type=Path)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = base.validate(
        args.zip.resolve(),
        args.sidecar.resolve(),
        args.bash.resolve(),
        args.python.resolve(),
        expected_zip_sha256=args.expected_zip_sha256,
        report_schema="node0004-v50-runner-controls-v1",
        require_return_manifest=True,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(report, indent=2))
    return 0 if report.get("valid") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
