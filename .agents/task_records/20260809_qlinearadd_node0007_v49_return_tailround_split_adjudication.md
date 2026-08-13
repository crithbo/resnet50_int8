# QLinearAdd node0007 v49 return / tail-round split adjudication

- analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- return: `C:/Users/15383/Downloads/r5_qadd_n7_tailround_flow_v49_r1786169131743745543_3998251_return.zip`
- return SHA256: `8bf7864bd7fc5ee8e4ac5509a4e8b1e37705e3aeea9c54e419faeb51e7a6bdd3`
- machine report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-flow-v49-return-analysis/report.json`
- machine report SHA256: `6673ad508cd7c7799ec525adabeadd4c428f18f9237f2fb2a64a50849a610b2d`
- numeric/W3/qparams/tail/workload/golden repeated: `false`
- server action: `false`

## Adjudication

The logical three-part QLinearAdd composite is:

1. A/B input-domain alignment and dequantization: physical `op_a_dequant`,
   `op_b_dequant`, and non-computational `op_relocation_pad` -- completed.
2. W3-ordered FP32 residual sum: physical `op_fp32_add` -- completed.
3. exact UINT8 output tail: physical `op_tail_mul` completed; the final physical
   `op_tail_round` did not complete.

The last proven good boundary is the first 16-byte prepared-data acceptance in
`op_tail_round`.  The first divergence is the second COL occurrence aliasing the
same 16-byte Buffer5 set.  The final JSON retained the native interleaved spatial
offsets but generalized `GROUP2.COL_LC end/stride` from native `4/2` to `32/16`.
Modulo the 32-byte row, bases 0 and 16 select the same set, so their union has
only 16 bytes; bases 0 and 2 select complementary sets and exactly cover bytes
0 through 31.  The return independently agrees: two write requests, one
prepared beat, saturated Buffer_AG/RDAG/WR queues, and 46 complete qualified
stall windows.

There is a separate package-parser defect: Python `int(value, 0)` rejects the
observer's zero-padded decimal token `02`.  This did not create the DUT stall.

## Split decision

An isolated final-stage diagnostic is legal and useful.  It must be labelled
`DIAGNOSTIC_STIMULUS_NOT_PRODUCER_EVIDENCE` if its `tail_mul` boundary tensor is
generated from the frozen host oracle rather than recovered byte-for-byte from
a naturally completed hardware producer.  Such a package may prove the local
`tail_round` transaction/terminal/readback behavior but cannot claim the
upstream producer, cross-stage barrier/lifetime, the six-stage chain, or E3/E4/E5.
After that quick local-stage check, the same corrected config must still pass the
six-stage natural-terminal and exact 28-D conjunction.

The changed causal slice has been materialized locally without repeating the
frozen numeric analysis or workload:

- build receipt: `artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-colfix-v50-rebuild/build_receipt.json`
  (`9470c1afcfe04978f1c66e234711b93065147a1be34e74497eee75f40bf1407b`)
- validation report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-colfix-v50-rebuild/validation_report.json`
  (`cf581aba9171c5d3f3f266f7af28a7da69044e420e0e9166d5acef43e97922f2`)
- result: valid, errors=0; fresh `tail_round` mapping and fresh six-stage
  execplan validation pass; exact 28 final-D entries remain present.
- changed leaves: only `GROUP2.COL_LC.end 32 -> 4` and
  `GROUP2.COL_LC.stride 16 -> 2` in `op_tail_round`.
- the initially launched full six-stage request-address enumeration was stopped
  after it was identified as unchanged-surface repetition.  The direct changed
  Buffer5 transaction window and seven negative controls were used instead;
  no DRAM base/address leaf changed.

## Blocker delta and rule feedback

- closed: `B_QADD_V49_TAILROUND_FIRST_BLOCKING_EDGE_NOT_UNIQUE`
- opened: `B_QADD_TAILROUND_INTERLEAVED_COL_ALIAS`
- opened: `B_QADD_V49_CANONICAL_DECIMAL_PARSE`
- rule delta proposal: transaction supply must be derived from each COL base plus
  the complete stream spatial-stride vector modulo physical row width.  A COL
  stride of 2 is not intrinsically invalid; validity depends on the stream layout.
