# Conv/SA node0004 v20 return adjudication and v21 Buffer-AG keep fix

## Scope and immutable boundaries

- Mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`.
- `numeric_analysis_repeated=false`.
- `node0004_workload_rebuilt=false`.
- Frozen W3/matrix payloads were consumed read-only.
- No `.agents/plan.md`, public rule, functional RTL, or other operator-family
  asset was modified.
- No server inspection, upload, lease, or execution was performed.

## Active post-generation receipts

The following files were read completely after the final v21 ZIP was built:

- `.agents/rules/生成前必读索引.md`
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/服务器测试包生成规则.md`
  `88fcc7e87da9d92d281b8096389e31f1735b0e99ce3b13dd37635a8b96c0a7c6`
- `.agents/rules/INT8_SA点积专项规则.md`
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

Applied server-package rule IDs include:

- `CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001`
- `CDA-SERVER-LONG-RUN-PROGRESS-LOCALIZATION-001`
- `CDA-SERVER-OBSERVER-BINDING-FOUR-WAY-001`
- `CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001`
- `CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001`
- `CDA-SERVER-DEFAULT-PROGRESS-DIAGNOSTICS-001`
- `CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001`
- `CDA-SERVER-STRICT-LOCAL-AUDIT-MINIMAL-RUNTIME-PREFLIGHT-001`
- `CDA-SERVER-RUNNER-PREFLIGHT-TO-COMPILE-POSITIVE-CONTROL-001`
- `CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`
- `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`

## RETURN_ANALYSIS

Input return:

- disk path:
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_n4_hw_v20_buffer_mode_fix_return(1).zip`
- bytes: `77744`
- SHA256:
  `b8a1ac0a9f7c9d705b21f332b010a3eaa59d131f85fd1eae524a2d2f26b57b55`
- `(1)` is only a local download collision suffix.
- An adjacent sidecar is absent. Under
  `CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`, this is
  content-neutral and not a blocker. The return ZIP SHA was recomputed
  locally; internal identity, exact-set, allowlist, and source binding were
  still required.

Bound source:

- `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v20_buffer_mode_fix.zip`
- bytes: `5819495`
- SHA256:
  `e67775aed87d2065f51190049a9a7ba05fb98de9ba08a4362901612248f92ead`

Return gates:

- CRC/path/single root: PASS.
- Internal `RETURN_ALLOWLIST.json`: 13 records, all hashes and sizes match.
- Exact returned file set: 14 files including the allowlist, PASS.
- Package preflight: PASS.
- Installed preflight: PASS; runtime D initially absent.
- Observer precompile/SHA/XMR identity: PASS.
- Compile exit: `0`.
- Run invocation exit: `0`.
- Signal: `NONE`.
- Observer enabled at time zero: PASS.
- Natural terminal: false.
- Formal D: 0 of expected 320 items; missing 320, mismatch 0.
- `mismatch=0` with all 320 missing is not a pass.
- E3=false, E4=false, E5=false.

Machine report:

- `contracts/operator_config/node0004_v20_return_analysis_v1.json`
- SHA256:
  `6c6393c3d371beafaf83a4158e5aa18a91797735a070784a9d9f9569206c37f5`
- Analyzer:
  `tools/analyze_node0004_v20_return.py`
- analyzer SHA256:
  `856f916dde79154b447140e32d8e7f3b8484e851bd710af8e591c327a21fb80d`
- analyzer exit code: `0`.

## FIRST_DIVERGENCE and HANG_ROOT_CAUSE

Last good boundary:

- each stream enqueued and dequeued the first row's two Buffer-AG COL
  addresses;
- Buffer0 produced four accepted SA reads;
- four actual ALU-to-outbuffer write cycles occurred.

First bad boundary:

- after the first buffered COL terminal, no next-row Buffer-AG enqueue was
  generated.

Deterministic root cause:

`BUFFER_AG_ROW_KEEP_THRESHOLD_LT_COL_TERMINAL`.

The active RTL source is:

- `NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv`
- SHA256:
  `bbf2d8542f29229953395edf28d9a9cfe48030419753ee52bc62cc09e6028e4d`
- relevant lines: 149-152.

For ROW keep mode, the RTL releases the held ROW at the buffered COL terminal
only when:

`buffered_col_last_index <= row_keep_last_index`.

The frozen v20 config had five violations:

| stream | COL last | ROW keep threshold | release |
| --- | ---: | ---: | --- |
| 0 | 5 | 4 | false |
| 1 | 5 | 4 | false |
| 2 | 5 | 4 | false |
| 3 | 4 | 3 | false |
| 4 | 5 | 4 | false |

Dynamic evidence matches exactly:

- `BUFFER0_FLOW_BOUNDARY_V1`: `ag_enq=2`, `ag_deq=2`,
  `ag_empty=1`, `arm_req_accept=4`.
- `A_REUSE_BOUNDARY_V1`: `buf_read0=4`, `array_clear0=1`,
  `alu2ob_cycles=4`.
- `ABPE_BOUNDARY_V1`: downstream output never completed because only the
  first accumulation row was supplied.

Therefore the canonical observer label
`BUFFER4_READ_WITNESS_TO_BUFFER5_WRITE_WITNESS` is a downstream coarse
boundary, not the earliest causal boundary. The v20 Buffer0 mode fix itself
worked for the first row and is retained.

## Minimal configuration fix and local rebuild

Only these five typed-materializer leaves changed:

- stream0 `[0]`: `4 -> 5`
- stream1 `[0]`: `4 -> 5`
- stream2 `[0]`: `4 -> 5`
- stream3 `[0]`: `3 -> 4`
- stream4 `[0]`: `4 -> 5`

Required formula:

`stream_engine.streamN.buf_idx_keep_last_index[0] =
buffer_loop_configs.GROUPN.COL_LC.last_index`.

Fresh local assets:

- config:
  `configs/native_ndp_sim/node0004_bufkeep_fix_c0_v4/accumulate_waves/wave-0.json`
- config SHA256:
  `3f39ac9baccce2d7052420636eda69ae3c0e7d59f53f245f9c02e89e32a4c6d2`
- rebuild report:
  `artifacts/operator_config_validation/r5-node0004-bufkeep-fix-c0-v4/local_rebuild_report.json`
- rebuild report SHA256:
  `6497ff04bc5ffa39e1494ea8b039df01af5060846e74da69a480dff7ac2beea5`
- mapping validation SHA256:
  `85ba59363980afe5736dd19ccac52b65a966c107bf6fd2404286e810099d768a`
- 128-bit bitstream SHA256:
  `6996170d1c1c3c6b02b9a1980c612c2b207255f2bb1f7fe5e202709acf3ea55b`
- execplan SHA256:
  `dafcaada34fc48785ea6c9b8e8a224da36dca35e7ee44bdb8e745e337a817934`
- SCA SHA256:
  `4d0f27f395cf79340ea7c641d6f77185600a5a53e4ece4be128263e68cc59c22`

Contract test:

`.\.venv\Scripts\python.exe -m unittest tests.test_conv_sa_hardware_contract`

- exit code: `0`
- result: 4 tests PASS.
- includes a negative control that decrements one ROW keep threshold and
  requires fail-closed.

## PACKAGE_RELEASE

Unique successor:

- status: `PACKAGE_READY_NOT_RUN`
- classification: `CONFIG_FUNCTIONAL_FIX_WITH_PROGRESS_DIAGNOSTICS`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v21_bufkeep_fix.zip`
- bytes: `5819202`
- ZIP SHA256:
  `bd9fadb9bdd18c1678461ae055fea7e15be5d414957b76de48f761833e345131`
- sidecar:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v21_bufkeep_fix.zip.sha256`
- sidecar SHA256:
  `b2153e5bac25f7e964570be37093713c8e924a185249075ea7f76e13b136917a`
- server command:
  `bash r5_n4_hw_v21_bufkeep_fix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- expected return:
  `r5_n4_hw_v21_bufkeep_fix_return.zip`
- the server runner also creates
  `r5_n4_hw_v21_bufkeep_fix_return.zip.sha256`, but the user need not upload
  that sidecar under the current transport policy.

Runner positive control:

- command:
  `.\.venv\Scripts\python.exe tools\validate_node0004_v16_runner_positive_control.py --zip artifacts\operator_config_validation\r5-server-test-packages\r5_n4_hw_v21_bufkeep_fix.zip --sidecar artifacts\operator_config_validation\r5-server-test-packages\r5_n4_hw_v21_bufkeep_fix.zip.sha256 --bash "C:\Program Files\Git\bin\bash.exe" --python .venv\Scripts\python.exe --output artifacts\operator_config_validation\r5-server-test-packages\r5_n4_hw_v21_bufkeep_fix.runner_positive_control.json`
- validator exit code: `0`.
- safe compile stub expected/observed exit: `73/73`.
- compile stub invocation count: `1`.
- wrong observer identity negative exit: `5`, compile invocation count `0`.
- report SHA256:
  `7a58bc53f6f9fd09607f9c81813b8d71c645e1cac2c2d51298d4a2ce8530fe64`

Final ZIP self-audit:

- validator:
  `tools/validate_node0004_v21_final_zip.py`
- validator SHA256:
  `0e3a4a9ede035859f853bc01dbbe8012f5426d50f9d9dcc6e1413b45228a6f10`
- validator exit code: `0`.
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`.
- `errors=0`.
- report:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v21_bufkeep_fix.final_zip_rule_self_audit.json`
- report SHA256:
  `879ecaa8c7b6efbcebda0fa7598abe55163cf68fbd7e5beb693339894141f297`

Additional negative controls, all expected/observed exit `1/1`:

- missing one keep-threshold leaf;
- wrong keep-release formula;
- configuration rebuild not declared;
- missing current return-transport rule;
- wrong bitstream payload;
- missing runner positive control.

## BLOCKER_DELTA

Closed:

- v19 Buffer0 mode/lifetime mismatch;
- external return sidecar absence as a transport blocker;
- v20 Buffer-AG ROW keep threshold configuration error, locally fixed in v21.

Still open:

- v21 has not been run on the server;
- no natural terminal and no 320-item exact formal D readback exist for v21;
- consequently E3/E4/E5 remain open until the v21 return is analyzed.

## RULE_DELTA_PROPOSAL

`NONE`.
