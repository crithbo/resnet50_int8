# 整网测试收敛优化 v1 主线裁决

日期：2026-08-05  
主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`  
优化 owner：`019fd276-14c5-7800-94db-87ebfb9ce632`

## 1. 输入证据

- owner report：
  `artifacts/operator_config_validation/r5-whole-network-test-convergence-optimizer-v1/report.json`
- owner report SHA256：
  `8548433dee6f52e96f6d72bc3281d6d13ab0f81218a7683b548c963146bbedb7`
- owner task record SHA256：
  `16efc1165bbdb0b26dc98f81ac3a31b993e458f4eca89f67c9838364c3c59467`
- owner task 状态：`READ_ONLY_AUDIT_COMPLETE_MAINLINE_DECISION_REQUIRED`
- 五个 current package SHA 均与 dispatch 一致；审计未修改包、算子资产、RTL、plan 或规则，
  未执行服务器动作。

## 2. 主线裁决

### 2.1 共享 final-ZIP driver 与机制登记表

`APPROVED_FOR_NEXT_FRESH_SUCCESSORS_IN_SHADOW_MODE`

- 允许优化 owner 在自己的专项范围实现一个共享 final-ZIP 顶层 driver 与按
  `mechanism_id + final_consumer_kind + consumer_signature` 索引的反例登记表。
- 首次迁移对 next fresh successor 与现有 family validator 做一次 shadow compare；结果一致且
  覆盖 actual consumers/uncovered=0 后，才可由对应 owner 请求转为 blocking。
- 当前五个包不因共享工具迁移而重建、替换、hold 或失效。
- 共享 driver 只统一 identity/path/runner/return、actual-consumer HDL/XMR/owner、predicate、
  materialized config 与 result conjunction；算子 numeric/layout 仍由专项 validator 裁决。

### 2.2 Changed-surface applicability

`APPROVED_AS_THE_ONLY_RULE_DRIFT_BLOCKING_ROUTE`

- 本地门统一分类为 `blocking_applicable / receipt_reuse / record_only / not_applicable`。
- hardcoded all-rule-SHA、mutable plan/report format、byte-equal 未变 surface 与 compile=0 后的
  actual/local/cloud identity equality 不得单独阻止 simulation 或 package release。
- production compile、目标 stage、natural terminal、正式 D conjunction、E4/E5、runtime-D absent、
  workload provenance、禁止 host internal tensor replay 与 RTL 授权继续为 blocking。
- 这是现有规则的实现裁决，不发布新的同义公共规则。

### 2.3 当前五包编排与提升策略

`APPROVED_WITH_ROOT_LEASE_AND_RESOURCE_GATES`

- wave 1：native Conv p7→`NDP_copy02`；GAP v40→`NDP_copy01`；serialized Conv v47→
  `NDP_copy03`。
- wave 2：p7 释放 copy02 后运行 QAdd v35；GAP v40 return 被 owner 裁决且没有否定 node0071
  causal prefix 后，才运行 node0071→node0075 v9。
- 若 VCS license、内存或 I/O 不允许三并行，降为双并行，但单 lease 优先级保持
  `p7 → GAP v40 → Conv v47 → QAdd v35 → node71→75 v9`。
- p7 的 c0、GAP/serialized Conv/QAdd 的当前局部边界一旦闭合，下一 fresh successor 必须优先
  提升到该族 natural terminal + 正式 D full target；除非 return 显示新的、无法由现有同包候选矩阵
  区分的首分歧，不再追加同边界 read-only leaf。

## 3. 规则反馈裁决

接受：

`RULE_CONFIRMATION=CURRENT_RULES_SEMANTICALLY_SUFFICIENT_IMPLEMENTATION_AND_ORCHESTRATION_GAPS_ONLY`

接受：

`RULE_DELTA_PROPOSAL=NONE_NO_NONSYNONYMOUS_RULE_GAP_PROVEN`

本轮不修改公共规则。主要改进放在共享 validator 实现、changed-surface applicability 和服务器
编排；不得用新增同义规则继续增加本地检查负担。

## 4. 已确认收益与 claim boundary

- 可量化、完全可避免的历史服务器墙钟下界：`28,951.178526183 s`（约 `8.042 h`），另有
  至少 6 个 simulation 前 package-local HDL/scope/XMR 失败轮次未纳入秒数。
- 三隔离 root 的 compile+simulation 上限估算由串行 `49 h` 降到 `28 h`；这是资源与 timeout
  ceiling 编排估算，不是实际性能承诺。
- 本裁决不改变任何算子数值结论、current package bytes、E3/E4/E5 状态或功能 RTL。

## 5. 下一动作

优化 owner 进入 `SHARED_DRIVER_SHADOW_IMPLEMENTATION`，只创建共享 driver/registry、测试和
机器报告；不得修改 current 五包、算子 owner 资产、plan、公共规则或服务器状态。所有在用算子
owner 接收本裁决，并在 next fresh successor 应用 changed-surface 与 full-target promotion 边界。
