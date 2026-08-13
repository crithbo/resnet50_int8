# RequantizeUint8 GA signed INT32-to-FP32 full-domain proof

Date: 2026-08-06

Status: `LIVE_GA_INT32_TO_FP32_FULL_DOMAIN_BIT_EXACT_PROVEN`

This is a read-only proof of one existing hardware primitive on one exact local
source identity. It does not edit or supersede a rule, and it does not promote
the RequantizeUint8/AverageRequant family-wide slow composite.

## Control and rule receipts

| Path | SHA256 | Role |
|---|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` | active agent contract |
| `.agents/plan.md` | `c073b82f87a7de9ed35ea39fcc8b802f813be08370d51e9a7aa6e58d3074c788` | mutable provenance only |
| `.agents/rules/生成前必读索引.md` | `3c0c9d5e836e2ea9cb7d697252fe2f46dfd5cce8facfdbd332d8bbd3d0fe48cc` | active routing |
| `.agents/rules/算子配置规则.md` | `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1` | public operator rule |
| `.agents/rules/RequantizeUint8算子配置规则.md` | `5fcd1c9d2f6fa6dd193e369412c46c16b7bd087b570cc607aa0d0f06ba4c7555` | family rule |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` | shared exact-tail rule |
| `.agents/rules/最小双Stage生命周期规则.md` | `821b8b04b0e33d0a93e06a3a1bca8307b417bcb63f109cf12414891e9a0bc171` | lifecycle rule |

The existing `RULE_DELTA_PROPOSAL_PENDING` record remains the rule-control
boundary. No `.agents/plan.md`, `.agents/rules/**`, functional RTL, ISA,
hardware, or active `ndp-sim` file was changed.

## Exact source and consumer receipt

Authoritative repository: `Trassic2.0_RTL`.

- local `HEAD` and `master`:
  `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`;
- `origin/master`:
  `e1fb0f7bb2761d6c804867de0c5d2cb77554c48d`;
- origin identity is recorded but is not promoted to the proven identity;
- working tree was clean;
- fix commit:
  `c81807554b5e39c040aeae39ffe30aa522f5f6ab`;
- source:
  `Trassic2.0_RTL/code/NDP_rtl/Slice/General_Array/GA_Inport/GA_Inport.sv`;
- Git blob:
  `59507fc7c2e7f156f46e1ee3d2d512465e1f1873`;
- bytes: `26030`;
- SHA256:
  `2d27c3bc339c58c8335ae79a6341bec54d27694801c036a0af8099e29b2a18cb`.

The read-only mirror
`NDP_copy01/rtl/Slice/General_Array/GA_Inport/GA_Inport.sv` is byte-identical
to that source. The executable minimum detector is `sign && lower31==0`, which
uniquely recognizes `0x80000000`. The adjacent `0xFFFF_FFFF` comment is stale
and is not semantic authority.

The machine report closes source/blob/SHA/size receipts for the conversion
source, `GA_Inport_Group_Config`, `GA_Inport_Group`, `General_Array`,
`GA_PE_Group_Interconnect`, the 32-bit width definition, LZD, barrel shifter,
CSA, and CLA dependencies. The current consumer chain is:

1. `GA_Inport_Group_Config` transports `ga_inport_int32tofp32`;
2. `GA_Inport` selects the converted data;
3. `GA_Inport_Group` preserves the 32-bit payload and tag;
4. `General_Array` assigns it to the GA PE group;
5. `GA_PE_Group_Interconnect` concatenates the same tag/data into the GA PE
   input.

## Complete mathematical proof

The proof compares a scalar transcription of the executable RTL equations with
an independent integer-only IEEE-754 binary32 roundTiesToEven reference and
with NumPy binary32 conversion.

- all exactly representable magnitudes `1..2^24-1` are enumerated;
- for exponents 24 through 30, every normalized 24-bit quotient is enumerated
  over the complete remainder partition below-half, exact-half, and
  above-half;
- guard, sticky, and retained parity make every member of each remainder class
  equivalent;
- positive and negative sign partitions, zero, and the separate INT32_MIN
  branch complete the domain.

Result:

- logical input coverage: `4,294,967,296 / 4,294,967,296`;
- representative equation checks: `184,549,375`;
- mismatches: `0`;
- status: `LIVE_GA_INT32_TO_FP32_FULL_DOMAIN_BIT_EXACT_PROVEN`.

Directed witnesses cover zero, `+1`, `-1`, INT32_MIN, INT32_MAX,
`-INT32_MAX`, positive and negative even/odd ties, positive and negative
exponent carry, carry predecessors, and historical node0075 input `-44906`.
The focused live RTL witness has `15/15` passing cases.

## Historical evidence adjudication

`contracts/operator_config/stage_operator_semantics_audit_v1.json` has SHA256
`27079b96ec9e5306807cb23f3718f9af5827607366eaab22c0fed817a45aa4aa`
and binds its failing observations to historical GA source SHA256
`42a7ac1d740c758de9656ee0d41663ef1c8b11253e76ba2e20be6faee2d12e17`.

On the current proven source:

- `-1`: `0xbf800000`, equal to the reference; historical value was
  `0xcf000000`;
- INT32_MIN: `0xcf000000`, equal to the reference; historical value was
  `0xce800000`.

Therefore those two counterexamples are closed only for the exact current
commit/blob/source identity. The stale comment and historical audit remain
preserved as provenance; neither is generalized across source identities.

## Validation and artifact identity

| Artifact | SHA256 |
|---|---|
| `tools/prove_requant_ga_int32_to_fp32_full_domain_v1.py` | `c03e03c0f42913b20265334ec3bb5dc766cad6fa534967fe59f7de52aaab0654` |
| `tests/rtl/requant_ga_int32_full_domain_witness_tb.sv` | `aac0e8d304338741f091d10fc868f5ca983efb49b79d55e30ceb1ad4f042b61b` |
| `tests/test_requant_ga_int32_to_fp32_full_domain_v1.py` | `8141ebbd43e80858c417e2f616cd152982d50b31fdd78757311a4bc0c447a4b4` |
| `artifacts/operator_config_validation/requant_ga_int32_to_fp32_full_domain_v1/report.json` | `e169cc378d380c635f88a94558df25982484e1dcd185be396265ee56170973f7` |
| `artifacts/operator_config_validation/requant_ga_int32_to_fp32_full_domain_v1/validation/rtl_witness.log` | `d1912c816171caa12f72ec8a6965c2b2e0eaa176fe0a495b60b911f2d67659a5` |

Final checks:

- proof generator: exit `0`;
- Python bytecode compile: exit `0`;
- `python -m unittest tests.test_requant_ga_int32_to_fp32_full_domain_v1`:
  `4/4 PASS`, exit `0`;
- Icarus compile: exit `0`;
- Icarus simulation: exit `0`, `cases=15 errors=0`;
- forbidden outputs under the proof artifact root: `0`;
- server package/action: none.

## RETURN_ANALYSIS

The existing GA signed INT32-to-FP32 ingress primitive is full-domain
bit-exact on the exact local `0ccae916...` / blob `59507fc...` identity.
Executable RTL, not the stale adjacent comment, recognizes INT32_MIN and
implements GRS roundTiesToEven including exponent carry.

This closes only the numeric-semantics subleaf for the current ingress
primitive. It does not prove a RequantizeUint8 or AverageRequant target.

The following counterexamples remain active and are preserved in the machine
report:

- sequential multiply/RNE versus one-round FMA:
  input `400`, multiplier `0x3d828f5c`, zero point `0`,
  sequential `26` versus fused `25`;
- magic wrap: scaled `-12582913`, expected UINT8 `0`, magic decode/saturate
  `255`;
- zero point after RNE: scaled `0.5`, zero point `1`, expected `1`, zero point
  folded into magic bias `2`.

## BLOCKER_DELTA

Close no family-level blocker. Refine the signed-ingress numeric subleaf to
`PROVEN_ON_EXACT_CURRENT_SOURCE`.

Keep open:

- family-wide existing-primitive slow composite;
- sequential FP32 multiply followed by independent RNE;
- integer zero-point addition and exact UINT8 saturation;
- typed/topology/address/lifetime composition;
- local materialization and strict complete JSON;
- all dynamic, natural-terminal, formal-D, E3, E4, E5, and server gates.

## RULE_DELTA_PROPOSAL

Status: `PENDING`; no rule was edited.

Evidence supports a non-synonymous rule update that:

1. binds native signed INT32-ingress conclusions to exact commit/blob/source
   identity;
2. treats executable equations plus complete proof as authoritative over a
   contradictory adjacent comment;
3. distinguishes historical source-specific counterexamples from current
   source behavior;
4. removes only the fixed current-source `-1`/INT32_MIN ingress premise while
   retaining the sequential-RNE, integer-zp/saturation, magic-wrap, composition,
   and dynamic gates.

## PACKAGE_RELEASE

`NONE`.

