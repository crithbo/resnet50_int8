# Requant lane-phase field proof and strict-materializer authorization

Date: 2026-08-06

Status:
`PROVEN_AT_EXISTING_HARDWARE_FIELD_EQUATION_LEVEL`

## Evidence

Machine report:

`artifacts/operator_config_validation/requant_lane_phase_serialization_isolated_v1/report.json`

- bytes: `46717`
- SHA256:
  `1fa2ad8e55be5e4d67e11b2001386dd8a92dafef61da6bb9883d8ea9a68c75ba`
- `pass=true`
- `errors=0`

Owner proof record SHA256:
`e8ed0c5d5a3caf12c22f510f750f091d6ef78057849196f4acb5bdb67e8c80d1`

Tool SHA256:
`b108f2dd80eb1fb68d0c5682972d92a28e770fd1f338319d6f9689b051284040`

Tests SHA256:
`09a991060d147ef458d7c96f0d665bb3336a65047a0ab73829b542e63f84c3b2`

Focused tests: `2/2 PASS`, including tampered scalar-template and
2^17-channel capacity fail-closed controls.

## Proven mechanism

Current fields can express Conv53 multiplier lane-phase serialization without
a dynamic lane mux:

1. for channel `c`, read exactly four bytes at `B_base + 4*c`;
2. use buffer2 column 0 with spatial stride `[0,1,2,3]` and spatial size `4`;
3. enable only buffer2 lane 0;
4. enable only GA inport1 lane 0;
5. route group1/source0 to PE00 input1;
6. retain B[c] with the existing PE00 keep behavior across the already-proven
   serialized occurrence loop;
7. use buffer validity, clear, and backpressure to load channel `c+1`.

Each former eight-wide channel group becomes eight scalar phases. Performance
has not been measured.

The proof composes exact pinned native evidence for four-byte scalar
memory-to-bank0-to-GA-lane0 transport and B/buffer2/inport1/PE00 keep with
current RD/WR buffer, request, buffer-manager, and GA inport equations.

All 53 Conv stages pass LC/index/stride/address capacity checks.
`(4*c) mod 16` is always one of `{0,4,8,12}`, so every four-byte payload fits
within one 16-byte beat.

The original channel1-to-PE10 counterexample remains valid for the native
eight-wide path; scalar phases avoid it rather than waive it.

## Blocker delta

Closed:

`B_REQUANT_CONV53_MULTIPLIER_LANES_1_TO_7_NOT_SERIALIZED_TO_PE00_INPUT1`

Opened:

- `B_REQUANT_CONV53_SCALAR_PHASE_STRICT_MATERIALIZATION`
- `B_REQUANT_CONV53_SCALAR_PHASE_BACKEND_AND_DYNAMIC_EXECUTION`

## Authorized next action

The next action is an isolated Requant strict-JSON materializer using the
proven scalar-phase mechanism, followed by the shared candidate and exact
family-set complete-JSON gates.

This is within the user's previously authorized hardware-frozen
existing-primitive B path. It remains restricted to local strict JSON.

The user-specified dependency order remains:

`Requant/Quant shared tail → QAdd → Conv`.

QAdd's isolated materializer must wait until the Requant strict complete-JSON
gate closes.

Backend binding, mapping, bitstream, execplan, SCA, package/ZIP, server action,
functional RTL, ISA, hardware, active `ndp-sim`, dynamic execution, formal D,
E3, E4, and E5 remain forbidden or unclaimed.

`RULE_DELTA_PROPOSAL=NONE`.
