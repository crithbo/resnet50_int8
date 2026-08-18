# family.conv.native — p50 formal return analysis and p51 local successor

- role_id: `family.conv.native`
- owner thread: `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`
- owner_epoch: `2`
- registry_epoch: `6`
- source package: `r5_n4_0cc_p50_rdbufdrain`
- formal return: `C:/Users/15383/Downloads/r5_n4_0cc_p50_rdbufdrain_r1786734260114876474_2596301_return.zip`
- fresh local successor: `r5_n4_0cc_p51_metaidxcone`
- status: `STORAGE_LIFECYCLE_COMPLETE`
- storage disposition: `P50_TESTED_P51_SOLE_NATIVE_PENDING`
- server actions performed: `[]`
- storage manager invoked: `false`

## Previous progress and current purpose

p41 proved production compile beyond the Datahub repair and p42 fixed the two-bit vector valid/ready scalar false-negative. p50 extended the p46/p49 accepted-progress boundary through RD_Buffer_AG dequeue, prepared-data, metadata and output join with 88 source-bound signals.

p51 retains all 88 p50 signals and adds 18 exact Buffer_AG/Memory_AG index-queue, WR metadata-transfer and spatial-accounting drivers. It changes only the package identity and diagnostic/runtime-return surfaces. Config, numeric data, workload, golden data, functional RTL, the p42 predicate and the MSE4 target remain frozen.

## p50 exact return and streaming integrity

- exact return bytes: `132713184`
- exact return SHA-256: `814ad1ea82523ec064451d013ca980394944d541ee0867088575d32c6463b22c`
- ZIP/member/package/execution/attempt/core identities: PASS
- production compile: `0`
- simulation started: `true`
- target entry: observed at `2445780625 ps`
- simulator exit: `124`
- shared evaluator decision: `WALL_CEILING`
- signal: `NONE`
- natural terminal: `false`
- formal-D/E3/E4/E5: unproven
- execution root: `/home/panqs/ndp/NDP_copy02`
- published root: `/home/panqs/ndp/NDP_copy01`
- root identity disposition: `EXECUTION_ROOT_DRIFT_RESTRICTED_DIAGNOSTIC_CONSUMPTION`

The VCD was consumed with bounded resume checkpoints to EOF. The exact VCD is `849662423` bytes, last timestamp `33883656250 ps`, last effective non-clock change `2446468125 ps`, and timescale `1ps`. The return binds the untruncated full-file archive identity, but the wall-ceiling exit left dump close/flush and full process-reap incomplete, so the evidence is `PARTIAL/DIAGNOSTIC_EVIDENCE_INCOMPLETE`.

The apparent remaining process is the package-local supervisor's transient `ps` child: it had no readable immutable `start_ticks`. The p51 helper filters identity-less snapshot rows rather than treating them as an owned simulator process.

Streaming artifacts:

- `outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_return_analysis_r1786734260114876474_2596301/analysis_state.json`
- `outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_return_analysis_r1786734260114876474_2596301/checkpoints.jsonl`
- `outputs/conv_native_four_lane_0ccae916_p50_rdbufdrain_return_analysis_r1786734260114876474_2596301/report.md`
- formal analysis: `160270` bytes, SHA-256 `5835914969f5439c6760d93aac19435141c126006a79e48ef1f756234921a6b4`

## Dynamic causal result

`LAST_PROVEN_GOOD`: production compile passed, all configured transfers reached the native flow, MSE4 entered, and descriptor/Buffer_AG/RD_Buffer/prepared-data activity crossed the p46/p49 accepted-progress boundary.

`FIRST_DIVERGENCE`: at `2446468125 ps`, RD buffer count was `2/full=1/dequeue=0`; prepared-data count was `32/valid=1/read_hs=0`; metadata queue was empty with transfer size zero; output input-valid was zero although both output slots were ready; last/finish did not propagate.

Accepted-cycle reconstruction proves:

- metadata request/write/read/output write/read accepts: `18`, each metadata request size `16`, sum `288`
- prepared writes/reads: `20/18`
- RD-buffer enqueues/dequeues: `23/21`

Thus the two residual prepared groups and two RD-buffer entries are exact, not a sampling inference. Output-buffer admission and completion propagation are rejected as first causes. The validated boundary classification is:

`DYNAMICALLY_PROVEN_METADATA_EMPTY_AT_PREPARED_OUTPUT_JOIN__UPSTREAM_METADATA_VS_BUFFER_TAG_CAUSE_OPEN`

The exact RTL root remains open between Buffer_AG versus Memory_AG index lifetime, WR metadata transfer underproduction and prepared spatial-size accounting.

## Direct config and actual RTL evidence

`DIRECT_CONFIG_EVIDENCE`: actual argv consumed the returned p50 `SCA_CFG`/`SCA_CFG_D`; the target ran and all configured transfers completed. No exact config-to-join contradiction is proven, so no config workaround is validated or proposed.

`DIRECT_ACTUAL_RTL_EVIDENCE`: the p50 compile log proves actual source-path/module/define membership, but the p50 return's packaged review was stale and no actual compiled RTL bytes were returned. Local NDP_copy01 equations are therefore reference-only for p50.

p51 closes this return defect after the real production compile by copying the exact seven critical actual RTL sources and a source manifest into the attempt, then generating the config/actual-RTL/dynamic review from that same attempt. The capture is post-compile and is not a server preflight/provider inventory.

Direct review receipt: `9672` bytes, SHA-256 `69803c835a1bf9cd144619b1f3d2cb3f07d431bb7ef0111a6af51bad392543a6`.

## Rule gap and package-defect disposition

`RULE_GAP_AUDIT` disposition is `RULE_CONFIRMATION_NO_CHANGE`. Current adaptive-v4/runtime-v3 rules already require qualified accepts and full source-bound driver coverage. The failure was a family implementation error: p50 counted a held `buf_ag_ob_wr_en` while the RD FIFO was full as progress on every owner clock, preventing a legal plateau. p51 uses only `en && !full` / `deq && !empty` accepts for RD, metadata and both index queues and carries a held-full negative control.

`PACKAGE_BUILD_FAILURE_RULE_AUDIT` is not triggered: this is one p50 package-local defect; the earlier p49 termination was an external user interrupt, not a second package-local target-execution failure.

Rule-gap receipt: `2805` bytes, SHA-256 `1504ad94a2a334c8df13403b2b5219deb31595279ae51ab1a719db6ce846b119`.

## p51 local package and gates

- ZIP: `outputs/conv_native_four_lane_0ccae916_p51_metaidxcone_release/r5_n4_0cc_p51_metaidxcone.zip`
- ZIP bytes: `5947691`
- ZIP SHA-256: `858a4672a01958726b8eba6a65cbbd1c72be4a33343d4fc9d44cb874d453031f`
- deterministic repeat ZIP: byte-identical
- 106 signals: 88 p50 retained, 18 added, no removals
- 41 roles, four boundaries, nine candidates, 36 complete pairwise candidate/boundary rows
- exact staging and clean-final-ZIP package Python/schema runtime, TB-VCD adaptive-v4, source-bound, full HDL frontend, lexical tree/ZIP, mode-selector tree/ZIP, runner tree/ZIP, runtime-preflight, runtime-v3 replay, held-full/process-row negative controls, post-sim return scenarios, first-fresh and deterministic final-ZIP gates: PASS
- current shared regression: `93 passed, 7 subtests passed`
- final release audit: `5682` bytes, SHA-256 `3b285e639f19fc644cf00d5d583662abb12938b8cfb56ecc538b6a550e7de0c8`
- release evidence: `1407` bytes, SHA-256 `b323deec3e1bcb18bee4659ad9223d92fcedb22f3b3a142c5a496d2b6c179359`
- storage-wait receipt: `321` bytes, SHA-256 `b7957b72b4875058499d9901d7d78cb7256957cddc4158870b2f27ce71be69ed`

p50 remains the sole native pending package and p51 is absent from managed storage. No storage manager call, index refresh, package move, upload, lease, connection or server run occurred.

## Future command and claim boundary

Unique future command, only after separate server authorization:

`bash r5_n4_0cc_p51_metaidxcone/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

Expected return:

`/home/panqs/ndp/simresult/r5_n4_0cc_p51_metaidxcone_<execution>_return.zip`

This is a local analysis/build/gate and authorized storage-publication result. It does not establish p51 production compile/simulation, a validated exact RTL root, natural terminal, formal-D, E3, E4 or E5.

## Storage lifecycle completion

After mainline granted native-only serialized storage authority, the corrected manager pre-audit passed with pending/tested/superseded counts `3/44/24`. The manager atomically moved consumed p50 and all receipts into `tested/conv_native_four_lane/r5_n4_0cc_p50_rdbufdrain/`, binding the exact p50 formal analysis, and published p51 plus 27 receipt files as the sole native pending package.

The corrected post-audit passed with counts `3/45/24`. The exact pending set is native p51, serialized v95b and QAdd v66. The pre/post non-native semantic snapshot remained byte-identical across 5821 files. No other-family artifact was modified.

- pending p51 ZIP: `5947691` bytes, SHA-256 `858a4672a01958726b8eba6a65cbbd1c72be4a33343d4fc9d44cb874d453031f`
- tested p50 ZIP: `5906571` bytes, SHA-256 `ad0e75a3c9202344272f6fdd9d22aafadeeca8a9e36a73e0fdcee0b53cd5af32`
- `PACKAGE_STORAGE_INDEX.json`: `358186` bytes, SHA-256 `4fedb57afb70c48d2c5c6c35f5dcd318fd4a5bc7c9bac6316af7bf901b85ce4d`
- lifecycle receipt: `outputs/conv_native_four_lane_0ccae916_p51_metaidxcone_release/storage_lifecycle_complete.json`

All storage writes stopped immediately after post-audit. No server action occurred.
