# Complete-JSON slow-composite authorization

Date: 2026-08-06

User decision:

- `HARDWARE_CHANGE_FORBIDDEN`
- hardware/ISA/functional RTL design branch rejected
- only `EXISTING_PRIMITIVE_SLOW_COMPOSITE_PROOF` is authorized

This supersedes
`WAIT_USER_DECISION_HARDWARE_ISA_OR_SLOW_COMPOSITE_PROOF`.

## Authorized scope

The whole-network convergence optimizer may work only in its isolated worktree
to prove whether existing primitives can form exact mathematical, typed,
topological, address, and lifetime-correct composite paths.

Dependency order:

1. RequantizeUint8 / QuantizeLinear shared tail;
2. QLinearAddUint8;
3. ConvInt32Accumulate.

Any unprovable path must remain fail closed with its exact counterexample.
Approximate arithmetic must not be promoted to exact semantics.

## Forbidden scope

- functional RTL, ISA, or hardware modification;
- active `ndp-sim` modification;
- mapping, bitstream, execplan, or SCA generation;
- package/ZIP generation or modification;
- server inspection, upload, run, or lease;
- host internal tensor replay;
- natural-terminal, formal-D, E3, E4, or E5 promotion.

Existing packages, current configurations, dynamic return analyses, and family
release states remain independent and unchanged by this proof authorization.
