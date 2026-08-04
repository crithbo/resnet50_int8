# Requant guard-only stock v1 预启动失败裁决

日期：2026-07-26

## 结论

`rq_node0001_guardonly_stock_v1_return.zip` 不是算子动态失败。包级和安装后
preflight 均通过，但实际事务安装器在编译前返回 125：

```text
TB probe preimage/tail/backup precondition failed
```

精确原因是包内尾文件名为
`tb_probe/requant_guard_only_path_observer_tail.svh`，而实际消费者
`package_tools/requant_node0001_server_runtime.py` 固定读取
`tb_probe/requant_mse4_guard_observer_tail.svh`。因此 `tail.is_file()` 为 false，
backup 未创建、observer 未安装，compile/simulation 均未开始。

独立裁决：

```text
status=SERVER_TEST_INFRASTRUCTURE_PRESTART_FAILURE
failure_class=SERVER_TEST_INFRASTRUCTURE_TB_PROBE_TAIL_NAME_MISMATCH
counts_as_dynamic_attempt=false
counts_as_node0001_e4=false
counts_as_node0001_e5=false
```

包内通用 finalizer 把它写成 `FIRST_DYNAMIC_FAILURE`，该标签被本次独立裁决覆盖：
没有任何 Start/Finish、accepted write 或正式 D，不能裁决 CONFIG、RTL 或数值。

## 身份与安全边界

- return ZIP：17,907 bytes；
- return SHA256：`8b20d0e6fe0b7374978a19ecaf41cdd2fbae04bb968f0707cc946333f8ba64ab`；
- compile/sim/run：125/125/125；
- Start/Finish/observer/formal D：0/0/0/0；
- pre/post/post-restore RTL tree 与 focused RTL 稳定；
- `native_return_observer.svh` 三阶段 SHA256 均为
  `47f0d66728f47c92f9f93f8cf87b47a0ff8567d587c3a099e2d03f610af09f49`。

因此服务器 RTL、TB 和 observer 均未被本包改变。旧 v1 冻结且禁止重跑。

## 修复要求

后继包必须使用全新 package/install/run/return 身份，冻结 guard JSON、码流、输入和
golden，只修安装契约。封包门新增实际消费者测试：从 exact ZIP 全新解压，调用包内
真实 `install-probe`、`verify-probe-installed`、`restore-probe`，要求 observer
逐字节恢复且包树前后 exact path/size/SHA 不变。

机器裁决：
`server_returns/rq_node0001_guardonly_stock_v1_return_analysis_20260726.json`。
