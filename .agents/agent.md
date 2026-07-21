# ResNet50 INT8 项目总览与协作约束

最后更新：2026-07-21（职责、事实来源、规则定位与服务器证据边界复核）

本文件只保存相对稳定的项目职责、代码地图、事实来源、证据边界和协作约束。当前任务、阻塞、输入身份和下一步只看`.agents/plan.md`；已经发生的版本过程、失败和恢复点只看`.agents/history.md`。

## 1. 文档职责

- `.agents/agent.md`：稳定总览、代码/工具入口、长期边界和协作约束。
- `.agents/plan.md`：唯一动态接手入口，只保留当前状态、当前输入、下一步和停止条件。
- `.agents/history.md`：压缩历史、服务器实测证据、版本错误、关键恢复点和制品清理记录，不作为当前命令来源。
- `.agents/rules/算子配置规则.md`：从实现、consumer/RTL和实证中提炼的模型语义、LC/PE/stream、layout、qparams和数值比较约束；只读取与当前修改相关的章节，发现与事实冲突时及时更正。
- `.agents/rules/服务器测试包生成规则.md`：从原仿真入口、实际runner和服务器结果中提炼的package/overlay、运行与回传约束；不是独立权威，也不因旧文字自动增加服务器校验。
- `.agents/archive/README.md`：专项历史文档索引；只用于追溯。
- `.agents/decisions/`与`contracts/`：设计裁决和机器合同；被hash绑定的合同不能为整理措辞随意改写。

发生冲突时，先区分可执行字段与说明性文字：活动consumer/RTL、实际生成输入输出、被消费的机器字段和直接服务器证据优先；原始README用于解释入口意图。机器合同中的自由文本同样可能过时，不能仅因被写入JSON就覆盖可复现行为。`plan.md`负责表达由这些事实得到的当前状态；规则和说明是派生总结，必须随事实修正。历史只用于追溯，不授权当前命令。

## 2. 项目目标与端到端链路

目标是把正式ResNet50 INT8 ONNX模型转成可审计、可重建、可在28-slice目标架构执行并能定位首错的硬件链：

```text
正式ONNX、输入和initializer
  -> 模型图与硬件原子算子lowering
  -> 节点/子步骤golden
  -> 28-slice physical layout、地址、JSON和bitstream
  -> typed execplan、cfg_pkg、SCA和Bank_data
  -> NDPFuncModel / ndp-sim / RTL或真实硬件执行
  -> 原始Bank dump与inverse
  -> Golden / NDPFuncModel / target execution三方比较
```

成功标准不是“JSON可解析”“bitstream已生成”“CPU占用高”或“make退出0”，而是目标执行链实际消费同一冻结身份后，完整P/staged-D输出经过physical inverse，与Golden和NDPFuncModel逐元素一致。

### 2.1 三类证据

1. **Golden**：正式ONNX和固定输入产生的节点/子步骤真值。
2. **NDPFuncModel**：消费typed request、配置原文/SHA、qparams和physical layout的配置绑定功能模型；证明数学和布局闭合，不是逐周期bitstream执行器。
3. **Target execution**：ndp-sim数值执行器、RTL仿真或真实硬件对冻结包的实际输出。RTL/硬件证据必须包含身份、退出状态、原始dump、inverse和比较报告。

正式报告必须分别保存Golden↔NDP、Golden↔target、NDP↔target三组结果。任一侧缺失时只能标记`three_way_not_comparable`。

## 3. 门状态口径

| 门 | 含义 | 不足以通过的证据 |
|---|---|---|
| G0 | 编排、schema、artifact生命周期与失败阻断 | mock运行成功 |
| G1 | 模型、输入、量化和架构基线完整批准 | 仅取得候选ONNX或部分参数 |
| G2 | 小算子功能/布局参考闭环 | 非正式目标布局 |
| G3 | 全图节点与子步骤golden闭环 | 未生成目标配置/运行包 |
| G4 | 28-slice公共物理布局与目标配置继承闭合 | 单个candidate通过 |
| G5 | 单算子正式编码与配置绑定软件执行闭合 | JSON/bitstream能生成 |
| G6 | 目标数值执行器完整消费配置并通过 | 仅准备execplan/Bank_data |
| G8 | RTL/真实硬件完整P/D三方bit-exact | 高CPU、局部marker、自然退出或文件存在 |

当前具体状态只在`plan.md`维护。

稳定门快照：W0/G0、W2/G2、W3/G3、W4/G4已通过；W1仅冻结当前可取得的模型/输入/量化事实，G1未整体关闭；`node-0004`的正式编码、config-bound软件P/D和freeze-bound单算子运行包已闭合，因此该首例范围G5=true。其他shape/算子族的G5仍未闭合，目标数值执行和RTL三方证据尚无，因此G6/G8保持false。最新变化以`plan.md`为准。

## 4. 仓库与事实来源

根仓负责编排、合同、lowering、golden、28-slice布局、目标配置审计、硬件freeze、服务器包、返回分析和三方比较。参考仓由`repos.lock.json`恢复：

| 仓库 | 职责 | 不能误称为 |
|---|---|---|
| `ndp-sim-ref` | 正式JSON parser、placement、bitstream和原生execplan生成规则 | ResNet数值功能模型或硬件通过证据 |
| `NDPFuncModel/conv_func` | Conv配置绑定功能模型、physical staging/inverse和P/D比较 | 逐周期RTL、bitstream解释器 |
| `CGRA_SIM` | 旧ResNet/QNN语义、软件算子和性能参考 | 当前28-slice配置真值 |
| `NDP_copy01` | 本地只读服务器入口镜像、主Makefile/TB/filelist兼容性分析 | 可在Windows本机完成的VCS环境 |

稳定锁定点和提交恢复记录见`history.md`及`repos.lock.json`，不要在本文件复制版本台账。

## 5. 核心代码与工具地图

### 5.1 模型、golden与layout

- `resnet50_pipeline/model/`：正式ONNX图、initializer和模型身份。
- `resnet50_pipeline/lowering/`：模型节点到硬件原子算子的稳定映射。
- `resnet50_pipeline/golden/`：节点输出和Conv accumulate/requant子步骤真值。
- `resnet50_pipeline/*28_layout.py`：28-slice physical布局、relayout和inverse。
- `resnet50_pipeline/conv_instance.py`：Conv实例事实、shape、qparams、地址和ABI入口；外围不得复制硬编码。
- `tools/run_onnx_golden.py`、`tools/run_subop_golden.py`：正式golden入口。
- `tools/verify_w4_*layout.py`、`tools/audit_w4_gate.py`：W4物理布局与门审计。

### 5.2 配置、编码与数值闭环

- `tools/generate_conv_instance.py`：生成统一Conv实例。
- `tools/generate_conv_1x1_real.py`、`tools/generate_conv_1x1_requant_real.py`：生成accumulate/requant配置。
- `tools/run_conv_1x1_encoder.py`、`tools/run_conv_1x1_requant_encoder.py`：调用正式parser/placement/encoder并复验确定性。
- `tools/run_w5_conv_preflight.py`：配置绑定的Golden/NDP P/D比较。
- `tools/export_conv_1x1_hardware_freeze.py`：冻结输入、配置、bitstream、parsed evidence、地址表和manifest。
- `tools/compare_conv_hardware_execplan_dump.py`、`tools/compare_conv_1x1_hardware_dump.py`：真实返回Bank/P/D的inverse和三方比较。

### 5.3 execplan与服务器包

- `tools/generate_conv_hardware_execplan.py`：项目唯一正式硬件package入口。
- `resnet50_pipeline/conv_execplan_hardware.py`：消费freeze和typed request，调用原生execplan API，增加服务器barrier、SCA、Bank_data与完整readback合同。
- `tools/build_ndp_server_overlay.py`：唯一runtime-only overlay/runner/manifest/ZIP入口。
- `tools/audit_ndp_server_overlay_zip.py`：从最终ZIP全新解包的第二轮独立审计。
- `tools/analyze_hardware_server_trace_zip.py`：原始服务器结果ZIP结构分析；不能冒充数值比较。
- `NDP_copy01/Makefile.tb_NDP_Top_new_phy`、`tb_NDP_Top_new_phy.sv`、`rtl/filelists/NDP_Top_phy_filelist.f`：服务器三个活动入口。
- `NDP_copy01/README_HARDWARE_SIM_ENTRY.md`：只保存该目录的活动文件地图、Make/TB实际语义和Linux/VCS运行条件；不承担当前revision状态。

## 6. `model_execplan`复用边界

原生执行计划的直接事实来源为`ndp-sim-ref/model_execplan`同目录源码、正式consumer和可复现输出；README用于解释接口，源码行为优先于过时示例：

- 地址格式为`(slave<<25)|(bank<<23)|(row<<10)|(col<<4)|subword`，配置地址写入Load_Config前右移10位。
- 原生opcode为Load_Config=`000`、Clock_Enable=`001`、Write_Reg=`100`、Start_Comp=`101`；Clock_Enable全局一次。
- 64-bit命令两两封装为128-bit文本时，后一个命令位于高64位、前一个位于低64位；奇数尾补零，文件以LF结束。
- 项目wrapper直接复用原生`InstructionGenerator`、`write_instruction_outputs`和`write_install_manifest`，再加入opcode `110`的服务器completion barrier。

不得另建第三套execplan编码器。通用`ndp-sim-ref/model_execplan/main.py`会重跑bitstream、使用固定输出目录、原生流缺服务器barrier，且失败路径不满足当前freeze的fail-closed要求，因此不能直接生成正式服务器包。

## 7. 服务器与HDL边界

- `NDP_copy01/rtl/**`、主testbench及所有`.v/.sv`均只读；overlay不得包含、覆盖或现场修改HDL。
- 服务器源码可以更新。runner只要求主Makefile、主TB和主filelist三个逻辑入口可读并记录provenance，不要求Git HEAD、整树SHA、物理路径位于服务器根内或与本地逐字节一致；接口语义由真实Make/VCS/UCLI执行判定。
- TB/RTL实际SHA只作为provenance记录，不作为启动阻断门。
- 非HDL UCLI/TCL只允许驱动经审计但未连接的环境端口等窄范围动作，不得修改设计功能、伪造完成或定时宣告成功。
- 默认不采全量波形；正式完成包使用`completion_no_wave`，诊断波形必须使用独立revision。
- 本机只生成/审计运行包、分析原始ZIP并比较P/D；VCS/Verdi真实编译仿真只在具备许可证的Linux服务器执行。

修改package/overlay/generator/runner前读取`plan.md`、原仿真README、包内README模板和服务器规则中与变化直接相关的章节；无需反复阅读无关历史。影响最终制品的新revision仍须经过“受影响生成链/真实目录行为自检”和“最终ZIP独立解包审计”两轮不同覆盖的检查，但不得重复同一全量validator冒充两轮。

## 8. Artifact与证据保留

- `artifacts/w3/golden_batch16/`和`subop_batch16/`是大型只读golden，不因服务器包清理而重建或删除。
- `artifacts/w3/golden_batch16/`已完成精确目录ownership恢复并保持递归只读/执行权限；不得用重建数据掩盖权限问题。
- typed request、config-bound preflight、官方encoder合同、批准freeze和下一revision明确依赖的数值资产是生成输入，不属于旧服务器包。
- 当前只保留一个最新工作revision的package/overlay/ZIP/sidecar/selfcheck；已发往服务器且结果尚待回传的诊断revision可暂留到证据入库和下一revision接替，随后按服务器规则清理。
- 未上服务器的旧revision在错误进入规则/history后删除全部生成包。
- 已上服务器的revision在原始结果ZIP完成入库、验证和下一revision接替后，只长期保留原始结果ZIP及其SHA记录，不保留对应package、overlay、展开结果或派生分析目录。
- 原始结果ZIP不可改写；CPU占用、日志片段和分析目录都不能代替它。

详细归档策略见服务器包规则第10.1节，当前保留清单见`plan.md`。

## 9. 环境恢复与验证

普通本地接手先读`plan.md`并检查工作区改动，不默认同步参考仓、重建W3或跑全量回归。本地可使用Git查看改动，但服务器运行和完整性校验永久不依赖Git或`.git`。

```powershell
.\.venv\Scripts\python.exe tools\sync_repositories.py sync
.\.venv\Scripts\python.exe tools\sync_repositories.py verify
```

参考模型只在缺失或明确复验基线时运行`tools/prepare_reference_model.py [--check]`。约951 MiB的W3输出只在目录缺失或模型身份变化时由`tools/run_onnx_golden.py`和`tools/run_subop_golden.py`重建；输出目录必须预先不存在，不能混合新旧节点结果。

依赖参考仓的Python命令先设置`PYTHONDONTWRITEBYTECODE=1`，避免历史tracked pyc造成假脏。日常只跑受影响模块测试；只有新冻结身份、公共合同/lock变化或正式发布边界才集中运行全量测试和`git diff --check`。

大型输出目录必须首次生成前不存在；生成器应fail closed，禁止把新旧数据混在同一目录。

## 10. 首例通过后的长期顺序

1. 先让`node-0004`完成正式服务器自然结束、完整readback和三方P/D，关闭首例G6/G8证据缺口。
2. 再用同一`ConvInstanceSpec`入口扩展1×1 shape/K/C组合；已完成的软件candidate不能冒充硬件批准。
3. 覆盖3×3、7×7 Conv及Pool、Add、Quant/Dequant、GAP、MatMul等算子族，每族都保留参数化、layout/inverse和配置绑定测试。
4. 生成typed网络execplan、地址生命周期与分段运行包，按残差块、stage、head、整网顺序合流。
5. 最终逐层保存Golden/NDP/target三组比较，禁止从单算子成功直接跳到整网通过。

## 11. 协作、Git与文档维护

- 修改前检查`git status --short`，保留无关用户改动；禁止未经明确授权使用`git reset --hard`、`git checkout --`或删除恢复点。
- 业务、合同、规则和测试修改应聚焦验证；硬件反馈与扩展工作不得并行改写真值文件。
- 只有用户明确要求推送/发布/同步云端时才允许`git push`；普通完成、本地提交或文档更新不构成推送授权。
- 获得直接推送授权后依次执行：`git status -sb`核对范围、`git fetch origin`、`git rev-list --left-right --count origin/main...HEAD`确认远端无独有提交、非强制`git push origin HEAD:main`、`git ls-remote origin refs/heads/main`核对远端SHA；分叉、认证失败或需要force时立即停止。
- 不覆盖或移动`.agents/conv_full(2).json/.txt`等未跟踪伪代码原件；它们不是正式配置源。
- 确认的新配置/服务器错误先写入对应rule和`plan.md`，再修改实现；完成后把过程压缩迁入`history.md`。
- `agent.md`不保存版本过程；`plan.md`不保存已完成命令和旧决策树；`history.md`控制在1000行以内，优先用表格、身份摘要和archive引用压缩重复细节。
