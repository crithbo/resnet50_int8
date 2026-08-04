# Conv node0004 v32 return → v33 physical LC18/PE7 diagnostic successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Route: serialized node0004 correctness only
- Status: `PACKAGE_READY_NOT_RUN`

## RETURN_ANALYSIS

The v32 return ZIP SHA is
`757c64ad8232e6dbad311eb29864c4c20f692c7585eec7e8d6156bbc100bfbed`.
The missing adjacent return sidecar is content-neutral only under
`CDA-SERVER-RETURN-TRANSPORT-USER-ATTESTED-NO-SIDECAR-001`.
CRC, root/path safety, duplicate/symlink rejection, RETURN_MANIFEST exact set,
allowlist per-file receipts, frozen source identity, package/install/observer
preflights, compile, run and signal gates all pass. Compile and run exit 0,
signal is `NONE`, and simulation reached the diagnostic `$finish`.

Natural DUT terminal is absent. Formal D is 0/320, therefore E3/E4/E5 all
remain false. `mismatch=0` is not treated as success when all 320 entries are
missing.

Qualified v32 counts are:

- MSE4 buffer-mode input1 fresh accept: 7
- all-index match / queue push / queue pop: 7 / 7 / 7
- WR_Memory_AG bias / transaction / finish: 7 / 7 / 7
- descriptor handshakes: 14 (exactly two per transaction)
- prepared groups: 16

All seven accepted indexes are conserved. The queue and WR address generator
are idle at the decision point while two prepared groups remain. Thus:

- `LAST_PROVEN_GOOD=MSE4_SEVENTH_BUFFER_INDEX_ACCEPT_MATCH_QUEUE_PUSH_POP_WR_AG_TRANSACTION_FINISH_AND_TWO_DESCRIPTOR_HANDSHAKES`
- `FIRST_DIVERGENCE=EXPECTED_EIGHTH_PE7_BUFFER_INDEX_OUTPUT_TO_MSE4_MEMORY_AG_IDX_QUEUE_INPUT1_ACCEPT`

The v32 return does not distinguish whether mapped LC18 fails to emit the
eighth value, mapped PE7 fails to accept/write/read it, or WRITE_STREAM0
input1 fails to accept a PE7 value. Logical LC9 `end=8` maps to physical LC18
`end=8`, so changing `end`, `keep_last_index`, or another configuration leaf
without the missing physical handshake evidence would be speculative.

The old
`B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED` remains
`INVALIDATED_NOT_RTL_BUG`.

## Successor

`r5_n4_hw_v33_lc18_pe7_diag.zip` is
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`, `candidate_release=false`.
It preserves the frozen workload, numeric payload, configuration, golden,
timeout, backpressure and functional RTL. The only new feature observes
qualified events across the actual mapped resources:

- logical `LC15 → physical LC17`
- logical `LC9 → physical LC18`
- logical `LC_PE.PE1 → physical PE7`
- logical `stream4 → physical WRITE_STREAM0`

The observer counts physical LC17 output, LC18 parent acceptance/output, PE7
inport0/inport2 capture, PE7 outbuffer write/read, and MSE4 input1 acceptance.
Raw valid/same, last/last_index, fanout backpressure and PE outbuffer count are
state corroboration only.

## Validation

Commands completed with exit 0:

1. `python tools/analyze_node0004_v32_return.py ...`
2. `python tools/build_node0004_v32_lc18_pe7_diag_package_v33.py`
3. `python tools/validate_node0004_v33_lc18_pe7_observer_scope.py ...`
4. `python tools/validate_node0004_v33_runner_controls.py ...`
5. `python tools/validate_node0004_v33_final_zip.py ...`

The focused HDL positive compile exits 0. Negative controls exit 1 for a
misspelled physical hierarchy, 4 for a deleted declaration, and 2 for broken
task syntax. Deleting a qualified counter update fails the semantic-closure
gate. Runner safe compile/EXIT and TERM finalizers behave as expected
(74/143); feature enable/limit/time0/return-target and canonical decision
negatives all fail closed.

Post-generation current-rule reread:

- `.agents/agent.md`
  `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`
- `.agents/rules/生成前必读索引.md`
  `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`
- `.agents/rules/服务器测试包生成规则.md`
  `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`
- `.agents/rules/算子配置规则.md`
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- `.agents/rules/NDP硬件字段语义.md`
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `.agents/rules/INT8_SA点积专项规则.md`
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

The plan moved only as mutable provenance after dispatch; no plan semantics
were copied into the package gate. Final audit reports
`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=[]`.

## PACKAGE_RELEASE

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v33_lc18_pe7_diag.zip`
- bytes: 5840529
- SHA256:
  `5094fc3e01a04c1931b81c4db3a67bf2f6b82f424124d0311866d03004997c90`
- sidecar SHA256:
  `a6b7b5bd22f3a2702892c4e92fd060ace3e10614c38dbc15d547dffd3464c8d3`
- command:
  `bash r5_n4_hw_v33_lc18_pe7_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- expected return:
  `r5_n4_hw_v33_lc18_pe7_diag_return.zip`

## BLOCKER_DELTA

- Closed:
  `B_CONV_NODE0004_MSE4_MEMORY_INDEX_QUEUE_AND_WR_AG_POST_ACCEPT_UNOBSERVED`
- Opened:
  `B_CONV_NODE0004_PHYSICAL_LC18_PE7_TO_MSE4_EIGHTH_BUFFER_INDEX_ACCEPT_UNOBSERVED`
- Preserved:
  `B_CONV_NODE0004_DYNAMIC_NATURAL_TERMINAL`,
  `B_CONV_NODE0004_FORMAL_D_320`

## RULE_CONFIRMATION

`CURRENT_RULES_SUFFICIENT`. The rules correctly separated user-attested
transport from internal receipts, required qualified transaction evidence,
forced return-to-successor closure, and required final-ZIP HDL/runner/feature
positive and negative controls. No non-synonymous public rule delta is needed.

No numeric/W3/workload/config/golden analysis was repeated; no functional RTL,
plan, or public rule was modified; no server action or lease occurred.
