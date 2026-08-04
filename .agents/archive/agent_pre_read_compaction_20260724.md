# 归档：生成前必读资料精简前的项目总览

原标题：`ResNet50 INT8 项目总览与协作约束`。本文件只用于保留 2026-07-24 精简前的
完整有效信息和历史上下文，不再作为当前命令或必读入口。

最后更新：2026-07-24（固化 JSON/服务器测试包两个不可绕过的生成前置门）

本文件保存稳定的项目边界、事实来源和协作约束。当前任务、阶段门、阻塞和下一步只看 `.agents/plan.md`；旧 revision、自定义服务器包路线和失败过程只在 `.agents/history.md` 与 `.agents/archive/` 中追溯，不作为当前命令来源。

## 0. 两个不可绕过的生成前置门

以下要求优先于本文件后续历史路线、旧包说明和临时任务计划。未满足时必须停止生成，
不得用“已经熟悉”“只改一个字段”“沿用旧包”“validator 能通过”代替本轮完整阅读。

### 0.1 算子配置 JSON 生成门

在新建、修改、规范化、派生或批量生成任何算子配置 JSON 前，执行者必须在本轮完整
阅读：

1. `.agents/rules/算子配置规则.md`；
2. `.agents/plan.md` 中目标算子、目标 stage family 和当前 blocker 相关章节；
3. `.agents/rules/` 中所有以目标算子、目标硬件单元或当前缺陷命名的专项规则；
4. 活动 `ndp-sim` 中目标算子的原生 README、`op_json`、已授权参考 JSON，以及
   mapper/encoder/execplan 的直接消费代码；
5. 目标 JSON 会触发的 LC、MSE、Buffer、SA、GA、N2N、CONFIG/生命周期合同。

生成记录必须列出本轮实际读过的文件、适用规则 ID、已知反例和未闭合动态项。只完成
JSON schema、mapper 或 bitstream 校验，不得声明硬件语义正确。若相关规则缺失、互相
冲突或仍为 `CONTRADICTED/TEST_REQUIRED`，必须 fail closed，先补规则/合同或提出最小
裁决实验，禁止猜默认值后继续生成。

### 0.2 服务器测试包生成门

在创建、修改、重打包或发布任何服务器测试包前，执行者必须在本轮完整阅读：

1. `.agents/rules/服务器测试包生成规则.md`；
2. `.agents/rules/算子配置规则.md`；
3. 目标算子的全部专项规则、当前 `.agents/plan.md` 状态及相关失败回传分析；
4. `NDP_copy01/README_HARDWARE_SIM_ENTRY.md` 和活动服务器入口实际消费的
   SCA/SCA_D、execplan、identity、readback/return 合同。

服务器侧交给用户执行的操作最好为一条、最多不得超过三行 shell 命令。包必须提供
单一 fail-fast 入口，自动完成预检、隔离运行、显式 SCA/SCA_D、身份采集、正式回读、
分析和 allowlist-only 回传；不得把复杂参数、手工安装或证据整理转嫁给用户。若三行内
无法安全完成，必须先改进包入口或向用户说明阻塞，不得发布复杂操作说明。

所有服务器测试包一律不得修改任何 `rtl/` 目录内的文件，包括本地
`NDP_copy01/rtl/`、服务器目标 `<NDP root>/rtl/` 及其复制品；不得携带、覆盖、
patch、生成、安装、恢复，也不得通过 Makefile、脚本、软链接或临时副本间接替换编译
所消费的 `rtl/` 目录内容。测试包必须对该目录执行只读身份核验。

`rtl/` 目录外的 testbench、observer、runner、分析器和入口脚本不受上述绝对禁止项
约束，但任何修改仍须符合服务器测试包规则：必须是测试/只读观测用途、最小化、逐文件
登记 diff 和哈希、可关闭且不得驱动或改变 DUT 功能语义。若需要修改 `rtl/` 目录内
文件，必须停止当前路线并重新取得用户明确授权；不得把历史授权扩展到新包。

每个包必须从当前 address-bound JSON 重新建立 planner、encoder、mapping、
bitstream、execplan、SCA/SCA_D provenance，保留独立 golden 和负向门，并禁止复用
已经失败或被否决包的派生产物。外部信号、超时或不完整回传必须按
`CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001` 收集最小证据，禁止返回 build tree
代替 observer/readback。

## 1. 当前工作路线

2026-07-24 当前服务器并行入口为两个 stock-RTL 单命令包：
`gap_int32_mac_stock_rtl_onecmd_v5`（GAP pure-config 六级归约）和
`decode_max_fp32_stockrtl_onecmd_v2`（DeepSeek FP32 reduction-max 控制）。
两者都只执行 `bash PREPARE_AND_RUN.sh /abs/path/NDP_copyXX`，显式绑定
`SCA_CFG/SCA_CFG_D`，使用唯一 install/run/return 身份，关闭波形并仅回传白名单内容。
旧 GAP v4 因 `SCA_D` 缺 `length` 已作废；旧 Decode v1 因未显式 fail-fast 检查
TB include 依赖而未发布。两个当前包都不含、也不写功能 RTL。Decode 包不能替代或
解除 ResNet INT8 MaxPool 的 `int8_max` blocker。

当前路线不是继续修补历史 Conv/MaxPool/DeepSeek 自定义包，而是使用 GitHub 原版 `ndp-sim` 的原生步骤生成服务器消费目录，并用受控单算子对照逐步定位服务器停滞点。`decode_summac_fp32N_fp32N` 已证明当前目录格式可运行；原生 `decode_max_fp32N_fp32N` 又在服务器自然完成并产生 28/28 个与本地 Golden 最低 32-bit 一致的 MSE4 写数据。该结果证明 FP32 max 的公共输出/写回链能够完成，node-0002 MaxPool 的现有停滞继续收敛到 INT8 专属路径。该轮因启动命令遗漏 `+SCA_CFG_D` 而跳过正式 DDR 回读，证据保持 E3，不是 E4。

DeepSeek Decode/Prefill 算子表中没有 2D MaxPool；`decode_max_fp32N_fp32N` 是 FP32 reduction max，不能触发 `int8_max` 分支。直接裁决包使用活动仓库 Git 跟踪的 `jsons/maxpool_config_16_16_16_stride2_padding1.json`，目录为 `ndp-sim/model_execplan/output/native_int8_maxpool16_r1_graph`。该静态配置的 8 个 GA PE 均为 `int8_max`，原生编码均为 `01011`，stream/GA inport ping-pong 均为零；本地结构、SCA、28-slice 数据和独立 UINT8 MaxPool Golden 已通过。服务器 `sim4(2).zip` 又确认正确装载和启动后，28 slice 均有读返回和写地址但写数据为零，无完成/回读/自然退出，约 4.977 ms 后被 SIGHUP 终止。

配套 FP32 对照为 `ndp-sim/model_execplan/output/native_deepseek_fp32_max_control_r1_graph`，使用 Git 跟踪的 `decode_max_fp32N_fp32N.json` 和全新原生 Decode Golden。它只有 FP32 `max`/编码 `00011`，没有 `int8_max`，stream/GA ping-pong 均为零；新 r1/r2 核心文件逐哈希一致。服务器 `sim5.zip` 已确认该新目录在 65 cycles 后完成、执行 28 项正式 D 回读并自然退出。INT8/FP32 A/B 现强力支持 GA `int8_max` 专属路径故障，但精确 RTL 唯一根因仍须服务器身份、内部信号和修复后复测闭合。

默认顺序为：

1. 使用最新版原版 `ndp-sim` 复现一个已通过服务器运行的参考算子类别；
2. 本地当前格式目录自洽且服务器消费文件齐全后，由用户手动加载并执行服务器测试；
3. 参考算子服务器通过后，扩展到最简单的 ResNet50 算子；
4. 最简单 ResNet50 算子通过后，最后处理 Conv。

任何阶段不得自行跳过当前门。2026-07-22 用户明确授权了一个受限例外：在 MaxPool 仍待服务器测试时，生成已有 `conv_1x1_real.json` 的 `node-0004 accumulate-wave-0` 单阶段冒烟包。该授权只覆盖此包，不代表恢复完整 Conv、旧 freeze/v20、requant 或三方比较。

算子配置语义分支的 R0～R4 已完成：活动规则现要求严格 JSON、零 penalty mapping、逐 bit/execplan、SCA、逐请求地址和语义/provenance 闭环；这只建立本地 fail-closed 门，不等于服务器 E4/E5 或 ResNet50 lowering 已完成。R5 若要修改/扩展活动工具链，仍须先由用户明确选择上游修复或项目补丁版本策略。

## 2. 文档职责与事实优先级

- `.agents/agent.md`：稳定路线、目录角色、权威边界与协作约束。
- `.agents/plan.md`：唯一动态执行入口。
- `.agents/rules/服务器测试包生成规则.md`：当前原生服务器消费文件夹的生成、比对和交接规则。
- `.agents/rules/算子配置规则.md`：当前原生算子输入、JSON、数据和配置来源规则。
- `.agents/history.md`、`.agents/archive/`：历史证据和旧路线，只读追溯。

冲突时依次采用：

1. 活动 `ndp-sim` 的原生 README、源码和真实输出；
2. 已通过服务器运行的参考目录，只读用于确认文件类别和服务器成功先例；
3. 用户手动服务器运行得到的原始返回；
4. 本项目规则、计划、合同和历史总结。

项目文档是人工总结，允许并要求在与原生事实冲突时修正。不得为迎合旧规则修改原生仓库输出或增加原生流程没有的步骤。

## 3. 仓库与目录角色

| 路径 | 角色 | 当前约束 |
|---|---|---|
| `C:\Users\15383\Desktop\Codex\project\resnet50_int8\ndp-sim` | 唯一活动的 GitHub 原版工具仓库；当前提交 `ec12424516ae0304228dd2321d4e604fe225e04e` | 只按仓内原生 README/源码使用；身份变化先审计 |
| `C:\Users\15383\Desktop\Codex\project\resnet50_int8\jsons` | 用户确认的服务器可运行参考算子目录 | 用户已允许调用；参与生成时必须记录到来源 manifest，不得伪装成原版产物 |
| `C:\Users\15383\Desktop\Codex\project\resnet50_int8\ndp-sim-ref` | 固定提交的旧参考仓 | 不得导入模块、运行脚本、复制配置或复用最终产物；R5 仅允许把固定提交中的单个 mapping cache 复制到隔离工具副本，并须由当前原生 mapper 对当前图重新计算 exact penalty=0 |
| 根仓其他 `tools/`、`resnet50_pipeline/`、历史 `artifacts/` | 既有自定义开发、正式 W3 数据和历史证据 | 用户已允许调用；必须逐项记录来源，且不得间接读取 `ndp-sim-ref` |
| `NDP_copy01` | 服务器环境/入口的本地参考资料 | 用户已允许调用本地内容；真实服务器装载、启动、等待和回读仍由用户执行或确认 |

`repos.lock.json` 和旧 ADR 可能仍记录过去仓库身份；在当前路线中它们是历史线索，不得覆盖上表。若将来需要修改机器合同，必须单独核实使用方，不能为文档整洁顺手改写。

## 4. 原生 `ndp-sim` 入口

开始生成前必须完整阅读与目标算子直接相关的原生文件：

- `ndp-sim/generate_python_golden/README.md`；
- `ndp-sim/generate_python_golden/README_gen_data.md`；
- `ndp-sim/address_remapping/README.md`（仅在目标算子适用时）；
- `ndp-sim/model_execplan/README.md`；
- `ndp-sim/model_execplan/README_op_json.md`；
- 目标算子的 `model_execplan/op_json/*.json`、所引用的 `jsons/*.json` 和对应数据/relayout 脚本。

原生链的职责边界：数据/golden/relayout 入口负责 tensor 数据；address remapping 只在原生流程声明适用时执行；`model_execplan` 负责地址、配置和执行计划，不能凭空生成 tensor 数据。典型消费输出包括 `install/execplan.txt`、`install/cfg_pkg`、`sca_cfg.json`、`sca_cfg_D.json` 和可选 `Bank_data`，最终以最新版 `ndp-sim` 的当前输出格式和服务器 loader 的真实消费要求为准。

仓库 README 没有写出的服务器装载、启动、等待完成和回读方法不得自行发明；本地自洽检查通过后由用户提供或执行这些服务器步骤。

## 5. 参考目录使用边界

参考目录只允许：

- 枚举相对路径、目录层级、文件类型和大小；
- 计算哈希；
- 在独立生成完成后执行只读字节或结构 diff；
- 确认哪些路径属于服务器运行后结果。

参考目录严禁：

- 复制、移动、链接、解包、转码或以脚本读出后重写文件；
- 作为生成命令的输入目录；
- 从内容中反推并手填 JSON、配置、地址、bitstream、数据、占位文件或指令；
- 用参考文件补齐原生工具未生成的路径。

如果完整生成所需内容在活动 `ndp-sim` 和用户明确提供的独立输入中不存在，必须停止并向用户确认，不能从参考目录“借用”。

## 6. 当前格式可运行性与候选资格

服务器候选必须满足：

- 使用最新版原版 `ndp-sim` 的当前入口和当前输出格式；
- `sca_cfg.json`、`sca_cfg_D.json` 或当前 manifest 引用的每个文件均存在；
- 正式数据由本轮 golden/relayout 流程生成，不从参考目录复制；
- 每个算子的 bitstream 生成真实成功，不能只看顶层脚本返回码；
- 当前格式允许与旧参考目录的文件集合、命名和字节内容不同；
- 命令、输入哈希、活动提交、依赖和原生日志可追溯；
- 原生工具报告错误、关键文件缺失或当前格式引用不自洽时立即失败。

原生工具即使退出码为 0，只要日志出现 placement/bitstream 失败或输出不完整，也不能判成功。

## 7. 当前基线与阶段顺序

当前首个服务器基线为最新版原版 `ndp-sim` 的单原子算子 `decode_summac_fp32N_fp32N`，目录为 `ndp-sim/model_execplan/output/decode_summac_fp32N_fp32N_graph`。它使用本轮固定 seed 合成数据和原生 28-slice/bitstream/execplan/assembler 生成，未从 `jsons/rmsnorm` 提取内容；用户已于 2026-07-22 确认该目录在服务器完整跑通。准确重跑规则及其与原 README/Makefile 的冲突见 `ndp-sim/README_SERVER_PACKAGE_LOCAL.md`。

当前基线通过后：

- 允许继续生成 `node-0002` MaxPool 服务器候选，但仍只使用活动原版 `ndp-sim` 与用户确认的独立输入；
- MaxPool 缺少原生 graph/relayout 等输入时必须向用户确认，不得从旧诊断包补齐；
- 用户已单独授权 `node-0004 accumulate-wave-0` 例外：既有配置只做同哈希别名，正式 W3 数据走当前 layout 生成，控制内容只由活动原版 `ndp-sim` 生成；
- 该例外之外不继续其他 Conv，也不恢复完整 batch/requant/数值链；
- 不恢复自定义 server profile、freeze、barrier、overlay、runner、ZIP 或三方比较链。

原例外目录 `ndp-sim/model_execplan/output/node0004_accumulate_wave0_graph` 已在服务器表现为不自然完成/疑似死锁，现冻结为失败证据：不得覆盖、删除、改名为候选或作为新包输入。独立目录 `ndp-sim/model_execplan/output/node0004_accumulate_wave0_nopp_r1_graph` 继续保留为待测候选。

node-0002 原目录 `ndp-sim/model_execplan/output/node0002_maxpool_wave0_graph` 同样必须保留为失败证据。更新 testbench 后的 28-slice 日志均表现为读返回已发生、写地址请求已发生但写数据为零；本地 RTL 对照把第一处确定性问题定位到 `GA_PE_Inbuffer.sv` 的 `int8_max` pipeline0。精确触发条件不是“tensor 为 INT8/UINT8”，而是 GA PE 使用高三位为 `010` 的 INT8 opcode、接收首个 valid 后仍需在同一执行中接收后续输入；当前原生工具正式暴露的该类 opcode 只有 `int8_max=01011`，活动 53 份原生 JSON 中只有两份 MaxPool 配置使用它。INT8 不进入 `alu_pipeline0_bp_post`，首个 valid 后 `enable/clear` 可永久为零。SA INT8 Conv/GEMM、INT32→UINT8 输出转换和 FP32 max 不经过该缺失分支。服务器包不能替换 RTL，因此 `ndp-sim/model_execplan/output/decode_max_fp32N_fp32N_graph` 不是 node-0002 修复包，而是使用仓库既有 `decode_max_fp32N_fp32N.json`、零 ping-pong、FP32 `max` 的原生诊断对照。它已在服务器 66 cycles 后自然完成，28 个 slice 各有 1 个 MSE4 写数据，最低 32-bit 与本地 D Golden 28/28 一致；这排除了该短 FP32 max 场景中的公共写回链死锁，但不证明 INT8 MaxPool 已修复。完整触发矩阵见 `contracts/ga_int8_pipeline_backpressure_defect_report_20260723.md`。

新的 `native_int8_maxpool16_r1_graph` 是与 node-0002 旧包隔离的小尺寸第二裁决点：它不读取旧失败包或 `ndp-sim-ref`，只复用活动仓库已有静态 JSON，并由活动原生 mapper/encoder/planner/assembler 生成控制内容。2026-07-23 首份 `sim4.zip` 因指向旧目录且主 SCA 不存在而无效；随后 `sim4(2).zip` 正确装载本包并复现“有读返回和写地址、无写数据、不自然完成”。该动态结果加强了 INT8 pipeline0 缺陷解释；在服务器 RTL/filelist 哈希和内部握手信号未归档前，不把静态缺支路写成已经排除所有其他共同原因的唯一根因。

2026-07-24 GAP v7 与 corrected-config + stock-RTL v10 又闭合了第二个、与上述
INT8 pipeline0 正交的 GA 缺陷：`int32_sum=0x0c` 的 transout 归并在深度 2 的
outbuffer occupancy=1 时固定减 2，count 回绕为非法 3；同一分支清 tag 不清 data，
`GA_PE_Inbuffer` 随后又在无 valid guard 时把旧槽作为下一 block 的 C。该问题登记为
`CDA-GAP-GA-ACCUM-STATE-001=CONTRADICTED / B_GAP_GA_ACCUM_STATE`。GAP 输入虽为
UINT8，但 GA 前已转为 INT32，所以它不是前述 INT8 MaxPool 问题；修复两者中的任意
一个不得解除另一个。统一记录见
`.agents/task_records/resnet50_dual_ga_rtl_blockers_and_next_operator_20260724.md`。

下一计算型 ResNet 候选固定为
`node-0077 / hwop-0077-00 DequantizeLinear`（UINT8 `[16,1000]`→FP32）。
它应从授权 `add_dequant` 参考中隔离非 transout 的 FP32 `mac` 仿射分支；原模板
末级 `add` 只用于合并双输入，不属于 standalone Dequantize。目标禁止使用
`int8_max`、`int32_sum` 或任何非 null `transout_last_index`。该选择只表示避开
两个已知 GA blocker；`B_DEQUANT_STANDALONE(_RECIPE)`、typed transport、完整原生
生成链和 E4/E5 仍未关闭，因此当前不得直接称为服务器候选。`View` 虽也规避两个
缺陷，但只是 zero-copy alias，不作为下一计算算子。

## 8. 诊断输出隔离

`ndp-sim/model_execplan/output/silu_withbaseaddr` 与 `ndp-sim/model_execplan/output/maxpool_node0002` 是旧诊断输出，不具备上传资格。后者曾混入从参考目录复制的空占位文件，永久不得作为输入、候选或复现证据。

诊断目录不得通过改名、补文件或重新打包升级为候选。后续正式复现必须使用全新的输出目录。

## 9. 服务器与人工交接边界

本地负责：原生生成、来源记录、目录自洽、逐路径存在性/格式检查和候选说明。

用户负责：把已通过本地自洽检查的原样文件夹加载到服务器指定位置，执行装载/启动/等待/回读命令，并把原始结果传回。

在用户返回真实服务器证据之前，只能声明“本地原生复现一致”，不能声明服务器可运行、自然完成或数值通过。

当前更新后的 `tb_NDP_Top_new_phy.sv` 在没有 `+SCA_CFG_D` 时会从主 SCA 路径派生硬编码的 `sca_cfg_D_softmax.json`。因此所有手动原生包运行都必须同时显式传入 `+SCA_CFG=<本包>/sca_cfg.json` 和 `+SCA_CFG_D=<本包>/sca_cfg_D.json`，并在日志开头核对两条 `Using SCA cfg ... file` 回显。出现 `Cannot open`、`skip matrix readback` 或意外的 `sca_cfg_D_softmax.json` 时只能判定回读失败；即使随后打印 `Simulation completed successfully!` 也不得升级为 E4。不得通过复制或改名伪造 softmax 回读文件。

GAP `hwop-0071-00` 的人工交接目录为
`artifacts/operator_config_validation/r5-server-workloads/gap_hwop0071_sum_graph`。
其结构只参照已由用户确认跑通的本地生成目录
`ndp-sim/model_execplan/output/decode_summac_fp32N_fp32N_graph` 的层级与文件类别，
不复制该参考目录的 payload：根部为 `sca_cfg.json`、`sca_cfg_D.json`、带基地址
graph、解释文件、manifest 及 `config/install/jsons`；16 个有效 slice 各有 A/D 的
原始 `.bin`、128-bit 文本和十进制文本。该目录已通过本地结构、哈希、SCA 引用、
LF 和伴随表示一致性检查，但尚无服务器 E4/E5。

## 10. 协作与文件维护

- 修改前检查工作树并保留无关用户改动；禁止未经明确授权使用 `git reset --hard`、`git checkout --`或删除用户文件。
- 本地文件编辑使用可审计补丁；原生仓库在基线复现阶段原则上只读，任何源码修改都意味着不再是“完全原生”。
- 不能复现的 README 步骤、数据来源或服务器操作必须向用户确认，不自行补充。
- `plan.md` 只保留当前状态和下一步；结束的过程压缩到 `history.md` 或归档。
- 只有用户明确要求时才提交、推送、上传或执行服务器外部操作。

## 11. 全新克隆、依赖与生成物恢复

根仓不嵌入外部仓库。全新克隆后从根目录执行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-resnet50.lock.txt
.\.venv\Scripts\python.exe bootstrap.py
.\.venv\Scripts\python.exe tools\sync_repositories.py verify
```

`bootstrap.py` 读取 `repos.lock.json`，恢复 `CGRA_SIM`、冻结旧参考 `ndp-sim-ref`、`NDPFuncModel` 和当前活动 `ndp-sim` 的完整提交，再验证 HEAD、dirty 状态、远端 URL 与外部证据 SHA。它不跟随分支 tip，也不恢复当前机器上任何未提交的参考仓修改。`NDPFuncModel` mirror 需要协作者具有读取权限；缺权限或提交不可达必须明确失败。

当前活动 `ndp-sim` 的 clean 基线固定为 `ec12424516ae0304228dd2321d4e604fe225e04e`。本机 `README_SERVER_PACKAGE_LOCAL.md` 和 `.gitignore` 差异不属于 bootstrap 内容；`node0004_accumulate_wave0*.json`、graph 和数据也不由外部仓提交提供，但根仓已用冻结的 `conv_1x1_real.json`、W3 数据和 `tools/generate_active_ndpsim_node0004_accumulate_nopp_r1_inputs.py` 确定性重建。必须先在 clean checkout 完成 `sync_repositories.py verify`，再运行该已授权的单算子生成器；生成后活动 `ndp-sim` 出现这些预期未跟踪文件，不得再把 dirty 状态误报为上游提交漂移。

约 951 MiB 的 W3 tensor/golden 按设计不进入 Git。只有目录缺失或模型身份变化时，且目标输出目录预先不存在，才依次运行：

```powershell
.\.venv\Scripts\python.exe tools\prepare_reference_model.py
.\.venv\Scripts\python.exe tools\run_onnx_golden.py artifacts\reference_model\resnet50-v1-12-int8.onnx artifacts\reference_model\input_batch16.npy artifacts\w3\golden_batch16
.\.venv\Scripts\python.exe tools\run_subop_golden.py artifacts\reference_model\resnet50-v1-12-int8.onnx artifacts\w3\golden_batch16 artifacts\w3\subop_batch16
```

已有产物优先用 manifest/hash 验证，不重建覆盖。两个小型 W3 图元数据和 R3 mapping evidence bundle 由 Git 跟踪；`NDP_copy01` 的 RTL/VCS 镜像不进入 Git，服务器 RTL 身份与运行/回读命令仍必须另行提供或机械核验。

## 12. R5 项目补丁版本（2026-07-23 起生效）

用户已明确选择项目补丁版本策略，替代此前“修改活动 `ndp-sim` 前等待授权”的暂停条件。活动 checkout 仍固定为
`ndp-sim@ec12424516ae0304228dd2321d4e604fe225e04e` 且只读；修复只在临时副本或显式物化副本中应用。正式身份、源哈希、四项替换和目标 6144-row profile 由
`contracts/ndp_patch_toolchain_v1.json` 锁定，决策见 `.agents/decisions/ADR-016-hash-bound-project-patchset-and-r5-closure.md`。

物化独立副本：

```powershell
.\.venv\Scripts\python.exe tools\materialize_patched_ndp_toolchain.py outputs\ndp-toolchain-6144-v1
```

生成 patched mapping/execplan evidence 时必须显式传入：

```text
--patchset-manifest contracts/ndp_patch_toolchain_v1.json
```

已发布的小型 R5 evidence 目录由根仓跟踪；新克隆在 `python bootstrap.py` 后可直接校验。当前机械总览为
`contracts/resnet50_project_closure.json`，重建命令是：

```powershell
.\.venv\Scripts\python.exe tools\build_project_closure.py
.\.venv\Scripts\python.exe -m unittest tests.test_project_closure -v
```

当前边界必须保持：本地 W3 独立公式为 78/78，typed lowering 为 133/133，网络软件审计为 93 条边、两个场景；正式 ResNet50 目标配置仍为 0/133，E4/E5 均为 0。`configs/` 中既有候选不得因文件存在而升级为正式配置。下一步只允许按 blocker 闭合代表算子，再取得真实服务器 E4、重复 E5 后推广；不得直接拼装并宣称整网完成。

2026-07-23 本地全量回归最终结果为共 460 项，443 项通过、17 项环境跳过、0 失败，测试框架耗时 999.012 秒（外层命令墙钟约 1005.3 秒）。该结果包含 v20 Conv 硬件包的完整生成、flat/page-aligned `ExecutionPlan` parser 合同、动态 dump-contract 回读和 P/D 比较，以及 typed lowering/E4-E5 交接、本轮 resolution overlay、MaxPool/node0004 候选包与地址绑定/legacy mapping 正负测试；它只证明本地链未回归，不提升任何 stage 的 E4/E5 等级。

R5 typed lowering 的正式机器入口是 `contracts/resnet50_r5_lowering_bundle.json`：133/133 request 完整，但 0/133 允许正式 target config emission。E4/E5 交接状态是 `contracts/resnet50_e4e5_handoff_readiness.json`；10 种代表当前 0/10 ready。真实服务器命令只允许填写到通过校验的 `resnet50-server-execution-protocol-v1`，并由 `tools/run_e4e5_server_protocol.py` 按 load/start/wait/readback 原样执行；不得修改模板状态或填占位符来绕过入口缺失。

本地小型 evidence 的重建/校验入口如下；所有输出目录必须使用全新路径，已有发布目录只校验、不覆盖：

```powershell
$py = '.venv\Scripts\python.exe'

# 16×16 UINT8 MaxPool：语义合同→严格副本→固定 cache 原生零代价复验
& $py tools\build_maxpool_zero_padding_contract.py
& $py tools\materialize_strict_operator_config.py `
  ndp-sim\jsons\maxpool_config_16_16_16_stride2_padding1.json `
  <fresh-maxpool-strict-dir> `
  --expected-source-sha256 624d675ddde6f386474289d473d1c69559691794f3c1ea775dfc99325cc8f072 `
  --operator-padding-contract contracts\maxpool_uint8_zero_padding_contract.json
& $py tools\generate_operator_config_mapping_evidence.py `
  <fresh-maxpool-strict-dir>\config.json <fresh-maxpool-mapping-dir> `
  --patchset-manifest contracts\ndp_patch_toolchain_v1.json `
  --frozen-mapping-cache ndp-sim-ref\bitstream\config\mapping_cache\dc65063f38e8722f.json

# node-0004：严格副本→最终地址绑定→mapping→typed semantic→双跑 execplan
& $py tools\generate_active_ndpsim_node0004_accumulate_nopp_r1_inputs.py
Push-Location ndp-sim\generate_python_golden
& ..\..\.venv\Scripts\python.exe ..\model_execplan\main.py `
  model_execplan\op_json\node0004_accumulate_wave0_nopp_r1_graph.json
Pop-Location
& $py tools\materialize_strict_operator_config.py `
  ndp-sim\jsons\node0004_accumulate_wave0_nopp_r1.json `
  <fresh-node0004-strict-dir> `
  --expected-source-sha256 0706ad05233d03f43b800797b1be40390c718f58d34c13df89a0208d75bba45e
& $py tools\materialize_address_bound_operator_config.py `
  <fresh-node0004-strict-dir> `
  ndp-sim\model_execplan\output\node0004_accumulate_wave0_nopp_r1_graph\node0004_accumulate_wave0_nopp_r1_graph_withbaseaddr.json `
  <fresh-address-bound-dir>
& $py tools\generate_operator_config_mapping_evidence.py `
  <fresh-address-bound-dir>\config.json <fresh-node0004-mapping-dir> `
  --patchset-manifest contracts\ndp_patch_toolchain_v1.json
& $py tools\build_node0004_nopp_semantic_contract.py `
  --mapping-bundle <fresh-node0004-mapping-dir> --output <fresh-semantic-contract.json>
& $py tools\generate_operator_config_execplan_evidence.py `
  ndp-sim\model_execplan\output\node0004_accumulate_wave0_nopp_r1_graph\node0004_accumulate_wave0_nopp_r1_graph_withbaseaddr.json `
  <fresh-node0004-execplan-dir> --mapping-bundle op0=<fresh-node0004-mapping-dir> `
  --semantic-contract <fresh-semantic-contract.json> `
  --patchset-manifest contracts\ndp_patch_toolchain_v1.json

& $py tools\build_r5_lowering_bundle.py
& $py tools\build_project_closure.py
& $py tools\build_e4e5_handoff_readiness.py
```

上述 MaxPool/node-0004 产物均是本地候选证据。正式 target config 仍为 0/133，E4/E5 仍为 0；只有用户提供真实服务器协议、RTL 身份和两轮原始回读后才能升级。

## 2026-07-23 R5 本地闭合、候选包重建与服务器交接

当前机器真值由以下四份合同共同给出：

- `contracts/resnet50_r5_resolution_overlay.json`：只按 stage/scope/hash 消解历史 blocker，不改写 `typed_config_parameter_contract.json`；
- `contracts/resnet50_r5_lowering_bundle.json`：133 个历史 request/hash 保持不变，另给出 effective resolution；当前 2/133 本地 resolved，其中 MaxPool 可生成配置、View 为零拷贝；
- `contracts/resnet50_project_closure.json`：本地闭合及两个 matrix-complete 候选包的总表；
- `contracts/resnet50_e4e5_handoff_readiness.json`：10 类代表、2 个本地 server-test candidate、0 个正式包、0 次正式 E4/E5。

生成目录必须使用全新路径。已存在的 evidence/candidate 只校验，禁止覆盖。完整 node-0002 MaxPool 重建顺序为：

```powershell
$py = '.venv\Scripts\python.exe'

& $py tools\build_maxpool_zero_padding_contract.py `
  --source-config ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json `
  --output contracts/maxpool_node0002_zero_padding_contract.json
& $py tools\materialize_strict_operator_config.py `
  ndp-sim\jsons\maxpool_config_16_112_112_stride2_padding1.json `
  configs\native_ndp_sim\maxpool_config_16_112_112_stride2_padding1_strict_v1 `
  --expected-source-sha256 a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1 `
  --operator-padding-contract contracts\maxpool_node0002_zero_padding_contract.json
& $py tools\generate_maxpool_node0002_guarded_wave0.py `
  artifacts\operator_config_validation\r5-maxpool-node0002-guarded-wave0-v1
& $py tools\materialize_maxpool_guarded_address_seed.py `
  artifacts\operator_config_validation\r5-maxpool-node0002-guarded-wave0-v1 `
  configs\native_ndp_sim\maxpool_node0002_guarded_wave0_address_seed_v1.json
& $py tools\materialize_address_bound_operator_config.py `
  configs\native_ndp_sim\maxpool_config_16_112_112_stride2_padding1_strict_v1 `
  configs\native_ndp_sim\maxpool_node0002_guarded_wave0_address_seed_v1.json `
  configs\native_ndp_sim\maxpool_config_16_112_112_stride2_padding1_guarded_address_bound_v2
& $py tools\generate_operator_config_mapping_evidence.py `
  configs\native_ndp_sim\maxpool_config_16_112_112_stride2_padding1_guarded_address_bound_v2\config.json `
  artifacts\operator_config_validation\r5-patched-mapping-evidence\maxpool-node0002-guarded-address-bound-v2 `
  --seed 20260723 --heuristic-restarts 2 `
  --patchset-manifest contracts\ndp_patch_toolchain_v1.json `
  --frozen-mapping-cache artifacts\operator_config_validation\r5-patched-mapping-evidence\maxpool-node0002-strict-address-bound-v1\mapping_cache\c55c0de0dc1460f4.json
& $py tools\build_r5_resolution_overlay.py
& $py tools\build_r5_lowering_bundle.py
& $py tools\build_maxpool_node0002_semantic_contract.py
& $py tools\generate_operator_config_execplan_evidence.py `
  artifacts\operator_config_validation\r5-maxpool-node0002-guarded-wave0-v1\graph.json `
  artifacts\operator_config_validation\r5-patched-execplan-evidence\maxpool-node0002-guarded-wave0-v5 `
  --mapping-bundle op0=artifacts\operator_config_validation\r5-patched-mapping-evidence\maxpool-node0002-guarded-address-bound-v2 `
  --semantic-contract contracts\maxpool_node0002_guarded_wave0_semantic_contract.json `
  --patchset-manifest contracts\ndp_patch_toolchain_v1.json
& $py tools\build_maxpool_node0002_server_candidate.py
```

node-0004 的当前语义合同依赖最新 lowering，因此 lowering/overlay 变化后必须重新执行 `tools/build_node0004_nopp_semantic_contract.py`，再生成新的 execplan evidence 和 `tools/build_node0004_nopp_r1_server_candidate.py`。候选仍只是单阶段活性冒烟。

最终本地状态重建与定向校验：

```powershell
& $py tools\build_r5_resolution_overlay.py
& $py tools\build_r5_lowering_bundle.py
& $py tools\build_project_closure.py
& $py tools\build_e4e5_handoff_readiness.py
& $py -m unittest `
  tests.test_r5_resolution_overlay `
  tests.test_r5_lowering_bundle `
  tests.test_maxpool_node0002_semantic_contract `
  tests.test_maxpool_server_candidate `
  tests.test_node0004_server_candidate `
  tests.test_project_closure `
  tests.test_e4e5_handoff -v
```

真实服务器命令只能取自 `contracts/resnet50_e4e5_handoff_readiness.json` 的两个 command template，并替换为用户批准的 protocol 和全新返回目录。run1/run2 必须分别执行；候选包不得改名为 formal package，未返回原始 readback 时不得提升 E4/E5。

## 2026-07-23 两个配置目录的用户授权正确性

用户明确确认根仓 `jsons` 中的参考配置，以及 `ndp-sim/jsons` 中云端固定版本原生
自带且未改变的算子配置，可以认为正确并经过测试。该授权由
`.agents/decisions/ADR-021-scope-config-authority-by-upstream-provenance.md` 和
`contracts/operator_config/operator_config_authority_v1.json` 固化。当前 Git 逐文件
分类是：根仓 12 份用户参考配置，以及
`uSFrances/ndp-sim@ec12424516ae0304228dd2321d4e604fe225e04e` 原生跟踪且未改变的
53 份配置，共 65 份按正确、高强度参考基线处理。

`ndp-sim/jsons/node0004_accumulate_wave0.json` 和
`node0004_accumulate_wave0_nopp_r1.json` 是固定提交之外的项目后加文件，没有通过
测试，不属于上述授权。它们只能用于身份审计、失败分析和有边界的静态假设，不能用于
解除 Conv 配置正确性 blocker。以后必须依据固定提交路径和 Git 内容身份分类，不能只
看所在目录或文件名。

这 65 份授权配置可直接用于字段语义、LC/PE/stream/buffer/SA/GA 拓扑、ScheduleIR、
规则提炼、已知配置反向复现和同族候选种子，不再要求先为每一份配置找到仓内原始服务器
日志。历史 E3、负回执和无效运行继续保留，但只描述本项目某次封装或执行，不得据此
撤销源参考配置正确性，除非存在直接绑定配置语义错误的新反证。

必须继续区分参考配置正确性和派生配置放行：新 shape、地址、常量、拓扑、跨 stage
状态及 ResNet50 候选仍须通过严格 schema、mapping、bitstream、execplan、逐请求地址、
独立 golden 和服务器 E4/E5。当前正式 target config 及 E4/E5 数量不因本授权自动增加。

## 2026-07-23 stage→算子 JSON 完整体系

活动机器入口为
`contracts/operator_config/stage_config_system_v1.json`，决策见 ADR-022。该合同必须
覆盖 lowering bundle 的全部 133 个 request 和 10 个 family，并为每个 stage 保存
request/geometry/parameter-schema hash、shape 变体、规则层、candidate blocker 与
formal blocker。

固定流水线是：

```text
typed request → family rule → logical ScheduleIR → slice/wave/buffer schedule
→ numeric kernel/constants → cross-stage CONFIG → strict address-unbound JSON
→ address/mapping/bitstream/execplan/SCA → independent golden + E4/E5
```

当前只允许两个 address-unbound candidate emitter（精确 MaxPool 与精确 GAP）和一个
View zero-copy binding；130 个 stage 仍 fail closed，formal 仍为 0。GAP 的精确上游
模板已经严格物化；`hwop-0071-00` 的 `x_zero_point=0` 编译期特化、每 slice 一份完整
sample、2048 channel 输出覆盖和 terminal `last_index=0` 已分别关闭
`B_EXECPLAN_TYPED_TRANSPORT`、`B_GAP_CENTERED_SUM`、`B_SUM_CROSS_SLICE` 与
`B_SUM_COMPLETION`。候选位于 `configs/stage_codegen/hwop-0071-00-v1`，仍是
address-unbound、非 formal，不能替代 mapping/execplan/SCA 或硬件 E4/E5。

DeepSeek 规则机器入口为：

- `contracts/operator_config/deepseek_stage_ir_crosswalk_v1.json`：47 份授权模板、
  87 个 graph、158 次 stage 出现和 40 种 stage type 的精确交叉索引；
- `contracts/operator_config/deepseek_reduction_rules_v1.json`：local/remote reduction、
  terminal 与 GAP 跨 slice 判定；
- `contracts/operator_config/deepseek_primitive_rules_v1.json`：22 份 GA elementwise、
  6 份 SA GEMM/GEMV 及 local/ring N2N 耦合。

这些入口允许复用结构规则，不允许把 FP16/FP32 的 SA、N2N 或 GA 数值直接外推为
ResNet INT8 Conv、bias/psum 或量化配置。精确模板复放、结构迁移和派生 target 是三个
不同证据等级。

活动 `ndp-sim/model_execplan` 是已支持算子的唯一执行实现：原生 `json_loader.py`
负责 graph/shape/source/slice 解析，`control_registers.py` 的 48 个 handler 负责
shape-driven 控制字段，且覆盖全部 40 种 graph-referenced DeepSeek stage type；
`output_writer.py`、`pipeline.py` 继续负责模板 patch、地址、bitstream、execplan 和 SCA。
本项目的 DeepSeek 三份合同只做索引、provenance、差异审计和 ResNet 迁移边界，不得
发展为第二套 graph parser、control-register generator 或 execplan pipeline。

对 native 已支持的精确 op type，必须生成/适配原生 op_json 并调用
`ndp-sim/model_execplan/main.py`。对 native 未支持的 ResNet type，若确需新增 handler，
只能通过哈希锁定补丁在隔离 `ndp-sim` 副本中扩展原生 registry，再走原生 pipeline；
不得在 `resnet50_pipeline` 平行实现相同控制字段和 bitstream/execplan 功能。决策见
ADR-024。

GAP padding 合同必须直接绑定 `contracts/typed_config_parameter_contract.json`，不能
绑定 lowering bundle；否则 overlay 引入该合同后会形成哈希循环。若 typed stage、
上游源配置、authority 或 RTL padding 证据改变，必须重新生成 GAP 合同，并在全新目录
重新 strict materialization 后才能更新发布目录。

日常重建顺序：

```powershell
$py = '.venv\Scripts\python.exe'
& $py tools\build_deepseek_stage_ir.py
& $py tools\build_deepseek_reduction_rules.py
& $py tools\build_deepseek_primitive_rules.py
& $py tools\build_gap_sum_padding_contract.py
& $py tools\build_r5_resolution_overlay.py
& $py tools\build_r5_lowering_bundle.py

# lowering 文件身份变化后，MaxPool/node0004 的 semantic、execplan 和 server candidate
# 收据也必须从全新目录重建；实际 execplan hash 不得无解释改变。

& $py tools\build_conv_stage_schedule_evidence.py
& $py tools\build_requant_stage_semantics_evidence.py
& $py tools\build_stage_config_backend_catalog.py
& $py tools\build_stage_config_system.py
& $py tools\build_project_closure.py
& $py tools\build_e4e5_handoff_readiness.py
```

下一开发顺序固定为：GAP 地址绑定/mapping/execplan/SCA，Requant 全 batch/wave，GA
affine 公共分支，最后 SA INT8 Conv/MatMul。参考配置正确性可以作为精确规则证据，
但任何派生变化仍必须独立通过严格链和 E4/E5。

## 2026-07-23 GAP、Conv、Requant 原生包授权与边界

用户已明确授权继续完成 GAP 原生包，并把 Conv accumulate 与 Requantize 作为下一
优先族推进；先前“只允许 node-0004 wave-0、不得恢复 full batch/requant”的临时限制
在本范围内失效。活动 `ndp-sim@ec124245...` 仍保持只读，所有新增 handler 只允许通过
哈希锁定的项目 patchset 安装到隔离副本。

当前必须区分三种状态：

- GAP sum：完整原生包、mapping、双跑 execplan、SCA、逐请求地址和矩阵包已闭合，
  只待服务器 E4/E5；
- node-0004 Requantize：完整 3-wave×8-shard 原生包及独立 W3 数值重放已闭合，
  只待服务器 E4/E5；它使用独立 W3 INT32 accumulator，不声称包含前驱 Conv 执行；
- node-0004 Conv accumulate：完整 `[28,28,8]` 三波、16 样本、矩阵、mapping、
  双跑 execplan、SCA 和逐请求地址已闭合，但当前 JSON 是项目后加配置，仍保留
  `B_CONV_INT8_SA`、`B_CONV_BIAS_PSUM` 和布局批准/服务器门，不能称为只待硬件的
  已批准配置，也不能推广到其余 Conv shape。

Conv D 是 HWC16 INT32，而当前独立 Requant A 是紧凑 HWC8 INT32。二者在同一
execplan 中直接交接还需要显式证明每个 K8 half 的基址偏移、64-byte 空间 stride、
slice owner 和 CONFIG/lifetime；现有 graph source schema 不表达子 tensor byte
offset。禁止用两个独立包来自同一 W3 tensor 这一事实冒充零拷贝串联证明。

大型 transport 与最终 server candidate 仍由 `.gitignore` 排除；它们不是克隆后天然
存在的文件。小型 patchset、strict JSON、mapping/execplan 收据和语义合同可提交，
忽略的矩阵包必须按下列入口在 fresh 路径重建：

```powershell
$py = '.venv\Scripts\python.exe'

# GAP transport；mapping/execplan 收据存在后组装最终包
& $py tools\generate_gap_hwop0071_native_transport.py
& $py tools\build_gap_hwop0071_server_candidate.py

# node-0004 Conv 三波 transport/config；随后使用三个 wave config 分别运行
# generate_operator_config_mapping_evidence.py，使用 op_w0/op_w1/op_w2 三个
# mapping bundle 运行 generate_operator_config_execplan_evidence.py。
& $py tools\generate_node0004_conv_native_inputs.py
& $py tools\build_node0004_conv_server_candidate.py

# node-0004 Requant transport/config；随后对 3×8 个 config 分别运行 mapping，
# 使用 op_w{0..2}_s{00..07} 的 24 个 bundle 运行 execplan evidence。
& $py tools\generate_node0004_requant_native_inputs.py
& $py tools\build_node0004_requant_server_candidate.py
```

两个 `build_*_server_candidate.py` 都要求相应 mapping 与 execplan evidence 已存在，
并拒绝覆盖旧目录；重建时应使用新版本目录或先由人工确认处理旧生成物。不得把
`r5-server-candidates` 中约数百 MB 的矩阵文本强制纳入 Git。

## 2026-07-23 服务器探针包与精简回传规则（probe_v5 基线）

此后测试分析阶段的服务器探针包统一沿用 `gap_hwop0071_sum_probe_v5` 的外层格式。
这里的“沿用 v5”指目录结构、单命令入口、身份采集、隔离安装和只读 observer，不继承
v5 默认开启 FSDB、归档完整运行树和重复复制波形的做法。本节覆盖本文件及
`.agents/rules/服务器测试包生成规则.md` 中旧的“不得加入 runner/ZIP”限制，但只覆盖
测试分析用的外层探针与回传封装；`workload/` 内的服务器消费内容仍必须保持冻结、原样
和可追溯，observer 不得改变功能 RTL、激励、时序或完成条件。用户在 2026-07-24
另行批准的 `repair_v9` 功能 RTL 修复测试包是下文唯一登记例外，不得据此外推到其他
RTL、算子或版本。

### 上传包固定格式

每个新版本使用全新版本号和全新运行目录，不覆盖服务器已有安装。顶层固定包含：

```text
PREPARE_AND_RUN.sh
README.md
TEST_PACKAGE_MANIFEST.json
workload/
tb_probe/
```

- `PREPARE_AND_RUN.sh` 是唯一入口，调用形式保持
  `bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX`；脚本完成身份采集、只读
  observer 安装、编译/运行、回传筛选与压缩。
- `workload/` 保存本轮冻结的 SCA、SCA_D、execplan、cfg_pkg、矩阵和必要说明；
  逐文件大小与 SHA-256 写入 manifest。禁止从旧失败包或服务器运行残留补文件。
- `tb_probe/` 只允许放只读 observer 及其安装说明。任何功能 RTL 或会改变激励、
  backpressure、完成条件、超时条件的 testbench 改动都不得混入探针包。
- `README.md` 必须给出唯一命令、预期新建目录、预期返回 ZIP 名、失败时仍会保留的
  最小证据，以及波形默认关闭的声明。
- `TEST_PACKAGE_MANIFEST.json` 必须记录 schema/version、包 SHA、workload 与 observer
  身份、允许替换的唯一 TB 路径、服务器基目录参数、运行目录名和回传大小预算。

运行流程固定为：

```text
pre_install 身份采集
→ 安装到全新隔离目录
→ post_install 身份采集与安装校验
→ 显式绑定 SCA/SCA_D 并运行
→ 保存退出状态
→ post_run 身份采集
→ 构建白名单回传目录
→ 校验并生成回传 ZIP/SHA-256
```

`+SCA_CFG` 与 `+SCA_CFG_D` 必须显式指向同一轮 `workload/`；不得依赖 testbench 默认
文件名。`server_identity_post_run.json` 必须在仿真结束后重新采集，再开始打包；禁止
把 pre/post-install 身份或前一版本的 post-run JSON 复制成当前结果。

### 波形与高频日志默认策略

每次运行必须在命令行显式关闭所有已知波形开关，包括
`DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0`，不能只依赖 Makefile 默认值。文本事件能够
裁决时不得生成 FSDB/VCD/VPD。

只有当前分析问题确实无法由限量文本事件裁决时，才允许启用一次受限波形。启用前必须
在 manifest/README 中写明 `evidence_need`、目标信号、起止条件和大小预算；波形必须
限制时间窗与信号范围，回传中只保留一份。不得同时在运行根、`sim_results/` 和
`archive/` 重复保存同一波形。

observer 与日志输出必须按目标 slice、目标 MSE/GA 和事件类型限流。默认只采集能够回答
当前假设的 req/rdata/wdata、CONFIG/exec/completion、STALL/heartbeat 和正式回读；
不得默认开启所有 slice 的 `bank_frame`、`nrm_buf_read/write`、逐周期内部状态或其他
高频日志。超时或外部终止仍须打包已落盘的最小文本证据。

### 服务器直接回传 ZIP

服务器脚本运行结束后必须直接生成 `<install_name>_return.zip` 和对应
`<install_name>_return.zip.sha256`。操作者只需回传这两个文件，不应再手工压缩整个
运行目录。回传目录只能按白名单从本轮 fresh 运行目录复制，默认允许：

- `return_observer/return_observer.log`；
- `return_observer/server_identity_pre_install.json`、
  `server_identity_post_install.json`、`server_identity_post_run.json`；
- `return_observer/observer_install_report.json` 和 `run_exit_status.txt`；
- `logs/compile.log`、`logs/sim.log`；
- 当前 manifest 明确指定的目标 slice/MSE/GA 限量日志；
- `sca_cfg.json`、`sca_cfg_D.json` 的副本或其完整身份记录；
- SCA_D 指向的正式回读文件，以及本轮合同明确要求的其他小型裁决证据；
- `RETURN_MANIFEST.json`。

`RETURN_MANIFEST.json` 必须列出运行命令、退出码、包/安装身份、三阶段身份文件、每个
回传文件的相对路径/大小/SHA-256、ZIP 前后总大小、波形是否启用及其理由。文件缺失时
写入 manifest 的 `missing_required` 并使脚本返回非零，但仍尽量产出可诊断的最小 ZIP。

默认禁止进入回传 ZIP：

- `csrc/`、`simv`、`simv.daidir/`、`.sdb`、`.so`、`.a` 等 VCS 编译/构建树；
- 完整运行根目录、完整 `archive/`、完整 `sim_results/` 或上一轮结果；
- 默认关闭的 FSDB/VCD/VPD，以及任何内容相同的重复副本；
- 非目标 slice 日志、未在 manifest 声明的高频日志和可由源包重建的矩阵/bitstream；
- 上传包 ZIP、回传 ZIP 自身或其他嵌套压缩包。

普通诊断回传的默认预算为 ZIP 不超过 16 MiB、解压后不超过 32 MiB、单个文本日志不超过
8 MiB。超过任一预算必须由当前分析所需的明确证据项解释，并在
`TEST_PACKAGE_MANIFEST.json` 与 `RETURN_MANIFEST.json` 同时记录批准理由和新预算；
不能仅因“可能以后有用”放宽。正式回读本身超过默认预算时，预算可按 SCA_D 声明的
预期文件集合与精确字节数上调，但仍不得夹带构建树、重复波形或无关日志。

压缩完成后脚本必须重新读取 ZIP 条目并 fail closed：检查必需文件、路径无越界、无禁止
后缀/目录、无重复内容、三阶段身份属于当前版本、实际大小未超预算，且 ZIP 的 SHA-256
已写出。该校验未通过时不得把整棵运行目录作为替代回传包。

### 用户授权功能 RTL 修复测试包例外（repair_v9）

只有用户明确要求“修改已知问题并生成下一版本测试包”时，才允许生成登记的功能 RTL
repair 包。每次生成前必须完整阅读：

- `.agents/rules/算子配置规则.md`
- `.agents/rules/GAP_probe_v7_validator_rules.md`
- `.agents/rules/GAP_repair_candidate_rules.md`
- `.agents/rules/服务器测试包生成规则.md`
- 涉及原生 execplan 时的 `ndp-sim-ref/model_execplan/readme.md`

固定安全与发布规则：

1. v7 包和原始回传永久只读；修复使用全新 config、mapping、execplan、install、
   run、return 和 ZIP 身份，禁止原地覆盖。
2. 配置改动后必须从地址绑定配置完整重建 planner、encoder、bitstream、execplan、
   SCA 和 SCA_D；文件哈希偶然与旧版相同不能代替本轮重建 provenance。
3. 本地 `NDP_copy01` 仍是只读 preimage。功能 RTL 只放在包内 `rtl_patch/` 的精确
   allowlist；安装前逐文件校验 canonical preimage hash，先做逐字节备份，再安装、
   隔离重编译、运行、采集 post-run、恢复并采集 post-restore。EXIT trap 必须尝试
   恢复；恢复失败时该轮必须失败。
4. `valid=true`、结构检查或自然完成都不是语义发布。GAP 包必须显式执行
   `CDA-GAP-D-READBACK-COVERAGE-001`、
   `CDA-GA-OUTBUFFER-OCCUPANCY-001`、
   `CDA-GA-INVALID-SLOT-ISOLATION-001`、
   `CDA-GA-CROSS-BLOCK-INIT-001`、
   `CDA-MSE4-MONITOR-EVIDENCE-001` 和
   `CDA-SERVER-FOCUSED-IDENTITY-001`。本地只能关闭静态前置门；正式 E4 需要
   全部 D readback 与独立 golden，E5 还需要独立重跑。
5. 回传继续采用直接 ZIP+sidecar 和 allowlist；必须包含 install/restore receipt、
   pre/post/post-run/post-restore 身份、两份 SCA、正式 D readback、限量 observer
   与 compile/sim 日志。波形、build tree、完整 run/archive 和嵌套压缩包默认禁止。
6. 本轮唯一登记实例为
   `gap_hwop0071_sum_repair_v9.zip`，SHA-256
   `4344b4166540482d12256b1a5893b8e3dbb512a74a7d735237de0ae2bf873864`，
   3,297,090 bytes、125 entries。v8 因复用了 v7 execplan/SCA，只是未发布草案，
   禁止上传或运行。

### “修正配置 + 服务器原始 RTL”裁决包

当用户要求先裁决配置修复本身时，必须生成与 repair 包不同的新身份，并遵守：

1. 包内功能 RTL 文件数必须为 0；禁止携带 `rtl_patch/`，禁止调用 repair installer，
   禁止写入、备份或恢复服务器 `rtl/` 下的任何功能文件。
2. 允许安装位于 `rtl/` 外的只读 TB observer，但必须说明该动作不改变 DUT 功能
   语义，并把 TB/observer 身份纳入 pre/post/post-run/final 采集。
3. 必须证明实际服务器整棵 RTL tree 和 focused RTL 在所有阶段逐字节稳定；focused
   集必须包含 `GA_PE_Inbuffer.sv`、`GA_PE_Outbuffer.sv`。服务器不必与本地或
   GitHub 绝对相同，但本轮使用的服务器 RTL 不得发生变化。
4. 若配置语义未再次改变，可以复用已有完整重建且哈希绑定的 corrected workload，
   以保持单变量裁决；必须记录原始完整重建 provenance。若任何配置字段改变，则必须
   重新完整生成 planner、encoder、mapping、bitstream、execplan、SCA/SCA_D。
5. stock-RTL 包不伪造 repair install/restore receipt，而要强制生成专用
   `stock_rtl_identity_receipt.json`。动态 GAP 门和 `candidate_release=false /
   E2_LOCAL_ONLY` 边界不变。
6. 当前登记实例为
   `gap_hwop0071_sum_configfix_stockrtl_v10.zip`，SHA-256
   `86cd391a4178258bd9f4068583db979f3ddd74f737841a3ca41f07bd9f71e907`，
   3,291,066 bytes、122 entries。只允许回传同身份的 ZIP 与 sidecar。
