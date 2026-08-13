# Conv native-four-lane p9b formal RETURN → p10 triggered successor

- Date: 2026-08-06
- Unique owner/mainline return target:
  `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Operator family: frozen node0004 native four-lane Conv only
- Serialized Conv baseline: preserved and not modified
- Functional RTL/public rules/plan: not modified
- Server upload/run/lease: not performed

## Current rule and identity receipts

The current disk was read before analysis/build.  Relevant receipts:

- `.agents/agent.md`:
  `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f`
- `.agents/plan.md`:
  `ebb4863e83ca8f3a78ca12a4f10d6c4ba060cdc310f4f0d7c69fe0983b3c7bb9`
- generation index:
  `2697fec8192f5008a0b5f288a4c38c36e9f493ff85db264479e4c5a88b03b706`
- server-package rule:
  `5540e9c724e9c313e9a874a8251ad291328d4df80f01382ca091520893e757a1`
- config rule:
  `dc5243226bacde799b368d37fb9eb656e6b7e3d33a0a2932ae72ab35415ae3e1`
- NDP hardware semantics:
  `603d57805bc5a5bdfca7406c402bc94db60c06ea6682493d672abb91671b1055`
- INT8 SA rule:
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- exact UINT8 tail rule:
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`
- hardware simulator entry:
  `0b271cd2ba4f16a0fd277d8f52f926be0ef51431ab9a995042363215afb9caa6`
- cloud authority used for causal classification:
  `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`

## Formal p9b return identity and internal receipt

- Formal external return:
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_0cc_p9b_tx5_return.zip`
- bytes: `105219`
- SHA256:
  `96a4d9678b92dd5b74eb010de1fe27303dfc26a856f553623b6a162e999fab0d`
- Adjacent sidecar: absent; only external transport is user-attested.
- Exact source p9b ZIP bytes: `5814296`
- Exact source p9b SHA256:
  `d85429b61e8270d0c4108bfdcdf3a66bce44a437b8aab96b0412a5555dffb085`
- Current archive after consumption:
  `artifacts/operator_config_validation/r5-server-test-packages/tested/conv_native_four_lane/r5_n4_0cc_p9b_tx5/r5_n4_0cc_p9b_tx5.zip`

The return CRC, one-root layout, internal `RETURN_MANIFEST`, internal
`RETURN_ALLOWLIST`, source package manifest binding, exact returned set and
per-record hashes all pass.  Package/install/observer preflights pass.

Machine analysis:

- `outputs/conv_native_four_lane_0ccae916_p9b_return_analysis/report.json`
- bytes: `18027`
- SHA256:
  `775ab5438a5a1945f3a00010c48c50cb014c15f0ebac6189b4188a3828526931`
- analyzer:
  `tools/analyze_conv_native_four_lane_0ccae916_p9b_return.py`
- analyzer SHA256:
  `2e9cc5f728669d561fb7232c7142075517719a895f461a9971f46ff1c353e441`

## Production execution and tx5 adjudication

- compile exit: `0`
- run exit: `125`
- signal: `INT`
- simulator feature marker: present
- c0 exec start: present
- natural c0 terminal: absent
- formal 320D: absent by p9b design, therefore neither pass nor fail
- E3/E4/E5/performance: not claimed

The threshold-5 configuration decisively crosses the former p8f boundary:

- p8f last qualified total: `52,859`
- p9b maximum qualified total: `139,198,964`
- last sampled `clk_sg` cycle: `94,860,826`
- host observation: `14,132 s`
- decision:
  `PARTIAL_CAUSAL_IMPROVEMENT_NOT_TERMINAL_CLOSURE`

Last qualified c0 counts:

- request: `16,16,16,14,32`
- read response: `16,16,16,12,0`
- write request: `0,0,0,0,32`
- ARM request: `8,5,10,2,6,3`
- ARM response: `3,2,8,0,4,0`
- ARM finish: `0,0,0,0,0,0`
- SA input/output: `28 / 3`
- MSE4 accepted index: `2`
- Buffer5 write-active-cycle/read: `46,399,378 / 122`
- `slice_finish`: `0`

The p9b Buffer5 write counter counts an active `wr_en` level every cycle.  Its
large value can therefore be caused by one held level and is not proof of
accepted write transactions.

## Actual/cloud ARM causal risk

Seven of the eight compiled causal leaves match cloud `0ccae916`.  The only
mismatch is the active `Array_Request_Manager.sv` terminal cone:

- cloud raw SHA256:
  `026019ed9643b3b7d83bc0888c4f5b89fc4776015524df1c69bacbab5315e557`
- actual production SHA256:
  `7892b4345b3a71024126b57a3a0126c489e0bffa2f520e64fa6cf2ed705f9894`
- actual bytes: `15654`
- actual source bytes returned: no

Per current cloud-authority rule, this identity difference did not block
simulation.  It remains a live causal risk because every ARM finish count is
zero, but it is not a uniquely proven root cause without the actual source
bytes and more discriminating dynamic boundaries.

## LPG / FD / root-cause decision

- `LAST_PROVEN_GOOD`: c0 exec start plus memory/request/ARM/SA/MSE4/Buffer5
  activity, with tx5 crossing the old p8f freeze.
- `FIRST_DIVERGENCE`: activity remains visible while ARM finish stays zero,
  SA accepts 28 inputs but only 3 outputs, MSE4 accepted index stops at 2, and
  `slice_finish` never occurs.
- `HANG_ROOT_CAUSE`: not unique. Remaining candidates are actual ARM terminal
  semantics, MSE4 last/index propagation, and SA-output/Buffer5 acceptance.
- terminal classification:
  `TX5_CROSSED_OLD_BOUNDARY_C0_TERMINAL_STILL_OPEN`

Closed blockers:

- `B_CONV_NATIVE4_TRANSOUT5_DID_NOT_CROSS_P8F_BOUNDARY`
- `B_CONV_NATIVE4_SIMULATOR_OR_FEATURE_NOT_STARTED`

Preserved blockers:

- `B_CONV_NATIVE4_ACTUAL_ARRAY_REQUEST_MANAGER_IDENTITY_CAUSAL_RISK`
- `B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN`
- `B_CONV_NATIVE4_TERMINAL_PROPAGATION_UNLOCALIZED`
- `B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN`
- `B_CONV_NATIVE4_FORMAL_320D_UNPROVEN`
- `B_CONV_NATIVE4_E3_E4_E5_UNPROVEN`

Because c0 did not close, the delegated branch does not advance directly to
27-run/320D.  One bounded, always-on triggered causal successor is required.

## Fresh p10 successor

Identity: `r5_n4_0cc_p10_trig`

Scope:

- exact p9b tx5 c0 workload/config/mapping/bitstream/execplan retained;
- SCA only normalizes the fresh install identity;
- numeric/W3/golden/address evidence reused byte-for-byte;
- no functional RTL, DUT input, ready/backpressure, timeout, or internal
  tensor replay change;
- adds bounded stage-gated triggered snapshots for request/ARM/SA/MSE4/
  Buffer5/terminal boundaries;
- separates Buffer5 active cycles from write-enable rising edges;
- signal-safe finalizer always emits a bounded canonical summary;
- remains c0 diagnostic only, without formal 320D.

Established config inversion is unchanged and is not a server-performance
claim:

- logical products / serialized occurrences: `205,520,896`
- native occurrences: `51,380,224`
- compute occurrence reduction: `4.0x`
- weight payload: `262,144 → 65,536 bytes` (`4.0x`)
- activation per producer reduction: `4.0x`
- native aggregate B+B' activation traffic:
  `25,690,112 bytes` (`2.0x` versus serialized single-B physical bytes)
- maximum useful lane utilization: `25% → 100%`

Final pending pickup:

- `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p10_trig.zip`
- bytes: `5823887`
- SHA256:
  `25c9c01fe7feb42ec8de3eef701386420e7ab014ad24630022539d97a9fb03b5`
- status: `PACKAGE_READY_NOT_RUN`
- candidate release: `false`

The operator-facing pending directory remains ZIP-only.  Sidecar/build/final
audit receipts are under:

`artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p10_trig/`

## Local release-gate evidence

The final exact ZIP passes:

- deterministic dual build and deterministic ZIP replay;
- safe one-root ZIP, CRC and exact manifest set;
- package preflight and observer SHA guard;
- p9b→p10 changed-surface closure: 87 immutable workload members exact;
- focused Icarus syntax/scope positive;
- declaration deletion and wrong-sibling negatives;
- no new private XMR (only clk/reset references already compiled in p9b);
- exact HDL event trace for all six required triggers:
  `FIRST_QUEUE_FULL`, `FIRST_BRANCH_DIVERGENCE`,
  `NO_PROGRESS_WINDOW`, `TERMINAL_GAP`, `STAGE_TRANSITION`,
  `EXIT_OR_SIGNAL`;
- reset/inactive, simultaneous-event, threshold, stable-level, terminal and
  signal/finalizer predicate neighbors;
- canonical finalizer positive and malformed-record fail-closed negative;
- exact final runner natural and signal safe-stub chains;
- actual/cloud SHA mismatch remains nonblocking through simulator stub;
- exact bounded return allowlist and return sidecar;
- single release-gate matrix all blocking applicable gates `PASS`;
- materialized config `receipt_reuse_byte_equal`;
- numeric/W3/golden `record_only`, not repeated.

Final audit:

- `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p10_trig/r5_n4_0cc_p10_trig.final_zip_audit.json`
- bytes: `17132`
- SHA256:
  `d652f31d3f82cc6b84bd40dd8c054b5eb74f08c98782607f7b5639646d1d0b01`

Key implementation assets:

- observer append SHA256:
  `3306735bd6b63cc92bc536c21cd0704303c5c104e853c6fe20904aadff7943f9`
- triggered finalizer SHA256:
  `9a275d0282697b54aa8316de668f2ccccbd3bab9ca85b7e7d903488d95ee863c`
- profile SHA256:
  `94a7e1c44dd5e9fa9bef3730587a79f0b09caa87fe515d7c8eaf688bcfa354b5`
- builder SHA256:
  `b72cc3e3a57a6fa8ccd2740de5b2f5a6a974ba07473a79cc704724b99a76738f`
- validator SHA256:
  `2f91b9459c041273d7b3155f9fe0b3fe4050df4b4d70117632246ce47cd3561d`

## Storage rotation

`CDA-SERVER-PACKAGE-STORAGE-ROTATION-001` is closed:

- p9b formal return was consumed, and its complete pending artifact set is now
  under `tested/conv_native_four_lane/r5_n4_0cc_p9b_tx5/`;
- p10 is the only pending native-four-lane identity;
- pending is flat ZIP-only;
- p10 sidecar/audits are in `pending_receipts`;
- final storage index `pass=true`;
- storage-index SHA256:
  `e2c1ca1bfe0f113a27a2775f913a6c90d398b07e1ae3ee2ab8fb6868bf3d57c3`.

The first rotate invocation exposed a recoverable tool-order issue when the
selected `new_evidence` file was itself part of the moved source set.  All
moves were reversed without overwrite, the pre-rotation audit was re-passed,
an immutable external audit receipt was used, and the same storage tool then
completed rotation and post-audit successfully.  No package bytes were lost
or changed.

## Required server command and expected return

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/server_root
```

Expected return:

`r5_n4_0cc_p10_trig_return.zip`

The next formal return must recover actual compiled production identity,
triggered summary/log, c0 `slice_finish`/natural terminal decision and the
canonical result conjunction.  If c0 closes, the following fresh successor
may advance directly to 27 natural runs plus formal 320D.  Before that return,
no E3/E4/E5 or production performance claim is permitted.

## Rule feedback

`RULE_CONFIRMATION`

Confirmed:

- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`
- `CDA-SERVER-ALWAYS-ON-TRIGGERED-CAUSAL-OBSERVABILITY-001`
- `CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001`
- `CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001`
- `CDA-SERVER-CLOUD-GITHUB-RTL-AUTHORITY-NONBLOCKING-DIFF-001`
- `CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`
- `CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001`

`RULE_DELTA_PROPOSAL=[]`

The rotate implementation ordering note above is a tooling hardening item,
not a semantic gap in the published rule.
