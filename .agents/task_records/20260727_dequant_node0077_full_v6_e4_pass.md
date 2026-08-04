# Dequant node0077/v6 正式 E4 通过

日期：2026-07-27

## 结论

`dequant_node0077_stockrtl_e4_onecmd_v2` 是 node0077/v6 第一份正式 stock-RTL E4
通过证据，归一化为 `FIRST_DYNAMIC_PASS`，不是 regression。

- return ZIP：252,634 bytes，
  SHA256 `79b3ea77d7a1651ee77181cffe7264d86da59f47fffa17277d603d8a727272d4`
- 来源 package：SHA256
  `2ac27a4856b36bb660c0293ff53f84794464283712f20fe0d84dabfa16b699e0`
- 内部 RETURN_RECEIPT：105/105 exact-set、size、SHA、allowlist 通过
- compile/sim/run：`0/0/0`；28/28 slice 自然完成；stock RTL 未变
- 正式 D：28×188=5,264 个 128-bit 行全部逐 bit 对 golden，地址唯一且未 preload
- 每片前 750 个 fp32 正确，末尾 2 个为 `+0.0f`
- layout inverse 无损还原 `float32[16,1000]`，actual/expected SHA256 均为
  `d5aa938813ec8ef7fe51cc2288df5f0e1782c19729a184cef248718ce83a311d`
- temporal observer：5,264 request、5,264 write-data；各片 188/188，finish summary
  一致，不做未经证明的 request/data 配对

## 状态变化

- 新增规则 `CDA-DEQUANT-NODE0077-E4-V6-DYNAMIC-PASS-001`
- `B_DEQUANT_SERVER_E4_E5` 收窄为 `B_DEQUANT_SERVER_E5`
- 正式服务器 E4 计数从 0 更新为 1
- `candidate_release=false`、正式 target config 仍保持；E5 通过前不得升级
- 机器报告：
  `server_returns/dequant_node0077_stockrtl_e4_onecmd_v2_return_analysis_20260727.json`
  SHA256 `c7d1380f6dd365b6349e050390a5e112125906eb04a73fcd54a3dec412bfe35f`

## 唯一后继

从完全相同的 v6 语义资产生成全新 package/install/run/return 身份的正式 E5，复验
28×188 formal D、全 tensor inverse、自然完成、temporal raw count、return exact-set
和 stock RTL 身份。E5 通过后只放行 Dequant node0077，不外推到其他节点或整网。

