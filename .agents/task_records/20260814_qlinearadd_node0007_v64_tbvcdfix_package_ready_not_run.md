# QLinearAdd node0007 v64 TB-VCD failure-fix package ready, not run

- role: `family.qlinearadd`, owner epoch 2, registry epoch 6
- package: `r5_qadd_n7_tailround_lanephase_v64_tbvcdfix`
- mode: `TB_VCD_BOUNDED_CAUSAL_CONE`
- status: `PACKAGE_READY_NOT_RUN`
- server actions: none

## Previous-version progress and formal return

v57h localized the historical DUT boundary after Buffer5 request decode and before the selected ping-pong port's required-lane read accept. v59 exposed and v60 repaired the manifest/install/SCA namespace mismatch. v63 compiled successfully and started production simulation, but it did not reach the tail-round target: execplan, bitstream, and slice00 through slice15 input transfers completed, slice16 write completed, and the package-local runtime supervisor then falsely asserted `SIM_TIME_FREEZE` during preload.

The exact v63 return was consumed with bounded streaming/resume. The VCD reached EOF locally, all 64 catalog signals mapped, and the legal multiline VCD header decodes as 1ps. Only clock/reset initialization activity occurred on the target cone; Buffer5 request decode, both ping-pong branches, bank/lane readiness, read accept, output, terminal, natural completion, formal D, E3, E4 and E5 were not reached. LAST_PROVEN_GOOD is the completed slice15 transfer/readback plus the slice16 write phase. FIRST_DIVERGENCE is `PACKAGE_RUNTIME_SUPERVISOR_FALSE_SIM_TIME_FREEZE_DURING_SLICE16_PRELOAD`, not an RTL/DUT divergence.

## Mandatory failure-rule audit

v59 and v63 are two server attempts that did not execute the same diagnostic target because of package-local defects. `PACKAGE_BUILD_FAILURE_RULE_AUDIT` was therefore submitted before building v64. Its non-synonymous family hard-gate delta is implemented and negatively tested:

- freeze supervision follows newly appended raw VCD `#timestamp` records;
- heartbeat uses non-overflowing `$time` with a 16,384-owner-cycle cadence;
- exactly the 64 source-bound catalog signals are dumped; whole-module dumping fails closed;
- multiline `$timescale` is decoded;
- partial runtime, missing close/flush, or unreaped descendants cannot produce finalization pass;
- required raw-TB-VCD exact-set/no-limit receipt is returned;
- compile/simulation downstream state and supervisor first error are live and structured.

The separate one-round-localization `RULE_GAP_AUDIT` was not triggered because v63's target never executed.

## Current-version purpose

v64 preserves the v63 manifest/install/SCA identity repair, configuration, numeric behavior, workload, golden data, functional RTL, tail-round target, 41-role/64-signal causal cone and both ping-pong branches. It changes only the fresh identity and the audited package-local TB/runtime/parser/return/gate surfaces so a future authorized execution can reach the target and return a bounded causal VCD without the v63 false-stop and decoder escapes.

## Local gates and claim boundary

Staging and independent exact-final-ZIP checks passed for mode selector, package-local HDL lexical scan, focused frontend positive/negative controls, exact signal scope/state/source binding, runner resilience, native-flow non-interference, post-sim return, runtime layout/six exits, VCD runtime/process/streaming/retention, current-epoch first-fresh negatives, manifest exact-set, deterministic ZIP recomputation and prepublication storage identity. Relevant runnable regressions passed; the bundled Python lacks `jsonschema`, so that one schema-only runtime-layout test module is recorded as an environment skip while the actual runtime-layout validator/harness passed.

The sole future command, if separately authorized, is:

`bash r5_qadd_n7_tailround_lanephase_v64_tbvcdfix/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

This record makes no upload, lease, connection, production compile/simulation, DUT root-cause, natural-terminal, formal-D, E3, E4 or E5 claim.

## Storage lifecycle

The family storage manager atomically moved the consumed v63 package and its receipts from pending to tested, bound the formal-return analysis, and published v64 as the sole QLinearAdd pending package with its release receipts. The corrected global storage audit passes with four unique pending families and no errors. No server action occurred. The machine-readable lifecycle receipt is `outputs/qlinearadd_node0007_v64_tb_vcd_fix_release/storage_release/storage_lifecycle_complete.json`.
