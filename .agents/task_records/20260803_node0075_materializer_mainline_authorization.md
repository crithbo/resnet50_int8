# node0075 QLinearMatMul materializer mainline authorization

## Provenance

- user authorization: `2026-08-03`
- mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- owner: Conv/SA/MatMul task
  `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- dispatch plan SHA256:
  `dbd88421ff90e4f15bb919cbd1f8fdb7f88917e6af5de232253a20405162080b`

## Priority

Complete the active node0004 v26 RETURN→successor closure without losing its
evidence, then make node0075 the next highest-priority implementation task.
Do not expand the remaining 52 Conv instances first.

## Authorized implementation scope

The owner may add or modify family-scoped non-RTL assets needed for:

- `MatMulInt32Accumulate` / `QLinearMatMul` op-json schema or template;
- handler and registry entries;
- node0075 consumer materializer;
- family-scoped builders, validators, tests, contracts and reports;
- deterministic target JSON, mapping, bitstream, execplan and SCA;
- config-bound local E2 and, only after E2, a diagnostic server package.

The owner may not modify `.agents/plan.md`, public/specialized rules,
functional RTL or another family's assets.

## Frozen identity-fusion input

Consume without recomputation:

- `contracts/operator_config/quantize_node0074_dq_view_q_identity_fusion_v1.json`
- `contracts/operator_config/node0071_node0075_uint8_identity_alias_integration_v1.json`

The approved frozen-chain rewrite removes node0072 and node0074 arithmetic and
aliases node0071-owned UINT8 storage to node0075 A. The generic exact-divider
blockers remain open outside this frozen path.

The node0075 A consumer must bind:

- 16 producer-owned slice bases;
- 2,048 bytes per slice;
- 64 ordered 32-byte transactions per slice;
- 32,768 total bytes;
- exact consumer occurrence and accepted-read coverage/order;
- producer completion/visibility barrier;
- accepted lifetime and release/no-replay witness.

Producer base addresses cannot be reported as consumer acceptance evidence.
Copy, relocation, host replay or host precomputation is forbidden.

## node0075-owned computation

The materialization must also bind node0075:

- B/weight input and exact rank-2 layout;
- bias/initial psum;
- INT8 SA accumulate;
- output requant with zero-point `60`;
- final D endpoint and formal readback.

The report must distinguish primitives reused from the frozen node0004
serialized route from node0075-specific missing capabilities. If stock RTL can
only use the one-nonzero-product-lane serialized fallback, it may be used for
a correctness diagnostic candidate with its approximately fourfold
occurrence/traffic cost and non-production boundary recorded. It is not a
family-wide performance release.

If the rank-2 layout, tail, handler, mapper or consumer endpoint cannot be
legally materialized, stop at the first exact missing leaf and do not create a
false package.

## Release sequence

1. local contract, handler, registry and materializer;
2. deterministic final target JSON→mapping→bitstream→execplan/SCA;
3. config-bound local E2;
4. only after E2, fresh
   `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / candidate_release=false` package;
5. current final-ZIP self-audit and proactive completion notification.

No server upload, run or lease is authorized. The owner must return exact
artifact identities, blocker delta, and an evidence-backed
`RULE_CONFIRMATION` or `RULE_DELTA_PROPOSAL`.
