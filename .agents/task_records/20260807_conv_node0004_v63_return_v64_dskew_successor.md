# Conv node0004 v63 RETURN → v64 DSKEW successor

## Scope and receipts

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- v63 return SHA256: `87ed7fab2c214b260f5a7ec9761e4e47581fcd321bb458e2a32f9a5d52456109`
- Frozen v63 source SHA256: `99f50faeed69d89cff3211121661b5331a9e98d8135064b41b76203f7c277712`
- Post-generation server rule SHA256: `a8f628413367805d5fe9822233b39460e5386b1ecaf321ba050546a96cd843d8`
- Full machine closure report: `outputs/conv_node0004_v63_return_v64_successor/report.json`

No numeric, W3, qparam, tail, workload, materialized config, golden, timeout,
backpressure, ISA, hardware, active ndp-sim, or functional RTL was rebuilt or
modified.

## RETURN_ANALYSIS

The v62 silent early-exit escape is closed. The formal v63 return records
production compile exit 0, run exit 0, signal `NONE`, and both
`RUNNER_ERROR`/`RUNNER_FINAL_STATUS` support in the exact source runner.

The PE keep fix is also dynamically proven:

- LC18 terminal index 3 is accepted by PE7.
- PE7 releases the corresponding result.
- physical LC17 advances from index 1 to index 2.

The run does not reach natural terminal. Formal D is 0/320 present,
320/320 missing, mismatch 0; all-missing is not a numeric pass. E3 is true by
the established project evidence boundary; E4 and E5 remain false.

## LPG, FD, and root status

- LAST_PROVEN_GOOD:
  `LC18_INDEX3_TERMINAL_ACCEPTED_BY_PE7_KEEP_INPORT0_AND_PE7_RESULT_RELEASED_WHILE_PHYSICAL_LC17_ADVANCES_TO_INDEX2`
- FIRST_DIVERGENCE:
  `D_DATA_PREPARE_TOTAL20_EXCEEDS_DESCRIPTOR_TOTAL18_AND_PREPARED_FIFO_REACHES32_WITH_DESCRIPTOR_FIFO_EMPTY`

Twenty 16-entry data groups are prepared, but only eighteen write descriptors
are emitted and drained. The unmatched two groups fill prepared storage to 32
entries while descriptor FIFO is empty, WR ready is low, and neither D-last nor
slice-finish occurs. This proves a unique causal skew boundary, not yet one
unique config or RTL cause. Four mechanisms remain compatible; therefore no
speculative config or RTL fix was made.

The old SA PE Outbuffer occupancy diagnosis remains
`INVALIDATED_NOT_RTL_BUG`.

## v64 successor

- Identity: `r5_n4_hw_v64_dskew_diag`
- Classification: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`
- Candidate release: `false`
- Pending ZIP SHA256:
  `e2ad1cbb94bec3379b5a810352cdfe8d9d5cfa17f2870696a862650b593d7e25`
- Exact command:
  `bash r5_n4_hw_v64_dskew_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`
- Expected return:
  `/home/panqs/ndp/simresult/r5_n4_hw_v64_dskew_diag_return.zip`

v64 adds one runtime-gated, low-overhead, time-aligned qualified DSKEW ledger.
It correlates descriptor, prepared-data, source push/pop, tag/Buffer accept,
LC13/14/15, PE7 write/read, MSE input, D write/last, descriptor terminal and
post-terminal counters. Levels remain corroboration only.

## Validation and storage

- Deterministic double build: PASS.
- Install-only V2 runner and 86/86 exact SCA opens: PASS.
- Shared runtime-layout validator: PASS, errors 0.
- Focused observer syntax/scope and actual-consumer negatives: PASS.
- DSKEW predicate event trace, stable-level and simultaneous-event controls:
  PASS.
- Runner nonzero-exit stderr visibility and collision controls: PASS.
- Final ZIP rule self-audit: PASS, errors 0.
- All required negative controls: fail closed.
- Storage audit: PASS.
- v63 moved to `tested`; v64 is the only
  `conv_serialized_node0004` package in `pending`.

## Rule feedback

`RULE_CONFIRMATION=CURRENT_RULES_SUFFICIENT`. The real v63 return confirms the
nonzero-exit stderr rule closed the silent-exit escape. Existing
continuous-closure, information-gain, predicate-trace, install-only,
fixed-result, root-direct-set, and storage-rotation rules were sufficient; no
non-synonymous rule delta is proposed.
