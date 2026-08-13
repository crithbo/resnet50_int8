# Serialized Conv node0004 v81 return → v82b phase-collector successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Status: `PACKAGE_READY_NOT_RUN`
- Package class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`, `candidate_release=false`

## Formal v81 return result

The v81 return ZIP passed internal integrity, exact-set, source/execution, install and publication binding. Production compile/run exited `0/0` with `signal=NONE`, but the joint result gate failed: no natural terminal was proven and all 320 formal-D entries were missing. Therefore E3/E4/E5 remain false.

The exact slice13/group1/MSE4 trigger occurred 13 times. The returned bounded log contained zero exact phase EVENT records because the package-local post-sim plugin ran the frozen bounded collector before the phase parser. That collector overwrote `c0/sim.log` after filtering out phase EVENT records. This is a package-local evidence-loss defect, not evidence of a DUT/config/numeric defect.

- LPG: `EXACT_SLICE13_GROUP1_MSE4_PHASE_TRIGGER_CONDITION_OCCURRED_13_TIMES`
- FD: `EXACT_TARGET_PHASE_EVENT_TO_POST_SIM_PHASE_PARSER_INPUT_PRESERVATION`
- Root: `PACKAGE_LOCAL_POST_SIM_COLLECTOR_ORDER_AND_LOG_MUTATION_DEFECT`
- Analysis: `outputs/conv_node0004_v81_return_v82_successor/return_analysis.json`, SHA256 `b29115c8904a6ec334ab499212f0a249a7b6f368582a8b90a94a4d29a127b525`

The historical SA outbuffer occupancy claim remains `INVALIDATED_NOT_RTL_BUG` and was not revived.

## Fresh v82b successor

The successor parses and persists exact phase EVENT records before bounded source-bound projection mutates the simulation log. It additionally binds exact canonical instance/group, a binary-known 38-bit payload, and a first-use semantic fingerprint. Numeric, W3, workload, config, golden, timeout, backpressure, functional RTL, ISA, hardware and active ndp-sim are frozen.

Intermediate v82 products were never published after the shared source-bound topology correction. The only release identity is:

- Package: `r5_n4_hw_v82b_phase_collectfix`
- Pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v82b_phase_collectfix.zip`
- Bytes: `5256542`
- SHA256: `cdd4dc08b616d29e891973267fff0dd00c380bada05c12e50e2a6d119bd7ee07`
- Command: `bash r5_n4_hw_v82b_phase_collectfix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`
- Expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v82b_phase_collectfix_<execution>_return.zip`

## Local release gates

- Phase/order focused controls: `8/8 PASS`.
- Current source-bound generator: SHA256 `c50c2f8117ee6e73da76cae4c5a0fc46a3774b7c775d9bb62942ff8bcd4b837f`; focused regression `21/21 PASS`.
- First-fresh epoch: `20260811-exact-instance-payload-semantic-fingerprint-v2`, `first_fresh_after_change=true`.
- Independent clean-extract first-fresh audit: PASS, errors `0`, SHA256 `0c71f0972193e7a2e6a1b9f0609d45198129c5c1da629cf9ba977445d310f71a`.
- Final-ZIP self-audit: PASS, errors `0`, SHA256 `edb5d77ae5db79433656377778dcf9193ffce5089faf0013a5d82ef52f079361`.
- Exact runner, 86-input open, post-sim core scenarios, source-bound logger→collector→parser, runtime layout, return contract and candidate discrimination all pass.

## Storage rotation

The storage operation bound current preimage SHA256 `b4b6d0aae7004bf041827921747d7fe59f9bfc49914cafaeec09e87a41374fb3`. v81 moved to `tested`; v82b is the sole pending serialized package. Native p36b and QAdd v54 were preserved byte-for-byte and their disposition did not change.

- Current storage index SHA256: `22313312e5fcfc5d73b60890ef237b6f5c99d12f26aafd36870b9d33909c238e`
- Rotation report SHA256: `eddc16b24f3c1f5573efe414c4fb2cb4fd3c43dffc0a01e81a44c683d0d3473a`
- Corrected evidence-metadata refresh SHA256: `d1512095e64e80062a12068001ea98dbbda0aa7f4191964bf9bfc0516c8fccf5`; ZIP bytes and dispositions unchanged.

## Blocker and rule feedback

Closed package-side blockers: wrong-instance phase binding and phase EVENT erasure before parsing. Remaining dynamic blockers are exact target phase classification, DUT natural terminal and formal-D 320 readback.

`RULE_CONFIRMATION=CONFIRMED_NO_DELTA`: the current exact-instance, binary-known/width, semantic-fingerprint and independent first-fresh audit rules directly cover the escapes exercised here. No non-synonymous rule delta is proposed.

No server upload/run/lease occurred. No plan, public rule, functional RTL, ISA, hardware or other-family asset was modified.
