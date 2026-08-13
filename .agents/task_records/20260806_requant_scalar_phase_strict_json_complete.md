# Requant scalar-phase strict JSON complete

Date: 2026-08-06

Family: `RequantizeUint8 / AverageRequant`

Unique mainline return target:
`019fbec2-fe93-7e03-9314-cff6f222f33d`

## Result

`COMPLETE_LOCAL_STRICT_JSON_54_OF_54`

The authorized existing-primitive slow composite is now materialized as 54
local strict operator JSON candidates:

- 53 Conv stages use channel-temporal four-byte multiplier transactions into
  buffer2 bank0, GA inport1 lane0 and `PE00.inport1` keep;
- `hwop-0075-01` uses its exact scalar multiplier `0x3a510db3` as a PE00
  constant;
- every candidate uses the accepted five-PE exact graph
  `mul -> clamp[-256,256] -> magic -> int32_sub -> integer zero-point ->
  UINT8 saturation`;
- the historical `-12582913 -> 255` magic-wrap counterexample remains in every
  candidate and is excluded by the exact three-region clamp, not waived;
- one-round FMA and host replay of scaled/rounded/saturated/final tensors are
  absent.

All logical loops are split into canonical positive-stride tiles with
`end<=32768`. Conv A/D address equations preserve HWC8 element order while
each channel is a temporal scalar phase. Multiplier transactions are exactly
four bytes at `multiplier_base + 4*channel`, never cross a 16-byte line, and
are held only through the bound spatial tile lifetime.

Addresses are complete in an operator-local, relocatable 30-bit address
space. Input, multiplier and output regions are 16-byte aligned,
non-overlapping and byte-complete. Uniform backend rebasing is outside this
claim and remains forbidden in this task.

## Coverage and provenance

```text
expected/covered/strict = 54/54/54
Conv/MatMul = 53/1
zero/even-nonzero/odd-nonzero zp = 33/16/5
multiplier elements = 26,561
field provenance leaves = 50,095
UNRESOLVED leaves = 0
```

Each candidate has:

- complete strict JSON;
- 100% leaf provenance ledger;
- authorized materializer capability matrix;
- leaf-complete current-test diff;
- four resolved PE-to-PE composition boundaries;
- one `COMPLETE` candidate contract.

The current-test comparison keeps the frozen node0001 guard-only history
read-only. Its last trustworthy boundary remains BST data plus coefficient
address 64/64 bit-exact. The historical coeff-to-ALU/outbuffer observation gap
is classified dynamic-only and is not attributed to these new local JSON
leaves.

## Shared gates

Candidate gate:

```text
candidate_count=54
pass=54
contract_valid=54
errors=0
completion_blockers=0
```

Exact family-set gate:

```text
scope_mode=PINNED_EXACT_STAGE_IDS
lowering_sha=bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432
expected=54
covered=54
missing=[]
unexpected=[]
duplicate=[]
type_errors=[]
lowering_sha_errors=[]
pass=true
```

## Validation

1. Family formula validator:

   ```text
   python tools/validate_requant_scalar_phase_strict_json_v1.py \
     --output artifacts/operator_config_validation/r5_requant_scalar_phase_strict_json_v1/validation/family_validator.json
   exit=0; pass=true; errors=[]; forbidden_output_count=0
   ```

   Report SHA256:
   `0443014860e6985c9c96f334d574714ff012a9e8f336889e69ec8603c2a94570`

2. Shared candidate validator:

   ```text
   python tools/validate_complete_operator_json_candidate.py \
     <each of 54 candidate_contract.json> --output <per-stage report>
   exit=0 for 54/54
   ```

3. Shared exact family-set auditor:

   ```text
   python tools/audit_complete_operator_json_family_set.py \
     artifacts/operator_config_validation/r5_requant_scalar_phase_strict_json_v1/family_set.json \
     --output artifacts/operator_config_validation/r5_requant_scalar_phase_strict_json_v1/validation/public_gate/family_set_audit.json
   exit=0; pass=true; errors=[]
   ```

   Report SHA256:
   `bc117ab155e5912ba536dce949ba49f96994649631f79a7a79b3652b4b0477f1`

4. Final complete local self-check:

   ```text
   python -m unittest \
     tests.test_requant_scalar_phase_strict_json_v1 \
     tests.test_complete_operator_json_candidate \
     tests.test_complete_operator_json_family_set -v
   exit=0; 23/23 PASS
   ```

Negative controls fail closed for multiplier-bit tamper, scalar-buffer-size
tamper, missing/unknown provenance, unsupported handler/composition, forbidden
server-package output, lowering-SHA drift, duplicate/missing/extra stage,
stage-ID drift and hardware-type mismatch.

## Receipts

| Item | SHA256 |
|---|---|
| report | `9b426c6731be52e5a68eec300d6765cc1589cec2c1a3decea66fad107cdf9ddf` |
| materialization manifest | `0aaaf23ff027eae4aed8bedcc082f4ece9af7f97acc0236e3ff1a6436f606ad4` |
| family set | `2758581edca27fe118066b9f0939925a4b854ac96329e6cbc16ac108a47d23af` |
| materializer | `c3fc8d51fb35293731ee86417b78802f7ee28c4c4a9f94c51689cd2ee4adf519` |
| family validator | `6559ccbc4c76ae208bd37eb3b106c14f457662b6d9c896fd0a327e88eb3089f9` |
| tests | `7f92746231e52a4b6415528cd14d524935a1b28c929e6cf30657bd0405da6902` |

Artifact root:
`artifacts/operator_config_validation/r5_requant_scalar_phase_strict_json_v1/`

Machine report:
`artifacts/operator_config_validation/r5_requant_scalar_phase_strict_json_v1/report.json`

## Current read receipts

| Path | SHA256 |
|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/plan.md` (mutable provenance) | `228775d9d7676808ae4df322f77b2d789713334b123a72f338176e9ec0823353` |
| `.agents/rules/生成前必读索引.md` | `3c0c9d5e836e2ea9cb7d697252fe2f46dfd5cce8facfdbd332d8bbd3d0fe48cc` |
| `.agents/rules/算子配置规则.md` | `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1` |
| `.agents/rules/RequantizeUint8算子配置规则.md` | `d2caeb55222f5b47585d890875e4d8f3f5c17d17a6849a93af4366e9f3447f99` |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` |
| `.agents/rules/最小双Stage生命周期规则.md` | `821b8b04b0e33d0a93e06a3a1bca8307b417bcb63f109cf12414891e9a0bc171` |
| `.agents/rules/NDP硬件字段语义.md` | `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055` |
| complete-JSON policy | `de2825cae9f892482cd8eb74a60ea9b409a7f8186516b7ac5a6c04344b10c746` |
| family-set schema | `bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18` |
| shared candidate validator | `4e30018656afd41f3f7d89f2d56070986e2465fac59d41483ae40fbf8f4ec62f` |
| shared family auditor | `3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1` |

The plan is mutable provenance only. No plan or rule file was modified.

## Structured return

### RETURN_ANALYSIS

- `LOCAL_STRICT_JSON=COMPLETE_54_OF_54`
- `SHARED_CANDIDATE_GATE=PASS_54_OF_54`
- `EXACT_FAMILY_SET_GATE=PASS_54_OF_54`
- `UNRESOLVED_LEAVES=0`
- `FORMAL_D=NONE`
- `OBSERVER=NONE`
- `BACKEND_OR_DYNAMIC=NOT_ENTERED`

### BLOCKER_DELTA

Close:

- `B_REQUANT_CONV53_SCALAR_PHASE_STRICT_MATERIALIZATION`
- `B_COMPLETE_JSON_REQUANT_SEQUENTIAL_RNE_ZP_SATURATION_COMPOSITE_CAPABILITY`

Keep:

- `B_REQUANT_CONV53_SCALAR_PHASE_BACKEND_AND_DYNAMIC_EXECUTION`
- `B_REQUANT_GUARD_DYNAMIC_DATA_PATH`
- `B_REQUANT_SERVER_E4_E5`

Add: none.

### RULE_DELTA_PROPOSAL

`NONE_NON_SYNONYMOUS`.

The current provenance, handler-capability, composition and exact-stage
family-set rules correctly fail closed and require no semantic change.

### PACKAGE_RELEASE

`NONE`

## Claim boundary

`COMPLETE` means local strict scalar-phase operator JSON only. No native
backend JSON, mapping, bitstream, execplan, SCA, package/ZIP, upload, server
run, lease, formal D, E3, E4 or E5 was generated or claimed. Functional RTL,
ISA, hardware and active `ndp-sim` were not modified.
