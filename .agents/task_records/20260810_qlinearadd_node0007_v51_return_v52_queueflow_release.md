# QLinearAdd node0007 v51 return to v52 continuous closure

- owner: `019fa2c0-b647-7a91-93bf-d21a173487e3`
- return target: `019fbec2-fe93-7e03-9314-cff6f222f33d`
- epoch ACK: `20260810-first-fresh-extra-audit-v1`
- first fresh after change: `true`
- package status: `PACKAGE_READY_NOT_RUN`
- claim: `DIAGNOSTIC_ONLY_NOT_FUNCTIONAL_FIX / E2_LOCAL_ONLY`

## Successor

- pickup: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_queueflow_v52.zip`
- bytes: `70648125`
- SHA256: `7ed0e6e84d32900b015f70091b7b8bbefae074a63f019d75026f8b25bf9f52d0`
- command: `cd /home/panqs/ndp/r5_qadd_n7_tailround_queueflow_v52 && bash PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy05`
- expected return: `/home/panqs/ndp/simresult/r5_qadd_n7_tailround_queueflow_v52_<execution>_return.zip`

v52 freezes v51's isolated `op_tail_round`, COL4/stride2 config, 28 host diagnostic FP32 inputs, 28 golden outputs, two-hour timeout, numeric/W3/qparams/tail and functional RTL. It only adds a bounded queue-flow observer/parser that pairwise distinguishes:

1. Buffer_AG paired ROW/COL enqueue/dequeue;
2. RD_Buffer_AG enqueue/dequeue/read-request eligibility;
3. WR_Data_Channel second prepared beat;
4. channel-1 output enqueue/request/accepted wdata.

Qualified events stay on `clk_sg`; `clk_db` emits state snapshots only. The final observer enforces a hard 96-event budget per exact instance, includes `%m` ownership, and the canonical parser fails closed for multi-instance mixing or over-budget logs. Host-precomputed boundary stimulus is not producer evidence.

## Independent first-fresh audit

- cheap aggregate invocations: `1`
- deterministic double build: `PASS`
- surviving final ZIP count: `1`
- independent clean-extract audit: `PASS`, errors `0`
- candidate coverage: `4/4`, uncovered `0`
- mandatory validator command exit: `0`
- validator report SHA256: `ed8e31a08cb76f0b8994ebaf29247dd1f0b603f0861acf710afcbb5219e4e976`
- final ZIP self-audit: `PASS`, errors `0`, SHA256 `2c0ed3b144e042fd998dbe994a185534613ab34e82327ab31753157dece77ce8`

The first audit attempt failed before content adjudication because the Windows clean-extract prefix exceeded the local path limit. A second attempt found two audit-fixture defects: the fixture's own `py_compile` polluted the extracted exact-set, and it queried `return_contract` instead of the manifest's `return_allowlist`. Both failed trees were preserved. The corrected fixture re-extracted the same exact ZIP into a short, clean namespace and passed with zero errors; neither issue required a package byte change.

## Receipts

- v51 analysis report: `e7cee01c594256e272c522b00b63e7cd896c2658728bcba12b7dd3313eaa634e`
- build receipt: `6499655bbf930c3a7a7b270a690d54d3d1b0818fb766c26a4c5f0b2ddd538c52`
- family validation: `e9c8488d3e506c014c42b0c1469a69178b88d06de7af20f6f4f6ae627f6aee6c`
- shared runtime layout: `b492f1102f2a928fc14b063e7b72330907842c68a1fe454a55d03369d90fe9c6`
- first-fresh contract: `f4863b2d57284fd0167719992309b7c4ad16d94f87cc7a69bae020ca37c33c52`
- release report: `artifacts/operator_config_validation/r5-qlinearadd-node0007-tailround-queueflow-v52-package/release_report.json`, bytes `4113`, SHA256 `2285e1a98f874840db68f18bd1f32138507dacc0595500b0fe85a37866023c83`

## Rule confirmation

The current long-run hang-first, qualified-event, feature end-to-end, continuous-closure, storage-rotation and first-fresh independent-audit rules were sufficient and causally useful. No new synonymous rule is proposed.

No server/upload/run/lease action occurred; no numeric/workload/golden analysis was repeated; no plan/public-rule/functional-RTL/other-family asset was modified.
