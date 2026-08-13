# family.conv.native p43 portable VCD/query successor

Date: 2026-08-12 (Asia/Shanghai)

## Ownership and dispatch

- role_id: `family.conv.native`
- owner: `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`
- owner_epoch: `2`
- registry_epoch: `6`
- current mainline: `019ff027-e7db-72a3-b282-cfad8708da05`
- activated rule: `CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001`
- rule-change epoch: `waveform-portable-local-decodability-v1-b0a94cf60d6e`
- dispatch: `CURRENT_DISK_PORTABLE_VCD_QUERY_METHOD_ACTIVATED / EXACT_FRESH_BUILD_DISPATCH`
- server action: none; no upload, run, lease, or server connection occurred.

## Previous-version progress and current-version purpose

Previous-version progress: p41 proved production compile beyond the Datahub public-surface repair. p42 corrected the package-local two-bit valid/ready scalar-comparison false negative while retaining the MSE4 wdata/slice-finish causal target.

Current-version purpose: build a fresh p42-equivalent portable successor so the corrected vector-handshake diagnostic is locally decodable in the next formal return. The successor retains authoritative raw VPD and adds direct unbounded VCD plus a registered complete source-bound query/event receipt from the same original simulation attempt.

## Fresh identity and frozen surface

- source identity: `r5_n4_0cc_p42_vecjoinfix`
- fresh identity: `r5_n4_0cc_p43_portablevq`
- source p42 ZIP:
  - bytes: `5987936`
  - SHA-256: `e742737932de3158a2bb2905a2e56f7c260e170289d4e9484cde545108c23e55`
- build receipt proves:
  - config/numeric/workload/golden/functional RTL are frozen;
  - workload identity-normalized byte equality is true for all 89 protected members;
  - all protected p42 observer/parser/diagnostic members are identity-normalized equal;
  - the p42 vector-handshake predicate and MSE4 target diagnostic are unchanged;
  - functional RTL modified: false;
  - target diagnostic modified: false.

Only fresh identity plus portable waveform/query/runtime-return surfaces changed.

## Portable runtime contract

- authoritative waveform remains enabled with `DUMP_VCD=1`, `DUMP_FSDB=0`, and `TB_DUMP_FSDB=0`;
- direct portable waveform is enabled independently with `DUMP_PORTABLE_VCD=1`;
- both raw VPD and direct VCD are generated in the same original simulation attempt;
- exact dump scope is `tb_NDP_Top_new_phy`, depth `0`, complete hierarchy and aggregates;
- raw VPD and VCD collection is unbounded: no byte, file, event, time-window, truncation, sampling, or size-deletion cap;
- actual compile argv/source identity, actual sim argv, exact dump Tcl, attempt/execution identity, scope/depth/timescale, raw receipt, VCD identity/header/catalog/completeness, query profile/source report/candidate set/instance/width, contiguous event sequence, all ordered 0/1/X/Z transitions, end states, and allowlist are bound;
- the exact ordered query candidate set contains nine retained MSE4 causal signals, including the two-bit `mse4_wdata_valid` and `mse4_wdata_ready` vectors;
- any VCD or query failure preserves raw VPD and compile/sim/signal/core return and sets `DIAGNOSTIC_EVIDENCE_INCOMPLETE`;
- compile-not-started continues to preserve compile-core evidence without fabricating a simulation-started waveform obligation.

The family adapter is `tools/conv_native_portable_vcd_query.py`. It uses the activated shared portable method and tightens the family first-fresh runtime status so both direct VCD and registered query completion are required.

## Build and gate results

- builder: `tools/build_conv_native_four_lane_0ccae916_p43_portablevq_package.py`
- finalizer: `tools/finalize_conv_native_four_lane_0ccae916_p43_portablevq_package.py`
- deterministic double build: PASS.
- one exact final ZIP: PASS.
- one top-level shared prebuild aggregate invocation: PASS.
- runner definition-before-use and return resilience: PASS.
- bootstrap-safe actual compile argv/source/bounded head-tail/first-error core return: PASS.
- Datahub public-surface/XMR gate: PASS.
- p42 vector-join predicate freeze gate: PASS.
- typed source-bound exact-generation gate: PASS.
- post-sim return-core gate: PASS.
- mandatory raw VPD gate: PASS.
- portable VCD/query exact-ZIP gate: PASS.
- shared runtime-layout/path-budget gate: PASS.
- six-exit runner harness: PASS for normal, preflight failure, compile failure, HUP, INT, and TERM; every scenario reaches the finalizer and publishes the fixed return.
- portable positive runtime fixture: PASS with 9 exact candidates, 27 events, contiguous sequence, complete status, and preserved X/Z transitions.
- portable negative runtime fixture: PASS; a missing candidate produces `DIAGNOSTIC_EVIDENCE_INCOMPLETE` while preserving return publication.
- new-epoch first-fresh audit: independent PASS with `upload_authorized=true`, zero errors, and exact epoch `waveform-portable-local-decodability-v1-b0a94cf60d6e`.
- unit tests: 14 PASS for the family adapter and shared portable-query method.
- Python syntax compilation: PASS for all p43 builder/finalizer/validator/runtime tools.

Recoverably preserved failed local build/audit evidence:

- `outputs/conv_native_four_lane_0ccae916_p43_portablevq_failed_frozen_attempt1/`
- `outputs/conv_native_four_lane_0ccae916_p43_portablevq_failed_adapter_identity_attempt2/`
- `outputs/conv_native_four_lane_0ccae916_p43_portablevq_failed_postsim_name_attempt3/`
- `outputs/conv_native_four_lane_0ccae916_p43_portablevq_failed_layout_attempt4/`
- `outputs/conv_native_four_lane_0ccae916_p43_portablevq_failed_schema_attempt5/`
- `outputs/conv_native_four_lane_0ccae916_p43_portablevq/first_fresh_audit_failed_receipt_attempt1/`

## Exact release receipts

Pending ZIP:

- path: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p43_portablevq.zip`
- bytes: `6016442`
- SHA-256: `657767774ef6762f4e93c3c0b23da71895c7ec699837ca443b0210457d55c11c`

Final ZIP audit:

- path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p43_portablevq/r5_n4_0cc_p43_portablevq.final_zip_audit.json`
- bytes: `6211`
- SHA-256: `7b1f3e2712bc79276eabf169a45d0aba7bfc502127d26459155c34a3cf7c24c8`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `status=PACKAGE_READY_NOT_RUN`
- errors: `[]`

First-fresh validation:

- path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p43_portablevq/r5_n4_0cc_p43_portablevq.first_fresh_validation.json`
- bytes: `2460`
- SHA-256: `9dc56d787bdbced4957688c2e4e09a86fc36bcd1f7d0443138c805be6a9a4d06`
- `pass=true`, `upload_authorized=true`, errors `[]`.

Build receipt:

- path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p43_portablevq/r5_n4_0cc_p43_portablevq.build.json`
- bytes: `2726`
- SHA-256: `e75ad08c581e014f6aac90e979c4713ee0bc882bf18412727cc4f1531f325760`

Portable-query static receipt:

- path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p43_portablevq/r5_n4_0cc_p43_portablevq.portable_query.json`
- bytes: `598`
- SHA-256: `e0bb4c057e0391d0e5c3e0048a155495837016333537cabda85206361ca28c86`

Portable positive/negative runtime fixture:

- path: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p43_portablevq/r5_n4_0cc_p43_portablevq.portable_runtime_fixture.json`
- bytes: `1631`
- SHA-256: `d0dfeb8abae5e951770ad4c19854b999dbb688cb2f809dc32f7cf24109e0160b`

## Storage rotation

`manage_server_test_package_storage.py rotate` atomically moved the unrun p42 package and its receipts to `superseded/conv_native_four_lane/r5_n4_0cc_p42_vecjoinfix/` and published p43 to the flat pending pickup directory. No bare pending-directory mutation was used.

An independent `manage_server_test_package_storage.py audit` after rotation reports:

- pass: `true`
- pending count: `3`
- tested count: `116`
- superseded count: `46`
- `pending_by_family.conv_native_four_lane = ["r5_n4_0cc_p43_portablevq"]`

Storage index:

- path: `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`
- bytes: `439688`
- SHA-256: `aa86481da1212bbfa4539db154f2a2aafc2ea1c54465ffa7ed586578cf87cfd9`

## Only future server command and expected formal return

This record does not authorize a server action. If separately authorized later, the only package command is:

`bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`

Expected formal return identities:

- `/home/panqs/ndp/simresult/r5_n4_0cc_p43_portablevq_r<epoch-ns>_<pid>_return.zip`
- `/home/panqs/ndp/simresult/r5_n4_0cc_p43_portablevq_r<epoch-ns>_<pid>_return.zip.sha256`

## Claim boundary and status

This closes only local construction, deterministic packaging, synthetic runtime plumbing, exact-ZIP gates, first-fresh audit, and storage publication. It does not claim a p43 production compile result, DUT simulation result, waveform contents from a real VCS run, MSE4 causal localization, natural terminal, formal D/E3/E4/E5, upload, lease, or server execution.

Final status: `PACKAGE_READY_NOT_RUN`.
