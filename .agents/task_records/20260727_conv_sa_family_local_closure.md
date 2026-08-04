# Conv / SA / MatMul 硬件族本地闭环记录

日期：2026-07-27  
状态：`BLOCKED_RTL_ARITHMETIC_AND_SIMULATOR_SEMANTICS_DIVERGE`  
证据等级：`E1_STATIC_SOURCE_BOUNDARY`  
`candidate_release=false`，`formal_target_instance_allowed=false`

## 范围与代表实例

- typed lowering 总览：133 stages，其中
  `ConvInt32Accumulate=53`、`MatMulInt32Accumulate=1`。
- 冻结代表：`node-0004 / hwop-0004-00`，
  `[16,64,56,56] × [64,64,1,1] → [16,64,56,56]`，stride 1、无 padding。
- `x_zero_point=0`，64 个 per-channel `w_zero_point` 全零；
  bias 为真实 W3 `int32[64]`，SHA-256
  `40bc2a3acbd553ffc067ea1c7b1c31cb59f18fca30451f55809ff76d2594bc0b`。
- 代表请求 SHA-256：
  `e27e10169168f3889df4c03bf15cb21de074abf3f3767dc4bee288425165874b`。

## 首个停止门

锁定的配置绑定 simulator 与 stock RTL 对 INT8 SA 的数值语义不一致：

```text
ONNX / NDPFuncModel:
  psum32 + Σ(s8(weight_i) × u8(activation_i))

stock RTL SA:
  psum32 + signext32(sum17) + (signext32(carry17) << 1)
```

RTL 证据位于
`NDP_copy01/rtl/Slice/Specialized_Array/SA_PE/SA_PE_ALU/SA_PE_Mul_Array.v`：
第一层 `CSA_4to2_int` 产生 `sum_int/carry_int`；`carry_int` 以
`{carry_int[30:0],1'b0}` 送入第二层 CSA，模块输出又把第二层 carry 左移一次。
`NDPFuncModel/component/SpecialPEA.py` 则明确执行 NumPy 普通
`sum(s8×u8)` 再加 psum。

最小反例：

```text
weights     = [1,1,1,1] (s8)
activations = [1,1,1,1] (u8)
psum        = 0
first CSA   = sum17=2, carry17=2
ONNX/model  = 4
stock RTL   = 6
```

因此 `CDA-SA-INT8-CSA-001=CONTRADICTED`。该差异发生在任意
tiling、bias/psum 生命周期、tail/padding、MSE occurrence 和 SA→Requant 交接之前，
不能由重排、bias 修正或 tail mask 消除。

## 闭环裁决

| 目标 | 裁决 |
|---|---|
| input/weight tiling | 已有结构模型，但不能形成数值放行 |
| bias 初值与 psum 累积 | 结构已建模；数值被 CSA 反例阻断 |
| tail/padding | 未越过算术停止门，不作通过声明 |
| SA→Requant | 未越过算术停止门，且本会话不接管 Requant |
| buffer/address/lifetime | 未越过算术停止门，不作通过声明 |
| MSE occurrence | 未越过算术停止门，不作通过声明 |
| mapping/bitstream/execplan/SCA | 不生成 release candidate |
| config-bound simulator/golden | simulator 使用普通点积，与 stock RTL 不兼容 |
| 服务器包 | 不生成；无 lease、无上传、无运行 |

## BLOCKER_DELTA

保持：

- `B_CONV_INT8_SA`
- `B_CONV_BIAS_PSUM`
- `B_EXECPLAN_TYPED_TRANSPORT`
- `B_LAYOUT_APPROVAL`

新增建议：

- `B_CONV_CONFIG_BOUND_SIMULATOR_RTL_CSA_MISMATCH`
- `B_CONV_STOCK_RTL_INT8_DOT_CAPABILITY`

关闭：无。

## RULE_DELTA_PROPOSAL

仅供主线裁决，不修改活动规则：

> 当 `CDA-SA-INT8-CSA-001` 仍为 `CONTRADICTED` 时，任何使用
> `NDPFuncModel SpecialPEA` 普通 INT8 点积语义的 Conv/MatMul
> config-bound simulator 均不得用于 stock-RTL release。

## 最小下一步

只能选择以下之一：

1. 提供实现普通 signed-weight/unsigned-activation dot 的新 stock RTL 身份，并从
   本地 E2 重新开始；
2. 明确授权一个不经过该 INT8 SA 路径、但精确实现 ONNX Conv/MatMul 的硬件拓扑，
   同时提供消费该拓扑最终配置的 simulator。

mapping 成功、encoder 成功、自然完成、重 tiling、bias 修正或服务器重测均不足以解除。

## 产物与验证

- 机器合同：
  `contracts/conv_sa_family_local_closure_v1.json`
  （SHA-256 `62b375c4ce090063403cd08b405a9fed05925790b38c0b0e8890a8d97a68492f`）
- validator：`resnet50_pipeline/conv_sa_family_closure.py`
- 入口：`tools/build_conv_sa_family_closure.py`
- 测试：`tests/test_conv_sa_family_closure.py`
- 命令：
  `.venv\Scripts\python.exe -m unittest -v tests.test_conv_sa_family_closure`
- 结果：3/3 passed。

完整读取 SHA 收据保存在机器合同 `read_receipt`。公共规则、plan 和功能 RTL均未修改。
