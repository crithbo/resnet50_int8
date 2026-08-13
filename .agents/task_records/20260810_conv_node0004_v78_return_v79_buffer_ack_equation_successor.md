# serialized Conv node0004 v78 return → v79 successor

- Owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- Mainline target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- Numeric/workload/config repeated: `false / false / false`
- Functional RTL modified: `false`
- Server action: `false`

## v78 formal return

The return ZIP `r5_n4_hw_v78_buffer_input_owner_diag_r1786370037540532089_657093_return.zip` is 297405 bytes with SHA256 `1e6f2f6f4c5af952c903fb0552736cab43a027cbe9eec7a3d69d46cd63ec5b77`. CRC, root/path, exact-set, allowlist, source/execution/publication, core and plugin gates pass. Compile/run are 0, signal is NONE, but natural terminal is absent and formal D is 0 present / 320 missing / 0 mismatch; E3/E4/E5 therefore remain false.

`LAST_PROVEN_GOOD=FINAL_DESCRIPTOR_EVENT_18_THEN_BUFFER_QUEUE_WRITE_AND_PAYLOAD_ADVANCE`.

`FIRST_DIVERGENCE=FIRST_POST_FINAL_BUFFER_WRITE_SHOWS_MATCHED_VALID_INPUTS_AND_NONFULL_QUEUE_BUT_NO_REPORTED_INPUT_ACK_BEFORE_NEXT_PAYLOAD_ACCEPT`.

The final descriptor is observed at t=2446463000. The first post-final write occurs at t=2446468000 with valid=3, same=3, gotten=0, full=0 and reported bp=0; the following write at t=2446469000 reports bp=3. This uniquely closes the former post-memory owner-class ambiguity, but v78 does not expose every same-instance keep/bp-mask/equation term at the active edge. Root status is `UNRESOLVED_AT_BUFFER_INPUT_ACK_KEEP_EQUATION_PHASE`; this is not yet an authorized config or RTL defect.

Analysis report: `outputs/conv_node0004_v78_return_analysis/report.json`, 4221 bytes, SHA256 `4d5cfad2f8037dbc148ed1b542bb2cf7fbc2fdeef9a88e3882a44314c6e81c9b`.

## v79 successor

`r5_n4_hw_v79_buffer_ack_equation_diag` is a `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX` package. It adds one generated source-bound, same-instance equation witness covering qualified queue-write, matched, valid, same, gotten, keep-mask, bp-mask, public bp and mode terms. Its parser separates the remaining keep suppression, combinational phase, token-alignment and equation/owner candidates. Frozen numeric/W3/workload/config/golden/timeout/backpressure/RTL bytes were not changed.

The package inherits the same-epoch first-fresh PASS receipt `db884337d0a4026a51e7f1cc6aa9106d1628cbdc8c6b2b362704cb4e23ec19c2` and declares `first_fresh_after_change=false`. Deterministic double build, source-bound regeneration, focused predicate negatives, post-sim core, install-only runner/layout, signal finalizer, return joint gate and exact final-ZIP audit all pass with exit 0. Final audit is 4593 bytes, SHA256 `20290b5ad084dfa33cc9abd63ae745cd1fea5fb5305d9deff2fe26712b3b61e4`.

Pickup ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v79_buffer_ack_equation_diag.zip`, 5237461 bytes, SHA256 `447b5a5647b94d914093ec660134ad99ec5ab5e6fc194227bb4e7e9c21484d65`.

Server command: `bash r5_n4_hw_v79_buffer_ack_equation_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`

Expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v79_buffer_ack_equation_diag_<execution>_return.zip`

Storage rotation moved v78 to tested and leaves exactly one serialized-Conv pending package. Storage audit exits 0; index is 295379 bytes, SHA256 `ce2738930972b979a21558e5a40f8af129735a836fa1588e3b80b3ffd96a4b8d`. Concurrent native/QAdd pending entries were preserved.

## Blocker and rule disposition

- Closed: `B_CONV_NODE0004_POST_MEMORY_TERMINAL_BUFFER_OWNER_CLASS_UNRESOLVED`.
- Refined open: `B_CONV_NODE0004_BUFFER_INPUT_ACK_KEEP_EQUATION_PHASE_UNRESOLVED`.
- Kept invalidated: `B_CONV_SA_PE_OUTBUFFER_ALU_WRITE_OCCUPANCY_NOT_COUNTED`.
- Rule feedback: `RULE_CONFIRMATION=CONFIRMED_SUFFICIENT_NO_DELTA`.
- Package release: `PACKAGE_READY_NOT_RUN`.
