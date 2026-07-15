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
- `CGRA_SIM@53c41e0...`、`ndp-sim-ref@e299b28...`、`NDPFuncModel@e35b24a...`和RTL28静态证据匹配`repos.lock.json`。
- 当前E1冻结点根仓回归258/258、NDP 20/20；测试数量可随提交增加，验收以零失败为准。

任一项失败时先判断环境、lock、用户改动或业务回归。不要直接重建W3、修改W4批准合同或重生成全部配置。

## 2. 恢复点与冻结包

| 范围 | 提交/标识 | 用途 |
|---|---|---|
| W3业务封版 | `35a4fde106d102b0e165e7eb13d60f7dd980db71` | 正式图、lowering和golden恢复点 |
| W4业务闭环 | `952a96b48416ed2ea1bd2d3068a541ab3dd43625` | 28-slice物理布局和G4恢复点 |
| 首例数值闭环 | `1388dede4aac53a77d02dec0b24db0ad2d35ef1f` | config-bound三档P/D恢复点 |
| 首例硬件交付 | `e9b6492098c2101aa86afd83bf95e8024fa6e8df` | 硬件负责人使用的根仓业务镜像 |
| NDP首例冻结 | `1d3181d832d7a409af779215e4aa590d03bd8ed3` | request schema 0.3与双staging实现 |
| E1 NDP参数化 | `e35b24a446bdaeb7a939ab50d8e0cad5fe2a393c` | 实例驱动的accumulate/requant校验与第二实例偏移 |
| E1第二个1×1 | `51d6e787e1c4df1fa617a4a2aa3b0ffa0dfcdb46` | `node-0008`正式编码与config-bound三档P/D候选闭环 |
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

### A. 硬件协作负责人【外部并行，已通知】

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

硬件负责人已经开始并行工作。其输出在返回前不阻塞下面的软件扩展；返回后只通过第12节的合流门进入公共真值。

### B. 操作者/本线程：单算子扩展与最终综合

操作者负责第二个1×1、Conv shape-family、其他算子族、typed execplan和最终综合。所有新实例在精确硬件证据前标`candidate`，首例freeze ID与硬件负责人镜像保持只读。

当前工作包已推进到`node-0003/hwop-0003-00~01`：`[16,64,56,56] -> [16,256,56,56]`、1×1/stride1。它保持输入与空间尺寸，只扩大输出通道，用于验证多output owner、256通道qparams、32个requant shard和staging/inverse扩展。

配置域暂定HIGH-4 `4/1/1`、LOW-28 `28/0/0`；每个新实例都要正式parser、placement、bitstream和数值复核。`ping_pong`由buffer生命周期和邻居接收单独裁决，不随selector机械变化。

### C. 公共合同工作【并入操作者主线，串行】

- 实现`B_EXECPLAN_TYPED_TRANSPORT`：从typed contract/manifest把shape、bias、per-channel qparams、rounding、zero-point、saturation、地址和provenance无损传入execplan handler。
- fail-closed拒绝缺字段、截断、资源越界、SHA不一致和旧16-slice路径。
- 公共schema、selector/ping-pong规则、合同、Git集成和全量回归由操作者主线串行修改；硬件反馈与扩展候选只能通过独立报告回灌，不直接改写真值。

## 7. 操作者主线总览

E0～E3和公共合同修改保持串行；E3通过并冻结实例接口后，E4可把互不共享产物目录的shape实例分组并行，最后由主线串行合并、全量回归。首例硬件实跑继续作为外部独立并行项。

| 顺序 | 工作包 | 状态 | 目标 | 进入条件 | 完成标志 |
|---:|---|---|---|---|---|
| E0 | 基线保护与参数化接口 | **completed** `a679df9e...` | 把首例硬编码入口变成`ConvInstanceSpec/request`驱动，同时保持首例全部hash不变 | 当前freeze可重建 | 首例JSON/bitstream/preflight/freeze逐字节不变，负向测试仍fail-closed |
| E1 | 第二个真实1×1 | **completed** `51d6e787...` | 闭合`node-0008`的多K psum/requant | E0通过 | 三档P/D bit-exact，正式encoder与确定性通过 |
| E2 | 输出通道扩展1×1 | **in_progress** | 闭合`node-0003`的64→256输出通道与32个requant shard | E1通过 | 通道覆盖恰好一次、staging/inverse正确、三档P/D通过 |
| E3 | typed transport | pending | 删除`B_EXECPLAN_TYPED_TRANSPORT`，让实例参数由manifest自动进入handler/request | E2通过，三种实例足以冻结schema | 首例、E1与E2由同一CLI重建；漏字段、错SHA、错dtype立即失败 |
| E4 | 1×1 shape-family | pending；接口冻结后可实例级并行 | 覆盖15种1×1逻辑signature | E2/E3通过 | 每个signature代表例全算子通过；全部1×1实例配置可重建 |
| E5 | 3×3与7×7 | pending | 参数化kernel/pad/stride/邻域与stem特殊路径 | E4稳定 | 4种3×3和1种7×7代表例三档P/D通过 |
| E6 | 全53 Conv | pending | 由20个signature扩展到53个正式模型实例 | E5通过 | 53实例无缺失、无重复、全部encode/config-bound比较通过 |
| O1～O6 | 其他算子族 | pending；族间可并行、族内串行 | Quant、MaxPool、Add、GAP、MatMul、Dequant/View逐族闭环 | Conv合同稳定 | 78节点/133 hw_op配置覆盖完整，族内数值门通过 |
| I1 | 网络execplan | pending；串行合流 | 生成typed execplan、地址、cfg_pkg与Bank_data | 代表算子合同稳定 | 133 hw_op顺序、地址/lifetime/alias和hash全部可审计 |
| I2 | 硬件反馈合流 | **running（外部）** | 接收首例硬件P/D并裁决是否产生freeze v2 | 外部dump返回 | 原始dump、comparison、首错或通过报告入库；公共真值唯一 |
| I3 | 子图/阶段综合 | pending | 从残差块扩到四个stage与head | I1及相关算子通过 | 每层首错可定位，stage输出与golden一致 |
| I4 | 全网三方闭环 | pending | golden/NDP/硬件逐算子与整网一致 | I2/I3和硬件整网能力具备 | G5～G9按直接证据升级，最终报告可复现 |

任何工作包失败都停在该包，不跳过失败实例继续生成“看似完整”的下游产物。

## 8. E0～E3：从首例复制转向真正参数化

### E0：已完成摘要

`a679df9ef3f36b2f0714b89a0719306009288a23`已新增统一`ConvInstanceSpec/ConvTargetRequest`，首例生成器、encoder wrapper、NDP adapter、preflight和freeze exporter均改从该对象取得identity、shape、typed tensor/qparam、HIGH-4 selector、tile、shard和路径绑定。`node-0008`与`node-0003`已可从同一typed contract解析为未冻结spec，但其配置/request仍按fail-closed拒绝冒充正式产物。

E0重构没有改写首例受控文件：累加JSON、requant manifest和hardware freeze manifest SHA保持原值；正式累加encoder仍为46连接/cost 0，8个requant shard仍各21连接/cost 0且双重编码一致；根仓254/254通过。详细实施与验证移入`history.md`。

### E1：已完成摘要

`51d6e787e1c4df1fa617a4a2aa3b0ffa0dfcdb46`已闭合`node-0008/hwop-0008-00~01`：正式累加编码为46连接/cost 0且双次输出一致，8个requant shard均通过正式编码；四段各64通道K生命周期覆盖Cin=256；NDP单坐标、首tile、全算子P/D全部bit-exact，两份staging D均inverse回canonical D，64通道唯一覆盖且每逻辑输出只flush一次。候选报告明确保持hardware/G5/G6/G8为false。

NDPFuncModel参数化提交为`e35b24a446bdaeb7a939ab50d8e0cad5fe2a393c`；根仓258/258、NDP 20/20及仓库lock验证通过。首例当前preflight只更新NDP源码身份，硬件负责人使用的freeze manifest、配置、bitstream和包内preflight未改写。详细过程、SHA和回退点已移入`history.md`，当前只执行E2。

### E2：输出通道扩展 `node-0003`

`node-0003/hwop-0003-00~01`为`Cin=64,Cout=256,H/W=56`。它用于验证：

- output owner与HIGH-ring分配从64扩到256；
- per-channel multiplier从64扩到256，按8 lane需要32个channel-disjoint requant shard；
- staging区、地址表、inverse和canonical K轴扩展；
- 不同输出channel组的bias/zp/scale不会误复用。

完成门E2与E1相同，并额外要求256个输出通道覆盖集合恰好为`[0,256)`、无重复/缺失，随机抽取首/中/末channel分别通过坐标级比较。

### E3：删除`B_EXECPLAN_TYPED_TRANSPORT`

先用首例、E1、E2三种实例定义schema，再扩网络handler：

1. `OperatorSpec`显式携带或内容寻址引用typed attributes/constants；
2. handler不得把FP32 scale塞进整数`params`，不得从文件名推断channel或shape；
3. 每个目标字段保留initializer/tensor ID、dtype、shape、值hash、派生公式和写入位置；
4. 累加和requant子配置共享同一个实例ID，manifest明确一对多；
5. adapter验证配置原文/SHA、64/256通道覆盖、slice、地址、循环和flush；
6. 同一CLI只改`node_id`即可重建首例/E1/E2，输出根按`artifacts/w5/<hw_op_id>/`隔离。

完成门E3：删除阻塞项；三实例正向通过，缺scale/zp/bias、axis丢失、float截断、旧16-slice字段和SHA漂移的测试全部失败；首例freeze不变。

## 9. E4～E6：Conv shape-family扩展矩阵

正式模型53个Conv归并为20种逻辑signature。逻辑signature相同只允许共享公式，不共享实例qparams、地址、JSON或结果hash。

### 9.1 1×1的15种signature

| 波次 | 代表节点 | shape特征 | 主要新增风险 |
|---|---|---|---|
| 已冻结 | `node-0004` | 64→64，56×56，s1 | 基线 |
| E1 | `node-0008` | 256→64，56×56，s1 | 多K/psum |
| E2 | `node-0003` | 64→256，56×56，s1 | 多输出owner/requant shard |
| E4-A | `node-0019`,`node-0021` | 128→512、512→128，28×28 | 通道与空间同时换档 |
| E4-B | `node-0036`,`node-0038` | 256→1024、1024→256，14×14 | 深K与高Cout |
| E4-C | `node-0061`,`node-0063` | 512→2048、2048→512，7×7 | 小空间/大通道/地址容量 |
| E4-D | `node-0016`,`node-0017` | 256→512/128，56→28，s2 | stride2、shortcut/主支对齐 |
| E4-E | `node-0033`,`node-0034` | 512→1024/256，28→14，s2 | 中stage降采样 |
| E4-F | `node-0058`,`node-0059` | 1024→2048/512，14→7，s2 | 最大通道降采样 |

每波只在前一波全通过后开启。每个代表例跑三档P/D；同signature的其余实例至少完成独立qparams/地址生成、正式编码和坐标/首tile比较，最终E6再跑全算子。

### 9.2 3×3与7×7

按空间从大到小扩3×3：

1. `node-0005`：64→64、56×56、pad1；先裁决R/S loop、padding sentinel、weight `KH,KW,C`顺序和九邻域地址。
2. `node-0018`：128→128、28×28；验证通道/空间参数化。
3. `node-0035`：256→256、14×14；验证深K与中等空间。
4. `node-0060`：512→512、7×7；验证高通道、小空间、边界占比与tail。
5. `node-0001`：7×7、3→64、224→112、stride2/pad3；作为独立stem模板，不能由3×3常数缩放得到。

旧`main_CONV_N2N.py`只作3×3算法参考。正式入口必须由request驱动kernel/stride/pad/channel/tile，不复制旧main常量。每种kernel首例必须额外比较padding内外坐标、四角/四边/中心和首末channel。

### 9.3 E6全53 Conv批量门

- 从W3枚举53个QLinearConv，不维护手写节点列表；发现54或52都失败。
- 每个node的一个或多个`hw_op_id`、中间P、最终D、配置和bitstream均有manifest记录。
- 20个signature代表例完成全算子P/D；其余33个实例先完成encode+坐标+tile，再按stage顺序跑全算子。
- 每实例独立验证per-channel qparams、bias、地址、tail、唯一flush和inverse；signature共享不得造成内容hash误命中。
- 汇总报告按node/hw_op/signature列出通过、失败、未运行；任何缺失都使E6失败。

E6完成不自动升级G6/G8：它只建立全Conv正式编码与config-bound软件数值证据。

## 10. O1～O6：其他单算子族扩展顺序

| 工作包 | 首个实例/覆盖 | 必须解决 | 族完成门 |
|---|---|---|---|
| O1 Quantize | `node-0000`，再`node-0074` | FP32输入路径、nearest-even、zp、UINT8 saturation；不能套INT32 quant模板 | 两种shape全算子D与ORT bit-exact |
| O2 MaxPool | `node-0002/hwop-0002-00` | UINT8比较、pad sentinel、3×3/s2/p1、边界和tail | 四角/边/中心及全算子D bit-exact |
| O3 QLinearAdd | `node-0007`起，覆盖stage1～4及`node-0076` | 两输入独立scale/zp、广播、requant、alias/lifetime；不能以FP32 Add-Dequant替代 | 17实例全部encode+数值通过，5种shape代表例全算子 |
| O4 GAP | `node-0071/hwop-0071-00~01` | centered UINT8 sum、除49、scale ratio、nearest-even、唯一requant | INT32 sum与UINT8 D均bit-exact |
| O5 MatMul | `node-0075/hwop-0075-00~01` | 16×2048×1000、N=1000 tail、INT32 psum、per-channel requant | 首/中/末N tail与全算子P/D通过 |
| O6 Dequant/View | `node-0072`,`node-0073`,`node-0077` | 单输入UINT8→FP32 affine；Flatten零拷贝合同 | Dequant tolerance记录，Flatten byte/hash不变 |

执行顺序为O1→O2→O3→O4→O6(pool输出)→O5→O3(dense Add)→O6(final)。原因是按网络拓扑尽早形成可组合前缀，同时把N=1000 MatMul tail留到GA/requant和typed transport稳定之后。

各族都复用统一六层验收：静态schema、正式encoder、单坐标、首tile、全算子、负向fail-closed。整数结果bit-exact；FP32 Dequant保存`atol/rtol`和最大误差。

## 11. I1：typed网络execplan与数据包

只有E3完成且E6/O1～O6的代表实例合同稳定后才开始正式网络生成；可提前写小fixture，不能提前宣称W7。

### 11.1 图和指令

- 唯一输入是W3 lowering manifest，不从旧77原语脚本或文件名重建顺序。
- 覆盖78节点、133个`hw_op`及55个internal tensor；Flatten是否零指令由layout兼容证据决定。
- Conv首/中/末K、GAP sum/requant、MatMul psum/requant按manifest产生独立配置/StartComp。
- 依赖、完成事件和consumer顺序与93条runtime边一致；残差两支未完成时不得启动Add。

### 11.2 地址和生命周期

- 地址规划限定6144-row逻辑容量、16B对齐和28-slice物理域；禁止沿用旧8192-row结果。
- 对79个runtime tensor与55个internal tensor计算birth/last-use、alias、in-place和跨stage释放。
- 每个physical region记录slice/bank/base/size/owner/tensor/hw_op；写区不得与仍存活读区重叠。
- 残差alias只在生产者layout字节兼容且lifetime不冲突时启用；否则显式搬运。

### 11.3 输出包

`artifacts/w7/network/`至少包含：

```text
network_manifest.json
typed_execplan.json
address_table.json
operator_instances/<hw_op_id>/config + bitstream + provenance
cfg_pkg/
Bank_data/
emulator_bundle/
validation/coverage.json + overlap.json + hashes.json
```

完成门I1：从空输出目录重复生成逐字节一致；133个`hw_op`无缺失/重复；所有配置可正式解析；地址无越界/冲突；每个文件受manifest SHA约束；任一失败使整个W7包无效。

## 12. I2：硬件反馈合流规则

硬件负责人返回首例结果后，操作者执行以下唯一合流路径：

1. 只读保存原始dump、硬件/RTL/固件版本、命令、退出码、重复次数和时间；禁止先手工改文件。
2. 核对freeze ID `f687debd...`、manifest SHA及地址表；不匹配则标`wrong_bundle`，不进入数值比较。
3. 用冻结比较器inverse P/D，生成machine-readable comparison和首错坐标。
4. 若P先错：按load/address→selector/ring→A/B role→bias/K-stage→overflow顺序定位。
5. 若P对D错：按requant shard/channel→multiplier/zp→round/saturation→staging/flush/inverse定位。
6. 若P/D均对：首例获得精确硬件通过证据，登记硬件版本和重复稳定性；是否升级G8仍看门定义，不由单例自动决定。
7. 任何修复先在软件复现并补负向测试，再生成新freeze ID；不得覆盖硬件负责人使用的v1目录。

硬件反馈与E1～O6可以时间并行，但公共schema、selector/ping-pong、地址合同和freeze版本变更只能在合流时串行裁决。

## 13. I3～I4：最终综合与三方闭环

### 13.1 分层综合顺序

1. **单算子层**：每个signature/族代表例完成golden↔NDP；硬件支持的代表例再做三方。
2. **残差块层**：stage1首块（含projection）、普通块；检查两支汇合、alias和Add qparams。
3. **stage层**：stage1→stage2→stage3→stage4，按拓扑只追第一处错误。
4. **head层**：GAP→Dequant→Flatten→Quant→MatMul→Add→Dequant，重点检查N=1000 tail。
5. **整网层**：固定输入下比较所有可dump checkpoint、最终logits和Top-1；下游污染不重复猜因。

### 13.2 三方比较合同

每次比较同时保存：

```text
golden vs config-bound NDP
golden vs hardware/RTL
NDP vs hardware/RTL
```

报告必须绑定模型/input/initializer、根仓/NDP/encoder/RTL提交、profile、配置/bitstream/execplan/Bank_data hash。首错包含`node_id`、`hw_op_id`、slice、逻辑坐标、physical地址、三方值及上游最后通过点。

### 13.3 最终门

- G5：计划要求的正式实例配置覆盖、解析、placement、bitstream和确定性全部满足。
- G6：真正目标逐周期或bitstream数值执行器消费同一包并与golden通过；config-bound bulk结果不能替代。
- G7：网络typed execplan、地址、cfg_pkg、Bank_data完整可重建。
- G8：精确硬件包执行、原始dump、inverse和比较证据满足批准范围。
- G9：逐算子、残差块、四stage、head及整网三方报告通过，无missing/incomplete。

门升级必须修改机器可读gate/report并通过测试；文字总结不能单独改变状态。

## 14. 统一产物、测试与回归要求

### 14.1 单算子目录合同

每个实例统一写入`artifacts/w5/<hw_op_id>/`，至少包含：

```text
instance_manifest.json
logical/ 与 physical/ 输入
golden/P,D
configs/accumulate + requant
bitstreams/128b + 64b
parsed_dump/ 与 mapping_review/
preflight.json
comparisons/coordinate,tile,full.json
negative_tests.json
```

大文件可再生且不进入普通Git；小型合同、schema、测试和确定性摘要进入Git。内容相同必须由SHA证明，不能靠文件名或时间戳判断缓存。

### 14.2 每包必跑测试

- 聚焦单元测试：新shape公式、地址、inverse、qparams、tail、flush和负向漂移；
- 首例freeze hash回归；
- 正式encoder两次确定性与位宽/placement检查；
- NDP对应19项及新增target binding测试；
- 根仓全量回归；
- `tools/sync_repositories.py verify`和`git diff --check`。

只有文档计划变更时不重跑大W3/全算子数值；代码或合同变更按影响范围运行，阶段门前必须全量。

## 15. 强制停止条件与越界禁止

- INT8/UINT8/INT32默认bit-exact；FP32必须记录`atol/rtol`。
- physical变换没有inverse、地址不对齐/重叠、字段截断、未知tail、SHA漂移或P/D不一致时停止当前波次。
- 不为赶进度把缺实例标通过，不以bitstream成功代替数值，不以NDP bulk代替G6，不以旧DeepSeek硬件结果代替当前freeze。
- 不在硬件负责人分支或dump目录修改公共生成器；不覆盖首例v1 freeze。
- 不修改受批准hash绑定的ADR-009/硬件合同来绕过失败。
- 不改写未跟踪的`.agents/conv_full(2).json/.txt`。
- 不自动推送GitHub；只有操作者明确要求时按`agent.md`的fast-forward流程推送。

## 16. 计划维护规则

- 本文件保留未完成工作的详细步骤；工作包完成后，把过程、提交、验证和被替代结论移入`history.md`，本文件只保留门状态和下一波。
- E/O/I工作包状态每次只允许一个内部步骤为`in_progress`；外部硬件状态单独标`waiting/running/returned`。
- 真实证据改变规则时同步更新`rules/算子配置规则.md`与测试；稳定代码入口变化时更新`agent.md`。
- 只有定位历史问题才读`history.md`；W4专项错误只读`W4_ARCHIVE.md`。
- 不再建立独立handoff文件；接手命令、负责人边界、当前首包和恢复点直接更新本文件。
