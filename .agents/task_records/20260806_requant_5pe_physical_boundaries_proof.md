# 2026-08-06 Requant 5PE physical-boundary proof

## Control

- family: `RequantizeUint8 / AverageRequant`
- unique mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- dispatch: continue from the accepted full-INT32 numeric 5PE graph and prove only duplicate-breakpoint BST address, single-operator selector/tag/backpressure, and 54-stage multiplier supply
- numeric dependency recomputed: `false`
- mapping / bitstream / execplan / SCA / strict target JSON generated: `false`
- package / ZIP / server / lease action: `false`
- functional RTL / ISA / hardware / active ndp-sim modified: `false`

## Current read receipts

The plan is mutable provenance. Its start-of-work SHA was
`d45bd34c61d7dd4684d8d62312f67dba9d3c5ae10433686d0f5094a52f878e44`
and its final-check SHA was
`5bda83437a79370c28f50e7d443eb6086cb1a02bdc79e8037a438a7e5ae4d71f`.
No semantic conclusion is derived from plan text alone.

| Path | SHA256 |
|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/rules/生成前必读索引.md` | `3c0c9d5e836e2ea9cb7d697252fe2f46dfd5cce8facfdbd332d8bbd3d0fe48cc` |
| `.agents/rules/算子配置规则.md` | `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1` |
| `.agents/rules/RequantizeUint8算子配置规则.md` | `3eb5c2f8f50f73f9bb69ba7287f9274b5595dd5ce551df5fd8f25cfafef19f55` |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` |
| `.agents/rules/最小双Stage生命周期规则.md` | `821b8b04b0e33d0a93e06a3a1bca8307b417bcb63f109cf12414891e9a0bc171` |
| `.agents/task_records/20260806_slow_composite_quant_hard_block_requant_5pe_interim.md` | `8f6ada90707e410dd5368cf1fc75f28d42593f83e736b7f75e226010cc110b86` |
| `contracts/operator_config/requant_quant_tail_evidence_input_v1.json` | `64aec997e9188ed69a0f0062dd9f66c5377d772fdc8b598dd1b8aa038a036f07` |
| `contracts/resnet50_r5_lowering_bundle.json` | `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432` |

## Frozen accepted dependency

The already accepted full-INT32 numeric graph is consumed without
recomputation:

`mul -> 3-region clamp[-256,256] -> magic -> intsub -> integer zp -> uint8`

This record does not promote that graph to strict JSON, physical
materialization, local E2, E3, E4, or E5.

## Source identity

- `Trassic2.0_RTL` HEAD:
  `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`
- `ndp-sim` HEAD:
  `ec12424516ae0304228dd2321d4e604fe225e04e`
- All exact source SHA256, current byte blob, HEAD blob, and scoped
  working-tree status are captured in the machine report.
- The proof binds current disk bytes. In particular,
  `ndp-sim/model_execplan/src/execution_plan_generator/control_registers.py`
  is a scoped modified working-tree file with SHA256
  `de296642364ddc1be2ca3f1163871c1098460d14bcb250290ebac4f5512bdc08`;
  it is not promoted to upstream authority.

## Results

### Duplicate-breakpoint BST address: PROVEN

- Current `Binary_Search_Tree.sv` and `Comparator.sv` are source-bound.
- `GTET` is greater-than-or-equal, hence equality descends right.
- Sorted breakpoints:
  - ranks 0..31: `-256.0` (`0xc3800000`), 32 duplicates
  - ranks 32..64: `+256.0` (`0x43800000`), 33 duplicates
- Heap-order load uses rank sequence:
  `[32]`, `[16,48]`, `[8,24,40,56]`, then strides 8, 4, and 2,
  with lower/upper boundary ranks `[0,64]`.
- The only reachable coefficient addresses are:
  - `x < -256`: address 0
  - `-256 <= x < 256`: address 32
  - `x >= 256`: address 65
- Equality at both duplicate boundaries is checked.
- Current RTL focused test: 10/10 representative finite-binary32
  boundary cases pass.
- NaN/Inf behavior is not claimed; it is outside the already accepted
  finite stage-0 output domain.

### Single-operator selector/tag/backpressure: PROVEN at source-equation level

The 4x4 GA topology admits this 5PE chain:

`PE00 -> PE01 -> PE10 -> PE11 -> PE12`

With consumer inport 0, the exact source/destination identities are:

| Edge | Consumer source ID | Producer destination ID |
|---|---:|---:|
| PE00 -> PE01 | 4 (west) | 4 |
| PE01 -> PE10 | 3 (north-east) | 7 |
| PE10 -> PE11 | 4 (west) | 4 |
| PE11 -> PE12 | 4 (west) | 4 |

- The selected source transports its complete `{tag,data}`.
- The selected source receives the consumer backpressure.
- All unselected source returns are neutral `ready=1`.
- The producer AND-reduces its destinations; therefore one selected
  consumer carries the exact pressure while unrelated destinations do
  not stall it.
- Terminal PE12 at `(row=1,col=2)` maps to outport 5, source 0; the
  terminal tag/mask and backpressure equation is proven.
- Current production RTL packed-array dynamic indexing is not directly
  elaborated by Icarus. The test is explicitly a current-source-anchor
  plus equivalent-equation test, not a production-module compilation or
  full dynamic/operator claim.

### 54-stage multiplier supply: PAYLOAD IDENTITY PROVEN, PHYSICAL SUPPLY BLOCKED

- Accepted evidence and lowering ordered IDs match exactly: 54/54.
- All 54 entries have valid shape/hash and finite-positive min/max.
- Total multiplier elements: 26,561.
- Shape histogram:
  - scalar: 1 stage
  - 64: 7 stages
  - 128: 8 stages
  - 256: 16 stages
  - 512: 11 stages
  - 1024: 7 stages
  - 2048: 4 stages
- 53/54 stages have `minimum != maximum`, proving at least two distinct
  per-channel values in each such stage.
- The existing
  `prefill_mul_fp32MN_fp32M_fp32MN` primitive is registered, but its
  current execplan control handler is a placeholder.
- `quant_from_buffer_int32MN_uint8MN` is absent from the address-remap
  registry and its control handler is also a placeholder.
- No current typed consumer equation binds exact multiplier bits and
  channel axis to PE00 input1 for every sample/spatial occurrence,
  including address, broadcast/serialization, and lifetime.

Minimal fail-closed counterexample:

- `hwop-0001-01` requires 64 multiplier values.
- Its accepted minimum is `3.840008033773046e-10`; maximum is
  `0.001863094512373209`.
- A single fixed PE constant cannot supply both values. A stream may be
  a viable existing primitive, but cannot be assumed until its exact
  occurrence/address/lifetime binding is proven.

## Validation

Machine report:

- path:
  `artifacts/operator_config_validation/requant_5pe_physical_boundaries_v1/report.json`
- SHA256:
  `0daab3582284b338c09072f81bcb7d5e3fcde8dc1917ad1d99dadcee84efc2a1`
- status:
  `BST_AND_SINGLE_OPERATOR_ROUTE_PROVEN__54_STAGE_MULTIPLIER_PHYSICAL_SUPPLY_BLOCKED`
- structural errors: 0
- completion blockers: 1
- `blocked_valid=true`
- `pass=false`

Commands:

1. `python tools/prove_requant_5pe_physical_boundaries_v1.py`
   - exit code: 0
   - BST RTL test: PASS, 10 checks
   - selector source-bound equation test: PASS
2. `python -m unittest tests.test_requant_5pe_physical_boundaries_v1 -v`
   - exit code: 0
   - result: 1/1 PASS

Materialized proof assets:

| Path | SHA256 |
|---|---|
| `tools/prove_requant_5pe_physical_boundaries_v1.py` | `f2df745cdf5c1d56540b29ad5188f8ab828fa5d9d17e723ac80e15054408208d` |
| `tests/test_requant_5pe_physical_boundaries_v1.py` | `64737258dc79c98c98b3639d8c830a566634606b1176c934c9869546906f43db` |
| `tests/rtl/requant_sfu_duplicate_breakpoint_bst_tb.sv` | `799693b1bef9af83d6d2faa1552b69de666bab007fae7aa24a34fcf2749ffc3b` |
| `tests/rtl/requant_5pe_selector_backpressure_tb.sv` | `8392e49dca5250a385bbb1a503ddf66438b028bdb530448965410915e74aea2f` |

## Structured return

### RETURN_ANALYSIS

- `BST_DUPLICATE_BREAKPOINT_ADDRESS=PROVEN`
- `SINGLE_OPERATOR_SELECTOR_TAG_BACKPRESSURE=PROVEN_SOURCE_EQUATION_LEVEL`
- `MULTIPLIER_PAYLOAD_IDENTITY=PROVEN_54_OF_54`
- `MULTIPLIER_PHYSICAL_OCCURRENCE_SUPPLY=BLOCKED`
- `STRICT_OR_PHYSICAL_OPERATOR=NOT_PROVEN`
- `FORMAL_D=NONE`
- `OBSERVER=NONE`

### BLOCKER_DELTA

- close subleaf:
  `B_REQUANT_5PE_DUPLICATE_BREAKPOINT_BST_ADDRESS`
- close subleaf:
  `B_REQUANT_5PE_SINGLE_OPERATOR_SELECTOR_TAG_BACKPRESSURE`
- keep open/refine:
  `B_REQUANT_5PE_PHYSICAL_MULTIPLIER_SUPPLY`
- aggregate:
  `B_REQUANT_5PE_PHYSICAL_BST_SELECTOR_TAG_BACKPRESSURE_MULTIPLIER_SUPPLY`
  remains open, narrowed to multiplier supply only
- keep all pre-existing strict, typed materialization, terminal,
  dynamic, E4, and E5 blockers

### RULE_DELTA_PROPOSAL

Proposed non-synonymous ID:
`CDA-REQUANT-PER-CHANNEL-MULTIPLIER-OCCURRENCE-SUPPLY-001`

Per-channel multiplier availability requires exact payload-bit and
channel-axis binding to every materialized consumer occurrence,
including address, broadcast or serialization, and lifetime.
Hash/min/max/count evidence, registry presence, or a placeholder handler
alone must not be promoted to physical supply.

### PACKAGE_RELEASE

`NONE`

## Claim boundary

This is a read-only source-equation and focused RTL proof. It produces
no target configuration or execution asset and does not claim strict
JSON, mapping, bitstream, execplan, SCA, local physical E2, E3, E4, or
E5. The accepted numeric 5PE dependency is unchanged.
