# node0004 exact UINT8 tail 全新 C1 依赖准备

日期：2026-07-28  
owner：QuantizeLinear / shared exact UINT8 quant-tail  
主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 1. 任务边界

本轮遵守主线覆盖裁决：node0004 全部旧本地 JSON、candidate、mapping、bitstream、
execplan/SCA、simulator output、report、package 与测试收据均不可信，只作负面历史，
没有被新生成器或 validator 消费。

允许且实际消费的来源只有：

- typed lowering/request；
- 正式 ONNX model 与 W3 accumulator/golden；
- 当前生成前索引、公共/NDP/tail/Requant 规则和主线覆盖记录；
- `repos.lock.json` 锁定的原生 `ndp-sim` 静态模板、typed model、handler、mapper、
  encoder 和 execplan 直接消费者。

本轮没有生成 node0004 target JSON、mapping、bitstream、execplan/SCA、完整 Conv、
服务器包，也没有检查或运行服务器。C0 仍为 `PENDING`。

## 2. 生成前读取收据

plan 只作 mutable provenance：

| path | SHA-256 | gate |
|---|---|---|
| `.agents/plan.md` | `e823f9d6cba28fff4659d0e2ba3ab3e0651be989feb0fd560a628095133d3fc9` | mutable provenance only |

当前匹配 fail-closed 规则：

| path | SHA-256 |
|---|---|
| `.agents/task_records/20260728_node0004_untrusted_fresh_rebuild_mainline_override.md` | `6626f3192390fe3b93483746f1dbd6a61cc13f21cd5b55559738cd3dfbad7c06` |
| `.agents/rules/生成前必读索引.md` | `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f` |
| `.agents/rules/算子配置规则.md` | `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171` |
| `.agents/rules/NDP硬件字段语义.md` | `a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59` |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `5593f9df3bbc5605e9b019b6cc53ee33b0edbeb203d657fdf974cb4b680c2df0` |
| `.agents/rules/RequantizeUint8算子配置规则.md` | `d9ec14cc6975e9596f3fe56e762cd4797c8ba6c70fa235503f5954e97c6f863f` |

其余 17 项 typed/model/W3/native source identity 由机器合同 current-match gate 完整保存。

## 3. RETURN_ANALYSIS

### 3.1 typed identity

```text
request_id  = r5:hwop-0004-01
node_id     = node-0004
hw_op_id    = hwop-0004-01
hw_op_type  = RequantizeUint8
predecessor = hwop-0004-00
logical     = INT32 NCHW [16,64,56,56] -> UINT8 NCHW [16,64,56,56]
elements    = 3,211,264
input bytes = 12,845,056
output bytes= 3,211,264
```

物理 layout、occurrence、transaction、address、lifetime、terminal 和 readback 均保持
`null`；只确认 `C=64` 因而任一未来 HWC8 方案没有 channel-mod-8 lane tail，不把该条件
事实写成已批准的 HWC8 endpoint。

### 3.2 全新 qparam identity

qparam 直接从正式 ONNX initializer 读取，并逐项与 lowering raw-byte SHA 交叉检查：

```text
x_scale = 0.021563487127423286, bits=0x3cb0a5e9
w_scale = float32[64], axis=0
y_scale = 0.007307368330657482, bits=0x3bef72a6
y_zero_point = uint8(0)
multiplier[c] = float32(float32(x_scale*w_scale[c])/y_scale)
multiplier sha256 =
  e83328d8589db8cfc2c5a1ff033d3c0e08d9bd87d8d8fcf52b8cb22189956bb2
multiplier min/max =
  2.7229637211689806e-08 / 0.01772809773683548
```

ONNX scalar的 canonical shape 为 `[]`，lowering transport shape 为 `[1]`；dtype、
element count 与 raw-byte SHA 相同。合同显式保存这一 crosswalk，没有静默把 shape
差异吞掉。

tail 类：

```text
REQUANT_INT32_PER_CHANNEL_FP32_MULTIPLIER_TO_UINT8_ZP0
signed INT32 ingress
per-channel float32 multiplier axis=0
sequential FP32 multiply -> nearest-even -> add zp0 -> clamp [0,255]
exact division = not applicable
```

### 3.3 正式 W3 新鲜回放

validator 直接读取正式 accumulator 与 UINT8 golden，没有读取任何旧 node0004 tail
report：

```text
element_count                  = 3,211,264
accumulator minimum/maximum    = -1,148,879 / 57,876
negative_count                 = 1,262,480
minus_one_count                = 128
zero_count                     = 112
below_zero_before_clip_count   = 948,480
above_255_before_clip_count    = 0
exact_halfway_count            = 0
formula vs golden mismatches   = 0
golden/replay payload SHA256   =
  2793bbe64e2b3289657f1c77bad61ebc54a4672791093d5c19a66ca742e7376e
```

该结果只关闭 qparam identity、软件公式和 frozen W3 数值，不是 hardware E2。

### 3.4 原生源码消费边界

授权 native template：

```text
ndp-sim/jsons/quant_from_buffer_int32MN_uint8MN.json
SHA256=db638f0640e74217e80e61350a2fe400f7b495e2201f17c39915328cdd455ba2
reuse_class=STRUCTURE_OR_PRIMITIVE_ONLY
```

它可复用的只有 LC/MSE/Buffer、8 组固定 `mac -> int32_sub` lane 和 UINT8 saturation
结构。其初始 shape 为 `A/D [1,32,32]`，静态 multiplier=`0.06375`、
magic bias=`12582975.75`，均不是 node0004 qparam。

直接源码审计：

- native `OperatorSpec` 只有 `op_id/op_type/used_slices/inputs/output`，没有 qparam；
- `quant_from_buffer_int32MN_uint8MN` handler docstring 明确为 placeholder；
- handler 只更新 3 个 loop end 和 read/write `dim_stride`；
- handler 没有 multiplier、magic、zero-point 或 subtract constant update；
- native mapper 将 `GA_PE` 视作固定物理资源，不形成 node0004 exact-tail qparam
  materializer/registration。

因此 typed handler=`PLACEHOLDER_BLOCKED`，per-channel multiplier/zero-point execplan
transport 均不存在。

### 3.5 是否存在纯配置精确路径

```text
exact_path_exists = false
decision = NO_EXACT_PURE_CONFIGURATION_PATH_CURRENTLY_PROVEN
first_unavoidable_capability = B_QUANT_TAIL_SIGNED_INT32_INGRESS
```

首个最小反例：

```text
accumulator = -1
expected IEEE FP32 bits = 0xbf800000
current native int32tofp32 bits = 0xcf000000
formal node0004 W3 hit count = 128
```

由于 multiplier 为正且 `zp=0`，该单点两条负值路径最终都会饱和为 UINT8 0；这种最终
masking 不能证明中间 signed ingress，也不能推广到合法输入域。当前规则中的 guard 路线
仍未成为 released exact signed-ingress capability。

随后仍独立开放：

- `B_QUANT_TAIL_FMA_ROUNDING_POINT`（沿用当前规则 26-vs-25 公共反例，不重做旧
  node0004 test）；
- `B_QUANT_TAIL_MAGIC_DOMAIN_BOUND`；
- `B_LAYOUT_APPROVAL`；
- `B_QUANT_TAIL_TYPED_BINDING`；
- `B_QUANT_TAIL_MAPPER_REGISTRATION`；
- `B_EXECPLAN_TYPED_TRANSPORT`；
- `B_NODE0004_C0_DEPENDENCY`。

## 4. BYPASS_ANNOTATION

```text
bypass_reason:
  native signed ingress and sequential rounding are not exact
contradicted_or_missing_native_path:
  direct signed INT32 conversion; sequential MUL->RNE; typed per-channel
  qparam transport; approved node0004 physical layout
exact_equivalence_scope:
  future path must cover the legal signed INT32 domain and the full frozen
  node0004 W3 tensor
materialized_configuration_mechanism:
  null
performance_and_resource_cost:
  not estimated before C0 and before an exact route exists
unresolved_production_blocker:
  all blockers listed in section 3.5
claim_boundary:
  dependency analysis only; CONFIG_ONLY_CORRECTNESS_BASELINE=false
```

## 5. DEPENDENCY_FOR_NODE0004_C1

已提供给 C1：

- fresh request/qparam identity；
- fresh formula/W3 replay；
- exact tail class；
- logical shape/dtype/byte count；
- signed-ingress first counterexample；
- native handler/mapper/execplan transport gap。

仍须等待：

```text
C0_RTL_AND_ENTRY_AUDIT = PENDING
full_conv_assembly_allowed = false
tail_target_generation_allowed = false
```

C0 选择路径后，还必须先取得 exact signed ingress、sequential MUL→RNE、physical
layout/transaction、typed handler、mapper 和 execplan transport，才能开始全新 tail
配置物化。六个 physical endpoint 字段保持 `null`，不得用 provisional 地址替代。

## 6. RULE_DELTA_PROPOSAL

提议但未修改公共规则：

1. `CDA-QPARAM-SCALAR-SHAPE-CROSSWALK-001`：ONNX scalar `[]` 与 typed transport
   `[1]` 只有在 dtype、element_count、raw-byte SHA 和 consumer scalar semantics
   全部相同时才可 crosswalk；必须把两种 shape 都写入合同。
2. `CDA-REQUANT-TYPED-QPARAM-TRANSPORT-PRECONFIG-001`：Requant 配置生成前，native
   `OperatorSpec`/handler 必须能显式运输 per-channel multiplier bit patterns、
   post-RNE zero-point 与 magic/subtract 常量；只更新 loop/stride 的 placeholder
   handler 必须 fail closed。

## 7. BLOCKER_DELTA

- `B_QUANT_TAIL_SIGNED_INT32_INGRESS`：以允许来源全新确认
  `OPEN_CONTRADICTED`，真实 W3 命中 `-1` 128 次。
- `B_QUANT_TAIL_TYPED_BINDING`：由泛化缺口加强为直接源码证据：
  `OperatorSpec` 无 qparam，handler 为 loop/stride-only placeholder。
- `B_EXECPLAN_TYPED_TRANSPORT`：确认没有 64-channel multiplier 或 zero-point transport。
- `B_LAYOUT_APPROVAL`：保持开放；不复用旧 node0004 HWC8/occurrence 资产。
- `B_QUANT_TAIL_FMA_ROUNDING_POINT` 与 `B_QUANT_TAIL_MAGIC_DOMAIN_BOUND`：保持开放，
  本轮不重做旧 node0004 数值测试。
- `B_NODE0004_C0_DEPENDENCY`：保持开放，禁止 full Conv assembly。

## 8. 资产与验证

新增资产：

- `resnet50_pipeline/node0004_exact_uint8_tail_fresh_c1.py`
- `tools/build_node0004_exact_uint8_tail_fresh_c1.py`
- `tools/validate_node0004_exact_uint8_tail_fresh_c1.py`
- `tests/test_node0004_exact_uint8_tail_fresh_c1.py`
- `contracts/operator_config/node0004_exact_uint8_tail_fresh_c1_dependency_v1.json`
- `artifacts/operator_config_validation/node0004-exact-uint8-tail-fresh-c1-dependency-v1/report.json`

验证命令：

```powershell
& '.\.venv\Scripts\python.exe' tools/build_node0004_exact_uint8_tail_fresh_c1.py
& '.\.venv\Scripts\python.exe' tools/validate_node0004_exact_uint8_tail_fresh_c1.py
& '.\.venv\Scripts\python.exe' -m unittest tests.test_node0004_exact_uint8_tail_fresh_c1
```

结果：

```text
validator = PASS_FRESH_C1_DEPENDENCY_BLOCKED_NO_EXACT_CONFIG_PATH
unittest  = 5/5 PASS
PACKAGE_RELEASE = NONE
```
