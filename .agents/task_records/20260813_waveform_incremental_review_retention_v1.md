# 大波形增量审查与三版本保留规则实现（2026-08-13）

## 目标

把大体积 FSDB/VPD return 的分析改为可续接事务：按 exact signal set × time window × candidate
查询，每完成一段立即落不可变 chunk，并原子更新小型 current index；确认唯一根因后停止无关扫描。
同一 family/test-track 本地最多保留三份重型 raw-waveform return，但只有正式收集完整、审查终态、
family/mainline 双消费且不是 CURRENT/BASELINE/CAUSAL 锚点的旧 return 才可淘汰。

## 实现

- 新规则：`CDA-SERVER-RETURN-WAVEFORM-INCREMENTAL-REVIEW-RETENTION-001`。
- 共享入口：`tools/server_waveform_incremental_review_retention.py`。
- 机器合同：`schemas/server_waveform_incremental_review_v1.schema.json`、
  `schemas/server_waveform_return_retention_v1.schema.json`、
  `contracts/server_waveform_incremental_review_retention_dispatch_v1.json`。
- 正控覆盖 immutable chunk、候选全量 disposition、唯一根因停止、三锚点 + 一个安全旧版本、
  deterministic core-only ZIP 与精确单文件 unlink。
- 负控覆盖 identity/revision 漂移、采样或截断、候选静默丢失、terminal 后追加、未双消费、
  全受保护无安全候选、storage-root 逃逸和目标字节漂移。

## 安全边界

完整、无限长、无采样/截断的波形回传仍是 collection 阶段硬门；三版本策略只在
post-adjudication 阶段生效。淘汰前派生并验证保留全部非波形成员的 core-only return，写明 raw
波形之后本地不可恢复；不删除目录、服务器包、报告、task record 或服务器状态。本任务未删除任何
真实 return。

## 验证与收据

机器报告：`outputs/whole_network_waveform_incremental_review_retention_v1/report.json`。
聚焦两套新工具 28/28 PASS；共享相关回归 119/119 PASS，环境性 skip 1；py_compile、JSON parse、
diff-check PASS。

`RULE_DELTA_PROPOSAL=CDA-SERVER-RETURN-WAVEFORM-INCREMENTAL-REVIEW-RETENTION-001`，属于非同义
生命周期增量：原规则禁止按大小丢弃 collection 证据，本规则仅授权双消费后的精确
post-adjudication retention。family 保留信号解释与根因裁决权。
