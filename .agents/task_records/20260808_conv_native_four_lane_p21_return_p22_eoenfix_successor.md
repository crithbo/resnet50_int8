# Conv native-four-lane p21 formal return -> p22 epoch-owner identifier successor

## Scope and immutable identities

- Owner: native-four-lane Conv only; serialized Conv, public rules, plan and functional RTL were not modified.
- Formal return: `C:/Users/15383/Downloads/r5_n4_0cc_p21_epochowner_r1786169058630848787_3994777_return.zip`, bytes `723157`, SHA256 `b40d518f9ba834dfd1452a7c658b498024be7083e25513bbb91a6426d41de7a9`.
- Execution identity: `r1786169058630848787_3994777`.
- Exact p21 source: `r5_n4_0cc_p21_epochowner.zip`, bytes `5876983`, SHA256 `cd78dd1aa2234bc12e4588b957fa900e71030486bd6eca4c315155451f631c8d`.
- p21 source was moved byte-preservingly from pending to `artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p21_epochowner/` only after formal return consumption.

## RETURN_ANALYSIS

Machine report: `outputs/conv_native_four_lane_0ccae916_p21_return_analysis/report_v2.json`, bytes `6508`, SHA256 `601556ae18e4d3cea3ce21a7dee99d7fc00cc29354b13b151fa541b0e9eba1a6`.

- CRC, single-root/path safety, exact RETURN_MANIFEST set, allowlist, returned source manifest, source ZIP manifest, unique per-execution return basename, package/install/observer preflights, path-budget equality, install-only runtime layout and NDP-root direct-child exact-set all pass.
- Production compile was started and exited `2`; run remained sentinel `125`; signal was `NONE`; DUT simulation did not start.
- Exact production frontend failure: `tb_probe/native_return_observer.svh:4640`, `Error-[IND]`, identifier `return_obs_enabled` undeclared, one compile error and no XMRE.
- Exact p21 observer SHA256 is `755ee7da53eb9550afaad604c4da5495cd071b26291ce76eb747d49506b0b527`. It declares and initializes `return_obs_eo_enabled`, while the time-zero feature-marker consumer at line 4640 alone used `return_obs_enabled`. The later task consumer already used `return_obs_eo_enabled`.
- Classification: `PACKAGE_LOCAL_OBSERVER_SCOPE_COMPILE_FAILURE_SIMULATION_NOT_STARTED`.
- Root cause: `PACKAGE_LOCAL_OBSERVER_EPOCH_OWNER_ENABLE_IDENTIFIER_SCOPE_TYPO`; this is a package-local self-audit escape, not DUT/config/RTL/numeric evidence.
- No dynamic epoch-owner ledger or post-PEkeep3 D-flow record exists. c0 slice finish, 27/27 natural terminal, formal 320D, mismatch zero, E3, E4, E5 and performance all remain false/unproven.

LPG: all fallible package/runtime preflights and production RTL parsing reached the exact package-local observer.

FD: the p21 epoch-owner time-zero feature marker before simulation.

## p22 continuous-closure successor

Package identity: `r5_n4_0cc_p22_eoenfix`.

Only semantic fix: one exact package-local token at the time-zero consumer, `return_obs_enabled` -> `return_obs_eo_enabled`. Package identity/runtime paths and manifests were mechanically rebound. No observer predicate, DUT hierarchy reference, runner control-flow semantics, workload, config, mapping, bitstream, execplan, SCA, numeric/W3/golden, timeout, functional RTL, ISA or hardware asset changed.

Pickup ZIP:

- `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p22_eoenfix.zip`
- bytes `5876663`
- SHA256 `876f9a16575648ddcb2dd594a881651cf7c678ddb30d344d112c68951f4fd8cf`

Expected server command:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected unique result template:

- `/home/panqs/ndp/simresult/r5_n4_0cc_p22_eoenfix_r<epoch-ns>_<pid>_return.zip`
- adjacent `.sha256`; duplicates absent.

## Release gates

- Deterministic double build: PASS.
- Frozen installed payload: `87/87` members byte-equal to p21; both SCA files identity-normalized equal.
- Focused package-local HDL: corrected actual-consumer positive compile PASS; removing the exact declaration FAIL; mutating the actual consumer back to the p21 typo FAIL.
- Family audit: `pending_receipts/conv_native_four_lane/r5_n4_0cc_p22_eoenfix/r5_n4_0cc_p22_eoenfix.family_audit.json`, bytes `379316`, SHA256 `bfa3edd215491c264420902da7947c08e6a877c880b8417913766bc4927e1d46`, PASS/errors0.
- Runner/finalizer scenarios: normal, preflight-fail, compile-fail, HUP, INT and TERM all PASS; root direct name+type set unchanged; package-owned writes remain under install; fixed simresult return is unique.
- Shared runtime-layout: `pending_receipts/conv_native_four_lane/r5_n4_0cc_p22_eoenfix/r5_n4_0cc_p22_eoenfix.shared_runtime_layout.json`, bytes `25088`, SHA256 `1ae0782858004816fccb93ac62edfc21c4312de914bdf812787c551706092491`, PASS/errors0, exact final ZIP invocation count one.
- Shadow build profile: `outputs/conv_native_four_lane_0ccae916_p22_eoenfix/server_package_build_profile_v2.json`, bytes `12894`, SHA256 `814c3cbad7e65525a56dbd02beed9e65224d3bae2e8d0a51377bada29c23b625`, contract valid/errors0.
- Final ZIP audit: `pending_receipts/conv_native_four_lane/r5_n4_0cc_p22_eoenfix/r5_n4_0cc_p22_eoenfix.final_zip_audit.json`, bytes `4429`, SHA256 `f12e755308c558a434ab50d9fbb1855f5ff11e2002e84fd13c925206f930737b`, `PACKAGE_READY_NOT_RUN`.
- Storage index: SHA256 `24a7e9768db109af7444ab495a7bffc1a83afc07a72d435947b7a5e2a4885bc7`; storage audit PASS and this family has exactly one pending ZIP.
- Server/upload/run/lease action: none.

## Blocker delta and claim boundary

- Closed: p21 formal return receipt; p21 exact package-local identifier root localization; p22 local actual-consumer scope/audit gate.
- Opened then closed locally: `B_CONV_NATIVE_P21_PACKAGE_LOCAL_EPOCH_OWNER_ENABLE_IDENTIFIER_SCOPE_ESCAPE`.
- Preserved dynamic blockers: per-input epoch ownership remains unobserved on production simulation; c0 slice finish, 27 natural terminals, formal 320D, E4/E5 and performance remain unproven.
- p22 is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`, `candidate_release=false`, `PACKAGE_RELEASE=PERFORMANCE_DIAGNOSTIC_CANDIDATE`, `PACKAGE_READY_NOT_RUN`.

## Rule feedback

`RULE_CONFIRMATION`:

- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`
- `CDA-SERVER-HDL-SCOPE-NEGATIVE-MUST-TARGET-ACTUAL-CONSUMER-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`
- repeatable per-execution return identity, install-only runtime layout, fixed simresult, root direct-set and storage rotation rules.

The p21 escape is a validator implementation miss already covered by the exact actual-consumer negative rule. `RULE_DELTA_PROPOSAL=NONE`.
