# GAP node0071 v41 return → v46 stage-transition diagnostic closure

- analysis owner: `019fa366-cb1f-7ae2-880c-f527be0680cd`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `ADJUDICATED / PACKAGE_READY_NOT_RUN`
- claim boundary: `CONFIG_ONLY_CORRECTNESS_BASELINE / E2_LOCAL_ONLY`
- numeric/sum/tail/workload/config/golden repeated: `false`
- functional RTL modified: `false`
- server upload/run/lease: `none`

## Current control receipts

- agent: `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- plan (mutable provenance): `43fe7b8c5b7d5d8daf1631f1d01cca1450ef13d7a4891722ebc509061e166e70`
- generation index: `37f75653e2c5c167a6fb5d178785b9d3f3a3262b78cddf19d34663418c179e88`
- server package rules: `755672c11626accf38160ddd5e2959cdf8949c0b4483f1243ff6b3a3bdb0ad8c`
- operator config rules: `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
- NDP field rules: `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- GAP int32 MAC rules: `4c3a88b8c6967812b0b64a550bb92a45117106f34996102335dc26fa1a211f8b`
- GAP probe rules: `db377ee2eb7ecc381a44a169a875ccecf2c46711399a4bdabcaef4ba164653d1`
- exact UINT8 tail rules: `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- cloud/local RTL authority: `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`
- actual compiled production RTL identity: `UNBOUND_BY_RETURN`

## RETURN_ANALYSIS

Input:

- return: `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n71_gap_v41_branch_isolated_config_fix_return.zip`
- bytes: `162750`
- SHA256: `01b548c257bc1feefa3c2168f6d68afd7b8a41bab403c6b4abdcaced52e88c34`
- adjacent sidecar: absent; accepted only under the user-attested no-sidecar transport rule
- frozen source ZIP SHA256: `11dd499aa99b2d2a67220a0d803e1878da8e1d932f51cee1b0e7c3430e957ed6`

Receipt:

- CRC/root/path/duplicate/symlink: PASS
- internal source/package/install/run/return identity: PASS
- RETURN_MANIFEST exact-set/per-file receipts/allowlist: PASS
- compile: `0`
- simulation/runner: `125/125`
- signal: `HUP`
- exact simulator message: external `SIGHUP`
- VCS sim time at interruption: `26341033125 ps`
- host CPU time: `2282.610 s`
- natural terminal: false
- formal D expected/present/missing: `48/0/48`
- mismatch: `0`, not evaluable because every formal D is missing
- SERVER_RESULT_GATE conjunction: false
- E3/E4/E5: `false/false/false`

The HUP arrived after approximately `2113.998 s` with an exactly flat final
observer size and line. Simulation time continued to advance, but no qualified
stage event advanced. This is an externally interrupted return after a distinct
post-stage idle, not a timeout, natural terminal, diagnostic finish, functional
PASS, or immediate functional failure inferred from missing D.

## LAST_PROVEN_GOOD

`SUM_S1_SLICE0_COMPLETE_WITH_INDEPENDENT_BUFFER_BRANCH_AND_MSE4_COMPLETION`

- Buffer_AG enqueue/dequeue: `8208/8192` for each observed flow
- Buffer_AG residual count: `16` for each observed flow
- Memory_AG enqueue/dequeue/request: `8192/8192/8192` for each flow
- DBCLK requests: `8192` for each flow
- MSE4 request/wdata: `8192/8192`
- prior shared-LC topology cycle: dynamically crossed and closed

## FIRST_DIVERGENCE / HANG_ROOT_CAUSE

- FIRST_DIVERGENCE:
  `SUM_S2_EXEC_START_ABSENT_AFTER_SLICE0_SUM_S1_COMP_FINISH_WITH_MASK_WIDE_DISPATCH_CONJUNCTION_UNOBSERVED`
- HANG_ROOT_CAUSE:
  `LONG_IDLE_AT_POST_SUM_S1_GLOBAL_STAGE_TRANSITION_PENDING_SELECTED_SLICE_READY_OR_LOCAL_QUEUE_OR_CONFIG_READY_LEAF`

RTL semantics bind global dispatch to:

`global2local_valid_hs = global2local_valid & ~gexec2slice_valid & slice2gexec_ready`

and require all selected mask factors plus config readiness. Slice0 completion
does not prove all selected slices are ready, local queues are consumable, or
the global/config factor has advanced. The v41 evidence therefore closes the
old LC-cycle blocker and opens only the mask-wide stage-transition conjunction.

## BLOCKER_DELTA

Closed:

- `B_GAP_NODE0071_SHARED_LC_TOPOLOGY_CYCLE_PENDING`

Opened:

- `B_GAP_NODE0071_POST_SUM_S1_MASK_WIDE_STAGE_TRANSITION_CONJUNCTION_PENDING_LEAF`

## Successor and frozen surface

Final successor:

- identity: `r5_n71_gap_v46_stage_transition_mask_diag`
- class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- candidate release: `false`
- evidence ceiling: `E2_LOCAL_ONLY`
- ZIP pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n71_gap_v46_stage_transition_mask_diag.zip`
- ZIP bytes: `1943896`
- ZIP SHA256: `97752ec7a3e11dbc41c814d0dfabfb055e52f897deff48fa53573f8c593ea555`
- sidecar receipt SHA256: `ee988a7f766a7ea6eb09ea98c26d2a201322349dceb7b74b79bede61cd7c31a1`

The observer is owner-clock sampled at `u_NDP_Top_new.clk`, uses at most 128
edge/rate-limited records plus a 1,048,576-cycle heartbeat, and distinguishes
all remaining low-cost candidates in one package: selected-slice compute
unfinished, selected-slice noncompute ready-low, local queue pending, global
config readiness, and other mask-match factors.

Frozen byte-equality:

- 64 input/golden numeric files: byte-equal
- 161 config/mapping/bitstream/execplan members: byte-equal
- timeout/backpressure/functional RTL: unchanged
- sum/tail/workload/config/golden: not recomputed

Unreleased intermediate identities v42-v45 were preserved outside package
storage and were never marked runnable. v46 is the only GAP pending identity.

## Fixed server return publication

Production runner keeps a literal, non-configurable server-only destination:

- ZIP: `/home/panqs/ndp/simresult/r5_n71_gap_v46_stage_transition_mask_diag_return.zip`
- sidecar: `/home/panqs/ndp/simresult/r5_n71_gap_v46_stage_transition_mask_diag_return.zip.sha256`

Normal, compile-fail, timeout, HUP, INT, and TERM share `finalize()`. The
publisher stages, verifies, checks target conflict and duplicate absence, then
atomically renames the ZIP and sidecar. No same-name return may remain under
the NDP root, package root, install root, run root, or cwd.

Local audit did not create or write `/home/panqs/ndp/simresult`. It parsed the
exact production runner and used an isolated fresh-extract harness whose only
environmental deltas were a temporary namespace mapping, Windows CRLF identity
normalization, and test-only signal injection. None is present in the final
ZIP and the production destination is not configurable.

Unique server invocation after extracting the ZIP:

`cd r5_n71_gap_v46_stage_transition_mask_diag && bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`

## Final validation

- deterministic double build: PASS
- final ZIP rule self-audit: `PASS=true`, `errors=0`
- final audit SHA256: `05215c1f663e0ec18a5814aee2fdc51bd0f6aed093e7a0c3a91eafc6dd9e66f5`
- focused HDL syntax/scope: PASS; SHA256 `9f54f2b54a618f59c113be93d5c4a1219547550a719f13bd41c04d62e19ce5ac`
- fixed-result runner/finalizer: PASS; SHA256 `7124ff4d07cab0262ebb47a0061d1c1900e9ea7c726fba350e07206f8ac71ef6`
- predicate trace: PASS; SHA256 `76d62f306bbfd6025f3dcbc0d16629b6ffb79d768f6ab50b43265a64b632a5a1`
- storage audit: PASS
- GAP pending set: exactly `r5_n71_gap_v46_stage_transition_mask_diag`
- v41 disposition after formal return: `tested`

Positive controls:

- safe normal simulator exit reaches shared finalizer and publishes a return;
  because no DUT formal D exists, the numeric conjunction fails closed with
  48 missing items and runner status 2
- compile-fail, HUP, INT, TERM each publish a signal-safe partial return
- exact package observer logic and cloud-current `global_exec_manager` private
  leaves compile under Icarus Verilog 12.0 focused scope

Negative controls all fail closed:

- fixed target conflict, original-location duplicate, corrupt sidecar
- configurable result root, removed fixed collect argument, TERM bypass
- removed declaration/update, misspelled consumer/private leaf/wrong sibling
- changed owner clock
- removed feature enable/heartbeat/time0 binding/parser call

## Reports

- v41 machine report:
  `artifacts/operator_config_validation/r5-gap-node0071-v41-return-analysis/report.json`,
  SHA256 `8678ef589dd8833d60441014df9813da08b306c6a7d9c796d22ad1a155570ab6`
- closure report:
  `artifacts/operator_config_validation/r5-gap-node0071-v41-return-analysis/closure_report.json`,
  SHA256 `a444f20b6be856326a8371c3d1cdbb94de7f36cb5b883ca02ab062093a736b12`
- storage index:
  `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`,
  SHA256 `11fb3aaab02b1d6ea254635c3e9fe10174900f0032cf0711bf27ccf97412d7ec`

## Rule result

RULE_CONFIRMATION:

- `CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`
- `CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`
- `CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001`
- `CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001`
- `CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`
- `CDA-GAP-HANDSHAKE-CONJUNCTION-FACTOR-OBSERVABILITY-001`

RULE_DELTA_PROPOSAL: `NONE`.

No production correctness, E3, E4, E5, or complete GAP claim is made.
