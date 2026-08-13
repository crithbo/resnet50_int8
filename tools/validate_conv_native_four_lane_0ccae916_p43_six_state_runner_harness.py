#!/usr/bin/env python3
"""Run p43 through the inherited six-state install/runtime harness."""

from pathlib import Path

import validate_conv_native_four_lane_0ccae916_p42_six_state_runner_harness as p42


ROOT = Path(__file__).resolve().parents[1]
p42.p41.prior.PACKAGE_ID = "r5_n4_0cc_p43_portablevq"
p42.p41.prior.SOURCE_ID = "r5_n4_0cc_p42_vecjoinfix"
p42.p41.prior.SOURCE_SHA256 = "e742737932de3158a2bb2905a2e56f7c260e170289d4e9484cde545108c23e55"
p42.p41.prior.SOURCE_ZIP = (
    ROOT
    / "artifacts/operator_config_validation/r5-server-test-packages/pending"
    / "r5_n4_0cc_p42_vecjoinfix.zip"
)

# The inherited p41 harness emits only a legacy VPD beside simv.  The p43
# first-fresh normal scenario must instead exercise the exact same-attempt
# run/sim_results VPD+VCD/query path.  Extend only the isolated simulator stub;
# package bytes and production behavior remain untouched.
original_mapped_prepare = p42.p41.prior.base.mapped_prepare


def portable_mapped_prepare(original, package, scenario_root, mode):
    value = original_mapped_prepare(original, package, scenario_root, mode)
    fake_make = scenario_root / "bin/make"
    text = fake_make.read_text(encoding="utf-8")
    anchor = 'printf \'stub-vpd\\n\' > "$(dirname "$0")/wave.vpd"\n'
    vcd = """$date p43-six-state $end
$version native-p43-portable-stub $end
$timescale 1 ns $end
$scope module tb_NDP_Top_new_phy.u_NDP_Top_new.slice_with_datahub_mc_group_gen[0].u_slice_with_datahub_mc_group.slice_group_gen[0].u_slice_wrapper.u_Slice.u_LSU.u_Stream_Engine.MSE_INST[4].WR_MSE.u_Memory_WR_Stream_Engine $end
$var wire 1 ! mse_mem_ag_tag_valid $end
$var wire 1 \" mse_mem_ag_bp_pre $end
$var wire 1 # wr_data_chl_req_valid $end
$var wire 1 $ wr_data_chl_req_ready $end
$var wire 1 % buf2mse_rvalid $end
$var wire 1 & wr_data_chl_ready $end
$var wire 2 ' mse2mem_wdata_valid [1:0] $end
$var wire 2 ( mem2mse_wdata_ready [1:0] $end
$var wire 1 ) slice_cmpt_finish $end
$upscope $end
$enddefinitions $end
#0
0!
0\"
0#
0$
0%
0&
b00 '
b00 (
0)
#5
x!
z\"
1#
1$
1%
1&
b1x '
b0z (
0)
#10
1!
0\"
0#
1$
0%
1&
b11 '
b11 (
1)
"""
    escaped = vcd.replace("'", "'\\''")
    injection = anchor + (
        'wave_tcl=""\n'
        'previous=""\n'
        'for argument in "$@"; do [ "$previous" != "-i" ] || wave_tcl="$argument"; previous="$argument"; done\n'
        '[ -n "$wave_tcl" ] || exit 91\n'
        'vpd_path="$(awk \'/-type VPD/ {print $3; exit}\' "$wave_tcl")"\n'
        'vcd_path="$(awk \'/-type VCD/ {print $3; exit}\' "$wave_tcl")"\n'
        'mkdir -p "$(dirname "$vpd_path")"\n'
        'printf \'stub-vpd-portable\\n\' > "$vpd_path"\n'
        f"printf '%s' '{escaped}' > \"$vcd_path\"\n"
    )
    if text.count(anchor) != 1:
        raise p42.p41.prior.base.HarnessError("p43 portable waveform stub anchor differs")
    fake_make.write_text(text.replace(anchor, injection, 1), encoding="utf-8", newline="\n")
    return value


p42.p41.prior.base.mapped_prepare = portable_mapped_prepare


if __name__ == "__main__":
    raise SystemExit(p42.p41.prior.main())
