# C0 独立 RTL 审计：node0004 INT8 SA

日期：2026-07-28  
角色：独立复核，不隶属 Conv/SA 主审  
唯一回传主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 结构化裁决

```text
RTL_DEFECT_CONFIRMED = true
NO_EXACT_ALTERNATIVE_ENTRY = true
SERIALIZED_CONFIG_FALLBACK_IS_ONLY_AVAILABLE_EXACT_ROUTE = false
NEW_CONV_BYPASS_GENERATION_ALLOWED = false
```

最后一项保持 false，因为本报告只满足独立复核腿；C0 仍须主线同时验收主审报告。本轮未修改
plan/rules/rtl，未生成 Conv target/bypass 资产或服务器包，未检查/运行服务器。

用户追加覆盖后，node0004 全部历史 JSON、mapping、bitstream、execplan/SCA、package、
simulator output、local E2 与测试收据均按失败的负面历史处理。本报告的三项裁决只依赖
活动 filelist/直接代码消费者、锁定 typed request 与 W3 identity；不消费旧 node0004
下游资产作为正证据。

## 独立源码链

活动本地 filelist 逐级包含：

```text
NDP_Top_phy_filelist.f
→ Slice_filelist.f
→ Specialized_Array_filelist.f
→ SA_PE_Group_filelist.f
→ SA_PE_filelist.f
→ SA_PE_Mul_Array.v
```

`NDP_Top_phy_filelist.f` 另经 `vcs_utils_filelist.f` 包含 `CSA_4to2.v`。所有直接源码 SHA
见机器报告 `outputs/c0_independent_rtl_audit_20260728/report.json`。

node0004 typed request 明确为 QLinearConv accumulate：`x:uint8`、`w:int8`、
`bias:int32`、`D:int32`。活动 encoder 表明保持该整数语义的 SA dtype 只有 int8=`00`，
mode 只在 GEMM/GEMV 间选择拓扑；RTL control 原样解码。`SA_PE_ALU.sv` 固定
DataA=inport0、DataB=inport1、DataC=psum；`SA_PE_Float_Control.v` 对四个 A byte
取符号与绝对值，对四个 B byte 保持 unsigned，因此实际到达目标
`s8(A) × u8(B) + int32(C)` 的任何正常 INT8 SA 配置都会进入同一 compressor。
由于旧 node0004 JSON 已撤权，本报告不声称某份历史 bitstream 是可信正证据；它证明的是
typed 目标在活动 encoder/RTL 中唯一正常编码入口的源码后果。

## 两个独立 RTL 缺陷

`CSA_4to2.v` 已执行：

```text
carry17 = carry_temp << 1
cout = carry_temp[16]
```

但 `SA_PE_Mul_Array.v` 的 INT8 instance 将 `.cout()` 悬空，并又执行：

```text
last_B = signext32(carry17) << 1
```

所以 stock 方程为：

```text
psum32 + signext32(sum17) + (signext32(carry17) << 1)
```

carry 被重复加权。与此正交，四个合法 `s8×u8` 乘积范围为
`[-130560,129540]`，超过 signed17 `[-65536,65535]`，必须使用 signed18；当前
signed17 compressor 且丢弃 cout，单独构成第二缺陷。

## 静态与动态证明

静态证明覆盖活动 filelist、control decode、packing、compressor 和 psum handoff。
本机存在 Icarus Verilog，故在非 RTL 路径建立最小 TB，直接编译活动
`CSA_4to2.v`，并按活动 `SA_PE_Mul_Array.v` 的 stock handoff 组合结果：

| products | 正确值 | stock |
|---|---:|---:|
| 1,1,1,1 | 4 | 6 |
| -1,-1,-1,-1 | -4 | -6 |
| 32385×4 | 129540 | 194310 |
| -32640×4 | -130560 | -195840 |
| 32385,-32640,1,-1 | -255 | -763 |

该动态证据是 focused local RTL proof，不是完整 NDP top/VCS/server proof。

psum wrap 不能一般性掩盖缺陷：错误 delta 与正确 dot 同在模 `2^32` 加法前进入，除偶然
个例抵消外仍保留。K=3/5 tail、bias on/off、nonzero x-zp 只改变有效 product 或 DataC，
不改变 compressor；任何 occurrence 只要含两个以上能产生 carry 的非零 product，仍可触发
同一首因。

## 替代入口穷举

- SA GEMM/GEMV：mode 只改变 PE 拓扑，INT8 PE 均进入同一 compressor。
- SA lane/packing：只能排列四个 signed-A/unsigned-B byte，不能修复 carry 权重或恢复 cout。
- SA FP16/BF16：改变数值域并引入浮点舍入，不保持完整 int32 模语义；dtype `01` 未获支持。
- GA `int32_mac`：opcode14 原语存在，但活动 handler registry 没有
  `ConvInt32Accumulate/QLinearConv` 入口；node0004 的 signed-A/u8-B 双流、barrier、
  matching/tag、normal FIFO 与 writeback 没有最终物化闭环，因而不是“当前可用精确入口”。
- GA FP32/FMA：整数转 FP 与浮点舍入不保持完整 int32 合法域。
- generic mapper/template：只能搬运已有字段，不能补造缺失算术和 typed transport owner。

因此当前活动源码/registry 下无另一条可配置且已可用的精确入口。历史 node0004 资产
不在候选矩阵中作为正入口，仅作为已撤权负面背景。

## 勘误：INT8 DataC/psum 被清零

主线要求对完整 `SA_ALU` 复核后，发现先前第三项裁决错误。活动源码逐式为：

```text
i_Mode=0
→ o_AddExp = DataC.exp & 0 = 0
→ o_AddNZero = |o_AddExp = 0
→ o_AddFract = DataC
→ pipe_FractC = o_AddNZero ? o_AddFract : 0 = 0
→ last_C = pipe_FractC = 0
→ integer result does not include DataC
```

`SA_PE_Float_CSA` 的 integer result 是 `MUL_Sum + MUL_Carry`，末级
`SA_PE_Float_Last` 在 `i_Mode=0` 时原样选择该 integer result，后续没有恢复 DataC。

完整活动 `SA_ALU` focused TB（并非 compressor 方程替身）动态得到：

| case | 期望 | RTL | `pipe_FractC` | `last_C` |
|---|---:|---:|---:|---:|
| single `1×1` + C=7 | 8 | 1 | 0 | 0 |
| four ones + C=5 | 9 | 6 | 0 | 0 |
| `-1×1` + C=-5 | -6 | -1 | 0 | 0 |

因此单乘积 occurrence 只能在 `C=0` 时精确地产生单个 product，不能通过 SA DataC 在多个
occurrence 之间累加。此前“single product plus psum32 精确”的结论撤回。

## 落盘后整数归约入口穷举

- LC_PE add/mac：固定 signed16 且输出 low16，不能归约任意 signed32 product。
- SA DataC recurrence：如上被清零。
- GA `int32_sum` opcode12：原语与一份 avgpool 静态 JSON 存在，但活动
  `operator_base_info`、control-register handler registry 没有 Conv/node0004 reduction
  入口；不存在全新 product ingress、ordered reduction、address/lifetime、barrier、
  terminal/writeback 的端到端 binding，不能称当前可用精确路线。
- GA `int32_mac` opcode14：32-bit buffer/constant 字段在孤立层面可表达
  `product*1+C`，但同样缺 product 落盘、C scratch recurrence、双流 matching、tag/FIFO、
  barrier、address/lifetime、terminal/writeback 与 mapper/handler 闭环。它是待设计候选
  primitive，不是当前已有精确配置入口。
- FP32/FP16/BF16：不能保持完整 signed32 模语义；host 预计算被明确禁止。

所以 `NO_EXACT_ALTERNATIVE_ENTRY=true` 仍成立，但“没有替代入口”不能反推 serialized
fallback 可用；当前精确路线是 `none`，配置生成必须继续 fail closed。

结构化勘误：

```text
CORRECTION_DELTA:
  RTL_DEFECT_CONFIRMED: true -> true
  NO_EXACT_ALTERNATIVE_ENTRY: true -> true
  SERIALIZED_CONFIG_FALLBACK_IS_ONLY_AVAILABLE_EXACT_ROUTE: true -> false
```

机器报告与最小 TB：

- `outputs/c0_independent_rtl_audit_20260728/report.json`
- `outputs/c0_independent_rtl_audit_20260728/tb_csa4to2_stock_handoff.sv`
- `outputs/c0_independent_rtl_audit_20260728/tb_sa_alu_int8_datac.sv`
