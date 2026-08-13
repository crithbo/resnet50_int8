#!/usr/bin/env python3
"""Fresh p37b identity after the p37 group-tag expansion audit escape."""

import json
from pathlib import Path

import build_conv_native_four_lane_0ccae916_p37_saepoch_package as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p37b_saepoch"
prior.SOURCE_ID = "r5_n4_0cc_p37_saepoch"
prior.SOURCE_ZIP = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p37_saepoch.zip"
prior.SOURCE_BYTES = 5_956_689
prior.SOURCE_SHA256 = "441da07145ee883585ff57dd8bc3320c1486dc2ea47f852759e2ff3443995e9a"
prior.SOURCE_BOUND = ROOT / "outputs/conv_native_four_lane_0ccae916_p37b_saepoch_source_bound"
prior.GENERATED = prior.SOURCE_BOUND / "generated"
prior.DEFAULT_OUTPUT = ROOT / "outputs/conv_native_four_lane_0ccae916_p37b_saepoch/build"
prior.PRIOR_FIRST_FRESH = ROOT / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p36b_semfp/r5_n4_0cc_p36b_semfp.first_fresh_validation.json"
_old_patch_manifest = prior.patch_manifest


def patch_manifest(package, changed, generated, target, runner, post_sim):
    _old_patch_manifest(package, changed, generated, target, runner, post_sim)
    path = package / "package_manifest.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["schema"] = "conv-native-four-lane-0ccae916-p37b-saepoch-package-v1"
    value["delivery_successor"].update({
        "source_package_identity": prior.SOURCE_ID,
        "source_zip_sha256": prior.SOURCE_SHA256,
        "source_disposition_after_consumption": "superseded",
        "reason": "p37 local audit overconstrained the public group-tag OR semantics at each lane; p37b observes valid+ready per lane and reconstructs the exact group tag",
    })
    prior.base.refresh_manifest_files(package, value)
    prior.write_json(path, value)


prior.patch_manifest = patch_manifest


if __name__ == "__main__":
    raise SystemExit(prior.main())
