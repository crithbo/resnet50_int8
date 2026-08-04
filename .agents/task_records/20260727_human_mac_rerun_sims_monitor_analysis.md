# Human MAC independent rerun `sims.zip` monitor analysis

## Identity and evidence boundary

- source:
  `C:\Users\15383\xwechat_files\wxid_vwpfpfs4fgyk22_29b7\msg\file\2026-07\sims.zip`
- bytes: 865782
- SHA256: `515b09ca64835e500830f62b275c8c5444a26df7c8ac8fc1883141d127c99026`
- entries: 1014
- uncompressed bytes: 3953893
- archive path audit: PASS; no duplicate or traversal entries.
- top-level evidence: `gexec2slice/`, `gconfig2slice/`, `local/`,
  `bank_frame/`.

This is treated as an independent rerun, not as an extension of the earlier
SIGHUP snapshot. It contains no formal return receipt, package identity gate,
run status, result gate, `sim.log`, or formal D readback. Numeric correctness
therefore remains fail-closed and is not adjudicable from this ZIP.

## Cross-slice dynamic facts

All 28 slices show the same sequence and counts:

1. Each slice received 50 configuration transfers.
2. GEXEC delivered the start command to all 28 slices at 58,838,000 ps.
3. MSE0 issued 128 read requests per slice from 58,854,000 through
   59,234,000 ps.
4. MSE0 returned all 128 responses per slice, ending at 59,269,000 ps.
5. MSE1–MSE3 issued no requests.
6. MSE4 issued exactly two initial write requests per slice at 58,854,000 ps.
7. MSE4 produced zero write-data handshakes on every slice.
8. Bank-frame evidence shows input-side bank0 reads but no post-start output
   writes.

The first dynamic divergence is therefore:

`MSE0 input return complete → no GA/output-buffer data → MSE4 write-data=0`.

This is a replicated deterministic stall, not random server slowness.

## Field-level root-cause diagnosis

The human corrected-v2 JSON enables only the single-stage integer-MAC
producers `PE00`, `PE02`, `PE10`, `PE12`, `PE20`, `PE22`, `PE30`, and `PE32`,
but retains:

```json
"general_array": {
  "outport": {
    "src_id": 1
  }
}
```

The trusted native quant reference uses `src_id=1` because its final producers
are the second-stage odd-column PEs (`PE01`, `PE03`, ...). In contrast, the
repository's single-stage `int32_mac` configurations select `src_id=0`.

The rerun observation—input consumption with zero output/write data on all
slices—is directly consistent with selecting the inactive GA output source.
The proposed minimal correction is:

`general_array.outport.src_id: 1 → 0`.

Classification: `DYNAMIC_SUPPORTED_ROOT_CAUSE` with high confidence, pending
an authorized corrected candidate and confirming rerun.

### Correction after connection-level review

The earlier draft of this record called
`dram_loop_configs.LC2.last_index=1` a secondary structural risk solely because
the trusted native quant reference uses `2`. That transfer was not justified
and is retracted.

`last_index` is a loop-terminal tag level, not an LC identity or the number of
wires/LC_PE hops. In the current topology LC1 and LC2 remain sibling child
loops of LC0, so their local terminal level `1` is internally coherent. The
inserted identity LC_PE branch propagates the terminal carrier and does not
create a new loop nesting level. The reference value `2` is contextual to that
reference's occurrence/lifetime contract and cannot be copied by field-name
equality.

Therefore `LC2.last_index` is not part of the proposed correction.

## Adjudication

- compile/config/start: supported by monitor evidence.
- deterministic stall: confirmed across 28/28 slices.
- first divergence: after MSE0 returns and before first MSE4 write data.
- likely root field: `general_array.outport.src_id`.
- completion: absent.
- formal readback: absent.
- numeric correctness: not adjudicable.
- classification:
  - `FIRST_DYNAMIC_FAILURE`
  - `NO_DYNAMIC_BASELINE`
  - `DETERMINISTIC_28_SLICE_STALL`
  - `DYNAMIC_SUPPORTED_ROOT_CAUSE`

No candidate was modified and no successor package was generated in this
analysis turn.
