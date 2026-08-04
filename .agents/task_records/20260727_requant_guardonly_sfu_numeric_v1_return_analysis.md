# Requant guard-only SFU numeric v1 回传裁决

日期：2026-07-27

## 结论

本轮不是 parser 根因。`rq_node0001_guardonly_sfu_numeric_stock_v1` 已自然完成一个
guard stage，stock RTL 与 observer 恢复身份通过；正式 D 仍为 16 行全零。

离线按物理 PE 将 `PE_SELECTED_INPUT` 与三拍后的 BST 记录逐事务配对，64/64 条 data
逐 bit 一致，且符号位为 1/0 时 coeff address 分别精确为 `0x00/0x41`。最后可信边界
因此从 preprocess0 valid 推进到
`SFU_BST_DATA_AND_COEFF_ADDR_64_OF_64_BIT_EXACT`。

包内 3,888 条 BST raw 记录不是 3,888 个事务：16 个 PE 各被持续为高的 level
qualifier 重复采样 243 周期，其中 400 条处于 X/Z。原自动路由所称
`raw=3888 / parsed=3488` parser divergence 被废弃，改判
`OBSERVER_EVENT_QUALIFICATION_ERROR`。

首个未观测区间是：

```text
selected coefficient SRAM output
  → ALU capture/tag/result
  → postprocess
  → normal outbuffer write
```

下游坏边界是：

```text
NORMAL_OUTPORT_ACCEPTED_64_ALL_ZERO
  → MSE4_WDATA_16_ALL_ZERO
  → formal D 16 lines all zero
```

当前仍不能在 CONFIG、RTL 和 observer 三类责任中二选一。node0001 仍不是 E4/E5，
`candidate_release=false`，保留 `B_REQUANT_GUARD_DYNAMIC_DATA_PATH` 与
`B_REQUANT_SERVER_E4_E5`。

## 身份与收据

- return ZIP：74,933 bytes；
  SHA256=`a1d15ef3b5a1c426eec92e8fd7b1888a81b29e8825cc9a3c753d0809e947bbad`
- 外部 sidecar：缺失；外层交付门 fail-closed，但不推翻内部诊断证据
- 内部 return：33 entries，32 个声明 payload 的 exact-set/size/SHA 全通过
- source package：
  `artifacts/operator_config_validation/r5-server-test-packages/rq_node0001_guardonly_sfu_numeric_stock_v1.zip`
- source package SHA256：
  `8e96d1bbd6e0379b8d33fca251b27bbc40bb32fc56d82418a3ae85e0515e1a1b`
- returned manifest SHA256：
  `d4b7ccf7ca24f0c4a940fb863ada3dc5c367797f71dfa04822aba400adbdf4ae`
- compile/sim/run：0/0/0
- lifecycle：1 start、1 finish、1 same-mask fence

## 规则增量

- 公共规则：
  `CDA-SERVER-OBSERVER-EVENT-QUALIFICATION-001`
- Requant 专项证据：
  `CDA-REQUANT-SFU-NUMERIC-V1-DYNAMIC-EVIDENCE-001`

## 唯一后继测试

保持 guard-only 的 JSON、mapping、bitstream、execplan、输入、RequantGuard、golden 和
预期写逐字节冻结，以全新身份增加 event-qualified 的 coeff SRAM output、ALU
capture/result、postprocess 与 normal outbuffer write 逐事务证据。不得修改功能 RTL
或 TB driver；只读 observer 只能安装到服务器命令显式传入的唯一 `NDP_copyXX`。

机器报告：
`server_returns/rq_node0001_guardonly_sfu_numeric_stock_v1_return_analysis_20260727.json`
