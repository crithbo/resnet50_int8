# QLinearAdd node0007 split-A v26 return analysis

- analysis owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- machine report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-split-a-v26-return-analysis/report.json`
- RETURN_ANALYSIS: `SPLIT_A_DUAL_DEQUANT_STAGE_LOCAL_PASS`
- LAST_PROVEN_GOOD: `OP_B_DEQUANT_COMP_FINISH_WITH_28_STRUCTURAL_READBACKS`
- FIRST_DIVERGENCE: `NONE_WITHIN_SPLIT_A_SCOPE`
- natural terminal: true; compile/simulation/canonical exits: `0/0/0`
- ordered scope: `op_a_dequant -> op_b_dequant`, 2 starts and 2 finishes
- structural outputs: expected/present/missing/invalid = `28/28/0/0`
- numeric mismatch evaluable: false. No independent expected payload is bound, so reported mismatch zero is not a numeric pass.
- E3/E4/E5: false/false/false; the claim is split-A stage-local only.
- numeric/W3/qparam/tail/workload/config/golden recomputation: none.

The missing adjacent sidecar is accepted only for external transport under the
user-attested no-sidecar rule. Internal CRC, root/path safety, exact allowlist,
per-file receipts and frozen source identity all passed.
