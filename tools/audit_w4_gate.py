from __future__ import annotations

import argparse
from pathlib import Path

from resnet50_pipeline.errors import ContractError
from resnet50_pipeline.w4_evidence import (
    canonical_json_bytes,
    current_evidence_path,
    resolve_current_output,
)
from resnet50_pipeline.w4_audit import audit_w4_gate


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the current RTL28 W4 evidence and decide the G4 gate"
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--write-current-evidence",
        action="store_true",
        help="Write to the content-addressed artifacts/w4/rtl28 evidence path",
    )
    parser.add_argument(
        "--hardware-approval",
        type=Path,
        help="Optional approved hardware contract; defaults to contracts/hardware_approval.json",
    )
    args = parser.parse_args()
    report = audit_w4_gate(args.project_root, args.hardware_approval)
    payload = canonical_json_bytes(report)
    encoded = payload.decode("utf-8")
    expected_output = current_evidence_path(
        args.project_root,
        report["architecture_sha256"],
        "g4-gate-audit",
        payload,
    )
    try:
        output = resolve_current_output(
            args.project_root,
            args.output,
            expected_output,
            args.write_current_evidence,
        )
    except ContractError as error:
        parser.error(str(error))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(payload)
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
