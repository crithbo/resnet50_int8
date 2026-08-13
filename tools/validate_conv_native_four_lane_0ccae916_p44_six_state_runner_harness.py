#!/usr/bin/env python3
"""Run p44 through the inherited six-state runtime harness with an FSDB stub."""

import json
import sys
from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p42_six_state_runner_harness as p42


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "r5_n4_0cc_p44_fsdbvq"
p42.p41.prior.PACKAGE_ID = PACKAGE
p42.p41.prior.SOURCE_ID = "r5_n4_0cc_p43_portablevq"
p42.p41.prior.SOURCE_SHA256 = "657767774ef6762f4e93c3c0b23da71895c7ec699837ca443b0210457d55c11c"
p42.p41.prior.SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane"
    / "r5_n4_0cc_p43_portablevq/r5_n4_0cc_p43_portablevq.zip"
)

original_mapped_prepare = p42.p41.prior.base.mapped_prepare


def fsdb_mapped_prepare(original, package, scenario_root, mode):
    value = original_mapped_prepare(original, package, scenario_root, mode)
    fake_make = scenario_root / "bin/make"
    text = fake_make.read_text(encoding="utf-8")
    anchor = 'printf \'stub-vpd\\n\' > "$(dirname "$0")/wave.vpd"\n'
    profile = json.loads(
        (package / "contracts/native_fsdb_query_profile.json").read_text(encoding="utf-8")
    )
    instance = profile["exact_probe_instance"]
    rows = []
    for sequence, candidate in enumerate(profile["candidates"]):
        value_text = "x" if candidate["width"] == 1 and sequence == 0 else "z" if candidate["width"] == 1 and sequence == 1 else "b1x" if candidate["width"] == 2 and sequence == 6 else "b0z" if candidate["width"] == 2 and sequence == 7 else "0" if candidate["width"] == 1 else "b00"
        rows.append(
            f"CODEX_NATIVE_FSDB_EVENT_V1 instance={instance} sequence={sequence} time_tick={sequence} "
            f"candidate={candidate['candidate_id']} width={candidate['width']} value={value_text}"
        )
    rows.append(
        f"CODEX_NATIVE_FSDB_SUMMARY_V1 instance={instance} sequence_count={len(profile['candidates'])} "
        "time_tick=9 end_vector=b00000000000"
    )
    log = "\\n".join(rows) + "\\nSimulation completed successfully!\\n"
    escaped = log.replace("'", "'\\''")
    injection = anchor + (
        'wave_tcl=""\n'
        'sim_log=""\n'
        'previous=""\n'
        'for argument in "$@"; do\n'
        '  [ "$previous" != "-i" ] || wave_tcl="$argument"\n'
        '  [ "$previous" != "-l" ] || sim_log="$argument"\n'
        '  previous="$argument"\n'
        'done\n'
        '[ -n "$wave_tcl" ] || exit 91\n'
        'wave_path="$(sed -n \'s/^set CODEX_WAVE_PATH {\\(.*\\)}$/\\1/p\' "$wave_tcl" | head -n 1)"\n'
        '[ -n "$wave_path" ] || exit 92\n'
        'mkdir -p "$(dirname "$wave_path")"\n'
        'printf \'stub-fsdb\\n\' > "$wave_path"\n'
        '[ -z "$sim_log" ] || mkdir -p "$(dirname "$sim_log")"\n'
        f"[ -z \"$sim_log\" ] || printf '%s' '{escaped}' > \"$sim_log\"\n"
    )
    if text.count(anchor) != 1:
        raise p42.p41.prior.base.HarnessError("p44 FSDB waveform stub anchor differs")
    fake_make.write_text(text.replace(anchor, injection, 1), encoding="utf-8", newline="\n")
    return value


p42.p41.prior.base.mapped_prepare = fsdb_mapped_prepare
original_scenario = p42.p41.prior.base.unique_runner_scenario


def diagnostic_scenario(package, harness_root, mode):
    value = original_scenario(package, harness_root, mode)
    if "--harness-output" in sys.argv:
        destination = Path(sys.argv[sys.argv.index("--harness-output") + 1]).with_name(
            "six_state_scenario_diagnostics.json"
        )
        current = json.loads(destination.read_text(encoding="utf-8")) if destination.is_file() else {}
        current[mode] = value
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


p42.p41.prior.base.unique_runner_scenario = diagnostic_scenario


if __name__ == "__main__":
    raise SystemExit(p42.p41.prior.main())
