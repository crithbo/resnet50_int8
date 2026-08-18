# family.conv.native p47 formal return → p48 package-local XMRE scope repair

Date: 2026-08-14 (Asia/Shanghai)

## Ownership and disposition

- role_id: `family.conv.native`
- owner thread: `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`
- owner_epoch: `2`
- registry_epoch: `6`
- current mainline: `019ff027-e7db-72a3-b282-cfad8708da05`
- return disposition: `RETURN_ANALYSIS_COMPLETE`
- rule-audit disposition: `RULE_GAP_AUDIT_NOT_TRIGGERED` and `PACKAGE_BUILD_FAILURE_RULE_AUDIT_NOT_TRIGGERED`
- successor disposition: `PACKAGE_READY_NOT_RUN`
- no upload, lease, connection, server run or other server action occurred
- plan, rules, owner registry, functional RTL, config, numeric, workload and golden surfaces were not modified

## Previous progress and current purpose

Previous-version progress: p41 proved production compile beyond the Datahub
public-surface repair; p42 corrected the two-bit vector valid/ready scalar
false-negative; p46 proved descriptor, buffer, MemAG and wdata accepts but ended
by manual INT before downstream terminal/accounting localization.

p47 purpose was to preserve the p42 predicate and cover the FIFO,
outstanding/response, last/count, completion FSM, drain/clear, per-MSE/slice
finish aggregation and global terminal causal chain in one bounded standard-TB
VCD.

Actual p47 result: production compile exited `2` before simulation.  VCS
reported exactly three package-local TB XMREs at
`native_mse4_bounded_causal_cone_vcd.sv:85..87`, all resolving nonexistent
dump-only `MSE_INST[5]`, `[6]`, `[7]` paths.  The selected `MSE_INST[4]` bind,
its full target scope, the parent Stream_Engine aggregate and the Slice
Execution Manager resolved before this stop.

p48 purpose is therefore strictly narrower: delete those three invalid
dump-only scopes while preserving selected MSE4, the p42 vector predicate,
the complete 41-role catalog/candidate matrix and the original
FIFO/outstanding/last/FSM/drain/clear/finish target.

## Exact p47 formal-return analysis

- exact return:
  `C:/Users/15383/Downloads/r5_n4_0cc_p47_tbvcdcone_r1786698137747571521_2253824_return.zip`
- package / execution / attempt:
  `r5_n4_0cc_p47_tbvcdcone` / `r1786698137747571521_2253824` / `a0`
- all 22 ZIP members were stream-consumed with exact root, duplicate, size,
  SHA-256, CRC, core-manifest and returned-package-manifest checks passing
- analysis state:
  `outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_return_analysis_r1786698137747571521_2253824/analysis_state.json`,
  bytes `1097`, SHA-256
  `01bc7f9e9903581bccd91c8a12429b9c13afd56ea6297b66d4c0ea72435049c0`
- append-only checkpoints:
  `outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_return_analysis_r1786698137747571521_2253824/checkpoints.jsonl`,
  bytes `1257`, SHA-256
  `7ef6910b26a525dd06e0fd607ddf0cbb02e7eafef363103c031f14f3dee14d3f`
- incremental report:
  `outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_return_analysis_r1786698137747571521_2253824/report.md`,
  bytes `1116`, SHA-256
  `e9cbfcd5adeab878410dd6f3a06c964878c8c3ca7fdaeafe36ebd1ea6d6e867d`
- formal analysis:
  `outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_return_analysis_r1786698137747571521_2253824/formal_return_analysis.json`,
  bytes `6490`, SHA-256
  `34a6b70c729df75c9c55f51457b046d8df1e411b0225510b141430624adcaf4d`
- streaming state: `NO_VCD_COMPILE_FAILED_ANALYSIS_COMPLETE`; the return has
  no VCD member, no runtime catalog/matrix, no owner-cycle or stop receipt, and
  no signal events

## Causal adjudication and boundaries

- family cumulative `LAST_PROVEN_GOOD`: p46 selected-MSE4 qualified wdata
  acceptance sequence 20 at `2446467000 ps`, with descriptor/buffer/MemAG
  accepts already proven
- current-execution last good: actual production compilation under
  `/home/panqs/ndp/NDP_copy02` reached VCS elaboration/XMR resolution for the
  package-local TB
- current-execution `FIRST_DIVERGENCE`: line 85 package-local `$dumpvars` XMRE
  at `MSE_INST[5]`; lines 86 and 87 are the only identical followers
- dynamic `FIRST_DIVERGENCE`: `NOT_OBSERVED_SIMULATION_NOT_STARTED`
- p42 vector repair: byte-frozen in the package identity but not dynamically
  re-tested in p47
- FIFO/outstanding/response/last/count/FSM/drain/clear/finish matrix:
  `NOT_EVALUABLE_NO_RUNTIME_CATALOG_MATRIX_OR_VCD`
- root classification:
  `PACKAGE_LOCAL_TB_SCOPE_XMR_NONEXISTENT_MSE_INSTANCES`, confidence
  `UNIQUE_HIGH` for the compile stop only; no DUT root is claimed
- published root was `/home/panqs/ndp/NDP_copy01`, actual root was
  `/home/panqs/ndp/NDP_copy02`; consumption remains
  `EXECUTION_ROOT_DRIFT_RESTRICTED_DIAGNOSTIC_CONSUMPTION`
- natural terminal: false; formal D: not evaluated; E3/E4/E5: false
- early-stop status: `NOT_REACHED_NOT_EVALUABLE`; compile failed before any
  simulator time, causal digest, `$dumpoff`, grace or stop evidence existed

## Rule-audit disposition

`RULE_GAP_AUDIT` is not triggered because production compile did not succeed
and the target did not execute.  `PACKAGE_BUILD_FAILURE_RULE_AUDIT` is not
triggered because p46 dynamically executed the same selected target and p47 is
the first subsequent package-local pre-execution failure, so the consecutive
two-attempt threshold is not met.

An exact local negative/positive control is nevertheless bound at
`outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_release/gates/p47_xmr_scope_repair.json`,
bytes `1462`, SHA-256
`00864c35106480ea05e8149a432fc18db726eef0045ba73490233a44975dace6`.
It proves that p47 contains exactly one of each invalid `[5]..[7]` reference,
p48 tree and final ZIP contain none, reinserting one is rejected, the TB diff
is exactly three deleted lines, and selected MSE4/aggregate scopes, workload,
catalog, candidate matrix and runner semantics remain frozen.

## Fresh package and gates

- pending ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p48_xmrscopefix.zip`
- bytes: `5869624`
- SHA-256:
  `8205601fc5c4786962992cd759a3a37b8d96787e7dbb8b1d0975c6cf90815ed2`
- final aggregate audit:
  `outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_release/gates/final_zip_release_audit.json`,
  bytes `7821`, SHA-256
  `8142b32ac2c621c7b3deb50a2ccb2f65fbfabd87e5dc7a3bb3e85893061bb7b7`
- first-fresh validation:
  `outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_release/gates/first_fresh_validation.json`,
  bytes `2539`, SHA-256
  `d4c7965c633a60fa9000286f83d2f4fd5e75a6a39d6f6034889d622467e40a69`
- staging aggregate profile:
  `outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_release/server_package_build_profile.json`,
  bytes `26343`, SHA-256
  `fcb52435e3e06e1d789c18bb5a7c4eb09dcaf8c926650c1724ecf81191ad667f`

The following current gates all pass on staging and/or the independent exact
final ZIP as applicable: mode selector; bounded causal-cone VCD; package-local
HDL lexical; full frontend/source-bound; runner definition-before-use and
compile-core; native-flow preflight noninterference; post-sim core return;
runtime layout/six-exit/process-tree; streaming/retention; first-fresh;
deterministic ZIP; exact p47 XMRE negative control; and prepublication storage.
The focused shared suite passed 76 tests.

## Storage lifecycle

The family storage manager atomically retired consumed p47 from pending to
`tested/conv_native_four_lane/r5_n4_0cc_p47_tbvcdcone/` and published p48 as
the sole native pending package.  Corrected global audit is `pass=true` with
counts pending=`4`, tested=`34`, superseded=`22`, and
`pending_by_family.conv_native_four_lane=[r5_n4_0cc_p48_xmrscopefix]`.
`PACKAGE_STORAGE_INDEX.json` bytes=`249280`, SHA-256
`2224a6f27a5833fe86120cab2a47e4d3d6958842ec0c6092f9a7cc478b8b2b6a`.

## Sole future command and claim boundary

Only after separate user authorization for server execution:

`bash r5_n4_0cc_p48_xmrscopefix/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

This receipt proves formal-return integrity, the exact p47 package-local
compile-stop root, the three-line dump-scope repair, frozen package surfaces,
local gates and storage publication.  It does not claim p48 production compile,
simulation, FIFO/last/FSM/finish behavior, natural terminal, formal D, E3, E4
or E5.  No server action occurred.
