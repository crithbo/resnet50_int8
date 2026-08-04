# Conv node0004 v22 return: SA PE outbuffer occupancy root cause

## Scope and non-repetition

This record closes the existing v22 return analysis without rebuilding the
frozen node0004 workload, repeating W3/numeric analysis, changing configuration,
modifying functional RTL, or generating a successor package.

- `numeric_analysis_repeated=false`
- `node0004_workload_rebuilt=false`
- `config_rebuilt=false`
- `functional_rtl_modified=false`
- `PACKAGE_RELEASE=NONE`
- `next_state=WAIT_RTL_FIX`

## RETURN_ANALYSIS

Return ZIP:
`C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_n4_hw_v22_featurebind_return.zip`

- bytes: `79566`
- SHA256: `70d0db137b78a329965c9fb841bcc3d8abafbb1b54871fd73566f397884c4bfe`
- source ZIP: `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v22_featurebind.zip`
- source SHA256: `caf96850ceb5dcf66233dd736757bb2e0b3fbb3b63b066dc9c0194022f1ac68b`
- missing adjacent sidecar is content-neutral under the user-attested transport
  policy.
- ZIP CRC/root/exact-set/allowlist: PASS.
- package/install/observer/three-feature runtime binding receipts: PASS.
- compile exit `0`; run exit `0`; signal `NONE`.
- natural terminal: absent.
- formal D: expected `320`, observed `0`, missing `320`, mismatch `0`.
- joint result gate: FAIL; E3/E4/E5 are all false. All-missing D with
  `mismatch=0` is not a numeric pass.

## FIRST_DIVERGENCE

Last good boundary:

- A group accepts `16`;
- B group accepts `16`;
- C group accepts `8`;
- per-PE ALU accepts `2048`, exactly `32 x 64` PE events;
- package observer independently records `alu2ob_cycles=32`.

First bad boundary:

`ALU_ACCEPT_TO_PE_OUTBUFFER_OCCUPANCY`.

The ALU result is accepted and physically written into the PE outbuffer RAM, but
the destination group's occupancy counter does not count that write. The group
therefore remains logically empty. Dynamic consequences match exactly:
`pe_out_accept=0`, `sa_group_out_accept=0`, Buffer5 write edge `0`, and no
natural terminal.

The canonical observer records qualified progress `182`, followed by four
consecutive `262144`-cycle zero-delta windows. This is a deterministic stall,
not a workload that merely needs more time.

## HANG_ROOT_CAUSE: confirmed RTL defect

Leaf:
`NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_Outbuffer.sv`

Leaf SHA256:
`be66a8c68e8c31398ccf7784eff73fd733831498bf5580c22f457d445cd229be`

Code chain:

1. Lines `240-255`, `445`, and `473-488`: one accepted initial C/psum
   transaction writes four physical entries at offsets `+0,+4,+8,+12`.
2. Lines `257-267`, `446`, and `479-491`: one accepted ALU result writes one
   physical entry at `alu2ob_wr_ptr`.
3. Lines `453-454`: `outbuffer_group_wr_cnt_update` includes only
   `outbuffer_group_initial_wr_en`; it omits
   `outbuffer_group_alu2ob_wr_en`.
4. Lines `501-516`: the counter consequently implements initial `+4` and output
   read `-1`, but no ALU-result `+1`.
5. Lines `72` and `545`: a zero counter asserts `empty`, which masks the stored
   psum tag and blocks the feedback/output sequence.

This is not an absent architectural feature. The RTL already contains the ALU
write request, handshake, pointer update, tag write, and data write. Only the
matching occupancy accounting is missing.

## Minimal hardware repair proposal

Proposal only; no RTL was modified.

For each physical outbuffer group, compute:

`delta = 4*initial_wr_accept + 1*alu_result_wr_accept - 1*output_rd_accept`

and update the count with an intermediate width that represents the complete
signed delta and legal range.

The repair cannot be a simple OR of initial and ALU write enables:

- initial write occupies four slots, while ALU write occupies one;
- an OR would count ALU-only as `+4`;
- the existing simultaneous write/read branch holds the count, but
  initial+ALU+read requires net `+4`;
- the two writes may select different ping-pong groups, so accounting must stay
  per group.

## Local directed positive and negative controls

Command:

`C:/Users/15383/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -m unittest tests.test_conv_node0004_sa_outbuffer_occupancy -v`

Result: exit `0`, `4/4 PASS`.

Test SHA256:
`21de66079db3e4ce8294a96c2d79ee738ea40bf4645fdb7538a598c9af4730b6`

- positive: initial-only write is correctly `0 -> 4`;
- negative: stock ALU-only write remains `0`, while required result is `1`;
- negative: simple OR makes ALU-only `+4`, not `+1`;
- negative: simple OR loses the mixed initial+ALU+read net delta.

Boundary: this is a directed state-transition model transcribed from the cited
RTL. A patched RTL compile/full simulation was not run because functional RTL
modification is outside this task's authorization.

## BLOCKER_DELTA

Closed:

- return/source identity, CRC, exact-set, allowlist and internal receipts;
- compile/runtime and three diagnostic-feature bindings;
- MSE0/Buffer0-1 delivery and SA A/B/C ingress as the first divergence.

Opened:

- `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`.

Remaining:

- hardware group implements and reviews the mixed-cardinality per-group counter;
- rerun the frozen node0004 package/workload against repaired RTL;
- only a natural terminal plus exact 320-item D readback can promote E3/E4/E5.

`RULE_DELTA_PROPOSAL=NONE`

Machine report:
`outputs/conv_node0004_v22_return_analysis/rtl_rootcause_report.json`

Machine report SHA256:
`ce63d40c5bbb61be442b72b06abadbc5cfc3f54d268e4061bb1b5313809d6f90`
