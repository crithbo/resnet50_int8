# RequantizeUint8 node0001 stock-RTL E4 包生成

日期：2026-07-25

## 结论

已从冻结的 node0001 本地 E2 资产生成唯一、最小、一条命令执行的 stock-RTL E4 包。
本轮未上传、未运行服务器仿真，未修改或打包任何 `rtl/` 文件。

```text
package_name = requant_node0001_e4_stockrtl_v1
install_name = requant_node0001_two_stage_stockrtl_e4_onecmd_v1
candidate_release = false
evidence_level = E2_LOCAL_ONLY
dynamic_baseline = NO_DYNAMIC_BASELINE
remaining_blocker = B_REQUANT_SERVER_E4_E5
```

正式 ZIP：

`artifacts/operator_config_validation/r5-server-test-packages/requant_node0001_e4_stockrtl_v1.zip`

- size：`2076052` bytes；
- SHA-256：`d5147bd0ef7f4c1c69704e7c15e9eb71c594735eb06b89d171f8a9ab9e7f019d`；
- sidecar：
  `artifacts/operator_config_validation/r5-server-test-packages/requant_node0001_e4_stockrtl_v1.zip.sha256`；
- payload tree SHA-256：
  `37b2c37eaca08f7a9153cad166d9dd587613644e389a0737d4bc6c42b14bca42`。

唯一服务器命令：

```bash
bash PREPARE_AND_RUN.sh /absolute/path/to/NDP_copyXX
```

预期直接回传：

```text
requant_node0001_two_stage_stockrtl_e4_onecmd_v1_return.zip
requant_node0001_two_stage_stockrtl_e4_onecmd_v1_return.zip.sha256
```

## 读取收据

刷新后的完整收据：
`.agents/task_records/20260725_requant_node0001_e4_package_read_receipt.json`。
其中 Requant 专项规则身份为
`bb428f79966d197e1df8b63b0ed3072fbc40edd74a25a434d707e9eb0b5de4f6`，
并显式采用 `CDA-REQUANT-TRANSIENT-GUARD-E4-001`。

主要规则 ID：

- `CDA-SERVER-WORKLOAD-PROVENANCE-001`
- `CDA-SERVER-ONE-COMMAND-001`
- `CDA-SCA-D-TB-READBACK-LENGTH-001`
- `CDA-SERVER-SIGNAL-SAFE-PARTIAL-COLLECTION-001`
- `CDA-SERVER-NO-DYNAMIC-BASELINE-001`
- `CDA-SERVER-RETURN-RECEIPT-001`
- `CDA-REQUANT-QPARAM-001`
- `CDA-REQUANT-INT32-GUARD-001`
- `CDA-REQUANT-SFU-LUT-001`
- `CDA-REQUANT-TWO-STAGE-001`
- `CDA-REQUANT-ROUND-MAGIC-001`
- `CDA-REQUANT-LAYOUT-HWC8-001`
- `CDA-REQUANT-MATERIALIZED-ROUNDTRIP-001`
- `CDA-REQUANT-E4-E5-001`
- `CDA-REQUANT-TRANSIENT-GUARD-E4-001`

## alias-aware 动态门

包内严格分开三栏证据：

1. `TRANSIENT_GUARD_WRITE_OBSERVER`：128 个历史 guard shard，由 actual accepted
   MSE4 local write-data `valid && ready` 的 same-clock 只读 observer 记录；
2. `FINAL_UINT8_FORMAL_SCA_D`：128 个最终 UINT8 shard 正式回读；
3. `LAST_RESIDENT_GUARD_FORMAL_D`：28 个 slice 的最后驻留 guard 唯一地址正式回读。

SCA_D exact-set 为 156 项，不复制 alias 地址冒充历史 guard。observer 位于 `rtl/`
外，只在 compile 期间事务式拼接到 `native_return_observer.svh`，随后立即逐字节恢复。
身份阶段为：

```text
pre_install
post_probe_install
post_compile
post_run
post_restore
```

恢复失败、任一功能 RTL 字节变化、observer 缺失、重复/缺失/额外/乱序 guard write、
正式 readback 不匹配、48-stage lifecycle/barrier 不完整或 return/gate 缺失均
fail closed。

## 地址、生命周期与数据

- 24 occurrence / 48 `Start_Comp`；
- 48 个 same-mask completion fence；
- 共享 `RequantGuard.txt` 只在首次 Start 前加载一次；
- consumer intermediate preload 为 0；
- 128 个 guard input、128 个 guard intermediate、128 个 final UINT8，共 384 个
  地址范围均检查起止行；
- 最大地址行为 2351，严格小于 6144；
- 包内 preload 数据由压缩的冻结 W3 NPY 在服务器确定性物化，避免把约 414 MiB 文本
  放入上传包；
- 大型原始 readback/probe 文本保留在隔离 RUN_DIR；标准回传只带逐项行数、哈希、
  首个分歧、身份、限量日志和结果门，不带 waveform/build tree/nested archive。

## 本地验证

- 两个全新目录独立构建；
- 两份 ZIP 大小均为 2076052 bytes；
- 两份 ZIP SHA-256 均为
  `d5147bd0ef7f4c1c69704e7c15e9eb71c594735eb06b89d171f8a9ab9e7f019d`；
- ZIP bytes 逐字节相等；
- 两份 exact ZIP/sidecar validator 均通过；
- 包专项测试 `tests.test_build_requant_node0001_onecmd_server_test`：5/5 通过；
- node0001 本地 E2、全族分类和本轮包相关组合回归：20 项通过；
- 组合回归中另有 1 个既有 node0004 合同测试在导入后报告
  `node0004_requant_semantics_evidence_v1.json` 与当前输入不同；它不属于 node0001
  冻结输入或本轮包门，未在本任务中改写。

## 修改文件

- `tools/build_requant_node0001_onecmd_server_test.py`
- `tools/requant_node0001_server_runtime.py`
- `tests/test_build_requant_node0001_onecmd_server_test.py`
- `.agents/task_records/20260725_requant_node0001_e4_package_read_receipt.json`
- 本记录

服务器 E4 尚未执行，因此不能解除 `B_REQUANT_SERVER_E4_E5`。E4 正式通过后才允许
以全新的 package/install/run/return 身份生成 E5。
