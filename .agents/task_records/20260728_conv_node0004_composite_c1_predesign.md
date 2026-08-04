# node0004 fresh composite C1 proposal-only predesign

日期：2026-07-28  
唯一主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`  
test_id：`r5_conv_node0004_composite_c1_predesign_v1`

## 边界

本轮按 C0 主线裁决只设计：

```text
SA single-product(DataC=0)
→ INT32 product scratch
→ GA opcode14 int32_mac(A,1,C) 64-term pairwise tree
→ bias/-x_zp*sum(w) correction leaf
```

shared exact UINT8 tail 当前仍 fail-closed。主线明确要求此时继续完成不产生 target 的
composite predesign/feasibility 合同，因此本轮没有生成 node0004 target JSON、mapping、
bitstream、execplan/SCA、config-bound target simulator 或服务器包。全部旧 node0004
物理资产、测试与回执均未作为输入。

## 活动收据

plan 仅作 mutable provenance：

- `.agents/plan.md`
  `971f3c7d479e6ad80cf39450d0f56bc3bad5a898daca152f2c859593cf27b017`

current-match fail-closed：

- 生成前索引：
  `12583308ec9a16dbb8ea15571a5280291fed7e152167d2e4e8e00509a9a6370f`
- 公共算子规则：
  `cbaffcc5fb3bea7da9f0c199bb2e7f06445a676ab456bdfd505b90dd89825171`
- NDP 字段语义：
  `a955834fc059f08bada8131adc94db5c05112eb1e6acc0a0976eee7e6ae17c59`
- INT8 SA 专项规则：
  `af4eb4c3795c8a8dfaba7dca47839906eb02dbb46bb17ec040f893638005502b`
- GAP int32_mac 规则：
  `b194d525fb7c1647b3fdaabd51d88dc4bc9b874ce7a910d4fdd1ca125b56fd96`
- 精确 UINT8 tail 规则：
  `32c47b83e98d9dd9cbf1f8be7f25dd99d86ddecb583d5972b61b1e72d3b931be`
- Requant 规则：
  `d9ec14cc6975e9596f3fe56e762cd4797c8ba6c70fa235503f5954e97c6f863f`
- C1 授权：
  `6415f8adfdd163a6c360a46e9392371c386b900b85722b9eee8a8d3760a89e2a`
- C1 主线裁决：
  `1f343efe8383b65ffb836427ba4994dcd78f7e0869b98882a831920ff34e9760`

### Receipt-only integration refresh

主线发布两条 predesign 规则并完成 C1 裁决后，只刷新上述活动身份。主线裁决绑定的本
记录 pre-refresh SHA 为
`01daa8e008174cba909bc50e1d0fe4962a6868a7678d7b279fe813eed4515422`。

本次 refresh 固定：

```text
classification = ACTIVE_RULE_RECEIPT_ONLY
numeric_analysis_repeated = false
frozen_numeric_oracle_sha256 =
  a2ba3cafbbac11e1ebd537bb91d7d88fe9770c61e202b78801ba042268ef6a41
conclusion_changed = false
target_or_package_generated = false
```

validator 不再调用 `_numeric_oracle`，不加载正式 W3 输入/accumulator；它只验证冻结
numeric-oracle 的 canonical SHA、旧 `mismatch=0` 摘要、活动规则收据、静态 schedule
守恒和全部 emission=false。单测用 mock 将 `_numeric_oracle` 设为一旦调用即抛错，
验证仍通过。

新规则 binding：

- `CDA-COMPOSITE-SCRATCH-GLOBAL-VS-TILED-CAPACITY-001`
- `CDA-PREDESIGN-SYMBOLIC-ADDRESS-NOT-PHYSICAL-COVERAGE-001`

tail 主线裁决新增：

```text
B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE = OPEN_CONTRADICTED
```

这不改变 accumulate predesign、数值摘要或首个 accumulate 物理 blocker。

## RETURN_ANALYSIS

### Fresh typed/numeric identity

唯一 typed request 是 `r5:hwop-0004-00`：

```text
X      UINT8 [16,64,56,56]
W      INT8  [64,64,1,1]
bias   INT32 [64]
output INT32 [16,64,56,56]
kernel 1x1, stride1, pad0, group1
x_zp=0
w_zp[0:64]=0
```

从正式 ONNX initializer 重新取得 W/bias/x_zp/w_zp，直接读取正式 producer output X，
独立执行完整 1x1 INT32 golden，并与正式 W3 accumulator 比较：

```text
elements = 3,211,264
mismatch = 0
computed/formal payload SHA256 =
  1ec864892d82279beff561927500f55ebec636daf2fb7c624a1e153dd5e17532
correction = bias - x_zp*sum(w) = bias
correction SHA256 =
  40bc2a3acbd553ffc067ea1c7b1c31cb59f18fca30451f55809ff76d2594bc0b
```

validator 不保存 product、partial sum、accumulator 或 final tensor；这只是独立 golden，
不是 host-precomputed operator replay。

### Symbolic address and coverage

全局 logical product 数：

```text
E = 16*64*56*56 = 3,211,264
P = E*64 = 205,520,896
```

全局 product scratch 若整层同时驻留：

```text
P*4 = 822,083,584 bytes
28-slice aggregate capacity =
  28*4*6144*64*16 = 704,643,072 bytes
excess = 117,440,512 bytes
```

因此整层 residency 不可行。可行的 proposal-only tile 为
`(n, oc_group8)`，共 `16*8=128` tile：

```text
tile_id = n*8 + oc_group8
q = ((oh*56+ow)*8+lane)
oc = 8*(tile_id%8) + q%8
n  = tile_id//8
oh = (q//8)//56
ow = (q//8)%56

X byte = (((n*64+k)*56+oh)*56+ow)
W byte = oc*64+k
product byte = P_base + 4*(q*64+k)
formal accumulator byte = 4*(((n*64+oc)*56+oh)*56+ow)
```

`(q,k)→q*64+k` 对
`q∈[0,25088), k∈[0,64)` 为 affine bijection。每 tile：

```text
output elements = 25,088
products        = 1,605,632
product bytes   = 6,422,528
```

128 tile 在 28 slice 上分 5 waves：
`[28,28,28,28,16]`。

### SA product

每个 logical scalar-product occurrence：

```text
D = i32(s8(W))*i32(u8(X))
DataC = 0
one nonzero dot4 lane + three explicit zero lanes
dot4 lane utilization = 25%
logical occurrences = 205,520,896
```

这是活动 RTL/source 与 C0 component TB 已证明的 primitive。物理 parallel grouping、
LC/MSE、Buffer bank/column、SA transout、last/last_index 仍为 null，不能由逻辑公式
代替。

### GA 64-term tree and correction leaf

六级：

```text
64 → 32 → 16 → 8 → 4 → 2 → 1
```

每级固定：

```text
opcode = int32_mac = 14
D = low32(A*1+C)
A address = prev_base + 4*(q*input_width + 2*j)
C address = prev_base + 4*(q*input_width + 2*j + 1)
D address = next_base + 4*(q*output_width + j)
```

K=64，全部层均为偶数，`odd_tail_count=0`。A 为 terminal carrier，C 必须逐 occurrence
tag match；B 为 constant 1；走 normal FIFO，禁止 transout；每级 D complete write
drain 后才允许下一层 reconfigure/reload。

correction 级：

```text
D = low32(root*1 + correction[oc])
correction[oc] = bias[oc] - x_zp*sum_k(w[oc,k])
node0004 correction[oc] = bias[oc]
```

每 tile 8 个 correction INT32 只占 32 bytes，proposal 使用 buffer4 keep replay；
root A 提供 terminal。GA INT32 word 的 buffer columns 使用活动 GAP 规则已批准的
`[0,4,8,12,16,20,24,28]`，对应 buffer bank `[0..7]`。这些是 source-expressible
predesign，尚不是最终 JSON/bitstream 物化证据。

### Residency and traffic lower bound

每 tile 使用互不重叠的 16-byte aligned regions：

```text
input        200,704 B
weight           512 B
correction        32 B
products   6,422,528 B
tree all   6,322,176 B
corrected    100,352 B
total      13,046,304 B
```

单 slice capacity 为 `25,165,824 B`，headroom 为 `12,119,520 B`。因此 proposal
tiling 在容量上可完成；容量不是首个物理 blocker。

全层 accumulate traffic lower bound：

```text
SA operands read                411,041,792 B
product write                   822,083,584 B
GA tree read                  1,618,477,056 B
GA tree write                   809,238,528 B
root + correction keep seed read 12,849,152 B
corrected write                  12,845,056 B
total                          3,686,535,168 B
```

该 lower bound 不含 config、RMW、line padding 与 tail traffic。

### FIRST_PHYSICAL_BLOCKER

```text
B_CONV_C1_SA_SCALAR_PRODUCT_MATERIALIZER_AND_TERMINAL
```

活动 native registry/handler/mapper 中没有一个已授权入口，能够把“一条非零 dot4 lane”
的 scalar product 编成最终 LC/MSE/Buffer/SA occurrence，并同时证明：

- product scratch 的 205,520,896 occurrence 全覆盖；
- SA input/weight lane packing；
- Buffer bank/column 与 supply-demand；
- tag/last/last_index terminal；
- direct INT32 scratch write 与 drain visibility；
- final JSON→mapping→bitstream occurrence inverse。

因此 `B_CONV_SA_PRODUCT_SCRATCH_SCHEDULE_AND_OWNERSHIP` 被细分为：

- logical byte schedule/capacity：本轮闭合；
- physical materializer/terminal/coverage：继续开放，且为首 blocker。

GA tree 仍是 `SOURCE_EXPRESSIBLE_PROPOSAL_ONLY`，保留
`B_CONV_GA_EXACT_ALTERNATIVE_TYPED_TOPOLOGY`。shared exact tail 仍保留 signed ingress、
FMA rounding、typed binding、mapper 与 execplan transport blocker。

## BYPASS_ANNOTATION

```text
bypass_reason:
  stock four-lane INT8 SA has duplicate carry shift, signed17 reduction
  range loss, and INT8 DataC/psum gating
contradicted_or_missing_native_path:
  normal four-lane dot, SA internal psum, registered composite Conv entry
exact_equivalence_scope:
  node0004 1x1 Cin64 accumulate, modulo-2^32 product/tree/correction,
  all 3,211,264 outputs
materialized_configuration_mechanism:
  null
performance_and_resource_cost:
  205,520,896 scalar SA occurrences, 25% dot4-lane utilization,
  six GA tree levels + one correction level, 128 tiles / five waves,
  13,046,304 B per tile
unresolved_production_blocker:
  SA scalar-product materializer/terminal first; exact UINT8 tail independent
claim_boundary:
  proposal-only; CONFIG_ONLY_CORRECTNESS_BASELINE=false
```

## 资产与验证

- generator：
  `resnet50_pipeline/conv_node0004_composite_c1_predesign.py`
  SHA256=`2512e958c5e136a1e691d268a10d73a8dd923ba20fe2fbb27fd45c0cf6c1b659`
- build wrapper：
  `tools/build_conv_node0004_composite_c1_predesign.py`
  SHA256=`58f2299bdca5d7e73df7ca92254db7a71f412adac2164d842cfc482b85fab510`
- validator：
  `tools/validate_conv_node0004_composite_c1_predesign.py`
  SHA256=`16d63b7d1575ee424a620049c3c7bb0dd50972100e61b721c243a10a3718590d`
- receipt refresh：
  `tools/refresh_conv_node0004_composite_c1_receipts.py`
  SHA256=`b89da12bb8884c3f05bb92c97d79860a8920dff817186a15380c7c6e19798709`
- tests：
  `tests/test_conv_node0004_composite_c1_predesign.py`
  SHA256=`e43ee6d382e599e1c44ba323dc0189cd29b09cfe203b7a6aae058e9ed098afe8`
- machine contract：
  `contracts/operator_config/conv_node0004_composite_c1_predesign_v1.json`
  SHA256=`6bc34decb9530289f15a6bc368e4ea9441ca6d5c7649ac79e323d9202271bfce`
- validation report：
  `artifacts/operator_config_validation/conv-node0004-composite-c1-predesign-v1/report.json`
  SHA256=`f45e634f3a5900db2d3358971bddc9e2d13ef3b72c5d6ba7b9cb91e06ee5d9e4`

验证：

```text
validator:
  PASS_RECEIPT_ONLY_INTEGRATION_REFRESH__PROPOSAL_ONLY_TARGET_FAIL_CLOSED
numeric_analysis_repeated:
  false
full W3:
  frozen prior conclusion only, mismatch=0; not rerun
unittest:
  6/6 PASS
py_compile:
  PASS
```

## RULE_DELTA_PROPOSAL

未修改公共规则。建议主线评估：

1. `CDA-COMPOSITE-SCRATCH-GLOBAL-VS-TILED-CAPACITY-001`：全局 scratch 超容量时不得直接
   判 topology 不可行；必须给出 tile residency、wave count、region overlap、barrier
   与 traffic lower bound，只有 tile 仍超容量才判资源硬阻塞。
2. `CDA-PREDESIGN-SYMBOLIC-ADDRESS-NOT-PHYSICAL-COVERAGE-001`：proposal-only affine
   bijection 可关闭 logical byte schedule，但 final occurrence hash、LC/MSE/Buffer、
   terminal 或 bitstream 任一未绑定时，不得提升为 materialized coverage。

## BLOCKER_DELTA

```text
ADD
  B_CONV_C1_SA_SCALAR_PRODUCT_MATERIALIZER_AND_TERMINAL

REFINE
  B_CONV_SA_PRODUCT_SCRATCH_SCHEDULE_AND_OWNERSHIP:
    logical schedule/capacity = CLOSED
    physical materializer/terminal/coverage = OPEN_FIRST_BLOCKER

KEEP
  B_CONV_GA_EXACT_ALTERNATIVE_TYPED_TOPOLOGY
  B_QUANT_TAIL_SIGNED_INT32_INGRESS
  B_QUANT_TAIL_FMA_ROUNDING_POINT
  B_QUANT_TAIL_MAGIC_DOMAIN_BOUND
  B_QUANT_TAIL_TYPED_BINDING
  B_QUANT_TAIL_MAPPER_REGISTRATION
  B_EXECPLAN_TYPED_TRANSPORT
  B_QUANT_TAIL_RAW_SIGNED_INT32_MAX0_OPCODE

PACKAGE_RELEASE = NONE
```

服务器包规则和 `ndp-sim/README_SERVER_PACKAGE_LOCAL.md` 未读取，因为完整 local E2
预封包门未通过；没有检查服务器文件、名称或 identity。
