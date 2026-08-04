# QLinearAdd node0007 v10 return / observer clock-domain adjudication

## Scope and immutable inputs

- Mainline target: `019fa2ca-72bc-7753-8d58-81e59bc76c88`
- Return ZIP SHA256:
  `a4bd588c8b3b2e57b144142990478a0d6a3ff48cfc37ce33c2af76f02d5eef6f`
- Adjacent return sidecar SHA256:
  `c217d164cf4d80e5dba39a4ef88e70c93f9be9f7ca001c869509759d4148bcf0`
- Bound v10 source ZIP SHA256:
  `573121def027a04b33650122e82d6c32cb8fbc4c9162cfc6cc831237a01869cf`
- Generation index SHA256:
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- Server-package rule SHA256:
  `0d94f0d10ac6a09b170f0980e3ae6a8408dda28b1aec29ff4e966e9279f44b9a`
- QLinearAdd rule SHA256:
  `c38935c63469a165ffe6b79c9e3d08de47bbbd9b9e0613cbc16253c138e4b76b`
- Numeric/workload analysis repeated: `false`
- Frozen reuse assets consumed: `true`
- Server inspected/uploaded/run by this task: `false`
- Functional RTL modified: `false`

## RETURN_ANALYSIS

The adjacent sidecar exactly names and hashes the return ZIP. ZIP CRC, unique
root, duplicate absence, return-manifest exact-set, per-file size/hash and
allowlist-only collection all pass. The returned package manifest is byte-equal
to the manifest in the bound v10 source package. Package and installed
preflights both pass, and all runtime formal-D targets are absent before the
run as required.

The known v10 runtime identity-duplication defect did not trigger on this run:
the duplicated literal happened to equal the v10 manifest identity. The runner
reached the real compiler, the package-local observer include directory and
enable macro were present in the actual compile argv, and compile returned 0.
This does not rehabilitate v10; it only makes the dynamic evidence independently
usable for diagnosis.

The simulator ran for 4197.344762825 seconds and was interrupted by `INT`
with exit 125. There was no natural terminal. The base observer returned 65
samples, including 64 heartbeats through active cycle 16777216. Request,
read-data and write-data accepted counters all remained zero through 16 complete
declared stall windows. This is a hang, not an ordinary under-one-hour
completion miss.

All 28 formal D files are missing. `mismatch_byte_count=0` is non-evaluable and
is not a numeric pass. E3, E4 and E5 are all false.

## FIRST_DIVERGENCE

- Last good: compile/elaboration, `op_a_dequant` execution start, and continuing
  base `clk_db` observer heartbeats.
- First proved bad: no qualified request/read/write or buffer transaction over
  16 complete stall windows.
- First internal boundary not observed by v10:
  `actual slice_start_run -> physical LC2/4/6/13/18 -> selected MSE0/MSE4 ->
  first request`.

## HANG_ROOT_CAUSE

The functional cause remains
`UNRESOLVED_INSIDE_EXEC_START_TO_FIRST_REQUEST`. Shared-LC topology, address
shape or timeout is not asserted as the cause.

The diagnostic failure has a deterministic package-local cause. The base
observer owns `return_obs_active_cycles` and heartbeat emission on `clk_db`.
The v10 tail owns both qualified internal counting and `FIRST_REQUEST_CHAIN`
printing on `clk_sg`, while its print trigger compares the cross-domain
`return_obs_active_cycles % heartbeat_period` to zero. A stopped/gated
`clk_sg`, or simply missing the exact cross-domain modulo value, suppresses
the whole first-request stream. The returned canonical record correctly
fails closed at `FIRST_REQUEST_CHAIN_RETURN_BINDING`; it cannot localize the
functional boundary.

## BLOCKER_DELTA

- Close: missing return sidecar, return identity, CRC/allowlist, preflight and
  observer four-way compile/runtime/return binding.
- Keep open: `QADD_NODE0007_EXEC_START_TO_FIRST_REQUEST_FUNCTIONAL_ROOT_CAUSE`.
- Open/close by v12 construction:
  `QADD_NODE0007_FIRST_REQUEST_OBSERVER_GATED_CLOCK_EMISSION`.
- Quarantine v10 remains in force.
- The minimal-runtime v11 successor is also not run-ready because it preserves
  the same observer tail.

## RULE_DELTA_PROPOSAL

Propose a family-neutral server-observer rule:

`CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001` — when a diagnostic
targets the absence of progress in a gated clock domain, qualified event
counters must remain owned by the target/source clock, but rate-limited
emission must be owned by an independently live observer clock. The return must
also include a qualified target-clock edge count. A modulo/equality trigger
formed from a counter written in another clock domain is insufficient.

No public rule file was modified.

## PACKAGE_RELEASE

- Fresh diagnostic successor:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_obsclk_v12.zip`
- ZIP SHA256:
  `87c4089d56dbd082d825b2575285e9ec48276402c25bbe9e648f4165e4a461f3`
- Sidecar SHA256:
  `a042cf7a37dc579e07b95648bfdcd06af759ab2adfde7535ae2daeec490db601`
- Class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Status: `PACKAGE_READY_NOT_RUN`
- One command:
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`
- Expected return:
  `r5_qadd_n7_obsclk_v12_return.zip`
- Expected return sidecar:
  `r5_qadd_n7_obsclk_v12_return.zip.sha256`

v12 keeps qualified LC/MSE counters on `clk_sg`, emits the rate-limited
`FIRST_REQUEST_CHAIN` snapshot on `negedge clk_db`, and returns a separate
`FIRST_REQUEST_CLOCK` record containing the `clk_sg` edge count and level.
Frozen workload/configuration and canonical qualified-progress semantics are
unchanged.

The post-generation final-ZIP current-rule audit passes with
`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`, `errors=0`, deterministic double build,
fresh-extract runner-to-safe-compile positive control, wrong-payload
precompile negative control, all inherited observer/canonical negative
controls and four new observer-clock negative controls fail-closed.
