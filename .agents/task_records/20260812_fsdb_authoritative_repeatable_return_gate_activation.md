# FSDB authoritative repeatable-return gate activation

Status: `CURRENT_DISK_FSDB_AUTHORITATIVE_SMOKE_GATE_ACTIVATED`

- activation epoch: `fsdb-authoritative-repeatable-return-v3-0a1dee9757c6`
- rules retained without synonymous duplicates:
  - `CDA-SERVER-WAVEFORM-DEFAULT-RETURN-UNBOUNDED-CAUSAL-COVERAGE-001`
  - `CDA-SERVER-WAVEFORM-PORTABLE-LOCAL-DECODABILITY-001`
- activation scope: shared current-disk rule/tool/schema/validator/runtime-return gate only

## Previous-version progress

The previous mandatory-waveform route successfully forced authoritative waveform transport into formal returns, but its `DUMP_VCD=1` output was binary VPD and the later direct-portable-VCD UCLI command was unsupported by production VCS. GAP v58, serialized Conv v88b and native Conv p43 therefore stopped at time 0; QAdd v59 stopped earlier at its independent manifest/SCA namespace preflight mismatch. Those returns were consumed and archived as tested evidence; no formal family package remains pending.

## Current-version purpose and disposition

The v3 shared gate replaces next-fresh VPD/direct-VCD output with one package-owned FSDB writer using `DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0`. It requires attempt-local `wave.fsdb` plus every shard, unbounded streaming collection in the same formal return ZIP, identity-bound WaveUtils or registered event evidence, and fail-closed preservation of raw/core evidence when query analysis is incomplete.

Sequential reruns of the same package reset only the exact package-owned cfg and attempt leaves, including stale FSDB, while preserving foreign siblings and all prior execution-named formal return ZIPs. A repeated target collision fails closed rather than overwriting.

The shared gate is locally active, but the four formal family successors remain frozen. Only `family.conv.serialized` may now build exactly one minimal FSDB-only smoke package. The user must run that smoke and return evidence proving production compile/elaboration, time-0/progress marker, simulation time greater than zero, fresh attempt-local FSDB and all shards, same-ZIP collection, registered query/event evidence, and safe second sequential execution with a distinct non-overwriting return name. Until that formal smoke return passes, GAP, native Conv, QAdd and the formal serialized Conv successor remain held.

## Current-disk validation

- mechanical FSDB v3 collector, plan schema, runtime-receipt schema, dispatch, fixtures, focused tests and optimizer report synchronized;
- mainline partial-exit implementation and tests preserved by narrow semantic merge;
- focused waveform/post-sim regression: 40 tests passed;
- Python compile and scoped diff check passed;
- active-rule audit passed with 14 active/registered rules, 160 unique definitions and zero duplicate definitions;
- no current/pending/tested family package, config, numeric asset, workload, golden or functional RTL changed.

## Dispatch boundary

Authorized next action: serialized Conv owner builds one minimal `PACKAGE_READY_NOT_RUN` smoke and returns its exact package/final-audit/first-fresh receipts. No server upload, run, lease or connection is authorized. Mainline does not poll after dispatch and waits for the family package receipt or user-provided formal smoke return.
