# GAP node0071 v9 local rule-semantics/RTL reaudit

- Date: 2026-07-31
- Family: QLinearGlobalAveragePool / node0071
- Claim boundary: `CONFIG_ONLY_CORRECTNESS_BASELINE`
- Final adjudication: `LOCAL_EXHAUSTIVE_REAUDIT_NO_DETERMINISTIC_ERROR_FOUND`
- Package state transition: `HOLD_PENDING_LOCAL_RULE_SEMANTICS_RTL_REAUDIT` -> `PACKAGE_READY_NOT_RUN`
- Package: `artifacts/operator_config_validation/r5-server-test-packages/r5_n71_gap_v9_ingress_rule.zip`
- Package SHA256: `d37f40e768001d3588cd22f25040ba4e229ffc138221a42b13d7e446436e644c`
- Package rebuilt: no
- Package bytes changed: no

## Scope and reuse

This was a receipt-only/static/directed-RTL reaudit. It consumed the frozen six-stage sum local-E2 mapping, exact-tail materialization, v9 SCA/execplan and active local RTL. It did not repeat GAP numeric analysis, rerun sum/tail workload, rebuild the package, modify functional RTL, inspect a server, upload, or run.

The six packaged sum binaries are byte-identical to the frozen local-E2 mapping outputs. All six stages retain:

- logical stream0/1/2 -> `READ_STREAM0`/`READ_STREAM3`/`WRITE_STREAM0`;
- physical read MSE0/read MSE3/write MSE4 (write-stream local index 0);
- enabled buffers 0/4/5, all-bank masks, no neighbor or pingpong;
- GA group0 -> operand0, constant 1 -> operand1, GA group2 -> operand2;
- opcode14 `int32_mac`, non-transout;
- logical lifetime 1, encoded `life_time_minus_1=0`.

## Directed evidence

Commands:

```text
iverilog -g2012 -I NDP_copy01/rtl/includes -s tb_ga_int32mac_dual_accept -o outputs/gap_node0071_v9_local_reaudit/tb_ga_int32mac_dual_accept.vvp outputs/gap_node0071_v9_local_reaudit/tb_ga_int32mac_dual_accept.sv NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv
vvp outputs/gap_node0071_v9_local_reaudit/tb_ga_int32mac_dual_accept.vvp
iverilog -g2012 -I NDP_copy01/rtl/includes -s tb_buffer_physical_route -o outputs/gap_node0071_v9_local_reaudit/tb_buffer_physical_route.vvp outputs/gap_node0071_v9_local_reaudit/tb_buffer_physical_route.sv NDP_copy01/rtl/Slice/LSU/Buffer_Manager_Cluster/Buffer_Manager_Cluster_Connect.sv
vvp outputs/gap_node0071_v9_local_reaudit/tb_buffer_physical_route.vvp
```

All four exit codes were 0.

- Route TB: `PASS: MSE3->buffer4->GA group2 and GA->buffer5->write MSE0 routes`.
- Joint-accept TB: `PASS: GA opcode14 waits for and jointly accepts operand0/operand2`.

The second TB explicitly drives A alone first. A is captured and backpressured, C remains requested, and no matched/qualified MAC is formed. When C arrives, A/constant1/C are consumed exactly once.

## Key equations and exclusions

- Read-MSE request/data pairing is reciprocal: address generation consumes an index only when returned data is ready; returned data enters its output queue only when the address queue can accept. Both output queues drain under the same buffer-ready signal and only advance when non-empty.
- For buffers 2..4 the source read-MSE index is `BUF_IDX-1`; therefore buffer4 is owned by MSE3.
- Buffer memory-write enable is `request_valid && request_rw && write_valid`. A request without its paired data cannot mark buffer validity.
- Input buffer physical mapping is group=`BUF_IDX/2`, slot=`BUF_IDX%2`; buffer4 is GA group2 slot0.
- With SA disabled its ready contribution is 1; the SA/GA consumer-ready conjunction cannot block this path.
- Opcode14 is not transout. GA matched requires every enabled operand's one-entry inbuffer valid.
- Buffer5 with source-id 1 selects GA output and feeds write-stream0/global MSE4.
- Natural terminal is only asserted after the last-tagged write data is accepted by memory; `Slice_Execution_Manager` remains in compute until this pulse, so the following barrier cannot prove completion early.

No deterministic error was found in owner, final physical number, LC/MSE binding, buffer mask/pingpong, ready/valid, full/empty, lifetime, GA tag/capture, output-buffer, write-data, last, terminal or barrier semantics.

The v7 boundary `MSE0_TO_BUFFER0_ACCEPTED + READ_STREAM3_PATH_UNOBSERVED -> GA_DUAL_OPERAND_ACCEPT_ABSENT` remains an observability boundary. Static topology and directed RTL exclude a deterministic stream1-to-wrong-MSE, MSE3-to-wrong-buffer, buffer4-to-wrong-GA-port, one-sided false accept, pingpong mismatch, SA backpressure, lifetime off-by-one, or early-terminal error. The qualified dual-ingress observer in unchanged v9 remains the correct next dynamic discriminator.

Machine report:

- `outputs/gap_node0071_v9_local_reaudit/local_exhaustive_reaudit_report.json`

## Rule delta proposal

No new public rule is required from this audit. Preserve `CDA-GAP-DUAL-OPERAND-INGRESS-OBSERVABILITY-001`; treat an observed MSE0 acceptance plus unobserved stream3 as insufficient to infer an active-RTL/config fault until MSE3 request, MSE3 returned-data acceptance, buffer4 valid/read acceptance and GA operand2 capture are independently qualified.

