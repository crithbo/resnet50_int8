# serialized Conv node0004 v50 return → v51 LC13/LC14 successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Status: `PACKAGE_READY_NOT_RUN`
- Package class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Candidate release: `false`
- Hardware/ISA/functional RTL change: none

## v50 formal return

The exact return ZIP is 113782 bytes with SHA256
`5401413f1586e8b7de4ad6ed2be2f8b2a0b4eea5072a80349b5b3217601e9d8a`.
The user confirmed that this diagnostic run completed. CRC/root/path,
RETURN_MANIFEST exact-set, allowlist, per-file receipts, source identity,
package/install preflight and runtime-D-absent checks pass.

Production compile and run both exit 0, signal is `NONE`, and the observer
finishes its bounded diagnostic budget. The DUT does not reach natural
terminal. Formal D is expected/present/missing/mismatch = 320/0/320/0, so
the joint result gate is false and E3/E4/E5 remain false.

## Qualified boundary

`LAST_PROVEN_GOOD`:
`LC9_ACCEPTS_TRUE_LAST_INDEX0_AND_D_WRITES_32_DESCRIPTORS_WHILE_LC13_RELEASES_FIRST_NONTERMINAL_VALUE`.

`FIRST_DIVERGENCE`:
`LC13_SECOND_OR_TERMINAL_VALUE_NOT_GLOBALLY_ACCEPTED_AND_LC14_LC15_NEVER_RELEASE`.

v50 corrects the v49 observer decode: the prior `lc9_last0=0` came from low
data bits, whereas v50 reads the real tag bits `[21]` and `[19:16]` and
proves one accepted LC9 last-index-zero event. LC13 advances once with a
nonterminal value; LC14 and LC15 never release. Descriptor push/pop is
32/32. Therefore LC9 terminal generation, LC15→LC9 loss, Buffer_AG terminal
selection, and descriptor terminal are no longer the first divergence.

The root remains unresolved within one localized link. Remaining candidates
are LC13 downstream backpressure, LC14 source/same-gotten suppression, LC14
counter input-without-output, or LC13 local terminal release. No config or
functional RTL defect is yet proven, so changing either would be speculative.

## v51 successor

v51 adds one bounded feature, `RETURN_OBS_LC13_LC14` (limit 128), covering
LC13 accepted/held output, LC14 selected input/same-gotten/input-ready,
LC14 counter write/count/pointers/output, and LC15 capture/output. Only
qualified handshakes and edges count as progress; stable level/count/empty
are state corroboration.

Numeric/W3/qparams/tail/workload/config/golden, timeout, backpressure and
functional RTL are frozen.

Final ZIP:
`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v51_lc13_lc14_diag.zip`
(5874303 bytes,
SHA256 `23d421c38b310bc458c6305fea33d9372a217a3bc2fced6e796e6368510964f0`).

Server command:
`bash r5_n4_hw_v51_lc13_lc14_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`

Expected return:
`/home/panqs/ndp/simresult/r5_n4_hw_v51_lc13_lc14_diag_return.zip`
and adjacent `.sha256`.

The production runner owns the fixed, nonconfigurable server path
`/home/panqs/ndp/simresult`. Local validation parsed the exact runner and
used an isolated harness only; it did not create, map, or write that server
path in the workspace.

## Validation and storage

Deterministic double build is byte-equal. Focused HDL syntax positive exits
0; missing declaration, task typo, and actual-consumer typo negatives exit
6, 1, and 1. Exact consumer deletion/rename/wrong-sibling negatives fail
closed. Predicate trace proves held level is not a transaction. Runner safe
compile reaches exit 74 and TERM finalizer reaches exit 143. Normal,
compile-fail, INT, and TERM publication paths share the same atomic finalizer;
path rewrite, conflict, sidecar, and duplicate negatives fail closed.

Post-rotation final-ZIP audit exits 0 with
`FINAL_ZIP_RULE_SELF_AUDIT_PASS=true` and `errors=0`.
The storage audit exits 0 and shows exactly one serialized pending ZIP: v51.
v50 and its receipts moved to
`tested/conv_serialized_node0004/r5_n4_hw_v50_dterm_owner_diag`.
The stale v49→v50 storage index was regenerated from the non-overwritten
physical tree before the atomic v50→v51 rotation.

## Blocker and rule result

Closed:

- `B_CONV_NODE0004_D_TERMINAL_OWNER_CHAIN_UNOBSERVED`
- `B_CONV_NODE0004_LC9_TRUE_LAST0_UNOBSERVED`

Opened:

- `B_CONV_NODE0004_LC13_TO_LC14_TERMINAL_RELEASE_UNOBSERVED`

Natural terminal and formal-D blockers remain. The old PE outbuffer occupancy
claim remains `INVALIDATED_NOT_RTL_BUG`.

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT_NO_DELTA`. The current qualified
observability, continuous closure, release-gate applicability, actual-consumer
scope, fixed simresult publication, and storage rotation rules produced
executable fail-closed evidence. No non-synonymous public rule delta is needed.
