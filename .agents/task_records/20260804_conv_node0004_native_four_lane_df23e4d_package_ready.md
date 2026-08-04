# Conv node0004 native four-lane df23e4d performance candidate

Date: 2026-08-04  
Owner: independent Conv native-four-lane performance owner  
Target mainline: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Scope and ownership

- The frozen `node-0004` / `r5:hwop-0004-00` typed request, W3,
  qparams and proven address/lifetime contract were reused read-only.
- The existing serialized single-nonzero-product implementation remains the
  independent correctness baseline. No serialized asset was modified or
  rebuilt, and this candidate does not count as serialized formal progress.
- Only fresh `native-four-lane-df23e4d`-prefixed tools, tests, contracts,
  generated configurations and package artifacts were created.
- Functional RTL, `.agents/plan.md`, public/specialized rules and other
  operator-family assets were not modified.
- No server upload, run or lease occurred.

## Current RTL identity and arithmetic gate

The candidate is limited to Trassic master
`df23e4dfc7bd2ac3cd3ba889c6083b1a87bd5727` and these active leaves:

- `SA_PE_Float_CSA.v`:
  `72a156f4888af38fa562dbd09a37eed3a9f6a64dedf27d3aa556174d55c5c2f3`;
- `SA_PE_Float_Control.v`:
  `00107da5137ada324407ba7dbf3e74d6e32428a42631aa23f44c5077ea7b7eeb`;
- `SA_PE_Mul_Array.v`:
  `135306563de4407c7d1279c942a7d1ce4e347dd8d263e3fd4a7d63f0e8a2587a`;
- `SA_ALU.v`:
  `c986ea2de79381afb220ccef83f28466ec3bdda39cd4d80255419bfa214fee06`.

`SA_PE_Float_CSA.v:47` is the live full-width signed-result assignment. The
upstream sync report is
`artifacts/rtl_sync/trassic_master_df23e4d_20260804/report.json`, SHA256
`6cf79c6d461ffb73ba7554dec8056b178a81ec5018bd0068accda4efb9a366a5`.

An independent focused 18-source Icarus/VVP run passed with marker
`RTL_REPAIR_DIRECTED_PASS`, including:

- adjacent `-6 + 5 = -1`;
- frozen node0003 `-5 + 5 = 0`;
- `INT32_MIN + 0 = INT32_MIN`;
- signed18 extrema `[-130560,129540]`;
- positive and negative modulo-s32 wrap.

Testbench:
`tests/rtl_audit/conv_native_four_lane_df23e4d_boundary_tb.sv`, SHA256
`dd339c9841ee57d2c1e566bb384cf0fe4e93b537e68505fb6dddaa90c5e0f286`.

The required all-53 frozen W3 enumeration scanned 53/53 Conv instances and
15,426,912,256 occurrences. `NEG5_PLUS5` remains reachable 528 times in 19
instances, while `INT32_MIN_PLUS0` is unreachable. Every reachable named
counterexample is now in the independently passing current-leaf directed set.

- raw reachability: SHA256
  `2ff8f915f78455a17e61aa650233af25f8254d8ad1840f40f0408f87601fc90c`;
- df23e4d adjudication report: SHA256
  `d681d682ad38ccb7a72427a9cfbba2d8e232d1a6e7be6adef784604f958e2f92`,
  status `RTL_AND_ALL53_REACHABILITY_REVALIDATION_PASS`.

Therefore `B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE` is closed for
this exact leaf identity. This is not a claim of correctness for another RTL
identity.

## Native four-lane local E2

Fresh materialization:

- target/config/mapping/bitstream/execplan/SCA root:
  `artifacts/operator_config_validation/r5-conv-native-four-lane-df23e4d-v1`;
- native simulator root:
  `configs/native_ndp_sim/r5_conv_native_four_lane_df23e4d_v1`;
- local E2 contract:
  `contracts/operator_config/r5_conv_native_four_lane_df23e4d_local_e2_v1.json`,
  SHA256
  `f9ecec4f99a5a906637ef5f480329513acc0202b59baee4b9387fb93b05446a2`;
- embedded contract SHA256:
  `d6b24d217bd23abcd99a6cb9f28e70e98b24a57279e71799311f0176ea89a72d`.

Status is `LOCAL_E2_PASS`, `candidate_release=false`. Deterministic double
build, exact target/config consumer binding, 51 mapping consumers, 27
execplans and 54 SCA/SCA_D consumers all closed. Native, serialized and
direct ONNX/W3 accumulator payloads have the same SHA256
`1ec864892d82279beff561927500f55ebec636daf2fb7c624a1e153dd5e17532`;
the exact uint8 requant tail also matches W3.

Directed/random/real-W3 fail-closed coverage includes the four 1x1
boundaries, signed18 extrema, K-tail 1/2/3, nonzero x-zero-point/bias and
mod-s32 wrap. No internal tensor is host-precomputed or replayed.

Actual final-config inversion, not theoretical projection:

- logical products: 205,520,896;
- serialized occurrences: 205,520,896;
- native occurrences: 51,380,224; compute occurrence reduction `4.0x`;
- maximum useful lane utilization: `25.0% -> 100.0%`;
- weight payload: `262,144 -> 65,536` bytes, `4.0x`;
- activation B producer: `51,380,224 -> 12,845,056` bytes, `4.0x`;
- native B plus B-prime total: 25,690,112 bytes, so combined physical
  activation reduction is `2.0x`;
- bias and D payloads are unchanged.

## Server package

`PACKAGE_READY_NOT_RUN`:

- class: `PERFORMANCE_DIAGNOSTIC_CANDIDATE`;
- `candidate_release=false`;
- canonical ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_conv_native_four_lane_df23e4d_perf_v1.zip`;
- bytes: 46,027,937;
- SHA256:
  `5cbf05cac96f887c6753d378c7f3f44daf04f60caa6016f1f41eab274cebd62f`;
- sidecar SHA256:
  `ae7647f1668121c740c0ab5857ece8356f81820121f3899584ee8adbb6e6630e`;
- build receipt SHA256:
  `a0d85350b8f7ae47765c29f1db8a5011b42e003cc6b6cf1b474e51260c1365a4`;
- final ZIP audit SHA256:
  `c017d8243ad7c30b895b9154997d03b14dfa9726ad1d31cb9f9869d41d42784b`;
- exact package file count: 833;
- deterministic ZIP double build and exact file-record comparison: true;
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, errors=0;
- functional RTL entries: 0;
- simulation runs: 27; formal D consumers: 320.

The final audit passed exact set/sidecar/current-rule closure, runner
preflight-to-compile binding, package-local HDL syntax/scope, observer
identity, compile-failure control, TERM partial-return control, canonical
negative controls and exact SCA/execplan/D consumer closure.

Run only after extracting the canonical ZIP:

`bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy01`

Expected return:

`r5_conv_native_four_lane_df23e4d_perf_v1_return.zip`

The official return must bind the actually compiled production RTL leaves
and prove 27/27 natural terminals, 320/320 formal D and mismatch=0. Until
then there is no performance/E3/E4/E5 pass claim.

## Verification

Combined regression:

`python -m unittest tests.test_conv_native_four_lane_performance tests.test_conv_native_four_lane_df23e4d_local_e2 tests.test_conv_native_four_lane_df23e4d_server_package -v`

Result: 12/12 passed.

Important implementation/audit SHA256:

- server runtime:
  `1adcf8d3d458ffc2e078519ce15c6db373c5057fdb057f7a02b871d21fbf2166`;
- package builder:
  `59acbd9f2762a1e35f659add270eaff619d2974798bebd215f7049e63739d210`;
- final ZIP validator:
  `173bf8458eb3e08d70482e1e71dfc13c9f1bd23d4da5afc5e4bad67319407ec5`;
- observer guard:
  `ef56eaf22384d6f5bc481714d0068ddad57e11ec5e683e18e42737c7f91f8384`;
- package observer:
  `2e58c6e7f2752eca541744ab4f806717e57a32b4d7b7fc3af8e0ebef17c08066`;
- package tests:
  `47c4f549f42e3875998321c3a0eb7ba6683e2ff536e95e35f27e3785e5ac933d`.

## BLOCKER_DELTA and rule feedback

Closed:

- `B_CONV_SA_INT32_NEGATIVE_PSUM_BOUNDARY_REACHABLE`;
- `B_CONV_NATIVE_FOUR_LANE_RTL_IDENTITY_AND_E2_PENDING`.

Preserved:

- `B_CONV_NATIVE_FOUR_LANE_SERVER_NATURAL_TERMINAL`;
- `B_CONV_NATIVE_FOUR_LANE_SERVER_FORMAL_D_320`;
- `B_CONV_NATIVE_FOUR_LANE_SERVER_PRODUCTION_RTL_IDENTITY`.

RULE_CONFIRMATION:
`CONFIRMED_SUFFICIENT_NO_RULE_DELTA`. Current final-ZIP, runner,
signal/partial-return, focused HDL syntax/scope, exact consumer closure,
`CDA-SA-INT8-RTL-COMPATIBILITY-001` and
`CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001` rules were sufficient. They
caught and forced correction of fresh package-local return-allowlist
persistence/observer-binding defects before release. No non-synonymous
public rule gap was found.

Current read receipts:

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`;
- generated-before-read index:
  `5146225e549942c4e25780ac4fc0120d7cac1ef355879284450dad2e48df237b`;
- server-package rule:
  `0916c655b0581cd99836d8cc1561a3f41b15b25e861692d596a4789c039b090e`;
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
