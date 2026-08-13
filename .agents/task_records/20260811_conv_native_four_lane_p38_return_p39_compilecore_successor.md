# 2026-08-11 native Conv p38 formal return to p39 compile-core successor

## Ownership and epoch binding

- Role: `family.conv.native`.
- Active owner thread: `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`; owner epoch `2`.
- Current mainline: `019ff027-e7db-72a3-b282-cfad8708da05`; mainline owner epoch `2`.
- Current registry epoch: `6`.
- Registry snapshot consumed before this record: `contracts/current_session_owner_registry_v1.json`, bytes `11867`, SHA256 `28d9137a040b6446db04f5280c7b660ff6b83170bad203dd2c95ca4634c776be`.
- Activated handoff publication: `.agents/task_records/20260811_handoff_conv_native_publication.json`, bytes `1053`, SHA256 `fb6e2866cc6996235d9535af590bb43a06ea39a1a77bf9fd302db321b3ab402c`.
- `conflicts=[]`.

This record is the family-owner publication receipt only. Updating the registry and plan remains a `mainline.control` action.

## Bound p38 formal return

- Formal return: `C:/Users/15383/Downloads/r5_n4_0cc_p38_mse4join_r1786436059412189518_1051036_return.zip`, bytes `2323`, SHA256 `be026648659b6468a6b0121686eb7f55b655b8342c809e05cc767cbde846231c`.
- Execution identity: `r1786436059412189518_1051036`.
- Formal analysis record: `.agents/task_records/20260811_conv_native_four_lane_p38_return_analysis_only.md`, bytes `4328`, SHA256 `7d9c6d7c90dc048a27591f0b947c4f02b1f72f3ad07d8f604ca2bceceff837f4`.
- Machine analysis: `outputs/conv_native_four_lane_0ccae916_p38_return_analysis/report.json`, bytes `9756`, SHA256 `cdf88ab1aca2abb82569c83a8e838d8d54d4a7ae3f0b75a7d82b10cb8f3e4b11`.
- Bound p38 source is now stored at `artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p38_mse4join/r5_n4_0cc_p38_mse4join.zip`, bytes `5970142`, SHA256 `328b7ec7b7034a1a2c202fad38d628199cfbbaa2213196d94daab39c25ff4d22`; exact `package_manifest.json` SHA256 `e871d4e2aef2364a696802f90d2e6cbace644133c33d3f6ec5ad2d4e05b647dd`.
- p38 classification remains `PACKAGE_LOCAL_PRODUCTION_COMPILE_STAGE_FAILURE_OR_LAUNCH_ERROR_WITH_ATTEMPT_EVIDENCE_UNAVAILABLE`: the return records `PRODUCTION_COMPILE` and runner exit `2`, but has no persisted actual compile argv, compile source identity, bounded compile log, first-error core, or simulator invocation. It proves no config, numeric, workload, DUT, functional-RTL, natural-terminal, formal-D, E4 or E5 result.

## p39 package publication

- Package: `r5_n4_0cc_p39_compilecore`.
- Exact pickup ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p39_compilecore.zip`, bytes `5973514`, SHA256 `d99d078a53ec88f5dc0374f0b080350d2e62a6e2121237f7da4dbce9a6c6b515`.
- Status: `PACKAGE_READY_NOT_RUN`; `candidate_release=false`.
- Final exact-ZIP audit: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p39_compilecore/r5_n4_0cc_p39_compilecore.final_zip_audit.json`, bytes `3979`, SHA256 `854e9ac3aa014b213483774a696a30734e536c50fbfa893576535a2274c01395`; `valid=true`, `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`.
- First-fresh exact-ZIP validation: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p39_compilecore/r5_n4_0cc_p39_compilecore.first_fresh_validation.json`, bytes `2455`, SHA256 `47452d8ac97a3293fd6633e32dcbf391d6c798ba1ba43c0d34db16ff984e5a09`; `pass=true`, `errors=[]`, `upload_authorized=true`.
- Build receipt: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p39_compilecore/r5_n4_0cc_p39_compilecore.build.json`, bytes `1603`, SHA256 `070a816f0bacbc667ac42c5723c119fbf22b90e801c44d48e4b3951158fb7a93`.
- Build profile: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p39_compilecore/r5_n4_0cc_p39_compilecore.build_profile.json`, bytes `20308`, SHA256 `9b0f220b4fbd1a767ab34252ab5bd052fbb7ff8ef16ff9e4e97421b6769ec4ad`; the shared cheap-shadow aggregate was invoked exactly once and reports contract valid/errors `0`.

## Closed package-local gates

- Runner definition-before-use / unsafe expansion audit PASS: `r5_n4_0cc_p39_compilecore.runner_return_resilience.json`, bytes `1634`, SHA256 `d1bc602a918032ac173533bde8bf3882829f797ad0e27bbc9780a96a6cc60e43`.
- Typed-v2 source-bound final-ZIP gate PASS: `r5_n4_0cc_p39_compilecore.source_bound_final_zip.json`, bytes `120341`, SHA256 `cc871d45cbd3fe0a672b982408a7e9f1644f0d1fe9a03320f3d0f6978e0022e5`.
- Independent post-sim core gate PASS: `r5_n4_0cc_p39_compilecore.post_sim.json`, bytes `3037`, SHA256 `ce48d0c212ba4377e3f18137fb84b56206b2830f8cef81bc265655e32dbd52df`.
- Compile-core and waveform allowlist harness PASS: `r5_n4_0cc_p39_compilecore.compile_core_harness.json`, bytes `2414`, SHA256 `34b2e986e85fdfc49cc359fdaba7ffedf28ff68726ddbc356ebda9e39fe59749`.
- Normal/preflight-fail/compile-fail/HUP/INT/TERM runner harness PASS: `r5_n4_0cc_p39_compilecore.runner_harness.json`, bytes `9653`, SHA256 `dce1d1cf96bab5eb5c7722c6de5213691d4c9c00b2b0ce5f5a64c5adccae26be`.
- Shared install-only runtime layout PASS: `r5_n4_0cc_p39_compilecore.shared_layout.json`, bytes `26348`, SHA256 `16cc62839b7717526be5da4a6af42103d3455723cb2137691200a08dc9664435`.

The p39 bootstrap compile-failure return retains the actual `compile_argv.json`, `compile_source_identity.json`, `compile_exit.txt`, `compile_log_receipt.json`, bounded `64 KiB` head/tail logs, and a bounded `4 KiB` first-error core. The full compile log and waveforms are excluded from the return. The normal, signal and compile-failure paths share one aggregate/finalizer path, and compile artifacts are bound to the actual selected source identity.

## Frozen surface and permitted delta

- Frozen without exception: config, numeric semantics, workload, golden data and functional RTL.
- All 87 install payload members are byte-identical to p38; both SCA files are identity-normalized equal; `functional_rtl_modified=false`.
- The only p39 changes are the fresh package identity, runner definition-before-use, bootstrap-safe compile-root-cause evidence capture/publisher, and identity-bound derived receipts.
- No pending ZIP was rebuilt, replaced or modified while creating this task record.

## Storage receipt

- Storage index: `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`, bytes `376119`, SHA256 `0ecc36d84e3aa0793eab553c7c1a6077e480b63443ebefe859b89afe292d4604`; global storage audit exit `0`.
- p38 disposition: `tested`, bound to the compile-exit-2 formal return analysis and its missing-root-cause-evidence classification.
- p39 disposition: `pending`, the sole native-four-lane pending package, reason `runner definition-before-use/bootstrap compile-rootcause return`, status `PACKAGE_READY_NOT_RUN`.

## Unique server command and expected return

- The unique authorized package command, if mainline later grants a server lease, is `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`.
- Expected formal return: `/home/panqs/ndp/simresult/r5_n4_0cc_p39_compilecore_r<epoch-ns>_<pid>_return.zip` plus the adjacent `.sha256` sidecar.
- No upload, server command, lease acquisition, remote filesystem action, production compile or DUT simulation was performed in this publication round.

## Claim boundary

`PACKAGE_READY_NOT_RUN` is a package-local publication claim only. It proves exact pending ZIP identity and the recorded local exact-ZIP, first-fresh, source-bound, aggregate, runner, bootstrap compile-core, post-sim and storage gates. It does not claim a server run, production compile result, simulator start, waveform production, c0 slice finish, natural 27/27 terminal, formal 320D, mismatch=0, E3, E4, E5, performance, or a config/numeric/DUT/RTL correction.

`RULE_CONFIRMATION`: the current runner definition-before-use, bootstrap-safe bounded compile-root-cause return, shared aggregate, source-bound, post-sim, waveform-exclusion and first-fresh exact-ZIP rules are satisfied by the exact p39 bytes above. No public rule, registry, plan, config, numeric, workload or RTL file was modified by this task-record publication.
