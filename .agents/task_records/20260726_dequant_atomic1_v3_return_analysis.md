# Dequant node0077 atomic v3 回传裁决与规则更新

日期：2026-07-26

## 身份与回传完整性

- 回传：
  `dq_node0077_atomic1_stock_v3_return.zip`
- bytes：`56789`
- SHA256：
  `b08755adfb3dd0665f34d9a0f320accdd9506ac043f7896eab8c62e1ad02e256`
- 用户未提供外部 sidecar；ZIP 内部身份仍可独立验收，但 sidecar 缺失已如实保留。
- 31 entries、解压 `669332` bytes；无不安全路径、重复项、波形、build tree 或
  nested archive。
- `RETURN_RECEIPT.json` 列出的 30 个 payload 与实际 30 个文件逐项
  path/size/SHA256 一致。
- 对应正式源包：
  `artifacts/operator_config_validation/r5-server-test-packages/dq_node0077_atomic1_stock_v3.zip`
  （bytes=`75376`，SHA256=
  `f77d92165cc32af41e157da27ce4b7141882c8d49871961cab22a41ba668742c`）。

## 动态结果

- compile/sim/run=`0/0/0`，仿真自然进入 SCA_D 并打印
  `Simulation completed successfully!`。
- slice0、slice1 均自然 Start/Finish；XMR 静态门检查 347 个生成层级引用，
  runtime-indexed XMR=0。
- 功能 RTL 未改，TB probe 编译后逐字节恢复，focused RTL/support identity 五阶段稳定。
- SCA 每片仅在 word 0 preload 一行 A；D 从 word 1 开始，所以 D 区未预置 golden。
- 正式 D 每片 4 行、共 8 行，全部非 `x` 且逐 bit 对独立 golden：
  - slice0 SHA256：
    `3d77e78c5fd2460ef679223c12580455ab0b0e1df4ee725a82caf9e6758f72b5`
  - slice1 SHA256：
    `4d6e5afa95a2d0053be3b45d8b2fb87044da267db9dbaa41b5892afd140a6083`

因此，修正后的 `GROUP2.ROW_LC.end=4` 已在 stock RTL 上动态证明能够提供完整 4 行
D，最小 CWH16 的 uint8-to-fp32、GA add、GA mul、normal outbuffer、MSE4 最终写回
与 SCA_D 数值路径均已闭合。

## observer 为何仍报失败

原始 observer 每片只配对出第 1、4 beat，共 4/8；同时出现 8 条
`missing_pre_remap_address` / `accepted_wdata_without_address`。

根因属于 observer evidence：

1. pending-address 队列仅在
   `mem_ag_ob_chl_wr_hs && mem_ag_ob_bp_pre_barrier` 时入队，却用每个解耦的
   `local_req_hs/local_wdata_hs` 出队；队列缺项时 observer 直接丢弃已经接受的
   write-data 证据。
2. expected JSON 保存的是 slice-local word `[1,2,3,4]`，observer 的
   `linear_addr` 已加 stream base。slice1 实际为
   `0x200001..0x200004`，不能直接与 `[1..4]` 比较。
3. observer 没有写出 `STAGE_FINISH` 汇总，所以尚未证明 finish 当周期每片恰有
   4 个 accepted write 且 outstanding=0。

正式 D 是唯一、未预置、全覆盖且 bit-exact 的权威最终数值证据。因此 observer
漏记不能定性为硬件丢写、配置失败或 RTL 缺陷。

## 最终分类

`ATOMIC_FUNCTIONAL_PASS_OBSERVER_TEMPORAL_EVIDENCE_INCOMPLETE`

- `ATOMIC_FUNCTIONAL_SEMANTICS_PASS=true`
- `ATOMIC_TEMPORAL_DRAIN_PASS=false`
- `ATOMIC_CONTRACT_FULL_PASS=false`
- 计 1 次原子动态运行，不计 node0077 E4/E5。
- `candidate_release=false`
- `B_DEQUANT_SERVER_E4_E5` 不变。

## 规则更新

- 新增 `CDA-SERVER-OBSERVER-DECOUPLED-HANDSHAKE-001`
  - 文件：`.agents/rules/服务器测试包生成规则.md`
  - SHA256：
    `67018547fbe4e485d3d8c2420821e0c8f65bfec0bab0ecc1099ad9de37e55eb7`
- 新增 `CDA-DEQUANT-ATOMIC-V3-DYNAMIC-EVIDENCE-001`
  - 文件：`.agents/rules/DequantizeLinear原子动态合同规则.md`
  - SHA256：
    `cc9e5215d92e55b7440a07954503586c9a6d50f56fe505595341c0ba71358d85`

机器报告：
`server_returns/dq_node0077_atomic1_stock_v3_return_analysis_20260726.json`

## 后继

无需为了相同最小数值语义原样再跑 atomic。下一轮应由测试修复任务使用完整 v6 冻结资产
生成全新身份 node0077 stock-RTL E4；正式 28×188 D 回读仍为权威数值门。若继续保留
observer，只独立统计 raw `local_req_hs`/`local_wdata_hs` 和 finish 计数，不再因
地址配对失败丢弃 write-data。E4 正式通过前不得生成 E5。
