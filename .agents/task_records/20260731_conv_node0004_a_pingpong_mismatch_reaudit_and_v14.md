# Conv node0004 A ping-pong mismatch re-audit and v14

## RETURN_ANALYSIS

The mandatory v13 local re-audit found a deterministic configuration error.
The frozen C0 config enabled `special_array.inport0` ping-pong at terminal tag
4, but disabled `stream_engine.stream0` ping-pong. Those fields control two
independent RTL selectors over the same physical A buffer pair.

- MSE0 therefore wrote Buffer0 only.
- SA inport0 consumed Buffer0 initially, then switched to Buffer1 after the
  first accepted terminal-tag-4 boundary.
- Buffer1 had no producer. Buffer0 then filled because the consumer no longer
  drained it, backpressuring MSE0.
- B could be retained, but A could not arrive at the PE. Consequently ALU
  accept, PE outbuffer, SA group output, Buffer5 write and terminal could not
  advance.

This mechanism exactly explains the v12 dynamic boundary: A/B/C memory data and
Buffer4 read were observed, while SA group output and Buffer5 write remained
zero.

The previous statement that both sides had ping-pong disabled came from the
wrong historical artifact root. The v13 package actually carried bitstream
`9a881913...e310`, which binds the active
`r5-node0004-assumed-hardware-v1` mapping and contains the unilateral
configuration.

## FIRST_DIVERGENCE

`stream_engine.stream0.ping_pong=0` versus
`special_array.inport0.pingpong_en=1`.

Active RTL evidence:

- `WR_Buffer_AG.sv` SHA `8db8ad4a...8c2b`, lines 197-213: producer selector
  toggles only when MSE ping-pong is enabled and the last boundary qualifies.
- `Stream_Engine_Connect.sv` SHA `0ca375c4...5425`, lines 219-232: that selector
  chooses the first/second physical buffer.
- `Buffer_Manager_Cluster_Connect.sv` SHA `fcdf9372...611f`, lines 155-172:
  MSE0 maps to physical Buffer0/1.
- `SA_Inport_Connect.sv` SHA `86c9bba2...9c83`, lines 30-94: SA owns a separate
  selector and toggles it on its accepted terminal boundary.
- `SA_PE_Control_Block.sv` SHA `e254af41...2ca6`, lines 147-198 and 288-298:
  ALU acceptance requires matched operands.

Two focused RTL tests passed:

1. held B plus later A reaches operand-match and ALU acceptance;
2. Buffer0/2 16-occurrence address, clear and finish sequence is reachable.

Thus the local PE matching and Buffer0/2 address engines are excluded as the
first deterministic deadlock.

## LOCAL_REPAIR

Only two logical leaves changed:

```text
stream_engine.stream0.ping_pong:             0 -> 1
stream_engine.stream0.pingpong_last_index: null -> 4
```

The formula is:

```text
stream0.ping_pong = special_array.inport0.pingpong_en
stream0.pingpong_last_index = special_array.inport0.pingpong_last_index
```

The generator and signed-A Conv validator were updated. The validator now
rejects unilateral enable or threshold mismatch. Unit tests pass 4/4.

From fresh output/config roots, C0 JSON, mapping, bitstream, execplan and SCA
were rebuilt. The logical diff is exactly the two leaves above. Old bitstream:
`9a881913...e310`; new bitstream: `3bded4cb...93b`. The 84 packaged A/B/C matrix
files remain byte-identical to v13. W3 numeric analysis and golden generation
were not repeated.

Local rebuild report:
`artifacts/operator_config_validation/r5-node0004-a-pingpong-fix-c0-v2/local_rebuild_report.json`,
SHA `7242059e...9fb2`.

## PACKAGE_RELEASE

`r5_n4_hw_v13_abpe_boundary.zip` SHA `a9e941db...e5c9` is
`QUARANTINED_DETERMINISTIC_CONFIGURATION_ERROR` and must not run.

Fresh successor:

- status: `PACKAGE_READY_NOT_RUN`
- ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_n4_hw_v14_a_pingpong_fix.zip`
- ZIP SHA: `4bf890b5ad57d8952226125de4979e96e0c00a1d347d2fb59aec7cabb1cf44b2`
- sidecar SHA:
  `43e2e00970979f2e4caab9629a2cf023bd9689604bea81e6364b0ad478b6cc50`
- single command:
  `bash r5_n4_hw_v14_a_pingpong_fix/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy`
- expected return: `r5_n4_hw_v14_a_pingpong_fix_return.zip`
- `candidate_release=false`, `server_rtl_entries=0`

Post-generation current-rule final ZIP self-audit:

- report SHA:
  `f720913bdaa72ea119414bc9f85e6870c7de91278e1014ed94f6475bb93ce42b`
- `FINAL_ZIP_RULE_SELF_AUDIT_PASS=true`
- `errors=0`
- all required negative controls fail closed
- independent deterministic rebuild reproduced the exact ZIP SHA
- fresh-extract runtime preflight exit 0, package tree unchanged, runtime D
  absent, observer four-way/canonical/return gates valid

## BLOCKER_DELTA

Closed:

- `B_NODE0004_A_PRODUCER_CONSUMER_PINGPONG_MISMATCH`

Opened:

- `B_NODE0004_V14_DYNAMIC_RETURN_PENDING`

Unchanged: E3/E4/E5 remain false until a bound server return satisfies the full
compile/run/natural-terminal/formal-D conjunction.

## RULE_DELTA_PROPOSAL

None. The existing non-base-field ownership, workload provenance, final ZIP
self-audit, observer binding and INT8-SA current rules were sufficient.
