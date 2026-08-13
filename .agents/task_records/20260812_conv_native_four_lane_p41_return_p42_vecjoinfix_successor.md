# Native Conv p41 formal-return analysis and p42 vector-join successor

Date: 2026-08-12 (Asia/Shanghai)

## Ownership and dispatch

- `role_id`: `family.conv.native`
- `owner_thread_id`: `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`
- `owner_epoch`: `2`
- `registry_epoch`: `6`
- `current_mainline_role_id`: `mainline.control`
- `current_mainline_thread_id`: `019ff027-e7db-72a3-b282-cfad8708da05`
- current owner registry at completion:
  - path: `contracts/current_session_owner_registry_v1.json`
  - bytes: `13461`
  - SHA-256: `a0cc7aaef89829a33da8fa7125911c84f0725b9bc6ccf4e3357828bc96ef4797`
- No `.agents/plan.md`, public rule, active-rule registry, owner registry, config, numeric, workload, golden, or functional RTL file was modified.
- No upload, lease, server run, or other server action was performed.

## Required progress/purpose statement

Previous-version progress: p39 localized production compile exit `2` to the two package-local observer `arb_req_ready` XMR sites. p40 repaired the Datahub public surface and structured first-error return but was withdrawn because it used the old `DUMP_VCD=0` semantics. p41 preserved those repairs and added mandatory full-hierarchy, unbounded VPD return.

Current-return purpose: prove that production compile passes the public-surface repair, validate the mandatory VPD return, and use the returned dynamic evidence to localize the retained MSE4 causal blocker. When p41's source-bound observer was proven defective within package/observer scope, build the narrowest fresh successor without changing the frozen target diagnostic.

## Exact p41 formal return and integrity

- formal return:
  - path: `C:/Users/15383/Downloads/r5_n4_0cc_p41_vpdfull_r1786457691694343631_1196369_return.zip`
  - bytes: `8660560`
  - SHA-256: `d39b21af39c0c79b2b6cfe7e3546f196fd0eb432564555a3f914149eaf00a1fc`
- exact source package, now tested:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p41_vpdfull/r5_n4_0cc_p41_vpdfull.zip`
  - bytes: `5986703`
  - SHA-256: `339d8f4e17cbf34132be9bc84f33dec637ea3fd6ecc8deeec5aa5620a012a95a`
- analyzer report:
  - path: `outputs/conv_native_four_lane_0ccae916_p41_return_analysis/report.json`
  - bytes: `17128`
  - SHA-256: `bbe580a2450c6f3defa379fc7a200a141e35a3d2b5c3a247bbf2de7ab3800f9e`
  - status: `RETURN_ANALYSIS_COMPLETE_PACKAGE_LOCAL_VECTOR_HANDSHAKE_OBSERVER_SUCCESSOR_REQUIRED`
  - `valid=true`, structural/CRC/safe-path/single-root/exact-return-set/source-manifest/source-generation/source-binding checks all passed.

## Dynamic result and localization

- Production compile exit: `0`; p41 therefore proved compile passed the p40 Datahub public-surface repair.
- Simulation started: `true`; run exit `255`, signal `INT`; no natural terminal and no formal D/E3/E4/E5 claim.
- Actual simulation arguments include `DUMP_VCD=1`, `DUMP_FSDB=0`, and `TB_DUMP_FSDB=0`.
- Last proven good: exact p41 compile passed, simulation started with mandatory full-hierarchy VPD, and the native ledger recorded 18 MSE4 descriptors, 18 MSE4 buffer-data accepts, and 18 MSE4 wdata handshakes.
- Source-bound MSE4 join parser recorded descriptor `18`, buffer data `18`, memag output `9`, wdata output `0`, slice finish `0`, then returned `EVIDENCE_INCOMPLETE` because the required wdata and slice-finish summaries were absent.
- Independent `N4D_PROGRESS_V1` ended with `wdata=0,0,0,0,18`; therefore the source-bound zero count was a false negative, not proof that MSE4 produced no wdata.
- First divergence: the generated MSE4 wdata probe observed zero events while the independent native ledger observed 18.
- Root cause: p41's package-local generated observer used `(p_0 === 1'b1) && (p_2 === 1'b1)` for two 2-bit valid/ready vectors. That scalar comparison recognizes only one exact vector value and misses valid same-channel overlaps.
- Required semantics: `(|(valid_vector & ready_vector)) === 1'b1`.
- Functional RTL fix required: `false`.
- The retained MSE4 target is not dynamically closed by p41. `buffer5.blocked_cycles=786432` remains observational context; p42 is required to obtain trustworthy source-bound wdata/slice-finish evidence.

## Waveform return

- return inspection:
  - path: `outputs/conv_native_four_lane_0ccae916_p41_return_analysis/waveform_return_inspection.json`
  - bytes: `441`
  - SHA-256: `0691f5c6ae6927ddd699bb4a07c3b5814cfcb397f606af120e421bb8aa45b999`
  - PASS; one VPD, simulation started, exit kind `INT`.
- safe extraction:
  - path: `outputs/conv_native_four_lane_0ccae916_p41_return_analysis/waveform_extraction.json`
  - bytes: `697`
  - SHA-256: `574db5e39ccb1377faab32ab03e9f4677d2c3fb93a7a16c0eff242022fdc922d`
  - PASS.
- VPD identity:
  - path: `outputs/conv_native_four_lane_0ccae916_p41_return_analysis/waveform_vpd_identity.json`
  - bytes: `1417`
  - SHA-256: `7851a48fa736aaf5d50fe6afcf6a8a8fd576bba0632eaadfcb7f536325891b28`
  - PASS; no local `verdi`, `dve`, or `vpd2vcd` executable was discovered, so no semantic waveform decode is claimed.
- extracted waveform:
  - path: `outputs/conv_native_four_lane_0ccae916_p41_return_analysis/waveform_extract/waveforms/compile/sim_results/wave.vpd`
  - bytes: `8013051`
  - SHA-256: `5b3956119aedb3274c1fd41207de74ad9a0b95678647b958b6063944cf61d07c`
- Runtime receipt proves all matching VPD shards were collected with no size limit. Viewer absence is not an acceptance failure under the current rule; this record makes no waveform-semantic claim.

## Narrow p42 repair

- fresh identity: `r5_n4_0cc_p42_vecjoinfix`
- changed package surfaces only:
  - fresh package identity and storage identity;
  - source-bound canonical predicate operator `BIT_AND_NONZERO`;
  - regenerated package-local observer, binding, parser, and their identity receipts;
  - derived runtime path-budget metadata required by the longer fresh identity.
- frozen exactly/identity-normalized:
  - config, numeric, workload, golden, functional RTL;
  - MSE4 target diagnostic and its candidate/instance scope;
  - p40 Datahub public-surface repair and structured first-error behavior;
  - runner/runtime return behavior;
  - mandatory waveform plan: `DUMP_VCD=1`, `DUMP_FSDB=0`, `TB_DUMP_FSDB=0`, `tb_NDP_Top_new_phy` depth 0 full hierarchy, no exclusions, every `wave.vpd` shard, no size cap, and started-without-wave fail closed.
- shared generator:
  - path: `tools/generate_server_source_bound_observer.py`
  - bytes: `100562`
  - SHA-256: `78050ea4fa150079a7349ddac7c5c8196e163c89703d390f32d30d5d29457d37`
- builder:
  - path: `tools/build_conv_native_four_lane_0ccae916_p42_vecjoinfix_package.py`
  - bytes: `29528`
  - SHA-256: `b912da957b64212d6dbe032479db0bcbb7d49faccf1459cc1e4573a1a2c5cf8b`
- finalizer:
  - path: `tools/finalize_conv_native_four_lane_0ccae916_p42_vecjoinfix_package.py`
  - bytes: `10207`
  - SHA-256: `3967dadc257b6ee5e245330988d1f79af6fae9a29b8b69d4416a57e435a91f12`

Failed prebuild/gate attempts were preserved recoverably under:

- `outputs/conv_native_four_lane_0ccae916_p42_vecjoinfix_failed_prebuild_attempt1/`
- `outputs/conv_native_four_lane_0ccae916_p42_vecjoinfix_failed_prebuild_attempt2/`
- `outputs/conv_native_four_lane_0ccae916_p42_vecjoinfix_failed_six_state_attempt3/`

No evidence was deleted or overwritten.

## Exact p42 gates

- deterministic double-build tree equality: PASS.
- current shared prebuild aggregate: PASS, exactly one top-level invocation, errors `[]`.
- exact final-ZIP safety/CRC/single-root/identity: PASS.
- runner definition-before-use: PASS, unsafe uses `[]`.
- bootstrap-safe compile-core harness: PASS, including actual compile argv, actual package source identity, bounded head/tail/first-error, exact compile-core return, and compile-not-started waveform exemption.
- Datahub public-surface/XMR gate: PASS.
- typed source-bound v2 exact-generation gate: PASS.
- p42 vector-join predicate gate: PASS; both operands are 2-bit and the emitted expression is `((|(p_0 & p_2)) === 1'b1)`.
- post-sim return-core exact-ZIP gate: PASS.
- mandatory waveform exact-ZIP gate: PASS.
- six-state runner harness: PASS for normal, preflight-fail, compile-fail, HUP, INT, and TERM; each reaches the finalizer and publishes the fixed-result return.
- shared runtime layout/path budget: PASS.
- first-fresh disposition: p42 is not the first fresh package after `waveform-mandatory-v2-01ca6d7cd4a4a270`; it exactly reuses the bound p41 first-fresh PASS receipt:
  - path: `outputs/conv_native_four_lane_0ccae916_p41_vpdfull/first_fresh_audit/first_fresh_validation.json`
  - bytes: `2416`
  - SHA-256: `6a806f40667596e205f8da6370db2a9d061e7253b0243023aaca3954b0d01666`
- exact final audit, now stored with pending receipts:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p42_vecjoinfix/r5_n4_0cc_p42_vecjoinfix.final_zip_audit.json`
  - bytes: `5744`
  - SHA-256: `ddbf7bb18a2d265cdb18c49224e1aba49f70e70f75dcee081b175800a7628b14`
  - `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors `[]`.
- relevant shared test suites: 75 tests PASS.

## Storage and ready receipt

- exact pending ZIP:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p42_vecjoinfix.zip`
  - bytes: `5987936`
  - SHA-256: `e742737932de3158a2bb2905a2e56f7c260e170289d4e9484cde545108c23e55`
- build receipt:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p42_vecjoinfix/r5_n4_0cc_p42_vecjoinfix.build.json`
  - bytes: `2517`
  - SHA-256: `38dd3cf4ccb3ea4997409f7a75423a139586b1e3595a5f46b46e831c44f5990c`
- `manage_server_test_package_storage.py rotate` moved p41 to `tested/conv_native_four_lane/...` and published only p42 as the native pending package.
- Final independently rerun global storage audit: PASS.
- Global pending count: `3`; tested count: `116`; superseded count: `45`.
- `pending_by_family.conv_native_four_lane = ["r5_n4_0cc_p42_vecjoinfix"]`.
- storage index:
  - path: `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`
  - bytes: `431989`
  - SHA-256: `732ed4287ea9b33e91b40d4233361e6a4cf82615749aa8a38d9b6efba8dc9989`

Final status: `RETURN_ANALYSIS_COMPLETE` plus `PACKAGE_READY_NOT_RUN`. The p41 compile/public-surface and mandatory-VPD objectives are closed. The retained MSE4 dynamic localization is not yet closed; p42 is the required narrow successor and has not been run.

## Only future server command and expected return

The only authorized future server command is:

`bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`

Expected fixed return templates:

- `/home/panqs/ndp/simresult/r5_n4_0cc_p42_vecjoinfix_r<epoch-ns>_<pid>_return.zip`
- `/home/panqs/ndp/simresult/r5_n4_0cc_p42_vecjoinfix_r<epoch-ns>_<pid>_return.zip.sha256`

No server action is authorized by this receipt itself.

## Claim boundary and mainline action

This record claims exact p41 return integrity, actual production compile success, simulation start, mandatory VPD return integrity, the dynamic package-local observer false negative, local p42 construction, frozen-surface checks, exact final-ZIP gates, bound first-fresh reuse, and clean storage rotation. It does not claim p42 production compile or DUT execution, a decoded VPD semantic conclusion, natural terminal, formal 320/320 D, mismatch zero, E3, E4, E5, performance, or a functional RTL root cause.

Mainline should consume this record and update the plan/registry pointers from p41 to p42 without changing package bytes. The family owner intentionally did not edit plan, rules, or registry.
