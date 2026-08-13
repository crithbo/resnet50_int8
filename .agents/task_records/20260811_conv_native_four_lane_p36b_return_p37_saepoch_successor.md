# 2026-08-11 Conv native four-lane p36b formal return → p37 SA beat-identity successor

## SUPERSEDED NOTICE — p37 MUST NOT RUN

The p36b RETURN_ANALYSIS in this record remains valid, but the p37 package release text is superseded. A post-audit check proved that p37 overconstrained every lane's `same` bit even though the public group tag uses `OR(lane_same)`.

Exact p37 ZIP `441da07145ee883585ff57dd8bc3320c1486dc2ea47f852759e2ff3443995e9a` is `PACKAGE_HELD_SEMANTIC_AUDIT_ESCAPE_SUPERSEDED`; it must not be uploaded or run. The corrected fresh successor is p37b, recorded in `.agents/task_records/20260811_conv_native_four_lane_p36b_return_p37b_saepoch_successor.md`.

## Ownership and frozen scope

- Family: `conv_native_four_lane` only; mainline return target `019fbec2-fe93-7e03-9314-cff6f222f33d`.
- Formal p36b return: `C:/Users/15383/Downloads/r5_n4_0cc_p36b_semfp_r1786417577426033642_868940_return.zip`, bytes `157471`, SHA256 `d95a8c69b9fb0b44016880d9427146c5b4d1d1980fecbc760419aa5d9e21f9ed`.
- Exact source p36b: bytes `5942345`, SHA256 `0111176e62fca03a023bbd83098067191113bdc4a91a7bf5c7e0e37c3d288e0e`.
- All 87 workload/config payload members, numeric/W3/golden, mapping/bitstream/execplan/SCA semantics, timeout and functional RTL remained frozen. No server upload, run or lease was performed.

## Formal RETURN_ANALYSIS

Machine report: `outputs/conv_native_four_lane_0ccae916_p36b_return_analysis/report.json`, bytes `13448`, SHA256 `dfd777acd1e426ac3f69952ae03f028e5182d229ef3f67fed047b642d1d050ce`.

- Transport, internal CRC/root/path/exact-set/allowlist/per-file, source/execution/install/publication/core/plugin identities pass.
- Production compile succeeded and c0 simulation started. The run ended by `INT`, simulator exit `130`, so this is a valid qualified partial return rather than a config/RTL/numeric failure.
- Actual production RTL identity was collected. Actual/local/cloud differences remain nonblocking provenance after successful compile and live simulation.
- Exact target, exact instance, 45-bit payload width and binary-known semantic fingerprint all pass. X/Z, wrong instance and width/semantic drift fail closed.
- Two exact Buffer5 ARM row2 accepts occurred at `2446438000` and `2446448000`. Their complete address/counter/tag vectors are byte-identical. Reset/wrap and advancing ARM tag/counter candidates are therefore closed.
- The 45-bit ARM payload is tag/control state, not the 256-bit data beat. p36b cannot distinguish two legitimate same-row data beats from one held beat accepted twice.
- LPG: two exact-target binary-known ARM row2 accepts.
- FD: complete producer data-beat identity is absent at the first ambiguous repeated tag.
- HANG_ROOT_CAUSE: `DUT_CAUSAL_LEAF_NARROWED_TO_STABLE_ARM_TAG_ACCEPTED_TWICE_PRODUCER_BEAT_IDENTITY_UNRESOLVED`.
- c0 slice finish/natural terminal, 27/27 natural runs, formal `320D`, E3, E4 and E5 remain false or unclaimed. Formal D is `0/320_unclaimed`, neither PASS nor mismatch failure.

## 本轮进展

Compared with p35c, functional progress is **nonzero causal narrowing**:

- closed the second undriven payload leaf and all X/Z/wrong-instance ambiguity;
- first proved two fully binary-known exact-target ARM accepts;
- closed reset/wrap and advancing ARM token-state candidates;
- narrowed the remaining split to complete SA data-beat identity: distinct same-tag beats versus held-beat reaccept.

No natural-terminal, formal-D or performance completion was gained in this return.

## p37 successor

Unique pickup:

`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p37_saepoch.zip`

- bytes `5956689`;
- SHA256 `441da07145ee883585ff57dd8bc3320c1486dc2ea47f852759e2ff3443995e9a`;
- class `PERFORMANCE_DIAGNOSTIC_CANDIDATE`, `candidate_release=false`, `PACKAGE_READY_NOT_RUN`;
- command `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`;
- expected return `/home/panqs/ndp/simresult/r5_n4_0cc_p37_saepoch_r<epoch-ns>_<pid>_return.zip` plus adjacent `.sha256`.

p37 binds eight exact group0 `SA_Outport` public lane instances. Each qualified acceptance carries a binary-known 40-bit `{valid,last,same,last_index,data,ready}` payload. The package groups all eight lanes by timestamp into one complete 256-bit beat:

- distinct complete data → `DISTINCT_SA_DATA_BEATS_SHARE_ARM_TAG`;
- equal complete data → `IDENTICAL_SA_DATA_BEAT_REACCEPT_OR_VALUE_COLLISION` and remains ambiguous, not over-promoted to replay;
- X/Z, wrong instance, width drift, missing lane and semantic drift → `EVIDENCE_INCOMPLETE`.

## Build and exact final-ZIP gates

- Same rule epoch `20260811-exact-instance-payload-semantic-fingerprint-v2`; `first_fresh_after_change=false` and p36b first-fresh PASS SHA256 `7e7cd5ea7e0ce3fbf0dcd6073dff27dbe0bd0b5abd619ccd67adfbacf02cfc3c` is bound.
- Exactly one cheap aggregate, errors `0`; exactly one final ZIP; deterministic double staging.
- 87 frozen payload members byte-equal; both SCA files identity-normalized equal; functional RTL unchanged.
- Family audit PASS SHA256 `f1d4d73565ca2293ad4a1d28579851d58643b686e717b382a6a093b84d524e46`.
- Typed-v2 exact final-ZIP PASS SHA256 `dfb70d1d77e95c50429fefb19efba7bca59d240f03b34925b787a2c327d85931`; semantic fingerprint `29958092805764976d0552032e3e36eb3b14cba8623f4a16b30689b4d1b88bf4`; 1 generated positive and 8 negatives PASS, including v80 wrong-instance and p34b X/Z.
- Post-sim core PASS SHA256 `39314bdfafcd0b10d5c3907efde8b0f15fdb77e544b50c76dd53407c44da632f`; both required live plugins (`arm_known_parser`, `sa_epoch_parser`) execute and pass.
- Normal/preflight-fail/compile-fail/HUP/INT/TERM runner PASS SHA256 `f9e4de257c24875ae7c2de001aa5bc44551c69888f5746090a462c081fdfb774`.
- Shared install-only runtime layout PASS SHA256 `0a27eeb7cb5d822d4b92cdba202c3c53cea07c966c171b21d35973f7c794f208`.
- Final audit PASS SHA256 `9128b94bca375015572b06f3141865236a89ec580f27ad595e2fb66b6096fc4d`.

## Storage rotation

- Re-read current pre-rotation index SHA256 `cbb2dca675b39471c4ac0e66600ec1ff0ea743a30f08ed60439788a129e4d4df` before mutation.
- p36b formal return consumed and moved to `tested`; p37 is the only native pending ZIP.
- Serialized v83b bytes `5259860`, SHA256 `ddfb1ce5d120799d0b8d56b3b55c3a9f242ff6df3d3b975c66f7dea7bad1c319` and QAdd v56 SHA256 `78e98876977060c3ea5c29ec93e130dbd48dc13c0d8386e8c5e42c075e2055fc` remain pending and unchanged.
- Current index bytes `330049`, SHA256 `1988a91fc2179316d9640309f490a83e30515acc46a36e5f16ec4acaa50a2072`; audit PASS; counts pending/tested/superseded = `3/106/38`.

## Performance and claim boundary

Frozen config inversion remains serialized/native occurrences `205520896/51380224`, compute-occurrence reduction `4.0x`, and maximum useful lane utilization `25%→100%`. These are config-derived receipts, not measured server performance or E4/E5.

## Blocker delta and rules

Closed:

- `B_CONV_NATIVE_P35C_SECOND_UNDRIVEN_PAYLOAD_LEAF`;
- `B_CONV_NATIVE_POSTCLEAR_ARM_TOKEN_ADVANCE_OR_RESET_WRAP_UNRESOLVED`.

Added:

- `B_CONV_NATIVE_STABLE_ARM_TAG_DISTINCT_DATA_BEAT_OR_REPLAY_UNRESOLVED`.

Preserved:

- `B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN`;
- `B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN`;
- `B_CONV_NATIVE4_FORMAL_320D_UNPROVEN`;
- `B_CONV_NATIVE4_E3_E4_E5_UNPROVEN`.

`RULE_CONFIRMATION`: current exact-instance, binary-known width, semantic-fingerprint, generated-observer, post-sim and storage rules operated as intended. No non-synonymous public-rule delta is proposed.

Combined closure report: `outputs/conv_native_four_lane_0ccae916_p36b_return_p37_successor/report.json`, bytes `7274`, SHA256 `1c3785a9489deb59831245bdc9677faf78c6ad8b4e63b4b78064ebfc582d948e`.
