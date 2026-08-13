# Native Conv p43 formal-return analysis: shared portable runtime escape and successor hold

Date: 2026-08-12 (Asia/Shanghai)

## Ownership and dispatch

- `role_id`: `family.conv.native`
- `owner_thread_id`: `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`
- `owner_epoch`: `2`
- `registry_epoch`: `6`
- `current_mainline_role_id`: `mainline.control`
- `current_mainline_thread_id`: `019ff027-e7db-72a3-b282-cfad8708da05`
- formal-return dispatch: `FORMAL_RETURN_READY / DIRECT_FAMILY_DISPATCH`
- controlling follow-up: `CROSS_FAMILY_SHARED_PORTABLE_RUNTIME_ALERT / READ_RETURN_AND_HOLD_SUCCESSOR`
- current owner registry at completion:
  - path: `contracts/current_session_owner_registry_v1.json`
  - bytes: `13842`
  - SHA-256: `15236511d6cf0c16230c45494dddc93fcdc740ff7ab253dc30b785c21036de8a`
- No plan, public rule, active-rule registry, owner registry, package, storage index, config, numeric, workload, golden, functional RTL, or shared portable-method file was modified.
- No upload, lease, server run, server connection, or other server action occurred.

## Required previous-progress/current-purpose statement

Previous-version progress: p41 proved production compile beyond the Datahub public-surface repair. p42 corrected the package-local two-bit valid/ready scalar-comparison false negative while retaining the MSE4 wdata/slice-finish target.

Current-version purpose: p43 preserves the corrected vector-handshake diagnostic and adds same-attempt raw VPD, direct VCD, and complete source-bound query/event evidence for locally actionable MSE4 causal localization.

## Exact formal return and integrity

- user-supplied formal return, preserved in place and not modified:
  - path: `C:/Users/15383/Downloads/r5_n4_0cc_p43_portablevq_r1786512367639483307_1421638_return.zip`
  - bytes: `8098284`
  - SHA-256: `c26fdc4c191cbaa2fec244fe8fd9c1629d77fc1807186e7089324529ebccb095`
- exact p43 source package, left unchanged in pending:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p43_portablevq.zip`
  - bytes: `6016442`
  - SHA-256: `657767774ef6762f4e93c3c0b23da71895c7ec699837ca443b0210457d55c11c`
- formal analyzer:
  - path: `tools/analyze_conv_native_four_lane_0ccae916_p43_return.py`
  - bytes: `22215`
  - SHA-256: `5b805074253322bc43d474fd50b011629fcdb8594ef8d398d8a589e23ab90efc`
- analyzer report:
  - path: `outputs/conv_native_four_lane_0ccae916_p43_return_analysis/report.json`
  - bytes: `28801`
  - SHA-256: `6728e8dc817941e6c329232fded8c2b98e1d9deea45bf80d3381eae58b34d85f`
  - status: `RETURN_ANALYSIS_COMPLETE_SHARED_PORTABLE_METHOD_RUNTIME_ESCAPE_SUCCESSOR_HOLD`
  - `valid=true`; two consecutive analyzer runs produced the same report identity.
- ZIP CRC, single-root, path-traversal, duplicate-member, symlink, and nested-archive checks: PASS.
- all `RETURN_CORE_MANIFEST.json` per-member byte/SHA receipts: PASS, mismatches `{}`.
- package/execution/return-basename identity: PASS for `r5_n4_0cc_p43_portablevq`, `r1786512367639483307_1421638`, and the supplied basename.
- returned package manifest, source-bound binding, source-bound generation report, and portable query source report are exact byte matches to the p43 source package: PASS.
- `missing_required_entries=[]`; core disposition is correctly `EVIDENCE_INCOMPLETE`.

## Compile, simulation, and time-0 escape

- Production compile exit is `0`; actual compile identity collection is marked true. This continues to prove the p41/p42 Datahub public-surface and package-local observer compile repairs crossed production compilation.
- Actual simulation argv is returned and binds the same `a0` attempt, exact UCLI Tcl, `DUMP_VCD=1`, `DUMP_FSDB=0`, `TB_DUMP_FSDB=0`, and `DUMP_PORTABLE_VCD=1`.
- `SIM_EXIT_RECEIPT.json` records simulator-process launch with `sim_exit_code=0`, signal `NONE`, and `natural_terminal_observed=false`.
- `package_local_preflight_status.json` independently records `dut_simulation_started=false`.
- Therefore `simv=0` is not DUT success. The production simulator returned zero after its command script aborted before time advance.
- Exact failing Tcl sequence:
  1. create authoritative `wave.vpd` as VPD;
  2. add `tb_NDP_Top_new_phy`, depth 0, aggregates;
  3. attempt `wave.vcd` with `dump -type VCD`;
  4. only after that line, issue `run`.
- Production VCS identity is `V-2023.12-SP2_Full64`.
- At Tcl line 3 and time `0 ps`, VCS reports `Error-[UCLI-DUMP-UNSUPP-FORMAT] Unsupported dump format` and states that the supported formats are only EVCD and VPD.
- There is no `ucli% run`, no DUT time advance, no family progress marker, no returned observer log, and no source-bound row. `source_bound_causal.log` is zero bytes; both host-progress samples report `trigger_bytes=0 public_bytes=0`.

## Waveform, portable evidence, and signal-level result

- mandatory raw-waveform inspection:
  - path: `outputs/conv_native_four_lane_0ccae916_p43_return_analysis/waveform_inspection.json`
  - bytes: `459`
  - SHA-256: `476b4ec03a9a4fc9b7ffe1b8a308dc7ca37e82599fb1b61bdf447e50a1095d0b`
  - PASS; one returned VPD, all matching shards collected, no size cap.
- safe raw-waveform extraction receipt:
  - path: `outputs/conv_native_four_lane_0ccae916_p43_return_analysis/waveform_extraction_receipt.json`
  - bytes: `685`
  - SHA-256: `51f96477c0a3874e25d0949c4c55b71d433919958dd75e299321c30736e7e1ce`
  - PASS.
- extracted authoritative raw VPD:
  - path: `outputs/conv_native_four_lane_0ccae916_p43_return_analysis/extracted/waveforms/run/sim_results/wave.vpd`
  - bytes: `8013479`
  - SHA-256: `14a9fff608356d18386bccf29bfec86f48e2809daa9baf2e8cd344a19f60ed2e`
  - completeness: `PARTIAL`, consistent with the time-0 abort.
- direct `wave.vcd`: absent; runtime status is `FAILED`.
- source-bound query catalog: nine exact MSE4 candidates are statically bound, including the two two-bit valid/ready vectors.
- dynamic query result: expected 9, covered 0, missing 9, events 0, end states 0, `flush_complete=false`, completeness `PARTIAL`.
- portable first-fresh status: `pass=false`, `DIAGNOSTIC_EVIDENCE_INCOMPLETE`; raw VPD and compile/sim/signal/core return were correctly preserved.
- same-attempt execution/attempt/profile/source identities are internally consistent, but the required portable payload is absent/incomplete.
- Portable evidence does **not** close the prior observer/local-decoder gap, and it provides no signal-level MSE4 transition from which a DUT causal divergence can be inferred.

## Causal adjudication

- `LAST_PROVEN_GOOD`: the exact p43 source identity passed production compile; production VCS launched, accepted the authoritative VPD destination and full depth-0 `tb_NDP_Top_new_phy` dump setup, and returned the identity-valid, unbounded partial raw VPD.
- `FIRST_DIVERGENCE`: at Tcl line 3 and simulation time 0 ps, production VCS rejected the shared direct-VCD command `dump -file .../wave.vcd -type VCD`; the later `run` command was never executed.
- execution root classification: `SHARED_PORTABLE_METHOD_RUNTIME_ESCAPE`.
- diagnostic state: `DIAGNOSTIC_EVIDENCE_INCOMPLETE`.
- root scope: shared portable waveform runtime method and its production capability assumption; not config, numeric, workload, golden, functional RTL, or the frozen MSE4 target diagnostic.
- retained MSE4 root classification: `UNRESOLVED_NO_DUT_TIME_OR_CAUSAL_ROWS`.
- natural terminal: false.
- formal D: false.
- E3: false.
- E4: false.
- E5: false.

## Successor and terminal state

- A fresh family successor is technically justified only after the shared portable runtime method is corrected, because p43 never advanced DUT time and cannot close the retained target.
- The current mainline dispatch explicitly assigns that correction to the optimizer/shared-method owner and forbids family-local shared-tool patching.
- No successor was built, staged, or rotated.
- p43 remains unchanged in pending; the formal return remains unchanged at the supplied Downloads path.
- config, numeric, workload, golden, functional RTL, the p42 vector-handshake correction, and the MSE4 wdata/slice-finish target remain frozen.
- terminal state for this family turn: `HOLD_FRESH_SUCCESSOR_PENDING_CURRENT_DISK_PORTABLE_METHOD_RUNTIME_FIX_READY`.
- next action after exact activation: reread the corrected current-disk portable rule/tool/dispatch/gates and build the narrowest fresh p43-equivalent identity, changing only shared-method-compatible waveform/runtime-return surfaces.

## Claim boundary

This record claims exact p43 return/source identity, production compile success, the time-0 shared portable-method runtime escape, raw partial VPD transport integrity, missing direct VCD, and zero/incomplete registered query evidence. It does not claim DUT simulation success, MSE4 signal causality, natural terminal, formal D, E3/E4/E5, numeric correctness, performance, or an RTL root cause.

Final status: `RETURN_ANALYSIS_COMPLETE / SHARED_PORTABLE_METHOD_RUNTIME_ESCAPE / DIAGNOSTIC_EVIDENCE_INCOMPLETE / HOLD_FRESH_SUCCESSOR_PENDING_CURRENT_DISK_PORTABLE_METHOD_RUNTIME_FIX_READY`.
