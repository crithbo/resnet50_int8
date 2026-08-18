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

## 3. Skill 强制触发

以下动作必须使用 `.codex/skills/resnet50-server-package-flow/SKILL.md`：

- 向已注册 family 派发或恢复任务；
- 构建/修补 package、runner、observer、可选 TB VCD 或 return；
- 分析正式 return、设计 successor；
- 审查可能影响公共规则/硬门的构包事故。

纯 config/numeric 研究且不触碰服务器包时不调用。Skill 只编排 current registry 与机器 gate，不能
授权服务器、RTL 或跨族写入。主线不得用临时子代理替代 registry 中持久 family owner。

## 4. 事实优先级

冲突时依次采用：用户本轮明确指示 → actual locked source/README/direct consumer → 身份绑定的原始
服务器 return → 用户授权的 reference → machine contract/active rule/current plan → history。

参考配置正确、派生配置正确、package 可执行和服务器 E4/E5 是独立结论，不相互替代。

## 5. 稳定权限边界

- 默认禁止修改任何 functional `rtl/`；必须有用户本轮明确授权。
- TB/observer/runner 必须可关闭、只读，不改变激励、握手、状态转移或完成条件。
- active `ndp-sim`、RTL、ISA 默认只读；隔离 handler/materializer 只在明确授权和 source binding 下实现。
- 禁止 host tensor replay/precompute、跨仿真 dump/reload，禁止用内部 write 冒充 downstream accept。
- tested/run-bound package 和原始 return 不覆盖；unrun candidate patch-first，复用未变 PASS 门。
- 只有用户明确要求时才上传/运行服务器、取 lease、提交、推送或做其它外部变更。

## 6. 工作区边界

| 路径 | 用途 |
|---|---|
| `ndp-sim` | active 原生工具链；默认只读 |
| `jsons` | 用户授权 reference，不冒充 active output |
| `tools/`、`contracts/`、`schemas/`、`tests/` | 项目机器合同与 gate |
| `artifacts/.../r5-server-test-packages/` | pending/tested/superseded 管理存储 |
| `NDP_copy01` | 本地服务器入口/RTL 参考；真实 VCS 在 Linux 服务器 |
| `.agents/history/` | 停用规则与历史，不是生成输入 |

## 7. 协作与完成

- family owner 只写本族范围并主动向 current mainline 回传；mainline 消费后更新 plan/registry。
- 非直接相关进度不持续同步到其它会话；改变其 input、方法、权限或 blocker 时再通知。
- 事故先分类为规则错误/遗漏、实现逃逸、会话不合规或单次领域失败；规则允许替换、合并、删除、
  归档，不采用“每次事故追加一条”。
- blocking hard gate 只能映射 `server_start`、`actual_input`、`state_safety`、`return`；其它 record-only。
- 本地结束必须报告 changed/frozen/reused surface、测试、claim boundary 和未授权动作未发生。

## 8. 不可降低的完成口径

整网/算子正式完成仍要求 production compile、simulation、目标stage、natural terminal、合法 workload、
formal-D conjunction、runtime-D 不缺失、E4、E5。局部仿真、schema、partial return、observer expected、
内部 buffer write 或 identity 相同都不能替代。
