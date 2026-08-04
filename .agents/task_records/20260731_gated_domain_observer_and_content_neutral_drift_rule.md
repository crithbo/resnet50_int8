# 门控时钟域 observer 与内容中性规则漂移复验

日期：2026-07-31

## 动态证据

QLinearAdd node0007 v10 formal return 证明：

- compile/elaboration 成功，simulation 运行约 69.96 分钟后由 INT 中断；
- 16 个完整 stall window 内 qualified request/read/write 均为 0，formal D 为 0/28；
- base observer 在 `clk_db` 上持续 heartbeat；
- FIRST_REQUEST_CHAIN 的 qualified counter/打印整体绑定门控 `clk_sg`，并以另一时钟域的
  `active_cycles % period == 0` 作为唯一打印门；
- 当 `clk_sg` 未启动、停止或跨域错过整点时，整段内部诊断静默，因此零条 chain 记录
  不能被升级为配置或 RTL 根因。

## 新规则

发布 `CDA-SERVER-GATED-DOMAIN-COUNTER-UNGATED-SNAPSHOT-001`：

- source-domain qualified counter 可以由目标门控时钟所有；
- snapshot/heartbeat/canonical record 必须由独立、持续存活的 observer clock 发出；
- 同时回收目标门控时钟的 qualified edge count/last-change witness；
- 禁止异域 counter modulo/equality 成为唯一 emitter；
- 必须有 source-domain 前进、source-domain 静止/门控停止、异域 modulo 负控和只读性
  验证。

## 内容中性规则漂移

为避免公共规则文本变化导致所有未运行包无意义重建，修订
`CDA-SERVER-FINAL-ZIP-RULE-SELF-AUDIT-001`：

- 新规则要求改变 package payload、runner/runtime、manifest 机器合同、负控或 return
  schema 时，必须 fresh identity；
- 新规则明确不适用，或 final ZIP 已逐项满足且无需改变任何包字节/行为/验证资产时，
  允许发布 `RULE_DRIFT_CONTENT_NEUTRAL_REVALIDATION_PASS` 包外收据并保留 ZIP 身份；
- 包外收据不能修复实际缺失字段、验证器、负控或 runner 行为。

## 收据

- `.agents/rules/服务器测试包生成规则.md`
  SHA-256=`507ca9090c20c081baaf9604e318c58b9984fba8765d39fdf53b7cce90e6be8d`
- `.agents/plan.md`
  mutable provenance SHA-256=`c346162d81c426e28b4b6b6b211e92066b95dd02d56b087ead5bfda56e44a1c8`
- `git diff --check`：exit 0

## 边界

本轮未修改功能 RTL、算子配置、workload、golden 或服务器文件，未上传或运行服务器。
