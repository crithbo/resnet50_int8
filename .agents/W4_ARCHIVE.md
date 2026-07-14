# W4 归档与错误追溯索引

最后更新：2026-07-14

本文件只服务W4追溯。W4实现、方案切换、事故、审计和最终裁决保留在原W4对话与`history.md`中；新对话的当前任务从`.agents/W5_HANDOFF.md`进入。这里不把历史条目重写成“从未发生”，也不允许旧结论重新覆盖现行合同。

## 1. W4最终结论

- W4业务闭环提交：`952a96b48416ed2ea1bd2d3068a541ab3dd43625`。
- W4闭环台账提交：`3b5fff4d2007d2acdd7793bc69988b1d6f98be40`。
- 目标：28-slice RTL，正式混合profile`w4_deepseek_hybrid28_resnet50_v1`。
- G4 v2：12/12 true，阻塞为空，W5获准。
- 明确非声明：`clean_elaboration_claimed=false`；未通过目标simulator、硬件或三方数值验收。

当前W4物理事实由以下文件共同决定：

- `.agents/decisions/ADR-007-target-rtl-and-28-slice-topology.md`：RTL commit与HIGH/LOW物理拓扑；
- `.agents/decisions/ADR-008-official-target-config-source.md`：正式JSON/bitstream/model_execplan来源；
- `.agents/decisions/ADR-009-deepseek-baseline-inheritance.md`：DeepSeek基线继承、混合profile与G4闭环；
- `contracts/architecture.json`；
- `contracts/deepseek_rtl28_physical_baseline.json`；
- `contracts/resnet50_rtl28_w4_delta.json`；
- `contracts/hardware_approval.json`。

ADR-009被批准合同按hash绑定，普通文档整理不得修改。

## 2. W4阶段索引

| 阶段 | 主要内容 | 关键提交/证据 |
|---|---|---|
| 旧16-slice阶段 | simple、Conv、Pool、Add、GAP、MatMul双profile及旧G4审计 | 仅作legacy；ADR-002/003/005和`artifacts/w4/legacy16_index.json` |
| 目标切换 | 固定`Trassic2.0_RTL@e3bdebba...`与28-slice HIGH/LOW拓扑 | `6626d916...`，ADR-007 |
| 环境事故与恢复 | managed worktree junction被宿主回收穿透并清空Local四目录；从已校验ZIP选择性恢复，随后禁止junction | `6d74a156...`；详细证据见`history.md`“managed worktree junction事故” |
| C0 | current gate fail-closed、architecture/approval迁移到RTL28、legacy证据隔离、RTL快照lock | `f8978827...`、`448c21c7...`、`e23ac8ab...` |
| C1 | 冻结28-slice geometry及Quantize/Dequantize/View正逆接口 | `c2443f7d...`；泄漏终审`13b9c4a4...` |
| C2 | Conv、MaxPool/GAP、MatMul并行实现；QLinearAdd单线程完成 | `3d55bd3b...`、`e67e05b9...` |
| C3 | 93边、91 qparam链、16残差Add、79 tensor生命周期/alias、两种静态成本场景 | `496a592d...` |
| C4 | 固定正式配置源；Pool三模板字段/寄存器/bitstream审计 | `543bb592...`、`3407a20c...`、`0518d2fc...` |
| C5 | Quant与Add-Dequant GA crosswalk | `cb882328...` |
| C6 | GEMV/MatMul与sum族静态配置审计 | `5048b703...` |
| C7 | 78节点/133 hw_op typed参数合同，491个initializer引用、94个派生参数 | `911cb98a...` |
| 最终闭环 | DeepSeek公共物理合同＋ResNet差异合同＋混合profile＋具名基线决定 | `952a96b4...`，ADR-009 |

完整40位hash、父提交、测试数和精确回退点以`history.md`相应条目为准。

## 3. W4中已经纠正的错误

1. **把旧16-slice软件candidate当成现行硬件证据。** 已通过current/legacy registry隔离、显式geometry和G4 fail-closed测试修复。旧文件保留，但不得进入current gate。
2. **把一张batch样本一个slice或`(owner+step)%slice_count`外推到28-slice。** 已改为RTL显式七条HIGH环和一条LOW环，batch组为`[3,3,2,2,2,2,2]`。
3. **把全网profile强迫为group/global二选一。** ADR-009改为完整28-bit启动mask加算子级`local/HIGH-4/LOW-28`通信域；当前七族没有LOW-28选择。
4. **把clean elaboration日志当成唯一W4批准前置。** 现在记录操作者对已完成DeepSeek硬件基线的具名确认，同时明确不伪造elaboration日志；新的clean日志只作额外RTL诊断。
5. **把正式配置来源、数值模拟器和硬件runtime混为一体。** ADR-008只批准JSON/bitstream/model_execplan来源；`NDPFuncModel`仍是Conv功能参考，目标数值执行和板级协议分别属于W6/W8。
6. **按CSV方括号范围解释寄存器位段。** 正式消费者实际使用`Nbit`宽度前缀与行顺序；MaxPool、Pool族、GA、SA和sum族审计已按正式规则重做。
7. **以bitstream生成成功替代数值正确。** C4～C6只标静态preflight，W5/W6仍必须执行golden+目标模拟器比较。
8. **managed worktree用junction共享Local依赖。** 已证明会在宿主回收时破坏Local源；现行规则禁止，依赖任务回Local或使用可恢复隔离副本。

## 4. 如何追溯W4回归

出现W4相关错误时按以下顺序，不要先重跑W3：

1. 运行`git status --short`，区分当前改动与既有提交。
2. 运行`.\.venv\Scripts\python.exe tools\sync_repositories.py verify`，确认RTL28证据和三参考仓lock。
3. 验证`contracts/hardware_approval.json`引用的ADR-009、DeepSeek物理合同和ResNet差异合同hash。
4. 重新运行G4审计，确认12个条件中的第一项变化；不要只看总状态。
5. 若是layout问题，先定位七族中哪个`forward/inverse/explain/validate`或哪条93边失败，再检查profile/domain/owner/tail。
6. 若是配置字段问题，查`contracts/target_config_authority_audit.json`和`contracts/typed_config_parameter_contract.json`，区分W4静态crosswalk与W5实例绑定。
7. 对照本索引中的阶段提交和`history.md`精确父提交，使用`git show <commit>`检查引入点；默认用`git revert`保留历史，不使用reset/rebase覆盖证据。

## 5. 不应触发W4返工的情况

- 目标数值模拟器入口缺失；
- INT8 SA、bias/psum/requant字段尚未闭环；
- W5实例JSON或qparams绑定失败；
- W7的6144-row地址规划、execplan或Bank_data失败；
- W8 load/start/wait/dump协议缺失；
- simulator/hardware与golden数值不一致但W4 inverse/layout仍bit-exact。

这些是后续阶段问题。只有目标RTL/profile/layout合同、模型/lowering身份、93边物理兼容或批准合同hash本身变化，才需要重开W4并明确列出失效证据。
