# DeepSeek RMSNorm 增量规则

最后更新：2026-07-25

本文件只保存 crop-derived DeepSeek RMSNorm 五 stage 验证中新确认的专项拓扑。公共生成门
和硬件字段语义不在此重复。证据上限为本地 E2，不授权服务器包或 RTL 修改。

## 1. prefill remote-sum 是 7×4-slice 分组归约

规则 ID：`CDA-DEEPSEEK-RMSNORM-GROUPED-REMOTE-SUM-001`

对 `hidden=896`、`7Q heads`、`4 slices/head` 的 crop：

- op0 `prefill_summac_fp32MN_fp32MN` 在 28 slice 分别产生每个 slice 的局部平方和；
- op1 `prefill_remote_sum_fp32MN_fp32MN` 必须启用 28 slice，A 的逻辑 shape 为
  `[1,4,32]`，`source=op0`，`type=slice0`；这里的 `slice0` 是每个四片组内的相对
  source selector，不是全芯片唯一的物理 slice0；
- op2 `prefill_mac_SFU_fp32MN_fp32MN` 必须启用 28 slice，A 为普通 `source=op1`，
  不得再附加全局 `type=slice0`；
- op3、op4 继续在 28 slice 分别完成 reciprocal-RMS broadcast multiply 和 gamma
  multiply。

可信依据为 `jsons/rmsnorm/rmsnorm_withbaseaddr.json`、其四份 execplan/SCA，以及
`ndp-sim/jsons` 中对应的五份硬件验证 JSON。

## 2. raw Stage 与活动 Stage producer 必须分离

规则 ID：`CDA-DEEPSEEK-RMSNORM-STAGE-TOPOLOGY-OWNER-001`

当前 `ndp-sim/model_execplan/op_json/rmsnorm.json` 与 crop-derived prefill Stage 把
op1 写成仅物理 slice27、A shape `[1,28,32]`，又把 op2 A 写成全局 `slice0`。该组合
会请求不存在的 producer slice，不能自动物化为完整生命周期。

上游文件保持只读，不作为项目活动 Stage 输出。项目活动 Stage producer 必须：

1. 同时保存 raw Stage 与 active Stage 的字段级 diff；
2. 只允许修改两个 RMSNorm occurrence 各自的 op1 slice mask、op1 A shape/type 和
   op2 A type，共 8 个登记叶子；
3. 不得把归一化前的 leader mismatch、28-source contiguous gather 当成硬件语义；
4. 只有 active 五 stage 双隔离完整结束、最终地址/SCA/CONFIG/control 解码均通过，
   才能关闭 `B_DS_RMSNORM_STAGE_TOPOLOGY_GAP`。

当前活动产物为 `layer0_prefill.rule_normalized.json`。其 8 个 RMSNorm 叶子、两次
隔离重建和可信 package 对照均通过后，该 blocker 对项目活动链路关闭；上游 raw
差异继续作为 provenance 边界保留。

