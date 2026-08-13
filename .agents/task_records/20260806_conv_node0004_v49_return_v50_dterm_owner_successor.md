# serialized Conv node0004 v49 return → v50 D-terminal owner successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Status: `PACKAGE_READY_NOT_RUN`
- Package class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Hardware/ISA/functional RTL change: none

## v49 formal return

The exact return ZIP is 113092 bytes, SHA256
`722a1cee4b7e54564d060e202792d8179e6223570b8bfbb5fd51eac3f268637b`.
The adjacent transport sidecar is absent and is nonblocking only under the
user-attested no-sidecar rule. ZIP CRC/root/path, exact-set, allowlist,
per-file receipts, package/install identity and source ZIP binding all pass.

Production compile and runner both exit 0 and the diagnostic simulation runs.
The stop is observer-directed, not a DUT natural terminal. Formal D has
expected/present/missing/mismatch = 320/0/320/0, so the joint result gate is
false and E3/E4/E5 are all false.

## Qualified boundary

`LAST_PROVEN_GOOD`:
`LC9_GLOBAL_ACCEPT_TO_LC7_CAPTURE_AND_MSE3_QUEUE_PROGRESS_PLUS_32_DESCRIPTOR_DATAHUB_WRITES`.

`FIRST_DIVERGENCE`:
`D_BUFFER_SOURCE_SCHEDULE_CONTINUES_AFTER_MEMORY_DESCRIPTOR_TERMINAL_WITHOUT_LAST_INDEX0_PROPAGATION`.

v49 closes the prior LC9 actual-destination ambiguity: LC9 advances twice,
LC7 captures twice and emits 16 accepted outputs, while MSE3 independently
pushes/pops 79/71 entries. The D write path issues and consumes exactly 32
descriptors and 32 DataHub writes. In contrast, GROUP4/Buffer_AG continues
with 53 source pushes and 37 pops; after descriptor terminal it produces four
more source pushes, three tag pushes, two prepares and one descriptor-free
prefetch. No qualified last-index-zero or slice finish is observed.

The unique root is not yet proven. The remaining causal alternatives are
LC13→14→15 parent terminal absence, LC15→LC9 terminal loss, GROUP4 expansion
outliving the descriptor schedule, or Buffer_AG selecting the wrong terminal
owner. Changing config now would be speculative.

## v50 successor

v50 freezes numeric/W3/qparams/tail/workload/config/golden, timeout,
backpressure and functional RTL. One bounded, triggered observer covers in a
single run:

- qualified LC13/14/15/9 advances and accepted last-index-zero;
- GROUP4 row/column accepted outputs and terminal;
- Buffer_AG accepted push/pop and selected terminal tag;
- descriptor push/pop/true terminal and first post-terminal source push.

Held levels, count and empty/full are corroboration only. The event predicates
are bound to `clk_db/rst_n_db`; the predicate trace covers reset/inactive,
held-valid, valid-without-ready, accepted terminal, wrong terminal index,
simultaneous push/pop, true descriptor terminal and post-terminal source.

Final ZIP:
`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v50_dterm_owner_diag.zip`
(5870731 bytes,
SHA256 `c8a809f8ebb723c286b5c0190bcd1142f9ba2d8965731b8ee194182c0922c830`).

Run command:
`bash r5_n4_hw_v50_dterm_owner_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`

Expected return: `r5_n4_hw_v50_dterm_owner_diag_return.zip`.

## Validation and storage

Deterministic double build is byte-equal. Focused HDL syntax positive exits 0;
missing declaration, task typo and actual-consumer typo negatives exit 6, 1
and 1. Exact consumer leaf deletion/rename and wrong-sibling negatives fail
closed. Runner safe compile stub exits 74 and TERM finalizer exits 143.
Final current-rule audit is PASS with errors=0.

v49 source ZIP and receipts moved to
`tested/conv_serialized_node0004/r5_n4_hw_v49_lc9_actual_compilefix`.
Failed v50 intermediate builds moved to
`superseded/conv_serialized_node0004/v50_build_retries`.
The serialized family has one pending ZIP: v50.

## Blocker and rule result

Closed:
`B_CONV_NODE0004_LC9_TO_LC7_AND_MSE3_ACTUAL_BRANCH_ACCEPT_UNOBSERVED`.

Opened:
`B_CONV_NODE0004_D_TERMINAL_OWNER_CHAIN_UNOBSERVED`.

Natural terminal and formal-D blockers remain. The old PE outbuffer occupancy
claim remains `INVALIDATED_NOT_RTL_BUG`.

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT_NO_DELTA`: continuous closure,
triggered causal observability, time-to-root-cause, storage rotation,
release-gate applicability, predicate trace, public-surface/XMR and
actual-consumer scope-negative rules all produced executable evidence. No
non-synonymous public rule delta is needed.
