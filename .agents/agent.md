# ResNet50 INT8 项目稳定入口

最后更新：2026-08-18

本文件只保存项目入口、角色、权限和协作纪律。current 状态只看 `.agents/plan.md`；动作读取路由看
`.agents/rules/生成前必读索引.md`；current owner 看
`contracts/current_session_owner_registry_v1.json`；历史只从 `.agents/history/` 入口查阅。

## 1. 文档唯一归属

| 事实 | 唯一 owner |
|---|---|
| current 状态、blocker、下一步、pending identity | `.agents/plan.md` |
| 动作/族读取路由、停止门、E0–E5 | `生成前必读索引.md` |
| complete JSON/provenance/materialization | `算子配置规则.md` |
| LC/MSE/Buffer/SA/GA/N2N 字段 | `NDP硬件字段语义.md` |
| package/runner/diagnostic/runtime/return | `服务器测试包生成规则.md` |
| role/owner/handoff | `会话转接与所有权规则.md` |
| 跨族收敛/规则事故 | `整网测试收敛优化专项规则.md` |
| primitive/family 稳定差异 | 对应专项规则 |
| 已完成证据 | `.agents/task_records/` 与 machine report |

活动规则 exact-set 和唯一 `CDA-*` owner 由 `contracts/active_rule_registry_v1.json` 登记；历史规则默认
不读、不参与生成。规则中不得保存 package 版本、当前结果或一次性授权。

## 2. 新会话/新模型接手

任何接手者固定执行：

1. 完整读本文件、current plan、生成前索引和会话转接规则；
2. 从 current owner registry 找到自己的 `role_id`、current mainline、write/forbidden scope 和
   in-flight pointer；
3. 按下表只读角色增量；不得先通读历史；
4. 服务器包相关任务调用项目 Skill；环境无 Skill 时显式读 Skill 文件并执行同一 workflow；
5. 运行 `tools/validate_project_takeover_readiness.py`，先回报 previous progress/current purpose/scope/
   forbidden/conflicts，再继续。

### 2.1 角色读取矩阵

共同必读：`agent.md`、`plan.md`、生成前索引、会话转接规则、current owner registry。

| role | 增量必读 |
|---|---|
| `mainline.control` | 配置、硬件字段、服务器包、整网优化；只在裁决某族时读该族规则 |
| `family.gap` | 配置、硬件字段、服务器包、GAP、量化尾、跨stage生命周期 |
| `family.conv.serialized/native` | 配置、硬件字段、服务器包、INT8 SA、Requant、量化尾、生命周期 |
| `family.qlinearadd` | 配置、硬件字段、服务器包、QAdd、量化尾、生命周期 |
| 其它 family | 三份公共生成规则 + 当前唯一目标族规则；只按实际复合关系叠加 primitive |
| `infra.server-package` | 服务器包规则和原生入口 README；不改 config 时不读其它族 |
| `optimizer.whole-network` | 整网优化、服务器包；仅 config audit 时读配置规则，默认不读族规则 |
| `consumer.human-json` | 配置、硬件字段、服务器包和当前唯一目标族规则 |

未知 role 先由 mainline 登记，不能自封为“全规则会话”。

## 3. 模型与推理强度路由（仅 deepseekharness 执行时采用）

**适用声明：本节只约束在 deepseekharness 环境运行本项目的会话；在 Codex 中执行时不得把本节当作
模型选择或思考强度依据。**

| 角色/环节 | 模型建议 | 思考强度 |
|---|---|---|
| `mainline.control` 日常路由、派发、验收、CAS 换届 | Flash | 默认 |
| `mainline.control` 裁决正式 return、改规则、事故分类、授权边界判断 | Pro | Max |
| family owner 只读接管、读规则、写 receipt、机械验证 | Flash | 默认 |
| family owner 分析正式 return、root cause、successor 候选矩阵 | Pro | Max |
| RTL/config 语义裁决、物化回环、地址/transaction 证明 | Pro | Max |
| 规则审计 `audit_active_rule_registry.py` / takeover 验证 | Flash | 默认 |
| 审计失败后的语义裁决 / 规则 delta 设计 | Pro | Max |
| 服务器运行阶段 | Flash | 默认 |
| 大 return 流式分析 | Flash（上下文不足再 Pro） | 默认起步，首分歧处再提高 |

固定规则：

1. 本项目大部分工作是遵循已有规则和机器 gate，**Flash 能完成时一律用 Flash**；不得用“模型不同”跳过控制面。
2. Pro/Max 只用于高代价推理：正式 return 裁决、successor 设计、规则事故裁决/规则 delta、RTL/地址/
   transaction 因果根因、审计失败后的语义裁决。
3. `audit_active_rule_registry.py`、`validate_project_takeover_readiness.py` 等是确定性机器检查，
   执行时用 Flash/默认强度；真正需要 Pro/Max 的是“审计失败后是否改规则、改哪里”。
4. 服务器上传/运行/取 lease 由 package/runner 决定，运行阶段 Max 无收益；收益在 return 分析阶段。
5. 新会话、新模型或新族接手时必须先按本路由选择执行强度；不确定时上报主线，不自行降级或升级。

## 4. Skill 强制触发

以下动作必须使用 `.codex/skills/resnet50-server-package-flow/SKILL.md`：

- 向已注册 family 派发或恢复任务；
- 构建/修补 package、runner、observer、可选 TB VCD 或 return；
- 分析正式 return、设计 successor；
- 审查可能影响公共规则/硬门的构包事故。

纯 config/numeric 研究且不触碰服务器包时不调用。Skill 只编排 current registry 与机器 gate，不能
授权服务器、RTL 或跨族写入。主线不得用临时子代理替代 registry 中持久 family owner。

`resnet50-server-package-flow` 只允许配置在本项目 `.codex/skills/` 下；不得复制到用户级/全局 skill
目录，也不得写入 DSH preset 或其它工作区。当前会话若无 skill 工具加载项，必须显式读取本文件执行。

## 5. 事实优先级

冲突时依次采用：用户本轮明确指示 → actual locked source/README/direct consumer → 身份绑定的原始
服务器 return → 用户授权的 reference → machine contract/active rule/current plan → history。

参考配置正确、派生配置正确、package 可执行和服务器 E4/E5 是独立结论，不相互替代。

## 6. 稳定权限边界

- 默认禁止修改任何 functional `rtl/`；必须有用户本轮明确授权。
- TB/observer/runner 必须可关闭、只读，不改变激励、握手、状态转移或完成条件。
- active `ndp-sim`、RTL、ISA 默认只读；隔离 handler/materializer 只在明确授权和 source binding 下实现。
- 禁止 host tensor replay/precompute、跨仿真 dump/reload，禁止用内部 write 冒充 downstream accept。
- tested/run-bound package 和原始 return 不覆盖；unrun candidate patch-first，复用未变 PASS 门。
- 只有用户明确要求时才上传/运行服务器、取 lease、提交、推送或做其它外部变更。

## 7. 工作区边界

| 路径 | 用途 |
|---|---|
| `ndp-sim` | active 原生工具链；默认只读 |
| `jsons` | 用户授权 reference，不冒充 active output |
| `tools/`、`contracts/`、`schemas/`、`tests/` | 项目机器合同与 gate |
| `artifacts/.../r5-server-test-packages/` | pending/tested/superseded 管理存储 |
| `NDP_copy01` | 本地服务器入口/RTL 参考；真实 VCS 在 Linux 服务器 |
| `.agents/history/` | 停用规则与历史，不是生成输入 |

### 7.1 文件生命周期

- 新建临时文件只放 `.tmp/<role>/<task>/`；可再生成的构包/提取中间结果放
  `work/<role-or-family>/<objective>/`。不得在项目根散落 `tmp*`、debug、extract、repeat ZIP 或缓存。
- 每个新生成根必须有 `WORKSPACE_OBJECT_MANIFEST.json`，登记 owner、用途、来源、canonical anchor、
  lifecycle、保护原因与 cleanup trigger。未知 legacy、symlink/reparse、拒绝访问路径默认保护，不按名称或
  年龄盲删。
- 一次任务超过 10000 条逻辑记录时，除 actual consumer 明确要求逐文件外，使用 JSONL、SQLite、
  Parquet 或压缩归档；不得默认每条记录创建一个文件。
- 任务结束、package admission+storage rotation、formal return 双消费和会话换届是 cleanup 触发点。
  清理必须 `scan -> plan -> quarantine -> verify -> purge`；首次或范围变化时先 dry-run。
- cleanup 失败不能反向否定已通过 package；它只保留 cleanup-pending，并在预计空间不足或继续制造同类
  中间文件前阻止下一次本地物化。源码、current pointer、pending、开放 blocker、E4/E5 和原始数据不删。

## 8. 协作与完成

- family owner 只写本族范围并主动向 current mainline 回传；mainline 消费后更新 plan/registry。
- 非直接相关进度不持续同步到其它会话；改变其 input、方法、权限或 blocker 时再通知。
- 事故先分类为规则错误/遗漏、实现逃逸、会话不合规或单次领域失败；规则允许替换、合并、删除、
  归档，不采用“每次事故追加一条”。
- blocking hard gate 只能映射 `server_start`、`actual_input`、`state_safety`、`return`；其它 record-only。
- 本地结束必须报告 changed/frozen/reused surface、测试、claim boundary 和未授权动作未发生。

## 9. 不可降低的完成口径

整网/算子正式完成仍要求 production compile、simulation、目标stage、natural terminal、合法 workload、
formal-D conjunction、runtime-D 不缺失、E4、E5。局部仿真、schema、partial return、observer expected、
内部 buffer write 或 identity 相同都不能替代。
