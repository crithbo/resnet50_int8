# 2026-08-06 Requant multiplier occurrence-supply proof

## Control

- family: `RequantizeUint8 / AverageRequant`
- unique mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- active rule:
  `CDA-REQUANT-PER-CHANNEL-MULTIPLIER-OCCURRENCE-SUPPLY-001`
- active Requant rule SHA256:
  `d2caeb55222f5b47585d890875e4d8f3f5c17d17a6849a93af4366e9f3447f99`
- task: prove or disprove exact payload bits/channel axis to every
  occurrence of `PE00.inport1`, including address,
  broadcast/serialization, and lifetime
- strict/backend/new operator JSON: `forbidden and not generated`
- mapping/bitstream/execplan/SCA: `forbidden and not generated`
- package/server/lease: `forbidden and not used`
- RTL/ISA/hardware/active ndp-sim changes: `forbidden and not made`
- accepted 5PE numeric graph recomputed: `false`

## Read receipts

| Path | SHA256 |
|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/plan.md` | `de7a956c8466b58004d14ffd66475c9cde8937e2cdb91184ce2b5d047160a6da` |
| `.agents/rules/生成前必读索引.md` | `3c0c9d5e836e2ea9cb7d697252fe2f46dfd5cce8facfdbd332d8bbd3d0fe48cc` |
| `.agents/rules/算子配置规则.md` | `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1` |
| `.agents/rules/RequantizeUint8算子配置规则.md` | `d2caeb55222f5b47585d890875e4d8f3f5c17d17a6849a93af4366e9f3447f99` |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` |
| `.agents/rules/最小双Stage生命周期规则.md` | `821b8b04b0e33d0a93e06a3a1bca8307b417bcb63f109cf12414891e9a0bc171` |
| `contracts/resnet50_r5_lowering_bundle.json` | `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432` |
| `contracts/operator_config/requant_quant_tail_evidence_input_v1.json` | `64aec997e9188ed69a0f0062dd9f66c5377d772fdc8b598dd1b8aa038a036f07` |
| `artifacts/reference_model/resnet50-v1-12-int8.onnx` | `c234f30975989788b4405f25253275aae247ab6dbdd34aaa69ab0a59ff76f6d0` |
| `ndp-sim/jsons/prefill_mul_fp32MN_fp32M_fp32MN.json` | `db66d5e8da6146eb743fe1006a6248daf040ba937d713a99f961c591325a272f` |
| `ndp-sim/address_remapping/src/address_remapping/registry.py` | `4bbd65d95ca19ba8f34abede68324e6b13883a91f3c66e7c2834b689feb8d6ab` |
| `ndp-sim/model_execplan/src/execution_plan_generator/control_registers.py` | `de296642364ddc1be2ca3f1163871c1098460d14bcb250290ebac4f5512bdc08` |

The plan is mutable provenance. All semantic conclusions below are
source/contract bound.

`ndp-sim` HEAD is
`ec12424516ae0304228dd2321d4e604fe225e04e`. The scoped current
`control_registers.py` and `operator_base_info.json` are modified
working-tree files. Their current bytes are recorded as current evidence
only and are not promoted to pinned upstream authority.

`Trassic2.0_RTL` HEAD is
`0ccae916ef61904a64d6cf8ec1d1931b45e428d8`. Exact source byte SHA and
Git blob receipts are in the machine report.

## Exact payload and axis proof

The proof driver parses the official ONNX protobuf directly. It does not
consume old candidate configs or server/package residue.

- parsed FP32 initializer count: 129
- covered Requant stages: 54/54
- reconstructed multiplier elements: 26,561
- reconstruction:
  `float32(float32(input_scale * weight_scale) / output_scale)`
- exact derived bytes are checked against both:
  - the typed lowering `value_sha256`
  - the accepted 54-stage evidence `multiplier_sha256`
- result: 54/54 exact payload hashes match

For each Conv stage:

- typed multiplier axis 0 is the output-channel vector
- bind native `M=C`
- bind native `N=batch*height*width`
- every Conv channel count is divisible by 8
- native tensor layout equation is:

```text
linear(n,h,w,c)
  = (c//8) * (N*H*W) * 8
    + ((n*H+h)*W+w) * 8
    + c%8
```

- multiplier payload layout is:

```text
payload_index(c) = c
address(c) = B_base + 4*c
```

This closes exact payload-bit inventory and channel-axis semantics. It
does not itself close physical supply.

## Native one-lane address/broadcast/lifetime capability

The registered primitive
`prefill_mul_fp32MN_fp32M_fp32MN` has:

- A logical axes `[M,N]`
- B logical axis `[M]`
- A physical linear order `[M_outer8,N,m8]`
- B physical linear order `[M_outer8,m8]`
- semantic operation `A[M,N] * B[M]`

The native JSON routes:

```text
stream1 target B
 -> buffer2 dst_port 1
 -> GA inport1
 -> PE inport1 mode=keep, keep_last_index=1
```

Therefore the current primitive proves:

- one 32-byte B transaction carries eight consecutive FP32 values
  `c=8*g..8*g+7`
- each selected PE receives one exact lane
- its inport keep-mode holds that lane across the native N loop
- the keep release predicate is source-bound to the current
  `GA_PE_Inbuffer.sv`

This closes only one-lane address and keep-lifetime capability within
the native eight-wide topology.

## Exact 5PE single-chain counterexample

The native template uses eight independent multiply PEs:

```text
GA index 0 -> PE00
GA index 1 -> PE10
GA index 2 -> PE20
GA index 3 -> PE30
GA index 4 -> PE02
GA index 5 -> PE12
GA index 6 -> PE22
GA index 7 -> PE32
```

The already accepted 5PE graph uses:

```text
PE00 multiply
PE01 clamp
PE10 magic
PE11 integer subtract
PE12 integer zero-point / uint8
```

For `hwop-0001-01`, the first two exact multiplier values are:

```text
channel 0 = 0x3a013ecf
channel 1 = 0x3925d60c
```

They are unequal. Under the unmodified native eight-wide transaction:

- channel 0 / lane 0 reaches `PE00.inport1`
- channel 1 / lane 1 reaches `PE10`, not `PE00.inport1`

But PE10 is the magic stage of the 5PE chain. Therefore the native
eight-wide primitive cannot be copied unchanged as the multiplier supply
for a single 5PE chain.

The current handler updates only:

- three IGA loop ends
- A stream stride
- B stream stride
- D stream stride

It does not update or define:

- B buffer spatial remapping
- B buffer spatial size
- GA inport1 lane mask/remap
- PE00 input1 lane source phase
- PE00 keep boundary per lane phase
- a lane-phase loop that serializes lanes 1..7 into PE00

Thus 53 Conv stages are fail-closed at:

`CONV53_MULTIPLIER_LANES_1_TO_7_NOT_SERIALIZED_TO_PE00_INPUT1`

This is not a proof that frozen hardware can never express a slower
configuration. It is an exact counterexample to the current existing
primitive/handler path and identifies the first missing configuration
capability. Backend generation is forbidden in this task, so no
speculative lane serializer is materialized.

## Scalar MatMul stage

`hwop-0075-01` has one scalar multiplier:

```text
exact bits = 0x3a510db3
```

Current RTL defines a 32-bit GA PE constant and exact constant capture
into the PE input buffer. A single constant therefore can supply every
`PE00.inport1` occurrence for this scalar stage.

Status:
`PROVEN_AT_RTL_CONSTANT_CAPTURE_EQUATION_LEVEL`

This closes only the scalar multiplier supply subleaf. It is not a
strict config, backend, physical E2, or dynamic claim.

## Machine result and validation

- report:
  `artifacts/operator_config_validation/requant_multiplier_occurrence_supply_v1/report.json`
- report SHA256:
  `ee54376962896214a2327aa5bb61fdb1d450e16521abe2f7d89326f5fea50f04`
- status:
  `EXACT_PAYLOAD_AND_SCALAR_SUPPLY_PROVEN__CONV53_PE00_LANE_SERIALIZATION_BLOCKED`
- structural errors: 0
- completion blockers: 1
- `blocked_valid=true`
- `pass=false`

Commands:

1. `python tools/prove_requant_multiplier_occurrence_supply_v1.py`
   - exit 0
2. `python -m unittest tests.test_requant_multiplier_occurrence_supply_v1 -v`
   - exit 0
   - 2/2 PASS
   - includes a tampered multiplier SHA negative control that fails
     payload identity closed

Assets:

| Path | SHA256 |
|---|---|
| `tools/prove_requant_multiplier_occurrence_supply_v1.py` | `ca299ac11be07436c6bbe272752c00d42dfe2f1ec94997ccda5791837eb0bfbe` |
| `tests/test_requant_multiplier_occurrence_supply_v1.py` | `db34438ebef0d7aa070611b56437f0e56cb978418519c721208c3c6306607221` |

## RETURN_ANALYSIS

- `EXACT_PAYLOAD_BITS=PROVEN_54_OF_54`
- `CHANNEL_AXIS_BINDING=PROVEN_53_CONV_PLUS_1_SCALAR`
- `NATIVE_ONE_LANE_ADDRESS=PROVEN`
- `NATIVE_ONE_LANE_BROADCAST_KEEP_LIFETIME=PROVEN`
- `MATMUL_SCALAR_PE00_CONSTANT_SUPPLY=PROVEN`
- `CONV53_ALL_CHANNEL_TO_PE00_SUPPLY=BLOCKED`
- `FAMILY_PHYSICAL_MULTIPLIER_SUPPLY=BLOCKED`
- `FORMAL_D=NONE`
- `OBSERVER=NONE`

## BLOCKER_DELTA

Close subleaves:

- `B_REQUANT_MULTIPLIER_EXACT_PAYLOAD_BITS_AND_CHANNEL_AXIS`
- `B_REQUANT_SCALAR_MULTIPLIER_PE00_CONSTANT_SUPPLY`
- `B_REQUANT_NATIVE_MULTIPLIER_ONE_LANE_ADDRESS_AND_KEEP_LIFETIME`

Keep open:

- `B_REQUANT_5PE_PHYSICAL_MULTIPLIER_SUPPLY`

Refined first break:

- `CONV53_MULTIPLIER_LANES_1_TO_7_NOT_SERIALIZED_TO_PE00_INPUT1`

## RULE_DELTA_PROPOSAL

`CONFIRMATION_NO_NEW_RULE`

The newly published occurrence-supply rule already distinguishes exact
inventory/one-lane capability from family-wide physical supply and
correctly requires this result to fail closed.

## PACKAGE_RELEASE

`NONE`

## Claim boundary

Read-only payload/source/consumer-equation proof only. No target JSON,
mapping, bitstream, execplan, SCA, strict/backend, physical E2, package,
server action, E3, E4, or E5 is created or claimed.
