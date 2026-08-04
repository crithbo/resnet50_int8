# QLinearAdd node0007 split-C ingress v28 return analysis

- owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- return SHA: `e42e6159912e111e4b04293f7682de2078fd3459a921203f5a44ad7b1aebd417`
- source v28 SHA: `f552f2a24ae62b1e4e11c1a69ddff6663ffa2ea4fa177b923d0298c15a739f50`
- machine report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-split-c-ingress-v28-return-analysis/report.json`

Internal CRC/root/path safety, exact allowlist, per-file receipts, returned
manifest, source binding and both preflights passed. The absent external
sidecar was accepted only under the user-attested transport rule.

Execution:

- compile/canonical exit `0/0`
- simulation `125`, signal `INT`, no natural terminal
- host/simulation wall time about `7895.916 / 7892.361` seconds
- only two stage starts and one finish were observed
- `op_a_dequant` completed; `op_b_dequant` was active when interrupted
- relocation and target FP32-add were not reached
- 28/28 split-C outputs are missing; mismatch is unevaluable
- E3/E4/E5 are false

Adjudication:

- `LAST_PROVEN_GOOD=OP_A_DEQUANT_COMP_FINISH`
- `FIRST_DIVERGENCE=OP_B_DEQUANT_MANUAL_INTERRUPT_BEFORE_COMP_FINISH`
- `HANG_ROOT_CAUSE=TARGET_FP32_HANG_NOT_REACHED`

The returned canonical `FP32 first output` record is not consumable as target
stage evidence. Its only ingress snapshot has `stage_seq=1` and accumulated
early-dequant counters. The package-local cause is exact: the v19 ingress
observer updated `qadd_ingress_exec_start_d` only while `return_obs_active`;
the value remained high across the inactive inter-stage gap, so later stage
edges did not increment/reset the observer stage sequence.

The successor must retain the shortest legal cumulative prefix because no
byte-bound hardware A/B/relocation checkpoint chain is available for replay.
It must fix stage tracking/reset, count only exact stage 4, and cover the full
candidate matrix from MSE0/MSE1 index queues through Buffer0/2 and GA pairing.
No numeric/W3/qparam/tail/workload/config/golden was recomputed.
