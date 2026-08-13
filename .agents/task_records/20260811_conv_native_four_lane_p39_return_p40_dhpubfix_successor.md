# 2026-08-11 native Conv p39 formal return to p40 Datahub public-surface successor

## Ownership and current snapshot

- Role: `family.conv.native`.
- Active owner thread: `019ff02d-974d-7c72-a4d5-de8dbf4ae60c`; owner epoch `2`.
- Current mainline: `019ff027-e7db-72a3-b282-cfad8708da05`; mainline owner epoch `2`.
- Current registry epoch consumed: `6`.
- Owner registry snapshot: `contracts/current_session_owner_registry_v1.json`, bytes `12822`, SHA256 `85686959a2af610606da821c0353751fcaf96f86366a42b4c7c09e7b870335ad`.
- Active rule registry: `contracts/active_rule_registry_v1.json`, bytes `9942`, SHA256 `f02e208ddb484803f943fdd8ae9f73cc30c417e10347bf5efd8ddf90aa281518`.
- `conflicts=[]`.

This is the family-owner return-analysis and successor-publication receipt. Registry and plan publication remain `mainline.control` actions.

## Required progress/purpose statement

- Previous-version progress: p38 reached the actual production compile stage and exited `2`, but its bootstrap return did not contain the actual compile argv, package-source identity, bounded compile log or reliable first-error core, so p38 could not localize the compile failure and never started DUT simulation.
- Current-return purpose: p39 changed only runner/return evidence plumbing so that a compile exit would return the actual compile argv/source identity, bounded log head/tail, exit and first-error evidence needed to identify the p38 production compile root cause.
- Fresh-successor purpose: p40 replaces the p39 package-local observer's unresolvable private Datahub arbitration XMR with module-surface valid/rwflag/ready observations, fixes structured first-error selection, and re-tests production compile before resuming the retained MSE4 causal objective.

## Exact p39 formal return and integrity

- Formal return: `C:/Users/15383/Downloads/r5_n4_0cc_p39_compilecore_r1786447845737357042_1115149_return.zip`, bytes `12228`, SHA256 `7fee000c0707d94aaad7494ab34120628165b0b09abade707df1c618127f9e45`.
- Execution identity: `r1786447845737357042_1115149`.
- Bound source package: `artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p39_compilecore/r5_n4_0cc_p39_compilecore.zip`, bytes `5973514`, SHA256 `d99d078a53ec88f5dc0374f0b080350d2e62a6e2121237f7da4dbce9a6c6b515`.
- Machine analysis: `outputs/conv_native_four_lane_0ccae916_p39_return_analysis/report.json`, bytes `5855`, SHA256 `a8c481119170e10eb0bd745e0fda958f0c2b644ef2b264c893046c8ea9029fc4`; `valid=true`, status `P39_VALID_COMPILE_CORE_RETURN_PACKAGE_LOCAL_OBSERVER_XMRE_ROOT_CAUSE`.
- Return CRC, single-root/path safety, duplicate/special-member rejection, exact allowlist, manifest per-member receipts, source ZIP exact-set/per-file manifest and actual package-source binding all pass.
- The actual production argv is `timeout --foreground --signal=TERM --kill-after=30s 2h make -f Makefile.tb_NDP_Top_new_phy compile DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0 RUN_DIR=<p39 a0 compile> VCS_EXTRA_OPTS=<native observer define, package tb_probe include and exact source_bound_causal_observer.svh>` with `cwd=/home/panqs/ndp/NDP_copy02`; no shell pipeline and all waveform switches are disabled.

## Production compile exit=2 root cause

- Last proven good: exact p39 source/execution binding entered the actual production `make ... compile`; bootstrap compile-core preserved argv, source identity, exit and bounded log evidence.
- First divergence: VCS reports exactly two `Error-[XMRE] Cross-module reference resolution error` diagnostics in package-local `tb_probe/native_return_observer.svh`.
- Exact sites:
  - line `2462`, channel `8`, unresolved token `arb_req_ready` from private path `local_req_full_channels[8].wr_en.u_local_req_full_channel.arb_req_ready[0]`;
  - line `2467`, channel `9`, unresolved token `arb_req_ready` from private path `local_req_full_channels[9].wr_en.u_local_req_full_channel.arb_req_ready[0]`.
- VCS terminates with `7 warnings`, `2 errors`; make terminates at `Makefile.tb_NDP_Top_new_phy:306: compile` with `Error 255`; runner returns `2`, signal `NONE`.
- The p39 first-error file itself selected an earlier Ubuntu platform warning because its regex matched a prose sentence containing `error`; the bounded tail nevertheless contains both complete XMRE diagnostics. This collector defect is also repaired in p40.
- Classification: `PACKAGE_LOCAL_OBSERVER_PRIVATE_XMR_ARB_REQ_READY_UNRESOLVED`. Functional RTL, config, numeric and workload are not implicated. DUT simulation did not start, so there is no c0 finish, 27/27 terminal, formal 320D, mismatch-zero, E3/E4/E5, waveform or performance result.

## p40 exact successor publication

- Package: `r5_n4_0cc_p40_dhpubfix`.
- Exact pickup ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p40_dhpubfix.zip`, bytes `5973269`, SHA256 `64c47086bcc1e9dade1b1c9e9fb912c186f49a0ab223c816996e08e9ad86b39f`.
- Status: `PACKAGE_READY_NOT_RUN`; `candidate_release=false`.
- Final exact-ZIP audit: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p40_dhpubfix/r5_n4_0cc_p40_dhpubfix.final_zip_audit.json`, bytes `4385`, SHA256 `c63ab5f2daab98bf7adf9e05812bf5341dc7681b13f02047fd8a92b6af98c196`; `valid=true`, `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`.
- First-fresh exact-ZIP validation: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p40_dhpubfix/r5_n4_0cc_p40_dhpubfix.first_fresh_validation.json`, bytes `2445`, SHA256 `ed0588fb701cdff2c997ddf84477d1ca80c0928f71de66764ec60fe3f7634112`; `pass=true`, `errors=[]`, `upload_authorized=true`.
- Shared aggregate profile: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p40_dhpubfix/r5_n4_0cc_p40_dhpubfix.build_profile.json`, bytes `20403`, SHA256 `a9690026389db65b3f3f2f3569933d092792b8a200b33e069bc85d42febf8aee`; contract valid, errors `0`, one top-level prebuild aggregate.

## Permitted observer/collector delta and frozen surface

- The p40 observer replaces channel 8/9 write selection with `datahub_top.local_channel2hub_req_valid && local_channel2hub_req_rwflag`, and acceptance with selected write grant plus `datahub_top.local_channel2hub_req_ready`.
- The private `arb_req_ready[0]` token is absent from the exact p40 observer. The inherited `observer_binding` is refreshed to the actual p40 member and production compile reuse is explicitly disabled until a p40 formal return.
- The compile first-error selector now prefers structured compiler headers such as `Error-[XMRE]` and rejects the p39 platform-warning false positive.
- Exact public-surface/collector positive and negative controls: `r5_n4_0cc_p40_dhpubfix.observer_public_surface.json`, bytes `1880`, SHA256 `e783e0aa6d5de1f0a9185e492fb7421ca772f3d45e576f6f7b4a5885b66fc3c4`; pass, including legacy-private-XMR and missing-ready negative controls.
- Frozen without exception: config, numeric semantics, workload, golden data and functional RTL. All 87 install payload members are byte-identical to p39; both SCA files are identity-normalized equal; `functional_rtl_modified=false`.
- No file under `rtl/`, no operator config, numeric contract or workload payload was changed.

## Closed gates

- Runner definition-before-use / unsafe expansion: `r5_n4_0cc_p40_dhpubfix.runner_return_resilience.json`, bytes `1619`, SHA256 `f6035a1c354675399a08fb4aff74e2171220429e0cacf2fa76b030e92cdc3112`; pass.
- Typed-v2 source-bound exact-ZIP gate: `r5_n4_0cc_p40_dhpubfix.source_bound_final_zip.json`, bytes `120311`, SHA256 `6d305abb5218b85b09189b0d4d83061d815d6934f2b72f60c23665a29034aba5`; pass with semantic controls.
- Independent post-sim core: `r5_n4_0cc_p40_dhpubfix.post_sim.json`, bytes `3025`, SHA256 `1577331e00ac3505ef00971cf5eeedebc79f507accd12e01e24969406fc7a64d`; pass.
- Compile-core, bounded first-error and waveform exclusion harness: `r5_n4_0cc_p40_dhpubfix.compile_core_harness.json`, bytes `2375`, SHA256 `94601a4f63c45f3c844b04f820f9f851944ccb61fdf4fe052f1cb1ce77d98bce`; pass.
- Normal/preflight-fail/compile-fail/HUP/INT/TERM six-state runner harness: `r5_n4_0cc_p40_dhpubfix.runner_harness.json`, bytes `9603`, SHA256 `234394d6bdcf6a1185e4827b4f72f6f451591d9ee5c7c4f44b5b9593545e4642`; pass.
- Shared install/runtime layout: `r5_n4_0cc_p40_dhpubfix.shared_layout.json`, bytes `25988`, SHA256 `307b92ba51afd6403fb8ef3497a0360f551d7344b198f53069e3aade21cff982`; pass.
- A pre-final local candidate exposed a stale inherited observer-binding receipt and was withheld before storage publication. The single aggregate correction refreshed that binding. The final immutable ZIP above was not changed during its final/first-fresh audits.
- The first-fresh parent process later timed out after the six-state harness had already written a complete PASS report; the same invocation was resumed from that completed report. A contract-adapter schema error (`bytes` was invalid on evidence rows and one evidence-kind string differed) was corrected without changing the exact p40 ZIP or any underlying PASS evidence. Final validation has `errors=[]`.

## Storage receipt

- Storage index: `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`, bytes `387883`, SHA256 `58f7a46b97bf7f0b75a92f8eaa495a00625caa985cd6d53a02c28b2fc9a03700`; global storage audit exit `0`, `pass=true`.
- p39 disposition: `tested`, bound to the formal compile-core return analysis and package-local XMRE classification.
- p40 disposition: `pending`, the sole `conv_native_four_lane` pending package.

## Unique command and expected formal return

- The unique authorized package command, only if mainline later grants a server lease, is `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`.
- Expected return: `/home/panqs/ndp/simresult/r5_n4_0cc_p40_dhpubfix_r<epoch-ns>_<pid>_return.zip` plus its adjacent `.sha256` sidecar.
- No upload, server command, lease acquisition, remote filesystem action, production compile or DUT simulation was performed in this round.

## Claim boundary and mainline action

`PACKAGE_READY_NOT_RUN` proves only the local immutable p40 package and its recorded exact-ZIP, first-fresh, public-surface, runner, aggregate, source-bound, post-sim, compile-core/waveform and storage gates. It does not prove that p40 compiles on the production server and does not claim any DUT result. A formal p40 return must first prove production compile; only then may the retained MSE4 causal workflow advance.

Current mainline should consume this record and update `contracts/current_session_owner_registry_v1.json` plus `.agents/plan.md` so the native-family pointer moves from p39 to p40. No public rule change is proposed.
