# Quantize node0074 Dequant/View/Quant identity-fusion adjudication

- Test ID: `r5-quantize-node0074-dq-view-q-identity-fusion-v1`
- Analysis owner thread: `019fa2c0-572b-7f21-ac5a-96e773dde534`
- Return target thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Date: 2026-08-03
- Status: `APPROVED_EQUIVALENT_WAIT_INTEGRATION_OWNER`
- Reuse class: `APPROVED_EQUIVALENT` for this frozen instance only
- Package release: `NONE` (`WAIT_INTEGRATION_OWNER`)

## Material passport

- Origin skill: `academic-research-suite/experiment-agent`
- Mode: `validate`
- Verification status: `VERIFIED_LOCAL_STATIC_AND_NUMERIC`
- Version label: `v1`
- Evidence ceiling: deterministic typed-source and binary32 semantic proof plus a
  Quantize-owned integration handoff. This is not a generic divider, target,
  integrated E2, E3, E4, E5, or server result.

## Active-source receipts

`plan.md` is mutable provenance only. The semantic sources below are current-match
fail-closed inputs in the machine contract.

| Path | Bytes | SHA256 | Gate |
|---|---:|---|---|
| `.agents/agent.md` | 11097 | `aae402d48b82d026c5512c8a6a5d4c9ff9db4bcc6a94576cd618c168f3fd188e` | historical read receipt |
| `.agents/plan.md` | 23316 | `918b43a8ff1333f6535806cda5c75d2273fe2663ebbc5370e4ff53c4784a17b4` | mutable provenance only |
| `.agents/rules/生成前必读索引.md` | 7525 | `f768a870d19699c87b66b735a759d3212db6ad51aace30e3a6305b2521a708c8` | current match |
| `.agents/rules/算子配置规则.md` | 18506 | `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171` | current match |
| `.agents/rules/NDP硬件字段语义.md` | 14974 | `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055` | current match |
| `.agents/rules/Flatten_View算子配置规则.md` | 3625 | `28ba3a92fecbb83149d494867429c34aa3124040a5c59fe99c4b9481feb3b7ee` | current match |
| `.agents/rules/DequantizeLinear算子配置规则.md` | 13919 | `f8cf7d2a041426f2b3348f3d02b570e3e559fe1a77c643a8393e77a2583e15a1` | current match |
| `.agents/rules/精确UINT8量化尾专项规则.md` | 9310 | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` | current match |
| `artifacts/reference_model/resnet50-v1-12-int8.onnx` | 25816052 | `c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0` | current match |
| `artifacts/w3/model_graph.json` | 339932 | `f030c5d4e43f63fbbcce771e4c4ea9e88b042be0a2c988e7f51de2c0e17ac410` | current match |
| `contracts/resnet50_r5_lowering_bundle.json` | 1971200 | `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432` | current match |
| `contracts/operator_config/quantize_node0074_exact_division_reuse_audit_v2.json` | 11622 | `7892b1dc2b54161ee2d5cab3c033d2a72bec19bbabaf269a38099674e2e45bdf` | current match |
| `contracts/operator_config/resnet50_node0071_node0072_shared_endpoint_v1.json` | 29431 | `9a832711eccd406d32ce802268889ecd67a9944a841d8cd8445af206ec93c2b0` | current match |
| `contracts/operator_config/stage_state_lifetime_contract_v1.json` | 244657 | `67f8e7758128a0dfea4b3faf2eab700b01b602ca052c3301fec967d6d2604744` | current match |

Applied rule IDs include
`CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001`,
`CDA-REUSE-FIRST-DEFERRED-RETEST-001`,
`CDA-CONFIG-MATERIALIZED-NONBASE-FIELD-OWNERSHIP-001`,
`CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001`, and
`CDA-QUANT-TAIL-RAW-SIGNED-GUARD-001`.

## BYPASS_ADJUDICATION

The frozen node0072 -> node0073 -> node0074 chain is
`APPROVED_EQUIVALENT`. This adjudication simultaneously removes node0072
Dequantize arithmetic and node0074 Quantize arithmetic. It replaces them with a
metadata-only UINT8 reshape/alias from node0071 D / node0072 A storage
`uint8[16,2048,1,1]` to node0075 A `uint8[16,2048]`.

The approval is not a general QuantizeLinear division capability. It uses no
host-precomputed scaled, rounded, saturated, or final tensor, and it does not use
REC/MUL as DIV. The original fp32 131072-byte node0072-D/node0073 endpoint is
explicitly excluded from the bypass storage.

## EXACT_EQUIVALENCE

The Dequantize input and Quantize output parameters are bitwise identical:

- scale: binary32 bits `0x3cbf57ec`, exact fraction
  `3134971/134217728`, value SHA256
  `a0da76078599a1809616c74430a869c573c530c8f89dec21191c963aadb321bc`;
- zero point: uint8 scalar 0, value SHA256
  `6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d`;
- axis: absent/null, per-tensor;
- node0075 A consumes uint8 `[16,2048]` with the same qdomain identifiers.

The validator evaluates all 256 legal uint8 values with exact-rational
implementations of binary32 round-to-nearest-even after multiply and divide:

- result mismatches: 0/256;
- noninteger exact unrounded quotients: 234/256;
- noninteger binary32 quotients: 50/256;
- maximum pre-division product-rounding error: `1/4194304`, at `u=224`;
- maximum unrounded quotient error: `32/3134971`, at `u=224`;
- maximum binary32 quotient error: `1/65536`, at `u=172`;
- minimum margin to the wrong nearest-even boundary: `32767/65536`;
- all 256 per-value records SHA256:
  `d074a345d23915884423ab5279e0f58d327ffec44b94dbea5d703910228fa59a`.

The complete per-value products, quotients, exact errors, binary32 bits, RNE
integers and clamped results are in the machine report.

## NEGATIVE_CONTROLS

Independent mutations of scale bits, zero point, dtype, quantization axis,
element order, byte strides/layout, and storage offset all fail closed. The
accepted `x_bits=0x406cefe0` REC/MUL counterexample remains bound without
retest: exact DIV produces 159 while reciprocal-MUL produces 158. It rejects a
generic divider substitution but is not on the paired-elimination execution
path.

## GRAPH_REWRITE_AND_ENDPOINT

The typed rewrite is closed:

- source tensor: `tensor-ab32f279540568c3`, uint8 `[16,2048,1,1]`;
- alias/consumer tensor: `tensor-6fbd5707d5f08110`, uint8 `[16,2048]`;
- element mapping: C-order `[n,c,0,0] -> [n,c]`;
- alias byte strides: `[2048,1]`;
- source storage ID:
  `r5:activation:node-0071:D:tensor-ab32f279540568c3:batch-slice-sharded-16x2048-v1`;
- 16 active slices, `base(slice)=0x000a2000+(slice_id<<25)`;
- 2048 bytes and 64 32-byte transactions per active slice;
- total valid coverage: 32768 bytes;
- producer ordered-address SHA256:
  `4d53305b6b1f2c48f8cf5043262f8866d5d82d2b207db9146ff09ab05ac38b2d`;
- producer written-byte-set SHA256:
  `3d900ae696639cb65053a0de41d9504e10bdbab3d7cbce764f94b06812f14d06`.

The final six consumer-owned endpoint fields remain null. This is intentional:
the current node0075 owner has not materialized A-port occurrence addresses,
read acceptance/coverage, the shared allocator alias overlay, the
node0071-completion-to-node0075-first-read barrier, or the release lifetime.
No provisional address is permitted.

Only the QuantizeLinear owner section of the canonical shared endpoint was
updated. DequantizeLinear and Flatten_View section hashes remain respectively
`e372f7b0fa434845a8199830c3c46a9467fc71d5687fa103750a86408191b371`
and `21e9f13fe422d7e6a6f4a0dae729380fc523c3030faad380d71d6ce6f9781d86`.
The canonical top-level cross-owner gate still carries the old
exact-division-on-path wording; changing it is outside Quantize ownership and
is included in the next-owner handoff.

## BLOCKER_DELTA

- `B_QUANT_NODE0074_EXACT_DIVISION`: remains open for the general family, but
  is no longer on the execution path of this frozen chain.
- `B_QUANT_TAIL_EXACT_FP32_DIVISION`: remains open for the shared general
  capability, but is no longer on this frozen chain's execution path.
- New first integration blocker:
  `B_QUANT_NODE0074_IDENTITY_FUSION_NODE0075_BINDING`,
  class `WAIT_INTEGRATION_OWNER`.

## RULE_DELTA_PROPOSAL

None. Current approved-equivalent, typed-edge, endpoint, lifetime, materialized
ownership and fail-closed rules already cover this adjudication.

## PACKAGE_RELEASE_OR_NEXT_OWNER_HANDOFF

`PACKAGE_RELEASE=NONE`, reason `WAIT_INTEGRATION_OWNER`.

Next owner: QLinearMatMul/integration allocator+execplan owner. Required patch:

1. Materialize the graph overlay that removes node0072/node0074 arithmetic and
   aliases node0071 D to node0075 A with the typed identity above.
2. Keep allocation ownership with `r5:hwop-0071-01:D`; do not relocate or copy.
3. Bind node0075 A occurrences to the exact 16 source slice bases and prove
   32768-byte read coverage with the producer byte-set/address hashes.
4. Bind first legal read after node0071 final D byte-set acceptance and
   completion/final barrier.
5. Keep the producer allocation live through node0075 final A input-data
   acceptance with no pending/replayed read; completion is the fallback release.
6. Update canonical top-level cross-owner gates/claim boundary without closing
   the two generic divider blockers.

## Artifacts

| Path | Bytes | SHA256 |
|---|---:|---|
| `resnet50_pipeline/quantize_node0074_identity_fusion.py` | 48972 | `ea597827fad0cfcdf941d07edab770c298a0b1adb9eb2735954ecbc6c1153a65` |
| `tools/build_quantize_node0074_identity_fusion.py` | 867 | `48c88486eec9cc6e45b638e299a87cd698334b29555e2c3649af95fd3919599f` |
| `tools/validate_quantize_node0074_identity_fusion.py` | 1104 | `c4ebe224adc287825bb09bc2d19c9fd7decc1d05b358f78d585a2d71212271d2` |
| `tests/test_quantize_node0074_identity_fusion.py` | 5172 | `fe54f45056a08f05920945cf04db76d4521295ac31df3fc36d983526329ee98b` |
| `contracts/operator_config/quantize_node0074_dq_view_q_identity_fusion_v1.json` | 22916 | `7f9dbfa7d92a70c310c04275ee7c1f90dfa763de975d68bf663d3f20cbc073db` |
| `contracts/operator_config/resnet50_node0072_node0074_shared_endpoint_v1.json` | 34551 | `04e3e6e7c5b27878cb021b653c1f6ec0df16b9a5530fdd11452bfe6eb2fcf89c` |
| `artifacts/operator_config_validation/r5-quantize-node0074-dq-view-q-identity-fusion-v1/report.json` | 188474 | `213ff272db06229451f2ccd5ca53c5533698dcfc8c28b14bf2cc189fe60ea8f8` |

## Reproducibility commands and exits

Python executable:
`C:\Users\15383\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`

1. `python tools/build_quantize_node0074_identity_fusion.py` -> exit 0.
2. `python tools/validate_quantize_node0074_identity_fusion.py` -> exit 0.
3. `python -m unittest tests.test_quantize_node0074_identity_fusion -v` ->
   exit 0, 10/10 tests passed. This suite includes all seven required negative
   controls and deterministic rerun equality for the 256-value proof.

## Accounting and mutation boundary

- New numeric analysis repeated: yes, exactly the independently required
  full-domain binary32 proof.
- Existing W3/golden tensor-value tests repeated: no.
- Existing Dequantize primitive tests repeated: no.
- Existing Flatten/View primitive tests repeated: no.
- Existing REC/MUL counterexample repeated: no.
- Reuse assets consumed: yes, typed graph/lowering, node0071 endpoint
  address/coverage, original lifetime gate and accepted counterexample.
- Functional RTL modified: no.
- Server files inspected: no.
- Server upload/run/lease: no.
- Target JSON/mapping/bitstream/execplan/SCA/package generated: no.
