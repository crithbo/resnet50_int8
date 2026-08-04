# QLinearAdd node0007 true split workload authorization

## Provenance

- mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- authorization date: `2026-08-03`
- mutable plan SHA256 at dispatch:
  `e37ee58cf9a4ac98423b066516ee610054f940505c00a8e3fb2bc921a412c583`

## Frozen current server identity

`r5_qadd_n7_bctrl_v24.zip` remains the current
`PACKAGE_READY_NOT_RUN` identity. The split-workload task must not overwrite,
rebuild or rename it.

## Authorized split

- A: `op_a_dequant + op_b_dequant`
- B: `op_relocation_pad`
- C: `op_fp32_add`
- D: `op_tail_mul + op_tail_round + formal D readback`

Each fresh package must change the compute workload, not merely observer scope,
and carry only its own stage bitstream/execplan, necessary slices and legal
boundary input.

## Legal boundary-input modes

### HARDWARE_PRODUCED_BOUNDARY_REPLAY

The payload must be recovered byte-for-byte from a verified hardware-stage
output/readback/checkpoint. Its contract must bind the source package, run,
stage and completion/acceptance boundary; tensor identity; shape, dtype,
layout and qdomain; original address and lifetime; payload size and SHA256;
and the injection address mapping.

A `COMP_FINISH` marker, observer counter or other state without recovered
payload bytes is not a hardware-produced boundary tensor. A host
recalculation cannot be relabeled as a hardware result.

### DIAGNOSTIC_STIMULUS_NOT_PRODUCER_EVIDENCE

A frozen golden may be admitted only through an independent diagnostic
partition contract and a separate stimulus identity/allocation. The source
must be declared truthfully. The package may diagnose only the local stage;
it cannot claim that the upstream producer ran, or that cross-stage barrier,
lifetime, chain correctness, E3, E4 or E5 is closed.

Such a package is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`, at most
`E2_LOCAL_ONLY`, with `candidate_release=false`.

## Mandatory fallback

If B, C or D lacks either a byte-recovered hardware boundary or a legal
golden-diagnostic partition contract, the owner must not create an internal
tensor replay package. It must use cumulative prefix workloads:

- A
- A+B
- A+B+C
- full A+B+C+D/readback

Checkpoint/restart is preferred when the active entry can bind it reliably.
The final six-stage plus 28-D end-to-end conjunction remains mandatory.

## Release gates

For each fresh identity:

- preserve numeric/W3/qparams/tail algorithm and functional RTL;
- bind the boundary provenance/typed/address/lifetime/hash contract;
- build twice deterministically;
- execute the current final-ZIP self-audit;
- execute package-local HDL compatible-frontend positive and three negative
  controls when package-local HDL is present;
- execute safe compile, EXIT, TERM and wrong-identity runner controls;
- bind return exact-set, allowlist and required-missing semantics;
- preserve low-cost qualified checkpoints around the local stage boundary;
- do not upload, run on the server or acquire a lease.

The owner must proactively notify the mainline for every
`PACKAGE_READY_NOT_RUN` or explicit quarantine/termination result and supply
an evidence-backed `RULE_CONFIRMATION` or `RULE_DELTA_PROPOSAL`.

## Current receipts

- agent:
  `d9fe95839c2c92a83083d956392a66876c1007fbb7922522c6a8920babab6721`
- index:
  `db339fb8f47105b76deef85cdd43cfc85af6358a0c8155571fde54c2006f26c5`
- common:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- hardware:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- server:
  `5761987d07f425a316bd845e390405c0c64d78c9a371b9cce22cc491c8f25f48`
- QLinearAdd:
  `aecf9d98136a23a73b3cd5ce8c8ec52f3070a763937373703e6376e3910e730f`
- exact UINT8 tail:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- hardware simulation entry:
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

## Rule adjudication

The authorization is covered by
`CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001`, QLinearAdd stage,
scratch/barrier/lifetime rules, and the current server-package release gates.
No new public rule is required at authorization time.
