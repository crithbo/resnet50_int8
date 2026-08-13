# Conv node0004 v77 return → v78 Buffer input-owner successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Formal return SHA256: `39d25e0fb99f790e019749d0d463c36a4be0d78ab5089c7ab9445efdb2b935bf`
- Source v77 SHA256: `316d5d2a50ae3378cd7809963e5a9bb54a38e5f07763d512864e02945dcd4d91`
- Analysis report: `outputs/conv_node0004_v77_return_analysis/report.json`

## Formal adjudication

The return is internally valid and source/execution bound. Compile and run both exited 0 with signal `NONE`, but the DUT did not reach natural terminal and formal D remained 0 present / 320 missing / 0 mismatch. Therefore E3/E4/E5 remain false.

Qualified target-complete evidence closes the previous incomplete-ring blocker. The Memory branch reaches its local terminal and drains 9/9, while the Buffer branch accepts eight further queue entries and ends with four residual entries. The last proven good boundary is `MEMORY_BRANCH_LOCAL_TERMINAL_AND_QUEUE_DRAIN_9_OF_9_WHILE_BUFFER_BRANCH_CONTINUES_QUALIFIED_PROGRESS`; the first divergence is `AFTER_MEMORY_LOCAL_TERMINAL_BUFFER_QUEUE_ACCEPTS_EIGHT_MORE_ENTRIES_AND_RETAINS_FOUR_WITH_NO_NATURAL_D_RELEASE`.

This is not yet a proven configuration or RTL defect: `buf_idx_mode=2` enables keep semantics, and adjacent writes retain the same raw row/column tags while changing queue payload. The open blocker is refined to `B_CONV_NODE0004_POST_MEMORY_TERMINAL_BUFFER_INPUT_OWNER_UNRESOLVED`. The historical outbuffer-occupancy diagnosis remains `INVALIDATED_NOT_RTL_BUG`.

## v78 successor

`r5_n4_hw_v78_buffer_input_owner_diag` is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It freezes numeric/W3/qparams/tail/workload/config/golden/timeout/backpressure/functional RTL and adds only a post-final Buffer input-owner parser and post-sim binding. It distinguishes five candidates using qualified `TOKEN_ORIGIN_ACCEPT_EDGE_V2`, `ROWLC4_BUFAG_EDGE_V1`, and `DTERM_OWNER_BOUNDARY_V1` records.

The first local candidate incorrectly used cumulative `desc==18` as the final event. A negative control caught this before release; the final package requires `desc_ev==1 && desc==18`. A second pre-release shared-layout check caught a stale path-budget receipt; the released ZIP now records the actual 130-character projected relative path and 227-character maximum absolute path.

The final ZIP passed deterministic double build, source-bound exact regeneration, post-sim four scenarios, temporal over-budget retention, the parser positive case and four negatives, isolated runner safe-compile/finalizer controls, return conjunction, shared runtime-layout validation, and final-ZIP audit (`errors=0`). This is the same first-fresh rule epoch, so it binds the accepted v77 first-fresh receipt and declares `first_fresh_after_change=false`.

## Release and storage

- Status: `PACKAGE_READY_NOT_RUN`
- Pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v78_buffer_input_owner_diag.zip`
- ZIP bytes: `5231287`
- ZIP SHA256: `57044a3aef6208650681fe76076d20700fa267ddf415e91a3beb7d5daf065b56`
- Command: `bash r5_n4_hw_v78_buffer_input_owner_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`
- Expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v78_buffer_input_owner_diag_<execution>_return.zip`
- Storage index SHA256: `8709dcdba3b92042a0f705dbb5863536ebe1a72bd994862f04be20eb6b668a42`

v77 was atomically rotated to `tested`; serialized Conv has exactly one pending ZIP. Parallel native Conv and QAdd pending identities were preserved.

## Rule feedback

`RULE_CONFIRMATION=CONFIRMED_EFFECTIVE_NO_DELTA`. The current final-ZIP and negative-control rules detected both package-local escapes before release, so no non-synonymous rule change is proposed.
