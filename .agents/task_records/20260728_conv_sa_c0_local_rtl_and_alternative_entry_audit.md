# Conv/SA C0 本地 RTL 与替代入口主审

日期：2026-07-28  
范围：`C0_READ_ONLY_CODE_AUDIT`  
目标：`r5:hwop-0004-00 / ConvInt32Accumulate`

## 结构化裁决

```text
RTL_DEFECT_CONFIRMED = true
NO_EXACT_ALTERNATIVE_ENTRY = true
SERIALIZED_CONFIG_FALLBACK_IS_ONLY_AVAILABLE_EXACT_ROUTE = false
NEW_CONV_BYPASS_GENERATION_ALLOWED = false
PACKAGE_RELEASE = NONE
```

第三项不是“不确定”，而是被活动 RTL 直接反证：单 lane 序列化只规避 dot4 第一层
compressor 缺陷，却不能保留非零 `DataC/psum`。因此三真绕行门不成立；在主线裁决并
补充新授权前，normal、alternative 和 serialized 三条配置生成路线都保持关闭。

## 收据与不可信历史隔离

- `.agents/plan.md`：`e823f9d6cba28fff4659d0e2ba3ab3e0651be989feb0fd560a628095133d3fc9`
  （仅 mutable provenance）
- 生成前索引：`12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- 公共算子规则：`cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- INT8 SA 专项规则：`630edcd5736f653e66da775b9ac4839159d79a9009db01f873f25d964f5dc3da`
- C0 授权：`7f7a481eae45fe21c3077d74930c6288c72fba744139d7692db0a43199f17b77`
- node0004 覆盖裁决：
  `6626f3192390fe3b93483746f1dbd6a61cc13f21cd5b55559738cd3dfbad7c06`

本审计未读取或消费任何旧 node0004 JSON、mapping、bitstream、execplan/SCA、package、
simulator output 或 E2/test receipt 作为正证据。旧资产只保留为撤权的负面历史。

## typed request

可信输入仅来自
`contracts/resnet50_r5_lowering_bundle.json`
（SHA256=`bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`）
中的 `r5:hwop-0004-00`
（request SHA256=`e27e10169168f3889df4c03bf15cb21de074abf3f3767dc4bee288425165874b`）：

- `x = uint8[16,64,56,56]`
- `w = int8[64,64,1,1]`
- `bias = int32[64]`
- `y_acc = int32[16,64,56,56]`
- `x_zero_point = 0`
- `w_zero_point = int8[64]`，全零

目标逐元素语义是：

```text
y_acc = bias + Σ_k (s8(w_k) * u8(x_k))  (mod 2^32)
```

非零 `x_zero_point` 的同族语义还要求初值
`bias - x_zero_point * Σ_k w_k` 作为 `DataC/psum32` 进入相同模加路径。

## 活动代码链

活动本地入口由 `NDP_copy01/Makefile.tb_NDP_Top_new_phy` 指向
`rtl/filelists/NDP_Top_phy_filelist.f`，依次包含 Slice、Specialized Array、SA PE 与
utils filelist。模块链为：

```text
NDP_Top_new_phy
  -> Slice
  -> Specialized_Array
  -> SA_PE_Group
  -> SA_PE
  -> SA_PE_Outbuffer (initial bias / feedback psum)
  -> SA_PE_ALU
  -> SA_ALU
  -> SA_PE_Float_Control
  -> SA_PE_Mul_Array
  -> CSA_4to2 / CSA_3to2
  -> psum32 output
```

`special.py` 只编码：

- `mode`: GEMM=`0`，其他字符串落为 GEMV=`1`
- `data_type`: INT8=`0`、FP16=`2`、BF16=`3`
- `bias_enable` 与 `transout_last_index`

`Specialized_Array_Config.sv:100-121` 将这些位直接解包为 `sa_mode`、
`sa_pe_computation_data_type` 与 `sa_pe_bias_enable`。GEMV 只在
`Specialized_Array_Config.sv:124-132` 改变启用的 PE 行；两种模式共用同一个
`SA_PE_ALU/SA_ALU`。

`SA_PE_Outbuffer.sv:560-561` 输出初始 bias 或反馈 psum，
`SA_PE_ALU.sv:25-31` 将其原样接到 `FMA_DataC`。因此下面的 DataC 丢失不是 mapper、
packing 或上游端口错误，而是 ALU 内部首处分歧。

活动 `control_registers.py` 的 `OP_CONTROL_REGISTER_FN` 没有 Conv/MatMul INT8 handler。
本族 hash-bound patch source 中 normal/serialized Conv handler 都只验证 shape/dtype
并 `return {}`；它们不修改 SA 算术字段，也不能修复下述 RTL 行为。Mapper 只分配
LC/PE/stream 资源，不改算术 identity。

## FIRST_DIVERGENCE

### 1. DataC/psum 在 INT8 路径被强制清零

`SA_PE_Float_Control.v:253-258`：

```text
o_AddExp   = DataC[30:23] & {8{i_Mode}}
o_AddNZero = |o_AddExp
```

INT8 的 `i_Mode=0`，故对任意 32-bit `DataC`，`o_AddNZero=0`。
随后 `SA_PE_Mul_Array.v:212`：

```text
pipe_FractC <= i_AddNZero ? i_FractC : 0
```

而 `SA_PE_Mul_Array.v:296` 才把 `pipe_FractC` 送入整数末级 CSA。故真实方程是：

```text
stock_INT8_result = broken_dot4(A, B) + 0
```

而不是：

```text
stock_INT8_result = dot4(A, B) + DataC
```

这直接否决 bias on、multi-wave/多 occurrence psum、K>单 occurrence、正负 psum wrap
及非零 x-zp 修正初值。它也否决“每 occurrence 一条非零 product lane”作为独立完整
accumulate fallback；该方法只在 `DataC=0` 的单 occurrence 产品上精确。

### 2. carry 被重复左移

`CSA_4to2.v:30-32` 已输出：

```text
carry = carry_temp << 1
```

`SA_PE_Mul_Array.v:295` 又把 `carry_int` 左移一次作为 `last_B`。因此普通四 lane
第一层的 carry 权重被从 `2` 错当成 `4`。最小反例：

```text
A = [1,1,1,1]s8
B = [1,1,1,1]u8
model = 4
RTL   = 6
```

### 3. signed17 不足且 cout 丢弃

四个合法产品的总范围为：

```text
minimum = 4 * (-128) * 255 = -130560
maximum = 4 * 127 * 255    = 129540
```

必须使用 signed18。`SA_PE_Mul_Array.v:279-292` 却实例化 17-bit `CSA_4to2`，
断开 `cout`，再从 bit16 符号扩展 sum/carry。仅删除重复左移不能修复该独立缺陷。

## 动态复核

本机无 VCS，使用本地 Icarus 读取活动 filelist 指向的真实 RTL；编译产物只放
`$env:TEMP`。

### SA

`tests/rtl_audit/int8_sa_stock_dot4_tb.sv`
（SHA256=`005c8d1ac8f1174c9e27732d743a0c12801da921e5779b89d1ba5a5d9d08c8d1`）
结果 `TB_PASS`，表示全部预声明正/负控制分类正确：

| case | RTL | model | 裁决 |
|---|---:|---:|---|
| four ones, bias off | `6` | `4` | fail |
| four ones, DataC=5 | `6` | `9` | fail，DataC 丢失 |
| max positive dot4 | `0x0002f706` | `0x0001fa04` | fail |
| max negative dot4 | `0xfffd0300` | `0xfffe0200` | fail |
| mixed sign | `0xfffffd05` | `0xffffff01` | fail |
| K=3 small tail | `3` | `3` | coincidental pass |
| K=3 full-range tail | `0x00027383` | `0x00017b83` | fail |
| one product, DataC=0 | `1` | `1` | pass |
| K=5 second occurrence, DataC=4 | `1` | `5` | fail |
| positive psum wrap | `1` | `0x80000000` | fail |
| negative psum wrap | `0xffffffff` | `0x7fffffff` | fail |
| nonzero x-zp corrected DataC=4 | `4` | `8` | fail |

### GA

`tests/rtl_audit/int32_ga_mac_tb.sv`
（SHA256=`727245663d0cc841bcedb70354644c5529f70f13d0c572bd8aa3b4f83e9d734a`）
直接实例化活动 `GA_PE_ALU`，opcode=`5'b01110`（encoder `int32_mac=14`）。
正、负、mixed-sign、正负 wrap 和大乘积模 `2^32` 六例全部逐 bit 通过。

该动态结果只证明“输入已正确扩展为两个 int32 operand 时，GA MAC 算术精确”，不证明
typed `int8` 权重进入 GA，也不证明 node0004 的 dual-stream、barrier、buffer、
lifetime 或完整 Conv schedule。

## capability matrix

| 入口 | product | psum32 | typed/full entry | 裁决 |
|---|---|---|---|---|
| SA INT8 GEMM four-lane | 错 | 错 | 已有入口 | 不可用 |
| SA INT8 GEMV | 错 | 错 | 与 GEMM 共用 ALU | 不可用 |
| SA 单非零 lane | `DataC=0` 时对 | 错 | 不完整 | 不是 accumulate route |
| SA FP16/BF16 | 浮点舍入 | 非整数模加 | dtype 不等价 | 不可用 |
| GA `int32_mac` | 对 | 对 | signed-int8 ingress/完整拓扑未绑定 | 诊断 primitive，不是现有 exact entry |
| IGA integer MAC | 16-bit | 16-bit | index datapath | 不可用 |

GA 入口的活动代码边界：

- `general.py:199` 将 `int32_mac` 编为 14；
- `GA_PE_ALU.sv:22-24` 解码为 integer mode、int32 precision、MAC；
- `GA_Inport.sv:319-338` 仅提供 `uint8 -> zero-extended int32`；
- encoder/RTL 均不存在 `int8 -> sign-extended int32` 字段；
- 活动 handler registry 无 Conv GA handler；
- 未存在 hash-bound 的 node0004 signed-weight widening、三输入同步、跨 stage barrier、
  psum buffer/lifetime 合同。

冻结权重可以在未来获得授权后派生 sign-extended int32 常量，或用额外硬件 stage 产生，
但二者当前都只是新的 lowering/topology 设计，不是 C0 已存在且可选择的精确入口。因此
`NO_EXACT_ALTERNATIVE_ENTRY=true` 的边界是“当前活动 typed-to-hardware 完整入口”，并不
否认 GA MAC primitive 的数值能力。

## STATIC / DYNAMIC 边界

静态已闭合：

- typed request identity 与目标方程；
- 活动本地 filelist、模块层级与直接 source SHA；
- encoder 位域到 SA/GA control 的解码；
- `DataA=s8 bytes`、`DataB=u8 bytes`、`DataC=outbuffer psum32`；
- carry 重复左移、signed17/`cout`、DataC 门控为零；
- SA mode/dtype、lane/packing、GA、IGA、FP、handler/mapper registry 矩阵。

动态已闭合：

- 活动 `SA_ALU` 的上述反例；
- 活动 `GA_PE_ALU/int32_mac` 在已扩展 int32 operands 上的模加算术。

未声称：

- 任何新 node0004 JSON/mapping/bitstream/execplan/SCA；
- address、bank、lifetime 或 terminal；
- full NDP top/VCS/server 行为；
- node0004 local E2 或服务器包。

## BLOCKER_DELTA

```text
ADD  B_SA_INT8_DATAC_PSUM_GATED_ZERO
KEEP B_SA_INT8_DUPLICATE_CARRY_SHIFT
KEEP B_SA_INT8_REDUCTION_WIDTH
KEEP B_CONV_INT8_SA
KEEP B_CONV_BIAS_PSUM
KEEP B_SA_SERIALIZED_FALLBACK_MATERIALIZATION
ADD  B_CONV_SA_PRODUCT_SCRATCH_SCHEDULE_AND_OWNERSHIP
ADD  B_CONV_GA_EXACT_ALTERNATIVE_TYPED_TOPOLOGY
     (仅当主线选择复合 C1 时)
```

## RULE_DELTA_PROPOSAL

1. 将 `CDA-SA-INT8-SERIALIZED-FALLBACK-001` 的源码候选边界收窄为：
   “每 occurrence 至多一条非零 product lane 且 `DataC=0` 时，该 occurrence 的单产品
   精确”；不得再称其为 SA 内部 psum accumulate fallback。
2. 新增 `CDA-SA-INT8-DATAC-PSUM-GATE-001`：INT8 mode 下必须动态/静态证明任意
   `DataC` 被逐 bit 纳入模 `2^32` 结果；仅验证 zero-psum product 不足以放行 bias、
   K-tail、multi-wave、nonzero x-zp 或 serialized route。
3. 若主线选择 GA alternative，须新增 typed signed-weight widening ownership、
   三输入同步、barrier、psum scratch visibility/lifetime 和全 tensor coverage 门；
   GA primitive 单测不得冒充完整入口。

## RETURN_ANALYSIS

活动 RTL 确认普通 SA INT8 dot4 存在功能缺陷，但本轮同时发现更早且更强的 DataC/psum
清零缺陷。现有 SA 单乘积序列化不能在 SA 内完成 node0004 accumulate；但
`SA product→INT32 scratch→GA tree` 在 primitive/source/config 层可表达，不能归类为
“无配置绕行”。它当前仍是 proposal-only，尚无完整 typed alternative entry。因此主线
不能进入 fresh serialized-SA-psum bypass，也不能在 C0 结果上直接生成 fresh GA 配置。
正确动作是先更新专项语义与 blocker，保持配置生成锁，再由主线选择：

- 新 C1：设计并验证完整 SA-product + GA-tree typed topology；或
- 等待用户授权兼容 RTL；或
- 提供另一条能在硬件中外置累加且闭合 barrier/lifetime 的全新拓扑。

## 补充：三路状态与复合路径

```text
NORMAL_EXACT_ENTRY = false
SA_SERIALIZED_PSUM = false
SA_PRODUCT_PLUS_GA_TREE = proposal-only
```

这里的 `proposal-only` 表示：活动源码与非 node0004 的正式 GAP local E2 已证明所需
primitive 可由 stock RTL/config 表达，但尚未形成可选择的 Conv typed-to-physical
完整入口。

### 已证明的 primitive

1. SA 单产品：每 occurrence 仅一条非零 lane 且 `DataC=0` 时，
   `s8(w)*u8(x)` 输出正确 32-bit two's-complement product。
2. 正式 INT32 transport：`NDP_Parameters.svh:564` 固定 SA outport data width=32；
   `SA_Outport.sv:441,455` 在关闭 FP16/BF16 转换时逐 bit 传递 32-bit 数据；
   `Slice_cdc.sv:360-361` 可将 SA 输出写 buffer，`:499-500` 也可送 GA。
3. GA 归约：opcode14 的 `int32_mac(A,1,C)` 对正负、mixed-sign 和 wrap 逐 bit 通过。
4. INT32 scratch/reload/barrier：node0071 sum-stage local E2
   （record SHA=`cc9f431570f4a114c0d80bc2bb19adb5e5e3e7592e7f2943379d5899f529d30c`）
   已物化 `49→25→13→7→4→2→1`，每级使用显式 INT32 scratch、reload 与 same-mask
   barrier，并闭合最终 JSON occurrence/address/coverage。它只证明 stage2+ 公共能力，
   不替代 Conv stage1 和 Conv 地址方程。

候选等价方程：

```text
products[p,k] = s8(w[k]) * u8(x[p,k])                 // SA, DataC=0
tree_l[p,j] = tree_(l-1)[p,2j] * 1
              + tree_(l-1)[p,2j+1]                  // GA opcode14
result[p] = tree_root[p] + bias[c] - x_zp * sum_k(w[c,k])
```

所有加法为 `mod 2^32`，故 pairwise reassociation 与目标 INT32 accumulate 逐 bit 等价。
奇数层必须显式补零，不能越界或复用 stale slot。

### node0004 与 3x3x64 规模

- node0004 为 1x1、Cin=64：每输出 64 个产品；产品 scratch 最小逻辑量
  `16*64*56*56*64*4 = 822,083,584 bytes`，未含 padding/alignment/tree scratch。
  64 项本身无 K tail，bias/x-zp correction 仍须作为 additive leaf 或独立末级。
- 3x3、Cin=64 为 576 项：
  `576→288→144→72→36→18→9→5→3→2→1`；从 9 开始的 odd tail 必须逐级显式
  zero leaf。若 correction 作为第 577 项，首层即需独立 tail ownership。
- 大 scratch 不等于源码证明资源不可实现：可按 output/K tile 分批落 DRAM；
  但会产生大量 start/barrier/traffic。C0 没有最终地址方案，故资源可实现性仍未通过。

### 三路首个 blocker

| 路线 | 状态 | 首个 blocker |
|---|---|---|
| `NORMAL_EXACT_ENTRY` | `false` | `SA_INT8_DATAC_GATED_ZERO`（另有 dot4 carry/width） |
| `SA_SERIALIZED_PSUM` | `false` | `SA_INT8_DATAC_GATED_ZERO` |
| `SA_PRODUCT_PLUS_GA_TREE` | `proposal-only` | `B_CONV_SA_PRODUCT_SCRATCH_SCHEDULE_AND_OWNERSHIP` |

复合路径进入已复用 GA stage2+ 前，仍缺：

- `(n,oc,oh,ow,k) -> product scratch byte address` 一一映射；
- 每个 SA product write 的 bank/column/terminal/byte coverage；
- node0004 64 项与家族 576 项的 spatial/channel/K tile 次序；
- product scratch drain 后才允许 GA reload 的 barrier/lifetime；
- bias 与 `bias-x_zp*Σw` 的 owner/formula/per-channel broadcast；
- GA A/C dual-stream tag/last/last_index、normal FIFO drain、每级 scratch visibility；
- typed Conv handler、mapper/manual materializer 授权与 leaf ownership；
- 所选 tiling 下的容量、流量和可完成性。

若主线选择该路线进入 C1，它属于 fresh alternative，不是原 serialized-SA-psum
bypass；必须从 typed request/活动规则重建，禁止消费撤权 node0004 资产。

机器可读报告：
`contracts/operator_config/conv_sa_c0_local_rtl_audit_v1.json`。
