# Serialized Conv v92b TB VCD causal-cone mainline acceptance

Date: 2026-08-14  
Role: `mainline.control`  
Family owner: `family.conv.serialized`  
Owner thread: `019ff02d-901b-7f70-a9da-f54e268b5bbe`  
Owner epoch: `2`  
Shared epoch: `tb-vcd-bounded-causal-cone-optional-v1-0820e1733437`

## Previous progress

v88 proved the retired derived ACK comparator was an observer/source-identity semantic false positive. v90 completed native production compile/elaboration/link but a package-local compile-log normalizer arity defect prevented simulation; v91 repaired only that defect.

## Current package and purpose

`r5_n4_hw_v92b_tbvcdcone` preserves the v91 normalizer repair, v88 actual-source baseline and real ACK/FIFO/aggregate/MSE4/terminal target. It selects `TB_VCD_BOUNDED_CAUSAL_CONE` and uses a source-bound 42-actual-signal/41-role standard-TB VCD causal cone. `OBSERVER_ONLY_WIDE_CAUSAL` remains unchanged as the default option, and the retired derived ACK comparator remains absent.

The exact pending package is:

`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v92b_tbvcdcone.zip`

The only future command, after separate user authorization, is:

`bash r5_n4_hw_v92b_tbvcdcone/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

## Mainline disposition

Status is `PACKAGE_READY_NOT_RUN`. Family-reported exact-ZIP, mode-selector, bounded causal-cone, source-bound, HDL, runner/compile-core, post-sim, runtime/process-tree/six-exit, strict plateau, streaming/retention, first-fresh and storage gates passed. v91 was atomically preserved under superseded only after the fresh package gates passed. Mainline independently confirmed v92b as the sole serialized pending package and the global storage audit passed.

## Claim boundary

This is local package acceptance only. No upload, lease, connection or server execution occurred. It does not claim production compile/simulation, DUT root cause, natural terminal, formal D, E3, E4 or E5, and it authorizes no RTL/config/numeric/workload/golden change.
