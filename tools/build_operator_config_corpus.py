from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from resnet50_pipeline.operator_config_corpus import (
    build_hardware_evidence_audit,
    build_operator_config_authority,
    build_operator_config_corpus,
    write_json_contract,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build normalized ndp-sim JSON corpus and hardware-evidence audit."
    )
    parser.add_argument(
        "--authority-output",
        type=Path,
        default=ROOT
        / "contracts/operator_config/operator_config_authority_v1.json",
    )
    parser.add_argument(
        "--corpus-output",
        type=Path,
        default=ROOT / "contracts/operator_config/ndpsim_json_corpus_v1.json",
    )
    parser.add_argument(
        "--hardware-output",
        type=Path,
        default=ROOT
        / "contracts/operator_config/ndpsim_json_hardware_evidence_v1.json",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    authority = build_operator_config_authority(ROOT)
    corpus = build_operator_config_corpus(ROOT)
    hardware = build_hardware_evidence_audit(ROOT, corpus)
    write_json_contract(args.authority_output, authority)
    write_json_contract(args.corpus_output, corpus)
    write_json_contract(args.hardware_output, hardware)
    print(
        f"authorized_configs={authority['summary']['authorized_operator_config_count']} "
        f"ndpsim_upstream_authorized="
        f"{authority['summary']['source_root_authorized_counts']['ndp-sim/jsons']} "
        f"project_added_unapproved="
        f"{authority['summary']['not_authorized_as_tested_reference_count']} "
        f"templates={corpus['summary']['template_count']} "
        f"exact_hardware_positive="
        f"{hardware['summary']['exact_positive_hardware_test_count']} "
        f"hardware_negative={hardware['summary']['exact_hardware_negative_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
