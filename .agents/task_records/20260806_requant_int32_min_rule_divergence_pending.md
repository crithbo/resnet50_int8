# RequantizeUint8 INT32_MIN rule divergence pending

Date: 2026-08-06

Status: `RULE_DELTA_PROPOSAL_PENDING`

This record does not modify or supersede any public or specialized rule.

## Frozen hardware boundary

The user has permanently rejected hardware, ISA, functional RTL, and active
`ndp-sim` changes. Only an existing-primitive slow-composite proof remains
authorized.

The current local mirror of:

`NDP_copy01/rtl/Slice/General_Array/GA_Inport/GA_Inport.sv`

has:

- bytes: `26030`;
- SHA256:
  `2d27c3bc339c58c8335ae79a6341bec54d27694801c036a0af8099e29b2a18cb`.

Its live expression is:

`ga_inport_int32_min = ga_inport_int32_sign && lower_31_bits_are_zero`.

The expression identifies signed `0x80000000`, although the adjacent source
comment still says `0xFFFF_FFFF`. Functional adjudication must follow the live
equation, not the stale comment. The same source contains magnitude conversion
and guard/round/sticky ties-to-even logic.

## Suspected rule conflict

The current specialized RequantizeUint8 rule still treats the native
INT32-to-FP32 path as having a fixed negative-magnitude counterexample and
requires a guard path derived from that historical premise. This may be a
non-synonymous conflict with the current authoritative hardware lineage.

The finding is not yet sufficient to edit the rule. Before any rule delta, the
Requant owner must provide:

1. an exact repository, commit, blob SHA, source SHA, typed signature, and
   current-consumer receipt;
2. an exhaustive or mathematically complete signed 32-bit conversion proof;
3. directed receipts for zero, `-1`, `INT32_MIN`, positive/negative RNE ties,
   extrema, and exponent carry;
4. replay of every historical counterexample and classification of stale
   comments/contracts;
5. separation of INT32 ingress correctness from the still-open sequential
   multiply-RNE, zero-point, saturation, and magic-wrap tail capabilities.

Until those gates close, the old rule remains in force, no new capability is
claimed, and no current configuration, package, RTL, server action, natural
terminal, formal D, E3, E4, or E5 status changes.
