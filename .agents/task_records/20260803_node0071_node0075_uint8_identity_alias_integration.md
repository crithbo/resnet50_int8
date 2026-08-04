# node0071 D → node0075 A UINT8 identity-alias integration

- test_id: `r5-node0071-node0075-uint8-identity-alias-integration-v1`
- provenance owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- result: `ALIAS_OVERLAY_READY_EXECPLAN_BINDING_BLOCKED`
- wait state: `WAIT_NODE0075_MATERIALIZER_CAPABILITY`
- package release: `NONE`

## Input receipt

The integration consumed, without repeating the frozen binary32/W3/REC analysis:

- `quantize_node0074_dq_view_q_identity_fusion_v1.json`
  SHA256 `7f9dbfa7d92a70c310c04275ee7c1f90dfa763de975d68bf663d3f20cbc073db`
- its report SHA256
  `213ff272db06229451f2ccd5ca53c5533698dcfc8c28b14bf2cc189fe60ea8f8`
- its task record SHA256
  `3a63fd8b9403d35d5e8f76a89fd4faf812649f91767cfc71ebe59ffc3b0167f0`
- canonical node0072↔node0074 endpoint SHA256
  `04e3e6e7c5b27878cb021b653c1f6ec0df16b9a5530fdd11452bfe6eb2fcf89c`
- node0071↔node0072 endpoint SHA256
  `9a832711eccd406d32ce802268889ecd67a9944a841d8cd8445af206ec93c2b0`
- typed lowering bundle SHA256
  `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`
- stage config SHA256
  `79aa86fc958a2394c5161229378e490472bd5ea4273e40ea5d2139294038cf1e`
- lifetime contract SHA256
  `67f8e7758128a0dfea4b3faf2eab700b01b602ca052c3301fec967d6d2604744`

Current mutable plan receipt is
`160cfe7fb9fbc7d485081c2c8d7afbd7c02dafcbb324d418801c3a9cfc29b60c`.
All rule and source receipts are embedded in the generated contract/report.

## Materialized overlay

The approved paired elimination is represented as a metadata-only overlay:

- remove node0072 Dequant arithmetic and node0074 Quant arithmetic together;
- alias `tensor-ab32f279540568c3` `uint8[16,2048,1,1]` to
  `tensor-6fbd5707d5f08110` `uint8[16,2048]`;
- C-order map `[n,c,0,0] -> [n,c]`, byte strides `[2048,1]`, offset 0;
- preserve storage
  `r5:activation:node-0071:D:tensor-ab32f279540568c3:batch-slice-sharded-16x2048-v1`;
- preserve allocation owner `r5:hwop-0071-01:D`;
- no new allocation, relocation, copy, replay, host tensor, or legacy
  131072-byte FP32 endpoint.

This is a consumable graph/allocation requirement.  It is deliberately not
claimed as installed in the native execplan.

## Consumer address and lifetime adjudication

The required 16 slice bases are fully enumerated by
`0x000a2000 + (slice_id << 25)`, with 2048 bytes and 64×32-byte transactions
per slice.  Required total read coverage is 32768 bytes.  The frozen producer
hashes remain:

- ordered address:
  `4d53305b6b1f2c48f8cf5043262f8866d5d82d2b207db9146ff09ab05ac38b2d`
- written byte set:
  `3d900ae696639cb65053a0de41d9504e10bdbab3d7cbce764f94b06812f14d06`

Consumer occurrence addresses, consumer address/read-byte-set hashes and
accepted-read witnesses remain absent.  Producer base projection is explicitly
rejected as consumer proof.

The first legal read requirement is node0071 final D byte-set accepted plus
node0071 completion/final barrier accepted.  Release requires node0075 final A
input-data accepted and no pending/replayed read, conservatively node0075
completion if the former is not observable.  Those cross-operator witnesses
cannot be materialized before the consumer exists.

## First divergence

`B_MATMUL_NODE0075_FINAL_A_CONSUMER_MATERIALIZER_MISSING`

The typed request exists at
`contracts/resnet50_r5_lowering_bundle.json:50492`, and its effective resolution
at line 56518 has `json_emitter_ready=false`.  The stage remains blocked at
`contracts/operator_config/stage_config_system_v1.json:30973`; ordinal 129 is
`blocked_before_config_encoding` at
`contracts/operator_config/stage_state_lifetime_contract_v1.json:2980`.
The typed node0074→node0075 edge at line 7528 still says physical allocation is
blocked until address/offset/lifetime are bound.

The active native toolchain has neither
`op_json/MatMulInt32Accumulate.json` nor `op_json/QLinearMatMul.json`.
Its registry at
`ndp-sim/model_execplan/src/execution_plan_generator/control_registers.py:1774`
contains neither name, and lookup at line 1874 only invokes registered
handlers.  The pipeline reads `<op_type>.json` and raises on absence at
`ndp-sim/model_execplan/src/execution_plan_generator/pipeline.py:131`.

Therefore the first divergence is before a final node0075 A address equation,
mapping, bitstream, execplan/SCA or accepted terminal can exist.  It is a
materializer-capability blocker, not a newly demonstrated RTL first
divergence.

## Blocker delta and claim boundary

- `B_QUANT_NODE0074_IDENTITY_FUSION_NODE0075_BINDING`: remains open.
- Added precise sub-blocker:
  `B_MATMUL_NODE0075_FINAL_A_CONSUMER_MATERIALIZER_MISSING`.
- Generic exact-divider blockers remain open but are off this frozen path.
- node0075 SA/MatMul arithmetic, psum/tail, requant and E4/E5 blockers remain
  open downstream and were not retested.
- Canonical foreign owner sections and top-level gates were not modified.
- No target JSON, mapping, bitstream, execplan, SCA or server package exists.

Only after a registered node0075 materializer exists may the integration owner
install the overlay, invert every final A occurrence, prove exact consumer
coverage/order, bind accepted barriers/lifetime, and close only the identity
fusion endpoint blocker.

## Validation

Commands, both exit 0:

```text
<bundled-python> tools/validate_node0071_node0075_uint8_identity_alias_integration.py
<bundled-python> -m unittest tests.test_node0071_node0075_uint8_identity_alias_integration -v
```

The unittest suite ran 9 tests.  Six mutation controls all failed closed:
producer-base projection, allocation relocation, copy/host path, premature
coverage close, premature lifetime close, and foreign-owner write.

Accounting:

- `numeric_analysis_repeated=false`
- `binary32_domain_retested=false`
- `w3_retested=false`
- `node0075_workload_built=false`
- `consumed_reuse_assets=true`
- functional RTL, plan and public rules modified: false
- server inspected/uploaded/run/lease: false

`RULE_DELTA_PROPOSAL=NONE`; current rules already cover the boundary.
