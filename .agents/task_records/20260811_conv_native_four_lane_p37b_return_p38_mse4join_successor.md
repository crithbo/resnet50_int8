# 2026-08-11 native Conv p37b return and p38 MSE4-join successor

## Outcome

- Formal p37b return analysis is valid. The exact source/per-execution/CRC/root/path/exact-set/allowlist/per-file/install/publication/core/plugin receipts close, production compile succeeded without XMRE, simulation started, and INT/130 followed a long qualified c0 interval. This is a qualified partial return, not a too-short simulation.
- Two exact target eight-lane `valid && ready` SA beats at `2446438000` and `2446441000` share group tag `0x3fdf` but have distinct complete 256-bit identities. The public tag is reconstructed as `{valid_vector, OR(last), OR(same), lane0_last_index}`; the nonuniform-lane positive passes. Held-beat replay and distinct equal-value-beat candidates are closed.
- Downstream acceptance continues. The final DataHub channel-8 head is accepted; the terminal ledger then stops with MSE4 descriptor count `18`, prepared Buffer5-data count `20`, delta `2`, descriptor queue empty, source/tag state retained and no slice finish.
- LPG: two distinct complete SA beats and qualified downstream accepts. FD: exact MSE4 descriptor production ends at 18 while Buffer5 data preparation reaches 20. Root remains `DUT_CAUSAL_LEAF_NARROWED_TO_MSE4_ADDRESS_DESCRIPTOR_END_VERSUS_WRITE_DATA_PREPARATION_SKEW_UNRESOLVED`; no RTL or config fix is authorized.
- Natural c0 terminal, 27/27, formal 320D, mismatch=0, E3, E4, E5 and measured performance remain unclaimed.

Formal analyzer: `tools/analyze_conv_native_four_lane_0ccae916_p37b_return.py`, bytes `23367`, SHA256 `5a556c4c14894f4089366e6de623815e6cdeea1fd03fb906b053ac59eaa8ec36`.

Return report: `outputs/conv_native_four_lane_0ccae916_p37b_return_analysis/report.json`, bytes `20719`, SHA256 `2cac5f1ea63e869d550c2d95eb8ae563d20036f3d42db378c26163d7e62eaae7`.

## Blocker delta and progress

- Closed: `B_CONV_NATIVE_STABLE_ARM_TAG_DISTINCT_DATA_BEAT_OR_REPLAY_UNRESOLVED`, held-beat reaccept and distinct equal-value alternatives.
- Added: `B_CONV_NATIVE_MSE4_DESCRIPTOR_18_VS_PREPARED_20_UNIT_SEMANTICS_UNRESOLVED`.
- Preserved: c0 slice finish, 27 natural terminals, formal 320D and E3/E4/E5 remain unproven.
- Functional progress is `NONZERO_CAUSAL_NARROWING`: p37b first proves genuine distinct SA data behind the repeated ARM tag and moves first divergence from SA/Buffer5 acceptance to the MSE4 address-descriptor versus write-data join.

## p38 package

- Pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p38_mse4join.zip`
- bytes: `5970142`
- SHA256: `328b7ec7b7034a1a2c202fad38d628199cfbbaa2213196d94daab39c25ff4d22`
- Status: `PACKAGE_READY_NOT_RUN`, `PERFORMANCE_DIAGNOSTIC_CANDIDATE`, `candidate_release=false`.
- Command: `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`
- Expected return: `/home/panqs/ndp/simresult/r5_n4_0cc_p38_mse4join_r<epoch-ns>_<pid>_return.zip` plus adjacent `.sha256`.

p38 source-binds the exact slice0/group0/MSE4[4] write engine and joins five accepted-event boundaries: Memory_AG output, descriptor, Buffer5 data, output write data and slice finish. Its primary split distinguishes a legal descriptor/data unit ratio, an address/index terminal two units early, and descriptor/tag/source join suppression. It retains p37b SA/Buffer anchors for continuity. All 87 payload/config/numeric/W3/workload/mapping/bitstream/execplan/SCA/golden/timeout/functional RTL assets are frozen; SCA changes are identity-only.

Exactly one final p38 ZIP exists. Deterministic double staging, frozen 87-member byte equality, SCA identity-normalized equality and `functional_rtl_modified=false` pass. One cheap shadow aggregate was invoked; contract valid/errors0. The same rule epoch reuses the p36b first-fresh PASS receipt SHA256 `7e7cd5ea7e0ce3fbf0dcd6073dff27dbe0bd0b5abd619ccd67adfbacf02cfc3c` with `first_fresh_after_change=false`.

## Exact gates

- Family audit PASS: bytes `12134`, SHA256 `7145ee3c52f8d50804f69d177833dfccc048c95039fb5d33311b1fb1ba17e331`.
- Typed-v2 source-bound final ZIP PASS: bytes `120311`, SHA256 `ab9c99c6d40fb685c2af51c1e6ba34b552e9e36d4eb2159132a555a1d733604e`; nine semantic cases, eight fail-closed negatives.
- Post-sim independent core/live-causal PASS: bytes `3025`, SHA256 `dfb730280a106579d52540bb60f8d8d018e86ffbdcd3a372bd342b658169fc45`; required `arm_known_parser`, `sa_epoch_parser` and `mse4_join_parser` all execute/pass.
- Normal/preflight-fail/compile-fail/HUP/INT/TERM runner PASS: bytes `9611`, SHA256 `be2135afa1f0c4fcb25c0507204811c20b858c5ca6c671417af022b1cd35b89a`.
- Shared install-only runtime layout PASS: bytes `25210`, SHA256 `143d76a669422eee575504c7d43e2099e22560bf4f882fb7ff166fbbaad90749`.
- Build spec SHA256 `9ff782bf62b0cb9a4b46280b4224d49e42b77ff67739318e0a58ea08caf06561`; profile SHA256 `2f4c952fbd65e40653319db23d0732d35ce914dae88027f783e032130f67119f`.
- Final release audit PASS: bytes `8727`, SHA256 `e64a4adfd659e7abdf003ea94f8fc624c0c9a0007f457185c377445de58b0953`.
- Final machine report PASS: bytes `12064`, SHA256 `896feb1cf4ad7e52cae11f261782e5092d5d6702e458681cf04475023dc87155`.

One pre-final build attempt failed before any ZIP existed because an inherited frozen-check module path still named the p37 surface. The incomplete p38-only build directory was removed after verifying `final_zip_count=0`; the identity path was corrected and the one final ZIP was then created. No released ZIP was rebuilt or replaced.

## Storage and rules

- Exact storage preimage: bytes `340780`, SHA256 `61e364f4d19bf892f24e5824f673230399de34f176437000a17445e4bbc2f9ad`.
- Post-rotation index: bytes `344844`, SHA256 `163d05b575cc76cebe0a9f0dc2375c9f636aa96413107180b4a219a10ff2ba06`; audit exit `0`; pending/tested/superseded=`3/108/39`.
- p37b moved to `tested`; p38 is the sole native-four-lane pending ZIP. Serialized v84b and QAdd v56 remain pending and unchanged.

`RULE_CONFIRMATION`: current source-bound generation, exact-instance/grouping, binary-known/width fail-closed, semantic fingerprint, partial-exit live causal, independent post-sim core, continuous return-to-successor and storage-rotation gates all operated as intended. No non-synonymous public rule delta is proposed and no public rule was modified.

No upload, server run or lease was performed.
