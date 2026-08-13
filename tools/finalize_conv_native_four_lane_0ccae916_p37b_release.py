#!/usr/bin/env python3
"""Finalize corrected p37b by reusing the same-epoch p37 gate structure."""

import json
from pathlib import Path

import finalize_conv_native_four_lane_0ccae916_p37_release as prior


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p37b_saepoch"
BASE = ROOT / "outputs/conv_native_four_lane_0ccae916_p37b_saepoch"
BUILD = BASE / "build"
prior.PACKAGE = PACKAGE
prior.BASE = BASE
prior.BUILD = BUILD
prior.ZIP = BUILD / f"{PACKAGE}.zip"
prior.OUTPUT = BASE / f"{PACKAGE}.final_zip_audit.json"
prior.FILES = {
    "build": BUILD / f"{PACKAGE}.build.json",
    "family": BASE / "p37b_family_audit.json",
    "runner": BUILD / f"{PACKAGE}.runner_harness_v2.json",
    "shared": BUILD / f"{PACKAGE}.shared_layout_v2.json",
    "post_sim": BUILD / f"{PACKAGE}.post_sim.json",
    "source_bound": BUILD / f"{PACKAGE}.source_bound_final_zip.json",
    "profile": BASE / "server_package_build_profile_v2.json",
    "build_spec": BASE / "server_package_build_spec_v2.json",
    "p36b_return_analysis": ROOT / "outputs/conv_native_four_lane_0ccae916_p36b_return_analysis/report.json",
    "prior_first_fresh": ROOT / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p36b_semfp/r5_n4_0cc_p36b_semfp.first_fresh_validation.json",
}


def main() -> int:
    status = prior.main()
    result = json.loads(prior.OUTPUT.read_text(encoding="utf-8"))
    result.update({
        "schema": "conv-native-four-lane-p37b-saepoch-final-zip-audit-v1",
        "p37_disposition": "PACKAGE_HELD_SEMANTIC_AUDIT_ESCAPE_SUPERSEDED",
        "p37_audit_escape": (
            "p37 required every lane to carry same=1 although the public group tag uses OR(lane_same); "
            "p37b accepts valid+ready per lane and reconstructs the exact group tag."
        ),
        "content_neutral_audit_receipt_recovery": {
            "zip_rebuilt": False,
            "final_zip_count": 1,
            "first_runner_receipt_path_reentry": "refused to overwrite and emitted a local harness error receipt",
            "authoritative_runner_receipt": "r5_n4_0cc_p37b_saepoch.runner_harness_v2.json",
            "authoritative_shared_receipt": "r5_n4_0cc_p37b_saepoch.shared_layout_v2.json",
        },
        "claim_boundary": (
            "One corrected c0 diagnostic distinguishing complete accepted SA data beats behind the p36b stable ARM tag. "
            "The public group-tag OR semantics are reconstructed exactly; no natural terminal, formal 320D, E3/E4/E5 or measured performance claim."
        ),
    })
    prior.OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
