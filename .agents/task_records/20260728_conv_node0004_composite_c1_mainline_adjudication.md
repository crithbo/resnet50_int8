# Conv node0004 fresh composite C1 主线裁决

日期：2026-07-28  
主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 裁决

```text
C1_COMPOSITE_PREDESIGN = PASS_PROPOSAL_ONLY
C1_TARGET_MATERIALIZATION = BLOCKED_BEFORE_JSON
CONFIG_ONLY_CORRECTNESS_BASELINE = false
FIRST_COMPLETE_CONV_PASS = false
PACKAGE_RELEASE = NONE
```

用户要求的“详细 RTL/入口审计后尝试配置绕行”已执行。C0 确认 stock INT8 SA 与
SA 内 serialized-psum 均不正确后，主线授权 fresh：

```text
SA single product (DataC=0)
→ INT32 product scratch
→ GA int32_mac tree
→ bias/xzp correction
→ exact UINT8 tail
```

本轮在完整 target JSON 之前遇到两个独立硬门，故不得生成明知不完整的测试包。

## 已验收的 accumulate predesign

- 记录：
  `.agents/task_records/20260728_conv_node0004_composite_c1_predesign.md`
- SHA256：
  `01daa8e008174cba909bc50e1d0fe4962a6868a7678d7b279fe813eed4515422`
- 机器合同：
  `contracts/operator_config/conv_node0004_composite_c1_predesign_v1.json`
- SHA256：
  `7b6526eb55f877b7449ad2e08677ed0ba7eb22e342ab2ef6ba1e3a6e477f96c8`

fresh typed/model/W3 计算：

```text
INT32 outputs = 3,211,264
W3 mismatch = 0
scalar products = 205,520,896
full product scratch = 822,083,584 bytes
28-slice aggregate capacity = 704,643,072 bytes
```

整层不能同时常驻，但 `(n,oc_group8)` 形成 128 tile：

```text
outputs/tile = 25,088
bytes/tile = 13,046,304
slice capacity = 25,165,824
waves = [28,28,28,28,16]
```

所以总容量不是硬阻塞。六级
`64→32→16→8→4→2→1` GA opcode14 tree、bias correction、逻辑 affine address、
tile residency 与 3,686,535,168-byte accumulate traffic lower bound 已闭合。

首个 accumulate 物理 blocker：

```text
B_CONV_C1_SA_SCALAR_PRODUCT_MATERIALIZER_AND_TERMINAL
```

当前没有获批 typed/manual materializer 将 205,520,896 个单产品 occurrence 绑定到最终
LC/MSE/Buffer bank/column、SA lane、last/last_index、direct INT32 scratch write、
drain visibility 和 occurrence inverse。逻辑地址/容量正确不得冒充 final physical
coverage。

## 已验收的 exact-tail 绕行审计

- 记录：
  `.agents/task_records/20260728_node0004_exact_uint8_tail_max0_config_audit.md`
- SHA256：
  `8679bcfb130cf2ca34a9146d557be26179cf3aecb115e4ecb0e537877632f5fe`
- 机器合同：
  `contracts/operator_config/node0004_exact_uint8_tail_max0_audit_v1.json`
- SHA256：
  `1d8bdaf99a4b6555b7db9462511af0039947ff8dfbd069770d02057e75395564`

在 64 个 multiplier 均为有限正数、`y_zp=0` 时：

```text
UINT8(acc) = UINT8(max(acc,0))
```

对全 signed INT32 域数学成立；正式 W3 的 3,211,264 元素、1,262,480 个负累加值，
原公式↔max0↔golden 均 0 mismatch。但活动硬件没有 raw signed word max：

- FP32 `max=3` 必须先转换；
- `int8_max=11` 只比较四个 byte lane；
- INT32 只有 sum/sub/mac 12/13/14；
- INT32 class 与 max decode 在 bit2 上矛盾，0..31 编码交集为空。

因此首个完整节点硬 blocker 为：

```text
B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE = OPEN_CONTRADICTED
```

最终 UINT8 saturation 恰好遮蔽负值不能替代 raw signed guard 的中间硬件证据。

## 主线规则裁决

已接受并写入公共专项规则：

- `CDA-COMPOSITE-SCRATCH-GLOBAL-VS-TILED-CAPACITY-001`
- `CDA-PREDESIGN-SYMBOLIC-ADDRESS-NOT-PHYSICAL-COVERAGE-001`
- `CDA-QUANT-TAIL-RAW-SIGNED-GUARD-001`

它们没有降低任何生成门：proposal-only logical schedule 不能生成 target；不存在 raw
signed guard 时 exact tail 必须 fail-closed。

## 当前不可同时满足的约束

用户当前要求：

1. 不修改功能 RTL；
2. 不用 host 预计算内部 product/partial/accumulate/max0/scaled/rounded/final tensor；
3. 首个 Conv 测试必须覆盖完整 node0004 accumulate+requant；
4. local E2 通过后才生成测试包。

在这些约束下，现有活动 opcode/RTL 无法物化完整 node0004，因此：

```text
target JSON = NOT_GENERATED
mapping/bitstream/execplan/SCA = NOT_GENERATED
config-bound complete-node simulator = NOT_RUN
server package = NOT_GENERATED
server inspection/upload/run/lease = NONE
```

这不是包构建失败，也不是服务器失败；停止发生在生成前硬件能力门。

## BLOCKER_DELTA

```text
ADD  B_CONV_C1_SA_SCALAR_PRODUCT_MATERIALIZER_AND_TERMINAL
REFINE B_CONV_SA_PRODUCT_SCRATCH_SCHEDULE_AND_OWNERSHIP:
       logical schedule/capacity = CLOSED
       physical materializer/terminal/coverage = OPEN
ADD  B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE = OPEN_CONTRADICTED
KEEP B_CONV_GA_EXACT_ALTERNATIVE_TYPED_TOPOLOGY
KEEP B_QUANT_TAIL_FMA_ROUNDING_POINT
KEEP B_QUANT_TAIL_MAGIC_DOMAIN_BOUND
KEEP B_QUANT_TAIL_TYPED_BINDING
KEEP B_QUANT_TAIL_MAPPER_REGISTRATION
KEEP B_EXECPLAN_TYPED_TRANSPORT
```

## 下一决策边界

若继续坚持纯配置与完整节点口径，Conv 必须等待一个新的、可证明的 raw signed INT32
compare/select 或其他精确 signed ingress/rounding 配置入口；重复生成 scalar-product
JSON 或服务器包不能越过 tail 硬门。

若未来用户改变授权，可能的独立路线是兼容 RTL、外部提供的新硬件 primitive/identity，
或明确授权的计算分区；本记录不授权其中任何一项。
