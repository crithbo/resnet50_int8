# Exact UINT8 quant-tail rounding discriminator 主线裁决

日期：2026-07-27

## 接受的本地事实

- 冻结 singleton：
  `int32=400,multiplier_bits=0x3d828f5c,zero_point=0`；
- stage0 独立 INT32→FP32→MUL 后，128B FP32 scratch 每 lane bits 为
  `0x41cc0000`；
- stage1 raw FP32→`MAC(x,1.0,12582912.0)`→
  `INT32_SUB(0x4b400000-zp)`→UINT8 得到 26；
- 一阶段 fused negative control 得到 25；
- 三份 strict diagnostic JSON 的 222 个 leaf diff 全部有 owner/输入/公式/旧值/
  期望新值/授权声明；
- 最终 occurrence/address coverage 为 scratch 128/128B、stage1 output 32/32B、
  negative control 32/32B；
- stage1 消费合同内 stage0 producer output，不是 host 预计算，满足
  `CDA-CONFIG-ONLY-INPUT-REPLAY-NONCOMPUTATIONAL-001`。

该结果把“显式 scratch 可隔离 MUL 的 binary32 舍入点”从纯提案提升为
singleton config-bound diagnostic，但只覆盖 32 个相同正数 lane；没有 mapping、
bitstream、execplan/SCA、完整合法域、signed/magic domain 或动态 terminal/readback，
所以不是 `CONFIG_ONLY_CORRECTNESS_BASELINE`，不计 E2。

## node0074 裁决

真实 QuantizeLinear node0074 不生成 target。首个不可绕断点是 exact binary32
division：

```text
x_bits     = 0x3d0f81f1
scale_bits = 0x3cbf57ec
exact divide + RNE/saturate = 2
reciprocal-FMA-magic        = 1
```

该反例为正有限 FP32，先于 signed ingress、typed handler、mapper、occurrence 和
terminal，因此 `B_QUANT_NODE0074_EXACT_DIVISION` 保持开放。

规则/依赖收据刷新后，新增从属 blocker
`B_QUANT_NODE0074_FLATTEN_ENDPOINT_BINDING`。Flatten integrated E2 最终要求
node0074-A 具备：

- 与 node0073 output 相同的 storage identity；
- `consumer_base=producer_base+view_offset`；
- 32,768 个 FP32/131,072 bytes 的 accepted read coverage；
- allocation 存活到最后一次 accepted read。

exact division 仍是首断点，因此六个 final endpoint 字段保持 null，
`provisional_address_allowed=false`、`target_endpoint_claimed=false`；该依赖不改变
首断点顺序，也不得用 provisional 地址提升 Flatten integrated E2。

刷新身份：

- capability contract/report：
  `dedd0e467a31ecb42cd3e76faddb55901286b97fb2311fc4052d0a157dbd8c6e` /
  `f73c9eace3547ea5d02f976d43d63a1236258dcbeb8a77c286235047f6a2b7e1`
- discriminator contract/report：
  `82ab3276a8ae9ee35aeda366756dd4525dfac77c6e3ed40cf395d7a011f8a477` /
  `1a10cd4697af0e8e36e8d814fff783f99d920267caaa539d9760d400166739c0`
- manifest：
  `9800cce794f357b222f58fa53f393382d0cb90f6c0ce5dddb2b7ec79f986b4f0`

## 对 Requant/GAP/QLinearAdd 的影响

Requant 报告中的 three-PE topology 首断点现在有一个 two-stage singleton 诊断替代，
但完整 33 个 zp0/AverageRequant 域尚未证明，native transport/mapping/terminal 也未
闭合；因此 Requant baseline 计数仍为 0，其 blocker 不关闭。QLinearAdd 与 GAP 只可
消费该诊断作为顺序可分离证据，不能据此放行完整 UINT8 tail。

## 发布

- 公共规则增量：无；
- 完整 config-only baseline：0；
- E2/E4/E5：0；
- server package/lease：0；
- RTL 修改：0。
