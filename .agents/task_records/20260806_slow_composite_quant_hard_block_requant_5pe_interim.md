# Slow-composite interim: Quant hard block and Requant 5PE graph

Date: 2026-08-06

Owner task: `019fd276-14c5-7800-94db-87ebfb9ce632`

Status: `INTERIM_FAIL_CLOSED`

The current Requant signed-ingress rule SHA256
`3eb5c2f8f50f73f9bb69ba7287f9274b5595dd5ce551df5fd8f25cfafef19f55`
was consumed as authority. Only the signed-ingress primitive is closed.

## QuantizeLinear

For `hwop-0000-00`, fixed scale `0x3c98d99a` and zero point `114`, a
real-affine superset of the available SFU was used as an optimistic upper
bound. Adaptive exact transition/tie-envelope dynamic programming still
requires at least `82` coefficient segments, exceeding the current capacity
of `66` coefficients / `65` breakpoints.

A single reciprocal has `159` visible transition mismatches.

Therefore the existing-primitive slow-composite path for the Quant family is
`HARD_IMPOSSIBLE_UNDER_FROZEN_HARDWARE`. `hwop-0074-00` remains only
`NOT_PROVEN`, but that does not change the family result. Its previously
approved DQ→View→Q elimination route remains unchanged.

## RequantizeUint8

Using the proven current signed ingress, an exact full-INT32-domain numeric
graph has been established:

1. PE00 per-channel multiply;
2. PE01 three-region SFU clamp to `[-256, 256]`;
3. PE10 magic step;
4. PE11 integer subtract;
5. PE12 integer zero-point addition followed by UINT8 conversion.

This is not yet a strict JSON or physical capability claim. The remaining
proof obligations are:

- duplicate-breakpoint BST address semantics;
- single-operator selector, tag, and backpressure behavior;
- multiplier supply across all 54 stages.

The Requant owner has been reactivated to prove or disprove those exact
physical boundaries.

## Receipt and boundary

Interim proof report SHA256:
`9cc03b1f65621375c17d024baf568c0bd779f442dac29712f9526efddefb8ea5`

Direct tests: `6/6 PASS`

The exact report path and byte count remain pending the owner's final receipt.
No public/specialized rule, backend, active `ndp-sim`, RTL, ISA, hardware,
mapping, bitstream, execplan, SCA, ZIP/package, upload, server run, or lease
was changed or created by this interim adjudication.
