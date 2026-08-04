from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.qlinearadd_node0007_nested_lc_v4 import (
    CONTRACT_REL,
    ROOT_REL,
)
from resnet50_pipeline.qlinearadd_node0007_nested_lc_v4_closure import (
    TASK_RECORD_REL,
    validate_closure,
)
from tools import build_qlinearadd_node0007_server_package as implementation


INSTALL_NAME = "r5_qadd_n7_nested_lc_v4"


def configure() -> None:
    implementation.INSTALL_NAME = INSTALL_NAME
    implementation.MANIFEST_SCHEMA = (
        "qlinearadd-node0007-nested-lc-server-package-v4"
    )
    implementation.PACKAGE_DESCRIPTION = (
        "ResNet50 node0007 QLinearAdd signed-feedback-safe nested-LC test"
    )
    implementation.GENERATOR_REL = (
        "tools/build_qlinearadd_node0007_nested_lc_v4_server_package.py"
    )
    implementation.ROOT_REL = ROOT_REL
    implementation.CONTRACT_REL = CONTRACT_REL
    implementation.TASK_RECORD_REL = TASK_RECORD_REL
    implementation.SOURCE_PIPELINE = (
        implementation.ROOT / ROOT_REL / "execplan/pipeline_output"
    )
    implementation.validate_closure = validate_closure
    implementation.SUPERSEDED_IDENTITY = {
        "zip": (
            "artifacts/operator_config_validation/r5-server-test-packages/"
            "r5_qadd_n7_relocated_v3.zip"
        ),
        "sha256": (
            "265188700bca6c45d6d0894326f71b4e9c991cbaf3847f384785504ed7b2fc5c"
        ),
        "reason": (
            "v3 is QUARANTINED_NOT_RUN_NO_FUNCTIONAL_FIX because it retained "
            "the signed-feedback-wrapping flat LC domains"
        ),
        "v3_release_allowed": False,
    }


def main() -> int:
    configure()
    return implementation.main()


if __name__ == "__main__":
    raise SystemExit(main())
