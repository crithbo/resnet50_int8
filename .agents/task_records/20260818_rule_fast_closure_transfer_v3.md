# 2026-08-18 构包快速闭环、规则精简与可转交性 v3

状态：`IMPLEMENTED_AND_LOCALLY_VALIDATED`。

## 裁决

本轮先通过 `rule-maintenance-incident-adjudication-v1`。主因不是缺少更多事故条款，而是：

1. patch-first/reuse 的顶部语义被后文 all-SHA/all-first-fresh 口径抵消；
2. build gate registry 仍为 shadow-only，没有唯一正式 release 入口；
3. handoff 回归只验证临时 fixture，current owner registry 缺失/plan-storage 漂移仍可被忽略。

分类为 `RULE_SEMANTIC_ERROR`，采用替换、合并、删除、归档，不追加同义 ID。

## 已完成

- `server_package_pipeline.py` 现在有正式 `prepare` + `admit`：廉价错误一次聚合，最终 ZIP 一次 CRC/
  聚合 gate admission；blocking 只允许 server start、actual input、state safety、return。
- unrun candidate patch-first，未变 PASS receipt 复用；transport SHA/bytes 与 validator digest 漂移为
  cache/provenance，不再单独阻断。
- current owner registry 支持 path-only 日常指针；完整 digest 仍只用于真正的 handoff CAS。
- 新增 current-disk takeover gate，实际读取 canonical plan/owner/storage；当前识别 serialized v106、
  QAdd v80 两个 pending，检查 PASS。
- `agent.md` 明确角色读取矩阵和 Skill 触发；Skill 强制持久 family owner、prepare/admit、patch-first、
  future bounded TB-VCD default，且不改变 current ready package mode。
- 活动 server/session/optimizer/router 规则大幅压缩，旧 router/session/optimizer 原文进入统一 history。
  活动规则仍 14 份，定义 103 个，重复 0。

## 验证

- related focused tests：`123/123 PASS`；
- active-rule audit：`PASS`，14 active、103 unique definitions、0 duplicate；
- current-disk takeover：`PASS`；
- Python compile、JSON parse、targeted diff-check：`PASS`。

机器报告：`outputs/rule_fast_closure_transfer_v3/report.json`。

## 边界

未修改 `.agents/plan.md`，未构建/修补/hold/rotate current package，未执行 storage/server 动作，未改
functional RTL、config、numeric、workload 或 golden。current mainline 窄幅同步本 exact set 后才成为
canonical next-fresh workflow；现有 ready package 不因本轮规则变化追溯重建。
