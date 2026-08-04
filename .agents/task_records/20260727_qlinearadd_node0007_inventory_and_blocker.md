# QLinearAdd node-0007 代表实例盘点与首个结构 blocker

日期：2026-07-27  
任务边界：只处理 QLinearAdd / residual add；未修改 plan、公共/专项规则、功能 RTL 或其他算子族资产。

## 1. 裁决

- 代表实例冻结为 `node-0007 / hwop-0007-00 / r5:hwop-0007-00`，
  ONNX 名称 `resnetv17_stage1__plus0_quant`，硬件 family
  `QLinearAddUint8`，stage `add_requantize`。
- 这是 ResNet50 stage1 的真实 residual merge，不是 oracle 替身。两个数据输入均为
  `uint8[16,256,56,56]`，总计各 `12,845,056` bytes；无 broadcast 扩张。
- 本轮只能冻结 typed node、tensor identity、逻辑 shape/dtype/qparam 和拓扑 lifetime
  需求；不能冻结物理地址、buffer allocation 或 release point。活动机器合同明确将三条
  相关 edge 标记为 `blocked_until_address_offset_and_lifetime_are_bound`，并将本 stage
  的 `buffer_allocation_available`、`lifetime_release_available`、
  `address_alias_or_copy_decision_available` 标为 `false`。
- QLinearAdd 专项规则不存在。依据生成前停止门，缺专项规则时不得创建最终 JSON。
- 活动 native backend 只有相关模板
  `ndp-sim/jsons/add_dequant_uint8CWH_uint8CWH_fp32CWH.json`。它是
  uint8+uint8→FP32 add-dequant，不消费 `y_scale/y_zero_point`，不能充当完整
  uint8 QLinearAdd。`prefill_add_fp32MN_fp32MN_fp32MN.json` 只提供普通双输入 FP32
  add 的 LC/MSE/Buffer/GA/normal-outbuffer 结构对照，也不能批准量化路径。
- 因此本轮在生成前 fail closed：未生成 family generator/最终 JSON/mapping/bitstream/
  execplan/SCA/config-bound simulator/server package。

## 2. 冻结 typed 合同

### 身份与数据端口

| 项 | 冻结值 |
|---|---|
| A | `tensor-a2a1607bd3ac6eee`, `resnetv17_stage1_batchnorm2_fwd_quantized`, producer `r5:hwop-0006-01` |
| B | `tensor-01b2df1cb3665358`, `resnetv17_stage1_batchnorm3_fwd_quantized`, producer `r5:hwop-0003-01` |
| Y | `tensor-32e7128618bb2a38`, `resnetv17_stage1__plus0_quantized`, consumers `r5:hwop-0008-00` 与 `r5:hwop-0011-00` |
| shape/layout | logical NCHW `[16,256,56,56]`; 已批准的 W4-28 layout 只解决软件物理兼容，不等于最终 hardware allocation |
| dtype | A/B/Y 均 `uint8` |

### qparam

| 参数 | 十进制值 | 精确位/值 SHA-256 |
|---|---:|---|
| `a_scale` | `0.017621304839849472` | FP32 `0x3c905a8e`; `dcd461e2fdcafb3350e07693f22ef4ab7f080522fb4911a39ecb939dd637d7ba` |
| `a_zero_point` | `84` | `e632b7095b0bf32c260fa4c539e9fd7b852d0de454e9be26f24d0d6f91d069d3` |
| `b_scale` | `0.03495480865240097` | FP32 `0x3d0f2cc6`; `335f7953fca604a1ba5ee319290c6f21288e9ca94a5808bc351a5d4ca42f840a` |
| `b_zero_point` | `150` | `84873854dba02cf6a765a6277a311301b2656a7f770851828fe792ecef9092e3` |
| `y_scale` | `0.01425931230187416` | FP32 `0x3c699fe4`; `089a2c66a9c6614ae54bd3c0112720c056a13240788aa0e942dafacd4073a181` |
| `y_zero_point` | `0` | `6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d` |

独立 W3/ONNX 数值合同必须保持：

```text
r = float32(a_scale) * (int32(A) - int32(a_zero_point))
  + float32(b_scale) * (int32(B) - int32(b_zero_point))
Y = saturate_uint8(round_nearest_even(r / float32(y_scale)) + int32(y_zero_point))
```

任何 hardware 分解都必须逐操作顺序、逐舍入点证明与此式 bit-exact；把两个 affine branch
代数合并、只完成 FP32 add-dequant、或省略最终 nearest-even/UINT8 saturation 均不等价。

## 3. 首个结构 blocker

`BLOCKER_DELTA`：

```text
B_QADD_SPECIALTY_AND_MATERIALIZATION_CONTRACT
```

首处 fail-closed 原因是目标专项规则缺失，并且活动 native transport/handler 没有承载
QLinearAdd 的六个 typed qparam；现有相关模板在 FP32 输出处终止。其直接后果是无法合法
决定：

1. A/B 两个独立 read stream 如何进入不同 qdomain 的 affine 对齐，以及三输入/多流 GA
   的 producer、matching、readiness 和共享 LC backpressure；
2. 乘加顺序、FP32 或整数中间域、nearest-even 舍入位置、UINT8 saturation，以及
   normal outbuffer→MSE write 的精确 occurrence；
3. 28-slice 分片、tail identity、Buffer AG bank/byte、buffer lifetime、MSE occurrence、
   output address/release point；
4. 最终 address-bound JSON 的合同回读与 JSON→mapping→bitstream→execplan/SCA 的完整
   回环；
5. config-bound simulator 的实际配置消费和 formal D golden。

现存 blocker `B_ADD_DUAL_QDOMAIN`、`B_ADD_UINT8_REQUANT`、
`B_EXECPLAN_TYPED_TRANSPORT`、`B_ADD_REQUANT_E5`、`B_SERVER_E4_E5` 均保持；本记录不关闭
其中任何一项。

## 4. RULE_DELTA_PROPOSAL

建议主线新增 QLinearAdd 专项规则，至少包含：

- 固定 QLinearAdd W3 公式、FP32 输入 scale 精度、nearest-even 与 saturation 顺序；
- 两个 data tensor 与六个 qparam 的独立 provenance，以及禁止把 add-dequant 当作完整
  QLinearAdd；
- 授权的 hardware stage DAG：每个 affine branch、add、output requant 的真实 GA/SFU
  opcode、端口和中间 dtype；
- A/B 两流 readiness、共享 LC backpressure 无环证明、普通 normal outbuffer 和 MSE
  write occurrence；
- 28-slice layout、tail value、Buffer AG bank/byte、地址和跨消费者 lifetime；
- final materialized JSON 反解、原生 pipeline、config-bound simulator、formal D 和
  E4/E5 专项门；
- 若 stock RTL 缺少完整 output requant 数据路，要求报告首个 checkpoint 分歧，不允许
  用 add-dequant、软件公式或重复封包放行。

## 5. 下一步最小动作

主线先裁决并落地专项规则/授权 transport 设计。随后本族任务才能：

1. 为 `hwop-0007-00` 冻结确定的 stage DAG 与 physical allocation/lifetime；
2. 编写 family-specific generator/validator/test；
3. 生成最终 address-bound JSON 并做合同回读；
4. 完整重建 mapping/bitstream/execplan/SCA，完成 config-bound simulator 与 golden E2；
5. 仅在 blocker 明确关闭且 E2 通过后，生成一次 `candidate_release=false`、
   `rtl entries=0` 的组 B `NDP_copy02` PACKAGE_READY_NOT_RUN 候选。

当前没有主线 lease，也没有 PACKAGE_READY_NOT_RUN 或服务器运行。

