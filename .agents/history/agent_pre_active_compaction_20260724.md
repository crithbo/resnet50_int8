# ResNet50 INT8 项目总览与协作约束

最后更新：2026-07-24（生成前必读资料去重）

本文件只保存稳定边界和文档路由。当前任务、候选、blocker、暂停项和下一步只看
`.agents/plan.md` 的相关章节；完成过程看 `.agents/task_records/`，历史路线看
`.agents/history.md` 与 `.agents/archive/`。任何版本号、ZIP 哈希或临时结论都不得再
写入本文件。

## 1. 生成前置门

创建、修改、派生、重建或发布算子 JSON、mapping、bitstream、execplan、SCA/SCA_D
或服务器测试包前，必须先完整阅读：

1. `.agents/rules/生成前必读索引.md`；
2. 该索引按本轮动作、算子和实际硬件单元选出的公共规则、专项规则、原生入口及直接
   消费代码。

同一文件同一轮只读一次，并记录路径、SHA-256、适用原因、规则 ID、已知反例和未闭合
动态门。不得用“已经熟悉”“只改一个字段”“沿用旧包”或通用 validator 通过代替阅读。

若规则缺失/冲突，或相关结论仍为 `CONTRADICTED/TEST_REQUIRED`，必须 fail closed。
只完成 schema、mapping、bitstream 或本地公式，不得声明硬件语义或服务器发布通过。

## 2. 事实来源与冲突优先级

冲突时依次采用：

1. 用户本轮明确指示与授权；
2. 活动工具仓的锁定源码、README、真实生成输出和直接消费者；
3. 与本轮 package/workload/RTL 身份绑定的原始服务器回传；
4. 用户授权的参考配置及其固定上游身份；
5. 机器合同、专项规则、当前计划和历史记录。

项目文档是可修正总结。不得为迎合旧文档改写活动源码输出、服务器原始证据或冻结资产。
参考配置正确性、派生配置正确性、包结构正确性和服务器 E4/E5 是四个独立结论。

## 3. 仓库和目录角色

| 路径 | 角色 | 稳定边界 |
|---|---|---|
| `ndp-sim` | 活动原生工具链 | 身份由 `repos.lock.json`/当前审计锁定；活动 checkout 只读 |
| `ndp-sim-ref` | 固定旧参考/特定 typed 工具来源 | 默认禁用；只有机器合同或专项规则明确授权的文件才可在哈希门下使用 |
| `jsons` | 用户授权的服务器参考配置 | 可作精确参考或结构证据；不得伪装成活动原生产物 |
| `tools/`、`resnet50_pipeline/`、`contracts/` | 项目补丁、验证器和机器合同 | 必须登记来源；不得静默复制原生 planner/encoder 功能 |
| `artifacts/`、`server_returns/` | 生成证据和服务器原始/派生分析 | 历史身份只读；新实验使用全新路径 |
| `NDP_copy01` | 本地服务器入口/RTL 参考 | 默认只读；真实 VCS 在 Linux 服务器运行 |

项目补丁只允许安装到哈希绑定的隔离工具副本。活动上游 checkout、本地功能 RTL和历史
服务器回传不得原地修改。若工具来源、base commit、source SHA 或补丁 manifest 不匹配，
必须停止。

## 4. 功能 RTL 边界

默认禁止创建、携带、覆盖、patch、安装、恢复或间接替换任何 `rtl/` 目录中的文件，
包括本地 `NDP_copy01/rtl/` 和服务器 `<NDP root>/rtl/`。包必须只读采集实际编译入口
及 focused RTL 身份。

`rtl/` 外的 testbench、observer、runner 和分析器只有在以下条件全部满足时可修改：

- 用途是测试或只读观测；
- 不驱动 DUT，不改变激励、ready/valid、时序或完成条件；
- 逐文件记录 preimage、diff、大小和 SHA-256；
- 可关闭，并使用全新 compile/run 身份。

功能 RTL repair 必须获得用户本轮明确授权，并额外遵守专项 transactional restore
规则。历史授权不得外推。

## 5. 配置与执行链边界

稳定流水线为：

```text
typed request
→ 算子/shape 规则
→ logical ScheduleIR 与数值合同
→ strict address-unbound JSON
→ address-bound JSON
→ mapping/encoder/bitstream
→ execplan/SCA/SCA_D
→ independent golden
→ server E3/E4/E5
```

任何配置语义、地址、mapping 或执行计划变化都必须以本轮最终输入完整重建下游产物并
保存 provenance。失败/否决版本的 bitstream、execplan、SCA、回读和运行残留不能作为
新候选输入。输出字节偶然相同不能代替本轮重建收据。

活动 `model_execplan` 是已支持算子的 graph→配置实例→execplan/SCA 唯一实现。项目
合同只做 typed lowering、规则选择、严格验证、provenance 和发布门；不得建立平行
parser/planner/encoder。原生缺失 handler 时，只能在授权的哈希锁定隔离副本扩展原生
registry，再复用原生 pipeline。

## 6. 证据与服务器交接

E0～E5、`NO_DYNAMIC_BASELINE`、`FIRST_DYNAMIC_FAILURE` 和 `REGRESSION` 的唯一公共
定义在 `.agents/rules/生成前必读索引.md`。服务器身份、单命令、timeout、正式回读、
回传 allowlist 和 receipt 的唯一规则源是 `.agents/rules/服务器测试包生成规则.md`；
算子专项动态门仍由目标专项规则所有。

在用户返回绑定身份且通过相应动态门的服务器证据前，只能声明已经取得的本地等级。

## 7. 协作与文件维护

- 修改前检查工作树并保留无关用户改动；不使用 `git reset --hard`、
  `git checkout --` 或未经授权的删除。
- 冻结包、原始回传、发布 evidence 和已有输出目录只校验不覆盖；新工作使用新路径。
- `.agents/plan.md` 只维护当前状态/下一步；完成过程写入 task record，版本历史不回填
  公共规则。
- 规则文件只保存可执行约束、公式、反例、规则 ID 和发布门；版本号、包 SHA、某次日志
  行号和已结束过程写入 task record。
- 只有用户明确要求时才提交、推送、上传、运行服务器或执行其他外部变更。
