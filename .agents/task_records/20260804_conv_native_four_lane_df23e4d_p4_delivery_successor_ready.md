# Conv node0004 native four-lane df23e4d p4 delivery successor

Date: 2026-08-04  
Owner: independent Conv native-four-lane performance owner  
Target mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Result

Fresh p4 is `PACKAGE_READY_NOT_RUN`:

- class: `PERFORMANCE_DIAGNOSTIC_CANDIDATE`;
- `candidate_release=false`;
- install identity: `r5_n4_df23e4d_p4`;
- functional RTL entries: 0;
- server upload/run/lease: none.

This is a delivery/extraction successor to the immutable df23e4d v1 ZIP.
It does not change the frozen typed request, W3, qparams, numeric
configuration, mapping, bitstream, execplan, SCA/SCA_D, golden, observer or
expected production RTL leaves. The serialized correctness baseline and all
functional RTL remain untouched.

## Bound identities

- Trassic master:
  `df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727`;
- active `SA_PE_Float_CSA.v`:
  `72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3`;
- RTL sync report:
  `artifacts/rtl_sync/trassic_master_df23e4d_20260804/report.json`,
  SHA256
  `6cf79c6d461ffb73ba7554dec8056b178a81ec5018bd0068accda4efb9a366a5`;
- arithmetic/all-53 report:
  `outputs/conv_native_four_lane_df23e4d_revalidation/report.json`,
  SHA256
  `d681d682ad38ccb7a72427a9cfbba2d8e232d1a6e7be6adef784604f958e2f92`;
- immutable source v1 ZIP SHA256:
  `5cbf05cac96f887c6753d378c7f3f44daf04f60caa6016f1f41eab274cebd62f`.

The previously closed
`B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE` remains closed only for
this exact RTL identity. No broader INT32-domain or other-leaf claim is made.

## p4 package

- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_df23e4d_p4.zip`;
- bytes: 45,989,623;
- ZIP SHA256:
  `c8d42f979b07468e869d077755f987c09c04d017cd1bc6ab50a71a8ee1d0204e`;
- sidecar SHA256:
  `22163623e58c919f440dbc941c34213864bc44f1aa72d180b3c5025be053526e`;
- build receipt SHA256:
  `5f4c559438c66dc700053410cbcb6ecf0cae25d3dc8fd1a2d2305fa91ae0acaa`;
- final ZIP audit SHA256:
  `6a4aa8ca2719b16e62ff5c2b6e5a3684c0b3014d6d55fed60df6243d6c1f0a99`;
- exact ZIP file count: 834;
- simulation runs: 27;
- formal D consumers: 320.

Two independent fresh materializations produced the same ZIP SHA and exact
file records. Final fresh-extract validation reports
`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `error_count=0`.

The three members absent in the submitted incomplete extraction are directly
present in the final ZIP and final manifest:

- `workload/runtime/runs/t000/install/cfg_pkg/op_mul_w0_s00_resnet50_requant_node0004_mul_w0_s00_bitstream_128b.bin`;
- `workload/runtime/runs/t000/install/cfg_pkg/op_round_w0_s00_resnet50_requant_node0004_round_w0_s00_bitstream_128b.bin`;
- `workload/runtime/runs/t000/install/op_round_w0_s00/slice00/matrix_A_linearized_128bit.txt`.

The clean extract passes exact-set preflight with zero bytecode artifacts.
Deleting the first witness makes direct preflight fail and makes the full
runner exit 5 before compile, with no remaining install/run/evidence
namespace for this candidate.

## Workload and consumer identity

The v1→p4 workload comparison covers all 503 runtime files:

- 449 byte-identical;
- 54 SCA/SCA_D JSON files identical after normalizing only the fresh install
  identity;
- missing=0, extra=0, changed=0.

The final audit also passes exact ZIP set/hashes, SCA/execplan consumer
closure, 320 formal-D consumers, runtime-D absence, package-local observer
focused HDL syntax/scope, four-way runner binding, compile-failure return,
TERM partial return, production-leaf positive/negative controls and natural
terminal positive/negative controls.

The immutable local E2 remains `LOCAL_E2_PASS`. Current rebuild comparison
differs only at:

- the generated-before-read index receipt;
- the server-package-rule receipt;
- the derived contract self-hash.

All numeric, boundary, W3, mapping, bitstream, execplan, SCA and three-way
bit-exact content is unchanged. The E2 asset was not overwritten. Eleven
numeric/package regressions passed; the sole full-contract equality test
correctly reports this provenance-only rule-receipt drift. Four p4-specific
tests pass.

## Current path-budget gate

`CDA-SERVER-PACKAGE-INTERNAL-PATH-LENGTH-BUDGET-001`:

- declared user-supplied server root maximum: 96 characters;
- projected absolute path: 229/240 characters;
- maximum projected relative path: 132 characters;
- maximum inner suffix: 116/128 characters;
- maximum inner depth: 8/8;
- maximum ZIP-member path: 133 characters;
- repeated outer identity inside package: false.

The one component above the 48-character target is a frozen
`*_bitstream_128b.bin` ABI leaf and is explicitly declared in the manifest.
The too-deep member, repeated-identity and stale-consumer-reference negatives
all fail closed. Runtime recomputes the actual normalized server-root budget
before compile.

## Performance evidence ceiling

No new server performance evidence is claimed. The unchanged final-config
inversion inherited from the local E2 remains:

- logical/serialized product occurrences: 205,520,896;
- native occurrences: 51,380,224, reduction `4.0x`;
- maximum useful lane utilization: `25.0% -> 100.0%`;
- weight payload: `262,144 -> 65,536` bytes, reduction `4.0x`;
- activation B producer:
  `51,380,224 -> 12,845,056` bytes, reduction `4.0x`;
- native B plus B-prime: 25,690,112 bytes, combined physical activation
  reduction `2.0x`;
- bias and D payloads: unchanged.

These figures are inverted from final local artifacts, not measured server
throughput.

## Server handoff

Verify the sidecar, extract the ZIP into a newly created empty parent, enter
the single archive root, then run:

```bash
bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02
```

Expected return:

`r5_n4_df23e4d_p4_return.zip`

The formal return must still prove:

- 27/27 natural terminals;
- 320/320 formal D with mismatch=0;
- actually compiled production RTL leaf identities matching df23e4d.

Until that return is adjudicated, E3/E4/E5, measured performance and
candidate release remain open.

## Implementation and verification SHA256

- p4 runtime:
  `b4b3bd66d52cfeab919be95c4feb541b9239898d559501a6e56117733e1dec3a`;
- p4 builder:
  `3d122f83b3529ab0b1e3c67fbdb855c6dc21e81b96f027a8afd29387bc58c5a5`;
- p4 validator:
  `78f31483dd09198a0cb3c86bee35dd10dff6bd39e62884c0f8f5bfd7c5210a39`.

Verification:

```text
11 numeric/package tests: PASS
4 p4 delivery tests: PASS
final ZIP audit: PACKAGE_READY_NOT_RUN, errors=0
```

## BLOCKER_DELTA and rule feedback

Closed:

- `B_CONV_NATIVE_FOUR_LANE_P4_DELIVERY_EXACT_SET`;
- `B_CONV_NATIVE_FOUR_LANE_P4_INTERNAL_PATH_BUDGET`.

Preserved:

- `B_CONV_NATIVE_FOUR_LANE_SERVER_NATURAL_TERMINAL`;
- `B_CONV_NATIVE_FOUR_LANE_SERVER_FORMAL_D_320`;
- `B_CONV_NATIVE_FOUR_LANE_SERVER_PRODUCTION_RTL_IDENTITY`.

RULE_CONFIRMATION:
`CONFIRMED_SUFFICIENT_NO_RULE_DELTA`.

The current exact-set, bootstrap immutability, clean-extraction, path-budget,
runner positive/negative control, focused HDL, return allowlist and
result-conjunction rules were sufficient. They required the p4 short
identity, projected-path enumeration, three path negatives, fresh-extract
member controls and fail-closed cleanup before compile. No non-synonymous
public rule gap was found.

Current read receipts:

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`;
- `.agents/plan.md` mutable provenance:
  `a74a185fef9c0f448bbfc412ddd8adb37109cc3370740e2ec2e8097e148a5d5c`;
- generated-before-read index:
  `93b66e7986beeaddb01f237710af6874bb4bbfcc4c6c6929563c5e98d8397eb2`;
- server-package rule:
  `14b7e5fa45e5985f9c8bc849acf0a9e768ab4617f3c249addaeb7b5d291a47d1`;
- operator-config rule:
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`;
- hardware-field semantics:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`;
- INT8-SA rule:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`;
- exact-uint8-tail rule:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`;
- hardware simulator README:
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`.
