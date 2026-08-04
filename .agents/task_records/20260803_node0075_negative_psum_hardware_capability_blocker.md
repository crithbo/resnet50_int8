# node0075 frozen negative-psum hardware capability blocker

## Terminal adjudication

- mainline:
  `019fbec2-fe93-7e03-9314-cff6f222f33d`
- independent QLinearMatMul owner:
  `019fc775-8de0-7f10-bc4a-026a4673776f`
- operator scope:
  `node0075 / MatMulInt32Accumulate / QLinearMatMul`
- terminal status:
  `HARDWARE_CAPABILITY_BLOCKED`
- package release:
  `NONE`
- candidate release:
  `false`

The synchronized current RTL closes only the historical
`SA_FLOAT_CONTROL_ANSI_PORT_TRAILING_COMMA` syntax leaf.  A complete frozen
node0075 recurrence scan reaches the still-live
`SA_PE_Float_CSA` negative-psum split-reconstruction defect.  The first current
hardware leaf therefore occurs before handler/materializer/config/E2 emission.
No server package was generated.

## Startup and ownership receipt

The current plan, required public/hardware/server/specialized rules, node0075
authorizations, owner split, alias integration contract, RTL sync receipt and
relevant active RTL were reread from disk.  The current locked rule identities
are:

- `.agents/agent.md`:
  `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`
- required index:
  `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`
- operator configuration rules:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- hardware field semantics:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- INT8-SA specialized rules:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- exact UINT8 tail specialized rules:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- server package rules:
  `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`

The user-supplied resume plan SHA
`0c6bc109775d38545cabea1ac61149272bf024eeabc311541f49f8a4a2329eaa`
was valid at initial reread.  The mutable plan advanced legally during this
task to current SHA
`af733b60e539263b3be449dbcfdd77442db9a530c612041e29b6df9263495772`;
the current text contains the authorized resume dispatch and synchronized RTL
receipt.  It was not modified by this owner.

The startup inventory found no new node0075 handler, op-json, materializer,
mapping, bitstream, execplan or SCA in the active `ndp-sim`.  The only existing
node0075-scoped files were the prior alias-integration and historical
fail-closed materializer receipts.  They were preserved without deletion or
overwrite.  No Conv, GAP, QAdd, Quantize/Dequant/View or functional RTL asset
was modified.

## Current RTL identity

The authoritative sync report remains:

- `artifacts/rtl_sync/trassic_master_8f2f318_20260803/report.json`
- SHA256:
  `4a798e2257ece9d49d64ff8fc00acc826fef3d4dbd35291e26e88f141c273e18`

Relevant current leaves:

- `SA_PE_Float_Control.v`:
  `4214262e12ab80bf3be867f558d762e134c3122f16df4f7d08063e383242c4e6`
- `SA_PE_Float_CSA.v`:
  `ea24759841d990f230f9c33a111f934e107c996a85b2f5ea00c9408ca73d0223`
- `SA_PE_Mul_Array.v`:
  `135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a`
- `SA_ALU.v`:
  `c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06`

The current `SA_PE_Float_CSA` still comments out the candidate full-width
expression and executes separate `[30:0]` and `[31]` assignments.  The local
focused node0075 witness compiles and simulates against these exact active
sources with Icarus/VVP exit `0/0`.

## Frozen recurrence proof

Inputs are the frozen W3 node0075 values:

- A:
  `uint8[16,2048]`,
  file SHA256
  `c2d08ebd45a564d63e499b333a9576bbdafc71448ee693c8a199a7cf65193f12`
- B:
  `int8[2048,1000]`,
  initializer value SHA256
  `0a04b48f313e071330869b5638d696e008a35801c74db1778f9376a8c6008688`
- A/B zero points:
  `0/0`
- initial psum:
  `0`
- formal accumulator:
  `int32[16,1000]`,
  file SHA256
  `ee8422fe7c20f0cc40adb18abcd0b8b0f9c433a6c2283e8c87262e3a7d419ec3`

The scan uses the required metadata-alias C-order:

```text
A[m,k] byte offset = k
transaction t carries k = 32t .. 32t+31
dot4 group g carries k = 4g .. 4g+3
g = 0 .. 511 in ascending recurrence order
```

This is the exact `addr(slice,t)=0x000a2000+(slice_id<<25)+32*t` order required
by the approved node0071→node0075 handoff.  No K reorder, A relayout, copy,
host tensor replay or precomputed psum was used.

Complete scan result:

- planned/enumerated occurrence count:
  `8,192,000 / 8,192,000`
- dot4 observed range:
  `[-3539,13286]`
- psum-in observed range:
  `[-45141,121038]`
- negative-psum occurrences:
  `4,343,952`
- negative psum exactly cancelled to zero:
  `272`
- negative psum transitioned to `INT32_MIN`:
  `0`
- all recurrence finals versus frozen formal accumulator:
  `0` mismatch
- ordered boundary-hit digest:
  `b7fdb8d30792b81175cc92f452dbaa6c01c74946685cd72f8cddaa3d0f83143b`

The first stream-order witness is:

```text
(m,n,k_group) = (0,65,3)
A/u8 lanes    = [28,13,1,0]
B/s8 lanes    = [1,-2,17,-2]
lane products = [28,-26,17,0]
psum_in       = -19
dot4          = +19
expected next = 0x00000000
```

The exact current RTL focused test returns `0x80000000`.  Thus the frozen
instance does not avoid the defect merely because its 16,000 final
accumulators contain no zero.  The defect is reached at an intermediate
recurrence boundary.

## First divergence and blocker delta

First divergence:

`B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE`

```text
frozen A/B + psum_in=-19
  -> exact dot4=+19
  -> mathematical next psum=0x00000000
  -> current SA_PE_Float_CSA split result=0x80000000
```

Blocker delta:

- closed:
  `SA_FLOAT_CONTROL_ANSI_PORT_TRAILING_COMMA`
- newly opened exact node0075 leaf:
  `B_MATMUL_NODE0075_SA_NEGATIVE_PSUM_ZERO_BOUNDARY_REACHABLE`
- keep open downstream/not reached:
  `B_MATMUL_NODE0075_FINAL_A_CONSUMER_MATERIALIZER_MISSING`,
  `B_MATMUL_TAIL`,
  `B_QUANT_TAIL_SIGNED_INT32_INGRESS`,
  `B_QUANT_TAIL_FMA_ROUNDING_POINT`,
  `B_QUANT_TAIL_MAGIC_DOMAIN_BOUND`

The leaf is not expressible as a legal config-only fix under the current
required A order.  Functional RTL repair was not authorized.  Therefore the
task stops before target JSON, mapping, bitstream, execplan/SCA, local E2 or
package generation.

## A reload and traffic accounting

Because fail-fast occurs before consumer materialization:

- actual materialized A reload passes:
  `0`
- actual accepted 32-byte A reads:
  `0`
- actual accepted A traffic:
  `0B`
- actual unique A storage accepted by a node0075 materializer:
  `0B`

The authorized post-repair minimum remains a counterfactual budget, not
acceptance:

- minimum passes:
  `ceil(1000/(16*8))=8`
- if reached:
  `512` reads/slice,
  `8192` reads total,
  `262144B` accepted traffic,
  `32768B` unique producer-owned storage

## Artifacts and validation

- machine contract:
  `contracts/operator_config/node0075_negative_psum_reachability_v1.json`
- contract SHA256:
  `a1fb5f8656a8ad5f79be91e1b1f0aaede3dae87da66d271ee7a7345a371025d8`
- current RTL witness:
  `outputs/node0075_negative_psum_reachability/current_rtl_witness.json`
- witness SHA256:
  `1aca3ca7215ed64a670f37ac52c11986add2c8bd1522894b2d907b1f7bd9f08d`
- validator report:
  `artifacts/operator_config_validation/r5-node0075-negative-psum-reachability-v1/report.json`
- validator report SHA256:
  `1d8c9c69ec5126e2be46532961e6efb2639b20847ae7326f93fa7cf5903a248b`

Validation:

- exact current RTL compile/simulation:
  exit `0/0`
- deterministic contract rebuild:
  identical SHA256
- unit tests:
  `5/5` pass
- independent validator:
  `PASS`
- validator negative controls:
  zero-hit erasure, premature E2 claim, unmaterialized reload claim and RTL
  mismatch erasure all fail closed

## RULE_CONFIRMATION

Evidence confirms:

- `CDA-SA-INT8-RTL-COMPATIBILITY-001`
- `CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001`
- `CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001`

These rules correctly require current-identity arithmetic compatibility and
fail-closed termination before formal target/package emission.  The evidence
scope is the frozen node0075 natural C-order recurrence and current
`8f2f318`-synchronized RTL only.  No public-rule delta is required.

Mainline should update the mutable plan statement that the frozen node0075
model avoids the known boundary: final-accumulator nonzero is insufficient;
the complete intermediate recurrence has 272 exact-cancellation hits.  This is
a plan/status correction, not a public-rule change.

