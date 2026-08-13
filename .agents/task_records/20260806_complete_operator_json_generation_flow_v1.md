# 新算子完整 JSON 生成流程 v1：公共门、九族闭环与能力阻断裁决

日期：2026-08-06  
owner task：`019fd276-14c5-7800-94db-87ebfb9ce632`  
唯一主线：`019fbec2-fe93-7e03-9314-cff6f222f33d`

## 1. 用户授权与边界

用户批准新的配置生成流程：

```text
typed target
→ native source-instance applicability
→ per-leaf provenance
→ handler capability
→ composition boundaries
→ strict complete JSON or exact BLOCKED
→ current tested config / blocker / result diff
→ whole-family lowering coverage
```

公共合同、schema、validator 和规则由本 owner 完成；九个算子族由各自持久 owner
执行。用户明确禁止生成服务器测试包。本轮没有生成 mapping、bitstream、execplan、
SCA、ZIP，没有上传、运行服务器或取 lease，也没有修改功能 RTL、current package 或
current family assets。

## 2. 启动读取收据

| 路径 | 读取时 SHA-256 |
|---|---|
| `.agents/agent.md` | `32801b76205716db1a4a049ba4c6e6874bdc7676d184b88b662bb55eb084d80f` |
| `.agents/rules/生成前必读索引.md` | `bd04756ccab49e5a94843a8d9337eda35f818073ea9daa31244be1ae9903e547` |
| `.agents/rules/整网测试收敛优化专项规则.md` | `20b3ac75123719ace1910372df3025d1d28f69c43f5ba3867c10cb7bce3fd06a` |
| `.agents/plan.md` | `6237dc3aa719b7797ade7ad1a5301de9eb3edc21e8a39d294dd6d7212d31f483` |
| `.agents/rules/服务器测试包生成规则.md` | `36f6596c913120c24725da95e269200ecff4b25130d4eefe8d99d21c7b2e7457` |
| `.agents/rules/算子配置规则.md` | `30d0b20979e639d6bd9d0ec81f5e920da19733f0b2e3fe7ba751ef7e44b972d1` |

## 3. 公共实现

公共门实现了：

- native JSON 只证明 source instance，不自动授权 target 泛化；
- strict candidate 全 leaf 唯一 provenance；
- source absent 与 null/zero/target-derived 分态；
- handler 的 shape/dtype/qparam/layout/address/schedule 能力矩阵；
- 多 primitive 的 typed/transaction/lifetime/rounding 边界；
- candidate 与 current tested config 逐 leaf 分类；
- `COMPLETE` 与合法 `BLOCKED` 分离；
- whole-family stage coverage；
- artifact root 禁止服务器包产物。

Conv 首次真实接入发现旧 driver 把合法 unresolved 能力缺口同时误报为结构错误。修复后
报告分成 `errors`、`completion_blockers`、`contract_valid`、`blocked_valid` 和
`pass`，合法 BLOCKED 不再冒充合同失败。

MatMul 首次真实接入又发现 family auditor 只按共享 `RequantizeUint8` 类型选 stage，
跨族误纳入 53 个 Conv requant。最终公共规则和实现采用：

```text
CDA-COMPLETE-JSON-FAMILY-SET-SCOPE-FAMILY-OR-STAGE-PREDICATE-001
family_scope.mode = PINNED_EXACT_STAGE_IDS
family_scope.lowering_sha256 = exact lowering SHA
family_scope.expected_stage_ids = complete exact family stage set
```

`target_hw_op_types` 在 exact mode 只逐 ID 校验真实 type，不扩张 scope。旧 manifest
保持显式 `LEGACY_HW_OP_TYPE_SELECTOR` 兼容语义并给出 migration recommendation。

最终公共身份：

| 文件 | SHA-256 |
|---|---|
| `tools/validate_complete_operator_json_candidate.py` | `4e30018656afd41f3f7d89f2d56070986e2465fac59d41483ae40fbf8f4ec62f` |
| `tools/audit_complete_operator_json_family_set.py` | `3e72c6c8fb5921b427d6e41b048acb51b1f55df65011e4b1733cdc341f7ff5f1` |
| `schemas/operator_config_complete_json_family_set_v1.schema.json` | `bc4b0b40810e526cfa6b6bb8bce734850b85bb44c0100b5e43212b0aba5bfd18` |
| `tests/test_complete_operator_json_candidate.py` | `d51ab72366735b5e7f3039c72cc47b4d28fcb3f92747bae878ccaee03589a717` |
| `tests/test_complete_operator_json_family_set.py` | `3153a13f725e4cc96df1c71a7ab40cea121b00957ec0c552db1a2f9952ec17d0` |

公共回归 20/20 PASS，`py_compile` PASS，`git diff --check` PASS。MatMul exact
控制覆盖正例及缺 stage、重复 ID、type 错绑、额外跨族 stage、lowering SHA 漂移和
stage ID 漂移。

## 4. 九族最终总账

当前 lowering 有 133 个唯一 stage。九个 family scope 合计 134 个 stage occurrence，
因为 `hwop-0075-01` 同时属于 generic RequantizeUint8 family 与 target-specific
QLinearMatMul composite：该 MatMul 实例为 COMPLETE，而通用 Requant 生成能力仍
BLOCKED。这不是重复遗漏；133/133 唯一 lowering IDs 至少被一个 manifest 覆盖，全部
逐 ID type 绑定正确。

九族全部得到 exactly-covered 的 COMPLETE 或合法 BLOCKED 裁决：

| family | 逻辑 stage | 最终状态 | 关键结果 |
|---|---:|---|---|
| GAP | 2 | COMPLETE | 0 unresolved；8 个物理配置与 v40 byte-equal |
| View | 1 | COMPLETE / metadata-only | 0 hardware JSON；UINT8 alias/address 静态闭合 |
| MaxPool | 1 | COMPLETE | 461/461 resolved；current v5 padding null→0 为 suspected defect |
| Dequant | 2 | COMPLETE | 832/832 resolved；两实例与 current final 全 SAME |
| QLinearMatMul | 2 | COMPLETE | 11,568/11,568 resolved；exact family scope 2/2 |
| ConvInt32Accumulate | 53 | capability BLOCKED | 615 unresolved；缺 generic equation-backed materializer |
| QLinearAdd | 17 | capability BLOCKED | 45,169 unresolved；缺 six-qparam composite handler |
| QuantizeLinear | 2 | capability BLOCKED | 1,016 unresolved；缺 exact binary32 divide-RNE/typed mapper |
| RequantizeUint8 | 54 | capability BLOCKED | 944 unresolved；placeholder handler 不支持 target axes |

全部九份 fresh family manifest 现均使用
`PINNED_EXACT_STAGE_IDS + lowering SHA bf661e4e...5432`，legacy family manifest
剩余数为 0。各 scope 的 expected/covered 为
`53/53、54/54、2/2、17/17、2/2、1/1、2/2、1/1、2/2`，scope
missing/unexpected/duplicate/type/SHA errors 均为 0。四个 BLOCKED family 的
auditor 非零只来自冻结 candidate 未达到 COMPLETE，不是 scope 失败。

机器总报告：
`artifacts/operator_config_validation/r5-complete-json-shared-gate-v1/report.json`。

## 5. 与 current 在测配置/卡点/结果的关键比对

1. GAP：候选与 v40 最终 config/execplan byte-equal；shared-LC/backpressure、terminal
   和 formal D 是动态问题，不能继续改 JSON。
2. Conv：615 个物理 leaf 中 614 SAME，1 个 route-specific intentional derivation；
   serialized/native 当前卡点没有由配置差异解释。
3. QAdd：v35 每侧 `4×4B=16B` 供给，而 Buffer5 要求 32B，属于
   `CONFIG_EXPLAINS`；v36 已静态修成 32B，但动态 return 未验证。
4. MaxPool：current v5 只在 enabled padding 的 `null→0` 与 strict candidate 不同；
   记 suspected defect，但服务器 stop 的因果证据仍不足。
5. MatMul：current v9 有 120 个 suspected leaves，集中于 accum stream1 重复 MSE
   byte location 和 READ_STREAM0 buffer lifetime `1/16→16/16`；ordering、实际 reads、
   terminal、formal D 仍是动态门。
6. Quant：旧 placeholder stride 覆盖错误不是 current package；node0074 已批准的
   DQ→View→Q 消除继续有效，不被 generic Quant blocker 推翻。
7. Requant：没有 proven current config diff 能解释 node0001 历史卡点。
8. Dequant：两个 strict candidate 与 current final 全 SAME。
9. View：current package 没有 View 硬件 config；正确结论是 metadata-only no-config，
   不能伪造 arithmetic JSON。

## 6. 规则裁决

- 公共 exact-stage family scope 是真实非同义规则/实现缺口，已实现并同步主线。
- QAdd `typed composite handler` 提案的语义已被既有 SIX-QPARAM、THREE-STAGE、
  BROADCAST、READINESS/LIFETIME 和 EXACT-TAIL 规则覆盖；这是实现能力缺口，不新增
  重复规则。
- `Flatten_View算子配置规则.md` 的代表路径仍写旧 FP32 node0072D→node0074A。
  专项已准备窄幅更新为当前 UINT8 node0071D→node0073→node0075A、32,768B、offset0，
  并保留 accepted lifetime/actual reads/terminal/formal-D 动态门；旧 FP32 路径只作
  off-path 历史证据。
- MaxPool validator 的旧 `ga_int8_max` 整体 CONTRADICTED 已由本族 owner 修正为
  numeric `LOCAL_SOURCE_PASS`、pipeline `CONTRADICTED` 两项独立事实；padding RTL
  receipt 同时绑定 current cloud checkout 与本地镜像的完整三分支方程。46/46 测试与
  8/8 篡改负控通过，strict candidate/current v5/diff SHA 未变化。机器报告 SHA 为
  `28fcaeefed00a8320a2c48da71dd9f10efa2cc450a8155709cd30c5a292efb9e`，
  padding receipt SHA 为
  `3228e677cb1c7767e0ee68256db524e6ee9d25ff648916f1b05a6d4a46650e75`。

## 7. 用户决定点

五个 COMPLETE family 已达到本次“完整 JSON + current diff”的目标；四个 BLOCKED
family 不能在现有授权下继续，因为公共规则要求 native handler 缺失时只有用户批准的
hash-bound patchset 才能在隔离副本扩展。

需要用户决定是否授权：

```text
在隔离副本为 ConvInt32Accumulate、QLinearAddUint8、
QuantizeLinear、RequantizeUint8 实现 hash-bound local handler/materializer 与测试；
继续禁止修改 active ndp-sim、禁止构包和服务器动作；
实现后仍必须通过同一 complete-JSON 与 exact family-scope 门。
```

未获该授权前，继续“补 JSON 字段”只能猜值或把 project config 冒充 upstream authority，
不符合已批准流程。

## 8. 声明边界

本记录只关闭九族 local complete-JSON 能力、逐字段来源、全族 coverage 和 current
静态对比。没有提升 production natural terminal、正式 D、E3/E4/E5、性能或服务器
release。
