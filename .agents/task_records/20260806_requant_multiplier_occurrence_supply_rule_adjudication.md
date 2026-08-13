# Requant multiplier occurrence-supply rule adjudication

Date: 2026-08-06

Status:
`BST_AND_SINGLE_OPERATOR_ROUTE_PROVEN__54_STAGE_MULTIPLIER_PHYSICAL_SUPPLY_BLOCKED`

## Evidence

Machine report:

`artifacts/operator_config_validation/requant_5pe_physical_boundaries_v1/report.json`

- report SHA256:
  `0daab3582284b338c09072f81bcb7d5e3fcde8dc1917ad1d99dadcee84efc2a1`
- `structural_errors=0`
- `completion_blockers=1`
- `blocked_valid=true`
- `pass=false`

Owner proof record SHA256:
`b840ad28f80987f1ca45aad8bc6f33dc65d96dc864538bd743bbd7dcbf9bc2c8`

## Closed boundaries

Duplicate-breakpoint BST semantics are source-bound and proven:

- ranks 0 through 31: `-256` / `0xc3800000`
- ranks 32 through 64: `+256` / `0x43800000`
- upper-bound equality dispatches right
- reachable coefficient addresses: `{0,32,65}`
- focused finite FP32 RTL cases: `10/10 PASS`

The single-operator 5PE route is proven at current-source equation level:

- chain: `PE00 → PE01 → PE10 → PE11 → PE12`
- consumer source / producer destination selectors:
  `4/4, 3/7, 4/4, 4/4`
- selected `{tag,data}` and consumer backpressure are preserved
- unselected sources remain ready
- terminal route: `PE12(row1,col2) → outport5/src0`

The result is source-equation proof, not a production-module compile claim for
the packed dynamic-index implementation.

Multiplier payload inventory is also proven for `54/54` stages:

- total elements: `26561`
- scalar stages: `1`
- 64 elements: `7`
- 128 elements: `8`
- 256 elements: `16`
- 512 elements: `11`
- 1024 elements: `7`
- 2048 elements: `4`
- `53/54` stages have `min != max`

## Remaining blocker

`B_REQUANT_5PE_PHYSICAL_MULTIPLIER_SUPPLY`

Current registered primitives and placeholder handlers do not bind exact
payload bits and channel axis to PE00 input1 for every sample/spatial
occurrence, including address, broadcast/serialization, and lifetime.

`hwop-0001-01` is the permanent scalar-constant negative control: its 64
multipliers range from `3.840008033773046e-10` to
`0.001863094512373209`, so one fixed PE constant cannot supply the tensor.

## Rule publication

Published rule ID:
`CDA-REQUANT-PER-CHANNEL-MULTIPLIER-OCCURRENCE-SUPPLY-001`

Rule file:
`.agents/rules/RequantizeUint8算子配置规则.md`

- bytes: `39624`
- SHA256:
  `d2caeb55222f5b47585d890875e4d8f3f5c17d17a6849a93af4366e9f3447f99`

The rule requires exact payload-bit/channel-axis binding to every materialized
consumer occurrence, with address, broadcast/serialization, and lifetime.
Hash/count/shape/min/max, registry presence, or a placeholder handler cannot
prove supply.

## Validation and boundary

- proof tool: exit `0`
- focused unittest: `1/1 PASS`
- deterministic rerun report SHA: unchanged
- `py_compile`: PASS
- `git diff --check`: PASS

Strict JSON, typed materialization, mapping, bitstream, execplan, SCA,
ZIP/package, server action, functional RTL, ISA, hardware, active `ndp-sim`,
natural terminal, formal D, E3, E4, and E5 remain unchanged.
