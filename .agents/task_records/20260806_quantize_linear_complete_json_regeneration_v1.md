# QuantizeLinear full-family complete-JSON regeneration v1

Date: 2026-08-06  
Family: `quantize_linear`  
Delegation source: `019fd276-14c5-7800-94db-87ebfb9ce632`  
Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`  
Analysis owner provenance: `019fa2c0-572b-7f21-ac5a-96e773dde534`

## Outcome

`HARDWARE_OR_SEMANTIC_CAPABILITY_BLOCKED`.

The current lowering bundle contains exactly two `QuantizeLinear` stages and
the generated family set covers both exactly once:

- `hwop-0000-00`: FP32 `[16,3,224,224]` NCHW to UINT8, scale bits
  `0x3c98d99a`, zero point 114.
- `hwop-0074-00`: FP32 `[16,2048]` NC to UINT8, scale bits `0x3cbf57ec`,
  zero point 0.

They form two materialized-consumer signature classes. The pinned upstream
`quant_from_buffer_int32MN_uint8MN.json` is class A for its own unchanged
INT32 `[1,32,32]` source instance and class C for both FP32 targets. No direct
binary32 DIV opcode, target qparam transport, generic mapper registration,
target shape schedule, or address/lifetime materialization is proven.

No target strict JSON was materialized. `complete_json/manifest.json` is the
only file in `complete_json/`. The source JSON remains unchanged.

`hwop-0074-00` retains its frozen-instance `APPROVED_EQUIVALENT` boundary:
the paired Dequant/View/Quant arithmetic elimination means no Quant JSON is
needed on that frozen execution path. This does not close the generic
`EXACT_BINARY32_DIVIDE_RNE` family blocker.

## Current rule receipts

- `.agents/agent.md`: `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/rules/生成前必读索引.md`:
  `d3a82e82199eb005d0d477b7cc740d11c42cf5fa3bef4ac2b2573cc5bad26bb6`
- `.agents/rules/算子配置规则.md`:
  `52939b59f079721a9a8438e3d5297f42118eadb1f2c2a238e20bcca73a30a820`
- `.agents/rules/NDP硬件字段语义.md`:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- `.agents/rules/精确UINT8量化尾专项规则.md`:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- `contracts/operator_config/complete_json_generation_contract_v1.json`:
  `de2825cae9f892482cd8eb74a60ea9b409a7f8186516b7ac5a6c04344b10c746`
- shared candidate validator:
  `4e30018656afd41f3f7d89f2d56070986e2465fac59d41483ae40fbf8f4ec62f`
- shared family auditor:
  `baa932a47a73e03746d1700015176cdeb21ac8c1c2b12d96929d0a1e9553fe82`

The generation-time plan read receipt is
`325be21aec6d57880c08a4e5f50d9effb83a8ad5e0e9c6bb579b175dc0e4e021`.
Plan is mutable provenance only; later control-plane changes are intentionally
not chased into the semantic current-match gate. This task did not modify it.

Relevant rule IDs:

- `CDA-NATIVE-REFERENCE-FIELD-APPLICABILITY-001`
- `CDA-NATIVE-HANDLER-CAPABILITY-MATRIX-001`
- `CDA-NATIVE-COMPOSITION-BOUNDARY-001`
- `CDA-CONFIG-SEMANTIC-OWNERSHIP-001`
- `CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001`
- `CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001`
- `CDA-REUSE-FIRST-DEFERRED-RETEST-001`
- `CDA-QUANT-TAIL-NUMERIC-ORDER-001`
- `CDA-QUANT-TAIL-ZP-AFTER-ROUND-001`
- `CDA-QUANT-TAIL-CAPABILITY-MATRIX-001`

## Native authority and leaf accounting

Pinned source:

- path: `ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json`
- repository commit: `ec12424516ae0304228dd2321d4e604fe225e04e`
- blob OID: `959e759e81eea358f52680c091f2dfa1535f564d`
- file SHA-256:
  `db638f0640e74217e80e61350a2fe400f7b495e2201f17c39915328cdd455ba2`
- primitive leaf count: 516

The family applicability ledger contains 1,032 records (516 leaves times two
stages): 1,016 unresolved and 16 primitive-only resolved. Those 16 records
only identify matching ingress-disable/output-pack primitives; they do not
authorize or materialize a target JSON.

The public blocked candidate contract for each stage binds the unchanged
source JSON only as a diagnostic leaf projection. Each public ledger has 516
entries and deliberately promotes none of them to FP32 target authority.
Per-stage shared-validator completion blockers:

- unresolved candidate leaf: 516
- unknown source-absent target field: 4
- unsupported handler axis: 6
- uncovered handler-dependent leaf: 516
- unresolved composition boundary: 1
- total: 1,043

The four explicit source-absent target fields are exact binary32 DIV opcode,
target scale transport, target shape schedule, and target addresses/lifetime.
They are `SOURCE_ABSENT_UNKNOWN_FOR_TARGET`; no implicit zero/null or nearest
template was used.

## Shared validator result

For both `hwop-0000-00` and `hwop-0074-00`:

- `candidate_status=BLOCKED`
- `contract_valid=true`
- `blocked_valid=true`
- `pass=false`
- `errors=[]`
- `completion_blockers=1043`
- `forbidden_server_package_outputs=[]`

Shared candidate CLI exits 1 by design because only a complete candidate has
`pass=true`. The family-set auditor also exits 1 because both covered
candidates remain blocked. It nevertheless proves:

- expected stage count: 2
- covered stage count: 2
- missing stage IDs: none
- unexpected stage IDs: none
- each candidate binds `target_hw_op_types=["QuantizeLinear"]` to the true
  lowering `hw_op_id/hw_op_type`
- no `no_config_stages` exemption was used

## Current tested configuration comparison

- `SAME`: the approved-equivalent node0074 logical result consumed by node0075
  remains UINT8 `[16,2048]`, 32,768 unique bytes for the first pass.
- `INTENTIONAL_DERIVATION`: node0074 Quantize JSON/config/execplan occurrence
  is omitted by the approved paired elimination. No node0000 Quantize package
  exists because current scoped operator packages begin from already
  quantized external UINT8.
- `SUSPECTED_CURRENT_DEFECT`: the native placeholder handler can overwrite
  `/stream_engine/stream2/dim_stride/1` from static 256 to 1024, historically
  yielding 256/1024 bytes of formal coverage per slice. This is a native
  handler materialization defect, not a defect in the current node0071-node0075
  package.
- `NEW_CANDIDATE_DEFECT`: none, because no target candidate was emitted.
- `DYNAMIC_ONLY`: producer completion/visibility, 8,192 accepted node0075 A
  events and hashes, natural terminal, and formal D remain dynamic-only.
- `CURRENT_ABSENT`: all 516 public source-projection leaves per stage, because
  no current target Quantize JSON exists.

No current server/package/observer/RTL blocker is attributed to a Quantize
configuration difference. The first generic blocker remains
`EXACT_BINARY32_DIVIDE_RNE`.

## Final commands

Python runtime:
`C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`

1. `python -m py_compile` for generator, builder, validator, and tests:
   exit 0.
2. `python tools/build_quantize_linear_complete_json_regeneration.py`:
   exit 0.
3. `python tools/validate_quantize_linear_complete_json_regeneration.py`:
   exit 0, local family validator PASS, errors 0.
4. Shared candidate validator for `hwop-0000-00`:
   exit 1, expected valid BLOCKED; errors 0.
5. Shared candidate validator for `hwop-0074-00`:
   exit 1, expected valid BLOCKED; errors 0.
6. Shared family-set auditor:
   exit 1, expected incomplete family; coverage 2/2, no missing/unexpected
   stages.
7. `python -m unittest tests.test_complete_operator_json_candidate
   tests.test_complete_operator_json_family_set`:
   exit 0, 11/11 PASS.
8. `python -m unittest
   tests.test_quantize_linear_complete_json_regeneration`:
   exit 0, 8/8 PASS, including unresolved-origin and target-emission negative
   controls.
9. Artifact forbidden-output scan:
   exit 0, 21 files, forbidden count 0.

The first local shared-validator trial correctly rejected two absent fields
that were mislabeled `TARGET_REQUIRED_DERIVED`. They were corrected to
`SOURCE_ABSENT_UNKNOWN_FOR_TARGET`; no target value was added.

## Key artifacts

Root:
`artifacts/operator_config_validation/r5_complete_json_regeneration_v1/quantize_linear`

- `report.json`: 12,694 bytes,
  `00fbea90812f0173da7af975d38ecd90327110a1546e9140f8c1f7214ea7dc19`
- `validation_report.json`: 1,361 bytes,
  `77b096631c79ea5160cfd7eb984a9d166a3b1e32fe4e379dc324f40d11b292bc`
- `field_provenance_ledger.json`: 767,871 bytes,
  `0ac3c595fe450797ced8a27b6705eac1ccc6430a5fe9e4c25a8b029ad4de9b0c`
- `reference_applicability.json`: 4,347 bytes,
  `2431bf5579f165ff705c602e759aa643bbca0488b67cd3c55c7382000714c1ed`
- `handler_capability.json`: 2,250 bytes,
  `59c89707aebdc77f0911bd9257550fce7a78348ec459a008143ef2b0594b5d11`
- `current_test_diff.json`: 2,471 bytes,
  `ee4db6bbb362c1ee7a40f018a8d5885ba204553fea5818440eb52279c6253ffa`
- `family_set.json`: 761 bytes,
  `eb3244499e5ffedc7913e111f453132a85014744833d148a42b33e1e5f8297f1`
- `family_set_audit_report.json`: 175,681 bytes,
  `10da03d084a70647763b9561d3ae811c1e6fd44f2bc9e901e141592eff6cfbe1`
- node0000 candidate contract: 1,731 bytes,
  `282dac0cf3e478ebc6215da9c2fe7de4912dc7d2389b1e59c6e4417cd100d322`
- node0000 shared validation report: 84,401 bytes,
  `a568a4946e5f7cf00674281164c78c9e64331ce5613bece1dee61e18270ec2ce`
- node0074 candidate contract: 1,731 bytes,
  `834f42c123ed7c713d7eed5496c60b6111afb1af8145463e7b9c000e7f2d19b5`
- node0074 shared validation report: 84,426 bytes,
  `751697764374ba23d6d77348ad9075ed71158a147f7d30fc74e52aa7c77f5823`

## Rule feedback and claim boundary

`RULE_CONFIRMATION`: the current native-reference applicability, handler
capability, composition-boundary, current-diff, and exact-tail rules correctly
force this family to stop. The refreshed shared BLOCKED adjudication correctly
separates structural errors from completion blockers. No non-synonymous rule
delta is required.

This work is static/local complete-JSON provenance and capability evidence
only. It is not a target JSON, mapping, bitstream, execplan, SCA, E2, E3, E4,
E5, server package, server upload, or server run. `PACKAGE_RELEASE=NONE`.
Numeric/W3/golden/Dequant/View primitive tests were not repeated. Existing
primitive/approved-equivalent evidence was consumed read-only. Functional RTL,
public rules, plan, current packages, and other family assets were not
modified.
