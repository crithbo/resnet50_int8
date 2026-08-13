# Four-family complete-JSON capability v2 mainline adjudication

Date: 2026-08-06

Source owner task: `019fd276-14c5-7800-94db-87ebfb9ce632`

Mainline task: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Result

`CAPABILITY_GAPS_REMAIN_FAIL_CLOSED`

The user-authorized isolated, hash-bound handler/materializer work reached the
first truthful hardware/ISA semantic boundary for all four previously blocked
families. It did not produce strict hardware JSON and did not fabricate a
configuration-only completion.

Pinned lowering:
`bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`.

Aggregate report:
`artifacts/operator_config_validation/r5_complete_json_capability_v2/report.json`
in the optimizer worktree.

Aggregate report bytes: `8028`

Aggregate report SHA256:
`ecae3f5a96485064544ce47b9541c07d46c79368b10f3f3d478fbc8be8ff023a`

Source task record bytes: `8701`

Source task record SHA256:
`46c8e631b83eddd7d007e63a32c93f4121c01a6e606a980481d4d19fd065b08d`

Validation: `31/31 PASS`, `py_compile PASS`, `git diff --check PASS`,
aggregate structural errors empty, and all four artifact roots contain no
forbidden mapping/bitstream/execplan/SCA/ZIP/server outputs.

## Family boundaries

- RequantizeUint8: exact scope `54/54`, 54 typed/address blueprints, strict
  JSON `0`. The missing capability is a family-wide proven signed INT32
  ingress plus sequential multiply then RNE plus integer-zero-point/saturation
  tail. Seventeen stages also retain a concrete magic-wrap counterexample.
- QLinearAddUint8: exact scope `17/17`, 17 logical and 102 physical typed
  plans, strict JSON `0`. Exact binary32 divide/RNE hardware consumption is
  absent, and the node0076 physical broadcast replay handler remains absent.
- ConvInt32Accumulate: exact scope `53/53`, 53 equation-derived plans and
  6,625 semantic leaves resolved, strict JSON `0`. The node0004
  assumed-fixed-hardware authorization cannot be generalized to the other 52
  stages; 615 strict hardware-surface leaves remain unauthorized.
- QuantizeLinear: exact scope `2/2`, strict JSON `0`. A finite binary32
  counterexample proves reciprocal multiplication is not exact division:
  input `0x406cefe0`, scale `0x3cbf57ec`, exact divide yields
  `0x431e8001` / UINT8 `159`, while reciprocal multiply yields
  `0x431e8000` / UINT8 `158`.

All four candidate/family contracts remain structurally valid legal BLOCKED
results. No family is promoted to COMPLETE.

## Mainline decision boundary

Reaching zero-UNRESOLVED strict hardware JSON now requires one new user
authorization:

1. isolated hardware/ISA capability design for exact division, signed INT32
   ingress/guard, sequential RNE/zero-point tail, and generic Conv SA
   semantics; or
2. a separate proof task for slower composite paths assembled from existing
   primitives.

Until that decision, no further value guessing is allowed. Current packages,
current configurations, active `ndp-sim`, functional RTL, natural-terminal
gates, formal-D conjunction, E3/E4/E5, and server execution state are
unchanged. No mapping, bitstream, execplan, SCA, ZIP, upload, run, or lease was
created by this adjudication.
