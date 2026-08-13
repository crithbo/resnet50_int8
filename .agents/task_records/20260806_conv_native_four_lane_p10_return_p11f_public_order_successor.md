# Conv native-four-lane p10 formal return → p11f public-order successor

## Scope and immutable inputs

- Owner scope: native four-lane Conv node0004 only.
- Mainline return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`.
- Formal p10 return:
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_0cc_p10_trig_return.zip`
  - bytes: `97182`
  - SHA256:
    `568a0c63f0db3e21a63a9fae94a711f91583fabb4f00a1a47ced0d613d721434`
- Exact p10 source:
  - SHA256:
    `25c9c01fe7feb42ec8de3eef701386420e7ab014ad24630022539d97a9fb03b5`
- p10 return analysis:
  `outputs/conv_native_four_lane_0ccae916_p10_return_analysis/report.json`
  - SHA256:
    `9b90164411d1c48f3b6c042e02bccdfcd68a018c44408c53e63c0a40b6dc55ba`

No functional RTL, serialized Conv asset, public rule, plan, numeric/W3/golden
or materialized workload/config was modified.

## RETURN_ANALYSIS

Status:
`EXTERNAL_HUP_AFTER_QUALIFIED_C0_STALL_SUCCESSOR_REQUIRED`.

Canonical classification:
`LONG_RUNNING_HANG_CONFIRMED_BEFORE_EXTERNAL_HUP`.

The HUP receipt is genuine, but it is not classified as
`PARTIAL_INTERRUPTED`: before HUP, the exact triggered observer recorded
four consecutive qualified no-progress windows. The last qualified key
remained `302`; request/ARM/SA/MSE4 accepted-transaction counts and the
Buffer5 rising-edge count were frozen. The host-side observer's former
`STILL_PROGRESSING` conclusion was caused by counting held Buffer/Buffer_AG
levels every cycle rather than accepted transactions.

Observed execution:

- compile status: `0`
- run status: `125`
- signal: `HUP`
- simulator and triggered feature started: yes
- natural slice finish: no
- formal D: `0` by p10 diagnostic design

Qualified c0 sequence:

- exec: cycle `1,030,926`, key `0`
- first queue full: key `203`
- first SA divergence: key `217`
- terminal gap: cycle `2,079,736`, key `302`
- four no-progress windows:
  `3,128,078`, `4,176,654`, `5,225,230`, `6,273,806`
- final accepted counters:
  - requests: `[16,16,16,138,32]`
  - ARM requests: `[8,5,10,2,6,3]`
  - ARM responses: `[3,2,8,0,4,0]`
  - ARM finish: `[0,0,0,0,0,0]`
  - SA input accepts: `28`, including last-index masks for `4` and `5`
  - SA output accepts: `3`, with no output-last
  - MSE4 accepts: only index `1`
  - Buffer5 held-active cycles: `5,242,646`
  - Buffer5 qualified rising edges: `1`

Production compile identity was collected from the actual VCS compile and is
nonblocking provenance. Three leaves differ from current cloud authority:

- `Array_Request_Manager.sv`:
  `7892b4345b3a71024126b57a3a0126c489e0bffa2f520e64fa6cf2ed705f9894`
- `Buffer_AG_Idx_Queue.sv`:
  `593b620820e39c27eec57a633f78e6855946a3c80d4ccab361c6aeecbf3d1034`
- `SA_PE_Float_Control.v`:
  `b4007536f8e26f753284bd7bb6d07516b943cd1a9facc8032abce2f4638aac5a`

Compile and simulator execution passed the identity collection point. The
identity delta therefore does not replace the c0 evidence and does not by
itself block simulation.

Blocker delta:

- closed:
  - `B_CONV_NATIVE4_INTERRUPTED_WHILE_QUALIFIED_PROGRESS`
  - `B_CONV_NATIVE4_BUFFER5_HELD_LEVEL_MISTAKEN_FOR_TRANSACTIONS`
  - `B_CONV_NATIVE4_SIMULATOR_OR_TRIGGER_FEATURE_NOT_STARTED`
- preserved:
  - `B_CONV_NATIVE4_ARM_FINISH_ZERO_CAUSAL_LEAF`
  - `B_CONV_NATIVE4_SA_OUTPUT_LAST_PROPAGATION_CAUSAL_LEAF`
  - `B_CONV_NATIVE4_MSE4_BUFFER5_ACCEPTANCE_CAUSAL_LEAF`
  - `B_CONV_NATIVE4_C0_SLICE_FINISH_UNPROVEN`
  - `B_CONV_NATIVE4_27_NATURAL_TERMINALS_UNPROVEN`
  - `B_CONV_NATIVE4_FORMAL_320D_UNPROVEN`
  - `B_CONV_NATIVE4_E3_E4_E5_UNPROVEN`

## p11f successor

Two unreleased build identities were rejected before storage publication:

- p11d: inherited runtime preflight expected the obsolete functional-fix
  candidate class.
- p11e: the longer fresh identity exposed a stale inherited ZIP-member path
  budget.

Both remain failure receipts only. Neither was placed in `pending`.

Final candidate:

- identity: `r5_n4_0cc_p11f_pubord`
- status: `PACKAGE_READY_NOT_RUN`
- class: diagnostic-only, `candidate_release=false`
- pickup ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_0cc_p11f_pubord.zip`
- bytes: `5836137`
- SHA256:
  `3198b62bf609f213f9355f8ddaa45df90dd05ea61443fe859247d0b9f3cd0acf`
- final audit:
  `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_native_four_lane/r5_n4_0cc_p11f_pubord/r5_n4_0cc_p11f_pubord.final_zip_audit.json`
- final-audit SHA256:
  `801d0817c5151bda212ca3996bb1bd4fcdc417e6e9b78187edb0781f6a0c0c48`

The workload/config/address/numeric/W3/golden causal slice is normalized
byte-equal to p10. p11f changes only the diagnostic observer/finalizer,
fresh package identity, exact runtime candidate-class/path-budget contract,
and fixed server return publisher.

p11f uses only already production-compiled public monitor surfaces. It stores
a bounded ordered trace of accepted SA input tags, accepted SA output tags,
and MSE4 accepts, and separately records raw SA-output valid/tag change,
Buffer-facing ready, blocked level and accepted progress. This distinguishes
the remaining earliest divergence among:

- SA output generation stops after accepted inputs;
- SA output is held by Buffer backpressure;
- SA output reaches Buffer but MSE4 does not consume it.

## Release gates

The final exact ZIP audit passed:

- safe ZIP, single root, CRC, exact set and sidecar;
- deterministic double build;
- package and install preflight;
- normalized p10 workload/config byte equality;
- focused Icarus compile/simulation and actual-consumer negative controls;
- public-surface observer ownership and no new DUT hierarchy reference;
- final exact predicate trace, including conjunct neighbors, duplicate/missing
  records and stable-level-not-progress negative;
- exact production runner Bash syntax and compile → nonblocking identity →
  simulator ordering;
- fixed literal server result root, with no configurable production path;
- normal, compile-fail, INT and TERM shared-finalizer publication positives;
- result conflict and duplicate-receipt fail-closed negatives;
- no functional RTL and no runtime-D payload;
- exact path budget and current rule receipts.

`release_gate_matrix.materialized_config=receipt_reuse` because the exact
workload/config/address bytes are unchanged. Numeric/W3/golden, unrelated RTL
and formal D were not rerun.

The local audit did not create, map or write
`/home/panqs/ndp/simresult`. It exercised the exact publisher logic only in
disposable local copies whose fixed path literal was replaced outside
production bytes.

## Storage rotation

p10's four-file package set was moved to
`tested/conv_native_four_lane/r5_n4_0cc_p10_trig`. Native-family pending now
contains exactly one package, p11f. The pending pickup directory is ZIP-only;
sidecar, validation and final audit are under `pending_receipts`.

The generic rotation command moved both sets, then attempted to hash the new
evidence through its old pre-move path and stopped before index write. A
family-scoped recovery revalidated the already-moved p10/p11f sets and rewrote
the storage index from the actual tree. No other-family package was moved.

- storage audit:
  `outputs/conv_native_four_lane_0ccae916_p10_return_analysis/p11f_storage_audit.json`
- SHA256:
  `ff7c74c8a731904c785dcea180ba3fcc4f2e656cbe98bfd34d8e6bf829e74128`
- final counts: pending `4`, tested `45`, superseded `23`
- native pending: `["r5_n4_0cc_p11f_pubord"]`

## Server handoff

Command:

`bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy02`

The server production runner publishes the only return pair atomically:

- `/home/panqs/ndp/simresult/r5_n4_0cc_p11f_pubord_return.zip`
- `/home/panqs/ndp/simresult/r5_n4_0cc_p11f_pubord_return.zip.sha256`

Expected receipt includes `duplicate_absent=true`. No same-name ZIP or
sidecar may remain under the package root, install namespace, `NDP_copy0x`,
run root or launch cwd.

## Claim boundary and rule feedback

p11f is a c0 causal diagnostic. It does not contain formal 320D and makes no
E3/E4/E5, natural-terminal, numeric-correctness or performance claim. A full
27-run/320D successor remains conditional on closing c0.

`RULE_CONFIRMATION`:

- `CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001`
- `CDA-SERVER-TIMEOUT-MANUAL-INTERRUPT-HANG-FIRST-001`
- `CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001`
- `CDA-SERVER-DIAGNOSTIC-DECISION-CANONICAL-RECORD-001`
- `CDA-SERVER-RESULT-GATE-CONJUNCTION-001`
- `CDA-SERVER-RETURN-TO-SUCCESSOR-CONTINUOUS-CLOSURE-001`
- `CDA-SERVER-DIAGNOSTIC-PREDICATE-TRACE-UNIT-001`
- `CDA-SERVER-OBSERVER-PUBLIC-SURFACE-OR-XMR-PROOF-001`
- `CDA-SERVER-LOCAL-RELEASE-GATE-IMPACT-APPLICABILITY-001`
- `CDA-SERVER-RETURN-FIXED-SIMRESULT-ATOMIC-PUBLISH-001`
- `CDA-SERVER-PACKAGE-STORAGE-ROTATION-001`

`RULE_DELTA_PROPOSAL=NONE`.
