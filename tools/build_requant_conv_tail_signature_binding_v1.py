from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.requant_conv_tail_signature_binding_v1 import (  # noqa: E402
    ARTIFACT_REL,
    CONTRACT_REL,
    build_and_write,
    file_sha256,
)


def main() -> None:
    value, validation = build_and_write()
    print(
        json.dumps(
            {
                "status": value["status"],
                "manifest_sha256": value["manifest_sha256"],
                "contract_file_sha256": file_sha256(CONTRACT_REL),
                "validation_file_sha256": file_sha256(
                    ARTIFACT_REL / "validation_report.json"
                ),
                "generation_receipt_file_sha256": file_sha256(
                    ARTIFACT_REL / "generation_receipt.json"
                ),
                "valid": validation["valid"],
                "summary": validation["summary"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

