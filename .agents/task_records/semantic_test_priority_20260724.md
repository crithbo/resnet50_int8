# 未闭合语义测试优先级

状态增量：六份真实 stage JSON、mapping、bitstream、六次完整
Load_Config/Start_Comp/Barrier 生命周期和 16×512 本地 golden E2 已完成。
无 RTL patch 原子服务器包已生成；动态双流 stall/resume、真实 drain、normal
FIFO 全周期和正式 D readback 属于服务器 E4。

状态增量：六份真实 stage JSON、mapping、bitstream、六次完整
Load_Config/Start_Comp/Barrier 生命周期和 16×512 本地 golden E2 已完成。
无 RTL patch 原子服务器包已生成；动态双流 stall/resume、真实 drain、normal
FIFO 全周期和正式 D readback 属于服务器 E4。

## P0：GAP repair_v9 服务器动态门

- 16×512 正式 D readback 逐行 golden。
- 8 个普通 GA PE 全周期 `count∈[0,2]`。
- invalid-slot reuse 为 0。
- 跨 block 在新 partial 有效前 `C=0`。
- same-clock MSE4 或正式回读裁决。
- focused pre/post/post-run/post-restore identity。
- 独立 E5 重跑。

这些测试本地不能替代，repair_v9 当前保持 E2。

## P1：纯配置替代路径

- `int32_mac(A,1,C)=A+C` 的 INT32 方程。
- opcode 14 不进入 transout。
- 49→25→13→7→4→2→1 六层显式归约。
- 双输入 buffer/tag/backpressure 和中间 INT32 写回。

本轮已新增前三项本地语义测试；双输入动态路由和服务器数值仍待测试。

本地结果：`tests.test_gap_int32_mac_reduction_semantics` 与 GAP
repair/RTL-repair/D-index 回归合计 17 项通过。该结果把 `int32_mac` 备选提升到
“公式、编码、非 transout 分类和归约调度已闭合”，不提升双输入动态路由或服务器
数值证据等级。

用户随后暂停 RTL repair 和服务器包续测。本地继续新增并通过：

- buffer0/group0 与 buffer4/group2 双输入、buffer5 写回的静态物理路由；
- A/C 同时 valid 才 match、同拍消费的 backpressure 方程；
- 相同 terminal tag 的非 transout 传播；
- normal outbuffer FIFO 六周期全部请求组合枚举，count 始终位于 `[0,2]`，
  合法同时读写不命中同一槽。

`tests.test_gap_int32_mac_reduction_semantics` 与
`tests.test_gap_int32_mac_stage_memory` 当前合计 22 项通过。已完成 GA 三输入、
normal outbuffer、双 MSE occurrence、六级地址/terminal 以及 CGRA/W3 golden
三方数值闭合。六份真实 stage JSON、mapping、bitstream、execplan 同 mask
barrier 生命周期和 16×512 本地 golden E2 已完成；无 RTL patch 原子服务器包
已生成。动态双流 stall/resume、真实 drain、normal FIFO 全周期和正式 D readback
仍属于服务器 E4，不能由本地结果替代。规则合同见
`.agents/rules/GAP_int32_mac_bypass_rules.md`，机器可验合同见
`contracts/operator_config/gap_int32_mac_bypass_v1.json`。

本地增量：真实 stage 资产已回灌机器合同，过期的
`B_GAP_INT32MAC_REAL_STAGE_ARTIFACTS=open` 已修正为 `closed_local_e2`。
另外已按 RTL 精确证明 opcode14 的 C/tag feedback 分支和 transout compaction
不可达，并逐份审查六 JSON 的三输入、转换、tailing/ping-pong 与地址对齐字段。
剩余 P1 仅是动态硬件证据，不再包含静态 JSON/bitstream/execplan 语义缺口。

## P2：影响 54 个 SA stage

- SA INT8 CSA 数值修复/替代方程。
- INT8、BF16、enabled-bias 的动态数值。
- FP32→FP16/BF16 tie、subnormal、overflow。

## P3：通用动态边界

- MSE first/stall/resume。
- padding 已有样例，tailing 缺授权启用样例。
- Buffer ping-pong 的非 A/READ_STREAM0 组合。
- N2N neighbor_stream1、mixed direction、clear/reconfigure。

## P4：其他 GA

- GA FP/LUT：sqrt、BF16、input ping-pong。
- 修复后的 GA int8_max 流水与数值重跑。
