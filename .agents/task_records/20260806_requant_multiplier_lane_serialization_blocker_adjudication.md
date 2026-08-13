# Requant multiplier lane-serialization blocker adjudication

Date: 2026-08-06

Status:
`EXACT_PAYLOAD_AND_SCALAR_SUPPLY_PROVEN__CONV53_PE00_LANE_SERIALIZATION_BLOCKED`

## Evidence

Machine report:

`artifacts/operator_config_validation/requant_multiplier_occurrence_supply_v1/report.json`

- bytes: `76194`
- SHA256:
  `ee54376962896214a2327aa5bb61fdb1d450e16521abe2f7d89326f5fea50f04`
- structural errors: `0`
- completion blockers: `1`
- `blocked_valid=true`
- `pass=false`

Owner proof record SHA256:
`13c32b54e16bc38e21f071ddf33dd42307bd1d570c1de6c11432ba5060b02f4d`

Validation:

- proof tool exit `0`
- focused unittests `2/2 PASS`
- tampered-payload SHA negative fails closed
- deterministic rerun report SHA unchanged

## Closed subleaves

Exact payload bits are proven for `54/54` stages. The proof parses 129 official
ONNX FP32 initializers and reconstructs all 26,561 multiplier elements using
the sequential float32 formula. Every computed byte SHA matches both the
lowering `value_sha256` and accepted multiplier evidence SHA.

Channel-axis binding is proven:

- Conv axis 0 is output C;
- native M=C and N=batch×H×W;
- all C values are divisible by 8;
- native A layout is `[M_outer8,N,m8]`;
- native B layout is `[M_outer8,m8]`;
- B[M] broadcasts across N;
- one-lane address is `B_base + 4*c`;
- PE keep lifetime is source-equation proven.

MatMul `hwop-0075-01` has exact scalar bits `0x3a510db3`; the current 32-bit GA
constant capture can persist for all PE00 input1 scalar occurrences.

## Refined first break

`B_REQUANT_CONV53_MULTIPLIER_LANES_1_TO_7_NOT_SERIALIZED_TO_PE00_INPUT1`

For `hwop-0001-01`:

- channel 0 multiplier `0x3a013ecf` maps native lane 0 to PE00;
- channel 1 multiplier `0x3925d60c` maps native lane 1 to PE10;
- the 5PE graph consumes multiplier only at PE00;
- PE10 is already reserved for the magic step;
- the native eight-wide route maps lanes 0 through 7 to
  `PE00,PE10,PE20,PE30,PE02,PE12,PE22,PE32`.

The current handler changes IGA loop ends and A/B/D strides only. It emits no
B buffer-spatial remap/size, GA inport1 lane remap/mask, PE00 lane-phase/keep
boundary, or lane-phase loop capable of serializing lanes 1 through 7 into
PE00.

This proves the current primitive/handler is contradicted for a single 5PE
chain. It does not prove frozen hardware can never express a slower
configuration.

## Next authorized proof

Under the user's hardware-frozen B-only decision, the next task may only prove
or disprove whether existing hardware fields can express lane-phase
serialization into PE00. It must stay in the isolated worktree and remain
source/config-equation proof.

No target strict JSON, mapping, bitstream, execplan, SCA, backend physical E2,
ZIP/package, server action, functional RTL, ISA, hardware, active `ndp-sim`,
formal D, observer, E3, E4, or E5 is authorized.

`RULE_DELTA_PROPOSAL=NONE`; the current occurrence-supply rule already enforces
this fail-closed distinction.
