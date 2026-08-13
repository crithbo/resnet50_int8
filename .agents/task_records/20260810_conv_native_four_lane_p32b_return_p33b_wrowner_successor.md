# 2026-08-10 Conv native-four-lane p32b formal return and p33b successor

## Scope and identities

- Sole family: native-four-lane Conv node0004. Serialized Conv, QAdd, numeric/W3, workload, config, mapping, bitstream, execplan, SCA semantics, golden and functional RTL were not changed.
- Formal return: `C:/Users/15383/Downloads/r5_n4_0cc_p32b_validowner_r1786370009009142729_655330_return.zip`, bytes `148722`, SHA256 `6bfd9e6eda9b0ae6ceb0ebbc066f1035b0bc791766b7ea851dedd168f5e9be7e`, execution `r1786370009009142729_655330`.
- Exact source p32b: `artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p32b_validowner/r5_n4_0cc_p32b_validowner.zip`, bytes `5934940`, SHA256 `fc21dc0fccb4fbf612e55418964f78ba482678ec232a4bb438b50f97e03a2d47` after formal-consumption rotation.
- Formal analysis: `outputs/conv_native_four_lane_0ccae916_p32b_return_analysis/report.json`, bytes `17479`, SHA256 `54210483a215ca5b9869b84f5f077105f96f3dd83e50150f95633c7243836fd0`, `valid=true`.
- Analyzer: `tools/analyze_conv_native_four_lane_0ccae916_p32b_return.py`, SHA256 `ad82f1a8bae5e3b28529642785f74716b971416bfa416084a647b2be52fd56d3`.

## Formal RETURN_ANALYSIS

- CRC, single root, safe paths, exact set, allowlist/per-file core receipts, source manifest, returned source manifest, execution identity, unique return basename, install/root/package/observer preflights, generated observer regeneration identity, post-sim core and all seven plugins passed.
- Production compile passed (`compile_exit_status=0`, no XMRE); c0 simulator started with the generated observer and valid feature binding.
- The process was externally interrupted by `INT` (`sim_exit_code=130`, disposition `PARTIAL_EXECUTION_RETURN`) after qualified progress. This is not a DUT/config/RTL/numeric failure. Natural terminal, c0 slice finish, 27/27, formal 320D, mismatch-zero and E3/E4/E5 remain false/unclaimed by design.
- Production causal identity was collected. The actual `Buffer.sv` leaf is SHA256 `ea9a5f0831a0561aee3f4fae94b354c50ec2c98f65ebcb21320fcb3056af9896`, while the local/cloud provenance leaf is `41ae28b741931bb53effdce6482e68110983f2d57f43cd4c87dfd50b6a34acc0`. Compile and simulation succeeded, so the identity difference is nonblocking provenance; dynamic exact-target evidence remains authoritative.

## LPG / FD / HANG_ROOT_CAUSE

- LPG: exact target slice0/group0 Buffer5 emitted `row2_clear_f0_at_0f` at `2446437000`, then the same target emitted `row2_postclear_bank_0f_no_write_accept` at `2446468000`, followed by its own final same-row2 marker at `2446469000`.
- Clear sample: bank-ready `0x0f`, MRM clear `0xf0`, row `2`, no accepted write at that sample. Post sample: bank-ready remains `0x0f`, no clear, and `buf_wreq_ready=0` at that sample.
- FD: high four banks remain nonempty after the target f0 clear sample, but p32b's `no_write_accept` predicate is sample-local. It does not prove that no ARM/MRM/NRM write was accepted during the intervening 31 ns.
- HANG_ROOT_CAUSE: `DUT_CAUSAL_LEAF_UNRESOLVED_CLEAR_MASK_OR_INTERVENING_WRITE`. The remaining observational equivalents are an effective ARM/MRM/NRM row2 write accepted within the clear-to-post window, or no intervening accepted write and a partial/ineffective per-byte clear mask/application. There is no unique evidence authorizing a functional RTL or config change.
- Blocker delta closed target-instance/epoch correlation, post-state class and post-sample acceptance. It added only the bounded temporal write-owner gap and preserved natural/320D/E3-E5 blockers.

## Unreleased p33 pre-audit escape

- Initial exact ZIP `r5_n4_0cc_p33_wrowner.zip`, bytes `5930835`, SHA256 `4667ec56def0f4528456c618f981bd422921d92dea61e1fa11add696ca7f1d71`, was never published or rotated into pending.
- Exact family audit `outputs/conv_native_four_lane_0ccae916_p33_wrowner/p33_family_audit.json`, SHA256 `7ae0df98d3d3420fdbc75cdcaf7291c38e7de9ac087df023db781e7f196ca47c`, correctly failed before release: the family parser treated Verilog `%0h` `mask=10` as decimal 10 instead of hexadecimal `0x10`, corrupting post-state/owner classification.
- Disposition: `UNRELEASED_SUPERSEDED_PREAUDIT_IDENTITY_RETAINED_NOT_REBUILT`. The p33 ZIP was not overwritten or rebuilt under the same identity.

## Fresh p33b successor

- Package: `r5_n4_0cc_p33b_wrowner`.
- Pending pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p33b_wrowner.zip`, bytes `5931155`, SHA256 `62b225be794774e1cd8c9a4f8a8d26e2cf5ecb1795ed44fe3d1ed748d81077df`.
- Candidate class: `PERFORMANCE_DIAGNOSTIC_CANDIDATE`, `candidate_release=false`, status `PACKAGE_READY_NOT_RUN`.
- Diagnostic: one generated Buffer boundary uses the exact f0 clear as its trigger and retains eight `RING_POST` samples. Its bitmap separately records effective ARM, MRM and NRM write acceptance under the actual Buffer mux priority and the post-clear 0x0f state. A package-local parser correlates only the declared target parent and one clear-to-post epoch.
- Parser source: `tools/conv_native_four_lane_p33_target_epoch_write_owner_parser.py`, SHA256 `ff6a2606452d9986c5c7bdcd5613ecf064cb1f0dc0e7e3efea9dcf30f56f59dc`; `%0h` masks are explicitly decoded base16.
- Generated plan SHA256 `847e5a7d8b0b5115691af339d20ff4a9a4dcf1c20e1780d66949dee82830d4d3`; generation report SHA256 `43ad98301ca9f5ea8078c063fecb9dcac72bf7cdc26f605bc8c0d19205b12f28`; exact binding SHA256 `f3468e4f6b8ef361f07a844e7171f8e93092106dc8505bf7adfba142acc23ef3`.
- Frozen proof: deterministic double build; all 87 installed payload members byte-equal to p32b; both SCA files identity-normalized equal; numeric/W3/golden not rerun; functional RTL modified=false.
- Same rule epoch reuse: `20260810-first-fresh-extra-audit-v1`, `first_fresh_after_change=false`, prior p31 independent-audit PASS SHA256 `48c58b614af0ba1fe311d454e5229d4f000a5b944d711e52a8c43ecc85ab0ec1`.

## Final gates

- Family exact-ZIP audit PASS, errors 0, eight owner bitmaps pairwise distinguished, five temporal/identity negatives fail closed, over-budget parser trace covered: SHA256 `1c460b141f91e355ce836571bb674381e4c5a6346e2768b95d5384d46b55596c`.
- Exact source-bound final-ZIP regeneration PASS/errors 0: SHA256 `b1cefb8861e2137ae1076cce67517c8eb44a031967d7d0d0ed0baccf636d6100`.
- Post-sim core final-ZIP gate PASS/errors 0: SHA256 `f275ec4ac45dbec5a83a07645c368e995bdec4a859b9a3141b13352b7ca895dd`.
- Exact runner normal/preflight-fail/compile-fail/HUP/INT/TERM six-state PASS, finalizer reached, fixed simresult published, NDP-root direct set unchanged: SHA256 `6a959a826f8ad8e2d6d0bcc52027b4d3650e0ae86139a85b0f79bc585cf3846d`.
- Shared install-only runtime layout PASS/errors 0: SHA256 `987541552e1f2920fe238f61a46950a2c6f3bdfc945a716c11a3f838a4efebfb`.
- Shadow build spec SHA256 `e6d60b8dfcb0a447622e2931bee3ab224661ce2f6de70e25d29236feb199bd66`; compiled profile contract valid/errors 0, SHA256 `8564fb1af03d1ca576fc582df5a264892c52d05bce12cdd57e369c1ba7e6ebc4`.
- Final release audit PASS SHA256 `9f6ebf73112e4eea0e813d4d49213f6e9d8b786f391ef56ed4c4194c7b4b6156`.

## Storage and server handoff

- p32b formal source/receipts rotated to `tested/conv_native_four_lane/r5_n4_0cc_p32b_validowner/`.
- p33b is the sole pending package for `conv_native_four_lane`; serialized and QAdd pending assets were preserved.
- Storage index PASS SHA256 `ce2738930972b979a21558e5a40f8af129735a836fa1588e3b80b3ffd96a4b8d`.
- Server command: `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`.
- Expected return: `/home/panqs/ndp/simresult/r5_n4_0cc_p33b_wrowner_r<epoch-ns>_<pid>_return.zip` plus adjacent `.sha256`; duplicate absence required.
- No upload, server run or lease action was performed.

## Current receipts and rule feedback

- Agent SHA256 `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`; mutable plan SHA256 `4f04b3e207a5fd200b6bbc6e66b6c0a312d1e4f24317cd9266d31d2018aecc13`; generation index SHA256 `032e3015afe870ab6db3068b46022823a91d2f39741daa9328d880a5178bfad3`; server rule SHA256 `0a738d04a018af3442b749eb0c28fc2d79dce10623d82262b29af16393a9f6b7`; config rule SHA256 `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`; hardware semantics SHA256 `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`; INT8-SA rule SHA256 `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`; hardware entry SHA256 `0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`.
- `RULE_CONFIRMATION`: the current changed-observer exact regeneration, predicate-trace, multiclass no-loss, post-sim independent core, six-state runner, install-layout, result conjunction, nonblocking cloud identity and first-fresh epoch rules are sufficient. In particular, the exact predicate controls caught the p33 `%0h` radix escape locally before release. No non-synonymous public-rule delta is required and no public rule file was modified.
