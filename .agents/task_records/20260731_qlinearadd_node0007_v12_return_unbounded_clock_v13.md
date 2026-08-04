# QLinearAdd node0007 v12 return and rate-limited v13 successor

## Scope and receipts

- Mainline: `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- Return ZIP:
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\r5_qadd_n7_obsclk_v12_return.zip`
- Return ZIP SHA256:
  `aef5c0847f10b28fae87598994a7abb27e339bfe474014ce168211fc9c540b14`
- Adjacent sidecar: absent
- Bound source v12 ZIP SHA256:
  `87c4089d56dbd082d825b2575285e9ec48276402c25bbe9e648f4165e4a461f3`
- Generation index SHA256:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- Server rule SHA256:
  `507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d`
- QLinearAdd rule SHA256:
  `c38935c63469a165ffe6b79c9e3d08de47bbbd9b9e0613cbc16253c138e4b76b`
- Numeric/workload analysis repeated: `false`
- Frozen reuse assets consumed: `true`
- Functional RTL modified: `false`
- Server inspected/uploaded/run by this task: `false`

## RETURN_ANALYSIS

The return ZIP has a valid CRC, a unique safe root and no duplicate members.
Its returned package manifest is byte-equal to the frozen v12 source manifest.
Package/install preflight both report valid, both prove formal runtime D targets
absent, and neither inspects server sources. Compile exits 0.

The adjacent sidecar and `RETURN_MANIFEST.json` are absent. Required non-readback
allowlist entries are also absent:

- `runs/return_observer.log`
- `evidence/actual_compile_argv.txt`
- `evidence/CANONICAL_PROGRESS_DECISION.json`
- `evidence/canonical_decision_exit_status.txt`

Therefore the formal receipt and return exact-set are fail-closed. The ZIP is
`RETURN_SNAPSHOT_NONAUTHORITATIVE`; its contained evidence may be used only for
diagnosis.

Simulation ran 4429.607884391 seconds and was interrupted by `INT`, exit 125.
There is no natural terminal. Formal D is observed 0/28, missing 28, and the
conjunctive result gate is false. `mismatch_byte_count=0` is non-evaluable.
E3, E4 and E5 are false.

## FIRST_DIVERGENCE

The progress sampler contains 37 monotonic `FIRST_REQUEST_CLOCK` records. The
first has active cycles 431670 / `clk_sg_edges=215835`; the last has active
cycles 15325732 / `clk_sg_edges=7662866`. This proves:

- `EXEC_START` occurred;
- the independent `clk_db` snapshot block ran;
- target `clk_sg` was alive and continued advancing.

No `FIRST_REQUEST_CHAIN` record, full observer or canonical decision is present
in the returned ZIP. The most precise functional interval remains:

```text
LAST_GOOD = EXEC_START + clk_sg edge progression
FIRST_UNOBSERVED = slice_start_run -> LC4 -> LC2/6 -> LC13/18
                   -> selected MSE0/MSE4 -> first request
DOWNSTREAM_BAD = no natural terminal + formal D 0/28
```

Level values are not counted as transactions.

## HANG_ROOT_CAUSE

Execution state is `LONG_RUNNING_HANG_PENDING_ROOT_CAUSE`. The functional root
cause remains:

`UNRESOLVED_AFTER_EXEC_START_WITH_CLK_SG_ALIVE_TO_FIRST_REQUEST`.

The v10 gated-clock-silence candidate is closed. Shared-LC, address, MSE queue or
RTL is not selected without qualified chain evidence.

The v12 package has a deterministic observer defect:

`DETERMINISTIC_UNBOUNDED_FIRST_REQUEST_CLOCK_EMITTER`.

Static final-ZIP source shows `FIRST_REQUEST_CHAIN` under the heartbeat modulo
gate, but `FIRST_REQUEST_CLOCK` after that gate, still inside every
`negedge clk_db`. Dynamically, all 37 sampled clock records have arbitrary
active-cycle values rather than heartbeat multiples. At active cycle 15325732,
even an 80-byte lower bound implies at least 1,226,058,560 bytes of clock log,
146 times the declared 8 MiB single-text budget. This explains why required
observer/canonical evidence could not be authoritatively returned. It is a
package diagnostic failure, not a configuration or RTL finding.

## BLOCKER_DELTA

- Close: v10 hypothesis that the target `clk_sg` never starts.
- Open: `QADD_NODE0007_EXEC_START_TO_FIRST_REQUEST_FUNCTIONAL_ROOT_CAUSE`,
  narrowed by excluding target-clock silence.
- Open/close with v13:
  `QADD_NODE0007_UNBOUNDED_FIRST_REQUEST_CLOCK_LOG`.
- v12 is quarantined and cannot be run again.

## RULE_DELTA_PROPOSAL

Propose:

`CDA-SERVER-RELATED-DIAGNOSTIC-RECORDS-SHARED-RATE-GATE-001` — every record
belonging to one heartbeat snapshot, including target-clock edge/last-change
witnesses, must be emitted inside the same proven rate gate. Final-ZIP negative
controls must move each sibling record outside that gate and fail closed.
Progress samples at arbitrary active-cycle values are a dynamic counterexample
to claimed heartbeat rate limiting.

No public rule file was modified.

## PACKAGE_RELEASE

- Fresh successor:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_obsrate_v13.zip`
- ZIP SHA256:
  `fe65a96ad6365872f2f004f6702b197f33fc6b5fcd4397df716714f443b28858`
- Sidecar SHA256:
  `6ec76ea1bb8f0c2fee4164bfa0df34ffbe48e7b0fabc51273c5c85d4a684eb5b`
- Class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Status: `PACKAGE_READY_NOT_RUN`
- Command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- Expected return:
  `r5_qadd_n7_obsrate_v13_return.zip`
- Expected sidecar:
  `r5_qadd_n7_obsrate_v13_return.zip.sha256`

v13 changes only the package-local observer: `FIRST_REQUEST_CLOCK` is moved
inside the same `clk_db` heartbeat gate as `FIRST_REQUEST_CHAIN`. Qualified
`clk_sg` counters, the ten-level chain, runner, frozen workload/configuration,
canonical parser and formal D contract are otherwise unchanged.

Post-generation current-rule final-ZIP audit passes with
`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`, deterministic double build,
fresh-extract real-runner safe compile-stub exit 86, wrong identity precompile
exit 5, and all inherited plus four observer-rate negative controls fail closed.
