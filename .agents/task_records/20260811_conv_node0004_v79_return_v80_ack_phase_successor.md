# serialized Conv node0004 v79 return → v80 successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Mainline target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Numeric/workload/config repeated: `false / false / false`
- Functional RTL modified: `false`
- Server action: `false`

## v79 formal return

The exact v79 return is 337252 bytes, SHA256 `b130f1b0b1bcde8ece6c20f1746f847c68566dd2d60ba210e7dc501a8ceaf571`, execution `r1786374110391704069_681582`. Internal CRC/root/path/exact-set/allowlist, source/execution/install/publication, core and plugin gates pass. Compile/run are 0 and signal is NONE, but natural terminal is absent and formal D is 0 present / 320 missing / 0 mismatch, so E3/E4/E5 remain false.

`LAST_PROVEN_GOOD=SAME_INSTANCE_BUFFER_WRITE_ACCEPT_WITH_NOT_FULL_AND_BP_MASK_EQ3`.

`FIRST_DIVERGENCE=SAME_ACTIVE_EDGE_PUBLIC_BP_VECTOR_NOT_EQ3_DESPITE_NOT_FULL_AND_BP_MASK_EQ3`.

The generated same-instance bitmap contains 33 target writes and 16 exact contradiction-class witnesses: write accepted, queue not full and bp-mask=3 while public bp is not 3. The current RTL equation is `mse_buf_queue_bp_pre[i] = !buf_ag_idx_queue_full && buf_idx_bp_pre_mask[i]`. Because v79 samples the active region only, a delta-cycle settling transient remains observationally equivalent to a persistent public-ack or compiled-source mismatch. No config or RTL defect is claimed.

Analysis report: `outputs/conv_node0004_v79_return_analysis/report.json`, 3604 bytes, SHA256 `6403782cf19500fe52697c58d0ca5fbf2562e1917d36f68156bacf23f101293b`.

## v80 successor

`r5_n4_hw_v80_ack_phase_diag` is `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`. It preserves the frozen numeric/workload/config/golden/timeout/backpressure/RTL bytes and adds only a low-cost same-instance phase witness. For the exact target write it records active-edge, post-`#0`, and stable half-cycle operands/result plus the upstream gotten/consumer state. Its parser distinguishes persistent mismatch, active transient that settles and is consumed, settled-but-not-consumed, multi-delta settling, operand transition and incomplete evidence.

The exact observer binds the real RTL target SHA `7bbf229f60fb91fe89fd78d8e2df8716cd4de2be3fc578c5270c570ea33c7bca`. Row and tag ports use the RTL macros (`SE_BUF_ROW_INPORT_IDX_WIDTH=2`, `SE_BUF_INPORT_TAG_WIDTH=7`). Icarus does not parse SystemVerilog `bind`; therefore the final gate separately compiles the immutable target and observer module and machine-checks every exact bind actual against the real target declarations, with deletion, typo and wrong-sibling negatives. This focused fallback passes and does not claim full-design VCS elaboration.

Deterministic double build, exact source-bound regeneration, post-sim core, phase predicate traces, focused HDL/scope, inherited equation/input-owner/temporal parsers, runner safe compile/signal finalizer, 86/86 installed input opens, runtime layout, return joint gate and final ZIP audit all pass with exit 0. The same epoch reuses v77 first-fresh PASS `db884337d0a4026a51e7f1cc6aa9106d1628cbdc8c6b2b362704cb4e23ec19c2` and declares `first_fresh_after_change=false`.

Final ZIP: 5240046 bytes, SHA256 `cd3dd4f78f1ed75c0fc94b3113f6afb447c507e61fe9d289a20d90854e117a8a`.

Command: `bash r5_n4_hw_v80_ack_phase_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`

Expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v80_ack_phase_diag_<execution>_return.zip`

## Blocker and rule disposition

- Closed: `B_CONV_NODE0004_BUFFER_INPUT_ACK_KEEP_EQUATION_PHASE_UNRESOLVED`.
- Refined open: `B_CONV_NODE0004_BUFFER_ACK_ACTIVE_VS_SETTLED_CONSUMER_PHASE_UNRESOLVED`.
- Kept invalidated: `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`.
- Rule feedback: `RULE_CONFIRMATION=CONFIRMED_SUFFICIENT_NO_DELTA`.
- Package release: `PACKAGE_READY_NOT_RUN` after official storage rotation.

Official storage audit exits 0. v79 is archived under `tested/conv_serialized_node0004`; the only serialized-Conv pending ZIP is `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v80_ack_phase_diag.zip`. Concurrent native Conv and QAdd pending identities are unchanged. Storage index is 300877 bytes, SHA256 `f9a7d18c10ec87d3382a061bd1b0198ae825de0176c159933e10f9e6101aecef`.
