# DeepSeek RoPE 增量规则

适用范围：由 DeepSeek GQA 中的非交错 RoPE 语义，经过显式 crop contract，
生成多 slice 的乘法、跨片配对与加法 stage。公共生成门、身份分级和证据等级
仍由生成前必读索引与公共算子配置规则拥有；本文只拥有 RoPE 特有语义。

## CDA-DEEPSEEK-ROPE-HALF-PAIRING-001

当 `rotary_interleaved=0`、每个 head 有 `H` 个连续元素、每片承载 `E` 个连续
元素，且切片顺序没有另行置换时，半向量距离为 `H/2`，对应切片距离为
`H/(2E)`。生成器必须从这些已验证量派生 producer→destination 路由，不得从
路由类型名猜测实现。

对于当前 crop：`H=128`、`E=32`、每 head 四片，所以源片与目标片的组内编号
必须满足 `destination = source xor 2`。`rope_slice_xor2` 这个字符串本身不是
证据；必须检查实际 consumer、最终 Write_Reg 地址和物理 payload 顺序。

## CDA-DEEPSEEK-ROPE-SIGN-SINGLE-OWNER-001

RoPE 的正负号只能由一处拥有，并且必须与半向量配对共同验证。以下两类实现
可以成立，但不得混用：

1. op1 使用未交换的激活，sin 表为前半 `+sin`、后半 `-sin`，乘积按半向量
   距离送往另一半；relayout 不再整体取负。
2. 在进入 op1 前显式交换半向量，并把 sin 表重排为前半 `-sin`、后半
   `+sin`；op1 输出与最终 add 同片，不再做跨片输出路由。

任何额外的全表取负、相邻片交换或隐式地址置换都必须有独立 payload 方程
证明。结构可生成、路由名称相似或最终 shape 相同均不能代替该证明。

## CDA-DEEPSEEK-ROPE-PAYLOAD-COVERAGE-001

可信 JSON 可以证明单 stage 的硬件配置字段，但只有覆盖全部参与片、全部输入
和全部中间输出的非空 payload，才能证明跨 stage 的配对及符号语义。空文件、
单片残留文件或仅有请求数量不能作为数值 oracle。

当前 `jsons/rope/install` 的 252 个 `matrix_{A,B,D}` `.bin` 文件中，仅
`op0/slice14/matrix_D_linearized_128bit.bin` 非空；其余 251 个为空。因此该
目录仍是配置/拓扑 oracle，不是完整 RoPE 数值 oracle。

## CDA-DEEPSEEK-ROPE-IMPLEMENTATION-CHOICE-001

生成正式 RoPE Stage 前，必须在机器合同中明确选择“跨片 XOR2”或“预交换、
同片 add”之一，并反解最终 bitstream/execplan 验证该选择。若 Stage、relayout
和路由 consumer 分属不同选择，必须 fail-closed，并分别保留
`STAGE_ROUTE_SEMANTICS` 与 `GOLDEN_RELAYOUT_SEMANTICS` blocker。

历史原生材料的裁决边界：

- ONNX Community 图只按 `SEMANTIC_MODEL_MATCH` 使用；
- 896/7Q/1KV/1-layer 均来自显式 crop contract；
- 当前 prefill Stage 仍选择跨片实现；
- 当前 `slice_routing.py` 实际执行 `slice_id ^ 0b11`；
- 当前 prefill golden 已把后半 sin 保存为负值，而当前 relayout 又整体取负；
- 在完整 payload 或硬件 readback 证明另一物理置换前，不得把该组合声明为
  RoPE 数值闭环。

本地规则闭环选择固定为第一种实现，即 `CANONICAL_CROSS_SLICE_XOR2`：

- 激活不预交换；
- sin 前半为正、后半为负；
- op1 producer→destination 为 `slice_id xor 0b10`；
- payload relayout 只做 `M8_N` 物理排列，不再拥有全局取负；
- op2 在目标片读取 op0 同片输出和由 XOR2 路由到达的 op1 输出。

该选择由项目侧只读隔离 overlay
`resnet50_pipeline/native_overlays/deepseek_rope/slice_routing.py` 落实到
execplan consumer；原生 checkout 保持不变。生成收据必须同时绑定原生
preimage、overlay postimage、两次隔离运行和最终逐 slice Write_Reg 路由。
不得只修改类型名或在合同里改写结论。

完整本地数值门要求 7 head × 4 slice 的 op0/op1/op2 所有 A/B/D 物理 payload
均非空，op0.A 与 op1.A 逐字节相同，并证明：

```text
y_first  = x_first  * cos - x_second * sin
y_second = x_first  * sin + x_second * cos
```

合成 payload 只能关闭公式、配对、符号与 relayout 的本地 E2；仍不得声明为
原始 ONNX 权重、硬件 readback 或 E4/E5。
