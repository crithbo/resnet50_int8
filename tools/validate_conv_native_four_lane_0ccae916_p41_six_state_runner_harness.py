#!/usr/bin/env python3
"""Run p41 through the inherited six-state install/runtime harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p30_runner_harness as prior


ROOT = Path(__file__).resolve().parents[1]
prior.PACKAGE_ID = "r5_n4_0cc_p41_vpdfull"
prior.SOURCE_ID = "r5_n4_0cc_p40_dhpubfix"
prior.SOURCE_SHA256 = "64c47086bcc1e9dade1b1c9e9fb912c186f49a0ab223c816996e08e9ad86b39f"
prior.SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/superseded"
    / "conv_native_four_lane/r5_n4_0cc_p40_dhpubfix/r5_n4_0cc_p40_dhpubfix.zip"
)

# The inherited runner harness predates the mandatory waveform epoch.  Extend
# only its isolated simulator stub so every simulation-started scenario emits
# a nonempty VPD beside simv, exactly where the p41 plan discovers it.
original_mapped_prepare = prior.base.mapped_prepare


def waveform_mapped_prepare(original, package, scenario_root, mode):
    value = original_mapped_prepare(original, package, scenario_root, mode)
    fake_make = scenario_root / "bin/make"
    text = fake_make.read_text(encoding="utf-8")
    anchor = ': > "${STUB_MARKER:?}"\n'
    injection = anchor + 'printf \'stub-vpd\\n\' > "$(dirname "$0")/wave.vpd"\n'
    if text.count(anchor) != 1:
        raise prior.base.HarnessError("mandatory-waveform stub anchor differs")
    fake_make.write_text(text.replace(anchor, injection, 1), encoding="utf-8", newline="\n")
    return value


prior.base.mapped_prepare = waveform_mapped_prepare


if __name__ == "__main__":
    raise SystemExit(prior.main())
