# family.conv.native p48 formal return and p49 runtime-v3 successor

Date: 2026-08-14 (Asia/Shanghai)

## Ownership and status

- role_id: `family.conv.native`
- owner thread: `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`
- owner_epoch: `2`
- registry_epoch: `6`
- current mainline thread: `019ff027-e7db-72a3-b282-cfad8708da05`
- family storage key: `conv_native_four_lane`
- return package: `r5_n4_0cc_p48_xmrscopefix`
- fresh package: `r5_n4_0cc_p49_tbvcdrt2`
- selected mode: `TB_VCD_BOUNDED_CAUSAL_CONE`
- current activation epoch: `tb-vcd-exit-mechanism-consistency-v3`
- status: `RETURN_ANALYSIS_COMPLETE + RULE_CONFIRMATION_NO_CHANGE + PACKAGE_READY_NOT_RUN`

No upload, lease, connection, server run, or other server action occurred. No
plan, rule, owner registry, functional RTL, config, numeric, workload, or
golden surface was changed.

## Previous progress and current purpose

Previous-version progress: p41 proved production compile beyond the Datahub
public-surface repair; p42 corrected the two-bit vector valid/ready scalar
false-negative; p46 proved descriptor, buffer, MemAG and wdata accepts; p47
repaired its package-local XMR scope failure. p48 then compiled and entered
simulation, but a stale display-heartbeat runtime supervisor falsely classified
an active, advancing VCD run as frozen and stopped before the selected MSE4
target executed.

Current-version purpose: preserve the p42 vector predicate and selected MSE4
wdata/slice-finish causal target, replace the false-freeze authority with the
current shared runtime-v3 evaluator, and bind a quiescent archived causal-cone
VCD by full-file SHA-256, bytes, and final timestamp. The exact replay must keep
`ADVANCING` and `PLATEAU_SUSPECTED_ONLY` running, stop only on complete
dump-off-plus-grace plateau or a true three-interval freeze, and fail closed on
incomplete flush/close/reap/finalization evidence.

## p48 formal return integrity and streaming analysis

- exact return: `C:/Users/15383/Downloads/r5_n4_0cc_p48_xmrscopefix_r1786704774390782459_2297616_return.zip`
- exact return bytes: `6504753`
- exact return SHA-256: `a9bf1c85c827985b30461727c4f0371fea1f1d9fff71dcf43eca599054e4e0e3`
- package/execution: `r5_n4_0cc_p48_xmrscopefix` / `r1786704774390782459_2297616`
- one-root exact-member, CRC, package/execution/runtime/core and returned-package-manifest identities pass
- original ZIP remains preserved unchanged
- streaming analysis directory: `outputs/conv_native_four_lane_0ccae916_p48_xmrscopefix_return_analysis_r1786704774390782459_2297616`
- state: `analysis_state.json`
- append-only checkpoints: `checkpoints.jsonl`
- incremental report: `report.md`
- formal analysis: `formal_return_analysis.json`
- mandatory build-failure rule audit: `PACKAGE_BUILD_FAILURE_RULE_AUDIT.json`

The VCD was consumed in bounded 8 MiB chunks through EOF rather than loaded as
one object: `107352563` bytes, `2432725` lines, `14` checkpoints, last timestamp
`303783125 ps`.

## p48 production classification

- production compile exit: `0`
- simulation started: `true`
- outer exit: `124`
- timed out: `true`
- natural terminal: `false`
- target entry: `false`
- VCD flush/close completion: `false`
- owned process-tree reap completion: `false`
- final classification: `PACKAGE_RUNTIME_FALSE_FREEZE / PARTIAL / DIAGNOSTIC_EVIDENCE_INCOMPLETE`

The returned actual root was `/home/panqs/ndp/NDP_copy02`, while the published
command was rooted at `/home/panqs/ndp/NDP_copy01`; this is
`EXECUTION_ROOT_DRIFT_RESTRICTED_DIAGNOSTIC_CONSUMPTION` and prevents an
integration identity claim.

VCD sizes at 0/30/60/90 seconds were `0`, `33576731`, `60881567`, and
`107090015` bytes, and the final VCD reached `303783125 ps`, while the display
heartbeat remained at `625`. The old supervisor nevertheless emitted
`SIM_TIME_FREEZE`. This matches the QAdd-v63-like mid-run runtime escape: VCD
time and bytes advanced, so the stop was not a true simulation-time freeze.

`LAST_PROVEN_GOOD`: production compile passed the p47 XMR repair; simulation and
the VCD advanced through `303783125 ps`; 32 preload transfers completed and
matrix transfer 33 started.

`FIRST_DIVERGENCE`: the outer supervisor treated a stale display/log heartbeat
as authoritative despite fresh VCD timestamps and continued file growth, then
stopped and finalized a partial attempt before the MSE4 target.

The last visible operation remained preload (`Write Burst24`). MSE4 was never
enabled, so p48 gives no new FIFO/outstanding/response/last/count/FSM/drain/
clear/finish narrowing beyond p46. It does not prove a DUT hang, a natural
terminal, formal D, E3, E4, or E5.

## Mandatory rule audit disposition

p47 and p48 are two consecutive package-local attempts that did not execute the
target, so `PACKAGE_BUILD_FAILURE_RULE_AUDIT` was completed before p49.

Disposition: `RULE_CONFIRMATION_NO_CHANGE`. Current rules already fail closed
for p47's XMR scope defect and p48's stale-heartbeat false freeze. The missing
piece was isolated package implementation/release against the newly activated
runtime-v3 contract, not a synonymous shared-rule delta.

## p49 exact package, receipts, and gates

- exact pending ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p49_tbvcdrt2.zip`
- ZIP bytes: `5886153`
- ZIP SHA-256: `a9d12f85c1d36757a787c0cd9f5672e256b865c2bb6a75316721259bb1aeb318`
- pending receipts: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p49_tbvcdrt2/`
- release workspace: `outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_release`
- final aggregate: `outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_release/gates/final_zip_release_audit.json`
- release evidence: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p49_tbvcdrt2/r5_n4_0cc_p49_tbvcdrt2.release.json`

All current staging aggregate, exact-final-ZIP, deterministic recomputation,
mode selector, lexical/full-HDL/source-bound, TB-VCD causal-cone, native-flow
noninterference, post-sim, runner/compile-core, runtime/six-exit/process-tree,
streaming/retention, current-epoch first-fresh and package-release-admission
gates pass. Six v3 negative controls pass. Exact packaged replay proves:

- `ADVANCING -> CONTINUE`
- `PLATEAU_SUSPECTED_ONLY -> CONTINUE`
- `PLATEAU_DUMP_OFF_PLUS_GRACE -> CAUSAL_PLATEAU`
- `THREE_INTERVAL_TRUE_FREEZE -> SIM_TIME_FREEZE`

The packaged shared evaluator receipt is the sole outer-runner exit authority.
The finalizer performs one full streaming VCD scan and binds the quiescent
archive's SHA-256, bytes, and last timestamp. Missing dump flush/close, owned
process reap, archive identity, or authority agreement cannot finalize PASS.

Actual Make dump argv remain `DUMP_VCD=0`, `DUMP_FSDB=0`,
`TB_DUMP_FSDB=0`. No VPD/FSDB/FST, UCLI direct-VCD, vendor query, whole-chip
unbounded dump, truncation, sampling, hard byte cap, or size deletion is used.

## Storage lifecycle and index identity

The family storage manager atomically archived consumed p48 and its streaming
analysis receipts under
`tested/conv_native_four_lane/r5_n4_0cc_p48_xmrscopefix/`, then published p49
as the sole native pending ZIP with 18 indexed receipt files.

- storage index: `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`
- index bytes at native publication: `290753`
- index SHA-256 at native publication: `d5bdcc8093cef3ee1a3fa5ee9221e665c29be77348e72a887686f306d402ae61`
- indexed family: `conv_native_four_lane`
- indexed pending package: `r5_n4_0cc_p49_tbvcdrt2`

The native entry is internally clean and `pending_by_family` names exactly p49.
The first corrected global audit after this publication was temporarily blocked
only by a concurrently introduced, not-yet-indexed serialized-family v94b
pending package. No serialized artifact was touched by this family.

Mainline then issued `MAINLINE STORAGE FREEZE`. The read-only freeze snapshot is:

- physical native pending: `r5_n4_0cc_p49_tbvcdrt2`
- indexed native pending: `r5_n4_0cc_p49_tbvcdrt2`
- physical serialized pending: `r5_n4_hw_v94b_tbvcd_wrdrain`
- indexed serialized pending: `r5_n4_hw_v93d_tbvcd_hardened`

Therefore native package/receipt/family identity is complete, but the global
index is cross-family stale. No further storage manager write, move, or index
refresh was attempted after the freeze. A global-clean claim is withheld until
mainline completes the serialized/index repair and sends
`GLOBAL_STORAGE_AUDIT_CLEAN`.

## Sole future command and claim boundary

Only after separate user authorization for server execution:

`bash r5_n4_0cc_p49_tbvcdrt2/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

Expected execution-bound return:

`/home/panqs/ndp/simresult/r5_n4_0cc_p49_tbvcdrt2_<execution>_return.zip`

Status is `PACKAGE_READY_NOT_RUN`. Local gates prove exact package composition,
runtime-v3 replay behavior, deterministic publication, frozen surfaces, and
fail-closed return mechanics. They do not claim production compile, simulation,
target entry, root cause, natural terminal, formal D, E3, E4, or E5.
