# FSDB-only repeatable return gate v1

## Outcome

Implemented the local shared next-fresh FSDB gate under the existing waveform and repeat-execution rule IDs. The current profile uses `DUMP_VCD=0 DUMP_FSDB=1 TB_DUMP_FSDB=0`, one package-owned writer, attempt-local `wave.fsdb` plus every shard, and same-formal-ZIP return without a byte cap, sampling, truncation or size-based deletion. Historical VPD v2 receipts remain readable but are no longer a next-fresh production choice.

The existing exact-owned reset helper remains authoritative for repeated execution: only the exact package cfg and attempt leaves are reset, so stale matrix/config/compile/evidence/log/FSDB files are overwritten by recreation while foreign siblings remain unchanged. Formal return ZIPs are not overwritten; each execution receives a unique name and prior returns remain available.

## Staged activation

The serialized Conv owner was notified before the shared edit and prepared one minimal smoke, not a formal operator successor. It correctly held construction until mainline activates the current-disk shared epoch. That smoke must prove real VCS time advance, attempt-local FSDB production, same-ZIP collection, registered query/event evidence, and safe second execution. The four formal packages remain frozen until both the shared sync and the user-run smoke pass.

## Validation

- Focused compatibility/FSDB/post-sim suites: 38/38 PASS.
- `py_compile` for both shared waveform collector and post-sim helper: PASS.
- `git diff --check`: PASS.
- The old portable-query suite has a pre-existing internal mismatch between its direct-VCD-era tests and its already changed dispatch/tool modes; this delta does not claim or use direct VCD.

## Publication boundary

New FSDB schemas/dispatch/fixtures/test and the mandatory collector may be mechanically synchronized. Rules, README, registry and `server_post_sim_return.py` require narrow semantic merge into canonical mainline because mainline contains newer parallel partial-exit/profile increments. No current/pending/tested package, plan, RTL, config, numeric asset, workload or server state was changed.

Machine report: `outputs/whole_network_fsdb_only_repeatable_return_v1/report.json`.

