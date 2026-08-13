# serialized Conv node0004 v70 return → v71 token-origin successor

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `PACKAGE_READY_NOT_RUN`
- package class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`

## RETURN_ANALYSIS

The formal v70 return is bound to execution `r1786203000568429970_4150663`, return SHA256
`3860731999ee024b3589094a95bb3c7e78684424f49b2ea5099fd0f573d5cff7`, and source SHA256
`1076a9a5371d3988c31efbecfa750c10ee12b4ffc5e0777aeffa2a6ea710ec93`.
CRC, single root, safe paths, exact allowlist, per-file receipts, source manifest, install reset,
observer feature, fixed publication and NDP-root direct-set gates pass. Production compile and run
exit zero with signal `NONE`; simulation started, but the DUT did not reach natural terminal and no
formal D member was returned (`0/320`, missing `320`, mismatch `0`). Therefore E3/E4/E5 remain false.

The bound source manifest expects cloud RTL `0ccae916ef61904a64d6cf8ec1d1931b45e428d8`; the return does
not carry a separate actual Git-commit receipt. Successful production compilation makes this an
identity provenance limitation/nonblocking causal risk, not a compile or DUT failure.

## Qualified causal result

- LPG: `DESCRIPTOR_18_AND_PREPARED_GROUP_18_JOIN_DRAIN_WITH_BUFFER_POP_21`.
- FD: `POST_DESCRIPTOR_BUFFER_POP_22_ACCEPTS_TAG_0X35_AND_PREPARED_GROUP_20_WITH_NO_DESCRIPTOR`.
- Final exact qualified counts: descriptor `18`, Buffer pop/request/return `23/21/18`, prepared
  write/read `20/18`.
- After descriptor 18: no additional descriptor; two Buffer pops, two requests, one return, two
  prepared writes and one final prepared read. The extra popped tags are `0x35` and `0x24`; both
  expose last-index `5`. `buf_ag_last_req_flag=0` and `data_last=0` throughout the excess suffix.
- The descriptor queue ends empty while prepared occupancy reaches `32`.

This closes the output-side token ownership question and excludes memory-channel backpressure and
simple return replay. It does not expose the Memory_AG and Buffer_AG combined input queue-write
tokens, so it cannot yet distinguish early Memory_AG token exhaustion, excess Buffer_AG token
supply, a stale Buffer queue entry, or last/index projection mismatch. No CONFIG or RTL mutation is
authorized by v70 alone.

## v71 successor

v71 adds one read-only, low-cost `TOKEN_ORIGIN_EDGE_V1` ledger. Every emitted record contains all
five event-class bits in the same owner-clock sample: Memory queue write, Buffer queue write,
Memory queue pop, Buffer queue pop and descriptor accept. It records raw per-input tags/backpressure,
combined queue write/read data and output tags. There is no priority arbiter and no class-specific
snapshot advancement, satisfying the current multiclass no-loss gate. Numeric, workload, config,
golden, timeout, backpressure and functional RTL are byte-frozen.

Final ZIP audits pass with errors `0`: deterministic double build, exact manifest/sidecar, install-only
six-flow harness, actual runner-to-safe-compile/finalizer, focused HDL syntax/scope and declaration/XMR
negatives, return contract, and multiclass predicate trace including the priority-only loss negative.

Pickup:
`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v71_token_origin_diag.zip`

- bytes: `5181565`
- SHA256: `8cab1c7762496cf25ecde9057388d88c428711a2e52dc5a1e8e610a66840b452`
- command: `bash r5_n4_hw_v71_token_origin_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`
- expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v71_token_origin_diag_<return_tag>_return.zip`

Storage rotation moved v70 to `tested` and leaves exactly one serialized-Conv package pending. No
other family package was moved or overwritten.

## Rule feedback

`RULE_CONFIRMATION`: current continuous-closure, install-layout, fixed-result, root-direct-set and
multiclass edge no-loss rules are sufficient. The v70 return itself supplies 25 same-sample
multi-event records and exact all-bit parsing reproduces all class totals; v71's local negative model
proves a priority-only emitter would lose classes. No non-synonymous public rule delta is proposed.
