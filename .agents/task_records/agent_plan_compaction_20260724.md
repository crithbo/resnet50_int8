# agent/plan 活动入口精简记录

日期：2026-07-24

## 目标与边界

按“唯一信息归属、当前与历史分离”的规则精简 `.agents/agent.md` 和
`.agents/plan.md`：

- `agent.md` 只保留稳定项目边界；
- `plan.md` 只保留活动任务、blocker、顺序和交接；
- 版本过程、旧命令、包身份、已完成步骤和被取代状态迁入 history；
- 不删除有效信息，不改功能 RTL，不生成服务器包。

## 历史快照

| 原活动文件 | 历史快照 | 行数 | bytes | SHA-256 |
|---|---|---:|---:|---|
| `.agents/agent.md` | `.agents/history/agent_pre_active_compaction_20260724.md` | 112 | 5,862 | `27f2e3a567d39e01abe176289bcffb3bc28fd6a4c39ffb0dd17c79784154b966` |
| `.agents/plan.md` | `.agents/history/plan_pre_active_compaction_20260724.md` | 2,008 | 153,778 | `d4bc08ec44017a1d438961391577fdb74584b6b203daa66978706b07d95d515b` |

迁移前后快照逐字节哈希相同。历史文件不得作为新生成命令或当前状态来源。

## 当前活动文件

| 文件 | 精简前 | 精简后 | 当前 SHA-256 |
|---|---:|---:|---|
| `.agents/agent.md` | 112 行 / 5,862 B | 64 行 / 3,439 B | `367f4f4260246d40531d83cc6d24fe94946cb05bce6fbef18c428f05b634c083` |
| `.agents/plan.md` | 2,008 行 / 153,778 B | 126 行 / 6,993 B | `45e192e1e5a046a4ba5409535dcc90a198441bca6da21610606e8b34ebd8bd96` |

合计由 2,120 行降至 190 行，减少 1,930 行；完整旧文仍在 history。

Windows 当前会话中的活动文档监视阻止 `apply_patch` 直接 unlink 两个构造中间文件；
它们已压缩为 3 行、无规则内容的非活动跳转占位：
`.agents/agent.compacted.md` 与 `.agents/plan.compacted.md`。生成入口和读取索引均不
引用它们，测试强制其不得重新承载活动内容。

## 唯一归属

- 生成前读取矩阵、E0～E5、回归分类：`生成前必读索引.md`；
- 配置完整重建和 provenance：`算子配置规则.md`；
- 服务器单命令/回传：`服务器测试包生成规则.md`；
- 稳定事实优先级与不可修改边界：`agent.md`；
- 当前 Dequant 任务、冻结路线与顺序：`plan.md`；
- 逐版本证据、旧命令和已结束路线：history/task record。

## 当前状态校正

活动 plan 只保留以下可派工事实：

1. 软件公式 78/78、typed request 133/133；
2. 正式 target config 0/133，E4=0，E5=0；
3. DequantizeLinear 本地 E2 集成是唯一活动计算路线；
4. GAP `int32_mac`、GAP repair 和功能 RTL patch 服务器路线冻结；
5. 其余 family 只以 blocker 和重新启动条件存在，不带旧候选命令。

Dequant 的 E2 v3 是规则维护任务进行中的报告；在 backend/总账接入和最终 task record
完成前，活动 plan 保持 `IN_PROGRESS_LOCAL_E2_INTEGRATION`、
`candidate_release=false`、`server_package_allowed=false`。

## 验证

```text
python -m unittest tests.test_agent_plan_compaction -v
```

验证覆盖活动文件行数、禁止历史版本身份、唯一 E0～E5 定义、当前状态字段、历史快照
哈希和历史索引。
