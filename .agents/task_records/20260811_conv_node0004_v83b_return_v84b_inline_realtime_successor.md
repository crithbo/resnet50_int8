# Conv node0004 v83b RETURN → v84b inline-realtime successor

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- scope: serialized Conv correctness diagnostic only
- numeric/workload/config/golden repeated: `false`
- functional RTL/ISA/hardware/active ndp-sim modified: `false`
- server/upload/run/lease: `false`

## Formal v83b result

The per-execution return ZIP is 348917 bytes with SHA256
`f9caa057a0f9000fcfc4e78a5a8b96741ff601f861a2be1df94c313d3f2823b9`.
CRC, one-root/path safety, exact-set, core per-file receipts, execution identity,
and the byte-equal source `package_manifest.json` binding pass. Compile and run
both exited zero and signal is `NONE`. The core disposition is
`EVIDENCE_INCOMPLETE`: natural terminal is false and formal D is
present/missing/mismatch = 0/320/0, so E3/E4/E5 are false.

`LAST_PROVEN_GOOD=COMPLETE_SOURCE_BOUND_TRUTH_TABLE_UNIQUE_MATCH_AND_13_EXACT_KNOWN_PHASE_GROUPS_PERSISTED`.
The eight-row source-bound truth table now uniquely matches
`mem_match_absent_memterm_1_bufterm_1`. The exact slice13/group1/MSE4 phase
stream contains 65 events, 13 complete groups, zero foreign events, and zero
unknown/width-invalid 38-bit payloads.

`FIRST_DIVERGENCE=V83B_STABLE_PHASE_PARSER_REJECTS_SUB_NS_SCHEDULE_DUE_TO_INTEGER_TIME_QUANTIZATION`.
Every group has integer `$time` collisions among the intended sub-nanosecond
phases, so the parser correctly rejects the schedule. The named fields show
the ACK equation mismatching in 65/65 samples, including 13/13 late samples,
but this is not classified as an RTL/config defect until an exact same-instance
inline RHS/XOR witness with strictly ordered `$realtime` is returned.

Progress relative to v82b is real but non-functional: the incomplete candidate
table and edge-collision observer defects are closed. Natural terminal and D
did not advance.

## One-final-ZIP correction

The first exact v84 ZIP was materialized as 5264421 bytes, SHA256
`7e7ba538ffd66f3dfbd5d36d78868d3550708eaecd3025707a4ac3f3797424f1`.
Its post-sim fixture failed because the new plugin unconditionally invoked the
frozen full collector even when the live-only fixture intentionally had no
compile receipt. The ZIP and failure report are retained and are not released.
Per one-final-ZIP, the corrected identity is fresh v84b; v84 bytes were not
overwritten.

## v84b successor

`r5_n4_hw_v84b_ack_inline_realtime_diag` is
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves the v83b workload and adds
only exact target observation fields: explicit phase ordinal, `$realtime`,
`expected_bp={2{!full}} & bpmask`, and `xor=bp ^ expected_bp`. Payload width is
42 bits and remains exact-instance/binary-known/fingerprint bound. The plugin
persists this decision before the frozen bounded source-bound collector.

Deterministic double build passes. Focused phase HDL/parser tests include
stable/persistent/settling positives and wrong-instance, unknown payload,
wrong ordinal, wrong inline expected, realtime collision, missing phase,
deleted consumer, and misspelled consumer negatives. Exact source-bound
regeneration, post-sim four-scenario publication, runner safe compile/sim and
EXIT/HUP/INT/TERM finalization, 86/86 SCA input opens, install-only layout,
return conjunction, and final-ZIP release matrix all pass with errors=0.
The same rule epoch reuses prior first-fresh PASS receipt
`0c71f0972193e7a2e6a1b9f0609d45198129c5c1da629cf9ba977445d310f71a`
and declares `first_fresh_after_change=false`.

## Rule confirmation

`RULE_CONFIRMATION`: current exact-instance, known-width/fingerprint,
parse-before-projection, partial-exit live-only, post-sim independent-core,
one-final-ZIP, runner/layout, final-ZIP audit, and storage rules all caught or
bounded the v83b/v84 package-local escapes. No non-synonymous public rule delta
is required.
