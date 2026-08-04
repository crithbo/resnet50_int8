# Flatten / QLinearAdd / Requant 并行结果主线裁决

日期：2026-07-27

## Flatten / View node0073

接受 `ENDPOINT_BINDING_PENDING`：

- node0073 是 metadata-only zero-copy alias，不生成算术 JSON、instruction 或 request；
- typed 链为 node0072 D `fp32[16,2048,1,1]` → View(axis=1) →
  node0074 A `fp32[16,2048]`；
- 32,768/32,768 元素地址映射、C-order strides、131,072-byte span、allocation
  ownership 与 accepted-handshake lifetime 已闭合；
- 独立 local E2 不适用；node0072-D/node0074-A 最终 addressed execplan/layout、
  双端 occurrence/address coverage、allocator plan 与 release 证书缺失，因此
  integrated target local E2=false。

发布 `Flatten_View算子配置规则.md`。不允许为满足计数而生成无意义算术 JSON。

规则发布后的 family 收据刷新已验收：

- status=`ENDPOINT_BINDING_PENDING`；
- `claim_label=null`、`claim_enabled=false`；
- `CONFIG_ONLY_CORRECTNESS_BASELINE` 只作为 endpoint 证书通过后的 eligible label；
- input/constant replay、copy 和 host-precomputed internal/scaled/rounded/saturated/final
  tensor 全为 false；
- 6/6 定向测试、双重重建和 32,768 元素枚举保持通过，未重做数值分析。

刷新身份：

- config：
  `a63655c339ab68b7edad6d7c9a30776d369749dda80d3b5661152ec07582bddc`
- contract：
  `067351563c40fb1b95e63f3b327e9758f19c49c72d3c48b348d223426ada9851`
- validation report：
  `62b92ffad44bc89ea6e6a97c6f77110170e208ccefde0f63ffed1cabea61b13c`
- manifest：
  `078a3f6df952750684214a1e3db931eaf019b788c6dc6d7b7dbd4c5cc58285fb`

后续 Dequant node0072 local E2 已补齐 producer standalone handoff：owner、logical
strides/span、28 片 D base/coverage、addressed graph/layout/execplan/SCA 和
config-bound physical D 均已冻结。但 shared multi-op execplan、跨 node
lifetime/visibility、node0073 consumption 与 dynamic final-write accepted 仍缺失，
所以 `B_VIEW_PRODUCER_ALLOCATION` 不关闭，只收窄为 integrated certificate pending。

## QLinearAdd stage0

接受 `STAGE0_MATERIALIZED_TAIL_BLOCKED_NOT_RELEASED`：

- 17 个逻辑实例拆成 51 个 physical stage：A exact dequant、B exact dequant、
  paired FP32 add；
- 51 个 non-alias scratch 共 1,059,849,152 physical bytes，
  stage0 logical scratch traffic 1,766,395,200 bytes；
- node0076 B 保持 1000 元素；末 occurrence 8 个有效 FP32/32 bytes，
  physical 4032=4000 typed+32 padding；16,000 replay 地址已枚举；
- 13/13 定向测试通过，只关闭到 `SUM_F32` 的 W3/readiness/replay/scratch/
  barrier/lifetime/config-bound 子范围。

完整 QLinearAdd baseline 数仍为 0。共享 UINT8 tail、native typed handler/final leaf
diff、mapping/bitstream、execplan/SCA、Y 和动态门全部保持开放。

QLinearAdd 专项规则增加 stage0 三 physical stage、broadcast replay tail 分账与
stage0 claim boundary。

规则发布后的 QLinearAdd receipt-only refresh 已验收，未重做 17-instance 数值分析：

- node0076 replay 的 source producer 为 `hwop-0076-00:B_DEQUANT`，source tensor 为
  `hwop-0076-00:B_SCALED`；
- 映射固定为
  `B_SCALED.base+(logical_output_index%1000)*sizeof(float32)`；
- 数据来自正式 hardware stage output committed scratch，
  `host_precomputed_internal_tensor=false`；
- receipt-only validator `valid=true`、warnings 为空、
  `numeric_analysis_repeated=false`。

刷新身份：

- config：
  `04479a175adb059757a05e1de602f7cb7fd61f71317341a61842eb76c998295e`
- stage0 contract：
  `90eeb8eaa3bf3a3aacfa62a2cfa83728225a515183fb4607f9dba53aedaa7a50`
- receipt report：
  `b3fe017bbd639e62f0c5258381fe6333bb52689e9de71dd3f42a89cc197b7c10`

## Requant / AverageRequant

接受 `NO_GROUP_MATERIALIZED_FIRST_BREAK_ADJUDICATED`：

- 54/54 W3 和 33 zp0/16 even nonzero/5 odd nonzero 分类不变；
- 三组 `CONFIG_ONLY_CORRECTNESS_BASELINE` 数量均为 0；
- zp0 与 AverageRequant 首断点是
  `B_QUANT_TAIL_THREE_PE_TOPOLOGY`；
- even/odd nonzero 首断点是
  `B_QUANT_TAIL_SIGNED_INT32_INGRESS`；odd tie parity 是次级门；
- node0001 旧 local E2 不外推，event-edge 包冻结。

发布 `CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001`：只允许重放原始 typed
input、正式 producer output 和冻结常量；不得由 host 预计算内部 scaled/rounded/
saturated/final tensor 替代算子计算。

Requant receipt/dependency refresh 已验收，未重做 54-stage 数值分析：

- Quant 两阶段 singleton 仅作为
  `LOCAL_CONFIG_BOUND_DIAGNOSTIC_NOT_BASELINE` 依赖；
- stage0 scratch `0x41cc0000`、sequential=26、fused negative control=25；
- 不证明完整 33 zp0/AverageRequant 域、signed/magic domain、native transport、
  mapping/bitstream、execplan/SCA 或 terminal；
- baseline=0、首断点顺序和 blocker 集合均不变。

刷新身份：

- contract：
  `17f9e1f14e401a9542b1f78d62ce2aebd2e1029357931aaec825e70e100fd05b`
- validation report：
  `ef9d0719627959dce7a5451d4c8fa1e2d778b359c8a394366be961d3aa3775b8`
- generation receipt：
  `31e1d9b132bc5a40678f5d7edef026ccb9f4d76a146305ec052c9aec5e6fe1ae`

## 全局计数与发布

- 正式 ResNet 三方节点仍为 1/78；
- 新增完整 config-only correctness baseline：0；
- 新增完整 operator E2：0；
- server package：0；
- server lease：0；
- RTL 修改：0。

三项 family 结果均通过主线证据边界审阅；没有一项升级为完整节点通过。
