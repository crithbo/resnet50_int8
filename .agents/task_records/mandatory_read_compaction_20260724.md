# 生成前必读资料精简记录

日期：2026-07-24

## 目标

把“生成前必须完整阅读”从多文件重复清单改为单一路由入口；公共文件只保留稳定有效
约束，硬件字段按实际触发单元条件阅读。删除的是重复段落、版本身份和已结束过程，不删除
规则 ID、公式、反例、provenance、停止条件或 E0～E5 发布门。

本轮不生成/运行服务器包，不修改功能 RTL；GAP int32_mac v1～v5 和 repair_v9 保持
冻结只读。

## 结构变化

新增：

- `.agents/rules/生成前必读索引.md`：唯一公共读取路由、条件选择、读取收据和
  no-dynamic-baseline 分类；
- `.agents/rules/NDP硬件字段语义.md`：LC、LC_PE、MSE、padding/tailing、Buffer、SA、
  GA、N2N 和跨单元覆盖的条件附录；
- `tests/test_mandatory_read_compaction.py`：检查路由、归档、有效反例、重复标题和公共
  文件大小上限。

重写为当前有效入口：

- `.agents/agent.md`；
- `.agents/rules/服务器测试包生成规则.md`；
- `.agents/rules/算子配置规则.md`；
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`；
- `.agents/rules/GAP_int32_mac_bypass_rules.md`；
- `.agents/rules/GAP_repair_candidate_rules.md`。

只删除重复公共清单、未改变专项 CDA 语义：

- `.agents/rules/DequantizeLinear算子配置规则.md`。

保持原样：

- `.agents/rules/GAP_probe_v7_validator_rules.md`；该文件已经短小且只有专项动态门。

## 完整信息保留

精简前全文移动到只读归档：

- `.agents/archive/agent_pre_read_compaction_20260724.md`；
- `.agents/archive/server_package_rules_pre_read_compaction_20260724.md`；
- `.agents/archive/operator_config_rules_pre_read_compaction_20260724.md`；
- `.agents/archive/NDP_copy01_README_HARDWARE_SIM_ENTRY_pre_read_compaction_20260724.md`；
- `.agents/archive/GAP_int32_mac_bypass_rules_pre_read_compaction_20260724.md`；
- `.agents/archive/GAP_repair_candidate_rules_pre_read_compaction_20260724.md`。

版本号、ZIP SHA、日志行、旧 runner 命令和结束过程继续可审计，但不再是生成前必读或
当前命令来源。当前版本状态只进入 plan/task record。

## 去重结果

四份原公共必读文件：

| 文件 | 精简前 | 精简后 |
|---|---:|---:|
| `.agents/agent.md` | 729 行 / 51,829 B | 112 行 / 5,862 B |
| `服务器测试包生成规则.md` | 374 行 / 24,319 B | 250 行 / 10,581 B |
| `算子配置规则.md` | 816 行 / 60,366 B | 243 行 / 12,168 B |
| `NDP_copy01/README_HARDWARE_SIM_ENTRY.md` | 210 行 / 12,475 B | 136 行 / 5,461 B |

原四文件合计 2,129 行；当前四文件加新路由和完整硬件条件附录合计 1,066 行，仍减少
1,063 行。实际单算子只读命中的硬件章节，不再被迫阅读 SA/N2N 等无关域。

专项文件：

- GAP int32_mac：174→131 行，并去除重复增量和逐版本结果；
- GAP repair：100→87 行，并把候选实例身份移回 task record；
- DequantizeLinear：205→199 行，只去除公共必读文件逐项复写。

## 有效规则迁移

| 原内容 | 唯一当前归属 |
|---|---|
| 必读选择、原生文件选择、读取收据 | `生成前必读索引.md` |
| 项目稳定边界、事实优先级、RTL 默认禁改 | `.agents/agent.md` |
| E0～E5 和动态基线/回归分类 | `生成前必读索引.md` |
| JSON 层级、语义 owner、物化回环、mapping/execplan/provenance | `算子配置规则.md` |
| LC/MSE/Buffer/SA/GA/N2N 位域、公式与 RTL 反例 | `NDP硬件字段语义.md` |
| 单命令、SCA_D、timeout、identity、return allowlist、预算 | `服务器测试包生成规则.md` |
| Make/TB/filelist、SCA loader、完成观察、readback ABI | `NDP_copy01/README_HARDWARE_SIM_ENTRY.md` |
| GAP int32_mac 逻辑树、双输入、normal FIFO、stage memory | `GAP_int32_mac_bypass_rules.md` |
| GAP v7 动态门 | `GAP_probe_v7_validator_rules.md` |
| repair transactional restore 与 E2/E4/E5 门 | `GAP_repair_candidate_rules.md` |

新增/强化规则：

- `CDA-CONFIG-SEMANTIC-OWNERSHIP-001`；
- `CDA-CONFIG-MATERIALIZED-ROUNDTRIP-001`；
- `CDA-SERVER-WORKLOAD-PROVENANCE-001`；
- `CDA-SERVER-ONE-COMMAND-001`；
- `CDA-SERVER-NO-DYNAMIC-BASELINE-001`；
- `CDA-SERVER-RETURN-RECEIPT-001`；
- `CDA-GAP-INT32MAC-MATERIALIZED-STAGE1-001`；
- `CDA-GAP-INT32MAC-BRANCH-ISOLATION-001`。

所有旧硬件反例 ID 仍在活动规则中，包括
`CDA-SA-INT8-CSA-001`、`CDA-SA-FP-CONVERT-001`、
`CDA-GA-INPORT-CONVERT-001`、`CDA-GA-INT8-MAX-PIPE-001`、
`CDA-GAP-GA-ACCUM-STATE-001` 和 `CDA-N2N-ROUTE-TRANSFER-001`。

## GAP 可靠性修正

公共精简同时纠正两处会导致流程误判的旧描述：

1. GAP int32_mac v1～v5 没有任何服务器成功动态基线；不得称 v5 为回归。
2. 旧 local E2 没有反解最终 stage-1 JSON 的 transaction/buffer/bank/lifetime，
   因此恢复到 `<E2` 并禁止新包。共享 LC 只标 `STRUCTURAL_RISK`，不冒充已证根因。

## 当前文件身份

- `.agents/agent.md`：
  `27f2e3a567d39e01abe176289bcffb3bc28fd6a4c39ffb0dd17c79784154b966`
- `.agents/rules/生成前必读索引.md`：
  `539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7`
- `.agents/rules/NDP硬件字段语义.md`：
  `7f446adb1719658ce75c2614c6d619fc2c7cdcabf5e4fd34945482645539158f`
- `.agents/rules/服务器测试包生成规则.md`：
  `4707fc8ca6c3d358f61d32b109175ec319e39ffa1d1f56c791796c6718406688`
- `.agents/rules/算子配置规则.md`：
  `a5fbe2f0fa2e26d8cd4ebfe8772d5a3c69516d6918cfaa5087198706a352427b`
- `.agents/rules/GAP_int32_mac_bypass_rules.md`：
  `f53fecb9106705d113354b4ab81356cbdc8179e602b2f7e584390bafe57e67a8`
- `.agents/rules/GAP_repair_candidate_rules.md`：
  `226e17ff344cd55c215707f8d6dd3ff4bedb3efff2cdef11ec44cb5a0e0b0d47`
- `.agents/rules/DequantizeLinear算子配置规则.md`：
  `ba75b679199aa140a9765b8f44ae335b492f667509f50a0c01f9dfc6cdd3f8e2`
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`：
  `4318f3a28de399fb522740315f11bdddf346e71969cf1e45686899a568b042d7`

## 验证

```text
python -m unittest tests.test_mandatory_read_compaction -v
Ran 8 tests
OK
```

测试确认：

- 只有路由文件拥有公共读取矩阵；
- 精简前全文归档存在；
- 公共活动文件不含具体 package/probe/repair 版本身份；
- 通用 GAP bypass/repair 规则不含候选版本身份；
- 关键硬件反例和新增可靠性规则仍在活动规则中；
- 重复标题已移除；
- E0～E5 的逐级定义只存在于公共路由，其他文件只引用；
- 公共文件行数受门限约束。
