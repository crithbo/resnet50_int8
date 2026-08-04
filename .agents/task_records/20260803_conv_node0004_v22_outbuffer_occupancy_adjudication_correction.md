# Conv node0004 v22 outbuffer occupancy adjudication correction

## Scope

This is a mainline read-only re-adjudication prompted by the hardware-group
clarification that `outbuffer_group_count` changes only on initial population
and final output consumption, while ALU results are written through
`alu2ob_wr_ptr`.

No return was rerun. No numeric, W3, qparam, workload, configuration or golden
analysis was repeated. No server package was uploaded or run. No functional RTL
was modified.

## Corrected RTL semantics

Authoritative RTL:

- `NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_Outbuffer.sv`
- `NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_Control_Block.sv`

The outbuffer uses distinct pointers:

- `initial_port_wr_ptr` populates four initial psum slots per accepted initial
  write at `ptr`, `ptr+4`, `ptr+8`, and `ptr+12`.
- `ob2alu_rd_ptr` selects an existing live psum slot for ALU feedback.
- `alu2ob_wr_ptr` writes the ALU result back into the corresponding existing
  slot.
- `ob_out_rd_ptr` consumes final output slots.

`outbuffer_group_count` therefore represents live logical psum/output slots:
initial population adds four and final output consumption removes one. An ALU
write is a replacement of an already-live slot, not allocation of a new slot,
and must not add one to the count.

The previous proposed equation

```text
delta = 4*initial_accept + 1*alu_accept - 1*output_read_accept
```

was based on an incorrect physical-write-equals-new-occupancy assumption and is
withdrawn.

## v22 evidence that remains valid

The frozen v22 return identity and transport/package receipts remain unchanged.
The dynamic run still proves:

- SA A/B/C ingress occurred;
- per-PE ALU accepts occurred;
- `alu2ob_wr_handshake` occurred;
- no PE output accept, SA group output accept, Buffer5 write, natural terminal,
  or formal D output occurred.

The v22 observer's final state also reported `psum_ready` asserted for all PEs,
which is inconsistent with the former claim that a zero occupancy count was
masking psum feedback.

## Invalidated evidence

The old task record and machine report:

- `.agents/task_records/20260801_conv_node0004_v22_return_rtl_outbuffer_occupancy_rootcause.md`
- `outputs/conv_node0004_v22_return_analysis/rtl_rootcause_report.json`

are retained as historical artifacts but their
`B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED` root-cause and RTL
repair proposal are superseded.

The cited `4/4 PASS` from
`tests/test_conv_node0004_sa_outbuffer_occupancy.py` is not RTL validation. The
test defines a `repaired_count_next()` model that assumes every ALU write adds
one, then verifies consequences of that assumption. It cannot establish that
the assumption matches the intended outbuffer protocol.

## Corrected boundary

LAST_PROVEN_GOOD:

`SA_ALU_RESULT_ACCEPT_AND_OUTBUFFER_WRITE`

FIRST_DIVERGENCE:

`SA_ALU_RESULT_WRITE_TO_FINAL_RESULT_RELEASE_AND_PE_OUTPUT_VALID`

The output-valid path is controlled by the final-result tag decision:

```text
input last/index matching
  -> sa_pe_inport_last_matched or sa_pe_inport_last_out
  -> pipelined ALU last/matched
  -> ob_out_rd_ready[alu2ob_pingpong_buffer_select]
  -> sa_pe_outbuffer_port valid
```

The v22 observer did not return the last/matched terms, `ob_out_rd_ready`, the
three ping-pong selects, `outbuffer_group_count`, or the four pointer alignment
states. It therefore cannot distinguish configuration/tag-terminal mismatch,
ping-pong/pointer misalignment, or an RTL final-release defect.

## Blocker delta

- invalidated:
  `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`
- opened:
  `B_CONV_NODE0004_SA_FINAL_RESULT_RELEASE_PATH_UNOBSERVED`
- status:
  `RETURN_REANALYSIS_OPEN / PACKAGE_RELEASE=NONE`
- RTL classification:
  `NOT_YET_PROVEN`

## Successor requirement

Under the current return-to-successor continuous-closure rule, the Conv owner
must generate a fresh diagnostic-only successor that freezes numeric/W3/qparam,
workload, configuration, golden and functional RTL, and adds only low-cost,
qualified observation for:

- input last/index and matched/out decisions;
- pipelined ALU last/matched and ALU-result tag;
- `ob_out_rd_ready` set/clear;
- initial/ob2alu/alu2ob/outport ping-pong selects;
- initial/ob2alu/alu2ob/output pointers and their wrap/change events;
- count/empty only as corroborating state, not as the presumed root cause;
- first PE output valid/accept and first downstream SA/Buffer5 accept.

No functional RTL repair is authorized by this correction.

## Machine receipt

- path:
  `outputs/conv_node0004_v22_return_analysis/outbuffer_occupancy_adjudication_correction.json`
- bytes: `5346`
- SHA256:
  `2369d9eb4976b67d54a34b5eacfb1e24877b3a2a7000d29967ab082a3d960b8c`
- JSON parse: `PASS`
