# 2026-08-11 Conv native four-lane p34b return → p35c arm-known successor

## Scope and ownership

- Family: `conv_native_four_lane`; frozen node0004 native-four-lane diagnostic line only.
- Formal return: `C:/Users/15383/Downloads/r5_n4_0cc_p34b_armtoken_r1786378914397059149_731119_return.zip`, bytes `150589`, SHA256 `e9f01d27a84b7dc6b912cff66f6895db95c2bab2cac1b7ef0814bd75178b129b`, execution `r1786378914397059149_731119`.
- Exact source: `r5_n4_0cc_p34b_armtoken.zip`, bytes `5934761`, SHA256 `98d9f8b23824d2b5ec9e90f87fdfa1a3ee6bc61df5c9edca81ff19cf5f5b5fd1`.
- No functional RTL, ISA, hardware, active ndp-sim, public rule, `.agents/plan.md`, serialized Conv, QAdd, numeric/W3/golden, workload/config/mapping/bitstream/execplan or frozen 87 installed payload member was modified.
- No upload, server execution or lease action was performed.

## Current rule identity

- `.agents/agent.md`: `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`.
- `.agents/plan.md`: `4f04b3e207a5fd200b6bbc6e66b6c0a312d1e4f24317cd9266d31d2018aecc13` (mutable provenance only).
- `.agents/rules/生成前必读索引.md`: `d55645b911ae21c1e4a0b653f9c6c0c0ef12d8c1aead8f3bd27925d52734e767`.
- `.agents/rules/服务器测试包生成规则.md`: `2283153ad28ac3cfc21584ac705ef90e640bf157146153f4bc50dfd0e8f0af0e`.
- `.agents/rules/算子配置规则.md`: `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`.
- `tools/server_post_sim_return.py`: `19bea6cc8bb5bd6247f7d2da67de3df967a562f1193c82a2f1a1ddb1ae483e6f`.
- First-fresh ACK epoch: `20260811-native-live-causal-partial-exit-v1`, bound to final package `r5_n4_0cc_p35c_armknown`.

## Formal RETURN_ANALYSIS

- Machine report: `outputs/conv_native_four_lane_0ccae916_p34b_return_analysis/report.json`, SHA256 `3c40b9f32dff646387c72ad4bb92a594ecf4c76b6ef3066b9fe991be7f7283aa`.
- CRC, one-root/path safety, internal exact-set/allowlist/per-file receipts, source identity, execution identity, install/runtime publication, post-sim core and required-plugin receipts all validate.
- Production compile succeeded (`compile_exit_status=0`), DUT simulation started, simulator ended on captured `INT` (`sim_exit_code=130`, package `run_exit_status=125`). The partial return is valid evidence and is not a DUT/config/numeric failure.
- Production RTL identity was collected. Actual/cloud and actual/local leaf differences remain nonblocking provenance because production compile and simulation both passed.
- No c0 slice finish, natural terminal, formal 320D payload, mismatch-zero result conjunction, E3, E4 or E5 is established.

## LPG / FD / root cause

- LPG: p33b exact target clear followed by two ARM-owned accepted writes at `2446438000` and `2446448000`.
- FD: p34b ARM token payload is not binary-known. Three target rows contain `Z`: `5ffe200ff79Z`, `5ffe200ff7dZ`, `5ffe200ff7dZ`.
- The observed `Array_Request_Manager.add_array_req_addr` leaf is declared but not live-assigned in current source. The package parser maps non-hex payload to `-1`, then bit-slices it as all-one fields and falsely reports `TARGET_ARM_ROW2_STABLE_TOKEN_REACCEPT`.
- HANG_ROOT_CAUSE: `PACKAGE_LOCAL_DIAGNOSTIC_PAYLOAD_UNKNOWN_FAIL_OPEN`. This proves neither functional RTL nor configuration root cause, and authorizes no RTL/config change.
- Remaining observational equivalents: legitimate advancing ARM tokens; stable-token replay; address/counter reset or wrap.

## 本轮进展

- Compared with p33b, no functional blocker was closed; functional progress is **ZERO**.
- First proved in this round: p34b's target ARM payload includes an unknown `Z`, and the package-local parser converts it into a false all-one token decision.
- The remaining functional candidate set is unchanged but now correctly bounded to three classes: legitimate advance, stable replay, reset/wrap.
- The successor removes the undriven field, records only binary-known live EVENT fields, and fails closed on any X/Z before decode, so the next return can discriminate those three classes without inventing evidence.

## Blocker delta

- Added and closed package-side escape in the successor: `B_CONV_NATIVE_P34B_UNKNOWN_ARM_PAYLOAD_PARSER_FAIL_OPEN`.
- Preserved: `B_CONV_NATIVE_POSTCLEAR_ARM_TOKEN_ADVANCE_OR_REPLAY_UNRESOLVED`, `B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN`, `B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN`, `B_CONV_NATIVE4_FORMAL_320D_UNPROVEN`, `B_CONV_NATIVE4_E4_E5_UNPROVEN`.

## Continuous-closure successor

- Final identity: `r5_n4_0cc_p35c_armknown`.
- `p35` stopped after its single cheap aggregate found a prebuild contract/report-class mismatch; no ZIP was created (`PREBUILD_ONLY_FAILED_NO_ZIP_PRESERVED`).
- `p35b` stopped during pre-final staging because the expected source-bound generation report basename was absent; no ZIP was created (`PREFINAL_STAGING_FAILED_NO_ZIP_PRESERVED`).
- `p35c` then used a fresh identity and produced exactly one final ZIP; the ZIP was not rebuilt.
- Final ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p35c_armknown.zip`, bytes `5938804`, SHA256 `b755592dbd01f05a63f0471ed76ede7673ab987b57a2cf579a8566a3d26f59fc`.
- Final audit: `outputs/conv_native_four_lane_0ccae916_p35c_armknown/r5_n4_0cc_p35c_armknown.final_zip_audit.json`, SHA256 `e21870cd266017d63788eb7b037c11094cbd6936770b002b41b0223a017b8c94`, `valid=true`, `PACKAGE_READY_NOT_RUN`.
- Candidate class: `PERFORMANCE_DIAGNOSTIC_CANDIDATE`, `candidate_release=false`; claim scope is one c0 binary-known live ARM causal diagnostic only.

## Required gates

- Deterministic double staging and frozen 87-payload byte equality: PASS.
- One cheap prebuild aggregate for p35c and one final ZIP: PASS.
- Source-bound generation and exact regeneration from final ZIP: PASS.
- Required plugin disposition: `arm_known_parser=LIVE_CAUSAL_FIXTURE`; tiny live-only fixture PASS; final-only ring as sole input negative PASS; X/Z fail-closed negative PASS; required first payload sample present.
- Post-sim core return independent publication scenarios: PASS.
- Runner normal/preflight-fail/compile-fail/HUP/INT/TERM: PASS; shared install-only runtime layout: PASS.
- First-fresh independent clean-extract audit: `outputs/p35c_first_fresh_audit_v2/validation.json`, SHA256 `a292b618fe6e8b76321c626d71d931fe2710cf5e382e05fe9dda8695f412f59e`, `pass=true`, `error_count=0`, `upload_authorized=true`.
- Family audit: `outputs/conv_native_four_lane_0ccae916_p35c_armknown/p35c_family_audit.json`, SHA256 `490c0f8f4dc07a9fefc520dde266c98bf9d3562adf63ca28b0391670227b5cd6`, `valid=true`.

## Storage and run handoff

- p34b formal source package was rotated to `tested/conv_native_four_lane/r5_n4_0cc_p34b_armtoken` with byte identity retained.
- Native-four-lane pending contains only `r5_n4_0cc_p35c_armknown`; serialized v80 and QAdd v54 pending packages were preserved.
- Storage index: `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`, SHA256 `4b399d647fd6d665684bf056b018678a7b9bb7dee9f9e7e413b10d7c1bac1846`, `pass=true`, counts pending/tested/superseded=`3/100/38`.
- Server command: `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`.
- Expected unique return: `/home/panqs/ndp/simresult/r5_n4_0cc_p35c_armknown_r<epoch-ns>_<pid>_return.zip` plus adjacent `.sha256`; duplicate absence remains required.

## Rule feedback

- `RULE_CONFIRMATION`:
  - `CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001` correctly blocks a final-only/unknown-decoded diagnostic from being used as causal evidence and requires the live-only fixture now present in p35c.
  - `CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001` correctly requires transaction-qualified rows rather than stable-level replay counts.
  - `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001` is satisfied by the single highest-information binary-known successor.
- No non-synonymous public rule delta is proposed and no public rule file was changed.
