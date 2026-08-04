# QLinearAdd node0007 v16 return(2) / D-buffer column-pair adjudication

## RETURN_ANALYSIS

Input:

- return:
  `C:/Users/15383/xwechat_files/wxid_vwpfpfs4fgyk22_29b7/msg/file/2026-08/r5_qadd_n7_dbuf_rule_v16_return (2).zip`
- bytes: 183491
- SHA256:
  `63b9d494ab9360225fe91c70ab96c8297c1eca8189c973ed409778112411a692`
- `(2)` is a local download suffix only.
- Missing adjacent sidecar is non-blocking under the user-attested transport
  policy.
- bound source:
  `artifacts/operator_config_validation/r5-server-test-packages/r5_qadd_n7_dbuf_rule_v16.zip`
- source SHA256:
  `a1a9eb21b43175c63708fc458cb01c6ce055345f7e9296d73e1034f888e73cf5`

Independent integrity result:

- ZIP CRC/path/single exact root: pass
- 20 entries total: 19 returned files plus `RETURN_MANIFEST.json`
- internal exact-set and per-file size/hash receipts: pass
- every returned target is source-manifest allowlisted: pass
- returned package manifest equals source package manifest: pass
- package and installed preflight: pass
- runtime formal D targets absent before execution: pass

Execution result:

- compile: 0
- simulation: 125
- signal: INT
- natural terminal: false
- simulator wall time: 10750.52714275 seconds
- total wall time: 10852.464595016 seconds
- formal D: expected 28, observed 0, missing 28
- mismatch bytes: 0, but not evaluable because all formal D is missing
- E3/E4/E5: false

Machine report:

- `artifacts/operator_config_validation/r5-qlinearadd-node0007-dbuf-rule-v16-return2-analysis/report.json`
- SHA256:
  `22c2205fa1481a64c2c247f4750ff70ad2240a0a28c929ac2721f89ecd068887`

## FIRST_DIVERGENCE

The old screenshot boundary is not the terminal boundary.

- `op_a_dequant`: EXEC 16128244000 ps, COMP 16804297000 ps,
  540843 active cycles.
- `op_b_dequant`: EXEC 16804882000 ps, COMP 17480952000 ps,
  540857 active cycles.
- `op_relocation_pad`: EXEC 17481651000 ps; no COMP; INT at
  21789559375 ps.

The last good boundary is both dequant stages completing and finite stage3
read/address/GA/write-request activity. The first bad boundary is the stage3
Buffer5 → Buffer_AG_Idx_Queue → RD_Buffer_AG → WR_Data_Channel backend:

- base req/rdata/wdata freeze at 748016/139972/597414
- deep addr_enqueue/req_hs/meta/consume/buffer/ga/mse4_idx freeze at
  38/64/38/22/18/56/3
- SG ga_input/ga_output freeze at 56/40
- MSE4 req ch0/ch1 = 2/1
- MSE4 wdata ch0/ch1 = 1/0
- MSE4 outstanding ch0/ch1 = 1/1
- at least three complete 1048576-cycle windows show no downstream progress

`buf5_wr`, `buf5_rd`, and repeated MSE index input2 activity are excluded as
forward progress: they count sustained level/repeated upstream handshakes
without queue write/request/write-data completion.

The returned canonical decision is not execution-authoritative because it
compares samples across stage-local `active_cycles` reset. Raw stage3
qualified downstream counters establish
`LONG_RUNNING_HANG_AT_STAGE3_WRITE_BACKEND_CHAIN`.

## HANG_ROOT_CAUSE

Dynamic evidence alone cannot distinguish the exact first internal queue
register. Static configuration and active RTL widths provide a deterministic
configuration error:

```text
physical Buffer row = 8 banks * 4 bytes = 32 bytes
one write-MSE Buffer read = 16 lanes * 1 byte = 16 bytes
```

The v15/v16 formula incorrectly treats `stream2.buf_spatial_size=16` as a
physical Buffer row size. Its configuration is:

```text
ROW_LC: start=0 end=2 stride=1
COL_LC: start=0 end=4 stride=2
buffer5.end_row=1
```

This means two physical 32-byte rows and overlapping 16-byte read windows
starting at columns 0 and 2. It is not a disjoint 32-byte transaction
partition. The old scalar equality `2 * 16 = 32` hides the physical
over-coverage `2 * 32 = 64` and the wrong column windows.

The minimal local correction for `op_relocation_pad`, `op_tail_mul`, and
`op_tail_round` is:

```text
GROUP2.ROW_LC.end:        2 -> 1
GROUP2.COL_LC.end:        4 -> 32
GROUP2.COL_LC.stride:     2 -> 16
buffer5.buf_end_row_addr: 1 -> 0
```

It produces one Buffer row and two disjoint MSE windows `[0,16)` and
`[16,32)`, matching the repository native FP32 write oracle
`ndp-sim/jsons/decode_add_fp32N_fp32N_fp32N.json`.

## Local materialization

The corrected six-stage graph was rebuilt from empty mapping state.
The known approximately 37-million-request generic enumerator was stopped
after all mapping, double-run bitstream/execplan and execplan validation
artifacts were complete. It was replaced with targeted exact-leaf and
coverage validation because the changed leaves do not affect DRAM loops,
base addresses or dimension strides.

Results:

- only the four authorized leaves change in the three affected final JSONs
- only those three 128-bit bitstreams change
- decoded values are ROW end 1, COL end 32/stride 16, Buffer5 end row 0
- physical mapping is unchanged
- execplan, per-stage commands, SCA, SCA_D, graph base addresses and DRAM
  occurrence are unchanged
- native double run is equal
- numeric/W3/qparams/tail/workload/golden were not recomputed
- functional RTL was not modified

Artifacts:

- local root:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-d-buffer-column-pair-v18`
- targeted report:
  `artifacts/operator_config_validation/r5-qlinearadd-node0007-d-buffer-column-pair-v18/targeted_validation_report.json`
- targeted report SHA256:
  `74eacbfa22554d0b55218bd9f7c9a9e79d6432889b59bd5aca9c9c6c50c7e3fa`
- execplan report SHA256:
  `06619133067e063a88f67228b8abe2a18d4c586f44c28b3a8d0cf1596c280331`
- double-run comparison SHA256:
  `cf341539c123799634ff919280568d5514b5b261536ef8c0e5eeb6a9920fd958`
- `local_candidate_valid=true`
- `errors=[]`

Directed tests: 9/9 pass.

## BLOCKER_DELTA

Closed:

- actual terminal stage is now fixed at `op_relocation_pad`
- old v15/v16 row-only D-buffer supply conclusion is refuted
- a minimal configuration correction is locally materialized and validated

Open:

- current published QAdd rule SHA
  `a1faa3319c267b6d6b7f3e9d2b74c45a52b9a347888dc42de0dfb8599ced5964`
  still mandates the refuted row-only formula under rule
  `CDA-QADD-D-BUFFER-TRANSACTION-SUPPLY-CONSERVATION-001`
- the correct local candidate therefore cannot pass current-rule final-ZIP
  self-audit
- v16 is quarantined by the dynamic stage3 hang
- cadence-only v17 is quarantined because it does not observe or correct the
  newly proven backend contract

## RULE_DELTA_PROPOSAL

Deprecate the row-only equation and its v15 approval. Replace it with:

```text
buffer_row_bytes
  = BUFFER_BANK_NUM * BUFFER_BANK_DATA_NUM

mse_read_bytes
  = MSE_BUF_REQ_NUM * MSE_BUF_REQ_DATA_WIDTH / 8

transaction byte coverage
  = disjoint union of accepted (ROW_LC, COL_LC) read windows
```

Required checks:

1. Every window is within the physical 32-byte Buffer row.
2. Window starts derive from paired ROW/COL tags accepted by
   `Buffer_AG_Idx_Queue`, not from row trip count alone.
3. The union is gap-free, overlap-free and exactly covers the transaction.
4. `buffer5.buf_end_row_addr` equals the maximum physical row used.
5. Validator binds qualified Buffer5 GA write accept/row-bank valid,
   Buffer_AG pair enqueue/dequeue, RD_Buffer_AG request/clear,
   WR_Data_Channel request/prepared-data/accepted-wdata/outstanding.
6. Delete a window, overlap windows, restore col stride 2, add the second
   physical row, or tamper MSE read width must all fail closed.
7. v14/v16 are frozen dynamic counterexamples; v15 approval is withdrawn.

## PACKAGE_RELEASE

`NONE_ACTIVE_RULE_CONTRADICTION`.

No server package was generated. There is no currently runnable QAdd package:

- v16: `QUARANTINED_DYNAMIC_STAGE3_WRITE_BACKEND_HANG`
- v17: `QUARANTINED_CADENCE_ONLY_INSUFFICIENT`
- local v18 configuration candidate:
  `LOCAL_VALIDATED_NOT_PACKAGED_PENDING_QADD_RULE_DELTA`

After the QAdd rule is corrected, the local v18 assets can be packaged under
a fresh identity and subjected to the current server-rule final-ZIP audit.
