# ndp-sim ResNet50 复用审计与主线重规划

日期：2026-07-27  
状态：`READ_ONLY_AUDIT_COMPLETE_REPLAN_FROZEN`

## 1. 主线裁决

本轮接受“ndp-sim 已包含除 Conv 外的大部分 ResNet50 算子或近似原语”作为新的盘点输入，
但不把模板存在、上游测试或名称相似升级为目标实例放行。78 个 ONNX 节点仍分为 8 类：

| ONNX 算子 | 节点数 | 当前裁决 |
|---|---:|---|
| QLinearConv | 53 | INT8 SA 普通点积语义仍是核心缺口 |
| QLinearAdd | 17 | add-dequant 与普通 add 可复用；缺完整 output requant 和复合后端 |
| QuantizeLinear | 2 | INT32→UINT8 oracle 可复用；缺精确 FP32→UINT8 变体 |
| DequantizeLinear | 2 | 已有可复用实现；node0077 正式闭环，node0072 仅需实例适配 |
| MaxPool | 1 | 目标模板和无符号 max 静态语义已存在；缺 flow/mapper/动态闭环 |
| QLinearGlobalAveragePool | 1 | UINT8→INT32 sum 与 requant 原语均存在；缺两级物化和控制闭环 |
| Flatten | 1 | 不需要计算算子；缺物理 alias/offset/lifetime |
| QLinearMatMul | 1 | 与 Conv 共用 INT8 SA 点积根缺口，且输出 requant 为非零 zero-point |

严格按“精确 ONNX backend”统计，除 Conv 外仍缺 QuantizeLinear、QLinearAdd 和
QLinearMatMul 的完整后端。按“需要新增的独立能力”统计，工程缺口收敛为：

1. `R5_GAP_EXACT_UINT8_QUANT_TAIL`：FP32/INT32→UINT8、任意 zero-point、float32 scale、
   nearest-even、saturation、shape/layout 与 typed transport 的统一精确量化尾；
2. `R5_GAP_INT8_SA_DOT_PRODUCT`：可靠的 UINT8×INT8→INT32 SA 点积；Conv 与 MatMul
   共用；
3. `R5_GAP_COMPOSITE_BACKEND_INTEGRATION`：把既有原语组合成 QLinearAdd、GAP、
   MaxPool 与 View 的精确 DAG，并绑定 handler/mapper/address/lifetime。

前两项为 P0；第三项为依赖 P0 的 P1/P2 物化工作。上述 `R5_GAP_*` 是本记录的规划
gap ID，不自动成为公共 blocker 或规则 ID。

## 2. 复用与测试证据边界

`contracts/operator_config/ndpsim_json_corpus_v1.json` 记录 55 份模板，其中 53 份被标为
用户授权的上游硬件测试参考，2 份为项目新增/修改 candidate。这提高字段和拓扑复用的
可信度，但不证明：

- 精确 ResNet qdomain、rounding、saturation 与广播语义；
- handler 与 address-remapping registry 已注册；
- 目标 instance 的 JSON→mapping→bitstream→execplan/SCA 回环；
- config-bound simulator、E4 或 E5。

当前源码仍显示：

- `quant_from_buffer_int32MN_uint8MN` 和
  `add_dequant_uint8CWH_uint8CWH_fp32CWH` 的 control-register handler 标注
  `Placeholder`；
- address-remapping 测试明确断言 quant、add-dequant、avgpool 与 maxpool 不在默认
  registry；
- 原生 GEMM/GEMV 是 FP16，不能替代目标 UINT8×INT8→INT32 MatMul；
- MaxPool 有 UINT8 无符号 max 静态证明，但仓内没有等价的目标硬件通过记录；
- 正式 ResNet 三方闭环仍只有 Dequant node0077/v6，计数保持 1/78。

## 3. 重新规划的任务方案

### P0-A：统一精确 UINT8 quant tail

主 owner：QuantizeLinear 族；RequantizeUint8 提供 54-stage 分类和非零 zero-point 反例。

当前只允许：

- 建立 FP32/INT32 ingress、任意 zero-point、nearest-even、saturation 的 capability matrix；
- 冻结统一 numeric DAG、typed transport 和反例集合；
- 向主线提交 `RULE_DELTA_PROPOSAL` 与 `BLOCKER_DELTA`。

当前禁止生成目标 JSON、服务器包或运行服务器。专项规则和共享合同仍须由主线裁决。

### P0-B：INT8 SA dot-product 共因

主 owner：Conv/SA 族，同时覆盖 QLinearMatMul accumulate。

当前只允许：

- 保留普通点积最小反例；
- 明确 stock RTL、candidate config 与目标 UINT8×INT8→INT32 的首处分歧；
- 提供兼容实现/RTL 身份/授权选项。

在取得兼容实现或新授权前，不继续 bias/psum/tail，不生成 Conv/MatMul 包，不改功能 RTL。

### P1-A：QLinearAdd 复合后端

依赖 P0-A。QLinearAdd 族先设计：

- 16 个同 shape residual add；
- 1 个 `[1000]→[16,1000]` broadcast bias add；
- 六 qparam transport；
- add-dequant→精确 quant tail 的 stage DAG；
- 三 edge allocation/address/lifetime。

共享 quant tail 与专项规则未获主线批准前不得物化。

### P1-B：Requant 一般化

依赖 P0-A。保留 54/54 W3 exact、33 个 zero-point-zero 数值兼容、21 个当前 guard
反证、仅 node0001 物理 E2 的边界。服务器 event-edge 诊断不再作为本次语义重规划的
前置条件；没有用户实际上机时不授予 lease。

### P2：直接复用物化

在 P0 合同稳定且主线另行派发后，分别处理：

- Dequant node0072 实例适配；
- MaxPool target mapper/flow；
- GAP sum→requant 两级物化；
- Flatten physical view。

不同 family 继续分任务，不在既有 Dequant 或其他族任务中混做。

## 4. 控制面边界

- 本轮未读取或核验任何服务器文件、服务器名称、RTL/Makefile/filelist/TB/Git 身份；
- 未生成 JSON、mapping、bitstream、execplan/SCA 或服务器包；
- 未授予 `SERVER_RUNNING` lease；
- 未修改 `.agents/rules/**` 或 `rtl/**`；
- 既有 Requant event-edge 与 human JSON variable-root 包保持冻结，只读待命；
- 生成前 fail-closed、无同门动态基线不称 regression、正式三方计数 1/78 均保持。

## 5. 机器记录与读取身份

机器记录：

- `contracts/operator_config/resnet50_ndpsim_reuse_gap_audit_v1.json`

关键输入：

| 路径 | SHA256 |
|---|---|
| `.agents/agent.md` | `5a4660df1e771b75045c45f75e08b7eba771542750b91ab18af6ab0434043de0` |
| `.agents/plan.md`（编辑前） | `d641693de626c45ca7dbe80cb79a68360de619eafa81a6fb6274b7a088df4f5e` |
| `.agents/rules/生成前必读索引.md` | `539e8dfbe52ad9fc8bd9fdef8c69d448fb5fd713e938e3adc5f663f82fd806d7` |
| `contracts/typed_config_parameter_contract.json` | `abbc87b0b13c92611a90fe1767b32b15fe9c49f23bee616ca2bb51219dd181bd` |
| `contracts/resnet50_r5_lowering_bundle.json` | `bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432` |
| `contracts/operator_config/ndpsim_json_corpus_v1.json` | `bd2527db3470521e309acd43224dc15a694b210b293011e944f964e9b76270e3` |
| `ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json` | `db638f0640e74217e80e61350a2fe400f7b495e2201f17c39915328cdd455ba2` |
| `ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json` | `15f5321ab57cb73ca2f650693859657759f834389677451a9a89e66217e9e6da` |
| `ndp-sim/jsons/avgpool_config_2048_7_7.json` | `a3d19c7b1759eb40b66a6b786234865b61917e9cf74822a62dd469729c2497c5` |
| `ndp-sim/jsons/maxpool_config_16_112_112_stride2_padding1.json` | `a0091f3fae223abd5225c54b833cf3bb578b3fea6b202883c5cbf4be50d60cb1` |

详细 source identity、逐算子分类和计划依赖以机器记录为准。
