# QLinearAdd node0007 v46 recovered return → v49 tail-round flow

## Provenance

- analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- recovered return: `C:/Users/15383/Downloads/r5_qadd_n7_fullchain_returnfix_v46_r1786110475344343035_3722926_return.zip`
- return bytes/SHA256: `407184` / `fbde2a98d03c6de43219dba469d2113b628706f42803604da8f19daf424be07f`
- machine analysis: `artifacts/operator_config_validation/r5-qlinearadd-node0007-v46-recovered-return-analysis/report.json`
- machine analysis SHA256: `4efad03a21fef653f76d0e5b69b3f5ed3270f832da008fbbe58185ebfa957d49`
- release report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v49-package/release_report.json`
- release report bytes/SHA256: `4641` / `9b7e936be001c2552dddb7783306030502cd580bd682a96ba9efab4c1d5fdde1`

## RETURN_ANALYSIS

The ZIP is a recovery publication of the already-run v46 execution, not a new DUT run. CRC, root, path safety, exact-set, allowlist and per-file receipts pass. Its returned package manifest is byte-identical to the repeatable v46 source manifest and that source is bound by the frozen-functional receipt.

Compile exited 0. Simulation exited 124 after 28,887.15 seconds with signal `NONE`; natural terminal is false. All six stages started and the first five finished. `op_tail_round` started, produced finite request/rdata/wdata activity, and then stopped making qualified progress for at least 43 complete 1,048,576-cycle stall windows. Formal UINT8 D is expected 28, present 0, missing 28; mismatch is not evaluable. E3/E4/E5 remain false.

- LAST_PROVEN_GOOD: `OP_TAIL_MUL_COMP_FINISH_THEN_OP_TAIL_ROUND_FINITE_REQ_RDATA_WDATA_ACTIVITY`
- FIRST_DIVERGENCE: `OP_TAIL_ROUND_AFTER_FINITE_MSE4_REQUEST_ACTIVITY_BEFORE_PAIRED_WDATA_GA_OUTPUT_AND_COMP_FINISH`
- HANG_ROOT_CAUSE: not unique inside Buffer5 → Buffer_AG queue → RD_Buffer_AG → WR_Data_Channel → GA/terminal flow control.

The v46 canonical result is not authoritative for progress because its buffer enable levels were counted as events. Stable level is state only; the defensive adjudication is a long-running hang, not “still progressing.”

## Successor closure

Unreleased v47 was rejected by the current shared runtime gate for silent nonzero runner exits and stale path-budget receipts. Unreleased v48 fixed those defects but was rejected before publication because its manifest rule paths were encoding-corrupted. Neither identity entered pending storage.

Fresh v49 preserves the six-stage workload, config, numeric/W3/qparams/tail/golden, 8-hour production timeout and functional RTL. It adds only the qualified tail-round flow diagnostic plus current runner/provenance corrections. The observer counts accepted events in `clk_sg`, snapshots in live `clk_db`, and leaves ready/full/empty/valid levels as state.

## PACKAGE_RELEASE

- status: `PACKAGE_READY_NOT_RUN`
- class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- evidence: `E2_LOCAL_ONLY`
- candidate_release: `false`
- pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_flow_v49.zip`
- bytes/SHA256: `38066331` / `b5fe58fff8401fb60284951859be975931e8744e1e0235b60847973513abf071`
- receipt sidecar: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/qlinearadd_node0007/r5_qadd_n7_tailround_flow_v49/r5_qadd_n7_tailround_flow_v49.zip.sha256`
- server command: `cd /home/panqs/ndp && unzip -q r5_qadd_n7_tailround_flow_v49.zip && bash r5_qadd_n7_tailround_flow_v49/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`
- expected return: `/home/panqs/ndp/simresult/r5_qadd_n7_tailround_flow_v49_r*_return.zip`

Storage rotation moved the consumed v46 pending identity to tested. Exactly one QAdd ZIP remains pending.

## Validation receipts

- build receipt SHA256: `800e8d23e6ad8d03672d872b9d56140ee3de238de73c0b1ed7717d02d060aba5`
- family validation SHA256: `b44a04175164e5b94742e58a4231c3088d3a50e5448cd322eb58a01b0237165d`, valid=true, errors=0
- shared runtime validation SHA256: `66dc2133f930934ca597d63ad55ab052147df59a8d614bb859333fde69bab6a0`, pass=true, errors=0
- final-ZIP self-audit SHA256: `6d75b4c0c06e35222614f3b9e82c5447ffcd709fd766434b0bdbb474c2677aba`, `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors=0
- HDL negative exits: declaration=1, update=1, actual-consumer misspell=1, wrong-sibling=1
- exact runner failure unit: exit=37 with package/code/message stderr marker

## BLOCKER_DELTA / rule feedback

Closed recovery-publication and source-binding blockers. Opened `B_QADD_V46_TAIL_ROUND_LONG_HANG` and `B_QADD_V46_CANONICAL_LEVEL_AS_PROGRESS`; v49 is the single highest-information successor for the remaining interval.

`RULE_CONFIRMATION`: current qualified-event, ungated snapshot, canonical decision, final-ZIP, runner visibility, install-only and storage-rotation rules correctly detected both the dynamic false-progress claim and the unreleased packaging defects. No non-synonymous rule delta is proposed.

No server action, DUT rerun, numeric/workload/config/golden repeat, or functional RTL change occurred.
