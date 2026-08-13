# 2026-08-12 — FSDB-authoritative waveform smoke-first mainline freeze

## Ownership and user adjudication

- Mainline role: `mainline.control`; owner epoch `2`; registry epoch `6`.
- Shared-method owner: `optimizer.whole-network`.
- Smoke owner: `family.conv.serialized`.
- User decision: authoritative formal-return waveform changes from the failed raw-VPD/direct-VCD profile to
  FSDB. Unneeded VPD generation is disabled. The four formal family successors remain frozen until a serialized
  FSDB-only smoke proves the production behavior.
- No server action is authorized by this record.

## Previous progress and current purpose

Previous progress: GAP v58, serialized Conv v88b and native Conv p43 passed production compilation but the shared
UCLI `dump ... -type VCD` command stopped each run at 0 ps; QAdd v59 failed earlier on a package-local
manifest/install/SCA identity mismatch. All consumed packages are tested, the pending exact set is empty and no
family DUT target was dynamically retested. Serialized v88b also proved that the older ACK RTL allegation was an
observer/source-identity semantic false positive rather than a functional RTL defect.

Current purpose: production-prove one minimal FSDB-only runtime and return path before rebuilding any of the four
formal operator packages.

## Frozen formal-package boundary

- GAP, native Conv and QAdd remain `HOLD_FSDB_SMOKE_GATE`; they build no package.
- Serialized Conv may build exactly one fresh minimal smoke package and return `PACKAGE_READY_NOT_RUN`; it must
  not rebuild the formal serialized diagnostic yet.
- No family may upload, lease, connect to or run a server under this local-build authorization.
- Config, numeric, workload, golden, functional RTL and all four target diagnostics remain frozen.

## Required shared FSDB contract

The optimizer current-disk publication and later mainline rule sync must establish:

1. FSDB is the authoritative waveform returned in the formal return ZIP.
2. Actual compile/simulation settings are `DUMP_VCD=0`, `DUMP_FSDB=1`, `TB_DUMP_FSDB=0`; obsolete VPD/direct
   VCD generation is disabled and cannot satisfy the gate.
3. Every package-owned `wave.fsdb` and shard is collected without ZIP, extraction, per-file, aggregate-byte or
   event cap, and without truncation, sampling or size-based deletion.
4. WaveUtils or an explicitly registered event/query receipt supplies locally actionable, identity-bound signal
   evidence. A missing/failed decoder preserves FSDB and core return but marks diagnosis incomplete.
5. A repeated invocation of the same package bash safely resets or overwrites only the package-owned cfg, run,
   evidence and compile workspace. It cannot consume stale attempt evidence.
6. Under one fixed simresult directory, earlier returns remain intact; every invocation publishes a new return
   name bound to its fresh execution identity and uses atomic no-overwrite publication.
7. Production proof must distinguish compile success, simulator process exit and actual time advance. A run with
   no time-0/progress marker or no time greater than zero cannot claim DUT execution or complete waveform evidence.

## Serialized minimal smoke acceptance

The smoke must contain only the minimum frozen workload/runtime needed to prove the shared behavior. Its local
release gates must cover FSDB-only argv/Tcl, package-owned FSDB and shards, WaveUtils/registered event receipt,
time-progress markers, repeat-run reset, stale-evidence negatives, fixed-simresult distinct-return naming,
interrupt/compile-fail core return, exact final ZIP and first-fresh audit.

Local `PACKAGE_READY_NOT_RUN` is not production proof. After a later explicit user server run, its formal return
must prove production VCS time advance, fresh FSDB generation and collection, repeat execution isolation and
non-overwriting execution-bound return publication. Only then may mainline dispatch the four formal fresh builds.

## Claim boundary

This record changes only mainline control-plane status and dispatch. Public rule/schema/tool/test content remains
pending the optimizer `CURRENT_DISK_FSDB_AUTHORITATIVE_SMOKE_GATE_READY` publication. No package was built by
mainline; no RTL/config/numeric/workload/server action occurred. Conflicts: `[]`.
