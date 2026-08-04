# Requant 测试修复历史证据与工具归属接收收据

日期：2026-07-27

## 接收范围

已完整读取
`.agents/task_records/20260727_test_repair_to_family_threads_handoff.md`
第 1、3 节；文件为 10,811 bytes，SHA256
`d34d107740385eb1c7d01acf4117ad6b91c056a5c5441dd8d749d06928a583a8`。

后续结构化结果只回传主线
`019fa2ca-72bc-7753-8d58-81e59bc76c88`。组 A、`NDP_copy01`、当前无
SERVER_RUNNING lease 与全部停止门不变。

## 只读动态历史

以下权威记录已完整读取并接收为本族只读历史：

- atomic2 v2：
  `.agents/task_records/20260726_requant_atomic2_v2_return_analysis.md`，
  SHA256
  `a0ffffab5463cc886a17de1c500cfc08cf3dbe34443a6908fec87d89df4568b3`
- directsig v1：
  `.agents/task_records/20260727_requant_guardonly_directsig_v1_return_analysis.md`，
  SHA256
  `1f0fa68401c3e3a925cc8457b641e3fd5999424503ce6d9d363e1c51b477c4dc`
- sfu_ready v1：
  `.agents/task_records/20260727_requant_guardonly_sfu_ready_v1_return_analysis.md`，
  SHA256
  `543164638bda1d7d3b233b568daea6c3bad50002f8b0e0e401572e8d0cd16f43`
- sfu_numeric v1：
  `.agents/task_records/20260727_requant_guardonly_sfu_numeric_v1_return_analysis.md`，
  SHA256
  `ce38cde297f04420ce83c3c85e2ef610510575e8f5c3b0797430641cb7d0da64`
- native SiLU control：
  `.agents/task_records/20260727_decode_silu_control_stock_v1_return_analysis.md`，
  SHA256
  `b1cda36fc10c592c9093b20dbe69dd546fb25177b8e057e1a37c1c5513502a3`
- native SiLU 机器报告：
  `server_returns/decode_silu_fp16N_fp32N_control_stock_v1_return_analysis_20260727.json`，
  SHA256
  `894b01355a888316a9f9475e38cfb2a565689895ba842955e31cc187dd3f8f6a`

历史裁决固定为：

```text
Requant E4/E5 pass = false
last_proven_good =
  SFU_BST_DATA_AND_COEFF_ADDR_64_OF_64_BIT_EXACT
first_unobserved_interval =
  selected coefficient SRAM output
  → ALU capture/tag/result
  → postprocess
  → normal outbuffer write
downstream_bad =
  NORMAL_OUTPORT_ACCEPTED_64_ALL_ZERO
  → MSE4_WDATA_16_ALL_ZERO
  → formal D all zero
```

native SiLU control 只证明共同 stock-RTL
`SFU coeff→ALU→postprocess→normal outbuffer→outport→MSE4 wdata`
payload 路径可工作。其正式 D occurrence/address coverage 失败，分类保持
`SHARED_SFU_NUMERIC_NORMAL_OUTBUFFER_MSE4_PAYLOAD_PASS__D_OCCURRENCE_ADDRESS_COVERAGE_FAIL`；
不得外推为 RequantGuard、Requant E4/E5 或正式 target pass，也不生成 SiLU v2。

## 当前候选和维护归属

唯一候选保持：

```text
rq_node0001_guardonly_sfu_eventedge_stock_v1.zip
bytes = 78068
sha256 = 31877dcf0f11a52a0822525e8f49312d25807f81884377f748425693c89b4a53
state = PACKAGE_READY_NOT_RUN
candidate_release = false
```

以下文件自本收据起归 Requant 本族维护：

- `tools/requant_node0001_server_runtime.py`：
  SHA256 `0d3383a8e054f763880c504166794c428bfd9eb27347d0c06a302f0d2aad98a1`
- `tools/requant_guard_eventedge_server_runtime.py`：
  SHA256 `de0faddd4b4a354e2a005e42903b0aa519ee37cf31cac5c4c2d650a793c3daa9`
- `tools/build_requant_guard_eventedge_onecmd_server_test.py`：
  SHA256 `58399857a35f6f71e14afd5c824f295f4eef2ba753960a53e03269643298fbde`
- `tests/test_build_requant_guard_eventedge_onecmd_server_test.py`：
  SHA256 `3afc769f84ecde5f048923137bebeec773bf42ed9eabc0308d4945a242b1bb9a`

本轮仅接收归属和保存身份，没有修改上述文件。旧 package、return 和权威记录保持只读。
收到 eventedge 正式回传前，不启用 round-only、alias/lifetime 或完整 E4。

## 结构化增量

```text
RETURN_ANALYSIS:
  new_dynamic_result = none
  ownership_handoff = accepted

BLOCKER_DELTA:
  keep =
    B_REQUANT_GUARD_DYNAMIC_DATA_PATH
    B_REQUANT_SERVER_E4_E5
  close = []
  add = []

RULE_DELTA_PROPOSAL = []
PACKAGE_RELEASE = none
```

未修改 `.agents/plan.md`、`.agents/rules/**`、功能 RTL 或其他算子族资产。
