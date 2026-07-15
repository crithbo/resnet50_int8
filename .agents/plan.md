# ResNet50 INT8 当前执行计划与唯一接手入口

最后更新：2026-07-15

本文件同时承担**唯一接手入口**和**当前执行计划**。不要再寻找或新建独立handoff文件。稳定代码地图见`.agents/agent.md`；配置推导细则见`.agents/rules/算子配置规则.md`。

> `.agents/history.md`只用于定位历史问题、追溯旧结论/提交/父提交和回退点。一般接手和执行当前任务时不要加载；已完成的W0～W5详细计划已归档在那里，不在本文件重复。

## 1. 接手先做三条只读检查

在Local根工作区依次运行：

```powershell
git status --short
.\.venv\Scripts\python.exe tools\sync_repositories.py verify
$env:PYTHONDONTWRITEBYTECODE='1'; .\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

预期：

- 除操作者保留的`.agents/conv_full(2).json`和`.agents/conv_full(2).txt`外，没有未解释改动；文档编辑中的预期差异先核对再继续。
- `CGRA_SIM@53c41e0...`、`ndp-sim-ref@e299b28...`、`NDPFuncModel@1d3181d...`和RTL28静态证据匹配`repos.lock.json`。
- 最近冻结点根仓回归249/249、NDP 19/19；测试数量可随提交增加，验收以零失败为准。

任一项失败时先判断环境、lock、用户改动或业务回归。不要直接重建W3、修改W4批准合同或重生成全部配置。

## 2. 恢复点与冻结包

| 范围 | 提交/标识 | 用途 |
|---|---|---|
| W3业务封版 | `35a4fde106d102b0e165e7eb13d60f7dd980db71` | 正式图、lowering和golden恢复点 |
| W4业务闭环 | `952a96b48416ed2ea1bd2d3068a541ab3dd43625` | 28-slice物理布局和G4恢复点 |
| 首例数值闭环 | `1388dede4aac53a77d02dec0b24db0ad2d35ef1f` | config-bound三档P/D恢复点 |
| 首例硬件交付 | `e9b6492098c2101aa86afd83bf95e8024fa6e8df` | 硬件负责人使用的根仓业务镜像 |
| NDP首例冻结 | `1d3181d832d7a409af779215e4aa590d03bd8ed3` | request schema 0.3与双staging实现 |
| 当前根仓HEAD | 接手时运行`git rev-parse HEAD` | 可能只增加文档/台账，不自动代表新数值版本 |

首例交付目录为`artifacts/w5/hwop-0004-00/hardware_freeze/`：

- freeze ID：`f687debd0215f1d29b6ca94176c4e9cbcf20434d58bce57c430129edb8922d5f`；
- manifest SHA-256：`72e17cb52c2948f86fe6b0e9b2715de57c5404a72a04f9514247f174e8a95550`；
- preflight SHA-256：`8dd0d61bacd0f840f09b038a16180dac4d7408878857d5b10143f684bf2f0c80`；
- 累加JSON SHA-256：`a20641cfcf65068c3ca31d710a0ef45d28a53cbf80d5e246ce54f0de3fe16f2c`；
- requant manifest SHA-256：`4424a6524dcdaaf1933b57875e4f3a1ae7edb11321dd02b692bbed51b82b274f`。

`ADR-009-deepseek-baseline-inheritance.md`受`contracts/hardware_approval.json`的SHA约束；除非执行正式批准迁移，不为文档整理修改它。

## 3. 最终目标与门口径

```text
正式ONNX/输入/initializer
  -> 节点到硬件原子算子lowering和稳定manifest
  -> raw及子步骤golden
  -> 28-slice partition/relayout/packing/address
  -> 单算子JSON和bitstream
  -> 目标数值执行与dump
  -> 网络execplan/数据包
  -> RTL或硬件执行与dump
  -> golden / simulator / hardware逐算子及整网bit-exact
```

一个QLinearConv可拆成首K bias、中间psum、末K requant；模型节点数不能直接当JSON/StartComp数。每一门只认直接证据：

- G5：真实实例配置由正式parser/placement/encoder接受并可复现；
- G6：真正目标数值执行器消费同一配置/bitstream并与golden一致；
- G8：精确冻结包由RTL/硬件执行，原始dump inverse后与golden一致；
- 配置可编码、NDP功能一致、DeepSeek旧配置可上硬件三件事不能互相替代。

## 4. 当前门状态

| 工作包 | 状态 | 当前边界 |
|---|---|---|
| W0/G0 | 通过 | manifest、contract、backend、artifact、cache/resume和mock DAG闭合 |
| W1/G1 | 部分完成，G1未整体通过 | 模型/输入/量化事实、RTL28和配置源已冻结；运行协议仍分阶段闭合 |
| W2/G2 | 通过 | 小Conv软件fixture通过，不外推为目标机规格 |
| W3/G3 | 通过 | 78节点、133个`hw_op`、ORT节点与子步骤golden闭合 |
| W4/G4 | 通过 | `w4_deepseek_hybrid28_resnet50_v1`、七族layout、93边、91条qparam链和批准合同闭合；无clean elaboration声明 |
| W5/G5 | 首例冻结，G5仍false | 真实1×1累加+8份requant JSON正式编码；没有批准完整算子族/目标执行证据 |
| W6/G6 | config-bound两方P/D通过，G6仍false | NDP实际消费配置原文/SHA并三档bit-exact；它不是逐周期/bitstream目标模拟器 |
| W7/G7 | 未开始 | 网络typed execplan、地址计划和Bank_data未闭合 |
| W8/G8 | 未通过 | 冻结包可交硬件；精确配置硬件P/D未取得 |
| W9/G9 | 未开始 | 全算子和整网三方回归未完成 |

## 5. 首个真实1×1冻结边界

实例为`node-0004`、`hwop-0004-00~01`，1×1/stride1，`[16,64,56,56] -> [16,64,56,56]`。已完成：

- `conv_1x1_real.json`采用HIGH-4 `mem/src/dst=4/1/1`、`ping_pong=0`；正式编码46条连接、constraint cost 0。
- `conv_1x1_requant_real/`的8份JSON覆盖64通道；每份正式编码21条连接、constraint cost 0。
- NDP schema 0.3验证manifest、8份原文/SHA、GA常量、slice、16B staging地址、LC `1/9408/2352`和每逻辑输出唯一flush。
- 28个slice各写低/高两个staging D，offset `904400/979664`，再inverse回canonical D。
- 单坐标、首tile150,528元素和全算子3,211,264元素P/D均0 mismatch；canonical P/D SHA分别为`1ec864...`、`2793bbe...`。
- 冻结交付包含339个manifest文件、约41.9 MB：physical A/B/bias/qparams、P/D golden、10份配置、18份bitstream、308个physical region和56个staging输出区。

已删除首例阻塞`B_N2N_TARGET_SELECTOR`、`B_REQUANT_TARGET_NUMERICS`。旧结论“首例缺真实JSON”“仍是schema 0.2”“64通道requant未进入NDP”均已过时。

首例配置侧只保留：

- `B_EXECPLAN_TYPED_TRANSPORT`：network execplan尚不能无损传递逐实例typed qparams和全部目标字段。它不阻塞冻结包手工加载，但阻塞自动生成第二批/整网配置。

精确硬件P/D未取得是W8证据缺口，不再误写成selector、requant或JSON字段阻塞。

## 6. 当前人员拆分，以冻结提交为边界

### A. 硬件协作负责人

只使用根仓`e9b6492...`、NDP `1d3181d...`和freeze ID `f687debd...`，不修改公共生成器：

1. 执行确定性导出，核对freeze ID/manifest SHA；
2. 按`address_table.json`加载physical A/B/bias/qparams与对应JSON/bitstream；
3. 运行真实N2N，保存`P/slice-XX.bin`、`D/slice-XX.bin`；
4. 记录RTL/FPGA版本、加载方式、命令/协议、退出状态和dump hash；
5. 用比较器inverse回canonical P/D，输出首错逻辑坐标、slice、物理地址和三方值。

```powershell
.\.venv\Scripts\python.exe tools\export_conv_1x1_hardware_freeze.py
.\.venv\Scripts\python.exe tools\compare_conv_1x1_hardware_dump.py --freeze-root artifacts\w5\hwop-0004-00\hardware_freeze --dump-root <hardware-dump-root> --output <comparison.json>
```

验收：P、D各3,211,264元素、0 mismatch，实际SHA为`1ec864...`、`2793bbe...`。失败时保留原始dump并以首错定位，不在硬件协作分支改公共配置规则。

### B. 单算子扩展负责人

从同一冻结提交推进，新结果在硬件证据前标`candidate`：

1. 选择第二个正式模型1×1实例，列出shape/qparams/partition与首例的同异；
2. 用同一schema、正式encoder、config-bound NDP和三档P/D形成第二实例闭环；
3. 建shape-family参数测试，覆盖通道/tile/tail/地址/多K阶段，不批量生成53层Conv；
4. 再扩一个真实3×3代表例，验证padding、邻域和weight索引，而非依赖旧写死main。

配置域暂定HIGH-4 `4/1/1`、LOW-28 `28/0/0`；每个新实例都要正式parser、placement、bitstream和数值复核。`ping_pong`由buffer生命周期和邻居接收单独裁决，不随selector机械变化。

### C. 公共合同负责人【串行】

- 实现`B_EXECPLAN_TYPED_TRANSPORT`：从typed contract/manifest把shape、bias、per-channel qparams、rounding、zero-point、saturation、地址和provenance无损传入execplan handler。
- fail-closed拒绝缺字段、截断、资源越界、SHA不一致和旧16-slice路径。
- 公共schema、selector/ping-pong规则、合同、Git集成和全量回归只由这一串行流修改；硬件反馈与扩展候选通过独立报告回灌。

## 7. 从单算子扩到全Conv前的强制门

旧`NDPFuncModel/main_CONV_N2N.py`能跑固定3×3，是因输入组织、padding、weight索引和循环边界共同满足写死假设，并非可泛化入口。全Conv扩展前必须：

- 统一以request/schema驱动`kernel/stride/pad/N/C/H/W/K/tile/tail/qparams/flush`，不复制旧main常量；
- 对1×1与真实3×3各至少一个实例完成单坐标、首tile、全算子P/D；
- 显式表示首K bias、中间psum、末K requant和唯一flush；
- 参数化physical正向/inverse，验证16B对齐、范围不重叠和slice owner可追溯；
- 固化shape-family回归后再考虑53层批量生成。

只有正式编码而无config-bound数值时标`G5 candidate`；只有NDP功能数值而无目标逐周期/bitstream执行，不能升级G6。

## 8. 其余算子与后续阻塞

以下不是首个1×1的阻塞，但会阻止全算子/整网：

- AvgPool：现有模板只覆盖INT32 sum，缺除法/requant/rounding/saturation的目标配置与数值证据。
- MaxPool：需确认UINT8比较、padding sentinel和输出语义，不能沿用有符号假设。
- QLinearAdd：缺两输入独立scale/zp、统一输出requant和完整target数值链。
- MatMul/GEMM：缺正式INT8/INT32 psum、tail、per-channel requant和ResNet head实例闭环。
- sum/归约族：缺跨slice完成协议、末阶段唯一写回和冲突证明。
- W7：缺typed execplan、全网地址/lifetime/alias、StartComp序列和Bank_data。
- W8：缺板级/RTL load/start/wait/dump协议和精确冻结包实跑证据。

W7只在代表性算子合同稳定后开始；W8首例可与候选扩展并行，但不能用旧DeepSeek硬件成功替代当前freeze ID结果；W9必须逐算子再整网比较。

## 9. 强制质量门与停止条件

- INT8/UINT8/INT32默认bit-exact；FP32记录`atol/rtol`。
- 所有physical变换必须有inverse；无法inverse的D不得宣布数值完成。
- 每个JSON保存字段provenance、parsed dump、mapping review、128/64位hash和确定性复现。
- 每次模拟/硬件运行绑定模型、数据、配置、bitstream、代码版本和输出hash。
- 遇到未知字段、截断、资源越界、未解析tail、地址重叠、SHA漂移、无法inverse或P/D不一致，停止横向扩展并登记首错。
- 禁止在精确硬件结果前宣称G8；禁止在目标逐周期/bitstream执行前宣称G6；禁止为文档整理修改受批准hash约束的合同。
- 不改写未跟踪的`.agents/conv_full(2).json`和`.agents/conv_full(2).txt`。

## 10. 计划维护规则

- 本文件只保留当前状态、当前阻塞、下一工作包和必要恢复点。
- 工作包完成后，把过程、提交、验证和被替代结论追加到`history.md`；从本文件删除详细完成步骤，只留门状态摘要。
- 只有定位历史问题才读`history.md`；W4专项错误只读`W4_ARCHIVE.md`。
- 代码入口变化时更新`agent.md`；真实实验证据修正规则时同步更新`rules/算子配置规则.md`和测试。
- 不再建立独立接手文件；接手命令、负责人边界和恢复点直接更新本文件。
