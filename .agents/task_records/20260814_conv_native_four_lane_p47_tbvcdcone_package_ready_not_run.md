# family.conv.native PACKAGE_READY_NOT_RUN: p47 bounded causal-cone TB VCD

Date: 2026-08-14 (Asia/Shanghai)

## Ownership and activation

- role_id: `family.conv.native`
- owner thread: `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`
- owner_epoch: `2`
- registry_epoch: `6`
- family storage key: `conv_native_four_lane`
- activation_epoch: `tb-vcd-bounded-causal-cone-optional-v1-0820e1733437`
- selected_mode: `TB_VCD_BOUNDED_CAUSAL_CONE`
- exact package base: `r5_n4_0cc_p47_tbvcdcone`
- status: `PACKAGE_READY_NOT_RUN`

## Previous progress and current purpose

Previous-version progress: p41 proved production compile beyond the Datahub
public-surface repair; p42 corrected the two-bit vector valid/ready scalar
false-negative; p46 proved descriptor, buffer, MemAG and wdata accepts but its
formal run ended by INT before downstream terminal/accounting localization.

Current-version purpose: preserve the p42 vector predicate and p46-selected
MSE4 wdata/slice-finish target, then return a bounded, source-bound standard-TB
VCD causal cone over actual FIFO occupancy/enqueue/dequeue/full/empty,
tag/address/mask pairing, MemAG outstanding/response identity, last/count,
completion FSM drain/clear, per-MSE/slice finish aggregation, stage terminal,
formal-D boundary and global progress witness.

## Exact package and receipts

- release ZIP: `outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_release/r5_n4_0cc_p47_tbvcdcone.zip`
  - bytes: `5868419`
  - SHA-256: `7b4c171167c5c405546285669b34f6185f3b4aa9b1140c0c30c14b0b9469b857`
- final aggregate audit: `outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_release/gates/final_zip_release_audit.json`
- first-fresh validation: `outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_release/gates/first_fresh_validation.json`
- staging aggregate profile: `outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_release/server_package_build_profile.json`
- exact-ZIP VCD contract recheck: `outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_release/gates/tb_vcd_final_zip.json`
- exact-ZIP mode selector: `outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_release/gates/mode_selector_zip.json`
- exact-ZIP lexical/runner/post-sim receipts: `outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_release/gates/hdl_lexical_zip.json`, `runner_zip.json`, `post_sim_final_zip.json`
- runtime/retention receipts: `outputs/conv_native_four_lane_0ccae916_p47_tbvcdcone_release/gates/runtime_six_exit.json`, `runtime_layout.json`, `streaming_retention.json`

All current staging-tree aggregate, exact-final-ZIP, source-bound/full-HDL,
mode-selector, bounded-causal-cone, runner/compile-core, native-flow
noninterference, post-sim, runtime/six-exit/process-tree, retention/streaming,
first-fresh, deterministic-ZIP and prepublication storage gates passed. The
focused current shared regressions passed 75 tests. The previous p46 pending ZIP
remained byte-frozen until this conjunction passed.

## Storage lifecycle

After the full conjunction passed, the family storage manager atomically:

- published `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p47_tbvcdcone.zip` as the sole native pending ZIP;
- moved the byte-equal unrun p46 package and all receipts to `artifacts/operator_config_validation/r5-server-test-packages/superseded/conv_native_four_lane/r5_n4_0cc_p46_nativeflow/`;
- refreshed `PACKAGE_STORAGE_INDEX.json` without touching another family.

The corrected global storage audit returned `pass=true` with exactly
`pending_by_family.conv_native_four_lane = ["r5_n4_0cc_p47_tbvcdcone"]`.

## Frozen surface and runtime contract

- config, numeric, workload, golden, functional RTL and the selected diagnostic target are frozen;
- no DUT-driving HDL was introduced;
- actual Make dump argv are `DUMP_VCD=0`, `DUMP_FSDB=0`, `TB_DUMP_FSDB=0`;
- the sole waveform producer is package-local standard `$dumpfile/$dumpvars/$dumpon/$dumpoff/$dumpflush`;
- VPD, FSDB, FST, UCLI direct-VCD, vendor query and full-top unbounded dump are absent;
- decimal 100,000,000 bytes is warning-only; no byte/event cap, truncation, sampling or size deletion is allowed;
- 8GB VCD and 10GB return projections are operational fail-closed stops, not truncation;
- non-natural exits remain `PARTIAL/DIAGNOSTIC_EVIDENCE_INCOMPLETE` and cannot claim natural terminal/formal-D/E4/E5;
- analysis is streaming/resumable through `analysis_state.json`, append-only `checkpoints.jsonl` and incremental `report.md`;
- protected raw-result retention is `MAX_PROGRESS + LATEST_1 + LATEST_2` with all deletion prerequisites enforced.

## Sole future command and claim boundary

Only after a separate user authorization for server execution:

`bash r5_n4_0cc_p47_tbvcdcone/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`

No upload, lease, connection, server run, or production command occurred in
this construction. Local gates do not claim production compile, simulation,
root cause, natural terminal, formal D, E3, E4 or E5.
