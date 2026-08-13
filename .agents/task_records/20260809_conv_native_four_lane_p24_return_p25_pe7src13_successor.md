# Conv native four-lane p24 formal return and p25 PE7-source13 successor

Date: 2026-08-09  
Owner: native four-lane Conv performance branch  
Mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`

## Formal p24 identity and receipt

- Formal return: `C:/Users/15383/Downloads/r5_n4_0cc_p24_selport_r1786203016970364534_4152336_return.zip`
- Return bytes: `2067865`
- Return SHA256: `8420a8bc99daca2bd0aabbc425826b8dcb01b7560ddbf164c3339d7da9fff5bf`
- Execution identity: `r1786203016970364534_4152336`
- Exact source p24 bytes: `5880634`
- Exact source p24 SHA256: `4690da16077c60c91d7de7c5fd1042f17bdb8db844d59ae4169528a6ba318c28`
- Source after formal consumption: `artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p24_selport/r5_n4_0cc_p24_selport.zip`
- Machine analysis: `outputs/conv_native_four_lane_0ccae916_p24_return_analysis/report.json`, bytes `9363`, SHA256 `79c02876dd43d0d0bf83f859a1eef87b1e81aab6a81bb44f051ca548fd9dca37`

The return CRC, single root, path safety, exact set, allowlist, embedded source manifest,
per-execution basename, install-only/root-direct-set, package/install/observer/path-budget
preflights and production compile all pass. Production compile exited zero and simulation
started. The run was later externally interrupted with `INT` (`run_exit_status=125`) after a
qualified c0 stall. It did not reach natural `slice_finish`.

p24 is c0 diagnostic-only and has no formal-D payload by construction. Therefore the absence of
formal D is neither a mismatch nor a pass. Natural 27/27, formal 320/320, E3, E4, E5 and performance
remain unclaimed.

## Public ledger adjudication

p24 closed three alternatives:

- the configured MSE4 input1 source is consistently `src_id=13`;
- `Stream_Engine_Connect` output and `Memory_WR_Stream_Engine` input are byte-equal on every emitted
  row (`port_eq=1`);
- a valid/backpressure-qualified index-8 transfer reaches both public boundaries.

The p24 observer itself hardcoded PE7 as source 7. Current exact RTL defines
`MSE_SRC_LC_NUM=12`, `MSE_SRC_PE_NUM=6`, and for MSE4 the PE-source formula maps source 13 to PE7;
source 7 remains in the LC class. Consequently p24 `src_is_pe7=0`, `select_eq=0` and the 128
source-side event rows reflect an unselected source7, not a functional config/Connect failure.

```text
LPG = production compile/sim + configured src13 + Connect==Memory-WR + qualified index8 transfer
FD  = package-local observer assumes PE7 source7 instead of source13
HANG_ROOT_CAUSE = ROOT_NOT_YET_UNIQUE_ACTUAL_PE7_SOURCE13_TO_CONNECT_EDGE
classification = PACKAGE_LOCAL_OBSERVER_SOURCE_ID_FORMULA_ESCAPE
```

Actual production `IGA_Interconnect.sv` was not collected by p24, so current local formula alone is
not promoted to an actual-production identity claim. A single fresh successor is required.

## p25 continuous-closure release

Disposition: `PACKAGE_READY_NOT_RUN / PERFORMANCE_DIAGNOSTIC_CANDIDATE`;
`candidate_release=false`.

- Pickup ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p25_pe7src13.zip`
- ZIP bytes: `5882004`
- ZIP SHA256: `d2c0e853391f012273e6d6bb2e07c6e3bcbee0d895db5b866c77526c580390e6`
- Command: `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`
- Expected return: `/home/panqs/ndp/simresult/r5_n4_0cc_p25_pe7src13_r<epoch-ns>_<pid>_return.zip`

p25 changes only fresh identity, package-local observer source mapping 7→13, exact result schema,
manifest/return binding, and post-compile identity collection for `IGA_Interconnect.sv`. The
source13 progress predicate also requires the configured selector to equal 13. Numeric/W3,
workload/config/mapping/bitstream/execplan/SCA/golden/timeout, ISA, functional RTL, hardware and
active ndp-sim remain frozen. Installed payload is 87/87 byte-equal and both SCA files are
identity-normalized equal to p24.

Actual performance inversion is inherited byte-exact from the frozen package: native occurrences
`51,380,224` versus serialized `205,520,896` (`4.0x` reduction), weight bytes `65,536` versus
`262,144` (`4.0x`), activation per producer `12,845,056` versus `51,380,224` (`4.0x`), and maximum
useful lane utilization `100%` versus `25%`. These are package/config inversions, not server E4/E5
claims.

## Exact p25 local gates

- Deterministic double build: PASS.
- Family audit: `outputs/conv_native_four_lane_0ccae916_p25_pe7src13/p25_family_audit.json`,
  bytes `426957`, SHA256 `cc6888675f7e96616539f2cf8a402515d7575cd3374f50b1361946205362bc0b`, PASS/errors0.
- Runner harness: `outputs/conv_native_four_lane_0ccae916_p25_pe7src13/p25_runtime_layout_harness.json`,
  bytes `9611`, SHA256 `fe6cf3310981e040570567b2be9a1eea5ee6af86f902852c365f9ccf23f5cf28`;
  normal/preflight-fail/compile-fail/HUP/INT/TERM all close through the shared finalizer, fixed
  simresult publication and unchanged NDP-root direct-set.
- Shared runtime-layout validator: `outputs/conv_native_four_lane_0ccae916_p25_pe7src13/p25_shared_runtime_layout_from_harness.json`,
  bytes `25208`, SHA256 `d4efc88b90f72de6a5227a821ce106e4e34c15611b87fd9a8328484486dd4906`,
  PASS/errors0, exact-final-ZIP invocation count one.
- Shadow profile: `outputs/conv_native_four_lane_0ccae916_p25_pe7src13/server_package_build_profile.json`,
  bytes `13012`, SHA256 `2a4e23d60a2f298ef98f1aa98d0417ca2fe69c87ef273a23c4ab0f87973374b0`,
  contract valid/errors0.
- Final audit: `outputs/conv_native_four_lane_0ccae916_p25_pe7src13/r5_n4_0cc_p25_pe7src13.final_zip_audit.json`,
  bytes `4734`, SHA256 `973638d91b634e52a43b0b9845d68a797dc56928aed57d172f9cc3d65328703b`,
  `PACKAGE_READY_NOT_RUN`.
- Actual-production identities required in the formal p25 return include
  `IGA_Interconnect.sv`, `Stream_Engine_Connect.sv` and `Memory_WR_Stream_Engine.sv`; identity
  differences remain nonblocking for simulation and are adjudicated in the causal cone.

The current multiclass gate is blocking-applicable and passes: PE7-source13, Connect and
Memory-WR qualified classes are encoded together in one exact `event_mask` record. Simultaneous
three-class input produces `0x7`; priority collapse, missing-class, wrong-source progress and
state-as-progress controls all fail closed. No single-label priority arbiter can discard a lower
class.

Storage rotation passes: p24 is retained under `tested`; p25 is the sole
`conv_native_four_lane` pending ZIP; pending remains flat ZIP-only and all sidecars/audits remain
under `pending_receipts`.

## Rule feedback

`RULE_CONFIRMATION`:

- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`
- `CDA-SERVER-DIAGNOSTIC-EVENT-QUALIFICATION-001`
- `CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001`
- `CDA-SERVER-DIAGNOSTIC-LOGGER-PARSER-EXACT-FORMAT-TRACE-001`
- `CDA-SERVER-DIAGNOSTIC-MULTICLASS-EDGE-NO-LOSS-001`
- `CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001`
- `CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001`
- `CDA-SERVER-INSTALL-SUBTREE-RUNTIME-LAYOUT-001`
- `CDA-SERVER-NDP-ROOT-TOPLEVEL-NO-NEW-ENTRY-001`
- `CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`
- `CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`

No non-synonymous public-rule gap was found. No server/upload/run/lease action was performed.
