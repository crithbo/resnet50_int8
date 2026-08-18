# family.conv.native — p49 formal return analysis and p50 local successor

- role_id: `family.conv.native`
- owner_epoch: `2`
- registry_epoch: `6`
- source package: `r5_n4_0cc_p49_tbvcdrt2`
- formal return: `C:/Users/15383/Downloads/r5_n4_0cc_p49_tbvcdrt2_r1786716730326805125_2394257_return.zip`
- fresh local successor: `r5_n4_0cc_p50_rdbufdrain`
- status: `PACKAGE_READY_NOT_RUN_LOCAL_GATES_COMPLETE`
- storage disposition: `STORAGE_LIFECYCLE_COMPLETE_P50_UNIQUE_PENDING`
- server actions performed: `[]`
- storage manager invoked: `true` (single authorized native rotation; writes stopped afterward)

## Previous progress and current purpose

p41 proved production compile beyond the Datahub repair. p42 corrected the two-bit vector valid/ready scalar false-negative. p46 crossed descriptor/buffer/MemAG/write-data accepts. p49 repaired p48 false-freeze and entered MSE4 with runtime-v3; its purpose was to recover the FIFO/outstanding/last/FSM/drain/finish cone and bind the manual-interrupt symptoms to exact evidence.

p50 retains the p42 predicate and MSE4 target. It retains all 66 p49 signals, adds 22 zero-hop driver signals, makes six causal candidates pairwise distinguishable, uses valid-qualified X/Z for plateau qualification, preserves raw four-state VCD, normalizes vector catalog names, bounds PID cleanup, captures attempt-owned console output, and returns exact consumed config copies plus the direct config/actual-compiler-path evidence review.

## p49 formal return result

- Identity/integrity: exact package/execution/attempt/core/VCD archive binding passed.
- Compile/sim: production compile `0`; simulation started; MSE4 target entry at `2445780625 ps`.
- Termination: external user `INT`, sim exit `125`; not natural, not timeout, not a legal plateau stop. Dump was not closed/flushed and the process tree was not fully reaped.
- Runtime-v3: shared evaluator remained the sole outer-runner exit authority; ADVANCING and suspect-only cases continued, full plateau and true three-interval freeze cases stopped. No false-freeze/false-plateau was found.
- LAST_PROVEN_GOOD: all 86 matrix loads completed and descriptor/buffer/MemAG/write-data progress crossed the p46 accept boundary.
- FIRST_DIVERGENCE: RD_Buffer_AG reached count `2`, full `1`, dequeue `0` while enqueue demand remained; WR prepared-data count held `32`, metadata/output queues were idle, and last/transaction/slice finish did not propagate.
- Root classification: `DYNAMIC_CAUSAL_NARROWED_RD_BUFFER_OUTPUT_FULL_TO_WR_PREPARED_DRAIN_JOIN_NOT_UNIQUE`.
- Natural/formal boundary: natural terminal, formal-D, E3, E4 and E5 remain unproven.
- File-open warning: absent from the complete p49 compile/sim logs; not attributable to native p49.
- `0001001`: 252 `0x00001001` APB configuration write/readback logger rows; not raw binary, DUT payload, VCD text or a fatal condition.
- “Theoretical time near end”: not a terminal witness. Last selected non-clock change was `2446468125 ps`, the VCD advanced to `14920935625 ps`, MSE4/SEM remained active and finish stayed low until external INT.

Streaming analysis artifacts:

- `outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_return_analysis_r1786716730326805125_2394257/formal_return_analysis.json` — 10566 bytes — SHA-256 `3a15b430cdd1642e468e594fdfd21fffc85902f1140529139d068625ce34986f`
- `outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_return_analysis_r1786716730326805125_2394257/RULE_GAP_AUDIT.json` — 2743 bytes — SHA-256 `82df53cf1a57d3177480f9fb0c99d5c300ab1f56dbe06452e005b106841387be`
- `analysis_state.json`, append-only `checkpoints.jsonl`, and incremental `report.md` are in the same analysis directory.

## Superseding config/RTL diagnosis policy disposition

`DIRECT_CONFIG_EVIDENCE`:

- Actual argv selected p49 `SCA_CFG` and `SCA_CFG_D` under NDP_copy02.
- The running consumer acknowledged both files and loaded 86 p46-qualified config paths; the returned config has 86/86 p46-qualified object paths, and `sca_cfg_D` has 28/28 p46-qualified D paths.
- No p49 file-open warning occurred, all 86 transfers completed and MSE4 entered. The cross-package dependency is directly proven, but a causal link to the MSE4 divergence is not.

`DIRECT_ACTUAL_RTL_EVIDENCE`:

- The production compile log proves NDP_copy02 `RD_Buffer_AG.sv` and `WR_Data_Channel.sv` path/module membership and binds the actual define set.
- The formal return does not contain the NDP_copy02 functional RTL bytes or hashes. Local NDP_copy01 RTL is therefore a static reference, not actual compiled content identity.

`DYNAMIC_EXECUTION_EVIDENCE`:

- The RD-buffer full/dequeue and WR prepared-data/metadata/output boundary state above is dynamically proven.

Disposition: `OPEN_UNVALIDATED_MECHANISM`, not `VALIDATED_ROOT_CAUSE`. Ranked validation targets are (1) prepared-capacity admission/overshoot, (2) prepared-data/metadata pairing and output admission, (3) last/count/finish propagation, and (4) the cross-package config dependency. No `CONFIG_WORKAROUND` is proposed or applied because no exact config→consumer→actual-content→state-transition chain or targeted positive/negative control has validated it.

Direct review receipt:

- `outputs/conv_native_four_lane_0ccae916_p49_tbvcdrt2_return_analysis_r1786716730326805125_2394257/CONFIG_RTL_DIRECT_EVIDENCE_REVIEW.json` — 7372 bytes — SHA-256 `19f62c4da87dc56abd1c94cb6739531a1a9e89fb63ac56c0a2c737b7485449bb`

## p50 package and gates

- Exact ZIP: `outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_release/r5_n4_0cc_p50_rdbufdrain.zip` — 5906571 bytes — SHA-256 `ad0e75a3c9202344272f6fdd9d22aafadeeca8a9e36a73e0fdcee0b53cd5af32`
- Deterministic repeat ZIP is byte-identical.
- Signals: 88 total; all 66 p49 signals retained; 22 zero-hop drivers added; 41 roles, four boundaries, six candidates and 24 pairwise matrix rows.
- Current-v4 causal-cone, mode selector tree/ZIP, HDL lexical tree/ZIP, full HDL frontend, source-bound, native-flow preflight noninterference, post-sim, runner tree/ZIP, compile-core, runtime-v3 replay, retention/streaming, first-fresh negative controls, package release admission and final exact-ZIP gates all pass.
- Selected shared regression: 98 tests passed.
- Config, numeric, workload, golden, functional RTL, p42 predicate and MSE4 target remain frozen. p50 `sca_cfg.json`/`sca_cfg_D.json` are byte-equal to p49.
- Before serialized release, p49 pending remained untouched and p50 was absent from managed storage. After mainline's native-only serialized release, the storage manager atomically moved p49 to tested and published p50 as the sole native pending package.

Receipts:

- `outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_release/gates/final_zip_release_audit.json` — 6188 bytes — SHA-256 `a7ba8341f77f29474f9c25aeb18a0c1c21730e2a98ae3ab8f150567ed35a6984`
- `outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_release/r5_n4_0cc_p50_rdbufdrain.release_evidence.json` — 1610 bytes — SHA-256 `018b3749314096d44a121c3c3288c76aeb4a98e18b39e94164151d616d1cf2fd`
- `outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_release/storage_wait_receipt.json` — 280 bytes — SHA-256 `02b837932664231bc5da6cbe6b00a73bbb98956f62fcbe88881a94ddfef69ef2`

## Storage lifecycle completion

- Corrected pre-audit: PASS; pending/tested/superseded = `4/40/23`.
- Atomic native rotation: p49 `pending→tested`, bound to the exact p49 formal analysis; p50 ZIP plus 23 exact receipt files published as the sole native pending set.
- Corrected post-audit: PASS; pending/tested/superseded = `4/41/23`.
- Global pending exact set: native p50, serialized v94b, GAP v69, QAdd v65.
- Pending p50 ZIP: 5906571 bytes — SHA-256 `ad0e75a3c9202344272f6fdd9d22aafadeeca8a9e36a73e0fdcee0b53cd5af32`.
- Pending p50 release evidence: 1610 bytes — SHA-256 `018b3749314096d44a121c3c3288c76aeb4a98e18b39e94164151d616d1cf2fd`.
- `PACKAGE_STORAGE_INDEX.json`: 326049 bytes — SHA-256 `6f81ab92af42318222184e1c7c27623a5c7a6a1e1b614d4b959f60f151290a3d`.
- Lifecycle receipt: `outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_release/storage_lifecycle_complete.json` — 2333 bytes — SHA-256 `37c395cb365944743367e255c81a3eb8c8409e287a5afddedc3f9a3093bbfdc1`.
- Storage writes stopped after the post-audit. No other-family artifact was modified.

## Future command and claim boundary

Unique future command, only after separate server authorization:

`bash r5_n4_0cc_p50_rdbufdrain/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

Expected return:

`/home/panqs/ndp/simresult/r5_n4_0cc_p50_rdbufdrain_<execution>_return.zip`

This is a local build/gate and storage-publication result only. It does not establish p50 production compile/simulation, a validated root cause, natural terminal, formal-D, E3, E4 or E5. The only storage action was the explicitly authorized native manager rotation. No upload, lease, connection, server run, plan/rule/registry edit, functional RTL edit or config edit occurred.
