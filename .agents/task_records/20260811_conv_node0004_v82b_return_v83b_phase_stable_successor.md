# Conv node0004 v82b RETURN → v83b stable-phase successor

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- scope: serialized Conv correctness diagnostic only
- numeric/workload/config/golden repeated: `false`
- functional RTL/ISA/hardware/active ndp-sim modified: `false`
- server/upload/run/lease: `false`

## Formal v82b result

The formal return ZIP is 342626 bytes with SHA256
`f328f1cc6f634310466aca206148297825db3231beaf7102ff5b92516eff3638`.
CRC, one-root path safety, exact member set, per-file receipts, source package and
execution identity all close. Compile and run exited zero with `signal=NONE`,
but the return is `EVIDENCE_INCOMPLETE`: natural terminal is false and all 320
formal D items are missing (mismatch remains zero and is not treated as PASS).

`LAST_PROVEN_GOOD=EXACT_TARGET_PARSE_BEFORE_PROJECTION_WITH_13_COMPLETE_BINARY_KNOWN_PHASE_GROUPS`.
The exact slice13/group1/MSE4 target produced 65 events / 13 complete groups,
all binary-known 38-bit payloads with exact-instance and semantic-fingerprint
binding. This closes the v81 post-sim erasure blocker.

`FIRST_DIVERGENCE=V82B_POSTNBA_SAMPLE_COLLIDES_WITH_NEGEDGE_AND_MIXES_SUCCESSIVE_TOKEN_EPOCHS`.
All 13 POSTNBA samples have the same timestamp as HALF; seven NEXT samples also
alias that timestamp. The old observer's `#1` delay equals the measured
half-cycle boundary. Consequently every group is classified as operand/epoch
transition and cannot adjudicate the stable public ACK equation. This is a
package-local diagnostic sampling defect, not evidence of a configuration or
RTL defect. Functional completion progress this round is zero.

The source-bound plugin also encountered a real signature omitted by its four
candidate rows: `buf_ack=true`, `buf_terminal=true`,
`mem_source_match=false`, `mem_terminal=true`. The plugin correctly failed
closed rather than guessing.

## One-final-ZIP correction

The first exact v83 ZIP was materialized with SHA256
`4038daa2c4068b48c603b29c0f3beb1c187a323c918dc94f89d38b2203031dd9`.
Its post-sim microfixture still used the v82b phase vocabulary and failed
closed. That ZIP and its failure report are retained under
`outputs/conv_node0004_v82b_return_v83_successor/`; it is not a release
candidate. A later same-id staging ZIP is likewise not released. Per the
one-final-ZIP rule, the corrected release identity is fresh v83b.

## v83b successor

`r5_n4_hw_v83b_phase_stable_diag` is
`DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It samples PRE at negedge+250ps, then
EDGE, +1ps, +250ps, +750ps, all strictly away from the following clock edge.
It retains the exact 38-bit target ABI and completes the eight-row
source-match/terminal truth table. Numeric inputs, W3, qparams, tail,
workload, materialized configuration, golden, timeout, backpressure and RTL
remain frozen.

The new three-gate epoch is not new for this family; v83b binds the v82b prior
independent first-fresh PASS receipt
`0c71f0972193e7a2e6a1b9f0609d45198129c5c1da629cf9ba977445d310f71a`
and declares `first_fresh_after_change=false`.

Local gates cover exact source-bound typed-v2/fingerprint, focused HDL and
actual-consumer scope negatives, stable-phase predicate traces, post-sim core
and required plugin, real runner→safe compile/sim/finalizer, 86/86 SCA input
opens, install-only runtime layout, fixed return, result contract and final ZIP
release matrix. These gates make no natural-terminal, formal-D, E3, E4 or E5
claim.

## Rule feedback

`RULE_CONFIRMATION`: current parse-before-projection, exact-instance,
known-width/fingerprint, post-sim independent-core, one-final-ZIP, runtime
layout, final-ZIP audit and storage rules all caught or bounded the observed
package-local failures. No non-synonymous public rule delta is required.
