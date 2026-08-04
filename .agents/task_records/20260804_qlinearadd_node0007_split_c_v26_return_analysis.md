# QLinearAdd node0007 split-C v26 return analysis

- analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- machine report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-split-c-v26-return-analysis/report.json`
- RETURN_ANALYSIS: `SPLIT_C_TIMEOUT_AT_OP_FP32_ADD`
- LAST_PROVEN_GOOD: `OP_RELOCATION_PAD_COMP_FINISH`
- FIRST_DIVERGENCE: `OP_FP32_ADD_AFTER_FINITE_REQ_RDATA_BEFORE_FIRST_GA_INPUT_ACCEPT`
- HANG_ROOT_CAUSE: `LONG_RUNNING_HANG_AT_FP32_ADD_MSE_PAIRING_UNIQUE_LEAF_NOT_YET_OBSERVED`
- compile/simulation/canonical exits: `0/124/0`; natural terminal false
- ordered scope: 4 starts, only 3 finishes; `op_fp32_add` started and did not finish
- output gate: expected/present/missing/invalid = `28/0/28/0`
- numeric mismatch evaluable: false; mismatch zero is unevaluable.
- E3/E4/E5: false/false/false.

The old observer saw finite request/read-data activity and no first GA input,
but omitted the active MSE1 read stream and used an LC set that does not match
the split-C mapping. It therefore cannot uniquely distinguish MSE0/MSE1 paired
ingress, Buffer0/2 delivery, or GA operand pairing. The C package is consumed
and held; the full split-D package is not promoted.

The missing adjacent sidecar affects only external transport. All internal
identity and exact-set gates passed. Frozen numeric/W3/qparam/tail/workload/
config/golden assets were not recomputed.
