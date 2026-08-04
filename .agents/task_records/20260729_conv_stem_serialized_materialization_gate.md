# Conv stem 单乘积序列化物化前停止门

日期：2026-07-29  
owner：Conv / SA  
唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 活动收据

- `.agents/plan.md`：`ca96023deebdc274d052fb3248143a5b8a3fa3c9ba5de0bee9d793bb0fcac54d`
  （mutable provenance；派发时 `65f8b1ab...` 不作语义门）
- `.agents/rules/生成前必读索引.md`：
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- `.agents/rules/算子配置规则.md`：
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- `.agents/rules/INT8_SA点积专项规则.md`：
  `54a1e12541aaeb6f62dadb19c47a6154eb0462b758a35a9a5bc4a0043cb37dce`
- `.agents/rules/NDP硬件字段语义.md`：
  `18d71520dd4ededc5edd9bb316acd0cc0421a9a261cf14b28ea6997ddd0e844a`
- `.agents/rules/精确UINT8量化尾专项规则.md`：
  `1685bd6527111bf014a738dbef4ee85b5b8d3e54c0565cb63eda9417d5c9425e`

只读输入：

- typed lowering：`bf661e4eda2011025d9922708ab46a64f8d1b3c279527b88aa7d630bb3545432`
- remaining52 expansion：
  `31065f28bc5c9ec46d150c74a1c3370a6166a3f4bff3fa54c711f3d7b5ef7063`
- Requant 53-tail manifest：
  `0cb706c1f95de010e840b212d3fa7b22cb63e20c4939da1eec52afc56e957fee`

## RETURN_ANALYSIS

本轮没有把旧 node0004 JSON、mapping、bitstream、execplan、SCA、simulator
或测试收据当成 stem 正证据。先从 `r5:hwop-0001-00` typed geometry 与已验收
remaining52 数值域重新建立物化前方程，再审计活动 generator、layout 和 execplan
patch registry。

机器合同：

- `contracts/operator_config/conv_stem_serialized_materialization_gate_v1.json`
- SHA-256：
  `a334937bc4d93a4c539b973090d9312d8688dd98538c774a7271e3bca5ee593c`
- validation：
  `artifacts/operator_config_validation/conv_stem_serialized_materialization_gate_v1.validation.json`
- validation SHA-256：
  `31bd543ea9ce2499fdf0b8027bde4b656b45f080ccba9d43aabb6adc6e0a310b`
- 定向测试：`Ran 1 test / OK`
- `numeric_analysis_repeated=false`
- `target_and_package_absent=true`

### 已闭合的 schedule/capacity 下界

stem 几何固定为：

```text
input        [16,3,224,224] uint8
weight       [64,3,7,7] int8
output       [16,64,112,112] int32
stride       2x2
padding      3/3/3/3
logical K    147
serialized K 148
x_zp         114
```

one-product-lane 方案按每个输出元素 148 个 occurrence 物化，其中
`k=147` 是 tail 的全零 weight occurrence：

```text
typed output elements             = 16*64*112*112 = 12,845,056
normal dot4 occurrence             = 475,267,072
serialized padded occurrence      = 12,845,056*148 = 1,901,068,288
occurrence ratio                  = 4.0x
effective lane utilization        = 147/(148*4) = 24.831%
```

沿用 28/28/8 slice 的三 wave sample 所有权，得到 64 个
`(sample, output-channel-step)` region。每区建议尺寸：

```text
A serialized weight =     9,472 B  = 148*16*4
B im2col replay      = 7,426,048 B  = 112*112*148*4
C correction        =        64 B  = 16*4
D int32             =   802,816 B  = 112*112*16*4
total               = 8,238,400 B
one-slice capacity  = 25,165,824 B
```

因此容量不是首 blocker。proposal-only base offset 为：

```text
A=0
B=9,472
C=7,435,520
D=7,435,584
```

proposal-only loop/stride：

```text
LC1/LC11/LC14.end = 112
LC2/LC12/LC15.end = 14
LC4/LC6.end       = 37
LC5/LC7.end       = 4
B.dim_stride      = [32,4736,66304]
D.dim_stride      = [32,64,7168]
```

D 的符号 byte 方程：

```text
offset = row*7168 + (wblock*8+q)*64 + half*32 + byte
row=0..111, wblock=0..13, q=0..7, half=0..1, byte=0..31
```

机器枚举恰好覆盖 `[0,802815]` 的 802,816 个连续 byte。该结论只关闭
symbolic schedule 和 slice-capacity lower bound；未提升为 final JSON 的物理
request/address/terminal/lifetime 证据。

DataC 的建议初值保持精确 QLinearConv accumulate 公式：

```text
C[oc] = bias[oc] - 114 * sum(weight[oc,0:147])  (mod 2^32)
psum[k+1] = psum[k] + s8(weight[k])*u8(activation[k]) (mod 2^32)
```

没有 host 预计算 partial sum 或 final accumulator。

## FIRST_BLOCKER

状态：`BLOCKED_BEFORE_TARGET_JSON`  
blocker：`B_CONV_STEM_TYPED_MATERIALIZER_AND_HANDLER`  
分类：`SOURCE_TOOLCHAIN_SEMANTIC_OWNER_MISSING`

首个不可伪造的断点不是 SA 容量或 7x7 卷积本身，而是当前活动本地正式工具链
没有一个可绑定 `r5:hwop-0001-00` 的 stem 专用语义入口：

1. `tools/generate_conv_instance.py:318` 明确拒绝除已 review 的
   `1x1/pad0`、`3x3/pad1` 之外的 typed Conv；所以它不能给 7x7/stride2/pad3
   签发正式 JSON。
2. `resnet50_pipeline/conv28_layout.py:428` 的 signed-A local ABI 明确只支持
   `1x1/stride1/pad0`；所以它不能给 stem 签发最终 weight/im2col physical
   packing。
3. `resnet50_pipeline/ndp_patch_toolchain.py:303` 的 serialized handler
   名称和身份固定为 node0004；同文件 `:311`、`:312`、`:323` 又把
   A/B/D 固定为 `4096/802816/50176` 元素 ABI。stem 实际要求
   `9472/7426048/200704`。
4. `resnet50_pipeline/ndp_patch_toolchain.py:454` 的 fail-closed registry
   没有 stem patchset ID。现有 mapping/execplan evidence 工具会调用该 registry
   验证并安装 patchset；在不修改共享 registry 的本族唯一前缀写入边界下，
   无法合法注册 fresh stem operator type。

审计过“新建本族独立 handler”的可能性：mapping/execplan evidence 的
patchset current-match 和安装路径仍直接绑定共享 `_patched_files_for()`，
仅新建旁路模块不能得到同一条正式 patchset/mapper/execplan 证据链。使用未知
operator type 会绕过 ABI handler；借用 node0004 type 则会伪造身份且被固定
shape 拒绝。二者都不能计正式 local E2。

需要主线明确扩展授权：允许增加 stem 专用 typed generator、signed serialized
im2col packer，以及共享 ndp patch registry 中的 stem handler/patchset identity。
在该授权前，手写半链 target 会把 proposal-only 地址当成物理真值，因此本轮
fail closed。

## Requant 只读绑定裁决

已接受的 `r5:hwop-0001-01` 记录只读显示：

```text
classification = FULL_LOCAL_E2_MATERIALIZED_EXACT_NODE0001
profile_id      = TAIL_N16_C64_H112_W112_HWC8
```

本轮没有重跑其 W3 数值分类或复制 multiplier。绑定状态为
`BLOCKED_ON_ACCUMULATE_PHYSICAL_IDENTITY`：accumulate 的 final D layout、
base/address、terminal 和 lifetime 尚未产生，因而不能证明它与既有 Requant
输入 identity/address/lifetime 兼容。首断点在 accumulate 侧，不在 Requant
算术侧。

## BLOCKER_DELTA

关闭：

- `B_CONV_STEM_SYMBOLIC_SCHEDULE`
- `B_CONV_STEM_SLICE_CAPACITY_LOWER_BOUND`

新增：

- `B_CONV_STEM_TYPED_MATERIALIZER_AND_HANDLER`

保持：

- `B_CONV_STEM_PHYSICAL_COVERAGE`
- `B_CONV_STEM_CONFIG_BOUND_W3`
- `B_CONV_STEM_REQUANT_BINDING`
- `B_NODE0004_DYNAMIC_RESULT_PENDING`

## RULE_DELTA_PROPOSAL

不建议新增公共规则文本。请求主线作一次窄授权裁决：是否允许 Conv/SA owner
为 stem 增加 shared ndp patch registry 的新 patchset/handler identity。若授权，
后续仍应使用本族唯一 `conv_stem_*` generator/packer/validator，并禁止复用
node0004 operator identity 或常量。

## PACKAGE_RELEASE

```text
PACKAGE_RELEASE=NONE
```

本轮没有生成 stem target JSON、mapping、bitstream、execplan、SCA 或服务器包；
没有检查服务器、上传、运行或取得 lease；没有修改 plan、公共 rules 或 RTL。

