# Requant Conv53 tail signature binding

日期：2026-07-29  
唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## RETURN_ANALYSIS

状态：
`LOCAL_CONTRACT_ONLY_SIGNATURE_BINDING_READY`

本轮没有重复任何数值分析或 W3 分类，没有重新生成、修改或封装 node0004，也没有生成
任何新的 operator target JSON、mapping、bitstream、execplan/SCA 或服务器包。

本轮明确消费以下复用资产：

1. 既有 Conv53 binding 中除 node0004 外的 52 项已验收 W3 分类；
2. node0004 fresh `tail_graph.json`、本地 config-bound numeric report、主线 task
   record 和冻结 package identity；
3. typed lowering/request 中 53 个 Conv tail 的 shape、qparam 与 multiplier bit-payload
   SHA。

node0004 ZIP 保持不可变：

```text
artifacts/operator_config_validation/r5-server-test-packages/r5_node0004_hw_v1.zip
SHA256=335a174251c2d0070a29f204f5ad0c5b2ae5e471350f7bbcc8875b3b06bed989
status=PACKAGE_READY_NOT_RUN
```

未检查服务器文件/名称/RTL identity，未上传、未运行、未取得 lease。

## 活动读取收据

| 文件 | SHA256 | 用途 |
|---|---|---|
| `.agents/plan.md` | dispatch=`f9a3ce73baa73346c144f14bf005262f0b0caaf66d981da157a5a11c0a703183`; generation=`e4402432aee1ab91db3a4d545471e409eace2a0d79880f0932a31abfb8c6ceda` | 第 0、0.1 节活动执行覆盖；两次复读语义不变，plan 仅 mutable provenance |
| `.agents/rules/生成前必读索引.md` | `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f` | 路由与停止门 |
| `.agents/rules/算子配置规则.md` | `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171` | reuse-first binding |
| `.agents/rules/精确UINT8量化尾专项规则.md` | `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e` | direct signed 两阶段与 exact-tail 门 |
| `.agents/rules/RequantizeUint8算子配置规则.md` | `5fcd1c9d2f6fa6dd193e369412c46c16b7bd087b570cc607aa0d0f06ba4c7555` | node0004 覆盖与 Requant 增量 |

## 签名定义

每个 Conv tail 使用以下五维 canonical JSON 计算 SHA256：

```text
logical_shape_nchw
y_zero_point_uint8
multiplier_fp32_bits_sha256
rounding_saturation_profile_id
physical_schedule_profile_id
```

53 个 stage 的 per-channel multiplier bit-payload SHA 全部唯一，因此：

- exact signature 数：53；
- unique multiplier payload 数：53；
- 不存在把 node0004 的 64-channel multiplier 常量直接复用于其他 stage 的情况。

`value_sha256` 是精确 FP32 bit payload 身份；十进制 min/max 不替代该身份。

## node0004 两阶段锚点

fresh node0004 锚点固定为：

```text
shape=[16,64,56,56]
y_zero_point=0
multiplier_bits_sha256=e83328d8589db8cfc2c5a1ff033d3c0e08d9bd87d8d8fcf52b8cb22189956bb2
physical_layout=HWC8
occurrence_shape=[1,3136,8]
sample_waves=3
samples_per_wave=[7,7,2]
channel_shards=8
two_stage_pairs=24
stage_count=48
```

每 occurrence：

- INT32 stage0 input：100,352 bytes；
- FP32 scratch：100,352 bytes；
- UINT8 stage1 output：25,088 bytes。

顺序固定为：

```text
signed INT32 -> FP32
-> explicit FP32 multiply
-> FP32 scratch + completion barrier
-> raw FP32 fixed-magic RNE
-> INT32 subtract
-> UINT8 saturation
```

该锚点本地 tail mismatch=0、magic domain finite，但包未运行，所以不计 E4/E5。

## 复用与独立物化分类

| 类别 | 数量 | 裁决 |
|---|---:|---|
| frozen node0004 anchor | 1 | 不重建、不重封装 |
| zp0 且 shape 与 node0004 相同 | 5 | 可复用精确两阶段配方和 schedule 形状模板；必须 fresh multiplier/address/lifetime 物化 |
| zp0、其他 shape | 27 | 可复用精确两阶段算术顺序；必须独立物化物理 schedule |
| even nonzero-zp | 15 | 只复用 direct-signed stage0、scratch/barrier、RNE 与 saturation 原语；post-RNE zp 和物理 schedule 独立物化 |
| odd nonzero-zp | 5 | 同上，并保留 tie-parity 独立验证 |

因此：

- node0004 exact two-stage recipe 可供另外 32 个 zp0 Conv 作为算术配方复用；
- 其中仅 5 个与 node0004 同 shape，可再复用 schedule 形状模板；
- 其余 52 个 Conv 全部仍需逐实例 fresh materialization；
- 20 个 nonzero-zp Conv 不得称为复用 node0004 的完整配方。

## 既有 W3 分类保持

其他 52 项直接引用原分类，未重新运行：

| 既有分类 | 数量 |
|---|---:|
| `FULL_LOCAL_E2_MATERIALIZED_EXACT_NODE0001` | 1 |
| `NUMERIC_RECIPE_COMPATIBLE_PHYSICAL_E2_PENDING` | 31 |
| `CURRENT_GUARD_RECIPE_CONTRADICTED_NONZERO_EVEN_ZP` | 15 |
| `CURRENT_GUARD_RECIPE_CONTRADICTED_NONZERO_ODD_ZP` | 5 |

旧 guard 分类只记录历史 recipe 边界；2026-07-29 的 direct-signed 硬件可用假设允许
继续做本地 binding/materialization 规划，但不会把其他实例自动升级为 E2/E4/E5。

## 物理 schedule profile

所有 profile 均为 HWC8、lane=8、batch=16；除 node0004 锚点外，三 wave 与
pair/stage 数只作 dependency forecast，不是 emission authority。

| logical shape | stage 数 | channel shards | two-stage pairs | stage count |
|---|---:|---:|---:|---:|
| `[16,64,112,112]` | 1 | 8 | 24 | 48 |
| `[16,64,56,56]` | 6 | 8 | 24 | 48 |
| `[16,128,28,28]` | 8 | 16 | 48 | 96 |
| `[16,256,56,56]` | 4 | 32 | 96 | 192 |
| `[16,256,14,14]` | 12 | 32 | 96 | 192 |
| `[16,512,28,28]` | 5 | 64 | 192 | 384 |
| `[16,512,7,7]` | 6 | 64 | 192 | 384 |
| `[16,1024,14,14]` | 7 | 128 | 384 | 768 |
| `[16,2048,7,7]` | 4 | 256 | 768 | 1536 |

每个非 node0004 stage 都必须 fresh 绑定 multiplier bits、slice mask、base/address、
scratch alias、barrier、lifetime、terminal 和最终 materialized JSON。

## 机器产物

| 产物 | SHA256 |
|---|---|
| `resnet50_pipeline/requant_conv_tail_signature_binding_v1.py` | `edff8477828fd608ab50c4a62fb6b335b70e31419c705d59c4971a1225418b63` |
| `tools/build_requant_conv_tail_signature_binding_v1.py` | `cf7e84dc45be1ef3ea68b39f76d24ade026874c5109aea75ccca141f7fdc9f9f` |
| `tools/validate_requant_conv_tail_signature_binding_v1.py` | `ffe45e851be5eea44013d953928a9f7bbcb1b3f97c449e0edf3385ad4fb9617e` |
| `contracts/operator_config/requant_conv53_tail_signature_binding_v1.json` | `0cb706c1f95de010e840b212d3fa7b22cb63e20c4939da1eec52afc56e957fee` |
| `artifacts/operator_config_validation/r5-requant-conv53-tail-signature-binding-v1/validation_report.json` | `116a252453959bcc86970c57ad331649fed569f17f8f247ccc3a9a6d3155881f` |
| `artifacts/operator_config_validation/r5-requant-conv53-tail-signature-binding-v1/generation_receipt.json` | `3e5808c339cb10fa49386bde5b351919f4ccc4fd63e2239961e41892e1b6f135` |

manifest semantic SHA256：
`8f59ba4c76f2321fc280807d2db4d4dafd9082529cc79f3d9d0542e61a4a5969`。

validator 24/24 checks 通过，覆盖 53 unique request/signature/multiplier payload、
9 个 schedule profile、24 个 shape+zp group、1/5/27/15/5 reuse 分类、
33/15/5 rounding 分类、冻结 ZIP 身份和禁止产物边界。

## BLOCKER_DELTA

```text
add=[]
close=[]
carry_forward=[
  remaining 52 Conv tails require fresh instance materialization,
  each non-node0004 multiplier payload requires fresh exact-bit binding,
  each non-node0004 address/lifetime/slice-mask schedule remains unmaterialized,
  20 nonzero-zp tails require independent post-RNE zp materialization,
  5 odd nonzero-zp tails retain tie-parity validation,
  final Trassic2.0_RTL commit identity remains unbound,
  real server compile/run/readback and E4/E5 remain open
]
```

本轮没有因分类或免复测关闭任何 blocker。

## RULE_DELTA_PROPOSAL

`[]`

## PACKAGE_RELEASE

```text
new_package=NONE
frozen_node0004_package_consumed_as_read_only_anchor=true
frozen_zip_sha256=335a174251c2d0070a29f204f5ad0c5b2ae5e471350f7bbcc8875b3b06bed989
```

该结果只是一份本地机器 binding 合同，不构成其他 52 项 E2，也不构成任何 E4/E5 或
candidate release。
