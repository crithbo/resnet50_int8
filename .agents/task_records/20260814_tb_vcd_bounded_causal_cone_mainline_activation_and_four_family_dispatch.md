# TB VCD bounded causal-cone mainline activation and four-family dispatch

Date: 2026-08-14  
Role: `mainline.control`  
Owner thread: `019ff027-e7db-72a3-b282-cfad8708da05`  
Owner epoch: `2`  
Registry epoch consumed: `6`  
Shared epoch: `tb-vcd-bounded-causal-cone-optional-v1-0820e1733437`

## Previous progress

`OBSERVER_ONLY_WIDE_CAUSAL` was the sole current bulk-evidence path. It successfully established broad selected-cone plateaus, but the native p46 and GAP v61 returns still lacked enough post-accept, queue, bank, barrier, outstanding, clear, finish and global-terminal state to close a unique root in one round. The observer path remains a valid, unchanged default and is not retired.

## Current purpose and decision

The user approved a second explicit diagnostic option and selected it for the next fresh package of GAP, serialized Conv, native Conv and QLinearAdd. The optional mode is `TB_VCD_BOUNDED_CAUSAL_CONE`; it does not replace observer-only.

The shared selector, causal-cone contract, runtime supervisor, retention/streaming analysis tools and focused regressions from the optimizer receipt were mechanically synchronized. Mainline narrowly merged the public rule/router/optimizer/README semantics and registered a mode-conditional final-ZIP gate. Exactly one bulk mode is applicable per package; the observer gates remain applicable only to observer mode and the VCD gate only to VCD mode.

## Activated VCD contract

- package-local TB standard `$dumpfile/$dumpvars/$dumpon/$dumpoff/$dumpflush` only;
- actual `DUMP_VCD=0,DUMP_FSDB=0,TB_DUMP_FSDB=0`;
- no VPD, FSDB, FST, UCLI direct-VCD, vendor query or full-top unbounded dump;
- 41 source-bound causal roles, four FIRST_DIVERGENCE layers and complete pairwise candidate×boundary matrix;
- plateau stop only under advancing owner-clock/sim-time plus stable qualified counters, complete causal-state digest and global witness, complete coverage and no unresolved X/Z;
- global progress advance forbids local plateau stop;
- independent 3×30-second sim-time freeze, 60-minute wall, 8GB VCD projection, 10GB return projection, disk/write/quota and signal safeguards;
- 100,000,000-byte warning only; no hard truncation, sampling or size deletion;
- all non-natural safety exits publish PARTIAL/core evidence and never claim natural terminal, formal D, E4 or E5;
- streaming `analysis_state.json`, append-only `checkpoints.jsonl` and incrementally edited `report.md`;
- per-family raw result retention `MAX_PROGRESS + LATEST_1 + LATEST_2`, with deletion only after analysis, family/mainline dual consumption, deterministic core evidence and protected-set audit.

## Four-family build dispatch

All four family owners are authorized only to build and locally validate a fresh VCD-mode successor:

- GAP preserves the v61 slice-local workaround and sum_s2 target and adds selector, MSE0/Buffer0 ARM, ping-pong/bank, barrier/lifetime/clear, GA/MSE4 and finish/global progress cone.
- Serialized Conv preserves the v91 compile-log normalizer repair, v88 actual-source baseline and the real ACK/FIFO/aggregate/MSE4/terminal target; the retired derived ACK comparator remains forbidden.
- Native Conv preserves the p42 vector correction and p46 MSE4 accepted progress and adds FIFO occupancy/enq/deq, tag/address/mask, outstanding/response, last/count, completion FSM, drain/clear and finish aggregation.
- QLinearAdd preserves the v62 manifest/SCA identity repair and tail-round selected-port target and covers both ping-pong branches, bank/lane ownership/readiness, producer/clear, read accept, output and terminal.

Each family must keep its current pending package byte-frozen until the fresh VCD exact ZIP passes all current gates and new-epoch first-fresh audit; only then may its storage manager atomically move the old pending package to superseded and publish the new package. Each family must proactively return `PACKAGE_READY_NOT_RUN` or an explicit terminal state to the dynamically resolved mainline.

## Claim boundary

This record authorizes local package construction and validation only. It authorizes no upload, lease, connection, server execution, functional RTL/config/numeric/workload/golden change, production VCS claim, DUT root-cause claim, natural terminal, formal D, E3, E4 or E5. Mainline does not continuously poll family tasks after dispatch.
