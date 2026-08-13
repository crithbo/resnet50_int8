# serialized Conv node0004 v71 return → v72 token-origin accept successor

- owner: `019fa2c1-17df-7122-bcbd-a727aaf173f5`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- status: `PACKAGE_READY_NOT_RUN`
- package class: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX`

## RETURN_ANALYSIS

The formal v71 return is bound to execution `r1786206230306714342_4179619`, return SHA256
`5d424c2865d9b98f183e85794a9bbf89f827efcc79e2fc81ee4d9cfb70202340`, and source v71 SHA256
`8cab1c7762496cf25ecde9057388d88c428711a2e52dc5a1e8e610a66840b452`. ZIP CRC/root/path,
RETURN_MANIFEST exact-set/allowlist/per-file receipts, source/install/reset, observer feature, actual
compile and simulation binding all pass. Compile and run exit `0`, signal is `NONE`.

The DUT did not reach natural terminal and returned no formal D (`0/320`, missing `320`, mismatch
`0`); all-missing is not a numeric pass. E3/E4/E5 remain false.

## LPG / FD / root cause

- LPG: `V70_DESCRIPTOR_18_AND_PREPARED_GROUP_18_JOIN_DRAIN_WITH_BUFFER_POP_21`.
- FD: `V71_TOKEN_ORIGIN_RECORD_12_COUNTS_BUFFER_QUEUE_WRITE_ATTEMPT_WHILE_BUF_BP_IS_ZERO`.
- root: `UNRESOLVED_DUE_TO_PACKAGE_LOCAL_DIAGNOSTIC_EVENT_QUALIFICATION_FAILURE`.
- class: `PACKAGE_LOCAL_OBSERVER_DEFECT`.

The v71 observer used `buf_ag_idx_queue_wr_en = buf_all_idx_matched && mse_enable` as an accepted
FIFO write. RTL exposes that this is only a write attempt; acceptance additionally requires
`!buf_ag_idx_queue_full`. At record 12/time 2446119000, v71 reports `buf_wr_ev=1` while
`buf_bp=0`. It then spends the 128-record budget on the held attempt level and reports 126 Buffer
writes. Those counts cannot distinguish config from RTL token ownership, so no DUT/config/numeric
failure is claimed.

## v72 successor

v72 changes only the diagnostic qualifier and fresh identity:

```text
mem_write_accept = mem_ag_idx_queue_wr_en && !mem_ag_idx_queue_full
buf_write_accept = buf_ag_idx_queue_wr_en && !buf_ag_idx_queue_full
```

It separately emits write-attempt and full state, which never advances progress. Pop remains
`rd_en && !empty`; descriptor remains `valid && ready`; all event classes remain present in the same
sample. Numeric/W3/qparams/tail/workload/config/golden/timeout/backpressure and functional RTL are
frozen.

Final ZIP audit passes with errors `0`: deterministic double build; exact ZIP/manifest/sidecar;
install-only six-flow harness and 86/86 SCA opens; runner stderr/finalizer controls; focused HDL
positive plus missing-declaration and actual-consumer-typo negatives; old attempt-only predicate
negative; stable-full zero-progress; multiclass no-loss; return contract. The shadow build profile is
contract-valid with zero errors and is nonblocking.

Pickup:
`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v72_token_origin_accept_diag.zip`

- bytes: `5184519`
- SHA256: `1cd8c9f55f8120e0c40599c54f6f385fbf159957bf74eafa0055c0ad4feed585`
- command: `bash r5_n4_hw_v72_token_origin_accept_diag/PREPARE_AND_RUN.sh /absolute/path/to/NDP_copy0x`
- expected return: `/home/panqs/ndp/simresult/r5_n4_hw_v72_token_origin_accept_diag_<return_tag>_return.zip`

Storage rotation moved v71 to `tested` and leaves exactly one serialized-Conv ZIP pending. No other
family package was moved or overwritten.

## Blocker delta and rule feedback

Closed: `B_CONV_NODE0004_V71_TOKEN_ORIGIN_WRITE_ATTEMPT_MISCOUNT`.

Open: Memory-vs-Buffer combined token origin, natural terminal, and formal D 320. The historical
outbuffer occupancy blocker remains `INVALIDATED_NOT_RTL_BUG`.

`RULE_CONFIRMATION`: existing event-qualification, predicate-trace, multiclass-no-loss and final-ZIP
self-audit rules already cover this escape. The defect was v71 validator noncompliance, not an absent
public rule; no non-synonymous rule delta is proposed.
