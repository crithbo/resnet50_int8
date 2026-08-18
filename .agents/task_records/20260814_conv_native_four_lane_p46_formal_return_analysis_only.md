# family.conv.native p46 formal return analysis only

Date: 2026-08-14 (Asia/Shanghai)

## Ownership and explicit scope

- `role_id`: `family.conv.native`
- owner epoch: `2`
- registry epoch: `6`
- current mainline is resolved from the current owner registry at notification time
- dispatch: `FORMAL_RETURN_ANALYSIS_ONLY / NO_SUCCESSOR_BUILD`
- status: `RETURN_ANALYSIS_COMPLETE_ANALYSIS_ONLY_NO_SUCCESSOR`
- no successor was built; no pending package or receipt was rotated; no upload, lease, connection, server run, or other server action occurred
- no plan, rule, owner registry, functional RTL, config, numeric, workload, or golden surface was changed

## Previous progress and current purpose

Previous-version progress: p41 proved production compile beyond the Datahub repair; p42 corrected the two-bit vector valid/ready scalar false-negative. p45 attempted broad observer-only localization, but its non-native provider assumption failed production compile at unresolved DesignWare modules before simulation.

Current-version purpose: p46 preserves the frozen p42-equivalent MSE4 wdata/slice-finish target, enters the actual native production flow without server-provider preflight, and returns exact native-flow compile, simulation, observer, partial-exit and compile-core evidence while closing p45's return defects.

## Formal return and integrity

- exact return: `C:/Users/15383/Downloads/r5_n4_0cc_p46_nativeflow_r1786677331882312446_2098382_return.zip`
- package/execution/attempt: `r5_n4_0cc_p46_nativeflow` / `r1786677331882312446_2098382` / `a0`
- exact return bytes: `83030787`
- exact return SHA-256: `822a8964e8f5b73457eaf9cd57596ea8a1f882f6b70afbce1daacb0ed5cb73c9`
- the original ZIP is preserved unchanged
- one-root/member exact-set, duplicate/missing/unexpected member, manifest identity and CRC checks pass
- every manifest-receipted member was streamed and independently matched for exact bytes and SHA-256
- the returned package manifest, observer contract, native-flow differential contract and source-bound binding are byte-equal to the exact pending source package members
- the 3,249,170,876-byte observer event member was not bulk-extracted; it was stream-validated through all 13,648,779 records with contiguous sequence, monotonic simulation time, exact same-attempt identity and no parse error

Machine-readable analysis:

- `outputs/conv_native_four_lane_0ccae916_p46_return_r1786677331882312446_2098382/report.json`
- `outputs/conv_native_four_lane_0ccae916_p46_return_r1786677331882312446_2098382/p46_stream_integrity_and_events.json`

## Actual production result

- actual native production compile exit: `0`
- simulation started: `true`
- actual simulator exit/signal: `125 / INT`
- timeout: `false`
- natural terminal: `false`
- returned last event time: `8,530,361,250 ps`
- actual VCS argv includes the native DesignWare `sim_ver` provider and the two exact package-local observer sources
- the selected production `Memory_WR_Stream_Engine.sv` exists, matches its expected SHA-256, contains every required bound symbol and has compiled-source status `COMPLETE`

The package publication record named only `bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01`, while the exact return records actual cwd/compile/simulation root `/home/panqs/ndp/NDP_copy02`. This is `EXECUTION_ROOT_DRIFT_RESTRICTED_DIAGNOSTIC_CONSUMPTION`. Exact selected target-RTL content and package-observer identities still match, so the compile and selected causal facts below are consumable as restricted diagnostics; they cannot be described as execution of the published command and cannot support an integration or E3-E5 identity claim.

Therefore p45's unresolved DesignWare compile stop is closed as a package-derivation/non-native-provider-assumption issue; it is not reproduced by the actual native flow. The `compile_first_error` member in this compile-success return contains only warnings and must not be interpreted as a true compiler error.

The process supervisor did not prove clean shutdown: it received signal 2 and recorded one owned simulator descendant after TERM/KILL/reap. This is `TEST_INFRASTRUCTURE_CLEANUP_INCOMPLETE`; it is not a DUT root-cause verdict, and this session performed no server check.

## Observer facts and causal boundary

The event stream contains 13,648,752 EVENT rows, 26 heartbeat rows and one PARTIAL_EXIT. It is complete for the returned interval, untruncated and unsampled, with no hard byte/event cap. The 100,000,000-byte observer threshold was exceeded only as a warning.

Selected exact-instance qualified evidence:

| Boundary | Qualified events | Last time |
| --- | ---: | ---: |
| each of SA lanes 0-7 accepted output data | 14 | `2,446,467,000 ps` |
| MSE4 descriptor accept | 18 | `2,446,463,000 ps` |
| MSE4 buffer-data accept | 18 | `2,446,467,000 ps` |
| MSE4 MemAG output accept | 9 | `2,446,459,000 ps` |
| MSE4 wdata output accept | 21 | `2,446,467,000 ps` |
| Buffer row2 clear-owner event | 3 | `2,446,448,000 ps` |
| ARM row2 token-state event | 3 | `2,446,448,000 ps` |
| MSE4 slice finish | 0 | absent |

`LAST_PROVEN_GOOD` is the selected MSE4's qualified wdata output acceptance sequence 20 at `2,446,467,000 ps`, supported in the same interval by 18 buffer accepts and SA lane acceptance through sequence 13. This is handshake progress only; it does not claim independently checked payload correctness.

The next exact boundary is not unique. The causal result is:

`MSE4 wdata/buffer accepts -> FIRST_UNOBSERVED(last request / last index / outstanding drain / state clear) -> DOWNSTREAM_BAD(slice finish absent)`

At return end, `mse_enable=1`, descriptor valid/ready=`0/1`, buffer rvalid/request-ready/data-ready=`0/1/0`, MemAG valid/bp-pre/bp-post=`0/1/1`, request valid/ready=`00/11`, wdata valid/ready=`00/11`, `last_req=0`, and `slice_finish=0`. The last genuine non-clock transition was `buf2mse_rvalid -> 0` at `2,446,468,125 ps`; all selected non-clock state then remained unchanged for `6,083,893,125 ps` of advancing simulation time until the INT finalization.

This closes permanent "no descriptor accept", "no buffer-data accept", and scalarized two-bit ready/valid false-negative explanations. Still open are descriptor/data/request/wdata pairing or accounting skew, partial MemAG starvation, last/last-index generation, outstanding drain, state-clear hold and slice-finish propagation. The canonical parser found no unique matching candidate and correctly returned `EVIDENCE_INCOMPLETE` because the required exact MSE4 slice-finish summary was absent.

## Hang and natural-termination classification

This return does not confirm a DUT deadlock. It proves a stable nonterminal selected state followed by a manual `INT`.

The supervisor observed 93 host heartbeats over about 46.55 minutes. Its longest unchanged parsed simulation-time interval lasted 1,292.60 seconds at `3,604,479,375 ps`, after which a later heartbeat advanced to `8,519,679,375 ps`. That late 4.9152-ms jump is a direct false-kill counterexample to treating a 20-minute wall-clock plateau or `simv` liveness alone as a confirmed hang. The classification is therefore `MANUAL_INT_WHILE_SIM_TIME_PROGRESS_REMAINED_OBSERVABLE_NOT_CONFIRMED_DEADLOCK`, with an execution-layer default of long-running root cause pending, not an RTL verdict.

Natural terminal=`false`; formal D=`0/320` absent/not evaluated; E3=`false`; E4=`false`; E5=`false`.

## Localization sufficiency and missing actual signals

The wide observer materially narrows the problem to the post-output-accept terminal/accounting cone, but it is not sufficient for one-run unique root localization. It lacks:

- descriptor FIFO and buffer-data FIFO enqueue/dequeue/occupancy/full/empty;
- descriptor/data tag, address, mask and accepted-beat pairing;
- MemAG queue input/output occupancy, selected channel and outstanding request count;
- memory request/wdata acceptance plus response/completion identity;
- actual last/last-index and expected terminal count at producer, queue and consumer boundaries;
- the MSE4 completion FSM, drain predicate, clear predicate and exact hold reason;
- per-MSE finish vector and slice-level finish aggregation/barrier;
- stage `EXEC_START/COMP_FINISH`, formal-D collection progress and a directly flushed in-simulator heartbeat independent of sim-log buffering.

The DUT/root classification remains `DYNAMIC_CAUSAL_INCONCLUSIVE_TERMINAL_ACCOUNTING_CONE`. No functional RTL or config claim is supported or authorized.

## Provisional early-stop recommendation

Current rules correctly forbid automatic early termination from this first signature. If later same-signature real returns and positive/negative controls prove that an early cutoff is safe, the provisional lower bound is 45 wall-clock minutes: two contiguous 22.5-minute windows, longer than twice p46's measured 21.54-minute apparent plateau.

An automatic cutoff must require the following conjunction for the whole window:

1. compile/simulation identity complete, target stage active, process alive, and not in compile/license/tool-start wait;
2. a directly flushed in-simulator heartbeat has no simulation-time advance;
3. all qualified descriptor/buffer/MemAG/request/wdata/completion counters and last accepted index are unchanged;
4. actual queue/outstanding/FSM/last/clear/finish state is bitwise stable;
5. catalog/chunks/candidate matrix are complete through the current sequence and cover every open candidate;
6. a final five-minute grace recheck reproduces the same snapshot before sending INT.

The terminal classification must remain `LONG_RUNNING_HANG_AT_<last_boundary>` rather than an RTL verdict. False-kill risks are legitimate long memory/backpressure or clock-gating latency, buffered logs, observer I/O overhead, omitted moving boundaries, and host/tool/license pauses. The 45-minute value is a proposal, not an activated rule or permission to change the current timeout.

## Observer versus exact one-shot TB VCD

Measured observer facts: the return ZIP is about 83 MB, while the event chunk expands to about 3.249 GB. Of 13,648,779 rows, 13,648,580 are clock records; only 172 are catalogued non-clock signal rows. The observer therefore has high semantic density in its qualified source-bound event summaries and excellent direct JSON/JSONL parsability, but very poor raw transport density because a free-running clock is serialized as one full JSON object per edge. The observed run lasted about 46.55 minutes, but no same-input no-observer or VCD baseline exists, so a percentage overhead claim is prohibited.

The exact one-shot TB VCD method would cover 38 curated aliases and preserve raw timing with standard local decoder support. It embeds less causal meaning and needs a VCD parser plus the identity/catalog receipt, but value-change identifiers should avoid repeated JSON keys and are plausibly smaller for the same signal set. Its production runtime and size have not been measured, so its overhead/volume comparison remains `PENDING_FRESH_BOUND_PROFILE`, not a claimed improvement.

## Rule feedback and claim boundary

`RULE_DELTA_PROPOSAL`:

- keep automatic early stop disabled until same-signature controls qualify the 45-minute conjunction;
- allow a semantically lossless periodic/delta representation for free-running clocks, preserving exact reconstructibility without one JSON object per edge;
- require streaming validation for unbounded observer chunks and prohibit whole-file reads;
- when compile exit is zero, encode `first_true_error=NOT_APPLICABLE_COMPILE_PASSED` instead of copying warnings into a true-error field.
- bind the published exact server root into return core identity and fail closed to an execution-root-drift diagnostic classification when the actual root differs, even if post-compile source content matches.

Claim boundary: this receipt proves formal-return identity/integrity, actual native compile success under `NDP_copy02`, exact selected target-RTL/package-observer content identity, simulation start, selected transitions and qualified progress through MSE4 wdata acceptance, followed by a stable selected nonterminal state and manual INT. Because the published command named `NDP_copy01`, it does not prove execution of that published command, a DUT deadlock, a unique RTL/config/numeric root cause, natural terminal, formal-D correctness, E3/E4/E5, current remote process state, or one-shot VCD performance.

No successor package and no storage lifecycle action were performed by explicit user instruction.
