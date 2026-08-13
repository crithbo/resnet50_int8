# 2026-08-11 Conv native four-lane p35c formal return → p36b semantic-fingerprint successor

## Ownership and scope

- Family: `conv_native_four_lane` only.
- Formal p35c return: `C:/Users/15383/Downloads/r5_n4_0cc_p35c_armknown_r1786384633990059082_756950_return.zip`, bytes `152068`, SHA256 `be5b38243a1ea156f6661bcbfbd8a7532951868d412d3f7c3b7025d94100f39f`.
- Exact source p35c SHA256: `b755592dbd01f05a63f0471ed76ede7673ab987b57a2cf579a8566a3d26f59fc`.
- Numeric/W3/workload/config/mapping/bitstream/execplan/SCA/golden/timeout and functional RTL stayed frozen. Serialized Conv and QAdd assets were not modified.
- No server upload, run, or lease was performed.

## Formal RETURN_ANALYSIS

Machine report: `outputs/conv_native_four_lane_0ccae916_p35c_return_analysis/report_v2.json`, bytes `10440`, SHA256 `467a302034be259a629af67a9547a463f51a83e0046aaea3342803ecec516166`.

- Internal transport/source/execution/install/publication/core/plugin identities pass.
- Production compile completed. Simulation was externally interrupted by `INT`: simulator exit `130`; this is a valid qualified partial return, not a DUT/config/RTL/numeric failure.
- p35c correctly rejected X/Z and did not reproduce p34b's numeric-sentinel fail-open.
- Three target ARM accepted rows carried Z in `add_array_life_cnt`. Current `Array_Request_Manager.sv` declares this leaf but does not drive it, so the package-local payload contract was incomplete.
- LPG: production compile and live Buffer/ARM observation were reached.
- FD: accepted target ARM payload remained unknown at the second undriven leaf.
- root: `PACKAGE_LOCAL_SOURCE_BOUND_SEMANTIC_COMPLETENESS_ESCAPE`.
- c0 slice finish/natural terminal/27-run/formal 320D/E3/E4/E5 remain false or unclaimed. Formal D is `0/320`, not a failure and not a pass.
- Functional progress this round is **zero**. The remaining legitimate-advance / stable-replay / reset-wrap candidates are unchanged.

## Next-fresh three-rule consumption

Current identities consumed:

- server rule `74ae37513d6bcb763543a7a4583ec1acea3d4b2919f07ab8fab266272bf3cc0b`;
- generation index `991740fe543243c1697174fe9c9621af0201469c8bab37c95ea4db12d8276f2c`;
- specialist rule `426876da2a299e4e2003f52cd254ff5f8f3fd5b3510a81b1e15fb0d47567ef23`;
- epoch `20260811-exact-instance-payload-semantic-fingerprint-v2`.

p36/p36b bind:

- exact canonical group0 Buffer5 instances;
- group0 Buffer4 near-miss instances;
- grouping key `(boundary_id, canonical_instance, seq)`;
- binary-known payloads with exact widths Buffer `98`, ARM `45`, final `17`;
- wrong instance, X/Z, numeric parse failure, missing/incorrect width and duplicate group keys to `EVIDENCE_INCOMPLETE`;
- semantic fingerprint first use with independent audit.

## Shared-generator escape and narrow repair

The first final ZIP identity `r5_n4_0cc_p36_semfp` was materialized once, SHA256 `7cc8fe28e77b39a1fc0e7b2970664b9ae5dc33f9f1deef0da86eb726e297152e`, then held. Typed v2 final validation exposed `v80_mixed_target_near_miss`: the shared control mutated the first plan boundary even though the selected candidate's payload-bearing EVENT was on the later ARM boundary. It therefore incorrectly returned `ARM_ACCEPT_NO_AUX` rather than `EVIDENCE_INCOMPLETE`. p36 was not rebuilt under the same identity and was not published.

The shared generator now chooses the actual payload-bearing decision EVENT boundary before applying wrong-instance mutations. New topology regression plus the current shared suite pass `83/83`, failures `0`, errors `0`. No rules or functional RTL changed.

- generator SHA256 `c50c2f8117ee6e73da76cae4c5a0fc46a3774b7c775d9bb62942ff8bcd4b837f`;
- generator test SHA256 `7115b6e56b433cd634d1ab887da3b6122625099e56017f8730cb4207154372a8`;
- delta report `outputs/server_source_bound_generator_decision_boundary_fix/report.json`, bytes `2869`, SHA256 `c10e8ceebeeca85e89f63f633270c738b7e57a4a02fb3e4fa7576c742f7c8dd7`.

## p36b release

Unique pickup ZIP:

`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p36b_semfp.zip`

- bytes `5942345`;
- SHA256 `0111176e62fca03a023bbd83098067191113bdc4a91a7bf5c7e0e37c3d288e0e`;
- command `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`;
- expected return `/home/panqs/ndp/simresult/r5_n4_0cc_p36b_semfp_r<epoch-ns>_<pid>_return.zip` plus adjacent `.sha256`;
- class `PERFORMANCE_DIAGNOSTIC_CANDIDATE`, `candidate_release=false`, `PACKAGE_READY_NOT_RUN`.

Local gates:

- one cheap aggregate, zero errors;
- one p36b final ZIP;
- deterministic double staging;
- 87 frozen installed payload members byte-equal; both SCA files identity-normalized equal;
- family audit PASS;
- typed source-bound v2 `14/14 PASS`: 6 positives and 8 negatives, including v80 wrong-instance and p34b X/Z;
- semantic fingerprint `127a2a92e6ef3ad9154114aa15ec5c39f69f6f13f1ac311ff9eadec3f34b21a5`, disposition `FIRST_USE_AUDITED`;
- post-sim core PASS;
- normal/preflight-fail/compile-fail/HUP/INT/TERM runner PASS with fixed simresult and unchanged NDP-root direct set;
- shared install-only runtime layout PASS;
- independent clean-extract first-fresh audit PASS and `upload_authorized=true`.

Receipts:

- final ZIP audit SHA256 `9c488a0c50dfa7a5aecb838aee24cae66203a30bedcad18818645041d9efbcee`;
- typed v2 source-bound report SHA256 `73f451155f3e91b5651138df73378676d26643707e21c81fe45f5269ca41b8fb`;
- first-fresh validation SHA256 `7e7cd5ea7e0ce3fbf0dcd6073dff27dbe0bd0b5abd619ccd67adfbacf02cfc3c`;
- combined machine report `outputs/conv_native_four_lane_0ccae916_p35c_return_p36b_successor/report.json`, bytes `6570`, SHA256 `9383888fa45f6c9c6b10fbf9a0a98b2533b06b5dcfb843c13325809679d44e11`.

## Storage rotation

- p35c moved to `tested` after formal return consumption.
- native pending is exactly p36b.
- concurrent serialized v81 and QAdd v54 pending packages were preserved.
- storage index SHA256 `b4b6d0aae7004bf041827921747d7fe59f9bfc49914cafaeec09e87a41374fb3`; audit PASS; counts pending/tested/superseded = `3/102/38`.

## Performance and claim boundary

Frozen config inversion remains:

- serialized occurrences `205,520,896`;
- native occurrences `51,380,224`;
- compute-occurrence reduction `4.0x`;
- maximum useful lane utilization `25% → 100%`.

These are unchanged config-derived receipts, not measured server performance or E4/E5. p36b remains c0 diagnostic-only; natural terminal, formal 320D and E3/E4/E5 require its formal server return and later continuous closure.

## Blocker delta and rule feedback

Closed:

- `B_CONV_NATIVE_P34B_UNKNOWN_ARM_PAYLOAD_PARSER_FAIL_OPEN`;
- `B_CONV_NATIVE_P35C_SECOND_UNDRIVEN_PAYLOAD_LEAF`;
- `B_SERVER_SOURCE_BOUND_MIXED_WRONG_INSTANCE_MUTATED_NONDECISION_BOUNDARY`.

Preserved:

- `B_CONV_NATIVE_POSTCLEAR_ARM_TOKEN_ADVANCE_OR_REPLAY_UNRESOLVED`;
- `B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN`;
- `B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN`;
- `B_CONV_NATIVE4_FORMAL_320D_UNPROVEN`;
- `B_CONV_NATIVE4_E3_E4_E5_UNPROVEN`.

`RULE_CONFIRMATION_WITH_NONSYNONYMOUS_SHARED_TOOL_DELTA`: current rules are sufficient and no public-rule delta is proposed. The exact-final typed gate worked as intended by blocking p36; the only non-synonymous change is the shared generator implementation/test repair above.
