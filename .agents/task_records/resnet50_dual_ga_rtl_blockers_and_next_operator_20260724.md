# ResNet50 两个 GA RTL blocker 与下一算子选择

日期：2026-07-24

本记录响应“把两个问题都记录，再重新找一个不触发这两个问题的 ResNet 算子”。
本轮只更新规则、计划和选择依据；没有修改功能 RTL、算子 JSON、bitstream、execplan、
SCA、服务器测试包或历史回传。

## 1. 两个问题必须正交登记

| 问题 | issue / blocker | 精确触发 | 当前影响 |
|---|---|---|---|
| GA INT8 pipeline0 反压及 INT8 max 数值分支 | `CDA-GA-INT8-MAX-PIPE-001=CONTRADICTED`；`B_GA_INT8_MAX_FLOW`、`B_GA_INT8_MAX_NUMERIC` | GA opcode 为 `int8_max=0x0b`，首项后仍需接收后续归约输入 | ResNet `node-0002 / hwop-0002-00 MaxPoolUint8` |
| GA INT32 transout accumulator | `CDA-GAP-GA-ACCUM-STATE-001=CONTRADICTED`；`B_GAP_GA_ACCUM_STATE` | `int32_sum=0x0c` 在 outbuffer occupancy=1 时固定减 2，count 回绕为 3；tag 清除但 data 保留，随后无 valid guard 地反馈旧 C | ResNet `node-0071 / hwop-0071-00 GlobalAverageSumInt32` |

二者位于同一 General Array，但 opcode、pipeline 分支、触发状态和修复点不同。
GAP 的输入 tensor 虽为 UINT8，GA 执行前已转换为 INT32，不能把它归入前一个
INT8 pipeline0 缺陷。修复其中一个 blocker 不得解除另一个。

绑定证据：

- `contracts/ga_int8_pipeline_backpressure_defect_report_20260723.md`
- `server_returns/gap_hwop0071_probe_v7_return_20260724/GAP_PROBE_V7_DIAGNOSIS.md`
- `server_returns/gap_hwop0071_configfix_stockrtl_v10_evidence_20260724/`
- `NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Inbuffer.sv`
- `NDP_copy01/rtl/Slice/General_Array/GA_PE_Group/GA_PE_Outbuffer.sv`

## 2. 候选筛选

筛选条件：

1. 必须是正式 ResNet50 lowering 中的 stage；
2. 不使用 GA `int8_max`；
3. 不使用 GA `int32_sum` transout；
4. 优先选择非 transout 的真实计算算子；
5. 不能用存在第三个已知 RTL 数值反例的路径替代；
6. 当前只选择下一开发目标，不把本地结构关系写成服务器通过。

| family / 代表 | 裁决 |
|---|---|
| `View`, `hwop-0073-00` | 完全不触发两个问题，但只是 zero-copy alias，没有独立硬件计算，保留为布局控制，不选作下一计算算子 |
| `DequantizeLinear`, `hwop-0077-00` | **选择**。形状 `[16,1000]`，目标是 UINT8→FP32 仿射；从授权参考中隔离 FP32 `mac` 分支，`transout_last_index=null` |
| `QuantizeLinear` | 不触发两个问题，但当前缺 FP32 输入精确 recipe 和 rounding 执行闭合，复杂度高于 Dequantize |
| `QLinearAddUint8` | 不触发两个问题，但有双量化域与输出 requant，需组合两个仿射分支，复杂度更高 |
| `RequantizeUint8` / `AverageRequantizeUint8` | 不触发这两个问题，但进入已反证的 `B_GA_INT32TOFP32_INPUT_DOMAIN`，不作为规避 RTL 缺陷的下一候选 |
| `ConvInt32Accumulate` / `MatMulInt32Accumulate` | 走 Specialized Array，不触发两个 GA 问题，但受 `B_SA_INT8_CSA_NUMERIC` 等独立 RTL/语义 blocker 阻塞 |
| `MaxPoolUint8` / `GlobalAverageSumInt32` | 分别直接命中本记录的两个 blocker，排除 |

## 3. 选定算子

选定：

```text
request_id: r5:hwop-0077-00
node_id: node-0077
onnx_name: resnetv17_dense0_fwd_DequantizeLinear
family: DequantizeLinear
input: uint8[16,1000]
output: float32[16,1000]
```

选择理由：

- 输入规模小于另一个 `hwop-0072-00` 的 `[16,2048,1,1]`；
- 已授权模板 `ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json`
  提供 UINT8→FP32 仿射结构；
- 该模板的两个 UINT8→FP32 仿射分支使用 FP32 `mac`；模板末级 `add` 只负责合并
  两个分支，不属于 standalone Dequantize 目标；
- 所有相关 PE 的 `transout_last_index` 都为 `null`，不会进入本次 GAP 的
  outbuffer 自归约状态机；
- 不经过 Specialized Array，避免把下一轮改成 SA INT8 数值缺陷裁决。

## 4. 尚未解除的边界

该选择不等于服务器包已经可生成。当前仍须先关闭：

- `B_DEQUANT_STANDALONE`
- `B_DEQUANT_STANDALONE_RECIPE`
- `B_EXECPLAN_TYPED_TRANSPORT`
- 正式地址、mapping、bitstream、execplan、SCA/SCA_D、独立 golden 和 E4/E5

下一步应从授权 `add_dequant` 模板隔离一个只含 FP32 `mac`、可独立终止的
Dequantize 分支，证明
scale/zero-point 常量、端口、last/completion 和写回覆盖，再在全新身份下走原生
planner/encoder/execplan 链。本记录不授权直接复制双输入 add-dequant 模板，也不授权
生成新测试包或修改功能 RTL。
