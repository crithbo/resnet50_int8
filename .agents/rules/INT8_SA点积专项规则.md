# INT8 SA 点积专项规则

最后更新：2026-08-11（剥离实例状态，仅保留稳定共性合同）

本文件保存 ResNet50 `QLinearConv` 与 `QLinearMatMul` 共用的
`UINT8 activation × INT8 weight → INT32 accumulate` 专项增量。公共 provenance、
物化回环、地址、证据等级和服务器门仍由公共规则拥有。

实例授权、当前硬件身份、候选状态与服务器结论只记录在 `.agents/plan.md` 和对应
`.agents/task_records/`。本文件不授予任何实例 release，也不保存版本化 package 结论。

## 1. 适用范围与目标方程

本门同时约束 53 个 `QLinearConv` accumulate stage 和 1 个
`QLinearMatMul` accumulate stage。目标方程为：

```text
int32_acc = bias_or_psum + Σ(s8(weight_i) * u8(activation_i))
```

操作数方向固定为 `DataA=s8 weight`、`DataB=u8 activation`、
`DataC=psum32`。任何交换符号域、把 INT8 数据改按 FP16/BF16 解释、依赖最终 requant
饱和掩盖 accumulate 错误的方案均不兼容。

## 2. stock RTL 首处分歧

规则 ID：`CDA-SA-INT8-DOT-ARITHMETIC-RANGE-001`

历史审计曾声称 JSON、mapper、bitstream、SA control 和 operand packing 已选择预期的
`gemm/int8` 路径，并定位 stock RTL 的两个独立缺陷：

1. `CSA_4to2` 输出 carry 时已经左移，`SA_PE_Mul_Array` 交给下一层前再次左移；
2. 四个合法 `s8×u8` 乘积之和需要 signed 18 bit，现有第一层只有 signed 17 bit，
   且 `cout` 未被消费。

四个 `1×1` 的最小反例只能证明重复 carry shift；算术放行还必须覆盖：

```text
4 * 127 * 255  =  129540
4 * -128 * 255 = -130560
```

以及正负值、进位、K=3/K=5、非零 input zero-point、bias off/on、正负边界和
psum32 模 `2^32` 累加。只删除重复移位或只扩大位宽均不足以放行。

上述 carry/位宽结论已由 C0 主审和独立复核从活动本地 filelist、mapper、encoder、
control、packing 与真实 `SA_ALU` 重新建立。C0 还发现更早且更强的第三项缺陷。

规则 ID：`CDA-SA-INT8-DATAC-PSUM-GATE-001`

活动 `SA_PE_Float_Control→SA_PE_Mul_Array` 在 INT8 `i_Mode=0` 时使：

```text
o_AddExp = DataC[30:23] & 0 = 0
o_AddNZero = 0
pipe_FractC = 0
integer last_C = 0
```

因此 stock INT8 方程不包含 `DataC/psum32`。完整 `SA_ALU` focused TB 已覆盖
single-product+nonzero DataC、four-ones+bias、K=5 第二 occurrence、正负 wrap 与
nonzero-xzp 修正初值，均确认 DataC 未进入结果。

INT8 accumulate 放行必须静态和动态证明任意 32-bit DataC 被逐 bit 纳入模 `2^32`
结果。只验证 `DataC=0` 的 product 不得放行 bias、K-tail、multi-wave、nonzero x-zp
或任何 SA 内 psum recurrence。

## 3. config-only correctness fallback

规则 ID：`CDA-SA-INT8-SERIALIZED-FALLBACK-001`

兼容 RTL 身份获批前，stock RTL 只证明以下窄 primitive：

```text
each SA occurrence has at most one nonzero product lane
AND DataC = 0
THEN output = one exact s8*u8 product
```

该 primitive 不能通过 SA DataC 在 occurrence 间累加。旧规则中
“serialized_one_product 是 stock correctness accumulate baseline”的表述正式撤回；
历史 node0004 物化、simulator 和测试全部撤权。`B_SA_SERIALIZED_FALLBACK_MATERIALIZATION`
保持开放，但其含义收窄为“单产品 stage 的 fresh materialization”，不再代表完整
Conv accumulate fallback。

主线已验收 C0 并选择 fresh composite C1：

- 禁止生成 SA 内 serialized-psum 路线；
- 只允许 node0004 使用
  `SA single-product(DataC=0)→INT32 scratch→GA int32_mac(A,1,C) tree`
  的 fresh composite 配置研发；
- 该路线不得消费任何 node0004 历史 JSON、mapping、bitstream、execplan/SCA、
  package、simulator output 或 local test receipt；
- 首个通过口径必须是 accumulate+requant 的完整 node0004 UINT8 local E2 与全新本地
  测试包，不是 accumulate-only。

规则 ID：`CDA-SA-INT8-COMPOSITE-PRODUCT-GA-TREE-001`

复合 C1 的算术合同固定：

```text
product[p,k] = s8(weight[k]) * u8(x[p,k])              // SA, DataC=0
tree[p,j] = int32(tree_left[p,j] * 1 + tree_right[p,j]) // GA opcode14
result[p] = tree_root[p] + bias[c] - x_zp * sum_k(weight[c,k])
```

全部加法按 `mod 2^32`。奇数层必须显式补零；correction 必须是有 typed 来源、公式、
per-channel broadcast 和 lifetime owner 的 additive leaf，不能由 host 预计算内部
accumulate 或最终 tensor。node0004 的 `x_zp=0` 仍必须保留 bias leaf 的 ownership，
不能因本实例修正项为零而删除全族合同。

规则 ID：`CDA-SA-INT8-COMPOSITE-MATERIALIZATION-GATE-001`

生成任何 node0004 测试包前，fresh composite 必须闭合：

- `(n,oc,oh,ow,k)→product scratch byte` 一一映射；
- 每个 SA product write 的 bank/column/terminal/valid-byte coverage；
- product scratch drain 后 GA reload 的 barrier、visibility 和 accepted-handshake lifetime；
- GA A/C dual-stream tag/last/last_index、normal FIFO drain 和逐级 scratch coverage；
- 64-term node0004 tree、显式 bias leaf、所有 padding 与最终 INT32 endpoint；
- typed handler 或获批 manual materializer 的逐 leaf owner/input/formula/old/new/auth；
- final JSON→mapping→bitstream→execplan/SCA/address/lifetime→config-bound inverse；
- fresh node0004 exact UINT8 tail 与完整 3,211,264-byte logical output 对 W3 逐 bit一致。

node0071 GAP sum-stage local E2 只可证明 stage2+ INT32 scratch/reload/GA-tree 公共原语；
不得代替 node0004 product stage、地址方程或 Conv typed topology。复合路线允许作为
本地 `CONFIG_ONLY_CORRECTNESS_BASELINE` 候选，不是 production 路线。822,083,584-byte
最小逻辑 product scratch、额外 tree scratch/start/barrier/traffic 和低利用率必须在
机器合同中显式报告。

规则 ID：`CDA-COMPOSITE-SCRATCH-GLOBAL-VS-TILED-CAPACITY-001`

全局 scratch 超过总物理容量时，不得直接把 topology 判为不可行，也不得忽略容量：
必须给出 tile residency、每 tile 非重叠 region、单 slice headroom、wave count、
跨 wave 重用/释放点、barrier 和全层 traffic lower bound。只有最小合法 tile 仍超过
可用容量，或其 lifetime/traffic 无法由最终 schedule 表达时，才能归类资源硬阻塞。

node0004 的 proposal-only 证明固定为 128 个 `(n,oc_group8)` tile、每 tile
13,046,304 bytes、单 slice 容量 25,165,824 bytes、五波 `[28,28,28,28,16]`；这只关闭
容量下界，不关闭物理 materializer。

规则 ID：`CDA-PREDESIGN-SYMBOLIC-ADDRESS-NOT-PHYSICAL-COVERAGE-001`

proposal-only affine bijection可以关闭 logical byte schedule，但 final occurrence
hash、LC/MSE/Buffer bank/column、SA lane packing、last/last_index、direct scratch
write 或 bitstream 任一未绑定时：

- `materialized_configuration_mechanism` 必须为 null；
- 不得称 final physical coverage、local E2 或 baseline；
- 不得生成依赖该 coverage 的 target JSON 或测试包。

node0004 当前首个物理 blocker 为
`B_CONV_C1_SA_SCALAR_PRODUCT_MATERIALIZER_AND_TERMINAL`。它要求为
205,520,896 个单产品 occurrence 建立最终 lane/terminal/direct INT32 scratch write
与 occurrence inverse；逻辑地址和容量已闭合不能替代该门。

## 4. production 路线与 RTL 授权

规则 ID：`CDA-SA-INT8-RTL-COMPATIBILITY-001`

production Conv/MatMul 必须使用能够精确实现 signed 18-bit `dot4` 并与 psum32
累加的兼容/修正 RTL identity。最小功能修复提案只能作用于
`SA_PE_Mul_Array` 的 INT8 branch：

- 两个 signed 17-bit pair sum 合成为 signed 18-bit `dot4`；
- integer `last_A=signext32(dot4)`、`last_B=0`、`last_C=psum32`；
- 后续继续使用现有 32-bit `CSA_3to2`；
- 公共 `CSA_4to2`、FP16/BF16 branch、接口和配置编码保持不变。

本规则只定义兼容性和验收条件，不授权修改功能 RTL。实际修改 `rtl/**`、生成 repair
服务器包或选择新的服务器 RTL 身份，仍须用户本轮明确授权。获批后至少通过本合同全部
反例、small-domain exhaustive、完整合法边界和独立 RTL testbench/observer。

兼容 RTL 验收必须同时保留三栏模型：

1. `stock_four_lane`：已知错误的 negative control；
2. `proposal_signed18`：未来兼容 RTL 的逐 occurrence oracle；
3. `serialized_one_product`：只作为 `DataC=0` 的单产品 primitive oracle，不再是
   accumulate 正确性基线。

每个 occurrence 必须比较 packed DataA/DataB、DataC 实际门控、两个 signed17 pair sum、
signed18 dot4、result bits 和 tail lane count；final-only equality 不足以放行。当前本地
repair-oracle proof 已覆盖 44,280 个 small-domain case、完整单乘积合法域、四 lane
合法边界、psum32 正负 wrap、K=3/5/6/7 tail 以及 nonzero x-zp+bias；其中 serialized
列只证明软件候选方程，不能再解释为 stock RTL 含 DataC 的动态通过。

未来 RTL identity 的 `current_binding` 必须默认为 null，只能接受用户提供或本轮明确
授权的 identity label、不可变 SHA manifest、top/module binding、本地 compile/sim
命令和 TB adapter。禁止自动发现服务器路径、名称或当前 RTL identity。

## 5. Conv/MatMul 共用停止门

规则 ID：`CDA-SA-INT8-CONV-MATMUL-COMMON-GATE-001`

以下 production/family blocker 在兼容算术路径闭合前保持开放：

- `B_CONV_INT8_SA`
- `B_MATMUL_INT8_SA`
- `B_CONV_CONFIG_BOUND_SIMULATOR_RTL_CSA_MISMATCH`
- `B_CONV_STOCK_RTL_INT8_DOT_CAPABILITY`
- `B_SA_INT8_DUPLICATE_CARRY_SHIFT`
- `B_SA_INT8_REDUCTION_WIDTH`
- `B_SA_INT8_DATAC_PSUM_GATED_ZERO`
- `B_CONV_SA_PRODUCT_SCRATCH_SCHEDULE_AND_OWNERSHIP`
- `B_CONV_C1_SA_SCALAR_PRODUCT_MATERIALIZER_AND_TERMINAL`
- `B_CONV_GA_EXACT_ALTERNATIVE_TYPED_TOPOLOGY`
- `B_SA_COMPATIBLE_RTL_IDENTITY_PENDING`

`B_SA_SERIALIZED_FALLBACK_MATERIALIZATION` 仅指 fresh single-product stage；
不能关闭完整 accumulate blocker。node0004 fresh composite 完整 local E2 与测试包形成
前，不得进入其他实例的批量 materialization。配置相似、单 product 通过、GA primitive
单测通过、四 ones 被修复或 MatMul shape 更小均不能绕过共用门。

主线授权记录：
`.agents/task_records/20260728_conv_c0_mainline_adjudication_and_composite_c1_authorization.md`。
