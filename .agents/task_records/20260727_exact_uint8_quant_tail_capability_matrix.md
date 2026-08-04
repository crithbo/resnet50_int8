# P0-A exact UINT8 quant-tail capability matrix

Date: 2026-07-27  
Status: `PROPOSAL_VALID_NO_UNCONDITIONAL_PURE_CONFIG`

## RETURN_ANALYSIS

The shared tail cannot yet be represented as one unconditional stock-RTL
pure-configuration capability.

Directly reusable parts are:

- raw FP32 GA ingress with all conversion flags disabled;
- the trusted `quant_from_buffer` LC/MSE/Buffer and two-PE GA topology;
- eight per-lane IEEE-754 constants and raw INT32 constants;
- GA outport saturation (`negative -> 0`, decoded bits 30:8 nonzero -> 255,
  otherwise low byte);
- the generic content-addressed typed-value envelope.

Independent gaps remain:

- QuantizeLinear requires exact float32 division, not merely a reciprocal
  constant and FMA;
- signed INT32 ingress is contradicted by the existing `-1` conversion;
- the magic-round recipe must preserve a software-visible multiply rounding
  point;
- the magic decoder needs a finite scaled-domain bound;
- target shape/layout, handler qparam binding, mapper registration and execplan
  replay are absent.

The first hardware capability unknown is the GA MAC rounding boundary. For
`int32=400`, multiplier bits `0x3d828f5c` and zero-point 0, the required
sequential FP32 multiply then nearest-even result is 26, while a correctly
rounded one-step fused multiply-plus-magic model returns 25. This vector should
be used before any shape or mapper work.

## Pure-configuration decision

`NO_UNCONDITIONAL_PURE_CONFIG_PROVEN`.

A conditional new recipe is plausible:

1. perform scaling with the contract-required explicit float32 rounding point;
2. add fixed FP32 magic `12582912.0`;
3. subtract raw `0x4b400000 - zero_point`;
4. reuse GA outport UINT8 saturation.

When scaling and magic addition must be separate, the proposed topology is a
three-PE, four-lane chain ending on an even GA column. A two-PE, eight-lane
chain is only valid when its input is already exactly pre-scaled. Neither
candidate is released: topology, range, handler, mapper and materialized
transport proofs are still missing.

## Counterexamples

- Odd zero-point tie: scaled `0.5`, zp `1`; expected 1, putting zp in the magic
  bias returns 2, while putting zp in the subtract constant returns 1.
- FMA contraction: `400 * float32(0.06375)`; sequential result 26, fused magic
  model 25.
- FP32 Quantize division: node0074 scale, input bits `0x3d0f81f1`; divide then
  RNE returns 2, reciprocal-FMA magic returns 1.
- Signed ingress: INT32 `-1` should convert to `0xbf800000`, current static RTL
  evidence gives `0xcf000000`.
- Magic range: scaled `-12582913`, zp 0; expected saturation 0, magic decode
  followed by the stock saturator returns 255.

## RULE_DELTA_PROPOSAL

- `CDA-QUANT-TAIL-NUMERIC-ORDER-001`: preserve every explicit float32 scaling
  rounding point; forbid FMA contraction without bounded-domain equivalence.
- `CDA-QUANT-TAIL-ZP-AFTER-ROUND-001`: add zero-point after RNE; with magic
  decoding, keep the FP32 bias fixed and adjust the raw subtract constant.
- `CDA-QUANT-TAIL-MAGIC-DOMAIN-001`: prove finite scaled bounds and saturation
  edges for every magic-round instance.
- `CDA-QUANT-TAIL-CAPABILITY-MATRIX-001`: ingress, signed domain, qparams,
  rounding, saturation, topology, layout, handler, mapper and execplan are
  independent release cells.

## BLOCKER_DELTA

Propose adding:

- `B_QUANT_TAIL_FMA_ROUNDING_POINT`
- `B_QUANT_TAIL_MAGIC_DOMAIN_BOUND`
- `B_QUANT_TAIL_EXACT_FP32_DIVISION`
- `B_QUANT_TAIL_SIGNED_INT32_INGRESS`
- `B_QUANT_TAIL_THREE_PE_TOPOLOGY`
- `B_QUANT_TAIL_TYPED_BINDING`
- `B_QUANT_TAIL_MAPPER_REGISTRATION`

Retain all existing Quantize/Requant layout, transport, fp32 ingress and
rounding blockers. Close none.

## Outputs and validation

- Contract:
  `contracts/operator_config/exact_uint8_quant_tail_capability_v1.json`
- Validator:
  `resnet50_pipeline/exact_uint8_quant_tail_capability.py`
- CLI:
  `tools/validate_exact_uint8_quant_tail_capability.py`
- Tests:
  `tests/test_exact_uint8_quant_tail_capability.py`
- Report:
  `artifacts/operator_config_validation/exact-uint8-quant-tail-capability-v1/report.json`

Validation result: five counterexample tests passed; 12 semantic source
identities matched and three historical read receipts were retained; 12
capability cells and five consumer classes were checked.

## Provenance/current-match integration correction

Mainline later changed `.agents/plan.md` from the generation-time SHA
`697b1b5d...616256e` to a new control-plane identity. The original validator
incorrectly treated that historical read receipt as a live semantic-source
lock, causing reproducibility to depend on every later mainline plan edit.

The contract now separates:

- `read_receipt`: immutable generation-time provenance for the plan, replan
  task record and reuse-gap audit. The validator reports current presence/hash
  and whether it still matches, but a later control-plane change is not a
  semantic failure and the recorded SHA is never rewritten;
- `semantic_source_identities`: the twelve current-match fail-closed inputs
  that actually determine quant-tail numerics or compiler/hardware capability,
  including typed qparams, lowering, Requant classification, trusted JSON
  oracles, encoder, handler, mapper and GA RTL consumers.

No RTL, mapper, qparam, handler, oracle or other semantic identity gate was
removed or weakened.

## Published specialty-rule binding

Mainline approved the four fail-closed proposals and published
`.agents/rules/精确UINT8量化尾专项规则.md` with SHA-256
`5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0`.
The capability contract now includes that rule in
`semantic_source_identities`, so any later semantic rule change fails closed.
The routing index SHA
`6ae4c7fe09fcdb39a48357cfef645c272f67e7a81d09b5547ebd9a929e6ce1a4`
is retained only as a historical `read_receipt`. The plan receipt remains the
original generation-time identity and was not refreshed.

No target JSON, mapping, bitstream, execplan, SCA or package was generated. No
server files were inspected and no server action occurred. Plan, public rules
and RTL were not modified.
