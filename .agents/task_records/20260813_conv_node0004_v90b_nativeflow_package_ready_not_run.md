# Serialized Conv node0004 v90b native-flow PACKAGE_READY_NOT_RUN

Date: 2026-08-13  
Role: `family.conv.serialized`  
Owner epoch: `2`  
Registry epoch: `6`  
Activation: `runtime-preflight-native-flow-v1`

## 上一版本进度

v88b production compile/elaboration 已通过，并由 actual compiled source 证明旧 ACK comparator
是 observer/source-identity 语义误报。v89b 改用 actual-source ACK/FIFO/aggregate/accept/MSE4/
terminal 宽因果 observer，但真实 production compile 在 unresolved
`DW_ecc`/`DW_sync`/`DW_lod`/`DW_fifo_s1_sf` 处退出，simulation 未启动。v88 与 v89 的编译差异
仍未闭合，本轮不把它归因于环境，也未恢复 module-provider probe。

## 本版本目的

fresh identity `r5_n4_hw_v90b_nativeflow` 冻结 v88 workload/actual-source 基线与 v89 的纠正后
causal target，直接执行原生 production `cd`/package-owned install/compile/sim。runner 在唯一
`# CODEX_PRODUCTION_LAUNCH` 前只初始化身份并 arm partial-return traps，不读取或盘点服务器自有
文件、目录、工具、library、RTL、TB、filelist 或 module provider。真实命令失败后，formal return
回收 actual cwd、compile/sim argv、相关 env、`SCA_CFG`/`SCA_CFG_D`、`Repeat_Num`、actual source
identity、完整 compile/sim logs、first true error、exits 与 `simulation_started`，供注册的 native-flow
differential 使用；未知 loader/start/wait/readback 保持 `SERVER_RUNTIME_UNKNOWN`。

## Frozen surface

- config/numeric/workload/golden/functional RTL/target diagnostic：冻结且未修改。
- dump profile：`DUMP_VCD=0 DUMP_FSDB=0 TB_DUMP_FSDB=0`。
- 旧 `buf_idx_queue_bp_pre` 派生 ACK comparator：未回引。
- observer：38 个 actual nets、26 个 causal roles、6 个两两可区分候选；100000000 decimal bytes
  仅 warning，无 hard byte/event/time cap、sampling、truncation 或 size deletion。

## Current local gates

- runtime-preflight non-interference：PASS；production marker exactly one；forbidden findings `[]`。
- observer contract/final ZIP/source-bound：PASS；26/26 roles，38 signals，6 candidates。
- package-local HDL lexical 与 Icarus full positive/negative：PASS。
- runner definition-before-use/compile-core：PASS。
- canonical post-sim exact final-ZIP：PASS。
- synthetic natural/timeout/nonzero/HUP/INT/TERM source-bound roundtrip：PASS。
- repeat-safe exact-owned runtime layout：PASS。
- current-epoch first-fresh independent audit：PASS；6/6 candidate coverage，uncovered `[]`。
- focused shared regression：87 PASS，1 environment skip；独立 first-fresh contract validator PASS。
- storage manager audit：PASS；pending max-per-family 满足。

## Exact publication

- pickup ZIP:
  `artifacts/operator_config_validation/r5-server-test-packages/pending/r5_n4_hw_v90b_nativeflow.zip`
  bytes `5852687`, SHA-256 `c0b2871aed019494c0526534a1aec56bc18304281cedbdd034ee14e55afbfc1e`。
- release receipt:
  `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_serialized_node0004/r5_n4_hw_v90b_nativeflow/r5_n4_hw_v90b_nativeflow.release_receipt.json`
  bytes `3046`, SHA-256 `b3848d0865367e60f8b8b608783a6893fe94205ca2c3725d16c114126bc48e69`。
- final-ZIP audit:
  `artifacts/operator_config_validation/r5-server-test-packages/pending_receipts/conv_serialized_node0004/r5_n4_hw_v90b_nativeflow/r5_n4_hw_v90b_nativeflow.final_zip_audit.json`
  bytes `4796`, SHA-256 `5b5671f890f86385e9efe13bfcdd8f1a804a6af909bfbde83d0d52ea4d3665b9`。
- current storage index:
  `artifacts/operator_config_validation/r5-server-test-packages/PACKAGE_STORAGE_INDEX.json`
  bytes `525283`, SHA-256 `fb7a59089518df6eb088693d553cf5d6e3ea0d38f839aa732d6ad958953a3822`；
  `pass=true`，serialized pending exact set 为 `[r5_n4_hw_v90b_nativeflow]`。

## Disposition and claim boundary

Status: `PACKAGE_READY_NOT_RUN`。唯一未来服务器命令：

```bash
bash r5_n4_hw_v90b_nativeflow/PREPARE_AND_RUN.sh /home/panqs/ndp/NDP_copy01
```

本轮未 upload、未取 lease、未连接或运行服务器。local PASS 不证明 production compile/simulation、
不解释 v88/v89 compile 差异，也不证明 natural terminal、formal-D、E3、E4 或 E5。

`conflicts=[]`
