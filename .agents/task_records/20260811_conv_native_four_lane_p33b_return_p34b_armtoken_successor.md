# 2026-08-11 Conv native-four-lane p33b formal return and p34b successor

## Scope and exact identities

- Sole family: native-four-lane Conv node0004. Serialized Conv, QAdd, numeric/W3, workload, config, mapping, bitstream, execplan, SCA semantics, golden, functional RTL, ISA and hardware were not changed.
- Formal return: `C:/Users/15383/Downloads/r5_n4_0cc_p33b_wrowner_r1786374098477088271_679932_return.zip`, bytes `143523`, SHA256 `0d3cc837c58e1cd0eba8afdc6a03a1dd19809d9ece5493a36e6d95d6c60f022e`, execution `r1786374098477088271_679932`.
- Exact source p33b after rotation: `artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p33b_wrowner/r5_n4_0cc_p33b_wrowner.zip`, bytes `5931155`, SHA256 `62b225be794774e1cd8c9a4f8a8d26e2cf5ecb1795ed44fe3d1ed748d81077df`.
- Formal analysis: `outputs/conv_native_four_lane_0ccae916_p33b_return_analysis/report.json`, bytes `15030`, SHA256 `9a7a96d9725404b71e2f636c14eb2140f87d846aae406cf827b4fbb6f5fa7fe9`, `valid=true`.
- Analyzer: `tools/analyze_conv_native_four_lane_0ccae916_p33b_return.py`.

## Formal RETURN_ANALYSIS

- CRC, one safe root, exact set, allowlist/core per-file receipts, source manifest, returned source identity, execution/unique basename, install/preflight, production compile and c0 simulator-start gates passed.
- Production compile passed (`compile_exit_status=0`, no XMRE). The c0 simulator ran with the generated observer and was externally interrupted by `INT` (`sim_exit_code=130`, `PARTIAL_EXECUTION_RETURN`) after qualified progress. Missing natural terminal/D is not a DUT, config, RTL or numeric failure.
- The shared post-sim core behaved correctly: it published the allowlisted partial return despite one required package parser failure. Natural c0 slice finish, 27/27, formal 320D, mismatch-zero, E3/E4/E5 and performance remain false/unclaimed.
- Actual production RTL identity was collected. Actual/cloud differences are nonblocking provenance because compile and simulation passed; dynamic exact-target evidence remains authoritative.

## Exact-target live evidence and failure localization

- The package-local `target_epoch_write_owner_parser` failed because it required SystemVerilog `final`-block `RING_POST` records. External `INT` did not emit those final-only rows.
- The independent core return preserved the raw live log. Exact target slice0/group0 Buffer5 emitted clear at `2446437000`, then ARM-only accepted row2 writes at `2446438000` and `2446448000`, before the same-parent final row2 block at `2446469000`.
- Owner bitmap is therefore exact `ARM=1, MRM=0, NRM=0`. This closes clear-mask/no-intervening-write, MRM rewrite and NRM rewrite alternatives.
- LPG: exact target clear followed by two qualified ARM row2 accepts.
- FD: Buffer5 is repopulated by ARM after clear.
- HANG_ROOT_CAUSE: `DUT_CAUSAL_LEAF_NARROWED_TO_POSTCLEAR_ARM_REWRITE_TOKEN_IDENTITY_UNRESOLVED`. Remaining equivalents are two legitimate advancing ARM tokens, stable-token replay, or ARM address/counter reset/wrap. No functional RTL or config fix is authorized.
- New bounded blocker: `B_CONV_NATIVE_POSTCLEAR_ARM_TOKEN_ADVANCE_OR_REPLAY_UNRESOLVED`. Natural/320D/E3-E5 blockers remain.

## Unreleased p34 pre-audit escape

- Initial p34 exact ZIP: `outputs/conv_native_four_lane_0ccae916_p34_armtoken/build/r5_n4_0cc_p34_armtoken.zip`, bytes `5934148`, SHA256 `475b0ba83ffd4d34548fefa2f7d098aefb4ea94de64c8ea166c24f16eefeb5a1`.
- It was never published or rotated into pending. Exact family audit failed because package-local `arm_token_parser.py` imported a workspace-only p33 parser module absent from the ZIP.
- Disposition: `UNRELEASED_SUPERSEDED_PREAUDIT_IDENTITY_RETAINED_NOT_REBUILT`. The p34 ZIP was not overwritten or rebuilt under the same identity.
- p34b embeds all logger parsing/normalization/radix primitives. The p34b prebuild aggregate first found a local fixture-path mapping error before ZIP materialization; the full aggregate was rerun after the one mechanical receipt fix and then passed. Only one p34b final ZIP was generated.

## Fresh p34b successor

- Package: `r5_n4_0cc_p34b_armtoken`.
- Pending pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p34b_armtoken.zip`, bytes `5934761`, SHA256 `98d9f8b23824d2b5ec9e90f87fdfa1a3ee6bc61df5c9edca81ff19cf5f5b5fd1`.
- Candidate: `PERFORMANCE_DIAGNOSTIC_CANDIDATE`, `candidate_release=false`, `PACKAGE_READY_NOT_RUN`.
- Highest-information scope: live exact-target Buffer clear/ARM-accept anchors plus same-parent `Array_Request_Manager` accepted-row2 payloads containing request address/valid/rw/ready, array address, counter0/counter1/lifetime, valid/last/last-index/same, update/add signals and address reset. The family parser distinguishes distinct token-state progress, stable-token reaccept, reset/wrap and single accept without depending on final-block rings.
- Generated plan SHA256 `935ca5ceea0cf58386f96ba5e9d9f405197a8e24213a261874dbab1b59b1bffc`; source-bound generation report SHA256 `ed8fe1460c701ff4ec22e1397aed524d18995ae64409a5657d6fbb9530688bb0`.
- Deterministic double build passed. All 87 installed payload members are byte-equal to p33b; both SCA files are identity-normalized equal; numeric/W3/golden were not rerun; functional RTL modified=false.
- Same rule epoch reuse: `20260810-first-fresh-extra-audit-v1`, `first_fresh_after_change=false`, prior p31 independent-audit PASS SHA256 `48c58b614af0ba1fe311d454e5229d4f000a5b944d711e52a8c43ecc85ab0ec1`.

## Final exact-ZIP gates

- Family audit PASS/errors0, four live token decisions plus three target/time negatives and over-budget multi-instance trace: SHA256 `c814b6cc60c85d3022cc24beceaeeffae97c28e38a71b86a7c8717c47ecdead7`.
- Source-bound final-ZIP exact regeneration PASS/errors0: SHA256 `02663d041999fd611f5f6873e1250614aa07d6461d454da1243dd00f72ae1808`.
- Post-sim core final-ZIP gate PASS/errors0: SHA256 `626f0dd046fd59aab75eebd5e126e82d959c394a4044f716cd3983bd44b278e0`.
- Exact runner normal/preflight-fail/compile-fail/HUP/INT/TERM six-state PASS; finalizer reached, fixed simresult published and NDP-root direct set unchanged: SHA256 `e3b92999a04315074128a90964d564c164ac47751509b290fb4e258031663bef`.
- Shared install-only runtime layout PASS/errors0: SHA256 `aa8b81ece19ec784d831654f9774782f391df33cd87ea1d6cb1da7958146f7e2`.
- Shadow build spec SHA256 `65535e1251c3c0db21d1bdc97ed6bb0c701b4d7428c1fd6c91581f39aab5cd19`; compiled profile contract valid/errors0 SHA256 `4d9e60fde14383fe9c87075649d8c4f52b8bfffdcc36c13dbc0253919e466380`.
- Final release audit PASS SHA256 `c3dde4913323c33303ae1297a0f096be207e2fbbbdfe76a547de1c2e2284fcc1`.

## Storage and handoff

- p33b formal source/receipts rotated to `tested/conv_native_four_lane/r5_n4_0cc_p33b_wrowner/`.
- p34b is the sole pending ZIP for `conv_native_four_lane`; concurrent serialized v79 and QAdd v54 pending packages were preserved.
- Storage index `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`, bytes `299376`, SHA256 `52ff51cdc05f3158d21e89a80bd38a78f6933f4d2fbd17bd6b9fe3e29a1357db`, `pass=true`.
- Server command: `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`.
- Expected return: `/home/panqs/ndp/simresult/r5_n4_0cc_p34b_armtoken_r<epoch-ns>_<pid>_return.zip` plus adjacent `.sha256`; duplicate absence required.
- No upload, server run or lease action was performed.

## Current rule receipts and feedback

- Agent SHA256 `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`; mutable plan SHA256 `4f04b3e207a5fd200b6bbc6e66b6c0a312d1e4f24317cd9266d31d2018aecc13`; generation index SHA256 `032e3015afe870ab6db3068b46022823a91d2f39741daa9328d880a5178bfad3`; server rule SHA256 `0a738d04a018af3442b749eb0c28fc2d79dce10623d82262b29af16393a9f6b7`; config rule SHA256 `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`; hardware semantics SHA256 `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`; INT8-SA SHA256 `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`; hardware entry SHA256 `0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`.
- `RULE_DELTA_PROPOSAL CDA-SERVER-DIAGNOSTIC-PARTIAL-EXIT-LIVE-CAUSAL-RECORD-001`: a required diagnostic parser intended to adjudicate INT/TERM partial returns must consume qualified live records or a signal-safe persisted equivalent; a SystemVerilog `final`-block ring dump must not be its sole causal input. Evidence is p33b: final-only `RING_POST` was absent after INT, while independently returned live exact-target `EVENT` rows uniquely proved ARM-only rewrite. No public rule file was modified.
