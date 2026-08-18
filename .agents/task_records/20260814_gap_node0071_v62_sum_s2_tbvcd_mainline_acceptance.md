# GAP node0071 v62 sum_s2 TB VCD causal-cone mainline acceptance

Date: 2026-08-14  
Role: `mainline.control`  
Family owner: `family.gap`  
Owner thread: `019ff02d-8225-7d21-9779-e46ce4130572`  
Owner epoch: `2`  
Shared epoch: `tb-vcd-bounded-causal-cone-optional-v1-0820e1733437`

## Previous progress

v56 dynamically proved the slice-local-base workaround through sum_s1. v61 preserved that workaround, entered native production simulation and narrowed the sustained sum_s2 loss of progress to the MSE0-to-Buffer0 ARM acceptance/availability boundary, but did not uniquely distinguish bank/clear, ping-pong readiness, barrier or downstream consumption.

## Current package and purpose

`r5_n71_gap_v62_sum_s2_tbvcd` preserves the frozen configuration, numeric surface, workload, golden, functional RTL, slice-local workaround and sum_s2 target. It selects `TB_VCD_BOUNDED_CAUSAL_CONE` and provides a package-local standard-TB VCD over 1,910 actual signals and 41 causal roles covering MSE0 supply/tag, Buffer0 ARM acceptance, bank/clear, ping-pong/bank readiness, normal-read barrier, GA acceptance/source, MSE4, stage finish and global progress.

The exact pending package is:

`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v62_sum_s2_tbvcd.zip`

The only future command, after separate user authorization, is:

`bash r5_n71_gap_v62_sum_s2_tbvcd/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

## Mainline disposition

Status is `PACKAGE_READY_NOT_RUN`. Family-reported exact-ZIP selector/VCD causal-cone, 41-role/four-layer source binding, candidate matrix, HDL, runner/compile-core, native-flow noninterference, post-sim, runtime/process-tree/six-exit, strict plateau, streaming/retention, first-fresh and storage gates passed. v61 was atomically preserved under superseded only after v62 passed. Mainline independently confirmed v62 as the sole GAP pending package and the global storage audit passed.

## Claim boundary

This is local package acceptance only. No upload, lease, connection or server execution occurred. It does not claim production compile/simulation, unique root cause, natural terminal, formal D, E3, E4 or E5, and it authorizes no RTL/config/numeric/workload/golden change.
