# QLinearAdd node0007 v67 return / v68 storage acceptance

- date: 2026-08-15
- role: `mainline.control`
- family owner: `family.qlinearadd`, owner epoch 2, registry epoch 6

## v67 formal result

- Exact return integrity and execution binding passed; production compile passed and simulation started.
- The exact 4/2 configuration lineage was compiled, but the functional target was not reached.
- `FIRST_DIVERGENCE=PACKAGE_LOCAL_ZERO_DURATION_PRETARGET_SNAPSHOT_FALSE_FREEZE`: each pretarget `$dumpon/$dumpflush/$dumpoff` pulse occurred at one simulation instant, so VCD time remained zero while owner cycles and execution time advanced. Semantic-v5 correctly classified the static pre-planned-dumpoff VCD witness as `SIM_TIME_FREEZE`.
- A separate package runner defect used PID-only ownership and produced 1710 termination actions plus one remaining process record.
- Two consecutive package-local pretarget failures triggered `PACKAGE_BUILD_FAILURE_RULE_AUDIT`. Disposition is `RULE_CONFIRMATION`: no public rule change; the family-local machine exception requires every transport-only pretarget pulse to span a real owner-clock edge and advance VCD time, with PID+start-time ownership and bounded reap.
- Functional 4/2 repair remains dynamically unvalidated; natural terminal, formal-D and E3/E4/E5 were not reached.

Evidence:

- `outputs/qlinearadd_node0007_v67_return_r1786793338560402996_2911236/formal_return_analysis.json`, 11818 bytes, SHA-256 `f699f0cd65b4cbe95062f2cf83e55b477a1f6f420b3a0867736dd8089de9e6a7`
- `outputs/qlinearadd_node0007_v67_return_r1786793338560402996_2911236/PACKAGE_BUILD_FAILURE_RULE_AUDIT.json`, 3445 bytes, SHA-256 `0cfe548a2bdecb34ac1782f166860dd9cc1105ae13e5caaa4bbb56fbe9134140`
- `outputs/qlinearadd_node0007_v67_return_r1786793338560402996_2911236/RULE_AUDIT_DISPOSITION.json`, 1467 bytes, SHA-256 `d3b9482793af33111bc344ce5c1f1ad4ec33460e7c712b2cafaa9933ad0b7c9b`

## v68 package and storage

- Fresh successor: `r5_qadd_n7_tailround_lanephase_v68_cfg42_t2`.
- It preserves the exact validated 4/2 lineage, frozen workload/numeric/golden/functional RTL, 64-signal/41-role cone and 7x4 candidate matrix.
- It changes only the pretarget pulse duration/verification and PID+start-time process ownership/reap surfaces. All staging and independent exact-ZIP gates passed.
- Pending ZIP: `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_qadd_n7_tailround_lanephase_v68_cfg42_t2.zip`, 108709836 bytes, SHA-256 `449e07e917bca6ff406bd94804903375e24d51b74b5c20762dc53e110ff228f4`.
- Release receipt: `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/qlinearadd_node0007/r5_qadd_n7_tailround_lanephase_v68_cfg42_t2/r5_qadd_n7_tailround_lanephase_v68_cfg42_t2.release_receipt.json`, 3571 bytes, SHA-256 `6fb090aa5f713b000a6fc7abbfc348a68cbeea531462d577fd09aefd72801e6f`.
- Storage manager atomically moved consumed v67 to tested and published v68 as the sole QAdd pending package. Corrected global audit passed with counts pending/tested/superseded `3/50/24`.
- Current storage index: 420761 bytes, SHA-256 `a5c33b84c986c08ee51a952b7ef3abe88e43dcb9e899856153d70d608f59e6f3`.
- Native p52 and serialized v97 were verified member-by-member unchanged. No server action occurred.

Unique future command after separate authorization:

`bash r5_qadd_n7_tailround_lanephase_v68_cfg42_t2/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy04`
