# 旧“测试修复”任务到新算子族任务的证据交接

日期：2026-07-27  
来源任务：`019f8edc-ef60-7db1-a95c-f77ae2d4cc58`  
接收主线：`019fa2ca-72bc-7753-8d58-81e59bc76c88`

## 0. 转接后的状态更新

本记录物化后，Dequant 新任务已完成原交接边界中尚缺的 config-bound simulator 腿。
`node0077/v6` 现为：

`THREE_PARTY_CONFIG_BOUND_CLOSURE_PASS`

三方比较覆盖 `float32[16,1000]` 的 16,000 个元素，golden、simulator、E4 hardware、
E5 hardware 两两均为 0 bit mismatch；项目正式 ResNet 三方节点计数可从 `0/78`
更新为 `1/78`。权威记录：

- `.agents/task_records/20260727_dequant_node0077_config_bound_three_party_closure.md`
- `artifacts/operator_config_validation/r5-dequant-node0077-config-bound-simulator-v1/three_party_report.json`

下面第 2 节仍完整保留旧测试修复任务移交的硬件证据；其中“Dequant 剩余工作只有
simulator 腿”应以本节的新状态取代。

## 1. 证据等级总览

旧测试修复任务中可称“服务器数值路径通过”的项目只有：

1. Dequant node0077 atomic v3：最小功能数值通过，但 observer temporal drain
   证据不完整，不计 E4/E5；
2. Dequant node0077/v6：完整 E4 首次通过和全新身份 E5 重复通过；
3. 原生 `decode_silu_fp16N_fp32N` control：共同 SFU/normal-outbuffer/MSE4
   payload 通过，但正式 D occurrence/address coverage 失败。

Requant node0001 本身没有通过 E4/E5；其诊断只是把首分歧逐步推进到
Requant 专属 coeff/ALU 消费路径。GAP 没有服务器动态通过版本。

## 2. DequantizeLinear 交接

接收任务：`019fa2bf-f9a5-7a73-ada3-b2b910721de3`

### 2.1 atomic v3

- return ZIP：`dq_node0077_atomic1_stock_v3_return.zip`
- bytes：`56789`
- SHA256：
  `b08755adfb3dd0665f34d9a0f320accdd9506ac043f7896eab8c62e1ad02e256`
- source package SHA256：
  `f77d92165cc32af41e157da27ce4b7141882c8d49871961cab22a41ba668742c`
- compile/sim/run：`0/0/0`
- slice0/1 自然完成；
- formal D：2 slice×4 行，全部 binary-known 且逐 bit 对独立 golden；
- 证明最小 CWH16 的 uint8→fp32、GA add/mul、normal outbuffer、MSE4 和
  SCA_D 数值路径；
- observer 因解耦 request/wdata 队列和地址域混用漏配对，temporal drain
  未通过；
- 分类：
  `ATOMIC_FUNCTIONAL_PASS_OBSERVER_TEMPORAL_EVIDENCE_INCOMPLETE`
- 不计 E4/E5，不应重跑相同 atomic。

权威记录：

- `.agents/task_records/20260726_dequant_atomic1_v3_return_analysis.md`
- `server_returns/dq_node0077_atomic1_stock_v3_return_analysis_20260726.json`

### 2.2 完整 v6 E4

- identity：`dequant_node0077_stockrtl_e4_onecmd_v2`
- return ZIP：252,634 bytes
- return SHA256：
  `79b3ea77d7a1651ee77181cffe7264d86da59f47fffa17277d603d8a727272d4`
- source package SHA256：
  `2ac27a4856b36bb660c0293ff53f84794464283712f20fe0d84dabfa16b699e0`
- compile/sim/run：`0/0/0`
- 28/28 slice 自然完成；
- formal D：`28×188=5,264` 行，地址唯一、未 preload、逐 bit 对 golden；
- 每片 750 个有效 fp32，末尾 2 个 `+0.0f`；
- inverse 还原 `float32[16,1000]`，actual/expected SHA256：
  `d5aa938813ec8ef7fe51cc2288df5f0e1782c19729a184cef248718ce83a311d`
- temporal raw count：5,264 request / 5,264 write-data；
- 分类：`FIRST_DYNAMIC_PASS`。

权威记录：

- `.agents/task_records/20260727_dequant_node0077_full_v6_e4_pass.md`
- `server_returns/dequant_node0077_stockrtl_e4_onecmd_v2_return_analysis_20260727.json`

### 2.3 完整 v6 E5

- identity：`dequant_node0077_stockrtl_e5_onecmd_v1`
- return ZIP：253,442 bytes
- return SHA256：
  `ae993cbf7cc51757a6be24f89e72a3e77ac98cba8953ef1510f93e736a71ca66`
- source package：153,596 bytes
- source package SHA256：
  `83cd2db78f99d27f02c2b65a46f9f5c43e94b9ff9a5c50ef0273a0409f1cab68`
- compile/sim/run：`0/0/0`
- 28/28 slice 自然完成；
- formal D、inverse、temporal count 和 stock RTL identity 与 E4 独立复验通过；
- 分类：`E5_PASS / REPEATED_DYNAMIC_PASS`；
- `B_DEQUANT_SERVER_E5` 已关闭；
- node0077/v6 是正式 ResNet target config。

权威记录：

- `.agents/task_records/20260727_dequant_node0077_full_v6_e5_pass.md`
- `server_returns/dequant_node0077_stockrtl_e5_onecmd_v1_return_analysis_20260727.json`

Dequant 不再生成服务器包；剩余工作只有 config-bound simulator 三方总账。

## 3. RequantizeUint8 与原生 SiLU control 交接

接收任务：`019fa2bf-95cd-7502-82c8-6a48cf12d648`

### 3.1 Requant 动态证据链

Requant 全部诊断均非 E4/E5：

1. atomic2 v2：
   - 1 logical occurrence、guard+round 两 stage 自然完成；
   - raw observer 重解析为 20/20 accepted write，guard 16、round 4；
   - 20 个 payload 和 20 行 formal D 全零；
   - 首分歧：
     `GUARD_WRITE_PAYLOAD_ZERO_AFTER_NONZERO_INPUT_PRELOAD`。
2. direct-signal：
   - int32→fp32 registered conversion、GA final out、PE selected input
     均 64/64，62 非零、2 预期零；
   - MSE4 16/16 和 formal D 仍全零；
   - 最后可信边界推进到 PE selected input。
3. SFU readiness：
   - opcode `0x18`、SFU valid、compute-enable、LUT init、group valid 和
     preprocess0 registered valid 已证明；
   - MSE4/formal D 仍全零；
   - 最后可信边界：
     `SFU_PREPROCESS0_VALID`。
4. SFU numeric：
   - selected input 到 BST data 64/64 逐 bit；
   - coeff address 按符号 64/64 精确为 `0x00/0x41`；
   - level qualifier 的 3,888 raw 不是事务数，400 条为 X/Z；
   - 最后可信边界：
     `SFU_BST_DATA_AND_COEFF_ADDR_64_OF_64_BIT_EXACT`；
   - 未观测区间：
     coeff SRAM output→ALU capture/result→postprocess→normal outbuffer write。

权威记录：

- `.agents/task_records/20260726_requant_atomic2_v2_return_analysis.md`
- `.agents/task_records/20260727_requant_guardonly_directsig_v1_return_analysis.md`
- `.agents/task_records/20260727_requant_guardonly_sfu_ready_v1_return_analysis.md`
- `.agents/task_records/20260727_requant_guardonly_sfu_numeric_v1_return_analysis.md`

### 3.2 原生 SiLU control 的正证据和错误边界

- return ZIP：57,030 bytes
- return SHA256：
  `182d3dbb160aac768cd37d634cc2ba34584a8524df4cb4983df3cc6691e0f246`
- source package：47,209 bytes
- source package SHA256：
  `3cbabba52e414f38ec33a2e234972fe3455655a6669163e5765d4c1141a62c53`
- compile/sim/run：`0/0/0`，自然完成；
- 真实 event：每片 16，合计 32；
- preprocess、coeff、ALU input/result、postprocess、normal outbuffer
  input/commit、outport 均 32/32；
- MSE4 payload 16/16 逐 bit 正确；
- 共同 stock RTL：
  `SFU coeff→ALU→postprocess→normal outbuffer→outport→MSE4 wdata`
  已证明可工作；
- 但每片正式 D 8 行仅前 2 行 known，后 6 行 X，只保存最后 occurrence；
- 分类：
  `SHARED_SFU_NUMERIC_NORMAL_OUTBUFFER_MSE4_PAYLOAD_PASS__D_OCCURRENCE_ADDRESS_COVERAGE_FAIL`。

这只排除“共同 SFU 普遍失效”，不能证明 RequantGuard 专属 coeff table/opcode/tag/
config consumption。无需生成 SiLU v2。

权威记录：

- `.agents/task_records/20260727_decode_silu_control_stock_v1_return_analysis.md`
- `server_returns/decode_silu_fp16N_fp32N_control_stock_v1_return_analysis_20260727.json`

### 3.3 当前唯一 Requant 候选

- identity：`rq_node0001_guardonly_sfu_eventedge_stock_v1`
- ZIP：78,068 bytes
- SHA256：
  `31877dcf0f11a52a0822525e8f49312d25807f81884377f748425693c89b4a53`
- manifest SHA256：
  `1c14c62a39a407dac6383f07ce18dc2697c7122351b8603c6c072e7e1d70af48`
- frozen semantic tree SHA256：
  `3f6c7116c72dcebcae9102a3d822c7f4d8f1e26b8005af1432e72e461559e222`
- 23 个冻结语义文件；
- `PACKAGE_READY_NOT_RUN`、`candidate_release=false`、非 E4/E5；
- 当前没有服务器 lease；
- 唯一命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

权威记录：

- `.agents/task_records/20260727_requant_guardonly_sfu_eventedge_stock_v1_package.md`
- `.agents/task_records/20260727_requant_guardonly_sfu_eventedge_v1_read_receipt.json`

工具所有权转给 Requant 新任务：

- `tools/requant_node0001_server_runtime.py`
- `tools/requant_guard_eventedge_server_runtime.py`
- `tools/build_requant_guard_eventedge_onecmd_server_test.py`
- `tests/test_build_requant_guard_eventedge_onecmd_server_test.py`

冻结旧包和旧 return 只读。收到 event-edge 正式回传前，不启用 round、alias/lifetime
或完整 E4。

## 4. GAP 与基础设施历史

当前没有新 GAP 算子任务，因此全部交给新主线保管，保持冻结。

### 4.1 probe_v7

最终分类：

`ga_int32_sum_outbuffer_count_underflow_then_invalid_slot_reuse`

正交缺陷：

- RTL_CONTROL：
  - GA outbuffer occupancy 下溢；
  - invalid slot stale C；
  - 跨 block feedback 初始化错误。
- CONFIG_SEMANTICS：
  - MSE4 D-index carrier 只覆盖 2 个唯一 D 地址，不能由 request 总数替代。

规则 ID：

- `CDA-GA-OUTBUFFER-OCCUPANCY-001`
- `CDA-GA-INVALID-SLOT-ISOLATION-001`
- `CDA-GA-CROSS-BLOCK-INIT-001`
- `CDA-GAP-ORTHOGONAL-DEFECTS-001`
- `CDA-GAP-D-READBACK-COVERAGE-001`
- `CDA-MSE4-MONITOR-EVIDENCE-001`
- `CDA-SERVER-FOCUSED-IDENTITY-001`

记录：`.agents/task_records/gap_hwop0071_probe_v7_rule_sync_20260724.md`

### 4.2 GAP int32_mac pure-config bypass

只完成本地数值/地址合同：

- CGRA_SIM / explicit tree / W3 golden 对 32,768 个 49 元素向量一致；
- 输出 SHA256：
  `f838df652cadb27110ed79084f49fd7e80445277d497e0d6e019c49132b73117`
- 六层 scratch、transaction、padding、terminal tag 本地闭合；
- 未生成真实六层 JSON/mapping/bitstream/execplan/SCA；
- 未做 dual-stream、stage barrier 或 16×512 formal D 动态证明。

保持 blocker：

- `B_GAP_GA_ACCUM_STATE`
- `B_GAP_INT32MAC_REAL_STAGE_ARTIFACTS`
- `B_GAP_INT32MAC_DYNAMIC_DUAL_STREAM`
- `B_GAP_INT32MAC_STAGE_BARRIER`
- `B_GAP_INT32MAC_FORMAL_READBACK`

记录：`.agents/task_records/gap_int32_mac_bypass_local_closure_20260724.md`

### 4.3 repair_v9

- ZIP SHA256：
  `4344b4166540482d12256b1a5893b8e3dbb512a74a7d735237de0ae2bf873864`
- 包含两项功能 RTL repair，只是历史 candidate；
- `candidate_release=false / E2_LOCAL_ONLY`；
- 用户已暂停 GAP repair/服务器续测，功能 RTL repair 未获当前授权；
- 不得运行、重建或把结构门称作语义通过。

记录：`.agents/task_records/gap_repair_v9_rule_sync_20260724.md`

### 4.4 可复用基础设施教训

- Python import 必须禁止生成未列入 manifest 的 `__pycache__/pyc`；
- 隔离 RUN_DIR 的相对 include 必须显式传 include 目录并在 compile 前校验目标 SHA；
- stock TB completion 观察可能不 mask-aware，不能把执行计划完成后 TB 等待误判为 RTL hang；
- observer `role=` 后空白、level qualifier 重复采样、同周期采样、解耦 request/wdata、
  pre/post-remap 地址域都必须单独处理；
- 正式 D 支配 observer 的漏配对；observer 不能以配对失败丢弃已接受的 write-data；
- snapshot/截断 log/缺 finalizer 不计正式 attempt；
- 同一动态门没有 known-good baseline 时不得称 regression。

以上已进入公共规则或专项规则；新算子任务只读取，不得复制历史事故段落或直接修改
公共规则。

## 5. 不相关算子族

旧测试修复任务没有为当前 QuantizeLinear、QLinearAdd 或 Conv/SA 提供可复用的
正式 package/pass identity。它们的新任务不得把 Dequant、Requant 或 SiLU 的通过
外推为本族通过，只能按主线派发的可信 JSON/RTL oracle 边界使用通用字段语义。
