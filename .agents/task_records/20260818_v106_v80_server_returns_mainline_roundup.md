# 2026-08-18 v106 / v80 服务器返回主线路汇总

- mainline: `44764e6e-52db-4219-bf61-51a72507063e`
- server actions by mainline: none（测试由用户远程完成）
- family analyses: `family.qlinearadd` 与 `family.conv.serialized` 分别完成

## QLinearAdd v80 return

- return 已从 Downloads 暂存：`outputs/qlinearadd_node0007_v80_return_r1787026013023508017_4080375/return.zip`
- 分析结论：`DIAGNOSTIC_EVIDENCE_INCOMPLETE / PARTIAL_EXECUTION_RETURN`
- compile/simulation started，但未进入 4/2 target；qualified target progress=0/18816。
- FIRST_DIVERGENCE：实际 wall=3600 默认值，而不是授权的 15000；supervisor 收尾阶段 `Set changed size during iteration` 崩溃。
- natural terminal/Formal-D/E4/E5 均不成立；pending v80 包未改动。
- family 报告：
  - `outputs/qlinearadd_node0007_v80_return_r1787026013023508017_4080375/formal_return_analysis.json`
  - `outputs/qlinearadd_node0007_v80_return_r1787026013023508017_4080375/formal_mainline_receipt.json`

## Serialized Conv v106 return

- 服务器无 canonical return ZIP；`guard_exit=122` 是 operational guard 哨兵。
- 本地判定：`RETURN_INFRASTRUCTURE_GUARD_FAILURE_BEFORE_CANONICAL_PUBLICATION`；tuple10 `UNRESOLVED`。
- `MEMORY_TUPLE_ACTIVITY_PRESENT` 只能证明 tuple 活动存在，不等于 tuple10 达成。
- 需用户从服务器取回证据，优先级清单：
  `outputs/conv_node0004_v106b_return_recovery/server_recovery_checklist.md`
- family 报告：
  `outputs/conv_node0004_v106b_return_recovery/guard_failure_local_analysis.json`

## claim boundary

主线仅路由、登记与汇报；两个 family owner 完成本族分析。未重建/补丁任何 package，未上传/运行服务器，未取 lease，未改 RTL/config/numeric/workload。
