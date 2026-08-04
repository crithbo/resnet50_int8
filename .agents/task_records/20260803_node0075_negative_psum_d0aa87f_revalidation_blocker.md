# node0075 d0aa87f negative-psum revalidation blocker (2026-08-03)

## Terminal status

- Owner family: `QLinearMatMul/node0075` only.
- Owner thread: `019fc775-8de0-7f10-bc4a-026a4673776f`.
- Mainline thread: `019fbec2-fe93-7e03-9314-cff6f222f33d`.
- Status: `HARDWARE_CAPABILITY_BLOCKED`.
- `PACKAGE_RELEASE=NONE`.
- `candidate_release=false`.
- First exact blocker:
  `B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE`.
- The d0aa87f RTL identity update does **not** close this blocker.

The owner therefore stopped before handler/registry, consumer materializer,
target JSON, mapping, bitstream, execplan, SCA, config-bound E2, or server
package generation. No upload, server run, or lease action was performed.

## Startup receipt and scope inventory

The mandatory current-disk instructions, routed public rules, node0075
authorizations, identity-alias contract/task record, current RTL sync receipt,
and relevant current RTL were read in full before adjudication.

- `.agents/agent.md`:
  `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`
- `.agents/plan.md`:
  `7e576abb1d965450886480eb604dbd887c06a2989d30ac90ec9ec2639ddf1af8`
- `.agents/rules/生成前必读索引.md`:
  `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`
- operator configuration rules:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- hardware field semantics:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- server package rules:
  `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`
- INT8 SA special rules:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- exact UINT8 tail special rules:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- current d0aa87f RTL sync report:
  `fb104ea11c9a5ad2d3b83998cec331fb7b0440b781cd2beb690de915ed8c2771`

Read-only inventory found no active `ndp-sim` node0075
`QLinearMatMul`/`MatMulInt32Accumulate` op-json schema/template,
handler/registry, or independent consumer materializer. Existing node0075
assets on disk are prior fail-closed reachability/materializer evidence and
approved identity-alias integration assets. They were consumed read-only and
were neither deleted nor overwritten. Conv, GAP, QAdd, Quantize/Dequant/View,
public rules, plan, and functional RTL assets were not modified.

## Current RTL identity

- Trassic master:
  `d0aa87f682880a260fb792aaac88f70a23aba414`
- Functional commit:
  `cb11353d4196b4af26aac18b4dcc39ba0027e8bc`
- `SA_PE_Float_CSA.v`:
  `429a29a929a508f7562f9c78d4ab2cd4095961296d0e6f65e8419a4444a6145a`
- `SA_PE_Float_Control.v`:
  `00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb`
- `SA_PE_Mul_Array.v`:
  `135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a`
- `SA_ALU.v`:
  `c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06`

## Independent directed RTL gate

A fresh owner-side Icarus/VVP testbench compiled and simulated the exact
current active RTL. Compile exit was `0`; simulation exit was `0`.

| Case | Observed | Expected | Result |
|---|---:|---:|---|
| `-20 + 19` | `0xffffffff` | `0xffffffff` | pass |
| `-19 + 19` | `0x80000000` | `0x00000000` | **fail** |
| `-18 + 19` | `0x00000001` | `0x00000001` | pass |
| `0 + 19` | `0x00000013` | `0x00000013` | pass |
| `7 + 19` | `0x0000001a` | `0x0000001a` | pass |

For the frozen exact case, the live internal receipt is:

- full-width magnitude: `0x00000013`;
- CSA raw result: `0x00000000`;
- `Int_Res_Sign`: `1`;
- final output: `0x80000000`.

Thus the full-width Control-side magnitude update is present, but it does not
canonicalize exact zero.

## Fresh complete frozen recurrence

The owner independently reloaded the frozen A tensor, ONNX weight initializer,
and formal accumulator, then ran a fresh direct natural `m -> k_group`
recurrence. It did not import the earlier node0075 reachability implementation
or report.

- planned occurrences: `8,192,000`;
- enumerated occurrences: `8,192,000`;
- negative psum occurrences: `4,343,952`;
- reachable negative-to-exact-zero occurrences: `272`;
- dot4 range: `[-3539, 13286]`;
- psum input range: `[-45141, 121038]`;
- formal accumulator mismatch count: `0`;
- boundary-hit digest:
  `e1b6c87ad2eed55be91edc2462a84a5a16c930223beaf9d21278e942615a363c`.

First stream-order witness:

- `(m,n,k_group)=(0,65,3)`;
- A lanes: `[28,13,1,0]`;
- B lanes: `[1,-2,17,-2]`;
- lane products: `[28,-26,17,0]`;
- psum input: `-19`;
- dot4: `19`;
- expected next accumulator: `0`.

## Exact live leaf

`SA_PE_Float_Control` now supplies the correct full-width magnitude
`0x00000013`. However, the live `SA_PE_Float_CSA` result sign is computed as
`c_Result0_wire[31] XOR i_SignC`. At exact magnitude cancellation,
`c_Result0_wire` is zero, so this expression retains `i_SignC=1`; result bits
`[30:0]` are zero and the final value becomes noncanonical negative zero
`0x80000000`.

This leaf is not expressible through the current node0075 configuration fields.
Functional RTL mutation is outside this owner's authorization. The gate
therefore remains fail-closed.

## Materializer and traffic accounting

Because the arithmetic compatibility gate fails before materialization:

- actual materialized A reload passes: `0`;
- actual accepted 32-byte reads: `0`;
- actual accepted A traffic: `0 B`;
- actual unique consumer-accepted byte set: `0 B`.

The authorized post-fix minimum remains counterfactual, not acceptance:

- `ceil(1000/(16*8))=8` passes;
- `512` accepted 32-byte reads per slice;
- `8192` accepted reads total;
- `262144 B` accepted traffic;
- `32768 B` unique producer-owned storage.

## Blocker delta

- Source identity updated from 8f2f318 to d0aa87f.
- Closed: none.
- Retained:
  `B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE`.
- Not reached:
  `B_MATMUL_NODE0075_FINAL_A_CONSUMER_MATERIALIZER_MISSING`,
  `B_MATMUL_TAIL`, `B_QUANT_TAIL_SIGNED_INT32_INGRESS`,
  `B_QUANT_TAIL_FMA_ROUNDING_POINT`, and
  `B_QUANT_TAIL_MAGIC_DOMAIN_BOUND`.

## Determinism and validation

- Independent run receipt deterministic rerun SHA before/after:
  `fd10530f88c444e829d1248c0e73c51fb5a17639012546eaba4b0d8cf42ad2a5`.
- Contract deterministic rebuild SHA:
  `3e04bcc0994272ca713acc15f34b26cfb0c38f3d1aba53253f3dbb3f2085b9f7`.
- Python compile checks: pass.
- Unit tests: `5/5` pass.
- Validator status: `PASS_FAIL_CLOSED`.
- Negative controls: `6/6` pass:
  exact mismatch erasure, zero reachable hits, unmaterialized traffic claim,
  premature E2 claim, stale RTL identity, and premature package claim all fail
  closed.

## Fresh artifact identities

- directed RTL testbench:
  `fac6c5a00dac1dcf7a08aa2a78f2e7f37f434673326fa3dba73107d30a805428`
- independent runner:
  `534c15d89709267dc7caf692977cde2689bcc89497b0ead11be6ddd8d5945f65`
- current RTL and recurrence receipt:
  `fd10530f88c444e829d1248c0e73c51fb5a17639012546eaba4b0d8cf42ad2a5`
- contract builder:
  `7928e28165d11afb43d08125a8af233af690f046b80863a7a81a21288fcd56a6`
- terminal contract:
  `3e04bcc0994272ca713acc15f34b26cfb0c38f3d1aba53253f3dbb3f2085b9f7`
- validator:
  `155829482f0ba49111db925e06316d477e22f51654a9392586474be5386e653e`
- unit test:
  `cf07bd543a371ac012bd12b9b0f966f45a8a9f69cc7a911a97b7ecdb31351598`
- validation report:
  `125d9ce541ce7d5d932bdb066abdea506e22cdd9c349175e642a57ca36f1bc23`

## RULE_CONFIRMATION

Confirmed under the exact claim boundary of the frozen node0075 natural-order
recurrence and the active d0aa87f RTL identity:

- `CDA-SA-INT8-RTL-COMPATIBILITY-001`;
- `CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001`;
- `CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001`.

The current rules correctly require arithmetic compatibility before
materialization or packaging, and correctly prevent theoretical reload traffic
from being recorded as accepted traffic.

## RULE_DELTA_PROPOSAL

- Required: `false`.
- Reason: the current rules already express the necessary current-identity
  compatibility and fail-fast behavior. This result is an RTL capability
  blocker, not a public-rule gap.
