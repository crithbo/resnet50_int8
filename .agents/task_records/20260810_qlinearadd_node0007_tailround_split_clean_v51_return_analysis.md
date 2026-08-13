# QLinearAdd node0007 v51 formal return analysis

- owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- formal return: `C:/Users/15383/Downloads/r5_qadd_n7_tailround_split_clean_v51_r1786345773466170577_479267_return.zip`
- return bytes/SHA256: `448574` / `6cc79a5aede9a8ebbed01f3cc2a03596e6d3b320f4661ab3fb68abf4ee0f6fb7`
- source bytes/SHA256: `70643824` / `cf499102675dda4501e4e0c2e9cde1142985b3aca6b94a46edf7afb45f668141`
- machine report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-split-clean-v51-return-analysis/report.json`
- machine report bytes/SHA256: `22267` / `e7cee01c594256e272c522b00b63e7cd896c2658728bcba12b7dd3313eaa634e`

## Adjudication

The return is internally valid and source/execution bound. Compile succeeded, simulation timed out after about 2.03 hours with `signal=NONE`, no natural terminal, and 28/28 stage-local D targets missing. `mismatch=0` is unevaluable.

`LAST_PROVEN_GOOD=OP_TAIL_ROUND_BUFFER5_FIRST_ACCEPTED_WRITE_AND_MSE4_CH0_FIRST_WDATA`.

`FIRST_DIVERGENCE=AFTER_BUFFER_AG_AND_RDAG_FINITE_ENQUEUE_BEFORE_RDAG_DEQUEUE_READ_REQUEST_AND_SECOND_CHANNEL_PREPARED_WDATA`.

At least 16 complete qualified stall windows were frozen. The return closes the prior “COL4/stride2 untested” blocker but does not uniquely distinguish Buffer_AG pair dequeue, RD_Buffer_AG eligibility/read request, WR prepared second beat, or channel-1 delivery. Host-precomputed FP32 diagnostic stimulus remains explicitly non-producer evidence.

No numeric/W3/qparam/tail/golden/workload/config analysis was repeated. No server action or RTL change occurred.
