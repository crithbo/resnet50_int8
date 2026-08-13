# 2026-08-12 — Serialized Conv v87b false-positive, config-workaround and conditional RTL adjudication

## Ownership and scope

- Mainline role: `mainline.control`
- Family role: `family.conv.serialized`
- Family owner thread: `019ff02d-901b-7f70-a9da-f54e268b5bbe`
- Registry epoch: `6`
- Mode: read-only adjudication.
- No RTL, config, numeric, workload, package, storage, rule or server state was changed.

## Required progress and purpose

Previous progress: v85b localized production compile exit `2` to two package-local observer XMRE sites;
withdrawn v86b preserved the observer/structured-first-error repair; v87b compiled beyond that repair,
started simulation and returned authoritative raw VPD. Its execution-bound phase observer reported a stable
ACK public-output versus same-instance inline-RHS contradiction.

Current purpose: test whether that classification can be a false positive, determine whether a
semantics-preserving serialized-Conv configuration workaround exists and issue a code-grounded RTL report
without modifying or running anything.

## Mainline adjudication

- `FALSE_POSITIVE_DISPOSITION=EVIDENCE_INCOMPLETE`.
- `OBSERVER_OR_TB_FALSE_POSITIVE=LARGELY_REBUTTED_BUT_NOT_CLOSED`.
- `SOURCE_IDENTITY_MISMATCH=OPEN_MATERIAL_ALTERNATIVE`.
- `CONFIG_INDUCED_VALID_BEHAVIOR=REBUTTED_FOR_SAME_TIME_BOOLEAN_CONTRADICTION`.
- `FUNCTIONAL_RTL_DEFECT=CONDITIONALLY_SUPPORTED_IF_ACTUAL_COMPILED_DUT_SOURCE_MATCHES_CURRENT_LOCAL_SOURCE`.
- `CONFIG_WORKAROUND=NONE` under mathematical, transaction, lifetime, coverage, natural-terminal and
  formal-D equivalence.
- `RTL_ERROR_REPORT=CONDITIONAL_RTL_ERROR_REPORT`.

The workflow state remains `WAIT_RTL_FIX` only as a terminal control-plane bucket. It is not an unconditional
claim that the current local RTL text was the faulty server-compiled text. Before an RTL repair can be authorized,
the project must bind the actual compiled target/filelist/include/define/preprocessed/elaborated-driver identity
and obtain same-attempt portable VCD/query evidence or another identity-bound semantic decoder result.

## False-positive review

The exact observer is input-only, uses the full slice13/group1/MSE4 WR Buffer-AG hierarchy and records 13
complete five-phase sequences containing 65 binary-known events. Every stable `LATE_750PS` sample retains XOR
bit1; strict `$realtime`, post-edge sampling, input-only bind and zero X/Z parse failures strongly rebut ordinary
NBA/continuous-assign settling, X/Z and observer-drive explanations. The old parser's slice0/group0 hard binding
is separate from the exact phase parser and does not contaminate the exact decision, but remains a return-
completeness defect.

The remaining false-positive boundary is material: v87b's compile-source receipt binds the Makefile and package
observers but not the actual server DUT target, filelist, parameters, defines/includes, preprocessed target or
elaborated driver set. The raw 65 event rows were not returned, `slice_rst` was not included in the payload and
the raw VPD has not been semantically decoded. Therefore the executed contradiction is strong evidence, but its
mapping to the current local source is conditional.

## Code-grounded conditional RTL report

Current local source:

- `NDP_copy01/rtl/Slice/LSU/Stream_Engine/Memory_Stream_Engine/Buffer_AG_Idx_Queue.sv:47` maps the column tag
  to port/bit 0; line 52 maps the row tag to port/bit 1.
- Lines 69-84 update `buf_idx_gotten_bit` from the public ACK.
- Lines 117-128 form same/gotten/valid masks and `buf_all_idx_matched`.
- Lines 149-150 form keep release and `buf_idx_bp_pre_mask`.
- Line 152 continuously defines, for each bit, `mse_buf_queue_bp_pre = !buf_ag_idx_queue_full &&
  buf_idx_bp_pre_mask`.
- Lines 168-186 enqueue matched indices into the depth-32 Buffer-AG FIFO.
- `Stream_Engine.sv:291` mirrors pre ACK to post ACK; lines 506-539 connect MSE4 through the sole WR-MSE path.
- `NDP_Parameters.svh:436-438` defines four read MSEs and one write MSE.

Observed execution-bound condition is `wr=1`, `full=0`, `bpmask=2'b11` while public ACK differs from the
same-instance RHS at stable +750 ps: 12 late samples have XOR 2 and one has XOR 3, so all include the row/bit1
contradiction. If the actual compiled source and single-driver set match the local code, this cannot be legal
configuration behavior. The downstream ledger's memory residual `0`, buffer residual `4`, eight enqueues versus
seven dequeues after memory terminal, absent natural terminal and formal D `0/320` support a temporal causal chain,
but without portable driver-cone evidence do not prove the ACK contradiction is the unique stall root.

## Configuration-workaround adjudication and cost

The real D stream4 uses Buffer-AG `[row,col]=[keep,buffer]`, spatial size 16 and the only WR MSE (MSE4).
No alternate write engine exists, and strict Buffer-AG requires exactly one keep and one buffer side.

- Swapping row/col ownership or changing keep threshold still exercises the same two-bit ACK equation and changes
  tag ownership, ordering, transaction boundary and lifetime. It is diagnostic-only and resets all closure claims.
- Splitting the 4x4 traversal into four row phases still uses MSE4, adds at least three launch/synchronization
  intervals and reduces row-phase concurrency to at most one quarter before complete rematerialization evidence.
- Disabling slice13 without replay loses at least `1/28` physical coverage. Replay needs at least a second stage,
  lowers first-stage peak slice utilization to at most `27/28`, adds synchronization and moved-shard traffic, and
  still uses the same MSE4 module.
- Changing target or suppressing D write discards all 320 formal-D outputs and is not the same operator.

Therefore no proven production configuration workaround preserves the serialized Conv computation, transactions,
lifetime, D coverage, natural terminal and E3/E4/E5 boundary.

## Next evidence and repair boundary

The first later fresh package, only after the portable VCD/query shared gate is activated and mainline dispatches
it, must bind the actual compiled DUT/filelist/include/define/preprocessed driver identity; retain all 65 raw phase
rows plus `clk/rst_n/slice_rst`; and return same-attempt raw VPD, direct portable VCD and a complete registered
event/query receipt. Functional repair candidates remain conceptual until that evidence closes source identity:
restore the documented single driver, remove duplicate/alias/macro ownership, or coherently revise the entire ACK
protocol only if a registered ACK is architecturally intended.

Any later repair must pass production compile, positive ACK-equation and deliberate-negative controls, raw VPD,
portable VCD/query, natural terminal, formal D `320/320` and the independent E3/E4/E5 gates. No current package
build or server action is authorized by this record.

## Source receipts

- Family task record: `outputs/conv_node0004_v87b_false_positive_review_v1/task_record.md`, bytes `16255`,
  SHA-256 `5bf1aac33011f480f291f1bdc5ff5eca8eb3d4ae5246e0b8843cd079fe988769`.
- Machine review: `outputs/conv_node0004_v87b_false_positive_review_v1/review_report.json`, bytes `33285`,
  SHA-256 `91a51bec20be400663988dbcd5e31877107bce0b9222245dcfca37c654486101`.
- Identity receipt: `outputs/conv_node0004_v87b_false_positive_review_v1/identity_receipt.json`, bytes `1545`,
  SHA-256 `e4a8a47420b9fd1dbb857e65828170607fcb0123364b81cce2652fb27e088075`.

Conflicts: `[]`.
