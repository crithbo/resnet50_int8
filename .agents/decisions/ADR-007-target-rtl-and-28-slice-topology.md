# ADR-007：锁定目标RTL并重建28-slice性能布局

状态：已由操作者采用（adopted）；RTL目标为candidate，W4按新方案重开，G4未通过、W5未授权
日期：2026-07-13

## 决定

1. 目标硬件确定为28个slice，不再把16-slice布局应用到28-slice硬件。
2. 目标RTL选择并固定为`xlsjdjdk/Trassic2.0_RTL@e3bdebba95dec36ee8eba43caa92a326a88392cd`。选择时远端分支为：`master=e3bdebba...`、`dc=c239be5d...`、`xilinx=fdde69a6...`。
3. ResNet50主体的首选profile为`w4_group4x7_batch_channel28_candidate_v1`：七个硬件4-slice小环并行分担batch，环内按C/K通道所有权执行。
4. 增加`w4_global_ring28_candidate_v1`作为比较候选，不作为整网默认；优先评估GAP后的MatMul/head，是否采用由dry-run、simulator和硬件cycle共同决定。
5. W0～W3口径、模型、lowering和约951 MB golden产物保持有效；旧16-slice W4实现、报告和ADR只作历史参考，不约束新设计。

## RTL版本审查结论

- `master`与`dc`的活动`NDP_Parameters.svh`、`NDP_Top.sv`、主filelist以及SA/GA计算阵列语义一致，均为28-slice。
- `master`更新，且在活动路径增加或修订neighbor buffer bank mask、基于真实slice启动的remote flag清理、AXI写地址/数据解耦及PHY/APB配置，因此在功能完整性相近时选择最新`master`。
- `xilinx`分支为旧16-slice版本，文件和功能覆盖明显较少；其综合脚本仍含工艺库、时钟等TODO，不作为目标版本。
- 目标commit仍不是“已验证可构建”的批准版本：当前`NDP_Top.sv`声明模块`NDP_Top_new`，而部分lint脚本仍指定`NDP_Top`；仓库只有旧的失败lint摘要，没有本项目可重放的clean elaboration/bitstream证据。因此W1/G1仍需补编译与接口合同。

## 物理拓扑

七个HIGH小环按RTL的`HIGH_NEXT_MAP`冻结为：

```text
G0:  0 -> 2 -> 3 -> 1 -> 0
G1:  4 -> 6 -> 7 -> 5 -> 4
G2:  8 -> 10 -> 11 -> 9 -> 8
G3: 12 -> 13 -> 15 -> 14 -> 12
G4: 16 -> 17 -> 19 -> 18 -> 16
G5: 20 -> 21 -> 23 -> 22 -> 20
G6: 24 -> 25 -> 27 -> 26 -> 24
```

LOW大环按RTL的`LOW_NEXT_MAP`冻结为：

```text
0 -> 12 -> 13 -> 15 -> 17 -> 19 -> 21 -> 23 -> 25 -> 27 -> 26
  -> 10 -> 11 -> 9 -> 8 -> 24 -> 22 -> 20 -> 18 -> 16 -> 14
  -> 2 -> 4 -> 6 -> 7 -> 5 -> 3 -> 1 -> 0
```

任何实现不得用`(owner+step)%slice_count`替代这些物理映射。

## 主profile规则

batch=16按固定连续样本区间分给七组：

```text
G0: N[0:3]    G1: N[3:6]
G2: N[6:8]    G3: N[8:10]   G4: N[10:12]
G5: N[12:14]  G6: N[14:16]
```

- 每组4个slice拥有连续C/K chunk；activation沿小环完成4步/3次neighbor transfer。
- weight按K owner分片并在七组间复制；bias、per-channel qparams、INT32 psum和D跟随K owner。
- 两条残差分支必须保持相同batch group、C/K owner、轴序、tail和base/alias规则；六个Add qparams仍独立。
- MaxPool、QLinearAdd和GlobalAveragePool尽量在owner slice本地完成。
- Conv0的C=3允许一个环内activation owner只保存tail，但四个K owner仍参与输出计算。
- 第一版安全调度允许3样本组比2样本组多一个工作单元；确认per-slice queue/barrier语义后再评估异步wavefront，不用复制虚假样本制造“全利用率”。

## 大环和profile转换规则

- 大环候选按全28 slice切K/O，可用于高通道、低空间或head层；不能仅因slice更多就宣称更快。
- 主体默认保持小环profile；不得在残差块内部切换。
- 第一版整网最多允许一次显式小环到大环转换，优先放在GAP后`[16,2048]`进入MatMul之前。
- 是否启用转换必须把SA有效lane、activation字节×hop、weight复制、DDR占用、barrier尾部空闲和转换读写成本放入同一报告，并由真实simulator/hardware cycle复核。

## 失效和保留

- `ADR-002`已废止。
- `ADR-003`、`ADR-005`及`artifacts/w4/*16*`/旧双profile报告只保留历史；其93条边集合、生命周期/alias算法和报告schema可复用，物理数值不可复用。
- `ADR-004`的版本化批准机制继续使用，但批准合同必须描述28-slice和真实物理环。
- `ADR-006`的逻辑结果比较器与slice数无关，继续使用。
- 旧`config/utils/config_parameters*.py`的16-slice镜像只作历史字段线索；`model_execplan`现有28-bit mask、28个slave和128-bit指令框架是更接近目标的起点，仍需逐字段对照目标commit。

## 新G4门

G4只有在以下条件全部满足后才可通过：

1. 新28-slice拓扑mapper逐项匹配RTL的HIGH/LOW映射，并通过正逆与非法拓扑测试。
2. 全部算子族在主profile完成raw->physical->raw bit-exact；大环候选至少覆盖代表层。
3. 93条边、91条qparam链、16个残差Add重新完成物理兼容、生命周期和alias审计。
4. 成本报告包含lane利用率、hop字节、weight复制、容量、barrier尾部和profile转换，且不把估算冒充cycle。
5. 目标RTL/ISA/register-map、端口layout和运行协议形成带版本合同；目标顶层能在权威工具链clean elaboration。

在此之前`g4_status=not_passed`、`w5_authorized=false`，不得生成正式W5 JSON/bitstream或宣称硬件profile已批准。
