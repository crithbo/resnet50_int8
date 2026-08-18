# Observer operational attempt boundary v1 activation

## Outcome

The v98 disk-full incident is adjudicated as `RULE_SEMANTIC_OMISSION`, with
package-local amplification escapes as a secondary cause. The current observer rules correctly
forbid silent event/byte truncation, but previously did not distinguish that prohibition from a
one-shot termination of the entire attempt at an operational disk/growth boundary.

No new public rule ID was introduced. The existing observer, triggered observability,
writer-quiescence, post-sim return and repeat-execution rules now bind the missing operational
semantics. The observer-only build gate advances to semantic version 3.

## Activated semantics

- The 100,000,000-byte observer preference remains warning-only and is not a stop threshold.
- Every next-fresh observer package binds a package-specific peak-space projection across compile
  output, observer chunks, simulator-log duplication, parser/rewrite scratch, return staging and
  publication sidecars, plus an explicit minimum-free-space reserve.
- Compile, simulation and finalization growth/free-space watches may request exactly one whole-
  attempt operational stop. They may not silently cap, sample, truncate, overwrite or delete
  causal rows.
- The stop path flushes and preserves every completed/flushable row, marks the return
  `DIAGNOSTIC_EVIDENCE_INCOMPLETE`, performs TERM/wait/KILL/reap, and cannot establish natural
  terminal, Formal-D, E4 or E5.
- Exact-owned attempt cleanup is allowed only after durable return ZIP CRC/exact-set/bytes/SHA and
  sidecar verification. Foreign siblings and failed publications remain untouched.
- v99's 20GB reserve, 3600-second wall and 10.8GB projection remain package-local prototype values,
  not shared constants.

## Verification

- Focused and related regression: 125/125 PASS.
- Active-rule audit: 14/14 active and registered, 164 definitions, 0 duplicates, 0 errors, 0 warnings.
- JSON parse and Python compile checks: PASS.
- Machine receipt:
  `outputs/observer_operational_attempt_boundary_activation_v1/activation_receipt.json`.

## Boundary

Activation is required-next-fresh only. Exact pending v99 remains byte-frozen and was neither held
nor rebuilt. This activation performs no upload, lease, connection, server run, functional RTL,
config, numeric or workload mutation.
