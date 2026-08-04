# Conv/SA 其余 52 个实例 schedule/packing 扩展清单

日期：2026-07-29  
owner：Conv / SA  
唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 活动收据

- plan（mutable provenance）：
  `0d78a70b4e2a984b4f34b0d3be1d790bbdf4c4c8c04d0b0dac8e3a799a5a4299`；
- 生成前索引：
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`；
- 公共算子规则：
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`；
- INT8 SA 专项规则：
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`；
- 服务器包规则：
  `153b0f03210f8e4f98b6b39a7ca7a40b11c788085ba3775826e42beb171167a2`；
- Requant 只读依赖：
  `contracts/operator_config/requant_conv53_tail_signature_binding_v1.json`
  SHA-256=`0cb706c1f95de010e840b212d3fa7b22cb63e20c4939da1eec52afc56e957fee`。

## RETURN_ANALYSIS

生成的机器合同：

- `contracts/operator_config/conv_sa_remaining52_expansion_v1.json`；
- SHA-256：
  `31065f28bc5c9ec46d150c74a1c3370a6166a3f4bff3fa54c711f3d7b5ef7063`；
- validator：
  `artifacts/operator_config_validation/conv_sa_remaining52_expansion_v1.validation.json`；
- validator SHA-256：
  `b07d8072bcc91a007219f4a07c4c5ae620b044a9b10c980059a8307d3c9105bd`；
- 52/52 records，validator `valid=true`、error=0、小域独立 oracle PASS。

本轮明确排除冻结 anchor `hwop-0004-00`，没有重复 node0004 数值分析。对其余 52
个 Conv 执行了新的完整 W3 枚举；总计：

```text
actual final-packed dot4 occurrence = 15,375,532,032
exact schedule signature            = 22
normal four-lane domain compatible  = 51
one-product-lane fallback required  = 1
```

枚举消费的是最终 packer 对应的真实 operand：

```text
DataA = s8 weight
DataB = u8 activation
reduction order = OIHW flatten: input_channel -> kernel_h -> kernel_w
```

空间 padding 使用 typed `x_zero_point`，K-tail 的 weight lane 使用 `w_zp=0`，因此
tail 乘积为零。没有用软件 `(x-x_zp)` 中间张量冒充最终硬件 lane，也没有用理论
min/max envelope 替代实际 occurrence。

Requant 依赖只读消费既有 53-stage 分类。没有重跑 Requant W3 分类；每条记录只绑定
其 profile、rounding class、唯一 multiplier bits hash，并保持：

- fresh multiplier binding required；
- fresh address/lifetime binding required；
- node0004 constant reuse forbidden。

## 唯一 signed17/cout 命中实例

`hwop-0001-00` / ResNet50 stem 7x7 Conv：

```text
input       = [16,3,224,224]
weight      = [64,3,7,7]
output      = [16,64,112,112]
stride/pad  = [2,2] / [3,3,3,3]
K           = 147
dot4 groups = 37
K-tail      = 3 logical lanes + 1 zero-product lane
x_zp        = 114
```

完整 475,267,072 个实际 dot4 的范围为：

```text
[-101231, 95485]
```

其中 2,499,984 个 occurrence 超出 signed17 `[-65536,65535]`。首个反例：

```text
output_flat_nhw_index = 599
output_channel        = 10
k_group               = 36
activation u8 lanes   = [188,217,198,114]
weight s8 lanes       = [-116,-127,-123,0]
lane products         = [-21808,-27559,-24354,0]
dot4                  = -73721
```

该值仍在 signed18 合法域内，但根据当前 plan 的 signed17/cout 命中门，在最终
Trassic2.0_RTL commit 未绑定、node0004 动态结果仍无效时，stem 被分类为
`ONE_PRODUCT_LANE_DATAC_FALLBACK_REQUIRED`，不能与其余 51 项一起直接复用普通
four-lane 路线。

stem 的配置绕行资源下界：

```text
normal dot4 occurrences       =   475,267,072
serialized padded occurrences = 1,901,068,288
occurrence ratio              = 4.0x
effective lane utilization    = 24.831%
```

其余 51 项实际范围均未超 signed17；除 stem 外，最宽负侧实例为 `hwop-0018-00`
的 `[-47035,36864]`。

## schedule 和资源边界

每条记录均绑定：

- kernel、stride、padding、dilation、group；
- input/weight/output NCHW/OIHW；
- K、dot4 group、K-tail；
- sample-wave forecast、bias presence、input zero-point；
- Requant rounding profile 与 9 类 tail physical schedule profile；
- activation/weight/bias/INT32 output bytes；
- normal/fallback occurrence 与 lane utilization；
- typed request、W3 activation、ONNX weight/w_zp/bias、Requant signature ownership。

22 个 signature 是按 schedule + input zero-point + output requant class 分类所得；
53 个 exact multiplier payload 仍保持逐实例唯一，不纳入可复制常量。

所有 physical address、slice mask、bank、terminal、lifetime 仍标为
`LIST_ONLY_DYNAMIC_GATE_PENDING`。本清单不计其他 52 项 E2，不计 E4/E5。

## BLOCKER_DELTA

新增：

- `B_CONV_STEM_SIGNED17_DOMAIN_HIT`：stem 2,499,984 个实际 dot4 命中旧
  signed17/cout 反例域，按当前门必须独立 one-product-lane 路线或等待绑定 signed18
  修复身份后单独动态裁决；
- `B_CONV_REMAINING52_PHYSICAL_BINDING`：52/52 的 multiplier、address、slice mask、
  bank、terminal、lifetime 仍需 fresh materialization；
- `B_CONV_REMAINING52_DYNAMIC_GATE`：node0004 有效 compile/sim/readback 尚未取得，
  禁止批量封包。

关闭：

- `B_CONV_REMAINING52_TYPED_CENSUS`：52/52 typed/source ownership 完整；
- `B_CONV_REMAINING52_FINAL_PACKING_DOMAIN_UNKNOWN`：15,375,532,032 occurrence
  已完整枚举；
- `B_CONV_REMAINING52_SIGNATURE_GROUPING_UNKNOWN`：机器分类为 22 个 exact schedule
  signature。

保持：

- node0004 v2 必须等待服务器先解决 RTL merge conflict 后重新运行；
- 最终 Trassic2.0_RTL commit identity 未绑定；
- 其他 52 项 E2/E4/E5 均未声明。

## RULE_DELTA_PROPOSAL

无新的公共规则文本提案。建议主线把 stem 的实际反例与 4x/24.831% 成本作为
当前 `signed17/cout` 分支门的实例绑定写入 plan/task record，而不是扩写公共公式。

## PACKAGE_RELEASE

```text
PACKAGE_RELEASE=NONE_FOR_REMAINING52
```

没有为其余 52 个 Conv 生成 target JSON、mapping、bitstream、execplan/SCA 或服务器
包；没有检查服务器、上传、运行或取得 lease。

## 数值与复用声明

- `numeric_analysis_repeated_for_node0004=false`；
- `new_numeric_analysis_performed_for_remaining52=true`，只执行一次；
- `validator_numeric_analysis_repeated=false`；
- `requant_w3_classification_repeated=false`；
- `reuse_assets_consumed=true`：只读消费 typed lowering、正式 ONNX/W3 与 Requant
  signature manifest；
- 没有消费旧 node0004 动态结果，也没有复测已接受的非 Conv 算子。
