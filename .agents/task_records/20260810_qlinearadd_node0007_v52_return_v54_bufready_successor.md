# QLinearAdd node0007 v52 return → v54 Buffer5-read-ready successor

Owner `019fa2c0-b647-7a91-93bf-d21a173487e3`; return target
`019fbec2-fe93-7e03-9314-cff6f222f33d`.

## RETURN_ANALYSIS

Formal return:
`C:/Users/15383/Downloads/r5_qadd_n7_tailround_queueflow_v52_r1786363786427884298_586990_return.zip`,
bytes `450246`, SHA256
`595f31705a463f83c6b3af1a0920d2dcca8a3d694050d32b4bc865103dc20493`.
The missing adjacent sidecar is covered only by user-attested transport. ZIP CRC,
single safe root, duplicate/symlink gate, RETURN_MANIFEST per-file size/SHA,
allowlist exact-set and byte-exact v52 source manifest binding all pass.

Compile is 0; simulation is 124 after two hours; signal is `NONE`. There is one
ordered `op_tail_round` start and no finish. Fifteen complete qualified windows
are frozen. All 28 D targets are missing, therefore mismatch zero is unevaluable;
natural terminal and E3/E4/E5 are false.

- LAST_PROVEN_GOOD:
  `OP_TAIL_ROUND_BUFFER_AG_PAIR_DEQUEUE_AND_RD_BUFFER_AG_VALID_QUEUE_FILL`
- FIRST_DIVERGENCE:
  `RD_BUFFER_AG_VALID_REQUEST_WITH_WR_DATA_CHANNEL_READY_BUT_BUF2MSE_RREQ_READY_LOW`
- direct equation:
  `buf_ag_ob_rd_en = buf2mse_rreq_ready && wr_data_chl_ready`
- final dynamic state: RDAG count 2/full, request valid `0xffff`,
  `wr_data_chl_ready=1`, `buf2mse_rreq_ready=0`.

The v52 canonical failure is independently a package defect: event `%m` from two
procedural scopes produced a false multiple-instance set. Raw qualified evidence
remains consumable.

Machine report:
`artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-queueflow-v52-return-analysis/report.json`,
bytes `23508`, SHA256
`0f51dedb517da9f84117efda60c6faacf4022d24421668b27505013da8a3ce7e`.

## Continuous closure and release

The first v53 candidate was stopped before publication because its canonical
binding did not require `EXEC_START.stage==1`. It is quarantined at SHA256
`9f8f3a1d624335e536448c817c7ab8a1cc1c0be76994e7ea66783b62ca997c87`.

Fresh v54 changes only identity, stable selected-slice ownership and the bounded
Buffer5 observer/parser. Workload, COL4/stride2 configuration, bitstream,
execplan, SCA semantics, FP32 diagnostic input, UINT8 golden, numeric/W3/qparams/
tail, two-hour timeout and functional RTL are frozen. It observes:

1. MSE write ping-pong selection and both physical ready ports;
2. Buffer5 MRM read request valid/rw/row/strobe;
3. per-bank ready and four-lane valid bits at the requested row;
4. qualified Buffer5 writes, clears and accepted reads.

The exact final ZIP passes deterministic double build, clean-extract inventory,
manifest exact-set, current immutable rule receipts, package-local XMR/source
closure, parser stage/slice binding, predicate traces, three negative controls,
runtime preflight and shared install-only runtime validation. Negative exits are
all nonzero for declaration deletion, actual consumer misspell and qualified
update deletion.

- package ID: `r5_qadd_n7_tailround_bufready_v54`
- ZIP bytes/SHA256: `70649173` /
  `e0b4cc00cbd29716c3399b5fcb95265ae10a1d2d67765466a023312b8cde3f26`
- local final audit bytes/SHA256: `24268` /
  `9be02ce0c2e89dd3bd70db553d50540559bdd70cc7ec0a6498d4c7ef68963271`
- shared validation bytes/SHA256: `19242` /
  `41c004b9c4669bb0d727fe763594a414f29c3afef50b78295d3a61ad0aa483ac`
- release report bytes/SHA256: `4129` /
  `7e42d7abd927d33f647ca178863d84048d9735bab9e3b1fa90d9a7d84ce45c41`
- first-fresh epoch reuse: `first_fresh_after_change=false`, prior PASS
  `ed8e31a08cb76f0b8994ebaf29247dd1f0b603f0861acf710afcbb5219e4e976`.

After storage rotation the unique QAdd pickup is
`artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_bufready_v54.zip`.
The consumed v52 source is retained under `tested`; concurrent Conv pending ZIPs
are untouched.

Server command after mainline selects the leased NDP root:

```bash
cd /home/panqs/ndp/r5_qadd_n7_tailround_bufready_v54 && bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy0x
```

Expected return:
`/home/panqs/ndp/simresult/r5_qadd_n7_tailround_bufready_v54_<execution>_return.zip`.

## Rule feedback

`RULE_CONFIRMATION`: the current return integrity, hang-first, qualified-event,
formal-result conjunction, diagnostic-stimulus boundary, continuous closure,
changed-surface applicability, predicate-trace, package-local HDL, install-only
runtime, fixed publication and storage rotation rules are sufficient. No
non-synonymous rule delta is proposed.

