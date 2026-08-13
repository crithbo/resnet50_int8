# 2026-08-10 native four-lane Conv p31 return to p32b valid-owner successor

## Scope

- Family: `conv_native_four_lane`, frozen node0004 c0 diagnostic branch.
- Formal p31 return: `r5_n4_0cc_p31_postclear_r1786363816915779986_588811_return.zip`, bytes `141788`, SHA256 `b4e1e8a54828b24beee0ac9cdccf417316e9c8043aa8bb7b57e5d0eb201aa4f7`.
- Exact p31 source SHA256: `d022977daebb1c633d0c4fa32ca58cf5b660a6f4c4dff6cb11d499a21d2345c9`.
- No functional RTL, numeric, W3, workload, config, mapping, bitstream, execplan or golden change.

## Formal p31 adjudication

- Analysis: `outputs/conv_native_four_lane_0ccae916_p31_return_analysis/report.json`, SHA256 `cb9fd32feeed1644b100687b102218bbc34571fed5e244697703044b7638f14f`.
- Status: `P31_PARTIAL_INTERRUPTED_TARGET_HIGH_BANK_VALID_OWNERSHIP_SUCCESSOR_REQUIRED`.
- CRC/root/path/exact-set/allowlist/per-file/source/execution/install/root/publication/core/plugin receipts are valid. Production compile passed with no XMRE; c0 simulation started and all six plugins passed.
- The execution ended by `INT` (`sim_exit=130`) with qualified c0 progress. This is a partial interrupted diagnostic return, not a DUT/config/RTL/numeric failure.
- Natural terminal and c0 slice finish were not reached. The source intentionally requested zero formal-D reads, so 27/27 natural, 320/320 D, E3, E4, E5, mismatch-zero and performance remain unclaimed.
- Actual production causal-leaf SHA differences versus local/cloud are nonblocking provenance because compile and simulation passed.
- Exact target Buffer5 parent observed `row2_block_bank_ready_0f` at time `2446437000`, with bank-ready `0x0f`, mask `0xff`, MRM clear `0xf0`, valid clear `0xf0`, valid/write enables `0xff`, write row `2`, and tag-row-empty `0`; the same target parent observed the final same-row2 block at time `2446469000`.
- LPG: compile/c0/source-bound observer active; exact target reached post-clear `0x0f`, then same-parent final marker.
- FD: after the `0xf0` clear, target Buffer5 row2 banks 4..7 remain nonempty. Aggregate-ready recomputation is consistent with `mask=0xff` and `bank_ready=0x0f`, so it is not the root.
- Root boundary: `DUT_CAUSAL_LEAF_UNRESOLVED_VALID_OWNERSHIP`, class `BUFFER5_ROW2_HIGH_HALF_VALID_PERSISTS_AFTER_F0_CLEAR`. Remaining equivalents are effective clear-mask preservation, accepted same/following-edge re-write, or clear/write row/epoch mismatch. No functional RTL or config fix is yet authorized.
- Closed blockers: signal-safe final-state escape; final `0f` versus `ff`; aggregate-ready recomputation ambiguity. Preserved blockers: target high-bank valid ownership, c0/natural/27/320D/E4/E5.

## p32b materialization

- Release identity: `r5_n4_0cc_p32b_validowner`.
- The family-local exact-parent and bounded-epoch correlator requires `clear_time < state_time <= final_time` and distinguishes no-write, accepted-write, `00`, `0f`, `f0`, `ff`, and other post-clear states before the final marker.
- Source-bound generation positives and missing-enable/simultaneous-class/wrong-epoch/wrong-instance negatives all pass; over-budget multi-instance trace handling is bounded.
- Deterministic double build passed. Frozen installed payloads are 87/87 byte-equal; SCA identity-normalized equality passed.
- Build report SHA256 `12bc7351596a01f8d171f60f4043a2f4fb56afcecfdc27a47bb30ef30c79660f`.
- Exact final ZIP bytes `5934940`, SHA256 `fc21dc0fccb4fbf612e55418964f78ba482678ec232a4bb438b50f97e03a2d47`.

## Exact runner, layout and release disposition

- Family audit SHA256 `f2586894a1afce31f2435f74b687e11ccf7db506ce5977de72a4a6b41e2158ee`, PASS/errors 0.
- Source-bound exact-final-ZIP regeneration SHA256 `de271a6bae5984d80b0a3cd77ca56d6a13b8b9c25e091b31b3f3d753eea75bab`, PASS/errors 0.
- Post-sim independent core-return audit SHA256 `63775faa91502c3fc983d4c69269140b253e0b6e4b1496e29040c3650a3d1d7d`, PASS/errors 0.
- Exact runner six-state audit SHA256 `fc45c9fd4e1f285f7b53abfb3a43e8a42ba6a46968c2b7594f5057fe7b25adea`: normal/preflight-fail/compile-fail/HUP/INT/TERM all pass, expected exits `0/5/42/129/130/143`, fixed result published, NDP-root direct exact-set unchanged.
- Shared install-only V2 layout audit SHA256 `e8f371b0e27d4ef40d47154fbd44cb10156e7a6ef9a0242c36a8add3c6b20389`, PASS/errors 0. It was consumed by the exact runner harness and was not replaced by an earlier core-only gate.
- No new rule-change epoch occurred after p31. p32b declares `first_fresh_after_change=false` and binds p31 first-fresh PASS receipt SHA256 `48c58b614af0ba1fe311d454e5229d4f000a5b944d711e52a8c43ecc85ab0ec1`.
- Final ZIP audit SHA256 `6e792b9aec388dd417c46818d5ec4a0e5244d219cde5a0e6769b7cfb95a08cd8`, status `PACKAGE_READY_NOT_RUN`, package class `PERFORMANCE_DIAGNOSTIC_CANDIDATE`, `candidate_release=false`.
- The earlier `p32` ZIP was an unreleased pre-audit identity. Its wrong-epoch negative exposed a family-parser gap; it was retained as `UNRELEASED_SUPERSEDED_PREAUDIT_IDENTITY_RETAINED_NOT_REBUILT` and was never published or overwritten.
- A p32b shadow build-profile attempt failed only because three `receipt_reuse_candidates` entries were strings rather than objects. This was an audit-spec/fixture shape error, not an exact-ZIP, runner, shared-layout, source-bound or post-sim failure. A content-neutral v2 profile revalidation passed with spec SHA256 `bc47b51e70dd25d93b65dfbcffe8ee7a4497100b563af6050e34a912f8fd42cd` and profile SHA256 `9706ddeefd8d6a535047a0c2c49cce767b1c33b2d2b7f4d1b4a790cfa4d45395`; the p32b ZIP was not rebuilt and its identity did not change.

## Storage and pickup

- p31 rotated to `tested` with its formal analysis evidence.
- p32b is the sole `conv_native_four_lane` pending ZIP; concurrent serialized and QAdd pending entries were preserved.
- Pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p32b_validowner.zip`.
- Storage index SHA256 `a56dd1c31c50b9b68f670b520cad73db67c7a3b82b40d69c31df02447ae275e4`, audit PASS.
- Server command: `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`.
- Expected return: `/home/panqs/ndp/simresult/r5_n4_0cc_p32b_validowner_r<epoch-ns>_<pid>_return.zip` plus adjacent `.sha256`; duplicate absent required.
- No upload, server run or lease action was performed.

## Rule feedback

`RULE_DELTA_PROPOSAL`: `CDA-SERVER-SOURCE-BOUND-DECISION-INSTANCE-EPOCH-CORRELATION-001`. When a generated decision combines repeated module instances or multiple epochs, the decision must bind an exact instance key and bounded epoch; mixed-instance or mixed-epoch evidence must fail closed. P31's global sticky `class_seen` could combine 28 Buffer_Manager parents, while the family-local p32b correlator demonstrates the required exact-parent/epoch behavior. No public rule was modified.
