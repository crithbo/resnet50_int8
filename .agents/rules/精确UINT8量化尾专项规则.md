# 精确 UINT8 量化尾专项规则

最后更新：2026-08-11（剥离实例状态，仅保留共享精确尾合同）

本文件保存多个 ResNet50 算子共享的“缩放/除法后精确舍入、加 UINT8 zero-point、
饱和输出”专项增量。适用消费者包括 QuantizeLinear、RequantizeUint8、
QLinearAdd 输出、GAP/AverageRequant 输出和 QLinearMatMul 输出。公共 provenance、
物化回环、地址、证据等级和服务器门仍由公共规则拥有。

实例授权、物化完成度、candidate release 与 E4/E5 状态只记录在 `.agents/plan.md` 和
对应 `.agents/task_records/`。本文件只拥有可跨 Quantize、Requantize、QLinearAdd、
GAP 与 MatMul 复用的数值顺序、有限域和能力矩阵。

## 1. 复用边界

允许继续作为原语或结构 oracle 的资产：

- conversion flag 全关闭时的 raw FP32 GA ingress；
- `quant_from_buffer` 的 LC/MSE/Buffer/two-PE 结构；
- 8-lane raw FP32 constant 与 raw INT32 constant transport；
- 在 integer decode 已正确时的 GA outport UINT8 saturation；
- generic content-addressed typed value envelope。

不得直接复用为目标后端：

- 固定 `[1,32,32]`/rank-3 schedule；
- 把 output zero-point 加进 FP32 magic bias 的旧配方；
- placeholder control handler；
- 未注册的 mapper topology；
- 只在特定输入域无 mismatch 的实例级 recipe。

## 2. 数值顺序与 FMA 门

规则 ID：`CDA-QUANT-TAIL-NUMERIC-ORDER-001`

目标算子的每个显式 FP32 运算和舍入点必须按 W3/ONNX 顺序保留。软件要求
“先 FP32 multiply，再 RNE”时，不得把 multiply 与 magic-add 收缩成一次 FMA，除非对
该实例完整合法输入域证明 bit-exact 等价。

首个硬件区分向量固定为：

```text
input_int32 = 400
multiplier_bits = 0x3d828f5c
zero_point = 0
sequential_fp32_multiply_then_rne = 26
one_round_fused_magic_model = 25
```

该向量未在配置绑定硬件语义中闭合前，`B_QUANT_TAIL_FMA_ROUNDING_POINT` 保持开放。
Requant node0001 的实例级本地 E2 或 33 个 `zp=0` stage 的 W3 数值兼容，均不能自动
推广成无条件 FMA 舍入能力。

QuantizeLinear 还必须实现精确 FP32 division 顺序。`x/scale` 不得默认改写为
`x*reciprocal` 或 reciprocal-FMA；此门只约束 division 消费者，不误标 Requant
multiplier 路径。

## 3. zero-point 必须在 RNE 后加入

规则 ID：`CDA-QUANT-TAIL-ZP-AFTER-ROUND-001`

目标顺序固定为：

```text
rounded = round_to_nearest_even(scaled)
shifted = rounded + output_zero_point
out = clamp_uint8(shifted)
```

不得把任意 zero-point 改写进 FP32 magic bias。对 `scaled=0.5,zp=1`，旧
zp-in-bias 路径得到 2，目标结果为 1。

当前 proposal-only 配方为固定 FP32 magic bias `12582912.0`，并把 zero-point 编入
raw `INT32_SUB` constant：

```text
0x4b400000 - zero_point
```

该配方只有在舍入边界、三 PE/四 lane topology、typed binding、mapper 和完整物化回环
全部闭合后才能批准。Requant 的 5 个 odd nonzero-zp stage 还必须保留 tie-parity 门。

## 4. magic 有限域

规则 ID：`CDA-QUANT-TAIL-MAGIC-DOMAIN-001`

每个 magic-round 实例必须从真实 W3/typed request 证明 scaled 值的有限上下界，并覆盖
下溢、上溢、0/255 饱和和边界相邻值。对 `scaled=-12582913,zp=0`，当前 magic decode
后再饱和会错误得到 255，因此无界输入不得使用该配方。

Requant 全族当前细分为：

- 33/33 `zp=0`：保留 W3 数值兼容，但全部被 FMA rounding 与 magic finite-domain 门
  阻塞；33/33 的正式 W3 均含负值；
- 16 个 even nonzero-zp：signed ingress、rounding、finite-domain 阻塞；
- 5 个 odd nonzero-zp：除上述三门外，再加 zero-point-after-RNE/tie-parity；
- QLinearMatMul requant `r5:hwop-0075-01,zp=60` 另有 rank-2 layout blocker。

## 5. capability matrix 独立放行

规则 ID：`CDA-QUANT-TAIL-CAPABILITY-MATRIX-001`

以下 12 个能力格必须独立给出状态与证据，禁止一个原生模板或单个动态 pass 代替整个
量化尾：

1. FP32 ingress；
2. nonnegative INT32 ingress；
3. signed INT32 ingress；
4. FP32 scale/multiplier 或 exact division；
5. 任意 UINT8 zero-point；
6. nearest-even rounding；
7. UINT8 saturation；
8. GA topology；
9. shape/layout/transaction/tail；
10. typed handler；
11. mapper registration；
12. execplan transport 与 materialized roundtrip。

保持开放的共享 blocker 至少包括：

- `B_QUANT_TAIL_FMA_ROUNDING_POINT`
- `B_QUANT_TAIL_MAGIC_DOMAIN_BOUND`
- `B_QUANT_TAIL_EXACT_FP32_DIVISION`
- `B_QUANT_TAIL_SIGNED_INT32_INGRESS`
- `B_QUANT_TAIL_THREE_PE_TOPOLOGY`
- `B_QUANT_TAIL_TYPED_BINDING`
- `B_QUANT_TAIL_MAPPER_REGISTRATION`

其中 exact FP32 division 只映射到实际 division 消费者；其他 blocker 按各 family 的
输入域和拓扑逐项映射。任一相关格仍为 `CONTRADICTED`、`HARDWARE_ORDER_UNKNOWN`、
`PLACEHOLDER_BLOCKED`、`REGISTRY_MISSING` 或仅 proposal 时，禁止生成正式目标 JSON、
mapping、bitstream、execplan/SCA 或服务器包。

## 6. raw signed guard 不能由 FP32/per-byte max 或最终饱和替代

规则 ID：`CDA-QUANT-TAIL-RAW-SIGNED-GUARD-001`

当某实例试图用：

```text
raw signed INT32 acc
→ max(acc, 0)
→ nonnegative INT32-to-FP32
→ scale / RNE / UINT8 saturation
```

绕过已反证的 signed INT32-to-FP32 ingress 时，必须在转换前同时证明：

- 活动 opcode 和 RTL 存在 raw signed 32-bit word compare/select；
- typed handler/mapper 明确运输 INT32 dtype、零常量和 compare/select 语义；
- 最终 materialized occurrence、地址、terminal 与 accepted lifetime 消费的是原始
  accumulator，而不是 host 生成的 max0 tensor；
- 全合法域和冻结 W3 的最终 UINT8 等价性均成立。

FP32 `max` 必须先转换，不能解决 signed ingress；`int8_max` 是四个独立 byte lane，
不能比较 signed INT32 word；最终 UINT8 saturation 恰好遮蔽负值也不能替代中间硬件
证据。不存在 raw signed guard 时必须在其处 fail-closed。

node0004 的数学改写已对全 signed INT32 域证明：64 个 multiplier 均为有限正数且
`y_zp=0` 时，原公式与先做 max0 的最终 UINT8 相同；正式 W3 的 3,211,264 元素、
1,262,480 个负累加值也为 0 mismatch。但活动编码中：

```text
FP32 max = opcode 3
INT8 max = opcode 11
INT32 sum/sub/mac = opcode 12/13/14
INT32 class requires opcode[4:2] = 3'b011
max requires opcode[2:0] = 3'b011
```

两项在 bit2 上矛盾，0..31 无交集，也不存在 `int32_max`。因此
`B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE=OPEN_CONTRADICTED` 是 node0004 该绕行的
首断点；nonnegative converter、顺序 MUL→RNE、per-channel transport、mapper 与
composite endpoint 均为后续未达门。该审计不生成 tail target，也不构成
`CONFIG_ONLY_CORRECTNESS_BASELINE`。
